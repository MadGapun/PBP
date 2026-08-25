"""Tests for src/bewerbungs_assistent/duplicate_detection.py (#471)."""

from datetime import datetime, timedelta, timezone

from bewerbungs_assistent.duplicate_detection import (
    find_duplicate_job,
    normalize_company_name,
)


# --- normalize_company_name ---

def test_normalize_strips_legal_suffix():
    assert normalize_company_name("Systemhaus Nord Ltd.") == "systemhaus nord"
    assert normalize_company_name("ACME GmbH") == "acme"
    assert normalize_company_name("BigCorp AG") == "bigcorp"
    assert normalize_company_name("Foo GmbH & Co. KG") == "foo"


def test_normalize_strips_parens():
    assert (normalize_company_name("Systemhaus Nord Ltd. (Endkunde: Anlagenbau Sued)")
            == "systemhaus nord")
    assert (normalize_company_name("Werft Nord (Abt. Business & Engineering IT)")
            == "werft nord")


def test_normalize_umlauts():
    assert normalize_company_name("Werft Nord") == "werft nord"
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

def test_systemhaus_nord_gleiche_url_wird_gefangen():
    """#471/#670: Bei IDENTISCHER URL ist es sicher ein Duplikat — unabhaengig
    vom Titel. Die URL ist das zuverlaessigste Signal.

    Hinweis: Der urspruengliche #471-Catch beruhte auf einem einzelnen
    geteilten Domain-Keyword (PLM). Das hat #670 bewusst entschaerft, weil
    es verschiedene Stellen derselben Firma faelschlich blockte. Reale
    Reposts werden jetzt zuverlaessig ueber die URL erkannt.
    """
    t_minus_2h = (datetime.now() - timedelta(hours=2)).isoformat()
    existing = [
        {
            "hash": "add792f49628",
            "title": "PLM Expert (Endkunde: Anlagenbau Sued) via Systemhaus Nord",
            "company": "Systemhaus Nord Ltd. (Endkunde: Anlagenbau Sued)",
            "url": "https://systemhaus-nord.example/jobs/plm-123",
            "found_at": t_minus_2h,
        }
    ]
    hit = find_duplicate_job(
        firma="Systemhaus Nord Ltd.",
        titel="SAP / PLM Lead Consultant",
        url="https://systemhaus-nord.example/jobs/plm-123",
        candidates=existing,
    )
    assert hit is not None, "Gleiche URL muss als Duplikat erkannt werden"
    assert hit["grund"] == "url_match"


def test_670_single_domainkeyword_blockt_nicht():
    """#670: 'PLM Project Manager' und 'PLM Product Owner' teilen nur 'PLM',
    sind aber verschiedene Jobs -> KEIN Duplikat (verschiedene URLs)."""
    existing = [
        {
            "hash": "konsumgueter1",
            "title": "PLM Project Manager (m/w/d)",
            "company": "Konsumgueter GmbH",
            "url": "https://konsumgueter.example/jobs/pm",
        }
    ]
    hit = find_duplicate_job(
        firma="Konsumgueter GmbH",
        titel="PLM Product Owner (m/w/d)",
        url="https://konsumgueter.example/jobs/po",
        candidates=existing,
    )
    assert hit is None, "Single geteiltes Domain-Keyword darf nicht blocken (#670)"


def test_firma_mit_klammer_match():
    existing = [
        {"hash": "h1", "company": "Systemhaus Nord Ltd. (Endkunde: ACME)",
         "title": "PLM Consultant", "url": ""},
    ]
    hit = find_duplicate_job("Systemhaus Nord Ltd.", "PLM Architect", "", existing)
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


def test_zeitnaehe_ohne_titel_match_blockt_nicht():
    """#670: Gleiche Firma + Zeitnaehe, aber KEINE Titel-Ueberlappung
    (shared_tokens leer) -> KEIN Duplikat. Vorher (bis beta.86) gab das
    faelschlich eine 'firma_plus_zeitnaehe'-Warnung und blockte das Anlegen.
    """
    t_minus_1h = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    existing = [
        {"hash": "h1", "company": "Foo GmbH",
         "title": "Frontend Developer", "url": "",
         "found_at": t_minus_1h},
    ]
    hit = find_duplicate_job("Foo GmbH", "Marketing Manager", "", existing)
    assert hit is None, "Zeitnaehe allein darf nicht blocken (#670)"


def test_leere_eingaben():
    assert find_duplicate_job("", "Title", "", []) is None
    assert find_duplicate_job("Firma", "", "", []) is None
    assert find_duplicate_job("Firma", "Title", "", []) is None
