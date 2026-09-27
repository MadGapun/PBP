"""#1108: Die Ersterfassung endet auch ohne Berufserfahrung oder Ausbildung,
und Praeferenzen gelten erst nach einer Antwort als erledigt."""
from __future__ import annotations

import asyncio
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
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _werkzeug(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1108")
    register_all(mcp, db, logging.getLogger("test.1108"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def test_ohne_erfahrung_und_ausbildung_zum_abschluss(db):
    _werkzeug(db, "profil_erstellen", {"name": "Einsteigerin", "email": "a@example.com",
                                       "stellentyp": "festanstellung"})
    db.add_skill({"name": "Kundenservice", "category": "fachlich", "level": 3})
    erg = _werkzeug(db, "erfassung_fortschritt_speichern", {"bereich": "berufserfahrung"})
    assert erg["phase"] == "erfassung"
    erg = _werkzeug(db, "erfassung_fortschritt_speichern", {"bereich": "ausbildung"})
    assert erg["phase"] == "review", erg
    erg = _werkzeug(db, "erfassung_fortschritt_speichern", {"bereich": "review_abgeschlossen"})
    assert erg["phase"] == "suche"


def test_praeferenzen_nicht_vor_der_ersten_frage(db):
    from bewerbungs_assistent.services.ersterfassung_phasen import stand
    _werkzeug(db, "profil_erstellen", {"name": "Neu", "email": "n@example.com"})
    assert stand(db.get_profile())["praeferenzen"] is False
    _werkzeug(db, "profil_erstellen", {"name": "Neu", "email": "n@example.com",
                                       "stellentyp": "beides"})
    assert stand(db.get_profile())["praeferenzen"] is True


def test_umlaut_bereich_und_unbekannter(db):
    _werkzeug(db, "profil_erstellen", {"name": "Neu", "email": "n@example.com"})
    erg = _werkzeug(db, "erfassung_fortschritt_speichern", {"bereich": "präferenzen"})
    assert erg["bereich"] == "praeferenzen"
    assert db.get_erfassung_fortschritt().get("praeferenzen") is True
    erg = _werkzeug(db, "erfassung_fortschritt_speichern", {"bereich": "hobbys"})
    assert "fehler" in erg and "hobbys" not in db.get_erfassung_fortschritt()


def test_dashboard_und_ersterfassung_rechnen_gleich(db):
    from bewerbungs_assistent.services.ersterfassung_phasen import stand
    from bewerbungs_assistent.services.profile_service import get_profile_completeness
    _werkzeug(db, "profil_erstellen", {"name": "Neu", "email": "n@example.com"})
    _werkzeug(db, "erfassung_fortschritt_speichern", {"bereich": "ausbildung"})
    profil = db.get_profile()
    checks = get_profile_completeness(profil)["checks"]
    s = stand(profil)
    for a, b in (("berufserfahrung", "berufserfahrung"), ("ausbildung", "ausbildung"),
                 ("praeferenzen", "praeferenzen")):
        assert checks[a] == s[b], (a, checks[a], s[b])
    assert checks["ausbildung"] is True


def test_lesen_nutzt_dieselbe_regel(db):
    _werkzeug(db, "profil_erstellen", {"name": "Neu", "email": "n@example.com"})
    _werkzeug(db, "erfassung_fortschritt_speichern", {"bereich": "berufserfahrung"})
    erg = _werkzeug(db, "erfassung_fortschritt_lesen", {})
    assert erg["bereiche"]["berufserfahrung"] is True
    assert erg["bereiche"]["praeferenzen"] is False
