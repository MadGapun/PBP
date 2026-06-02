"""Tests fuer Issue #667 (B19, beta.84) — Minus-Keywords.

Vierte Keyword-Kategorie analog zu Plus: weiche Score-Abwertung, KEIN
harter Ausschluss. Stelle bleibt sichtbar, rutscht aber nach unten.

Schema unveraendert (v44) — search_criteria ist ein generisches
Key-Value-Store. `keywords_minus` ist nur ein neuer Key.
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


def _register_suche(tmp_db):
    from bewerbungs_assistent.tools.suche import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


# ── 1) MCP-Tools: suchkriterien_setzen + _bearbeiten + _anzeigen ─────────


def test_suchkriterien_setzen_persistiert_minus(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    fn = mcp.tools["suchkriterien_setzen"]

    result = fn(keywords_minus=["Automotive", "SAP-only"])
    assert result["status"] == "gespeichert"

    crit = tmp_db.get_search_criteria()
    assert crit.get("keywords_minus") == ["Automotive", "SAP-only"]


def test_suchkriterien_bearbeiten_minus_hinzufuegen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    set_fn = mcp.tools["suchkriterien_setzen"]
    edit_fn = mcp.tools["suchkriterien_bearbeiten"]

    set_fn(keywords_minus=["Automotive"])
    result = edit_fn(kategorie="minus", aktion="hinzufügen", werte=["Versicherung"])
    assert "fehler" not in result, f"Unerwartet: {result}"

    crit = tmp_db.get_search_criteria()
    assert "Automotive" in crit["keywords_minus"]
    assert "Versicherung" in crit["keywords_minus"]


def test_suchkriterien_bearbeiten_minus_entfernen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    set_fn = mcp.tools["suchkriterien_setzen"]
    edit_fn = mcp.tools["suchkriterien_bearbeiten"]

    set_fn(keywords_minus=["Automotive", "SAP-only", "Versicherung"])
    edit_fn(kategorie="minus", aktion="entfernen", werte=["SAP-only"])

    crit = tmp_db.get_search_criteria()
    assert "SAP-only" not in crit["keywords_minus"]
    assert "Automotive" in crit["keywords_minus"]


def test_suchkriterien_bearbeiten_invalid_kategorie_meldet_minus_in_fehler(tmp_db):
    """Fehlermeldung enthaelt jetzt 'minus' in der erlaubten Liste."""
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    edit_fn = mcp.tools["suchkriterien_bearbeiten"]

    result = edit_fn(kategorie="erfunden", aktion="hinzufuegen", werte=["x"])
    assert "fehler" in result
    assert "minus" in result["fehler"]


# ── 2) Scoring-Engine fit_analyse mit Minus-Keywords ─────────────────────


def test_fit_analyse_minus_treffer_zieht_score(tmp_db):
    """Eine Stelle mit Minus-Treffer bekommt weniger Score als ohne."""
    from bewerbungs_assistent.job_scraper import fit_analyse

    job = {
        "title": "Lead Architect (m/w/d)",
        "description": "Wir suchen einen Architekten fuer unser Automotive-Team. "
                       "Python und FastAPI Erfahrung gewuenscht.",
    }
    base_criteria = {
        "keywords_muss": ["Python"],
        "keywords_plus": ["FastAPI"],
        "gewichtung": {"muss": 2, "plus": 1, "minus": 2},
    }
    base = fit_analyse(job, base_criteria)

    with_minus = dict(base_criteria)
    with_minus["keywords_minus"] = ["Automotive"]
    minus_result = fit_analyse(job, with_minus)

    assert "Automotive" in minus_result["minus_hits"]
    assert minus_result["total_score"] < base["total_score"]


def test_fit_analyse_minus_ohne_treffer_aendert_nichts(tmp_db):
    from bewerbungs_assistent.job_scraper import fit_analyse

    job = {
        "title": "Python Developer",
        "description": "Wir suchen Python-Entwickler fuer Web-Apps. Django/FastAPI.",
    }
    crit = {
        "keywords_muss": ["Python"],
        "keywords_minus": ["Versicherung", "Automotive"],
        "gewichtung": {"muss": 2, "plus": 1, "minus": 2},
    }
    result = fit_analyse(job, crit)
    assert result["minus_hits"] == []


def test_fit_analyse_minus_default_gewicht_1(tmp_db):
    """Ohne explizites minus-Gewicht: Default 1."""
    from bewerbungs_assistent.job_scraper import fit_analyse

    job = {"title": "x", "description": "Wir nutzen Automotive-Standards."}
    crit = {
        "keywords_muss": [],
        "keywords_minus": ["Automotive"],
        # KEIN gewichtung-Dict
    }
    result = fit_analyse(job, crit)
    assert "Automotive" in result["minus_hits"]
    # Score sollte um genau 1 (Default) abgezogen sein - kann <0 sein, total_score = max(0, total)
    minus_factor = next(
        (v for k, v in result["factors"].items() if "MINUS" in k), 0
    )
    assert minus_factor == -1


def test_fit_analyse_risks_bei_mehreren_minus_treffern(tmp_db):
    """Ab 2 Minus-Treffern Risk-Eintrag — fuer Transparenz."""
    from bewerbungs_assistent.job_scraper import fit_analyse

    job = {
        "title": "Architect Automotive",
        "description": "Automotive Architect, SAP-only Stack, Versicherung-Branche.",
    }
    crit = {
        "keywords_muss": ["Architect"],
        "keywords_minus": ["Automotive", "SAP-only", "Versicherung"],
    }
    result = fit_analyse(job, crit)
    assert len(result["minus_hits"]) >= 2
    assert any("MINUS-Keyword" in r for r in result["risks"])


def test_fit_analyse_kein_risk_bei_einem_minus_treffer(tmp_db):
    """Ein einzelner Minus-Treffer ist noch kein Risk-Hinweis."""
    from bewerbungs_assistent.job_scraper import fit_analyse

    job = {"title": "Architect", "description": "Architect fuer Automotive."}
    crit = {
        "keywords_muss": ["Architect"],
        "keywords_minus": ["Automotive"],
    }
    result = fit_analyse(job, crit)
    assert len(result["minus_hits"]) == 1
    assert not any("MINUS-Keyword" in r for r in result["risks"])


def test_fit_analyse_minus_ist_nicht_dasselbe_wie_ausschluss(tmp_db):
    """Minus-Treffer ZIEHEN den Score, SCHLIESSEN die Stelle aber nicht aus.
    Sie taucht weiter im Result auf — nur niedriger."""
    from bewerbungs_assistent.job_scraper import fit_analyse

    job = {
        "title": "Architect Automotive",
        "description": "Senior Architect, Python, Automotive-Erfahrung.",
    }
    crit = {
        "keywords_muss": ["Python"],
        "keywords_plus": ["Architect"],
        "keywords_minus": ["Automotive"],
        "gewichtung": {"muss": 2, "plus": 1, "minus": 1},
    }
    result = fit_analyse(job, crit)
    # Score ist nicht 0 — Stelle bleibt bewertbar
    assert result["total_score"] > 0
    assert "Python" in result["muss_hits"]
    assert "Automotive" in result["minus_hits"]


def test_calculate_score_minus_zieht_punkte():
    """Test der schnellen calculate_score-Variante (#667)."""
    from bewerbungs_assistent.job_scraper import calculate_score

    job_with_minus = {
        "title": "Python Architect",
        "description": "Python Lead fuer Automotive-OEM.",
    }
    job_without_minus = {
        "title": "Python Architect",
        "description": "Python Lead fuer Healthcare.",
    }
    crit = {
        "keywords_muss": ["Python"],
        "keywords_minus": ["Automotive"],
        "gewichtung": {"muss": 5, "minus": 3},
    }
    score_with = calculate_score(job_with_minus, crit)
    score_without = calculate_score(job_without_minus, crit)
    assert score_with < score_without
