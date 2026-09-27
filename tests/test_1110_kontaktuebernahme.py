"""#1110: Kontaktuebernahme aus dem Bestand ohne Dubletten, ohne
wiederkehrende Ablehnungen, und Vorschlaege nicht in der Hauptliste."""
from __future__ import annotations

import asyncio
import logging
import os
from types import SimpleNamespace

import pytest


class _KI:
    def __init__(self, kontakte):
        self.kontakte = kontakte

    def get_status(self, force_refresh=False):
        return SimpleNamespace(ollama_available=True, available_models=["m"],
                               user_state="active")

    def run(self, kind, payload):
        return SimpleNamespace(success=True, payload={"contacts": self.kontakte})


RECRUITERIN = {"name": "Erika Beispiel", "email": "erika@example.com",
               "kategorie": "recruiter", "rolle": "Recruiterin", "confidence": 0.9}


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Kontakte"})
    from bewerbungs_assistent.services import llm_service
    d.ki = _KI([RECRUITERIN])
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db=None: d.ki)
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _werkzeug(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1110")
    register_all(mcp, db, logging.getLogger("test.1110"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def _bewerbungen(db, n):
    for i in range(n):
        db.add_application({"title": f"Stelle {i}", "company": "Musterbetrieb GmbH",
                            "status": "beworben", "notes": "Kontakt: Erika Beispiel"})


def _vorschlaege(db):
    return [k for k in db.list_contacts(mit_vorschlaegen=True) if k.get("is_pending")]


@pytest.mark.parametrize("werkzeug, args", [
    ("kontakte_aus_bestand_importieren", {"dry_run": False}),
    ("kontakte_aus_bewerbungen_extrahieren", {"dry_run": False, "max_bewerbungen": 20}),
])
def test_eine_person_in_zehn_bewerbungen_ist_ein_vorschlag(db, werkzeug, args):
    _bewerbungen(db, 10)
    erg = _werkzeug(db, werkzeug, args)
    assert len(_vorschlaege(db)) == 1, erg
    assert erg["schon_vorhanden"] == 9


def test_vorhandene_person_wird_kein_vorschlag(db):
    db.add_contact({"full_name": "Erika Beispiel", "email": "erika@example.com",
                    "company": "Musterbetrieb GmbH"})
    _bewerbungen(db, 2)
    _werkzeug(db, "kontakte_aus_bestand_importieren", {"dry_run": False})
    assert _vorschlaege(db) == []


def test_abgelehnter_vorschlag_kommt_nicht_wieder(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    _bewerbungen(db, 1)
    _werkzeug(db, "kontakte_aus_bestand_importieren", {"dry_run": False})
    vorschlag = _vorschlaege(db)[0]
    dash._db = db
    assert TestClient(dash.app).delete(f"/api/contacts/pending/{vorschlag['id']}").status_code == 200
    erg = _werkzeug(db, "kontakte_aus_bestand_importieren", {"dry_run": False})
    assert _vorschlaege(db) == []
    assert erg["frueher_abgelehnt"] == 1
    # Die Spur ist ein Hash — kein Name, keine Mail.
    zeile = db.connect().execute("SELECT * FROM kontakt_vorschlag_abgelehnt").fetchone()
    assert "erika" not in str(tuple(zeile)).lower()


def test_vorschlaege_nicht_in_der_hauptliste(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    _bewerbungen(db, 1)
    _werkzeug(db, "kontakte_aus_bestand_importieren", {"dry_run": False})
    assert db.list_contacts() == []
    dash._db = db
    daten = TestClient(dash.app).get("/api/contacts").json()
    liste = daten.get("contacts", daten) if isinstance(daten, dict) else daten
    assert liste == [] or all(not k.get("is_pending") for k in liste)
    assert _werkzeug(db, "kontakte_auflisten", {}).get("anzahl", 0) == 0


def test_nur_telefon_wird_wiedererkannt(db):
    from bewerbungs_assistent.services import kontakt_pflicht
    a = kontakt_pflicht.sicherstellen(db, telefon="0100 5551234", firma="Musterbetrieb GmbH")
    b = kontakt_pflicht.sicherstellen(db, telefon="0100/555-1234", firma="Musterbetrieb GmbH")
    assert a["status"] == "angelegt" and b["status"] == "vorhanden"
