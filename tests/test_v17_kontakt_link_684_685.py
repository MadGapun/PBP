"""Regression-Tests fuer die Beta-Stabilisierung:

- #684: CON-Prefix bei kontakt_verknuepfen wurde nicht akzeptiert, weil IdKind
  kein 'CON' kannte -> parse_id/strip_prefix liessen die ID unveraendert.
- #685: link_contact(target_kind='meeting') fragte die nicht existierende
  Tabelle 'meetings' ab statt 'application_meetings' -> sqlite OperationalError
  ('no such table: meetings').
"""
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_kontaktlink_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_684_con_prefix_parsed_and_stripped():
    """CON-<hex> muss als Kontakt-ID erkannt und entprefixt werden (#684)."""
    from bewerbungs_assistent.services.typed_ids import parse_id, strip_prefix, IdKind
    kind, raw = parse_id("CON-abc12345")
    assert kind is IdKind.CONTACT
    assert raw == "abc12345"
    assert strip_prefix("CON-deadbeef") == "deadbeef"
    # Ohne Prefix bleibt die rohe ID unveraendert
    assert strip_prefix("abc12345") == "abc12345"


def test_685_link_contact_to_meeting(setup_env):
    """link_contact mit target_kind='meeting' darf nicht an
    'no such table: meetings' scheitern (#685)."""
    db = setup_env
    cid = db.add_contact({"full_name": "Recruiter Person"})
    bid = db.add_application({"title": "Stelle", "company": "Firma"})
    mid = db.add_meeting({
        "application_id": bid,
        "title": "Interview",
        "meeting_date": "2026-07-01T10:00:00",
    })

    link_id = db.link_contact(cid, "meeting", mid, role="interviewer")
    assert link_id

    # Kurz-ID des Meetings muss ueber den LIKE-Zweig ebenfalls aufloesen
    link_id2 = db.link_contact(cid, "meeting", mid[:8], role="beobachter")
    assert link_id2


def test_685_link_contact_meeting_not_found(setup_env):
    """Nicht existierendes Meeting liefert eine saubere ValueError-Meldung,
    keinen OperationalError mehr (#685)."""
    db = setup_env
    cid = db.add_contact({"full_name": "X"})
    with pytest.raises(ValueError, match="Meeting nicht gefunden"):
        db.link_contact(cid, "meeting", "ffffffffffff")
