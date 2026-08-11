"""Tests fuer v1.7.12 — #768 (A27): WAL-Hygiene.

Belegter Vorfall 23.07.2026: MCP-Server und Dashboard hielten die DB von
zwei Seiten offen; die Hauptdatei blieb 29 Stunden unveraendert, waehrend
3,9 MB Schreibvorgaenge in der WAL steckten — bei einem harten Kill
waeren Stunden Arbeit in der Schwebe gewesen. Es gab im gesamten Code
KEINEN einzigen wal_checkpoint-Aufruf.
"""
import asyncio
import importlib
import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_768_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_768_checkpoint_leert_wal(setup_env):
    db, _ = setup_env
    # Schreiblast erzeugen -> WAL waechst
    for i in range(50):
        db.add_application({"company": f"F{i}", "title": "T",
                            "status": "beworben"})
    assert db.wal_groesse_bytes() > 0, "WAL muss nach Writes Inhalt haben"
    res = db.wal_checkpoint(truncate=True)
    assert not res.get("fehler"), res
    assert res["blockiert"] is False, "einzelner Prozess darf nie blockieren"
    assert db.wal_groesse_bytes() == 0, \
        "TRUNCATE muss die WAL auf 0 zuruecksetzen"


def test_768_passive_blockiert_nie(setup_env):
    db, _ = setup_env
    db.add_application({"company": "F", "title": "T", "status": "beworben"})
    res = db.wal_checkpoint(truncate=False)
    assert res["modus"] == "PASSIVE"
    assert not res.get("fehler"), res


def test_768_close_schreibt_wal_zurueck(setup_env):
    """Sauberes Beenden darf keine Arbeit in der Sidecar-Datei lassen."""
    db, tmpdir = setup_env
    for i in range(30):
        db.add_application({"company": f"C{i}", "title": "T",
                            "status": "beworben"})
    wal_pfad = Path(str(db.db_path) + "-wal")
    assert wal_pfad.exists() and wal_pfad.stat().st_size > 0
    db.close()
    groesse = wal_pfad.stat().st_size if wal_pfad.exists() else 0
    assert groesse == 0, f"WAL nach close(): {groesse} Bytes"
    # Fixture-Teardown ruft close() erneut — muss idempotent sein
    db.connect()


def test_768_diagnose_meldet_wal_zustand(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp

    async def _run():
        tool = await mcp.get_tool("pbp_diagnose")
        res = await tool.run({"auto_fix": False})
        return res.structured_content if hasattr(
            res, "structured_content") else res
    raw = asyncio.run(_run())
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    alles = str(raw)
    assert "WAL" in alles, "Diagnose muss den WAL-Zustand ausweisen"
