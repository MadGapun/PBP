"""Eine Jobsuche starten — ein Weg fuer Claude, Dashboard und Automatik (#1096).

Bis hierher hatte jeder Startweg seine eigene Fassung: nur der Weg ueber
Claude warnte vor Stellenarten ohne laufende Quelle (#906) und pruefte,
ob es Suchbegriffe gibt (#695); die Automatik nannte die uebersprungenen
Browser-Quellen nicht (#1049), hatte keinen Watchdog und verbuchte einen
Abbruch nicht als Fehler — der Job blieb auf "running", und jeder
manuelle Start antwortete "laeuft bereits".

Was je Herkunft gilt, steht in SCHRITTE. Alles andere gilt fuer alle.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

HERKUNFT = ("claude", "dashboard", "automatik")

#: Schritte, die nicht fuer jede Herkunft gelten. Die Automatik uebernimmt
#: keine Erstauswahl: sie startet nur mit einer vorhandenen Auswahl, und
#: eine Auswahl darf nur ein Mensch treffen.
SCHRITTE = {
    "claude": {"erstauswahl": True},
    "dashboard": {"erstauswahl": True},
    "automatik": {"erstauswahl": False},
}

#: Watchdog: Grundzeit fuer die schnellen Quellen und das Speichern. Eine
#: Suche, die danach noch nicht abgeschlossen ist, gilt als gescheitert.
ZEITLIMIT_SEK = 600
#: Langlaufende Quellen bringen ihr eigenes Budget mit (#1038): LinkedIn
#: ueber JobSpy darf bis zu `LINKEDIN_BUDGET_MAX` laufen. Mit einem festen
#: Zeitlimit von zehn Minuten meldete der Watchdog einen solchen Lauf als
#: gescheitert, waehrend die Ergebnisse noch eintrafen — und ein zweiter
#: Start lief parallel, weil der Job nicht mehr als laufend galt.
LANGLAUF_QUELLEN = frozenset({"jobspy_linkedin"})


def zeitlimit(quellen: list[str]) -> int:
    """Wie lange der Watchdog wartet, bevor er einen Lauf fuer gescheitert
    haelt: die Grundzeit plus das Hoechstbudget jeder langlaufenden Quelle."""
    limit = ZEITLIMIT_SEK
    if LANGLAUF_QUELLEN & set(quellen or ()):
        from ..job_scraper.jobspy_source import LINKEDIN_BUDGET_MAX
        limit += LINKEDIN_BUDGET_MAX
    return limit


def _stellentyp_ohne_quelle(db, laufende: list[str]) -> list[dict]:
    """#906: eine Stellenart, fuer die keine Quelle mitlaeuft."""
    try:
        from ..job_scraper import STELLENTYP_QUELLEN
        typen = (db.get_search_criteria() or {}).get("stellentypen") or []
    except Exception as exc:  # noqa: BLE001
        logger.debug("Stellentyp-Pruefung (#906): %s", exc)
        return []
    aktiv = set(laufende)
    befunde = []
    for typ in typen:
        noetig = STELLENTYP_QUELLEN.get(typ)
        if noetig and not (noetig & aktiv):
            befunde.append({"stellentyp": typ, "quellen_dafuer": sorted(noetig)})
    return befunde


def _lauf(db, job_id: str, params: dict) -> None:
    """Der Suchlauf im Thread. Jeder Abbruch wird als "fehler" verbucht."""
    from .hintergrund_status import laufender_task
    try:
        with laufender_task(f"jobsuche:{job_id[:8]}"):
            from ..job_scraper import run_search
            run_search(db, job_id, params)
            job = db.get_background_job(job_id) or {}
            if job.get("status") in ("pending", "running"):
                # run_search kehrte zurueck, ohne den Lauf abzuschliessen
                db.update_background_job(
                    job_id, "fehler",
                    message="Die Suche endete ohne Abschluss — bitte erneut starten.")
                return
            # #1038 Punkt 4: erst die Anzeigentexte der neuen Treffer, dann
            # die Aussortierung — sie ueberspringt Stellen ohne Text (#756).
            from . import text_nachzug
            try:
                text_nachzug.nach_suche(db, job_id)
            except Exception as exc:  # noqa: BLE001 — die Suche war gut
                logger.warning("Anzeigentexte nach der Suche: %s", exc)
            from . import auto_aussortierung
            try:
                auto_aussortierung.nach_suche(db, job_id)  # #1092, Schalter
            except Exception as exc:  # noqa: BLE001 — die Suche war gut
                logger.warning("Auto-Aussortierung nach der Suche: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Jobsuche fehlgeschlagen (%s): %s", params.get("herkunft"), exc,
                     exc_info=True)
        db.update_background_job(job_id, "fehler",
                                 message=f"Suche abgebrochen: {exc}")


def starten(db, quellen: list[str] | None = None, keywords: list[str] | None = None,
            herkunft: str = "claude") -> dict:
    """Startet den internen Suchlauf. Liefert immer ein dict mit `status`:
    keine_quellen, keine_suchbegriffe, nur_manuelle_quellen, laeuft_bereits
    oder gestartet — und `schritte`, was gelaufen ist."""
    if herkunft not in HERKUNFT:
        raise ValueError(f"Unbekannte Herkunft {herkunft!r}")
    from ..tools.jobs import _MANUAL_SOURCES
    from .search_service import aktive_quellen
    schritte: list[str] = []

    quellen = list(quellen or [])
    if not quellen:
        quellen = aktive_quellen(db) or []
    if not quellen:
        return {"status": "keine_quellen", "schritte": schritte}

    # #695: ohne Suchbegriffe faellt z.B. die Bundesagentur still auf
    # generische Begriffe zurueck und flutet die Liste.
    if not keywords:
        crit = db.get_search_criteria() or {}
        if not (crit.get("keywords_muss") or crit.get("keywords_plus")):
            return {"status": "keine_suchbegriffe", "schritte": schritte}

    manuelle = [q for q in quellen if q in _MANUAL_SOURCES]
    auto = [q for q in quellen if q not in _MANUAL_SOURCES]
    manuelle_info = {q: _MANUAL_SOURCES[q] for q in manuelle}
    schritte.append("browser_quellen")
    if not auto:
        return {"status": "nur_manuelle_quellen", "manuelle_quellen": manuelle_info,
                "schritte": schritte}

    uebernommen = False
    if SCHRITTE[herkunft]["erstauswahl"]:
        schritte.append("erstauswahl")
        try:
            if not db.get_profile_setting("active_sources", []):
                from ..job_scraper import SOURCE_REGISTRY
                from .search_service import ohne_defekte
                auswahl = ohne_defekte(auto, SOURCE_REGISTRY)  # #1039
                if auswahl:
                    db.set_profile_setting("active_sources", auswahl)
                    uebernommen = True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Erstauswahl der Quellen: %s", exc)

    laufend = db.get_running_background_job("jobsuche")
    # #1118: ein Eintrag, der laenger als das Zeitlimit des Laufs keine
    # Rueckmeldung gab und dessen Thread nicht mehr lebt, ist abgebrochen.
    # Er blockierte sonst jeden neuen Start — Claude, Knopf und Automatik —,
    # und kein Werkzeug schloss ihn ab.
    from .hintergrund_alter import abschliessen, veraltet
    for _ in range(5):
        if not (laufend and veraltet(laufend)):
            break
        abschliessen(db, laufend)
        schritte.append("toten_lauf_abgeschlossen")
        laufend = db.get_running_background_job("jobsuche")
    if laufend:
        return {"status": "laeuft_bereits", "job_id": laufend["id"], "schritte": schritte}

    ohne_quelle = _stellentyp_ohne_quelle(db, auto)
    schritte.append("stellentyp_pruefung")
    params = {
        "keywords": keywords,
        "quellen": auto,
        "browser_quellen": manuelle,         # #1049: im Lauf-Hinweis
        "stellentyp_ohne_quelle": ohne_quelle,  # #906: im Lauf-Hinweis
        "herkunft": herkunft,
    }
    job_id = db.create_background_job("jobsuche", params)

    thread = threading.Thread(target=_lauf, args=(db, job_id, params), daemon=True,
                              name=f"pbp-jobsuche-{job_id[:8]}")
    thread.start()
    schritte += ["nachlauf", "watchdog"]

    grenze = zeitlimit(auto)

    def _watchdog():
        thread.join(timeout=grenze)
        if not thread.is_alive():
            return
        # Nach dem Suchlauf arbeitet derselbe Thread weiter (Anzeigentexte
        # nachladen, Auto-Aussortierung). Ist die Suche selbst schon
        # abgeschlossen, ist das kein gescheiterter Lauf.
        job = db.get_background_job(job_id) or {}
        if job.get("status") not in ("pending", "running"):
            return
        logger.warning("Jobsuche Timeout nach %s s (Job %s)", grenze, job_id)
        db.update_background_job(job_id, "fehler",
                                 message=f"Zeitlimit von {grenze // 60} Minuten überschritten")

    threading.Thread(target=_watchdog, daemon=True,
                     name=f"pbp-watchdog-{job_id[:8]}").start()

    return {"status": "gestartet", "job_id": job_id, "quellen": auto,
            "manuelle_quellen": manuelle_info, "quellen_uebernommen": uebernommen,
            "stellentyp_ohne_quelle": ohne_quelle, "schritte": schritte}
