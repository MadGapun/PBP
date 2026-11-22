"""#1432: Funde aus der Generalprobe fuer Videofolge 10.

Testdaten fiktiv, Datenbank isoliert.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

from bewerbungs_assistent.services import auswertung_daten as ad
from bewerbungs_assistent.services import nachweis_daten as nd
from bewerbungs_assistent.services import statistik_erweitert as se
from bewerbungs_assistent.services.bewerbung_status import ANTWORT_DER_FIRMA

HEUTE = "2026-11-21"
WURZEL = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path))
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "t.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Beate Beispiel"})
    yield d
    d.close()


def _app(db, status, tag, ereignisse):
    aid = db.add_application({"title": "Planer", "company": "Musterbau GmbH", "status": status,
                              "applied_at": tag, "source": "stepstone"})
    c = db.connect()
    c.execute("DELETE FROM application_events WHERE application_id=?", (aid,))
    c.execute("UPDATE applications SET status=?, applied_at=? WHERE id=?", (status, tag, aid))
    for s, t in [("beworben", tag)] + ereignisse:
        c.execute("INSERT INTO application_events (application_id,status,event_date,notes) "
                  "VALUES (?,?,?,'')", (aid, s, t))
    c.commit()
    return aid


def _antwort(db):
    return se.zeitliche_kennzahlen(db, apps=db.get_applications())["zeit_bis_erste_reaktion"]


@pytest.mark.parametrize("status", ["abgelaufen", "zurueckgezogen", "dokument"])
def test_keine_antwort_der_firma_zaehlt_nicht(db, status):
    _app(db, "abgelaufen" if status != "zurueckgezogen" else status, "2026-10-01",
         [(status, "2026-10-05")])
    assert _antwort(db)["anzahl"] == 0


def test_spaetere_echte_antwort_zaehlt_mit_ihrem_datum(db):
    _app(db, "interview", "2026-10-01", [("dokument", "2026-10-02"), ("interview", "2026-10-11")])
    erg = _antwort(db)
    assert erg["anzahl"] == 1 and erg["median_tage"] == 10


def test_alte_antwortzeit_zaehlt_abgelaufen_nicht(db):
    _app(db, "abgelaufen", "2026-08-01", [("abgelaufen", "2026-10-01")])
    _app(db, "interview", "2026-10-01", [("eingangsbestaetigung", "2026-10-05"), ("interview", "2026-10-11")])
    quelle = (WURZEL / "src" / "bewerbungs_assistent" / "database.py").read_text(encoding="utf-8")
    assert "'zweitgespraech', 'angebot', 'abgelaufen')" not in quelle
    erg = db.get_extended_stats()["response_times"]
    assert erg["sample_size"] == 1 and erg["average_days"] == 4


def test_nachweis_und_kennzahl_nutzen_dieselbe_liste():
    assert nd.RUECKMELDUNG_STATUS is ANTWORT_DER_FIRMA
    assert set(nd.RUECKMELDUNG_TEXT) == set(ANTWORT_DER_FIRMA)


def test_nachweis_trennt_termine_und_einladungen(db):
    mit = _app(db, "interview", "2026-11-02", [("interview", "2026-11-05")])
    _app(db, "interview", "2026-11-03", [("interview", "2026-11-06")])
    _app(db, "zweitgespraech", "2026-11-03", [("zweitgespraech", "2026-11-07")])
    c = db.connect()
    c.execute("INSERT INTO application_meetings (id,application_id,title,meeting_date,meeting_type,status) "
              "VALUES ('m1',?,'Termin','2026-11-10','vor_ort','durchgefuehrt')", (mit,))
    c.commit()
    k = {x["name"]: x for x in nd.nachweis_daten(db, heute=HEUTE)["kacheln"]}
    assert k["Gesprächstermine"]["wert"] == 1
    assert k["Gesprächstermine"]["hinweis"] == "eingetragen, dazu 2 Einladungen ohne Termin"


def test_auswertung_nennt_einladungen(db):
    aid = _app(db, "interview", "2026-11-02", [("interview", "2026-11-05")])
    c = db.connect()
    c.execute("UPDATE applications SET has_reached_interview=1 WHERE id=?", (aid,))
    c.commit()
    k = {x["name"]: x for x in ad.auswertung_daten(db, heute=HEUTE)["kacheln"]}
    assert "mit Gespräch" not in k
    assert k["eingeladen"]["wert"] == "1" and k["eingeladen"]["hinweis"] == "zum Gespräch, von 1"


def _muster():
    pfad = WURZEL / "docs" / "screenshots" / "musterprofile.py"
    spec = importlib.util.spec_from_file_location("musterprofile_1432", pfad)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


def test_musterprofile_haben_stimmigen_ablauf(db):
    m = _muster()
    m.assert_isolated(db)
    m.seed_all(db)
    m.seed_firmen(db)
    c = db.connect()
    heute = datetime.now().date().isoformat()
    apps = c.execute("SELECT id, applied_at FROM applications WHERE applied_at IS NOT NULL").fetchall()
    assert len(apps) > 20
    for a in apps:
        evs = c.execute("SELECT status, event_date FROM application_events WHERE application_id=? "
                        "ORDER BY event_date", (a["id"],)).fetchall()
        einladung = next((e["event_date"][:10] for e in evs if e["status"] == "interview"), None)
        for e in evs:
            tag = e["event_date"][:10]
            if e["status"] == "abgelaufen":
                assert (datetime.fromisoformat(tag) - datetime.fromisoformat(a["applied_at"][:10])).days >= 42 \
                    or tag == heute
            if e["status"] in ANTWORT_DER_FIRMA and tag != heute:
                assert datetime.fromisoformat(tag).weekday() < 5, (e["status"], tag)
        termine = c.execute("SELECT meeting_date FROM application_meetings WHERE application_id=? "
                            "AND status='durchgefuehrt'", (a["id"],)).fetchall()
        for t in termine:
            assert einladung and t["meeting_date"][:10] >= einladung, (t["meeting_date"], einladung)
