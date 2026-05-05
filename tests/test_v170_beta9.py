"""Tests fuer v1.7.0-beta.9 — CSV-Export (#578) + DSGVO-Selbstauskunft (#581)."""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta9_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test", "email": "test@example.com"})
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= #578 CSV-Export ===============

def test_578_csv_response_helper_has_bom():
    """_csv_response setzt UTF-8-BOM (Excel-Kompatibilitaet)."""
    from bewerbungs_assistent.dashboard import _csv_response
    rows = [{"name": "Max", "email": "max@x.de"}]
    cols = [("Name", "name"), ("E-Mail", "email")]
    response = _csv_response(rows, cols, "test.csv")
    body = response.body.decode("utf-8")
    assert body.startswith("﻿")  # UTF-8-BOM
    assert "Max" in body
    assert "Name,E-Mail" in body


def test_578_csv_handles_empty_rows():
    from bewerbungs_assistent.dashboard import _csv_response
    response = _csv_response([], [("ID", "id")], "empty.csv")
    body = response.body.decode("utf-8")
    assert body.startswith("﻿")
    assert "ID" in body  # Header bleibt


def test_578_csv_german_date_format():
    """Datums-Felder werden als DD.MM.YYYY geliefert."""
    from bewerbungs_assistent.dashboard import _csv_response
    rows = [{"applied_at": "2026-05-05T10:00:00"}]
    response = _csv_response(rows, [("Beworben", "applied_at")], "test.csv")
    body = response.body.decode("utf-8")
    assert "05.05.2026" in body


# ============= #581 DSGVO-PDF ===============

def test_581_self_disclosure_pdf_creates(setup_env):
    db, tmpdir = setup_env
    from bewerbungs_assistent.export_report import generate_data_self_disclosure
    out = Path(tmpdir) / "auskunft.pdf"
    generate_data_self_disclosure(db, db.get_profile(), out)
    assert out.exists()
    assert out.stat().st_size > 1000  # Mindestens Cover + Sektionen


def test_581_self_disclosure_contains_user_data(setup_env):
    """PDF enthaelt User-Namen und Profildaten."""
    db, tmpdir = setup_env
    from bewerbungs_assistent.export_report import generate_data_self_disclosure
    out = Path(tmpdir) / "auskunft.pdf"
    generate_data_self_disclosure(db, db.get_profile(), out)
    import pypdf
    text = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(str(out)).pages)
    assert "Test" in text  # Name aus dem Profil
    assert "Datenauskunft" in text
    assert "DSGVO" in text


def test_581_works_without_profile(setup_env):
    """PDF laesst sich auch ohne Profil erstellen (Fallback-Text)."""
    db, tmpdir = setup_env
    from bewerbungs_assistent.export_report import generate_data_self_disclosure
    out = Path(tmpdir) / "auskunft_noprofile.pdf"
    generate_data_self_disclosure(db, None, out)
    assert out.exists()
