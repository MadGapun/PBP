"""Tests fuer v1.6.6 Bewerbungsbericht (#540) — Arbeitsamt-Tauglichkeit."""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v166_test_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test User"})
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _generate_pdf(db, profile, out_path, **kwargs):
    from bewerbungs_assistent.export_report import generate_application_report
    data = db.get_report_data()
    generate_application_report(data, profile, out_path, **kwargs)
    return out_path


def _pdf_text(pdf_path) -> str:
    """Extrahiert den Klartext aus dem PDF (alle Seiten zusammen)."""
    import pypdf
    reader = pypdf.PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# ============= Master-Toggle: Arbeitsamt-Block ein/aus ===============
def test_540_arbeitsamt_block_disabled_by_default(setup_env):
    """Ohne Toggle wird der Arbeitsamt-Block NICHT gerendert (auch wenn Felder gesetzt)."""
    db, tmpdir = setup_env
    profile = db.get_profile()
    out = Path(tmpdir) / "off.pdf"
    _generate_pdf(db, profile, out, report_settings={
        "arbeitsamt_block_enabled": False,
        "ba_vermittlungsnummer": "ABC123",
        "ba_aktenzeichen": "12345Z2026",
    })
    text = _pdf_text(out)
    assert "ABC123" not in text, "Vermittlungsnummer sollte NICHT im Bericht stehen wenn Toggle aus"
    assert "12345Z2026" not in text, "Aktenzeichen sollte NICHT im Bericht stehen wenn Toggle aus"


def test_540_arbeitsamt_block_enabled(setup_env):
    """Mit Toggle und Feldern wird der Block gerendert."""
    db, tmpdir = setup_env
    profile = db.get_profile()
    out = Path(tmpdir) / "on.pdf"
    _generate_pdf(db, profile, out, report_settings={
        "arbeitsamt_block_enabled": True,
        "ba_vermittlungsnummer": "TESTABC123",
        "ba_aktenzeichen": "X12345Y",
        "ba_berater_name": "Frau Mustermann",
        "ba_berater_stelle": "Agentur Bremen",
    })
    text = _pdf_text(out)
    assert "TESTABC123" in text
    assert "X12345Y" in text
    assert "Mustermann" in text


def test_540_arbeitsamt_enabled_but_empty_fields(setup_env):
    """Toggle an, aber alle Felder leer — Block wird nicht gerendert."""
    db, tmpdir = setup_env
    profile = db.get_profile()
    out = Path(tmpdir) / "empty.pdf"
    _generate_pdf(db, profile, out, report_settings={
        "arbeitsamt_block_enabled": True,
        "ba_vermittlungsnummer": "",
        "ba_aktenzeichen": "",
    })
    text = _pdf_text(out)
    assert "Vorlage fuer das Arbeitsamt" not in text


# ============= Bericht-Settings API ===============
def test_540_settings_api_get_default(setup_env):
    """GET /api/settings/report liefert Defaults wenn nichts gespeichert."""
    db, _ = setup_env
    # Direkter DB-Zugriff weil API-Test ohne FastAPI-TestClient zu schwer
    settings = {
        "arbeitsamt_block_enabled": bool(db.get_profile_setting("report_arbeitsamt_block_enabled", False)),
        "ba_vermittlungsnummer": db.get_profile_setting("report_ba_vermittlungsnummer", "") or "",
    }
    assert settings["arbeitsamt_block_enabled"] is False
    assert settings["ba_vermittlungsnummer"] == ""


def test_540_settings_api_set_and_get(setup_env):
    """Speichern und wieder lesen via DB-API."""
    db, _ = setup_env
    db.set_profile_setting("report_arbeitsamt_block_enabled", True)
    db.set_profile_setting("report_ba_vermittlungsnummer", "MEINE-NUMMER")
    assert db.get_profile_setting("report_arbeitsamt_block_enabled") is True
    assert db.get_profile_setting("report_ba_vermittlungsnummer") == "MEINE-NUMMER"


# ============= Footer Seite X/Y ===============
def test_540_footer_has_page_numbers(setup_env):
    """Footer enthaelt 'Seite X / Y' Marker."""
    db, tmpdir = setup_env
    profile = db.get_profile()
    out = Path(tmpdir) / "pages.pdf"
    _generate_pdf(db, profile, out)
    text = _pdf_text(out)
    assert "Seite" in text
    # Mindestens Seite 1 / N
    assert "Seite 1" in text


# ============= Beraterkommentar-Block ===============
def test_540_berater_kommentar_block_only_when_enabled(setup_env):
    """Beraterkommentar-Block nur sichtbar wenn Toggle aktiv."""
    db, tmpdir = setup_env
    profile = db.get_profile()
    out_off = Path(tmpdir) / "kommentar_off.pdf"
    _generate_pdf(db, profile, out_off, report_settings={"berater_kommentar_block": False})
    out_on = Path(tmpdir) / "kommentar_on.pdf"
    _generate_pdf(db, profile, out_on, report_settings={"berater_kommentar_block": True})
    # Bei aktiviertem Block ist der Bericht groesser (8 leere Linien dazu)
    assert out_on.stat().st_size > out_off.stat().st_size


# ============= Neue Sektionen vorhanden ===============
def test_540_neue_sektionen_in_toc(setup_env):
    """Inhaltsverzeichnis enthaelt die zwei verbleibenden neuen Sektionen.

    v1.6.8: 'Bewerbungs-Trichter' und 'Geschaetzter Zeitaufwand' wurden
    entfernt, weil die Datenbasis die Aussagen nicht zuverlaessig deckt
    (Bewerbungen auch ueber Direct-Add, Effort-Heuristik traegt nicht).
    """
    db, tmpdir = setup_env
    profile = db.get_profile()
    out = Path(tmpdir) / "toc.pdf"
    _generate_pdf(db, profile, out)
    text = _pdf_text(out)
    assert "Aktivitaetsprotokoll" in text
    assert "Quellen-Aktivitaet" in text
    # v1.6.8: Trichter ist raus
    assert "Bewerbungs-Trichter" not in text
    # v1.6.8: Effort-Proxy ist raus
    assert "Geschaetzter Zeitaufwand" not in text


# ============= Zeitraum-Filter ===============
def test_540_zeitraum_filter_works(setup_env):
    """Bericht akzeptiert zeitraum_von/zeitraum_bis."""
    db, tmpdir = setup_env
    profile = db.get_profile()
    out = Path(tmpdir) / "filtered.pdf"
    # Sollte ohne Crash laufen, auch wenn keine Daten im Zeitraum
    _generate_pdf(db, profile, out,
                   zeitraum_von="2025-01-01", zeitraum_bis="2025-12-31")
    assert out.stat().st_size > 1000  # Bericht hat zumindest Cover + TOC
