"""#1118: ein Suchlauf blieb dauerhaft auf "laeuft" und blockierte jeden
neuen Start.

Kette aus dem Melder-Bericht: die Entfernungs-Nachrechnung hielt die
Schreibsperre ueber alle Geocoder-Anfragen, der gleichzeitige Suchlauf
starb an "database is locked", sein Abschluss blieb ungespeichert, die
drei Stale-Netze scheiterten am Zeitzonen-Vergleich, und der Startweg
kannte kein Alter. Jeder Test haelt eines dieser Glieder fest.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Suche"})
    d.set_search_criteria("keywords_muss", ["einkauf"])
    d.set_profile_setting("active_sources", ["bundesagentur", "jobspy_linkedin"])
    import bewerbungs_assistent.dashboard as dash
    dash._db = d
    from bewerbungs_assistent.services import auto_aussortierung
    monkeypatch.setattr(auto_aussortierung, "nach_suche", lambda *_a, **_k: None)
    yield d
    for t in threading.enumerate():
        if t.name.startswith(("pbp-jobsuche", "pbp-entfernungen", "pbp-watchdog")):
            t.join(timeout=10)
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _toter_lauf(db, vor_minuten, quellen=("bundesagentur", "jobspy_linkedin")):
    """Ein Suchlauf-Eintrag wie im Bericht: running, 100 %, lange still."""
    job_id = db.create_background_job("jobsuche", {"quellen": list(quellen)})
    zeit = (datetime.now(timezone.utc) - timedelta(minutes=vor_minuten)).isoformat()
    con = db.connect()
    con.execute("UPDATE background_jobs SET status='running', progress=100, "
                "message='jobspy_linkedin: ok (525 Stellen) | 8/8 Quellen OK', "
                "updated_at=?, created_at=? WHERE id=?", (zeit, zeit, job_id))
    con.commit()
    return job_id


# ----------------------------------------------------------- Alter, Zonen

def test_alter_rechnet_mit_zeitzone():
    from bewerbungs_assistent.services import hintergrund_alter as ha
    vor_3h = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    assert 10700 < ha.alter_sekunden(vor_3h) < 10900
    # Ohne Zone gilt die Ortszeit (aeltere Eintraege).
    lokal = (datetime.now() - timedelta(minutes=5)).isoformat()
    assert 290 < ha.alter_sekunden(lokal) < 310
    assert ha.alter_sekunden("") is None and ha.alter_sekunden("kaputt") is None


def test_grenze_folgt_dem_zeitlimit_des_laufs():
    """LinkedIn meldet sich bis zu 20 Minuten nicht — ein lebender Lauf
    darf nach 25 Minuten nicht als tot gelten, nach 40 schon."""
    from bewerbungs_assistent.services import hintergrund_alter as ha
    jetzt = datetime.now(timezone.utc)

    def job(minuten, quellen):
        return {"id": "abcdef12-x", "job_type": "jobsuche", "status": "running",
                "params": json.dumps({"quellen": quellen}),
                "updated_at": (jetzt - timedelta(minutes=minuten)).isoformat()}
    assert not ha.veraltet(job(25, ["jobspy_linkedin"]), jetzt)
    assert ha.veraltet(job(40, ["jobspy_linkedin"]), jetzt)
    assert not ha.veraltet(job(10, ["bundesagentur"]), jetzt)
    assert ha.veraltet(job(20, ["bundesagentur"]), jetzt)
    fertig = dict(job(300, ["bundesagentur"]), status="fertig")
    assert not ha.veraltet(fertig, jetzt)


def test_lebender_thread_ist_nie_tot():
    from bewerbungs_assistent.services import hintergrund_alter as ha
    halt = threading.Event()
    t = threading.Thread(target=halt.wait, name="pbp-jobsuche-deadbeef", daemon=True)
    t.start()
    try:
        alt = {"id": "deadbeef-1", "job_type": "jobsuche", "status": "running",
               "params": {"quellen": []},
               "updated_at": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()}
        assert not ha.veraltet(alt)
    finally:
        halt.set()
        t.join(timeout=5)
    assert ha.veraltet(alt)


# ------------------------------------------------------- Startweg heilt

def test_toter_lauf_blockiert_den_start_nicht(db, monkeypatch):
    """Nachtrag im Bericht: jobsuche_starten() -> laeuft_bereits, fuer immer."""
    from bewerbungs_assistent.services import jobsuche_start as js
    import bewerbungs_assistent.job_scraper as scraper
    monkeypatch.setattr(scraper, "run_search",
                        lambda d, job_id, params: d.update_background_job(job_id, "fertig", progress=100))
    tot = _toter_lauf(db, vor_minuten=170)
    erg = js.starten(db, herkunft="claude")
    assert erg["status"] == "gestartet", erg
    assert erg["job_id"] != tot
    assert "toten_lauf_abgeschlossen" in erg["schritte"]
    alt = db.get_background_job(tot)
    assert alt["status"] == "fehler" and "#1118" in alt["message"]


def test_frischer_lauf_blockiert_weiter(db, monkeypatch):
    from bewerbungs_assistent.services import jobsuche_start as js
    import bewerbungs_assistent.job_scraper as scraper
    monkeypatch.setattr(scraper, "run_search", lambda *_a, **_k: None)
    frisch = _toter_lauf(db, vor_minuten=3)
    erg = js.starten(db, herkunft="claude")
    assert erg["status"] == "laeuft_bereits" and erg["job_id"] == frisch


# -------------------------------------------------- Dashboard, drei Netze

def test_laufanzeige_schliesst_toten_lauf(db):
    import asyncio
    import bewerbungs_assistent.dashboard as dash
    tot = _toter_lauf(db, vor_minuten=170)
    assert asyncio.run(dash.api_jobsuche_running()) == {"running": False}
    assert db.get_background_job(tot)["status"] == "fehler"


def test_detailabfrage_schliesst_toten_lauf(db):
    import asyncio
    import bewerbungs_assistent.dashboard as dash
    tot = _toter_lauf(db, vor_minuten=170)
    job = asyncio.run(dash.api_background_job(tot))
    assert job["status"] == "fehler"


def test_laufanzeige_laesst_langen_linkedin_lauf(db):
    import asyncio
    import bewerbungs_assistent.dashboard as dash
    lebt = _toter_lauf(db, vor_minuten=25)
    assert asyncio.run(dash.api_jobsuche_running())["running"] is True
    assert db.get_background_job(lebt)["status"] == "running"


def test_startup_bereinigung_greift_trotz_zeitzone(db):
    import bewerbungs_assistent.dashboard as dash
    tot = _toter_lauf(db, vor_minuten=170)
    frisch = _toter_lauf(db, vor_minuten=5)
    dash._cleanup_stale_jobs(db)
    assert db.get_background_job(tot)["status"] == "fehler"
    assert db.get_background_job(frisch)["status"] == "running"


def test_jobsuche_status_schliesst_toten_lauf(db):
    import asyncio
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    tot = _toter_lauf(db, vor_minuten=170)
    mcp = FastMCP("PBP #1118")
    register_all(mcp, db, logging.getLogger("test.1118"))

    async def lauf():
        t = await mcp.get_tool("jobsuche_status")
        return (await t.run({})).structured_content
    asyncio.run(lauf())
    assert db.get_background_job(tot)["status"] == "fehler"


# ------------------------------------------- Nachrechnung ohne Sperre

def test_nachrechnung_haelt_keine_sperre_ueber_netzabfragen(db, monkeypatch):
    """Befund 1: vorher lief jedes UPDATE in derselben offenen Transaktion
    wie die Geocoder-Anfragen — 25 Minuten Schreibsperre bei 753 Orten."""
    from bewerbungs_assistent.services import eigener_standort, geocoding_service
    monkeypatch.setattr(eigener_standort, "_koordinaten", lambda _db: (53.55, 10.0))
    db.save_jobs([{"hash": f"ort{i}", "title": f"Stelle {i}", "company": "Musterbetrieb GmbH",
                   "url": f"https://example.com/{i}", "source": "manuell",
                   "location": f"Musterstadt {i}", "score": 1} for i in range(4)])
    offen = []

    def geocode(ort):
        offen.append(db.connect().in_transaction)
        return (53.0, 10.0)
    monkeypatch.setattr(geocoding_service, "geocode_location", geocode)
    erg = eigener_standort.entfernungen_nachziehen(db, alle=True, max_orte=None)
    assert erg["stellen"] == 4 and len(offen) == 4
    assert not any(offen), "Geocoder-Anfrage bei offener Schreibtransaktion"
    assert not db.connect().in_transaction


def test_nachrechnung_wartet_auf_laufende_suche(db, monkeypatch):
    """Befund/Wunsch 2: nicht gleichzeitig mit dem Suchlauf."""
    from bewerbungs_assistent.services import eigener_standort
    monkeypatch.setattr(eigener_standort, "WARTEN_TAKT_SEK", 0.05)
    monkeypatch.setattr(eigener_standort, "WARTEN_HOECHSTENS_SEK", 0.3)
    _toter_lauf(db, vor_minuten=1)
    job_id = db.create_background_job("entfernungen", {"alle": True})
    t0 = time.monotonic()
    eigener_standort._warten_auf_suche(db, job_id)
    assert time.monotonic() - t0 >= 0.25
    assert "Wartet" in db.get_background_job(job_id)["message"]


def test_nachrechnung_wartet_nicht_auf_toten_lauf(db, monkeypatch):
    from bewerbungs_assistent.services import eigener_standort
    monkeypatch.setattr(eigener_standort, "WARTEN_TAKT_SEK", 0.05)
    monkeypatch.setattr(eigener_standort, "WARTEN_HOECHSTENS_SEK", 5)
    _toter_lauf(db, vor_minuten=170)
    job_id = db.create_background_job("entfernungen", {"alle": True})
    t0 = time.monotonic()
    eigener_standort._warten_auf_suche(db, job_id)
    assert time.monotonic() - t0 < 1


# -------------------------------------------- Abschluss mit Wiederholung

def test_abschluss_ueberlebt_kurze_sperre(db, monkeypatch, tmp_path):
    """Befund 3: der Abschluss eines Laufs scheiterte an einer Sperre und
    niemand fing es — der Lauf blieb fuer immer 'running'."""
    monkeypatch.setattr(type(db), "JOB_WIEDERHOLUNG_PAUSE", 0.2)
    job_id = db.create_background_job("jobsuche", {"quellen": []})
    db.connect().execute("PRAGMA busy_timeout=100")
    fremd = sqlite3.connect(str(db.db_path), check_same_thread=False)
    fremd.execute("BEGIN IMMEDIATE")
    threading.Timer(0.3, fremd.commit).start()
    try:
        db.update_background_job(job_id, "fertig", progress=100, message="ok")
    finally:
        time.sleep(0.4)
        fremd.close()
        db.connect().execute("PRAGMA busy_timeout=30000")
    assert db.get_background_job(job_id)["status"] == "fertig"


def test_fortschritt_kippt_das_geocoding_nicht(caplog):
    """Befund 2: der erste Schreibvorgang des Geocoding-Blocks war eine
    Fortschrittsmeldung — scheiterte sie, fiel das Geocoding still aus."""
    from bewerbungs_assistent import job_scraper

    class Gesperrt:
        def update_background_job(self, *_a, **_k):
            raise sqlite3.OperationalError("database is locked")
    with caplog.at_level(logging.WARNING):
        job_scraper._fortschritt_sicher(Gesperrt(), "x", progress=90, message="Geocoding")
    assert "nicht gespeichert" in caplog.text


def test_geocoding_fehler_ist_eine_warnung():
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
              / "job_scraper" / "__init__.py").read_text(encoding="utf-8")
    assert 'logger.debug("Geocoding in Pipeline fehlgeschlagen' not in quelle
    assert "Geocoding im Suchlauf fehlgeschlagen" in quelle
