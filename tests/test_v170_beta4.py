"""Tests fuer v1.7.0-beta.4 — Kontaktdatenbank (#563)."""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta4_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


# ============= Schema ===============

def test_563_contacts_table_exists(setup_env):
    db, _ = setup_env
    conn = db.connect()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'"
    ).fetchone()
    assert row is not None
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='contact_links'"
    ).fetchone()
    assert row is not None


# ============= add_contact / get_contact ===============

def test_563_add_contact_basic(setup_env):
    db, _ = setup_env
    cid = db.add_contact({
        "full_name": "Maria Mustermann",
        "email": "maria@testcorp.com",
        "company": "TestCorp",
        "tags": ["recruiter", "hr"],
    })
    assert cid
    contact = db.get_contact(cid)
    assert contact["full_name"] == "Maria Mustermann"
    assert contact["email"] == "maria@testcorp.com"
    assert contact["tags"] == ["recruiter", "hr"]
    assert contact["id_typed"].startswith("CON-")


def test_563_add_contact_requires_name(setup_env):
    db, _ = setup_env
    with pytest.raises(ValueError):
        db.add_contact({"email": "x@y.com"})


def test_563_update_contact(setup_env):
    db, _ = setup_env
    cid = db.add_contact({"full_name": "X", "tags": ["recruiter"]})
    ok = db.update_contact(cid, {
        "full_name": "Y",
        "tags": ["hiring_manager"],
        "company": "NewCorp",
    })
    assert ok
    c = db.get_contact(cid)
    assert c["full_name"] == "Y"
    assert c["tags"] == ["hiring_manager"]
    assert c["company"] == "NewCorp"


def test_563_delete_contact_cascades_links(setup_env):
    db, _ = setup_env
    cid = db.add_contact({"full_name": "Tmp"})
    bid = db.add_application({"title": "T", "company": "C"})
    db.link_contact(cid, "application", bid, role="recruiter")
    assert len(db.get_contact_links(cid)) == 1
    db.delete_contact(cid)
    assert db.get_contact(cid) is None
    # FK cascade — links sollten weg sein
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM contact_links WHERE contact_id=?", (cid,)
    ).fetchall()
    assert len(rows) == 0


# ============= list_contacts mit Filtern ===============

def test_563_list_contacts_search(setup_env):
    db, _ = setup_env
    db.add_contact({"full_name": "Alpha", "company": "TestCorp"})
    db.add_contact({"full_name": "Beta", "company": "OtherCorp"})
    db.add_contact({"full_name": "Gamma", "email": "gamma@TestCorp.com"})
    # Suche nach "test" findet alle drei (case-insensitive)
    results = db.list_contacts(search="test")
    assert len(results) >= 2


def test_563_list_contacts_role_filter(setup_env):
    db, _ = setup_env
    db.add_contact({"full_name": "A", "tags": ["recruiter"]})
    db.add_contact({"full_name": "B", "tags": ["hr"]})
    db.add_contact({"full_name": "C", "tags": ["recruiter", "hiring_manager"]})
    recruiters = db.list_contacts(role="recruiter")
    assert len(recruiters) == 2
    hms = db.list_contacts(role="hiring_manager")
    assert len(hms) == 1


# ============= link_contact ===============

def test_563_link_contact_idempotent(setup_env):
    db, _ = setup_env
    cid = db.add_contact({"full_name": "X"})
    bid = db.add_application({"title": "T", "company": "C"})
    lid1 = db.link_contact(cid, "application", bid, role="recruiter")
    lid2 = db.link_contact(cid, "application", bid, role="recruiter")
    assert lid1 == lid2  # idempotent


def test_563_link_contact_different_roles(setup_env):
    db, _ = setup_env
    cid = db.add_contact({"full_name": "X"})
    bid = db.add_application({"title": "T", "company": "C"})
    # Verschiedene Rollen → verschiedene Verknuepfungen
    lid1 = db.link_contact(cid, "application", bid, role="recruiter")
    lid2 = db.link_contact(cid, "application", bid, role="interviewer")
    assert lid1 != lid2


def test_563_link_validates_kind(setup_env):
    db, _ = setup_env
    cid = db.add_contact({"full_name": "X"})
    with pytest.raises(ValueError):
        db.link_contact(cid, "invalid_kind", "some_id")


def test_563_get_contacts_for_target(setup_env):
    db, _ = setup_env
    cid_a = db.add_contact({"full_name": "Alice"})
    cid_b = db.add_contact({"full_name": "Bob"})
    bid = db.add_application({"title": "T", "company": "C"})
    db.link_contact(cid_a, "application", bid, role="recruiter")
    db.link_contact(cid_b, "application", bid, role="hiring_manager")
    contacts = db.get_contacts_for_target("application", bid)
    assert len(contacts) == 2
    by_name = {c["full_name"]: c for c in contacts}
    assert by_name["Alice"]["link_role"] == "recruiter"
    assert by_name["Bob"]["link_role"] == "hiring_manager"


# ============= MCP-Tools ===============

def test_563_kontakt_anlegen_tool(setup_env):
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "kontakt_anlegen", {
        "name": "Hans Schmidt",
        "email": "hans@bigcorp.com",
        "firma": "BigCorp",
        "rollen": ["recruiter"],
    })
    assert result["status"] == "angelegt"
    assert result["kontakt_id"].startswith("CON-")


def test_563_kontakt_validate_name(setup_env):
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "kontakt_anlegen", {"name": ""})
    assert "fehler" in result


def test_563_kontakte_auflisten_tool(setup_env):
    db, _ = setup_env
    db.add_contact({"full_name": "Alpha", "tags": ["recruiter"]})
    db.add_contact({"full_name": "Beta", "tags": ["hr"]})
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "kontakte_auflisten", {})
    assert result["anzahl"] == 2
    result = _call(mcp, "kontakte_auflisten", {"rolle": "recruiter"})
    assert result["anzahl"] == 1


def test_563_kontakt_verknuepfen_tool(setup_env):
    db, _ = setup_env
    cid = db.add_contact({"full_name": "Test"})
    bid = db.add_application({"title": "T", "company": "C"})
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "kontakt_verknuepfen", {
        "kontakt_id": cid,
        "ziel_typ": "bewerbung",
        "ziel_id": bid,
        "rolle": "recruiter",
    })
    assert result["status"] == "verknuepft"


def test_563_kontakte_zu_bewerbung_tool(setup_env):
    db, _ = setup_env
    cid = db.add_contact({"full_name": "Linked"})
    bid = db.add_application({"title": "T", "company": "C"})
    db.link_contact(cid, "application", bid, role="recruiter")
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "kontakte_zu_bewerbung", {"bewerbung_id": bid})
    assert result["anzahl"] == 1
    assert result["kontakte"][0]["full_name"] == "Linked"
    assert result["kontakte"][0]["link_role"] == "recruiter"
