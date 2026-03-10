"""Unit-Tests fuer gemeinsame Such- und Quellenlogik."""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.services.search_service import (  # noqa: E402
    build_source_rows,
    get_search_status,
    summarize_active_sources,
)


def test_get_search_status_without_timestamp():
    """Ohne Zeitstempel ist der Suchstatus 'nie'."""
    data = get_search_status(None)
    assert data == {"last_search": None, "days_ago": None, "status": "nie"}


def test_get_search_status_recent_search():
    """Frische Suchlaeufe werden als aktuell markiert."""
    now = datetime(2026, 3, 9, 12, 0, 0)
    data = get_search_status("2026-03-08T10:30:00", now=now)
    assert data["status"] == "aktuell"
    assert data["days_ago"] == 1


def test_get_search_status_invalid_timestamp():
    """Defekte Daten sollen keinen Absturz ausloesen."""
    data = get_search_status("kaputt", now=datetime(2026, 3, 9, 12, 0, 0))
    assert data["status"] == "unbekannt"
    assert data["last_search"] == "kaputt"


def test_summarize_active_sources_counts_known_keys_only():
    """Nur bekannte Registry-Keys sollen in die Aktiv-Anzahl einfliessen."""
    data = summarize_active_sources(["bundesagentur", "unbekannt"], ["bundesagentur", "stepstone"])
    assert data == {
        "active": 1,
        "total": 2,
        "active_keys": ["bundesagentur", "unbekannt"],
    }


def test_build_source_rows_marks_active_entries():
    """Quellenlisten fuer das Dashboard enthalten die Aktiv-Flags."""
    rows = build_source_rows(
        {
            "bundesagentur": {
                "name": "Bundesagentur",
                "beschreibung": "API",
                "methode": "REST API",
                "login_erforderlich": False,
            },
            "stepstone": {
                "name": "StepStone",
                "beschreibung": "Portal",
                "methode": "Playwright",
                "login_erforderlich": True,
            },
        },
        ["stepstone"],
    )
    assert rows[0]["active"] is False
    assert rows[1]["active"] is True
    assert rows[1]["login_erforderlich"] is True
