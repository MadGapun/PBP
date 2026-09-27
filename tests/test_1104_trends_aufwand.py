"""#1104: branchen_trends zaehlt Anzeigen mit Wortgrenzen und ohne feste
Fachrichtung; Aufwand und Termin-Export nur fuer das aktive Profil."""
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


def _trends(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1104")
    register_all(mcp, db, logging.getLogger("test.1104"))

    async def lauf():
        t = await mcp.get_tool("branchen_trends")
        return (await t.run({})).structured_content
    return asyncio.run(lauf())


def _stellen(db, texte):
    db.save_jobs([{"hash": f"t{i}1104", "title": f"Stelle {i}", "company": f"Firma {i} GmbH",
                   "url": f"https://example.com/{i}", "source": "manuell",
                   "description": f"{t} Anzeige Nummer {i}."}
                  for i, t in enumerate(texte)])


def test_kein_wert_ueber_hundert(db):
    db.save_profile({"name": "Trends"})
    _stellen(db, ["Python Python Python und SQL. " * 3] * 3 + ["Nur SQL gefragt. " * 3])
    erg = _trends(db)
    assert erg["status"] == "ok", erg
    assert all(e["prozent_jobs"] <= 100 for e in erg["top_skills"]), erg["top_skills"]
    python = next(e for e in erg["top_skills"] if e["skill"].lower() == "python")
    assert python["nennungen"] == 3


def test_keine_treffer_in_fremden_woertern(db):
    db.save_profile({"name": "Trends"})
    _stellen(db, ["Wir erwarten Skills im Detail per Mail, dazu ein Restaurant-Besuch. " * 3] * 4)
    namen = {e["skill"].lower() for e in _trends(db)["top_skills"]}
    assert not namen & {"ki", "ai", "rest"}, namen


def test_pflegeprofil_bekommt_keine_it_luecke(db):
    db.save_profile({"name": "Pflege"})
    db.add_skill({"name": "Grundpflege", "category": "fachlich", "level": 4})
    texte = ["Pflegefachkraft (m/w/d) für die Grundpflege und Behandlungspflege, "
             "Wundversorgung und Pflegedokumentation im Schichtdienst. " * 2] * 4
    _stellen(db, texte)
    luecke = {e["skill"].lower() for e in _trends(db)["skill_gap"]}
    assert not luecke & {"cad", "plm", "sap", "python", "java", "catia", "nx"}, luecke


def test_zu_wenig_anzeigen_keine_luecke(db):
    db.save_profile({"name": "Trends"})
    _stellen(db, ["Python gesucht. " * 5])
    erg = _trends(db)
    assert erg["status"] == "zu_wenig_daten" and "skill_gap" not in erg


# ── Aufwand und Termin-Export ────────────────────────────────────────

def _zwei_profile_mit_terminen(db):
    fremd = db.create_profile("Fremd")
    db.switch_profile(fremd)
    db.add_meeting({"title": "Fremdtermin", "meeting_date": "2027-01-01T10:00",
                    "vorbereitungszeit_min": 60})
    eigen = db.create_profile("Eigen")
    db.switch_profile(eigen)
    db.add_meeting({"title": "Eigener Termin", "meeting_date": "2027-01-02T10:00"})


def test_aufwand_nur_eigene_termine(db):
    _zwei_profile_mit_terminen(db)
    erg = db.get_aufwand_summary()
    assert erg["termine_anzahl"] == 1, erg


def test_termin_export_nur_eigene(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    _zwei_profile_mit_terminen(db)
    dash._db = db
    text = TestClient(dash.app).get("/api/meetings/export.csv").text
    assert "Eigener Termin" in text and "Fremdtermin" not in text


def test_extraktor_wortgrenzen_beide_richtungen():
    from bewerbungs_assistent.services import stellen_skills as sk
    vok = sk.vokabular() | {"rest"}
    assert "rest" not in sk.extrahiere_skills("Ein Restaurant-Besuch ist inklusive. " * 2, vok)
    assert "rest" in sk.extrahiere_skills("Erfahrung mit REST und SQL. " * 2, vok)
    assert "ki" in [b.lower() for b in sk.extrahiere_skills("KI-Kenntnisse sind ein Plus. " * 2, vok)]


def test_beugungsformen_einer_anzeige_zaehlen_einmal(db, monkeypatch):
    from bewerbungs_assistent.services import stellen_skills as sk
    monkeypatch.setattr(sk, "extrahiere_skills", lambda text, vok=None: ["Prozess", "Prozesse"])
    db.save_profile({"name": "Trends"})
    _stellen(db, ["Text a. " * 5, "Text b. " * 5, "Text c. " * 5])
    eintrag = _trends(db)["top_skills"][0]
    assert eintrag["nennungen"] == 3 and eintrag["prozent_jobs"] == 100.0, eintrag
