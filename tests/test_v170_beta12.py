"""Tests fuer v1.7.0-beta.12 — Heatmap, Skill-Zeitraeume API, Taetigkeitsbericht (#572, #579, #582)."""
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta12_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
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


# ============= Heatmap (#579) ===============

def test_579_heatmap_empty(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/stats/heatmap?days=90")
    assert r.status_code == 200
    j = r.json()
    assert "data" in j
    assert j["days"] == 90
    assert j["total_active_days"] == 0
    assert j["data"] == []


def test_579_heatmap_with_application(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # Bewerbung mit applied_at heute
    from datetime import datetime
    today = datetime.now().date().isoformat()
    db.add_application({
        "title": "Dev", "company": "ACME",
        "applied_at": today + "T10:00:00",
    })
    r = client.get("/api/stats/heatmap?days=30")
    assert r.status_code == 200
    j = r.json()
    assert j["total_active_days"] >= 1
    days_with_data = [d for d in j["data"] if d["date"] == today]
    assert len(days_with_data) == 1
    assert days_with_data[0]["breakdown"]["applications"] >= 1


def test_579_heatmap_clamps_days(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # zu klein -> wird auf 30 angehoben
    r = client.get("/api/stats/heatmap?days=5")
    assert r.json()["days"] == 30
    # zu gross -> wird auf 730 begrenzt
    r2 = client.get("/api/stats/heatmap?days=99999")
    assert r2.json()["days"] == 730


# ============= Skill-Zeitraeume API (#572) ===============

def test_572_skill_periods_api(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # Skill anlegen
    sid = db.add_skill({"name": "Python", "category": "tech"})
    # Zeitraum hinzufuegen
    r = client.post(f"/api/skills/{sid}/periods", json={
        "start_year": 2018, "end_year": 2024, "level": 4,
        "notes": "Hauptsprache",
    })
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    assert pid
    # Liste
    r2 = client.get(f"/api/skills/{sid}/periods")
    assert r2.status_code == 200
    periods = r2.json()["periods"]
    assert len(periods) == 1
    assert periods[0]["level_at_period"] == 4
    assert periods[0]["start_year"] == 2018
    # Loeschen
    r3 = client.delete(f"/api/skills/periods/{pid}")
    assert r3.status_code == 200
    r4 = client.get(f"/api/skills/{sid}/periods")
    assert r4.json()["periods"] == []


def test_572_delete_unknown_period_404(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.delete("/api/skills/periods/UNKNOWN-ID-123")
    assert r.status_code == 404


# ============= Taetigkeitsbericht-Modus (#582) ===============

def test_582_report_setting_default_off(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/settings/report")
    assert r.status_code == 200
    j = r.json()
    assert j.get("taetigkeitsbericht_mode") is False


def test_582_report_setting_toggle(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/settings/report", json={"taetigkeitsbericht_mode": True})
    assert r.status_code == 200
    j = r.json()
    assert j["gespeichert"]["taetigkeitsbericht_mode"] is True
    r2 = client.get("/api/settings/report")
    assert r2.json()["taetigkeitsbericht_mode"] is True


def test_582_pdf_with_taetigkeitsbericht_mode(setup_env, tmp_path):
    """Smoke-Test: PDF wird mit Modus an erzeugt (Cover-Titel + Sektion 11a)."""
    db, _ = setup_env
    from datetime import datetime
    today = datetime.now().date().isoformat()
    # Daten anlegen damit Aktivitaetsprotokoll greift
    db.add_application({
        "title": "Engineer", "company": "ACME", "status": "beworben",
        "applied_at": today + "T08:00:00",
    })
    report_data = db.get_report_data()
    profile = db.get_profile()
    out = tmp_path / "report.pdf"
    try:
        from bewerbungs_assistent.export_report import generate_application_report
    except ImportError:
        pytest.skip("fpdf2 nicht installiert")
    generate_application_report(
        report_data, profile, out,
        report_settings={"taetigkeitsbericht_mode": True}
    )
    assert out.exists()
    assert out.stat().st_size > 1000
