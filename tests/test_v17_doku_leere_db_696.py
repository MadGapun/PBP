"""Regression #696-A: ehrliche Leere-DB-Antworten der Dokument-Tools.

- 0 hochgeladene Dokumente != "Alle Dokumente sind bereits analysiert"
- kein_profil-Antworten enthalten eine Handlungsanweisung (Ersterfassung)
"""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_696_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
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


def _make_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import dokumente
    import logging
    mcp = FastMCP("test")
    dokumente.register(mcp, db, logging.getLogger("test"))
    return mcp


def test_696_batch_analysieren_keine_dokumente(setup_env):
    db = setup_env
    db.save_profile({"name": "Test"})
    mcp = _make_mcp(db)
    res = _call(mcp, "dokumente_batch_analysieren", {})
    assert res.get("status") == "keine_dokumente", res
    assert "hochgeladen" in res.get("nachricht", "").lower() or \
           "hochlade" in res.get("nachricht", "").lower() or \
           "Lade" in res.get("nachricht", ""), res


def test_696_analyse_plan_empfiehlt_upload_statt_batch(setup_env):
    db = setup_env
    db.save_profile({"name": "Test"})
    mcp = _make_mcp(db)
    res = _call(mcp, "analyse_plan_erstellen", {})
    assert res["status"] == "ok"
    assert "dokumente_batch_analysieren()" not in res["empfehlung"], res["empfehlung"]
    assert "hoch" in res["empfehlung"].lower(), res["empfehlung"]


def test_696_kein_profil_mit_handlungsanweisung(setup_env):
    db = setup_env  # KEIN Profil angelegt
    mcp = _make_mcp(db)
    for tool in ("dokumente_zur_analyse", "analyse_plan_erstellen",
                 "dokumente_batch_analysieren"):
        res = _call(mcp, tool, {})
        text = str(res)
        assert "rsterfassung" in text or "profil_erstellen" in text, (tool, res)
