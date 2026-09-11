"""Tests fuer #1026 — eine Telefonnummer als Jahresgehalt.

Nachtrag zum Fix aus #1018, gemeldet am selben Tag. Der Melder hat den
neuen Extraktor am eigenen Bestand nachgezogen — 823 geprueft, 122
geaendert, 6 geleert, **113 belegte Gehaltsangaben statt vorher 11** —
und dabei drei Luecken gefunden.

## Befund 1: die Grenze prueft nur den ersten Wert

`GRENZEN` steht im Modul, aber `_kandidat` hielt nur `zahlen[0]`
dagegen. Bei einer Spanne kam der zweite Wert ungeprueft durch:

    Telefon 0221-55510-10  Europastr. 1, 12345 Musterstadt
    -> 10 bis 55.510 EUR im Jahr, als BELEGT

55.510 passiert die Jahresgrenze, also wurde die Fundstelle
angenommen; danach machte `min(...)` aus der Durchwahl die Untergrenze.
**Die Pruefung stand vor der Sortierung, und die Sortierung hat den
geprueften Wert vertauscht.**

Im Bestand des Melders ist dieser Fehltreffer der einzige Jahreswert
unter 15.000 — die Untergrenze faengt also nichts weg, was echt waere.

Die Rufnummer steht hier in der 555-Fiktionskonvention des Projekts
(`scripts/scrub_pii.py`) statt in der Schreibweise des Berichts — der
PII-Pruefer hat die Originalzeile zu Recht als Telefonmuster gemeldet.
Der Defekt reproduziert sich identisch: 10 bis 55.510 statt 10 bis
56.789.

## Befund 2: `Eur` ohne Wortgrenze

Das Waehrungswort qualifiziert eine benachbarte Zahl als Betrag. Ohne
Wortgrenze tut das jede Zeichenfolge, die mit `Eur` beginnt:
`Europastr.`, `Eurotunnel`, `europaweit`. Dritter Fall dieser Klasse
nach „ki" in „Kita" (#970) und „us" in „Kundenservice" (#996) — und in
#1018 wurde die Wortgrenze bei `p. a.` ausdruecklich nachgezogen und
beim Waehrungswort vergessen. **Dieselbe Regel, zwei Stellen, eine
davon uebersehen.**

## Befund 3: ein falscher Wert war nicht korrigierbar

`gehalt_extrahieren` liest denselben Text beim naechsten Mal wieder
gleich, und `stelle_bearbeiten` kennt die Gehaltsfelder nicht. Damit
war **jeder** Fehltreffer dauerhaft, nicht nur dieser eine. Fuer
Dokumente gibt es `dokument_text_setzen` genau dafuer.

Neu `gehalt_setzen`. Der Schutz sitzt am Nadeloehr `save_salary_data`
und nicht bei den drei Aufrufern — eine Regel in einem von dreien
verschiebt die Divergenz bloss (#963). Und `save_jobs` braucht eine
EIGENE Zeile dafuer: `_BEWAHREN` schuetzt nur Spalten ausserhalb der
INSERT-Liste, und `salary_min`/`salary_max` stehen darin. Ohne sie
haette die Korrektur bis zum naechsten Suchlauf gehalten — lange genug,
um sie fuer dauerhaft zu halten, kurz genug, um unbemerkt zu
verschwinden.

## Arbeitsweise, zum wiederholten Mal teuer

Der Fix an `_WAEHRUNG` ging beim ersten Versuch in die Heredoc-Falle
(v1.7.24 MERKE 4): aus `\\b` wurde ein literales **Backspace-Zeichen**,
und `_WAEHRUNG` enthielt danach `\\x08`. Zwei vorher gruene Faelle
wurden rot, `grep` zeigte eine unauffaellige Zeile, und erst `cat -v`
machte es sichtbar. Die Lehre steht seit einem Jahr im Projekt — und
die Vorlage, aus der man kopiert, enthaelt sie nicht.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import gehalt_extraktion as ge  # noqa: E402


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.switch_profile(datenbank.create_profile("Gehalt"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung="g1", beschreibung="Text. " * 20):
    db.save_jobs([{
        "hash": kennung, "title": "Rolle", "company": "Firma",
        "url": f"https://example.com/1026/{kennung}",
        "source": "manuell", "_manual_entry": True,
        "description": beschreibung, "score": 5,
    }])
    return db.resolve_job_hash(kennung)


# ------------------------------------------------- AK 4: die Meldezeile


def test_die_reproduktionszeile_ergibt_kein_gehalt():
    """Die Zeile aus dem Bericht, woertlich.

    Vorher: 10 bis 55.510 EUR im Jahr, als belegt.
    """
    e = ge.extrahieren(
        "Telefon 0221-55510-10  Europastr. 1, 12345 Musterstadt")
    assert e["min"] is None, f"Gefunden: {e}"
    assert e["max"] is None
    assert e["art"] is None


# ------------------------------------------- AK 1: Plausibilitaetsgrenze


@pytest.mark.parametrize("text", [
    "Telefon 0221-55510-10  Europastr. 1",
    "Jahresgehalt 10 - 55510 EUR brutto",
    "Gehalt: 5 - 250000 Euro",
])
def test_ein_wert_ausserhalb_des_rahmens_verwirft_die_fundstelle(text):
    """Verworfen wird die GANZE Spanne, nicht nur der eine Wert.

    Eine halbe Spanne ist keine Angabe — lieber gar kein Wert als ein
    falscher (#989).
    """
    e = ge.extrahieren(text)
    assert e["min"] is None, f"{text!r} ergab {e['min']}-{e['max']}"


@pytest.mark.parametrize("text,erwartet_min,erwartet_max", [
    ("Gehalt: 58.000 - 62.000 Euro", 58000.0, 62000.0),
    ("49.847 - 79.836 EUR jaehrlich", 49847.0, 79836.0),
    ("60.000 - 80.000 EUR brutto", 60000.0, 80000.0),
    ("Tagessatz 900-1100 EUR", 900.0, 1100.0),
    ("3.750 - 4.050 € / Monat", 45000.0, 48600.0),
    ("Stundensatz 60 EUR/h", 60.0, 66.0),
])
def test_echte_angaben_bleiben_unberuehrt(text, erwartet_min, erwartet_max):
    """Die Gegenrichtung — beim Haerten beide Richtungen messen (#966).

    Die drei mittleren Faelle sind genau die, die meine erste Fassung
    der Wortgrenze kaputt gemacht hat.
    """
    e = ge.extrahieren(text)
    assert e["min"] == erwartet_min, f"{text!r} -> {e}"
    assert e["max"] == erwartet_max


# ------------------------------------------------- AK 2: min <= max


@pytest.mark.parametrize("text", [
    "Telefon 0221-55510-10  Europastr. 1",
    "Gehalt: 58.000 - 62.000 Euro",
    "62.000 - 58.000 EUR brutto",
    "49.847 - 79.836 EUR jaehrlich",
])
def test_min_ist_nie_groesser_als_max(text):
    e = ge.extrahieren(text)
    if e["min"] is not None:
        assert e["min"] <= e["max"], f"{text!r} -> {e['min']} > {e['max']}"


# ------------------------------------------- AK 3: Wortgrenze am Waehrungswort


@pytest.mark.parametrize("text", [
    "Europastr. 1, 45000 Musterstadt",
    "Eurotunnel-Projekt, 45000 Teilnehmende",
    "europaweit taetig mit 45000 Mitarbeitenden",
    "Eurofighter-Programm, 45000 Stunden",
])
def test_eur_am_wortanfang_qualifiziert_keine_zahl(text):
    """„Eur" ist nur dann eine Waehrung, wenn es als eigenes Wort
    dasteht."""
    e = ge.extrahieren(text)
    assert e["min"] is None, f"{text!r} ergab {e['min']}"


@pytest.mark.parametrize("text", [
    "45.000 EUR brutto",
    "45.000 Euro brutto",
    "45.000 € brutto",
    "45.000 eur brutto",
])
def test_das_waehrungswort_als_eigenes_wort_zaehlt_weiter(text):
    e = ge.extrahieren(text)
    assert e["min"] == 45000.0, f"{text!r} -> {e}"


def test_das_waehrungsmuster_traegt_wortgrenzen():
    """Die Regel selbst, nicht nur ihre Wirkung.

    Ein Guard gegen den Rueckfall: der Fix ist ein einzelnes `\\b`, und
    genau das ist beim ersten Versuch zu einem Backspace-Zeichen
    geworden, ohne dass `grep` etwas gezeigt haette.
    """
    assert chr(8) not in ge._WAEHRUNG, (
        "Im Waehrungsmuster steht ein literales Backspace-Zeichen — "
        "die Heredoc-Falle aus v1.7.24 MERKE 4")
    assert ge._WAEHRUNG.count(chr(92) + "b") >= 4, (
        f"Wortgrenzen fehlen: {ge._WAEHRUNG!r}")


def test_keine_steuerzeichen_im_modul():
    """Dasselbe fuer die ganze Datei — ein Backspace ist unsichtbar."""
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "services"
              / "gehalt_extraktion.py").read_text(encoding="utf-8")
    for zeichen in (chr(8), chr(12), chr(7)):
        assert zeichen not in quelle, (
            f"Steuerzeichen {zeichen!r} im Modul — vermutlich ein "
            f"Escaping-Unfall beim Patchen")


# ------------------------------------- Befund 3: von Hand setzen und loeschen


def _register(db):
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.analyse import register as _reg
    mcp = FastMCP("test")
    _reg(mcp, db, logging.getLogger("test"))
    return mcp


def _call(mcp, name, args):
    import asyncio

    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def test_gehalt_von_hand_setzen_und_wieder_freigeben(db):
    h = _stelle(db)
    mcp = _register(db)

    erg = _call(mcp, "gehalt_setzen",
                {"job_hash": h, "min_wert": 65000, "max_wert": 75000})
    assert erg["status"] == "gesetzt"
    assert erg["herkunft"] == "mensch"

    job = db.get_job(h)
    assert job["salary_min"] == 65000
    assert job["salary_max"] == 75000
    assert job["salary_estimated"] == 0

    frei = _call(mcp, "gehalt_setzen", {"job_hash": h, "loeschen": True})
    assert frei["status"] == "geloescht"
    assert db.get_job(h)["salary_min"] is None


def test_ein_handwert_ueberlebt_den_automatischen_lauf(db):
    """Der Kern von Befund 3."""
    h = _stelle(db)
    mcp = _register(db)
    _call(mcp, "gehalt_setzen",
          {"job_hash": h, "min_wert": 65000, "max_wert": 75000})

    # Der automatische Weg versucht zu schreiben — und wird abgewiesen.
    geschrieben = db.save_salary_data(h, 10, 55510, "jaehrlich",
                                      salary_estimated=0)
    assert geschrieben is False
    assert db.get_job(h)["salary_min"] == 65000


def test_ein_handwert_ueberlebt_einen_erneuten_suchlauf(db):
    """`_BEWAHREN` genuegt hier NICHT.

    Es schuetzt Spalten ausserhalb der INSERT-Liste, und `salary_min`
    steht darin. Ohne die eigene Regel in `save_jobs` haette die
    Korrektur bis zum naechsten Suchlauf gehalten.
    """
    h = _stelle(db)
    mcp = _register(db)
    _call(mcp, "gehalt_setzen",
          {"job_hash": h, "min_wert": 65000, "max_wert": 75000})

    # Dieselbe Stelle kommt im naechsten Lauf wieder herein.
    db.save_jobs([{
        "hash": "g1", "title": "Rolle", "company": "Firma",
        "url": "https://example.com/1026/g1",
        "source": "manuell", "_manual_entry": True,
        "description": "Text. " * 20, "score": 5,
        "salary_min": 10, "salary_max": 55510, "salary_type": "jaehrlich",
    }])

    job = db.get_job(h)
    assert job["salary_min"] == 65000, (
        "Der erneute Suchlauf hat den Handwert ueberschrieben")
    assert job["salary_quelle"] == "mensch"


def test_ein_freigegebener_wert_ist_wieder_automatisch_schreibbar(db):
    """Die Gegenrichtung: der Schutz darf nicht unaufhebbar sein."""
    h = _stelle(db)
    mcp = _register(db)
    _call(mcp, "gehalt_setzen",
          {"job_hash": h, "min_wert": 65000, "max_wert": 75000})
    _call(mcp, "gehalt_setzen", {"job_hash": h, "loeschen": True})

    assert db.save_salary_data(h, 58000, 62000, "jaehrlich",
                               salary_estimated=0) is True
    assert db.get_job(h)["salary_min"] == 58000


def test_vertauschte_werte_werden_abgewiesen_statt_getauscht(db):
    """Beim Menschen wird NICHT stillschweigend getauscht.

    Am Nadeloehr tauscht `_gehalt_gesund` vertauschte Werte — das ist
    ein Riegel gegen kaputte Automatik-Werte. Hier hat ein Mensch zwei
    Zahlen genannt, und welche er meinte, weiss nur er.
    """
    h = _stelle(db)
    mcp = _register(db)
    erg = _call(mcp, "gehalt_setzen",
                {"job_hash": h, "min_wert": 75000, "max_wert": 65000})
    assert "fehler" in erg
    assert db.get_job(h)["salary_min"] is None


def test_ein_ungewoehnlicher_wert_wird_gemeldet_aber_gespeichert(db):
    """Die Grenzen filtern Fehltreffer der MASCHINE.

    Ein Mensch darf einen Sonderfall eintragen — er soll nur wissen,
    dass er einer ist (#989: eine Luecke gehoert benannt, nicht
    gefuellt).
    """
    h = _stelle(db)
    mcp = _register(db)
    erg = _call(mcp, "gehalt_setzen",
                {"job_hash": h, "min_wert": 450000, "max_wert": 500000})
    assert erg["status"] == "gesetzt"
    assert "ungewoehnlich" in erg
    assert db.get_job(h)["salary_min"] == 450000


def test_gehalt_extrahieren_meldet_den_handwert_statt_still_zu_scheitern(db):
    """Eine Erfolgsmeldung ueber eine Nicht-Aenderung beendet die
    Fehlersuche (#994/#997)."""
    h = _stelle(db, beschreibung="Wir bieten 58.000 - 62.000 Euro brutto. "
                                 + "Text. " * 20)
    mcp = _register(db)
    _call(mcp, "gehalt_setzen",
          {"job_hash": h, "min_wert": 65000, "max_wert": 75000})

    erg = _call(mcp, "gehalt_extrahieren", {"job_hash": h})
    assert erg["status"] == "von_hand_gesetzt"
    assert db.get_job(h)["salary_min"] == 65000


def test_unbekannte_stelle_bekommt_eine_absage(db):
    mcp = _register(db)
    erg = _call(mcp, "gehalt_setzen",
                {"job_hash": "gibt-es-nicht", "min_wert": 50000})
    assert "fehler" in erg


@pytest.mark.parametrize("text,erwartet", [
    # Telefonnummer VORNE, echtes Gehalt HINTEN.
    ("Fragen? Telefon 0221-55510-10, Europastr. 1. "
     "Wir bieten 60.000 EUR brutto.", 60000.0),
    # Umgekehrte Reihenfolge.
    ("Wir bieten 60.000 EUR brutto. Kontakt: 0221-55510-10 Europastr. 1",
     60000.0),
    # Die verworfene Spanne allein bleibt eine Absage.
    ("Fragen? Telefon 0221-55510-10, Europastr. 1.", None),
])
def test_eine_verworfene_fundstelle_kostet_nicht_die_echte(text, erwartet):
    """Die Gegenrichtung zur Unterdrueckung des Einzelwert-Pfads.

    Die Sperre haengt an der STELLE im Text, nicht an der Art — sonst
    verloere eine Anzeige mit einer Telefonnummer vorne ihr echtes
    Gehalt weiter hinten. Beim Haerten beide Richtungen messen (#966).
    """
    e = ge.extrahieren(text)
    assert e["min"] == erwartet, f"{text!r} -> {e}"


def test_der_bestandslauf_zaehlt_uebersprungene_handwerte(db):
    """`gehaelter_neu_auswerten` meldet, was es NICHT angefasst hat.

    Sonst erschiene eine Stelle als unveraendert, obwohl der Lauf sie
    sehr wohl aendern wollte — und der Mensch wuesste nicht, dass sein
    Handwert gegriffen hat.
    """
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.jobs import register as _reg_jobs

    h = _stelle(db, beschreibung="Wir bieten 58.000 - 62.000 Euro brutto. "
                                 + "Text. " * 20)
    mcp_a = _register(db)
    _call(mcp_a, "gehalt_setzen",
          {"job_hash": h, "min_wert": 65000, "max_wert": 75000})

    mcp_j = FastMCP("test-jobs")
    _reg_jobs(mcp_j, db, logging.getLogger("test"))
    erg = _call(mcp_j, "gehaelter_neu_auswerten", {"dry_run": False})

    assert erg["von_hand_gesetzt_uebersprungen"] >= 1
    assert db.get_job(h)["salary_min"] == 65000


# ------------------- Die Faelle, die JEDEN Mechanismus EINZELN pruefen


@pytest.mark.parametrize("text", [
    # Waehrungswort echt, Reihenfolge vertauscht, Untergrenze unplausibel.
    # Die Wortgrenze hilft hier NICHT — nur die Grenze gegen beide Werte.
    "Jahresgehalt: 50352 - 10 EUR brutto",
    "Gehalt: 60000 - 12 Euro",
])
def test_beide_werte_muessen_die_grenze_passieren(text):
    """Isoliert Befund 1.

    Die Gegenprobe hat gezeigt, dass die uebrigen Tests auch ohne diese
    Pruefung gruen bleiben: im gemeldeten Fall faengt schon die
    Wortgrenze den Treffer ab, und in `"10 - 55510"` scheitert bereits
    `zahlen[0]` an der ersten Pruefung. **Zwei Fixes, die denselben Fall
    abdecken, belegen einander nicht** — deshalb dieser Fall, in dem das
    Waehrungswort echt ist und nur die zweite Zahl unplausibel.
    """
    e = ge.extrahieren(text)
    assert e["min"] is None, f"{text!r} ergab {e['min']}-{e['max']}"


@pytest.mark.parametrize("text", [
    # Beide Zahlen sind fuer ein Jahresgehalt plausibel; qualifiziert
    # wird die Spanne allein durch "Eur" in "Europastr." bzw.
    # "Eurotunnel". Hier hilft nur die Wortgrenze.
    "Projektnummer 45000-80000 Europastr. 1",
    "Hausnummer 30000-90000 Eurotunnel",
])
def test_nur_die_wortgrenze_faengt_diesen_fall(text):
    """Isoliert Befund 2.

    Meine ersten Tests zu diesem Befund waren wertlos: `"Europastr. 1,
    45000 Musterstadt"` enthaelt gar keine Spanne und keinen Beleg
    dahinter, der Treffer scheiterte also aus einem anderen Grund. Sie
    blieben gruen, als ich die Wortgrenze zur Probe wieder ausbaute.
    **Ein Test, der auch ohne den Mechanismus gruen bleibt, prueft ihn
    nicht** (v1.7.79, dritter Fall).
    """
    e = ge.extrahieren(text)
    assert e["min"] is None, f"{text!r} ergab {e['min']}-{e['max']}"


# ----------- Dritter Befund, nicht gemeldet: der Punkt als Dezimaltrenner


@pytest.mark.parametrize("text,erwartet_min,erwartet_max", [
    ("72.5-103k EUR", 72500.0, 103000.0),
    ("56.5-76k EUR/Jahr", 56500.0, 76000.0),
    ("67.5-89k EUR/Jahr", 67500.0, 89000.0),
    ("60-76.5k EUR/Jahr", 60000.0, 76500.0),
    # Dieselbe Anzeige mit deutschem Dezimalkomma.
    ("72,5-103k EUR", 72500.0, 103000.0),
])
def test_der_punkt_als_dezimaltrenner(text, erwartet_min, erwartet_max):
    """Beim Nachmessen der eigenen Aenderung gefunden, nicht gemeldet.

    `_ZAHL` verlangte hinter einem Punkt DREI Ziffern
    (Tausendertrennung). `"72.5"` fiel durch und wurde als blosse `5`
    gelesen — aus der Spanne 72.500 bis 103.000 wurde 5 bis 103, die an
    der Plausibilitaetsgrenze scheiterte.

    **Der Schaden lag danach im Einzelwert-Pfad:** der griff sich `103k`
    heraus und machte daraus 103.000 bis 113.300 — also die OBERGRENZE
    als Untergrenze. Am Bestand gemessen betraf das drei Anzeigen, alle
    drei sahen dadurch besser bezahlt aus als sie sind, und genau dieser
    Wert geht in den Score ein.

    Ueber 1.337 Anzeigen nachgerechnet: **0 Angaben fallen weg, 6 kommen
    dazu, 3 werden korrigiert.**
    """
    e = ge.extrahieren(text)
    assert (e["min"], e["max"]) == (erwartet_min, erwartet_max), f"{text!r} -> {e}"


@pytest.mark.parametrize("roh,erwartet", [
    ("72.5", 72.5),        # eine Ziffer -> Dezimalstelle
    ("72.50", 72.5),       # zwei Ziffern -> Dezimalstelle
    ("72.500", 72500.0),   # drei Ziffern -> Tausender
    ("45.000", 45000.0),
    ("1.234.567", 1234567.0),
    ("2.316,67", 2316.67),
    ("103", 103.0),
])
def test_punkt_heisst_tausender_oder_dezimalstelle(roh, erwartet):
    """Unterschieden wird an der ZAHL der Ziffern dahinter.

    Drei heisst Tausender, eine oder zwei heissen Dezimalstelle. Ein
    Text, in dem beide Schreibweisen vorkommen, ist damit lesbar.
    """
    assert ge._zahl(roh) == erwartet


def test_die_obergrenze_wird_nie_zur_untergrenze():
    """Die Eigenschaft hinter den drei korrigierten Anzeigen.

    Sie prueft keinen Einzelfall, sondern eine Regel: wo der Text eine
    Spanne nennt, darf der groessere Wert nie als Minimum herauskommen.
    """
    for text in ("72.5-103k EUR", "56.5-76k EUR/Jahr", "60-76.5k EUR/Jahr",
                 "Gehalt: 58.000 - 62.000 Euro", "900-1100 EUR pro Tag"):
        e = ge.extrahieren(text)
        if e["min"] is None:
            continue
        zahlen = [float(z.replace(",", ".")) for z in
                  __import__("re").findall(r"\d+(?:[.,]\d+)?", text)]
        assert e["min"] <= e["max"]
        assert not e["gerechnete_spanne"], (
            f"{text!r} nennt eine Spanne, es wurde aber eine gerechnet — "
            f"dabei entsteht die Obergrenze aus dem falschen Wert")
        assert zahlen  # die Anzeige nennt wirklich Zahlen
