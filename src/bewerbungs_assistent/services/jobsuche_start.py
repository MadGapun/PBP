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

#: Watchdog: ein Lauf, der danach noch lebt, gilt als gescheitert.
ZEITLIMIT_SEK = 600


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

    def _watchdog():
        thread.join(timeout=ZEITLIMIT_SEK)
        if thread.is_alive():
            logger.warning("Jobsuche Timeout nach %s s (Job %s)", ZEITLIMIT_SEK, job_id)
            db.update_background_job(job_id, "fehler",
                                     message=f"Zeitlimit von {ZEITLIMIT_SEK // 60} Minuten überschritten")

    threading.Thread(target=_watchdog, daemon=True,
                     name=f"pbp-watchdog-{job_id[:8]}").start()

    return {"status": "gestartet", "job_id": job_id, "quellen": auto,
            "manuelle_quellen": manuelle_info, "quellen_uebernommen": uebernommen,
            "stellentyp_ohne_quelle": ohne_quelle, "schritte": schritte}
