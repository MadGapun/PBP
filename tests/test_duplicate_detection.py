"""Tests for src/bewerbungs_assistent/duplicate_detection.py (#471)."""

from datetime import datetime, timedelta

from bewerbungs_assistent.duplicate_detection import (
    find_duplicate_job,
    normalize_company_name,
)


# --- normalize_company_name ---

def test_normalize_strips_legal_suffix():
    assert normalize_company_name("VirtoTech Ltd.") == "virtotech"
    assert normalize_company_name("ACME GmbH") == "acme"
    assert normalize_company_name("BigCorp AG") == "bigcorp"
    assert normalize_company_name("Foo GmbH & Co. KG") == "foo"


def test_normalize_strips_parens():
    assert (normalize_company_name("VirtoTech Ltd. (Endkunde: Rota Yokogawa)")
            == "virtotech")
    assert (normalize_company_name("Lürssen Werft (Abt. Business & Engineering IT)")
            == "luerssen werft")


def test_normalize_umlauts():
    assert normalize_company_name("Lürssen") == "luerssen"
    assert normalize_company_name("Müller GmbH") == "mueller"


def test_normalize_empty():
    assert normalize_company_name("") == ""
    assert normalize_company_name(None) == ""


# --- find_duplicate_job: URL match ---

def test_url_match_beats_everything():
    cands = [
        {"company": "Totally Different Corp", "title": "XYZ Engineer",
         "url": "https://foo.com/jobs/123", "hash": "abc"},
    ]
    hit = find_duplicate_job(
        "SomeCompany", "SomeTitle",
        "https://foo.com/jobs/123/",  # trailing slash
        cands,
    )
    assert hit is not None
    assert hit["grund"] == "url_match"
    assert hit["score"] == 1.0


# --- find_duplicate_job: #471 repro case ---

def test_virtotech_case_is_caught():
    """Der Original-Bug aus Issue #471: 2h spaeter, Titel umformuliert."""
    t_minus_2h = (datetime.now() - timedelta(hours=2)).isoformat()
    existing = [
        {
            "hash": "add792f49628",
            "title": "PLM Expert (Endkunde: Rota Yokogawa) via VirtoTech",
            "company": "VirtoTech Ltd. (Endkunde: Rota Yokogawa)",
            "url": "",
            "found_at": t_minus_2h,
        }
    ]
    hit = find_duplicate_job(
        firma="VirtoTech Ltd.",
        titel="SAP / PLM Lead Consultant",
        url="",
        candidates=existing,
    )
    assert hit is not None, "Duplikat muss erkannt werden"
    # Gemeinsame Tokens enthalten 'plm' (Domain-Keyword)
    assert "plm" in hit["shared_tokens"]


def test_firma_mit_klammer_match():
    existing = [
        {"hash": "h1", "company": "VirtoTech Ltd. (Endkunde: ACME)",
         "title": "PLM Consultant", "url": ""},
    ]
    hit = find_duplicate_job("VirtoTech Ltd.", "PLM Architect", "", existing)
    assert hit is not None


def test_rechtsform_unterschied_trotzdem_match():
    """'Foo GmbH' und 'Foo AG' sind selbe Basis-Firma, nicht automatisch match."""
    existing = [
        {"hash": "h1", "company": "Foo GmbH", "title": "Senior PLM Expert", "url": ""},
    ]
    # Beide werden auf "foo" normalisiert -> sollte matchen
    hit = find_duplicate_job("Foo AG", "PLM Consultant", "", existing)
    assert hit is not None


# --- Negative cases ---

def test_unterschiedliche_firma_keinen_match():
    existing = [
        {"hash": "h1", "company": "Foo GmbH", "title": "PLM Expert", "url": ""},
    ]
    hit = find_duplicate_job("Bar AG", "PLM Expert", "", existing)
    assert hit is None


def test_gleiche_firma_anderer_bereich_kein_match_ohne_zeitnaehe():
    """Gleiche Firma, aber Titel hat keinen Overlap und kein Zeit-Signal."""
    existing = [
        {"hash": "h1", "company": "Foo GmbH",
         "title": "Frontend Developer React", "url": "",
         "found_at": "2020-01-01T00:00:00"},  # sehr alt
    ]
    hit = find_duplicate_job("Foo GmbH", "Marketing Manager B2B", "", existing)
    # Keine gemeinsamen Tokens, kein Zeit-Bonus -> kein match
    assert hit is None


def test_zeitnaehe_ohne_titel_match_schwache_warnung():
    """Gleiche Firma, innerhalb 72h, keine Domain-Keyword-Ueberlappung."""
    t_minus_1h = (datetime.now() - timedelta(hours=1)).isoformat()
    existing = [
        {"hash": "h1", "company": "Foo GmbH",
         "title": "Frontend Developer", "url": "",
         "found_at": t_minus_1h},
    ]
    hit = find_duplicate_job("Foo GmbH", "Marketing Manager", "", existing)
    assert hit is not None
    assert hit["grund"] == "firma_plus_zeitnaehe"


def test_leere_eingaben():
    assert find_duplicate_job("", "Title", "", []) is None
    assert find_duplicate_job("Firma", "", "", []) is None
    assert find_duplicate_job("Firma", "Title", "", []) is None
