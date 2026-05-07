"""Tests fuer v1.7.0-beta.24 — Lokale-AI-Vertiefung + Quick-Wins.

#586 Profil-basiertes Auto-Aussortieren via match_job_to_skills
NEU  classify_email LLM-Task
#584 Test-Verbindung-Endpoint
#585 Auto-Detect-Banner (Frontend-Snapshot)
#587 firmen_recherche aktuelles firma-Feld
"""
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta24_")
    os.environ["BA_DATA_DIR"] = tmpdir
    os.environ.pop("PBP_LLM_MOCK", None)
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.services.llm_service as _llm_mod
    importlib.reload(_llm_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db, _srv_mod
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


def _result(raw):
    if isinstance(raw, dict) and set(raw.keys()) == {"result"}:
        return raw["result"]
    return raw


# ============= #586 match_job_to_skills LLM-Task ===============

def test_586_match_prompt_includes_profile_and_job(setup_env):
    """Prompt-Builder baut sinnvoll auf Profil + Stelle."""
    from bewerbungs_assistent.services.llm_service import _build_match_job_to_skills_prompt
    p = _build_match_job_to_skills_prompt({
        "profile_skills": ["Python", "PLM", "PRO.FILE"],
        "profile_position": "Senior PLM Architect",
        "profile_seniority": "Senior (15 Jahre)",
        "job_title": "Junior CAD-Konstrukteur",
        "job_company": "ACME GmbH",
        "job_description": "Wir suchen einen jungen Kollegen...",
    })
    assert "Senior PLM Architect" in p
    assert "Python, PLM, PRO.FILE" in p
    assert "Junior CAD-Konstrukteur" in p
    assert "ACME GmbH" in p
    assert "PASST" in p
    assert "PASST_NICHT" in p


def test_586_match_parser_passt_nicht():
    from bewerbungs_assistent.services.llm_service import _parse_match_job_to_skills
    out = _parse_match_job_to_skills(
        "PASST_NICHT | Senior-Profil passt nicht zu Junior-CAD-Stelle."
    )
    assert out["decision"] == "PASST_NICHT"
    assert "Senior-Profil" in out["reason"]


def test_586_match_parser_passt():
    from bewerbungs_assistent.services.llm_service import _parse_match_job_to_skills
    out = _parse_match_job_to_skills("PASST | thematisch und Stufe stimmen.")
    assert out["decision"] == "PASST"


def test_586_match_parser_handles_messy_output():
    from bewerbungs_assistent.services.llm_service import _parse_match_job_to_skills
    # Free-text Antwort ohne klare Struktur — Heuristik soll greifen
    out = _parse_match_job_to_skills("Nun, das passt nicht so richtig zum Profil.")
    assert out["decision"] == "PASST_NICHT"


def test_586_stellen_auto_aussortieren_no_ollama(setup_env):
    """Ohne Ollama liefert das Tool eine ehrliche Fehler-Meldung, nicht raten."""
    db, srv = setup_env
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("no ollama")):
        raw = _call(srv.mcp, "stellen_auto_aussortieren", {})
        r = _result(raw)
    assert "fehler" in r
    assert "Lokale AI" in r["fehler"] or "Ollama" in r.get("hinweis", "")


def test_586_stellen_auto_aussortieren_dry_run(setup_env):
    """Mit aktivem mock-LLM laeuft der Tool durch (dry_run=True ändert nichts)."""
    db, srv = setup_env
    db.set_profile_setting("llm_local_state", "active")
    db.save_jobs([
        {"hash": "h1", "title": "Senior PLM Architect", "company": "Cool",
         "source": "test", "score": 80, "url": "x"},
        {"hash": "h2", "title": "Technischer Zeichner", "company": "Old",
         "source": "test", "score": 20, "url": "y"},
    ])
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(db)
    svc._status.ollama_available = True
    svc._status.available_models = ["mock:7b"]
    svc._status.user_state = "active"
    svc._status.selected_model = "mock:7b"
    svc._status.last_check_at = 9999999999

    # Mock _ollama_generate: PASST fuer Senior, PASST_NICHT fuer Zeichner
    call_count = {"n": 0}
    def fake_gen(model, prompt, **kw):
        call_count["n"] += 1
        if "Senior PLM Architect" in prompt:
            return "PASST | thematisch perfekt."
        return "PASST_NICHT | Senior-Profil passt nicht zu Zeichner-Stelle."

    with patch.object(svc, "_ollama_generate", side_effect=fake_gen):
        # Patch get_llm_service, damit Tool unsere Mock-Instance nutzt
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=svc):
            raw = _call(srv.mcp, "stellen_auto_aussortieren",
                        {"dry_run": True, "max_stellen": 50})
            r = _result(raw)
    assert r.get("status") == "ok"
    assert r["geprueft"] == 2
    assert r["passt"] == 1
    assert r["passt_nicht"] == 1
    # dry_run → Stellen sind noch aktiv
    pid = db.get_active_profile_id()
    conn = db.connect()
    h2_active = conn.execute(
        "SELECT is_active FROM jobs WHERE hash LIKE ? AND profile_id=?",
        ("%h2%", pid)
    ).fetchone()
    assert h2_active["is_active"] == 1


# ============= NEU classify_email LLM-Task ===============

def test_classify_email_prompt_builds():
    from bewerbungs_assistent.services.llm_service import _build_classify_email_prompt
    p = _build_classify_email_prompt({
        "sender": "anna@acme.com",
        "subject": "Einladung zum Erstgespraech",
        "body": "Sehr geehrter Herr Mustermann, wir wuerden Sie gerne...",
    })
    assert "anna@acme.com" in p
    assert "Einladung zum Erstgespraech" in p
    assert "einladung_interview" in p
    assert "absage" in p


def test_classify_email_parser_known_category():
    from bewerbungs_assistent.services.llm_service import _parse_classify_email
    out = _parse_classify_email("einladung_interview")
    assert out["category"] == "einladung_interview"
    assert out["confidence"] >= 0.8


def test_classify_email_parser_unknown_falls_to_sonstiges():
    from bewerbungs_assistent.services.llm_service import _parse_classify_email
    out = _parse_classify_email("groovy")
    assert out["category"] == "sonstiges"


def test_classify_email_in_routing_table():
    from bewerbungs_assistent.services.llm_service import ROUTING_TABLE, TaskKind
    assert TaskKind.CLASSIFY_EMAIL in ROUTING_TABLE


# ============= #584 Test-Verbindung-Endpoint ===============

def test_584_test_connection_when_ollama_offline(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("nope")):
        r = client.post("/api/llm/test-connection")
    assert r.status_code == 200
    j = r.json()
    assert j["ollama_available"] is False
    assert j["test_roundtrip"]["skipped"] is True


def test_584_test_connection_full_diagnose(setup_env):
    db, _ = setup_env
    db.set_profile_setting("llm_local_state", "active")
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService(db)
    svc._status.ollama_available = True
    svc._status.available_models = ["mock:7b"]
    svc._status.user_state = "active"
    svc._status.selected_model = "mock:7b"
    svc._status.last_check_at = 9999999999

    with patch.object(svc, "_ollama_generate", return_value="lebenslauf"):
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=svc):
            from fastapi.testclient import TestClient
            from bewerbungs_assistent.dashboard import app
            client = TestClient(app)
            r = client.post("/api/llm/test-connection")
    j = r.json()
    assert j["ollama_available"] is True
    assert j["test_roundtrip"]["success"] is True
    assert j["test_roundtrip"]["backend"] == "local"
    assert j["test_roundtrip"]["result_payload"]["category"] == "lebenslauf"


# ============= #585 Auto-Detect-Banner Frontend ===============

def test_585_dashboard_has_auto_detect_banner_component():
    src = (PROJECT_ROOT / "frontend" / "src" / "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
    assert "LocalAiAutoDetectBanner" in src
    assert "/api/llm/status" in src
    assert "ollama_available" in src
    assert "pbp_local_ai_banner_dismissed_until" in src


# ============= #587 firmen_recherche bevorzugt aktuelles Feld ===============

def test_587_firmen_recherche_uses_application_first():
    src = (PROJECT_ROOT / "frontend" / "src" / "pages" / "ApplicationsPage.jsx").read_text(encoding="utf-8")
    # Endkunde sollte priorisiert sein
    assert "app.endkunde" in src
    # Fallback-Reihenfolge: endkunde -> application.company -> job.company
    # (Pruefen dass app.endkunde VOR job.company kommt)
    pos_endkunde = src.find("app.endkunde")
    pos_job_company = src.find("job?.company")
    assert pos_endkunde > 0 and pos_job_company > 0
    assert pos_endkunde < pos_job_company


# ============= MCP-Registry: 1 neues Tool ===============

def test_mcp_registry_includes_new_tool():
    """stellen_auto_aussortieren ist neu registriert."""
    src = (PROJECT_ROOT / "tests" / "test_mcp_registry.py").read_text(encoding="utf-8")
    # Wir aktualisieren den Test-Count zusammen mit dem Issue, dieser Test
    # verifiziert nur dass das neue Tool in der EXPECTED_TOOL_NAMES auftaucht
    # ODER dass test_mcp_registry mit der neuen Tool-Anzahl zurechtkommt.
    # Wenn EXPECTED_TOOL_NAMES nicht aktualisiert wurde: Reminder-Test.
    if "stellen_auto_aussortieren" not in src:
        pytest.fail(
            "EXPECTED_TOOL_NAMES in tests/test_mcp_registry.py muss um "
            "'stellen_auto_aussortieren' ergaenzt werden."
        )
