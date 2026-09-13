"""Tests fuer services/ats_firmen.py (#811): Slugs aus dem Bestand, inhaltlich geprueft."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.services import ats_firmen as ats  # noqa: E402


class _Url:
    def __init__(self, host):
        self.host = host


class _Antwort:
    def __init__(self, status=200, host=None, content=b"", daten=None):
        self.status_code = status
        self.url = _Url(host) if host else None
        self.content = content
        self._daten = daten

    def json(self):
        if self._daten is None:
            raise ValueError("kein JSON")
        return self._daten


# ------------------------------------------------ Slugs aus Firmennamen


@pytest.mark.parametrize("name, erwartet", [
    ("Musterbetrieb Nord GmbH", ["musterbetrieb-nord", "musterbetriebnord"]),
    ("Musterbetrieb Nord GmbH & Co. KG", ["musterbetrieb-nord", "musterbetriebnord"]),
    ("Mueller Anlagenbau AG", ["mueller-anlagenbau", "muelleranlagenbau"]),
    ("Müller Anlagenbau AG", ["mueller-anlagenbau", "muelleranlagenbau"]),
    ("Beispiel Software (Hamburg) GmbH", ["beispiel-software", "beispielsoftware"]),
])
def test_rechtsform_und_umlaute(name, erwartet):
    assert ats.slug_kandidaten(name) == erwartet


def test_ein_zusatz_wird_in_beiden_fassungen_geprueft():
    k = ats.slug_kandidaten("Beispielwerk Deutschland GmbH")
    assert k[:2] == ["beispielwerk-deutschland", "beispielwerkdeutschland"]
    assert "beispielwerk" in k


def test_ein_kurzer_oder_leerer_name_ergibt_keinen_kandidaten():
    assert ats.slug_kandidaten("") == []
    assert ats.slug_kandidaten("AG") == []
    assert ats.slug_kandidaten("XY GmbH") == []


def test_keine_aehnlichkeit_nur_feste_regeln():
    """Ein Wort weglassen waere geraten — und fragte eine fremde Firma ab."""
    assert "musterbetrieb" not in ats.slug_kandidaten("Musterbetrieb Nord GmbH")


# ------------------------------------------------ Slugs aus URLs (sicher)


@pytest.mark.parametrize("url, erwartet", [
    ("https://beispiel.jobs.personio.de/job/12345", ("personio", "beispiel")),
    ("https://beispiel.jobs.personio.com/", ("personio", "beispiel")),
    ("https://boards.greenhouse.io/beispiel/jobs/4711", ("greenhouse", "beispiel")),
    ("https://job-boards.eu.greenhouse.io/beispiel/jobs/4711", ("greenhouse", "beispiel")),
    ("https://boards-api.greenhouse.io/v1/boards/beispiel/jobs", ("greenhouse", "beispiel")),
])
def test_slug_aus_url(url, erwartet):
    assert ats.slug_aus_url(url) == erwartet


@pytest.mark.parametrize("url", [
    "https://www.personio.de/", "https://example.com/jobs/1", "", None,
    # Workable: Quelle defekt (#927), die Widget-API antwortet mit 404 —
    # ein Slug dafuer waere eine Einstellung ohne Draht.
    "https://apply.workable.com/beispiel/j/ABC123/",
])
def test_keine_ats_url(url):
    assert ats.slug_aus_url(url) is None


def test_workable_steht_nicht_in_den_systemen():
    assert set(ats.SYSTEME) == {"personio", "greenhouse"}


# ------------------------------------------------ Antwort bewerten


def test_erfundener_personio_slug_mit_200_auf_fremdem_host_ist_ungueltig():
    """Der Bericht vom 06.08.: 200 und viel Inhalt."""
    antwort = _Antwort(200, "www.personio.com", b"<!DOCTYPE html>" + b"x" * 50000)
    assert ats.bewerte_antwort(ats.PERSONIO, "erfunden", antwort) == (ats.UNGUELTIG, 0)


def test_erfundener_personio_slug_mit_429_auf_fremdem_host_ist_ungueltig():
    """Nachgemessen am 13.09.: 429 — der Host entscheidet, nicht der Status."""
    antwort = _Antwort(429, "personio.com", b"<!DOCTYPE html>")
    assert ats.bewerte_antwort(ats.PERSONIO, "erfunden", antwort) == (ats.UNGUELTIG, 0)


def test_gueltiger_personio_slug():
    xml = (b'<?xml version="1.0"?><workzag-jobs><position><id>1</id></position>'
           b'<position><id>2</id></position></workzag-jobs>')
    antwort = _Antwort(200, "beispiel.jobs.personio.de", xml)
    assert ats.bewerte_antwort(ats.PERSONIO, "beispiel", antwort) == (ats.GUELTIG, 2)


def test_personio_ohne_stellen_ist_gueltig_nicht_ungueltig():
    """Eine Firma ohne offene Stellen ist eine echte Flaute, kein falscher Slug."""
    antwort = _Antwort(200, "beispiel.jobs.personio.de",
                       b'<?xml version="1.0"?><workzag-jobs></workzag-jobs>')
    assert ats.bewerte_antwort(ats.PERSONIO, "beispiel", antwort) == (ats.GUELTIG, 0)


def test_greenhouse_404_ist_ungueltig():
    antwort = _Antwort(404, "boards-api.greenhouse.io", daten={"status": 404})
    assert ats.bewerte_antwort(ats.GREENHOUSE, "erfunden", antwort)[0] == ats.UNGUELTIG


def test_greenhouse_gueltig_zaehlt_stellen():
    antwort = _Antwort(200, "boards-api.greenhouse.io", daten={"jobs": [{}, {}, {}]})
    assert ats.bewerte_antwort(ats.GREENHOUSE, "beispiel", antwort) == (ats.GUELTIG, 3)


def test_personio_fehlerseite_auf_dem_richtigen_host_ist_ungueltig():
    """Der Host stimmt, aber es ist kein Feed — z.B. eine Fehlerseite."""
    antwort = _Antwort(200, "beispiel.jobs.personio.de",
                       b"<!DOCTYPE html><html><body>Wartung</body></html>")
    assert ats.bewerte_antwort(ats.PERSONIO, "beispiel", antwort) == (ats.UNGUELTIG, 0)


def test_json_ohne_stellenliste_ist_ungueltig():
    antwort = _Antwort(200, "boards-api.greenhouse.io", daten={"status": "ok"})
    assert ats.bewerte_antwort(ats.GREENHOUSE, "beispiel", antwort) == (ats.UNGUELTIG, 0)


def test_html_statt_json_ist_ungueltig():
    antwort = _Antwort(200, "boards-api.greenhouse.io", b"<html>")
    assert ats.bewerte_antwort(ats.GREENHOUSE, "beispiel", antwort)[0] == ats.UNGUELTIG


def test_ein_serverfehler_ist_nicht_erreichbar_und_nicht_ungueltig():
    antwort = _Antwort(503, "boards-api.greenhouse.io")
    assert ats.bewerte_antwort(ats.GREENHOUSE, "beispiel", antwort)[0] == ats.NICHT_ERREICHBAR


# ======================================================= mit Datenbank

import asyncio  # noqa: E402
import importlib  # noqa: E402
import inspect  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402

PERSONIO_XML = (b'<?xml version="1.0"?><workzag-jobs><position><id>1</id>'
                b'<name>Rolle</name></position></workzag-jobs>')


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "ats.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.switch_profile(datenbank.create_profile("ATS"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


class _Client:
    """Antwortet je URL; alles Unbekannte ist ein Greenhouse-404."""

    def __init__(self, antworten=None, fehler=None):
        self.antworten = antworten or {}
        self.fehler = fehler
        self.anfragen = []

    def get(self, url):
        self.anfragen.append(url)
        if self.fehler:
            raise self.fehler
        from urllib.parse import urlparse
        if url in self.antworten:
            return self.antworten[url]
        return _Antwort(404, urlparse(url).hostname, daten={"status": 404})


def _personio(slug):
    return ats.URLS[ats.PERSONIO].format(slug=slug)


def test_kandidaten_aus_bewerbung_kontakt_und_stellen_url(db):
    db.add_application({"title": "Rolle", "company": "Musterbetrieb Nord GmbH",
                        "status": "beworben"})
    db.add_contact({"full_name": "Erika Beispiel", "company": "Beispielwerk AG"})
    db.save_jobs([{"hash": "ats1", "title": "Rolle", "company": "Irgendwer",
                   "url": "https://beispiel-board.jobs.personio.de/job/1",
                   "source": "manuell", "_manual_entry": True,
                   "description": "Text " * 20}])
    kand = ats.kandidaten(db)
    assert kand[0] == {"system": "personio", "slug": "beispiel-board",
                       "firma": "Irgendwer", "quelle": ats.QUELLE_URL}
    firmen = {k["firma"] for k in kand}
    assert {"Musterbetrieb Nord GmbH", "Beispielwerk AG"} <= firmen


def test_die_obergrenze_begrenzt_die_firmennamen(db):
    for i in range(12):
        db.add_contact({"full_name": f"Person {i}", "company": f"Firma Nummer{i} GmbH"})
    namen = {k["firma"] for k in ats.kandidaten(db, max_namen=5)}
    assert len(namen) == 5


def test_ermitteln_speichert_treffer_und_ungueltige_aber_keinen_ausfall(db):
    db.add_contact({"full_name": "A", "company": "Musterbetrieb Nord GmbH"})
    client = _Client({_personio("musterbetrieb-nord"):
                      _Antwort(200, "musterbetrieb-nord.jobs.personio.de", PERSONIO_XML)})
    ergebnis = ats.ermitteln(db, client=client)
    assert [g["slug"] for g in ergebnis["gefunden"]] == ["musterbetrieb-nord"]
    assert ats.gueltige_slugs(db, ats.PERSONIO) == ["musterbetrieb-nord"]
    assert ergebnis["ungueltig"] >= 1
    # Zweiter Lauf: alles schon geprueft, keine neue Anfrage.
    vorher = len(client.anfragen)
    ats.ermitteln(db, client=client)
    assert len(client.anfragen) == vorher


def test_ein_ausfall_wird_nicht_als_ungueltig_gemerkt(db):
    db.add_contact({"full_name": "A", "company": "Musterbetrieb Nord GmbH"})
    ergebnis = ats.ermitteln(db, client=_Client(fehler=TimeoutError("weg")))
    assert ergebnis["nicht_erreichbar"] > 0 and ergebnis["ungueltig"] == 0
    assert len(ats.kandidaten(db)) > 0, "beim naechsten Lauf wieder dran"


def test_die_gueltigen_firmen_erreichen_die_suchparameter(db):
    """#811 und der Regler ohne Draht: personio_firmen kam nie an."""
    from bewerbungs_assistent.job_scraper import build_search_keywords

    db.set_search_criteria("keywords_muss", ["python"])
    db.set_search_criteria("personio_firmen", ["von-hand"])
    db.set_search_criteria("workable_firmen", ["auch-von-hand"])
    ats.speichern(db, ats.PERSONIO, "aus-bestand", "Aus Bestand", ats.QUELLE_NAME,
                  ats.GUELTIG, 3)
    ats.speichern(db, ats.PERSONIO, "ungueltig", "X", ats.QUELLE_NAME,
                  ats.UNGUELTIG, 0)
    ats.speichern(db, ats.GREENHOUSE, "gh-bestand", "Y", ats.QUELLE_URL,
                  ats.GUELTIG, 5)
    params = build_search_keywords(db)
    assert params["personio_firmen"] == ["aus-bestand", "von-hand"]
    assert params["workable_firmen"] == ["auch-von-hand"]
    assert params["greenhouse_companies"][0] == "gh-bestand"


def test_der_personio_adapter_verwirft_eine_umleitung():
    from bewerbungs_assistent.job_scraper import personio

    umleitung = _Client({_personio("erfunden"):
                         _Antwort(200, "www.personio.com", b"<!DOCTYPE html>" * 100)})
    assert personio._fetch_firma(umleitung, "erfunden") == []
    echt = _Client({_personio("beispiel"):
                    _Antwort(200, "beispiel.jobs.personio.de", PERSONIO_XML)})
    assert len(personio._fetch_firma(echt, "beispiel")) == 1


def test_der_personio_adapter_uebernimmt_kein_fremdes_board():
    """Ein umbenannter Slug leitet auf das Board einer ANDEREN Firma um —
    mit gueltigem Feed. Ohne Hostpruefung stuenden deren Stellen unter dem
    angefragten Namen im Bestand."""
    from bewerbungs_assistent.job_scraper import personio

    fremd = _Client({_personio("alter-name"):
                     _Antwort(200, "andere-firma.jobs.personio.de", PERSONIO_XML)})
    assert personio._fetch_firma(fremd, "alter-name") == []


def test_status_nennt_null_eigene_firmen(db):
    stand = ats.status(db)
    assert stand["personio"]["eigene_gueltig"] == 0
    assert stand["greenhouse"]["beispielfirmen"] > 0


def test_ats_firmen_gehoert_zu_einem_loeschbereich():
    from bewerbungs_assistent.services import loeschbereiche

    assert "ats_firmen" in {t for tab in loeschbereiche.BEREICHE.values() for t in tab}


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


def test_werkzeug_status_vorschau_und_wunsch(db, monkeypatch):
    mcp = _mcp(db)
    stand = _call(mcp, "ats_firmen_verwalten", {})
    assert "ermitteln" in stand["hinweis"]

    db.add_contact({"full_name": "A", "company": "Musterbetrieb Nord GmbH"})
    vorschau = _call(mcp, "ats_firmen_verwalten", {"aktion": "ermitteln"})
    assert vorschau["status"] == "vorschau" and vorschau["anfragen"] > 0
    assert ats.status(db)["personio"]["geprueft_ungueltig"] == 0, \
        "die Vorschau speichert nichts"

    def _pruefen(system, slug, client=None):
        if (system, slug) == ("greenhouse", "beispielwerk"):
            return ats.GUELTIG, 7
        return ats.UNGUELTIG, 0

    monkeypatch.setattr(ats, "pruefen", _pruefen)
    wunsch = _call(mcp, "ats_firmen_verwalten",
                   {"aktion": "hinzufuegen", "firmen": ["Beispielwerk", "Gibt Es Nicht GmbH"]})
    assert wunsch["aufgenommen"][0]["slug"] == "beispielwerk"
    assert wunsch["nicht_gefunden"] == ["Gibt Es Nicht GmbH"]
    assert ats.gueltige_slugs(db, ats.GREENHOUSE) == ["beispielwerk"]

    weg = _call(mcp, "ats_firmen_verwalten",
                {"aktion": "entfernen", "firmen": ["beispielwerk"]})
    assert weg["entfernt"] == 1


def test_scraper_diagnose_zeigt_die_ats_firmen():
    from bewerbungs_assistent.tools import jobs

    code = inspect.getsource(jobs)
    diagnose = code[code.index("def scraper_diagnose("):]
    diagnose = diagnose[:diagnose.index("@mcp.tool()")]
    assert 'result["ats_firmen"] = _ats.status(db)' in diagnose
