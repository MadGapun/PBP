"""Tests fuer v1.7.0-beta.54 — kontakte_aus_bewerbungen_extrahieren (#605)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta54_")
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


def _seed_apps_with_notes(db, n=3, with_event_notes=False):
    """Legt n Bewerbungen mit Notes an, optional Events."""
    aids = []
    for i in range(n):
        aid = db.add_application({
            "title": f"Senior Engineer {i}",
            "company": f"Firma{i}",
            "notes": f"Recruiter Person{i} hat sich gemeldet, Telefon 0151234567{i}.",
            "ansprechpartner": f"Person{i}",
            "kontakt_email": f"recruiter{i}@firma.de",
            "status": "beworben",
            "applied_at": "2026-05-01",
        })
        aids.append(aid)
        if with_event_notes:
            db.add_application_event(
                aid, "interview",
                f"Telefon mit Hiring-Manager Test{i} (HR), Termin am Freitag."
            )
    return aids


def _build_mcp(db):
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.kontakte import register
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


def _mock_llm_returning_contacts(contacts: list[dict]):
    """Hilfs-Funktion: erzeugt einen LLM-Service-Mock der die uebergebenen
    Kontakte zurueckliefert."""
    fake_status = MagicMock()
    fake_status.ollama_available = True
    fake_status.user_state = "active"
    fake_status.available_models = ["test-model"]

    fake_result = MagicMock()
    fake_result.success = True
    fake_result.payload = {"contacts": contacts}

    fake_svc = MagicMock()
    fake_svc.get_status.return_value = fake_status
    fake_svc.run.return_value = fake_result
    return fake_svc


# ============= Skip-Pfade ============

def test_skip_when_ai_not_available(setup_env):
    db = setup_env
    fake_status = MagicMock()
    fake_status.ollama_available = False
    fake_svc = MagicMock()
    fake_svc.get_status.return_value = fake_status
    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        mcp = _build_mcp(db)
        out = _call(mcp, "kontakte_aus_bewerbungen_extrahieren", {})
    assert "fehler" in out
    assert "Ollama" in out["hinweis"]


def test_skip_when_ai_paused(setup_env):
    db = setup_env
    fake_status = MagicMock()
    fake_status.ollama_available = True
    fake_status.user_state = "paused"
    fake_status.available_models = ["m"]
    fake_svc = MagicMock()
    fake_svc.get_status.return_value = fake_status
    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        mcp = _build_mcp(db)
        out = _call(mcp, "kontakte_aus_bewerbungen_extrahieren", {})
    assert "fehler" in out
    assert "paused" in out["fehler"] or "active" in out["hinweis"]


# ============= Dry-Run + Apply ============

def test_dry_run_returns_candidates_no_writes(setup_env):
    db = setup_env
    _seed_apps_with_notes(db, n=2)
    fake_svc = _mock_llm_returning_contacts([
        {"name": "Test Person", "email": "test@firma.de",
         "telefon": "0151234567", "rolle": "Recruiter",
         "kategorie": "recruiter", "confidence": 0.9},
    ])
    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        mcp = _build_mcp(db)
        out = _call(mcp, "kontakte_aus_bewerbungen_extrahieren",
                     {"dry_run": True, "max_bewerbungen": 5})
    assert out["status"] == "vorschau"
    assert out["geprueft"] >= 1
    assert out["kandidaten"] >= 1
    assert out["extrahiert"] == 0  # Dry-run schreibt nicht
    # Keine Kontakte in DB
    contacts = db.list_contacts()
    assert len(contacts) == 0


def test_apply_creates_pending_contacts(setup_env):
    db = setup_env
    _seed_apps_with_notes(db, n=2)
    fake_svc = _mock_llm_returning_contacts([
        {"name": "HR Person", "email": "hr@firma.de",
         "telefon": "", "rolle": "HR Manager",
         "kategorie": "hr", "confidence": 0.85},
    ])
    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        mcp = _build_mcp(db)
        out = _call(mcp, "kontakte_aus_bewerbungen_extrahieren",
                     {"dry_run": False, "max_bewerbungen": 5})
    assert out["status"] == "ausgefuehrt"
    assert out["extrahiert"] >= 1
    contacts = db.list_contacts()
    assert len(contacts) >= 1
    # Pending-Markierung
    assert any(c.get("is_pending") for c in contacts)


# ============= Filter nur_ohne_kontakte ============

def test_nur_ohne_kontakte_skips_already_extracted(setup_env):
    """Bewerbungen mit extracted_from-Marker werden uebersprungen."""
    db = setup_env
    aids = _seed_apps_with_notes(db, n=3)
    # Markiere die erste als bereits extrahiert
    db.add_contact({
        "full_name": "Bereits Da", "email": "x@y.de",
        "company": "Firma0", "extracted_from": f"application:{aids[0]}",
    })
    fake_svc = _mock_llm_returning_contacts([
        {"name": "X", "email": "x@y.de", "rolle": "R",
         "kategorie": "recruiter", "confidence": 0.9},
    ])
    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        mcp = _build_mcp(db)
        out = _call(mcp, "kontakte_aus_bewerbungen_extrahieren",
                     {"nur_ohne_kontakte": True, "max_bewerbungen": 10})
    # Sollte nur 2 von 3 pruefen
    assert out["geprueft"] == 2


def test_alle_bewerbungen_when_filter_off(setup_env):
    db = setup_env
    aids = _seed_apps_with_notes(db, n=3)
    db.add_contact({
        "full_name": "X", "company": "Firma0",
        "extracted_from": f"application:{aids[0]}",
    })
    fake_svc = _mock_llm_returning_contacts([])  # leer = keine neuen
    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        mcp = _build_mcp(db)
        out = _call(mcp, "kontakte_aus_bewerbungen_extrahieren",
                     {"nur_ohne_kontakte": False, "max_bewerbungen": 10})
    # Alle 3 werden geprueft
    assert out["geprueft"] == 3


# ============= max_bewerbungen Cap ============

def test_max_bewerbungen_caps_processing(setup_env):
    db = setup_env
    _seed_apps_with_notes(db, n=10)
    fake_svc = _mock_llm_returning_contacts([])
    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        mcp = _build_mcp(db)
        out = _call(mcp, "kontakte_aus_bewerbungen_extrahieren",
                     {"max_bewerbungen": 3, "dry_run": True})
    assert out["geprueft"] == 3


# ============= Confidence-Filter ============

def test_low_confidence_contacts_skipped(setup_env):
    db = setup_env
    _seed_apps_with_notes(db, n=1)
    fake_svc = _mock_llm_returning_contacts([
        {"name": "Hoch", "email": "h@y.de", "rolle": "R",
         "kategorie": "recruiter", "confidence": 0.9},
        {"name": "Niedrig", "email": "n@y.de", "rolle": "R",
         "kategorie": "recruiter", "confidence": 0.3},
    ])
    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        mcp = _build_mcp(db)
        out = _call(mcp, "kontakte_aus_bewerbungen_extrahieren",
                     {"dry_run": True})
    assert out["kandidaten"] == 1  # nur "Hoch"


# ============= Events werden mit eingerechnet ============

def test_event_notes_included_in_text(setup_env):
    """Events sollten in den LLM-Input einfliessen — wir verifizieren
    via Mock dass der LLM-Call den Event-Inhalt sieht."""
    db = setup_env
    _seed_apps_with_notes(db, n=1, with_event_notes=True)
    captured = {}

    def capture_run(task_kind, payload):
        captured["text"] = payload.get("text", "")
        result = MagicMock()
        result.success = True
        result.payload = {"contacts": []}
        return result

    fake_status = MagicMock()
    fake_status.ollama_available = True
    fake_status.user_state = "active"
    fake_status.available_models = ["m"]
    fake_svc = MagicMock()
    fake_svc.get_status.return_value = fake_status
    fake_svc.run.side_effect = capture_run

    with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
               return_value=fake_svc):
        mcp = _build_mcp(db)
        _call(mcp, "kontakte_aus_bewerbungen_extrahieren",
               {"max_bewerbungen": 1})
    # Event-Inhalt sollte im Text drin sein
    assert "Hiring-Manager" in captured["text"]
