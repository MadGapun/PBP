"""#954: Je Feld belegt / geschätzt / unbekannt, mit Methode und Zeitpunkt.

Geprüft wird an gespeicherten Stellen, nicht an handgebauten dicts — die
Kennzeichnung soll aus dem entstehen, was PBP wirklich ablegt (AK 6).
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"
LANG = "Aufgaben und Anforderungen der Stelle, ausführlich beschrieben. " * 4


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Herkunft"})
    yield d
    _threads_abwarten()
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _threads_abwarten():
    import threading
    for t in threading.enumerate():
        if t.name.startswith("pbp-"):
            t.join(timeout=10)


def _stelle(db, kennung, **mehr):
    job = {"hash": kennung, "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
           "url": f"https://example.com/{kennung}", "source": "manuell",
           "location": "Musterstadt", "description": LANG, "score": 3}
    job.update(mehr)
    db.save_jobs([job])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE ?",
                                (f"%{kennung}",)).fetchone()[0]
    return db.get_job(voll)


def _felder(db, job):
    from bewerbungs_assistent.services import wahrheit
    return wahrheit.felder(job, db.get_search_criteria())


# ── AK 1: die sechs Felder ──────────────────────────────────────────

def test_sechs_felder_mit_guete_methode_zeitpunkt(db):
    from bewerbungs_assistent.services import wahrheit
    f = _felder(db, _stelle(db, "a954"))
    assert tuple(f) == wahrheit.FELDER
    for eintrag in f.values():
        assert eintrag["guete"] in wahrheit.STUFEN
        assert eintrag["methode"]
        assert "erhoben_am" in eintrag


# ── Entfernung ──────────────────────────────────────────────────────

def test_luftlinie_ist_geschaetzt_mit_zeitpunkt(db):
    f = _felder(db, _stelle(db, "b954", distance_km=12.0))
    assert f["entfernung"]["guete"] == "geschaetzt"
    assert f["entfernung"]["methode"] == "luftlinie"
    assert f["entfernung"]["erhoben_am"], "kein Erhebungszeitpunkt"


def test_von_hand_gesetzte_entfernung_heisst_nicht_luftlinie(db):
    job = _stelle(db, "c954", distance_km=80.0)
    # Der Stempel vom ersten Speichern darf nicht einfach stehen bleiben.
    db.connect().execute("UPDATE jobs SET entfernung_am='2020-01-01T00:00:00' "
                         "WHERE hash LIKE '%c954'")
    db.connect().commit()
    db.set_job_entfernung(job["hash"], 5)
    f = _felder(db, db.get_job(job["hash"]))
    assert f["entfernung"]["guete"] == "belegt"
    assert f["entfernung"]["methode"] == "von_hand"
    assert "Luftlinie" not in f["entfernung"]["text"]
    assert f["entfernung"]["erhoben_am"] and not f["entfernung"]["erhoben_am"].startswith("2020")


def test_fahrstrecke_ist_belegt(db):
    f = _felder(db, _stelle(db, "d954", distance_km=30.0, fahrstrecke_km=41.0,
                            fahrzeit_min=35, route_quelle="ors"))
    assert (f["entfernung"]["guete"], f["entfernung"]["methode"]) == ("belegt", "routing")


def test_ohne_entfernung_unbekannt(db):
    f = _felder(db, _stelle(db, "e954"))
    assert f["entfernung"]["guete"] == "unbekannt"


def test_fit_analyse_nennt_fahrstrecke_und_handwert_nicht_luftlinie(db):
    from bewerbungs_assistent.job_scraper import fit_analyse
    job = _stelle(db, "f954", distance_km=80.0)
    db.set_job_entfernung(job["hash"], 5)
    krit = {"keywords_muss": ["Sachbearbeitung"]}
    faktoren = " ".join(fit_analyse(db.get_job(job["hash"]), krit)["factors"])
    assert "Luftlinie" not in faktoren
    assert "von dir eingetragen" in faktoren
    routed = _stelle(db, "g954", distance_km=30.0, fahrstrecke_km=41.0)
    faktoren = " ".join(fit_analyse(routed, {**krit, "_fahrstrecke_zaehlt": True})["factors"])
    assert "Fahrstrecke" in faktoren and "Luftlinie" not in faktoren


# ── AK 3: #827 unverändert ──────────────────────────────────────────

def test_geschaetztes_gehalt_bleibt_neutral_und_ist_gekennzeichnet(db):
    from bewerbungs_assistent.job_scraper import calculate_score
    krit = {"keywords_muss": ["Sachbearbeitung"], "min_gehalt": 50000}
    ohne = calculate_score({"title": "Sachbearbeitung", "description": LANG}, krit)
    mit = calculate_score({"title": "Sachbearbeitung", "description": LANG,
                           "salary_min": 90000, "salary_max": 100000,
                           "salary_type": "jaehrlich", "salary_estimated": 1}, krit)
    assert mit == ohne, "eine Schätzung darf nicht zählen (#827)"
    f = _felder(db, _stelle(db, "h954", salary_min=90000, salary_max=100000,
                            salary_type="jaehrlich", salary_estimated=1))
    assert (f["gehalt"]["guete"], f["gehalt"]["methode"]) == ("geschaetzt", "schaetzung_titel_ort")


def test_gehalt_aus_der_anzeige_ist_belegt(db):
    f = _felder(db, _stelle(db, "i954", salary_min=50000, salary_max=60000,
                            salary_type="jaehrlich", salary_estimated=0))
    assert (f["gehalt"]["guete"], f["gehalt"]["methode"]) == ("belegt", "anzeige")


# ── AK 2: Anforderungen dreiwertig, Text-Vollständigkeit ────────────

def test_gekappter_text_macht_anforderungen_unbekannt(db):
    f = _felder(db, _stelle(db, "j954", description="x" * 2000))
    assert f["beschreibung"]["guete"] == "unbekannt"
    assert f["beschreibung"]["methode"] == "gekappt"
    assert f["anforderungen"]["guete"] == "unbekannt"


def test_fehlender_text_macht_anforderungen_unbekannt(db):
    f = _felder(db, _stelle(db, "k954", description="kurz"))
    assert f["beschreibung"]["methode"] == "fehlt"
    assert f["anforderungen"]["guete"] == "unbekannt"


def test_voller_text_belegt(db):
    f = _felder(db, _stelle(db, "l954"))
    assert f["beschreibung"]["guete"] == "belegt"
    assert f["anforderungen"]["guete"] == "belegt"


def test_veroeffentlichung_unbekannt_oder_belegt(db):
    assert _felder(db, _stelle(db, "m954"))["veroeffentlicht"]["guete"] == "unbekannt"
    f = _felder(db, _stelle(db, "n954", veroeffentlicht_am="2026-09-01"))
    assert f["veroeffentlicht"]["guete"] == "belegt"


# ── Score-Grundlage ─────────────────────────────────────────────────

def _bewertet(db, kennung, **mehr):
    from bewerbungs_assistent.job_scraper import calculate_score
    job = {"hash": kennung, "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
           "url": f"https://example.com/{kennung}", "source": "manuell",
           "description": LANG, **mehr}
    job["score"] = calculate_score(job, {"keywords_muss": ["Sachbearbeitung"]})
    db.save_jobs([job])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE ?",
                                (f"%{kennung}",)).fetchone()[0]
    return db.get_job(voll)


def test_bewerteter_lauf_stempelt_die_grundlage(db):
    job = _bewertet(db, "o954")
    assert job["score_am"] and job["score_stand"].startswith("t=")
    assert _felder(db, job)["score"]["guete"] == "belegt"


def test_unbewertete_aktualisierung_laesst_grundlage_stehen(db):
    job = _bewertet(db, "p954")
    vorher = (job["score_am"], job["score_stand"])
    db.save_jobs([{"hash": "p954", "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/p954", "source": "manuell",
                   "description": LANG, "score": 0}])
    assert (db.get_job(job["hash"])["score_am"], db.get_job(job["hash"])["score_stand"]) == vorher


def test_geaenderter_text_macht_grundlage_ueberholt(db):
    job = _bewertet(db, "q954")
    db.update_job(job["hash"], {"description": LANG + " Neuer Absatz mit weiteren Anforderungen."})
    f = _felder(db, db.get_job(job["hash"]))
    assert f["score"]["methode"] == "ueberholt"
    assert "Anzeigentext" in f["score"]["text"]


def test_geaenderte_kriterien_machen_grundlage_ueberholt(db):
    job = _bewertet(db, "r954")
    db.set_search_criteria("keywords_muss", ["Buchhaltung"])
    assert _felder(db, db.get_job(job["hash"]))["score"]["methode"] == "ueberholt"


def test_update_job_mit_score_stempelt(db):
    job = _stelle(db, "s954")
    assert _felder(db, job)["score"]["guete"] == "unbekannt", "Altbestand ohne Grundlage"
    db.update_job(job["hash"], {"score": 4.0})
    f = _felder(db, db.get_job(job["hash"]))
    assert f["score"]["guete"] == "belegt"


def test_handscore_ist_von_hand(db):
    job = _stelle(db, "t954")
    db.update_job_score(job["hash"], 9)
    assert _felder(db, db.get_job(job["hash"]))["score"]["methode"] == "von_hand"


# ── AK 5: vier Werkzeuge, AK 4: kein Schalter ──────────────────────

def _werkzeug(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #954")
    register_all(mcp, db, logging.getLogger("test.954"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def test_vier_werkzeuge_geben_die_kennzeichnung_aus(db):
    db.set_search_criteria("keywords_muss", ["Sachbearbeitung"])
    job = _stelle(db, "u954", distance_km=12.0)
    kurz = job["hash"].split(":")[-1]
    fit = _werkzeug(db, "fit_analyse", {"job_hash": kurz})
    assert fit["herkunft"]["entfernung"]["guete"] == "geschaetzt"
    vorschau = _werkzeug(db, "scoring_vorschau", {"job_hash": kurz})
    assert "herkunft" in vorschau
    liste = _werkzeug(db, "stellen_anzeigen", {"ohne_schwelle": True})
    zeilen = liste.get("stellen") or liste.get("jobs") or []
    assert any("Entfernung geschätzt" in (z.get("herkunft") or "") for z in zeilen), zeilen
    angelegt = _werkzeug(db, "stelle_manuell_anlegen", {
        "titel": "Lagerlogistik", "firma": "Musterbetrieb GmbH",
        "beschreibung": LANG, "url": "https://example.com/v954"})
    assert "herkunft" in angelegt, angelegt


def test_kein_neuer_schalter():
    text = (SRC / "services" / "wahrheit.py").read_text(encoding="utf-8")
    assert "get_setting" not in text and "get_profile_setting" not in text


def test_dashboard_liefert_herkunft(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    _stelle(db, "w954", distance_km=12.0)
    daten = TestClient(dash.app).get("/api/jobs").json()
    zeilen = daten.get("jobs", daten) if isinstance(daten, dict) else daten
    zeile = next(z for z in zeilen if z["hash"].endswith("w954"))
    assert zeile["herkunft"]["entfernung"]["guete"] == "geschaetzt"


# ── AK 7: Hinweis nach dem Update ───────────────────────────────────

def test_hinweis_solange_grundlage_unbekannt(db):
    from bewerbungs_assistent.services.onboarding_hints import _condition_herkunft_neu
    job = _stelle(db, "x954")
    assert _condition_herkunft_neu(db) is True
    db.update_job(job["hash"], {"score": 3.0})
    assert _condition_herkunft_neu(db) is False


def test_bleibt_der_hoehere_alte_score_bleibt_seine_grundlage(db):
    """save_jobs behaelt den hoeheren alten Score. Dann gehoert auch die
    alte Grundlage dazu — nicht die des Laufs, der verloren hat."""
    job = _bewertet(db, "y954")
    vorher = job["score_stand"]
    assert job["score"] > 0
    db.save_jobs([{"hash": "y954", "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/y954", "source": "manuell",
                   "description": "Ganz anderer Text ohne Treffer. " * 5,
                   "score": 0.0, "_fachscore": 0.0, "_rahmenscore": 0.0}])
    nachher = db.get_job(job["hash"])
    assert nachher["score"] == job["score"]
    assert nachher["score_stand"] == vorher


def test_neuer_standort_stempelt_die_entfernung(db, monkeypatch):
    from bewerbungs_assistent.services import eigener_standort as es
    from bewerbungs_assistent.services import geocoding_service as gs
    monkeypatch.setattr(gs, "geocode_location",
                        lambda o: {"Hamburg": (53.55, 10.0), "Musterstadt": (53.0, 9.0)}.get(o))
    db.save_profile({"name": "Herkunft", "city": "Hamburg"})
    _threads_abwarten()
    job = _stelle(db, "z954")
    es.entfernungen_nachziehen(db, alle=True, max_orte=None)
    f = _felder(db, db.get_job(job["hash"]))
    assert f["entfernung"]["guete"] == "geschaetzt" and f["entfernung"]["erhoben_am"]
