"""Tests fuer stellen_qualitaet_pruefen MCP-Tool und Ollama-Validator (#645)."""
from __future__ import annotations

import json
import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


# ── Ollama-Validator-Parser ──────────────────────────────────────────


def test_validate_job_quality_parser_clean_json():
    """Sauberer JSON-Output von Ollama wird korrekt geparst."""
    from bewerbungs_assistent.services.llm_service import _parse_validate_job_quality
    raw = json.dumps({
        "vollstaendig": True,
        "score": 8,
        "vorhanden": ["aufgaben", "anforderungen", "standort"],
        "fehlt": ["gehalt", "benefits"],
        "begruendung": "Klare Aufgaben.",
        "claude_action": "keine",
    })
    out = _parse_validate_job_quality(raw)
    assert out["vollstaendig"] is True
    assert out["score"] == 8
    assert "aufgaben" in out["vorhanden"]
    assert out["claude_action"] == "keine"


def test_validate_job_quality_parser_with_codefence():
    """Markdown-Codefence-Antwort wird trotzdem geparst."""
    from bewerbungs_assistent.services.llm_service import _parse_validate_job_quality
    raw = """```json
{"vollstaendig": false, "score": 2, "vorhanden": [], "fehlt": ["alles"],
 "begruendung": "Beschreibung leer.", "claude_action": "nachladen"}
```"""
    out = _parse_validate_job_quality(raw)
    assert out["vollstaendig"] is False
    assert out["score"] == 2
    assert out["claude_action"] == "nachladen"


def test_validate_job_quality_parser_with_prefix_text():
    """Vorspann-Text vor dem JSON-Block wird ignoriert."""
    from bewerbungs_assistent.services.llm_service import _parse_validate_job_quality
    raw = """Hier ist meine Analyse:
{"vollstaendig": true, "score": 7, "vorhanden": ["x"], "fehlt": [],
 "begruendung": "OK.", "claude_action": "keine"}"""
    out = _parse_validate_job_quality(raw)
    assert out["score"] == 7
    assert out["vollstaendig"] is True


def test_validate_job_quality_parser_invalid_json_falls_back():
    """Unparsebarer Output -> sicherer Default mit claude_action=manuell."""
    from bewerbungs_assistent.services.llm_service import _parse_validate_job_quality
    out = _parse_validate_job_quality("Sorry, I can't help with that.")
    assert out["vollstaendig"] is False
    assert out["score"] == 0
    assert out["claude_action"] == "manuell_ergaenzen"
    assert "raw" in out


def test_validate_job_quality_parser_normalizes_invalid_action():
    """Ungueltige claude_action -> 'keine' (defensive)."""
    from bewerbungs_assistent.services.llm_service import _parse_validate_job_quality
    raw = json.dumps({
        "vollstaendig": True, "score": 5,
        "vorhanden": [], "fehlt": [],
        "begruendung": "x",
        "claude_action": "automatisch_alles_loeschen",  # ungueltig
    })
    out = _parse_validate_job_quality(raw)
    assert out["claude_action"] == "keine"


def test_validate_job_quality_prompt_contains_all_fields():
    """Prompt enthaelt Titel, Firma, URL, Beschreibung."""
    from bewerbungs_assistent.services.llm_service import _build_validate_job_quality_prompt
    p = _build_validate_job_quality_prompt({
        "title": "Senior PLM Berater",
        "company": "TestFirma-X",
        "location": "Hamburg",
        "url": "https://example.com/job/42",
        "description": "Beschreibung hier...",
        "source": "stepstone",
    })
    assert "Senior PLM Berater" in p
    assert "TestFirma-X" in p
    assert "Hamburg" in p
    assert "stepstone" in p
    assert "https://example.com/job/42" in p
    assert "claude_action" in p  # Schema-Hint


# ── stellen_qualitaet_pruefen MCP-Tool ───────────────────────────────


def _seed_test_jobs(tmp_db):
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "qpr-ok-1",
            "title": "Senior PLM Berater",
            "company": "TestFirma-A",
            "source": "stepstone",
            "url": "https://example.com/ok",
            "description": "Aufgaben: PLM-Beratung. Anforderungen: 5 Jahre Erfahrung.",
            "score": 30,
            "employment_type": "festanstellung",
        },
        {
            "hash": "qpr-noempty-1",
            "title": "Manager IT",
            "company": "TestFirma-B",
            "source": "manuell",
            "url": "",
            "description": "kurz",
            "score": 10,
            "employment_type": "festanstellung",
        },
        {
            "hash": "qpr-searchurl-1",
            "title": "Lead Architect",
            "company": "TestFirma-C",
            "source": "linkedin",
            "url": "https://linkedin.com/jobs/search?keywords=architect",
            "is_search_url": True,
            "description": "Aufgaben: Architektur leiten. Anforderungen: 10 Jahre.",
            "score": 20,
            "employment_type": "festanstellung",
        },
    ])


def test_qualitaet_pruefen_classifies_search_url_and_short_desc(
    tmp_db, monkeypatch,
):
    """Such-URLs + zu kurze Beschreibungen werden kategorisiert."""
    _seed_test_jobs(tmp_db)

    # url_health-Check mocken — wir wollen die Klassifikations-Logik
    # ohne echtes Netz testen
    from bewerbungs_assistent.services import url_health
    def _fake_check(url, title=None, *, client=None, timeout=15.0):
        if not url:
            return url_health.HealthResult(status=url_health.HealthStatus.LEER)
        return url_health.HealthResult(
            status=url_health.HealthStatus.OK,
            http_code=200,
            title_token_hits="3/3",
        )
    monkeypatch.setattr(
        "bewerbungs_assistent.services.url_health.check_job_url_health",
        _fake_check,
    )

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["stellen_qualitaet_pruefen"](
        max_stellen=10, nur_problematische=True, auto_aussortieren=False,
    )
    assert res["geprueft"] == 3
    befunde = res["befunde"]
    # qpr-noempty-1 hat description "kurz" (4 chars) und URL leer (manuell ok)
    assert befunde.get("beschreibung_fehlt", 0) >= 1
    # qpr-searchurl-1 hat is_search_url=True
    assert befunde.get("search_url", 0) >= 1
    # qpr-ok-1 ist ok — wenn nur_problematische=True nicht in details
    titles = [d["title"] for d in res["details"]]
    assert "Senior PLM Berater" not in titles


def test_qualitaet_pruefen_auto_aussortiert_url_404(tmp_db, monkeypatch):
    """Mit auto_aussortieren=True werden 404-Stellen dismissed."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "qpr-404-1",
            "title": "Veraltete Stelle",
            "company": "TestFirma-D",
            "source": "stepstone",
            "url": "https://example.com/dead",
            "description": "Volle Beschreibung mit allem drum und dran in 50+ chars.",
            "score": 20,
            "employment_type": "festanstellung",
        },
    ])

    from bewerbungs_assistent.services import url_health
    def _fake_check(url, title=None, *, client=None, timeout=15.0):
        return url_health.HealthResult(
            status=url_health.HealthStatus.HTTP_404, http_code=404,
        )
    monkeypatch.setattr(
        "bewerbungs_assistent.services.url_health.check_job_url_health",
        _fake_check,
    )

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["stellen_qualitaet_pruefen"](
        max_stellen=10, auto_aussortieren=True,
    )
    assert res["aussortiert"] == 1
    assert res["befunde"].get("url_404") == 1

    # Stelle ist jetzt aussortiert
    job = tmp_db.get_job("qpr-404-1")
    assert job.get("is_active") == 0
    assert job.get("dismiss_reason") == "veraltet_url"


def test_qualitaet_pruefen_preview_mode_does_not_dismiss(tmp_db, monkeypatch):
    """Default (auto_aussortieren=False) ist reine Vorschau."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "qpr-preview-404-1",
            "title": "Andere veraltete Stelle",
            "company": "TestFirma-E",
            "source": "stepstone",
            "url": "https://example.com/dead2",
            "description": "Volle Beschreibung mit allem drum und dran in 50+ chars.",
            "score": 20,
            "employment_type": "festanstellung",
        },
    ])

    from bewerbungs_assistent.services import url_health
    def _fake_check(url, title=None, *, client=None, timeout=15.0):
        return url_health.HealthResult(
            status=url_health.HealthStatus.HTTP_404, http_code=404,
        )
    monkeypatch.setattr(
        "bewerbungs_assistent.services.url_health.check_job_url_health",
        _fake_check,
    )

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["stellen_qualitaet_pruefen"](
        max_stellen=10, auto_aussortieren=False,
    )
    # 'aussortiert' field nur bei auto_aussortieren=True
    assert "aussortiert" not in res
    # 'hinweis' weil 1 Treffer mit url_404
    assert "hinweis" in res
    # Job ist NICHT aussortiert
    job = tmp_db.get_job("qpr-preview-404-1")
    assert job.get("is_active") == 1
