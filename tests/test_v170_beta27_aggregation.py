"""Tests fuer v1.7.0-beta.27 — #594 Stufe 2: Aggregation + Anti-Pattern."""
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta27_")
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


def _seed_events(db, events):
    """Hilfs-Funktion: Events direkt einfuegen."""
    db.add_activity_events_batch(events)


# ============= Aggregation ===============

def test_aggregate_returns_empty_when_no_events(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/activity/aggregate?days=30")
    j = r.json()
    assert j["total_events"] == 0
    assert j["top_pages"] == []
    assert j["anti_patterns"] == []


def test_aggregate_top_pages(setup_env):
    db = setup_env
    _seed_events(db, [
        {"event_type": "page_view", "page": "stellen"},
        {"event_type": "page_view", "page": "stellen"},
        {"event_type": "page_view", "page": "bewerbungen"},
        {"event_type": "click", "page": "stellen", "action": "filter"},
        {"event_type": "click", "page": "stellen", "action": "filter"},
        {"event_type": "click", "page": "stellen", "action": "filter"},
        {"event_type": "dwell", "page": "stellen",
         "metadata": {"duration_ms": 60000}},
        {"event_type": "dwell", "page": "bewerbungen",
         "metadata": {"duration_ms": 30000}},
    ])
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/activity/aggregate")
    j = r.json()
    assert j["total_events"] == 8
    pages = {p["page"]: p for p in j["top_pages"]}
    assert pages["stellen"]["views"] == 2
    assert pages["stellen"]["clicks"] == 3
    assert pages["stellen"]["dwell_minutes"] == 1.0
    assert pages["bewerbungen"]["dwell_minutes"] == 0.5


def test_aggregate_workflow_stats(setup_env):
    db = setup_env
    _seed_events(db, [
        {"event_type": "workflow_start", "action": "bewerbung_erstellen"},
        {"event_type": "workflow_complete", "action": "bewerbung_erstellen"},
        {"event_type": "workflow_start", "action": "bewerbung_erstellen"},
        {"event_type": "workflow_abort", "action": "bewerbung_erstellen"},
    ])
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    j = client.get("/api/activity/aggregate").json()
    wf = j["workflow_stats"]["bewerbung_erstellen"]
    assert wf["start"] == 2
    assert wf["complete"] == 1
    assert wf["abort"] == 1


def test_aggregate_top_filters(setup_env):
    db = setup_env
    _seed_events(db, [
        {"event_type": "filter_apply",
         "metadata": {"filter": "score_min", "value": "70"}},
        {"event_type": "filter_apply",
         "metadata": {"filter": "score_min", "value": "80"}},
        {"event_type": "filter_apply",
         "metadata": {"filter": "remote_only", "value": "true"}},
    ])
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    j = client.get("/api/activity/aggregate").json()
    filters = {f["filter"]: f["count"] for f in j["top_filters"]}
    assert filters["score_min"] == 2
    assert filters["remote_only"] == 1


def test_aggregate_dismiss_reasons_from_jobs(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    for hash_, reason in [
        ("h1", "falsches_fachgebiet"),
        ("h2", "falsches_fachgebiet"),
        ("h3", "zu_weit_entfernt"),
    ]:
        conn.execute(
            "INSERT INTO jobs (hash, profile_id, title, source, "
            "dismiss_reason, is_active) VALUES (?, ?, ?, ?, ?, 0)",
            (hash_, pid, "T", "test", reason)
        )
    conn.commit()
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    j = client.get("/api/activity/aggregate").json()
    reasons = {r["reason"]: r["count"] for r in j["dismiss_reasons_top"]}
    assert reasons["falsches_fachgebiet"] == 2
    assert reasons["zu_weit_entfernt"] == 1


# ============= Anti-Pattern-Detection ===============

def test_anti_pattern_high_clicks_per_view(setup_env):
    """Wenn eine Seite hohe Klick-pro-View hat → Anti-Pattern erkannt."""
    db = setup_env
    events = []
    # 5 Views + 50 Klicks auf gleicher Seite = 10 Klicks/View → Anti-Pattern
    for _ in range(5):
        events.append({"event_type": "page_view", "page": "stellen"})
    for _ in range(50):
        events.append({"event_type": "click", "page": "stellen", "action": "scroll"})
    _seed_events(db, events)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    j = client.get("/api/activity/aggregate").json()
    aps = j["anti_patterns"]
    assert any(ap["kind"] == "high_clicks_per_view" and ap["page"] == "stellen"
               for ap in aps)


def test_anti_pattern_high_abort_rate(setup_env):
    db = setup_env
    events = []
    # 10 Starts, 7 Aborts, 3 Completes → 70% Abort-Rate
    for _ in range(10):
        events.append({"event_type": "workflow_start", "action": "wizard"})
    for _ in range(7):
        events.append({"event_type": "workflow_abort", "action": "wizard"})
    for _ in range(3):
        events.append({"event_type": "workflow_complete", "action": "wizard"})
    _seed_events(db, events)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    j = client.get("/api/activity/aggregate").json()
    aps = j["anti_patterns"]
    assert any(ap["kind"] == "high_abort_rate" and ap["workflow"] == "wizard"
               for ap in aps)


def test_anti_pattern_no_false_positive_low_volume(setup_env):
    """Bei weniger als 5 Events: kein Anti-Pattern, weil Datenbasis zu duenn."""
    db = setup_env
    events = []
    # 3 Views + 30 Klicks (waere 10/View, aber Volume < 5)
    for _ in range(3):
        events.append({"event_type": "page_view", "page": "test"})
    for _ in range(30):
        events.append({"event_type": "click", "page": "test"})
    _seed_events(db, events)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    j = client.get("/api/activity/aggregate").json()
    aps = j["anti_patterns"]
    assert not any(ap["kind"] == "high_clicks_per_view" for ap in aps)


# ============= Frontend Snapshot ===============

def test_dashboard_has_learning_insights_card():
    src = (PROJECT_ROOT / "frontend" / "src" / "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
    assert "LearningInsightsCard" in src
    assert "Was PBP gelernt hat" in src
    assert "anti_patterns" in src
