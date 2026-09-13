"""Tests fuer #1031 (Umfang "Voll- oder Teilzeit") und #1033 (Jobsuche-Hinweis).

#1031: `_VOLLZEIT` liess zwischen "Voll-" und "Teilzeit" nur
Trennzeichen zu. Mit einem Bindewort dazwischen ("in Voll- oder
Teilzeit") galt die Stelle als reine Teilzeitstelle und fiel aus dem
Umfang-Filter "Vollzeit" heraus — obwohl sie ausdruecklich beides
anbietet. Die naechste Variante der Luecke aus v1.7.84.

#1033: `GET /api/jobsuche/last` las `neue_stellen`, das kein Suchlauf
schreibt. Der Hinweis in der Navigation meldete deshalb nach jedem Lauf
"0 neue Stellen", auch nach 105 Funden.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


# ------------------------------------------------------------- #1031


@pytest.mark.parametrize("titel", [
    "Sachbearbeitung (w/m/d) Rechtsstelle in Voll- oder Teilzeit",
    "Bürokraft (m/w/d) in Voll- und Teilzeit gesucht",
    "KAUFMÄNNISCHER MITARBEITER (M/W/D) IN VOLL- ODER TEILZEIT",
    "Hausverwalter (m/w/d) für die Immobilienverwaltung in Voll- bzw. Teilzeit",
    "Hausverwalter (m/w/d) in Voll- bzw Teilzeit",
    "Accountant (m/f/d) full- or part-time",
    "Accountant (m/f/d) full- and part-time",
])
def test_voll_mit_bindewort_und_teilzeit_ist_beides(titel):
    from bewerbungs_assistent.services import stellenart as sa

    assert sa.umfang_erkennen({"title": titel})["umfang"] == sa.BEIDES, titel


@pytest.mark.parametrize("titel, erwartet", [
    # Die alten Schreibweisen bleiben, was sie waren (v1.7.84).
    ("Pflegefachkraft Voll-/Teilzeit", "beides"),
    ("Buchhalter (m/w/d) Vollzeit oder Teilzeit", "beides"),
    ("Buchhalter (m/w/d) Vollzeit / Teilzeit", "beides"),
    # Gegenrichtung: ohne Vollzeit-Angabe bleibt es Teilzeit ...
    ("Sachbearbeitung (m/w/d) in Teilzeit", "teilzeit"),
    ("Sachbearbeitung (m/w/d) Teilzeit 20 Std.", "teilzeit"),
    # ... und ein Bindewort allein macht aus nichts eine Vollzeit.
    ("Sachbearbeitung (m/w/d) voll oder zeitweise remote, Teilzeit", "teilzeit"),
    ("Buchhalter (m/w/d) in Vollzeit", "vollzeit"),
])
def test_die_gegenrichtung_bleibt_unveraendert(titel, erwartet):
    from bewerbungs_assistent.services import stellenart as sa

    assert sa.umfang_erkennen({"title": titel})["umfang"] == erwartet, titel


def test_eine_teilzeit_zeile_ist_nicht_mehr_als_reine_art_aussortierbar():
    """`_VOLLZEIT` schuetzt auch die ART-Erkennung: eine Stelle "in Voll-
    oder Teilzeit" darf nicht als nicht gesuchte Teilzeit-Art gelten."""
    from bewerbungs_assistent.services import stellenart as sa

    assert sa._VOLLZEIT.search("in Voll- oder Teilzeit")
    assert sa._VOLLZEIT.search("full- or part-time")
    assert not sa._VOLLZEIT.search("voll oder zeitweise")


@pytest.mark.parametrize("feld, titel, erwartet", [
    # Der Titel bietet beides an: ein einzelner Feldwert ist nur eine
    # Teilmenge davon.
    ("teilzeit", "Bürokraft (m/w/d) in Voll- oder Teilzeit", "beides"),
    ("vollzeit", "Bürokraft (m/w/d) Vollzeit / Teilzeit", "beides"),
    # Gegenrichtung: sonst behaelt das Feld seinen Vorrang.
    ("teilzeit", "Bürokraft (m/w/d) in Teilzeit", "teilzeit"),
    ("vollzeit", "Bürokraft (m/w/d)", "vollzeit"),
    ("teilzeit", "Bürokraft (m/w/d) in Vollzeit", "teilzeit"),
])
def test_ein_titel_mit_beidem_uebersticht_ein_einwertiges_feld(feld, titel, erwartet):
    """Isolierender Fall fuer AK 4: ohne diese Regel liest das Nachziehen
    seinen eigenen frueheren Wert als Angabe der Quelle und korrigiert nie.
    Das Muster allein haette AK 4 nicht erfuellt."""
    from bewerbungs_assistent.services import stellenart as sa

    erg = sa.umfang_erkennen({"title": titel, "arbeitsumfang": feld})
    assert erg["umfang"] == erwartet, (feld, titel, erg)


def test_nachziehen_korrigiert_bereits_erfasste_stellen(tmp_path):
    """AK 4: ein erneuter Lauf von `stellen_merkmale_nachziehen` setzt eine
    als `teilzeit` gespeicherte Stelle auf `beides`."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path)
    try:
        db.switch_profile(db.create_profile("Test"))
        db.save_jobs([{
            "hash": "vt1031", "title": "Bürokraft (m/w/d) in Voll- oder Teilzeit",
            "company": "Musterbetrieb GmbH", "url": "https://example.com/1031",
            "source": "bundesagentur", "description": "Text. " * 40, "score": 3,
        }])
        con = db.connect()
        con.execute("UPDATE jobs SET arbeitsumfang='teilzeit' WHERE hash LIKE '%vt1031'")
        con.commit()

        import asyncio
        import logging

        from fastmcp import FastMCP

        from bewerbungs_assistent.tools import register_all

        mcp = FastMCP("t1031")
        register_all(mcp, db, logging.getLogger("t1031"))

        async def _run():
            w = await mcp.get_tool("stellen_merkmale_nachziehen")
            r = await w.run({"dry_run": False})
            return getattr(r, "structured_content", None) or r

        asyncio.run(_run())
        wert = con.execute(
            "SELECT arbeitsumfang FROM jobs WHERE hash LIKE '%vt1031'").fetchone()[0]
        assert wert == "beides"
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


# ------------------------------------------------------------- #1033


@pytest.fixture
def client(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.switch_profile(db.create_profile("Test"))

    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    alt = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app), db
    finally:
        dash._db = alt
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def _lauf(db, status, result, message="Lauf"):
    job_id = db.create_background_job("jobsuche", {})
    db.update_background_job(job_id, status, progress=100, message=message, result=result)
    return job_id


def _ergebnis_wie_im_bericht():
    return {
        "total": 105,
        "neu_aktiv": 88,
        "quellen": {"bundesagentur": 19, "jobspy_linkedin": 0},
        "quellen_status": {
            "bundesagentur": {"status": "ok", "count": 19},
            "stepstone": {"status": "ok", "count": 30},
            "jobspy_linkedin": {"status": "timeout", "count": 0},
            "xing": {"status": "uebersprungen"},
        },
    }


def test_die_zahl_kommt_aus_total_und_nicht_aus_einem_ungeschriebenen_schluessel(client):
    """AK 1 — der gemeldete Fall: 105 gefunden, angezeigt wurde 0."""
    c, db = client
    _lauf(db, "fertig", _ergebnis_wie_im_bericht())
    daten = c.get("/api/jobsuche/last").json()
    assert daten["ergebnis"] == "fertig"
    assert daten["neue_stellen"] == 105
    assert daten["neu_aktiv"] == 88


def test_der_timeout_zaehler_liest_quellen_status(client):
    c, db = client
    _lauf(db, "fertig", _ergebnis_wie_im_bericht())
    daten = c.get("/api/jobsuche/last").json()
    assert daten["timeout_quellen"] == 1
    assert daten["quellen"] == {"ok": 2, "timeout": 1, "fehler": 0, "uebersprungen": 1}


def test_ein_lauf_ohne_funde_meldet_null_und_nicht_unbekannt(client):
    """AK 2."""
    c, db = client
    _lauf(db, "fertig", {"total": 0, "neu_aktiv": 0, "quellen_status": {}})
    daten = c.get("/api/jobsuche/last").json()
    assert daten["ergebnis"] == "fertig"
    assert daten["neue_stellen"] == 0


def test_ein_fehlgeschlagener_lauf_ist_keine_null(client):
    """AK 3: `None` heisst "nicht bekannt" — ein Abbruch darf nicht wie
    ein Lauf ohne Funde aussehen (#989)."""
    c, db = client
    _lauf(db, "fehler", None, message="Suche abgebrochen: Verbindung weg")
    daten = c.get("/api/jobsuche/last").json()
    assert daten["ergebnis"] == "fehlgeschlagen"
    assert daten["neue_stellen"] is None
    assert "abgebrochen" in daten["meldung"]


def test_ein_nicht_gestarteter_lauf_wird_benannt(client):
    """Nebenbefund: ohne Suchbegriffe endet der Lauf als `fertig` mit
    `nicht_gestartet` (#967). Auch das war bis hierher "0 neue Stellen"."""
    c, db = client
    _lauf(db, "fertig", {"total": 0, "nicht_gestartet": True})
    daten = c.get("/api/jobsuche/last").json()
    assert daten["ergebnis"] == "nicht_gestartet"
    assert daten["neue_stellen"] is None


def test_der_suchlauf_schreibt_neu_aktiv():
    """Der Endpunkt liest nur, was der Suchlauf schreibt — dieser Guard
    haelt den Schluessel an seiner Quelle fest, damit sich die Luecke aus
    #1033 nicht in der Gegenrichtung wiederholt."""
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "job_scraper"
              / "__init__.py").read_text(encoding="utf-8")
    assert '"neu_aktiv":' in quelle
    dash = (_repo() / "src" / "bewerbungs_assistent" / "dashboard.py").read_text(encoding="utf-8")
    anfang = dash.index('@app.get("/api/jobsuche/last")')
    koerper = dash[anfang:anfang + 4000]
    assert 'result.get("total")' in koerper
    assert 'result.get("neue_stellen")' not in koerper
