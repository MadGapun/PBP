"""Tests fuer #1041, Nachtrag nach v1.7.107 (B54).

Der gemeinsame Kartenleser fuer Jobware und ingenieur.de nahm HTML-Kommentare
der Plattform mit (`<!--t=g-->`, `<!--qv q:key=...-->`, `<!--/qv-->`). Titel,
Firma und Ort trugen Reste, die Kennung entstand aus dem Titel mit Rest, und
der Uebergang aus v1.7.104 griff nicht: der alte Eintrag blieb aktiv, der
Neufund wurde ueber die URL als `duplikat` aussortiert. Die Fixtures der
v1.7.104-Tests enthielten keine Kommentare — deshalb hier Karten MIT den
gemessenen Kommentarformen. Alle Angaben sind erfunden.
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.job_scraper import jobboerse_karten, jobware, stelle_hash  # noqa: E402
from bewerbungs_assistent.services import geocoding_service, karten_heilung  # noqa: E402

JOBWARE_KARTE = """<html><body>
<div class="job-card">
  <h2 class="headline"><!--t=g-->Sachbearbeitung Einkauf (m/w/d)<!-- --></h2>
  <a href="/job/sachbearbeitung-einkauf-900000002"><span class="nrmdy-visually-hidden">Job "Sachbearbeitung Einkauf (m/w/d)" </span>ansehen</a>
  <span class="job-card__advertiser-name"><!--qv q:id=u q:key=Wed0:a8_19--><!--t=h-->Musterhandel GmbH<!--/qv--></span>
  <span class="job-card__location"><!--qv q:s q:sref=u q:key=prefix--><span class="nrmdy-visually-hidden">in</span><!--/qv--><!--t=w-->Musterstadt<!--/qv--></span>
</div>
</body></html>"""

INGENIEUR_KARTE = """<html><body>
<div class="job-card">
  <h2 class="headline"><!--t=f-->Konstruktion Sondermaschinenbau (gn)<!-- --></h2>
  <a href="/stellenangebot/konstruktion-sondermaschinenbau-900000003">Details</a>
  <div class="text-body-medium"><!--t=g-->Muster Maschinenbau GmbH</div>
  <div><span class="nrmdy-visually-hidden">in</span><!--qv q:s q:sref=n q:key=--><!--t=q-->Beispielhausen<!--/qv--></div>
</div>
</body></html>"""


# ====================================================== der Leser


@pytest.mark.parametrize("html, basis, erwartet", [
    (JOBWARE_KARTE, "https://www.jobware.de",
     {"titel": "Sachbearbeitung Einkauf (m/w/d)", "firma": "Musterhandel GmbH", "ort": "Musterstadt"}),
    (INGENIEUR_KARTE, "https://jobs.ingenieur.de",
     {"titel": "Konstruktion Sondermaschinenbau (gn)", "firma": "Muster Maschinenbau GmbH",
      "ort": "Beispielhausen"}),
])
def test_der_kartenleser_laesst_kommentare_aus(html, basis, erwartet):
    karten = jobboerse_karten.karten_aus_html(html, basis)
    assert len(karten) == 1
    for feld, wert in erwartet.items():
        assert karten[0][feld] == wert, (feld, karten[0])


def test_bereinigen_fuehrt_den_verfaelschten_wert_auf_den_sauberen_zurueck(monkeypatch):
    """Gemessen an echten Seiten: 36 von 36 Karten zeichengleich. Hier mit dem
    Leser von v1.7.104 bis v1.7.107 nachgestellt."""
    sauber = {n: jobboerse_karten.karten_aus_html(h, b)[0] for n, h, b in (
        ("jobware", JOBWARE_KARTE, "https://www.jobware.de"),
        ("ingenieur", INGENIEUR_KARTE, "https://jobs.ingenieur.de"))}
    monkeypatch.setattr(jobboerse_karten, "_ist_inhalt", lambda knoten: isinstance(knoten, str))
    for name, html, basis in (("jobware", JOBWARE_KARTE, "https://www.jobware.de"),
                              ("ingenieur", INGENIEUR_KARTE, "https://jobs.ingenieur.de")):
        alt = jobboerse_karten.karten_aus_html(html, basis)[0]
        assert karten_heilung.hat_rest(alt["titel"]), "der alte Leser muss den Fehler zeigen"
        for feld in ("titel", "firma", "ort"):
            assert karten_heilung.bereinigen(alt[feld]) == sauber[name][feld], (name, feld)


@pytest.mark.parametrize("text", [
    "Sachbearbeitung Einkauf (m/w/d)", "Qualitaetsmanager/in Automotive", "Teamleitung IT - Vollzeit",
    "Ingenieur q-Management", "Musterstadt / Beispielhausen", "Bereich t-Montage Musterstadt",
])
def test_bereinigen_laesst_normale_texte_stehen(text):
    assert karten_heilung.bereinigen(text) == text
    assert not karten_heilung.hat_rest(text)


# ====================================================== der Bestand


@pytest.fixture
def db(tmp_db):
    tmp_db.save_profile({"name": "Muster"})
    return tmp_db


def _stelle(kennung, titel, firma, ort, url, quelle):
    return {"hash": kennung, "title": titel, "company": firma, "location": ort, "url": url,
            "source": quelle, "description": "", "employment_type": "festanstellung", "score": 1}


def _zeilen(db):
    return [dict(r) for r in db.connect().execute(
        "SELECT hash, title, company, location, url, is_active, dismiss_reason, distance_km, lat, lon, "
        "score, fachscore FROM jobs ORDER BY hash").fetchall()]


def _oeffentlich(kennung):
    return kennung.rpartition(":")[2]


URL_J = "https://www.jobware.de/job/sachbearbeitung-einkauf-900000002"
URL_I = "https://jobs.ingenieur.de/stellenangebot/konstruktion-sondermaschinenbau-900000003"
TITEL_J = "Sachbearbeitung Einkauf (m/w/d)"
TITEL_I = "Konstruktion Sondermaschinenbau (gn)"


def test_altbestand_und_verfaelschter_neufund_werden_eine_stelle(db):
    """Meldefall: der Eintrag aus v1.7.103 blieb aktiv, der Neufund aus
    v1.7.107 wurde als `duplikat` aussortiert. Nach der Heilung gibt es EINE
    Stelle mit Titel, Firma und Ort — und der naechste saubere Fund landet
    auf ihr statt als neues Duplikat."""
    alt = _stelle(jobware.karten_hash(TITEL_J), f'Job"{TITEL_J}"ansehen', "Unbekannt",
                  "inMusterstadt", URL_J, "jobware")
    kaputt_titel = f"t=3n {TITEL_J}"
    kaputt = _stelle(jobware.karten_hash(kaputt_titel), kaputt_titel, "t=h Musterhandel GmbH",
                     "qv q:id=u q:key=Wed0:a8_19 qv q:s q:sref=u q:key=prefix /qv t=w Musterstadt /qv",
                     URL_J, "jobware")
    db.save_jobs([alt])
    db.save_jobs([kaputt])
    vorher = _zeilen(db)
    assert len(vorher) == 2 and sorted(z["is_active"] for z in vorher) == [0, 1]

    befund = karten_heilung.heilen(db)
    assert befund["zusammengefuehrt"] == 1

    nachher = _zeilen(db)
    assert len(nachher) == 1, "die aussortierte Doppelzeile bleibt nicht als Altlast"
    stelle = nachher[0]
    assert _oeffentlich(stelle["hash"]) == jobware.karten_hash(TITEL_J)
    assert (stelle["title"], stelle["company"], stelle["location"], stelle["is_active"]) == (
        TITEL_J, "Musterhandel GmbH", "Musterstadt", 1)

    db.save_jobs([_stelle(jobware.karten_hash(TITEL_J), TITEL_J, "Musterhandel GmbH",
                          "Musterstadt", URL_J, "jobware")])
    zeilen = _zeilen(db)
    assert len(zeilen) == 1 and zeilen[0]["is_active"] == 1


def test_verfaelschte_zeile_zieht_auf_die_richtige_kennung_um_samt_verweisen(db):
    kaputt_titel = f"t=f {TITEL_I}"
    db.save_jobs([_stelle(stelle_hash("ingenieur.de", kaputt_titel), kaputt_titel,
                          "t=g Muster Maschinenbau GmbH",
                          "qv q:s q:sref=n q:key= t=q Beispielhausen /qv", URL_I, "ingenieur_de")])
    alte_kennung = _zeilen(db)[0]["hash"]
    bewerbung = db.add_application({"job_hash": _oeffentlich(alte_kennung), "title": TITEL_I,
                                    "company": "Muster Maschinenbau GmbH", "status": "beworben"})

    befund = karten_heilung.heilen(db)
    assert befund["umgezogen"] == 1

    zeilen = _zeilen(db)
    assert len(zeilen) == 1
    neue_kennung = zeilen[0]["hash"]
    assert _oeffentlich(neue_kennung) == stelle_hash("ingenieur.de", TITEL_I)
    assert (zeilen[0]["title"], zeilen[0]["company"], zeilen[0]["location"]) == (
        TITEL_I, "Muster Maschinenbau GmbH", "Beispielhausen")
    conn = db.connect()
    verweis = conn.execute("SELECT job_hash FROM applications WHERE id=?", (bewerbung,)).fetchone()[0]
    assert _oeffentlich(verweis) == _oeffentlich(neue_kennung), "die Bewerbung wandert mit"
    fundstellen = [r[0] for r in conn.execute("SELECT job_hash FROM job_sources").fetchall()]
    assert fundstellen and all(f in (neue_kennung, _oeffentlich(neue_kennung)) for f in fundstellen)
    assert not conn.execute("SELECT 1 FROM jobs WHERE hash=?", (alte_kennung,)).fetchone()

    db.save_jobs([_stelle(stelle_hash("ingenieur.de", TITEL_I), TITEL_I, "Muster Maschinenbau GmbH",
                          "Beispielhausen", URL_I, "ingenieur_de")])
    zeilen = _zeilen(db)
    assert len(zeilen) == 1 and zeilen[0]["is_active"] == 1, "kein neues Duplikat"


def test_ein_verweis_in_oeffentlicher_form_wandert_ebenfalls(db):
    """Aeltere Wege legten den oeffentlichen Hash ab (v1.7.56 MERKE 4) — in
    gewachsenen Bestaenden gibt es solche Zeilen trotz Fremdschluessel. Das
    Ziel muss die GESPEICHERTE Kennung sein: eine oeffentliche Form als Ziel
    verletzte den Fremdschluessel, und die Heilung der Stelle rollte zurueck."""
    kaputt_titel = f"t=f {TITEL_I}"
    db.save_jobs([_stelle(stelle_hash("ingenieur.de", kaputt_titel), kaputt_titel, "t=g Muster GmbH",
                          "t=q Beispielhausen", URL_I, "ingenieur_de")])
    alte_kennung = _zeilen(db)[0]["hash"]
    bewerbung = db.add_application({"title": TITEL_I, "company": "Muster GmbH", "status": "beworben"})
    conn = db.connect()
    conn.execute("PRAGMA foreign_keys=OFF")  # Altbestand nachstellen
    with conn:
        conn.execute("UPDATE applications SET job_hash=? WHERE id=?", (_oeffentlich(alte_kennung), bewerbung))
    conn.execute("PRAGMA foreign_keys=ON")
    befund = karten_heilung.heilen(db)
    assert befund["umgezogen"] == 1
    neue_kennung = _zeilen(db)[0]["hash"]
    verweis = conn.execute("SELECT job_hash FROM applications WHERE id=?", (bewerbung,)).fetchone()[0]
    assert verweis == neue_kennung
    assert _oeffentlich(neue_kennung) == stelle_hash("ingenieur.de", TITEL_I)


def test_eine_firma_nur_aus_resten_wird_zum_platzhalter():
    felder = karten_heilung.saubere_felder({"title": "t=g Titel", "company": "t=h /qv", "location": ""})
    assert felder == {"title": "Titel", "company": "Unbekannt", "location": ""}


def test_altes_knopf_format_ohne_neufund_wird_bereinigt(db):
    db.save_jobs([_stelle(jobware.karten_hash(TITEL_J), f'Job"{TITEL_J}"ansehen', "Unbekannt",
                          "inMusterstadt", URL_J, "jobware")])
    kennung = _zeilen(db)[0]["hash"]
    befund = karten_heilung.heilen(db)
    assert befund["bereinigt"] == 1 and befund["umgezogen"] == befund["zusammengefuehrt"] == 0
    zeile = _zeilen(db)[0]
    assert (zeile["hash"], zeile["title"], zeile["location"]) == (kennung, TITEL_J, "Musterstadt")


def test_entfernung_und_score_werden_nachgezogen(db, monkeypatch):
    monkeypatch.setattr(geocoding_service, "geocode_and_calculate_distance", lambda ort, lat, lon: 12.5)
    monkeypatch.setattr(geocoding_service, "geocode_location", lambda ort: (53.6, 10.1))
    kaputt_titel = f"t=f {TITEL_I}"
    db.save_jobs([_stelle(stelle_hash("ingenieur.de", kaputt_titel), kaputt_titel, "t=g Muster GmbH",
                          "qv q:s q:key= t=q Beispielhausen /qv", URL_I, "ingenieur_de")])

    def bewerten(zeile):
        assert zeile["location"] == "Beispielhausen"
        zeile["_fachscore"], zeile["_rahmenscore"] = 4.0, 1.0
        return 5.0

    befund = karten_heilung.heilen(db, koordinaten=(53.5, 10.0), bewerten=bewerten)
    assert befund["entfernung_nachgezogen"] == 1 and befund["neu_bewertet"] == 1
    zeile = _zeilen(db)[0]
    assert (zeile["distance_km"], zeile["lat"], zeile["lon"], zeile["score"], zeile["fachscore"]) == (
        12.5, 53.6, 10.1, 5.0, 4.0)


def test_vorschau_schreibt_nichts_und_ein_zweiter_lauf_findet_nichts(db):
    kaputt_titel = f"t=3n {TITEL_J}"
    db.save_jobs([_stelle(jobware.karten_hash(kaputt_titel), kaputt_titel, "t=h Musterhandel GmbH",
                          "t=w Musterstadt", URL_J, "jobware")])
    vorher = _zeilen(db)
    vorschau = karten_heilung.heilen(db, dry_run=True)
    assert vorschau["umgezogen"] == 1 and _zeilen(db) == vorher
    assert karten_heilung.heilen(db)["umgezogen"] == 1
    zweiter = karten_heilung.heilen(db)
    assert zweiter["bereinigt"] == zweiter["umgezogen"] == zweiter["zusammengefuehrt"] == 0


def test_andere_quellen_und_zeilen_unbekannter_herkunft_behalten_ihre_kennung(db):
    db.save_jobs([
        _stelle("fremdequelle0001", "t=g Sachbearbeitung", "Muster GmbH", "Musterstadt",
                "https://example.com/job/1", "stepstone"),
        _stelle("vonhandgesetzt01", "t=g Sachbearbeitung Vertrieb", "Muster GmbH", "Musterstadt",
                "https://www.jobware.de/job/sachbearbeitung-vertrieb-900000009", "jobware"),
    ])
    karten_heilung.heilen(db)
    zeilen = {_oeffentlich(z["hash"]): z for z in _zeilen(db)}
    assert zeilen["fremdequelle0001"]["title"] == "t=g Sachbearbeitung", "andere Quelle unberuehrt"
    assert zeilen["vonhandgesetzt01"]["title"] == "Sachbearbeitung Vertrieb", "bereinigt, Kennung bleibt"


def test_der_suchlauf_heilt_vor_dem_speichern():
    from bewerbungs_assistent import job_scraper
    quelle = inspect.getsource(job_scraper.run_search)
    assert "karten_heilung" in quelle and "heilen(" in quelle
    assert quelle.index("heilen(") < quelle.index("db.save_jobs(unique)")
