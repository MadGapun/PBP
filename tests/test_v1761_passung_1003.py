"""Tests fuer v1.7.61 — #1003 und #1007: der Verdict kommt nicht aus dem Score.

Nutzer-Korrektur vom 09.09.2026:

    "Ob es eine Empfehlung gibt, hat nichts mit den Punkten, nichts mit
    dem Score zu tun — das ist nur ein Indikator fuer die Suchbegriffe.
    Ob es eine Empfehlung gibt oder nicht, entsteht erst durch die
    Fit-Analyse bzw. durch die Detailanalyse, die den Lebenslauf mit der
    Stelle vergleicht — und nicht irgendwelche Punkte."

Bis v1.7.60 bildete `_build_empfehlung` den Verdict aus
`total_score / total_score_max`. In diese Zahl gehen Keyword-Treffer,
Gehalt, Entfernung und Remote-Grad ein. **Der Lebenslauf geht nicht
ein.**

## Warum hier keine Schwellen getestet werden

Weil es keine mehr gibt. Der naheliegende Ausweg waere ein besserer
MASSSTAB gewesen (Verteilung des Bestands, hoechster bisher erreichter
Wert) — ich hatte die Verteilung selbst vorgeschlagen. Das haette
denselben Fehler nur sauberer gemacht.

`services/passung.py` rechnet deshalb gar nicht. Es entscheidet nach
Sachverhalten: k.o. vorhanden, gelesene Analyse vorhanden, sonst
`NICHT_BEURTEILBAR`.

## Die vierte Kategorie tut jetzt echte Arbeit

Seit #999 gab es `NICHT_BEURTEILBAR` als Notausgang fuer einen
fehlenden Hoechstwert. Jetzt sagt sie, was sie sagt: **niemand hat diese
Stelle gegen dein Profil gelesen.** Das ist etwas anderes als "passt
nicht" — genau die Verwechslung, die #989 abgeschafft hat.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import passung  # noqa: E402


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
    for _s in ({"name": "Datenmigration", "category": "fachlich"},
               {"name": "Projektleitung", "category": "methodisch"}):
        datenbank.add_skill(_s)
    datenbank.save_jobs([{
        "hash": "analyse0001", "title": "Consultant (m/w/d)",
        "company": "Musterwerk GmbH", "location": "Hamburg", "score": 84,
        "url": "https://example.org/stelle/1", "source": "manuell",
        "description": "Eine ausfuehrliche Stellenbeschreibung. " * 8,
    }])
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt


def _hash(db):
    return [j["hash"].split(":")[-1] for j in db.get_active_jobs()][0]


# -- Der Kern: kein Score erzeugt ein Urteil --------------------------

@pytest.mark.parametrize("score,maximum", [
    (388.5, 388.5), (100, 100), (84, 388.5), (15, 15), (0, 100),
])
def test_1003_kein_score_erzeugt_ein_urteil(score, maximum):
    """Die Umkehr des alten Vertrags, als Wache gegen den Rueckfall.

    Vorher galt: Anteil >= 75 % -> EMPFOHLEN. Ein Volltreffer auf die
    Suchbegriffe ist aber keine Aussage darueber, ob der Mensch passt.
    """
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    v = _build_empfehlung(
        {"total_score": score, "total_score_max": maximum,
         "muss_hits": ["a", "b"], "missing_muss": [], "risks": [],
         "beschreibung_vorhanden": True},
        {}, profil_kompetenzen=20)
    assert v["kategorie"] == "NICHT_BEURTEILBAR"
    assert v["grundlage"] == "keine_grundlage"


def test_1003_der_score_steht_daneben_und_sagt_was_er_misst():
    """Er verschwindet nicht — er wird nur richtig benannt."""
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    v = _build_empfehlung(
        {"total_score": 84, "total_score_max": 388.5, "muss_hits": ["a"],
         "missing_muss": ["b"], "risks": [], "beschreibung_vorhanden": True},
        {}, profil_kompetenzen=20)
    assert v["score"] == 84
    assert "SUCHBEGRIFFE" in v["score_bedeutung"]
    assert v["muss_treffer"] == 1 and v["muss_gesamt"] == 2


def test_1003_die_schwellen_stehen_nicht_mehr_im_code():
    """Guard gegen den bequemen Rueckfall.

    Die alten Grenzen (0.75 / 0.50 auf den Score-Anteil) waren zwei
    Zeilen. Sie wieder einzufuegen waere in fuenf Minuten getan — und
    niemandem faellt es auf, weil der Verdict danach wieder ploetzlich
    "funktioniert".
    """
    import re
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "tools"
              / "jobs.py").read_text(encoding="utf-8-sig")
    ohne_kommentare = "\n".join(
        z for z in quelle.split("\n") if not z.strip().startswith("#"))
    assert not re.search(r"anteil\s*>=", ohne_kommentare)


# -- Woher der Verdict jetzt kommt ------------------------------------

def test_1003_ein_ko_schlaegt_alles():
    """Wer eine Firma dreimal aus fachlichem Grund aussortiert hat, will
    beim vierten Mal keine Empfehlung lesen (#671)."""
    befund = passung.urteil(
        ko_gruende=["Wiedergaenger: dreimal fachlich aussortiert"],
        gespeicherte_analyse={"urteil": "EMPFOHLEN", "begruendung": "passt"})
    assert befund["kategorie"] == "NICHT_EMPFOHLEN"
    assert befund["grundlage"] == "ko_kriterium"
    assert befund["ko_gruende"]


def test_1003_die_gelesene_analyse_gilt():
    befund = passung.urteil(
        profil_kompetenzen=12,
        gespeicherte_analyse={
            "urteil": "BEDINGT", "begruendung": "Methodenluecke.",
            "grundlage": "detailanalyse", "am": "2026-09-09T10:00:00"})
    assert befund["kategorie"] == "BEDINGT"
    assert befund["grundlage"] == "detailanalyse"


@pytest.mark.parametrize("lage,erwartet", [
    ({"beschreibung_vorhanden": False, "profil_kompetenzen": 12},
     "keine_beschreibung"),
    ({"beschreibung_vorhanden": True, "profil_kompetenzen": 0},
     "kein_profil"),
    ({"beschreibung_vorhanden": True, "profil_kompetenzen": 12},
     "nicht_gelesen"),
])
def test_1003_drei_gruende_nicht_zu_urteilen(lage, erwartet):
    """Drei Sachverhalte, drei naechste Schritte.

    Sie zu einem "nicht beurteilbar" zu verschmelzen waere #989 in neuer
    Gestalt — der Mensch wuesste nicht, was er tun soll.
    """
    befund = passung.urteil(**lage)
    assert befund["kategorie"] == "NICHT_BEURTEILBAR"
    assert befund["warum"] == erwartet
    assert befund["begruendung"].strip()


def test_1003_ein_erfundenes_urteil_wird_ignoriert():
    """Ein Wert ausserhalb der vier Kategorien darf nicht durchrutschen."""
    befund = passung.urteil(
        profil_kompetenzen=12,
        gespeicherte_analyse={"urteil": "VIELLEICHT", "begruendung": "x"})
    assert befund["kategorie"] == "NICHT_BEURTEILBAR"


# -- #1007: der Befund haengt an der Stelle ---------------------------

def test_1007_urteil_wird_gespeichert_und_gelesen(db):
    h = _hash(db)
    assert db.set_job_analysis(
        h, "EMPFOHLEN", "Werdegang deckt die Rolle ab.") is True
    job = db.get_job(h)
    befund = passung.analyse_lesen(job, db.get_profile())
    assert befund["urteil"] == "EMPFOHLEN"
    assert "Werdegang" in befund["begruendung"]
    assert befund["am"]
    assert befund.get("veraltet") is None


def test_1007_ein_erfundenes_urteil_wird_abgewiesen(db):
    """Hier gibt es kein sinnvolles "sonstiges".

    Ein still umgedeutetes Urteil waere schlimmer als gar keines — das
    ist #980, wo ein Fallback "hinfaellig" als "erledigt" speicherte.
    """
    with pytest.raises(ValueError):
        db.set_job_analysis(_hash(db), "VIELLEICHT", "x")
    assert db.get_job(_hash(db)).get("analyse_urteil") in (None, "")


def test_1007_unbekannte_stelle_meldet_false(db):
    """Der Aufrufer darf nicht "gespeichert" melden, wo nichts
    gespeichert wurde (#997)."""
    assert db.set_job_analysis("gibtesnicht", "EMPFOHLEN", "x") is False


def test_1007_profilaenderung_kennzeichnet_den_befund_als_ueberholt(db):
    """Nicht verwerfen, sondern benennen.

    Das Urteil war zu seiner Zeit richtig; es still wegzuwerfen verloere
    die teuerste Auskunft im System.
    """
    h = _hash(db)
    db.set_job_analysis(h, "EMPFOHLEN", "passt")
    # Kompetenzen liegen in einer eigenen Tabelle — `save_profile`
    # nimmt sie nicht entgegen. Beim Schreiben dieses Tests aufgefallen.
    db.add_skill({"name": "Neue Kompetenz", "category": "fachlich"})

    befund = passung.analyse_lesen(db.get_job(h), db.get_profile())
    assert befund["veraltet"] is True
    verdikt = passung.urteil(profil_kompetenzen=3,
                             gespeicherte_analyse=befund)
    assert verdikt["kategorie"] == "EMPFOHLEN"     # bleibt gueltig
    assert verdikt["veraltet"] is True
    assert verdikt["hinweis"].strip()


def test_1007_befund_laesst_sich_loeschen(db):
    h = _hash(db)
    db.set_job_analysis(h, "NICHT_EMPFOHLEN", "Gap")
    assert db.clear_job_analysis(h) is True
    assert passung.analyse_lesen(db.get_job(h), db.get_profile()) is None


# -- Der Befund kommt in BEIDEN Listen an -----------------------------

def _werkzeug(db, name):
    import logging
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


def test_1007_mcp_werkzeug_speichert_und_loescht(db):
    h = _hash(db)
    speichern = _werkzeug(db, "stelle_analyse_speichern")
    antwort = speichern(h, "bedingt", "Methodenluecke, ueberbrueckbar.")
    assert antwort["status"] == "gespeichert"
    assert antwort["urteil"] == "BEDINGT"

    assert "fehler" in speichern(h, "vielleicht", "x")
    assert "fehler" in speichern("gibtesnicht", "EMPFOHLEN", "x")

    assert _werkzeug(db, "stelle_analyse_loeschen")(h)["status"] == "geloescht"


def test_1007_der_befund_steht_in_der_trefferliste(db):
    """Ein Befund, den nur ein Werkzeug kennt, ist kein Befund (#989)."""
    h = _hash(db)
    db.set_job_analysis(h, "EMPFOHLEN", "Werdegang passt.")
    liste = _werkzeug(db, "stellen_anzeigen")()
    eintrag = liste["stellen"][0]
    assert eintrag["analyse"]["urteil"] == "EMPFOHLEN"


def test_1007_ohne_befund_steht_nichts_in_der_liste(db):
    """"Noch nicht gelesen" ist kein Urteil und bekommt keine Marke."""
    liste = _werkzeug(db, "stellen_anzeigen")()
    assert "analyse" not in liste["stellen"][0]


def test_1007_rest_und_mcp_zeigen_denselben_befund(db):
    """Zwei Fassungen desselben Befunds waeren #963/#991 in der
    Trefferliste. Ein Test haelt beide Aufrufer fest."""
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    h = _hash(db)
    db.set_job_analysis(h, "NICHT_EMPFOHLEN", "Fachgebiet passt nicht.")
    dash._db = db
    with TestClient(dash.app) as klient:
        rest = klient.get("/api/jobs").json()
    eintraege = rest.get("jobs", rest) if isinstance(rest, dict) else rest
    aus_rest = [j for j in eintraege if j.get("analyse")]
    assert aus_rest, "Der Befund fehlt in GET /api/jobs"
    assert aus_rest[0]["analyse"]["urteil"] == "NICHT_EMPFOHLEN"

    aus_mcp = _werkzeug(db, "stellen_anzeigen")()["stellen"][0]
    assert aus_mcp["analyse"]["urteil"] == aus_rest[0]["analyse"]["urteil"]


def test_1007_die_marke_steht_im_stellen_tab():
    quelle = (_repo() / "frontend" / "src" / "pages"
              / "JobsPage.jsx").read_text(encoding="utf-8")
    assert "job.analyse?.urteil" in quelle
    assert "ANALYSE_ETIKETT" in quelle
