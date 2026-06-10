"""Regression #696-B: pbp_capabilities-Katalog synchron zur Tool-Realitaet.

Vorher fehlten im kuratierten Katalog die beta.78-90-Tools (todos,
Dokument-Lifecycle, stelle_reaktivieren, Wiedergaenger, eigene
Ablehnungsgruende, onboarding_hints) und kennlerngespraech_abschliessen
war falsch als Interview-Nachgang unter 'bewerbungen' gelistet —
tatsaechlich ist es das Profil-Onboarding-Gespraech (Dashboard-Wizard).
"""
import asyncio
import json
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
    # Isolations-Wächter: NIE gegen die echte User-DB laufen
    assert str(db.db_path).startswith(tmpdir), (
        f"Test-DB liegt NICHT im Temp-Verzeichnis: {db.db_path}"
    )
    db.save_profile({"name": "Test"})
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


def _full_catalog_text(mcp):
    """Alle Kategorie-Detail-Views als ein serialisierter String."""
    overview = _call(mcp, "pbp_capabilities", {})
    parts = [json.dumps(overview, ensure_ascii=False)]
    for kat in overview["kategorien"]:
        detail = _call(mcp, "pbp_capabilities", {"kategorie": kat})
        parts.append(json.dumps(detail, ensure_ascii=False))
    return "\n".join(parts)


def test_696_neue_tools_im_katalog(setup_env):
    mcp = _make_mcp(setup_env)
    text = _full_catalog_text(mcp)
    for needle in (
        "todo_anlegen",
        "stelle_reaktivieren",
        "dokument_archivieren",
        "ablehnungsgr",
        "interview_reflexion_speichern",
        "stelle_wiedergaenger_pruefen",
        "onboarding_hints_anzeigen",
        "keywords_minus",
    ):
        assert needle in text, f"'{needle}' fehlt im pbp_capabilities-Katalog"


def test_696_kennlerngespraech_nicht_mehr_interview_nachgang(setup_env):
    mcp = _make_mcp(setup_env)
    overview = _call(mcp, "pbp_capabilities", {})
    kennlern_eintraege = []
    for kat in overview["kategorien"]:
        detail = _call(mcp, "pbp_capabilities", {"kategorie": kat})
        for eintrag in detail["tools"]:
            if "kennlerngespraech_abschliessen" in eintrag:
                kennlern_eintraege.append((kat, eintrag))
    assert kennlern_eintraege, "kennlerngespraech_abschliessen fehlt komplett"
    for kat, eintrag in kennlern_eintraege:
        # Falsch-Beschreibung darf nicht mehr direkt am Eintrag stehen
        assert "Interview-Nachgang" not in eintrag, (kat, eintrag)
        assert kat == "profil", f"gehoert in 'profil', steht in '{kat}'"


def test_696_interview_nachgang_jetzt_bei_reflexion(setup_env):
    mcp = _make_mcp(setup_env)
    detail = _call(mcp, "pbp_capabilities", {"kategorie": "bewerbungen"})
    tools_text = " ".join(detail["tools"])
    assert "interview_reflexion_speichern" in tools_text
    assert "kennlerngespraech_abschliessen" not in tools_text
