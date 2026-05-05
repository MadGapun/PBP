"""Tests fuer v1.7.0-beta.16 — Daten-Quality-Bugfixes (#523, #526, #527)."""
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta16_")
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


# ============= #523 E-Mail-Matching „Im Zweifel unverknuepft" ===============

def test_523_pure_company_in_subject_is_not_enough():
    """Ein Mail mit Firma im Betreff aber FREMDER Domain ergibt KEINEN Match."""
    from bewerbungs_assistent.services.email_service import match_email_to_application
    apps = [{
        "id": "APP-1", "company": "Siemens Energy",
        "title": "PLM Architect", "kontakt_email": "hr@siemens-energy.com",
        "url": "https://siemens-energy.com/jobs/plm-architect",
    }]
    # Mail kommt von einer fremden Domain, hat aber „Siemens Energy" im Betreff
    parsed = {
        "sender": "noreply@bewerbung-tools.de",
        "subject": "Stellenanzeige Siemens Energy weitergeleitet",
        "_direction": "eingang",
    }
    app_id, score = match_email_to_application(parsed, apps)
    assert app_id is None, "Reine Firmen-im-Betreff darf NICHT auto-matchen"
    assert score == 0.0


def test_523_exact_kontakt_email_matches():
    """Wenn Sender genau die kontakt_email ist → Match (Domain-Signal vorhanden)."""
    from bewerbungs_assistent.services.email_service import match_email_to_application
    apps = [{
        "id": "APP-1", "company": "Siemens Energy",
        "kontakt_email": "hr@siemens-energy.com",
    }]
    parsed = {
        "sender": "hr@siemens-energy.com",
        "subject": "RE: Ihre Bewerbung",
        "_direction": "eingang",
    }
    app_id, score = match_email_to_application(parsed, apps)
    assert app_id == "APP-1"
    assert score >= 0.90


def test_523_domain_match_alone_passes_with_fuzzy_company():
    """Sender-Domain enthaelt Firmenname → Domain-Signal + Score >= 0.90."""
    from bewerbungs_assistent.services.email_service import match_email_to_application
    apps = [{
        "id": "APP-1", "company": "Siemens",
        "kontakt_email": "",
        "url": "",
    }]
    parsed = {
        "sender": "recruiting@siemens.com",
        "subject": "Bewerbung",
        "_direction": "eingang",
    }
    app_id, score = match_email_to_application(parsed, apps)
    assert app_id == "APP-1"
    assert score >= 0.90


def test_523_below_threshold_no_match():
    """Knapper Score (z.B. nur Title-Wort-Match) liegt unter 0.90 → kein Match."""
    from bewerbungs_assistent.services.email_service import match_email_to_application
    apps = [{
        "id": "APP-1", "company": "Acme",
        "title": "Senior Software Engineer",
        "kontakt_email": "",
    }]
    parsed = {
        "sender": "noreply@karriere-portal.de",
        "subject": "Senior Software Engineer Position",  # Title in subject
        "_direction": "eingang",
    }
    app_id, score = match_email_to_application(parsed, apps)
    assert app_id is None
    assert score == 0.0


# ============= #526 Bundesagentur URL-Migration ===============

def test_526_legacy_ba_urls_migrated_on_initialize(setup_env):
    """Frische DB ist auf v36 — Migration laeuft bei initialize() durch.
    Wir simulieren den Bestand vor der Migration und triggern manuell."""
    db, _ = setup_env
    conn = db.connect()
    # Stelle mit alter URL einfuegen
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, source, url, is_active) "
        "VALUES ('h1', ?, 'PLM Manager', 'ACME', 'bundesagentur', "
        "'https://www.arbeitsagentur.de/jobsuche/suche?id=12345-BB-67890-S', 1)",
        (db.get_active_profile_id(),)
    )
    conn.commit()
    # Jetzt Migration v35->v36 manuell laufen lassen
    db._migrate(35, 36)
    row = conn.execute("SELECT url FROM jobs WHERE hash='h1'").fetchone()
    assert row["url"] == "https://www.arbeitsagentur.de/jobsuche/jobdetail/12345-BB-67890-S"


def test_526_migration_idempotent(setup_env):
    """Wiederholte Migration v35->v36 zerstoert nichts."""
    db, _ = setup_env
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, source, url, is_active) "
        "VALUES ('h2', ?, 'X', 'Y', 'bundesagentur', "
        "'https://www.arbeitsagentur.de/jobsuche/jobdetail/abc', 1)",
        (db.get_active_profile_id(),)
    )
    conn.commit()
    db._migrate(35, 36)  # bringt nichts mehr
    db._migrate(35, 36)  # noch ein zweites mal
    row = conn.execute("SELECT url FROM jobs WHERE hash='h2'").fetchone()
    assert row["url"] == "https://www.arbeitsagentur.de/jobsuche/jobdetail/abc"


def test_526_only_bundesagentur_affected(setup_env):
    """Andere Quellen mit aehnlichen URLs werden nicht angefasst."""
    db, _ = setup_env
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, source, url, is_active) "
        "VALUES ('h3', ?, 'X', 'Y', 'stepstone', "
        "'https://www.arbeitsagentur.de/jobsuche/suche?id=foo', 1)",
        (db.get_active_profile_id(),)
    )
    conn.commit()
    db._migrate(35, 36)
    row = conn.execute("SELECT url FROM jobs WHERE hash='h3'").fetchone()
    # Source != bundesagentur → unangetastet
    assert "suche?id=foo" in row["url"]


# ============= #527 Freelancermap-Refresh-API ===============

def test_527_refresh_endpoint_empty_pool(setup_env):
    """Wenn keine Freelancermap-Stellen ohne Beschreibung da sind: 0 updates."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/jobs/refresh-freelancermap-descriptions", json={"max": 10})
    assert r.status_code == 200
    j = r.json()
    assert j["updated"] == 0
    assert j["checked"] == 0


def test_527_refresh_endpoint_caps_at_200(setup_env):
    """max-Param wird auf 200 gecappt — Schutz gegen Bestands-Bombing."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # Da pool leer ist, bleibt updated=0; uns interessiert nur dass die
    # Route nicht durchdreht bei riesigem max
    r = client.post("/api/jobs/refresh-freelancermap-descriptions",
                     json={"max": 99999})
    assert r.status_code == 200


def test_527_scraper_detail_limit_lifted_to_75():
    """Kommentar im Scraper bestaetigt Limit-Anhebung von 30 auf 75."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
           / "src" / "bewerbungs_assistent" / "job_scraper" / "freelancermap.py")
    code = src.read_text(encoding="utf-8")
    assert "DETAIL_FETCH_LIMIT = 75" in code
    # Alte Limit-Definition darf nicht mehr aktiv sein
    assert "DETAIL_FETCH_LIMIT = 30" not in code
