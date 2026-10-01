"""v1.7.146 — Das Ende eines Termins liegt nach dem Beginn (#1140).

Befund (01.10.2026, Prüfung "Zeit und Zwischenspeicher"): Das Kalender-
Formular rechnete Beginn + Dauer und schrieb das Ergebnis mit
`end.toISOString()`, also in UTC. In Deutschland wurde aus "14:00, 60 Minuten"
im Sommer das Ende 13:00 (im Winter 14:00): Ende vor Beginn, ungültige
ICS-Datei, und zwei sich überschneidende Termine (14:00 bis 15:00 und
14:30 bis 15:30) meldeten keine Kollision.

Hier: die Regel (`termin_zeit.ende_korrigieren`), ihre Wirkung beim Anlegen,
Ändern und beim Start (Bestand heilen), die Folgen (ICS, Kollisionen) und die
Wächter für die Oberfläche (keine UTC-Daten mehr für lokale Eingaben).
"""
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import termin_zeit  # noqa: E402


# ══ Die Regel ══════════════════════════════════════════════════════

@pytest.mark.parametrize("beginn,ende,dauer,erwartet,geaendert", [
    # der gemeldete Fall (Sommerzeit: UTC+2 -> Ende 13:00)
    ("2026-10-01T14:00", "2026-10-01T13:00", 60, "2026-10-01T15:00", True),
    # Winter: UTC+1 -> Ende = Beginn
    ("2026-12-01T14:00", "2026-12-01T14:00", 60, "2026-12-01T15:00", True),
    # Dauer als Text, über Mitternacht, krumme Dauer
    ("2026-10-01T14:00", "2026-10-01T13:00", "60", "2026-10-01T15:00", True),
    ("2026-10-01T23:30", "2026-10-01T22:30", 60, "2026-10-02T00:30", True),
    ("2026-10-01T09:15", "2026-10-01T08:15", 45, "2026-10-01T10:00", True),
    # ohne Dauer: lieber leer als falsch
    ("2026-10-01T14:00", "2026-10-01T13:00", None, None, True),
    ("2026-10-01T14:00", "2026-10-01T13:00", 0, None, True),
    ("2026-10-01T14:00", "2026-10-01T13:00", "abc", None, True),
    # ein gültiges Ende bleibt, auch wenn es zur Dauer nicht passt
    ("2026-10-01T14:00", "2026-10-01T15:30", 60, "2026-10-01T15:30", False),
    ("2026-10-01T14:00", "2026-10-01T15:00", None, "2026-10-01T15:00", False),
    # nichts zu prüfen
    ("2026-10-01T14:00", None, 60, None, False),
    ("2026-10-01T14:00", "", 60, "", False),
    ("2026-10-01", "2026-10-01", 60, "2026-10-01", False),          # ganztägig
    ("2026-10-01T14:00", "kein Datum", 60, "kein Datum", False),     # unlesbar: nicht anfassen
])
def test_ende_korrigieren(beginn, ende, dauer, erwartet, geaendert):
    assert termin_zeit.ende_korrigieren(beginn, ende, dauer) == (erwartet, geaendert)


# ══ Anlegen, Ändern, Start ═════════════════════════════════════════

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


def _bewerbung(db):
    return db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                               "status": "beworben"})


def _ende(db, mid):
    return db.connect().execute(
        "SELECT meeting_end FROM application_meetings WHERE id=?", (mid,)).fetchone()[0]


def test_anlegen_mit_utc_ende_speichert_ein_ende_nach_dem_beginn(db):
    """Genau das, was das alte Formular im Sommer schickte."""
    mid = db.add_meeting({"application_id": _bewerbung(db), "title": "Gespräch",
                          "meeting_date": "2030-07-01T14:00", "meeting_end": "2030-07-01T13:00",
                          "duration_minutes": 60})
    assert _ende(db, mid) == "2030-07-01T15:00"


def test_ein_richtiges_ende_bleibt(db):
    mid = db.add_meeting({"application_id": _bewerbung(db), "title": "Gespräch",
                          "meeting_date": "2030-07-01T14:00", "meeting_end": "2030-07-01T15:30",
                          "duration_minutes": 60})
    assert _ende(db, mid) == "2030-07-01T15:30"


def test_anlegen_ohne_ende_bleibt_ohne_ende(db):
    mid = db.add_meeting({"application_id": _bewerbung(db), "title": "Gespräch",
                          "meeting_date": "2030-07-01T14:00", "duration_minutes": 60})
    assert _ende(db, mid) is None


def test_verschieben_zieht_das_ende_mit(db):
    """Wer den Beginn verschiebt und das Ende nicht anfasst, bekommt kein Ende davor."""
    mid = db.add_meeting({"application_id": _bewerbung(db), "title": "Gespräch",
                          "meeting_date": "2030-07-01T14:00", "meeting_end": "2030-07-01T15:00",
                          "duration_minutes": 60})
    assert db.update_meeting(mid, {"meeting_date": "2030-07-07T10:00"})
    assert _ende(db, mid) == "2030-07-07T11:00"


def test_aendern_mit_utc_ende_wird_korrigiert(db):
    mid = db.add_meeting({"application_id": _bewerbung(db), "title": "Gespräch",
                          "meeting_date": "2030-07-01T14:00", "duration_minutes": 60})
    assert db.update_meeting(mid, {"meeting_date": "2030-07-01T16:00",
                                   "meeting_end": "2030-07-01T15:00",
                                   "duration_minutes": 90})
    assert _ende(db, mid) == "2030-07-01T17:30"


def test_aendern_ohne_zeitfelder_laesst_das_ende_in_ruhe(db):
    mid = db.add_meeting({"application_id": _bewerbung(db), "title": "Gespräch",
                          "meeting_date": "2030-07-01T14:00", "meeting_end": "2030-07-01T15:30",
                          "duration_minutes": 60})
    assert db.update_meeting(mid, {"title": "Neuer Titel", "notes": "Zimmer 4"})
    assert _ende(db, mid) == "2030-07-01T15:30"


def test_bestand_wird_beim_start_geheilt_und_der_zweite_lauf_aendert_nichts(db):
    """Termine, die das alte Formular schon gespeichert hat."""
    app = _bewerbung(db)
    sommer = db.add_meeting({"application_id": app, "title": "Sommer",
                             "meeting_date": "2030-07-01T14:00", "duration_minutes": 60})
    winter = db.add_meeting({"application_id": app, "title": "Winter",
                             "meeting_date": "2030-12-01T14:00", "duration_minutes": 60})
    ohne = db.add_meeting({"application_id": app, "title": "Ohne Dauer",
                           "meeting_date": "2030-12-02T14:00"})
    gut = db.add_meeting({"application_id": app, "title": "Gut",
                          "meeting_date": "2030-12-03T14:00", "meeting_end": "2030-12-03T15:00",
                          "duration_minutes": 60})
    con = db.connect()
    con.execute("UPDATE application_meetings SET meeting_end='2030-07-01T13:00' WHERE id=?", (sommer,))
    con.execute("UPDATE application_meetings SET meeting_end='2030-12-01T14:00' WHERE id=?", (winter,))
    con.execute("UPDATE application_meetings SET meeting_end='2030-12-02T13:00' WHERE id=?", (ohne,))
    con.commit()
    erg = db.termine_normalisieren()
    assert erg["ende_korrigiert"] == 3 and erg["unlesbar"] == []
    assert _ende(db, sommer) == "2030-07-01T15:00"
    assert _ende(db, winter) == "2030-12-01T15:00"
    assert _ende(db, ohne) is None, "ohne Dauer bleibt das Ende leer, nicht falsch"
    assert _ende(db, gut) == "2030-12-03T15:00"
    zweiter = db.termine_normalisieren()
    assert zweiter["ende_korrigiert"] == 0 and zweiter["geaendert"] == 0


# ══ Die Folgen: ICS und Kollisionen ════════════════════════════════

def _zeiten(ics):
    """[(DTSTART, DTEND)] je Termin aus dem Kalendertext."""
    paare, start = [], None
    for zeile in ics.splitlines():
        if zeile.startswith("DTSTART:"):
            start = zeile.split(":", 1)[1]
        elif zeile.startswith("DTEND:") and start:
            paare.append((start, zeile.split(":", 1)[1]))
            start = None
    return paare


def test_die_ics_datei_hat_ein_ende_nach_dem_beginn(db):
    con = db.connect()
    mid = db.add_meeting({"application_id": _bewerbung(db), "title": "Gespräch",
                          "meeting_date": "2030-07-01T14:00", "duration_minutes": 60})
    con.execute("UPDATE application_meetings SET meeting_end='2030-07-01T13:00' WHERE id=?", (mid,))
    con.commit()
    db.termine_normalisieren()
    from bewerbungs_assistent.services.ics_service import build_meetings_ics
    ics, anzahl = build_meetings_ics(db)
    assert anzahl == 1
    (start, ende), = _zeiten(ics)
    assert start == "20300701T140000" and ende == "20300701T150000"


@pytest.fixture
def client(db, monkeypatch):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    monkeypatch.setattr(dash, "_db", db)
    monkeypatch.delenv("BA_ERLAUBTE_HOSTS", raising=False)
    monkeypatch.delenv("BA_ERLAUBTE_HERKUENFTE", raising=False)
    return TestClient(dash.app)


def test_zwei_sich_ueberschneidende_termine_melden_eine_kollision(client):
    """Das alte Formular schickte beide Enden in UTC: Ende vor Beginn, keine Kollision."""
    tag = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    for titel, beginn, utc_ende in (("Erstes", "14:00", "13:00"), ("Zweites", "14:30", "13:30")):
        r = client.post("/api/meetings", json={
            "title": titel, "meeting_date": f"{tag}T{beginn}", "meeting_end": f"{tag}T{utc_ende}",
            "duration_minutes": 60, "meeting_type": "sonstiges"})
        assert r.status_code == 200, r.text
    erg = client.get("/api/meetings/calendar").json()
    assert len(erg["meetings"]) == 2
    for m in erg["meetings"]:
        assert m["meeting_end"] > m["meeting_date"], m
    assert len(erg["collisions"]) == 1


def test_zwei_getrennte_termine_melden_keine_kollision(client):
    tag = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    for titel, beginn, utc_ende in (("Erstes", "09:00", "08:00"), ("Zweites", "14:00", "13:00")):
        client.post("/api/meetings", json={
            "title": titel, "meeting_date": f"{tag}T{beginn}", "meeting_end": f"{tag}T{utc_ende}",
            "duration_minutes": 60})
    assert client.get("/api/meetings/calendar").json()["collisions"] == []


# ══ Die Oberfläche: kein UTC mehr für lokale Eingaben ══════════════

FRONTEND = ROOT / "frontend" / "src"
# Dateien, in denen `toISOString().slice(...)` bleiben darf: reine Zeitstempel in
# Dateinamen von Downloads (die Zone ist dort gleichgültig).
ERLAUBT = {"pages/SettingsPage.jsx"}


def test_keine_ortszeit_wird_mehr_aus_utc_geschnitten():
    funde = []
    for pfad in list(FRONTEND.rglob("*.jsx")) + list(FRONTEND.rglob("*.js")):
        rel = pfad.relative_to(FRONTEND).as_posix()
        if rel in ERLAUBT or rel.endswith(".test.mjs"):
            continue
        text = pfad.read_text(encoding="utf-8-sig")
        for nr, zeile in enumerate(text.splitlines(), 1):
            if re.search(r"toISOString\(\)\s*\.slice\(\s*0\s*,\s*(10|16)\s*\)", zeile):
                funde.append(f"{rel}:{nr}")
    assert not funde, ("Ein Datum oder eine Uhrzeit für den Menschen wird aus UTC "
                       "geschnitten (lokaleZeit.js benutzen): " + ", ".join(funde))


def test_das_kalenderformular_rechnet_das_ende_in_ortszeit():
    kalender = (FRONTEND / "pages" / "CalendarPage.jsx").read_text(encoding="utf-8-sig")
    assert "terminEnde(" in kalender and "lokaleDatumZeit(" in kalender


def test_der_node_test_laeuft_in_der_ci():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "node frontend/src/lib/lokaleZeit.test.mjs" in workflow
