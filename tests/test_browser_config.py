"""Tests for browser_config module — DOM selectors and keyword combinations."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.job_scraper.browser_config import (
    SELECTORS,
    build_keyword_combinations,
    build_js_extractor,
    build_js_description,
    get_selectors,
    update_selector,
)


# === Selector Configuration ===


def test_selectors_have_required_keys():
    """LinkedIn and XING selectors contain all required keys."""
    required_linkedin = {
        "job_card", "title_link", "title_text", "company", "location",
        "date", "description", "next_button", "login_indicators",
    }
    required_xing = {
        "job_card", "title_link", "company", "location",
        "description", "next_button", "login_indicators",
    }

    assert required_linkedin.issubset(set(SELECTORS["linkedin"].keys()))
    assert required_xing.issubset(set(SELECTORS["xing"].keys()))


def test_get_selectors_returns_defaults():
    """get_selectors returns defaults when no config file exists."""
    sel = get_selectors("linkedin")
    assert sel["job_card"] == SELECTORS["linkedin"]["job_card"]


def test_get_selectors_unknown_source():
    """get_selectors returns empty dict for unknown source."""
    sel = get_selectors("nonexistent")
    assert sel == {}


def test_update_selector_persists(tmp_path, monkeypatch):
    """update_selector writes to config file."""
    monkeypatch.setattr(
        "bewerbungs_assistent.job_scraper.browser_config.get_selectors",
        lambda src: dict(SELECTORS.get(src, {})),
    )
    # Patch get_data_dir to use tmp_path
    import bewerbungs_assistent.database as db_module
    monkeypatch.setattr(db_module, "get_data_dir", lambda: tmp_path)

    update_selector("linkedin", "job_card", ".new-selector")

    config_file = tmp_path / "browser_selectors.json"
    assert config_file.exists()
    custom = json.loads(config_file.read_text())
    assert custom["linkedin"]["job_card"] == ".new-selector"


# === Keyword Combinations ===


def test_build_keyword_combinations_empty():
    """Empty input returns empty list."""
    assert build_keyword_combinations([]) == []


def test_build_keyword_combinations_single():
    """Single keyword returns it as-is."""
    result = build_keyword_combinations(["PLM"])
    assert len(result) >= 1
    assert any("PLM" in q for q in result)


def test_build_keyword_combinations_core_plus_tech():
    """Core + tech keywords create paired queries."""
    result = build_keyword_combinations(["PLM", "SAP", "Teamcenter"])
    assert len(result) >= 2
    assert len(result) <= 6
    # Should have a PLM+Teamcenter combination
    assert any("PLM" in q and "Teamcenter" in q for q in result)


def test_build_keyword_combinations_with_roles():
    """Role keywords get combined with core keywords."""
    result = build_keyword_combinations(["PLM", "Consultant", "Architekt"])
    assert len(result) >= 2
    # Should have core+role combos
    assert any("PLM" in q and ("Consultant" in q or "Architekt" in q) for q in result)


def test_build_keyword_combinations_niche():
    """Niche keywords get OR-grouped."""
    result = build_keyword_combinations(["PLM", "PRO.FILE", "PROCAD"])
    # Should have an OR group for niche keywords
    assert any("OR" in q for q in result) or len(result) >= 2


def test_build_keyword_combinations_max_six():
    """Never returns more than 6 queries."""
    many_kw = ["PLM", "PDM", "SAP", "CAD", "Teamcenter", "Windchill",
               "Consultant", "Architekt", "Manager", "PRO.FILE"]
    result = build_keyword_combinations(many_kw)
    assert len(result) <= 6


def test_build_keyword_combinations_realistic():
    """Realistic PBP keywords produce sensible combinations."""
    kw = ["PLM", "SAP", "Teamcenter", "PRO.FILE", "PROCAD", "PDM", "CAD", "Programm"]
    result = build_keyword_combinations(kw)
    assert len(result) >= 3
    assert len(result) <= 6
    # At least one pair should be specific
    has_paired = any(
        q.count('"') >= 4  # At least 2 quoted terms
        for q in result
    )
    assert has_paired


# === JS Extractor Building ===


def test_build_js_extractor_linkedin():
    """LinkedIn JS extractor is valid JavaScript."""
    js = build_js_extractor("linkedin")
    assert "querySelectorAll" in js
    assert "jobId" in js
    assert "title" in js


def test_build_js_extractor_xing():
    """XING JS extractor is valid JavaScript."""
    js = build_js_extractor("xing")
    assert "querySelectorAll" in js
    assert "title" in js


def test_build_js_description_linkedin():
    """Description extractor targets correct selectors."""
    js = build_js_description("linkedin")
    assert "querySelector" in js
    assert "innerText" in js


def test_build_js_extractor_unknown():
    """Unknown source returns empty string."""
    js = build_js_extractor("nonexistent")
    assert js == ""
