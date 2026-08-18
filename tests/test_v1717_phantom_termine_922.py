"""Tests fuer v1.7.17 — #922: Phantom-Termine aus zitierten Mail-Threads.

Belegter Fall 31.07.: der Import EINER Mail mit Antwortverlauf legte
VIER Termine an — die Sendezeiten der zitierten Vorgaengermails, alle
als 'interview' mit 60 Minuten. Folge: vermuellter Kalender,
verfaelschte Aufwands-Statistik und firma_kontext berichtete fuenf
Interviews statt einem. Die Regel "nie aus dem Gedaechtnis, immer aus
PBP" setzt voraus, dass PBP stimmt.
"""
import importlib
import os
import shutil
import tempfile

import pytest

from bewerbungs_assistent.services.email_service import (
    extract_meetings_from_email, hat_termin_beleg, strip_quoted_reply)


# Nachgebaute Mail nach dem Belegfall (fiktive Namen, DoD-9).
MAIL_MIT_ZITAT = """\
Sehr geehrter Herr Mustermann,

anbei wie besprochen der Gehaltsrahmen. Melden Sie sich gern.

Mit freundlichen Gruessen
Erika Musterfrau

Am 28.07.2026 um 17:17 schrieb Erika Musterfrau:
> Vielen Dank fuer das Update.
>
> Am 28.07.2026 um 15:00 schrieb Max Mustermann:
>> Das Interview am 28.07.2026 um 12:00 war sehr aufschlussreich.
"""

MAIL_ECHTE_EINLADUNG = """\
Sehr geehrter Herr Mustermann,

wir laden Sie ein zum Online-Interview am 06.08.2026 um 16:00 Uhr.
Der Teams-Link folgt separat.

Mit freundlichen Gruessen
"""


def test_922_zitat_wird_abgeschnitten():
    eigen = strip_quoted_reply(MAIL_MIT_ZITAT)
    assert "Gehaltsrahmen" in eigen
    assert "17:17" not in eigen and "15:00" not in eigen and "12:00" not in eigen


def test_922_marker_varianten():
    for text in ("Text\n-----Urspruengliche Nachricht-----\nAm 1.1. um 9:00",
                 "Text\nVon: recruiter@example.com\nGesendet: 28.07.2026 17:17",
                 "Text\nOn Mon, Jul 28, 2026 at 5:17 PM, X wrote:\nalt",
                 "Text\n> zitiert um 15:00"):
        eigen = strip_quoted_reply(text)
        assert eigen.strip() == "Text", eigen


def test_922_import_erzeugt_keine_phantom_termine():
    """AK 5: die Beispielmail erzeugt 0 Termine."""
    parsed = {"subject": "AW: PLM Classification Data Lead - Gehaltsrahmen",
              "body_text": MAIL_MIT_ZITAT, "body_html": "", "attachments": []}
    assert extract_meetings_from_email(parsed) == []


def test_922_echte_einladung_wird_weiter_erkannt():
    """Gegenprobe: Terminvokabular im eigenen Text -> Termin bleibt."""
    parsed = {"subject": "Einladung zum Online-Interview",
              "body_text": MAIL_ECHTE_EINLADUNG, "body_html": "",
              "attachments": []}
    meetings = extract_meetings_from_email(parsed)
    assert meetings and meetings[0]["start"], meetings


def test_922_datum_ohne_terminvokabular_erzeugt_nichts():
    """AK 2: eine blosse Datumsangabe im Fliesstext ist kein Termin."""
    parsed = {"subject": "Ihre Bewerbung",
              "body_text": ("Guten Tag,\n\nunsere Rueckmeldung erfolgt "
                            "voraussichtlich am 06.08.2026 um 16:00 Uhr.\n"),
              "body_html": "", "attachments": []}
    # kein Konferenzlink, kein Terminvokabular -> kein Termin
    assert not hat_termin_beleg("unsere Rueckmeldung erfolgt")
    assert extract_meetings_from_email(parsed) == []


# ------------------------------------------------- Bestandsheilung (AK 6)

@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1717_922_")
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


def _termin(db, aid, titel, datum, **extra):
    daten = {"application_id": aid, "meeting_date": datum, "title": titel,
             "meeting_type": "interview"}
    daten.update(extra)
    return db.add_meeting(daten)


def test_922_bestandsheilung_findet_die_vier(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.termin_dubletten import (
        finde_phantom_termine)
    aid = db.add_application({"company": "Vermittler Mitte GmbH",
                              "title": "PLM Lead", "status": "interview"})
    titel = "AW: PLM Classification Data Lead - Gehaltsrahmen"
    for zeit in ("15:00", "17:13", "17:17", "17:47"):
        _termin(db, aid, titel, f"2026-07-28T{zeit}:00")
    # der ECHTE Termin desselben Tages: mit Link und Notizen
    _termin(db, aid, "Online-Interview", "2026-07-28T12:00:00",
            meeting_url="https://teams.example/abc", notes="Teams-Link")

    gruppen = finde_phantom_termine(db)
    assert len(gruppen) == 1, gruppen
    g = gruppen[0]
    assert g["anzahl"] == 4
    assert g["aus_einem_import"] is True
    assert "zitierten" in g["begruendung"]


def test_922_einzelner_betreff_termin_ist_nicht_verdaechtig(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.termin_dubletten import (
        finde_phantom_termine)
    aid = db.add_application({"company": "F", "title": "T",
                              "status": "interview"})
    _termin(db, aid, "Re: Terminbestaetigung", "2026-08-01T10:00:00")
    assert finde_phantom_termine(db) == []


def test_922_termin_mit_beleg_bleibt_unangetastet(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.termin_dubletten import (
        finde_phantom_termine)
    aid = db.add_application({"company": "F", "title": "T",
                              "status": "interview"})
    for zeit in ("10:00", "11:00"):
        _termin(db, aid, "AW: Gespraech", f"2026-08-01T{zeit}:00",
                meeting_url="https://teams.example/x")
    assert finde_phantom_termine(db) == []
