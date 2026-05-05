"""Tests fuer v1.7.0-beta.7 — Bug-Aufraeumung (#518, #526, #527)."""
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta7_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= #518 Follow-up-Typ-Hygiene ===============

def test_518_followup_types_defined(setup_env):
    """FOLLOWUP_TYPES enthaelt erwartete Kategorien inkl. interview_erinnerung."""
    db, _ = setup_env
    types = db.FOLLOWUP_TYPES
    assert "nachfass" in types
    assert "interview_erinnerung" in types
    assert "danke" in types
    assert "info" in types
    assert "sonstiges" in types


def test_518_unknown_type_normalized(setup_env):
    """Unbekannter follow_up_type wird auf 'sonstiges' normalisiert (nicht 'nachfass')."""
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    fid = db.add_follow_up(bid, "2026-06-01", follow_up_type="garbage_invalid")
    conn = db.connect()
    row = conn.execute("SELECT follow_up_type FROM follow_ups WHERE id=?", (fid,)).fetchone()
    assert row["follow_up_type"] == "sonstiges"


def test_518_valid_types_pass_through(setup_env):
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    fid = db.add_follow_up(bid, "2026-06-01", follow_up_type="interview_erinnerung")
    conn = db.connect()
    row = conn.execute("SELECT follow_up_type FROM follow_ups WHERE id=?", (fid,)).fetchone()
    assert row["follow_up_type"] == "interview_erinnerung"


# ============= #526 Bundesagentur URL ===============

def test_526_ba_url_format_check():
    """Code in bundesagentur.py nutzt jobdetail/{ref_nr} statt jobsuche/suche?id=..."""
    from pathlib import Path
    src = Path("src/bewerbungs_assistent/job_scraper/bundesagentur.py").read_text(encoding="utf-8")
    # Neue Form: jobdetail/{ref_nr}
    assert '"url": f"https://www.arbeitsagentur.de/jobsuche/jobdetail/' in src
    # Alte Form sollte weg sein
    assert '"url": f"https://www.arbeitsagentur.de/jobsuche/suche?id=' not in src


# ============= #527 Freelancermap Description ===============

def test_527_freelancermap_detail_fetch_in_code():
    """Code in freelancermap.py hat Detail-Fetch-Logik fuer Beschreibung."""
    from pathlib import Path
    src = Path("src/bewerbungs_assistent/job_scraper/freelancermap.py").read_text(encoding="utf-8")
    # Detail-Fetch-Schleife muss da sein
    assert "DETAIL_FETCH_LIMIT" in src
    # Beschreibung wird gesetzt (nicht nur leer)
    assert "description = txt[:2000]" in src
