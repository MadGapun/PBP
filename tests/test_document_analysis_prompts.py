"""Tests fuer document_analysis_prompts (#496)."""
from __future__ import annotations

import pytest

from bewerbungs_assistent.document_analysis_prompts import (
    TEMPLATES,
    available_templates,
    build_prompt,
    select_template_key,
)


def test_templates_have_required_fields():
    for key, tpl in TEMPLATES.items():
        assert "label" in tpl, f"{key}: label fehlt"
        assert "focus" in tpl, f"{key}: focus fehlt"
        assert "apply_to_profile" in tpl, f"{key}: apply_to_profile fehlt"
        assert isinstance(tpl["focus"], list)
        assert len(tpl["focus"]) >= 3


def test_available_templates_returns_all_keys():
    templates = available_templates()
    keys = {t["key"] for t in templates}
    assert keys == set(TEMPLATES.keys())


@pytest.mark.parametrize(
    "doc,expected",
    [
        ({"doc_type": "lebenslauf", "filename": "cv.pdf"}, "profil_aufbau"),
        ({"doc_type": "anschreiben", "filename": "cover.pdf"}, "profil_aufbau"),
        ({"doc_type": "zeugnis", "filename": "z.pdf"}, "profil_aufbau"),
        ({"doc_type": "zertifikat", "filename": "c.pdf"}, "profil_aufbau"),
        ({"doc_type": "stellenbeschreibung", "filename": "jd.pdf"}, "stellenausschreibung"),
        ({"doc_type": "sonstiges", "filename": "stellenausschreibung-acme.pdf"}, "stellenausschreibung"),
        ({"doc_type": "vorbereitung", "filename": "prep.pdf"}, "gespraechsnotiz"),
        ({"doc_type": "sonstiges", "filename": "gespraechsnotiz-acme.txt"}, "gespraechsnotiz"),
        ({"doc_type": "sonstiges", "filename": "arbeitsvertrag-acme.pdf"}, "vertrag"),
        ({"doc_type": "sonstiges", "filename": "offer-letter.pdf"}, "vertrag"),
        ({"doc_type": "sonstiges", "filename": "unknown.pdf"}, "fallback"),
    ],
)
def test_select_template_by_doc_type_and_filename(doc, expected):
    assert select_template_key(doc) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Wir bestaetigen den Eingang Ihrer Bewerbung", "eingangsbestaetigung"),
        ("wir haben Ihre Bewerbung erhalten", "eingangsbestaetigung"),
        ("Leider muessen wir Ihnen absagen", "absage"),
        ("Wir freuen uns, Ihnen einen Vertragsentwurf zu senden", "vertrag"),
        ("Wir moechten Sie gerne zum Vorstellungsgespraech einladen", "gespraechsnotiz"),
    ],
)
def test_select_template_by_email_content(text, expected):
    doc = {"doc_type": "mail_eingang", "filename": "x.eml", "extracted_text": text}
    assert select_template_key(doc) == expected


def test_select_template_email_without_match_falls_back():
    doc = {"doc_type": "mail_eingang", "filename": "x.eml",
           "extracted_text": "Hallo, anbei die Dokumente."}
    assert select_template_key(doc) == "fallback"


def test_build_prompt_auto_selects_template():
    doc = {
        "id": "abc123",
        "filename": "absage.eml",
        "doc_type": "mail_eingang",
        "extracted_text": "Leider absagen",
        "app_company": "ACME",
        "app_title": "Senior Dev",
        "extraction_status": "nicht_extrahiert",
    }
    result = build_prompt(doc)
    assert result["template"] == "absage"
    assert result["label"] == "Absage"
    assert result["apply_to_profile"] is False
    assert "ACME" in result["prompt"]
    assert "Senior Dev" in result["prompt"]
    assert "abc123" in result["prompt"]
    assert "extraktion_starten" in result["prompt"]


def test_build_prompt_forces_template_key():
    doc = {"id": "1", "filename": "x.pdf", "doc_type": "lebenslauf",
           "extraction_status": "analysiert"}
    result = build_prompt(doc, template_key="stellenausschreibung")
    assert result["template"] == "stellenausschreibung"
    assert result["label"] == "Stellenausschreibung"


def test_build_prompt_unknown_template_falls_back_to_auto():
    doc = {"id": "1", "filename": "x.pdf", "doc_type": "lebenslauf",
           "extraction_status": "nicht_extrahiert"}
    result = build_prompt(doc, template_key="does_not_exist")
    assert result["template"] == "profil_aufbau"


def test_build_prompt_applies_profile_workflow_for_cv():
    doc = {"id": "1", "filename": "cv.pdf", "doc_type": "lebenslauf"}
    result = build_prompt(doc)
    assert result["apply_to_profile"] is True
    assert "extraktion_ergebnis_speichern" in result["prompt"]
    assert "extraktion_anwenden" in result["prompt"]


def test_build_prompt_non_profile_workflow_mentions_pbp_tools():
    doc = {"id": "1", "filename": "x.pdf", "doc_type": "stellenbeschreibung"}
    result = build_prompt(doc)
    assert result["apply_to_profile"] is False
    assert "nachfass_planen" in result["prompt"] or "bewerbung_status_aendern" in result["prompt"]


def test_build_prompt_email_adds_email_hint():
    doc = {"id": "1", "filename": "x.eml", "doc_type": "mail_eingang",
           "extracted_text": "hallo"}
    result = build_prompt(doc)
    assert "E-Mail" in result["prompt"]
