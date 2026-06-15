"""Regression #701 (Backend-Teil): /api/status und /api/health liefern die
Serverzeit + Zeitzone (Europe/Berlin) fuer die Footer-Anzeige.

Die relative-Label-Logik (Europe/Berlin, Kipp-Test) liegt im Frontend und
wird durch frontend/src/lib/relativeDate.test.mjs (in der CI) abgedeckt.

HARTE ISOLATIONS-REGEL: db.db_path im Temp-Verzeichnis (BA_DATA_DIR).
"""
import importlib
import os
import re
import shutil
import tempfile

import pytest


@pytest.fixture
def dash():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_701_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    _dash_mod._db = db
    yield _dash_mod
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_701_status_liefert_serverzeit(dash):
    from fastapi.testclient import TestClient
    data = TestClient(dash.app).get("/api/status").json()
    assert data.get("timezone") == "Europe/Berlin"
    assert re.fullmatch(r"\d{2}:\d{2}", data.get("server_time", "")), data.get("server_time")


def test_701_health_liefert_serverzeit(dash):
    from fastapi.testclient import TestClient
    data = TestClient(dash.app).get("/api/health").json()
    assert data.get("timezone") == "Europe/Berlin"
    assert re.fullmatch(r"\d{2}:\d{2}", data.get("server_time", ""))
    assert data.get("server_time_iso")
