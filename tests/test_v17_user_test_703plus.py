"""Regressionstests fuer die User-Test-Funde 11./12.06. (beta.103):

- #708 (K20): busy_timeout auf der Haupt-Connection + rollback_if_stale-Netz
- #709/#710 (K21): force=True ueberstimmt Dedup; endkunde wird gespeichert
  und trennt Vermittler-Engagements in der Duplikat-Erkennung
- #711 (K22): Release-Hints nur anzeigen wenn Hint-Version > installierte
- #705 (K23): pbp_diagnose warnt bei gepflegtem Profil mit leeren Feldern
- #704 (K24): Workflow-Prompt weist Claude an, manuelle Quellen selbst
  abzuarbeiten
"""
import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_703p_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
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


def _make_mcp(db, modname):
    from fastmcp import FastMCP
    import importlib
    import logging
    mod = importlib.import_module(f"bewerbungs_assistent.tools.{modname}")
    mcp = FastMCP("test")
    mod.register(mcp, db, logging.getLogger("test"))
    return mcp


# ============= #708 / K20: DB-Lock-Haertung =============

def test_708_busy_timeout_gesetzt(setup_env):
    db = setup_env
    from bewerbungs_assistent.database import BUSY_TIMEOUT_MS
    conn = db.connect()
    timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    # #723: auf 30s angehoben (war 5s) — ueberdauert legitime Bulk-Writes,
    # bleibt weit unter dem 4-Min-Client-Timeout.
    assert timeout == BUSY_TIMEOUT_MS, f"busy_timeout ist {timeout}, erwartet {BUSY_TIMEOUT_MS}"
    assert BUSY_TIMEOUT_MS == 30000


def test_708_rollback_if_stale_raeumt_leak(setup_env):
    db = setup_env
    conn = db.connect()
    # Leak simulieren: Write ohne commit (implizite offene Transaktion)
    conn.execute("UPDATE settings SET value='x' WHERE key='nonexistent'")
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('test_leak', '1')"
    )
    assert conn.in_transaction, "Setup: Transaktion sollte offen sein"
    assert db.rollback_if_stale(context="Test") is True
    assert not conn.in_transaction, "Transaktion muss zurueckgerollt sein"
    # Der geleakte Insert ist weg
    row = conn.execute("SELECT 1 FROM settings WHERE key='test_leak'").fetchone()
    assert row is None


def test_708_rollback_if_stale_noop_ohne_transaktion(setup_env):
    db = setup_env
    db.connect()
    assert db.rollback_if_stale() is False


# ============= #709/#710 / K21: Dedup force + endkunde =============

def _neue_bewerbung(db, mcp, **kwargs):
    args = {"title": "PLM Consultant", "company": "VirtoTech Ltd.",
            "bereits_beworben": True}
    args.update(kwargs)
    return _call(mcp, "bewerbung_erstellen", args)


def test_709_force_ueberstimmt_dedup(setup_env):
    db = setup_env
    mcp = _make_mcp(db, "bewerbungen")
    r1 = _neue_bewerbung(db, mcp)
    assert r1.get("status") != "duplikat", r1
    # Exaktes Duplikat -> geblockt, Meldung nennt force
    r2 = _neue_bewerbung(db, mcp)
    assert r2.get("status") == "duplikat", r2
    assert "force" in r2.get("nachricht", ""), r2
    # force=True -> wird angelegt
    r3 = _neue_bewerbung(db, mcp, force=True)
    assert r3.get("status") != "duplikat", r3


def test_710_endkunde_gespeichert_und_trennt(setup_env):
    db = setup_env
    mcp = _make_mcp(db, "bewerbungen")
    r1 = _neue_bewerbung(db, mcp, endkunde="Rota Yokogawa")
    assert r1.get("status") != "duplikat", r1
    # Gleicher Vermittler + gleicher Titel, ANDERER Endkunde -> kein Duplikat
    r2 = _neue_bewerbung(db, mcp, endkunde="PRO.FILE Assessment Kunde")
    assert r2.get("status") != "duplikat", r2
    # endkunde ist persistiert
    apps = db.get_applications()
    endkunden = sorted((a.get("endkunde") or "") for a in apps)
    assert "Rota Yokogawa" in endkunden, endkunden
    # Gleicher Endkunde nochmal -> Duplikat
    r3 = _neue_bewerbung(db, mcp, endkunde="Rota Yokogawa")
    assert r3.get("status") == "duplikat", r3


# ============= #711 / K22: Versionsvergleich =============

def test_711_version_tuple_ordnung():
    from bewerbungs_assistent.dashboard import _version_tuple as vt
    assert vt("1.7.0-beta.101") < vt("1.7.0-beta.102")
    assert vt("1.7.0-beta.102") < vt("1.7.0")          # Stable > jede Beta
    assert vt("1.7.0") < vt("1.7.1")
    assert vt("1.6.10") < vt("1.7.0-beta.1")
    assert not (vt("1.7.0-beta.101") > vt("1.7.0-beta.102"))


def test_711_release_hint_nur_bei_neuerer_version(setup_env, tmp_path):
    """Hint mit version == installierte Version wird NICHT gezeigt;
    Hint mit hoeherer version schon."""
    db = setup_env
    import importlib
    import bewerbungs_assistent.dashboard as dash
    importlib.reload(dash)
    dash._db = db
    from bewerbungs_assistent import __version__

    def _hints_mit(version_feld):
        hints_file = tmp_path / "hints.json"
        hints_file.write_text(json.dumps({"hints": [{
            "id": "x", "title": f"Neu in {version_feld}",
            "text": "t", "version": version_feld,
        }]}), encoding="utf-8")
        os.environ["PBP_HINTS_URL"] = str(hints_file)
        if hasattr(dash.api_public_hints, "_cache"):
            delattr(dash.api_public_hints, "_cache")
        from fastapi.testclient import TestClient
        client = TestClient(dash.app)
        return client.get("/api/public/hints").json()["hints"]

    try:
        assert _hints_mit(__version__) == [], "eigener Release darf nicht angekuendigt werden"
        assert len(_hints_mit("99.0.0")) == 1, "echtes Update muss angekuendigt werden"
    finally:
        os.environ.pop("PBP_HINTS_URL", None)
        if hasattr(dash.api_public_hints, "_cache"):
            delattr(dash.api_public_hints, "_cache")


# ============= #705 / K23: Profil-Integritaets-Warnung =============

def test_705_diagnose_warnt_bei_leeren_kontaktfeldern(setup_env):
    db = setup_env
    # Gepflegtes Profil (Positionen + Skills), aber Kontaktfelder leer
    db.add_position({"title": "Consultant", "company": "X",
                     "start_date": "2020-01"})
    for s in ("Python", "PLM", "SAP"):
        db.add_skill({"name": s, "level": 4, "category": "fachlich"})
    mcp = _make_mcp(db, "analyse")
    res = _call(mcp, "pbp_diagnose", {})
    integ = [w for w in res.get("warnungen", [])
             if w.get("bereich") == "Profil-Integritaet"]
    assert integ, res.get("warnungen")
    assert "backups" in integ[0]["loesung"].lower()


# ============= #704 / K24: Workflow-Anweisung =============

def test_704_workflow_arbeitet_manuelle_quellen_ab(setup_env):
    db = setup_env
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    text = _prompt_registry(db)["jobsuche_workflow"]()
    assert "ARBEITE DIESE QUELLEN SELBST AB" in text
    assert "stelle_manuell_anlegen" in text
