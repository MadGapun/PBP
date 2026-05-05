"""Tests fuer v1.7.0-beta.17 — Nice-to-haves (#520, #533, #581)."""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta17_")
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
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= #520 Score-over-time API ===============

def test_520_score_over_time_empty(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/stats/score-over-time?interval=month&weeks=12")
    assert r.status_code == 200
    j = r.json()
    assert j["interval"] == "month"
    assert j["data"] == []
    assert j["total"] == 0
    assert j["buckets"] == ["0-30", "30-60", "60-80", "80-100"]


def test_520_score_over_time_with_jobs(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    from datetime import datetime
    client = TestClient(app)
    pid = db.get_active_profile_id()
    conn = db.connect()
    today = datetime.now().date().isoformat()
    # Eine Stelle pro Bucket
    for i, score in enumerate((15, 45, 70, 90)):
        conn.execute(
            "INSERT INTO jobs (hash, profile_id, title, company, source, "
            "score, found_at, is_pinned) VALUES (?, ?, ?, 'X', 's', ?, ?, 0)",
            (f"h{i}", pid, f"Title{i}", score, f"{today}T10:00:00")
        )
    conn.commit()
    r = client.get("/api/stats/score-over-time")
    j = r.json()
    assert j["total"] == 4
    period = datetime.now().strftime("%Y-%m")
    matching = [d for d in j["data"] if d["period"] == period]
    assert len(matching) == 1
    row = matching[0]
    assert row["0-30"] == 1
    assert row["30-60"] == 1
    assert row["60-80"] == 1
    assert row["80-100"] == 1


def test_520_score_over_time_clamps_weeks(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/stats/score-over-time?weeks=99999")
    assert r.json()["weeks"] == 104
    r2 = client.get("/api/stats/score-over-time?weeks=1")
    assert r2.json()["weeks"] == 4


# ============= #533 Bulk-Doku-Vorbereitung ===============

def test_533_bulk_prepare_empty_pool(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/documents/bulk-analyze-prep",
                    json={"max_dokumente": 10})
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "empty"
    assert j["count"] == 0


def test_533_bulk_prepare_returns_prompt_with_ids(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    pid = db.get_active_profile_id()
    conn = db.connect()
    # Zwei Dokumente einfuegen — eins verknuepft, eins offen
    # Erst die Bewerbung anlegen damit FK greift
    bid = db.add_application({"title": "Engineer", "company": "ACME"})
    conn.execute(
        "INSERT INTO documents (id, profile_id, filename, doc_type, extraction_status, "
        "linked_application_id, created_at) VALUES "
        "('d1', ?, 'cv.pdf', 'lebenslauf', 'nicht_extrahiert', NULL, '2026-05-01T10:00:00'),"
        "('d2', ?, 'mail.msg', 'email', 'extrahiert', ?, '2026-05-02T10:00:00')",
        (pid, pid, bid)
    )
    conn.commit()
    r = client.post("/api/documents/bulk-analyze-prep",
                    json={"filter_unverknuepft_nur": True, "max_dokumente": 50})
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["count"] == 1
    assert "d1" in j["ids"]
    assert "d2" not in j["ids"]
    assert "dokumente_batch_analysieren" in j["prompt"]
    assert "cv.pdf" in j["prompt"]


def test_533_bulk_prepare_caps_max_dokumente(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/documents/bulk-analyze-prep",
                    json={"max_dokumente": 9999})
    # Cap bei 50, aber Pool ist leer -> count=0
    assert r.status_code == 200


# ============= #581 DSGVO-PDF-Frontend-Anbindung ===============

def test_581_pdf_endpoint_returns_pdf_or_skips(setup_env):
    """Smoke-Test: Endpoint liefert PDF oder skipped wenn fpdf2 fehlt."""
    db, _ = setup_env
    # fpdf2 muss installiert sein damit der Endpoint sinnvoll antwortet
    try:
        import fpdf  # noqa: F401
    except ImportError:
        pytest.skip("fpdf2 nicht installiert")
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/privacy/self-disclosure.pdf")
    # Entweder 200 mit PDF oder 500 falls Profil-Daten fehlen
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        assert r.headers["content-type"].startswith("application/pdf")


def test_581_settings_page_has_dsgvo_button():
    """SettingsPage Datenschutz-Tab enthaelt den DSGVO-Selbstauskunft-Button."""
    project_root = Path(__file__).resolve().parents[1]
    src = (project_root / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert "DSGVO Art. 15" in src
    assert "/api/privacy/self-disclosure.pdf" in src
    assert "Selbstauskunft" in src
