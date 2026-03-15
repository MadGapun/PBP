"""Gemeinsame Such- und Quellenlogik fuer Dashboard und weitere Services."""

from datetime import datetime


def get_search_status(last_search_at: str | None, now: datetime | None = None) -> dict:
    """Normalize the stored last-search timestamp into a UI-friendly status."""
    if not last_search_at:
        return {"last_search": None, "days_ago": None, "status": "nie"}

    current_time = now or datetime.now()
    try:
        dt = datetime.fromisoformat(last_search_at)
        days = (current_time - dt).days
    except (ValueError, TypeError):
        return {"last_search": last_search_at, "days_ago": None, "status": "unbekannt"}

    status = "aktuell" if days == 0 else "veraltet" if days < 7 else "dringend"
    return {"last_search": last_search_at, "days_ago": days, "status": status}


def summarize_active_sources(active_keys, available_keys) -> dict:
    """Count active sources relative to the known registry keys."""
    active_list = list(active_keys or [])
    active_set = set(active_list)
    keys = list(available_keys)
    active_count = sum(1 for key in keys if key in active_set)
    return {
        "active": active_count,
        "total": len(keys),
        "active_keys": active_list,
    }


def build_source_rows(source_registry: dict, active_keys) -> list:
    """Build dashboard-friendly source rows with active flags."""
    active_set = set(active_keys or [])
    return [
        {
            "key": key,
            "name": info["name"],
            "beschreibung": info["beschreibung"],
            "methode": info["methode"],
            "login_erforderlich": info["login_erforderlich"],
            "active": key in active_set,
        }
        for key, info in source_registry.items()
    ]
