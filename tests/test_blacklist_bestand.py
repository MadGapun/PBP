"""Blacklist auf den Bestand: ein Weg fuer Claude, Dashboard und
`blacklist_anwenden` (#992-Klasse).

Vorher sortierte `blacklist_verwalten('hinzufuegen', typ='firma')` per
rohem UPDATE aus: ueber ALLE Profile, ohne Zeitpunkt und Herkunft im
Protokoll (#1010) und mit einer eigenen Teilstring-Regel. Das Dashboard
sortierte beim Anlegen gar nicht aus.

Alle Firmen sind Platzhalter.
"""
from __future__ import annotations

import ast
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


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database
    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "bl.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Erstes"))
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, h, firma="Musterbetrieb GmbH", titel="Sachbearbeitung Einkauf"):
    db.save_jobs([{"hash": h, "title": titel, "company": firma,
                   "url": f"https://jobs.example.org/{h}"}])


def _aktiv(db, h):
    return bool(db.get_job(db.resolve_job_hash(h)).get("is_active"))


def _mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.suche import register
    mcp = FastMCP("t")
    register(mcp, db, logging.getLogger("t"))
    return mcp


def _call(mcp, name, args):
    async def lauf():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(lauf())


def test_claude_weg_nur_aktives_profil_und_mit_protokoll(db):
    _stelle(db, "bl1")
    anderes = db.create_profile("Zweites")
    db.switch_profile(anderes)
    _stelle(db, "bl2")
    erg = _call(_mcp(db), "blacklist_verwalten",
                {"aktion": "hinzufuegen", "typ": "firma", "wert": "Musterbetrieb GmbH"})
    assert erg.get("stellen_deaktiviert") == 1
    assert not _aktiv(db, "bl2")
    zeile = db.get_job(db.resolve_job_hash("bl2"))
    assert zeile.get("dismissed_at") and zeile.get("dismissed_by") == "ich"
    # die Stelle des ersten Profils bleibt
    db.switch_profile([p for p in db.get_profiles() if p["id"] != anderes][0]["id"])
    assert _aktiv(db, "bl1")


def test_claude_weg_nimmt_die_ausnahme_wie_der_suchlauf(db):
    _stelle(db, "bl3", titel="PLM Berater")
    _stelle(db, "bl4", titel="Lagerhelfer")
    _call(_mcp(db), "blacklist_verwalten",
          {"aktion": "hinzufuegen", "typ": "firma", "wert": "Musterbetrieb GmbH",
           "ausser_wenn_titel_enthaelt": ["PLM"]})
    assert _aktiv(db, "bl3") and not _aktiv(db, "bl4")


def test_dashboard_weg_sortiert_ebenso_aus(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    _stelle(db, "bl5")
    _stelle(db, "bl6", firma="Andere Firma AG")
    vorher = dash._db
    dash._db = db
    try:
        antwort = TestClient(dash.app).post(
            "/api/blacklist", json={"type": "firma", "value": "Musterbetrieb GmbH"}).json()
    finally:
        dash._db = vorher
    assert antwort["stellen_deaktiviert"] == 1
    assert not _aktiv(db, "bl5") and _aktiv(db, "bl6")


def test_anwenden_vorschau_schreibt_nichts(db):
    from bewerbungs_assistent.services import blacklist_bestand
    _stelle(db, "bl7")
    db.add_to_blacklist("firma", "Musterbetrieb GmbH")
    lauf = blacklist_bestand.anwenden(db, dry_run=True)
    assert len(lauf["treffer"]) == 1 and lauf["deaktiviert"] == 0
    assert _aktiv(db, "bl7")


def test_kein_rohes_update_auf_jobs_in_der_blacklist():
    """Aussortieren geht durch dismiss_job — kein eigenes UPDATE (#913)."""
    q = (_repo() / "src" / "bewerbungs_assistent" / "tools" / "suche.py").read_text(encoding="utf-8")
    for k in ast.walk(ast.parse(q)):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            assert not k.value.lstrip().upper().startswith("UPDATE JOBS SET IS_ACTIVE=0"), k.lineno


def test_neuer_firmeneintrag_wendet_nur_sich_selbst_an(db):
    """Ein bestehender Stichwort-Eintrag wirkt im Suchlauf; ein neuer
    Firmen-Eintrag darf nicht nebenbei nach ihm aussortieren — das bleibt
    `blacklist_anwenden` vorbehalten, mit Vorschau."""
    _stelle(db, "bl8", firma="Andere Firma AG", titel="Lagerhelfer")
    db.add_to_blacklist("keyword", "Lagerhelfer")
    _stelle(db, "bl9")
    _call(_mcp(db), "blacklist_verwalten",
          {"aktion": "hinzufuegen", "typ": "firma", "wert": "Musterbetrieb GmbH"})
    assert _aktiv(db, "bl8") and not _aktiv(db, "bl9")
