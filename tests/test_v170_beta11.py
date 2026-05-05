"""Tests fuer v1.7.0-beta.11 — Bewerbungs-Detail-API (#472, #568, #580)."""
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta11_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= Application-Jobs (#472) ===============

def test_472_api_app_jobs_link_unlink(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    bid = db.add_application({"title": "T", "company": "C"})
    db.save_jobs([{"hash": "j1", "title": "A", "company": "C", "url": "x", "source": "manuell", "score": 50}])
    r = client.post(f"/api/applications/{bid}/jobs", json={"job_hash": "j1", "version_label": "Original"})
    assert r.status_code == 200
    r2 = client.get(f"/api/applications/{bid}/jobs")
    assert r2.json()["count"] == 1
    assert r2.json()["jobs"][0]["link_version"] == "Original"


def test_472_api_unlink_app_job(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    bid = db.add_application({"title": "T", "company": "C"})
    db.save_jobs([{"hash": "j1", "title": "A", "company": "C", "url": "x", "source": "manuell", "score": 50}])
    db.link_application_to_job(bid, "j1")
    pid = db.get_active_profile_id()
    full_hash = f"{pid}:j1"
    r = client.delete(f"/api/applications/{bid}/jobs/{full_hash}")
    assert r.status_code == 200


# ============= Aufwand (#568) ===============

def test_568_api_app_aufwand_summary(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    bid = db.add_application({"title": "T", "company": "C"})
    db.add_application_cost({"application_id": bid, "kind": "tool", "amount": 25.50})
    r = client.get(f"/api/applications/{bid}/aufwand")
    assert r.status_code == 200
    assert r.json()["kosten_summe_eur"] == 25.50


def test_568_api_app_costs_crud(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    bid = db.add_application({"title": "T", "company": "C"})
    r = client.post(f"/api/applications/{bid}/costs", json={
        "kind": "tool", "amount": 49.99, "description": "Notion 1J"
    })
    assert r.status_code == 200
    cid = r.json()["id"]

    r2 = client.get(f"/api/applications/{bid}/costs")
    assert r2.json()["costs"][0]["amount"] == 49.99

    r3 = client.delete(f"/api/costs/{cid}")
    assert r3.status_code == 200


def test_568_api_costs_validates_amount(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    bid = db.add_application({"title": "T", "company": "C"})
    r = client.post(f"/api/applications/{bid}/costs", json={
        "kind": "tool", "amount": -5
    })
    assert r.status_code == 400


# ============= Stellen-Vergleich (#580) ===============

def test_580_api_jobs_compare(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    db.save_jobs([
        {"hash": "h1", "title": "Senior PLM", "company": "TestCorp", "url": "x",
         "source": "manuell", "score": 70, "description": "PLM SAP Cloud"},
        {"hash": "h2", "title": "PLM Architect", "company": "OtherCorp", "url": "y",
         "source": "manuell", "score": 75, "description": "PLM Aras Cloud"},
    ])
    r = client.get("/api/jobs/compare?a=h1&b=h2")
    assert r.status_code == 200
    data = r.json()
    assert "plm" in data["vergleich"]["titel_gemeinsam"]
    assert data["vergleich"]["score_diff"] == -5
    assert data["vergleich"]["gleiche_firma"] is False


def test_580_api_compare_missing_job(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/jobs/compare?a=nonexistent1&b=nonexistent2")
    assert r.status_code == 404


# ============= Frontend-Component vorhanden ===============

def test_v170_beta11_components_in_jsx():
    from pathlib import Path
    src = Path("frontend/src/pages/ApplicationsPage.jsx").read_text(encoding="utf-8")
    assert "ApplicationJobsSection" in src
    assert "ApplicationAufwandSection" in src
    assert "StellenVergleichModal" in src
    # Empty-State-Texte fuer Endnutzer-Fuehrung
    assert "Repost" in src or "Vermittler" in src  # Erklaerung fuer mehrere Stellen
    assert "Reisekosten" in src or "Tool-Abos" in src  # Erklaerung Aufwand
