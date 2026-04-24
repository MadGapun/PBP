"""Smoke tests for Adapter-v2-Flip (#499).

Verifiziert, dass
- alle `_SCRAPER_MAP`-Eintraege einen Adapter haben,
- der Orchestrator Fehler isoliert,
- das Feature-Flag `scraper_adapter_v2` die run_search-Pipeline
  transparent auf den Adapter-Pfad umleitet.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.job_scraper import _SCRAPER_MAP, run_search  # noqa: E402
from bewerbungs_assistent.job_scraper.adapters import (  # noqa: E402
    AdapterResult,
    AdapterStatus,
    JobPosting,
    available_adapters,
    get_adapter,
    run_adapters,
)
from bewerbungs_assistent.job_scraper.adapters.legacy_adapter import (  # noqa: E402
    LegacyScraperAdapter,
)


def test_every_scraper_map_source_has_adapter():
    """Jede Quelle in _SCRAPER_MAP muss ueber die Registry adressierbar sein."""
    registered = set(available_adapters())
    missing = set(_SCRAPER_MAP.keys()) - registered
    assert not missing, f"Adapter fehlen fuer: {sorted(missing)}"


def test_legacy_adapter_wraps_search_function():
    """LegacyScraperAdapter ruft die echte Funktion, mappt auf JobPosting."""
    adapter = LegacyScraperAdapter("fake", "bundesagentur", "search_bundesagentur")

    with patch("bewerbungs_assistent.job_scraper.bundesagentur.search_bundesagentur",
               return_value=[{
                   "hash": "h1", "title": "T", "company": "C", "location": "Hamburg",
                   "url": "", "source": "bundesagentur",
               }]):
        result = adapter.search({"keywords": ["Python"]})

    assert result.status == AdapterStatus.OK
    assert result.count == 1
    assert isinstance(result.postings[0], JobPosting)
    assert result.postings[0].hash == "h1"


def test_legacy_adapter_isolates_exceptions():
    """Wirft der Scraper, liefert der Adapter ERROR statt zu crashen."""
    adapter = LegacyScraperAdapter("fake", "bundesagentur", "search_bundesagentur")

    with patch("bewerbungs_assistent.job_scraper.bundesagentur.search_bundesagentur",
               side_effect=RuntimeError("boom")):
        result = adapter.search({})

    assert result.status == AdapterStatus.ERROR
    assert "boom" in (result.message or "")
    assert result.count == 0


def test_orchestrator_isolates_crashing_adapter():
    """Ein kaputter Adapter reisst die anderen nicht mit."""

    class _Crasher:
        source_key = "crash"

        def search(self, params):
            raise ValueError("kaputt")

        def test_connection(self):
            return AdapterStatus.ERROR

    with patch("bewerbungs_assistent.job_scraper.adapters.orchestrator.get_adapter",
               side_effect=lambda k: _Crasher() if k == "crash" else None):
        out = run_adapters(["crash", "unknown"], {})

    assert out["crash"].status == AdapterStatus.ERROR
    assert "kaputt" in (out["crash"].message or "")
    assert out["unknown"].status == AdapterStatus.NOT_CONFIGURED


def test_bundesagentur_adapter_registered():
    """Spezialisierter Adapter darf generischen Eintrag ueberschreiben."""
    from bewerbungs_assistent.job_scraper.adapters.bundesagentur_adapter import (
        BundesagenturAdapter,
    )
    adapter = get_adapter("bundesagentur")
    assert isinstance(adapter, BundesagenturAdapter)


def test_run_search_uses_legacy_path_by_default(tmp_path, monkeypatch):
    """Ohne Flag laeuft die alte Pipeline — adapter_pfad=='legacy'."""
    monkeypatch.delenv("PBP_FEATURES", raising=False)
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    try:
        from bewerbungs_assistent.database import Database
        db = Database(db_path=tmp_path / "t.db")
        db.initialize()
        job_id = db.create_background_job("jobsuche", {})

        # Scraper-Aufrufe leer halten
        with patch(
            "bewerbungs_assistent.job_scraper.bundesagentur.search_bundesagentur",
            return_value=[],
        ):
            run_search(db, job_id, {"quellen": ["bundesagentur"], "keywords": ["x"]})

        row = db.get_background_job(job_id)
        result = row["result"] if isinstance(row["result"], dict) else {}
        assert result.get("adapter_pfad") == "legacy"
        db.close()
    finally:
        os.environ.pop("BA_DATA_DIR", None)


def test_run_search_uses_adapter_path_when_flag_enabled(tmp_path, monkeypatch):
    """Flag=scraper_adapter_v2 routet ueber run_adapters-Pfad."""
    monkeypatch.setenv("PBP_FEATURES", "scraper_adapter_v2")
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    try:
        from bewerbungs_assistent.database import Database
        db = Database(db_path=tmp_path / "t.db")
        db.initialize()
        job_id = db.create_background_job("jobsuche", {})

        fake = [{
            "hash": "h2", "title": "Adapter-Flip Test", "company": "X",
            "location": "Remote", "url": "", "source": "bundesagentur",
        }]
        with patch(
            "bewerbungs_assistent.job_scraper.bundesagentur.search_bundesagentur",
            return_value=fake,
        ) as call:
            run_search(db, job_id, {"quellen": ["bundesagentur"], "keywords": ["x"]})
            assert call.called

        row = db.get_background_job(job_id)
        result = row["result"] if isinstance(row["result"], dict) else {}
        assert result.get("adapter_pfad") == "v2"
        # Scraper-Call kam durch den Adapter-Pfad: Status zeigt Count >= 1.
        ba_status = result.get("quellen_status", {}).get("bundesagentur", {})
        assert ba_status.get("status") == "ok"
        assert ba_status.get("count", 0) >= 1
        db.close()
    finally:
        os.environ.pop("BA_DATA_DIR", None)
