"""Tests fuer v1.7.12 — #823 (F37): Elwosa-Inhaltskanaele.

Elwosa redete ueber Jahreszeiten, waehrend PBP wusste, dass eine Quelle
versiegt war und eine Stelle ohne Anker im Bestand lag. Die Kanaele
liefern, was in die #822-Slots gehoert — kein Kanal postet an der
Engine vorbei.
"""
import importlib
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_823_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _ruhezeit_aus(db):
    h = datetime.now().hour
    db.set_profile_setting("elwosa_ruhezeit", f"{(h + 2) % 24}-{(h + 3) % 24}")


# --------------------------------------------------------- Link-Felder

def test_823_link_felder_werden_gespeichert_und_geliefert(setup_env):
    db, _ = setup_env
    mid = db.add_elwosa_message(
        content="Testlinie mit Verweis.", trigger_kind="betriebslage",
        link_url="pbp://tab/stellen", link_label="Stellen ansehen")
    msgs = db.get_elwosa_messages(limit=5)
    m = next(x for x in msgs if x["id"] == mid)
    assert m["link_url"] == "pbp://tab/stellen"
    assert m["link_label"] == "Stellen ansehen"


# ------------------------------------------------------------ Changelog

def test_823_changelog_kandidat_aus_neuester_version(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.elwosa_provider import (
        changelog_kandidaten)
    kand = changelog_kandidaten(db)
    assert kand, "CHANGELOG.md hat immer eine neueste Version"
    c = kand[0]
    assert c.trigger_kind == "changelog"
    assert c.trigger_ref, "Versionsnummer als trigger_ref"
    assert c.link_url.startswith("https://github.com/")
    assert len(c.content) <= 280


def test_823_changelog_max_drei_linien_je_version(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.elwosa_provider import (
        changelog_kandidaten, changelog_gemeldet)
    version = changelog_kandidaten(db)[0].trigger_ref
    for _ in range(3):
        changelog_gemeldet(db, version)
    assert changelog_kandidaten(db) == [], \
        "nach 3 gemeldeten Linien ist die Version durch"


def test_823_changelog_neue_version_setzt_zaehler_zurueck(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.elwosa_provider import (
        changelog_kandidaten, changelog_gemeldet)
    for _ in range(3):
        changelog_gemeldet(db, "0.0.1-alt")
    # Andere (aktuelle) Version im Changelog -> Zaehler zaehlt neu
    assert changelog_kandidaten(db), \
        "Versionswechsel muss den Kanal wieder oeffnen"


# ---------------------------------------------------------- Betriebslage

def test_823_betriebslage_meldet_quelle_versiegt(setup_env):
    db, _ = setup_env
    conn = db.connect()
    conn.execute(
        "INSERT INTO scraper_health (scraper_name, last_run, "
        "consecutive_silent, consecutive_failures, total_successes) "
        "VALUES ('demoquelle', '2026-08-01', 4, 0, 50)")
    conn.commit()
    from bewerbungs_assistent.services.elwosa_provider import (
        betriebslage_kandidaten)
    kand = betriebslage_kandidaten(db)
    versiegt = [c for c in kand if c.dedup_key.startswith("quelle_versiegt")]
    assert versiegt, kand
    assert "demoquelle" in versiegt[0].content
    assert versiegt[0].prioritaet == 0, "Betriebslage ist Ereignis-Klasse"


def test_823_post_candidate_respektiert_sperren(setup_env):
    db, _ = setup_env
    _ruhezeit_aus(db)
    from bewerbungs_assistent.services import elwosa
    from bewerbungs_assistent.services.elwosa_provider import Candidate
    cand = Candidate(content="Eine Quelle liefert nichts mehr. Vermerkt.",
                     trigger_kind="betriebslage",
                     dedup_key="test:1")
    mid = elwosa.post_candidate(db, cand)
    assert mid, "erster Post muss durchgehen"
    # Cooldown umgehen, dann: gleicher Inhalt binnen 7 Tagen -> gesperrt
    alt = (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()
    conn = db.connect()
    conn.execute("UPDATE elwosa_messages SET created_at=? WHERE id=?",
                 (alt, mid))
    conn.commit()
    assert elwosa.post_candidate(db, cand) is None, \
        "derselbe Befund kommt nicht taeglich wieder"


def test_823_post_candidate_validiert_sprach_dna(setup_env):
    db, _ = setup_env
    _ruhezeit_aus(db)
    from bewerbungs_assistent.services import elwosa
    from bewerbungs_assistent.services.elwosa_provider import Candidate
    cand = Candidate(content="Tolle Neuigkeiten!!! 🎉",
                     trigger_kind="betriebslage", dedup_key="x")
    assert elwosa.post_candidate(db, cand) is None, \
        "Ausrufezeichen/Emoji verletzen die Sprach-DNA"


# ------------------------------------------------------ Rueckschlag-Sperre

def test_823_nach_absage_keine_stimmungslinien(setup_env):
    db, _ = setup_env
    _ruhezeit_aus(db)
    from bewerbungs_assistent.services import elwosa
    aid = db.add_application({"company": "Firma X", "title": "Rolle",
                              "status": "beworben"})
    db.update_application_status(aid, "abgelehnt")
    assert elwosa.speak(db, "holiday_summer", ctx={}) is None, \
        "24 h nach einer Absage keine Sommerloch-Pointen"
    assert elwosa.speak(db, "easter_egg",
                        ctx={"egg_id": "irgendwas"}) is None
    # Ereignis-Trigger bleiben erlaubt (die Absage selbst kommentieren)
    mid = elwosa.speak(db, "auto_dismiss_ran", ctx={"count": 2})
    assert mid, "Ereignis-Trigger sind von der Sperre ausgenommen"


# ------------------------------------------------- Tip-Dismiss-Teilung

def test_823_tip_dismiss_wirkt_auf_hint(setup_env):
    """Linie im Stream abweisen = Onboarding-Hint abweisen (geteilter
    Zustand, beide Richtungen)."""
    db, _ = setup_env
    from bewerbungs_assistent.services.onboarding_hints import (
        _get_dismissed)
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)

    mid = db.add_elwosa_message(
        content="Termine vorhanden, aber nie Aufwand erfasst. Vermerkt.",
        trigger_kind="tip", trigger_ref="g11_aufwand_tracken")
    r = client.delete(f"/api/elwosa/messages/{mid}")
    assert r.status_code == 200
    assert "g11_aufwand_tracken" in _get_dismissed(db), \
        "Dismiss im Stream muss den Hint mit abweisen"
