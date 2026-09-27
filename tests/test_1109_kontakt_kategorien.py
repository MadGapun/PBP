"""#1109: Umbenennen trennt eine Kontakt-Kategorie nicht von ihren
Kontakten, und Systemkategorien entstehen nicht doppelt."""
from __future__ import annotations

import asyncio
import json
import logging
import os

import pytest


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Kategorien"})
    d._ensure_default_categories()
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _kat(db, slug):
    return next(k for k in db.list_contact_categories() if k["slug"] == slug)


def _kontakte(db):
    """Zwei Kontakte, beide Speicherformen der Tags."""
    a = db.add_contact({"full_name": "Erika Beispiel", "company": "Musterbetrieb GmbH"})
    b = db.add_contact({"full_name": "Max Muster", "company": "Musterbetrieb GmbH"})
    con = db.connect()
    con.execute("UPDATE contacts SET tags=? WHERE id=?", (json.dumps(["recruiter"]), a))
    con.execute("UPDATE contacts SET tags=? WHERE id=?", ("recruiter, sonstiges", b))
    con.commit()


def test_umbenennen_behaelt_die_kontakte(db):
    _kontakte(db)
    kat = _kat(db, "recruiter")
    assert kat["contact_count"] == 2
    assert db.update_contact_category(kat["id"], name="Personalvermittlung")
    neu = next(k for k in db.list_contact_categories() if k["id"] == kat["id"])
    assert neu["name"] == "Personalvermittlung" and neu["contact_count"] == 2


def test_systemkategorie_entsteht_nicht_neu(db):
    kat = _kat(db, "recruiter")
    db.update_contact_category(kat["id"], name="Personalvermittlung")
    assert db._ensure_default_categories() == 0
    namen = [k["name"] for k in db.list_contact_categories()]
    assert "Recruiter" not in namen


def test_loeschen_nach_umbenennen_prueft_die_kontakte(db):
    _kontakte(db)
    kat_id = db.add_contact_category("Headhunter")
    con = db.connect()
    con.execute("UPDATE contacts SET tags=? WHERE full_name='Max Muster'", ('["headhunter"]',))
    con.commit()
    db.update_contact_category(kat_id, name="Personalberatung")
    erg = db.delete_contact_category(kat_id)
    assert erg.get("betroffene_kontakte") == 1, erg


def test_ueber_dashboard_und_werkzeug(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    _kontakte(db)
    dash._db = db
    tc = TestClient(dash.app)
    kat = _kat(db, "recruiter")
    assert tc.put(f"/api/contacts/categories/{kat['id']}", json={"name": "Vermittlung"}).status_code == 200
    mcp = FastMCP("PBP #1109")
    register_all(mcp, db, logging.getLogger("test.1109"))

    async def lauf():
        t = await mcp.get_tool("kontakt_kategorie_bearbeiten")
        return (await t.run({"kategorie_id": kat["id"], "name": "Agentur"})).structured_content
    asyncio.run(lauf())
    neu = next(k for k in db.list_contact_categories() if k["id"] == kat["id"])
    assert neu["name"] == "Agentur" and neu["contact_count"] == 2


def test_neue_kategorie_mit_altem_namen(db):
    kat = _kat(db, "recruiter")
    db.update_contact_category(kat["id"], name="Personalvermittlung")
    neu_id = db.add_contact_category("Recruiter")
    neu = next(k for k in db.list_contact_categories() if k["id"] == neu_id)
    assert neu["slug"] != "recruiter"
    with pytest.raises(ValueError):
        db.add_contact_category("Personalvermittlung")


def test_bestand_reparatur(db):
    from bewerbungs_assistent.services.contact_colors import slug_for_name
    _kontakte(db)
    kat = _kat(db, "recruiter")
    con = db.connect()
    # Stand vor #1109: der Schluessel wanderte mit dem Namen.
    con.execute("UPDATE contact_categories SET name=?, slug=? WHERE id=?",
                ("Personalvermittlung", slug_for_name("Personalvermittlung"), kat["id"]))
    con.commit()
    erg = db.kontakt_kategorien_reparieren()
    assert [r["id"] for r in erg["repariert"]] == [kat["id"]]
    assert next(k for k in db.list_contact_categories() if k["id"] == kat["id"])["contact_count"] == 2
    assert db.kontakt_kategorien_reparieren() == {"repariert": [], "doppelt": []}


def test_bestand_mit_dublette_wird_gemeldet_nicht_geloescht(db):
    from bewerbungs_assistent.services.contact_colors import slug_for_name
    kat = _kat(db, "recruiter")
    con = db.connect()
    con.execute("UPDATE contact_categories SET name=?, slug=? WHERE id=?",
                ("Personalvermittlung", slug_for_name("Personalvermittlung"), kat["id"]))
    con.commit()
    db._ensure_default_categories()  # legt "recruiter" neu an
    vorher = len(db.list_contact_categories())
    erg = db.kontakt_kategorien_reparieren()
    assert erg["doppelt"] and erg["repariert"] == []
    assert len(db.list_contact_categories()) == vorher
