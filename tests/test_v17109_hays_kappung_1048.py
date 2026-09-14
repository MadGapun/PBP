"""Tests fuer #1048 — hays kappte den Anzeigentext bei 500 Zeichen.

`hays.py` speicherte `data.get("description", "")[:500]`. #952 hatte die
Kappung bei 2000 Zeichen aus 26 Adaptern entfernt; der Guard dagegen
suchte die Zeichenkette `[:2000]` und liess jede andere Zahl durch.

Gemessen am 14.09.2026:

* live: 8 von 8 hays-Anzeigen tragen 1.527 bis 3.311 Zeichen,
* Kopie eines Bestands: 48 von 48 hays-Stellen exakt 500 Zeichen,
* alle Texte mit exakt 2000 Zeichen stammen von vor v1.7.23 — keine
  andere Quelle kappt noch.

Das Nachladen erkannte nur exakt 2000 als gekappt, fand die hays-Stellen
also nicht, und keiner der vier Nachlade-Wege bewertete danach neu.
"""
import ast
import asyncio
import importlib
import json
import logging
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.job_scraper import fit_analyse  # noqa: E402
from bewerbungs_assistent.job_scraper.textgrenzen import (  # noqa: E402
    ALTE_KAPPUNG,
    QUELLEN_KAPPUNG,
    ist_gekappt,
    kappungs_grenze,
    kappungs_hinweis,
)

# Eine Anzeige wie die gemessenen: Vorstellung vorn, das Entscheidende
# hinter Zeichen 500.
VORSPANN = ("Die Musterfirma Nord ist ein mittelstaendischer Anbieter von "
            "Loesungen fuer die Industrie und legt Wert auf eine offene "
            "Kultur. ") * 6
SCHLUSS = ("\n\nIhr Profil: mehrjaehrige Erfahrung mit Windchill. Die Stelle "
           "ist befristet auf 24 Monate. Gehalt: 60.000 - 70.000 EUR pro Jahr.")
ANZEIGE = VORSPANN + SCHLUSS
GEKAPPT = ANZEIGE[:500]


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "test.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.switch_profile(datenbank.create_profile("Muster"))
    datenbank.set_search_criteria("keywords_muss", ["Windchill"])
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _mcp(db):
    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    return mcp


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def _stelle(db, hash_, text, quelle="hays"):
    db.save_jobs([{
        "hash": hash_, "title": f"Projektmanager {hash_}",
        "company": "Musterfirma Nord", "location": "Musterstadt",
        "url": f"https://example.com/1048/{hash_}", "source": quelle,
        "description": text, "score": 0,
    }])


def _zeile(db, hash_):
    return db.connect().execute(
        "SELECT description, score, fachscore, salary_min, salary_max, "
        "salary_type, arbeitsumfang, befristet FROM jobs WHERE hash=?",
        (db.resolve_job_hash(hash_),)).fetchone()


def test_vorbedingung_die_anzeige_traegt_ihre_belege_erst_hinter_500():
    """Sonst pruefen die Faelle unten nichts."""
    from bewerbungs_assistent.services import gehalt_extraktion, stellenart

    assert len(VORSPANN) > 500
    assert gehalt_extraktion.extrahieren(ANZEIGE)["art"]
    assert not gehalt_extraktion.extrahieren(GEKAPPT)["art"]
    assert stellenart.merkmale({"title": "x", "description": ANZEIGE})["befristet"]
    assert not stellenart.merkmale({"title": "x", "description": GEKAPPT})["befristet"]
    assert "Windchill" not in GEKAPPT


# ---------------------------------------------- AK 1: voller Text in die Ablage


def test_hays_speichert_den_vollen_anzeigentext(monkeypatch):
    from bewerbungs_assistent.job_scraper import hays

    sitemap = ("<urlset><url><loc>https://www.hays.de/jobangebot/"
               "projektmanager-musterstadt-1</loc></url></urlset>")
    posting = {"@type": "JobPosting", "title": "Projektmanager (m/w/d)",
               "hiringOrganization": {"name": "Musterfirma Nord"},
               "jobLocation": {"address": {"addressLocality": "Musterstadt"}},
               "description": ANZEIGE}
    detail = ('<html><head><script type="application/ld+json">'
              + json.dumps(posting) + "</script></head><body></body></html>")

    class _Antwort:
        def __init__(self, text):
            self.text, self.status_code = text, 200

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **k):
            return _Antwort(sitemap if url == hays.SITEMAP_URL else detail)

    monkeypatch.setattr(hays.httpx, "Client", _Client)
    monkeypatch.setattr(hays.time, "sleep", lambda _s: None)
    stellen = hays.search_hays({})
    assert len(stellen) == 1
    assert stellen[0]["description"] == ANZEIGE


# ------------------------------- AK 2: das Nachladen erkennt die Kappung


def test_die_grenze_einer_quelle_gilt_nur_fuer_diese_quelle():
    """500 Zeichen sind bei jeder anderen Quelle eine kurze Anzeige.

    Sie dort als gekappt zu fuehren waere ein Fehlalarm (#929).
    """
    assert QUELLEN_KAPPUNG["hays"] == 500
    assert kappungs_grenze("x" * 500, "hays") == 500
    assert kappungs_grenze("x" * 500, " hays ") == 500
    assert kappungs_grenze("x" * 500, "arbeitnow") is None
    assert kappungs_grenze("x" * 500) is None
    assert kappungs_grenze("x" * 499, "hays") is None
    assert kappungs_grenze("x" * 501, "hays") is None


def test_die_allgemeine_grenze_aus_952_gilt_weiter_fuer_jede_quelle():
    assert kappungs_grenze("x" * ALTE_KAPPUNG) == ALTE_KAPPUNG
    assert kappungs_grenze("x" * ALTE_KAPPUNG, "hays") == ALTE_KAPPUNG
    assert ist_gekappt("x" * ALTE_KAPPUNG)
    assert not ist_gekappt("")
    assert not ist_gekappt(None, "hays")


def test_der_hinweis_nennt_die_richtige_grenze_und_herkunft():
    hays = kappungs_hinweis("x" * 500, "hays")
    assert "500 Zeichen" in hays and "Quelle" in hays
    alt = kappungs_hinweis("x" * ALTE_KAPPUNG)
    assert "2000 Zeichen" in alt and "v1.7.23" in alt
    assert kappungs_hinweis("x" * 500, "arbeitnow") == ""


def test_fit_analyse_meldet_den_hays_text_als_unvollstaendig():
    kriterien = {"keywords_muss": ["PLM"], "keywords_plus": [],
                 "keywords_minus": [], "keywords_ausschluss": []}
    text = ("Wort " * 100)[:500]
    assert len(text) == 500
    hays = fit_analyse({"title": "Consultant", "description": text,
                        "source": "hays", "company": "Musterfirma Nord"},
                       kriterien)
    andere = fit_analyse({"title": "Consultant", "description": text,
                          "source": "arbeitnow", "company": "Musterfirma Nord"},
                         kriterien)
    assert hays["beschreibung_unvollstaendig"] is True
    assert andere["beschreibung_unvollstaendig"] is False


def test_der_mengenweg_findet_die_gekappte_hays_stelle(db):
    """Vorher fiel sie durch beide Raster: nicht unter 50, nicht 2000."""
    _stelle(db, "h1048a", GEKAPPT)
    _stelle(db, "h1048b", GEKAPPT, quelle="arbeitnow")
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"umfang": "gekappt"})
    assert erg["status"] == "vorschau", erg
    assert erg["betroffen"] == 1
    assert erg["gefunden"]["gekappt"] == 1
    assert erg["beispiele"][0]["zeichen"] == 500


# ------------------------------- AK 3: Score und Merkmale aus dem vollen Text


def _nachladen_liefert(monkeypatch, text):
    from bewerbungs_assistent.services import nachladen

    def _holen(url, client, **k):
        return nachladen.Befund(status=nachladen.GELESEN, text=text,
                                http_status=200, quelle="html")
    monkeypatch.setattr(nachladen, "beschreibung_holen", _holen)


def test_der_mengenweg_bewertet_die_geheilte_stelle_neu(db, monkeypatch):
    _stelle(db, "h1048c", GEKAPPT)
    vorher = _zeile(db, "h1048c")
    assert vorher["score"] == 0
    _nachladen_liefert(monkeypatch, ANZEIGE)

    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"umfang": "gekappt", "nur_zaehlen": False})
    assert erg["geheilt"] == 1, erg
    zeile = _zeile(db, "h1048c")
    assert zeile["description"] == ANZEIGE
    assert zeile["score"] > 0
    assert zeile["fachscore"] is not None
    assert zeile["salary_type"] and zeile["salary_min"]
    assert zeile["befristet"] == 1
    assert erg["gewachsen"][0]["score"]["nachher"] == zeile["score"]


def test_der_einzelweg_bewertet_neu_und_nennt_die_kappung(db, monkeypatch):
    _stelle(db, "h1048d", GEKAPPT)
    _nachladen_liefert(monkeypatch, ANZEIGE)

    erg = _call(_mcp(db), "stellenbeschreibung_nachladen",
                {"stellen_hash": "h1048d"})
    assert erg["status"] == "ok", erg
    assert erg["gekappten_text_geheilt"] is True
    assert erg["neu_ausgewertet"]["score"]["nachher"] > 0
    assert _zeile(db, "h1048d")["score"] > 0


def test_ein_von_hand_gesetztes_gehalt_bleibt(db):
    from bewerbungs_assistent.services import nachladen

    _stelle(db, "h1048e", GEKAPPT)
    assert db.save_salary_data("h1048e", 90000, 95000, "jaehrlich",
                               salary_estimated=0, quelle="mensch")
    erg = nachladen.text_uebernehmen(db, "h1048e", ANZEIGE)
    assert erg["gehalt"] is False
    zeile = _zeile(db, "h1048e")
    assert (zeile["salary_min"], zeile["salary_max"]) == (90000, 95000)


def test_ein_gespeicherter_umfang_wird_nicht_umgedeutet(db):
    """Ergaenzen, nicht umdeuten — ein Wert, der sich selbst bestaetigt,
    war schon einmal der Fehler (#1031)."""
    from bewerbungs_assistent.services import nachladen

    _stelle(db, "h1048f", GEKAPPT)
    conn = db.connect()
    conn.execute("UPDATE jobs SET arbeitsumfang='vollzeit' WHERE hash=?",
                 (db.resolve_job_hash("h1048f"),))
    conn.commit()
    erg = nachladen.text_uebernehmen(
        db, "h1048f", ANZEIGE + " Auch in Teilzeit moeglich.")
    assert "arbeitsumfang" not in erg["merkmale"]
    assert _zeile(db, "h1048f")["arbeitsumfang"] == "vollzeit"


def test_ein_vorhandenes_gehalt_ohne_neuen_beleg_bleibt(db):
    from bewerbungs_assistent.services import nachladen

    _stelle(db, "h1048g", GEKAPPT)
    db.save_salary_data("h1048g", 50000, 55000, "jaehrlich",
                        salary_estimated=1)
    nachladen.text_uebernehmen(db, "h1048g", VORSPANN + " Ohne Zahlen.")
    zeile = _zeile(db, "h1048g")
    assert (zeile["salary_min"], zeile["salary_max"]) == (50000, 55000)


def _funktion(pfad: Path, name: str) -> str:
    # `dashboard.py` beginnt mit einem BOM, das `ast.parse` ablehnt.
    quelle = pfad.read_text(encoding="utf-8-sig")
    for knoten in ast.walk(ast.parse(quelle)):
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and knoten.name == name:
            return ast.get_source_segment(quelle, knoten)
    raise AssertionError(f"{name} nicht gefunden in {pfad.name}")


@pytest.mark.parametrize("datei,name", [
    ("tools/jobs.py", "stellenbeschreibung_nachladen"),
    ("tools/jobs.py", "beschreibungen_nachladen_bestand"),
    ("dashboard.py", "api_refetch_description"),
    ("dashboard.py", "_run_auto_refetch_descriptions"),
])
def test_jeder_nachladeweg_geht_durch_text_uebernehmen(datei, name):
    """Vier Aufrufer, und bis v1.7.108 bewertete keiner neu (#963)."""
    block = _funktion(_repo() / "src" / "bewerbungs_assistent" / datei, name)
    assert "text_uebernehmen(" in block
    assert not re.search(r'update_job\([^)]*\{\s*"description"', block), (
        f"{name} schreibt den Text wieder selbst")


# ---------------------------------------- Guard: keine Kappung in die Ablage


def _kappungen_in_die_ablage(quelltext: str) -> list:
    """Zeilen, in denen `description` einen abgeschnittenen Wert bekommt.

    Der #952-Guard suchte die Zeichenkette `[:2000]` — und liess `[:500]`
    durch. Geprueft wird deshalb die BAUFORM: ein Slice mit Obergrenze als
    Wert von `description`, direkt oder ueber eine Variable, die aus einem
    solchen Slice entstand.
    """
    baum = ast.parse(quelltext)

    def _kappt(knoten) -> bool:
        if not (isinstance(knoten, ast.Subscript)
                and isinstance(knoten.slice, ast.Slice)
                and knoten.slice.upper is not None):
            return False
        # `max_chars` ist die Grenze des AUFRUFERS. Dass ihre Vorgabe
        # keine feste Zahl ist, prueft
        # `test_jede_max_chars_vorgabe_ist_die_notbremse`.
        obere = knoten.slice.upper
        return not (isinstance(obere, ast.Name) and obere.id == "max_chars")

    gekappte_namen = {
        ziel.id
        for knoten in ast.walk(baum) if isinstance(knoten, ast.Assign)
        and _kappt(knoten.value)
        for ziel in knoten.targets if isinstance(ziel, ast.Name)
    }

    def _wert_gekappt(wert) -> bool:
        return _kappt(wert) or (isinstance(wert, ast.Name)
                                and wert.id in gekappte_namen)

    funde = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Dict):
            for schluessel, wert in zip(knoten.keys, knoten.values):
                if (isinstance(schluessel, ast.Constant)
                        and schluessel.value == "description"
                        and _wert_gekappt(wert)):
                    funde.append(wert.lineno)
        elif isinstance(knoten, ast.Assign):
            for ziel in knoten.targets:
                if (isinstance(ziel, ast.Subscript)
                        and isinstance(ziel.slice, ast.Constant)
                        and ziel.slice.value == "description"
                        and _wert_gekappt(knoten.value)):
                    funde.append(knoten.lineno)
    return funde


def test_der_guard_erkennt_jede_gestalt_der_kappung():
    """Beide Richtungen — ein Guard, der nichts findet, belegt nichts."""
    assert _kappungen_in_die_ablage(
        'job = {"description": data.get("description", "")[:500]}')
    assert _kappungen_in_die_ablage(
        'desc = text[:300]\njob = {"description": desc}')
    assert _kappungen_in_die_ablage(
        'job = {}\njob["description"] = text[:1500]')
    assert not _kappungen_in_die_ablage(
        'job = {"description": fuer_speicher(text)}')
    assert not _kappungen_in_die_ablage(
        'job = {"description": text, "remote": detect(text[:500])}')
    assert not _kappungen_in_die_ablage(
        'job = {"description": text[5:]}')
    # Die Grenze des Aufrufers ist erlaubt, eine benannte feste Zahl nicht.
    assert not _kappungen_in_die_ablage(
        'result["description"] = text[:max_chars]')
    assert _kappungen_in_die_ablage(
        'LIMIT = 800\njob = {"description": text[:LIMIT]}')


def test_jede_max_chars_vorgabe_ist_die_notbremse():
    """Die zweite Gestalt derselben Falle: eine feste Zahl als VORGABE.

    `extract_jobposting_jsonld(html, max_chars=2000)` stand bis v1.7.108
    da — der #952-Guard suchte `[:2000]` und sah die Vorgabe nicht, und
    der Adapter-Guard oben erlaubt `[:max_chars]` nur wegen dieses Tests.
    """
    ordner = _repo() / "src" / "bewerbungs_assistent" / "job_scraper"
    feste = []
    for datei in sorted(ordner.glob("*.py")):
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            argumente = knoten.args
            positionell = argumente.posonlyargs + argumente.args
            paare = list(zip(positionell[len(positionell) - len(argumente.defaults):],
                             argumente.defaults))
            paare += [(a, d) for a, d in zip(argumente.kwonlyargs,
                                             argumente.kw_defaults) if d is not None]
            for arg, vorgabe in paare:
                if arg.arg == "max_chars" and not (
                        isinstance(vorgabe, ast.Constant) and vorgabe.value is None):
                    feste.append(f"{datei.name}:{knoten.name}")
    assert feste == [], f"max_chars mit fester Vorgabe: {feste}"


def test_json_ld_ohne_grenze_behaelt_den_vollen_text():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld

    html = ('<script type="application/ld+json">'
            + json.dumps({"@type": "JobPosting", "description": "x" * 5000})
            + "</script>")
    assert len(extract_jobposting_jsonld(html)["description"]) == 5000


def test_json_ld_ohne_grenze_greift_die_notbremse(monkeypatch):
    """Ohne Argument gilt die Notbremse, nicht "gar keine Grenze".

    Die Gegenprobe zeigte den Fall als stumm: `text[:None]` liefert
    ebenfalls den ganzen Text, der Unterschied liegt erst jenseits der
    Notbremse.
    """
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld, textgrenzen

    monkeypatch.setattr(textgrenzen, "SPEICHER_MAX", 1000)
    html = ('<script type="application/ld+json">'
            + json.dumps({"@type": "JobPosting", "description": "x" * 5000})
            + "</script>")
    assert len(extract_jobposting_jsonld(html)["description"]) == 1000


def test_die_qualitaetspruefung_meldet_die_gekappte_hays_stelle(db, monkeypatch):
    """Die Gegenprobe zeigte die Pruefung als stumm — es gab keinen Fall.

    Die Erreichbarkeit wird ersetzt: gefragt ist hier nur die Kategorie,
    nicht das Netz.
    """
    from bewerbungs_assistent.services import url_health

    class _Erreichbar:
        status = "erreichbar"
        should_dismiss = False

        def to_dict(self):
            return {"status": self.status}

    monkeypatch.setattr(url_health, "check_job_url_health",
                        lambda url, title, client=None: _Erreichbar())
    _stelle(db, "h1048h", GEKAPPT)
    _stelle(db, "h1048i", GEKAPPT, quelle="arbeitnow")

    erg = _call(_mcp(db), "stellen_qualitaet_pruefen", {"max_stellen": 10})
    gekappt = [d for d in erg["details"]
               if "beschreibung_gekappt" in d.get("kategorien", [])]
    assert [d["source"] for d in gekappt] == ["hays"], erg["details"]
    assert erg["beschreibung_gekappt_gesamt"]["anzahl"] == 1
    assert "hays" in erg["beschreibung_gekappt_gesamt"]["hinweis"]


def test_kein_adapter_kappt_den_anzeigentext_in_die_ablage():
    ordner = _repo() / "src" / "bewerbungs_assistent" / "job_scraper"
    funde = {}
    for datei in sorted(ordner.glob("*.py")):
        zeilen = _kappungen_in_die_ablage(datei.read_text(encoding="utf-8"))
        if zeilen:
            funde[datei.name] = zeilen
    assert funde == {}, f"Diese Adapter kappen in die Ablage: {funde}"
