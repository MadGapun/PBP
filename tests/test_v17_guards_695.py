"""Regression #695: Stille Falsch-Erfolge in Kern-Tools.

- stelle_bewerten: Fehler statt Phantom-Erfolg bei unbekanntem Hash
  (und KEINE Statistik-Verfaelschung)
- bewerbung_status_aendern: Fehler bei unbekannter ID; APP-Praefix wird
  akzeptiert; falsches Praefix wird abgelehnt
- jobsuche_starten: startet nicht ohne Suchkriterien (BA-Default-Flut)
"""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_695_")
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


# ============= stelle_bewerten =============

def test_695_stelle_bewerten_unbekannter_hash(setup_env):
    db = setup_env
    mcp = _make_mcp(db, "jobs")
    conn = db.connect()
    vorher = conn.execute(
        "SELECT COALESCE(SUM(usage_count),0) AS n FROM dismiss_reasons"
    ).fetchone()["n"]
    res = _call(mcp, "stelle_bewerten", {
        "job_hash": "ffffffff", "bewertung": "passt_nicht",
        "gruende": ["zeitarbeit"],
    })
    assert "fehler" in res, res
    assert res.get("status") != "aussortiert"
    nachher = conn.execute(
        "SELECT COALESCE(SUM(usage_count),0) AS n FROM dismiss_reasons"
    ).fetchone()["n"]
    assert vorher == nachher, "Phantom-Eintrag in der Ablehnungs-Statistik"


def test_695_stelle_bewerten_passt_unbekannt(setup_env):
    db = setup_env
    mcp = _make_mcp(db, "jobs")
    res = _call(mcp, "stelle_bewerten", {"job_hash": "ffffffff", "bewertung": "passt"})
    assert "fehler" in res, res


# ============= bewerbung_status_aendern =============

def test_695_status_aendern_unbekannte_id(setup_env):
    db = setup_env
    mcp = _make_mcp(db, "bewerbungen")
    res = _call(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": "deadbeef", "neuer_status": "interview",
    })
    assert "fehler" in res, res
    assert res.get("status") != "aktualisiert"


def test_695_status_aendern_app_praefix(setup_env):
    db = setup_env
    aid = db.add_application({"title": "T", "company": "C", "status": "beworben"})
    mcp = _make_mcp(db, "bewerbungen")
    res = _call(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": f"APP-{aid}", "neuer_status": "interview",
    })
    assert "fehler" not in res, res
    app = db.get_application(aid)
    assert app["status"] == "interview", "Status wurde nicht real geaendert"


def test_695_status_aendern_falsches_praefix(setup_env):
    db = setup_env
    aid = db.add_application({"title": "T", "company": "C", "status": "beworben"})
    mcp = _make_mcp(db, "bewerbungen")
    res = _call(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": f"DOC-{aid}", "neuer_status": "interview",
    })
    assert "fehler" in res, res
    assert db.get_application(aid)["status"] == "beworben"


# ============= jobsuche_starten =============

def test_695_jobsuche_ohne_kriterien_startet_nicht(setup_env):
    db = setup_env
    db.set_profile_setting("active_sources", ["bundesagentur"])
    mcp = _make_mcp(db, "jobs")
    res = _call(mcp, "jobsuche_starten", {})
    assert res.get("status") == "keine_suchbegriffe", res
    assert "suchkriterien_setzen" in res.get("nachricht", "")


def test_695_jobsuche_mit_explizit_keywords_umgeht_guard(setup_env):
    db = setup_env
    db.set_profile_setting("active_sources", ["bundesagentur"])
    mcp = _make_mcp(db, "jobs")
    res = _call(mcp, "jobsuche_starten", {"keywords": ["PLM Consultant"]})
    # Startet (oder scheitert an etwas ANDEREM als den Suchbegriffen)
    assert res.get("status") != "keine_suchbegriffe", res
