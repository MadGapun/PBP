"""#798 Stufe 3: der Nachweis der Bewerbungsbemuehungen. Liest das erzeugte PDF.

Testdaten fiktiv, Datenbank isoliert.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from pypdf import PdfReader

from bewerbungs_assistent import export_nachweis as en
from bewerbungs_assistent.services import nachweis_daten as nd

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


def _app(db, firma, status, tag, gespraech=False):
    aid = db.add_application({"title": "Fertigungsplaner", "company": firma, "status": status,
                              "applied_at": tag, "source": "stepstone",
                              "bewerbungsart": "mit_dokumenten"})
    c = db.connect()
    c.execute("DELETE FROM application_events WHERE application_id=?", (aid,))
    c.execute("UPDATE applications SET status=?, applied_at=?, has_reached_interview=?, "
              "rejection_reason=? WHERE id=?",
              (status, tag, 1 if gespraech else 0,
               "Geheimer Absagegrund" if status == "abgelehnt" else None, aid))
    c.commit()
    return aid


def _ev(db, aid, status, tag):
    c = db.connect()
    c.execute("INSERT INTO application_events (application_id,status,event_date,notes) "
              "VALUES (?,?,?,'Private Notiz')", (aid, status, tag))
    c.commit()


def _termin(db, aid, tag, art="vor_ort", status="durchgefuehrt"):
    c = db.connect()
    c.execute("INSERT INTO application_meetings (id,application_id,title,meeting_date,meeting_type,"
              "status) VALUES (?,?,?,?,?,?)", (f"m{aid}{tag}{art}", aid, "Termin", tag, art, status))
    c.commit()


@pytest.fixture()
def bestand(db):
    a = _app(db, "Musterbau GmbH", "interview", "2026-11-03", True)
    _ev(db, a, "eingangsbestaetigung", "2026-11-04")
    _ev(db, a, "interview", "2026-11-09")
    _termin(db, a, "2026-11-13")
    _termin(db, a, "2026-11-14", status="abgesagt")
    b = _app(db, "Beispielwerk AG", "abgelehnt", "2026-11-05")
    _ev(db, b, "abgelehnt", "2026-11-19")
    f = _app(db, "Altfirma KG", "beworben", "2026-10-10")
    _ev(db, f, "eingangsbestaetigung", "2026-11-02")
    _app(db, "Vorher GmbH", "abgelehnt", "2026-09-01")
    db.add_application_cost({"kind": "reise", "amount": 38.4, "description": "Bahnfahrt",
                             "incurred_at": "2026-11-13"})
    return db


def _pdf(db, tmp_path, mit_kosten=False, einstellungen=None, von=VON, bis=BIS):
    daten = nd.nachweis_daten(db, von, bis, heute=HEUTE, mit_kosten=mit_kosten)
    pfad = tmp_path / "n.pdf"
    en.erzeugen(daten, "Beate Beispiel", pfad, einstellungen)
    seiten = [p.extract_text() for p in PdfReader(str(pfad)).pages]
    return daten, seiten, " ".join("\n".join(seiten).split())


def test_kacheln_zaehlen_nur_was_geschah(bestand, tmp_path):
    d, _, _ = _pdf(bestand, tmp_path)
    w = {k["name"]: k["wert"] for k in d["kacheln"]}
    assert w == {"Bewerbungen": 2, "Gesprächstermine": 1, "Rückmeldungen": 4, "Laufende Verfahren": 2}


def test_frueheres_verfahren_steht_getrennt_mit_bezug(bestand, tmp_path):
    d, _, text = _pdf(bestand, tmp_path)
    assert [l["firma"] for l in d["laufende_frueher"]] == ["Altfirma KG"]
    assert "Laufende Verfahren aus früheren Zeiträumen" in text
    assert "Eingang bestätigt (Bewerbung vom 10.10.2026)" in text


def test_nachweis_enthaelt_keine_bewertung_und_keine_gruende(bestand, tmp_path):
    bestand.connect().execute("UPDATE applications SET notes='Private Notiz'")
    bestand.connect().commit()
    _, _, text = _pdf(bestand, tmp_path, mit_kosten=True)
    for wort in ("Punkte", "Score", "Quote", "%", "Geheimer Absagegrund", "Private Notiz"):
        assert wort not in text, wort


def test_kosten_nur_auf_wunsch(bestand, tmp_path):
    _, _, ohne = _pdf(bestand, tmp_path)
    assert "Bewerbungskosten" not in ohne and "38,40" not in ohne
    _, _, mit = _pdf(bestand, tmp_path, mit_kosten=True)
    assert "Bewerbungskosten im Zeitraum" in mit and "38,40 €" in mit and "Summe" in mit


def test_jede_seite_traegt_name_zeitraum_und_seitenzahl(db, tmp_path):
    for i in range(45):
        _app(db, f"Musterfirma {i:02d} GmbH", "beworben", f"2026-11-{i % 28 + 1:02d}")
    _, seiten, _ = _pdf(db, tmp_path)
    assert len(seiten) >= 2
    for nr, s in enumerate(seiten, 1):
        s = " ".join(s.split())
        assert "Beate Beispiel · Nachweis 01.11.2026 bis 30.11.2026" in s
        assert f"Seite {nr} von {len(seiten)}" in s


def test_kopfzeile_wiederholt_sich_und_keine_zeile_wird_geteilt(db, tmp_path):
    for i in range(45):
        _app(db, f"Musterfirma {i:02d} GmbH", "beworben", f"2026-11-{i % 28 + 1:02d}")
    _, seiten, text = _pdf(db, tmp_path)
    assert sum("Arbeitgeber und Stelle" in s for s in seiten) >= 2
    for i in range(45):
        assert f"Musterfirma {i:02d} GmbH, Fertigungsplaner" in text


def test_amtsblock_und_notizen_nur_wenn_eingeschaltet(bestand, tmp_path):
    _, _, ohne = _pdf(bestand, tmp_path)
    assert "Kundennummer" not in ohne and "Notizen aus dem" not in ohne
    _, _, mit = _pdf(bestand, tmp_path, einstellungen={
        "arbeitsamt_block_enabled": True, "ba_vermittlungsnummer": "123X",
        "ba_aktenzeichen": "AZ-1", "berater_kommentar_block": True})
    assert "Kundennummer 123X" in mit and "Aktenzeichen AZ-1" in mit
    assert "Notizen aus dem Beratungsgespräch" in mit and "Unterschrift" in mit


def test_ein_datumsformat_und_keine_schluessel(bestand, tmp_path):
    _, _, text = _pdf(bestand, tmp_path)
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)
    assert not re.search(r"[a-z]+_[a-z]+", text)
    for umschrift in ("Gespraech", "Rueckmeldung", "bestaetigt", "Zeitraeume"):
        assert umschrift not in text


def test_leerer_zeitraum_sagt_es(db, tmp_path):
    _, _, text = _pdf(db, tmp_path)
    assert "In diesem Zeitraum ist keine Bewerbung erfasst." in text


def test_nachweis_ist_beim_textpruefer_registriert():
    q = (Path(__file__).resolve().parents[1] / "scripts" / "ui_texte_pruefen.py").read_text(encoding="utf-8")
    assert "export_nachweis.py" in q and "services/nachweis_daten.py" in q


def test_endpunkt_liefert_pdf_mit_zeitraum_und_kosten_nur_mit_haken(bestand):
    import io
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    alt = dash._db
    dash._db = bestand
    try:
        client = TestClient(dash.app)
        ohne = client.get("/api/bericht/nachweis", params={"from": VON, "to": BIS})
        assert ohne.status_code == 200 and ohne.headers["content-type"] == "application/pdf"
        text = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(ohne.content)).pages)
        assert "Nachweis der Bewerbungsbemühungen" in text and "Bewerbungskosten" not in text
        assert client.put("/api/settings/report", json={"nachweis_kosten": True}).status_code == 200
        assert client.get("/api/settings/report").json()["nachweis_kosten"] is True
        mit = client.get("/api/bericht/nachweis", params={"from": VON, "to": BIS})
        text = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(mit.content)).pages)
        assert "Bewerbungskosten" in text
    finally:
        dash._db = alt


def test_amtsdaten_bleiben_draussen_solange_der_block_aus_ist(bestand, tmp_path):
    """Gegenprobe: Daten sind gespeichert, der Schalter ist aus."""
    _, _, text = _pdf(bestand, tmp_path, einstellungen={
        "arbeitsamt_block_enabled": False, "ba_vermittlungsnummer": "123X"})
    assert "123X" not in text and "Kundennummer" not in text
