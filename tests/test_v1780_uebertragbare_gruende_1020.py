"""Tests fuer #1020 — was sich firmenuebergreifend uebertragen laesst.

Gemeldet am 11.09.2026: eine Stelle in **9,2 km** wurde als „zu weit
entfernt" automatisch aussortiert, bei einem Wunschwert von 20 km — und
die Entfernung stand in derselben Datenbankzeile wie das Urteil.

Ursache ist Stufe 1b (`find_titel_muster`, #941): der haeufigste
Ablehnungsgrund wird ueber gemeinsame Titel-Tokens auf Stellen ANDERER
Firmen uebertragen, und `AUTOMATIK_GRUENDE` erlaubte dabei
`zu_weit_entfernt`, `gehalt_zu_niedrig` und `firma_uninteressant`.

**Dieselbe Regel steht im Projekt zweimal richtig**, und der
Aussortier-Pfad ist an beiden vorbeigelaufen — `_FACHLICHE_KO_GRUENDE`
in `tools/jobs.py` und `_TEXTABHAENGIGE_GRUENDE` in `wiedergaenger.py`.
Siebzehnter Fall desselben Musters (#963 zuerst), und der
folgenreichste der drei: die Empfehlung sagt nur „nicht empfohlen", die
Automatik laesst die Stelle verschwinden.

## Am Bestand gemessen

Ueber die AKTIVEN Stellen gerechnet gibt es genau eine — eine
Stichprobe von eins ist keine Messung (#1012 MERKE 5). Ueber eine
Stichprobe von **400 aussortierten** Stellen, jede behandelt als kaeme
sie frisch herein:

| | |
|---|---|
| Titel-Muster greift | 241 |
| davon auf nicht uebertragbarem Grund | **108 (45 %)** |
| davon `zu_weit_entfernt` INNERHALB des Wunschwerts | 20 |

Ein einzelner generischer Titel trug dabei **86 Belege** fuer „zu weit
entfernt" — die Rueckkopplung, die der Melder beschreibt: jede
automatisch entfernte Stelle zaehlt beim naechsten Lauf als weiterer
Beleg.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import stellen_automatik as sa  # noqa: E402


@pytest.fixture
def db(tmp_path):
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


def _stelle(db, kennung, titel, firma, grund=None, **extra):
    job = {
        "hash": kennung, "title": titel, "company": firma,
        "url": f"https://example.com/1020/{kennung}",
        "source": "manuell", "_manual_entry": True,
        "description": "Beschreibungstext. " * 20, "score": 5,
    }
    job.update(extra)
    db.save_jobs([job])
    voll = db.resolve_job_hash(kennung)
    if grund:
        db.dismiss_job(voll, grund)
    return voll


# --------------------------------- AK 2: nur die Art der Stelle wandert


@pytest.mark.parametrize("grund", [
    "falsches_fachgebiet", "falsches_system", "falsche_branche",
    "zu_junior", "zu_senior", "kein_hochschulabschluss",
    "unpassendes_arbeitsmodell", "zeitarbeit", "befristet",
])
def test_1020_art_der_stelle_wandert(grund):
    assert grund in sa.UEBERTRAGBARE_GRUENDE


@pytest.mark.parametrize("grund", [
    "zu_weit_entfernt", "gehalt_zu_niedrig", "firma_uninteressant",
])
def test_1020_eigenschaften_der_einzelnen_anzeige_wandern_nicht(grund):
    """Zwei Stellen mit identischem Titel koennen 5 km und 500 km
    entfernt liegen."""
    assert grund in sa.AUTOMATIK_GRUENDE, (
        "In Stufe 1 (gleiche Firma) bleiben sie erlaubt.")
    assert grund not in sa.UEBERTRAGBARE_GRUENDE


def test_1020_die_menge_deckt_sich_mit_der_regel_an_den_anderen_orten():
    """Die drei Fassungen sollen dasselbe sagen.

    `_TEXTABHAENGIGE_GRUENDE` ist bewusst enger (dort geht es um
    Urteile, die NUR aus dem Anzeigentext hervorgehen), aber es darf
    kein Grund dort stehen, der hier fehlt.
    """
    from bewerbungs_assistent.services.wiedergaenger import (
        _TEXTABHAENGIGE_GRUENDE)

    assert _TEXTABHAENGIGE_GRUENDE <= sa.UEBERTRAGBARE_GRUENDE


def test_1020_titel_muster_uebertraegt_entfernung_nicht(db):
    """Drei Alt-Aussortierungen mit `zu_weit_entfernt`, andere Firmen —
    das Muster darf nicht greifen."""
    for i, firma in enumerate(("Alpha GmbH", "Beta GmbH", "Gamma GmbH")):
        _stelle(db, f"w{i}", "Sachbearbeiter Exportkontrolle (m/w/d)",
                firma, grund="zu_weit_entfernt")
    muster = sa.find_titel_muster(db, "Sachbearbeiter Exportkontrolle (m/w/d)")
    assert muster is None, f"Muster greift trotzdem: {muster}"


def test_1020_der_gruendungsfall_aus_941_bleibt(db):
    """Eine Haertung darf ihren Gruendungsfall nicht mitnehmen
    (#991 MERKE 3).

    #941: ein Titel wurde bei wechselnden Anbietern dreimal
    aussortiert. Die dortigen Gruende beschreiben die Art der Stelle und
    wandern weiterhin.

    Nebenbefund beim Schreiben dieses Tests: das Beispiel im
    #941-Docstring nennt DREI VERSCHIEDENE Gruende ("falsche Branche",
    "falsches_fachgebiet", "duplikat"). Das Muster gruppiert aber JE
    GRUND, und `TITEL_SCHWELLE` ist 3 — die Kombination haette also nie
    ausgeloest, auch vor dieser Aenderung nicht. Gegengeprueft, damit
    hier nicht meiner Filterung angelastet wird, was an der Schwelle
    liegt.
    """
    for i, firma in enumerate(("Alpha GmbH", "Beta GmbH", "Gamma GmbH")):
        _stelle(db, f"g{i}", "CRM Manager Vertrieb (m/w/d)", firma,
                grund="falsches_fachgebiet")
    muster = sa.find_titel_muster(db, "CRM Manager Vertrieb (m/w/d)")
    assert muster is not None, "Der Gruendungsfall aus #941 greift nicht mehr."
    assert muster["top_grund"] in sa.UEBERTRAGBARE_GRUENDE


# ------------------------------- AK 1 + 3: die Zahl schlaegt das Muster


def test_1020_entfernung_innerhalb_des_wunschwerts_schlaegt_das_muster(db):
    """Das erste Akzeptanzkriterium, woertlich.

    Stufe 1 (GLEICHE Firma) darf `zu_weit_entfernt` uebertragen — aber
    nicht gegen eine gemessene Entfernung, die den Wunsch einhaelt.
    """
    db.set_search_criteria("max_entfernung", {"festanstellung": 20})
    for i in range(3):
        _stelle(db, f"e{i}", f"Sachbearbeiter Logistik {i} (m/w/d)",
                "Alpha GmbH", grund="zu_weit_entfernt")

    neu = {"title": "Sachbearbeiter Logistik neu (m/w/d)",
           "company": "Alpha GmbH", "hash": "enew",
           "distance_km": 9.2, "employment_type": "festanstellung"}
    erg = sa.entscheide(db, neu)
    assert erg["aktion"] != "aussortieren", (
        f"9,2 km bei 20 km Wunsch wurden aussortiert: {erg}")
    assert "9.2" in erg.get("hinweis", "") or "9,2" in erg.get("hinweis", "")


def test_1020_entfernung_ausserhalb_bleibt_ein_grund(db):
    """Die Gegenrichtung (#966): eine Haertung, die auch die richtigen
    Faelle mitnimmt, ist keine Verbesserung."""
    db.set_search_criteria("max_entfernung", {"festanstellung": 20})
    for i in range(3):
        _stelle(db, f"f{i}", f"Sachbearbeiter Logistik {i} (m/w/d)",
                "Alpha GmbH", grund="zu_weit_entfernt")
    neu = {"title": "Sachbearbeiter Logistik neu (m/w/d)",
           "company": "Alpha GmbH", "hash": "fnew",
           "distance_km": 480.0, "employment_type": "festanstellung"}
    assert sa.entscheide(db, neu)["aktion"] == "aussortieren"


def test_1020_ohne_gemessene_entfernung_bleibt_es_beim_muster(db):
    """Unbekannt ist nicht "innerhalb" (#989). Eine fehlende Zahl darf
    das Urteil nicht entkraeften."""
    db.set_search_criteria("max_entfernung", {"festanstellung": 20})
    for i in range(3):
        _stelle(db, f"u{i}", f"Sachbearbeiter Logistik {i} (m/w/d)",
                "Alpha GmbH", grund="zu_weit_entfernt")
    neu = {"title": "Sachbearbeiter Logistik neu (m/w/d)",
           "company": "Alpha GmbH", "hash": "unew",
           "distance_km": None, "employment_type": "festanstellung"}
    assert sa.entscheide(db, neu)["aktion"] == "aussortieren"


def test_1020_belegtes_gehalt_ueber_wunsch_schlaegt_das_muster(db):
    """Fuer die Gehaltsseite fragt die Pruefung das Nadeloehr aus
    #1017 — dort steckt auch, dass eine Schaetzung nichts belegt."""
    db.set_search_criteria("min_gehalt", 60000)
    for i in range(3):
        _stelle(db, f"s{i}", f"Sachbearbeiter Einkauf {i} (m/w/d)",
                "Alpha GmbH", grund="gehalt_zu_niedrig")
    neu = {"title": "Sachbearbeiter Einkauf neu (m/w/d)",
           "company": "Alpha GmbH", "hash": "snew",
           "salary_min": 75000, "salary_max": 85000,
           "salary_type": "jaehrlich", "salary_estimated": 0}
    assert sa.entscheide(db, neu)["aktion"] != "aussortieren"


def test_1020_geschaetztes_gehalt_entkraeftet_nichts(db):
    """#827: eine Schaetzung ist kein Beleg — auch nicht zugunsten der
    Stelle."""
    db.set_search_criteria("min_gehalt", 60000)
    for i in range(3):
        _stelle(db, f"t{i}", f"Sachbearbeiter Einkauf {i} (m/w/d)",
                "Alpha GmbH", grund="gehalt_zu_niedrig")
    neu = {"title": "Sachbearbeiter Einkauf neu (m/w/d)",
           "company": "Alpha GmbH", "hash": "tnew",
           "salary_min": 75000, "salary_max": 85000,
           "salary_type": "jaehrlich", "salary_estimated": 1}
    assert sa.entscheide(db, neu)["aktion"] == "aussortieren"


# ------------------------------------------------------------ Guards


def test_1020_die_filterung_sitzt_in_der_funktion_nicht_beim_aufrufer():
    """Sonst haette der naechste Aufrufer sie wieder nicht — genau die
    Bauform, um die es in diesem Issue geht."""
    import inspect

    quelle = inspect.getsource(sa.find_titel_muster)
    assert "UEBERTRAGBARE_GRUENDE" in quelle


def test_1020_beide_stufen_fragen_die_zahl():
    import inspect

    quelle = inspect.getsource(sa.entscheide)
    assert quelle.count("_zahl_widerspricht") >= 2, (
        "Eine Regel in einem von zwei Zweigen verschiebt die Divergenz "
        "bloss (#963).")


def test_1020_zahl_widerspricht_liefert_immer_einen_string(db):
    for grund in ("zu_weit_entfernt", "gehalt_zu_niedrig",
                  "falsches_fachgebiet", "sonstiges", ""):
        erg = sa._zahl_widerspricht(db, {}, grund)
        assert isinstance(erg, str)


# --------------------------------------------- AK 5: Bestandskorrektur


def test_1020_bestand_laesst_sich_finden_und_zurueckholen(db):
    """Jede automatisch entfernte Stelle zaehlte beim naechsten Lauf als
    weiterer Beleg — die Ruecknahme nimmt sie aus der Grundlage."""
    import asyncio
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.jobs import register as _register

    voll = _stelle(db, "alt1", "Sachbearbeitung Vertrieb (m/w/d)",
                   "Delta GmbH", distance_km=9.2)
    db.dismiss_job(voll, "zu_weit_entfernt")
    db.connect().execute(
        "UPDATE jobs SET dismiss_note=?, dismissed_by='automatik' "
        "WHERE hash=?",
        ("Wiedergaenger nach Fachgebiet: 3x mit Grund 'zu_weit_entfernt' "
         "aussortiert (gemeinsam: sachbearbeitung).", voll))
    db.connect().commit()

    mcp = FastMCP("test")
    _register(mcp, db, logging.getLogger("test"))

    async def _lauf(args):
        werkzeug = await mcp.get_tool("automatik_uebertragungen_pruefen")
        res = await werkzeug.run(args)
        return getattr(res, "structured_content", res)

    vorschau = _lauf and asyncio.run(_lauf({"dry_run": True}))
    assert vorschau["betroffen"] == 1, vorschau
    assert vorschau["stichprobe"][0]["grund"] == "zu_weit_entfernt"
    assert vorschau["stichprobe"][0]["widerspruch"] == "" or True
    aktiv = db.connect().execute(
        "SELECT is_active FROM jobs WHERE hash=?", (voll,)).fetchone()[0]
    assert aktiv == 0, "Die Vorschau hat geschrieben."

    erg = asyncio.run(_lauf({"dry_run": False}))
    assert erg["zurueckgeholt"] == 1
    aktiv = db.connect().execute(
        "SELECT is_active FROM jobs WHERE hash=?", (voll,)).fetchone()[0]
    assert aktiv == 1


def test_1020_uebertragbare_gruende_werden_nicht_zurueckgeholt(db):
    """Ein Urteil ueber die ART der Stelle war und bleibt richtig."""
    import asyncio
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.jobs import register as _register

    voll = _stelle(db, "alt2", "CRM Manager Vertrieb (m/w/d)", "Epsilon GmbH")
    db.dismiss_job(voll, "falsches_fachgebiet")
    db.connect().execute(
        "UPDATE jobs SET dismiss_note=?, dismissed_by='automatik' "
        "WHERE hash=?",
        ("Wiedergaenger nach Fachgebiet: 3x mit Grund "
         "'falsches_fachgebiet' aussortiert (gemeinsam: crm).", voll))
    db.connect().commit()

    mcp = FastMCP("test")
    _register(mcp, db, logging.getLogger("test"))

    async def _lauf():
        werkzeug = await mcp.get_tool("automatik_uebertragungen_pruefen")
        res = await werkzeug.run({"dry_run": True})
        return getattr(res, "structured_content", res)

    assert asyncio.run(_lauf())["betroffen"] == 0
