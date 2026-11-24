"""#798 Stufe 2: der Datenkern `bericht_daten`. Testdaten fiktiv, DB isoliert."""
from __future__ import annotations

import pytest

from bewerbungs_assistent.services import bericht_daten as bd
from bewerbungs_assistent.services import bericht_zeitraum as bz

HEUTE = "2026-11-21"


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


def _app(db, status, tag, gespraech=False, source="stepstone"):
    aid = db.add_application({"title": "Planer", "company": "Musterfirma GmbH",
                              "status": status, "applied_at": tag, "source": source})
    c = db.connect()
    c.execute("UPDATE applications SET has_reached_interview=?, applied_at=?, status=?, source=? "
              "WHERE id=?", (1 if gespraech else 0, tag, status, source, aid))
    c.commit()
    return aid


@pytest.mark.parametrize("n,basis,text,wert", [
    (1, 1, "1 von 1", None), (3, 9, "3 von 9", None), (3, 12, "25,0 % (3 von 12)", 25.0),
])
def test_kleine_fallzahlen_nennen_anzahlen_statt_prozent(n, basis, text, wert):
    k = bd.anteil(n, basis)
    assert (k["text"], k["wert"]) == (text, wert)


def test_ohne_basis_ist_der_zustand_unbekannt():
    k = bd.anteil(0, 0)
    assert k["zustand"] == "unbekannt" and k["wert"] is None and k["text"] == "noch keine Angabe"


def test_median_erst_ab_drei_faellen_mit_anzahl_und_spanne():
    assert bd.dauer({"anzahl": 0})["text"] == "noch keine Angabe"
    zwei = bd.dauer({"anzahl": 2, "median_tage": 5.0, "min_tage": 4.0, "max_tage": 6.0})
    assert zwei["zustand"] == "unbekannt" and zwei["text"] == "noch keine Angabe (erst 2 Fälle)"
    drei = bd.dauer({"anzahl": 3, "median_tage": 5.0, "min_tage": 2.0, "max_tage": 9.5})
    assert drei["wert"] == 5.0 and drei["spanne"] == [2.0, 9.5]
    assert drei["text"] == "5 Tage (Median aus 3 Fällen, 2 bis 9,5 Tage)"


@pytest.mark.parametrize("von,bis,art,n", [
    ("2026-01-15", "2026-12-20", "monat", 12),
    ("2026-01-01", "2027-01-31", "quartal", 5),
    ("2021-01-01", "2025-12-31", "quartal", 20),
    ("2020-01-01", "2026-06-30", "jahr", 7),
])
def test_zeitachse_waehlt_die_einheit_und_laesst_luecken_stehen(von, bis, art, n):
    a = bd.zeitachse([{"applied_at": von, "has_reached_interview": 1}], von, bis)
    assert a["art"] == art and len(a["abschnitte"]) == n
    assert sum(x["bewerbungen"] for x in a["abschnitte"]) == 1
    assert sum(x["gespraeche"] for x in a["abschnitte"]) == 1
    assert sum(1 for x in a["abschnitte"] if x["bewerbungen"] == 0) == n - 1


def test_lange_listen_nennen_den_rest():
    b = bd.begrenzt(list(range(10)))
    assert len(b["zeilen"]) == 7 and b["weitere"] == 3 and b["weitere_text"] == "und 3 weitere"
    assert bd.begrenzt([1])["weitere_text"] == ""


def test_datenluecke_ist_eine_eigene_zeile_am_ende():
    apps = [{"source": "stepstone"}, {"source": ""}, {"source": ""}, {"source": ""}]
    w = bd.wege(apps)
    assert [z["weg"] for z in w["zeilen"]] == ["Portale", "Weg nicht erfasst"]
    assert w["zeilen"][-1]["luecke"] and "kein Ergebnis" in w["luecke_satz"]


def test_zeitraum_und_stichtag_getrennt(db):
    _app(db, "beworben", "2026-10-05")                 # laeuft aus frueher
    _app(db, "beworben", "2026-11-03", gespraech=True)
    _app(db, "abgelehnt", "2026-11-04", gespraech=True)
    _app(db, "abgelaufen", "2026-11-05")
    _app(db, "angebot", "2026-11-06", gespraech=True)
    _app(db, "abgelehnt", "2026-09-01")                # ausserhalb
    d = bd.bericht_daten(db, "2026-11-01", "2026-11-30", heute=HEUTE)
    k = d["kennzahlen"]
    assert k["bewerbungen"]["wert"] == 4 and k["bewerbungen"]["bezug"] == bd.IM_ZEITRAUM
    assert k["mit_gespraech"]["text"] == "3 von 4"
    assert k["angebote"]["text"] == "1 von 4" and k["absagen"]["text"] == "1 von 4"
    assert k["versandet"]["text"] == "1 von 4"
    assert k["laufen"]["bezug"] == bd.AM_STICHTAG and k["laufen"]["wert"] == 3
    assert k["laufen_aus_frueher"]["wert"] == 1
    assert d["zeitraum"]["stichtag"] == HEUTE and d["zeitraum"]["text"] == "01.11.2026 bis 30.11.2026"
    assert d["absagen"]["nach_gespraech"]["text"] == "1 von 1"


def test_quoten_stimmen_mit_der_einen_rechnung_ueberein(db):
    for i in range(12):
        _app(db, "abgelehnt" if i < 3 else "beworben", f"2026-11-{i + 1:02d}", gespraech=i < 6)
    d = bd.bericht_daten(db, "2026-11-01", "2026-11-30", heute=HEUTE)
    q = bz.quoten_fuer(db, [a for a in db.get_applications()])
    assert d["kennzahlen"]["mit_gespraech"]["wert"] == q["interview_rate"] == 50.0
    assert d["kennzahlen"]["absagen"]["wert"] == q["rejection_rate"] == 25.0


def test_nachgetragene_zaehlen_bei_anzahlen_nicht_bei_dauer(db, monkeypatch):
    alt = _app(db, "abgelehnt", "2026-03-01")
    neu = _app(db, "abgelehnt", "2026-11-02")
    c = db.connect()
    for aid, a, b in ((alt, "2026-03-01", "2026-03-11"), (neu, "2026-11-02", "2026-11-05")):
        c.execute("DELETE FROM application_events WHERE application_id=?", (aid,))
        c.execute("INSERT INTO application_events (application_id,status,event_date,notes) "
                  "VALUES (?,?,?,'')", (aid, "beworben", a))
        c.execute("INSERT INTO application_events (application_id,status,event_date,notes) "
                  "VALUES (?,?,?,'')", (aid, "abgelehnt", b))
    c.commit()
    monkeypatch.setattr(db, "get_pbp_first_active_at", lambda: "2026-10-01")
    d = bd.bericht_daten(db, heute=HEUTE)
    assert d["kennzahlen"]["bewerbungen"]["wert"] == 2
    assert d["dauer"]["nachgetragen"]["wert"] == 1
    assert d["dauer"]["bis_antwort"]["anzahl"] == 1
    assert "1 nachgetragene Bewerbung" in d["dauer"]["nachgetragen_satz"]


def test_stufen_ohne_zahl_entfallen_und_werden_genannt(db):
    d = bd.bericht_daten(db, heute=HEUTE)
    assert [s["stufe"] for s in d["trichter"]["stufen"]] == ["Beworben", "Gespräch", "Angebot"]
    assert {s["stufe"] for s in d["trichter"]["entfallen"]} == {"Antwort erhalten", "Zweitgespräch"}


def test_leerer_bestand_bricht_nicht_und_sagt_unbekannt(db):
    d = bd.bericht_daten(db, "2026-11-01", "2026-11-30", heute=HEUTE)
    assert d["kennzahlen"]["bewerbungen"]["text"] == "0"
    assert d["kennzahlen"]["mit_gespraech"]["text"] == "noch keine Angabe"
    assert d["dauer"]["bis_antwort"]["text"] == "noch keine Angabe"
    assert len(d["zeitachse"]["abschnitte"]) == 1


def test_vergleich_zwei_zahlen_ohne_wertung(db):
    _app(db, "beworben", "2026-11-10")
    _app(db, "beworben", "2026-10-01")
    _app(db, "beworben", "2026-07-01")
    _app(db, "beworben", "2026-01-01")
    v = bd.bericht_daten(db, heute=HEUTE)["vergleich"]
    assert v["letzte_3_monate"]["wert"] == 2 and v["3_monate_davor"]["wert"] == 1
    assert set(v) == {"letzte_3_monate", "3_monate_davor"}


def test_datenkern_ist_beim_textpruefer_registriert():
    from pathlib import Path
    q = (Path(__file__).resolve().parents[1] / "scripts" / "ui_texte_pruefen.py").read_text(encoding="utf-8")
    assert "services/bericht_daten.py" in q
