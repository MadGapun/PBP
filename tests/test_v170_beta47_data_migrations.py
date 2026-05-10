"""Tests fuer v1.7.0-beta.47 — Daten-Migrationen (#613, #616)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta47_")
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


def _seed_job(db, hash_suffix, source="manuell", url=""):
    pid = db.get_active_profile_id()
    full_hash = f"{pid}:{hash_suffix}"
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, url, source, "
        "is_active, found_at) VALUES (?,?,?,?,?,?,?,?)",
        (full_hash, pid, "Test Job", "ACME", url, source, 1, "2026-05-10T10:00:00")
    )
    conn.commit()
    return full_hash


# ============= #613: detect_source_from_url ==============

def test_detect_linkedin_variants():
    from bewerbungs_assistent.services.url_to_source import detect_source_from_url
    assert detect_source_from_url("https://www.linkedin.com/jobs/view/12345") == "linkedin"
    assert detect_source_from_url("https://linkedin.com/jobs/view/12345") == "linkedin"
    assert detect_source_from_url("https://lnkd.in/abc123") == "linkedin"


def test_detect_other_known_sources():
    from bewerbungs_assistent.services.url_to_source import detect_source_from_url
    assert detect_source_from_url("https://www.stepstone.de/stellenangebote--Senior-PLM--12345") == "stepstone"
    assert detect_source_from_url("https://de.indeed.com/viewjob?jk=abc") == "indeed"
    assert detect_source_from_url("https://www.xing.com/jobs/test") == "xing"
    assert detect_source_from_url("https://jobboerse.arbeitsagentur.de/123") == "bundesagentur"
    assert detect_source_from_url("https://www.freelance.de/Projekt/12345") == "freelance_de"


def test_detect_unknown_url_falls_back_to_manuell():
    from bewerbungs_assistent.services.url_to_source import detect_source_from_url
    assert detect_source_from_url("https://www.firma-xyz.de/karriere/job/42") == "manuell"
    assert detect_source_from_url("") == "manuell"
    assert detect_source_from_url(None) == "manuell"


def test_detect_handles_url_without_scheme():
    from bewerbungs_assistent.services.url_to_source import detect_source_from_url
    assert detect_source_from_url("linkedin.com/jobs/123") == "linkedin"
    assert detect_source_from_url("www.stepstone.de/job/x") == "stepstone"


# ============= #613: stelle_manuell_anlegen autodetect ==============

def test_stelle_manuell_anlegen_autodetects_linkedin(setup_env):
    db = setup_env
    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("stelle_manuell_anlegen")
        res = await tool.run({
            "titel": "Senior PLM Architect",
            "firma": "ACME",
            "url": "https://www.linkedin.com/jobs/view/12345",
            # quelle nicht gesetzt -> Default 'manuell' -> sollte zu 'linkedin' werden
        })
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run())
    assert "fehler" not in out, out
    # Stelle sollte mit source='linkedin' angelegt sein
    jobs = db.get_active_jobs()
    matching = [j for j in jobs if "ACME" in (j.get("company") or "")]
    assert len(matching) >= 1
    assert matching[0]["source"] == "linkedin", (
        f"URL-Detection nicht angewendet, source={matching[0].get('source')}"
    )


def test_stelle_manuell_anlegen_explicit_quelle_wins(setup_env):
    """Wenn quelle explizit gesetzt ist (nicht 'manuell'), bleibt sie."""
    db = setup_env
    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("stelle_manuell_anlegen")
        res = await tool.run({
            "titel": "Test", "firma": "ACME-Beta",
            "url": "https://www.linkedin.com/jobs/view/99",
            "quelle": "firmenwebsite",  # explizit
        })
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run())
    jobs = db.get_active_jobs()
    matching = [j for j in jobs if "Beta" in (j.get("company") or "")]
    assert matching[0]["source"] == "firmenwebsite"


# ============= #613: Migration-Tool quellen_aus_urls_korrigieren ==============

def test_korrigieren_dry_run_finds_candidates(setup_env):
    db = setup_env
    _seed_job(db, "abc1", source="manuell", url="https://www.linkedin.com/jobs/x")
    _seed_job(db, "abc2", source="manuell", url="https://stepstone.de/job/y")
    _seed_job(db, "abc3", source="manuell", url="")  # leere URL -> bleibt manuell

    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run(dry):
        tool = await mcp.get_tool("quellen_aus_urls_korrigieren")
        res = await tool.run({"dry_run": dry})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run(True))
    assert out["status"] == "vorschau"
    assert out["count_changed"] == 2
    sources = sorted(c["source_neu"] for c in out["changes"])
    assert sources == ["linkedin", "stepstone"]
    # Dry run hat NICHT geschrieben
    conn = db.connect()
    rows = conn.execute("SELECT source FROM jobs WHERE hash LIKE '%:abc1'").fetchall()
    assert rows[0]["source"] == "manuell"


def test_korrigieren_apply_writes_changes(setup_env):
    db = setup_env
    _seed_job(db, "xyz1", source="manuell", url="https://www.linkedin.com/jobs/x")

    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run(dry):
        tool = await mcp.get_tool("quellen_aus_urls_korrigieren")
        res = await tool.run({"dry_run": dry})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run(False))
    assert out["status"] == "ausgefuehrt"
    assert out["count_applied"] == 1
    conn = db.connect()
    rows = conn.execute("SELECT source FROM jobs WHERE hash LIKE '%:xyz1'").fetchall()
    assert rows[0]["source"] == "linkedin"


def test_korrigieren_idempotent(setup_env):
    """Zweiter Lauf nach Erfolg findet 0 Kandidaten."""
    db = setup_env
    _seed_job(db, "xyz9", source="manuell", url="https://www.linkedin.com/jobs/x")

    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _call(dry):
        tool = await mcp.get_tool("quellen_aus_urls_korrigieren")
        res = await tool.run({"dry_run": dry})
        return res.structured_content if hasattr(res, "structured_content") else res

    asyncio.run(_call(False))  # Erstlauf
    out2 = asyncio.run(_call(True))
    assert out2["count_changed"] == 0


# ============= #616: verwaiste_stellenrefs_bereinigen ==============

def _create_orphaned_application(db, app_data, fake_hash):
    """Hilfs-Funktion: legt Job an, Bewerbung dran, loescht Job mit
    foreign_keys=OFF damit der orphaned-FK-State entsteht."""
    pid = db.get_active_profile_id()
    full_hash = f"{pid}:{fake_hash}"
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, source, "
        "is_active, found_at) VALUES (?,?,?,?,?,?,?)",
        (full_hash, pid, app_data.get("title", "X"),
         app_data.get("company", "Y"), "manuell", 1, "2026-05-10")
    )
    conn.commit()
    app_data = dict(app_data)
    app_data["job_hash"] = full_hash
    aid = db.add_application(app_data)
    # Job loeschen ohne FK-Cascade auszuloesen → orphaned state
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DELETE FROM jobs WHERE hash=?", (full_hash,))
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")
    return aid


def test_orphan_finder_finds_missing_jobs(setup_env):
    """Bewerbung mit job_hash der nicht (mehr) in jobs existiert."""
    db = setup_env
    aid = _create_orphaned_application(db, {
        "title": "Orphaned Job",
        "company": "Phantom GmbH",
        "url": "https://www.linkedin.com/jobs/lost",
        "status": "beworben",
        "applied_at": "2026-05-10",
    }, "nonexistent12")

    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _call(strategie, dry):
        tool = await mcp.get_tool("verwaiste_stellenrefs_bereinigen")
        res = await tool.run({"strategie": strategie, "dry_run": dry})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_call("report", True))
    assert out["count_orphaned"] == 1
    assert out["orphans"][0]["company"] == "Phantom GmbH"


def test_orphan_strategy_leeren_clears_job_hash(setup_env):
    db = setup_env
    aid = _create_orphaned_application(db, {
        "title": "Lost", "company": "X",
        "status": "beworben", "applied_at": "2026-05-10",
    }, "phantom01abc")

    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _call():
        tool = await mcp.get_tool("verwaiste_stellenrefs_bereinigen")
        res = await tool.run({"strategie": "leeren", "dry_run": False})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_call())
    assert out["count_applied"] == 1
    # Verify in DB — leeren setzt auf NULL (FK-konform), nicht ''
    apps = db.get_applications()
    assert apps[0]["job_hash"] in (None, "", "None")


def test_orphan_strategy_rekonstruieren_creates_placeholder(setup_env):
    db = setup_env
    aid = _create_orphaned_application(db, {
        "title": "Senior PLM",
        "company": "Reconstruct GmbH",
        "url": "https://www.linkedin.com/jobs/orig",
        "status": "beworben", "applied_at": "2026-05-10",
    }, "lost000abcd")

    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _call():
        tool = await mcp.get_tool("verwaiste_stellenrefs_bereinigen")
        res = await tool.run({"strategie": "rekonstruieren", "dry_run": False})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_call())
    assert out["count_applied"] == 1
    # Stelle sollte als is_active=0 angelegt worden sein
    conn = db.connect()
    placeholder = conn.execute(
        "SELECT * FROM jobs WHERE company = 'Reconstruct GmbH'"
    ).fetchone()
    assert placeholder is not None
    assert placeholder["is_active"] == 0
    assert "Rekonstruiert" in (placeholder["description"] or "")
    # Bewerbung jetzt mit dem neuen Hash verknuepft
    apps = db.get_applications()
    assert apps[0]["job_hash"] != f"lost000abcd"


def test_orphan_invalid_strategie(setup_env):
    db = setup_env
    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _call():
        tool = await mcp.get_tool("verwaiste_stellenrefs_bereinigen")
        res = await tool.run({"strategie": "voodoo"})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_call())
    assert "fehler" in out
