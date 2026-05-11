"""Tests fuer v1.7.0-beta.52 — JSON-LD-Helper extrahiert (#624 Phase 3)."""
from __future__ import annotations

import pytest


# === extract_jobposting_jsonld() ===

def test_extracts_basic_jobposting():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    html = """
    <html><head>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": "Senior Python Developer",
        "description": "Wir suchen einen Senior Python Developer mit FastAPI-Erfahrung.",
        "datePosted": "2026-05-11",
        "hiringOrganization": {"@type": "Organization", "name": "ACME GmbH"}
    }
    </script>
    </head><body></body></html>
    """
    result = extract_jobposting_jsonld(html)
    assert result["title"] == "Senior Python Developer"
    assert "FastAPI" in result["description"]
    assert result["datePosted"] == "2026-05-11"
    assert result["hiringOrganization"]["name"] == "ACME GmbH"


def test_strips_html_from_description():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    html = """
    <script type="application/ld+json">
    {
        "@type": "JobPosting",
        "description": "<p>Wir suchen <strong>Senior</strong> Engineer.</p><ul><li>Python</li><li>SQL</li></ul>"
    }
    </script>
    """
    result = extract_jobposting_jsonld(html)
    assert "<p>" not in result["description"]
    assert "<strong>" not in result["description"]
    assert "Senior" in result["description"]
    assert "Python" in result["description"]


def test_returns_empty_dict_when_no_jsonld():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    html = "<html><body><p>Keine JSON-LD hier.</p></body></html>"
    assert extract_jobposting_jsonld(html) == {}


def test_returns_empty_dict_when_jsonld_not_jobposting():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    html = """
    <script type="application/ld+json">
    {"@type": "Article", "headline": "Etwas anderes"}
    </script>
    """
    assert extract_jobposting_jsonld(html) == {}


def test_handles_array_of_jsonld_items():
    """JSON-LD kann Array sein, oder @graph mit mehreren Items."""
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    html = """
    <script type="application/ld+json">
    [
        {"@type": "WebSite", "name": "Job-Portal"},
        {"@type": "JobPosting", "title": "DevOps", "description": "K8s + AWS"}
    ]
    </script>
    """
    result = extract_jobposting_jsonld(html)
    assert result["title"] == "DevOps"


def test_handles_graph_envelope():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    html = """
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": "Firma"},
            {"@type": "JobPosting", "title": "Backend Dev", "description": "Python"}
        ]
    }
    </script>
    """
    result = extract_jobposting_jsonld(html)
    assert result["title"] == "Backend Dev"


def test_handles_multiple_jsonld_scripts_first_wins():
    """Wenn mehrere JSON-LD-Scripts: das erste JobPosting wird genommen."""
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    html = """
    <script type="application/ld+json">
    {"@type": "WebSite", "name": "Site"}
    </script>
    <script type="application/ld+json">
    {"@type": "JobPosting", "title": "First", "description": "first desc"}
    </script>
    <script type="application/ld+json">
    {"@type": "JobPosting", "title": "Second", "description": "second"}
    </script>
    """
    result = extract_jobposting_jsonld(html)
    assert result["title"] == "First"


def test_max_chars_limits_description():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    long_text = "x" * 5000
    html = f"""
    <script type="application/ld+json">
    {{"@type": "JobPosting", "description": "{long_text}"}}
    </script>
    """
    result = extract_jobposting_jsonld(html, max_chars=500)
    assert len(result["description"]) == 500


def test_handles_malformed_json_gracefully():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    html = """
    <script type="application/ld+json">
    { broken json without quotes
    </script>
    <script type="application/ld+json">
    {"@type": "JobPosting", "title": "Valid", "description": "OK"}
    </script>
    """
    result = extract_jobposting_jsonld(html)
    # Sollte nicht crashen, sondern den naechsten validen finden
    assert result["title"] == "Valid"


def test_handles_empty_input():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    assert extract_jobposting_jsonld("") == {}
    assert extract_jobposting_jsonld(None) == {}


# === fetch_description_from_detail nutzt jetzt den Helper ===

def test_fetch_description_uses_jsonld_first():
    """Verifiziere dass der Refactor in fetch_description_from_detail
    den extract_jobposting_jsonld()-Helper verwendet."""
    from unittest.mock import MagicMock
    from bewerbungs_assistent.job_scraper import fetch_description_from_detail
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = """
    <script type="application/ld+json">
    {"@type": "JobPosting", "description": "Aus JSON-LD"}
    </script>
    <main>Aus HTML-Selektor (sollte NICHT genommen werden)</main>
    """
    fake_client = MagicMock()
    fake_client.get.return_value = fake_resp
    result = fetch_description_from_detail("https://example.com", fake_client)
    assert "Aus JSON-LD" in result
    assert "HTML-Selektor" not in result


def test_fetch_description_falls_back_to_selectors():
    """Wenn kein JSON-LD, dann CSS-Selectors als Fallback."""
    from unittest.mock import MagicMock
    from bewerbungs_assistent.job_scraper import fetch_description_from_detail
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = """
    <html><body>
    <main>Lange Beschreibung mit mehr als 100 Zeichen die der Fallback-Selektor finden sollte und zurueckgeben muss.</main>
    </body></html>
    """
    fake_client = MagicMock()
    fake_client.get.return_value = fake_resp
    result = fetch_description_from_detail("https://example.com", fake_client)
    assert "Lange Beschreibung" in result


# === bundesagentur Migration ===

def test_bundesagentur_uses_make_session():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
            / "src" / "bewerbungs_assistent" / "job_scraper" / "bundesagentur.py")
    content = src.read_text(encoding="utf-8")
    assert "make_session" in content
    # Das alte Pattern darf nicht mehr drin sein
    assert "with httpx.Client(timeout=30) as client" not in content
