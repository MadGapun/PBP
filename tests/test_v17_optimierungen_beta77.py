"""Tests fuer beta.77-Optimierungen.

Issues:
- #653 (B12): Scraper-URL-Updates ferchau/ingenieur_de + Deprecation monster/solcom
- #654 (B17): Neuer Adzuna-Adapter
- #655 (E14): Doku-Typen-Erweiterung + Per-Typ-Handler-System
"""
from __future__ import annotations

import logging

import pytest


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


# ── #653 (B12) Scraper-URL-Updates ─────────────────────────────────────


def test_b12_ingenieur_de_neuer_url_in_source_registry():
    """#653: ingenieur_de zeigt auf jobs.ingenieur.de Subdomain."""
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    entry = SOURCE_REGISTRY["ingenieur_de"]
    assert entry.get("defekt") is not True  # nicht mehr als defekt markiert
    assert "url_aktualisiert_am" in entry
    assert "jobs.ingenieur.de" in entry["manueller_fallback"]


def test_b12_ferchau_neuer_url_in_source_registry():
    """#653: ferchau zeigt auf touch.ferchau.com."""
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    entry = SOURCE_REGISTRY["ferchau"]
    assert entry.get("defekt") is not True
    assert "url_aktualisiert_am" in entry
    assert "touch.ferchau.com" in entry["manueller_fallback"]


def test_b12_monster_als_deprecated_markiert():
    """#653: monster ist nicht mehr defekt sondern deprecated (Domain weg)."""
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    entry = SOURCE_REGISTRY["monster"]
    assert entry.get("deprecated") is True
    assert "deprecated_grund" in entry
    assert "transitioning" in entry["deprecated_grund"].lower() or "08/2025" in entry["deprecated_grund"]


def test_b12_solcom_als_deprecated_markiert():
    """#653: solcom ist deprecated (Cloudflare-Block dauerhaft)."""
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    entry = SOURCE_REGISTRY["solcom"]
    assert entry.get("deprecated") is True
    assert "cloudflare" in entry["deprecated_grund"].lower()


def test_b12_ingenieur_de_scraper_url_im_code_aktualisiert():
    """#653: ingenieur_de-Scraper-Code benutzt die neue Subdomain."""
    import inspect
    from bewerbungs_assistent.job_scraper import ingenieur_de as ing_mod
    src = inspect.getsource(ing_mod)
    assert "jobs.ingenieur.de" in src


def test_b12_ferchau_scraper_url_im_code_aktualisiert():
    """#653: ferchau-Scraper-Code benutzt die neue Plattform."""
    import inspect
    from bewerbungs_assistent.job_scraper import ferchau as ferchau_mod
    src = inspect.getsource(ferchau_mod)
    assert "touch.ferchau.com" in src


# ── #654 (B17) Adzuna-Adapter ──────────────────────────────────────────


def test_b17_adzuna_skipt_ohne_credentials():
    """#654: Ohne app_id/app_key sofort skip, kein httpx-Aufruf."""
    from bewerbungs_assistent.job_scraper.adzuna import search_adzuna
    # Empty params, kein DB-Setting
    result = search_adzuna({})
    assert result == []


def test_b17_adzuna_in_source_registry():
    """#654: Adzuna ist als Quelle registriert."""
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY, _SCRAPER_MAP
    assert "adzuna" in SOURCE_REGISTRY
    entry = SOURCE_REGISTRY["adzuna"]
    assert entry["api_key_erforderlich"] is True
    assert "adzuna_app_id" in entry["api_key_settings"]
    assert "adzuna_app_key" in entry["api_key_settings"]
    assert "adzuna" in _SCRAPER_MAP


def test_b17_adzuna_process_raw_job_minimal():
    """#654: _process_raw_job mapped Adzuna-Felder korrekt."""
    from bewerbungs_assistent.job_scraper.adzuna import _process_raw_job
    raw = {
        "id": "12345",
        "title": "Senior PLM Consultant",
        "description": "PLM-Beratung in Hamburg",
        "company": {"display_name": "TestFirma AG"},
        "location": {"display_name": "Hamburg, Germany"},
        "redirect_url": "https://www.adzuna.de/details/12345",
        "salary_min": 75000,
        "salary_max": 95000,
        "salary_is_predicted": 0,
    }
    job = _process_raw_job(raw)
    assert job is not None
    assert job["title"] == "Senior PLM Consultant"
    assert job["company"] == "TestFirma AG"
    assert job["location"] == "Hamburg, Germany"
    assert job["url"] == "https://www.adzuna.de/details/12345"
    assert job["source"] == "adzuna"
    assert job["salary_min"] == 75000
    assert job["salary_max"] == 95000
    assert job["adzuna_id"] == "12345"
    assert job["salary_estimated"] == 0


def test_b17_adzuna_process_raw_job_skipt_kurze_titel():
    """#654: Stellen mit zu kurzem Titel werden gefiltert."""
    from bewerbungs_assistent.job_scraper.adzuna import _process_raw_job
    assert _process_raw_job({"id": "1", "title": "Hi"}) is None
    assert _process_raw_job({"id": "2", "title": ""}) is None


def test_b17_adzuna_credentials_aus_params():
    """#654: Credentials werden aus params honoriert (fuer Tests)."""
    from bewerbungs_assistent.job_scraper.adzuna import _get_credentials
    creds = _get_credentials({
        "adzuna_app_id": "test_id",
        "adzuna_app_key": "test_key",
    })
    assert creds == ("test_id", "test_key")


# ── #655 (E14) Doku-Typen-Erweiterung ──────────────────────────────────


def test_e14_neue_doctypes_filename_interview_bestaetigung():
    """#655: 'Confidential - Interview confirmation' -> interview_bestaetigung."""
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type(
        "Confidential - Interview confirmation - 24_04 - 13.00 CET.eml", ""
    ) == "interview_bestaetigung"


def test_e14_neue_doctypes_filename_projekt_update():
    """#655: 'Update zum Projekt ...' -> projekt_update."""
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type(
        "Update zum Projekt_ Lead Business Analyst PLM Teamcenter.eml", ""
    ) == "projekt_update"
    assert _detect_doc_type(
        "Zwischenfeedback.eml", ""
    ) == "projekt_update"


def test_e14_neue_doctypes_filename_gespraechs_feedback():
    """#655: 'Persoenliche Rueckmeldung zum Projekt' -> gespraechs_feedback."""
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type(
        "Persoenliche Rueckmeldung zum Projekt Interim CAD-PLM Transformation.eml", ""
    ) == "gespraechs_feedback"


def test_e14_content_based_interview_bestaetigung():
    """#655: Content-Marker 'der Termin findet statt am' -> interview_bestaetigung."""
    from bewerbungs_assistent.dashboard import _detect_doc_type
    body = (
        "Hallo Markus, der Termin findet statt am 24.04. um 13:00 Uhr. "
        "Bitte bestaetige kurz. Liebe Gruesse, Anna."
    )
    assert _detect_doc_type("Mail.eml", body) == "interview_bestaetigung"


def test_e14_known_types_enthaelt_alle_neuen():
    """#655: KNOWN_TYPES enthaelt die 4 neuen Typen aus dem Reality-Check."""
    from bewerbungs_assistent.services.document_handlers import KNOWN_TYPES
    for t in ("interview_bestaetigung", "projekt_update",
              "gespraechs_feedback", "vermittler_korrespondenz"):
        assert t in KNOWN_TYPES, f"{t} fehlt in KNOWN_TYPES"


def test_e14_handle_doc_recruiter_anfrage_extrahiert_email():
    """#655: handle_doc fuer recruiter_anfrage extrahiert Kontakt-Email."""
    from bewerbungs_assistent.services.document_handlers import handle_doc
    info = handle_doc({
        "doc_type": "recruiter_anfrage",
        "extracted_text": (
            "Hallo Herr Birzite, ich habe eine spannende Vakanz fuer Sie. "
            "Bitte melden Sie sich unter recruiter@firma.de oder "
            "+49 89 12345-678. Beste Gruesse, Test Recruiter."
        ),
    })
    assert info["typ"] == "recruiter_anfrage"
    assert "recruiter@firma.de" in info["fields"]["kontakt_emails"]
    assert info["fields"]["kontakt_telefon"] is not None


def test_e14_handle_doc_interview_einladung_extrahiert_termin():
    """#655: handle_doc fuer interview_einladung erkennt Datum/Zeit/Plattform."""
    from bewerbungs_assistent.services.document_handlers import handle_doc
    info = handle_doc({
        "doc_type": "interview_einladung",
        "extracted_text": (
            "Wir wuerden gerne am 19.05.2026 um 11:00 Uhr ein Zoom-Call "
            "mit Ihnen fuehren. Bitte bestaetigen Sie den Termin."
        ),
    })
    assert info["fields"]["moegliches_datum"] is not None
    assert "11:00" in (info["fields"]["moegliche_uhrzeit"] or "")
    assert (info["fields"]["platform"] or "").lower() == "zoom"


def test_e14_handle_doc_gespraechs_feedback_signal():
    """#655: handle_doc fuer gespraechs_feedback erkennt positives Signal."""
    from bewerbungs_assistent.services.document_handlers import handle_doc
    info = handle_doc({
        "doc_type": "gespraechs_feedback",
        "extracted_text": (
            "Hallo Markus, von meiner Seite passt das alles soweit. "
            "Sehr interessant, was Sie gemacht haben. Wir freuen uns "
            "auf die naechste Runde."
        ),
    })
    assert info["fields"]["tendenz"] == "positiv"
    assert info["fields"]["positiv_marker"] >= 2


def test_e14_handle_doc_unknown_type_fallback():
    """#655: handle_doc fuer unbekannten Typ liefert sonstiges-Standardantwort."""
    from bewerbungs_assistent.services.document_handlers import handle_doc
    info = handle_doc({"doc_type": "irgendwas_neues", "extracted_text": "x"})
    assert info["typ"] == "irgendwas_neues"
    assert info["beschreibung"] == "Nicht klassifiziertes Dokument"
    assert info["fields"] == {}


def test_e14_mcp_tool_dokument_typen_anzeigen(tmp_db):
    """#655: dokument_typen_anzeigen liefert Typ-Liste + Verteilung."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.add_document({
        "filename": "test_cv.pdf",
        "doc_type": "lebenslauf",
        "extracted_text": "Test " * 100,
    })
    tmp_db.add_document({
        "filename": "test_recruiter.eml",
        "doc_type": "recruiter_anfrage",
        "extracted_text": "Test " * 100,
    })

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import dokumente as dok_mod
    dok_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["dokument_typen_anzeigen"]()
    assert "typen" in res
    assert res["anzahl_typen"] >= 20  # KNOWN_TYPES hat 20+ Eintraege
    # Verteilung enthaelt unsere Test-Docs
    assert res["gesamt_dokumente"] >= 2
    lebenslauf_entry = next(
        (t for t in res["typen"] if t["typ"] == "lebenslauf"), None
    )
    assert lebenslauf_entry is not None
    assert lebenslauf_entry["dokumente_in_db"] >= 1


def test_e14_mcp_tool_dokument_typen_anzeigen_ohne_verteilung(tmp_db):
    """#655: Mit mit_verteilung=False kommt nur die Typ-Liste."""
    tmp_db.create_profile("Test User", "test@example.com")
    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import dokumente as dok_mod
    dok_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["dokument_typen_anzeigen"](mit_verteilung=False)
    assert "typen" in res
    assert "gesamt_dokumente" not in res
    assert "dokumente_in_db" not in res["typen"][0]
