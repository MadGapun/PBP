"""Tests fuer pbp_capabilities + pbp_grenze_melden (v1.6.3 / #514).

Verifiziert:
- Server-instructions sind nicht leer und enthalten Anti-Bypass-Hinweis
- pbp_capabilities() liefert Uebersicht ohne kategorie + Detail mit kategorie
- pbp_grenze_melden() loggt + liefert Issue-Body
"""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_caps_test_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _result(raw):
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if hasattr(raw, "structured_content"):
        raw = raw.structured_content
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    # FastMCP 2.12+ wraps single-value results in {"result": ...}
    if isinstance(raw, dict) and set(raw.keys()) == {"result"}:
        raw = raw["result"]
    return raw


def _call(mcp, name, args):
    """FastMCP 2.12+ Tool-Call-Helper (siehe CLAUDE.md).

    `mcp.call_tool` existiert in FastMCP 2.12 nicht mehr. Stattdessen:
    `await mcp.get_tool(name); await tool.run(args)`.
    """
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def test_server_instructions_present():
    """PBP-Server-Instructions enthalten Anti-Bypass-Hinweis."""
    from bewerbungs_assistent.server import mcp, PBP_INSTRUCTIONS
    assert PBP_INSTRUCTIONS, "PBP_INSTRUCTIONS darf nicht leer sein"
    assert "PBP-Tools" in PBP_INSTRUCTIONS or "PBP-Logik" in PBP_INSTRUCTIONS
    assert "NIEMALS" in PBP_INSTRUCTIONS, "Anti-Bypass muss explizit sein"
    assert "pbp_capabilities" in PBP_INSTRUCTIONS
    assert "pbp_grenze_melden" in PBP_INSTRUCTIONS
    # Kommt das auch beim FastMCP-Server an?
    assert mcp.instructions == PBP_INSTRUCTIONS


def test_capabilities_overview(setup_env):
    """pbp_capabilities() ohne kategorie liefert Uebersicht aller Bereiche."""
    from bewerbungs_assistent.server import mcp
    raw = _call(mcp, "pbp_capabilities", {})
    result = _result(raw)
    assert "kategorien" in result
    assert "anti_bypass_hinweis" in result
    # Mindestens die Kernkategorien
    for k in ("profil", "jobsuche", "bewerbungen", "system"):
        assert k in result["kategorien"], f"Kategorie {k} fehlt"


def test_capabilities_detail(setup_env):
    """pbp_capabilities('jobsuche') liefert konkrete Tool-Liste."""
    from bewerbungs_assistent.server import mcp
    raw = _call(mcp, "pbp_capabilities", {"kategorie": "jobsuche"})
    result = _result(raw)
    assert result.get("kategorie") == "jobsuche"
    assert "tools" in result
    tools_text = " ".join(result["tools"])
    # Bulk-Tool muss in der Jobsuche-Kategorie genannt sein
    assert "stellen_bulk_bewerten" in tools_text


def test_capabilities_unknown_kategorie(setup_env):
    """Unbekannte Kategorie liefert Fehler mit verfuegbarer Liste."""
    from bewerbungs_assistent.server import mcp
    raw = _call(mcp, "pbp_capabilities", {"kategorie": "frittenbude"})
    result = _result(raw)
    assert "fehler" in result
    assert "verfuegbare_kategorien" in result


def test_grenze_melden_logs_and_returns_issue_body(setup_env):
    """pbp_grenze_melden() loggt nach limitations.log + liefert Issue-Body."""
    db, tmpdir = setup_env
    from bewerbungs_assistent.server import mcp
    raw = _call(mcp, "pbp_grenze_melden", {
        "was_versucht": "Alle Bewerbungen aus 2024 archivieren",
        "warum_pbp_nicht_passt": "bewerbungen_bulk_status_aendern existiert nicht",
        "vorschlag": "Bulk-Status-Aenderung mit Filter aelter_als",
    })
    result = _result(raw)
    assert result.get("status") == "gemeldet"
    assert "gh_issue_url" in result
    assert "github.com/MadGapun/PBP/issues/new" in result["gh_issue_url"]
    assert "vorgeschlagener_issue_body" in result
    assert "Alle Bewerbungen aus 2024" in result["vorgeschlagener_issue_body"]
    # Pruefen ob limitations.log angelegt wurde
    log_path = os.path.join(tmpdir, "limitations.log")
    assert os.path.isfile(log_path), f"limitations.log nicht angelegt: {log_path}"
    content = open(log_path, encoding="utf-8").read()
    assert "Alle Bewerbungen aus 2024" in content


def test_grenze_melden_without_vorschlag(setup_env):
    """vorschlag ist optional — der Issue-Body funktioniert auch ohne."""
    from bewerbungs_assistent.server import mcp
    raw = _call(mcp, "pbp_grenze_melden", {
        "was_versucht": "Foo",
        "warum_pbp_nicht_passt": "Bar",
    })
    result = _result(raw)
    assert result.get("status") == "gemeldet"
    assert "vorgeschlagener_issue_body" in result
