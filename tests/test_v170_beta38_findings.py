"""Tests fuer v1.7.0-beta.38 — User-Test-Findings (#600/#601/#607)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta38_")
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


# ============= #607 Score-Buckets ===============

def test_make_score_buckets_legacy_below_10():
    from bewerbungs_assistent.database import _make_score_buckets
    buckets = _make_score_buckets(8)
    labels = [b[2] for b in buckets]
    assert labels == ["0", "1-3", "4-6", "7-9", "10+"]


def test_make_score_buckets_dynamic_max_50():
    from bewerbungs_assistent.database import _make_score_buckets
    buckets = _make_score_buckets(50)
    # 50/6 = 8.3 -> auf 5 gerundet = 10 → 6 Buckets
    assert len(buckets) >= 5
    # Erste Bucket ist 0-X
    assert buckets[0][0] == 0
    # Letzte Bucket umschliesst den max-Wert
    assert buckets[-1][1] >= 50


def test_make_score_buckets_dynamic_max_90():
    from bewerbungs_assistent.database import _make_score_buckets
    buckets = _make_score_buckets(90)
    assert len(buckets) >= 5
    # Sortierung: lower-bound aufsteigend
    lowers = [b[0] for b in buckets]
    assert lowers == sorted(lowers)
    assert buckets[0][0] == 0
    assert buckets[-1][1] >= 90


def test_score_distribution_in_report_data(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    # Setup: 5 Stellen mit Scores 10, 25, 45, 70, 90
    for i, score in enumerate([10, 25, 45, 70, 90]):
        conn.execute(
            "INSERT INTO jobs (hash, profile_id, title, company, score, "
            "is_pinned, is_active, found_at) "
            "VALUES (?, ?, ?, ?, ?, 0, 1, ?)",
            (f"{pid}:s{i}", pid, "T", "C", score, "2026-05-01")
        )
    conn.commit()

    rd = db.get_report_data()
    # ordered Liste muss da sein
    assert "score_distribution_ordered" in rd
    ordered = rd["score_distribution_ordered"]
    assert len(ordered) >= 5
    # Reihenfolge: niedriger Score zuerst
    lowers = [int(item["bracket"].split("-")[0].rstrip("+"))
              for item in ordered]
    assert lowers == sorted(lowers)
    # Summe der counts == 5
    total = sum(item["cnt"] for item in ordered)
    assert total == 5


# ============= #601 Elwosa Power-User Settings ===============

def test_elwosa_settings_default_includes_power_user_keys(setup_env):
    db = setup_env
    s = db.get_elwosa_settings()
    assert "cooldown_seconds" in s
    assert s["cooldown_seconds"] == 90
    assert "comment_user_actions" in s
    assert s["comment_user_actions"] is False


def test_elwosa_settings_set_cooldown(setup_env):
    db = setup_env
    out = db.set_elwosa_settings(cooldown_seconds=30)
    assert out["cooldown_seconds"] == 30


def test_elwosa_settings_cooldown_validation(setup_env):
    db = setup_env
    with pytest.raises(ValueError):
        db.set_elwosa_settings(cooldown_seconds=5)
    with pytest.raises(ValueError):
        db.set_elwosa_settings(cooldown_seconds=10000)


def test_elwosa_settings_comment_user_actions_toggle(setup_env):
    db = setup_env
    out = db.set_elwosa_settings(comment_user_actions=True)
    assert out["comment_user_actions"] is True


def test_elwosa_frequency_unbegrenzt_accepted(setup_env):
    db = setup_env
    out = db.set_elwosa_settings(frequency="unbegrenzt")
    assert out["frequency"] == "unbegrenzt"


def test_elwosa_can_post_class_unbegrenzt_bypasses_idle_limit(setup_env):
    """Bei frequency='unbegrenzt' entfallen die KONTINGENTE — nicht die
    Sperrfristen (v1.7.12/#822: 'viele Linien' heisst nie 'dieselbe Art
    im Stundentakt'). Der Alt-Vertrag (100 idle heute, trotzdem weiter)
    war Teil der stuendlichen Wiederholung."""
    db = setup_env
    from datetime import datetime, timedelta, timezone
    db.set_elwosa_settings(frequency="unbegrenzt")
    from bewerbungs_assistent.services import elwosa
    settings = db.get_elwosa_settings()

    # Frisch gepostetes idle -> Kind-Sperre (12h) blockt, auch unbegrenzt
    mid = db.add_elwosa_message("idle frisch", trigger_kind="idle")
    assert elwosa.can_post_class(db, "idle", settings) is False

    # Sperre abgelaufen -> unbegrenzt umgeht die Tages-Kontingente
    alt = (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()
    conn = db.connect()
    conn.execute("UPDATE elwosa_messages SET created_at=? WHERE id=?",
                 (alt, mid))
    conn.commit()
    assert elwosa.can_post_class(db, "idle", settings) is True


def test_elwosa_triggers_disabled_blocks_class(setup_env):
    db = setup_env
    db.set_elwosa_settings(triggers_disabled=["tip", "easter_egg"])
    from bewerbungs_assistent.services import elwosa
    settings = db.get_elwosa_settings()
    assert elwosa.can_post_class(db, "tip", settings) is False
    assert elwosa.can_post_class(db, "easter_egg", settings) is False
    # Andere Klassen unberuehrt
    assert elwosa.can_post_class(db, "mail_received", settings) is True


def test_api_elwosa_settings_includes_new_keys(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/elwosa/settings")
    j = r.json()
    assert "cooldown_seconds" in j
    assert "comment_user_actions" in j


def test_api_elwosa_set_cooldown_via_put(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/elwosa/settings", json={"cooldown_seconds": 60})
    assert r.status_code == 200
    assert r.json()["cooldown_seconds"] == 60


def test_api_elwosa_invalid_cooldown(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/elwosa/settings", json={"cooldown_seconds": 5})
    assert r.status_code == 400


# ============= #601 Frontend ===============

def test_elwosa_sidebar_has_settings_button():
    p = PROJECT_ROOT / "frontend" / "src" / "components" / "ElwosaSidebarChat.jsx"
    content = p.read_text(encoding="utf-8")
    # Settings-Icon ist da, mood-Anzeige raus
    assert "Settings" in content
    assert "onNavigateToSettings" in content
    # mood wird nicht mehr im Header angezeigt
    assert "status.mood && status.mood" not in content


def test_elwosa_settings_section_has_power_user_block():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "Power-User-Optionen" in content
    assert "cooldown_seconds" in content
    assert "comment_user_actions" in content
    assert "triggers_disabled" in content
    assert '"unbegrenzt"' in content


# ============= #600 Installer ===============

def test_macos_installer_has_browser_open():
    p = PROJECT_ROOT / "INSTALLIEREN.command"
    content = p.read_text(encoding="utf-8")
    # macOS auto-open via 'open ' command
    assert 'open "http://localhost:8200/"' in content
    # Health-Check-Loop
    assert "DASH_OK=1" in content


def test_linux_installer_has_browser_open():
    p = PROJECT_ROOT / "installer" / "install.sh"
    content = p.read_text(encoding="utf-8")
    assert "xdg-open" in content
    assert "open_browser" in content
    assert "Dashboard wird gestartet" in content


def test_windows_installer_opens_browser_even_on_health_fail():
    """Update-Pfad: alte Instanz kann Port belegen. Browser trotzdem oeffnen."""
    p = PROJECT_ROOT / "INSTALLIEREN.bat"
    content = p.read_text(encoding="utf-8")
    # Im else-Pfad muss start-Befehl ebenfalls aufgerufen werden
    bad_section = content.split('antwortet nicht nach 30 Sekunden')[1]
    assert 'start "" "http://localhost:8200/"' in bad_section
