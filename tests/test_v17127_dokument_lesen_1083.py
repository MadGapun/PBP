"""Tests fuer v1.7.127 — #1083: den Text eines Dokuments ueber PBP lesen.

Gemeldet am 24.09.2026: eine verknuepfte Absagemail war ueber MCP nicht
lesbar, Claude musste per SQL zugreifen. Und der Absagegrund stand seit
Monaten in PBP, ohne dass die Repost-Warnung ihn nannte.
Alle Firmen und Namen hier sind erfunden.
"""
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

ABSAGE = (
    "Betreff: Ihre Bewerbung\n\n"
    "Sehr geehrte Bewerberin, sehr geehrter Bewerber,\n\n"
    "vielen Dank fuer Ihr Interesse. Nach sorgfaeltiger Pruefung haben wir "
    "uns leider fuer eine Kandidatin mit mehr Fuehrungserfahrung entschieden. "
    "Wir wuenschen Ihnen alles Gute.\n\nMit freundlichen Gruessen\nMusterwerk Nord"
)


@pytest.fixture
def db(tmp_path):
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = str(tmp_path / "daten")
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Muster Person"})
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt


def _werkzeuge(db):
    from bewerbungs_assistent.tools import bewerbungen, dokumente, jobs
    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

        def prompt(self, *a, **kw):
            return lambda fn: fn

    for modul in (bewerbungen, dokumente, jobs):
        modul.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt


def _absage_anlegen(db, text=ABSAGE):
    app_id = db.add_application({
        "title": "Leitung Produktdaten", "company": "Musterwerk Nord GmbH",
        "status": "abgelehnt"})
    doc_id = db.add_document({
        "filename": "absage.eml", "doc_type": "absage",
        "extracted_text": text, "linked_application_id": app_id})
    return app_id, doc_id


def test_1083_dokument_lesen_liefert_den_text(db):
    _, doc_id = _absage_anlegen(db)
    antwort = _werkzeuge(db)["dokument_lesen"](doc_id)
    assert antwort["text"] == ABSAGE
    assert antwort["vollstaendig"] is True
    assert antwort["typ"] == "absage"
    assert "weiter_ab_zeichen" not in antwort


def test_1083_dokument_lesen_ist_seitenweise_und_kappt_nicht_still(db):
    lang = "Absatz mit Inhalt. " * 1000
    _, doc_id = _absage_anlegen(db, text=lang)
    lesen = _werkzeuge(db)["dokument_lesen"]
    erste = lesen(doc_id)
    assert erste["vollstaendig"] is False
    assert erste["gesamt_zeichen"] == len(lang)
    zusammen = erste["text"]
    weiter = erste["weiter_ab_zeichen"]
    # Obergrenze: ein Weg, der ab_zeichen ignoriert, liefe sonst endlos
    # (in der Gegenprobe so geschehen).
    for _ in range(20):
        if weiter is None:
            break
        teil = lesen(doc_id, ab_zeichen=weiter)
        zusammen += teil["text"]
        weiter = teil.get("weiter_ab_zeichen")
    assert zusammen == lang


def test_1083_unbekanntes_dokument_nennt_den_weg(db):
    antwort = _werkzeuge(db)["dokument_lesen"]("gibtsnicht")
    assert "fehler" in antwort
    assert "bewerbung_details" in antwort["naechster_schritt"]


def test_1083_bewerbung_details_zeigt_den_textanfang(db):
    app_id, doc_id = _absage_anlegen(db)
    antwort = _werkzeuge(db)["bewerbung_details"](app_id)
    doc = [d for d in antwort["dokumente"] if d["id"] == doc_id][0]
    assert "Betreff: Ihre Bewerbung" in doc["textanfang"]
    assert doc_id in doc["ganzer_text"]


def test_1083_repost_warnung_nennt_den_grund_aus_der_mail(db):
    from bewerbungs_assistent.duplicate_detection import find_repost_of_application
    _absage_anlegen(db)
    stelle = {"hash": "neu001", "title": "Leitung Produktdaten",
              "company": "Musterwerk Nord GmbH"}
    ohne = find_repost_of_application(stelle, db.get_applications())
    assert "Fuehrungserfahrung" not in ohne["warnung"]
    mit = find_repost_of_application(stelle, db.get_applications(), db=db)
    assert "Fuehrungserfahrung" in mit["warnung"]
    assert mit["ablehnungsgrund"]["quelle"] == "dokument"
    assert mit["ablehnungsgrund_dokumentiert"] is True


def test_1083_der_grund_der_bewerbung_hat_vorrang(db):
    from bewerbungs_assistent.services import dokument_text
    app_id, _ = _absage_anlegen(db)
    db.connect().execute("UPDATE applications SET rejection_reason=? WHERE id=?",
                         ("Gehaltsvorstellung zu hoch", app_id))
    grund = dokument_text.ablehnungsgrund(db, app_id)
    assert grund == {"quelle": "bewerbung", "text": "Gehaltsvorstellung zu hoch"}


def test_1083_auszug_ohne_signal_faellt_auf_den_anfang_zurueck():
    from bewerbungs_assistent.services import dokument_text
    assert dokument_text.ablehnungs_auszug("Hallo.\nDanke fuer die Unterlagen.")
    assert "Fuehrungserfahrung" in dokument_text.ablehnungs_auszug(ABSAGE)
    assert "Wir wuenschen" not in dokument_text.ablehnungs_auszug(ABSAGE)


def test_1083_liste_und_fit_analyse_nennen_den_grund(db):
    _absage_anlegen(db)
    db.save_jobs([{"hash": "neu001", "title": "Leitung Produktdaten",
                   "company": "Musterwerk Nord GmbH", "location": "Musterstadt",
                   "score": 20, "url": "https://example.org/anzeige/neu-1",
                   "source": "linkedin",
                   "description": "Eine ausfuehrliche Stellenbeschreibung. " * 8}])
    werkzeuge = _werkzeuge(db)
    liste = werkzeuge["stellen_anzeigen"]()
    stellen = liste.get("stellen") or liste.get("jobs")
    assert "Fuehrungserfahrung" in stellen[0]["repost_warnung"]
    fit = werkzeuge["fit_analyse"]("neu001")
    assert "Fuehrungserfahrung" in fit["repost_warnung"]
