"""#1102: Termine in einer Form, kommende Termine von heute, Kalenderexport
mit Zeitzone. Zeitzone der Tests: Europe/Berlin (Sommer- und Winterzeit)."""
from __future__ import annotations

import os
from pathlib import Path
import time
from datetime import datetime, timedelta

import pytest


@pytest.fixture(autouse=True)
def berlin(monkeypatch):
    if not hasattr(time, "tzset"):
        pytest.skip("tzset nur unter POSIX")
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Termine"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


# ── Die Form ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("ein, aus", [
    ("2026-04-18 14:00", "2026-04-18T14:00"),
    ("2026-04-18T14:00", "2026-04-18T14:00"),
    ("2026-04-18T14:00:30", "2026-04-18T14:00:30"),
    ("18.04.2026 14:00", "2026-04-18T14:00"),
    ("18.4.2026, 9:05 Uhr", "2026-04-18T09:05"),
    ("2026-04-18", "2026-04-18"),
    ("18.04.2026", "2026-04-18"),
    # Sommerzeit: UTC+2
    ("2026-04-18T12:00:00+00:00", "2026-04-18T14:00"),
    ("2026-04-18T12:00:00Z", "2026-04-18T14:00"),
    # Winterzeit: UTC+1
    ("2026-01-15T12:00:00+00:00", "2026-01-15T13:00"),
])
def test_normalisieren(ein, aus):
    from bewerbungs_assistent.services.termin_zeit import normalisieren
    assert normalisieren(ein) == aus


@pytest.mark.parametrize("ein", ["morgen um drei", "31.02.2026 10:00", "", "2026-13-01"])
def test_unlesbares_wird_abgewiesen(ein):
    from bewerbungs_assistent.services.termin_zeit import normalisieren
    with pytest.raises(ValueError, match="Erlaubt"):
        normalisieren(ein)


# ── AK 1: ein Termin von heute ist kommend ──────────────────────────

def _app(db):
    return db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                               "status": "beworben"})


def test_termin_von_heute_mit_leerzeichen_ist_kommend(db):
    spaeter = datetime.now() + timedelta(hours=2)
    if spaeter.date() != datetime.now().date():
        pytest.skip("kurz vor Mitternacht")
    db.add_meeting({"application_id": _app(db), "title": "Gespräch",
                    "meeting_date": spaeter.strftime("%Y-%m-%d %H:%M")})
    assert [m["title"] for m in db.get_upcoming_meetings()] == ["Gespräch"]


def test_ganztaegiger_termin_von_heute_ist_kommend(db):
    db.add_meeting({"application_id": _app(db), "title": "Probetag",
                    "meeting_date": datetime.now().strftime("%Y-%m-%d")})
    assert [m["title"] for m in db.get_upcoming_meetings()] == ["Probetag"]


def test_vergangener_termin_ist_nicht_kommend(db):
    frueher = datetime.now() - timedelta(hours=2)
    db.add_meeting({"application_id": _app(db), "title": "Vorbei",
                    "meeting_date": frueher.strftime("%Y-%m-%d %H:%M")})
    assert db.get_upcoming_meetings() == []


# ── AK 2: Werkzeug und Dashboard weisen Unlesbares ab ───────────────

def _werkzeug(db, name, args):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1102")
    register_all(mcp, db, logging.getLogger("test.1102"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def test_werkzeug_wandelt_deutsche_form_um(db):
    app = _app(db)
    erg = _werkzeug(db, "meeting_hinzufuegen",
                    {"bewerbung_id": app, "datum": "18.04.2027 14:00"})
    assert erg["status"] == "angelegt", erg
    gespeichert = db.connect().execute(
        "SELECT meeting_date FROM application_meetings").fetchone()[0]
    assert gespeichert == "2027-04-18T14:00"


def test_werkzeug_weist_unlesbares_ab(db):
    erg = _werkzeug(db, "meeting_hinzufuegen",
                    {"bewerbung_id": _app(db), "datum": "naechsten Dienstag"})
    assert "fehler" in erg and "Erlaubt" in erg["fehler"]
    assert db.connect().execute("SELECT COUNT(*) FROM application_meetings").fetchone()[0] == 0


def test_dashboard_weist_unlesbares_ab(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    tc = TestClient(dash.app)
    r = tc.post("/api/meetings", json={"meeting_date": "irgendwann", "title": "X"})
    assert r.status_code == 400
    r = tc.post("/api/meetings", json={"meeting_date": "2027-04-18 14:00", "title": "X"})
    mid = r.json()["id"]
    assert tc.put(f"/api/meetings/{mid}", json={"meeting_date": "bald"}).status_code == 400


def test_mail_import_verliert_nur_den_einen_termin(db):
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    assert dash._termin_aus_mail({"application_id": _app(db), "title": "X",
                                  "meeting_date": "unlesbar"}) is None


def test_jeder_mail_weg_nimmt_den_helfer():
    """Ein direkter add_meeting im Upload-Weg liess bei einer unlesbaren
    Zeit die uebrigen Termine UND den Timeline-Eintrag der Mail fallen."""
    import ast
    quelle = (Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
              / "dashboard.py").read_text(encoding="utf-8-sig")
    baum = ast.parse(quelle)
    direkt = []
    for fn in ast.walk(baum):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name in ("_termin_aus_mail", "api_create_meeting"):
            continue
        for k in ast.walk(fn):
            if (isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
                    and k.func.attr == "add_meeting"):
                direkt.append(fn.name)
    assert not direkt, f"add_meeting ohne _termin_aus_mail: {direkt}"


# ── AK 3 und 4: Kalenderexport ──────────────────────────────────────

def test_einladung_in_utc_steht_im_kalender_richtig(db):
    from bewerbungs_assistent.services.ics_service import build_meetings_ics
    db.add_meeting({"application_id": _app(db), "title": "Einladung",
                    "meeting_date": "2026-04-18T12:00:00+00:00"})
    ics, n = build_meetings_ics(db)
    assert n == 1
    # 14:00 Ortszeit — als Ortszeit geschrieben, wie der Kalender sie liest
    assert "DTSTART:20260418T140000" in ics


def test_zeit_mit_zone_wird_als_utc_geschrieben():
    from bewerbungs_assistent.services.ics_service import _fmt_dt
    assert _fmt_dt("2026-04-18T14:00:00+02:00") == "20260418T120000Z"


def test_ganztaegig_im_kalender():
    from bewerbungs_assistent.services.ics_service import build_meeting_ics
    ics = build_meeting_ics({"id": "t1", "meeting_date": "2026-04-18", "title": "Probetag"})
    assert "DTSTART;VALUE=DATE:20260418" in ics
    assert "DTEND;VALUE=DATE:20260419" in ics


def test_einzel_und_gesamtexport_maskieren_gleich(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.services.ics_service import build_meetings_ics
    app = _app(db)
    mid = db.add_meeting({"application_id": app, "title": "Gespräch; Runde 2, vor Ort",
                          "meeting_date": "2027-04-18 14:00",
                          "location": "Halle 3; Tor 2",
                          "notes": "Zeile eins\nZeile zwei, mit Komma"})
    dash._db = db
    einzel = TestClient(dash.app).get(f"/api/meetings/{mid}/ics").text
    gesamt, _ = build_meetings_ics(db)
    for text in (einzel, gesamt):
        assert "Gespräch\\; Runde 2\\, vor Ort" in text
        assert "LOCATION:Halle 3\\; Tor 2" in text
        assert "Zeile eins\\nZeile zwei" in text.replace("\r\n ", "")
        assert all(len(z.encode()) <= 75 for z in text.split("\r\n"))


# ── AK 5: Bestand ───────────────────────────────────────────────────

def test_bestand_wird_normalisiert_und_zweiter_lauf_aendert_nichts(db):
    mid = db.add_meeting({"application_id": _app(db), "title": "Alt",
                          "meeting_date": "2027-04-18T14:00"})
    kaputt = db.add_meeting({"application_id": _app(db), "title": "Kaputt",
                             "meeting_date": "2027-04-19T10:00"})
    con = db.connect()
    con.execute("UPDATE application_meetings SET meeting_date='2027-04-18 14:00' WHERE id=?", (mid,))
    con.execute("UPDATE application_meetings SET meeting_date='irgendwann' WHERE id=?", (kaputt,))
    con.commit()
    erg = db.termine_normalisieren()
    assert erg["geaendert"] == 1 and erg["unlesbar"] == [kaputt]
    assert con.execute("SELECT meeting_date FROM application_meetings WHERE id=?",
                       (mid,)).fetchone()[0] == "2027-04-18T14:00"
    assert db.termine_normalisieren()["geaendert"] == 0
    assert con.execute("SELECT meeting_date FROM application_meetings WHERE id=?",
                       (kaputt,)).fetchone()[0] == "irgendwann", "Unlesbares geloescht"
