"""Tests fuer v1.7.0-beta.68 — #642 Phantom-Bewerbungen + #644 Mail-Doku-Link."""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta68_")
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
        sc = res.structured_content if hasattr(res, "structured_content") else res
        # FastMCP wrappt manche dict-Returns als {"result": {...}} — auspacken
        if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
            return sc["result"]
        return sc
    return asyncio.run(_run())


def _mcp(db, *modules):
    from fastmcp import FastMCP
    import logging
    mcp = FastMCP("test")
    log = logging.getLogger("test")
    for m in modules:
        m.register(mcp, db, log)
    return mcp


def _add_doc(db, filename):
    return db.add_document({
        "filename": filename, "filepath": f"/x/{filename}",
        "doc_type": "lebenslauf", "extracted_text": "CV Inhalt",
    })


# ============= #642 Phantom-Bewerbungen ============

def test_642_no_phantom_from_generic_names(setup_env):
    db = setup_env
    from bewerbungs_assistent.tools import dokumente
    mcp = _mcp(db, dokumente)
    for fn in [
        "Lebenslauf;Mustermann,Max-Ausführlich.pdf",
        "CV;Mustermann,Max -freelancer.pdf",
        "Lebenslauf;Mustermann,Max-SC.pdf",
        "Lebenslauf;Mustermann,Max-SL.pdf",
        "CV;Mustermann,Max-deutsch.pdf",
        "Lebenslauf;Mustermann,Max-20260203.pdf",
    ]:
        _add_doc(db, fn)
    result = _call(mcp, "bewerbungs_dokumente_erkennen", {"auto_erstellen": True})
    erstellt = result.get("erstellt", [])
    assert len(erstellt) == 0, f"Phantom-Bewerbungen angelegt: {erstellt}"


def test_642_real_company_with_hyphen_intact(setup_env):
    db = setup_env
    from bewerbungs_assistent.tools import dokumente
    mcp = _mcp(db, dokumente)
    _add_doc(db, "Lebenslauf;Mustermann,Max; Beispiel-Systems.pdf")
    result = _call(mcp, "bewerbungs_dokumente_erkennen", {"auto_erstellen": False})
    firmen = [e["firma"] for e in result.get("firmen", [])]
    assert any("Beispiel" in f for f in firmen), f"Firma verstuemmelt: {firmen}"
    assert "Systems" not in firmen


def test_642_legit_company_still_detected(setup_env):
    db = setup_env
    from bewerbungs_assistent.tools import dokumente
    mcp = _mcp(db, dokumente)
    _add_doc(db, "Anschreiben;Mustermann,Max-Musterfirma GmbH.pdf")
    result = _call(mcp, "bewerbungs_dokumente_erkennen", {"auto_erstellen": False})
    firmen = [e["firma"] for e in result.get("firmen", [])]
    assert any("Musterfirma" in f for f in firmen), f"Echte Firma nicht erkannt: {firmen}"


# ============= #644 email_verknuepfen Dokument-Fallback ============

def test_644_email_verknuepfen_falls_back_to_document(setup_env):
    db = setup_env
    from bewerbungs_assistent.tools import bewerbungen
    mcp = _mcp(db, bewerbungen)
    app_id = db.add_application({"title": "Eng", "company": "ACME GmbH", "status": "beworben"})
    doc_id = db.add_document({
        "filename": "einladung.eml", "filepath": "/x/einladung.eml",
        "doc_type": "email", "extracted_text": "Sehr geehrte...",
    })
    result = _call(mcp, "email_verknuepfen",
                   {"email_id": doc_id, "bewerbung_id": app_id})
    assert result.get("status") == "verknuepft", result
    assert result.get("document_id") == doc_id
    conn = db.connect()
    row = conn.execute(
        "SELECT linked_application_id FROM documents WHERE id=?", (doc_id,)
    ).fetchone()
    assert row["linked_application_id"] == app_id


def test_644_unknown_id_clear_error(setup_env):
    db = setup_env
    from bewerbungs_assistent.tools import bewerbungen
    mcp = _mcp(db, bewerbungen)
    app_id = db.add_application({"title": "Eng", "company": "X", "status": "beworben"})
    result = _call(mcp, "email_verknuepfen",
                   {"email_id": "gibt-es-nicht", "bewerbung_id": app_id})
    assert "fehler" in result
    assert "Dokument" in result.get("hinweis", "") or "Dokument" in result["fehler"]
