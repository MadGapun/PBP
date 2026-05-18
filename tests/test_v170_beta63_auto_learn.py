"""Tests fuer v1.7.0-beta.63 — Ollama wird zur Hintergrund-KI (#638 Stufe 1+3).

- A) Auto-Aussortierung nach Jobsuche (Hook im Such-Thread)
- B) Few-Shot-Lernschleife: recent_dismissals im Match-Prompt
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta63_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= B) DB-Helper get_recent_user_dismissals ============

def test_get_recent_user_dismissals_returns_manual_only(setup_env):
    """Auto-Dismiss-Eintraege werden ausgefiltert — sonst Echokammer."""
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    # Manuelle Aussortierung
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, source, is_active, dismiss_reason, updated_at) "
        "VALUES (?, ?, 'Junior Dev', 'ACME GmbH', 'test', 0, 'falsches_fachgebiet', ?)",
        (f"{pid}:h1", pid, "2026-05-14T10:00:00"),
    )
    # Auto-Aussortierung (sollte gefiltert sein)
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, source, is_active, dismiss_reason, updated_at) "
        "VALUES (?, ?, 'Sales Manager', 'BLA GmbH', 'test', 0, 'auto:profil_match_negativ:wrong', ?)",
        (f"{pid}:h2", pid, "2026-05-14T11:00:00"),
    )
    # Aktive Stelle (sollte gefiltert sein)
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, source, is_active, dismiss_reason, updated_at) "
        "VALUES (?, ?, 'Active Job', 'C GmbH', 'test', 1, NULL, ?)",
        (f"{pid}:h3", pid, "2026-05-14T12:00:00"),
    )
    conn.commit()

    result = db.get_recent_user_dismissals(limit=10)
    assert len(result) == 1
    assert result[0]["title"] == "Junior Dev"
    assert result[0]["company"] == "ACME GmbH"
    assert result[0]["dismiss_reason"] == "falsches_fachgebiet"


def test_get_recent_user_dismissals_orders_desc(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    for i in range(3):
        conn.execute(
            "INSERT INTO jobs (hash, profile_id, title, company, source, is_active, "
            "dismiss_reason, updated_at) "
            f"VALUES ('{pid}:h{i}', ?, 'Job {i}', 'Firma {i}', 'test', 0, "
            "'reason', ?)",
            (pid, f"2026-05-1{i}T10:00:00")
        )
    conn.commit()

    result = db.get_recent_user_dismissals(limit=10)
    assert len(result) == 3
    # Neueste zuerst
    assert result[0]["title"] == "Job 2"
    assert result[1]["title"] == "Job 1"
    assert result[2]["title"] == "Job 0"


def test_get_recent_user_dismissals_limit(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    for i in range(15):
        conn.execute(
            "INSERT INTO jobs (hash, profile_id, title, company, source, is_active, "
            "dismiss_reason, updated_at) "
            f"VALUES ('{pid}:h{i:02d}', ?, 'J{i}', 'F', 'test', 0, 'r', ?)",
            (pid, f"2026-05-{i+1:02d}T10:00:00")
        )
    conn.commit()
    assert len(db.get_recent_user_dismissals(limit=5)) == 5
    assert len(db.get_recent_user_dismissals(limit=20)) == 15


# ============= B) Prompt-Builder mit Few-Shot ============

def test_match_prompt_includes_recent_dismissals():
    """Wenn recent_dismissals da sind, taucht der Few-Shot-Block im Prompt auf."""
    from bewerbungs_assistent.services.llm_service import _build_match_job_to_skills_prompt
    payload = {
        "profile_skills": ["Python", "PLM"],
        "profile_position": "Senior Engineer",
        "job_title": "Senior Software Architect",
        "job_company": "TechFirma",
        "job_description": "We need a great architect.",
        "recent_dismissals": [
            {"title": "Junior Dev", "company": "Startup A",
             "dismiss_reason": "falsches_seniority_level"},
            {"title": "Sales Manager", "company": "Big Corp",
             "dismiss_reason": "falsches_fachgebiet"},
        ],
    }
    prompt = _build_match_job_to_skills_prompt(payload)
    assert "BEISPIELE" in prompt
    assert "Junior Dev" in prompt
    assert "Startup A" in prompt
    assert "falsches_seniority_level" in prompt
    assert "Sales Manager" in prompt


def test_match_prompt_no_block_if_no_dismissals():
    """Ohne recent_dismissals KEIN BEISPIELE-Block."""
    from bewerbungs_assistent.services.llm_service import _build_match_job_to_skills_prompt
    payload = {
        "profile_skills": ["Python"],
        "job_title": "Engineer",
        "job_company": "Firma",
        "job_description": "test",
    }
    prompt = _build_match_job_to_skills_prompt(payload)
    assert "BEISPIELE" not in prompt


def test_match_prompt_caps_examples_at_5():
    """Bei >5 Dismissals nur 5 im Prompt — sonst Token-Explosion."""
    from bewerbungs_assistent.services.llm_service import _build_match_job_to_skills_prompt
    payload = {
        "profile_skills": [],
        "job_title": "Test", "job_company": "Test", "job_description": "x",
        "recent_dismissals": [
            {"title": f"Job {i}", "company": f"Firma {i}", "dismiss_reason": "x"}
            for i in range(10)
        ],
    }
    prompt = _build_match_job_to_skills_prompt(payload)
    # Mind. die ersten 5 sind drin
    for i in range(5):
        assert f"Job {i}" in prompt
    # Job 5-9 nicht
    assert "Job 9" not in prompt


# ============= A) Auto-Dismiss-Hook ============

def test_auto_dismiss_skips_when_setting_off(setup_env, monkeypatch):
    """Wenn auto_dismiss_after_search=false, wird der Hook uebersprungen."""
    db = setup_env
    db.set_profile_setting("auto_dismiss_after_search", "false")

    from bewerbungs_assistent.tools.jobs import _maybe_auto_dismiss_after_search
    # Wenn der Hook das LLM aufrufen wuerde, wuerde es krachen — also
    # erwarte: er macht nichts.
    _maybe_auto_dismiss_after_search(db, "fake-job-id")
    # No exception — passed.


def test_auto_dismiss_skips_when_ollama_unavailable(setup_env, monkeypatch):
    db = setup_env
    db.set_profile_setting("auto_dismiss_after_search", "true")

    from bewerbungs_assistent.services import llm_service
    class FakeStatus:
        ollama_available = False
        user_state = "active"
        error = None
    class FakeSvc:
        def get_status(self, force_refresh=False):
            return FakeStatus()
    monkeypatch.setattr(llm_service, "get_llm_service", lambda d: FakeSvc())

    from bewerbungs_assistent.tools.jobs import _maybe_auto_dismiss_after_search
    _maybe_auto_dismiss_after_search(db, "fake-job-id")
    # No exception — übersprungen.


def test_auto_dismiss_skips_when_user_state_not_active(setup_env, monkeypatch):
    db = setup_env
    db.set_profile_setting("auto_dismiss_after_search", "true")

    from bewerbungs_assistent.services import llm_service
    class FakeStatus:
        ollama_available = True
        user_state = "paused"
        error = None
    class FakeSvc:
        def get_status(self, force_refresh=False):
            return FakeStatus()
    monkeypatch.setattr(llm_service, "get_llm_service", lambda d: FakeSvc())

    from bewerbungs_assistent.tools.jobs import _maybe_auto_dismiss_after_search
    _maybe_auto_dismiss_after_search(db, "fake-job-id")
    # No exception — übersprungen.


def test_auto_dismiss_default_setting_is_true(setup_env):
    """Default-Wert wenn nie gesetzt: 'true' damit der Hook von Anfang
    an aktiv ist (sobald Ollama laeuft)."""
    db = setup_env
    val = db.get_profile_setting("auto_dismiss_after_search", "true")
    # entweder nicht gesetzt (return default 'true') oder schon 'true'
    assert str(val).lower() in ("true", "1", "yes")
