"""Tests fuer #663 C66 — ein Grund, eine Schreibweise.

Nutzerauftrag vom 10.09.2026: die beiden weiteren Paare mit
zusammenfuehren, die beim Aufraeumen des `Dublikat`-Tippfehlers
auffielen.

Gemessen am Bestand:

| Gruppe | Grund-Eintraege | in den Stellen |
|---|---|---|
| Branche | `Falsche Branche` (50), `falsche_branche` (1) | `falsche branche` (49), `falsche_branche` (1) |
| System | `Falsches System` (50), `falsches_system` (5) | `falsches system` (50), `falsches_system` (5) |

**Label und gespeicherter Wert sind zwei verschiedene Zeichenketten** —
in den Stellen steht `falsches system` mit Leerzeichen, also weder wie
das eine noch wie das andere Label. Deshalb reicht ein Umbenennen
nicht.
"""
import json
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import gruende_schreibweise as gs  # noqa: E402


@pytest.fixture
def db(tmp_path):
    import importlib

    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _grund(db, label: str) -> int:
    """Legt einen Grund an — und meldet, wenn es ihn schon gibt.

    Eine frische Datenbank bringt `falsches_system` und
    `falsche_branche` bereits als Standardgruende mit. Beim Schreiben
    dieser Tests hat das eine DRITTE Zeile erzeugt und den Lauf
    scheinbar nicht-idempotent gemacht — der eigentliche Fund war, dass
    die Gruppierung zwei Eintraege mit identischem Label verschluckte.
    """
    erg = db.add_dismiss_reason(label)
    return erg["id"] if isinstance(erg, dict) else erg


def _eintraege_mit(db, schluessel_wert: str) -> list:
    """Alle Grund-Eintraege, die auf diesen Schluessel fallen."""
    return [g for g in db.get_dismiss_reasons()
            if gs.schluessel(g["label"]) == schluessel_wert]


def _stelle(db, kennung: str, grund) -> str:
    db.save_jobs([{
        "hash": kennung, "title": f"Rolle {kennung}",
        "company": f"Firma {kennung} GmbH",
        "url": f"https://example.com/c66/{kennung}",
        "source": "manuell", "description": "Text. " * 20,
        "score": 5, "_manual_entry": True,
    }])
    voll = db.resolve_job_hash(kennung)
    wert = grund if isinstance(grund, str) else json.dumps(
        grund, ensure_ascii=False)
    db.connect().execute(
        "UPDATE jobs SET dismiss_reason=?, is_active=0 WHERE hash=?",
        (wert, voll))
    db.connect().commit()
    return voll


def _werte(db) -> dict:
    """Alle Einzelwerte aus `jobs.dismiss_reason` mit Haeufigkeit."""
    zaehler: dict = {}
    for z in db.connect().execute(
            "SELECT dismiss_reason FROM jobs WHERE dismiss_reason IS NOT NULL "
            "AND TRIM(dismiss_reason) != ''"):
        for w in gs._einzelwerte(z[0])[0]:
            zaehler[w] = zaehler.get(w, 0) + 1
    return zaehler


# --------------------------------------------- Der Schluessel


@pytest.mark.parametrize("a,b", [
    ("Falsches System", "falsches_system"),
    ("Falsches System", "falsches system"),
    ("Falsche Branche", "falsche-branche"),
    ("Zu kurze Projektdauer", "zu_kurze_projektdauer"),
])
def test_663_nur_die_schreibweise_unterscheidet(a, b):
    assert gs.schluessel(a) == gs.schluessel(b)


@pytest.mark.parametrize("a,b", [
    ("falsches_system", "falsches_fachgebiet"),
    ("zu_junior", "zu_senior"),
    ("Dublikat", "duplikat"),
])
def test_663_verschiedene_sachverhalte_bleiben_getrennt(a, b):
    """Die Gegenrichtung — und `Dublikat` gegen `duplikat` gehoert dazu.

    Das ist ein TIPPFEHLER (b statt p), keine Schreibweise. Ihn hier
    mitzugruppieren hiesse, Aehnlichkeit entscheiden zu lassen — dafuer
    gibt es `ablehnungsgrund_umbenennen`, wo ein Mensch das Ziel nennt.
    """
    assert gs.schluessel(a) != gs.schluessel(b)


# ------------------------------- Was als Spaltung gilt, und was nicht


def test_663_ein_grossgeschriebenes_label_ist_keine_spaltung(db):
    """**Der Fehler meiner ersten Fassung, am echten Bestand gefunden.**

    Ein Grund heisst im Editor `Veraltet` und steht in den Stellen als
    `veraltet` — das ist die normale Ablage, `stelle_bewerten` schreibt
    klein. Waere das ein Fall, wuerde der Lauf SAEMTLICHE Custom-Label
    kleinschreiben: Anzeige umbauen statt Daten aufraeumen.
    """
    _grund(db, "Veraltet")
    _stelle(db, "c66-v1", "veraltet")

    assert gs.bericht(db)["gruppen"] == []
    erg = gs.vereinheitlichen(db, dry_run=False)
    assert erg["stellen_umgeschrieben"] == 0
    labels = [g["label"] for g in db.get_dismiss_reasons()]
    assert "Veraltet" in labels, "Das Label wurde kleingeschrieben."


def test_663_zwei_grund_eintraege_sind_eine_spaltung(db):
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    gruppen = gs.bericht(db)["gruppen"]
    assert len(gruppen) == 1
    assert gruppen[0]["schluessel"] == "falschessystem"


def test_663_zwei_gespeicherte_schreibweisen_sind_eine_spaltung(db):
    _grund(db, "Falsche Branche")
    _stelle(db, "c66-b1", "falsche branche")
    _stelle(db, "c66-b2", "falsche_branche")
    assert len(gs.bericht(db)["gruppen"]) == 1


# ------------------------------------------ Beide Orte werden umgeschrieben


def test_663_die_stellen_werden_mit_umgeschrieben(db):
    """Der Kern: ein Umbenennen allein traefe die Stellen nicht.

    Es vergleicht gegen das alte LABEL — in den Stellen steht aber eine
    dritte Schreibweise.
    """
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    _stelle(db, "c66-s1", "falsches system")
    _stelle(db, "c66-s2", "falsches system")
    _stelle(db, "c66-s3", "falsches_system")

    gs.vereinheitlichen(db, dry_run=False)
    werte = _werte(db)
    assert len(werte) == 1, f"Es blieben mehrere Schreibweisen: {werte}"
    assert sum(werte.values()) == 3


def test_663_die_grund_eintraege_werden_zusammengefuehrt(db):
    """Am Ende bleibt EIN Eintrag je Schluessel — egal wie viele es waren.

    Eine frische Datenbank bringt `falsche_branche` schon mit, hier
    kommen also drei Zeilen zusammen. Genau daran ist meine erste
    Fassung gescheitert: sie schluesselte nach Label-TEXT und sah den
    dritten Eintrag nicht.
    """
    _grund(db, "Falsche Branche")
    _grund(db, "falsche_branche")
    _stelle(db, "c66-b1", "falsche branche")

    assert len(_eintraege_mit(db, "falschebranche")) >= 2
    gs.vereinheitlichen(db, dry_run=False)
    assert len(_eintraege_mit(db, "falschebranche")) == 1

    labels = [g["label"] for g in db.get_dismiss_reasons()]
    assert len({gs.schluessel(l) for l in labels}) == len(labels), (
        "Es gibt weiter zwei Eintraege mit demselben Schluessel.")


def test_663_die_listenform_wird_mitgezogen(db):
    """Gruende stehen seit #913 normalerweise als JSON-Liste da."""
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    _stelle(db, "c66-l1", ["falsches_system", "zu_weit_entfernt"])
    _stelle(db, "c66-l2", "falsches system")

    gs.vereinheitlichen(db, dry_run=False)
    wert = db.connect().execute(
        "SELECT dismiss_reason FROM jobs WHERE hash LIKE '%c66-l1'"
    ).fetchone()[0]
    geparst = json.loads(wert)
    assert isinstance(geparst, list), "Aus der Liste wurde ein String."
    assert "zu_weit_entfernt" in geparst, "Ein fremder Grund ging verloren."
    assert len({gs.schluessel(w) for w in geparst}) == 2


def test_663_eine_stelle_mit_beiden_schreibweisen_behaelt_eine(db):
    """Sonst entstuende `["falsches system", "falsches system"]`."""
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    _stelle(db, "c66-d1", ["falsches system", "falsches_system"])

    gs.vereinheitlichen(db, dry_run=False)
    wert = db.connect().execute(
        "SELECT dismiss_reason FROM jobs WHERE hash LIKE '%c66-d1'"
    ).fetchone()[0]
    assert len(json.loads(wert)) == 1


# --------------------------------------------- Die Zielschreibweise


def test_663_die_whitelist_form_gewinnt(db):
    """Jede andere Schreibweise wird von `stelle_bewerten` still auf
    `sonstiges` normalisiert und verfaelscht die Statistik (#663 Teil 2)."""
    _grund(db, "Bereits Beworben")
    _grund(db, "bereits_beworben")
    _stelle(db, "c66-w1", "bereits beworben")
    _stelle(db, "c66-w2", "bereits beworben")
    _stelle(db, "c66-w3", "bereits beworben")

    gruppe = gs.bericht(db)["gruppen"][0]
    assert gruppe["ziel"] == "bereits_beworben"
    assert gruppe["aus_whitelist"] is True, (
        "Die haeufigste Form hat gewonnen, obwohl es eine Whitelist-Form "
        "gibt — dann landet der Grund kuenftig auf 'sonstiges'.")


def test_663_sonst_gewinnt_die_haeufigste_gespeicherte_form(db):
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    for i in range(4):
        _stelle(db, f"c66-h{i}", "falsches system")
    _stelle(db, "c66-h9", "falsches_system")
    assert gs.bericht(db)["gruppen"][0]["ziel"] == "falsches system"


def test_663_das_ziel_laesst_sich_ueberschreiben(db):
    """Es sind die Daten des Nutzers.

    Eine Schreibweise, die PBP sich aussucht und stillschweigend
    durchsetzt, waere dieselbe Bevormundung wie ein erfundener
    Ablehnungsgrund.
    """
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    _stelle(db, "c66-u1", "falsches system")

    gs.vereinheitlichen(db, dry_run=False,
                        ziele={"falschessystem": "falsches_system"})
    assert list(_werte(db)) == ["falsches_system"]


# ------------------------------------------ Vorschau, Idempotenz, Grenzen


def test_663_die_vorschau_ist_die_vorgabe_und_schreibt_nichts(db):
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    _stelle(db, "c66-p1", "falsches system")
    vorher = _werte(db)
    anzahl_vorher = len(db.get_dismiss_reasons())

    erg = gs.vereinheitlichen(db)  # ohne Argument = dry_run
    assert erg["status"] == "vorschau"
    assert erg["stellen_umgeschrieben"] >= 0
    assert _werte(db) == vorher
    assert len(db.get_dismiss_reasons()) == anzahl_vorher


def test_663_der_lauf_ist_idempotent(db):
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    _stelle(db, "c66-i1", "falsches system")
    _stelle(db, "c66-i2", "falsches_system")

    erst = gs.vereinheitlichen(db, dry_run=False)
    zweit = gs.vereinheitlichen(db, dry_run=False)
    assert erst["stellen_umgeschrieben"] >= 1
    assert zweit["stellen_umgeschrieben"] == 0
    assert zweit["grund_eintraege_zusammengefuehrt"] == 0


def test_663_fremde_gruende_bleiben_unberuehrt(db):
    """Beim Haerten immer beide Richtungen messen (#966)."""
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    _stelle(db, "c66-f1", "falsches system")
    _stelle(db, "c66-f2", "falsches_fachgebiet")
    _stelle(db, "c66-f3", "zu_weit_entfernt")

    gs.vereinheitlichen(db, dry_run=False)
    werte = _werte(db)
    assert werte.get("falsches_fachgebiet") == 1
    assert werte.get("zu_weit_entfernt") == 1


def test_663_keine_stelle_verliert_ihren_grund(db):
    """Die wichtigste Zusicherung: es wird vereinheitlicht, nicht
    geloescht."""
    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    for i, wert in enumerate(["falsches system", "falsches_system",
                              ["falsches system", "zu_junior"]]):
        _stelle(db, f"c66-k{i}", wert)

    vorher = db.connect().execute(
        "SELECT COUNT(*) FROM jobs WHERE dismiss_reason IS NOT NULL "
        "AND TRIM(dismiss_reason) != ''").fetchone()[0]
    gs.vereinheitlichen(db, dry_run=False)
    nachher = db.connect().execute(
        "SELECT COUNT(*) FROM jobs WHERE dismiss_reason IS NOT NULL "
        "AND TRIM(dismiss_reason) != ''").fetchone()[0]
    assert nachher == vorher


def test_663_ein_leerer_bestand_stuerzt_nicht_ab(db):
    assert gs.bericht(db)["gruppen"] == []
    assert gs.vereinheitlichen(db, dry_run=False)["stellen_umgeschrieben"] == 0


def test_663_das_werkzeug_ist_registriert_und_ruft_den_dienst(db):
    """DoD 8c: ein Weg zaehlt erst, wenn er auch aufgerufen wird."""
    import asyncio
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all

    _grund(db, "Falsches System")
    _grund(db, "falsches_system")
    _stelle(db, "c66-m1", "falsches system")

    mcp = FastMCP("PBP Test C66")
    register_all(mcp, db, logging.getLogger("test.c66"))

    async def _lauf():
        werkzeug = await mcp.get_tool("ablehnungsgruende_vereinheitlichen")
        erg = await werkzeug.run({"dry_run": True})
        return getattr(erg, "structured_content", erg)

    antwort = asyncio.run(_lauf())
    assert antwort["status"] == "vorschau"
    assert len(antwort["gruppen"]) == 1
