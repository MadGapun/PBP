"""Regression #729: Blacklist-Check bei stelle_manuell_anlegen + Hinweis-Dedup.

1. stelle_manuell_anlegen() legt eine Stelle einer geblacklisteten Firma NICHT
   an (Fehler statt stille Anlage); force=True ueberbrueckt bewusst.
2. is_company_blacklisted matcht case-insensitiv und beidseitig-substring —
   die gemeinsame Basis fuer den Block UND den (nicht mehr doppelten) Hinweis
   nach stelle_bewerten().

HARTE ISOLATIONS-REGEL: db.db_path im Temp-Verzeichnis (BA_DATA_DIR).
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_729_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    d = Database()
    d.initialize()
    d.save_profile({"name": "Test"})
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import jobs
    import logging
    m = FastMCP("test")
    jobs.register(m, db, logging.getLogger("test"))
    return m


# ============= is_company_blacklisted =============

def test_729_helper_matcht_beidseitig(db):
    db.add_to_blacklist("firma", "Geblockt GmbH", "uninteressant")
    assert db.is_company_blacklisted("Geblockt GmbH")
    assert db.is_company_blacklisted("geblockt gmbh")          # case-insensitiv
    assert db.is_company_blacklisted("Die Geblockt GmbH & Co") # company enthaelt value
    assert db.is_company_blacklisted("Geblockt")               # value enthaelt company
    assert db.is_company_blacklisted("Andere AG") is None
    assert db.is_company_blacklisted("") is None


def test_729_keyword_eintrag_blockt_firma_nicht(db):
    # keyword-Blacklist darf den Firmen-Check nicht ausloesen
    db.add_to_blacklist("keyword", "zeitarbeit", "")
    assert db.is_company_blacklisted("zeitarbeit GmbH") is None


# ============= stelle_manuell_anlegen Block =============

def test_729_manuell_anlegen_blockt_blacklist_firma(db):
    db.add_to_blacklist("firma", "Geblockt GmbH", "kein Interesse")
    mcp = _mcp(db)
    res = _call(mcp, "stelle_manuell_anlegen",
                {"titel": "Entwickler", "firma": "Geblockt GmbH"})
    assert "fehler" in res, res
    assert "Blacklist" in res["fehler"]
    assert "kein Interesse" in res["fehler"]
    # nichts in der DB angelegt
    assert db.get_active_jobs() == [] or all(
        j.get("company") != "Geblockt GmbH" for j in db.get_active_jobs())


def test_729_force_uebersteuert_blacklist(db):
    db.add_to_blacklist("firma", "Geblockt GmbH", "kein Interesse")
    mcp = _mcp(db)
    res = _call(mcp, "stelle_manuell_anlegen",
                {"titel": "Entwickler", "firma": "Geblockt GmbH", "force": True})
    assert "fehler" not in res, res
    assert res.get("status") in ("angelegt", "erstellt") or res.get("hash")


def test_729_nicht_geblockte_firma_geht_durch(db):
    db.add_to_blacklist("firma", "Geblockt GmbH", "")
    mcp = _mcp(db)
    res = _call(mcp, "stelle_manuell_anlegen",
                {"titel": "Entwickler", "firma": "Saubere AG"})
    assert "fehler" not in res, res
