"""Tests fuer v1.7.0-beta.60 — User-Test-Sammel-Patch.

Vier zusammenhaengende Aenderungen:
- #636 MCP-Tool-Telemetrie (time_tool decorator + pbp_mcp_diagnose)
- #631 Status-Wechsel-Datum nachtraeglich editierbar
- #625 Sidebar-Layout (CSS only, kein Test)
- #637 Ollama via API starten (Stufe 1: Subprocess-Spawn)
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import time

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta60_")
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
    from bewerbungs_assistent.tools import analyse, bewerbungen
    mcp = FastMCP("test")
    import logging
    log = logging.getLogger("test")
    analyse.register(mcp, db, log)
    bewerbungen.register(mcp, db, log)
    return mcp


# ============= #636 Tool-Timing-Decorator ============

def test_time_tool_records_call(setup_env):
    """Decorator schreibt Eintrag in den Telemetrie-Buffer."""
    from bewerbungs_assistent.tools import time_tool, get_recent_tool_calls
    import logging
    log = logging.getLogger("test")

    @time_tool(log, "test_func")
    def some_tool(x):
        return {"value": x * 2}

    result = some_tool(5)
    assert result == {"value": 10}

    calls = get_recent_tool_calls(limit=5)
    assert len(calls) >= 1
    last = calls[0]
    assert last["name"] == "test_func"
    assert last["status"] == "ok"
    assert last["duration_sec"] >= 0


def test_time_tool_records_error_status(setup_env):
    """Tool das fehler-dict zurueckliefert wird als 'fehler' geloggt."""
    from bewerbungs_assistent.tools import time_tool, get_recent_tool_calls
    import logging
    log = logging.getLogger("test")

    @time_tool(log, "fehler_tool")
    def fehler_tool():
        return {"fehler": "Etwas ist schief gelaufen"}

    fehler_tool()
    calls = get_recent_tool_calls(limit=5)
    last = next(c for c in calls if c["name"] == "fehler_tool")
    assert last["status"] == "fehler"
    assert "schief" in last["error"]


def test_time_tool_records_exception(setup_env):
    """Tool das eine Exception wirft wird als 'exception' geloggt."""
    from bewerbungs_assistent.tools import time_tool, get_recent_tool_calls
    import logging
    log = logging.getLogger("test")

    @time_tool(log, "boom_tool")
    def boom_tool():
        raise ValueError("Boom")

    with pytest.raises(ValueError):
        boom_tool()

    calls = get_recent_tool_calls(limit=5)
    last = next(c for c in calls if c["name"] == "boom_tool")
    assert last["status"] == "exception"
    assert "Boom" in last["error"]


def test_get_slow_tool_calls_filters_threshold(setup_env):
    from bewerbungs_assistent.tools import time_tool, get_slow_tool_calls
    import logging
    log = logging.getLogger("test")

    @time_tool(log, "slow_tool")
    def slow_tool():
        time.sleep(0.05)
        return {}

    @time_tool(log, "fast_tool")
    def fast_tool():
        return {}

    slow_tool()
    fast_tool()

    slow = get_slow_tool_calls(threshold_sec=0.04)
    names = [c["name"] for c in slow]
    assert "slow_tool" in names
    # fast_tool sollte UNTER der Schwelle sein
    fast_in_slow = [c for c in slow if c["name"] == "fast_tool"]
    assert not fast_in_slow


# ============= #636 pbp_mcp_diagnose Tool ============

def test_pbp_mcp_diagnose_returns_recent_calls(setup_env):
    db = setup_env
    mcp = _make_mcp(db)

    # Trigger ein paar Tools (bewerbung_erstellen ist mit time_tool gewrapped)
    _call(mcp, "bewerbung_erstellen", {
        "title": "Test", "company": "ACME GmbH",
    })
    result = _call(mcp, "pbp_mcp_diagnose", {})
    assert result["status"] == "ok"
    assert "tool_calls" in result
    assert "server_pid" in result
    assert "pbp_version" in result
    # Mindestens unser bewerbung_erstellen sollte im Buffer auftauchen
    names = [c["name"] for c in result["tool_calls"]]
    assert "bewerbung_erstellen" in names


def test_pbp_mcp_diagnose_filter_slow(setup_env):
    db = setup_env
    mcp = _make_mcp(db)
    result = _call(mcp, "pbp_mcp_diagnose",
                   {"nur_langsame": True, "threshold_sec": 1000.0})
    # Nichts sollte 1000+ Sekunden brauchen
    assert result["tool_calls"] == []


# ============= #631 Datums-Editing ============

def test_event_date_update_db_layer(setup_env):
    db = setup_env
    # Bewerbung anlegen mit Status-Wechsel
    app_id = db.add_application({
        "title": "Eng", "company": "ACME GmbH", "status": "beworben",
    })
    db.update_application_status(app_id, "abgelehnt", rejection_reason="Sonstiges")

    # Event finden
    conn = db.connect()
    events = conn.execute(
        "SELECT id, status, event_date FROM application_events WHERE application_id=?",
        (app_id,)
    ).fetchall()
    rejected_event = next(e for e in events if e["status"] == "abgelehnt")
    assert rejected_event is not None

    # Datum auf vergangenes Datum korrigieren
    result = db.update_application_event_date(
        rejected_event["id"], "2026-04-15", app_id=app_id,
    )
    assert result["status"] == "ok"
    assert result["new_date"].startswith("2026-04-15")
    assert result["old_date"] != result["new_date"]


def test_event_date_update_invalid_date(setup_env):
    db = setup_env
    result = db.update_application_event_date(1, "nicht-ein-datum")
    assert "fehler" in result


def test_event_date_update_unknown_event(setup_env):
    db = setup_env
    result = db.update_application_event_date(999999, "2026-04-15")
    assert "fehler" in result
    assert "nicht gefunden" in result["fehler"]


def test_event_date_update_german_date_format(setup_env):
    db = setup_env
    app_id = db.add_application({
        "title": "Eng", "company": "ACME GmbH", "status": "beworben",
    })
    db.update_application_status(app_id, "interview")
    conn = db.connect()
    e = conn.execute(
        "SELECT id FROM application_events WHERE application_id=? AND status='interview'",
        (app_id,)
    ).fetchone()
    result = db.update_application_event_date(
        e["id"], "15.04.2026", app_id=app_id,
    )
    assert result["status"] == "ok"
    assert result["new_date"].startswith("2026-04-15")


def test_mcp_tool_event_datum_setzen(setup_env):
    db = setup_env
    mcp = _make_mcp(db)
    app_id = db.add_application({
        "title": "Eng", "company": "ACME GmbH", "status": "beworben",
    })
    db.update_application_status(app_id, "abgelehnt")
    conn = db.connect()
    e = conn.execute(
        "SELECT id FROM application_events WHERE application_id=? AND status='abgelehnt'",
        (app_id,)
    ).fetchone()
    result = _call(mcp, "bewerbung_event_datum_setzen", {
        "event_id": e["id"],
        "neues_datum": "2026-04-20",
        "bewerbung_id": app_id,
    })
    assert result["status"] == "ok"
    assert result["event_status"] == "abgelehnt"
    assert result["new_date"].startswith("2026-04-20")


def test_api_event_date_endpoint(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    db = setup_env
    app_id = db.add_application({
        "title": "Eng", "company": "ACME GmbH", "status": "beworben",
    })
    db.update_application_status(app_id, "interview")
    conn = db.connect()
    e = conn.execute(
        "SELECT id FROM application_events WHERE application_id=? AND status='interview'",
        (app_id,)
    ).fetchone()

    client = TestClient(app)
    r = client.put(
        f"/api/applications/{app_id}/events/{e['id']}/date",
        json={"event_date": "2026-04-25"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "ok"
    assert data["new_date"].startswith("2026-04-25")


def test_api_event_date_endpoint_invalid(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    db = setup_env
    app_id = db.add_application({
        "title": "Eng", "company": "ACME GmbH", "status": "beworben",
    })
    client = TestClient(app)
    r = client.put(
        f"/api/applications/{app_id}/events/999999/date",
        json={"event_date": "2026-04-25"},
    )
    assert r.status_code == 400


# ============= #637 Ollama-Start ============

def test_llm_start_when_ollama_missing(setup_env, monkeypatch):
    """Wenn `ollama` Binary nicht im PATH ist, antwortet der Endpoint
    mit 404 + status='not_installed' + Hilfe-URL."""
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    import subprocess

    # Status: nicht erreichbar
    from bewerbungs_assistent.services import llm_service
    class FakeStatus:
        ollama_available = False
        ollama_endpoint = None
        available_models = []
        models_detail = []
        selected_model = None
        user_state = "off"
        error = None
    class FakeSvc:
        def get_status(self, force_refresh=False):
            return FakeStatus()
    monkeypatch.setattr(llm_service, "get_llm_service", lambda db: FakeSvc())

    # Subprocess.Popen wirft FileNotFoundError
    def fake_popen(*args, **kwargs):
        raise FileNotFoundError("ollama")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    client = TestClient(app)
    r = client.post("/api/llm/start")
    assert r.status_code == 404
    data = r.json()
    assert data["status"] == "not_installed"
    assert "ollama.com" in data["hilfe_url"]


def test_llm_start_already_running(setup_env, monkeypatch):
    """Wenn Ollama schon laeuft, kommt status='already_running' zurueck
    ohne Spawn-Versuch."""
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    from bewerbungs_assistent.services import llm_service
    import subprocess

    class FakeStatus:
        ollama_available = True
        ollama_endpoint = "http://127.0.0.1:11434"
        available_models = ["test"]
        models_detail = []
        selected_model = "test"
        user_state = "active"
        error = None
    class FakeSvc:
        def get_status(self, force_refresh=False):
            return FakeStatus()
    monkeypatch.setattr(llm_service, "get_llm_service", lambda db: FakeSvc())
    # Popen darf NICHT aufgerufen werden — wenn doch, AssertionError
    def must_not_call(*args, **kwargs):
        raise AssertionError("subprocess.Popen sollte nicht gerufen werden")
    monkeypatch.setattr(subprocess, "Popen", must_not_call)

    client = TestClient(app)
    r = client.post("/api/llm/start")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "already_running"
    assert data["endpoint"] == "http://127.0.0.1:11434"


def test_llm_start_spawns_subprocess(setup_env, monkeypatch):
    """Wenn Ollama nicht laeuft aber das Binary da ist, wird gespawnt."""
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    from bewerbungs_assistent.services import llm_service
    import subprocess

    class FakeStatus:
        ollama_available = False
        ollama_endpoint = None
        available_models = []
        models_detail = []
        selected_model = None
        user_state = "off"
        error = None
    class FakeSvc:
        def get_status(self, force_refresh=False):
            return FakeStatus()
    monkeypatch.setattr(llm_service, "get_llm_service", lambda db: FakeSvc())

    spawned_args = []
    class FakeProc:
        pid = 12345
    def fake_popen(args, **kwargs):
        spawned_args.append(args)
        return FakeProc()
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    client = TestClient(app)
    r = client.post("/api/llm/start")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "starting"
    assert data["pid"] == 12345
    assert spawned_args == [["ollama", "serve"]]
