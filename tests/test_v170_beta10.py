"""Tests fuer v1.7.0-beta.10 — Kontakte-Frontend + API (#563)."""
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta10_")
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
    # Dashboard-globalen _db setzen damit TestClient die Endpoints sieht
    _dash_mod._db = db
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= API-Endpoints (TestClient) ===============

def test_563_api_create_and_list_contact(setup_env):
    """POST /api/contacts + GET /api/contacts Round-Trip."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/contacts", json={
        "full_name": "Maria Mustermann",
        "email": "maria@x.de",
        "tags": ["recruiter"],
    })
    assert r.status_code == 200
    cid = r.json()["id"]
    assert cid

    r2 = client.get("/api/contacts")
    assert r2.status_code == 200
    data = r2.json()
    assert data["count"] == 1
    assert data["contacts"][0]["full_name"] == "Maria Mustermann"


def test_563_api_create_validation(setup_env):
    """POST /api/contacts ohne Name liefert 400."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/contacts", json={"email": "x@y.de"})
    assert r.status_code == 400
    assert "error" in r.json()


def test_563_api_update_contact(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    cid = db.add_contact({"full_name": "Alt"})
    r = client.put(f"/api/contacts/{cid}", json={"full_name": "Neu", "company": "X-Corp"})
    assert r.status_code == 200
    contact = db.get_contact(cid)
    assert contact["full_name"] == "Neu"
    assert contact["company"] == "X-Corp"


def test_563_api_delete_contact(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    cid = db.add_contact({"full_name": "Tmp"})
    r = client.delete(f"/api/contacts/{cid}")
    assert r.status_code == 200
    assert db.get_contact(cid) is None


def test_563_api_link_and_unlink(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    cid = db.add_contact({"full_name": "Test"})
    bid = db.add_application({"title": "T", "company": "C"})
    r = client.post(f"/api/contacts/{cid}/links", json={
        "target_kind": "application",
        "target_id": bid,
        "role": "recruiter",
    })
    assert r.status_code == 200
    link_id = r.json()["id"]

    # Reverse-Lookup
    r2 = client.get(f"/api/applications/{bid}/contacts")
    assert r2.status_code == 200
    data = r2.json()
    assert data["count"] == 1
    assert data["contacts"][0]["full_name"] == "Test"
    assert data["contacts"][0]["link_role"] == "recruiter"

    # Unlink
    r3 = client.delete(f"/api/contacts/links/{link_id}")
    assert r3.status_code == 200
    r4 = client.get(f"/api/applications/{bid}/contacts")
    assert r4.json()["count"] == 0


def test_563_api_link_validates_kind(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    cid = db.add_contact({"full_name": "Test"})
    r = client.post(f"/api/contacts/{cid}/links", json={
        "target_kind": "ungueltig",
        "target_id": "x",
    })
    assert r.status_code == 400


def test_563_api_search_filter(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    db.add_contact({"full_name": "Anna Mueller", "company": "TestCorp"})
    db.add_contact({"full_name": "Bob Schmidt", "company": "OtherCorp"})
    r = client.get("/api/contacts?search=anna")
    assert r.json()["count"] == 1
    assert r.json()["contacts"][0]["full_name"] == "Anna Mueller"


def test_563_api_role_filter(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    db.add_contact({"full_name": "A", "tags": ["recruiter"]})
    db.add_contact({"full_name": "B", "tags": ["hr"]})
    r = client.get("/api/contacts?role=recruiter")
    assert r.json()["count"] == 1


# ============= Frontend-Datei vorhanden ===============

def test_563_contacts_page_jsx_exists():
    from pathlib import Path
    p = Path("frontend/src/pages/ContactsPage.jsx")
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    assert "ContactsPage" in src
    assert "ROLE_OPTIONS" in src  # Vordefinierte Tag-Liste


def test_563_app_jsx_routes_kontakte():
    from pathlib import Path
    src = Path("frontend/src/App.jsx").read_text(encoding="utf-8")
    assert 'page === "kontakte"' in src
    assert "ContactsPage" in src
    assert '"kontakte"' in src  # In TAB_CONFIG


def test_563_applications_page_has_contacts_section():
    from pathlib import Path
    src = Path("frontend/src/pages/ApplicationsPage.jsx").read_text(encoding="utf-8")
    assert "ApplicationContactsSection" in src
    # Erklaerender Empty-State muss da sein
    assert "Wer war beim Interview dabei?" in src or "Beteiligte Personen" in src
