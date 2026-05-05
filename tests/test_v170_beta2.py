"""Tests fuer v1.7.0-beta.2.

Issues:
- #577 Stilarchiv (Schema, DB-Helpers, MCP-Tools)
- #512 Lokale AI: echte Ollama-Integration (Pfade, Prompt-Builders, Parser)
"""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta2_")
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


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


# ============= #577 Stilarchiv Schema ===============

def test_577_document_versions_table_exists(setup_env):
    """Schema v32 hat document_versions-Tabelle."""
    db, _ = setup_env
    conn = db.connect()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='document_versions'"
    ).fetchone()
    assert row is not None


def test_577_add_and_get_document_version(setup_env):
    """add_document_version + get_recent_document_versions Round-Trip."""
    db, _ = setup_env
    vid = db.add_document_version({
        "kind": "cover_letter",
        "title": "TestCorp PLM Manager",
        "content": "Sehr geehrte Damen und Herren, mein Anschreiben...",
        "outcome": "interview",
    })
    assert vid
    versions = db.get_recent_document_versions("cover_letter", limit=5)
    assert len(versions) == 1
    assert versions[0]["title"] == "TestCorp PLM Manager"
    assert versions[0]["outcome"] == "interview"
    assert versions[0]["word_count"] > 0


def test_577_get_versions_filters_by_kind(setup_env):
    """get_recent_document_versions filtert nach kind."""
    db, _ = setup_env
    db.add_document_version({"kind": "cover_letter", "content": "A"})
    db.add_document_version({"kind": "cv", "content": "B"})
    db.add_document_version({"kind": "cover_letter", "content": "C"})
    cls = db.get_recent_document_versions("cover_letter", limit=10)
    assert len(cls) == 2
    cv = db.get_recent_document_versions("cv", limit=10)
    assert len(cv) == 1


def test_577_only_with_outcome_filter(setup_env):
    """only_with_outcome filtert auf erfolgreich/erfolglos markierte."""
    db, _ = setup_env
    db.add_document_version({"kind": "cover_letter", "content": "A", "outcome": "interview"})
    db.add_document_version({"kind": "cover_letter", "content": "B"})
    db.add_document_version({"kind": "cover_letter", "content": "C", "outcome": "abgelehnt"})
    all_v = db.get_recent_document_versions("cover_letter", limit=10)
    with_out = db.get_recent_document_versions("cover_letter", limit=10, only_with_outcome=True)
    assert len(all_v) == 3
    assert len(with_out) == 2


def test_577_update_outcome(setup_env):
    """update_document_version_outcome setzt outcome nachtraeglich."""
    db, _ = setup_env
    vid = db.add_document_version({"kind": "cover_letter", "content": "X"})
    ok = db.update_document_version_outcome(vid, "interview")
    assert ok is True
    versions = db.get_recent_document_versions("cover_letter")
    assert versions[0]["outcome"] == "interview"


# ============= #577 Stilarchiv MCP-Tools ===============

def test_577_stilarchiv_speichern_tool(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "stilarchiv_speichern", {
        "kind": "cover_letter",
        "content": "Mein Anschreiben mit allen Details...",
        "title": "TestCorp",
    })
    assert result["status"] == "gespeichert"
    assert result["kind"] == "cover_letter"
    assert result["version_id"]


def test_577_stilarchiv_kontext_tool_empty(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "stilarchiv_kontext", {"kind": "cover_letter"})
    assert result["anzahl"] == 0
    assert "hinweis" in result


def test_577_stilarchiv_kontext_tool_with_data(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    # 3 Versionen ablegen
    for i in range(3):
        db.add_document_version({
            "kind": "cover_letter",
            "title": f"Firma {i}",
            "content": f"Anschreiben Nummer {i} mit Inhalt.",
            "outcome": "interview" if i == 0 else None,
        })
    result = _call(mcp, "stilarchiv_kontext", {"kind": "cover_letter", "limit": 10})
    assert result["anzahl"] == 3
    assert len(result["versionen"]) == 3
    # Sortiert nach created_at DESC: neueste zuerst
    assert result["versionen"][0]["title"] == "Firma 2"


def test_577_stilarchiv_validates_kind(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "stilarchiv_speichern", {
        "kind": "ungueltig",
        "content": "X",
    })
    assert "fehler" in result


def test_577_stilarchiv_outcome_setzen_tool(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    create = _call(mcp, "stilarchiv_speichern", {
        "kind": "cover_letter",
        "content": "Inhalt",
    })
    vid = create["version_id"]
    upd = _call(mcp, "stilarchiv_outcome_setzen", {
        "version_id": vid,
        "outcome": "interview",
    })
    assert upd["status"] == "gespeichert"


def test_577_stilarchiv_outcome_validates(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    create = _call(mcp, "stilarchiv_speichern", {"kind": "cover_letter", "content": "x"})
    upd = _call(mcp, "stilarchiv_outcome_setzen", {
        "version_id": create["version_id"],
        "outcome": "ungueltig",
    })
    assert "fehler" in upd


# ============= #512 Local AI Prompt/Parser ===============

def test_512_classify_document_prompt_builds():
    """_build_classify_document_prompt liefert sinnvollen Text."""
    from bewerbungs_assistent.services.llm_service import _build_classify_document_prompt
    prompt = _build_classify_document_prompt({
        "text": "Lebenslauf von Max Mustermann\n\nBerufserfahrung: ...",
        "filename": "cv.pdf",
    })
    assert "Lebenslauf" in prompt
    assert "klassifiziere" in prompt.lower() or "klassifik" in prompt.lower()
    assert "lebenslauf" in prompt
    assert "anschreiben" in prompt


def test_512_classify_document_parser_valid_categories():
    """Parser erkennt valide Kategorien aus Roh-Output."""
    from bewerbungs_assistent.services.llm_service import _parse_classify_document
    assert _parse_classify_document("lebenslauf")["category"] == "lebenslauf"
    assert _parse_classify_document("LEBENSLAUF")["category"] == "lebenslauf"
    assert _parse_classify_document(" anschreiben\n")["category"] == "anschreiben"
    assert _parse_classify_document("zertifikat.")["category"] == "zertifikat"


def test_512_classify_document_parser_unknown_falls_back():
    """Parser faellt bei unbekanntem Output auf 'sonstiges' zurueck."""
    from bewerbungs_assistent.services.llm_service import _parse_classify_document
    result = _parse_classify_document("ich weiss es nicht")
    assert result["category"] == "sonstiges"
    assert result["confidence"] < 0.5


def test_512_extract_skills_prompt_builds():
    from bewerbungs_assistent.services.llm_service import _build_extract_skills_prompt
    prompt = _build_extract_skills_prompt({
        "text": "Python, Django, SQL, Projektmanagement",
    })
    assert "Skills" in prompt
    assert "kommagetrennt" in prompt.lower()


def test_512_extract_skills_parser():
    from bewerbungs_assistent.services.llm_service import _parse_extract_skills
    result = _parse_extract_skills("Python, Django, SQL, Projektmanagement")
    assert result["count"] == 4
    assert "Python" in result["skills"]
    assert "Django" in result["skills"]


def test_512_extract_skills_parser_handles_messy_output():
    """Parser entfernt Bullets, Nummern, Whitespace."""
    from bewerbungs_assistent.services.llm_service import _parse_extract_skills
    result = _parse_extract_skills("- Python  ,  •Django  ,  *SQL  ")
    assert "Python" in result["skills"]
    assert "Django" in result["skills"]
    assert "SQL" in result["skills"]


def test_512_run_falls_back_when_local_not_implemented(setup_env):
    """Wenn kein Mock und kein Ollama: Fallback auf CLAUDE."""
    from bewerbungs_assistent.services.llm_service import (
        LLMService, TaskKind, Backend, reset_llm_service
    )
    reset_llm_service()
    os.environ.pop("PBP_LLM_MOCK", None)
    db, _ = setup_env
    svc = LLMService(db=db)
    result = svc.run(TaskKind.CLASSIFY_DOCUMENT, {"text": "X"})
    # Kein Ollama → Fallback CLAUDE (success=False, fallback_message)
    assert result.backend == Backend.CLAUDE
    assert result.success is False
    assert result.fallback_message
