"""Tests fuer v1.7.0-beta.43 — Komplett-Deinstallation aus Gefahrenzone (#621)."""
from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta43_")
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


def test_launch_uninstaller_requires_confirmation(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/danger/launch-uninstaller", json={})
    assert r.status_code == 400
    assert "DEINSTALLIEREN" in r.json()["error"]


def test_launch_uninstaller_wrong_confirmation(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/danger/launch-uninstaller",
                    json={"confirm": "loesch mich"})
    assert r.status_code == 400


@pytest.mark.skipif(platform.system() == "Windows",
                    reason="Test prueft das Non-Windows-Reject")
def test_launch_uninstaller_rejects_non_windows(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/danger/launch-uninstaller",
                    json={"confirm": "DEINSTALLIEREN"})
    assert r.status_code == 400
    assert "Windows" in r.json()["error"]


@pytest.mark.skipif(platform.system() != "Windows",
                    reason="Pfad-Check ist Windows-spezifisch")
def test_launch_uninstaller_404_when_bat_missing(setup_env, monkeypatch):
    """Auf Windows: wenn die .bat nicht in %LOCALAPPDATA%\\BewerbungsAssistent\\app
    existiert (z.B. Dev-Checkout), 404 mit klarer Meldung."""
    # LOCALAPPDATA auf einen leeren Tempdir umbiegen
    fake_localappdata = tempfile.mkdtemp(prefix="pbp_fake_appdata_")
    monkeypatch.setenv("LOCALAPPDATA", fake_localappdata)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/danger/launch-uninstaller",
                    json={"confirm": "DEINSTALLIEREN"})
    import shutil
    shutil.rmtree(fake_localappdata, ignore_errors=True)
    assert r.status_code == 404
    assert "nicht gefunden" in r.json()["error"]


def test_settings_page_has_uninstall_section():
    """Frontend-Seite enthaelt die neue Komponente."""
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "UninstallSection" in content
    assert "/api/danger/launch-uninstaller" in content
    # Hinweis zu Claude/Ollama muss sichtbar sein
    assert "Claude Desktop" in content
    assert "Ollama" in content
