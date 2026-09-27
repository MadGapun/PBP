"""jobtitel_verwalten: IDs sichtbar, kein Erfolg ueber eine Nicht-Aenderung
(#997-Klasse, #994-Klasse).

Kein Werkzeug gab die IDs der Jobtitel heraus, und eine unbekannte ID
meldete trotzdem "geloescht". Der Dashboard-Weg antwortete laengst mit 404.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database
    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "titel.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Titel"))
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _call(db, **args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.profil import register
    mcp = FastMCP("t")
    register(mcp, db, logging.getLogger("t"))

    async def lauf():
        tool = await mcp.get_tool("jobtitel_verwalten")
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(lauf())


def test_anzeigen_nennt_die_ids(db):
    tid = db.add_job_title("Sachbearbeitung Einkauf")
    erg = _call(db, aktion="anzeigen")
    assert erg["anzahl"] == 1 and erg["titel"][0]["id"] == tid


def test_unbekannte_id_meldet_keinen_erfolg(db):
    for aktion in ("loeschen", "aendern", "deaktivieren", "aktivieren"):
        erg = _call(db, titel_id="gibt-es-nicht", aktion=aktion, neuer_titel="X")
        assert erg["status"] == "nicht_gefunden", aktion
        assert "anzeigen" in erg["naechster_schritt"]


def test_titeltext_statt_id(db):
    db.add_job_title("Sachbearbeitung Einkauf")
    erg = _call(db, titel_id="sachbearbeitung einkauf", aktion="deaktivieren")
    assert erg["status"] == "deaktiviert"
    assert db.get_suggested_job_titles()[0]["is_active"] == 0


def test_aendern_und_loeschen(db):
    tid = db.add_job_title("Einkauf")
    assert _call(db, titel_id=tid, aktion="aendern", neuer_titel="Einkauf Junior")["status"] == "geaendert"
    assert db.get_suggested_job_titles()[0]["title"] == "Einkauf Junior"
    assert _call(db, titel_id=tid, aktion="loeschen")["status"] == "geloescht"
    assert db.get_suggested_job_titles() == []


def test_titel_eines_anderen_profils_bleibt_unberuehrt(db):
    tid = db.add_job_title("Einkauf")
    erstes = db.get_active_profile_id()
    db.switch_profile(db.create_profile("Zweites"))
    assert _call(db, titel_id=tid, aktion="loeschen")["status"] == "nicht_gefunden"
    assert len(db.get_suggested_job_titles(erstes)) == 1


def test_verschwindet_der_titel_dazwischen_kein_erfolg(db, monkeypatch):
    """Zwischen Nachsehen und Loeschen kann das Dashboard den Titel schon
    entfernt haben — die Antwort liest, was die Datenbank sagt."""
    tid = db.add_job_title("Einkauf")
    monkeypatch.setattr(type(db), "delete_job_title", lambda self, t, profile_id=None: False)
    assert _call(db, titel_id=tid, aktion="loeschen")["status"] == "nicht_gefunden"
