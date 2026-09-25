"""Tests fuer v1.7.129 — #1080 Stufe 1: eine Firma in allen Quellen.

`firma_kontext` sah nur `applications.company` und die Stellen. Eine
Firma steht aber auch als Vermittler, als Endkunde hinter einem
Vermittler, als Arbeitgeber im Lebenslauf, als Projektkunde, bei
Kontakten, in Anfragen und Recherchen und auf der Blacklist. Alle Firmen
und Personen hier sind erfunden.
"""
import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


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
    from bewerbungs_assistent.tools import bewerbungen as modul
    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    modul.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt


def _bewerbung(db, company, title="Fachrolle", status="beworben",
               vermittler="", endkunde="", notes=""):
    aid = db.add_application({"title": title, "company": company,
                              "status": status, "notes": notes})
    felder = {k: v for k, v in (("vermittler", vermittler),
                                ("endkunde", endkunde)) if v}
    if felder:
        db.update_application(aid, felder)
    return aid


# --- Namensabgleich --------------------------------------------------------

def test_namensform_und_abgleich():
    from bewerbungs_assistent.services.firmen_bezuege import abgleich, namensform
    assert namensform("Musterwerk Süd GmbH & Co. KG") == "musterwerk sued"
    assert namensform("Unbekannt") == ""
    assert abgleich(namensform("Musterwerk Sued"),
                    namensform("Musterwerk Süd GmbH")) == "gleich"
    assert abgleich(namensform("Muster-Technik"),
                    namensform("MusterTechnik AG")) == "gleich"
    assert abgleich(namensform("Acme"),
                    namensform("Acme Solutions GmbH")) == "teil"
    assert abgleich(namensform("BM"),
                    namensform("Beispielwerk Maschinen GmbH")) == "abkuerzung"
    assert abgleich(namensform("BWM"),
                    namensform("Beispielwerk Maschinen GmbH")) is None


def test_wortgrenze_statt_buchstabenfolge():
    """Die alte Suche verglich Teilstrings — "Kita" traf jede "Kitagruppe"
    und "ki" jede "Kita". Verglichen werden jetzt Woerter."""
    from bewerbungs_assistent.services.firmen_bezuege import abgleich, namensform
    assert abgleich(namensform("Beispiel"), namensform("Beispielwerk GmbH")) is None
    # zwei Zeichen tragen keinen Teil-Abgleich
    assert abgleich(namensform("ab"), namensform("ab cd ef Beispiel AG")) is None


# --- Rollen in firma_kontext -----------------------------------------------

def test_endkunde_hinter_vermittler_wird_gefunden_und_gewarnt(db):
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               endkunde="Beispielwerk Maschinen GmbH", status="beworben")
    antwort = _werkzeuge(db)["firma_kontext"]("Beispielwerk Maschinen")
    assert antwort["gefunden"]
    rollen = [b["rolle"] for b in antwort["bewerbungen"]]
    assert rollen == ["endkunde"]
    assert antwort["bewerbungen"][0]["vermittler"] == "Muster Vermittlung GmbH"
    assert any("Doppelvorstellung" in w for w in antwort["warnungen"])


def test_abgeschlossene_vorstellung_warnt_nicht(db):
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               endkunde="Beispielwerk Maschinen GmbH", status="abgelehnt")
    antwort = _werkzeuge(db)["firma_kontext"]("Beispielwerk Maschinen")
    assert antwort["gefunden"]
    assert antwort["warnungen"] == []


def test_zwei_kanaele_heissen_doppelvorstellung(db):
    _bewerbung(db, "Beispielwerk Maschinen GmbH")
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               endkunde="Beispielwerk Maschinen")
    antwort = _werkzeuge(db)["firma_kontext"]("Beispielwerk Maschinen GmbH")
    assert any(w.startswith("DOPPELVORSTELLUNG") for w in antwort["warnungen"])


def test_firma_als_vermittler(db):
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               endkunde="Beispielwerk Maschinen GmbH")
    antwort = _werkzeuge(db)["firma_kontext"]("Muster Vermittlung")
    assert antwort["bewerbungen"][0]["rolle"] == "bewerbungsziel"
    assert antwort["rollen"].get("vermittler") == 1


def test_lebenslauf_kontakt_blacklist_anfrage_recherche(db):
    pos = db.add_position({"company": "Beispielwerk Maschinen GmbH", "title": "Konstrukteur",
                           "start_date": "2015-01", "end_date": "2019-06"})
    db.add_position({"company": "Mustertechnik Heute AG", "title": "Planer",
                     "start_date": "2020-01", "is_current": 1})
    alt = db.add_position({"company": "Musterfirma Alt KG", "title": "Planer",
                           "start_date": "2010-01", "end_date": "2014-12"})
    db.add_project(alt, {"name": "Umstellung", "customer_name": "Beispielwerk Maschinen"})
    db.add_project(alt, {"name": "Geheim", "customer_name": "Beispielwerk Maschinen",
                         "is_confidential": 1})
    db.add_contact({"full_name": "Erika Beispiel", "company": "Beispielwerk Maschinen GmbH",
                    "position": "Leitung Technik"})
    db.add_document({"filename": "anfrage.eml", "doc_type": "recruiter_anfrage",
                     "extracted_text": "Fuer unseren Kunden Beispielwerk Maschinen suchen wir"})
    db.add_document({"filename": "lebenslauf.pdf", "doc_type": "lebenslauf",
                     "extracted_text": "Beispielwerk Maschinen GmbH 2015-2019"})
    db.add_research_note("firmenrecherche", "Beispielwerk Maschinen: Familienbetrieb")
    db.add_to_blacklist("firma", "Beispielwerk Maschinen", reason="Gespraech 2019")

    antwort = _werkzeuge(db)["firma_kontext"]("Beispielwerk Maschinen GmbH")
    rollen = antwort["rollen"]
    assert rollen["arbeitgeber_frueher"] == 1
    assert "arbeitgeber_aktuell" not in rollen   # Mustertechnik Heute ist eine andere Firma
    assert rollen["projektkunde"] == 2
    assert rollen["kontakt"] == 1
    assert rollen["anfrage"] == 1
    assert rollen["recherche"] == 1
    assert rollen["blacklist"] == 1
    # der Lebenslauf zaehlt nicht als Anfrage — dort steht die Station schon
    assert rollen.get("korrespondenz") is None
    kurz = [p["kurz"] for p in antwort["weitere_bezuege"]["projektkunde"]]
    assert "Umstellung bei Musterfirma Alt KG" in kurz
    assert "vertrauliches Projekt bei Musterfirma Alt KG" in kurz
    assert not any("Geheim" in k for k in kurz)


def test_verweise_statt_inhalt(db):
    """Nutzerwort 25.09.2026: nicht alles hinschreiben, sondern auf den
    Bereich verweisen, in dem es steht."""
    pos = db.add_position({"company": "Beispielwerk Maschinen GmbH", "title": "Konstrukteur",
                           "start_date": "2015-01", "end_date": "2019-06"})
    kid = db.add_contact({"full_name": "Erika Beispiel", "company": "Beispielwerk Maschinen",
                          "notes": "lange Notiz " * 50})
    did = db.add_document({"filename": "anfrage.eml", "doc_type": "recruiter_anfrage",
                           "extracted_text": "Kunde Beispielwerk Maschinen " + "x " * 500})
    aid = _bewerbung(db, "Beispielwerk Maschinen GmbH")
    db.save_jobs([{"hash": "nordw001", "title": "Planer", "company": "Beispielwerk Maschinen",
                   "location": "", "score": 1, "source": "manuell",
                   "url": "https://example.org/job/nordw001", "description": ""}])
    db.dismiss_job("nordw001", "falsches_fachgebiet")
    antwort = _werkzeuge(db)["firma_kontext"]("Beispielwerk Maschinen")
    wb = antwort["weitere_bezuege"]
    assert wb["arbeitgeber_frueher"][0]["oeffnen"] == f"positionen_anzeigen(nur_id='{pos}')"
    assert wb["arbeitgeber_frueher"][0]["kurz"] == "Konstrukteur, 2015-01 bis 2019-06"
    assert wb["kontakt"][0]["oeffnen"] == f"kontakt_anzeigen('{kid}')"
    assert wb["anfrage"][0]["oeffnen"] == f"dokument_lesen('{did}')"
    assert antwort["bewerbungen"][0]["oeffnen"] == f"bewerbung_details('{aid}')"
    beispiel = antwort["aussortiert_beispiele"][0]
    assert beispiel["grund"] == "falsches_fachgebiet"
    assert beispiel["oeffnen"].startswith("fit_analyse(")
    # der Inhalt selbst steht nicht in der Antwort
    text = str(antwort)
    assert "lange Notiz" not in text and "x x x" not in text


def test_aktueller_arbeitgeber(db):
    db.add_position({"company": "Mustertechnik Heute AG", "title": "Planer",
                     "start_date": "2020-01", "is_current": 1})
    antwort = _werkzeuge(db)["firma_kontext"]("Mustertechnik Heute")
    assert antwort["rollen"] == {"arbeitgeber_aktuell": 1}
    assert antwort["gefunden"]


def test_endkunde_nur_in_notizen_wird_zur_pruefung(db):
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               notes="Einsatz beim Kunden Beispielwerk Maschinen in Musterstadt")
    antwort = _werkzeuge(db)["firma_kontext"]("Beispielwerk Maschinen")
    assert antwort["in_notizen_erwaehnt"]
    assert antwort["in_notizen_erwaehnt"][0]["moeglicher_endkunde"]
    assert any(w.startswith("Pruefen") for w in antwort["warnungen"])
    # nicht als Vorstellung gezaehlt — nur benannt
    assert not any("Doppelvorstellung" in w and not w.startswith("Pruefen")
                   for w in antwort["warnungen"])


def test_kurzer_name_sucht_nicht_im_freitext(db):
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               notes="Rueckruf abc morgen")
    antwort = _werkzeuge(db)["firma_kontext"]("ABC")
    assert antwort["in_notizen_erwaehnt"] == []
    assert not antwort["gefunden"]


def test_platzhalter_findet_nichts(db):
    _bewerbung(db, "Unbekannt")
    antwort = _werkzeuge(db)["firma_kontext"]("Unbekannt")
    assert "fehler" in antwort


def test_schreibweisen_stehen_in_der_antwort(db):
    _bewerbung(db, "Musterwerk Süd GmbH")
    db.add_position({"company": "Musterwerk Sued", "title": "Planer",
                     "start_date": "2012-01", "end_date": "2014-01"})
    antwort = _werkzeuge(db)["firma_kontext"]("Musterwerk Süd")
    assert set(antwort["schreibweisen"]) == {"Musterwerk Süd GmbH", "Musterwerk Sued"}


# --- Bestandsbericht -------------------------------------------------------

def test_bestandsbericht_findet_schreibweisen_und_endkunden(db):
    _bewerbung(db, "Musterwerk Süd GmbH")
    db.add_contact({"full_name": "Erika Beispiel", "company": "Musterwerk-Sued"})
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               notes="Kunde ist Musterwerk Süd, Start im Herbst")
    bericht = _werkzeuge(db)["firmen_bestand_pruefen"]()
    gruppe = [g for g in bericht["schreibweisen"]
              if "Musterwerk Süd GmbH" in g["schreibweisen"]]
    assert gruppe and "Musterwerk-Sued" in gruppe[0]["schreibweisen"]
    assert bericht["endkunde_nur_in_notizen_anzahl"] == 1
    eintrag = bericht["endkunde_nur_in_notizen"][0]
    assert eintrag["genannte_firmen"] == ["musterwerk sued"]
    assert eintrag["laeuft"]


def test_bestandsbericht_ignoriert_eingetragene_endkunden(db):
    _bewerbung(db, "Musterwerk Süd GmbH")
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               endkunde="Musterwerk Süd", notes="Kunde ist Musterwerk Süd")
    bericht = _werkzeuge(db)["firmen_bestand_pruefen"]()
    assert bericht["endkunde_nur_in_notizen_anzahl"] == 0


def test_bestandsbericht_schreibt_nichts(db):
    _bewerbung(db, "Musterwerk Süd GmbH")
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               notes="Kunde ist Musterwerk Süd")
    conn = db.connect()
    vorher = conn.execute("SELECT id, company, vermittler, endkunde, notes "
                          "FROM applications ORDER BY id").fetchall()
    _werkzeuge(db)["firmen_bestand_pruefen"]()
    nachher = conn.execute("SELECT id, company, vermittler, endkunde, notes "
                           "FROM applications ORDER BY id").fetchall()
    assert [tuple(r) for r in vorher] == [tuple(r) for r in nachher]


def test_werkzeug_steht_in_capabilities():
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "tools" / "analyse.py"
              ).read_text(encoding="utf-8")
    assert "firmen_bestand_pruefen" in quelle
    assert '"firma_kontext —' in quelle


def test_bericht_nennt_nicht_den_vermittler_selbst(db):
    _bewerbung(db, "Musterwerk Süd GmbH")
    _bewerbung(db, "Muster Vermittlung GmbH", vermittler="Muster Vermittlung GmbH",
               notes="Muster Vermittlung meldet sich, Kunde ist Musterwerk Süd")
    eintrag = _werkzeuge(db)["firmen_bestand_pruefen"]()["endkunde_nur_in_notizen"][0]
    assert eintrag["genannte_firmen"] == ["musterwerk sued"]


def test_kontext_findet_keine_bewerbung_ueber_buchstabenfolge(db):
    """Die alte Regel verglich Teilstrings: "Beispiel" traf "Beispielwerk"."""
    _bewerbung(db, "Beispielwerk Maschinen GmbH")
    antwort = _werkzeuge(db)["firma_kontext"]("Beispiel")
    assert antwort["bewerbungen"] == []
