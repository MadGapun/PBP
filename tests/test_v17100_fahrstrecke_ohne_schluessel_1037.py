"""Tests fuer #1037 Punkt 3 (C81): ohne Routing-Schluessel gilt die Luftlinie.

Die Rueckfrage beim Entfernen des Schluessels versprach "PBP rechnet danach
wieder mit der Luftlinie". `entfernung.preis_km` kannte den Schluessel aber
nicht: an Stellen mit gespeicherter Fahrstrecke rechneten Score, Regler und
Auto-Aussortierung weiter mit ihr.

Alle Firmen und Orte sind Platzhalter.
"""
import importlib
import inspect
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "routing.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.switch_profile(datenbank.create_profile("Routing"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _stelle():
    # Luftlinie 30 km, Fahrstrecke 90 km — die beiden Zahlen liegen auf
    # verschiedenen Seiten der Grenze von 50 km.
    return {"title": "Sachbearbeitung Einkauf", "company": "Musterfirma",
            "distance_km": 30.0, "fahrstrecke_km": 90.0,
            "employment_type": "festanstellung"}


def _schluessel_setzen(db, wert):
    from bewerbungs_assistent.services import routing

    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, wert)


# ====================================================== preis_km


@pytest.mark.parametrize("kriterien, erwartet", [
    ({"_fahrstrecke_zaehlt": True}, 90.0),
    ({"_fahrstrecke_zaehlt": False}, 30.0),
    # Kriterien ohne Angabe: kein Schluessel, also die Luftlinie
    ({}, 30.0),
    # gar keine Kriterien: bisheriges Verhalten (der Guard verbietet das
    # in jedem Rechenweg)
    (None, 90.0),
])
def test_preis_km_folgt_dem_schluessel(kriterien, erwartet):
    from bewerbungs_assistent.services import entfernung

    assert entfernung.preis_km(_stelle(), kriterien) == erwartet


def test_ohne_fahrstrecke_bleibt_die_luftlinie():
    from bewerbungs_assistent.services import entfernung

    job = {"distance_km": 12.5}
    assert entfernung.preis_km(job, {"_fahrstrecke_zaehlt": True}) == 12.5
    assert entfernung.preis_km(job, {"_fahrstrecke_zaehlt": False}) == 12.5


# ====================================================== die Kriterien wissen es


def test_kriterien_tragen_ob_ein_schluessel_eingerichtet_ist(db):
    _schluessel_setzen(db, "")
    assert "_fahrstrecke_zaehlt" not in db.get_search_criteria()
    _schluessel_setzen(db, "test-schluessel-ohne-bedeutung")
    assert db.get_search_criteria()["_fahrstrecke_zaehlt"] is True


def test_ohne_schluessel_bleiben_leere_kriterien_leer(db):
    """Opt-in wie die uebrigen Injektionen. Die erste Fassung setzte den
    Eintrag IMMER — leere Kriterien waren danach nicht mehr leer, und ein
    frisches Profil verlor den Hinweis auf den naechsten Schritt (#927)."""
    _schluessel_setzen(db, "")
    assert db.get_search_criteria() == {}


def test_der_schluessel_steht_nie_in_den_kriterien(db):
    """Die Kriterien landen in Antworten und Exporten — der Schluessel nie."""
    geheim = "test-schluessel-ohne-bedeutung"
    _schluessel_setzen(db, geheim)
    assert geheim not in repr(db.get_search_criteria())


# ====================================================== Wirkung in der Automatik


def test_nach_dem_entfernen_rechnet_die_automatik_mit_der_luftlinie(db):
    """Meldefall: Schluessel entfernt, Fahrstrecke steht noch an der Stelle."""
    from bewerbungs_assistent.services import routing
    from bewerbungs_assistent.services import stellen_automatik as sa

    db.set_search_criteria("max_entfernung", {"festanstellung": 50})
    _schluessel_setzen(db, "test-schluessel-ohne-bedeutung")
    assert sa._zahl_widerspricht(db, _stelle(), "zu_weit_entfernt") == ""

    routing.schluessel_entfernen(db)
    hinweis = sa._zahl_widerspricht(db, _stelle(), "zu_weit_entfernt")
    assert "30.0 km" in hinweis, hinweis


def test_nach_dem_entfernen_rechnet_der_score_mit_der_luftlinie(db):
    from bewerbungs_assistent import job_scraper
    from bewerbungs_assistent.services import routing

    db.set_search_criteria("max_entfernung", {"festanstellung": 50})
    _schluessel_setzen(db, "test-schluessel-ohne-bedeutung")
    # v1.7.117 (#1052): die Zusage der Rueckfrage ("PBP rechnet danach
    # wieder mit der Luftlinie") wirkt im Rahmenwert — der Score ist seit
    # der Trennung der Fachwert und kennt die Entfernung nicht mehr.
    def _rahmen():
        j = dict(_stelle())
        job_scraper.calculate_score(j, db.get_search_criteria())
        return j["_rahmenscore"]

    mit = _rahmen()
    routing.schluessel_entfernen(db)
    ohne = _rahmen()
    assert ohne > mit, (mit, ohne)


def test_ohne_schluessel_kostet_die_fahrstrecke_im_regler_nichts_extra(db):
    """Die Gegenrichtung zu #950 AK 6 fuer den Regler-Zuschlag.

    Gegenprobe v1.7.100: ohne diesen Fall fing nur der Quelltext-Guard den
    Regler ohne Kriterien — ein Guard, der eine Zeichenkette prueft, belegt
    nicht die Wirkung (v1.7.93 MERKE 3)."""
    from bewerbungs_assistent.services import routing
    from bewerbungs_assistent.services.scoring_service import (
        apply_scoring_adjustments)

    routing.schluessel_entfernen(db)
    nah = apply_scoring_adjustments({"distance_km": 20}, 50, db)
    mit_route = apply_scoring_adjustments(
        {"distance_km": 20, "fahrstrecke_km": 400}, 50, db)
    assert mit_route["final_score"] == nah["final_score"], (nah, mit_route)


def test_die_rueckfrage_nennt_den_weg_zu_den_gespeicherten_scores(db):
    from bewerbungs_assistent.services import routing

    antwort = routing.schluessel_entfernen(db)
    assert "Luftlinie" in antwort["hinweis"]
    assert "scores_neu_berechnen" in antwort["hinweis"]


# ====================================================== Guard


def test_kein_rechenweg_ruft_preis_km_ohne_kriterien():
    """Ein Aufrufer ohne Kriterien saehe den Schluessel nicht — genau der
    gemeldete Fehler, nur an der naechsten Stelle."""
    quelle = _repo() / "src" / "bewerbungs_assistent"
    treffer = []
    for datei in quelle.rglob("*.py"):
        if datei.name == "entfernung.py":
            continue
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"preis_km\(\s*job\s*\)", zeile):
                treffer.append(f"{datei.relative_to(quelle)}:{nr}")
    assert not treffer, treffer
