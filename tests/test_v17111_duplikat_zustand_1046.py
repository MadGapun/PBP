"""Tests fuer #1046 — die Duplikat-Meldung nennt den Zustand der vorhandenen Stelle.

Bis v1.7.110 meldeten `stelle_manuell_anlegen` und
`linkedin_treffer_uebernehmen` nur "Diese Stelle existiert bereits (Hash:
...)". Im belegten Lauf kamen zwei von sieben Stellen so zurueck, und
daraufhin wurde vorgeschlagen, sie auszusortieren — beide waren laengst
aussortiert.
"""
import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import stellen_zustand  # noqa: E402

TEXT = ("Die Musterfirma Nord sucht Verstaerkung fuer Projekte im Bereich "
        "Produktdatenmanagement und begleitet Kunden bei der Einfuehrung. ") * 12


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "test.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.switch_profile(datenbank.create_profile("Muster"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def mcp(db):
    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.jobs import register
    server = FastMCP("test")
    register(server, db, logging.getLogger("test"))
    return server


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def _anlegen(mcp, titel="Berater Produktdaten", quelle="firmenwebsite"):
    return _call(mcp, "stelle_manuell_anlegen", {
        "titel": titel, "firma": "Musterfirma Nord",
        "url": "https://example.com/1046/berater", "beschreibung": TEXT,
        "quelle": quelle})


def _bewerbung(db, job_hash="", titel="Berater Produktdaten"):
    return db.add_application({
        "title": titel, "company": "Musterfirma Nord",
        "job_hash": job_hash, "status": "beworben"})


# ------------------------------------------------ AK 1-3: gleiche Kennung


def test_eine_aktive_stelle_wird_als_aktiv_gemeldet(mcp):
    erst = _anlegen(mcp)
    assert erst["status"] == "angelegt", erst
    zweit = _anlegen(mcp)
    assert "fehler" not in zweit
    assert zweit["duplikat"] == "duplikat_aktiv"
    assert zweit["vorhandene_stelle"]["zustand"] == "aktiv"
    assert zweit["existing_hash"] == erst["hash"]
    assert "stelle_bewerten" in zweit["nachricht"]


def test_eine_aussortierte_stelle_nennt_grund_und_zeitpunkt(mcp, db):
    erst = _anlegen(mcp)
    db.dismiss_job(erst["hash"], reason="falsches_fachgebiet")
    zweit = _anlegen(mcp)
    block = zweit["vorhandene_stelle"]
    assert zweit["duplikat"] == "duplikat_aussortiert"
    assert block["aussortier_gruende"] == ["falsches_fachgebiet"]
    assert block.get("aussortiert_am")
    assert "zu tun ist nichts" in zweit["nachricht"]
    assert "stelle_reaktivieren" in zweit["nachricht"]


def test_eine_beworbene_stelle_nennt_bewerbung_und_status(mcp, db):
    erst = _anlegen(mcp)
    bewerbung_id = _bewerbung(db, erst["hash"])
    zweit = _anlegen(mcp)
    block = zweit["vorhandene_stelle"]
    assert zweit["duplikat"] == "duplikat_beworben"
    assert block["bewerbung_id"] == bewerbung_id[:8]
    assert block["bewerbungsstatus"] == "beworben"
    assert "Keine zweite Bewerbung" in zweit["nachricht"]


def test_beworben_schlaegt_aussortiert(mcp, db):
    """Auch eine aussortierte Stelle mit Bewerbung soll vor einer zweiten
    Bewerbung warnen — das ist die teurere Verwechslung."""
    erst = _anlegen(mcp)
    _bewerbung(db, erst["hash"])
    db.dismiss_job(erst["hash"], reason="bereits_beworben")
    assert _anlegen(mcp)["duplikat"] == "duplikat_beworben"


# ------------------------------------------------ AK 4: beide Wege, alle Stufen


def test_eine_laufende_bewerbung_mit_gleichem_titel_nennt_den_zustand(mcp, db):
    """Stufe A: andere Kennung, aber eine laufende Bewerbung passt."""
    bewerbung_id = _bewerbung(db)
    erg = _anlegen(mcp, quelle="xing")
    assert erg["warnung"] == "duplikat_bewerbung"
    assert erg["duplikat"] == "duplikat_beworben"
    assert erg["vorhandene_stelle"]["bewerbung_id"] == bewerbung_id[:8]


def test_eine_gleiche_aktive_stelle_unter_anderer_kennung_nennt_den_zustand(mcp):
    """Stufe B: identische aktive Stelle aus einer anderen Quelle."""
    erst = _anlegen(mcp, quelle="firmenwebsite")
    erg = _anlegen(mcp, quelle="xing")
    assert erg["warnung"] == "duplikat_aktive_stelle"
    assert erg["duplikat"] == "duplikat_aktiv"
    assert erg["vorhandene_stelle"]["zustand"] == "aktiv"
    assert erg["existing_hash"] == erst["hash"]


_TITEL = {1: "Berater Produktdaten", 2: "Entwickler Steuerungstechnik",
          3: "Projektleiter Anlagenbau"}


def _treffer(nummer):
    # Deutlich verschiedene Titel: "Berater Produktdaten 1/2/3" hielt die
    # Duplikat-Stufe B beim ersten Lauf zu Recht fuer dieselbe Stelle.
    return {"job_id": f"10460{nummer}", "titel": _TITEL[nummer],
            "firma": "Musterfirma Nord", "beschreibung": TEXT}


def test_der_linkedin_trichter_unterscheidet_die_drei_faelle(mcp, db):
    """AK 5: nicht mehr alles unter "abgewiesen"."""
    eintraege = [_treffer(1), _treffer(2), _treffer(3)]
    erst = _call(mcp, "linkedin_treffer_uebernehmen",
                 {"treffer": eintraege, "dry_run": False})
    assert erst["trichter"]["angelegt"] == 3, erst
    kennungen = {a["job_id"]: a["hash"] for a in erst["angelegt"]}
    db.dismiss_job(kennungen["104602"], reason="falsches_fachgebiet")
    _bewerbung(db, kennungen["104603"], titel=_TITEL[3])

    zweit = _call(mcp, "linkedin_treffer_uebernehmen",
                  {"treffer": eintraege, "dry_run": False})
    gruende = zweit["trichter"]["gruende"]
    assert gruende == {"duplikat_aktiv": 1, "duplikat_aussortiert": 1,
                       "duplikat_beworben": 1}, gruende
    for eintrag in zweit["uebersprungen"]:
        assert eintrag["vorhandene_stelle"]["zustand"] in stellen_zustand.ZUSTAENDE
    for schluessel in gruende:
        assert schluessel in zweit["trichter_text"]


def test_linkedin_nennt_auch_bei_einer_laufenden_bewerbung_den_zustand(mcp, db):
    """Stufe A ueber den LinkedIn-Weg: andere Kennung, laufende Bewerbung
    mit gleichem Titel. Bei gleicher Kennung ist der Warnungsname schon der
    Zustand — erst hier zeigt sich, ob der Trichter `duplikat` bevorzugt."""
    _bewerbung(db, titel=_TITEL[1])
    erg = _call(mcp, "linkedin_treffer_uebernehmen",
                {"treffer": [_treffer(1)], "dry_run": False})
    assert erg["trichter"]["gruende"] == {"duplikat_beworben": 1}, erg["trichter"]
    assert erg["uebersprungen"][0]["vorhandene_stelle"]["zustand"] == "beworben"


# ------------------------------------------------ die Texte selbst


def test_jeder_zustand_hat_seinen_eigenen_naechsten_schritt():
    aktiv = {"hash": "abc", "zustand": "aktiv"}
    aussortiert = {"hash": "abc", "zustand": "aussortiert", "aussortier_gruende": []}
    beworben = {"hash": "abc", "zustand": "beworben", "bewerbung_id": "b1",
                "bewerbungsstatus": ""}
    assert stellen_zustand.schluessel(aktiv) == "duplikat_aktiv"
    assert "stelle_bewerten('abc'" in stellen_zustand.nachricht(aktiv)
    assert "ohne Grund" in stellen_zustand.nachricht(aussortiert)
    assert "Status: unbekannt" in stellen_zustand.nachricht(beworben)
    assert len({stellen_zustand.nachricht(b) for b in (aktiv, aussortiert, beworben)}) == 3
