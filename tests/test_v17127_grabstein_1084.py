"""Tests fuer v1.7.127 — #1084: was zusammengefuehrt ist, kommt nicht wieder.

Gemeldet am 24.09.2026: eine per `stelle_mergen` aufgeloeste
Neuausschreibung stand am naechsten Morgen mit demselben Hash wieder als
ungepruefte Stelle auf Platz 1. `merge_jobs` loeschte die Dublette ohne
Spur, und der Import verglich nur mit der URL der ersten Anzeige.
Alle Firmen und Adressen hier sind erfunden.
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


def _stelle(hash_, titel, url, quelle="linkedin"):
    return {"hash": hash_, "title": titel, "company": "Musterwerk Nord GmbH",
            "location": "Musterstadt", "score": 20, "url": url, "source": quelle,
            "description": "Eine ausfuehrliche Stellenbeschreibung. " * 8}


MASTER = _stelle("master001", "Leitung Produktdaten (m/w/d)",
                 "https://example.org/anzeige/alt-111")
NEU = _stelle("repost001", "Teamleitung Stammdaten und Produktdaten",
              "https://example.org/anzeige/neu-222")


def _aktive_hashes(db):
    return {j["hash"].split(":")[-1] for j in db.get_active_jobs()}


def _zusammenfuehren(db):
    db.save_jobs([MASTER])
    db.save_jobs([NEU])
    assert _aktive_hashes(db) == {"master001", "repost001"}
    ergebnis = db.merge_jobs("master001", "repost001", dry_run=False)
    assert ergebnis.get("status") == "ok", ergebnis
    assert _aktive_hashes(db) == {"master001"}


def test_1084_erneuter_suchlauf_legt_die_aufgeloeste_stelle_nicht_an(db):
    _zusammenfuehren(db)
    antwort = db.save_jobs([dict(NEU)])
    assert _aktive_hashes(db) == {"master001"}
    assert antwort["wiederfunde_aufgeloest"] == 1
    assert antwort["duplikate_erkannt"] == 1
    assert db.connect().execute(
        "SELECT COUNT(*) FROM jobs WHERE hash LIKE '%repost001'").fetchone()[0] == 0


def test_1084_die_url_der_dublette_steht_am_master_und_wird_erkannt(db):
    """Neuer Hash, aber die URL der zusammengefuehrten Anzeige."""
    _zusammenfuehren(db)
    from bewerbungs_assistent.services import stellen_quellen
    master = db.resolve_job_hash("master001")
    urls = {f["url"] for f in stellen_quellen.lesen(db, master)}
    assert NEU["url"] in urls
    assert MASTER["url"] in urls

    anders = dict(NEU, hash="repost002", title="Anderer Titel ganz anders")
    db.save_jobs([anders])
    assert _aktive_hashes(db) == {"master001"}


def test_1084_der_wiederfund_steht_sichtbar_am_master(db):
    _zusammenfuehren(db)
    db.save_jobs([dict(NEU, source="stepstone")])
    from bewerbungs_assistent.services import stellen_grabstein
    befund = stellen_grabstein.erneut_gesehen(db, db.resolve_job_hash("master001"))
    assert befund and befund["quelle"] == "stepstone"
    assert befund["am"]
    assert "Erneut gesehen" in befund["text"]


def test_1084_bericht_ohne_auto_fix(db):
    _zusammenfuehren(db)
    # Ein Weg, der den Grabstein umgeht (manuelle Anlage), bringt sie zurueck.
    # Andere URL und anderer Titel, sonst faengt schon die Fundstelle ihn.
    db.save_jobs([dict(NEU, _manual_entry=True, source="manuell",
                       url="https://example.org/anzeige/dritte-444",
                       title="Referent Konstruktionsdaten")])
    from bewerbungs_assistent.services import stellen_grabstein
    bericht = stellen_grabstein.bericht(db)
    assert bericht["grabsteine"] == 1
    assert [w["hash"] for w in bericht["wiedergekehrt"]] == ["repost001"]
    assert bericht["auto_fix"] is False
    assert "v1.7.127" in bericht["grenze"]
    # Lesend: der Bericht aendert nichts.
    assert "repost001" in _aktive_hashes(db)


def test_1084_kette_zweier_zusammenfuehrungen(db):
    """Wird der Master selbst zusammengefuehrt, zeigt der Grabstein weiter."""
    _zusammenfuehren(db)
    dritter = _stelle("haupt0001", "Fachreferent Variantenmanagement",
                      "https://example.org/anzeige/haupt-333")
    db.save_jobs([dritter])
    assert db.merge_jobs("haupt0001", "master001", dry_run=False)["status"] == "ok"
    db.save_jobs([dict(NEU)])
    assert _aktive_hashes(db) == {"haupt0001"}


def test_1084_ohne_zusammenfuehrung_bleibt_alles_wie_vorher(db):
    """Gegenrichtung: zwei verschiedene Stellen werden weiter angelegt."""
    db.save_jobs([MASTER, NEU])
    assert _aktive_hashes(db) == {"master001", "repost001"}


def test_1084_dublettenpruefung_nennt_den_bericht(db):
    from bewerbungs_assistent.tools import jobs as job_tools
    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    job_tools.register(_Sammler(), db, logging.getLogger("test"))
    _zusammenfuehren(db)
    antwort = gesammelt["stellen_dubletten_pruefen"]()
    assert antwort["wiedergekehrte_zusammenfuehrungen"]["grabsteine"] == 1


def test_1084_wiederfund_ueber_dieselbe_quelle_aktualisiert_das_datum(db):
    """Dieselbe Quelle und URL wie beim Zusammenfuehren: die Fundstelle
    gibt es schon, also muss das Datum nachgezogen werden."""
    _zusammenfuehren(db)
    from bewerbungs_assistent.services import stellen_grabstein
    master = db.resolve_job_hash("master001")
    assert stellen_grabstein.erneut_gesehen(db, master) is None
    db.save_jobs([dict(NEU)])
    befund = stellen_grabstein.erneut_gesehen(db, master)
    assert befund and befund["quelle"] == "linkedin"


def test_1084_stellenliste_nennt_den_wiederfund(db):
    from bewerbungs_assistent.tools import jobs as job_tools
    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    job_tools.register(_Sammler(), db, logging.getLogger("test"))
    _zusammenfuehren(db)
    db.save_jobs([dict(NEU, source="stepstone")])
    antwort = gesammelt["stellen_anzeigen"]()
    stellen = antwort.get("stellen") or antwort.get("jobs")
    assert stellen[0]["erneut_gesehen"]["quelle"] == "stepstone"
    fit = gesammelt["fit_analyse"]("master001")
    assert fit["erneut_gesehen"]["quelle"] == "stepstone"


def test_1084_altbestand_ohne_fundstelle_bekommt_die_url_am_master(db):
    """Stellen von vor #951 tragen keine Fundstellenzeile — dann muss das
    Zusammenfuehren die URLs selbst am Master ablegen, sonst gibt es
    nichts, was `merge_jobs` umhaengen koennte."""
    db.save_jobs([MASTER])
    db.save_jobs([NEU])
    db.connect().execute("DELETE FROM job_sources")
    db.connect().commit()
    assert db.merge_jobs("master001", "repost001", dry_run=False)["status"] == "ok"
    from bewerbungs_assistent.services import stellen_quellen
    urls = {f["url"] for f in stellen_quellen.lesen(db, db.resolve_job_hash("master001"))}
    assert {MASTER["url"], NEU["url"]} <= urls
