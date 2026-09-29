"""Wann gilt ein Hintergrund-Job als tot? (#1118)

Drei Netze sollten haengengebliebene Jobs einfangen — die Detailabfrage im
Dashboard, die Laufanzeige und die Startup-Bereinigung. Alle drei zogen
ein zeitzonenbewusstes `updated_at` (so schreibt es `database._now`) von
einem naiven `datetime.now()` ab; der TypeError wurde geschluckt, und kein
Netz griff je. Ein toter Suchlauf blockierte danach jeden neuen Start,
weil der Startweg (#1096) kein Alter kannte.

Eine Frage, ein Ort: hier steht, wie alt ein Job ist und ab wann er als
abgebrochen gilt. Die Grenze fuer die Jobsuche folgt ihrem Zeitlimit
(`jobsuche_start.zeitlimit`): waehrend LinkedIn im zweiten Abschnitt
laeuft, meldet ein lebender Lauf bis zu 20 Minuten nichts — eine feste
15-Minuten-Grenze haette ihn abgeschossen. Ein Job, dessen Thread in
diesem Prozess noch lebt, ist nie tot.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

#: Grenze fuer Jobs ohne eigenes Zeitlimit.
STANDARD_SEK = 30 * 60
#: Spielraum ueber dem Zeitlimit der Jobsuche (Speichern, Geocoding).
PUFFER_SEK = 5 * 60
#: Status, die als "laeuft noch" gelten.
LAUFEND = ("running", "pending", "laeuft")


def zeitpunkt(text) -> datetime | None:
    """ISO-Zeitpunkt als UTC. Ohne Zone gilt die Ortszeit des Rechners
    (so schrieben aeltere Fassungen)."""
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc)


def alter_sekunden(text, jetzt: datetime | None = None) -> float | None:
    zp = zeitpunkt(text)
    if zp is None:
        return None
    return ((jetzt or datetime.now(timezone.utc)) - zp).total_seconds()


def _params(job: dict) -> dict:
    p = job.get("params") or {}
    if isinstance(p, str):
        try:
            p = json.loads(p or "{}")
        except ValueError:
            p = {}
    return p if isinstance(p, dict) else {}


def grenze_sek(job: dict) -> int:
    if job.get("job_type") == "jobsuche":
        from .jobsuche_start import zeitlimit
        return zeitlimit(_params(job).get("quellen") or []) + PUFFER_SEK
    return STANDARD_SEK


def thread_lebt(job: dict) -> bool:
    """Arbeitet in DIESEM Prozess noch ein Thread fuer den Job?"""
    kennung = str(job.get("id") or "")[:8]
    if not kennung:
        return False
    return any(t.is_alive() and t.name.startswith("pbp-")
               and not t.name.startswith("pbp-watchdog-")
               and t.name.endswith(kennung)
               for t in threading.enumerate())


def veraltet(job: dict | None, jetzt: datetime | None = None,
             mindestens_sek: int = 0) -> bool:
    if not job or job.get("status") not in LAUFEND:
        return False
    if thread_lebt(job):
        return False
    alter = alter_sekunden(job.get("updated_at") or job.get("created_at"), jetzt)
    if alter is None:
        return False
    return alter > max(grenze_sek(job), mindestens_sek)


def abschliessen(db, job: dict, jetzt: datetime | None = None) -> bool:
    """Markiert einen toten Job als Fehler — mit Grund im Klartext."""
    alter = alter_sekunden(job.get("updated_at") or job.get("created_at"), jetzt) or 0
    try:
        db.update_background_job(
            job["id"], "fehler", progress=int(job.get("progress") or 0),
            message=(f"Abgebrochen: seit {int(alter // 60)} Minuten keine Rückmeldung, "
                     "der Lauf ist nicht mehr aktiv (#1118)."))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Toten Hintergrund-Job %s nicht abgeschlossen: %s", job.get("id"), exc)
        return False
    logger.warning("Hintergrund-Job %s (%s) ohne Rückmeldung seit %d Min als abgebrochen markiert (#1118)",
                   job.get("id"), job.get("job_type"), int(alter // 60))
    return True
