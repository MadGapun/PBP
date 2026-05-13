"""Tests fuer v1.7.0-beta.59 — Doku-Analyse-Payload-Limits (#635).

Sicherstellt dass:
- analyse_plan_erstellen liefert keine Vollliste der Dateinamen
- dokumente_batch_analysieren trunkated bei zu grossen Texten
- Hard-Caps werden eingehalten (kein Argument-Trick kann Response sprengen)
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta59_")
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
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _make_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import dokumente
    mcp = FastMCP("test")
    import logging
    log = logging.getLogger("test")
    dokumente.register(mcp, db, log)
    return mcp


def _add_docs(db, n=20, text_size=15000):
    """Add n documents with large extracted_text."""
    pid = db.get_active_profile_id()
    text = "x" * text_size
    for i in range(n):
        db.add_document({
            "id": f"doc-{i:03d}",
            "filename": f"Lebenslauf_Firma_{i:03d}.pdf",
            "filepath": f"/fake/doc-{i:03d}.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": text,
        })


# ============= analyse_plan_erstellen ============

def test_plan_response_is_compact(setup_env):
    db = setup_env
    _add_docs(db, n=30, text_size=5000)
    mcp = _make_mcp(db)
    result = _call(mcp, "analyse_plan_erstellen", {})
    assert result["status"] == "ok"
    # Pro Batch nur Vorschau-Datei-Liste, kein Vollliste
    for b in result["batches"]:
        assert "dateien_vorschau" in b
        assert "weitere_dateien" in b
        assert len(b["dateien_vorschau"]) <= 3
        assert "dateien" not in b  # alte Vollliste nicht mehr


def test_plan_total_bytes_uses_blob_length(setup_env):
    """LENGTH(BLOB) == Bytes — bei Latein-Text == LENGTH(text)."""
    db = setup_env
    _add_docs(db, n=5, text_size=1000)
    mcp = _make_mcp(db)
    result = _call(mcp, "analyse_plan_erstellen", {})
    # 5 Docs x 1000 chars = 5000 Bytes (ASCII)
    assert result["total_text_bytes"] == 5000


# ============= dokumente_batch_analysieren ============

def test_batch_truncates_large_documents(setup_env):
    db = setup_env
    # Ein einzelnes Dokument mit 50KB Text
    _add_docs(db, n=1, text_size=50000)
    mcp = _make_mcp(db)
    result = _call(mcp, "dokumente_batch_analysieren",
                   {"max_bytes_per_doc": 5000})
    assert result["status"] == "ok"
    assert result["dokumente_gekuerzt"] == 1
    doc = result["dokumente"][0]
    assert doc["gekuerzt"] is True
    assert doc["text_laenge_original"] == 50000
    # Truncated text + Marker insgesamt etwas mehr als max_bytes_per_doc
    assert doc["text_laenge_uebertragen"] < 5300
    assert "gekuerzt" in doc["extrahierter_text"]


def test_batch_does_not_exceed_max_text_bytes(setup_env):
    db = setup_env
    _add_docs(db, n=20, text_size=10000)
    mcp = _make_mcp(db)
    result = _call(mcp, "dokumente_batch_analysieren",
                   {"max_text_bytes": 20000, "max_bytes_per_doc": 4000})
    # Summe der uebertragenen Bytes muss unter max_text_bytes plus
    # einem Marker-Overhead pro Doku liegen.
    total = sum(d["text_laenge_uebertragen"] for d in result["dokumente"])
    # 20000 plus pro-Doku-Marker (~120 Bytes), max 8 Docs
    assert total < 20000 + 8 * 200


def test_batch_hard_caps_invalid_args(setup_env):
    """Niemand kann mit max_text_bytes=999999 die Response sprengen."""
    db = setup_env
    _add_docs(db, n=5, text_size=10000)
    mcp = _make_mcp(db)
    result = _call(mcp, "dokumente_batch_analysieren",
                   {"max_text_bytes": 9_999_999, "max_dokumente": 9999,
                    "max_bytes_per_doc": 9_999_999})
    # Hard-Caps: 50000 / 20 / 20000
    # Bei 5 Docs x 10000 Bytes ist die Total-Payload <= 50000
    total = sum(d["text_laenge_uebertragen"] for d in result["dokumente"])
    assert total <= 50000 + 5 * 200  # pro-Doku-Marker-Overhead


def test_batch_profile_section_is_capped(setup_env):
    db = setup_env
    _add_docs(db, n=2, text_size=1000)
    # Riesiges Profil mit 200 Skills + langer Summary
    for i in range(200):
        db.add_skill({"name": f"Skill_{i}", "category": "fachlich", "level": 3})
    pid = db.get_active_profile_id()
    db.connect().execute(
        "UPDATE profile SET summary=? WHERE id=?",
        ("x" * 5000, pid),
    )
    db.connect().commit()
    mcp = _make_mcp(db)
    result = _call(mcp, "dokumente_batch_analysieren",
                   {"profil_mitsenden": True})
    p = result["aktuelles_profil"]
    assert len(p["skills"]) <= 100, f"skills nicht gecappt: {len(p['skills'])}"
    assert len(p["summary"]) <= 500, f"summary nicht gecappt: {len(p['summary'])}"
    # Counter zeigt die volle Anzahl trotz Cap
    assert p["skills_anzahl"] >= 100


def test_batch_empty_docs(setup_env):
    db = setup_env
    mcp = _make_mcp(db)
    result = _call(mcp, "dokumente_batch_analysieren", {})
    assert result["status"] == "fertig"
