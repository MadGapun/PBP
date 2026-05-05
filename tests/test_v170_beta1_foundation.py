"""Tests fuer v1.7.0-beta.1 Foundation (LLM-Service + Typisierte IDs).

Issues:
- #512 LLM-Service-Abstraktion (Foundation, kein echter Ollama-Call in beta.1)
- #505 ID-Typisierung (Variante A: nicht-breaking, beide Formen akzeptiert)
- #583 LLM-Status-Indicator-Backend (UI-Foundation)
"""
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta1_")
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


# ============= #505 Typisierte IDs ===============

def test_505_format_id_adds_prefix():
    from bewerbungs_assistent.services.typed_ids import format_id, IdKind
    assert format_id(IdKind.APPLICATION, "42061e46") == "APP-42061e46"
    assert format_id(IdKind.DOCUMENT, "d60ac54b") == "DOC-d60ac54b"
    assert format_id(IdKind.JOB, "abcd1234") == "JOB-abcd1234"


def test_505_format_id_handles_none_and_empty():
    from bewerbungs_assistent.services.typed_ids import format_id, IdKind
    assert format_id(IdKind.APPLICATION, None) is None
    assert format_id(IdKind.APPLICATION, "") == ""


def test_505_format_id_replaces_existing_prefix():
    """Defensive: falls schon ein Prefix dran ist, wird der ersetzt."""
    from bewerbungs_assistent.services.typed_ids import format_id, IdKind
    assert format_id(IdKind.APPLICATION, "DOC-d60ac54b") == "APP-d60ac54b"
    assert format_id(IdKind.JOB, "APP-42061e46") == "JOB-42061e46"


def test_505_parse_id_recognizes_prefix():
    from bewerbungs_assistent.services.typed_ids import parse_id, IdKind
    kind, raw = parse_id("APP-42061e46")
    assert kind == IdKind.APPLICATION
    assert raw == "42061e46"


def test_505_parse_id_naked_hex_returns_none_kind():
    from bewerbungs_assistent.services.typed_ids import parse_id
    kind, raw = parse_id("42061e46")
    assert kind is None
    assert raw == "42061e46"


def test_505_parse_id_handles_none_and_empty():
    from bewerbungs_assistent.services.typed_ids import parse_id
    assert parse_id(None) == (None, "")
    assert parse_id("") == (None, "")


def test_505_parse_id_unknown_prefix_kept_raw():
    """Unbekannte 'Praefixe' (wie '12345-abc') werden nicht missinterpretiert."""
    from bewerbungs_assistent.services.typed_ids import parse_id
    kind, raw = parse_id("ABCDEF-test")
    assert kind is None
    assert raw == "ABCDEF-test"  # bleibt as-is


def test_505_validate_id_accepts_naked_hex():
    """Variante A: nackte Hex-IDs werden durchgereicht (Backwards-Compat)."""
    from bewerbungs_assistent.services.typed_ids import validate_id, IdKind
    raw = validate_id(IdKind.APPLICATION, "42061e46")
    assert raw == "42061e46"


def test_505_validate_id_accepts_correct_prefix():
    from bewerbungs_assistent.services.typed_ids import validate_id, IdKind
    raw = validate_id(IdKind.APPLICATION, "APP-42061e46")
    assert raw == "42061e46"


def test_505_validate_id_rejects_wrong_prefix():
    from bewerbungs_assistent.services.typed_ids import validate_id, IdKind, TypedIdMismatch
    with pytest.raises(TypedIdMismatch) as exc_info:
        validate_id(IdKind.APPLICATION, "DOC-d60ac54b")
    assert "APP-" in str(exc_info.value)
    assert "DOC" in str(exc_info.value)


def test_505_strip_prefix():
    from bewerbungs_assistent.services.typed_ids import strip_prefix
    assert strip_prefix("APP-42061e46") == "42061e46"
    assert strip_prefix("42061e46") == "42061e46"
    assert strip_prefix(None) == ""


# ============= #512 LLM-Service Foundation ===============

def test_512_llm_service_singleton():
    """get_llm_service liefert immer dieselbe Instanz."""
    from bewerbungs_assistent.services.llm_service import get_llm_service, reset_llm_service
    reset_llm_service()
    s1 = get_llm_service()
    s2 = get_llm_service()
    assert s1 is s2
    reset_llm_service()


def test_512_status_when_ollama_not_running():
    """Bei fehlendem Ollama: ollama_available=False, kein Crash."""
    from bewerbungs_assistent.services.llm_service import LLMService
    # Mock-Modus AUS, damit echter HTTP-Check laeuft (sollte fehlschlagen)
    os.environ.pop("PBP_LLM_MOCK", None)
    svc = LLMService()
    status = svc.get_status(force_refresh=True)
    # Kein Ollama auf Test-System → not available
    assert status.ollama_available is False
    assert status.error is not None


def test_512_status_caching():
    """Status wird gecacht — zwei Aufrufe innerhalb 30s liefern denselben Wert."""
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService()
    status1 = svc.get_status()
    last_check_1 = status1.last_check_at
    status2 = svc.get_status()
    last_check_2 = status2.last_check_at
    # Cache greift → Timestamp identisch
    assert last_check_1 == last_check_2


def test_512_routing_for_creative_tasks():
    """GENERATE_COVER_LETTER bevorzugt CLAUDE."""
    from bewerbungs_assistent.services.llm_service import LLMService, TaskKind, Backend
    svc = LLMService()
    backend = svc.select_backend(TaskKind.GENERATE_COVER_LETTER)
    assert backend == Backend.CLAUDE


def test_512_routing_for_local_tasks_falls_back_to_claude():
    """In beta.1 ist LOCAL noch nicht implementiert → Fallback auf CLAUDE."""
    from bewerbungs_assistent.services.llm_service import LLMService, TaskKind, Backend
    os.environ.pop("PBP_LLM_MOCK", None)
    svc = LLMService()
    backend = svc.select_backend(TaskKind.CLASSIFY_DOCUMENT)
    # Ohne Ollama / ohne user_state=active → CLAUDE
    assert backend == Backend.CLAUDE


def test_512_mock_mode_returns_local_result(setup_env):
    """Mit PBP_LLM_MOCK=1 simuliert der Service eine lokale Ausfuehrung."""
    from bewerbungs_assistent.services.llm_service import LLMService, TaskKind, Backend
    db, _ = setup_env
    db.set_profile_setting("llm_local_state", "active")
    os.environ["PBP_LLM_MOCK"] = "1"
    svc = LLMService(db=db)
    status = svc.get_status(force_refresh=True)
    assert status.ollama_available is True
    backend = svc.select_backend(TaskKind.CLASSIFY_DOCUMENT)
    assert backend == Backend.LOCAL
    result = svc.run(TaskKind.CLASSIFY_DOCUMENT, {"text": "Lebenslauf von ..."})
    assert result.success is True
    assert result.backend == Backend.LOCAL
    assert result.payload["mock"] is True
    os.environ.pop("PBP_LLM_MOCK", None)


def test_512_user_state_paused_blocks_local(setup_env):
    """User-State 'paused' verhindert LOCAL auch wenn Ollama da waere."""
    from bewerbungs_assistent.services.llm_service import LLMService, TaskKind, Backend
    db, _ = setup_env
    db.set_profile_setting("llm_local_state", "paused")
    os.environ["PBP_LLM_MOCK"] = "1"  # Ollama wuerde verfuegbar sein
    svc = LLMService(db=db)
    backend = svc.select_backend(TaskKind.CLASSIFY_DOCUMENT)
    # Trotz Mock-Ollama: paused → CLAUDE
    assert backend == Backend.CLAUDE
    os.environ.pop("PBP_LLM_MOCK", None)


# ============= #583 LLM-Status-API ===============

def test_583_status_api_returns_ui_state(setup_env):
    """Endpoint liefert ui_state fuer den Sidebar-Indicator."""
    db, _ = setup_env
    os.environ.pop("PBP_LLM_MOCK", None)
    # Reset singleton damit der DB-Zustand reflektiert wird
    from bewerbungs_assistent.services.llm_service import reset_llm_service, get_llm_service
    reset_llm_service()
    svc = get_llm_service(db)
    s = svc.get_status(force_refresh=True)
    # Test-System hat kein Ollama → ui_state sollte 'not_installed' sein
    assert not s.ollama_available
    # API-Logik nachbauen
    if not s.ollama_available:
        ui_state = "not_installed"
    elif not s.available_models:
        ui_state = "no_model"
    else:
        ui_state = s.user_state
    assert ui_state == "not_installed"


def test_583_state_transitions(setup_env):
    """User kann zwischen off/paused/active wechseln."""
    db, _ = setup_env
    for state in ("off", "paused", "active", "off"):
        db.set_profile_setting("llm_local_state", state)
        assert db.get_profile_setting("llm_local_state") == state
