"""Tests fuer v1.7.0-beta.62 — Ollama Cold-Start-Fix (#638).

- keep_alive im generate-Payload
- warmup() liefert {warm, model, duration_sec}
- /api/llm/warmup endpoint
- /api/llm/status?refresh=1 erzwingt force_refresh
- Pre-Warmup in stellen_auto_aussortieren
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta62_")
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


# ============= keep_alive in generate ============

def test_ollama_generate_uses_keep_alive(setup_env):
    """_ollama_generate muss keep_alive=60m im JSON-Body senden."""
    from bewerbungs_assistent.services.llm_service import LLMService
    import urllib.request

    svc = LLMService(setup_env)
    svc._status.ollama_endpoint = "http://fake:11434"

    captured_body = []
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self):
            return json.dumps({"response": "ok"}).encode()
    def fake_urlopen(req, timeout=None):
        captured_body.append(req.data)
        return FakeResp()

    with patch.object(urllib.request, "urlopen", fake_urlopen):
        svc._ollama_generate("qwen2.5:7b", "prompt")

    assert captured_body, "urlopen wurde nicht aufgerufen"
    payload = json.loads(captured_body[0])
    assert payload.get("keep_alive") == "60m"


# ============= warmup() ============

def test_warmup_returns_warm_status(setup_env):
    from bewerbungs_assistent.services.llm_service import LLMService
    import urllib.request

    svc = LLMService(setup_env)
    svc._status.ollama_available = True
    svc._status.ollama_endpoint = "http://fake:11434"
    svc._status.selected_model = "qwen2.5:7b"
    svc._status.last_check_at = 9_999_999_999  # Cache nie ablaufen lassen

    captured = []
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'{"response":"x"}'
    def fake_urlopen(req, timeout=None):
        captured.append(req.data)
        return FakeResp()

    with patch.object(urllib.request, "urlopen", fake_urlopen):
        r = svc.warmup()

    assert r["status"] == "warm"
    assert r["model"] == "qwen2.5:7b"
    assert "duration_sec" in r
    payload = json.loads(captured[0])
    assert payload["keep_alive"] == "60m"
    assert payload["options"]["num_predict"] == 1


def test_warmup_no_ollama(setup_env):
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(setup_env)
    svc._status.ollama_available = False
    svc._status.last_check_at = 9_999_999_999
    r = svc.warmup()
    assert r["status"] == "no_ollama"


def test_warmup_no_model_selected(setup_env):
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(setup_env)
    svc._status.ollama_available = True
    svc._status.ollama_endpoint = "http://fake:11434"
    svc._status.selected_model = None
    svc._status.last_check_at = 9_999_999_999
    r = svc.warmup()
    assert r["status"] == "no_model"


def test_warmup_handles_exception(setup_env):
    from bewerbungs_assistent.services.llm_service import LLMService
    import urllib.request
    svc = LLMService(setup_env)
    svc._status.ollama_available = True
    svc._status.ollama_endpoint = "http://fake:11434"
    svc._status.selected_model = "test"
    svc._status.last_check_at = 9_999_999_999

    def boom(*a, **kw): raise ConnectionError("network down")
    with patch.object(urllib.request, "urlopen", boom):
        r = svc.warmup()
    assert r["status"] == "error"
    assert "network down" in r["error"]


# ============= API endpoints ============

def test_api_llm_warmup_endpoint(setup_env, monkeypatch):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    from bewerbungs_assistent.services import llm_service

    class FakeSvc:
        def warmup(self, model=None):
            return {"status": "warm", "model": "fake", "duration_sec": 0.05}
    monkeypatch.setattr(llm_service, "get_llm_service", lambda db: FakeSvc())

    client = TestClient(app)
    r = client.post("/api/llm/warmup")
    assert r.status_code == 200
    assert r.json()["status"] == "warm"


def test_api_llm_status_force_refresh_param(setup_env, monkeypatch):
    """/api/llm/status?refresh=1 propagiert force_refresh=True an Service."""
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    from bewerbungs_assistent.services import llm_service

    captured = []
    class FakeStatus:
        ollama_available = True
        ollama_endpoint = "http://x"
        available_models = []
        models_detail = []
        selected_model = None
        user_state = "active"
        error = None
    class FakeSvc:
        def get_status(self, force_refresh=False):
            captured.append(force_refresh)
            return FakeStatus()
    monkeypatch.setattr(llm_service, "get_llm_service", lambda db: FakeSvc())

    client = TestClient(app)
    client.get("/api/llm/status?refresh=1")
    client.get("/api/llm/status")
    assert captured[0] is True, "refresh=1 sollte force_refresh=True triggern"
    assert captured[1] is False, "ohne refresh sollte force_refresh=False sein"


# ============= heartbeat module: warmup loop ============

def test_start_ollama_warmup_loop_idempotent(setup_env):
    """Mehrfach-Aufruf startet nicht mehrere Threads."""
    from bewerbungs_assistent import heartbeat
    heartbeat.start_ollama_warmup_loop(setup_env)
    t1 = heartbeat._ollama_warmup_thread
    heartbeat.start_ollama_warmup_loop(setup_env)
    t2 = heartbeat._ollama_warmup_thread
    assert t1 is t2
    assert t1 and t1.is_alive()
