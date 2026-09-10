"""Tests fuer #931 — was ich mindestens nehme, und was ich sage.

Ein Feld erfuellte zwei Zwecke, die einander widersprechen: die
Filterschwelle (der NIEDRIGSTE noch akzeptable Wert) und den Nennwert
im Gespraech (ein HOEHERER Wert, weil von der genannten Zahl nach unten
verhandelt wird).

Nutzerwort:

    "was in den einstellungen steht, das zaehlt, das ist minimum. was
    ich dann den kunden und in den stellen sage, haengt an den
    kunden/stellen. unter den min. gehalts-saetzen die
    wunsch-nennungs-saetze (editierbar)."

Die sieben Akzeptanzkriterien stehen hier einzeln (DoD 8a).
"""
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import nennwerte  # noqa: E402


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


# ------------------------------------- AK 2: der Kern des ganzen Issues


def test_931_der_wunschwert_wirkt_nicht_im_scoring(db):
    """AK 2 woertlich: gleicher Score mit und ohne gesetzten Wunschwert.

    **Was dieser Test NICHT beweist, und das gehoert hierher.** Die
    Gegenprobe hat es gezeigt: nimmt man die Trennung im Nadeloehr
    wieder heraus, bleibt er GRUEN. Der Grund ist banal — `calculate_score`
    liest die drei neuen Schluessel schlicht nicht, weil sie neu sind.
    Er belegt also, dass heute kein Rechenweg sie anfasst, nicht dass
    sie ferngehalten werden.

    Der Test, der die Trennung wirklich prueft, ist
    `test_931_das_nadeloehr_entfernt_die_wunschwerte` — er ist in der
    Gegenprobe als einziger rot geworden.

    Trotzdem bleibt dieser hier stehen: er ist der Waechter fuer den
    Tag, an dem jemand das Scoring generisch ueber die Kriterien laufen
    laesst. Dann faellt er als erster.
    """
    from bewerbungs_assistent.job_scraper import calculate_score
    from bewerbungs_assistent.services import scoring_kriterien

    db.set_search_criteria("keywords_muss", ["plm"])
    db.set_search_criteria("min_gehalt", 70000.0)

    stelle = {
        "title": "PLM Fachkraft Quintus",
        "company": "Halbleiterwerk Nord GmbH",
        "description": "Wir suchen PLM-Erfahrung. " * 20,
        "salary_min": 75000, "salary_max": 85000,
        "location": "Hamburg",
    }

    ohne = calculate_score(dict(stelle), scoring_kriterien.fuer_scoring(db))
    db.set_search_criteria("wunsch_gehalt", 95000.0)
    mit = calculate_score(dict(stelle), scoring_kriterien.fuer_scoring(db))

    ohne_wert = ohne[0] if isinstance(ohne, tuple) else ohne
    mit_wert = mit[0] if isinstance(mit, tuple) else mit
    assert ohne_wert == mit_wert, (
        f"Der Wunschwert hat den Score veraendert: {ohne_wert} -> {mit_wert}")


def test_931_das_nadeloehr_entfernt_die_wunschwerte(db):
    """Die Trennung sitzt an EINER Stelle.

    `fuer_scoring` speist Suchlauf, Neuberechnung, Fit-Analyse,
    Newsletter-Import und die manuelle Anlage. Die Trennung an den
    Aufrufern zu wiederholen waere die Bauform, die dieses Projekt
    vierzehnmal gekostet hat (#963 zuerst).
    """
    from bewerbungs_assistent.services import scoring_kriterien

    db.set_search_criteria("wunsch_gehalt", 95000.0)
    db.set_search_criteria("wunsch_tagessatz", 1200.0)
    db.set_search_criteria("min_gehalt", 70000.0)

    krit = scoring_kriterien.fuer_scoring(db)
    for feld in nennwerte.WUNSCH_FELDER:
        assert feld not in krit, f"{feld} steht in den Scoring-Kriterien."
    # Das Minimum bleibt — es SOLL wirken.
    assert krit.get("min_gehalt") == 70000.0


def test_931_die_kriterien_des_aufrufers_bleiben_unberuehrt():
    """Entfernt wird auf einer Kopie.

    Sonst verschwaende der Wunschwert auch fuer die Anzeige, und die
    soll ihn ja gerade zeigen.
    """
    original = {"min_gehalt": 70000, "wunsch_gehalt": 95000}
    sauber = nennwerte.aus_scoring_entfernen(original)
    assert "wunsch_gehalt" not in sauber
    assert original["wunsch_gehalt"] == 95000, "Das Original wurde veraendert."


# --------------------------------- AK 1/3: schreibbar und getrennt lesbar


def test_931_die_wunschwerte_sind_schreibbar_und_getrennt_lesbar(db):
    """AK 1 + 3, ueber die echten Werkzeuge."""
    import asyncio
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all

    mcp = FastMCP("PBP Test 931")
    register_all(mcp, db, logging.getLogger("test.931"))

    def _ruf(name, args):
        async def _lauf():
            werkzeug = await mcp.get_tool(name)
            erg = await werkzeug.run(args)
            return getattr(erg, "structured_content", erg)
        return asyncio.run(_lauf())

    _ruf("suchkriterien_setzen", {
        "keywords_muss": ["plm"],
        "min_gehalt": 70000, "wunsch_gehalt": 95000,
        "min_tagessatz": 900, "wunsch_tagessatz": 1200,
    })
    antwort = _ruf("suchkriterien_anzeigen", {})
    saetze = antwort.get("saetze") or {}
    zeilen = {z["feld"]: z for z in saetze.get("werte", [])}

    assert zeilen["min_gehalt"]["minimum"] == 70000.0
    assert zeilen["min_gehalt"]["wunsch"] == 95000.0
    assert zeilen["min_tagessatz"]["wunsch"] == 1200.0
    # Beide sind BENANNT — eine Zahl ohne Bedeutung waere die
    # Vermischung, wegen der das Issue entstanden ist.
    assert "Filterschwelle" in saetze["bedeutung"]["minimum"]
    assert "NICHT im Scoring" in saetze["bedeutung"]["wunsch"]


def test_931_ein_nennwert_unter_dem_minimum_wird_benannt(db):
    """Kein Block — nur der Hinweis. Es kann Absicht sein.

    Aber von der genannten Zahl wird nach unten verhandelt, nie nach
    oben: ein Nennwert unter dem eigenen Minimum ist fast immer ein
    Vertipper.
    """
    db.set_search_criteria("min_gehalt", 80000.0)
    db.set_search_criteria("wunsch_gehalt", 60000.0)
    zeilen = {z["feld"]: z for z in nennwerte.uebersicht(db)["werte"]}
    assert "hinweis" in zeilen["min_gehalt"]
    # Gespeichert wurde er trotzdem.
    assert zeilen["min_gehalt"]["wunsch"] == 60000.0


def test_931_ohne_gesetzte_werte_schweigt_die_uebersicht(db):
    """Ein Abschnitt, der immer dasteht, wird nach dem zweiten Mal
    ignoriert (#929)."""
    assert nennwerte.uebersicht(db)["werte"] == []


# ------------------------------------------ AK 4: Vorbelegung je Bewerbung


def test_931_die_stellenart_entscheidet_welcher_nennwert_vorsteht(db):
    """Ein Freelance-Projekt fragt nach dem Tagessatz, nicht nach dem
    Jahresgehalt."""
    db.set_search_criteria("wunsch_gehalt", 95000.0)
    db.set_search_criteria("wunsch_tagessatz", 1200.0)
    db.set_search_criteria("wunsch_stundensatz", 150.0)

    assert nennwerte.vorbelegung(db, "festanstellung")["feld"] == "wunsch_gehalt"
    assert nennwerte.vorbelegung(db, "freelance")["feld"] == "wunsch_tagessatz"
    assert nennwerte.vorbelegung(db, "werkstudent")["feld"] == "wunsch_stundensatz"


def test_931_ohne_wunschwert_gibt_es_keine_vorbelegung(db):
    """Eine erfundene Zahl in einem Gehaltsfeld waere schlimmer als
    keine (#989, #1006)."""
    assert nennwerte.vorbelegung(db, "festanstellung") is None


def test_931_die_bewerbung_schlaegt_den_nennwert_vor(db):
    """AK 4 am echten Werkzeug."""
    import asyncio
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all

    db.set_search_criteria("wunsch_gehalt", 95000.0)
    mcp = FastMCP("PBP Test 931b")
    register_all(mcp, db, logging.getLogger("test.931b"))

    async def _lauf():
        werkzeug = await mcp.get_tool("bewerbung_erstellen")
        erg = await werkzeug.run({
            "title": "Rolle Quintus", "company": "Halbleiterwerk Nord GmbH"})
        return getattr(erg, "structured_content", erg)

    antwort = asyncio.run(_lauf())
    vorschlag = antwort.get("gehaltsvorstellung_vorschlag")
    assert vorschlag is not None, "Kein Nennwert vorgeschlagen."
    assert vorschlag["wert"] == 95000.0
    assert "entscheidest du" in vorschlag["hinweis"]


def test_931_die_vorbelegung_ist_ein_vorschlag_keine_festlegung(db):
    """Sie SCHREIBT nichts — sie steht in der Antwort.

    `bewerbung_erstellen` nimmt gar keine `gehaltsvorstellung` entgegen
    (die gibt es an `bewerbung_bearbeiten`), und beim Erfassen steht die
    Zahl meist noch nicht fest. Der Vorschlag darf deshalb auf keinen
    Fall ins Feld geschrieben werden — eine Zahl, die niemand genannt
    hat, in einem Gehaltsfeld waere eine erfundene Angabe (#1006).
    """
    import asyncio
    import inspect
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all

    db.set_search_criteria("wunsch_gehalt", 95000.0)
    mcp = FastMCP("PBP Test 931c")
    register_all(mcp, db, logging.getLogger("test.931c"))

    async def _lauf():
        werkzeug = await mcp.get_tool("bewerbung_erstellen")
        erg = await werkzeug.run({
            "title": "Rolle Quintus Zwei",
            "company": "Halbleiterwerk Nord GmbH"})
        return getattr(erg, "structured_content", erg)

    antwort = asyncio.run(_lauf())
    bewerbung = db.get_application(antwort["bewerbung_id_voll"])
    assert not (bewerbung.get("gehaltsvorstellung") or ""), (
        "Der Vorschlag wurde ins Feld geschrieben.")
    # In der ANTWORT steht er sehr wohl — dort gehoert er hin.
    assert antwort["gehaltsvorstellung_vorschlag"]["wert"] == 95000.0


# ---------------------------------- AK 5/6: die Nebenbefunde, nachgemessen


def test_931_die_wunschfelder_gelten_als_eigene_kriterien():
    """AK 5 sinngemaess: ein gleichnamiger Eintrag im Sammelbecken
    waere wirkungslos und saehe doch nach einer Einstellung aus.

    Das ist der Fall aus #988. Der vorhandene Widerspruchs-Melder
    (#813 AK 6) deckt die neuen Felder jetzt mit ab.
    """
    from bewerbungs_assistent.tools.suche import _EIGENE_KRITERIEN

    for feld in nennwerte.WUNSCH_FELDER:
        assert feld in _EIGENE_KRITERIEN, (
            f"{feld} wuerde als custom_kriterien-Eintrag stillschweigend "
            "wirkungslos bleiben.")


def test_931_der_widerspruchs_melder_erkennt_die_doppelung(db):
    """Beide Richtungen: er meldet, wenn es kollidiert — und schweigt
    sonst (#929)."""
    from bewerbungs_assistent.tools.suche import _custom_widerspruch

    assert _custom_widerspruch({"custom_kriterien": {"homeoffice": 9}}) is None
    meldung = _custom_widerspruch(
        {"custom_kriterien": {"wunsch_gehalt": 95000}})
    assert meldung and "wunsch_gehalt" in meldung


def test_931_das_frontend_bietet_die_felder_unter_dem_minimum():
    """AK 1: "unter den min. gehalts-saetzen die wunsch-nennungs-saetze"."""
    seite = (_repo() / "frontend" / "src" / "pages"
             / "ProfilePage.jsx").read_text(encoding="utf-8")
    for feld in nennwerte.WUNSCH_FELDER:
        assert f"criteriaDraft.{feld}" in seite, f"{feld} fehlt im Formular."
    # ... und zwar NACH dem Minimum, nicht davor.
    assert seite.index("criteriaDraft.min_stundensatz") < seite.index(
        "criteriaDraft.wunsch_gehalt"), (
        "Die Nennwerte stehen ueber den Minimum-Saetzen.")
    # Der Hinweis sagt, dass sie nicht filtern — sonst haelt man sie
    # fuer eine zweite Schwelle.
    assert "Filtert nicht" in seite


def test_931_die_migration_legt_die_felder_leer_an(db):
    """AK 7: vorhandene Minimum-Werte werden NICHT umgesetzt.

    Ein Minimum, das stillschweigend zum Nennwert wird, waere eine
    erfundene Angabe in einer Gehaltsverhandlung — und die vorhandene
    Filterschwelle waere gleichzeitig weg.
    """
    db.set_search_criteria("min_gehalt", 70000.0)
    kriterien = db.get_search_criteria() or {}
    for feld in nennwerte.WUNSCH_FELDER:
        assert kriterien.get(feld) in (None, "", 0), (
            f"{feld} wurde ungefragt befuellt.")
    assert nennwerte.lesen(db) == {}
