"""Tests fuer #1052 Schritt 2 — die Daumen in der Liste, die der Mensch ansieht.

Die Bausteine (Fachwert, Rahmen, Neigung) stehen seit
`test_v17117_fachwert_rahmen_1052.py`. Hier geht es um das, was #989 in
einem Satz sagt: **ein Befund, den nur ein Werkzeug kennt, ist kein
Befund.** Beide Daumen muessen an der Liste ankommen — an der im Chat
UND an der im Stellen-Tab —, und sie muessen aus DERSELBEN Rechnung
kommen. Zwei Fassungen waeren #1008 noch einmal: dort trug derselbe
Feldname in beiden Wegen verschiedene Zahlen.

Dazu der Filter "Rahmen passt nicht ausblenden". Seine Vorgabe ist AN
(Nutzerantwort 15.09.2026) — die Ausnahme von der Lehre aus #1008, und
deshalb gilt deren zweiter Teil hier strenger: er nennt seine Zahl, und
er blendet nur aus, was BELEGT nicht passt.

Alle Firmen und Orte sind Platzhalter.
"""
import asyncio
import importlib
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

JOBS_PAGE = _repo() / "frontend" / "src" / "pages" / "JobsPage.jsx"


def _ohne_kommentare(text: str) -> str:
    """Ein Guard darf nicht an der Begruendung anschlagen, warum etwas
    verboten ist (v1.7.50 MERKE 2)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(
        z for z in text.split("\n") if not z.lstrip().startswith("//"))


# ══ Das Nadeloehr ═══════════════════════════════════════════════════

def _krit():
    return {"keywords_muss": ["Stammdaten"],
            "max_entfernung": {"festanstellung": 50},
            "min_gehalt": 60000}


def _stelle(**extra):
    job = {"hash": "x1", "title": "Stammdaten Migration",
           "company": "Musterfirma GmbH", "location": "Musterstadt",
           "description": "Stammdaten und Migration. " * 10,
           "employment_type": "festanstellung",
           "distance_km": 12.0, "salary_min": 75000,
           "salary_type": "jaehrlich", "salary_estimated": 0,
           "score": 12.0}
    job.update(extra)
    return job


class _DB:
    """Ein Bestand mit genug Bewerbungen, damit die Schwellen tragen."""

    def __init__(self, werte=None):
        from bewerbungs_assistent.services import fachwert
        self._werte = list(werte if werte is not None
                           else range(10, 10 + fachwert.MIN_BEWERBUNGEN))

    def get_applications(self):
        return [{"job_hash": f"h{i}"} for i in range(len(self._werte))]

    def get_job(self, h):
        return {"score": self._werte[int(str(h)[1:])]}

    def get_dismissed_jobs(self):
        return []

    def get_search_criteria(self):
        return _krit()


def test_beide_daumen_kommen_aus_einem_kontext():
    """Die Schwellen entstehen aus der ganzen Bewerbungshistorie.

    Sie je Zeile neu zu rechnen hiesse, den Bestand einmal pro Stelle zu
    lesen — dieselbe Bauform wie die Synonyme in #987 und die Datenguete
    in #989: einmal vorbereiten, dann anwenden.
    """
    from bewerbungs_assistent.services import indikatoren

    ktx = indikatoren.kontext(_DB(), _krit())
    assert ktx["schwellen"].get("trennschwelle") is not None
    assert ktx["fach_maximum"] > 0

    befund = indikatoren.fuer_stelle(_stelle(), ktx)
    assert befund["fach"]["richtung"] in ("hoch", "mittel", "runter")
    assert befund["rahmen"]["richtung"] in ("hoch", "mittel", "runter")
    assert befund["fach_maximum"] == ktx["fach_maximum"]


def test_ohne_anzeigentext_bleibt_der_fachdaumen_grau():
    """Ein Fachwert aus dem Titel ist nicht falsch, er ist ungeprueft.

    Genau diese Unterscheidung traegt die FARBE — die Richtung bleibt
    sichtbar (#756, #989).
    """
    from bewerbungs_assistent.services import fachwert, indikatoren

    ktx = indikatoren.kontext(_DB(), _krit())
    mit = indikatoren.fuer_stelle(_stelle(), ktx)["fach"]
    ohne = indikatoren.fuer_stelle(_stelle(description="kurz"), ktx)["fach"]
    assert mit["farbe"] == fachwert.BELEGT
    assert ohne["farbe"] == fachwert.GRAU
    # Und die Richtung ist dieselbe — grau ist eine zweite Angabe, keine
    # Abwertung.
    assert mit["richtung"] == ohne["richtung"]


def test_die_daumen_stehen_nebeneinander_und_werden_nie_addiert():
    """Das erste Akzeptanzkriterium des Issues.

    Der Anlass war eine Zahl, in der beides steckte: 400 km zogen den
    fachlich besten Treffer des Bestands auf 0, und dort war er von
    einer fachfremden Anzeige nicht mehr zu unterscheiden.
    """
    from bewerbungs_assistent.services import indikatoren

    job = _stelle()
    ktx = indikatoren.kontext(_DB(), _krit())
    befund = indikatoren.fuer_stelle(job, ktx)
    # Der Befund traegt zwei Marken und das Fachmaximum — und keinen
    # Namen, unter dem eine Summe stehen koennte.
    assert set(befund) == {"fach", "rahmen", "fach_maximum"}
    assert isinstance(befund["fach"], dict) and isinstance(befund["rahmen"], dict)

    # Und die Probe an der Sache: diese Stelle traegt einen Rahmen von
    # null verschieden — der Fachwert, den die Rechnung liefert, enthaelt
    # ihn NICHT. Ohne diesen Fall pruefte der Test nur Feldnamen.
    from bewerbungs_assistent.job_scraper import calculate_score
    kopie = dict(job)
    fach = calculate_score(kopie, _krit())
    assert kopie["_rahmenscore"] != 0
    assert fach == kopie["_fachscore"] != fach + kopie["_rahmenscore"]


def test_nur_belegt_verletzte_rahmen_gelten_als_passt_nicht():
    """Der Filter darf Ungeprueftes nicht ausblenden.

    Ein grauer Daumen nach unten heisst "sieht schlecht aus, aber
    ungeprueft". Ihn wegzufiltern waere die Verwechslung, gegen die #989
    angetreten ist — nur diesmal mit Folgen: die Stelle waere weg.
    """
    from bewerbungs_assistent.services import indikatoren, rahmen

    belegt = {"rahmen_daumen": {"richtung": rahmen.RUNTER, "farbe": rahmen.BELEGT}}
    grau = {"rahmen_daumen": {"richtung": rahmen.RUNTER, "farbe": rahmen.GRAU}}
    passt = {"rahmen_daumen": {"richtung": rahmen.HOCH, "farbe": rahmen.BELEGT}}
    assert indikatoren.rahmen_passt_nicht(belegt) is True
    assert indikatoren.rahmen_passt_nicht(grau) is False
    assert indikatoren.rahmen_passt_nicht(passt) is False
    assert indikatoren.rahmen_passt_nicht({}) is False


# ══ Beide Listen ════════════════════════════════════════════════════

@pytest.fixture
def umgebung(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    # KEIN eigener Dateiname: der MCP-Weg unten oeffnet die Datenbank
    # selbst ueber `BA_DATA_DIR`. Mit einem abweichenden Pfad haetten
    # die beiden Listen verschiedene Bestaende verglichen — und der
    # Vergleich waere gruen geworden, ohne etwas zu pruefen.
    db = database.Database()
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Daumen"})
    db.set_search_criteria("keywords_muss", ["Stammdaten"])
    db.set_search_criteria("max_entfernung", {"festanstellung": 50})
    db.set_search_criteria("min_gehalt", 60000)

    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    vorher = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app), db
    finally:
        dash._db = vorher
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def _bestand(db):
    """Drei Stellen: Rahmen passt, Rahmen passt belegt NICHT, ungeprueft."""
    jobs = [
        {"hash": "nah", "title": "Stammdaten Migration",
         "company": "Musterfirma GmbH", "location": "Musterstadt",
         "url": "https://example.com/1052/nah",
         "source": "manuell", "_manual_entry": True,
         "description": "Stammdaten und Migration. " * 12,
         "employment_type": "festanstellung", "distance_km": 12.0,
         "salary_min": 75000, "salary_type": "jaehrlich",
         "salary_estimated": 0, "score": 14.0},
        {"hash": "fern", "title": "Stammdaten Migration",
         "company": "Musterwerk AG", "location": "Musterberg",
         "url": "https://example.com/1052/fern",
         "source": "manuell", "_manual_entry": True,
         "description": "Stammdaten und Migration. " * 12,
         "employment_type": "festanstellung", "distance_km": 400.0,
         "salary_min": 75000, "salary_type": "jaehrlich",
         "salary_estimated": 0, "score": 14.0},
        {"hash": "unklar", "title": "Stammdaten Migration",
         "company": "Musterbetrieb KG", "location": "",
         "url": "https://example.com/1052/unklar",
         "source": "manuell", "_manual_entry": True,
         "description": "Stammdaten und Migration. " * 12,
         "employment_type": "festanstellung",
         "score": 14.0},
    ]
    db.save_jobs(jobs)


def test_der_stellen_tab_bekommt_beide_daumen(umgebung):
    """#989 MERKE 1: ein Befund, den nur ein Werkzeug kennt, ist keiner."""
    tc, db = umgebung
    _bestand(db)
    antwort = tc.get("/api/jobs?active=true&limit=10&rahmen_ausblenden=false").json()
    assert antwort["jobs"], antwort
    for job in antwort["jobs"]:
        assert "fach_daumen" in job, job.get("title")
        assert "rahmen_daumen" in job
        assert job["rahmen_daumen"]["richtung"] in ("hoch", "mittel", "runter")


def test_die_mcp_liste_bekommt_dieselben_daumen(umgebung):
    """Zwei Fassungen desselben Indikators waeren #1008 noch einmal.

    Dort trug derselbe Feldname in beiden Wegen verschiedene Zahlen,
    weil ein Aufrufer am Nadeloehr vorbeiging.
    """
    tc, db = umgebung
    _bestand(db)
    import bewerbungs_assistent.server as srv
    importlib.reload(srv)

    async def _run():
        tool = await srv.mcp.get_tool("stellen_anzeigen")
        res = await tool.run({"pro_seite": 10})
        return res.structured_content if hasattr(res, "structured_content") else res

    liste = asyncio.run(_run())
    zeilen = {z["hash"].split(":")[-1]: z for z in liste.get("stellen", [])}
    assert zeilen, liste
    rest = tc.get("/api/jobs?active=true&limit=10&rahmen_ausblenden=false").json()
    vom_server = {j["hash"].split(":")[-1]: j for j in rest["jobs"]}
    for kennung, zeile in zeilen.items():
        assert zeile["rahmen_daumen"]["richtung"] == \
            vom_server[kennung]["rahmen_daumen"]["richtung"], kennung
        assert zeile["fach_daumen"]["richtung"] == \
            vom_server[kennung]["fach_daumen"]["richtung"], kennung


def test_der_rahmenfilter_ist_vorgabe_an_und_nennt_seine_zahl(umgebung):
    """Die Ausnahme von #1008 — und deshalb ihr zweiter Teil verschaerft.

    Vorgabe AN war die Nutzerantwort; ein Filter, der schweigt, hat beim
    Melder sieben von acht Stellen verschwinden lassen. Also nennt er,
    wie viele er ausblendet, und er ist mit einem Klick aus.
    """
    tc, db = umgebung
    _bestand(db)

    mit_filter = tc.get("/api/jobs?active=true&limit=10&sort=score_desc").json()
    sichtbar = {j["hash"].split(":")[-1] for j in mit_filter["jobs"]}
    assert "fern" not in sichtbar, "400 km sind belegt ausserhalb der Grenze"
    assert "nah" in sichtbar
    # Die ungeprueste Stelle bleibt — "unbekannt" ist nicht "passt
    # nicht" (#989).
    assert "unklar" in sichtbar
    assert mit_filter["rahmen_verborgen"] == 1

    ohne_filter = tc.get(
        "/api/jobs?active=true&limit=10&sort=score_desc"
        "&rahmen_ausblenden=false").json()
    assert "fern" in {j["hash"].split(":")[-1] for j in ohne_filter["jobs"]}
    assert ohne_filter["rahmen_verborgen"] == 0


def test_ohne_listenanfrage_filtert_niemand(umgebung):
    """Dashboard und Onboarding holen die rohe Liste.

    Die Vorgabe AN darf ihnen nicht stillschweigend Stellen wegnehmen —
    sie stellen keine Listenanfrage und bekommen den Bestand.
    """
    tc, db = umgebung
    _bestand(db)
    roh = tc.get("/api/jobs?active=true").json()
    assert isinstance(roh, list)
    assert {j["hash"].split(":")[-1] for j in roh} == {"nah", "fern", "unklar"}


# ══ Die Oberflaeche ═════════════════════════════════════════════════

def test_karte_und_dialog_zeigen_beide_daumen():
    """Sechs Akzeptanzkriterien betreffen die Anzeige — ein Grep auf die
    Datei ist dort kein Beleg, aber ein FEHLENDER Aufruf ist einer."""
    quelle = _ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    assert quelle.count("<DaumenAbzeichen") >= 4, (
        "Karte und Dialog zeigen je zwei Daumen")
    assert "job.fach_daumen" in quelle and "job.rahmen_daumen" in quelle
    assert "detailDialog.job.fach_daumen" in quelle
    assert "detailDialog.job.rahmen_daumen" in quelle


def test_die_oberflaeche_rechnet_die_richtung_nicht_selbst():
    """Die Regeln stehen im Dienst, die Zuordnung in `lib/daumen.js`.

    Eine dritte Fassung im JSX waere #963 im Frontend — und genau das
    ist in dieser Liste schon einmal passiert (#1030: zehn Filter in
    Python UND in JavaScript).
    """
    quelle = _ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    for verdacht in ("trennschwelle", "oberes_viertel", "max_entfernung",
                     "min_gehalt"):
        assert verdacht not in quelle, (
            f"'{verdacht}' im Stellen-Tab — die Richtung gehoert in den Dienst")


def test_nirgends_wird_fach_und_rahmen_addiert():
    """Das erste Akzeptanzkriterium, als Guard.

    Gesucht wird die BAUFORM, nicht eine Fundstelle: jede Addition der
    beiden Groessen, in welcher Schreibweise auch immer.
    """
    quelle = _ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    muster = re.compile(
        r"(fachscore|fach_daumen|fach_maximum)[^\n]{0,40}\+[^\n]{0,40}"
        r"(rahmenscore|rahmen_daumen)")
    assert not muster.search(quelle), "Fach und Rahmen werden addiert"
    lib = _repo() / "frontend" / "src" / "lib" / "daumen.js"
    assert not muster.search(_ohne_kommentare(lib.read_text(encoding="utf-8")))


def test_der_schalter_steht_sichtbar_in_der_filterzeile():
    """Vorgabe AN heisst: er muss auffindbar und abschaltbar sein."""
    quelle = _ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    assert "Rahmen passt nicht ausblenden" in quelle
    assert "rahmenAusblenden: true" in quelle, "Vorgabe AN"
    assert "rahmen_ausblenden" in quelle, "das Abschalten geht an den Server"
    assert "rahmenVerborgen" in quelle, "der Filter nennt seine Zahl"
