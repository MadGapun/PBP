"""v1.7.0-beta.94 (#677/#678): Hintergrund-Scheduler fuer die Automatik.

Zwei periodische Tasks, Intervall pro Profil konfigurierbar (0 = aus):
- **lernen**: laesst Ollama die Aktivitaet/Dokumente analysieren
  (`_run_analyze_user_patterns`, #594) — der „Sofort-Lauf" automatisiert.
- **jobsuche**: startet die **interne** Jobsuche (nur Scraper-Quellen, die
  Claude-in-Chrome-/Login-Wall-Quellen aus `_MANUAL_SOURCES` bleiben aussen
  vor — die laufen weiter manuell ueber die Chrome-Extension).

Architektur: ein Daemon-Thread, der alle paar Minuten tickt. Gestartet aus
`start_dashboard` (dort ist `dashboard._db` gesetzt und es ist die EINE
Instanz mit dem Dashboard — kein Doppel-Lauf bei mehreren MCP-Prozessen).

Constraint: laeuft nur, solange der MCP-Server / Claude Desktop laeuft —
das ist kein Windows-Dienst.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_TICK_SECONDS = 300          # alle 5 Minuten pruefen
_INITIAL_DELAY = 90          # Start nicht sofort beim Hochfahren
_thread: Optional[threading.Thread] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _is_due(interval_tage: int, last_at: str, now: datetime) -> bool:
    if not interval_tage or interval_tage <= 0:
        return False
    last = _parse(last_at)
    if last is None:
        return True
    return (now - last).total_seconds() >= interval_tage * 86400


def compute_status(db) -> dict:
    """Status fuer UI/MCP: Intervall + letzter + naechster Lauf je Task."""
    s = db.get_automatik_settings()
    now = _utcnow()

    def _next(iv: int, last_at: str):
        if not iv:
            return None
        last = _parse(last_at)
        if last is None:
            return "faellig"
        due = last + timedelta(days=iv)
        return "faellig" if due <= now else due.isoformat()

    return {
        "jobsuche": {
            "intervall_tage": s["jobsuche_intervall_tage"],
            "letzter_lauf": s["jobsuche_last_at"] or None,
            "naechster_lauf": _next(s["jobsuche_intervall_tage"], s["jobsuche_last_at"]),
        },
        "lernen": {
            "intervall_tage": s["lernen_intervall_tage"],
            "letzter_lauf": s["lernen_last_at"] or None,
            "naechster_lauf": _next(s["lernen_intervall_tage"], s["lernen_last_at"]),
        },
        "hinweis": (
            "Laeuft nur solange Claude Desktop / der MCP-Server offen ist."
        ),
    }


def run_lernen_now(db, log: logging.Logger = logger) -> dict:
    """Startet den Lern-Lauf im HINTERGRUND (v1.7.11, #799).

    Vorher lief das synchron im Scheduler-Thread — inklusive des
    Ollama-Aufrufs aus `_run_analyze_user_patterns`, der bei kaltem Modell
    50-60 s braucht (#638). Da alle Threads sich EINE SQLite-Connection
    teilen (`check_same_thread=False`), zog ein haengender Lernlauf jeden
    weiteren DB-Zugriff mit — der MCP-Server war komplett blockiert.

    Jetzt wie die Jobsuche: eigener Thread, Eintrag in `background_jobs`
    mit Status/Dauer/Fehlertext. Damit hinterlaesst jeder Lauf eine Spur;
    vorher war in `background_jobs` ausschliesslich `jobsuche` zu sehen,
    obwohl die Automatik taeglich einen Lernlauf meldete.

    Zwei Stufen, in dieser Reihenfolge:
      1. REGELBASIERT (#799) — laeuft immer, braucht keine lokale KI
      2. Pattern-Analyse (#594) — self-gated, nutzt Ollama wenn verfuegbar
    Stufe 1 laeuft zuerst, damit der Nutzer auch dann Erkenntnisse
    bekommt, wenn Stufe 2 uebersprungen wird oder scheitert.
    """
    if db.get_running_background_job("lernen"):
        return {"status": "laeuft_bereits"}
    job_id = db.create_background_job("lernen", {"quelle": "automatik"})

    def _run():
        ergebnis: dict = {}
        try:
            db.update_background_job(job_id, "laeuft", progress=10,
                                     message="Regelbasierte Erkenntnisse")
            from ..services.lerninsights import kandidaten_ableiten, speichern
            from .. import __version__ as _v
            lauf = kandidaten_ableiten(db)
            ergebnis["regelbasiert"] = speichern(
                db, lauf["kandidaten"], app_version=_v)
            ergebnis["regeln_gelaufen"] = lauf["regeln_gelaufen"]
            if lauf["abgebrochen"]:
                ergebnis["regeln_uebersprungen"] = lauf["regeln_uebersprungen"]
        except Exception as exc:
            log.warning("Regelbasierte Erkenntnisse fehlgeschlagen: %s", exc)
            ergebnis["regelbasiert_fehler"] = str(exc)

        try:
            db.update_background_job(job_id, "laeuft", progress=60,
                                     message="Pattern-Analyse (lokale KI)")
            from ..dashboard import _run_analyze_user_patterns
            ergebnis["pattern_analyse"] = _run_analyze_user_patterns(
                _utcnow().isoformat())
        except Exception as exc:
            log.warning("Pattern-Analyse fehlgeschlagen: %s", exc)
            ergebnis["pattern_analyse_fehler"] = str(exc)

        fehler = [k for k in ergebnis if k.endswith("_fehler")]
        db.update_background_job(
            job_id, "fehler" if len(fehler) == 2 else "fertig",
            progress=100,
            message=("Lern-Lauf abgeschlossen" if not fehler
                     else f"Teilweise fehlgeschlagen: {', '.join(fehler)}"),
            result=ergebnis)

    threading.Thread(target=_run, daemon=True, name="automatik-lernen").start()
    return {"status": "gestartet", "job_id": job_id}


def run_jobsuche_now(db, log: logging.Logger = logger) -> dict:
    """Startet die INTERNE Jobsuche im Hintergrund (nur Scraper-Quellen).

    Manuelle/Browser-Quellen (`_MANUAL_SOURCES`) werden ausgelassen — die
    laufen weiter ueber Claude-in-Chrome.
    """
    try:
        from ..tools.jobs import _MANUAL_SOURCES
    except Exception:  # pragma: no cover
        _MANUAL_SOURCES = {}
    quellen = db.get_profile_setting("active_sources", []) or []
    auto = [q for q in quellen if q not in _MANUAL_SOURCES]
    if not auto:
        return {"status": "keine_internen_quellen"}
    if db.get_running_background_job("jobsuche"):
        return {"status": "laeuft_bereits"}
    params = {
        "keywords": None,
        "quellen": auto,
        "nur_remote": False,
        "max_entfernung_km": 0,
    }
    job_id = db.create_background_job("jobsuche", params)

    def _run():
        try:
            from ..job_scraper import run_search
            run_search(db, job_id, params)
        except Exception as exc:  # pragma: no cover
            log.warning("Automatik-Jobsuche-Fehler: %s", exc)

    threading.Thread(target=_run, daemon=True, name="automatik-jobsuche").start()
    return {"status": "gestartet", "job_id": job_id, "quellen": auto}


def _tick(db) -> None:
    s = db.get_automatik_settings()
    now = _utcnow()
    if _is_due(s["lernen_intervall_tage"], s["lernen_last_at"], now):
        logger.info("Automatik: Lern-Lauf faellig -> starte")
        run_lernen_now(db)
        db.mark_automatik_run("lernen")
    if _is_due(s["jobsuche_intervall_tage"], s["jobsuche_last_at"], now):
        logger.info("Automatik: interne Jobsuche faellig -> starte")
        res = run_jobsuche_now(db)
        # Nur als gelaufen markieren, wenn es etwas zu tun gab (gestartet)
        # oder definitiv nichts zu tun ist (keine internen Quellen) — bei
        # 'laeuft_bereits' NICHT markieren, dann beim naechsten Tick erneut.
        if res.get("status") in ("gestartet", "keine_internen_quellen"):
            db.mark_automatik_run("jobsuche")


def start_automatik_scheduler(db) -> None:
    """Startet den Daemon-Thread (idempotent)."""
    global _thread
    if _thread and _thread.is_alive():
        return

    def _loop():
        time.sleep(_INITIAL_DELAY)
        logger.info("Automatik-Scheduler gestartet (Tick alle %ds)", _TICK_SECONDS)
        while True:
            try:
                _tick(db)
            except Exception as exc:  # pragma: no cover - Loop darf nie sterben
                logger.warning("Automatik-Scheduler-Tick-Fehler: %s", exc)
            time.sleep(_TICK_SECONDS)

    _thread = threading.Thread(target=_loop, daemon=True, name="automatik-scheduler")
    _thread.start()
