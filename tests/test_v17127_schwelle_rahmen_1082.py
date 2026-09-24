"""Tests fuer v1.7.127 — #1082: die Schwelle vergleicht den Fachwert.

Gemeldet am 23.09.2026: eine fachlich starke Stelle in rund 450 km
verschwand aus der Liste. Vier Ursachen, gefunden beim Nachsehen:

1. Die Liste rechnete die Scoring-Regler fuer Entfernung, Remote und
   Gehalt in den Wert, gegen den die Schwelle hielt — und kappte bei 0.
2. Die Schwelle las die rohe Zahl und ignorierte die Stufe aus #1063.
3. Der Stellen-Tab wandte die Schwelle nie an, obwohl die Einstellung
   "blendet in der Liste aus" versprach.
4. Der Fachdaumen las denselben vermischten Wert.

Dazu AK 3: nennt die Anzeige einen naeheren Standort, zaehlt dieser.
Alle Orte hier sind erfunden.
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

HEIM = (53.50, 10.00)
NAH = (53.55, 10.05)          # rund 6 km vom Wohnort
FERN = (49.50, 8.50)          # rund 450 km vom Wohnort


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


def _werkzeug(db, name):
    from bewerbungs_assistent.tools import jobs as job_tools

    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    job_tools.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt[name]


def _stelle(hash_, score, distance_km=None, **extra):
    stelle = {
        "hash": hash_, "title": f"Fachrolle {hash_}", "company": f"Musterwerk {hash_} GmbH",
        "location": "Fernstadt", "score": score,
        "url": f"https://example.org/stelle/{hash_}", "source": "manuell",
        "description": "Eine ausfuehrliche Stellenbeschreibung. " * 8,
    }
    if distance_km is not None:
        stelle["distance_km"] = distance_km
    stelle.update(extra)
    return stelle


def _entfernung_kostet(db, punkte):
    """Jede Entfernungsstufe kostet `punkte` — der gemeldete Fall."""
    for dim in ("entfernung_fest", "entfernung_freelance"):
        for eintrag in db.get_scoring_config(dim):
            db.set_scoring_config(dim, eintrag["sub_key"], punkte)
        db.set_scoring_config(dim, "999", punkte)


# --- Ursache 1: Rahmen blendet nicht aus, keine Kappung -----------------

def test_1082_fachstarke_ferne_stelle_bleibt_sichtbar(db):
    db.save_jobs([_stelle("fern01", 10, distance_km=450)])
    _entfernung_kostet(db, -15)
    db.set_scoring_config("schwellenwert", "auto_ignore", 5)

    antwort = _werkzeug(db, "stellen_anzeigen")()
    assert antwort["anzahl_gesamt"] == 1, antwort
    stelle = antwort["stellen"][0] if "stellen" in antwort else antwort["jobs"][0]
    assert stelle["fach_score"] == 10
    # Keine Kappung bei 0: ein negativer Wert darf nicht wie 0 aussehen.
    assert stelle["score"] < 0
    assert antwort["durch_rahmen_nicht_mehr_verborgen"] == 1
    assert "durch_schwelle_verborgen" not in antwort


def test_1082_regler_ergebnis_trennt_fach_und_rahmen(db):
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments
    _entfernung_kostet(db, -15)
    db.set_scoring_config("schwellenwert", "auto_ignore", 5)
    ergebnis = apply_scoring_adjustments(
        {"distance_km": 450, "employment_type": "festanstellung"}, 10, db)
    assert ergebnis["final_score"] < 0
    assert ergebnis["fach_score"] == 10
    assert ergebnis["rahmen_adjustment"] <= -15
    assert ergebnis["final_score"] == round(10 + ergebnis["rahmen_adjustment"], 1)
    assert ergebnis["ignored"] is False
    assert ergebnis["unter_schwelle"] is False
    assert ergebnis["nur_durch_rahmen_unter_schwelle"] is True


def test_1082_fachschwache_stelle_bleibt_verborgen(db):
    """Gegenrichtung: der Fachwert unter der Schwelle blendet weiter aus."""
    db.save_jobs([_stelle("schwach1", 2, distance_km=5)])
    db.set_scoring_config("schwellenwert", "auto_ignore", 5)
    antwort = _werkzeug(db, "stellen_anzeigen")()
    assert antwort.get("anzahl", 0) == 0
    assert antwort["durch_schwelle_verborgen"] == 1
    assert antwort["davon_allein_durch_rahmen"] == 0
    assert "FACHWERT" in antwort["schwelle_vergleicht"]


# --- AK 2: alle aktiven Stellen ohne Schwelle ----------------------------

def test_1082_ohne_schwelle_liefert_alle(db):
    db.save_jobs([_stelle("schwach1", 2), _stelle("stark01", 20)])
    db.set_scoring_config("schwellenwert", "auto_ignore", 5)
    antwort = _werkzeug(db, "stellen_anzeigen")(ohne_schwelle=True)
    assert antwort["anzahl_gesamt"] == 2
    stellen = antwort.get("stellen") or antwort.get("jobs")
    markiert = {s["hash"].split(":")[-1]: s.get("unter_schwelle") for s in stellen}
    assert markiert["schwach1"] is True
    assert not markiert["stark01"]


def test_1082_ohne_schwelle_hebt_kein_ausdrueckliches_ignorieren_auf(db):
    """Nur die Schwelle darf fuer einen Aufruf aufgehoben werden."""
    db.save_jobs([_stelle("zeitarb1", 20, employment_type="zeitarbeit")])
    db.set_scoring_config("stellentyp", "zeitarbeit", 0, ignore_flag=True)
    antwort = _werkzeug(db, "stellen_anzeigen")(ohne_schwelle=True)
    assert antwort.get("anzahl_gesamt", 0) == 0


# --- Ursache 2: die Stufe gewinnt ----------------------------------------

def test_1082_schwelle_kommt_aus_dem_nadeloehr(db, monkeypatch):
    """Die rohe Zahl steht auf 0 — die gewaehlte Stufe verlangt 50."""
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments
    monkeypatch.setattr(db, "get_scoring_threshold", lambda: 50.0)
    ergebnis = apply_scoring_adjustments({"employment_type": "festanstellung"}, 10, db)
    assert ergebnis["unter_schwelle"] is True
    assert ergebnis["ignored"] is True


# --- Ursache 3: der Stellen-Tab blendet aus und nennt die Zahl ----------

def test_1082_stellen_tab_blendet_unter_schwelle_aus():
    from bewerbungs_assistent.services import stellen_liste
    jobs = [{"hash": "a", "title": "A", "score": 20},
            {"hash": "b", "title": "B", "score": 2, "unter_schwelle": True}]
    antwort = stellen_liste.aufbereiten(jobs, {"rahmen_ausblenden": False})
    assert [j["hash"] for j in antwort["jobs"]] == ["a"]
    assert antwort["schwelle_verborgen"] == 1

    aus = stellen_liste.aufbereiten(
        jobs, {"rahmen_ausblenden": False, "schwelle_ausblenden": "false"})
    assert len(aus["jobs"]) == 2
    assert aus["schwelle_verborgen"] == 0


def test_1082_liste_markiert_unter_schwelle(db):
    db.save_jobs([_stelle("schwach1", 2), _stelle("stark01", 20)])
    db.set_scoring_config("schwellenwert", "auto_ignore", 5)
    jobs = db.get_active_jobs()
    db._mit_scoring_reglern(jobs, sortieren=False)
    markiert = {j["hash"].split(":")[-1]: j["unter_schwelle"] for j in jobs}
    assert markiert == {"schwach1": True, "stark01": False}


def test_1082_frontend_kennt_den_schalter():
    quelle = (_repo() / "frontend" / "src" / "pages" / "JobsPage.jsx").read_text(
        encoding="utf-8")
    assert "schwelleAusblenden: true" in quelle
    assert 'p.set("schwelle_ausblenden", "false")' in quelle
    assert "({schwelleVerborgen})" in quelle


# --- Ursache 4: der Fachdaumen liest den Fachwert ------------------------

def test_1082_fachdaumen_liest_den_fachwert(monkeypatch):
    from bewerbungs_assistent.services import fachwert, indikatoren
    gesehen = []
    monkeypatch.setattr(fachwert, "daumen",
                        lambda punkte, *a, **kw: gesehen.append(punkte) or {"richtung": "hoch"})
    indikatoren.fuer_stelle({"score": -5, "fach_score": 10}, {"schwellen": {}})
    assert gesehen == [10]


# --- AK 3: ein naeherer Standort aus der Anzeige zaehlt ------------------

_KRIT = {"standort_lat": HEIM[0], "standort_lon": HEIM[1],
         "_standorte": {"nahdorf": list(NAH), "fernstadt": list(FERN)}}


def test_1082_standorte_nur_im_standort_zusammenhang():
    from bewerbungs_assistent.services import standorte
    assert standorte.genannte_orte(
        "Standorte: Fernstadt, Nahdorf oder Drittort.") == ["Fernstadt", "Nahdorf", "Drittort"]
    assert standorte.genannte_orte("Hybrid von Nahdorf aus.") == ["Nahdorf aus"]
    assert standorte.genannte_orte("Unsere Kunden sitzen in Nahdorf.") == []


def test_1082_naeherer_standort_zaehlt_fuer_die_entfernung():
    from bewerbungs_assistent.services import entfernung
    job = {"location": "Fernstadt", "distance_km": 450,
           "description": "Einsatzort: Fernstadt oder Nahdorf (hybrid)."}
    km = entfernung.preis_km(job, _KRIT)
    assert km is not None and km < 10


def test_1082_ferner_oder_unbekannter_standort_aendert_nichts():
    from bewerbungs_assistent.services import entfernung, standorte
    nah = {"location": "Nahdorf", "distance_km": 6,
           "description": "Weitere Standorte: Fernstadt, Unbekanntheim."}
    assert standorte.naechster(nah, _KRIT) is None
    assert entfernung.preis_km(nah, _KRIT) == 6
    # Ohne Verzeichnis: das Verhalten von vorher.
    fern = {"location": "Fernstadt", "distance_km": 450,
            "description": "Standort: Nahdorf."}
    assert entfernung.preis_km(fern, {"standort_lat": HEIM[0]}) == 450


def test_1082_standort_gegen_fahrstrecke_umgerechnet():
    from bewerbungs_assistent.services import entfernung
    job = {"location": "Fernstadt", "distance_km": 450, "fahrstrecke_km": 600,
           "description": "Arbeitsort: Nahdorf."}
    krit = dict(_KRIT, _fahrstrecke_zaehlt=True)
    luft = entfernung.preis_km(job, _KRIT)
    fahrt = entfernung.preis_km(job, krit)
    assert fahrt == round(luft * entfernung.FAHRSTRECKEN_FAKTOR, 1)


def test_1082_verzeichnis_kommt_aus_dem_bestand(db):
    from bewerbungs_assistent.services import scoring_kriterien, standorte
    db.save_jobs([_stelle("ort01", 5, lat=NAH[0], lon=NAH[1], location="Nahdorf (Hybrid)")])
    orte = standorte.verzeichnis(db)
    assert "nahdorf" in orte

    # Ohne Wohnort kein Verzeichnis in den Kriterien (nur mit Inhalt).
    assert "_standorte" not in scoring_kriterien.fuer_scoring(db)
    db.set_search_criteria("standort_lat", HEIM[0])
    db.set_search_criteria("standort_lon", HEIM[1])
    assert "nahdorf" in scoring_kriterien.fuer_scoring(db)["_standorte"]


def test_1082_liste_nennt_den_naeheren_standort():
    from bewerbungs_assistent.services import indikatoren
    job = {"location": "Fernstadt", "distance_km": 450, "score": 5,
           "description": "Standorte: Fernstadt oder Nahdorf."}
    indikatoren.anhaengen([job], {"kriterien": _KRIT, "schwellen": {}})
    assert job["naechster_standort"]["ort"] == "Nahdorf"


def test_1082_regler_rechnen_mit_dem_naeheren_standort(db):
    """Auch die Entfernungs-Regler nehmen den naeheren Standort — sonst
    rechneten Regler und Rahmendaumen verschieden."""
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments
    db.save_jobs([_stelle("ort01", 5, lat=NAH[0], lon=NAH[1], location="Nahdorf")])
    db.set_search_criteria("standort_lat", HEIM[0])
    db.set_search_criteria("standort_lon", HEIM[1])
    _entfernung_kostet(db, -15)
    for dim in ("entfernung_fest",):
        db.set_scoring_config(dim, "30", 0)
    job = {"location": "Fernstadt", "distance_km": 450, "employment_type": "festanstellung",
           "description": "Standorte: Fernstadt oder Nahdorf."}
    ergebnis = apply_scoring_adjustments(job, 10, db)
    assert ergebnis["rahmen_adjustment"] == 0, ergebnis["adjustments"]


def test_1082_fit_analyse_sagt_wenn_die_stelle_unter_der_schwelle_liegt(db):
    db.save_jobs([_stelle("schwach1", 2)])
    db.set_scoring_config("schwellenwert", "auto_ignore", 50)
    fit = _werkzeug(db, "fit_analyse")("schwach1")
    assert fit.get("unter_schwelle") is True
    assert "FACHWERT" in fit["schwellen_hinweis"]
