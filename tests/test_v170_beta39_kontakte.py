"""Tests fuer v1.7.0-beta.39 — #608 Kategorien + #606 Auto-Import."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta39_")
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


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


# ============= #608 Schema v42 ===============

def test_schema_v42_contact_categories_exists(setup_env):
    db = setup_env
    conn = db.connect()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "contact_categories" in tables


def test_contacts_has_pending_columns(setup_env):
    db = setup_env
    conn = db.connect()
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(contacts)"
    ).fetchall()}
    assert "is_pending" in cols
    assert "extracted_from" in cols


# ============= #608 Default-Kategorien ===============

def test_default_categories_seeded(setup_env):
    db = setup_env
    cats = db.list_contact_categories()
    slugs = {c["slug"] for c in cats}
    assert "recruiter" in slugs
    assert "hr" in slugs
    assert "ansprechpartner" in slugs
    assert "endkunde" in slugs
    assert "vermittler" in slugs
    assert "referenz" in slugs
    assert "sonstiges" in slugs
    # Alle haben Farben
    for c in cats:
        assert c["color"].startswith("#") and len(c["color"]) == 7


def test_default_categories_idempotent(setup_env):
    db = setup_env
    n1 = len(db.list_contact_categories())
    n2 = len(db.list_contact_categories())
    assert n1 == n2 == 7


def test_system_categories_protected_from_delete(setup_env):
    db = setup_env
    cats = db.list_contact_categories()
    recruiter = next(c for c in cats if c["slug"] == "recruiter")
    out = db.delete_contact_category(recruiter["id"])
    assert "fehler" in out
    assert "System" in out["fehler"]


# ============= #608 Custom-Kategorien ===============

def test_add_custom_category_with_auto_color(setup_env):
    db = setup_env
    cid = db.add_contact_category("Headhunter")
    cats = db.list_contact_categories()
    custom = next(c for c in cats if c["id"] == cid)
    assert custom["name"] == "Headhunter"
    assert custom["slug"] == "headhunter"
    assert custom["color"].startswith("#")
    assert custom["is_system"] is False


def test_add_category_duplicate_slug_raises(setup_env):
    db = setup_env
    db.add_contact_category("Headhunter")
    with pytest.raises(ValueError):
        db.add_contact_category("Headhunter")


def test_update_category_name_changes_slug(setup_env):
    db = setup_env
    cid = db.add_contact_category("Alumni")
    db.update_contact_category(cid, name="Ehemalige")
    cats = db.list_contact_categories()
    cat = next(c for c in cats if c["id"] == cid)
    assert cat["name"] == "Ehemalige"
    assert cat["slug"] == "ehemalige"


def test_update_category_color(setup_env):
    db = setup_env
    cid = db.add_contact_category("X")
    db.update_contact_category(cid, color="#FF0000")
    cats = db.list_contact_categories()
    cat = next(c for c in cats if c["id"] == cid)
    assert cat["color"] == "#FF0000"


def test_delete_custom_category(setup_env):
    db = setup_env
    cid = db.add_contact_category("ZuLoeschen")
    out = db.delete_contact_category(cid)
    assert out.get("deleted") is True


def test_delete_category_with_contacts_blocked(setup_env):
    db = setup_env
    cid = db.add_contact_category("InUse")
    db.add_contact({
        "full_name": "Max Mustermann",
        "tags": ["inuse"],
    })
    out = db.delete_contact_category(cid)
    assert "fehler" in out
    assert out.get("betroffene_kontakte") == 1


def test_pick_next_color_avoids_used():
    from bewerbungs_assistent.services.contact_colors import (
        pick_next_color, COLOR_PALETTE,
    )
    used = COLOR_PALETTE[:5]
    next_color = pick_next_color(used)
    assert next_color == COLOR_PALETTE[5]


def test_slug_for_name_handles_umlauts():
    from bewerbungs_assistent.services.contact_colors import slug_for_name
    assert slug_for_name("Geschäftsführer") == "geschaeftsfuehrer"
    assert slug_for_name("HR / Personal") == "hr-personal"
    assert slug_for_name("Ansprechpartner") == "ansprechpartner"


# ============= #608 API ===============

def test_api_list_categories(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/contacts/categories")
    j = r.json()
    assert "categories" in j
    assert j["count"] >= 7


def test_api_add_category(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/contacts/categories", json={"name": "Test"})
    assert r.status_code == 200
    assert r.json().get("id")


def test_api_update_category(setup_env):
    db = setup_env
    cid = db.add_contact_category("Test")
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put(f"/api/contacts/categories/{cid}",
                   json={"color": "#123456"})
    assert r.status_code == 200


def test_api_delete_category_blocks_system(setup_env):
    db = setup_env
    cats = db.list_contact_categories()
    sys_id = next(c["id"] for c in cats if c["is_system"])
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.delete(f"/api/contacts/categories/{sys_id}")
    assert r.status_code == 409


# ============= #608 MCP-Tools ===============

def test_mcp_tool_kontakt_kategorien_auflisten(setup_env):
    db = setup_env
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.kontakte import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    out = _call(mcp, "kontakt_kategorien_auflisten", {})
    assert out["anzahl"] >= 7


def test_mcp_tool_kontakt_kategorie_anlegen(setup_env):
    db = setup_env
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.kontakte import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    out = _call(mcp, "kontakt_kategorie_anlegen", {"name": "Custom"})
    assert out.get("status") == "angelegt"


# ============= #606 LLM-Task extract_contacts ===============

def test_extract_contacts_taskkind_exists():
    from bewerbungs_assistent.services.llm_service import TaskKind
    assert TaskKind.EXTRACT_CONTACTS.value == "extract_contacts"


def test_extract_contacts_in_routing_table():
    from bewerbungs_assistent.services.llm_service import (
        TaskKind, ROUTING_TABLE, Backend
    )
    assert Backend.LOCAL in ROUTING_TABLE[TaskKind.EXTRACT_CONTACTS]


def test_parse_extract_contacts_simple():
    from bewerbungs_assistent.services.llm_service import _parse_extract_contacts
    raw = (
        "Anna Mueller | a.mueller@acme.de | hr | Recruiterin ACME | 0.95\n"
        "Stefan Klein |  | ansprechpartner | Lead | 0.7"
    )
    out = _parse_extract_contacts(raw)
    assert out["count"] == 2
    assert out["contacts"][0]["name"] == "Anna Mueller"
    assert out["contacts"][0]["kategorie"] == "hr"
    assert out["contacts"][0]["confidence"] == 0.95


def test_parse_extract_contacts_skips_invalid():
    from bewerbungs_assistent.services.llm_service import _parse_extract_contacts
    out = _parse_extract_contacts("AB | x | y | z | 0.9\n")  # name zu kurz
    assert out["count"] == 0


def test_parse_extract_contacts_caps_at_five():
    from bewerbungs_assistent.services.llm_service import _parse_extract_contacts
    raw = "\n".join(
        f"Person {i}xy | x@y.de | hr | rolle | 0.8" for i in range(10)
    )
    out = _parse_extract_contacts(raw)
    assert out["count"] == 5


def test_extract_contacts_prompt_includes_categories():
    from bewerbungs_assistent.services.llm_service import _build_extract_contacts_prompt
    prompt = _build_extract_contacts_prompt({
        "text": "Hallo, ich bin Anna von ACME.",
        "context_company": "ACME",
        "bekannte_kategorien": ["recruiter", "hr"],
    })
    assert "ACME" in prompt
    assert "recruiter" in prompt
    assert "hr" in prompt
    assert "PIPE" in prompt or "|" in prompt


# ============= #606 One-Shot-Migration ===============

def test_kontakte_aus_bestand_dry_run(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO applications (id, profile_id, title, company, status, "
        "applied_at, created_at, updated_at, ansprechpartner, kontakt_email) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("app1", pid, "X", "ACME", "beworben", "2026-05-01",
         "2026-05-01", "2026-05-01",
         "Anna Mueller", "a.mueller@acme.de")
    )
    conn.commit()

    from bewerbungs_assistent.services.llm_service import TaskResult, Backend
    fake_payload = {
        "contacts": [
            {"name": "Anna Mueller", "email": "a.mueller@acme.de",
             "kategorie": "hr", "rolle": "Recruiterin",
             "confidence": 0.9},
        ],
        "count": 1,
        "raw": "...",
    }
    fake_status = MagicMock()
    fake_status.ollama_available = True
    fake_status.user_state = "active"
    fake_status.available_models = ["llama3:8b"]
    fake_svc = MagicMock()
    fake_svc.get_status.return_value = fake_status
    fake_svc.run.return_value = TaskResult(
        backend=Backend.LOCAL, success=True, payload=fake_payload,
        fallback_message=None,
    )

    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.kontakte import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    with patch(
        "bewerbungs_assistent.services.llm_service.get_llm_service",
        return_value=fake_svc,
    ):
        out = _call(mcp, "kontakte_aus_bestand_importieren", {"dry_run": True})

    assert out.get("status") == "vorschau"
    assert out.get("kandidaten") >= 1
    # Bei dry_run werden keine Kontakte angelegt
    contacts = db.get_contacts() if hasattr(db, "get_contacts") else db.list_contacts()
    assert len(contacts) == 0


def test_kontakte_aus_bestand_real_run_creates_pending(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO applications (id, profile_id, title, company, status, "
        "applied_at, created_at, updated_at, ansprechpartner, kontakt_email) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("app2", pid, "X", "BCorp", "beworben", "2026-05-01",
         "2026-05-01", "2026-05-01",
         "Bob Schmidt", "b@bcorp.de")
    )
    conn.commit()

    from bewerbungs_assistent.services.llm_service import TaskResult, Backend
    fake_payload = {
        "contacts": [
            {"name": "Bob Schmidt", "email": "b@bcorp.de",
             "kategorie": "hr", "rolle": "Recruiter",
             "confidence": 0.85},
        ],
        "count": 1,
        "raw": "...",
    }
    fake_status = MagicMock()
    fake_status.ollama_available = True
    fake_status.user_state = "active"
    fake_status.available_models = ["llama3:8b"]
    fake_svc = MagicMock()
    fake_svc.get_status.return_value = fake_status
    fake_svc.run.return_value = TaskResult(
        backend=Backend.LOCAL, success=True, payload=fake_payload,
        fallback_message=None,
    )

    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.kontakte import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    with patch(
        "bewerbungs_assistent.services.llm_service.get_llm_service",
        return_value=fake_svc,
    ):
        out = _call(mcp, "kontakte_aus_bestand_importieren", {"dry_run": False})

    assert out.get("status") == "ausgefuehrt"
    assert out.get("extrahiert") >= 1
    # Pending-Kontakte sind angelegt
    pending = conn.execute(
        "SELECT * FROM contacts WHERE is_pending=1"
    ).fetchall()
    assert len(pending) >= 1


# ============= #606 Pending-API ===============

def test_api_pending_contacts_empty(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/contacts/pending")
    j = r.json()
    assert j["count"] == 0


def test_api_approve_pending_contact(setup_env):
    db = setup_env
    cid = db.add_contact({
        "full_name": "Max",
        "tags": ["hr"],
        "is_pending": 1,
    })
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post(f"/api/contacts/pending/{cid}/approve")
    assert r.status_code == 200
    # Nicht mehr pending
    r2 = client.get("/api/contacts/pending")
    assert r2.json()["count"] == 0


def test_api_reject_pending_contact(setup_env):
    db = setup_env
    cid = db.add_contact({
        "full_name": "Reject me",
        "tags": ["hr"],
        "is_pending": 1,
    })
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.delete(f"/api/contacts/pending/{cid}")
    assert r.status_code == 200


# ============= Auto-Engine ===============

def test_auto_engine_includes_extract_contacts(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/auto-actions/run")
    j = r.json()
    assert "extract_contacts" in j


# ============= Frontend ===============

def test_contacts_page_uses_pending_banner():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "ContactsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "PendingContactsBanner" in content
    assert "/api/contacts/pending" in content


def test_contacts_page_uses_category_management():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "ContactsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "CategoryManagementSection" in content
    assert "/api/contacts/categories" in content


def test_role_chip_uses_dynamic_color():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "ContactsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "useCategories" in content
    assert "cat?.color" in content
