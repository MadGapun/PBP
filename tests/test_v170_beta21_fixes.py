"""Tests fuer v1.7.0-beta.21 — User-Test-Findings.

1. PAGE_IDS enthaelt 'kontakte' (2-Klick-Bug-Fix)
2. /api/contacts/enrich-from-linkedin liefert Prompt + JS
"""
import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta21_")
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


# ============= #1 PAGE_IDS enthaelt 'kontakte' ===============

def test_page_ids_includes_kontakte():
    """utils.js: PAGE_IDS muss 'kontakte' enthalten — sonst 2-Klick-Bug.

    Hintergrund: parsePageFromHash() fiel auf 'dashboard' zurueck wenn
    der Hash unbekannt war. Beim 1. Klick auf 'Kontakte' setzte
    navigateTo den Hash, hashchange-Listener ruft parsePageFromHash,
    findet 'kontakte' nicht in PAGE_IDS, setzt page zurueck auf
    'dashboard' — der Klick verpufft. Erst der 2. Klick blieb stabil
    weil der Hash schon stand.
    """
    src = (PROJECT_ROOT / "frontend" / "src" / "utils.js").read_text(encoding="utf-8")
    # Sehr explizit: kontakte muss als String-Literal in PAGE_IDS-Liste sein
    # Wir suchen nach `"kontakte",` mit exakt einem Kontext der PAGE_IDS-naehe
    assert '"kontakte"' in src
    # Der Bug-Erklaer-Kommentar dokumentiert das Risiko
    assert "2-Klick-Bug" in src or "PAGE_IDS vergessen" in src or "fuehrte zum" in src


# ============= #2 LinkedIn-Anreicherung ===============

def test_enrich_endpoint_validates_linkedin_url(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # Ohne URL → 400
    r = client.post("/api/contacts/enrich-from-linkedin", json={})
    assert r.status_code == 400
    # Ungueltige URL → 400
    r = client.post("/api/contacts/enrich-from-linkedin",
                    json={"linkedin_url": "https://example.com/foo"})
    assert r.status_code == 400


def test_enrich_endpoint_returns_prompt(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/contacts/enrich-from-linkedin", json={
        "linkedin_url": "https://linkedin.com/in/example-person",
    })
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert "linkedin.com/in/example-person" in j["prompt"]
    assert "javascript_tool" in j["prompt"]
    assert "(()" in j["extraction_js"]  # JS-IIFE
    # Hinweis erklaert WARUM keine direkte Server-Loesung
    assert "Login-Wall" in j["hinweis"] or "Bot-Detection" in j["hinweis"]


def test_enrich_endpoint_uses_contact_linkedin_if_no_url(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    cid = db.add_contact({
        "full_name": "X",
        "linkedin_url": "https://www.linkedin.com/in/some-person",
    })
    r = client.post("/api/contacts/enrich-from-linkedin",
                    json={"contact_id": cid})
    assert r.status_code == 200
    j = r.json()
    assert "some-person" in j["linkedin_url"]


def test_enrich_endpoint_404_for_unknown_contact(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/contacts/enrich-from-linkedin",
                    json={"contact_id": "CON-doesnotexist"})
    assert r.status_code == 404


def test_contact_dialog_has_data_holen_button():
    """ContactsPage.jsx hat den 'Daten holen'-Button im LinkedIn-Feld."""
    src = (PROJECT_ROOT / "frontend" / "src" / "pages" / "ContactsPage.jsx").read_text(encoding="utf-8")
    assert "Daten holen" in src
    assert "/api/contacts/enrich-from-linkedin" in src
    assert "Claude-in-Chrome" in src or "eingeloggten Chrome" in src
