"""Der Nachlernlauf „KI lernt nach“ (#1396): im Leerlauf, in Portionen, blind.

Eine Entscheidung von Mensch oder Claude, die die lokale KI nie gesehen hat,
ist ein Lernstoff: die KI bewertet die Stelle BLIND (ohne die Entscheidung zu
kennen und ohne die Stelle selbst unter den Beispielen), PBP vergleicht
(`ki_lernen.nach_entscheidung`), speichert `ollama_lag_richtig`, und eine
Abweichung wird zum Gegenbeispiel, das der Prompt kuenftig bevorzugt zeigt.

Grundfunktion, kein eigener Schalter: der Lauf startet von selbst, sobald die
lokale KI eingeschaltet ist (der bestehende KI-Schalter `llm_local_state`).
Bei ausgeschalteter KI gibt es keine Laeufe und keine Wartezeiten; die Marker
werden trotzdem gefuehrt (`ki_lernen`).

Rahmen, damit PBP nicht merklich langsamer wird (der Start wird nie gebremst;
der Scheduler wartet ohnehin 90 s und tickt alle 5 Minuten):

* nur im Leerlauf: nie neben Jobsuche, Lernlauf, Aufraeum-Runde, Installation
  oder einem laufenden Claude-Werkzeug (`datenordner.laufende_arbeit`);
* eine Portion hoechstens `PORTION_STELLEN` Stellen und `PORTION_SEKUNDEN`
  Sekunden, in der Woche hoechstens `WOCHENBUDGET` Stellen;
* nach zwei Fehlern in Folge endet die Portion (die KI ist dann nicht erreichbar);
* der Thread heisst `pbp-ki-nachlernen`: Loeschen und Speicher-Aufraeumen
  warten auf ihn, und die Test-Suite beendet ihn vor dem Schliessen der DB.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("bewerbungs_assistent.ki_nachlernen")

PORTION_STELLEN = 6
PORTION_SEKUNDEN = 100
WOCHENBUDGET = 150
#: Vermerk der Zeitpunkte der letzten Woche (`*_cache`: ein Vermerk des
#: Programms, keine Einstellung des Menschen - der Loeschbereich zaehlt ihn nicht).
BUDGET_SCHLUESSEL = "ki_nachlernen_cache"
THREAD_NAME = "pbp-ki-nachlernen"
MIN_TEXT = 50


def ki_an(db) -> bool:
    """Der bestehende KI-Schalter: nur `active` heisst eingeschaltet."""
    try:
        return str(db.get_profile_setting("llm_local_state", "off")) == "active"
    except Exception:
        return False


def _kandidaten_zeilen(db, limit: int) -> list:
    conn = db.connect()
    pid = db.get_active_profile_id()
    return conn.execute(
        "SELECT hash, title, company, description, is_active, dismiss_reason, "
        "dismissed_by, entschieden_von, zurueckgeholt_am, analyse_urteil, "
        "analyse_begruendung, dismiss_note FROM jobs "
        "WHERE (profile_id=? OR profile_id IS NULL) "
        "AND entschieden_von IN ('mensch','claude') AND ollama_gesehen_am IS NULL "
        "AND length(COALESCE(description,'')) >= ? "
        "ORDER BY CASE WHEN COALESCE(analyse_begruendung,'') != '' THEN 0 "
        "WHEN COALESCE(dismiss_note,'') != '' THEN 1 ELSE 2 END, updated_at DESC "
        "LIMIT ?", (pid, MIN_TEXT, int(limit))).fetchall()


def kandidaten(db, limit: int = PORTION_STELLEN) -> list:
    """Entschiedene Stellen mit Anzeigentext, die die KI noch nie gesehen hat.

    Bevorzugt: mit Begruendung (Claude-Urteil, Notiz des Menschen). Nur
    Entscheidungen, die als Beispiel taugen (`entscheidungsklasse`)."""
    from .ki_lernen import entscheidungsklasse
    treffer = []
    for z in _kandidaten_zeilen(db, limit * 8):
        if entscheidungsklasse(z):
            treffer.append(dict(z))
        if len(treffer) >= limit:
            break
    return treffer


def _budget_zeitpunkte(db) -> list:
    grenze = datetime.now(timezone.utc) - timedelta(days=7)
    alle = (db.get_setting(BUDGET_SCHLUESSEL, {}) or {}).get("zeitpunkte", [])
    behalten = []
    for z in alle:
        try:
            if datetime.fromisoformat(z) >= grenze:
                behalten.append(z)
        except (TypeError, ValueError):
            continue
    return behalten


def _budget_verbucht(db, n: int) -> None:
    jetzt = datetime.now(timezone.utc).isoformat()
    z = _budget_zeitpunkte(db) + [jetzt] * n
    db.set_setting(BUDGET_SCHLUESSEL, {"zeitpunkte": z[-WOCHENBUDGET * 2:]})


def wochenbudget_rest(db, wochenbudget: int = WOCHENBUDGET) -> int:
    return max(0, wochenbudget - len(_budget_zeitpunkte(db)))


def andere_arbeit() -> list:
    """Was gerade sonst im Hintergrund laeuft (leer = Leerlauf)."""
    try:
        from .datenordner import laufende_arbeit
        return list(laufende_arbeit())  # auch eine noch laufende Portion dieses Laufs
    except Exception:  # pragma: no cover
        return []


def portion(db, svc=None, max_stellen: int = PORTION_STELLEN,
            max_dauer_sek: int = PORTION_SEKUNDEN,
            wochenbudget: int = WOCHENBUDGET) -> dict:
    """Eine Portion Nachlernen. Gibt immer ein Ergebnis zurueck, wirft nie."""
    erg = {"status": "ok", "geprueft": 0, "richtig": 0, "falsch": 0,
           "unsicher": 0, "fehler": 0}
    try:
        if not ki_an(db):
            return {**erg, "status": "ki_aus"}
        rest = wochenbudget_rest(db, wochenbudget)
        if rest <= 0:
            return {**erg, "status": "wochenbudget"}
        todo = kandidaten(db, min(max_stellen, rest))
        if not todo:
            return {**erg, "status": "nichts_zu_tun"}
        from . import auto_aussortierung as aa, ki_beispiele, ki_lernen
        from .llm_service import TaskKind, get_llm_service
        svc = svc or get_llm_service(db)
        status = svc.get_status()
        if not status.ollama_available or not status.available_models:
            return {**erg, "status": "ki_nicht_erreichbar"}
        try:
            svc.warmup()
        except Exception as exc:  # nicht fatal: ein warmes Modell antwortet auch so
            logger.debug("Warmup (Nachlernen): %s", exc)
        kontext = aa.profil_kontext(db.get_profile() or {})
        top = aa.anti_muster_top(db)
        pool = ki_beispiele.pool_laden(db)
        start = time.monotonic()
        folgefehler = 0
        verbucht = 0
        conn = db.connect()
        for job in todo:
            if time.monotonic() - start >= max_dauer_sek:
                erg["status"] = "teilweise"
                break
            payload = {
                **kontext,
                "job_title": job.get("title") or "",
                "job_company": job.get("company") or "",
                "job_description": (job.get("description") or "")[:1500],
                "dismiss_reasons_top": top,
                # BLIND: die Stelle selbst ist nie ihr eigenes Beispiel
                # (`ki_beispiele.waehlen` schliesst sie aus), ihre Entscheidung
                # steht nirgends im Prompt.
                "lern_beispiele": ki_beispiele.beispiele_fuer(db, job, pool=pool),
            }
            try:
                res = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, payload)
            except Exception as exc:
                logger.warning("Nachlernen: Aufruf fehlgeschlagen: %s", exc)
                res = None
            if res is None or not res.success:
                erg["fehler"] += 1
                folgefehler += 1
                if folgefehler >= 2:
                    erg["status"] = "abgebrochen"
                    break
                continue
            folgefehler = 0
            antwort = res.payload or {}
            urteil = antwort.get("decision", "UNSICHER")
            ki_lernen.ollama_gesehen(
                conn, job["hash"], urteil, antwort.get("reason") or "",
                antwort.get("sicherheit", "klar"))
            lag = ki_lernen.nach_entscheidung(conn, job["hash"])
            erg["geprueft"] += 1
            verbucht += 1
            if lag == 1:
                erg["richtig"] += 1
            elif lag == 0:
                erg["falsch"] += 1
            else:
                erg["unsicher"] += 1
        if verbucht:
            _budget_verbucht(db, verbucht)
        erg["dauer_sek"] = round(time.monotonic() - start, 1)
    except Exception as exc:  # pragma: no cover - der Lauf darf nie den Scheduler stoeren
        logger.warning("Nachlernen: %s", exc)
        erg["status"] = "fehler"
        erg["fehler_text"] = str(exc)[:200]
    return erg


def _offene_stellen(db) -> int:
    conn = db.connect()
    pid = db.get_active_profile_id()
    return conn.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM jobs WHERE (profile_id=? OR profile_id IS NULL) "
        "AND entschieden_von IN ('mensch','claude') AND ollama_gesehen_am IS NULL "
        "AND length(COALESCE(description,'')) >= ? LIMIT 1)", (pid, MIN_TEXT)).fetchone()[0]


def tick(db, log: logging.Logger = logger) -> dict:
    """Vom Scheduler gerufen: startet hoechstens eine Portion im Hintergrund.

    Billig, wenn es nichts zu tun gibt: bei ausgeschalteter KI kommt sofort
    `ki_aus` zurueck, ohne Abfrage der KI, ohne Warten."""
    if not ki_an(db):
        return {"status": "ki_aus"}
    if wochenbudget_rest(db) <= 0:
        return {"status": "wochenbudget"}
    if not _offene_stellen(db):
        return {"status": "nichts_zu_tun"}
    busy = andere_arbeit()
    if busy:
        return {"status": "beschaeftigt", "arbeit": busy}

    def _run():
        job_id = None
        try:
            ergebnis = portion(db)
            if ergebnis["status"] in ("ki_nicht_erreichbar", "ki_aus", "nichts_zu_tun",
                                      "wochenbudget"):
                return  # nichts getan: auch keine Zeile im Protokoll der Hintergrundarbeit
            job_id = db.create_background_job("ki_nachlernen", {"quelle": "automatik"})
            db.update_background_job(
                job_id, "fehler" if ergebnis["status"] in ("fehler", "abgebrochen") else "fertig",
                progress=100,
                message=(f"KI lernt nach: {ergebnis['geprueft']} Stellen verglichen, "
                         f"{ergebnis['falsch']} Abweichungen"),
                result=ergebnis)
        except Exception as exc:  # noqa: BLE001 - der Thread darf nie still sterben
            log.warning("KI lernt nach: %s", exc)
            if job_id:
                try:
                    db.update_background_job(job_id, "fehler", message=f"Abbruch: {exc}")
                except Exception:  # pragma: no cover
                    pass

    threading.Thread(target=_run, daemon=True, name=THREAD_NAME).start()
    return {"status": "gestartet"}
