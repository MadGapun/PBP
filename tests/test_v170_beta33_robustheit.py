"""Tests fuer v1.7.0-beta.33 — #590 Aufgabe C: Scraper-Robustheit-Upgrade.

Auto-Reactivate-Mechanik mit exponential Backoff (24h/48h/72h/168h),
Retry-After-Respect, Health-Score-Endpoints.
"""
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta33_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= Schema v40 ==============

def test_schema_v40_columns_exist(setup_env):
    db = setup_env
    conn = db.connect()
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(scraper_health)"
    ).fetchall()}
    assert "reactivate_at" in cols
    assert "reactivate_attempt" in cols
    assert "retry_after" in cols


# ============= Auto-Reactivate-Mechanik ==============

def test_silent_threshold_sets_reactivate_at(setup_env):
    db = setup_env
    # Mehrfach silent → erreicht SILENT_AUTO_DEACTIVATE_THRESHOLD
    for _ in range(db.SILENT_AUTO_DEACTIVATE_THRESHOLD + 1):
        db.update_scraper_health("indeed", "ok", count=0, time_s=1.0)
    row = db.connect().execute(
        "SELECT is_active, reactivate_at, reactivate_attempt "
        "FROM scraper_health WHERE scraper_name=?", ("indeed",)
    ).fetchone()
    assert row["is_active"] == 0
    assert row["reactivate_at"] is not None
    assert row["reactivate_attempt"] >= 1


def test_get_scrapers_due_for_probe_returns_overdue(setup_env):
    db = setup_env
    # Setze reactivate_at in die Vergangenheit
    db.update_scraper_health("scraperA", "fail", count=0, time_s=1.0)
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    conn = db.connect()
    conn.execute(
        "UPDATE scraper_health SET is_active=0, reactivate_at=? "
        "WHERE scraper_name=?", (past, "scraperA")
    )
    conn.commit()
    due = db.get_scrapers_due_for_probe()
    names = {d["scraper_name"] for d in due}
    assert "scraperA" in names


def test_schedule_scraper_probe_success_reactivates(setup_env):
    db = setup_env
    # Erst auf is_active=0 setzen
    db.update_scraper_health("scraperB", "fail", count=0, time_s=1.0)
    db.toggle_scraper("scraperB", False)
    out = db.schedule_scraper_probe("scraperB", success=True)
    assert out["reactivated"] is True
    row = db.connect().execute(
        "SELECT is_active, reactivate_at, reactivate_attempt "
        "FROM scraper_health WHERE scraper_name=?", ("scraperB",)
    ).fetchone()
    assert row["is_active"] == 1
    assert row["reactivate_at"] is None
    assert row["reactivate_attempt"] == 0


def test_schedule_scraper_probe_failure_uses_backoff(setup_env):
    db = setup_env
    db.update_scraper_health("scraperC", "fail", count=0, time_s=1.0)
    out1 = db.schedule_scraper_probe("scraperC", success=False)
    assert out1["backoff_hours"] == 24
    assert out1["attempt"] == 1
    out2 = db.schedule_scraper_probe("scraperC", success=False)
    assert out2["backoff_hours"] == 48
    assert out2["attempt"] == 2
    out3 = db.schedule_scraper_probe("scraperC", success=False)
    assert out3["backoff_hours"] == 72
    out4 = db.schedule_scraper_probe("scraperC", success=False)
    assert out4["backoff_hours"] == 168


def test_ok_clears_reactivate_state(setup_env):
    db = setup_env
    # Erst deaktivieren, dann erfolgreichen Run melden
    for _ in range(db.SILENT_AUTO_DEACTIVATE_THRESHOLD + 1):
        db.update_scraper_health("indeed", "ok", count=0, time_s=1.0)
    db.update_scraper_health("indeed", "ok", count=15, time_s=2.0)
    row = db.connect().execute(
        "SELECT is_active, reactivate_at, reactivate_attempt "
        "FROM scraper_health WHERE scraper_name=?", ("indeed",)
    ).fetchone()
    assert row["is_active"] == 1
    assert row["reactivate_at"] is None
    assert row["reactivate_attempt"] == 0


# ============= Retry-After (HTTP 429) ==============

def test_retry_after_in_future_blocks(setup_env):
    db = setup_env
    db.update_scraper_health("linkedin", "fail", count=0, time_s=1.0)
    future = (datetime.now() + timedelta(minutes=30)).isoformat()
    db.set_scraper_retry_after("linkedin", future)
    held = db.is_scraper_held_by_retry_after("linkedin")
    assert held == future


def test_retry_after_in_past_does_not_block(setup_env):
    db = setup_env
    db.update_scraper_health("linkedin", "fail", count=0, time_s=1.0)
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    db.set_scraper_retry_after("linkedin", past)
    held = db.is_scraper_held_by_retry_after("linkedin")
    assert held is None


def test_retry_after_unset_does_not_block(setup_env):
    db = setup_env
    db.update_scraper_health("linkedin", "ok", count=10, time_s=1.0)
    held = db.is_scraper_held_by_retry_after("linkedin")
    assert held is None


# ============= API ===============

def test_api_probes_due(setup_env):
    db = setup_env
    db.update_scraper_health("scrA", "fail", count=0, time_s=1.0)
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    conn = db.connect()
    conn.execute(
        "UPDATE scraper_health SET is_active=0, reactivate_at=? "
        "WHERE scraper_name=?", (past, "scrA")
    )
    conn.commit()
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/scraper-health/probes-due")
    assert r.status_code == 200
    j = r.json()
    names = {d["scraper_name"] for d in j["due"]}
    assert "scrA" in names


def test_api_probe_result_success(setup_env):
    db = setup_env
    db.update_scraper_health("scrB", "fail", count=0, time_s=1.0)
    db.toggle_scraper("scrB", False)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/scraper-health/scrB/probe-result", json={"success": True})
    j = r.json()
    assert j["reactivated"] is True


def test_api_probe_result_failure(setup_env):
    db = setup_env
    db.update_scraper_health("scrC", "fail", count=0, time_s=1.0)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/scraper-health/scrC/probe-result",
                    json={"success": False})
    j = r.json()
    assert j["reactivated"] is False
    assert j["backoff_hours"] == 24


def test_api_retry_after_set(setup_env):
    db = setup_env
    db.update_scraper_health("scrD", "fail", count=0, time_s=1.0)
    future = (datetime.now() + timedelta(hours=2)).isoformat()
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/scraper-health/scrD/retry-after",
                    json={"retry_after": future})
    assert r.status_code == 200
    held = db.is_scraper_held_by_retry_after("scrD")
    assert held == future


def test_api_auto_actions_includes_scraper_probe(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/auto-actions/run")
    j = r.json()
    assert "scraper_probe" in j


# ============= Manueller toggle clears reactivate state ==============

def test_manual_toggle_clears_probe_plan(setup_env):
    db = setup_env
    db.update_scraper_health("scrE", "fail", count=0, time_s=1.0)
    db.schedule_scraper_probe("scrE", success=False)  # Set probe plan
    # Manual toggle on
    db.toggle_scraper("scrE", True)
    row = db.connect().execute(
        "SELECT reactivate_at, reactivate_attempt, retry_after "
        "FROM scraper_health WHERE scraper_name=?", ("scrE",)
    ).fetchone()
    assert row["reactivate_at"] is None
    assert row["reactivate_attempt"] == 0
    assert row["retry_after"] is None


# ============= Frontend ===============

def test_settings_page_uses_scraper_health_card():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "ScraperHealthCard" in content
    assert "/api/scraper-health/" in content
    assert "probe-result" in content
