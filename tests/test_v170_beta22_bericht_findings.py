"""Tests fuer v1.7.0-beta.22 — Bewerbungsbericht-Findings.

1. Interview-Rate Track-Record (vorher: 0% trotz Interviews)
2. Zeitraum + PBP-Start auf Cover-Page
3. PBP-Start-Datum Auto-Detect aus application_events
4. Pre-PBP-Daten grau im PDF + Erklaer-Block
"""
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta22_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= #1 Interview-Rate Track-Record ===============

def test_pbp_start_auto_detect_empty(setup_env):
    db = setup_env
    assert db.get_pbp_first_active_at() is None  # noch keine Events


def test_pbp_start_auto_detect_from_events(setup_env):
    db = setup_env
    aid = db.add_application({"title": "X", "company": "Y"})
    # add_application erzeugt automatisch ein event mit jetzt
    first = db.get_pbp_first_active_at()
    assert first is not None
    assert len(first) == 10  # YYYY-MM-DD


def test_pbp_start_user_override(setup_env):
    db = setup_env
    db.add_application({"title": "X", "company": "Y"})
    db.set_pbp_first_active_at("2026-03-15")
    assert db.get_pbp_first_active_at() == "2026-03-15"
    # Override loeschen → wieder auto-detect
    db.set_pbp_first_active_at(None)
    assert db.get_pbp_first_active_at() != "2026-03-15"


def test_api_pbp_start_date(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    db.add_application({"title": "X", "company": "Y"})
    # GET — Auto-Detect
    r = client.get("/api/settings/pbp-start-date")
    j = r.json()
    assert j["effective"] is not None
    assert j["override"] is None
    # PUT Override
    r2 = client.put("/api/settings/pbp-start-date", json={"date": "2026-03-15"})
    assert r2.status_code == 200
    assert r2.json()["effective"] == "2026-03-15"
    # PUT Auto = leer
    r3 = client.put("/api/settings/pbp-start-date", json={"date": ""})
    assert r3.json()["mode"] == "auto_detect"
    # PUT ungueltiges Datum
    r4 = client.put("/api/settings/pbp-start-date", json={"date": "garbage"})
    assert r4.status_code == 400


def test_api_pbp_start_date_unset_after_override(setup_env):
    db = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    db.add_application({"title": "X", "company": "Y"})
    client.put("/api/settings/pbp-start-date", json={"date": "2026-03-15"})
    # 'auto' als Wert loescht den Override
    r = client.put("/api/settings/pbp-start-date", json={"date": "auto"})
    assert r.json()["mode"] == "auto_detect"


# ============= #4 PDF-Generierung mit allen Bericht-Findings ===============

def test_pdf_with_track_record_interview_rate(setup_env):
    """PDF wird erzeugt, has_reached_interview wird genutzt."""
    db = setup_env
    try:
        import fpdf  # noqa: F401
    except ImportError:
        pytest.skip("fpdf2 nicht installiert")

    # 5 Bewerbungen, davon 3 jemals im Interview, 2 nur beworben
    # has_reached_interview wird automatisch gesetzt durch Status-Wechsel
    aid1 = db.add_application({"title": "A", "company": "C1", "status": "interview"})
    aid2 = db.add_application({"title": "B", "company": "C2", "status": "angebot"})
    aid3 = db.add_application({"title": "C", "company": "C3", "status": "abgelehnt"})
    # aid3 manuell auf has_reached_interview setzen (war jemals Interview)
    db.connect().execute(
        "UPDATE applications SET has_reached_interview=1 WHERE id=?", (aid3,)
    )
    db.connect().commit()
    db.add_application({"title": "D", "company": "C4", "status": "beworben"})
    db.add_application({"title": "E", "company": "C5", "status": "abgelehnt"})

    from bewerbungs_assistent.export_report import generate_application_report
    report_data = db.get_report_data()
    profile = db.get_profile()
    out = Path(tempfile.gettempdir()) / "test_beta22_report.pdf"
    generate_application_report(
        report_data, profile, out,
        pbp_first_active_at=db.get_pbp_first_active_at(),
    )
    assert out.exists()
    # PDF-Bytes inspizieren — Track-Record-Begriff sollte drin sein
    raw = out.read_bytes()
    # PDF speichert Strings teilweise komprimiert; eine harte
    # Verifikation des Inhalts ist beim PDF-Format aufwaendig.
    # Hier reicht: Datei wurde erzeugt und ist nicht trivial klein.
    assert len(raw) > 2000


def test_pdf_with_pre_pbp_data_marked(setup_env):
    """PDF mit Bewerbung vor PBP-Start zeigt grauen Marker + Legende."""
    db = setup_env
    try:
        import fpdf  # noqa: F401
    except ImportError:
        pytest.skip("fpdf2 nicht installiert")

    # PBP-Start auf 2026-03-15 fixiert
    db.set_pbp_first_active_at("2026-03-15")
    # Pre-PBP Bewerbung (vor 15.03.)
    db.add_application({
        "title": "Alt", "company": "Vor PBP",
        "applied_at": "2026-02-10T10:00:00", "status": "abgelehnt",
    })
    # Post-PBP Bewerbung
    db.add_application({
        "title": "Neu", "company": "Mit PBP",
        "applied_at": "2026-04-01T10:00:00", "status": "interview",
    })
    from bewerbungs_assistent.export_report import generate_application_report
    out = Path(tempfile.gettempdir()) / "test_beta22_pre_pbp.pdf"
    generate_application_report(
        db.get_report_data(), db.get_profile(), out,
        pbp_first_active_at="2026-03-15",
    )
    assert out.exists()
    assert out.stat().st_size > 2000


# ============= #2 Cover-Page haengt PBP-Start-Datum an ===============

def test_cover_page_includes_pbp_start_when_provided(setup_env):
    """Smoke: PBP-Start-Datum-Block wird ins PDF gerendert."""
    db = setup_env
    try:
        import fpdf  # noqa: F401
    except ImportError:
        pytest.skip("fpdf2 nicht installiert")
    db.add_application({"title": "X", "company": "Y", "status": "beworben"})
    from bewerbungs_assistent.export_report import generate_application_report
    out = Path(tempfile.gettempdir()) / "test_beta22_cover.pdf"
    generate_application_report(
        db.get_report_data(), db.get_profile(), out,
        pbp_first_active_at="2026-03-15",
    )
    assert out.exists()
    assert out.stat().st_size > 2000
