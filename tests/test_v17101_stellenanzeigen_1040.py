"""Tests fuer #1040 (B49): stellenanzeigen.de liefert Firma und Ort, fuer jeden Suchbegriff.

Bis v1.7.100 kam jede Stelle als "Unbekannt" ohne Ort herein (die Seite
nutzt generierte Klassennamen), und der Kartenweg lief nur fuer den ersten
Suchbegriff. Die Fixtures bilden die gemessene Struktur nach; alle Titel,
Firmen und Orte sind erfunden.
"""
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.job_scraper import stellenanzeigen_de as sa  # noqa: E402

FIXTURES = _repo() / "tests" / "fixtures" / "scrapers"


def _seite(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _Antwort:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _Client:
    def __init__(self, seiten: dict, abrufe: list):
        self._seiten = seiten
        self._abrufe = abrufe

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url, params=None, **_):
        begriff = (params or {}).get("q", "")
        self._abrufe.append(begriff)
        if begriff in self._seiten:
            return _Antwort(200, self._seiten[begriff])
        return _Antwort(404, "")


@pytest.fixture
def lauf(monkeypatch):
    def _lauf(seiten: dict, begriffe: list):
        abrufe: list = []
        monkeypatch.setattr(sa.httpx, "Client",
                            lambda *a, **k: _Client(seiten, abrufe))
        monkeypatch.setattr(sa.time, "sleep", lambda *_a, **_k: None)
        stellen = sa.search_stellenanzeigen_de({"keywords": {"general": begriffe}})
        return stellen, abrufe
    return _lauf


# ====================================================== Firma und Ort


def test_jede_karte_bringt_firma_und_ort(lauf):
    """Meldefall: 31 von 31 Stellen kamen als "Unbekannt" ohne Ort."""
    stellen, _ = lauf({"Sachbearbeitung": _seite("stellenanzeigen_de_ergebnis.html")},
                      ["Sachbearbeitung"])
    assert len(stellen) == 3
    assert all(s["company"] != "Unbekannt" for s in stellen), stellen
    assert all(s["location"] for s in stellen), stellen
    erste = stellen[0]
    assert erste["title"] == "Sachbearbeitung Einkauf (m/w/d)"
    assert erste["company"] == "Muster Handelsgesellschaft mbH"
    assert erste["location"] == "Musterstadt"


def test_hinweise_vor_dem_titel_verschieben_nichts(lauf):
    """Die dritte Karte traegt zwei Hinweise VOR dem Titel."""
    stellen, _ = lauf({"Sachbearbeitung": _seite("stellenanzeigen_de_ergebnis.html")},
                      ["Sachbearbeitung"])
    dritte = stellen[2]
    assert dritte["company"] == "Musterwerke Nordheim GmbH"
    assert dritte["location"] == "Nordheim"


def test_die_url_ist_die_anzeige_und_absolut(lauf):
    stellen, _ = lauf({"Sachbearbeitung": _seite("stellenanzeigen_de_ergebnis.html")},
                      ["Sachbearbeitung"])
    assert stellen[0]["url"] == (
        "https://www.stellenanzeigen.de/job/"
        "sachbearbeitung-einkauf-m-w-d-musterstadt-10000001/")


def test_ohne_ort_steht_keine_arbeitszeit_im_ortsfeld():
    """Fehlt der Ort, steht an seiner Stelle eine Arbeitszeit — die gehoert
    nicht ins Ortsfeld, sonst geocodet PBP "Vollzeit"."""
    html = (
        '<div><div><a href="/job/lagerhilfe-10000009/">Lagerhilfe im Musterlager</a>'
        '<span>Musterlager GmbH</span><span>Vollzeit</span><span>13.09.2026</span>'
        '</div></div>')
    karte = sa.karten_aus_html(html)[0]
    assert karte["firma"] == "Musterlager GmbH"
    assert karte["ort"] == ""


def test_ohne_arbeitgeber_bleibt_der_platzhalter():
    html = ('<div><a href="/job/aushilfe-10000010/">Aushilfe im Verkauf</a>'
            '<span>13.09.2026</span></div>')
    karte = sa.karten_aus_html(html)[0]
    assert karte["firma"] == "" and karte["ort"] == ""
    assert sa._stelle(karte["titel"], karte["firma"], karte["ort"],
                      karte["url"])["company"] == "Unbekannt"


# ====================================================== jeder Suchbegriff


def test_jeder_suchbegriff_wird_ausgewertet(lauf):
    """Meldefall: 25 Stellen in jedem Lauf, obwohl drei Seiten 61 trugen."""
    seiten = {"Sachbearbeitung": _seite("stellenanzeigen_de_ergebnis.html"),
              "Logistik": _seite("stellenanzeigen_de_ergebnis_2.html")}
    stellen, abrufe = lauf(seiten, ["Sachbearbeitung", "Logistik"])
    assert abrufe == ["Sachbearbeitung", "Logistik"]
    titel = [s["title"] for s in stellen]
    assert "Disposition Logistik (m/w/d)" in titel, titel


def test_eine_anzeige_auf_zwei_ergebnisseiten_zaehlt_einmal(lauf):
    seiten = {"Sachbearbeitung": _seite("stellenanzeigen_de_ergebnis.html"),
              "Logistik": _seite("stellenanzeigen_de_ergebnis_2.html")}
    stellen, _ = lauf(seiten, ["Sachbearbeitung", "Logistik"])
    urls = [s["url"] for s in stellen]
    assert len(urls) == len(set(urls)) == 4, urls


def test_eine_fehlerseite_stoppt_die_uebrigen_begriffe_nicht(lauf):
    seiten = {"Logistik": _seite("stellenanzeigen_de_ergebnis_2.html")}
    stellen, abrufe = lauf(seiten, ["Kaputt", "Logistik"])
    assert abrufe == ["Kaputt", "Logistik"]
    assert len(stellen) == 2


# ====================================================== JSON-LD bleibt


def test_json_ld_wird_weiter_gelesen_und_nicht_doppelt_gezaehlt(lauf):
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type": "JobPosting", "title": "Sachbearbeitung Einkauf (m/w/d)",'
        ' "hiringOrganization": {"name": "Muster Handelsgesellschaft mbH"},'
        ' "jobLocation": {"address": {"addressLocality": "Musterstadt"}},'
        ' "url": "https://www.stellenanzeigen.de/job/sachbearbeitung-einkauf-m-w-d-musterstadt-10000001/",'
        ' "description": "Aufgaben und Anforderungen."}'
        '</script></head><body>'
        '<div><a href="/job/sachbearbeitung-einkauf-m-w-d-musterstadt-10000001/">'
        'Sachbearbeitung Einkauf (m/w/d)</a><span>Muster Handelsgesellschaft mbH</span>'
        '<span>Musterstadt</span></div></body></html>')
    stellen, _ = lauf({"Einkauf": html}, ["Einkauf"])
    assert len(stellen) == 1, stellen
    assert stellen[0]["description"] == "Aufgaben und Anforderungen."


# ====================================================== bekannte Grenze


def test_bekannt_gleicher_titel_ergibt_denselben_hash(lauf):
    """Bewusst NICHT in diesem Release behoben (B50): der Hash haengt nur
    am Titel. Ihn zu aendern wuerde jede bereits aussortierte Stelle dieser
    Quelle beim naechsten Fund als NEU anlegen — der Duplikat-Abgleich
    sieht nur aktive Stellen. Der Test haelt den Stand fest, damit die
    Aenderung eine bewusste bleibt."""
    stellen, _ = lauf({"Sachbearbeitung": _seite("stellenanzeigen_de_ergebnis.html")},
                      ["Sachbearbeitung"])
    assert stellen[0]["hash"] == stellen[2]["hash"]
    assert stellen[0]["url"] != stellen[2]["url"]


# ====================================================== Bestand heilt sich


@pytest.fixture
def db(tmp_path):
    import importlib
    import os

    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "sa1040.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.switch_profile(datenbank.create_profile("Stellenanzeigen"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


_TEXT = "Aufgaben und Anforderungen der Stelle. " * 5


def _gespeichert(db, url):
    return dict(db.connect().execute(
        "SELECT company, location, is_active, dismiss_reason FROM jobs WHERE url=?",
        (url,)).fetchone())


def test_ein_wiederfund_fuellt_firma_und_ort_der_gespeicherten_stelle(db):
    """Punkt 5 zum Teil: der alte Hash bleibt, also landet der Wiederfund
    auf seiner Zeile — und Firma und Ort kommen dort an."""
    alt = sa._stelle("Sachbearbeitung Einkauf (m/w/d)", "", "",
                     "https://www.stellenanzeigen.de/job/sachbearbeitung-einkauf-10000001/",
                     _TEXT)
    db.save_jobs([alt])
    assert _gespeichert(db, alt["url"])["company"] == "Unbekannt"

    neu = sa._stelle("Sachbearbeitung Einkauf (m/w/d)", "Muster Handelsgesellschaft mbH",
                     "Musterstadt", alt["url"], _TEXT)
    db.save_jobs([neu])
    zeile = _gespeichert(db, alt["url"])
    assert zeile["company"] == "Muster Handelsgesellschaft mbH"
    assert zeile["location"] == "Musterstadt"


def test_eine_aussortierte_stelle_bleibt_beim_wiederfund_aussortiert(db):
    """Der Grund, warum der Hash in diesem Release bleibt (B50)."""
    alt = sa._stelle("Sachbearbeitung Einkauf (m/w/d)", "", "",
                     "https://www.stellenanzeigen.de/job/sachbearbeitung-einkauf-10000001/",
                     _TEXT)
    db.save_jobs([alt])
    db.dismiss_job(db.resolve_job_hash(alt["hash"]), "zu_weit_entfernt")

    neu = sa._stelle("Sachbearbeitung Einkauf (m/w/d)", "Muster Handelsgesellschaft mbH",
                     "Musterstadt", alt["url"], _TEXT)
    db.save_jobs([neu])
    zeile = _gespeichert(db, alt["url"])
    assert zeile["is_active"] == 0, zeile
    assert zeile["company"] == "Muster Handelsgesellschaft mbH"
