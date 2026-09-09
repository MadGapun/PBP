"""Tests fuer v1.7.62 — #1008 Befund 1, 2 und 3.

Nutzer-Report vom 09.09.2026, mit Screenshot. Die Sidebar zaehlt acht
Stellen, die Liste zeigt eine, F5 und Strg+F5 aendern nichts. Der Melder
haelt die Anwendung fuer defekt. Sie ist es nicht — sie filtert und sagt
es nicht.

**Befund 1** — die Kennzahl-Karte trug die Ueberschrift "AKTIVE STELLEN"
ueber der Zahl der ANGEZEIGTEN Stellen und zwei Zeilen darunter die
Notiz "8 aktiv gesamt, 7 durch Filter verborgen". Die Karte widersprach
sich selbst und liess den (korrekten) Sidebar-Zaehler falsch aussehen.

Die Ursache lag tiefer und ist unangenehm: der Score-Filter der Liste
bezog seinen Vorgabewert aus `search_criteria.min_score_schwelle` — laut
PBPs eigener Beschreibung die Schwelle, ab der eine Stelle beim Suchlauf
ueberhaupt GESPEICHERT wird, ausdruecklich "wirkt waehrend der Suche,
nicht in der Liste". Der Anzeige-Filter heisst `schwellenwert/
auto_ignore` und wirkt serverseitig. Bis v1.7.50 lief der Zugriff
lautlos ins Leere; **#993 hat ihn repariert und damit einen seit
beta.27 schlafenden Filter scharfgeschaltet** — ohne Zutun des Nutzers,
und ein Neuladen half nicht, weil der Wert bei jedem Start neu aus den
Kriterien kam. Das ist die Bauform aus #980: eine Einstellung, die etwas
anderes bedeutet als sie sagt.

**Befund 2** — vier Werte fuer denselben Score. `save_jobs` behaelt beim
erneuten Speichern den hoeheren ALTEN `score`, schrieb `fachscore` und
`rahmenscore` aber bedingungslos neu. Danach stand die Aufteilung des
einen Laufs neben dem Gesamtwert eines anderen. Nachgestellt und
bestaetigt.

**Befund 3** — wirkungslose Regler liegen wie echte Einstellungen im
Bestand. `hochschulabschluss/fehlt` stand sogar in JEDER frischen
Datenbank, obwohl die Pruefung dahinter in v1.7.35 (#972) ersatzlos
entfernt wurde.
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


def ohne_kommentare(text: str) -> str:
    """Kommentare raus.

    Sonst prueft ein Quelltext-Guard die Erklaerung mit, warum etwas
    nicht mehr dasteht — und schlaegt an ihr an. Dritter Fall nach #993,
    #998 und v1.7.31 MERKE (6); diesmal von vornherein bedacht, weil die
    Begruendung den verbotenen Ausdruck nennen MUSS.
    """
    ohne_block = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return "\n".join(
        re.sub(r"(^|\s)//.*$", "", z) for z in ohne_block.split("\n"))


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


def _werkzeuge(db, modul):
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

    modul.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt


# -- Befund 1: der unsichtbare Filter ---------------------------------

def test_1008_anzeigefilter_startet_ungefiltert():
    """Die Vorgabe filtert nichts. Wer filtern will, sagt es."""
    quelltext = JOBS_PAGE.read_text(encoding="utf-8")
    block = re.search(r"export const FILTER_STANDARD = \{[^}]*\}", quelltext)
    assert block, "FILTER_STANDARD fehlt — die Filter-Vorgabe braucht EINEN Ort."
    assert 'minScore: "0"' in block.group(0)
    assert "hideApplied: true" in block.group(0), \
        "Bestehendes Verhalten unveraendert lassen — nur der Score war der Fund."


def test_1008_die_speicherschwelle_ist_kein_anzeigefilter():
    """Der Kern von Befund 1.

    `min_score_schwelle` wirkt waehrend der SUCHE. Sie als Vorgabe des
    Anzeige-Filters zu nehmen, ist eine stille Zweckentfremdung — und
    genau sie hat sieben von acht Stellen unsichtbar gemacht, ohne dass
    der Nutzer je einen Filter gesetzt haette.
    """
    quelltext = ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    assert "min_score_schwelle" not in quelltext, (
        "Die Speicher-Schwelle darf die Anzeige nicht filtern. Der "
        "Anzeige-Filter heisst schwellenwert/auto_ignore und wirkt "
        "serverseitig.")


def test_1008_die_karte_benennt_was_sie_zeigt():
    """AK 1: Ueberschrift und Zahl meinen dieselbe Groesse."""
    quelltext = JOBS_PAGE.read_text(encoding="utf-8")
    stelle = quelltext.index("value={filteredJobs.length}")
    davor = quelltext[max(0, stelle - 1200):stelle]
    assert "Angezeigte Stellen" in davor, (
        "Steht die Zahl der angezeigten Stellen da, darf die Ueberschrift "
        "nicht 'Aktive Stellen' versprechen.")
    assert "verborgeneStellen > 0" in davor


def test_1008_hinweis_steht_ueber_der_liste_und_ist_aufhebbar():
    """AK 2 und 3 zusammen.

    Der Melder hat mehrfach neu geladen. Ein Hinweis in einer Kennzahl
    NEBEN der Liste hat ihn nicht erreicht — er gehoert darueber, mit
    dem Weg zurueck in Reichweite.
    """
    quelltext = JOBS_PAGE.read_text(encoding="utf-8")
    hinweis = quelltext.index("durch aktive Filter verborgen")
    liste = quelltext.index("filteredJobs.map((job) => (")
    assert hinweis < liste, "Der Hinweis gehoert VOR die Liste, nicht dahinter."
    assert "Filter aufheben" in quelltext[hinweis:liste]


def test_1008_die_verborgenen_werden_gegen_das_geladene_gezaehlt():
    """Eine zu hohe Zahl ist so irrefuehrend wie eine fehlende.

    Gegen `jobsTotal` gerechnet wuerden bei aktivem Nachladen die noch
    gar nicht geholten Seiten als "durch Filter verborgen" gelten.
    """
    quelltext = JOBS_PAGE.read_text(encoding="utf-8")
    zeile = next(z for z in quelltext.split("\n")
                 if z.strip().startswith("const verborgeneStellen"))
    assert "currentList.length - filteredJobs.length" in zeile
    assert "jobsTotal" not in zeile


def test_1008_zuruecksetzen_und_hinweis_lesen_dieselbe_vorgabe():
    """Ein Kommentar haelt nichts zusammen (#963, #991, #992).

    Zwei Fassungen der Zuruecksetz-Form waeren beim naechsten neuen
    Filter auseinandergelaufen — und der Knopf haette ihn stehen
    gelassen, ohne dass es auffiele.
    """
    quelltext = ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    assert quelltext.count("...FILTER_STANDARD") >= 2, (
        "Zuruecksetzen-Knopf und Hinweis muessen dieselbe Definition lesen.")
    assert quelltext.count('minScore: "0"') == 1, (
        "Die Vorgabe steht genau einmal da.")


# -- Befund 2: ein Score, eine Aufteilung -----------------------------

def _krit():
    return {"keywords_muss": ["plm"], "keywords_plus": ["remote"],
            "gewichtung": {"muss": 7, "plus": 3}}


def _bewerten_und_speichern(db, hash_, beschreibung, remote=None):
    from bewerbungs_assistent.job_scraper import calculate_score
    job = {"hash": hash_, "title": "Consultant", "company": "Musterwerk GmbH",
           "location": "Hamburg", "url": f"https://example.org/{hash_}",
           "source": "manuell", "description": beschreibung}
    if remote:
        job["remote_level"] = remote
    job["score"] = calculate_score(job, _krit())
    db.save_jobs([job])
    return job


def _gespeichert(db, hash_):
    return [j for j in db.get_active_jobs() if j["hash"].endswith(hash_)][0]


def test_1008_teilscores_beschreiben_den_gespeicherten_wert(db):
    """AK 5: die Beziehung wird festgeschrieben.

    Nachgestellt aus dem Bericht: erst ein voller Anzeigentext, dann
    derselbe Hash mit duennem Text. `save_jobs` behaelt den hoeheren
    alten Gesamtwert — die Aufteilung muss ihm folgen, sonst steht die
    Summe des einen Laufs neben dem Wert des anderen. Genau so entstand
    das gemeldete "score 10.0 bei fachscore 0.0 und rahmenscore 0.0".
    """
    _bewerten_und_speichern(db, "teil1", "PLM PLM PLM remote " * 5, "remote")
    vorher = _gespeichert(db, "teil1")
    _bewerten_und_speichern(db, "teil1", "Eine Rolle ohne Fachbegriffe.")
    nachher = _gespeichert(db, "teil1")

    assert nachher["score"] == vorher["score"], \
        "Der hoehere Wert bleibt — das ist gewolltes Verhalten."
    summe = round((nachher["fachscore"] or 0) + (nachher["rahmenscore"] or 0), 1)
    assert abs(summe - nachher["score"]) < 0.05, (
        f"score={nachher['score']} aber fachscore+rahmenscore={summe} — "
        "zwei Laeufe in einer Zeile.")


def test_1008_metadaten_update_loescht_die_aufteilung_nicht(db):
    """Vom eigenen Test gefunden.

    Ein Nachladen der Beschreibung geht ohne Bewertung durch `save_jobs`.
    Wuerde die Aufteilung dabei auf NULL fallen, staende ein Gesamtwert
    ohne jede Herkunft da — "nicht bewertet" waere dann eine
    Falschaussage.
    """
    _bewerten_und_speichern(db, "teil2", "PLM PLM remote " * 5, "remote")
    db.save_jobs([{
        "hash": "teil2", "title": "Consultant (m/w/d)",
        "company": "Musterwerk GmbH", "location": "Hamburg",
        "url": "https://example.org/teil2", "source": "manuell",
        "description": "PLM PLM remote " * 5,
    }])
    row = _gespeichert(db, "teil2")
    assert row["fachscore"] is not None and row["rahmenscore"] is not None
    summe = round(row["fachscore"] + row["rahmenscore"], 1)
    assert abs(summe - row["score"]) < 0.05


def test_1008_liste_und_fit_analyse_nennen_denselben_score(db):
    """AK 4: derselbe Wert auf beiden Wegen.

    Die Liste zeigt den GESPEICHERTEN Wert, die Fit-Analyse rechnet neu.
    Bei unveraenderten Kriterien und unveraendertem Text muessen beide
    dasselbe sagen — weicht es ab, ist eine der beiden Rechnungen eine
    andere (#963/#987).
    """
    from bewerbungs_assistent.tools import jobs as job_tools
    db.set_search_criteria("keywords_muss", ["plm"])
    db.set_search_criteria("keywords_plus", ["remote"])
    db.set_search_criteria("gewichtung", {"muss": 7, "plus": 3})
    _bewerten_und_speichern(db, "teil3", "PLM PLM PLM remote " * 5, "remote")

    werkzeuge = _werkzeuge(db, job_tools)
    row = _gespeichert(db, "teil3")
    liste = werkzeuge["stellen_anzeigen"]()
    # Der Titel traegt eine Datenguete-Marke (#989) — deshalb `in`.
    eintrag = next(s for s in liste["stellen"] if "Consultant" in s["titel"])
    rest = db._mit_scoring_reglern(db.get_active_jobs(), sortieren=False)
    rest_wert = next(j["score"] for j in rest if j["hash"].endswith("teil3"))
    assert eintrag["score"] == rest_wert, (
        f"MCP-Liste {eintrag['score']} gegen Oberflaeche {rest_wert} — "
        "derselbe Feldname, zwei Bedeutungen.")

    fit = werkzeuge["fit_analyse"](job_hash=row["hash"].split(":")[-1])
    # Die Fit-Analyse rechnet den FACHWERT; die Liste zeigt ihn samt
    # Reglern. Beide gleichzumachen wuerde die 100-Prozent-Eigenschaft
    # aus #999 brechen — also muss die Analyse den Listenwert BENENNEN.
    in_liste = fit.get("score_in_liste", fit["total_score"])
    assert abs(in_liste - eintrag["score"]) < 0.05, (
        f"Liste {eintrag['score']} gegen Fit-Analyse {in_liste} — "
        "zwei Rechenwege fuer dieselbe Zahl.")
    if "score_in_liste" in fit:
        assert "Regler" in fit["score_hinweis"], \
            "Weicht die Zahl ab, muss dastehen WARUM."


# -- Befund 3: Regler ohne Wirkung ------------------------------------

def test_1008_frische_datenbank_traegt_keinen_toten_regler(db):
    """Der Melder fand `hochschulabschluss/fehlt` im Bestand.

    Es war kein Bestandsproblem: der Regler wurde in JEDE frische
    Datenbank geschrieben, obwohl seine Pruefung in v1.7.35 (#972)
    ersatzlos entfernt wurde. Ein Warnhinweis daraufhin haette JEDEN
    Anwender beim ersten Start getroffen — und ein Pruefer, der bei
    korrektem Zustand Alarm gibt, wird ignoriert (#929).
    """
    tote = [c for c in (db.get_scoring_config() or [])
            if c.get("dimension") == "hochschulabschluss"]
    assert tote == [], f"Toter Regler in frischer DB: {tote}"


def test_1008_unbekannter_sub_key_wird_beim_setzen_abgewiesen(db):
    """Seit v1.7.36 (#988) richtig — hier als Rueckfall-Schutz.

    Genau so entstand der gemeldete Wert 35: jemand wollte eine Schwelle
    setzen und erwischte den falschen sub_key. Angenommen, ohne Wirkung,
    ohne Fehlermeldung.
    """
    from bewerbungs_assistent.tools import analyse as analyse_tools
    werkzeuge = _werkzeuge(db, analyse_tools)
    antwort = werkzeuge["scoring_konfigurieren"](
        aktion="setzen", dimension="schwellenwert",
        sub_key="schwellenwert", wert=35)
    assert "fehler" in antwort
    assert "auto_ignore" in antwort["fehler"], \
        "Die Absage muss den richtigen Regler nennen, nicht nur ablehnen."
    assert not [c for c in (db.get_scoring_config() or [])
                if c.get("sub_key") == "schwellenwert"]


def test_1008_diagnose_meldet_wirkungslose_regler(db):
    """AK aus dem Kommentar: gemeldet, nicht nur beim Anzeigen bemaengelt.

    Sichtbar war der tote Regler bisher nur, wer `scoring_konfigurieren
    ('anzeigen')` aufrief. Die Diagnose — der Weg, den man bei einem
    Verdacht geht — schwieg.
    """
    from bewerbungs_assistent.tools import analyse as analyse_tools
    db.set_scoring_config("schwellenwert", "schwellenwert", 35)

    befund = _werkzeuge(db, analyse_tools)["pbp_diagnose"]()
    treffer = [w for w in befund.get("warnungen", [])
               if w.get("bereich") == "Scoring"]
    assert treffer, "Die Diagnose muss den wirkungslosen Regler nennen."
    assert "schwellenwert/schwellenwert" in treffer[0]["meldung"]
    assert "auto_ignore" in treffer[0]["empfehlung"], \
        "Ein Befund ohne Weg nach vorn ist die Haelfte wert."


def test_1008_die_diagnose_schweigt_ohne_tote_regler(db):
    """Die Gegenrichtung — und die wichtigere.

    Ein Alarm, der bei korrektem Zustand kommt, wird nach dem zweiten
    Mal ignoriert (#929, DoD 9).
    """
    from bewerbungs_assistent.tools import analyse as analyse_tools
    befund = _werkzeuge(db, analyse_tools)["pbp_diagnose"]()
    treffer = [w for w in befund.get("warnungen", [])
               if w.get("bereich") == "Scoring"]
    assert treffer == [], f"Fehlalarm auf sauberem Bestand: {treffer}"


def test_1008_kein_wert_ohne_leser_mehr(db):
    """Der Hochschulabschluss-Malus wurde geschrieben und nie gelesen.

    Dieselbe Bauform wie das `chrome`-Feld (#993) und die beiden Regler
    ohne Draht (#1000), diesmal in den Scoring-Kriterien.
    """
    treffer = []
    for pfad in (_repo() / "src").rglob("*.py"):
        text = pfad.read_text(encoding="utf-8", errors="replace")
        for nr, zeile in enumerate(text.split("\n"), 1):
            nackt = zeile.split("#")[0]
            if "_hochschulabschluss_malus" in nackt:
                treffer.append(f"{pfad.name}:{nr}")
    assert treffer == [], f"Wert ohne Leser lebt weiter: {treffer}"
