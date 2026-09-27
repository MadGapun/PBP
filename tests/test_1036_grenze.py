"""#1036, die offenen Punkte: gleitende Naehe, eine Grenze, 0 bleibt 0.

- Die Naehe-Punkte standen in zwei Stufen: eine Stelle in 29 km bekam bei
  50 km Grenze dasselbe wie eine vor der Haustuer.
- Das Profil trug eine dritte Fassung der Vorgaben und machte aus einer
  eingetragenen 0 still 50 km (`|| 50`); der Server tat dasselbe (`> 0`).
- Die Datenguete verglich die rohe Luftlinie mit der rohen Karte und
  kannte weder die Vorgabe je Form noch die Fahrstrecke.

Alle Firmen und Orte sind Platzhalter.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


def _kriterien(**extra):
    k = {"keywords_muss": ["Einkauf"], "keywords_plus": [], "keywords_ausschluss": [],
         "gewichtung": {"naehe": 4, "muss": 2, "plus": 1, "minus": 1,
                        "remote": 2, "fern_malus": 3}}
    k.update(extra)
    return k


def _stelle(km, art="festanstellung"):
    return {"title": "Sachbearbeitung Einkauf", "company": "Musterfirma",
            "description": "Wir suchen Unterstuetzung im Einkauf. " * 5,
            "distance_km": km, "employment_type": art, "remote_level": "vor_ort"}


# ============================================================ die Kurve


def test_naehe_gleitend():
    from bewerbungs_assistent.services.entfernung import naehe_punkte
    assert naehe_punkte(0, 50, 4) == 4.0
    assert naehe_punkte(25, 50, 4) == 2.0
    assert naehe_punkte(50, 50, 4) == 0.0
    assert naehe_punkte(51, 50, 4) is None
    assert naehe_punkte(None, 50, 4) is None
    assert naehe_punkte(0, 0, 4) == 4.0, "Grenze 0: am Wohnort voll"
    assert naehe_punkte(1, 0, 4) is None


def test_zwei_nahe_stellen_sind_nicht_mehr_gleich():
    from bewerbungs_assistent.job_scraper import calculate_score
    nah, mittel = _stelle(5), _stelle(25)
    calculate_score(nah, _kriterien())
    calculate_score(mittel, _kriterien())
    assert nah["_rahmenscore"] > mittel["_rahmenscore"], \
        "bis v1.7.140 bekamen 5 und 25 km bei 50 km Grenze dieselben Punkte"


@pytest.mark.parametrize("km", [0, 10, 29, 31, 45, 50, 60, 120])
def test_beide_rechenwege_gleich(km):
    """#963: calculate_score und fit_analyse rechnen dieselbe Naehe."""
    from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse
    job = _stelle(km)
    calculate_score(job, _kriterien())
    fit = fit_analyse(_stelle(km), _kriterien())
    assert fit["rahmenscore"] == job["_rahmenscore"]


# ============================================================ die Grenze


def test_eingetragene_null_bleibt_null():
    from bewerbungs_assistent.services.entfernung import grenze_km
    assert grenze_km({"max_entfernung": {"festanstellung": 0}}, "festanstellung") == 0
    assert grenze_km({"max_entfernung": {"festanstellung": 30}}, "festanstellung") == 30
    assert grenze_km({"max_entfernung": {}}, "festanstellung") == 50
    assert grenze_km({"max_entfernung": {"festanstellung": -5}}, "festanstellung") == 50


def test_null_heisst_nur_am_wohnort():
    from bewerbungs_assistent.job_scraper import calculate_score
    zuhause, weg = _stelle(0), _stelle(8)
    k = _kriterien(max_entfernung={"festanstellung": 0})
    calculate_score(zuhause, k)
    calculate_score(weg, k)
    assert zuhause["_rahmenscore"] > 0
    assert weg["_rahmenscore"] < 0


def test_datenguete_nimmt_die_vorgabe_und_die_grenze():
    """Ohne eigenen Eintrag galt eine Festanstellung nie als zu weit."""
    from bewerbungs_assistent.services import datenguete
    stand, grund = datenguete._entfernung(_stelle(300), _kriterien())
    assert stand == datenguete.VERLETZT
    assert "50 km" in grund and "Luftlinie" in grund
    stand, _ = datenguete._entfernung(_stelle(30), _kriterien())
    assert stand == datenguete.GEPRUEFT


def test_datenguete_sieht_die_fahrstrecke_nur_mit_haken():
    from bewerbungs_assistent.services import datenguete
    job = dict(_stelle(40), fahrstrecke_km=80)
    assert datenguete._entfernung(job, _kriterien())[0] == datenguete.GEPRUEFT
    stand, grund = datenguete._entfernung(job, _kriterien(_fahrstrecke_zaehlt=True))
    assert stand == datenguete.VERLETZT and "Fahrstrecke" in grund


# ================================================================ Server


@pytest.fixture
def client(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    import importlib
    from bewerbungs_assistent import database
    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "grenze.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.switch_profile(db.create_profile("Grenze"))
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    vorher = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app), db
    finally:
        dash._db = vorher
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_vorgaben_kommen_vom_server(client):
    from bewerbungs_assistent.services.entfernung import VORGABE_GRENZE_KM
    c, _ = client
    antwort = c.get("/api/entfernung/vorgaben").json()
    assert antwort["grenzen"] == VORGABE_GRENZE_KM
    # Leere Kriterien bleiben leer (#927) — die Vorgaben stehen nicht darin.
    assert "_grenze_vorgaben" not in c.get("/api/search-criteria").json()


def test_null_wird_gespeichert_und_gelesen(client):
    c, db = client
    c.post("/api/search-criteria", json={"max_entfernung": {"festanstellung": 0}})
    assert db.get_search_criteria()["max_entfernung"] == {"festanstellung": 0}


# ============================================================ Oberflaeche


def _profil():
    return (_repo() / "frontend" / "src" / "pages" / "ProfilePage.jsx").read_text(encoding="utf-8-sig")


def test_profil_ohne_eigene_vorgabetabelle():
    seite = _profil()
    assert "DEFAULT_MAX_ENTFERNUNG" not in seite
    import re
    funde = re.findall(r"Number\([^()]*max_entfernung[^()]*\)\s*\|\|\s*\d+", seite)
    assert not funde, funde
    assert 'optionalApi("/api/entfernung/vorgaben")' in seite


def test_profil_nennt_dieselben_formen_wie_der_filter():
    seite = _profil()
    assert "Object.entries(ANSTELLUNGSFORM_TEXT)" in seite
    assert '{ value: "teilzeit", label: "Teilzeit" }' not in seite
    assert 'data-testid="teilzeit-ist-umfang"' in seite
