"""Tests fuer v1.7.0-beta.66 — KI-Transparenz (#632 St1 + #638 St5)."""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta66_")
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


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _make_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import analyse
    import logging
    mcp = FastMCP("test")
    analyse.register(mcp, db, logging.getLogger("test"))
    return mcp


# ============= #632 Stufe 1: Aufwand-Klassen ============

def test_capabilities_has_aufwand_klassen(setup_env):
    db = setup_env
    mcp = _make_mcp(db)
    result = _call(mcp, "pbp_capabilities", {})
    assert "aufwand_klassen" in result
    klassen = result["aufwand_klassen"]
    assert "gratis_db" in klassen
    assert "lokal_guenstig" in klassen
    assert "claude_mittel" in klassen
    assert "claude_teuer_bulk" in klassen
    # jede Klasse hat Beschreibung + Beispiele
    for k, v in klassen.items():
        assert v.get("beschreibung")
        assert isinstance(v.get("beispiele"), list)


def test_capabilities_category_view_unaffected(setup_env):
    """Kategorie-Detail-View hat keine aufwand_klassen (nur Overview)."""
    db = setup_env
    mcp = _make_mcp(db)
    result = _call(mcp, "pbp_capabilities", {"kategorie": "jobsuche"})
    assert "aufwand_klassen" not in result
    assert "tools" in result


# ============= #638 Stufe 5: Genauigkeits-Tracking ============

def _add_job(db, hash_, title, active=1, dismiss=None):
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, source, is_active, "
        "dismiss_reason, updated_at) VALUES (?, ?, ?, 'Firma', 'test', ?, ?, '2026-05-14')",
        (f"{pid}:{hash_}", pid, title, active, dismiss),
    )
    conn.commit()


def test_accuracy_insufficient_data(setup_env):
    db = setup_env
    # Nur 2 auto-aussortierte -> unter Schwelle 5
    _add_job(db, "j1", "Job1", active=0, dismiss="auto:profil_match_negativ:x")
    _add_job(db, "j2", "Job2", active=0, dismiss="auto:profil_match_negativ:x")
    stats = db.get_ollama_accuracy_stats()
    assert stats["auto_aussortiert_gesamt"] == 2
    assert stats["datenbasis_ausreichend"] is False
    assert stats["genauigkeit_prozent"] is None


def test_accuracy_with_corrections(setup_env):
    db = setup_env
    # 8 auto-aussortiert, davon 2 reaktiviert (User-Korrektur)
    for i in range(6):
        _add_job(db, f"d{i}", f"Dismissed{i}", active=0,
                 dismiss="auto:profil_match_negativ:x")
    for i in range(2):
        _add_job(db, f"r{i}", f"Reactivated{i}", active=1,
                 dismiss="auto:profil_match_negativ:x")
    stats = db.get_ollama_accuracy_stats()
    assert stats["auto_aussortiert_gesamt"] == 8
    assert stats["reaktiviert"] == 2
    assert stats["datenbasis_ausreichend"] is True
    # 100 * (1 - 2/8) = 75.0
    assert stats["genauigkeit_prozent"] == 75.0


def test_accuracy_ignores_manual_dismissals(setup_env):
    db = setup_env
    # Manuelle Aussortierungen zaehlen NICHT (kein auto:-Prefix)
    for i in range(10):
        _add_job(db, f"m{i}", f"Manual{i}", active=0, dismiss="passt_nicht")
    stats = db.get_ollama_accuracy_stats()
    assert stats["auto_aussortiert_gesamt"] == 0


def test_accuracy_in_mcp_diagnose(setup_env):
    db = setup_env
    mcp = _make_mcp(db)
    result = _call(mcp, "pbp_mcp_diagnose", {})
    assert "ollama_genauigkeit" in result
    assert "auto_aussortiert_gesamt" in result["ollama_genauigkeit"]


def test_accuracy_api_endpoint(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    db = setup_env
    _add_job(db, "x1", "X", active=0, dismiss="auto:profil_match_negativ:y")
    client = TestClient(app)
    r = client.get("/api/llm/accuracy")
    assert r.status_code == 200
    assert "auto_aussortiert_gesamt" in r.json()
