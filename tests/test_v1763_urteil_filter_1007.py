"""Tests fuer v1.7.63 — #1007, letztes Akzeptanzkriterium.

*"Filter/Sortierung nach dem Urteil moeglich (mindestens: nur beurteilte
anzeigen)."*

v1.7.61 hat #1007 fast vollstaendig geliefert: Speicherung je Stelle,
Marke in beiden Listen, unterscheidbare Herkunft, Alter und
Veraltet-Kennzeichnung, `NICHT_BEURTEILBAR` statt eines aus dem Score
abgeleiteten Urteils, Rueckschreibweg fuer Claude. Der Filter fehlte —
und ein Issue mit sieben Kriterien, von denen sechs erfuellt sind, ist
nicht erledigt (DoD 8a).

Der neue Filter faellt selbst unter die Lehre aus #1008: er ist
abschaltbar, in der Vorgabe AUS, in der Hinweiszeile benannt, und er
sagt, wie viele Stellen er ausblendet.
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

JOBS_PAGE = _repo() / "frontend" / "src" / "pages" / "JobsPage.jsx"


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


def _stellen_anlegen(db, anzahl=5):
    db.save_jobs([{
        "hash": f"urteil{i:04d}",
        "title": f"Consultant {i} (m/w/d)",
        "company": f"Musterwerk {i} GmbH",
        "location": "Hamburg", "score": 20,
        "url": f"https://example.org/stelle/{i}",
        "source": "manuell",
        "description": "Eine ausfuehrliche Stellenbeschreibung. " * 8,
    } for i in range(anzahl)])


def _beurteilen(db, hash_, urteil="EMPFOHLEN"):
    voll = next(j["hash"] for j in db.get_active_jobs()
                if j["hash"].endswith(hash_))
    db.set_job_analysis(voll, urteil=urteil,
                        begruendung="Profil deckt die Kernaufgaben.",
                        grundlage="detailanalyse")


def test_1007_ohne_filter_kommt_alles_durch(db):
    """Gegenprobe zuerst: die Vorgabe filtert nichts."""
    _stellen_anlegen(db, 5)
    _beurteilen(db, "urteil0000")
    antwort = _werkzeug(db, "stellen_anzeigen")()
    assert antwort["anzahl_gesamt"] == 5
    assert "ohne_urteil_verborgen" not in antwort


def test_1007_nur_beurteilte_zeigt_nur_gelesene(db):
    """Das Akzeptanzkriterium selbst."""
    _stellen_anlegen(db, 5)
    _beurteilen(db, "urteil0000")
    _beurteilen(db, "urteil0001", urteil="NICHT_EMPFOHLEN")

    antwort = _werkzeug(db, "stellen_anzeigen")(nur_beurteilt=True)
    assert antwort["anzahl_gesamt"] == 2
    assert antwort["ohne_urteil_verborgen"] == 3
    assert all(s.get("analyse", {}).get("urteil") for s in antwort["stellen"])


def test_1007_der_filter_sagt_was_er_ausblendet(db):
    """Die Lehre aus #1008 gilt auch fuer den NEUEN Filter.

    Ein Filter, der stillschweigend unterdrueckt, erzeugt denselben
    Eindruck eines leeren Bestands — egal wie sinnvoll er ist.
    """
    _stellen_anlegen(db, 4)
    antwort = _werkzeug(db, "stellen_anzeigen")(nur_beurteilt=True)
    assert antwort["anzahl"] == 0
    assert antwort["ohne_urteil_verborgen"] == 4
    assert "Filter" in antwort["nachricht"]
    assert "stelle_analyse_speichern" in antwort["naechster_schritt"]


def test_1007_der_hinweis_nennt_den_weg_zurueck(db):
    """Ein Befund ohne Weg nach vorn ist die Haelfte wert."""
    _stellen_anlegen(db, 3)
    _beurteilen(db, "urteil0000")
    antwort = _werkzeug(db, "stellen_anzeigen")(nur_beurteilt=True)
    assert "nicht aussortiert" in antwort["urteils_hinweis"]
    assert "ungeprueft" in antwort["urteils_hinweis"]


def test_1007_frontend_hat_den_schalter_und_nennt_ihn(db):
    """Ein Filter ohne Bedienelement waere der Fehler aus #1008.

    Nachgezogen mit #948: der Schalter war ein Ja/Nein-Feld
    (`onlyAnalysed`) und heisst jetzt `pruefstand` mit drei Werten —
    die Gegenrichtung "zeig mir, was ich noch nicht angesehen habe"
    war vorher gar nicht erreichbar. Die vier Zusicherungen von #1007
    gelten unveraendert weiter und stehen hier gegen das neue Feld;
    geaendert hat sich der Mechanismus, nicht die Anforderung.
    """
    quelltext = JOBS_PAGE.read_text(encoding="utf-8")
    block = re.search(r"export const FILTER_STANDARD = \{[^}]*\}", quelltext)
    assert 'pruefstand: ""' in block.group(0), \
        "Vorgabe AUS — sonst filtert wieder etwas, das niemand gesetzt hat."
    assert "Nur beurteilte" in quelltext, "Der Schalter fehlt."
    assert 'schluessel: "pruefstand"' in quelltext, \
        "Der Filter muss in der Hinweiszeile ueber der Liste auftauchen."
    # Gefiltert wird weiterhin nach dem URTEIL — die Einteilung kommt
    # seit #948 vom Server, damit es sie nicht zweimal gibt.
    assert "job.pruefstand?.art" in quelltext
    assert '"beurteilt"' in quelltext
