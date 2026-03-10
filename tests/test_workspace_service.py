"""Unit-Tests fuer gemeinsame Workspace-Guidance."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.services.workspace_service import (  # noqa: E402
    build_workspace_summary,
    format_nav_badge,
    summarize_follow_ups,
)


def test_summarize_follow_ups_counts_due_items():
    """Faellige Nachfassaktionen werden korrekt gezaehlt."""
    data = summarize_follow_ups(
        [
            {"scheduled_date": "2026-03-08"},
            {"scheduled_date": "2026-03-10"},
            {"scheduled_date": "2026-03-09"},
        ],
        today="2026-03-09",
    )
    assert data == {"total": 3, "due": 2}


def test_format_nav_badge_limits_large_numbers():
    """Sehr grosse Zaehler werden kompakt formatiert."""
    assert format_nav_badge(0) is None
    assert format_nav_badge(7) == "7"
    assert format_nav_badge(120) == "99+"


def test_workspace_summary_without_profile_is_onboarding():
    """Ohne Profil startet die Guidance im Onboarding-Zustand."""
    data = build_workspace_summary(
        profile=None,
        jobs=[],
        applications=[],
        source_summary={"active": 0, "total": 9, "active_keys": []},
        search_status={"last_search": None, "days_ago": None, "status": "nie"},
        follow_up_summary={"total": 0, "due": 0},
    )
    assert data["has_profile"] is False
    assert data["readiness"]["stage"] == "onboarding"
    assert data["navigation"]["profile_badge"] is None


def test_workspace_summary_prioritizes_source_activation_after_profile():
    """Nach einem brauchbaren Profil kommen Quellen vor Jobsuche und Follow-ups."""
    profile = {
        "name": "Tester",
        "email": "test@example.com",
        "phone": "+49 40 123",
        "address": "Musterweg 1",
        "summary": "Kurzprofil",
        "positions": [{"projects": [{"name": "Projekt"}]}],
        "education": [{"institution": "FH"}],
        "skills": [{"name": "Python"}],
        "preferences": {"stellentyp": "festanstellung"},
        "documents": [{"filename": "cv.pdf"}],
    }
    data = build_workspace_summary(
        profile=profile,
        jobs=[],
        applications=[],
        source_summary={"active": 0, "total": 9, "active_keys": []},
        search_status={"last_search": None, "days_ago": None, "status": "nie"},
        follow_up_summary={"total": 1, "due": 1},
    )
    assert data["readiness"]["stage"] == "quellen_aktivieren"
    assert data["profile"]["completeness"] == 100


def test_workspace_summary_prioritizes_followups_when_setup_is_ready():
    """Wenn Profil, Quellen und Suche passen, gewinnen ueberfaellige Follow-ups."""
    profile = {
        "name": "Tester",
        "email": "test@example.com",
        "phone": "+49 40 123",
        "address": "Musterweg 1",
        "summary": "Kurzprofil",
        "positions": [{"projects": [{"name": "Projekt"}]}],
        "education": [{"institution": "FH"}],
        "skills": [{"name": "Python"}],
        "preferences": {"stellentyp": "festanstellung"},
        "documents": [{"filename": "cv.pdf"}],
    }
    data = build_workspace_summary(
        profile=profile,
        jobs=[{"hash": "abc"}],
        applications=[{"id": "app1"}],
        source_summary={"active": 2, "total": 9, "active_keys": ["bundesagentur", "stepstone"]},
        search_status={"last_search": "2026-03-09T10:00:00", "days_ago": 0, "status": "aktuell"},
        follow_up_summary={"total": 2, "due": 1},
    )
    assert data["readiness"]["stage"] == "nachfassen"
    assert data["navigation"]["applications_badge"] == "1"
