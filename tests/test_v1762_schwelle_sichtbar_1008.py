"""Tests fuer v1.7.62 — #1008: der unsichtbare Schwellenfilter.

Nutzer-Report vom 09.09.2026: die Sidebar zaehlt 8 Stellen, die Liste
zeigt eine. Neuladen aendert nichts. Wirksam war die
Mindest-Score-Schwelle — und die steht in der Filterzeile nicht.

**Beim Nachsehen dieselbe Bauform im MCP**, also im Kernstueck von PBP:

    for j in jobs:
        result = apply_scoring_adjustments(j, j.get("score", 0), db)
        if result.get("ignored"):
            auto_ignored += 1
            continue          # <- still verworfen
    ...
    logger.info("Scoring-Regler: %d Stellen auto-ignoriert", auto_ignored)

Die Zahl ging ins **Log**, nicht in die Antwort. Und die leere Liste
meldete:

    "Keine Stellen gefunden. Starte eine Jobsuche mit jobsuche_starten()"

waehrend `pbp_diagnose` dieselben Stellen als aktiv fuehrte. **PBP
widersprach sich damit in sich selbst** — und der genannte naechste
Schritt war der falsche: eine Suche bringt nichts, wenn die Treffer
bereits da sind und nur unter der Schwelle liegen.

Das ist #813 woertlich ("389 Rohtreffer, 387 am Filter verworfen,
gemeldet wurde: alle 2 waren schon bekannt"), nur an der Trefferliste
statt am Suchlauf. Und es ist #989: eine unsichtbare Filterung sieht
aus wie ein leerer Markt.
"""
import importlib
import logging
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
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


def _stellen_anlegen(db, anzahl=8, score=3):
    db.save_jobs([{
        "hash": f"schwelle{i:04d}",
        "title": f"Consultant {i} (m/w/d)",
        "company": f"Musterwerk {i} GmbH",
        "location": "Hamburg", "score": score,
        "url": f"https://example.org/stelle/{i}",
        "source": "manuell",
        "description": "Eine ausfuehrliche Stellenbeschreibung. " * 8,
    } for i in range(anzahl)])


def _schwelle_setzen(db, wert):
    """Die Schwelle so setzen, wie die Anwendung sie kennt."""
    db.set_scoring_config("schwellenwert", "auto_ignore", wert)


def test_1008_ohne_schwelle_kommt_alles_durch(db):
    """Gegenprobe zuerst: ohne Schwelle darf nichts fehlen."""
    _stellen_anlegen(db, anzahl=8, score=3)
    antwort = _werkzeug(db, "stellen_anzeigen")()
    assert antwort["anzahl_gesamt"] == 8
    assert "durch_schwelle_verborgen" not in antwort


def test_1008_die_verborgenen_stellen_werden_gezaehlt(db):
    """Der Kern: die Zahl gehoert in die Antwort, nicht ins Log."""
    _stellen_anlegen(db, anzahl=8, score=3)
    _schwelle_setzen(db, 50)

    antwort = _werkzeug(db, "stellen_anzeigen")()
    assert antwort["anzahl"] == 0
    assert antwort["durch_schwelle_verborgen"] == 8


def test_1008_die_leere_liste_nennt_die_richtige_ursache(db):
    """Der teuerste Teil des Befunds.

    "Starte eine Jobsuche" ist der falsche naechste Schritt, wenn die
    Treffer bereits da sind und nur unter der Schwelle liegen. Eine
    Meldung, die die Ursache ausschliesst, ist schlimmer als keine
    (v1.7.36 MERKE 5).
    """
    _stellen_anlegen(db, anzahl=8, score=3)
    _schwelle_setzen(db, 50)

    antwort = _werkzeug(db, "stellen_anzeigen")()
    assert "Schwelle" in antwort["nachricht"]
    assert "Filter" in antwort["nachricht"]
    assert "jobsuche_starten" not in antwort["nachricht"]
    assert "scoring_konfigurieren" in antwort["naechster_schritt"]


def test_1008_bei_teilweiser_filterung_steht_der_hinweis_dabei(db):
    """Sonst sieht eine gefilterte Liste aus wie die ganze."""
    _stellen_anlegen(db, anzahl=4, score=3)
    db.save_jobs([{
        "hash": "schwelle_hoch", "title": "Senior Consultant (m/w/d)",
        "company": "Musterwerk Nord GmbH", "location": "Hamburg",
        "score": 90, "url": "https://example.org/stelle/hoch",
        "source": "manuell",
        "description": "Eine ausfuehrliche Stellenbeschreibung. " * 8,
    }])
    _schwelle_setzen(db, 50)

    antwort = _werkzeug(db, "stellen_anzeigen")()
    assert antwort["anzahl_gesamt"] == 1
    assert antwort["durch_schwelle_verborgen"] == 4
    assert "nicht aussortiert" in antwort["schwellen_hinweis"]


def test_1008_pbp_widerspricht_sich_nicht_mehr(db):
    """Die Diagnose zaehlt die Stellen, die Liste verschwieg sie.

    Genau diese Diskrepanz hat den Nutzer glauben lassen, die Anwendung
    sei defekt. Beide Wege muessen dieselbe Wirklichkeit beschreiben —
    die Liste darf filtern, aber sie muss es SAGEN.
    """
    _stellen_anlegen(db, anzahl=8, score=3)
    _schwelle_setzen(db, 50)

    aktiv_laut_db = len(db.get_active_jobs())
    antwort = _werkzeug(db, "stellen_anzeigen")()
    gesehen = (antwort.get("anzahl_gesamt", antwort.get("anzahl", 0))
               + antwort.get("durch_schwelle_verborgen", 0))
    assert gesehen == aktiv_laut_db, (
        f"Die Liste kennt {gesehen} Stellen, die Datenbank {aktiv_laut_db} — "
        "genau diese Luecke war der Befund.")


def test_1008_aussortierte_werden_nicht_zusaetzlich_gefiltert(db):
    """Die Schwelle gilt fuer die aktive Liste, nicht fuer das Archiv —
    sonst waere der Blick auf Aussortiertes doppelt gefiltert."""
    _stellen_anlegen(db, anzahl=3, score=3)
    for j in db.get_active_jobs():
        db.dismiss_job(j["hash"].split(":")[-1], "falsches_fachgebiet")
    _schwelle_setzen(db, 50)

    antwort = _werkzeug(db, "stellen_anzeigen")(filter="aussortiert")
    assert antwort["anzahl_gesamt"] == 3
    assert "durch_schwelle_verborgen" not in antwort


def test_1008_min_score_null_holt_die_verborgenen_nicht_zurueck(db):
    """Die Antwort behauptet das — also wird es geprueft.

    Ein Hinweis, der einen Weg ausschliesst, muss stimmen: sonst
    probiert der Leser ihn doch, bekommt wieder nichts und glaubt der
    ganzen Meldung nicht mehr (v1.7.36 MERKE 5).
    """
    _stellen_anlegen(db, anzahl=8, score=3)
    _schwelle_setzen(db, 50)

    antwort = _werkzeug(db, "stellen_anzeigen")(min_score=0)
    assert antwort["anzahl"] == 0
    assert antwort["durch_schwelle_verborgen"] == 8


def test_1008_der_genannte_weg_existiert_wirklich(db):
    """Guard gegen einen Prompt, den niemand kompiliert (#1000, #958).

    Der naechste Schritt nennt einen Aufruf samt Parameternamen. Steht
    dort ein Tippfehler oder wird der Parameter kuenftig umbenannt,
    laeuft der Leser ins Leere — und zwar genau in dem Moment, in dem er
    schon einmal nichts gefunden hat.
    """
    import inspect

    _stellen_anlegen(db, anzahl=3, score=3)
    _schwelle_setzen(db, 50)
    antwort = _werkzeug(db, "stellen_anzeigen")()
    text = antwort["naechster_schritt"]

    from bewerbungs_assistent.tools import analyse as analyse_tools

    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

        def prompt(self, *a, **kw):
            def deko(fn):
                return fn
            return deko

    analyse_tools.register(_Sammler(), db, logging.getLogger("test"))
    assert "scoring_konfigurieren" in gesammelt, \
        "Der genannte Weg fuehrt zu einem Werkzeug, das es nicht gibt."

    echte = set(inspect.signature(
        gesammelt["scoring_konfigurieren"]).parameters)
    genannt = set(re.findall(r"([a-z_]+)=", text)) - {"min_score"}
    assert genannt, "Der Hinweis nennt gar keinen Parameter — dann taugt er nichts."
    assert genannt <= echte, (
        f"Genannt, aber nicht vorhanden: {sorted(genannt - echte)}")
