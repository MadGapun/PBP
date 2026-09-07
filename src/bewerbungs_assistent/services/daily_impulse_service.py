"""Tagesimpuls-Service fuer das PBP-Dashboard (#163).

Laedt kuratierte Impulse aus einer JSON-Datei, bestimmt den aktuellen
Nutzerkontext und waehlt pro Kalendertag einen stabilen Impuls aus.
"""

import hashlib
import json
from datetime import date
from pathlib import Path

_CONTENT_PATH = Path(__file__).resolve().parent.parent / "content" / "tagesimpulse.json"
_impulse_cache: list[dict] | None = None

# Context priority (highest first).
#
# #977 (v1.7.31): `follow_up_due` steht seit dem 07.09.2026 VOR `weekend`.
# Vorher gewann der Ruhe-Kontext am Samstag auch dann, wenn etwas
# ueberfaellig war — auf einem Bildschirm stand oben "2 Aufgaben
# ueberfaellig" und unten "Heute darf es stiller sein". Ruhe darf es
# geben, sobald nichts offen ist; bei Ueberfaelligkeit ist sie keine
# Ruecksicht, sondern eine falsche Aussage.
CONTEXT_PRIORITY = [
    "follow_up_due",
    "weekend",
    "jobs_ready",
    "search_refresh",
    "sources_missing",
    "profile_building",
    "onboarding",
    "default",
]


def _load_impulse() -> list[dict]:
    """Load impulse data from JSON file (cached after first read)."""
    global _impulse_cache
    if _impulse_cache is None:
        with open(_CONTENT_PATH, encoding="utf-8") as fh:
            _impulse_cache = json.load(fh)
    return _impulse_cache


def detect_context(
    *,
    has_profile: bool,
    profile_completeness: int,
    active_sources: int,
    search_status: str,
    active_jobs: int,
    total_applications: int,
    follow_ups_due: int,
    overdue_tasks: int = 0,
    today: date | None = None,
) -> str:
    """Determine the highest-priority context from workspace signals.

    Parameters mirror what is already available from workspace_service /
    dashboard helpers.  The priority order follows the Codex plan.
    """
    today = today or date.today()

    # Offenes zuerst — auch am Wochenende (#977). `overdue_tasks` sind die
    # ueberfaelligen Todos aus `get_overdue_tasks` (D23/#683); sie speisen
    # die rote Warnung oben auf dem Dashboard und muessen denselben Impuls
    # steuern, sonst widersprechen sich zwei Bloecke desselben Bildschirms.
    if follow_ups_due > 0 or overdue_tasks > 0:
        return "follow_up_due"

    # Ruhe, sobald nichts offen ist
    if today.weekday() >= 5:
        return "weekend"

    # Jobs ready but no applications yet
    if active_jobs > 0 and total_applications == 0:
        return "jobs_ready"

    # Search needs refresh
    if has_profile and search_status in {"nie", "veraltet", "dringend"}:
        return "search_refresh"

    # No active sources
    if has_profile and active_sources == 0:
        return "sources_missing"

    # Profile incomplete
    if has_profile and profile_completeness < 60:
        return "profile_building"

    # No profile at all
    if not has_profile:
        return "onboarding"

    return "default"


def select_impulse(context: str, today: date | None = None) -> dict:
    """Pick a deterministic impulse for the given context and date.

    Filters impulse candidates by context, then uses a date+context hash
    to select a stable entry for the day.
    """
    today = today or date.today()
    all_impulse = _load_impulse()

    candidates = [imp for imp in all_impulse if context in imp.get("contexts", [])]
    if not candidates:
        # Fallback to default context
        candidates = [imp for imp in all_impulse if "default" in imp.get("contexts", [])]
    if not candidates:
        # Ultimate fallback — use everything
        candidates = all_impulse

    seed = f"{today.isoformat()}:{context}"
    idx = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(candidates)
    return candidates[idx]


def get_daily_impulse(
    *,
    enabled: bool = True,
    has_profile: bool = False,
    profile_completeness: int = 0,
    active_sources: int = 0,
    search_status: str = "nie",
    active_jobs: int = 0,
    total_applications: int = 0,
    follow_ups_due: int = 0,
    overdue_tasks: int = 0,
    today: date | None = None,
) -> dict:
    """Main entry point: return the full impulse payload for the API.

    Returns a dict with ``enabled``, ``context``, ``datum``, and
    ``impulse`` (containing ``id``, ``title``, ``text``, ``tags``).
    When disabled, ``impulse`` is ``None``.
    """
    today = today or date.today()

    if not enabled:
        return {
            "enabled": False,
            "context": None,
            "datum": today.isoformat(),
            "impulse": None,
        }

    context = detect_context(
        has_profile=has_profile,
        profile_completeness=profile_completeness,
        active_sources=active_sources,
        search_status=search_status,
        active_jobs=active_jobs,
        total_applications=total_applications,
        follow_ups_due=follow_ups_due,
        overdue_tasks=overdue_tasks,
        today=today,
    )

    chosen = select_impulse(context, today)

    return {
        "enabled": True,
        "context": context,
        "datum": today.isoformat(),
        "impulse": {
            "id": chosen["id"],
            "title": "Heute für dich",
            "text": chosen["text"],
            "tags": chosen.get("tags", []),
        },
    }
