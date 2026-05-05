"""Tests fuer v1.7.0-beta.5.

- #472 n:m Bewerbung-Stelle (application_jobs Junction)
- #572 Skill-Zeitraeume (skill_periods)
- #580 Stellen-Vergleich + Aehnliche-Stellen-Finden
"""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta5_")
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


# ============= #472 n:m Schema + Migration ===============

def test_472_application_jobs_table_exists(setup_env):
    db, _ = setup_env
    conn = db.connect()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='application_jobs'"
    ).fetchone()
    assert row is not None


def test_472_link_application_to_job_idempotent(setup_env):
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    db.save_jobs([{
        "hash": "j1", "title": "Some", "company": "C", "url": "x",
        "source": "manuell", "score": 50,
    }])
    lid1 = db.link_application_to_job(bid, "j1")
    lid2 = db.link_application_to_job(bid, "j1")
    assert lid1 == lid2


def test_472_primary_uniqueness(setup_env):
    """Wenn eine zweite Verknuepfung als primary kommt, wird die erste auf nicht-primary gesetzt."""
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    db.save_jobs([
        {"hash": "j1", "title": "A", "company": "C", "url": "x", "source": "manuell", "score": 50},
        {"hash": "j2", "title": "B", "company": "C", "url": "y", "source": "manuell", "score": 50},
    ])
    db.link_application_to_job(bid, "j1", is_primary=True)
    db.link_application_to_job(bid, "j2", is_primary=True)
    jobs = db.get_jobs_for_application(bid)
    primaries = [j for j in jobs if j.get("link_primary")]
    assert len(primaries) == 1
    assert primaries[0]["hash"].endswith("j2")


def test_472_get_jobs_for_application(setup_env):
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    db.save_jobs([
        {"hash": "j1", "title": "A", "company": "C", "url": "x", "source": "manuell", "score": 50},
        {"hash": "j2", "title": "B", "company": "C", "url": "y", "source": "manuell", "score": 50},
    ])
    db.link_application_to_job(bid, "j1", version_label="Original", is_primary=True)
    db.link_application_to_job(bid, "j2", version_label="Repost")
    jobs = db.get_jobs_for_application(bid)
    assert len(jobs) == 2
    labels = {j.get("link_version") for j in jobs}
    assert labels == {"Original", "Repost"}


def test_472_get_applications_for_job(setup_env):
    """Reverse-Lookup: alle Bewerbungen zu einer Stelle."""
    db, _ = setup_env
    db.save_jobs([{
        "hash": "shared", "title": "X", "company": "C", "url": "x",
        "source": "manuell", "score": 50,
    }])
    b1 = db.add_application({"title": "X", "company": "C"})
    b2 = db.add_application({"title": "X", "company": "C"})
    db.link_application_to_job(b1, "shared")
    db.link_application_to_job(b2, "shared")
    apps = db.get_applications_for_job("shared")
    assert len(apps) == 2


def test_472_unlink_application_job(setup_env):
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    db.save_jobs([{"hash": "j1", "title": "A", "company": "C", "url": "x", "source": "manuell", "score": 0}])
    db.link_application_to_job(bid, "j1")
    assert len(db.get_jobs_for_application(bid)) == 1
    ok = db.unlink_application_job(bid, "j1")
    assert ok
    assert len(db.get_jobs_for_application(bid)) == 0


# ============= #572 skill_periods ===============

def test_572_skill_periods_table_exists(setup_env):
    db, _ = setup_env
    conn = db.connect()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_periods'"
    ).fetchone()
    assert row is not None


def test_572_add_and_get_skill_periods(setup_env):
    db, _ = setup_env
    profile = db.get_profile()
    sid = db.add_skill({"profile_id": profile["id"], "name": "Python", "level": 3})
    p1 = db.add_skill_period(sid, start_year=2010, end_year=2015, level=3)
    p2 = db.add_skill_period(sid, start_year=2022, end_year=None, level=4)
    periods = db.get_skill_periods(sid)
    assert len(periods) == 2
    # Ordering: laufender (end=None) vor abgeschlossenen
    # NULL end_year wird durch COALESCE auf 9999 angehoben
    # so dass laufende Zeitraeume zuerst kommen
    assert periods[0]["end_year"] is None or periods[0]["end_year"] >= 2022


def test_572_delete_skill_period(setup_env):
    db, _ = setup_env
    profile = db.get_profile()
    sid = db.add_skill({"profile_id": profile["id"], "name": "Java", "level": 2})
    pid = db.add_skill_period(sid, start_year=2010, end_year=2012)
    ok = db.delete_skill_period(pid)
    assert ok
    assert len(db.get_skill_periods(sid)) == 0


# ============= #580 Stellen-Vergleich + Aehnlich ===============

def test_580_stelle_vergleichen_tool(setup_env):
    db, _ = setup_env
    db.save_jobs([
        {"hash": "h1", "title": "Senior PLM Manager", "company": "TestCorp", "url": "x",
         "source": "manuell", "score": 70, "description": "PLM SAP Teamcenter Cloud"},
        {"hash": "h2", "title": "PLM Solution Architect", "company": "OtherCorp", "url": "y",
         "source": "manuell", "score": 75, "description": "PLM Aras Cloud AWS"},
    ])
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "stelle_vergleichen", {"hash_a": "h1", "hash_b": "h2"})
    assert result["stelle_a"]["title"] == "Senior PLM Manager"
    assert result["stelle_b"]["title"] == "PLM Solution Architect"
    # 'plm' ist in beiden Titeln gemeinsam
    assert "plm" in result["vergleich"]["titel_gemeinsam"]
    assert result["vergleich"]["score_diff"] == -5
    assert result["vergleich"]["gleiche_firma"] is False


def test_580_aehnliche_stellen_finden(setup_env):
    db, _ = setup_env
    db.save_jobs([
        {"hash": "anchor", "title": "PLM Manager", "company": "C1", "url": "x",
         "source": "manuell", "score": 70,
         "description": "PLM Teamcenter Projektleitung Engineering"},
        {"hash": "similar", "title": "PLM Senior", "company": "C2", "url": "y",
         "source": "manuell", "score": 60,
         "description": "PLM Teamcenter Projektmanagement Engineering"},
        {"hash": "different", "title": "Marketing Lead", "company": "C3", "url": "z",
         "source": "manuell", "score": 30,
         "description": "Marketing Brand Strategy Social Media"},
    ])
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "aehnliche_stellen_finden", {"stellen_hash": "anchor"})
    # similar sollte oben stehen, different sollte nicht (oder mit niedriger sim) erscheinen
    hashes = [r["hash"].split(":")[-1] for r in result["aehnliche"]]
    assert "similar" in hashes
    # 'different' kann auch erscheinen, aber mit niedrigem Score
    if "different" in hashes:
        idx_sim = hashes.index("similar")
        idx_diff = hashes.index("different")
        assert idx_sim < idx_diff


# ============= MCP-Tools bewerbung_stelle_* ===============

def test_472_bewerbung_stelle_verknuepfen_tool(setup_env):
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    db.save_jobs([{"hash": "j1", "title": "A", "company": "C", "url": "x", "source": "manuell", "score": 50}])
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "bewerbung_stelle_verknuepfen", {
        "bewerbung_id": bid,
        "stellen_hash": "j1",
        "version_label": "v1",
    })
    assert result["status"] == "verknuepft"


def test_472_bewerbung_stellen_anzeigen_tool(setup_env):
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    db.save_jobs([
        {"hash": "j1", "title": "A", "company": "C", "url": "x", "source": "manuell", "score": 50},
        {"hash": "j2", "title": "B", "company": "C", "url": "y", "source": "manuell", "score": 50},
    ])
    db.link_application_to_job(bid, "j1", is_primary=True)
    db.link_application_to_job(bid, "j2")
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "bewerbung_stellen_anzeigen", {"bewerbung_id": bid})
    assert result["anzahl"] == 2


# ============= MCP-Tools skill_zeitraum_* ===============

def test_572_skill_zeitraum_hinzufuegen_tool(setup_env):
    db, _ = setup_env
    profile = db.get_profile()
    sid = db.add_skill({"profile_id": profile["id"], "name": "Rust", "level": 2})
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "skill_zeitraum_hinzufuegen", {
        "skill_id": sid,
        "start_jahr": 2020,
        "end_jahr": 2022,
        "level": 3,
    })
    assert result["status"] == "angelegt"


def test_572_skill_zeitraeume_anzeigen_tool(setup_env):
    db, _ = setup_env
    profile = db.get_profile()
    sid = db.add_skill({"profile_id": profile["id"], "name": "Go", "level": 1})
    db.add_skill_period(sid, start_year=2018, end_year=2020, level=2)
    db.add_skill_period(sid, start_year=2023, end_year=None, level=3)
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "skill_zeitraeume_anzeigen", {"skill_id": sid})
    assert result["anzahl"] == 2
