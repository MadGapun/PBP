"""#1302: freelancermap - interner Lauf brach nach 90 s ab, Quelle fehlte im Browser-Handoff.

Gemessen am 08.11.2026 (wenige Abrufe gegen die echte Seite): die Suchseite antwortet in 0,2 bis 0,6 s und traegt
ihre Ergebnisliste als eingebettetes JSON. Das alte Einbettungsformat gab es nicht mehr; der Scraper holte deshalb
fuer jeden Suchbegriff bis zu 75 Detailseiten, und der Lauf brach an der Zeitgrenze ab - die 120 s aus der Tabelle
galten fuer Browser-Quellen nie, es blieben 90 s. Kein Live-HTTP in diesen Tests.

Testdaten fiktiv (Musterfirma GmbH). Datenbanken liegen in eigenen Temp-Ordnern (BA_DATA_DIR).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

import pytest

from bewerbungs_assistent.job_scraper import freelancermap as fm


def _projekt(nr: int, titel: str, *, remote: int | None = None, firma: str = "Musterfirma GmbH") -> dict:
    p = {
        "id": 9000000 + nr,
        "slug": f"musterprojekt-{nr}",
        "title": titel,
        "description": "<div><strong>Aufgaben</strong></div><ul><li>Stammdaten pflegen</li>"
                       "<li>PLM-Prozesse begleiten</li></ul>",
        "company": firma,
        "firstName": "Vorname",
        "lastName": "Nachname",
        "poster": {"company": firma, "firstName": "Vorname", "lastName": "Nachname"},
        "created": "2026-11-04T16:59:10+01:00",
        "city": "Musterstadt",
        "locations": [{"id": 1, "name": "Musterstadt"}],
        "links": {"project": f"/projekt/musterprojekt-{nr}"},
    }
    if remote is not None:
        p["projectContractType"] = {"type": "contracting", "remoteInPercent": remote}
    return p


def _seite(projekte: list | None) -> str:
    """Eine Suchseite wie am 08.11.2026 gemessen - mit oder ohne eingebettete Liste."""
    if projekte is None:
        return "<html><body><a href='/projekt/irgendwas-ohne-liste'>Ein Projekt ohne Liste</a></body></html>"
    daten = {"config": {}, "initialState": {"filter": {"query": "x"},
                                             "result": {"projects": projekte, "count": len(projekte)}}}
    return ("<html><head></head><body><div id='app'></div>"
            "<script type=\"application/json\" class=\"js-react-on-rails-component\" "
            "data-component-name=\"ProjectSearch\">" + json.dumps(daten) + "</script></body></html>")


class _Antwort:
    def __init__(self, status: int, text: str):
        self.status_code = status
        self.text = text
        self.headers = {"content-type": "text/html; charset=UTF-8"}


class _Client:
    def __init__(self, antworten: dict, abrufe: list):
        self.antworten, self.abrufe = antworten, abrufe

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, **_kw):
        self.abrufe.append(url)
        return self.antworten.get(url) or _Antwort(404, "")


@pytest.fixture
def netz(monkeypatch):
    """Ersetzt httpx.Client im Scraper; liefert die Liste der Abrufe."""
    abrufe: list = []
    antworten: dict = {}
    monkeypatch.setattr(fm.httpx, "Client", lambda *a, **k: _Client(antworten, abrufe))
    monkeypatch.setattr(fm.time, "sleep", lambda *_a, **_k: None)
    browser = []
    monkeypatch.setattr(fm, "_playwright_fallback", lambda urls, deadline=None: browser.append(urls) or [])
    return antworten, abrufe, browser


# ------------------------------------------------------------------ Leser der Suchseite

def test_die_eingebettete_liste_wird_gelesen():
    assert [p["title"] for p in fm.projekte_aus_suchseite(_seite([_projekt(1, "PLM Berater")]))] == ["PLM Berater"]
    assert fm.projekte_aus_suchseite(_seite([])) == [], "leere Suche ist eine Liste, keine Stoerung"
    assert fm.projekte_aus_suchseite(_seite(None)) is None, "ohne Datenblock: None (Aufbau geaendert)"


def test_ein_projekt_wird_zur_freelance_stelle_ohne_personennamen():
    job = fm.job_aus_projekt(_projekt(1, "SAP MDM Projektleitung", remote=100))
    assert job["employment_type"] == "freelance"
    assert job["remote_level"] == "remote"
    assert job["company"] == "Musterfirma GmbH"
    assert job["url"] == "https://www.freelancermap.de/projekt/musterprojekt-1"
    assert job["is_search_url"] is False
    assert job["veroeffentlicht_am"] == "2026-11-04"
    assert "Stammdaten pflegen" in job["description"]
    assert "Vorname" not in json.dumps(job) and "Nachname" not in json.dumps(job)
    assert fm.job_aus_projekt(_projekt(2, "Teilweise vor Ort", remote=40))["remote_level"] == "hybrid"


def test_die_suchadresse_ist_die_volltextsuche():
    assert fm.such_url("SAP MDM") == "https://www.freelancermap.de/projekte?query=SAP+MDM"


# ------------------------------------------------------------------ der Lauf

def test_eine_seite_je_begriff_keine_detailabrufe(netz):
    antworten, abrufe, browser = netz
    urls = [fm.such_url("PLM"), fm.such_url("SAP MDM")]
    antworten[urls[0]] = _Antwort(200, _seite([_projekt(1, "PLM Berater"), _projekt(2, "PLM Architekt")]))
    antworten[urls[1]] = _Antwort(200, _seite([_projekt(2, "PLM Architekt"), _projekt(3, "SAP MDM Lead")]))
    fortschritt: dict = {}
    jobs = fm.search_freelancermap({"keywords": {"freelancermap_urls": urls}, "_fortschritt": fortschritt})
    assert abrufe == urls, "je Begriff genau EIN Abruf - die Detailseiten waren die Ursache des Abbruchs"
    assert [j["title"] for j in jobs] == ["PLM Berater", "PLM Architekt", "SAP MDM Lead"]
    assert all(j["employment_type"] == "freelance" for j in jobs)
    assert fortschritt["fertig"] == 2 and not fortschritt["abgebrochen"]
    assert browser == []


def test_eine_leere_suche_startet_keinen_browser(netz):
    antworten, _abrufe, browser = netz
    url = fm.such_url("Gibtsnicht")
    antworten[url] = _Antwort(200, _seite([]))
    assert fm.search_freelancermap({"keywords": {"freelancermap_urls": [url]}}) == []
    assert browser == [], "vorher lief Playwright 30 s je Begriff, wenn die Suche schlicht nichts fand"


def test_das_zeitbudget_beendet_den_lauf_mit_dem_bisher_gefundenen(netz, monkeypatch):
    antworten, abrufe, _ = netz
    urls = [fm.such_url(f"Begriff {i}") for i in range(5)]
    for i, u in enumerate(urls):
        antworten[u] = _Antwort(200, _seite([_projekt(i, f"Projekt {i}")]))
    uhr = {"t": 0.0}

    def _monotonic():
        uhr["t"] += 10.0  # jeder Blick auf die Uhr kostet 10 s
        return uhr["t"]

    monkeypatch.setattr(fm.time, "monotonic", _monotonic)
    fortschritt: dict = {}
    jobs = fm.search_freelancermap({"keywords": {"freelancermap_urls": urls}, "_fortschritt": fortschritt,
                                    "_zeitbudget_s": 45})
    assert fortschritt["abgebrochen"] and fortschritt["grund"] == "zeitbudget"
    assert 0 < len(jobs) < 5 and len(abrufe) < 5
    from bewerbungs_assistent.services.scraper_classifier import lauf_grund
    assert lauf_grund(fortschritt).startswith(f"teilweise: {fortschritt['fertig']} von 5 Suchbegriffen")


def test_gesperrte_antworten_beenden_den_lauf(netz):
    antworten, abrufe, browser = netz
    urls = [fm.such_url(f"B{i}") for i in range(4)]
    for u in urls:
        antworten[u] = _Antwort(429, "zu viele")
    fortschritt: dict = {}
    assert fm.search_freelancermap({"keywords": {"freelancermap_urls": urls}, "_fortschritt": fortschritt}) == []
    assert len(abrufe) == fm.SPERREN_BIS_ABBRUCH, "nach zwei Sperren nicht weiter anklopfen"
    assert fortschritt["grund"] == "gesperrt" and browser == []
    from bewerbungs_assistent.services.scraper_classifier import lauf_grund
    assert "gesperrt: 2 Antwort(en) HTTP 429" in lauf_grund(fortschritt)


def test_seite_ohne_liste_nennt_den_aufbau(netz):
    antworten, _abrufe, _ = netz
    url = fm.such_url("PLM")
    antworten[url] = _Antwort(200, _seite(None))
    fortschritt: dict = {}
    fm.search_freelancermap({"keywords": {"freelancermap_urls": [url]}, "_fortschritt": fortschritt})
    from bewerbungs_assistent.services.scraper_classifier import lauf_grund
    assert "ohne Ergebnisliste" in lauf_grund(fortschritt)


def test_lauf_grund_bei_der_zeitgrenze():
    from bewerbungs_assistent.services.scraper_classifier import lauf_grund
    assert lauf_grund({"begriffe": 14, "fertig": 3, "langsamste_s": 0.6}, 120) == (
        "Zeitgrenze 120s erreicht nach 3 von 14 Suchbegriffen; langsamste Antwort 0.6s")
    assert lauf_grund({}, 120) == "Zeitgrenze 120s erreicht, bevor eine Suchseite fertig war"
    assert lauf_grund({"begriffe": 2, "fertig": 2}) == ""


# ------------------------------------------------------------------ Suchlauf: Zeitgrenze und Grund

@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path))
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    d.set_search_criteria("keywords_muss", ["Stammdaten"])
    import bewerbungs_assistent.dashboard as dash
    dash._db = d
    from bewerbungs_assistent.services import netz_pruefung
    monkeypatch.setattr(netz_pruefung, "erreichbar", lambda *a, **k: True)
    yield d
    d.close()


def _health(db, name):
    return next((h for h in db.get_scraper_health() if h["scraper_name"] == name), None)


def test_der_suchlauf_gibt_freelancermap_120_s_und_nennt_den_grund(db, monkeypatch):
    """Vorher galt fuer Browser-Quellen "StepStone 180 s, sonst 90 s" - die 120 s der Tabelle nie."""
    import bewerbungs_assistent.job_scraper as js
    from concurrent.futures import TimeoutError as FuturesTimeoutError
    gewartet: list = []

    class _Zukunft:
        def result(self, timeout=None):
            gewartet.append(timeout)
            raise FuturesTimeoutError()

    class _Ausfuehrer:
        def __init__(self, *a, **k):
            pass

        def submit(self, fn, *args):
            fn(*args)  # der Scraper laeuft an und haelt seinen Fortschritt fest
            return _Zukunft()

        def shutdown(self, *a, **k):
            pass

    def _scraper(params):
        params["_fortschritt"].update({"begriffe": 14, "fertig": 3, "langsamste_s": 0.5})
        return []

    monkeypatch.setattr(js, "ThreadPoolExecutor", _Ausfuehrer)
    monkeypatch.setattr(fm, "search_freelancermap", _scraper)
    job_id = db.create_background_job("jobsuche", {})
    js.run_search(db, job_id, {"quellen": ["freelancermap"], "keywords": ["Stammdaten"]})
    assert gewartet == [120]
    status = db.get_background_job(job_id)["result"]["quellen_status"]["freelancermap"]
    assert status["status"] == "timeout"
    assert status["detail"].startswith("Zeitgrenze 120s erreicht nach 3 von 14 Suchbegriffen")
    assert "Zeitgrenze 120s erreicht nach 3 von 14" in (_health(db, "freelancermap")["last_status_detail"] or "")


def test_ein_teilweiser_lauf_speichert_freelance_und_nennt_es(db, monkeypatch):
    import bewerbungs_assistent.job_scraper as js

    def _scraper(params):
        params["_fortschritt"].update({"begriffe": 9, "fertig": 4, "grund": "zeitbudget", "abgebrochen": True})
        return [fm.job_aus_projekt(_projekt(1, "Stammdaten Management Projekt", remote=100))]

    monkeypatch.setattr(fm, "search_freelancermap", _scraper)
    job_id = db.create_background_job("jobsuche", {})
    js.run_search(db, job_id, {"quellen": ["freelancermap"], "keywords": ["Stammdaten"]})
    status = db.get_background_job(job_id)["result"]["quellen_status"]["freelancermap"]
    assert status["status"] == "ok" and status["detail"].startswith("teilweise: 4 von 9")
    zeile = db.connect().execute("SELECT employment_type FROM jobs WHERE source='freelancermap'").fetchone()
    assert zeile is not None and zeile["employment_type"] == "freelance"


# ------------------------------------------------------------------ Health-Check

def test_die_probe_liest_die_liste_wie_der_scraper(monkeypatch):
    from bewerbungs_assistent.job_scraper import health
    seiten = {"jetzt": _seite([_projekt(1, "A"), _projekt(2, "B")])}

    class _Sitzung:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            assert url.startswith("https://www.freelancermap.de/projekte?query=")
            return _Antwort(200, seiten["jetzt"])

    monkeypatch.setattr(health, "make_session", lambda **k: _Sitzung())
    erg = health.check_source("freelancermap")
    assert (erg["reachable"], erg["inhalt"], erg["treffer"]) == (True, "ok", 2)
    seiten["jetzt"] = _seite(None)
    erg = health.check_source("freelancermap")
    assert erg["inhalt"] == "verdaechtig" and "Seitenaufbau" in erg["inhalt_hinweis"]
    assert health._PROBE_EXTRA_HEADERS["freelancermap"]["User-Agent"] == fm._HEADERS["User-Agent"]


def _mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1302")
    register_all(mcp, db, logging.getLogger("test.1302"))
    return mcp


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def test_der_health_check_nennt_den_grund_des_letzten_laufs(db, monkeypatch):
    from bewerbungs_assistent.job_scraper import health
    db.update_scraper_health("freelancermap", "timeout", time_s=120,
                             detail="Zeitgrenze 120s erreicht nach 3 von 14 Suchbegriffen",
                             error_class="server_weg")
    monkeypatch.setattr(health, "check_source", lambda s, *a, **k: {
        "source": s, "reachable": True, "http_status": 200, "latency_ms": 500, "inhalt": "ok", "treffer": 20})
    erg = _call(_mcp(db), "quellen_health_check", {"quellen": ["freelancermap"], "parallel": False})
    r = erg["results"][0]
    assert "Zeitgrenze 120s erreicht nach 3 von 14" in r["letzter_lauf"]
    assert r["einordnung"].startswith("Die Seite antwortet und liefert Stellen")


# ------------------------------------------------------------------ Browser-Handoff

def test_ausgefallen_steht_im_auftrag_mit_den_suchkriterien(db):
    from bewerbungs_assistent.services import browser_handoff as bh
    assert not [e for e in bh.browser_quellen(db, auswahl=["freelancermap"]) if e["key"] == "freelancermap"], \
        "solange der interne Lauf liefert, steht freelancermap nicht im Auftrag"
    db.update_scraper_health("freelancermap", "timeout", time_s=120, detail="Zeitgrenze 120s erreicht",
                             error_class="server_weg")
    eintraege = bh.browser_quellen(db, auswahl=["freelancermap", "bundesagentur"])
    e = next(x for x in eintraege if x["key"] == "freelancermap")
    assert e["art"] == bh.INTERN_AUSGEFALLEN
    assert e["suchbegriffe"] == ["Stammdaten"] and e["suchbegriffe_herkunft"] == "suchkriterien"
    assert e["suchprofil_vorhanden"] is False
    assert e["werkzeug"] == "quelle_handoff('freelancermap', <Suchbegriff>)"
    assert "bundesagentur" not in {x["key"] for x in eintraege}, "ohne Such-URL kein Browser-Auftrag"
    text = bh.prompt(eintraege)
    assert "Freelancermap" in text and "Suchbegriffe aus meinen Suchkriterien" in text
    assert "Zeitgrenze 120s erreicht" in text
    assert bh.MARKE_IM_ZWEIFEL in text
    # Liefert der naechste Lauf wieder, faellt die Quelle von selbst heraus.
    db.update_scraper_health("freelancermap", "ok", count=12, time_s=20)
    assert not [x for x in bh.browser_quellen(db, auswahl=["freelancermap"]) if x["key"] == "freelancermap"]


def test_ein_eigenes_suchprofil_gilt_vor_den_suchkriterien(db):
    from bewerbungs_assistent.services import browser_handoff as bh
    from bewerbungs_assistent.job_scraper import build_search_keywords
    assert build_search_keywords(db)["freelancermap_urls"] == [fm.such_url("Stammdaten")], \
        "ohne Suchprofil sucht die Quelle mit den MUSS-Begriffen - nicht ohne Begriffe"
    db.update_portal_search_profile("freelancermap", primaere_suchen=[{"keywords": "SAP MDM"}, "PLM"])
    assert build_search_keywords(db)["freelancermap_urls"] == [fm.such_url("SAP MDM"), fm.such_url("PLM")]
    db.update_scraper_health("freelancermap", "error", error_class="kaputt", detail="x")
    e = next(x for x in bh.browser_quellen(db, auswahl=["freelancermap"]) if x["key"] == "freelancermap")
    assert e["suchbegriffe"] == ["SAP MDM", "PLM"] and e["suchprofil_vorhanden"] is True


def test_suchprofil_lesen_sagt_womit_der_interne_lauf_sucht(db):
    erg = _call(_mcp(db), "suchprofil_lesen", {"portal": "freelancermap"})
    assert erg["gespeichert"] is False
    assert "MUSS" in erg["interner_lauf_sucht_mit"]
    assert "interner_lauf_sucht_mit" not in _call(_mcp(db), "suchprofil_lesen", {"portal": "xing"})


def test_quelle_handoff_kennt_freelancermap():
    from bewerbungs_assistent.job_scraper.handoff import build_handoff
    paket = build_handoff("freelancermap", "SAP MDM")
    assert paket["status"] == "handoff"
    assert paket["url"] == fm.such_url("SAP MDM")


def test_jobsuche_starten_nennt_die_ausgefallene_quelle(db, monkeypatch):
    import threading
    import bewerbungs_assistent.job_scraper as js
    from bewerbungs_assistent.services import jobsuche_start
    monkeypatch.setattr(js, "run_search", lambda _db, job_id, _p: _db.update_background_job(
        job_id, "fertig", progress=100, result={"total": 0}))
    db.update_scraper_health("freelancermap", "timeout", time_s=120, detail="Zeitgrenze 120s erreicht",
                             error_class="server_weg")
    erg = jobsuche_start.starten(db, quellen=["freelancermap", "bundesagentur"], herkunft="claude")
    for t in threading.enumerate():
        if t.name.startswith("pbp-jobsuche"):
            t.join(timeout=10)
    assert erg["status"] == "gestartet", erg
    assert "freelancermap" in erg["quellen"], "die Quelle laeuft intern weiter"
    assert "quelle_handoff('freelancermap'" in erg["manuelle_quellen"]["freelancermap"]
