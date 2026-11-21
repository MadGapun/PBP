"""#798 Stufe 3: die Auswertung. Liest das erzeugte PDF; Testdaten fiktiv, DB isoliert."""
from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from pypdf import PdfReader

from bewerbungs_assistent import export_auswertung as ea
from bewerbungs_assistent.services import auswertung_daten as ad
from bewerbungs_assistent.services.anzeigenamen import quelle_text

HEUTE = "2026-11-21"
VON, BIS = "2026-11-01", "2026-11-30"


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


def _app(db, status, tag, gespraech=False, source="stepstone", firma="Musterbau GmbH"):
    aid = db.add_application({"title": "Planer", "company": firma, "status": status,
                              "applied_at": tag, "source": source})
    c = db.connect()
    c.execute("DELETE FROM application_events WHERE application_id=?", (aid,))
    c.execute("UPDATE applications SET status=?, applied_at=?, has_reached_interview=?, source=? "
              "WHERE id=?", (status, tag, 1 if gespraech else 0, source, aid))
    c.commit()
    return aid


def _pdf(db, tmp_path, von=VON, bis=BIS):
    daten = ad.auswertung_daten(db, von, bis, heute=HEUTE)
    pfad = tmp_path / "a.pdf"
    ea.erzeugen(daten, "Beate Beispiel", pfad)
    seiten = [p.extract_text() for p in PdfReader(str(pfad)).pages]
    return daten, seiten, " ".join("\n".join(seiten).split())


@pytest.mark.parametrize("gesamt,nach,erwartet", [
    (2, 2, ""), (3, 1, ""), (4, 2, ""), (3, 2, "2 der 3 Absagen kamen nach einem Gespräch."),
])
def test_satz_steht_nur_wenn_die_zahlen_ihn_tragen(gesamt, nach, erwartet):
    assert ad.satz_absagen(gesamt, nach) == erwartet


@pytest.mark.parametrize("n,text", [(1, "1 von 1"), (3, "3 von 3"), (12, "100,0 % (12 von 12)")])
def test_kleine_fallzahlen_im_kern_der_auswertung(db, n, text):
    for i in range(n):
        _app(db, "beworben", f"2026-11-{i + 1:02d}", gespraech=True)
    d = ad.auswertung_daten(db, VON, BIS, heute=HEUTE)
    assert d["kennzahlen"]["mit_gespraech"]["text"] == text
    assert d["wege"]["zeilen"][0]["gespraeche"]["text"] == text


def test_pdf_nennt_dieselben_zahlen_wie_der_kern(db, tmp_path):
    _app(db, "abgelehnt", "2026-11-03", True)
    _app(db, "abgelehnt", "2026-11-04", True)
    _app(db, "abgelehnt", "2026-11-05", False, source="")
    _app(db, "interview", "2026-11-06", True)
    _app(db, "beworben", "2026-09-01")
    d, _, text = _pdf(db, tmp_path)
    assert d["kennzahlen"]["bewerbungen"]["wert"] == 4
    assert "Wie weit kamen die 4 Bewerbungen?" in text
    assert "2 der 3 Absagen kamen nach einem Gespräch." in text
    assert "Weg nicht erfasst" in text and "kein Ergebnis" in text
    assert "Zweitgespräch" in text and "Ohne belastbare Zahl" in text


def test_jede_seite_traegt_name_zeitraum_und_seitenzahl(db, tmp_path):
    for i in range(40):
        _app(db, "beworben", f"2026-11-{i % 28 + 1:02d}", firma=f"Musterfirma {i:02d} GmbH")
    _, seiten, _ = _pdf(db, tmp_path)
    assert len(seiten) >= 2
    for nr, s in enumerate(seiten, 1):
        s = " ".join(s.split())
        assert "Beate Beispiel · Auswertung 01.11.2026 bis 30.11.2026" in s
        assert f"Seite {nr} von {len(seiten)}" in s


def test_suche_nur_im_gesamten_verlauf(db, tmp_path):
    _app(db, "beworben", "2026-11-03")
    d, _, text = _pdf(db, tmp_path)
    assert d["meine_suche"]["verfuegbar"] is False and ad.SUCHE_NUR_GESAMT in text
    assert ad.auswertung_daten(db, heute=HEUTE)["meine_suche"]["verfuegbar"] is True


def test_keine_rohwerte_und_ein_datumsformat(db, tmp_path):
    _app(db, "arbeitgeber_ausgefallen", "2026-11-03", source="firmenwebsite")
    _app(db, "beworben", "2026-11-04", source="netzwerk")
    _, _, text = _pdf(db, tmp_path)
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)
    assert not re.search(r"[a-z]+_[a-z]+", text)
    assert "firmenwebsite" not in text and "netzwerk" not in text
    assert "Firmenwebsite" in text and "Netzwerk" in text


def test_eigene_wege_haben_einen_namen():
    assert quelle_text("firmenwebsite") == "Firmenwebsite"
    assert quelle_text("persoenlich") == "Persönlicher Kontakt"


def test_endpunkte_liefern_pdf_und_dieselben_zahlen(db):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    _app(db, "beworben", "2026-11-03", True)
    _app(db, "beworben", "2026-09-03")
    alt = dash._db
    dash._db = db
    try:
        client = TestClient(dash.app)
        r = client.get("/api/bericht/auswertung", params={"from": VON, "to": BIS})
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
        assert "Auswertung meiner Stellensuche" in PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
        k = client.get("/api/bericht/kennzahlen", params={"from": VON, "to": BIS}).json()
        assert k["kennzahlen"]["bewerbungen"]["wert"] == 1
        assert k["zeitraum"]["text"] == "01.11.2026 bis 30.11.2026"
    finally:
        dash._db = alt


def test_auswertung_ist_beim_textpruefer_registriert():
    q = (Path(__file__).resolve().parents[1] / "scripts" / "ui_texte_pruefen.py").read_text(encoding="utf-8")
    assert "export_auswertung.py" in q and "services/auswertung_daten.py" in q


def test_excel_hat_rohdaten_blaetter_mit_bezug(db, tmp_path):
    import datetime
    import openpyxl
    from bewerbungs_assistent.services import bericht
    aid = _app(db, "beworben", "2026-11-03", True)
    db.connect().execute("INSERT INTO application_events (application_id,status,event_date,notes) "
                         "VALUES (?,?,?,'')", (aid, "interview", "2026-11-09"))
    db.connect().execute("INSERT INTO application_meetings (id,application_id,title,meeting_date,"
                         "meeting_type,status) VALUES ('m1',?,'T','2026-11-13','vor_ort','durchgefuehrt')",
                         (aid,))
    db.connect().commit()
    pfad = tmp_path / "r.xlsx"
    bericht.erzeugen(db, pfad, "excel", VON, BIS)
    wb = openpyxl.load_workbook(str(pfad))
    assert {"Bewerbungen", "Ereignisse", "Termine", "Kennzahlen"} <= set(wb.sheetnames)
    e = wb["Ereignisse"]
    assert isinstance(e["A2"].value, datetime.datetime) and e["A2"].number_format == "DD.MM.YYYY"
    assert e.freeze_panes == "A2" and e.auto_filter.ref
    assert wb["Termine"]["D2"].value == "Gespräch vor Ort"
    zeilen = {r[0]: r for r in wb["Kennzahlen"].iter_rows(min_row=2, values_only=True)}
    assert zeilen["Bewerbungen"][1] == "1" and zeilen["Bewerbungen"][4] == "im Zeitraum"
    assert zeilen["Laufende Verfahren"][4] == "am Stichtag"
    assert zeilen["Bewerbungen"][5] == "01.11.2026 bis 30.11.2026"
