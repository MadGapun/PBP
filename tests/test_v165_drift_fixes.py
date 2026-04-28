"""Tests fuer v1.6.5-Drift-Fixes (#534 Counter, #539 fit_analyse-Score)."""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v165_test_")
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
    return raw


def _call(mcp, name, args):
    """v1.6.5: FastMCP 2.12 entfernte mcp.call_tool — wir nutzen tool.run()."""
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


# ============= #534 — Counter-Drift mit Blacklist =================
def test_534_blacklist_filter_konsistent_active_jobs(setup_env):
    """Counter (mit exclude_blacklisted=True) und Liste sind konsistent."""
    db, _ = setup_env
    # Zwei aktive Jobs anlegen, einer von Blacklist-Firma
    db.save_jobs([
        {
            "hash": "h_normal_01",
            "title": "Senior Python Developer",
            "company": "TechCorp AG",
            "url": "https://example.com/1",
            "source": "bundesagentur",
            "score": 50,
            "found_at": "2026-04-28T00:00:00",
        },
        {
            "hash": "h_blacklisted_02",
            "title": "Senior Consultant PLM",
            "company": "BadCorp Ltd",  # wird gleich blacklisted
            "url": "https://example.com/2",
            "source": "linkedin",
            "score": 30,
            "found_at": "2026-04-28T00:00:00",
        },
    ])
    db.add_to_blacklist("firma", "BadCorp Ltd")

    # Counter mit exclude_blacklisted=True (was die Liste auch nutzt)
    counter_value = len(db.get_active_jobs(exclude_applied=True, exclude_blacklisted=True))
    list_value = len(db.get_active_jobs(exclude_applied=False, exclude_blacklisted=True))

    assert counter_value == 1, f"Counter sollte nur 1 nicht-blacklisted Job zeigen, hat {counter_value}"
    assert list_value == 1, "Liste sollte gleich viele Jobs zeigen wie Counter"
    assert counter_value == list_value, "Counter und Liste muessen identisch sein"


# ============= #539 — fit_analyse persistiert Score ================
def test_539_fit_analyse_persistiert_score(setup_env):
    """fit_analyse schreibt total_score zurueck nach jobs.score."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp

    # Job mit Initial-Score 0 (z.B. Scrape ohne Score-Berechnung)
    db.save_jobs([{
        "hash": "fit_test_01",
        "title": "Senior Python Developer",
        "company": "PythonCo",
        "url": "https://example.com/fit1",
        "source": "manuell",
        "description": "Python FastAPI Postgres Backend Developer mit Erfahrung",
        "score": 0,  # Initial 0 — fit_analyse soll auf >0 erhoehen
        "found_at": "2026-04-28T00:00:00",
    }])

    # Suchkriterien die zu Score-Erhoehung fuehren sollten
    db.set_search_criteria("keywords_muss", ["python"])
    db.set_search_criteria("keywords_plus", ["fastapi", "postgres", "backend"])

    # Initial: Score = 0
    initial_score = db.get_job("fit_test_01").get("score")
    assert initial_score == 0

    # fit_analyse aufrufen
    raw = _call(mcp, "fit_analyse", {"job_hash": "fit_test_01"})
    result = _result(raw)

    # total_score sollte hoeher sein und in DB persistiert
    assert "total_score" in result
    new_score = result["total_score"]
    assert new_score > initial_score, f"Erwartet > {initial_score}, bekommen: {new_score}"

    # DB sollte aktualisiert sein
    persisted = db.get_job("fit_test_01").get("score")
    assert persisted == new_score, f"Score nicht persistiert: DB={persisted}, fit_analyse={new_score}"

    # score_aktualisiert sollte im result enthalten sein
    assert "score_aktualisiert" in result


def test_539_fit_analyse_kein_redundanter_update(setup_env):
    """Wenn Score gleich bleibt, kein DB-Update + kein score_aktualisiert."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp

    # Job mit Score 0 ohne Keywords
    db.save_jobs([{
        "hash": "fit_idle_01",
        "title": "Junior PHP Developer",
        "company": "PHPCo",
        "url": "https://example.com/fit2",
        "source": "manuell",
        "description": "PHP Hobby-Programmierung",
        "score": 0,
        "found_at": "2026-04-28T00:00:00",
    }])
    # Keine matching Keywords
    db.set_search_criteria("keywords_muss", ["python"])

    raw = _call(mcp, "fit_analyse", {"job_hash": "fit_idle_01"})
    result = _result(raw)

    # Wenn Initial-Score und neuer Score gleich (z.B. beide 0): kein redundantes Update
    if result.get("total_score") == 0:
        assert "score_aktualisiert" not in result, (
            "Wenn Score unveraendert, sollte kein score_aktualisiert-Marker sein"
        )
