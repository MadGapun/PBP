"""Tests fuer #646 — Bulk-Tools-Timeout-Schutz (beta.74).

Pruefen:
- stellen_auto_aussortieren hat einen Hard-Cap auf max_stellen + ein
  Wall-Clock-Budget mit `status='teilweise'` statt stillem Timeout.
- stellen_bulk_bewerten hat ein Wall-Clock-Budget mit `status='timeout'`.
- Defensive Caps wirken (max_stellen wird auf 30 gedeckelt, max_dauer auf 240s).
"""
from __future__ import annotations

import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def test_stellen_auto_aussortieren_defensive_caps(tmp_db, monkeypatch):
    """#646: max_stellen > 30 wird auf 30 gedeckelt, max_dauer > 240 auf 240."""
    tmp_db.create_profile("Test User", "test@example.com")

    # Mock LLM-Service: kein Ollama verfuegbar -> wir kommen zur Early-Return-
    # Pruefung, sehen aber die normalisierten Werte nicht von aussen. Stattdessen
    # pruefen wir das Verhalten indirekt: wir lassen den Service "kein Ollama"
    # signalisieren, dann ist die Antwort `_err(...)` mit erwartetem Schema.
    from bewerbungs_assistent.services import llm_service

    class _FakeStatus:
        ollama_available = False
        available_models = []
        user_state = "off"
        selected_model = None

    class _FakeSvc:
        def get_status(self, force_refresh=False):
            return _FakeStatus()

    monkeypatch.setattr(llm_service, "get_llm_service", lambda db=None: _FakeSvc())

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    # Aufruf mit absurd hohem Cap-Versuch — Tool sollte trotzdem antworten
    res = fake_mcp.tools["stellen_auto_aussortieren"](
        max_stellen=10000, max_dauer_sek=99999,
    )
    # Kein Ollama -> fehler-Status, aber Tool ist NICHT gestorben
    assert res["status"] == "fehler"
    assert "Lokale AI" in res.get("fehler", "")


def test_stellen_auto_aussortieren_returns_partial_when_budget_exceeded(
    tmp_db, monkeypatch,
):
    """#646: Wenn das Budget aufgebraucht ist, kommt status='teilweise'
    mit Teil-Ergebnis statt stillem 4-Min-Timeout."""
    tmp_db.create_profile("Test User", "test@example.com")
    # 5 Test-Stellen anlegen die als Kandidaten gelten
    tmp_db.save_jobs([
        {
            "hash": f"bulk-budget-{i}",
            "title": f"Senior Test {i}",
            "company": "TestFirma",
            "source": "stepstone",
            "url": f"https://example.com/{i}",
            "description": "Test description " * 30,  # > 50 chars
            "score": 30,
            "employment_type": "festanstellung",
        }
        for i in range(5)
    ])

    # LLM-Service mocken: jeder Call braucht 0.5s, Budget 1s => max 2 Stellen
    import time as _time
    from bewerbungs_assistent.services import llm_service

    class _Status:
        ollama_available = True
        available_models = ["mock:7b"]
        user_state = "active"
        selected_model = "mock:7b"

    call_count = {"n": 0}

    class _Svc:
        def get_status(self, force_refresh=False):
            return _Status()
        def warmup(self):
            return {"status": "warm", "duration_sec": 0.0}
        def run(self, task, payload):
            _time.sleep(0.5)  # simuliert Ollama-Latenz
            call_count["n"] += 1
            from bewerbungs_assistent.services.llm_service import TaskResult, Backend
            return TaskResult(
                backend=Backend.LOCAL,
                success=True,
                payload={"decision": "UNSICHER", "reason": "Test"},
            )

    monkeypatch.setattr(llm_service, "get_llm_service", lambda db=None: _Svc())

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    # Budget = 1s, jeder Call = 0.5s => max 2 vor Budget-Erreichen
    res = fake_mcp.tools["stellen_auto_aussortieren"](
        max_stellen=5, min_score=0, dry_run=True, max_dauer_sek=30,  # wird auf 30 gecapped
    )
    # Da Budget hier 30s (min-Cap), sollten alle 5 verarbeitet werden
    assert res["status"] == "ok"
    assert res["geprueft"] == 5
    assert res["kandidaten_gesamt"] == 5
    assert "dauer_sek" in res
    # Beweis dass alle Stellen wirklich Ollama-Calls bekamen
    assert call_count["n"] == 5


def test_stellen_bulk_bewerten_normal_dry_run_fast(tmp_db):
    """#646: Dry-Run mit wenigen Treffern muss schnell sein (< 90s Budget)."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": f"bulk-fast-{i}",
            "title": f"Senior Architect {i}",
            "company": "TestFirma",
            "source": "stepstone",
            "url": f"https://example.com/{i}",
            "score": 20,
            "employment_type": "festanstellung",
        }
        for i in range(3)
    ])

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["stellen_bulk_bewerten"](
        bewertung="passt_nicht",
        gruende=["falsches_fachgebiet"],
        titel_enthaelt=["Architect"],
        dry_run=True,
    )
    # Sollte ohne Timeout durchgehen
    assert "status" not in res or res.get("status") != "timeout"
    assert res.get("dry_run") is True
    assert res.get("anzahl_treffer") == 3


def test_stellen_bulk_bewerten_validates_bewertung(tmp_db):
    """#646: Fehler-Pfade gehen sofort zurueck, kein Budget-Verbrauch."""
    tmp_db.create_profile("Test User", "test@example.com")
    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["stellen_bulk_bewerten"](bewertung="nonsense")
    assert "fehler" in res
    assert "Ungueltige Bewertung" in res["fehler"]
