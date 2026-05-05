"""Tests fuer v1.7.0-beta.13 — Bug-Fixes & Polish (#518, #578)."""
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta13_")
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


# ============= Follow-up Typ-Hygiene (#518) ===============

def test_518_only_nachfass_triggers_banner(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    aid = db.add_application({"title": "Engineer", "company": "ACME"})
    # Faelliger nachfass — soll Banner ausloesen
    db.add_follow_up(aid, "2024-01-01", follow_up_type="nachfass",
                     template="Hallo, gibt es Neuigkeiten?")
    # Faellige Interview-Erinnerung — soll NICHT Banner ausloesen
    db.add_follow_up(aid, "2024-01-01", follow_up_type="interview_erinnerung",
                     template="Erinnerung: Interview morgen 13:00 Uhr")
    # Faellige Info-Notiz — soll NICHT Banner ausloesen
    db.add_follow_up(aid, "2024-01-01", follow_up_type="info",
                     template="Memo")

    r = client.get("/api/follow-ups")
    assert r.status_code == 200
    j = r.json()
    assert len(j["follow_ups"]) == 3, "Alle 3 Eintraege weiter sichtbar"
    # Aber nur EINER ist banner-faellig
    assert j["faellige"] == 1
    nachfass = [f for f in j["follow_ups"] if f["follow_up_type"] == "nachfass"][0]
    assert nachfass["faellig"] is True
    assert nachfass["banner_typ"] is True
    interview = [f for f in j["follow_ups"] if f["follow_up_type"] == "interview_erinnerung"][0]
    assert interview["faellig"] is False
    assert interview["faellig_datum"] is True  # Datum ja
    assert interview["banner_typ"] is False    # aber kein Banner


def test_518_unknown_type_normalized_to_sonstiges(setup_env):
    db, _ = setup_env
    aid = db.add_application({"title": "T", "company": "C"})
    fid = db.add_follow_up(aid, "2024-01-01", follow_up_type="unbekannt-xyz")
    fu = db.get_follow_up(fid)
    assert fu["follow_up_type"] == "sonstiges"


# ============= CSV-Export (#578) ===============

def test_578_meetings_csv_export(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    aid = db.add_application({"title": "Dev", "company": "ACME"})
    db.add_meeting({
        "application_id": aid,
        "title": "Erstgespraech",
        "meeting_date": "2026-04-22T13:00:00",
        "meeting_type": "interview",
        "location": "Online",
    })
    r = client.get("/api/meetings/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.content.decode("utf-8-sig")  # BOM beruecksichtigen
    assert "Datum/Zeit" in body  # Header
    assert "Erstgespraech" in body
    assert "ACME" in body


def test_578_applications_csv_smoke(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    db.add_application({"title": "Eng", "company": "Foo", "applied_at": "2026-04-01T10:00:00"})
    r = client.get("/api/applications/export.csv")
    assert r.status_code == 200
    body = r.content.decode("utf-8-sig")
    assert "Firma" in body
    assert "Foo" in body
    # Datums-Format DD.MM.YYYY in der CSV
    assert "01.04.2026" in body
