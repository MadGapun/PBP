"""Tests fuer v1.7.0-beta.28 — #594 Stufe 3: LLM-Pattern-Analyse +
Korrektur-Loop + adaptive Prompts.

Tests laufen ohne Ollama: lokale AI wird ueber Patches simuliert.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta28_")
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


# ============= LLM-Service: analyze_user_patterns ===============

def test_analyze_user_patterns_taskkind_exists():
    from bewerbungs_assistent.services.llm_service import TaskKind
    assert TaskKind.ANALYZE_USER_PATTERNS.value == "analyze_user_patterns"


def test_analyze_user_patterns_in_routing_table():
    from bewerbungs_assistent.services.llm_service import (
        TaskKind, ROUTING_TABLE, Backend
    )
    backends = ROUTING_TABLE[TaskKind.ANALYZE_USER_PATTERNS]
    assert Backend.LOCAL in backends


def test_analyze_user_patterns_prompt_includes_aggregate():
    from bewerbungs_assistent.services.llm_service import (
        _build_analyze_user_patterns_prompt
    )
    prompt = _build_analyze_user_patterns_prompt({
        "aggregate": {
            "window_days": 30,
            "total_events": 200,
            "top_pages": [{"page": "stellen", "views": 50}],
        }
    })
    assert "30" in prompt
    assert "TYP|TITEL|EMPFEHLUNG" in prompt
    assert "filter_recommendation" in prompt
    assert "ux_friction" in prompt


def test_parse_analyze_user_patterns_extracts_three_insights():
    from bewerbungs_assistent.services.llm_service import (
        _parse_analyze_user_patterns
    )
    raw = (
        "filter_recommendation|Score-Filter ueber 70|Du nutzt das oft, koennte Default werden\n"
        "ux_friction|Zu viele Klicks auf Stellen|Filter koennten helfen\n"
        "dismiss_pattern|85% wegen falsches_fachgebiet|Auto-Filter bauen"
    )
    out = _parse_analyze_user_patterns(raw)
    assert out["count"] == 3
    assert out["insights"][0]["kind"] == "filter_recommendation"
    assert out["insights"][1]["kind"] == "ux_friction"
    assert "Auto-Filter" in out["insights"][2]["recommendation"]


def test_parse_analyze_user_patterns_rejects_invalid_kind():
    from bewerbungs_assistent.services.llm_service import (
        _parse_analyze_user_patterns
    )
    raw = "garbage_kind|Title|Something\nfilter_recommendation|valid|ok"
    out = _parse_analyze_user_patterns(raw)
    assert out["count"] == 1
    assert out["insights"][0]["kind"] == "filter_recommendation"


def test_parse_analyze_user_patterns_caps_at_three():
    from bewerbungs_assistent.services.llm_service import (
        _parse_analyze_user_patterns
    )
    raw = "\n".join(
        f"filter_recommendation|Title{i}|Rec{i}" for i in range(10)
    )
    out = _parse_analyze_user_patterns(raw)
    assert out["count"] == 3


def test_parse_analyze_user_patterns_empty():
    from bewerbungs_assistent.services.llm_service import (
        _parse_analyze_user_patterns
    )
    out = _parse_analyze_user_patterns("")
    assert out["count"] == 0
    assert out["insights"] == []


# ============= DB: learning_insights CRUD ===============

def test_upsert_learning_insight_creates(setup_env):
    db = setup_env
    insight_id = db.upsert_learning_insight({
        "kind": "filter_recommendation",
        "title": "Score-Filter ueber 70",
        "details": {"recommendation": "Default setzen"},
        "score": 0.9,
        "app_version": "1.7.0-beta.28",
    })
    assert insight_id > 0
    items = db.list_learning_insights()
    assert len(items) == 1
    assert items[0]["title"] == "Score-Filter ueber 70"
    assert items[0]["recommendation"] == "Default setzen"
    assert items[0]["observed_count"] == 1


def test_upsert_learning_insight_increments_count(setup_env):
    db = setup_env
    db.upsert_learning_insight({
        "kind": "ux_friction", "title": "X", "details": {}
    })
    db.upsert_learning_insight({
        "kind": "ux_friction", "title": "X", "details": {}
    })
    items = db.list_learning_insights()
    assert len(items) == 1
    assert items[0]["observed_count"] == 2


def test_dismiss_learning_insight(setup_env):
    db = setup_env
    iid = db.upsert_learning_insight({
        "kind": "ux_friction", "title": "Anti", "details": {}
    })
    ok = db.dismiss_learning_insight(iid)
    assert ok
    assert db.list_learning_insights(only_active=True) == []
    assert len(db.list_learning_insights(only_active=False)) == 1


def test_deactivate_outdated_insights(setup_env):
    db = setup_env
    db.upsert_learning_insight({
        "kind": "ux_friction", "title": "Old",
        "details": {}, "app_version": "1.6.0",
    })
    db.upsert_learning_insight({
        "kind": "ux_friction", "title": "New",
        "details": {}, "app_version": "1.7.0-beta.28",
    })
    # Manuell last_seen_at auf > 30 Tage zurueckdatieren fuer "Old"
    from datetime import datetime, timedelta
    old_ts = (datetime.now() - timedelta(days=60)).isoformat()
    conn = db.connect()
    conn.execute(
        "UPDATE learning_insights SET last_seen_at=? WHERE title='Old'",
        (old_ts,)
    )
    conn.commit()

    n = db.deactivate_outdated_insights("1.7.0-beta.28")
    assert n == 1
    titles = [i["title"] for i in db.list_learning_insights(only_active=True)]
    assert "New" in titles
    assert "Old" not in titles


def test_count_llm_corrections(setup_env):
    db = setup_env
    db.add_activity_event({
        "event_type": "llm_correction", "entity_type": "job",
        "entity_id": "x", "metadata": {}, "learning_enabled": True,
    })
    db.add_activity_event({
        "event_type": "click", "entity_type": "job",
        "entity_id": "y", "metadata": {}, "learning_enabled": True,
    })
    assert db.count_llm_corrections() == 1


# ============= API: /api/learning/insights ===============

def test_api_learning_insights_empty(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/learning/insights")
    assert r.status_code == 200
    assert r.json() == {"insights": [], "count": 0}


def test_api_learning_insights_returns_persisted(setup_env):
    db = setup_env
    db.upsert_learning_insight({
        "kind": "filter_recommendation",
        "title": "Schwellwert 70",
        "details": {"recommendation": "Default machen"},
        "score": 0.8,
    })
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/learning/insights")
    j = r.json()
    assert j["count"] == 1
    assert j["insights"][0]["title"] == "Schwellwert 70"
    assert j["insights"][0]["recommendation"] == "Default machen"


def test_api_dismiss_learning_insight(setup_env):
    db = setup_env
    iid = db.upsert_learning_insight({
        "kind": "ux_friction", "title": "X", "details": {}
    })
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.delete(f"/api/learning/insights/{iid}")
    assert r.status_code == 200
    assert r.json()["dismissed"] == iid

    r2 = client.get("/api/learning/insights?only_active=1")
    assert r2.json()["count"] == 0


# ============= _run_analyze_user_patterns ===============

def test_analyze_skipped_when_learning_disabled(setup_env):
    db = setup_env
    db.set_profile_setting("learning_enabled", False)
    from bewerbungs_assistent.dashboard import _run_analyze_user_patterns
    out = _run_analyze_user_patterns("2026-05-07T12:00:00")
    assert out["skipped"] is True
    assert "learning_enabled" in out["reason"]


def test_analyze_skipped_when_too_few_events(setup_env):
    db = setup_env
    # 5 events << 50 default threshold
    for i in range(5):
        db.add_activity_event({
            "event_type": "page_view", "page": "stellen",
            "metadata": {}, "learning_enabled": True,
        })
    from bewerbungs_assistent.dashboard import _run_analyze_user_patterns
    out = _run_analyze_user_patterns("2026-05-07T12:00:00")
    assert out["skipped"] is True
    assert "Mindestschwelle" in out["reason"]


def test_analyze_skipped_when_local_ai_unavailable(setup_env):
    db = setup_env
    # 60 events > threshold
    events = [
        {"event_type": "page_view", "page": "stellen",
         "metadata": {}, "learning_enabled": True}
        for _ in range(60)
    ]
    db.add_activity_events_batch(events)

    # Lokale AI nicht verfuegbar
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError):
        from bewerbungs_assistent.dashboard import _run_analyze_user_patterns
        out = _run_analyze_user_patterns("2026-05-07T12:00:00")
    assert out["skipped"] is True


def test_analyze_persists_insights_when_llm_returns(setup_env):
    db = setup_env
    events = [
        {"event_type": "page_view", "page": "stellen",
         "metadata": {}, "learning_enabled": True}
        for _ in range(60)
    ]
    db.add_activity_events_batch(events)

    from bewerbungs_assistent.services.llm_service import TaskResult, Backend
    fake_payload = {
        "insights": [
            {"kind": "filter_recommendation",
             "title": "Score >= 70",
             "recommendation": "Default setzen"},
            {"kind": "ux_friction",
             "title": "Viele Klicks",
             "recommendation": "Filter pruefen"},
        ],
        "count": 2,
        "raw": "...",
    }

    fake_status = MagicMock()
    fake_status.ollama_available = True
    fake_status.user_state = "active"
    fake_status.available_models = ["llama3:8b"]

    fake_svc = MagicMock()
    fake_svc.get_status.return_value = fake_status
    fake_svc.run.return_value = TaskResult(
        backend=Backend.LOCAL, success=True, payload=fake_payload,
        fallback_message=None,
    )

    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        from bewerbungs_assistent.dashboard import _run_analyze_user_patterns
        out = _run_analyze_user_patterns("2026-05-07T12:00:00")

    assert out.get("skipped") in (False, None)
    assert out["insights"] == 2
    items = db.list_learning_insights()
    assert len(items) == 2
    titles = {i["title"] for i in items}
    assert "Score >= 70" in titles
    assert "Viele Klicks" in titles


# ============= Adaptive Prompts (#594 Stufe 3) ===============

def test_match_job_prompt_includes_dismiss_reasons():
    from bewerbungs_assistent.services.llm_service import (
        _build_match_job_to_skills_prompt
    )
    prompt = _build_match_job_to_skills_prompt({
        "profile_skills": ["Python"],
        "profile_position": "Senior Developer",
        "profile_seniority": "Senior",
        "job_title": "Werkstudent",
        "job_company": "ACME",
        "job_description": "Junior Aufgaben.",
        "dismiss_reasons_top": [
            {"reason": "falsches_fachgebiet", "count": 50},
            {"reason": "zu_junior", "count": 30},
        ],
    })
    assert "GELERNT" in prompt
    assert "falsches_fachgebiet" in prompt
    assert "50 Mal" in prompt
    assert "zu_junior" in prompt


def test_match_job_prompt_works_without_dismiss_reasons():
    from bewerbungs_assistent.services.llm_service import (
        _build_match_job_to_skills_prompt
    )
    prompt = _build_match_job_to_skills_prompt({
        "profile_skills": ["Python"],
        "profile_position": "Senior",
        "profile_seniority": "Senior",
        "job_title": "Job",
        "job_company": "X",
        "job_description": "...",
    })
    # Sollte ohne GELERNT-Block funktionieren
    assert "GELERNT" not in prompt
    assert "PASST" in prompt


# ============= LLM-Correction-Loop ===============

def test_user_override_tracked_as_llm_correction(setup_env):
    """Wenn User auf 'passt' bei einer Stelle klickt, die vorher von der
    Auto-Aussortierung als 'profil_match_negativ' gedismissed wurde, soll
    ein 'llm_correction' Event entstehen."""
    db = setup_env
    # Setup: Stelle anlegen + dismiss mit profil_match_negativ
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, "
        "is_active, dismiss_reason, found_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"{pid}:abc", pid, "Test", "ACME", 0,
         "profil_match_negativ", "2026-05-01")
    )
    conn.commit()

    # User klickt 'passt'
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register as register_jobs
    mcp = FastMCP("test")
    register_jobs(mcp, db, logging.getLogger("test"))

    import asyncio

    async def _run():
        tool = await mcp.get_tool("stelle_bewerten")
        return await tool.run({"job_hash": "abc", "bewertung": "passt"})

    asyncio.run(_run())

    # llm_correction Event muss existieren
    assert db.count_llm_corrections() >= 1


def test_user_override_NOT_tracked_for_normal_dismiss(setup_env):
    """Wenn die Stelle nicht von der LLM dismissed wurde (z.B. user-dismiss
    mit grund 'gehalt_zu_niedrig'), dann darf KEIN llm_correction-Event
    entstehen."""
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, "
        "is_active, dismiss_reason, found_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"{pid}:xyz", pid, "Test2", "ACME", 0,
         "gehalt_zu_niedrig", "2026-05-01")
    )
    conn.commit()

    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register as register_jobs
    mcp = FastMCP("test")
    register_jobs(mcp, db, logging.getLogger("test"))

    import asyncio

    async def _run():
        tool = await mcp.get_tool("stelle_bewerten")
        return await tool.run({"job_hash": "xyz", "bewertung": "passt"})

    asyncio.run(_run())

    assert db.count_llm_corrections() == 0
