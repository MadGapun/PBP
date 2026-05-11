"""Tests fuer v1.7.0-beta.51 — Health-Check fuer Quellen (#624 Phase 2)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta51_")
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


# ============= check_source() ============

def test_check_source_unknown_source():
    from bewerbungs_assistent.job_scraper.health import check_source
    r = check_source("doesnt-exist")
    assert r["reachable"] is False
    assert r["error"] == "unknown_source"


def test_check_source_no_probe_defined():
    """Manche Quellen (z.B. Browser-basiert) haben keine API → no_probe_defined."""
    from bewerbungs_assistent.job_scraper.health import check_source
    # 'jobspy_indeed' ist Wrapper, kein direkter API-Probe
    r = check_source("jobspy_indeed")
    assert r["reachable"] is False
    assert r["error"] == "no_probe_defined"


def test_check_source_reachable_200():
    from bewerbungs_assistent.job_scraper import health
    fake_resp = MagicMock(spec=httpx.Response)
    fake_resp.status_code = 200

    fake_client = MagicMock()
    fake_client.get.return_value = fake_resp
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.health.make_session",
               return_value=fake_client):
        r = health.check_source("arbeitnow")

    assert r["reachable"] is True
    assert r["http_status"] == 200
    assert r["error"] is None
    assert r["latency_ms"] is not None
    assert r["method"] == "GET"


def test_check_source_unreachable_503():
    from bewerbungs_assistent.job_scraper import health
    fake_resp = MagicMock(spec=httpx.Response)
    fake_resp.status_code = 503

    fake_client = MagicMock()
    fake_client.get.return_value = fake_resp
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.health.make_session",
               return_value=fake_client):
        r = health.check_source("remoteok")

    assert r["reachable"] is False
    assert r["http_status"] == 503


def test_check_source_timeout():
    from bewerbungs_assistent.job_scraper import health

    fake_client = MagicMock()
    fake_client.get.side_effect = httpx.TimeoutException("simulated")
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.health.make_session",
               return_value=fake_client):
        r = health.check_source("greenhouse")

    assert r["reachable"] is False
    assert r["error"] == "timeout"


def test_check_source_transport_error():
    from bewerbungs_assistent.job_scraper import health

    fake_client = MagicMock()
    fake_client.get.side_effect = httpx.ConnectError("dns failed")
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.health.make_session",
               return_value=fake_client):
        r = health.check_source("remotive")

    assert r["reachable"] is False
    assert "transport" in r["error"]


def test_check_source_post_method():
    """workday_dax nutzt POST."""
    from bewerbungs_assistent.job_scraper import health
    fake_resp = MagicMock(spec=httpx.Response)
    fake_resp.status_code = 200

    fake_client = MagicMock()
    fake_client.post.return_value = fake_resp
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.health.make_session",
               return_value=fake_client):
        r = health.check_source("workday_dax")

    assert r["reachable"] is True
    assert r["method"] == "POST"
    fake_client.post.assert_called_once()


# ============= check_all_sources() / get_probable_sources() ============

def test_get_probable_sources_returns_known_keys():
    from bewerbungs_assistent.job_scraper.health import get_probable_sources
    keys = get_probable_sources()
    # Mind. die zentralen sollten dabei sein
    expected = {"bundesagentur", "arbeitnow", "remoteok", "greenhouse",
                 "remotive", "himalayas", "personio"}
    assert expected.issubset(set(keys))


def test_check_all_returns_one_result_per_source():
    from bewerbungs_assistent.job_scraper import health
    fake_resp = MagicMock(spec=httpx.Response)
    fake_resp.status_code = 200

    fake_client = MagicMock()
    fake_client.get.return_value = fake_resp
    fake_client.post.return_value = fake_resp
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.health.make_session",
               return_value=fake_client):
        results = health.check_all_sources()

    assert len(results) == len(health.get_probable_sources())
    assert all(r["reachable"] for r in results)


# ============= MCP-Tool quellen_health_check ============

def _build_mcp(db):
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    return mcp


def _call(mcp, name, args):
    import asyncio
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def test_mcp_health_check_specific_source(setup_env):
    db = setup_env
    fake_resp = MagicMock(spec=httpx.Response)
    fake_resp.status_code = 200
    fake_client = MagicMock()
    fake_client.get.return_value = fake_resp
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.health.make_session",
               return_value=fake_client):
        mcp = _build_mcp(db)
        out = _call(mcp, "quellen_health_check",
                     {"quellen": ["arbeitnow"], "parallel": False})

    assert out["count_total"] == 1
    assert out["count_reachable"] == 1
    assert out["results"][0]["source"] == "arbeitnow"


def test_mcp_health_check_all_sources_with_mock(setup_env):
    db = setup_env
    fake_resp = MagicMock(spec=httpx.Response)
    fake_resp.status_code = 200
    fake_client = MagicMock()
    fake_client.get.return_value = fake_resp
    fake_client.post.return_value = fake_resp
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.health.make_session",
               return_value=fake_client):
        mcp = _build_mcp(db)
        out = _call(mcp, "quellen_health_check",
                     {"quellen": [], "parallel": True})

    assert out["count_total"] >= 10  # mind. 10 Quellen mit Probe
    assert out["count_reachable"] == out["count_total"]


def test_mcp_health_check_mixed_results(setup_env):
    """Manche reachable, manche nicht."""
    db = setup_env
    call_count = [0]

    def get_side_effect(url):
        call_count[0] += 1
        resp = MagicMock(spec=httpx.Response)
        # Jeder zweite Aufruf liefert 503
        resp.status_code = 503 if call_count[0] % 2 == 0 else 200
        return resp

    fake_client = MagicMock()
    fake_client.get.side_effect = get_side_effect
    fake_client.post.return_value = MagicMock(status_code=200, spec=httpx.Response)
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.health.make_session",
               return_value=fake_client):
        mcp = _build_mcp(db)
        out = _call(mcp, "quellen_health_check",
                     {"quellen": ["arbeitnow", "remoteok", "greenhouse",
                                   "remotive"],
                      "parallel": False})

    assert out["count_unreachable"] >= 1
    assert out["count_reachable"] >= 1
