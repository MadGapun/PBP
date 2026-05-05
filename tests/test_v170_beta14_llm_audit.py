"""LLM-Audit fuer v1.7.0-beta.14 — schliesst die Test-Luecken im LLM-Pfad
die in beta.1..beta.2 nur als Mock-Tests vorhanden waren.

Drei Test-Schichten:
1. HTTP-API-Endpunkte (`/api/llm/*`) — keine wurden bisher per TestClient getestet.
2. _ollama_generate / _check_ollama / trigger_pull — der echte HTTP-Pfad
   mit gemocktem urllib.request.
3. Routing-Verhalten bei realistischen User-States (off/paused/active +
   Ollama-Verfuegbarkeit) — Ergaenzung zu den bestehenden Mock-Tests.
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta14_llm_")
    os.environ["BA_DATA_DIR"] = tmpdir
    # WICHTIG: PBP_LLM_MOCK explizit aus, damit wir den echten Pfad testen
    os.environ.pop("PBP_LLM_MOCK", None)
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.services.llm_service as _llm_mod
    importlib.reload(_llm_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= HTTP-API-Endpoints ===============

def test_llm_status_endpoint_when_ollama_offline(setup_env):
    """Wenn Ollama nicht laeuft, liefert /status ui_state=not_installed."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # urllib.urlopen wirft URLError → Ollama nicht erreichbar
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("connection refused")):
        # Cache invalidieren
        from bewerbungs_assistent.services.llm_service import get_llm_service
        get_llm_service(db).get_status(force_refresh=True)
        r = client.get("/api/llm/status")
    assert r.status_code == 200
    j = r.json()
    assert j["ui_state"] == "not_installed"
    assert j["ollama_available"] is False


def test_llm_state_endpoint_validates_input(setup_env):
    """`/api/llm/state` lehnt ungueltige States ab."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # Mock: Ollama nicht da, damit der force_refresh nicht blockiert
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("ollama down")):
        r = client.put("/api/llm/state", json={"state": "schmuh"})
    assert r.status_code == 400
    assert "off" in r.json()["error"]


def test_llm_state_endpoint_accepts_valid_states(setup_env):
    """`/api/llm/state` akzeptiert off/paused/active und persistiert."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("ollama down")):
        for state in ("off", "paused", "active"):
            r = client.put("/api/llm/state", json={"state": state})
            assert r.status_code == 200, f"state={state} failed: {r.text}"
            assert r.json()["state"] == state
    # Persistiert in DB
    assert db.get_profile_setting("llm_local_state", "") == "active"


def test_llm_model_endpoint_validates_input(setup_env):
    """`/api/llm/model` braucht ein nicht-leeres Modell."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("ollama down")):
        r = client.put("/api/llm/model", json={"model": ""})
    assert r.status_code == 400


def test_llm_model_endpoint_persists(setup_env):
    """`/api/llm/model` speichert den Modellnamen."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("ollama down")):
        r = client.put("/api/llm/model", json={"model": "llama3.2:3b"})
    assert r.status_code == 200
    assert db.get_profile_setting("llm_local_model", "") == "llama3.2:3b"


def test_llm_pull_endpoint_returns_502_on_ollama_error(setup_env):
    """`/api/llm/pull` liefert 502 wenn Ollama nicht antwortet."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("ollama down")):
        r = client.post("/api/llm/pull", json={"model": "llama3.2:3b"})
    assert r.status_code == 502
    assert r.json()["status"] == "error"


def test_llm_pull_endpoint_validates_model(setup_env):
    """`/api/llm/pull` braucht model-Param."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/llm/pull", json={})
    assert r.status_code == 400


def test_llm_recommended_models_endpoint(setup_env):
    """`/api/llm/recommended-models` liefert kuratierte Liste."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/llm/recommended-models")
    assert r.status_code == 200
    j = r.json()
    assert "models" in j
    assert len(j["models"]) >= 1
    # Mindestens eines soll llama3.2 sein (Standard-Empfehlung)
    assert any("llama" in m.get("id", "").lower() for m in j["models"])


# ============= _check_ollama (echter HTTP-Pfad) ===============

def _mock_urlopen_response(json_data):
    """Erzeugt einen MagicMock der wie urllib.request.urlopen-Result wirkt."""
    import json as _json
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = _json.dumps(json_data).encode("utf-8")
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_check_ollama_success_with_models(setup_env):
    """Wenn Ollama OK + Modelle: ollama_available=True, available_models gefuellt."""
    db, _ = setup_env
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(db)
    fake_resp = _mock_urlopen_response({
        "models": [{"name": "llama3.2:3b"}, {"name": "qwen2.5:7b"}]
    })
    with patch("urllib.request.urlopen", return_value=fake_resp):
        s = svc.get_status(force_refresh=True)
    assert s.ollama_available is True
    assert "llama3.2:3b" in s.available_models
    assert "qwen2.5:7b" in s.available_models


def test_check_ollama_success_no_models(setup_env):
    """Ollama da, aber keine Modelle installiert → ui_state=no_model."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    fake_resp = _mock_urlopen_response({"models": []})
    with patch("urllib.request.urlopen", return_value=fake_resp):
        from bewerbungs_assistent.services.llm_service import get_llm_service
        get_llm_service(db).get_status(force_refresh=True)
        r = client.get("/api/llm/status")
    assert r.json()["ui_state"] == "no_model"


def test_check_ollama_handles_timeout(setup_env):
    """Bei Timeout: ollama_available=False, error-Feld gefuellt."""
    db, _ = setup_env
    import socket
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(db)
    with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
        s = svc.get_status(force_refresh=True)
    assert s.ollama_available is False
    assert s.error is not None
    assert "timed out" in s.error.lower()


# ============= _ollama_generate (echter HTTP-Pfad) ===============

def test_ollama_generate_returns_response_field(setup_env):
    """`_ollama_generate` extrahiert das `response`-Feld der Ollama-Antwort."""
    db, _ = setup_env
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(db)
    svc._status.ollama_endpoint = "http://localhost:11434"
    fake_resp = _mock_urlopen_response({"response": "lebenslauf", "done": True})
    with patch("urllib.request.urlopen", return_value=fake_resp):
        out = svc._ollama_generate("llama3.2:3b", "test prompt")
    assert out == "lebenslauf"


def test_ollama_generate_handles_empty_response(setup_env):
    """Wenn Ollama leeres response liefert, kommt leerer String zurueck."""
    db, _ = setup_env
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(db)
    fake_resp = _mock_urlopen_response({"response": "", "done": True})
    with patch("urllib.request.urlopen", return_value=fake_resp):
        out = svc._ollama_generate("llama3.2:3b", "x")
    assert out == ""


# ============= run() End-to-End mit gemocktem Ollama ===============

def test_run_classify_document_full_pipeline(setup_env):
    """Realistischer End-to-End-Pfad: User aktiviert lokale AI, Ollama
    laeuft, classify_document landet beim lokalen Backend, Antwort wird
    geparst und ist in den erwarteten Kategorien."""
    db, _ = setup_env
    db.set_profile_setting("llm_local_state", "active")
    db.set_profile_setting("llm_local_model", "llama3.2:3b")

    from bewerbungs_assistent.services.llm_service import LLMService, TaskKind, Backend
    svc = LLMService(db)

    # Erst: get_status mit gemocktem Ollama → available
    fake_status = _mock_urlopen_response({"models": [{"name": "llama3.2:3b"}]})
    # Dann: _ollama_generate mit "lebenslauf" als Antwort
    fake_generate = _mock_urlopen_response({"response": "lebenslauf"})

    call_count = {"n": 0}
    def side_effect(req, **kw):
        # Erster Call ist /api/tags, zweiter /api/generate
        call_count["n"] += 1
        return fake_status if call_count["n"] == 1 else fake_generate

    with patch("urllib.request.urlopen", side_effect=side_effect):
        result = svc.run(TaskKind.CLASSIFY_DOCUMENT, {
            "text": "Lebenslauf von Markus B. ...",
            "filename": "cv.pdf",
        })
    assert result.backend == Backend.LOCAL
    assert result.success is True
    assert result.payload["category"] == "lebenslauf"


def test_run_falls_back_to_claude_when_ollama_dies_mid_call(setup_env):
    """Wenn _ollama_generate eine Exception wirft, faellt run() auf
    CLAUDE zurueck statt zu crashen."""
    db, _ = setup_env
    db.set_profile_setting("llm_local_state", "active")
    db.set_profile_setting("llm_local_model", "llama3.2:3b")

    from bewerbungs_assistent.services.llm_service import LLMService, TaskKind, Backend
    svc = LLMService(db)

    # Status sagt "Ollama da, Modell da" → select_backend wird LOCAL waehlen
    svc._status.ollama_available = True
    svc._status.available_models = ["llama3.2:3b"]
    svc._status.user_state = "active"
    svc._status.selected_model = "llama3.2:3b"
    svc._status.last_check_at = 9999999999  # Cache-Hit erzwingen

    # Aber _ollama_generate crasht
    with patch.object(svc, "_ollama_generate", side_effect=ConnectionResetError("oops")):
        result = svc.run(TaskKind.CLASSIFY_DOCUMENT, {"text": "x"})
    # Fallback auf CLAUDE
    assert result.backend == Backend.CLAUDE
    assert result.success is False
    assert "Claude" in (result.fallback_message or "")


def test_run_paused_state_blocks_local_even_with_ollama(setup_env):
    """User-State=paused → LOCAL nicht waehlbar, auch wenn Ollama da ist."""
    db, _ = setup_env
    db.set_profile_setting("llm_local_state", "paused")

    from bewerbungs_assistent.services.llm_service import LLMService, TaskKind, Backend
    svc = LLMService(db)
    svc._status.ollama_available = True
    svc._status.available_models = ["llama3.2:3b"]
    svc._status.user_state = "paused"
    svc._status.last_check_at = 9999999999

    backend = svc.select_backend(TaskKind.CLASSIFY_DOCUMENT)
    assert backend == Backend.CLAUDE  # Fallback auch im paused-State


# ============= trigger_pull (echter Pfad) ===============

def test_trigger_pull_success(setup_env):
    """Erfolgreicher Modell-Download liefert status=success."""
    db, _ = setup_env
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(db)
    fake_resp = _mock_urlopen_response({"status": "success"})
    with patch("urllib.request.urlopen", return_value=fake_resp):
        result = svc.trigger_pull("llama3.2:3b")
    assert result["status"] == "success"
    assert result["model"] == "llama3.2:3b"


def test_trigger_pull_returns_error_on_failure(setup_env):
    """Bei Netzwerk-Fehler liefert trigger_pull error-Status (kein crash)."""
    db, _ = setup_env
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(db)
    with patch("urllib.request.urlopen",
               side_effect=ConnectionRefusedError("ollama not running")):
        result = svc.trigger_pull("llama3.2:3b")
    assert result["status"] == "error"
    assert "ollama" in result["error"].lower() or "refused" in result["error"].lower()
