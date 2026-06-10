"""Regression-Tests fuer die User-Test-Funde vom 10.06. (beta.101):

- #699: blacklist_verwalten warnt (statt einzutragen), wenn die Firma laufende
  Bewerbungen im Interview-Stadium hat; force=True uebersteuert.
- #700 Bug A: der Auto-Followup-Reconciler legt KEINEN Nachfass an, wenn fuer
  die Bewerbung bereits ein zukuenftiger Termin (geplant/bestaetigt) existiert.
"""
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_699_700_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    # Isolations-Assert: NIE gegen die echte AppData-DB laufen
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    _dash_mod._db = db
    yield db, _dash_mod
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _make_suche_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import suche
    import logging
    mcp = FastMCP("test")
    suche.register(mcp, db, logging.getLogger("test"))
    return mcp


# ============= #699: Blacklist-Schutz =============

def test_699_warnung_bei_interview_bewerbung(setup_env):
    db, _ = setup_env
    db.add_application({"title": "Lead Consultant PLM", "company": "adesso SE",
                        "status": "interview"})
    mcp = _make_suche_mcp(db)
    res = _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "adesso",
    })
    assert res["status"] == "warnung", res
    assert res["betroffene_bewerbungen"], res
    assert "force" in res["hinweis"]
    # Nicht eingetragen
    assert all(e["value"].lower() != "adesso" for e in db.get_blacklist())


def test_699_force_traegt_trotzdem_ein(setup_env):
    db, _ = setup_env
    db.add_application({"title": "X", "company": "adesso SE", "status": "interview"})
    mcp = _make_suche_mcp(db)
    res = _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "adesso", "force": True,
    })
    assert res["status"] == "hinzugefuegt", res
    assert any(e["value"].lower() == "adesso" for e in db.get_blacklist())


def test_699_keine_warnung_ohne_kritische_bewerbung(setup_env):
    db, _ = setup_env
    # 'beworben' ist KEIN kritischer Status — Eintrag geht durch
    db.add_application({"title": "X", "company": "Beispiel GmbH", "status": "beworben"})
    mcp = _make_suche_mcp(db)
    res = _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Beispiel GmbH",
    })
    assert res["status"] == "hinzugefuegt", res


# ============= #700 A: Reconciler respektiert Termine =============

def _add_stale_application(db, status="beworben", days_ago=20):
    applied = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    aid = db.add_application({"title": "T", "company": "C", "status": status})
    conn = db.connect()
    conn.execute("UPDATE applications SET applied_at=? WHERE id=?", (applied, aid))
    conn.commit()
    return aid


def test_700a_kein_nachfass_bei_zukuenftigem_termin(setup_env):
    db, dash = setup_env
    aid = _add_stale_application(db)
    future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT15:00:00")
    db.add_meeting({"application_id": aid, "title": "Interview",
                    "meeting_date": future, "status": "geplant"})
    result = dash._run_auto_followup_reconciler(datetime.now().isoformat())
    assert result["created_count"] == 0, result


def test_700a_nachfass_ohne_termin(setup_env):
    db, dash = setup_env
    _add_stale_application(db)
    result = dash._run_auto_followup_reconciler(datetime.now().isoformat())
    assert result["created_count"] == 1, result


def test_700a_vergangener_termin_blockiert_nicht(setup_env):
    db, dash = setup_env
    aid = _add_stale_application(db)
    past = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%dT15:00:00")
    db.add_meeting({"application_id": aid, "title": "War schon",
                    "meeting_date": past, "status": "geplant"})
    result = dash._run_auto_followup_reconciler(datetime.now().isoformat())
    assert result["created_count"] == 1, result
