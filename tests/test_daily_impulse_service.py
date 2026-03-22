"""Tests fuer den Tagesimpuls-Service (#163)."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.services.daily_impulse_service import (
    detect_context,
    get_daily_impulse,
    select_impulse,
    _load_impulse,
)


# --- Content loading ---

class TestContentLoading:
    def test_loads_140_entries(self):
        data = _load_impulse()
        assert len(data) == 140

    def test_each_entry_has_required_fields(self):
        for entry in _load_impulse():
            assert "id" in entry
            assert "text" in entry
            assert "tags" in entry
            assert "contexts" in entry
            assert isinstance(entry["contexts"], list)
            assert len(entry["contexts"]) > 0


# --- Context detection ---

class TestDetectContext:
    def test_weekend_has_highest_priority(self):
        # Saturday
        result = detect_context(
            has_profile=True,
            profile_completeness=80,
            active_sources=3,
            search_status="aktuell",
            active_jobs=5,
            total_applications=2,
            follow_ups_due=3,
            today=date(2026, 3, 21),  # Saturday
        )
        assert result == "weekend"

    def test_follow_up_due(self):
        result = detect_context(
            has_profile=True,
            profile_completeness=80,
            active_sources=3,
            search_status="aktuell",
            active_jobs=5,
            total_applications=2,
            follow_ups_due=2,
            today=date(2026, 3, 23),  # Monday
        )
        assert result == "follow_up_due"

    def test_jobs_ready(self):
        result = detect_context(
            has_profile=True,
            profile_completeness=80,
            active_sources=3,
            search_status="aktuell",
            active_jobs=5,
            total_applications=0,
            follow_ups_due=0,
            today=date(2026, 3, 23),
        )
        assert result == "jobs_ready"

    def test_search_refresh(self):
        result = detect_context(
            has_profile=True,
            profile_completeness=80,
            active_sources=3,
            search_status="veraltet",
            active_jobs=0,
            total_applications=0,
            follow_ups_due=0,
            today=date(2026, 3, 23),
        )
        assert result == "search_refresh"

    def test_sources_missing(self):
        result = detect_context(
            has_profile=True,
            profile_completeness=80,
            active_sources=0,
            search_status="aktuell",
            active_jobs=0,
            total_applications=0,
            follow_ups_due=0,
            today=date(2026, 3, 23),
        )
        assert result == "sources_missing"

    def test_profile_building(self):
        result = detect_context(
            has_profile=True,
            profile_completeness=40,
            active_sources=2,
            search_status="aktuell",
            active_jobs=0,
            total_applications=0,
            follow_ups_due=0,
            today=date(2026, 3, 23),
        )
        assert result == "profile_building"

    def test_onboarding(self):
        result = detect_context(
            has_profile=False,
            profile_completeness=0,
            active_sources=0,
            search_status="nie",
            active_jobs=0,
            total_applications=0,
            follow_ups_due=0,
            today=date(2026, 3, 23),
        )
        assert result == "onboarding"

    def test_default(self):
        result = detect_context(
            has_profile=True,
            profile_completeness=80,
            active_sources=3,
            search_status="aktuell",
            active_jobs=5,
            total_applications=3,
            follow_ups_due=0,
            today=date(2026, 3, 23),
        )
        assert result == "default"


# --- Selection stability ---

class TestSelectImpulse:
    def test_same_day_same_impulse(self):
        day = date(2026, 3, 22)
        result1 = select_impulse("default", day)
        result2 = select_impulse("default", day)
        assert result1["id"] == result2["id"]

    def test_different_day_can_differ(self):
        """Different days should generally produce different impulses."""
        results = set()
        for offset in range(10):
            day = date(2026, 1, 1 + offset)
            results.add(select_impulse("default", day)["id"])
        # At least 2 different impulses over 10 days
        assert len(results) >= 2

    def test_different_context_can_differ(self):
        day = date(2026, 3, 22)
        result_default = select_impulse("default", day)
        result_weekend = select_impulse("weekend", day)
        # They use different candidate pools so they should typically differ
        # (but we only assert both return valid results)
        assert "id" in result_default
        assert "id" in result_weekend

    def test_fallback_on_unknown_context(self):
        result = select_impulse("nonexistent_context", date(2026, 3, 22))
        assert "id" in result
        assert "text" in result


# --- Full API payload ---

class TestGetDailyImpulse:
    def test_disabled_returns_null_impulse(self):
        result = get_daily_impulse(enabled=False)
        assert result["enabled"] is False
        assert result["impulse"] is None

    def test_enabled_returns_full_payload(self):
        result = get_daily_impulse(
            enabled=True,
            has_profile=True,
            profile_completeness=80,
            active_sources=3,
            search_status="aktuell",
            active_jobs=5,
            total_applications=3,
            follow_ups_due=0,
            today=date(2026, 3, 23),
        )
        assert result["enabled"] is True
        assert result["context"] == "default"
        assert result["datum"] == "2026-03-23"
        assert result["impulse"]["id"].startswith("impuls_")
        assert result["impulse"]["title"] == "Heute für dich"
        assert len(result["impulse"]["text"]) > 0
        assert isinstance(result["impulse"]["tags"], list)

    def test_weekend_context_in_payload(self):
        result = get_daily_impulse(
            enabled=True,
            has_profile=True,
            profile_completeness=80,
            active_sources=3,
            search_status="aktuell",
            active_jobs=5,
            total_applications=3,
            follow_ups_due=0,
            today=date(2026, 3, 21),  # Saturday
        )
        assert result["context"] == "weekend"

    def test_stable_across_calls(self):
        kwargs = dict(
            enabled=True,
            has_profile=True,
            profile_completeness=80,
            active_sources=3,
            search_status="aktuell",
            active_jobs=5,
            total_applications=3,
            follow_ups_due=0,
            today=date(2026, 3, 23),
        )
        r1 = get_daily_impulse(**kwargs)
        r2 = get_daily_impulse(**kwargs)
        assert r1["impulse"]["id"] == r2["impulse"]["id"]
        assert r1["impulse"]["text"] == r2["impulse"]["text"]
