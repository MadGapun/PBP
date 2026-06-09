"""Regression #686: analyse_plan_erstellen gleicht eingehende Dokumente gegen
bestehende Bewerbungen ab (Firmenname im INHALT, nicht nur im Dateinamen) und
schlaegt die Zuordnung vor -> Dublettenschutz.

Vorher: `erkannte_firmen` kam nur aus `_extract_firma_from_filename`, ein
adesso-Interview-Mail (Firma nur im Text) blieb unerkannt, kein
Zuordnungsvorschlag -> Beinahe-Dublette.
"""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_686_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
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
    from bewerbungs_assistent.tools import dokumente
    import logging
    mcp = FastMCP("test")
    dokumente.register(mcp, db, logging.getLogger("test"))
    return mcp


def test_686_company_match_key():
    from bewerbungs_assistent.tools.dokumente import _company_match_key
    assert _company_match_key("adesso SE") == "adesso"
    assert _company_match_key("Bechtle GmbH") == "bechtle"
    assert _company_match_key("Lufthansa Technik") == "lufthansa"
    assert _company_match_key("The Quality Group") == "quality"
    assert _company_match_key("SAP") == ""    # zu kurz/generisch -> kein Matching
    assert _company_match_key("") == ""


def test_686_plan_matcht_dokument_gegen_bewerbung(setup_env):
    db = setup_env
    db.add_application({"title": "Lead Consultant PLM", "company": "adesso SE"})
    # Eingehendes Dokument: Firmenname NUR im Inhalt, NICHT im Dateinamen
    db.add_document({
        "id": "doc-mail-001",
        "filename": "Mail_2026-06-08.eml",
        "filepath": "/fake/doc-mail-001.eml",
        "doc_type": "email",
        "extracted_text": (
            "Von: recruiting@adesso-group.com\n"
            "Betreff: Einladung zum Interview\n"
            "adesso SE freut sich, Sie kennenzulernen."
        ),
    })
    mcp = _make_mcp(db)
    result = _call(mcp, "analyse_plan_erstellen", {})
    assert result["status"] == "ok"
    z = result["bewerbungs_zuordnungen"]
    assert any(
        e["dateiname"] == "Mail_2026-06-08.eml" and e["firma"] == "adesso SE"
        for e in z
    ), z
    # Firma taucht jetzt in erkannte_firmen auf (vorher nur aus Dateinamen)
    assert "adesso SE" in result["erkannte_firmen"]


def test_686_kein_match_ohne_treffer(setup_env):
    db = setup_env
    db.add_application({"title": "X", "company": "Bechtle GmbH"})
    db.add_document({
        "id": "doc-x",
        "filename": "Mail.eml",
        "filepath": "/fake/x.eml",
        "doc_type": "email",
        "extracted_text": "Keine passende Firma in diesem Text.",
    })
    mcp = _make_mcp(db)
    result = _call(mcp, "analyse_plan_erstellen", {})
    assert result["bewerbungs_zuordnungen"] == []
