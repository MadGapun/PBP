"""Regression #694: Onboarding-Sackgassen in gefuehrten Prompts.

- Keine Umlaut-Toolnamen mehr in Live-Prompts (skill_hinzufügen etc.)
- Kein Verweis auf nicht-existentes anschreiben_generieren
- workflow_starten normalisiert Umlaut-Namen + klarer Fehler bei unbekannt
- Kein-Profil-Fall im Kennlerngespraech-Prompt behandelt
"""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src" / "bewerbungs_assistent"


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_694_")
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


def _make_workflows_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import workflows
    import logging
    mcp = FastMCP("test")
    workflows.register(mcp, db, logging.getLogger("test"))
    return mcp


# ============= Quelltext-Asserts (Live-Prompts sauber) =============

def test_694_keine_umlaut_toolnamen_mehr():
    src = (SRC / "prompts.py").read_text(encoding="utf-8")
    for verboten in ("skill_hinzufügen", "position_hinzufügen",
                     "bewerbung_status_ändern", "docs/FAQ.md"):
        assert verboten not in src, f"{verboten!r} steht noch in prompts.py"


def test_694_anschreiben_generieren_nirgends():
    treffer = []
    for py in SRC.rglob("*.py"):
        if "anschreiben_generieren" in py.read_text(encoding="utf-8", errors="replace"):
            treffer.append(py.name)
    assert not treffer, f"Nicht-existentes Tool referenziert in: {treffer}"


def test_694_kennlern_prompt_intakt(setup_env):
    db = setup_env
    from bewerbungs_assistent.prompts import build_kennlerngespraech_prompt
    text = build_kennlerngespraech_prompt(db)
    assert len(text) > 500
    assert "skill_hinzufuegen" in text
    # Kein-Profil-Fall ist als eigener Schritt dokumentiert
    assert "Kein aktives Profil" in text


# ============= workflow_starten robust =============

def test_694_umlaut_workflowname_normalisiert(setup_env):
    db = setup_env
    mcp = _make_workflows_mcp(db)
    res = _call(mcp, "workflow_starten", {"name": "profil_überprüfen"})
    assert res.get("status") == "gestartet", res
    assert "nicht gefunden" not in res.get("anweisungen", "")


def test_694_unbekannter_workflow_klarer_fehler(setup_env):
    db = setup_env
    mcp = _make_workflows_mcp(db)
    res = _call(mcp, "workflow_starten", {"name": "gibtsnicht"})
    assert "fehler" in res, res
    assert res.get("status") != "gestartet"
    assert isinstance(res.get("verfuegbare_workflows"), list)
    assert "ersterfassung" in res["verfuegbare_workflows"]
