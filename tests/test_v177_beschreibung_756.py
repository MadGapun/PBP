"""Tests fuer #756 (v1.7.7) — Beschreibung-zuerst + Score 0 ist kein Urteil.

Praxis-Fund vom 13.07.: Stellen ohne nachgeladene Beschreibung standen mit
Score 0 in der Liste und wurden von der lokalen KI auf Titel-Basis
aussortiert. Seitdem gilt:

  1. stellen_auto_aussortieren legt beschreibungslose Stellen (< 50 Zeichen,
     konsistent mit fit_analyse/#180) NIE der LLM vor — sie werden als
     "uebersprungen_ohne_beschreibung" ausgewiesen, naechster Schritt
     stellenbeschreibung_nachladen.
  2. stellen_anzeigen markiert Score 0 + fehlende Beschreibung als
     score_status='unbewertet' und liefert eine Summenzeile.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


class FakeLLMService:
    """Immer-verfuegbare lokale KI, die ALLES als PASST_NICHT einstuft —
    damit ist jeder LLM-Call an einer beschreibungslosen Stelle sichtbar."""

    def __init__(self):
        self.run_calls = []

    def get_status(self, force_refresh=False):
        return SimpleNamespace(
            ollama_available=True,
            available_models=["mock-modell"],
            user_state="active",
            selected_model="mock-modell",
        )

    def warmup(self):
        return {"status": "warm", "duration_sec": 0.01}

    def run(self, kind, payload):
        self.run_calls.append(payload)
        return SimpleNamespace(
            success=True,
            payload={"decision": "PASST_NICHT", "reason": "Mock-Ablehnung"},
            fallback_message="",
        )


def _register_jobs(tmp_db):
    from bewerbungs_assistent.tools.jobs import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _add_job(tmp_db, hash_short, title, score, description):
    pid = tmp_db.get_active_profile_id() or ""
    full = f"{pid}:{hash_short}"
    tmp_db.save_jobs([{
        "hash": full, "title": title, "company": "Testfirma GmbH",
        "location": "Hamburg", "url": f"https://x/{hash_short}",
        "source": "manuell", "score": score, "description": description,
    }])
    return full


LANGE_BESCHREIBUNG = "Wir suchen Verstaerkung fuer unser Team. " * 5


# ── stellen_auto_aussortieren: Beschreibung-zuerst ───────────────────────


def test_auto_aussortieren_ueberspringt_ohne_beschreibung(tmp_db, monkeypatch):
    tmp_db.create_profile("Test", "test@example.com")
    mit1 = _add_job(tmp_db, "mit1", "Bilanzbuchhalter", 40, LANGE_BESCHREIBUNG)
    mit2 = _add_job(tmp_db, "mit2", "Steuerfachwirt", 30, LANGE_BESCHREIBUNG)
    ohne1 = _add_job(tmp_db, "ohn1", "PLM Consultant", 0, "")
    ohne2 = _add_job(tmp_db, "ohn2", "Projektleiter PLM", 0, "kurz")

    fake = FakeLLMService()
    monkeypatch.setattr(
        "bewerbungs_assistent.services.llm_service.get_llm_service",
        lambda db: fake,
    )

    mcp = _register_jobs(tmp_db)
    result = mcp.tools["stellen_auto_aussortieren"](max_stellen=10)

    assert result["status"] == "ok"
    # Nur die beiden MIT Beschreibung wurden der LLM vorgelegt
    assert len(fake.run_calls) == 2
    assert result["geprueft"] == 2
    assert result["passt_nicht"] == 2
    assert result["uebersprungen_ohne_beschreibung"] == 2
    assert len(result["uebersprungen_details"]) == 2
    assert "stellenbeschreibung_nachladen" in result["uebersprungen_hinweis"]

    # DB-Wahrheit: beschreibungslose Stellen bleiben unangetastet aktiv
    assert tmp_db.get_job(ohne1)["is_active"] == 1
    assert tmp_db.get_job(ohne2)["is_active"] == 1
    assert tmp_db.get_job(mit1)["is_active"] == 0
    assert tmp_db.get_job(mit2)["is_active"] == 0


def test_auto_aussortieren_alle_ohne_beschreibung_leer_mit_hinweis(tmp_db, monkeypatch):
    tmp_db.create_profile("Test", "test@example.com")
    _add_job(tmp_db, "ohn1", "PLM Consultant", 0, "")
    _add_job(tmp_db, "ohn2", "Projektleiter", 0, "")

    fake = FakeLLMService()
    monkeypatch.setattr(
        "bewerbungs_assistent.services.llm_service.get_llm_service",
        lambda db: fake,
    )

    mcp = _register_jobs(tmp_db)
    result = mcp.tools["stellen_auto_aussortieren"](max_stellen=10)

    assert result["status"] == "leer"
    assert result["uebersprungen_ohne_beschreibung"] == 2
    assert "stellenbeschreibung_nachladen" in result["hinweis"]
    # Kein einziger LLM-Call auf beschreibungslose Stellen
    assert fake.run_calls == []


# ── stellen_anzeigen: Score 0 ist kein Urteil ────────────────────────────


def test_stellen_anzeigen_markiert_unbewertet(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    _add_job(tmp_db, "unb1", "PLM Consultant", 0, "")
    _add_job(tmp_db, "tit1", "PLM Manager", 20, "")
    _add_job(tmp_db, "voll", "PLM Architect", 30, LANGE_BESCHREIBUNG)

    mcp = _register_jobs(tmp_db)
    result = mcp.tools["stellen_anzeigen"]()

    by_title = {s["titel"].split(" ", 1)[1]: s for s in result["stellen"]}

    unbewertet = by_title["PLM Consultant"]
    assert unbewertet["beschreibung_fehlt"] is True
    assert unbewertet["score_status"] == "unbewertet"
    assert "KEIN Urteil" in unbewertet["score_hinweis"]
    assert "stellenbeschreibung_nachladen" in unbewertet["score_hinweis"]

    nur_titel = by_title["PLM Manager"]
    assert nur_titel["beschreibung_fehlt"] is True
    assert "score_status" not in nur_titel
    assert "nur auf dem Titel" in nur_titel["score_hinweis"]

    voll = by_title["PLM Architect"]
    assert "beschreibung_fehlt" not in voll
    assert "score_hinweis" not in voll

    assert result["unbewertet_anzahl"] == 1
    assert "KEIN Urteil" in result["unbewertet_hinweis"]


def test_stellen_anzeigen_ohne_unbewertete_kein_hinweis(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    _add_job(tmp_db, "voll", "PLM Architect", 30, LANGE_BESCHREIBUNG)

    mcp = _register_jobs(tmp_db)
    result = mcp.tools["stellen_anzeigen"]()
    assert "unbewertet_anzahl" not in result
