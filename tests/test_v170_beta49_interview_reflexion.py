"""Tests fuer v1.7.0-beta.49 — Post-Interview-Reflexion (#464)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta49_")
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
    _dash_mod._db = db
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _add_app(db, company="ACME", title="Test Job", status="interview_abgeschlossen"):
    return db.add_application({
        "title": title, "company": company,
        "status": status, "applied_at": "2026-05-01",
    })


# ============= Schema v43 ===============

def test_schema_v43_table_exists(setup_env):
    db = setup_env
    conn = db.connect()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "interview_reflections" in tables


def test_schema_version_at_least_43(setup_env):
    db = setup_env
    conn = db.connect()
    row = conn.execute(
        "SELECT value FROM settings WHERE key='schema_version'"
    ).fetchone()
    assert int(row[0]) >= 43


# ============= DB-Methoden ============

def test_upsert_creates_then_updates(setup_env):
    db = setup_env
    aid = _add_app(db)
    rid1 = db.upsert_interview_reflection(aid, {
        "was_lief_gut": "Vorbereitung war solide",
        "gefuehl": 4,
    })
    assert rid1 > 0
    # Zweiter Aufruf updated denselben Datensatz
    rid2 = db.upsert_interview_reflection(aid, {
        "was_lief_schlecht": "Tech-Frage zu Aras-Migration nicht beantwortet",
        "gefuehl": 3,
    })
    assert rid2 == rid1
    r = db.get_interview_reflection(aid)
    assert r["was_lief_gut"] == "Vorbereitung war solide"  # bleibt
    assert "Aras-Migration" in r["was_lief_schlecht"]
    assert r["gefuehl"] == 3  # ueberschrieben


def test_get_returns_none_when_no_reflection(setup_env):
    db = setup_env
    aid = _add_app(db)
    assert db.get_interview_reflection(aid) is None


def test_list_reflections_orders_recent_first(setup_env):
    db = setup_env
    aid1 = _add_app(db, company="Alpha")
    aid2 = _add_app(db, company="Beta")
    db.upsert_interview_reflection(aid1, {"was_lief_gut": "X"})
    db.upsert_interview_reflection(aid2, {"was_lief_gut": "Y"})
    items = db.list_interview_reflections()
    assert len(items) == 2
    # Beta wurde spaeter angelegt -> kommt zuerst
    assert items[0]["company"] in ("Beta", "Alpha")  # robust gegen Reihenfolge
    companies = {i["company"] for i in items}
    assert companies == {"Alpha", "Beta"}


def test_cascade_deletes_with_application(setup_env):
    db = setup_env
    aid = _add_app(db)
    db.upsert_interview_reflection(aid, {"was_lief_gut": "x"})
    conn = db.connect()
    conn.execute("DELETE FROM applications WHERE id=?", (aid,))
    conn.commit()
    # FK ON DELETE CASCADE
    rows = conn.execute(
        "SELECT * FROM interview_reflections WHERE application_id=?",
        (aid,)
    ).fetchall()
    assert len(rows) == 0


# ============= MCP-Tools ============

def _call(mcp, name, args):
    import asyncio
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _build_mcp(db):
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.bewerbungen import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    return mcp


def test_tool_speichern_creates(setup_env):
    db = setup_env
    aid = _add_app(db, company="Speichern-GmbH")
    mcp = _build_mcp(db)
    out = _call(mcp, "interview_reflexion_speichern", {
        "bewerbung_id": aid,
        "was_lief_gut": "Klare Antworten",
        "gefuehl": 4,
    })
    assert out["status"] == "gespeichert"
    assert out["firma"] == "Speichern-GmbH"
    # In DB persistiert
    r = db.get_interview_reflection(aid)
    assert r["was_lief_gut"] == "Klare Antworten"


def test_tool_speichern_404_unknown_app(setup_env):
    db = setup_env
    mcp = _build_mcp(db)
    out = _call(mcp, "interview_reflexion_speichern", {
        "bewerbung_id": "nonexistent",
        "was_lief_gut": "x",
    })
    assert "fehler" in out


def test_tool_speichern_validates_gefuehl_range(setup_env):
    db = setup_env
    aid = _add_app(db)
    mcp = _build_mcp(db)
    out = _call(mcp, "interview_reflexion_speichern", {
        "bewerbung_id": aid,
        "gefuehl": 7,  # auserhalb 1-5
    })
    assert "fehler" in out
    assert "1 und 5" in out["fehler"]


def test_tool_lesen_empty_for_new(setup_env):
    db = setup_env
    aid = _add_app(db)
    mcp = _build_mcp(db)
    out = _call(mcp, "interview_reflexion_lesen", {"bewerbung_id": aid})
    assert out["status"] == "leer"


def test_tool_lesen_returns_full_data(setup_env):
    db = setup_env
    aid = _add_app(db, company="Lese-AG")
    db.upsert_interview_reflection(aid, {
        "was_lief_gut": "Konkret",
        "was_lief_schlecht": "Vague",
        "was_war_ueberraschend": "Cultural-Fit-Frage",
        "gefuehl": 3,
        "next_steps": "Nachfass in 5 Tagen",
        "wiederverwendbare_antwort": "Mein PLM-Migrationsbeispiel kam gut an",
    })
    mcp = _build_mcp(db)
    out = _call(mcp, "interview_reflexion_lesen", {"bewerbung_id": aid})
    assert out["status"] == "vorhanden"
    r = out["reflexion"]
    assert r["gefuehl"] == 3
    assert "PLM-Migration" in r["wiederverwendbare_antwort"]


def test_tool_anzeigen_lists_recent(setup_env):
    db = setup_env
    for i in range(3):
        aid = _add_app(db, company=f"Firma{i}")
        db.upsert_interview_reflection(aid, {
            "was_lief_gut": f"Gut {i}", "gefuehl": i + 2,
        })
    mcp = _build_mcp(db)
    out = _call(mcp, "interview_reflexionen_anzeigen", {"limit": 10})
    assert out["anzahl"] == 3
    assert len(out["reflexionen"]) == 3
    companies = {r["company"] for r in out["reflexionen"]}
    assert companies == {"Firma0", "Firma1", "Firma2"}


def test_tool_anzeigen_respects_limit(setup_env):
    db = setup_env
    for i in range(5):
        aid = _add_app(db, company=f"Cap{i}")
        db.upsert_interview_reflection(aid, {"gefuehl": 3})
    mcp = _build_mcp(db)
    out = _call(mcp, "interview_reflexionen_anzeigen", {"limit": 2})
    assert out["anzahl"] == 2
