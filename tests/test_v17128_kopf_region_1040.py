"""Tests fuer v1.7.128 — #1040, #1041, #1042: Firma und Ort aus der
Detailseite, und die Region bei Jobware und ingenieur.de.

Die Detailseiten der drei Boersen tragen ein `JobPosting` mit
`hiringOrganization` und `jobLocation`. Das Nachladen holte die Seite und
uebernahm nur den Text — Stellen mit "Unbekannt" und ohne Ort blieben
so, bis ein Suchlauf sie zufaellig wiederfand. Alle Firmen und Orte hier
sind erfunden.
"""
import importlib
import json
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


def _detailseite(firma="Musterwerk Nord GmbH", ort="Musterstadt", liste=False):
    posting = {"@context": "https://schema.org", "@type": "JobPosting",
               "title": "Fachrolle", "description": "<p>Aufgaben und Profil.</p>",
               "hiringOrganization": {"@type": "Organization", "name": firma},
               "jobLocation": {"@type": "Place", "address": {
                   "@type": "PostalAddress", "addressLocality": ort}}}
    if liste:
        posting["jobLocation"] = [posting["jobLocation"],
                                  {"address": {"addressLocality": "Zweitort"}}]
    return ("<html><head><script type=\"application/ld+json\">"
            + json.dumps(posting) + "</script></head><body><main>"
            + "<p>Ein ausfuehrlicher Anzeigentext mit Aufgaben und Profil.</p>" * 5
            + "</main></body></html>")


class _Antwort:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


class _Client:
    def __init__(self, text):
        self._text = text

    def get(self, url, **kw):
        return _Antwort(self._text)


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


@pytest.fixture
def ohne_netz(monkeypatch):
    """Geocoding ohne Nominatim: ein fester Punkt fuer jeden Ort."""
    from bewerbungs_assistent.services import geocoding_service as geo
    monkeypatch.setattr(geo, "geocode_location", lambda ort: (53.55, 10.05))
    monkeypatch.setattr(geo, "get_user_coordinates", lambda db: (53.50, 10.00))


def _stelle(db, company="Unbekannt", location="", description=""):
    db.save_jobs([{"hash": "kopf0001", "title": "Fachrolle", "company": company,
                   "location": location, "score": 5, "source": "stellenanzeigen_de",
                   "url": "https://example.org/job/kopf0001",
                   "description": description}])
    return "kopf0001"


# --- Firma und Ort aus dem JobPosting -------------------------------------

def test_kopf_aus_html_liest_firma_und_ort():
    from bewerbungs_assistent.services import nachladen
    assert nachladen.kopf_aus_html(_detailseite()) == {
        "firma": "Musterwerk Nord GmbH", "ort": "Musterstadt"}


def test_kopf_aus_html_nimmt_den_ersten_ort_und_ignoriert_platzhalter():
    from bewerbungs_assistent.services import nachladen
    kopf = nachladen.kopf_aus_html(_detailseite(firma="Unbekannt", liste=True))
    assert kopf == {"ort": "Musterstadt"}
    assert nachladen.kopf_aus_html("<html><body>ohne JSON-LD</body></html>") == {}


def test_beschreibung_holen_bringt_den_kopf_mit():
    from bewerbungs_assistent.services import nachladen
    befund = nachladen.beschreibung_holen(
        "https://example.org/job/1", _Client(_detailseite()))
    assert befund.erfolg
    assert befund.kopf["firma"] == "Musterwerk Nord GmbH"


def test_nachladen_fuellt_firma_ort_und_entfernung(db, ohne_netz):
    from bewerbungs_assistent.services import nachladen
    h = _stelle(db)
    ergebnis = nachladen.text_uebernehmen(
        db, h, "Ein vollstaendiger Anzeigentext. " * 10,
        kopf={"firma": "Musterwerk Nord GmbH", "ort": "Musterstadt"})
    job = db.get_job(h)
    assert job["company"] == "Musterwerk Nord GmbH"
    assert job["location"] == "Musterstadt"
    assert job["distance_km"] is not None and job["distance_km"] < 10
    assert set(ergebnis["kopf"]) == {"company", "location", "distance_km"}
    assert ergebnis["score"] is not None   # danach neu bewertet


def test_nachladen_ueberschreibt_nie(db, ohne_netz):
    from bewerbungs_assistent.services import nachladen
    h = _stelle(db, company="Echte Firma AG", location="Altort")
    ergebnis = nachladen.text_uebernehmen(
        db, h, "Ein vollstaendiger Anzeigentext. " * 10,
        kopf={"firma": "Andere GmbH", "ort": "Anderswo"})
    job = db.get_job(h)
    assert (job["company"], job["location"]) == ("Echte Firma AG", "Altort")
    assert ergebnis["kopf"] == []


def test_mengenweg_zieht_nur_den_kopf_nach(db, ohne_netz, monkeypatch):
    """Der Text ist schon vollstaendig — nur Firma und Ort fehlen."""
    from bewerbungs_assistent.services import nachladen
    from bewerbungs_assistent.tools import jobs as job_tools
    text = "Ein vollstaendiger Anzeigentext mit allem Noetigen.\n" * 12
    h = _stelle(db, description=text)
    # Genau so lang wie der gespeicherte Text: verglichen wird nach
    # `strip()`, ein Zeichen mehr haette den Textweg genommen und den
    # Kopf-Zweig gar nicht erreicht (in der Gegenprobe so geschehen).
    monkeypatch.setattr(nachladen, "beschreibung_holen", lambda *a, **k: nachladen.Befund(
        status=nachladen.GELESEN, text=text.strip(), http_status=200, quelle="html",
        kopf={"firma": "Musterwerk Nord GmbH", "ort": "Musterstadt"}))

    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    job_tools.register(_Sammler(), db, logging.getLogger("test"))
    lauf = gesammelt["beschreibungen_nachladen_bestand"]
    vorschau = lauf(umfang="ohne_firma_ort")
    assert vorschau["betroffen"] == 1
    erg = lauf(umfang="ohne_firma_ort", nur_zaehlen=False)
    assert erg["kopf_ergaenzt"] == 1
    assert erg["geheilt"] == 1
    assert erg["gewachsen"] == []          # der Text blieb, wie er war
    job = db.get_job(h)
    assert job["company"] == "Musterwerk Nord GmbH"
    assert job["description"].strip() == text.strip()


def test_unbekannter_umfang_nennt_den_neuen(db):
    from bewerbungs_assistent.tools import jobs as job_tools
    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    job_tools.register(_Sammler(), db, logging.getLogger("test"))
    antwort = gesammelt["beschreibungen_nachladen_bestand"](umfang="quatsch")
    assert "ohne_firma_ort" in antwort["grund"]


# --- Region ---------------------------------------------------------------

class _AdapterClient:
    aufrufe: list = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None, **k):
        _AdapterClient.aufrufe.append(dict(params or {}))
        return _Antwort("<html>" + "x" * 12000 + "</html>")


@pytest.fixture
def adapterclient(monkeypatch):
    import time as _time
    _AdapterClient.aufrufe = []
    monkeypatch.setattr(_time, "sleep", lambda *a: None)
    return _AdapterClient


@pytest.mark.parametrize("modul", ["jobware", "ingenieur_de"])
def test_region_erst_regional_dann_bundesweit(modul, adapterclient, monkeypatch):
    mod = importlib.import_module(f"bewerbungs_assistent.job_scraper.{modul}")
    monkeypatch.setattr(mod.httpx, "Client", adapterclient)
    suche = getattr(mod, f"search_{modul}")
    suche({"keywords": {"general": ["Fachrolle"], "regionen": ["Musterstadt"]}})
    orte = [a.get("l", "") for a in adapterclient.aufrufe]
    assert orte[0] == "Musterstadt"
    assert orte[1] in ("Deutschland", "")      # bundesweit bleibt dabei


@pytest.mark.parametrize("modul", ["jobware", "ingenieur_de"])
def test_ohne_region_wie_bisher(modul, adapterclient, monkeypatch):
    mod = importlib.import_module(f"bewerbungs_assistent.job_scraper.{modul}")
    monkeypatch.setattr(mod.httpx, "Client", adapterclient)
    getattr(mod, f"search_{modul}")({"keywords": {"general": ["Fachrolle"],
                                                   "regionen": ["Deutschland"]}})
    assert len(adapterclient.aufrufe) == 1
    assert adapterclient.aufrufe[0].get("l", "Deutschland") == "Deutschland"


def test_einzelwerkzeug_fuellt_den_kopf(db, ohne_netz, monkeypatch):
    from bewerbungs_assistent.services import nachladen
    from bewerbungs_assistent.tools import jobs as job_tools
    h = _stelle(db)
    monkeypatch.setattr(nachladen, "beschreibung_holen", lambda *a, **k: nachladen.Befund(
        status=nachladen.GELESEN, text="Ein vollstaendiger Anzeigentext. " * 10,
        http_status=200, quelle="html",
        kopf={"firma": "Musterwerk Nord GmbH", "ort": "Musterstadt"}))
    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    job_tools.register(_Sammler(), db, logging.getLogger("test"))
    antwort = gesammelt["stellenbeschreibung_nachladen"](h)
    assert antwort["status"] == "ok", antwort
    assert db.get_job(h)["company"] == "Musterwerk Nord GmbH"


def test_jeder_aufrufer_reicht_den_kopf_weiter():
    """Guard: ein Nachlade-Weg ohne `kopf=` liesse Firma und Ort wieder
    liegen — genau die Bauform, aus der #1040 Punkt 2 entstand. Gelesen
    wird der Syntaxbaum: ein Muster ueber den Text endet an der ersten
    Klammer eines Arguments (v1.7.110 MERKE 6)."""
    import ast
    src = _repo() / "src" / "bewerbungs_assistent"
    fundstellen = []
    for datei in src.rglob("*.py"):
        baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            name = getattr(knoten.func, "attr", None) or getattr(knoten.func, "id", None)
            if name == "text_uebernehmen":
                fundstellen.append((datei.name, knoten.lineno,
                                    any(k.arg == "kopf" for k in knoten.keywords)))
    assert len(fundstellen) >= 4, fundstellen
    assert all(ok for *_, ok in fundstellen), fundstellen
