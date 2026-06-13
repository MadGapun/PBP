"""Scraper-Robustheit B2 Schritt 3 (#722): Dashboard-Sichtbarkeit.

Verifiziert den Backend-Vertrag, auf dem die UI aufbaut: /api/sources liefert
pro Quelle ein health-Dict mit differenziertem Badge (gesund/pausiert/blockiert/
tot/kaputt/deaktiviert), Fehlerklasse und Probe-Zeitpunkt.

HARTE ISOLATIONS-REGEL: db.db_path im Temp-Verzeichnis (BA_DATA_DIR).
"""
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def dash_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_722_")
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
    yield db, _dash_mod
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _badge_for(client, key):
    rows = client.get("/api/sources").json()
    for r in rows:
        if r.get("key") == key:
            return r.get("health") or {}
    return None


def test_722_pausiert_badge_fuer_server_weg(dash_env):
    db, dash = dash_env
    db.set_profile_setting("active_sources", ["hays"])
    # 5x server_weg -> pausiert-mit-Probe
    for _ in range(5):
        db.update_scraper_health("hays", "error", count=0, error_class="server_weg",
                                 detail="timeout 90s")
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)
    health = _badge_for(client, "hays")
    assert health is not None, "Quelle hays nicht in /api/sources"
    assert health["badge"] == "pausiert", health
    assert health["error_class"] == "server_weg"
    assert health["reactivate_at"], "Probe-Zeitpunkt fehlt"


def test_722_tot_badge_fuer_404(dash_env):
    db, dash = dash_env
    db.set_profile_setting("active_sources", ["bundesagentur"])
    for _ in range(5):
        db.update_scraper_health("bundesagentur", "error", count=0, error_class="tot")
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)
    health = _badge_for(client, "bundesagentur")
    assert health["badge"] == "tot", health
    assert health["error_class"] == "tot"
    assert not health["reactivate_at"], "tot darf keinen Probe-Run planen"


def test_722_gesunde_quelle_zeigt_ok(dash_env):
    db, dash = dash_env
    db.set_profile_setting("active_sources", ["hays"])
    db.update_scraper_health("hays", "ok", count=17, time_s=3)
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)
    health = _badge_for(client, "hays")
    assert health["badge"] == "ok", health
    assert health["last_count"] == 17
