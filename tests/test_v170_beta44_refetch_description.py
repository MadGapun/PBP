"""Tests fuer v1.7.0-beta.44 — Stellenbeschreibung nachladen (#622).

Layer A (UI-Filter), Layer B (Per-Klick-Endpoint), Layer C (Auto-Engine-Step),
plus MCP-Tool. Wir mocken `httpx.Client.get` und
`fetch_description_from_detail`, um keine echten HTTP-Calls auszuloesen
(User-Vorgabe: keine Live-HTTP-Calls in Tests).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta44_")
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


def _seed_job_without_description(db, hash_suffix="abc"):
    """Hilfs-Funktion: Stelle ohne Beschreibung anlegen."""
    pid = db.get_active_profile_id()
    full_hash = f"{pid}:{hash_suffix}"
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, url, "
        " description, score, is_active, source, found_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (full_hash, pid, "Test Job", "ACME",
         "https://example.com/job/123", "", 75, 1, "manuell",
         "2026-05-09T10:00:00")
    )
    conn.commit()
    return full_hash


# ============= Layer B: Per-Klick-Refetch-Endpoint ============

def test_refetch_endpoint_404_when_job_missing(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/jobs/nonexistent/refetch-description")
    assert r.status_code == 404


def test_refetch_endpoint_400_when_no_url(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    full_hash = f"{pid}:nourl"
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, url, is_active, source) "
        "VALUES (?,?,?,?,?,?)",
        (full_hash, pid, "X", "", 1, "manuell")
    )
    conn.commit()
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post(f"/api/jobs/{full_hash}/refetch-description")
    assert r.status_code == 400
    assert "URL" in r.json()["error"]


def test_refetch_endpoint_success_writes_description(setup_env):
    db = setup_env
    job_hash = _seed_job_without_description(db, "ok123")
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app

    fake_text = "Wir suchen einen Senior PLM Engineer fuer unser Team. " * 5
    with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
               return_value=fake_text):
        client = TestClient(app)
        r = client.post(f"/api/jobs/{job_hash}/refetch-description")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["chars"] >= 50
    # Verifizieren dass auch wirklich in der DB landet
    job = db.get_job(job_hash)
    assert len(job["description"]) >= 50


def test_refetch_endpoint_404_when_no_description_found(setup_env):
    db = setup_env
    job_hash = _seed_job_without_description(db, "blocked")
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
               return_value=""):  # Bot-Block oder Login-Wall simulieren
        client = TestClient(app)
        r = client.post(f"/api/jobs/{job_hash}/refetch-description")
    assert r.status_code == 404
    # Failure-Counter wurde hochgezaehlt
    fail_count = int(db.get_setting(f"refetch_fail:{job_hash}", "0") or "0")
    assert fail_count == 1


def test_refetch_endpoint_502_on_http_exception(setup_env):
    db = setup_env
    job_hash = _seed_job_without_description(db, "neterr")
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
               side_effect=Exception("DNS broken")):
        client = TestClient(app)
        r = client.post(f"/api/jobs/{job_hash}/refetch-description")
    assert r.status_code == 502
    fail_count = int(db.get_setting(f"refetch_fail:{job_hash}", "0") or "0")
    assert fail_count == 1


# ============= Layer C: Auto-Engine-Step ============

def test_auto_refetch_finds_jobs_without_description(setup_env):
    db = setup_env
    _seed_job_without_description(db, "auto1")
    _seed_job_without_description(db, "auto2")
    from bewerbungs_assistent.dashboard import _run_auto_refetch_descriptions
    fake_text = "X" * 200
    with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
               return_value=fake_text):
        result = _run_auto_refetch_descriptions("2026-05-09T10:00:00")
    assert result["successes"] == 2
    assert result["failures"] == 0


def test_auto_refetch_skips_after_3_failures(setup_env):
    db = setup_env
    job_hash = _seed_job_without_description(db, "skipme")
    # Setze Failure-Count auf 3 (Backoff-Schwelle)
    db.set_setting(f"refetch_fail:{job_hash}", "3")
    from bewerbungs_assistent.dashboard import _run_auto_refetch_descriptions
    with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
               return_value="Sollte nicht gerufen werden"):
        result = _run_auto_refetch_descriptions("2026-05-09T10:00:00")
    assert result["skipped_backoff"] == 1
    assert result["processed"] == 0


def test_auto_refetch_respects_max_jobs_cap(setup_env):
    db = setup_env
    for i in range(15):
        _seed_job_without_description(db, f"cap{i}")
    from bewerbungs_assistent.dashboard import _run_auto_refetch_descriptions
    with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
               return_value="X" * 200):
        result = _run_auto_refetch_descriptions("2026-05-09T10:00:00", max_jobs=5)
    assert result["processed"] == 5
    assert result["successes"] == 5


def test_auto_refetch_increments_failure_counter(setup_env):
    db = setup_env
    job_hash = _seed_job_without_description(db, "failit")
    from bewerbungs_assistent.dashboard import _run_auto_refetch_descriptions
    with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
               return_value=""):
        _run_auto_refetch_descriptions("2026-05-09T10:00:00")
    fail = int(db.get_setting(f"refetch_fail:{job_hash}", "0") or "0")
    assert fail == 1


def test_auto_refetch_resets_failure_on_success(setup_env):
    db = setup_env
    job_hash = _seed_job_without_description(db, "recover")
    db.set_setting(f"refetch_fail:{job_hash}", "2")  # Vorherige Fehler
    from bewerbungs_assistent.dashboard import _run_auto_refetch_descriptions
    with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
               return_value="X" * 200):
        _run_auto_refetch_descriptions("2026-05-09T10:00:00")
    fail = int(db.get_setting(f"refetch_fail:{job_hash}", "0") or "0")
    assert fail == 0


# ============= MCP-Tool ============

def test_mcp_tool_stellenbeschreibung_nachladen_success(setup_env):
    db = setup_env
    job_hash = _seed_job_without_description(db, "mcp1")
    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("stellenbeschreibung_nachladen")
        with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
                   return_value="Y" * 200):
            res = await tool.run({"stellen_hash": job_hash})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run())
    assert out["status"] == "ok"
    assert out["chars"] >= 50


def test_mcp_tool_stellenbeschreibung_nachladen_no_url(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    full_hash = f"{pid}:nourl"
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, url, is_active, source) "
        "VALUES (?,?,?,?,?,?)",
        (full_hash, pid, "X", "", 1, "manuell")
    )
    conn.commit()

    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("stellenbeschreibung_nachladen")
        res = await tool.run({"stellen_hash": full_hash})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run())
    assert out["status"] == "fehler"
    assert "URL" in out["grund"]


# ============= Elwosa-Linien fuer Refetch ============

def test_refetch_status_lines_exist():
    from bewerbungs_assistent.services.elwosa_lines import STATUS_LINES
    assert "auto_refetch_descriptions" in STATUS_LINES
    assert len(STATUS_LINES["auto_refetch_descriptions"]) >= 3


def test_refetch_status_lines_pass_validator():
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    from bewerbungs_assistent.services.elwosa_lines import STATUS_LINES
    for line in STATUS_LINES["auto_refetch_descriptions"]:
        # Variablen mit Dummy-Werten fuellen
        try:
            filled = line.format(count=3, failed=2)
        except (KeyError, ValueError):
            filled = line
        validate_tonfall(filled)
