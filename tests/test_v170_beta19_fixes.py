"""Tests fuer v1.7.0-beta.19 — User-Test-Findings.

1. Installer: nach erfolgreicher Installation startet Dashboard
   automatisch (kein j/n-Prompt mehr) + klare Erfolgsmeldung.
2. Dashboard-Flackern: Live-Update-Token aendert sich nicht mehr bei
   reinen Lesezugriffen (vorher: WAL-mtime triggerte ihn permanent).
3. LLM-Modal „Mehr erfahren"-Button navigiert auf Lokale-KI-Tab
   (vorher: Hash-Link landete im Dashboard).
"""
import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ============= #1 Installer Auto-Start ===============

def test_installer_uses_auto_start_no_prompt():
    """INSTALLIEREN.bat fragt nicht mehr (j/n) — Dashboard startet automatisch."""
    bat = (PROJECT_ROOT / "INSTALLIEREN.bat").read_text(encoding="cp1252", errors="replace")
    # Alte j/n-Frage darf nicht mehr drin sein
    assert 'set /p OPEN_DASH=' not in bat, (
        "j/n-Prompt fuers Dashboard-Oeffnen darf nicht mehr da sein"
    )
    assert "Dashboard jetzt im Browser oeffnen" not in bat
    # Erfolgsmeldung sichtbar
    assert "ERFOLGREICH" in bat or "I N S T A L L A T I O N" in bat
    # Auto-Start des Dashboards
    assert 'start "" "%APP_DIR%\\Dashboard starten.bat"' in bat


def test_installer_shows_version_in_success():
    """Erfolgsmeldung enthaelt die installierte Version (PBP_VERSION)."""
    bat = (PROJECT_ROOT / "INSTALLIEREN.bat").read_text(encoding="cp1252", errors="replace")
    # Im Erfolgsblock muss %PBP_VERSION% verwendet werden
    assert "Version installiert: %PBP_VERSION%" in bat


# ============= #2 Live-Update-Token-Stabilitaet ===============

@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta19_")
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
    yield db, _dash_mod
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_live_update_token_stable_under_read_only_polling(setup_env):
    """Bei reinen Lese-Polls bleibt der Token stabil — kein Flackern."""
    db, dash_mod = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)

    # 5x hintereinander pollen ohne irgendwas zu schreiben
    tokens = []
    for _ in range(5):
        r = client.get("/api/live-update-token")
        assert r.status_code == 200
        tokens.append(r.json()["token"])

    assert len(set(tokens)) == 1, (
        f"Token aendert sich obwohl nichts geschrieben wurde: {tokens}"
    )


def test_live_update_token_changes_on_write(setup_env):
    """Bei echten Schreibvorgaengen aendert sich der Token (sonst keine Live-Updates)."""
    db, dash_mod = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)

    t1 = client.get("/api/live-update-token").json()["token"]
    # Echter Schreibvorgang — Bewerbung anlegen
    db.add_application({"title": "Test", "company": "ACME"})
    t2 = client.get("/api/live-update-token").json()["token"]

    assert t1 != t2, "Token muesste sich nach Schreibvorgang aendern"


def test_live_update_token_repeated_read_does_not_flap(setup_env):
    """Mehrfaches Pollen darf nicht zwischen 2 Werten oszillieren."""
    db, dash_mod = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)

    # 20x pollen — das simuliert 40 Sekunden Polling-Last
    tokens = [client.get("/api/live-update-token").json()["token"] for _ in range(20)]
    unique = set(tokens)
    assert len(unique) == 1, (
        f"Token oszilliert bei reinem Polling — {len(unique)} unterschiedliche Werte: {tokens[:5]}..."
    )


# ============= #3 LLM-Modal „Mehr erfahren" navigiert korrekt ===============

def test_llm_modal_uses_navigateTo_not_hash():
    """App.jsx LLM-Modal nutzt navigateTo statt href=#einstellungen?tab=ai."""
    app_jsx = (PROJECT_ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    # Alter buggy Hash-Link darf nicht mehr existieren
    assert 'href="#einstellungen?tab=ai"' not in app_jsx, (
        "Alter Hash-Link wurde nicht entfernt — landet weiter im Dashboard"
    )
    # Neuer Aufruf navigateTo("einstellungen", { tab: "ai" }) muss da sein
    assert 'navigateTo("einstellungen", { tab: "ai" })' in app_jsx


# ============= #4 Kontakte-Import-Discover ===============

def test_discover_empty_when_no_applications(setup_env):
    """Ohne Bewerbungen + Mail-Dokumente liefert /discover leere Listen."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/contacts/discover")
    assert r.status_code == 200
    j = r.json()
    assert j["from_applications"] == []
    assert j["from_emails"] == []


def test_discover_finds_application_contacts(setup_env):
    """Bewerbung mit ansprechpartner+kontakt_email wird als Kandidat geliefert."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    db.add_application({
        "title": "Engineer", "company": "ACME",
        "ansprechpartner": "Anna Recruiter",
        "kontakt_email": "anna@acme.com",
    })
    r = client.get("/api/contacts/discover")
    j = r.json()
    assert len(j["from_applications"]) == 1
    cand = j["from_applications"][0]
    assert cand["full_name"] == "Anna Recruiter"
    assert cand["email"] == "anna@acme.com"
    assert cand["company"] == "ACME"


def test_discover_skips_existing_contacts(setup_env):
    """Wenn der Kontakt schon mit gleicher Mail angelegt ist: kein Vorschlag."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    db.add_contact({"full_name": "Anna", "email": "anna@acme.com"})
    db.add_application({
        "title": "X", "company": "ACME",
        "ansprechpartner": "Anna Recruiter",
        "kontakt_email": "anna@acme.com",
    })
    r = client.get("/api/contacts/discover")
    j = r.json()
    assert j["from_applications"] == []


def test_discover_finds_emails_in_documents(setup_env):
    """E-Mail-Dokument mit extracted_text enthaelt Mail-Adressen → Kandidaten."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO documents (id, profile_id, filename, doc_type, "
        "extracted_text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("d1", pid, "mail.eml", "email",
         "From: recruiter@example.com\nTo: candidate@gmail.com\n"
         "Subject: Bewerbung\n\nHallo, ihre Bewerbung...",
         "2026-05-01T10:00:00")
    )
    conn.commit()
    r = client.get("/api/contacts/discover")
    j = r.json()
    emails = {c["email"] for c in j["from_emails"]}
    assert "recruiter@example.com" in emails
    assert "candidate@gmail.com" in emails


def test_import_discovered_creates_contacts(setup_env):
    """POST /import-discovered legt die uebergebenen Kandidaten als Kontakte an."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/contacts/import-discovered", json={
        "candidates": [
            {"full_name": "Anna", "email": "anna@x.de", "tags": ["recruiter"]},
            {"full_name": "Bob", "email": "bob@x.de"},
        ]
    })
    assert r.status_code == 200
    j = r.json()
    assert j["created"] == 2
    assert j["skipped"] == 0
    # Verifizieren dass die Kontakte wirklich existieren
    contacts = db.list_contacts()
    emails = {c.get("email") for c in contacts}
    assert "anna@x.de" in emails
    assert "bob@x.de" in emails


def test_import_discovered_skips_duplicates(setup_env):
    """Bestehende Mail wird beim Import skipped, nicht doppelt angelegt."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    db.add_contact({"full_name": "Anna", "email": "anna@x.de"})
    r = client.post("/api/contacts/import-discovered", json={
        "candidates": [
            {"full_name": "Anna", "email": "anna@x.de"},
            {"full_name": "Bob", "email": "bob@x.de"},
        ]
    })
    j = r.json()
    assert j["created"] == 1  # nur Bob neu
    assert j["skipped"] == 1


def test_contacts_page_has_import_button():
    """ContactsPage.jsx enthaelt den Import-Button + Wizard-Component."""
    src = (PROJECT_ROOT / "frontend" / "src" / "pages" / "ContactsPage.jsx").read_text(encoding="utf-8")
    assert "ImportDiscoverDialog" in src
    assert "/api/contacts/discover" in src
    assert "Importieren" in src
