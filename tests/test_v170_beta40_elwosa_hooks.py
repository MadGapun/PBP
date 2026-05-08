"""Tests fuer v1.7.0-beta.40 — Elwosa-Hooks (#609)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta40_")
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


# ============= Heartbeat-Endpoint ===============

def test_heartbeat_posts_welcome_first_time(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/elwosa/heartbeat")
    j = r.json()
    posted_kinds = {p["trigger"] for p in j.get("details") or []}
    assert "welcome" in posted_kinds


def test_heartbeat_skips_welcome_when_messages_exist(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    db.add_elwosa_message("schon da", trigger_kind="manual_via_claude")
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/elwosa/heartbeat")
    j = r.json()
    posted_kinds = {p["trigger"] for p in j.get("details") or []}
    assert "welcome" not in posted_kinds


def test_heartbeat_disabled_when_settings_off(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=False)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/elwosa/heartbeat")
    j = r.json()
    assert j["posted"] == 0


# ============= Hooks: bewerbung_erstellen ===============

def test_hook_bewerbung_erstellen_postet_elwosa(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.bewerbungen import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("bewerbung_erstellen")
        return await tool.run({
            "title": "Senior PLM",
            "company": "ACME",
            "stellenbeschreibung": "Beschreibung des Jobs",
        })
    asyncio.run(_run())

    msgs = db.get_elwosa_messages()
    # Mindestens eine Linie sollte posted sein mit firma=ACME
    assert any("ACME" in m["content"] for m in msgs)
    assert any(m["trigger_kind"] == "bewerbung_angelegt" for m in msgs)


# ============= Hooks: bewerbung_status_aendern ===============

def test_hook_status_change_absage_postet_elwosa(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    aid = db.add_application({"title": "T", "company": "BCorp"})
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.bewerbungen import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("bewerbung_status_aendern")
        return await tool.run({
            "bewerbung_id": aid,
            "neuer_status": "abgelehnt",
            "ablehnungsgrund": "skills_passen_nicht",
        })
    asyncio.run(_run())

    msgs = db.get_elwosa_messages()
    # Absage-Linie sollte gepostet sein (random aus Pool — 1/2 hat firma-Platzhalter)
    absage_msgs = [m for m in msgs if m["trigger_kind"] == "absage"]
    assert len(absage_msgs) >= 1
    # trigger_ref enthaelt aid
    assert absage_msgs[0]["trigger_ref"] == aid


# ============= Hook: Jobsuche-Start ===============

def test_jobsuche_speak_safe_direct(setup_env):
    """Pruefe direkt dass _elwosa_speak_safe den Hook ausloest."""
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    # Direkt die Helper-Funktion aufrufen (wie in /api/jobsuche/start verwendet)
    from bewerbungs_assistent.dashboard import _elwosa_speak_safe
    _elwosa_speak_safe("llm_task_running", ctx={"count": 5})
    msgs = db.get_elwosa_messages()
    assert any(m["trigger_kind"] == "llm_task_running" for m in msgs)


# ============= Hook: Auto-Engine-Steps ===============

def test_auto_engine_classify_emails_posts_elwosa(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    # Mail mit detected_status=NULL anlegen
    pid = db.get_active_profile_id()
    aid = db.add_application({"title": "T", "company": "C"})
    db.add_email({
        "application_id": aid,
        "filename": "x.eml", "subject": "Bewerbung",
        "sender": "a@b.de", "body_text": "Test",
        "direction": "eingang",
    })

    # LLM-Mock
    from bewerbungs_assistent.services.llm_service import TaskResult, Backend
    fake_status = MagicMock()
    fake_status.ollama_available = True
    fake_status.user_state = "active"
    fake_status.available_models = ["llama"]
    fake_svc = MagicMock()
    fake_svc.get_status.return_value = fake_status
    fake_svc.run.return_value = TaskResult(
        backend=Backend.LOCAL, success=True,
        payload={"category": "absage", "confidence": 0.9, "raw": ""},
        fallback_message=None,
    )

    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        from bewerbungs_assistent.dashboard import _run_auto_classify_emails
        out = _run_auto_classify_emails("2026-05-08T10:00:00")

    assert out["classified"] == 1
    msgs = db.get_elwosa_messages()
    # mail_classify-Linie sollte posted sein
    assert any(m["trigger_kind"] == "mail_classify" for m in msgs)


# ============= Linien-Pool fuer neue Trigger ===============

def test_bewerbung_angelegt_lines_exist():
    from bewerbungs_assistent.services.elwosa_lines import STATUS_CHANGE_LINES
    assert "bewerbung_angelegt" in STATUS_CHANGE_LINES
    assert len(STATUS_CHANGE_LINES["bewerbung_angelegt"]) >= 2


def test_llm_task_running_lines_exist():
    from bewerbungs_assistent.services.elwosa_lines import STATUS_LINES
    assert "llm_task_running" in STATUS_LINES
    assert len(STATUS_LINES["llm_task_running"]) >= 2


def test_new_lines_pass_tonfall_validator():
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    from bewerbungs_assistent.services.elwosa_lines import (
        STATUS_CHANGE_LINES, STATUS_LINES,
    )
    for line in STATUS_CHANGE_LINES["bewerbung_angelegt"]:
        # Mit dummy-Variable
        validate_tonfall(line.format(firma="ACME"))
    for line in STATUS_LINES["llm_task_running"]:
        validate_tonfall(line.format(count=3))


# ============= Frontend: Heartbeat-Polling ===============

def test_frontend_has_heartbeat_polling():
    p = PROJECT_ROOT / "frontend" / "src" / "components" / "ElwosaSidebarChat.jsx"
    content = p.read_text(encoding="utf-8")
    assert "/api/elwosa/heartbeat" in content
    assert "HEARTBEAT_INTERVAL_MS" in content
    assert "visibilitychange" in content
