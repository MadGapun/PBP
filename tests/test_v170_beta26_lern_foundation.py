"""Tests fuer v1.7.0-beta.26 — #594 Stufe 1: Lern-System-Foundation."""
import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta26_")
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


# ============= Schema v38 Migration ===============

def test_schema_v38_creates_tables(setup_env):
    db = setup_env
    conn = db.connect()
    tables = {
        r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "user_activity_events" in tables
    assert "learning_insights" in tables


def test_schema_version_is_38(setup_env):
    db = setup_env
    from bewerbungs_assistent.database import SCHEMA_VERSION
    assert SCHEMA_VERSION == 38
    conn = db.connect()
    row = conn.execute(
        "SELECT value FROM settings WHERE key='schema_version'"
    ).fetchone()
    assert row["value"] == "38"


# ============= add_activity_event + Batch ===============

def test_add_activity_event_default_enabled(setup_env):
    db = setup_env
    eid = db.add_activity_event({
        "event_type": "page_view",
        "page": "stellen",
        "session_id": "s-test",
        "app_version": "1.7.0-beta.26",
    })
    assert eid > 0
    conn = db.connect()
    n = conn.execute("SELECT COUNT(*) AS c FROM user_activity_events").fetchone()["c"]
    assert n == 1


def test_add_activity_event_silent_when_disabled(setup_env):
    """Wenn `learning_enabled=False` als Param: Event wird nicht gespeichert."""
    db = setup_env
    eid = db.add_activity_event({
        "event_type": "click",
        "learning_enabled": False,
    })
    assert eid == 0
    conn = db.connect()
    n = conn.execute("SELECT COUNT(*) AS c FROM user_activity_events").fetchone()["c"]
    assert n == 0


def test_batch_insert_multiple_events(setup_env):
    db = setup_env
    n = db.add_activity_events_batch([
        {"event_type": "page_view", "page": "dashboard"},
        {"event_type": "click", "page": "dashboard", "action": "schnellzugriff"},
        {"event_type": "filter_apply", "page": "stellen",
         "metadata": {"filter": "score_min", "value": "70"}},
    ])
    assert n == 3
    assert db.get_activity_event_count() == 3


def test_batch_skips_events_without_event_type(setup_env):
    db = setup_env
    n = db.add_activity_events_batch([
        {"event_type": "page_view"},
        {"page": "stellen"},  # ohne event_type → skip
    ])
    assert n == 1


def test_clear_activity_events_keeps_domain_data(setup_env):
    db = setup_env
    db.add_application({"title": "T", "company": "C"})  # Domain-Daten
    db.add_activity_event({"event_type": "page_view", "page": "x"})
    assert db.get_activity_event_count() == 1
    deleted = db.clear_activity_events()
    assert deleted == 1
    assert db.get_activity_event_count() == 0
    # Application bleibt
    assert len(db.get_applications()) == 1


def test_prune_old_events(setup_env):
    db = setup_env
    conn = db.connect()
    pid = db.get_active_profile_id()
    # 100 Tage altes Event direkt einfuegen (umgehe add_activity_event)
    conn.execute(
        "INSERT INTO user_activity_events "
        "(profile_id, event_type, timestamp) VALUES (?, ?, ?)",
        (pid, "page_view", "2020-01-01T00:00:00")
    )
    conn.commit()
    # Frisches Event
    db.add_activity_event({"event_type": "page_view", "page": "x"})
    assert db.get_activity_event_count() == 2
    deleted = db.prune_activity_events_older_than(90)
    assert deleted == 1
    assert db.get_activity_event_count() == 1


# ============= API: /api/activity/track ===============

def test_api_track_silent_when_learning_disabled(setup_env):
    db = setup_env
    db.set_profile_setting("learning_enabled", False)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/activity/track", json={
        "events": [{"event_type": "page_view"}]
    })
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"
    assert db.get_activity_event_count() == 0


def test_api_track_stores_when_enabled(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/activity/track", json={
        "events": [
            {"event_type": "page_view", "page": "stellen"},
            {"event_type": "click", "page": "stellen", "action": "filter"},
        ]
    })
    assert r.status_code == 200
    assert r.json()["stored"] == 2
    assert db.get_activity_event_count() == 2


def test_api_activity_stats(setup_env):
    db = setup_env
    db.add_activity_events_batch([
        {"event_type": "page_view"},
        {"event_type": "page_view"},
        {"event_type": "click"},
    ])
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/activity/stats")
    j = r.json()
    assert j["total_events"] == 3
    types = {t["type"]: t["count"] for t in j["by_type"]}
    assert types.get("page_view") == 2
    assert types.get("click") == 1


def test_api_activity_clear(setup_env):
    db = setup_env
    db.add_activity_events_batch([{"event_type": "click"}])
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.delete("/api/activity/clear")
    assert r.status_code == 200
    assert db.get_activity_event_count() == 0


def test_api_settings_learning_get_default_on(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/settings/learning")
    assert r.json()["learning_enabled"] is True


def test_api_settings_learning_toggle(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/settings/learning", json={"learning_enabled": False})
    assert r.status_code == 200
    assert r.json()["learning_enabled"] is False
    # Verifizieren: persistiert
    r2 = client.get("/api/settings/learning")
    assert r2.json()["learning_enabled"] is False


# ============= Frontend Snapshot ===============

def test_activity_tracking_module_exists():
    src = (PROJECT_ROOT / "frontend" / "src" / "activity-tracking.js").read_text(encoding="utf-8")
    assert "initActivityTracking" in src
    assert "trackEvent" in src
    assert "FLUSH_INTERVAL_MS" in src
    assert "navigator.sendBeacon" in src  # beforeunload-flush


def test_app_jsx_initializes_tracking():
    src = (PROJECT_ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "initActivityTracking" in src
    assert "track.pageView" in src
    assert "track.dwell" in src


def test_settings_page_has_learning_privacy_card():
    src = (PROJECT_ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert "LearningPrivacyCard" in src
    assert "Lern-Modus" in src
    assert "verlassen deinen Rechner" in src or "bleiben LOKAL" in src
    assert "Alle Lern-Daten loeschen" in src
