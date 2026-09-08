"""Tests fuer v1.7.48 — #1000: Parameter ohne Leser.

Das tausendste Issue des Projekts, gemeldet vom selben Anwender wie
#990, #994, #997 und #998:

    jobsuche_starten(keywords=[...], max_entfernung_km=15)

hat keine Wirkung. Stellen weit ausserhalb des Radius landen unveraendert
im Bestand, und `nur_remote=True` ebenso wenig. Beide Werte wurden
entgegengenommen, in die Job-Parameter geschrieben und von `run_search`
nie wieder angesehen; einziger Leser von `nur_remote` im ganzen Baum ist
der LinkedIn-Adapter, und der ist ueber dieses Tool gar nicht erreichbar.

**Beim Nachsehen zeigte sich, dass es nicht zwei Fundstellen waren,
sondern eine Familie: "maximale Entfernung" gibt es in vier
Schreibweisen, und nur eine hat einen Leser.**

1. `jobsuche_starten(max_entfernung_km=...)` — kein Leser (gemeldet)
2. `criteria["max_entfernung_km"]` — kein Leser. **Live gemessen am
   08.09.2026: steht auf 30**, waehrend `max_entfernung.freelance` auf
   1500 steht. Das Frontend schreibt das Feld, gerechnet wird gegen die
   Karte.
3. Der Ersterfassungs-Prompt weist Claude an, `max_entfernung_km` und
   `remote` an `suchkriterien_setzen` zu geben — **beide Parameter gibt
   es dort nicht.** Der Entfernungswunsch verdunstet damit ausgerechnet
   beim Onboarding.
4. `criteria["max_entfernung"]` — die Karte je Stellenart, der einzige
   Wert, gegen den gerechnet wird.

Die Entscheidung gegen den Einbau der beiden Tool-Parameter ist
inhaltlich, nicht nur pragmatisch: als harte Filter wuerden sie zwei
bewussten Entscheidungen widersprechen. Entfernung ist ein PREIS, kein
Ausschluss (#910/#988), und `nur_remote` als Filter verwuerfe jede
Stelle mit unbekanntem `remote_level` — also genau die Verwechslung von
"unbekannt" und "erfuellt nicht", die #989 abgeschafft hat.
"""
import importlib
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def db():
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_1000_")
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = tmpdir
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Muster Person"})
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt
        shutil.rmtree(tmpdir, ignore_errors=True)


def _tools(modul, db):
    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    modul.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt


@pytest.fixture
def suche(db):
    from bewerbungs_assistent.tools import suche as such_tools
    return _tools(such_tools, db)


# ── Die toten Parameter sind weg ──────────────────────────────────────

def test_1000_jobsuche_starten_hat_die_toten_parameter_nicht_mehr(db):
    """Ein Parameter ohne Wirkung ist schlechter als kein Parameter.

    Der Aufrufer bekommt jetzt einen lauten Fehler statt einer stillen
    Wirkungslosigkeit — das ist die ganze Absicht.
    """
    import inspect
    from bewerbungs_assistent.tools import jobs as job_tools
    gesammelt = _tools(job_tools, db)
    parameter = inspect.signature(gesammelt["jobsuche_starten"]).parameters
    assert "max_entfernung_km" not in parameter
    assert "nur_remote" not in parameter
    assert set(parameter) == {"keywords", "quellen"}


def test_1000_die_docstring_verspricht_nichts_mehr(db):
    """Die alte Docstring sagte woertlich "Maximale Entfernung in km
    (0 = kein Limit)". Ein Nutzer ohne Auto liest das als harte Grenze."""
    from bewerbungs_assistent.tools import jobs as job_tools
    text = _tools(job_tools, db)["jobsuche_starten"].__doc__
    assert "suchkriterien_setzen(max_entfernung_km=" in text
    assert "kein Limit" not in text


def test_1000_kein_aufrufer_reicht_die_toten_werte_mehr_durch():
    """Der Dashboard-Weg war identisch gebaut, und der Zeitplaner
    reichte sie ebenfalls durch. Eine Fundstelle zu beheben und die
    anderen stehen zu lassen waere die halbe Arbeit."""
    basis = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
    for datei in ("dashboard.py", "tools/jobs.py",
                  "services/automatik_scheduler.py"):
        code = "\n".join(
            z for z in (basis / datei).read_text(encoding="utf-8").split("\n")
            if not z.strip().startswith("#"))
        assert '"nur_remote":' not in code, datei
        assert '"max_entfernung_km":' not in code, datei


# ── Der Wunsch hat jetzt einen echten Weg ─────────────────────────────

def test_1000_eine_zahl_fuellt_die_karte(suche, db):
    """Ein Mensch sagt "hoechstens 30 km", nicht eine Karte je
    Stellenart."""
    antwort = suche["suchkriterien_setzen"](max_entfernung_km=30)
    karte = db.get_search_criteria()["max_entfernung"]
    assert set(karte.values()) == {30.0}
    assert "30 km" in antwort["entfernung"]
    # Die Zusage aus #988 steht in der Antwort, damit niemand einen
    # harten Ausschluss erwartet.
    assert "Preis" in antwort["entfernung"]


def test_1000_die_karte_gewinnt_wenn_beides_kommt(suche, db):
    """Der genauere Wunsch schlaegt den groben — und PBP sagt es,
    statt still einen der beiden zu verwerfen."""
    antwort = suche["suchkriterien_setzen"](
        max_entfernung_km=30,
        max_entfernung={"festanstellung": 40, "freelance": 1500})
    karte = db.get_search_criteria()["max_entfernung"]
    assert karte == {"festanstellung": 40, "freelance": 1500}
    assert "ignoriert" in antwort["entfernung"]


def test_1000_nur_die_gewaehlten_stellenarten(suche, db):
    """Wer nur Festanstellung sucht, bekommt keine Werte fuer Praktikum
    und Werkstudent untergeschoben."""
    suche["suchkriterien_setzen"](stellentypen=["festanstellung", "freelance"],
                                  max_entfernung_km=25)
    assert set(db.get_search_criteria()["max_entfernung"]) == {
        "festanstellung", "freelance"}


def test_1000_einzelwert_und_karte_laufen_nicht_auseinander(suche, db):
    """Der frueher tote Einzelwert wird mitgezogen, sobald die Karte
    einheitlich ist — sonst entsteht sofort wieder der Widerspruch, den
    dieses Issue beschreibt."""
    suche["suchkriterien_setzen"](max_entfernung_km=30)
    krit = db.get_search_criteria()
    assert krit["max_entfernung_km"] == 30.0
    # Bei unterschiedlichen Werten je Art gibt es keine ehrliche
    # Einzelzahl — dann steht dort nichts.
    suche["suchkriterien_setzen"](
        max_entfernung={"festanstellung": 30, "freelance": 1500})
    assert db.get_search_criteria().get("max_entfernung_km") in (None, "")


# ── Altbestand: benennen statt still umdeuten ─────────────────────────

def test_1000_wirkungsloser_altwert_wird_benannt(suche, db):
    """Der live gemessene Zustand: 30 im Einzelwert, 1500 fuer Freelance
    in der Karte.

    Eine stille Neudeutung waere eine Score-Aenderung, die niemand
    veranlasst hat — deshalb wird der Widerspruch BENANNT (das Vorgehen
    aus #988 fuer die wirkungslosen Scoring-Regler).
    """
    db.set_search_criteria("max_entfernung", {"festanstellung": 30,
                                              "freelance": 1500})
    db.set_search_criteria("max_entfernung_km", 30)
    antwort = suche["suchkriterien_anzeigen"]()
    hinweis = antwort["hinweis_entfernung"]
    assert "max_entfernung_km = 30" in hinweis
    assert "freelance 1500 km" in hinweis
    # Der Wert bleibt stehen, er wird nur erklaert.
    assert db.get_search_criteria()["max_entfernung_km"] == 30


def test_1000_kein_hinweis_wenn_alles_stimmt(suche, db):
    """Gegenprobe. Ein Pruefer, der bei korrektem Zustand Alarm gibt,
    wird nach dem zweiten Mal ignoriert (DoD-9-Lehre)."""
    suche["suchkriterien_setzen"](stellentypen=["festanstellung"],
                                  max_entfernung_km=30)
    assert "hinweis_entfernung" not in suche["suchkriterien_anzeigen"]()
    # Und ohne Einzelwert erst recht nicht.
    db.set_search_criteria("max_entfernung_km", None)
    assert "hinweis_entfernung" not in suche["suchkriterien_anzeigen"]()


def test_1000_widerspruchspruefer_kommt_mit_luecken_klar():
    """Er laeuft auf JEDER Anzeige — ein Absturz waere teurer als der
    Befund, den er meldet."""
    from bewerbungs_assistent.tools.suche import _entfernung_widerspruch
    for kriterien in ({}, {"max_entfernung_km": 30},
                      {"max_entfernung": {"festanstellung": 30}},
                      {"max_entfernung_km": None,
                       "max_entfernung": {"festanstellung": 30}},
                      {"max_entfernung_km": 0,
                       "max_entfernung": {"festanstellung": 30}},
                      {"max_entfernung_km": 30, "max_entfernung": {}}):
        assert _entfernung_widerspruch(kriterien) is None, kriterien


# ── Der Onboarding-Prompt nennt Parameter, die es gibt ────────────────

def test_1000_ersterfassung_nennt_nur_echte_parameter(db):
    """Der Prompt wies Claude an, `region` und `remote` an
    `suchkriterien_setzen` zu geben. Beide gibt es dort nicht — der
    Entfernungswunsch verdunstete beim Onboarding.

    Der Test prueft die Prompt-Anweisung gegen die ECHTE Signatur, nicht
    gegen eine Liste im Test. Ein kuenftig umbenannter Parameter faellt
    damit auf.
    """
    import inspect
    import re
    from bewerbungs_assistent import prompts
    from bewerbungs_assistent.tools import suche as such_tools

    echte = set(inspect.signature(
        _tools(such_tools, db)["suchkriterien_setzen"]).parameters)

    text = prompts.PROMPTS["ersterfassung"] if hasattr(prompts, "PROMPTS") \
        else inspect.getsource(prompts)
    stelle = text[text.index("suchkriterien_setzen("):][:600]
    genannt = set(re.findall(r"(\w+)=", stelle))
    unbekannt = genannt - echte
    assert not unbekannt, f"Prompt nennt Parameter, die es nicht gibt: {unbekannt}"


def test_1000_ersterfassung_erklaert_wohin_remote_gehoert():
    """Remote ist kein eigener Parameter, sondern ein Eintrag in
    `regionen` — das muss dastehen, sonst raet Claude wieder."""
    import inspect
    from bewerbungs_assistent import prompts
    text = inspect.getsource(prompts)
    stelle = text[text.index("Speichere die bestätigten Begriffe"):][:600]
    assert "regionen" in stelle
    assert "Remote" in stelle
