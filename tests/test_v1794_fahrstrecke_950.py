"""Tests fuer #950 Stufe 2: echte Fahrstrecke und Fahrzeit (AK 3 bis 6).

v1.7.50 hat die Luftlinie beschriftet und eine Schaetzung danebengestellt.
Hier kommt die echte Route: mit einem Schluessel von OpenRouteService
tragen Stellen Fahrstrecke und Fahrzeit, und die Preisrechnung nimmt die
Fahrstrecke. Ohne Schluessel aendert sich nichts.

Kein Test geht ins Netz — der Abruf wird ersetzt, und jede Datenbank
liegt im Temp-Verzeichnis.
"""
import asyncio
import importlib
import inspect
import json
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import entfernung  # noqa: E402
from bewerbungs_assistent.services import routing  # noqa: E402

SCHLUESSEL = "5b3ce3597851110001cf6248aaaabbbbccccddddeeeeffff0000"
START = (53.5511, 9.9937)
TEXT = "Ausfuehrliche Stellenbeschreibung mit genug Inhalt. " * 3


class _Antwort:
    def __init__(self, status=200, daten=None):
        self.status_code = status
        self._daten = daten or {}

    def json(self):
        return self._daten


class _Client:
    """Zaehlt Anfragen und antwortet mit fester Strecke je Ziel."""

    def __init__(self, status=200, km=390.4, sekunden=14100, fehler=None):
        self.anfragen = []
        self.status = status
        self.km = km
        self.sekunden = sekunden
        self.fehler = fehler

    def post(self, url, json=None, headers=None):
        self.anfragen.append({"url": url, "json": json, "headers": headers})
        if self.fehler:
            raise self.fehler
        ziele = len(json["destinations"])
        return _Antwort(self.status, {
            "distances": [[self.km] * ziele],
            "durations": [[self.sekunden] * ziele],
        })


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "route.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.switch_profile(datenbank.create_profile("Route"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _stelle(nr=1, **extra):
    job = {
        "hash": f"r950{nr:03d}", "title": f"Rolle {nr}",
        "company": f"Firma {nr}", "url": f"https://example.com/950/{nr}",
        "source": "manuell", "_manual_entry": True, "description": TEXT,
        "score": 10.0, "location": "Musterstadt", "distance_km": 271.5,
        "lat": 51.3127, "lon": 9.4797,
    }
    job.update(extra)
    return job


# ======================================================= entfernung.py


def test_ak6_preis_km_nimmt_die_fahrstrecke_sobald_sie_vorliegt():
    assert entfernung.preis_km({"distance_km": 271.5}) == 271.5
    assert entfernung.preis_km(
        {"distance_km": 271.5, "fahrstrecke_km": 390.4}) == 390.4


def test_eine_kaputte_fahrstrecke_ist_kein_beleg():
    assert entfernung.preis_km(
        {"distance_km": 271.5, "fahrstrecke_km": 0}) == 271.5
    assert entfernung.preis_km(
        {"distance_km": 12, "fahrstrecke_km": "kaputt"}) == 12
    assert entfernung.preis_km({}) is None
    assert entfernung.preis_km(None) is None


def test_fahrzeit_text():
    assert entfernung.fahrzeit_text(45) == "45 Min"
    assert entfernung.fahrzeit_text(60) == "1 Std"
    assert entfernung.fahrzeit_text(235) == "3 Std 55 Min"
    assert entfernung.fahrzeit_text(None) == ""


def test_ak3_befund_nennt_fahrstrecke_fahrzeit_und_luftlinie():
    befund = entfernung.befund({"distance_km": 271.5, "fahrstrecke_km": 390.4,
                                "fahrzeit_min": 235,
                                "route_quelle": "openrouteservice"})
    assert befund["entfernung_art"] == entfernung.ART_FAHRSTRECKE
    assert befund["entfernung_km"] == 390.4
    assert befund["luftlinie_km"] == 271.5
    assert befund["fahrzeit_text"] == "3 Std 55 Min"
    assert befund["entfernung_text"] == (
        "390.4 km Fahrstrecke, 3 Std 55 Min (271.5 km Luftlinie)")
    assert "fahrstrecke_km_geschaetzt" not in befund, \
        "eine berechnete Route braucht keine Schaetzung daneben"


def test_ak5_ohne_route_bleibt_der_befund_von_v1750():
    """Die Stelle als dict und die Zahl allein liefern dasselbe."""
    assert entfernung.befund({"distance_km": 271.5}) == entfernung.befund(271.5)
    assert entfernung.befund(271.5)["entfernung_art"] == entfernung.ART_LUFTLINIE
    assert entfernung.befund({"distance_km": None}) == {}


# ========================================================= routing.py


def test_ak5_ohne_schluessel_fragt_niemand_und_nichts_aendert_sich(db):
    client = _Client()
    job = _stelle()
    ergebnis = routing.fuer_stellen(db, [job], START, client=client)
    assert ergebnis["befund"] == routing.KEIN_SCHLUESSEL
    assert client.anfragen == []
    assert "fahrstrecke_km" not in job


def test_ak3_route_wird_gesetzt_und_die_anfrage_ist_korrekt(db):
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    client = _Client()
    job = _stelle()
    ergebnis = routing.fuer_stellen(db, [job], START, client=client)
    assert ergebnis == {"berechnet": 1, "ohne_route": 0, "befund": routing.OK}
    assert job["fahrstrecke_km"] == 390.4
    assert job["fahrzeit_min"] == 235
    assert job["route_quelle"] == routing.ANBIETER
    anfrage = client.anfragen[0]
    # Die Schnittstelle erwartet [lon, lat] — vertauscht laege das Ziel
    # im Indischen Ozean, und die Antwort waere trotzdem HTTP 200.
    assert anfrage["json"]["locations"][0] == [START[1], START[0]]
    assert anfrage["json"]["locations"][1] == [9.4797, 51.3127]
    assert anfrage["headers"]["Authorization"] == SCHLUESSEL


def test_ak4_zwischenspeicher_spart_die_zweite_anfrage(db):
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    client = _Client()
    routing.fuer_stellen(db, [_stelle(1)], START, client=client)
    zweite = _stelle(2)  # derselbe Ort, andere Stelle
    routing.fuer_stellen(db, [zweite], START, client=client)
    assert len(client.anfragen) == 1
    assert zweite["fahrstrecke_km"] == 390.4
    assert routing.zwischengespeichert(db) == 1


def test_viele_stellen_am_selben_ort_kosten_ein_ziel(db):
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    client = _Client()
    jobs = [_stelle(i) for i in range(5)]
    routing.fuer_stellen(db, jobs, START, client=client)
    assert len(client.anfragen) == 1
    assert len(client.anfragen[0]["json"]["destinations"]) == 1
    assert all(j["fahrstrecke_km"] == 390.4 for j in jobs)


def test_ein_ziel_ohne_route_wird_gemerkt_und_nicht_erneut_gefragt(db):
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    client = _Client(km=None, sekunden=None)
    job = _stelle()
    assert routing.fuer_stellen(db, [job], START, client=client)["ohne_route"] == 1
    routing.fuer_stellen(db, [_stelle(2)], START, client=client)
    assert len(client.anfragen) == 1
    assert "fahrstrecke_km" not in job


@pytest.mark.parametrize("status, befund", [
    (401, routing.SCHLUESSEL_ABGELEHNT),
    (403, routing.SCHLUESSEL_ABGELEHNT),
    (429, routing.KONTINGENT),
    (500, routing.NICHT_ERREICHBAR),
])
def test_fehlschlaege_werden_benannt_und_nicht_zwischengespeichert(
        db, status, befund):
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    job = _stelle()
    ergebnis = routing.fuer_stellen(db, [job], START,
                                    client=_Client(status=status))
    assert ergebnis["befund"] == befund
    assert "fahrstrecke_km" not in job
    assert routing.zwischengespeichert(db) == 0, \
        "ein Fehlschlag darf beim naechsten Lauf nicht als 'keine Route' gelten"


def test_ein_netzfehler_ist_nicht_erreichbar(db):
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    ergebnis = routing.fuer_stellen(
        db, [_stelle()], START, client=_Client(fehler=TimeoutError("weg")))
    assert ergebnis["befund"] == routing.NICHT_ERREICHBAR


def test_die_tagesgrenze_haelt_das_kontingent_ein(db):
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    db.set_setting(routing.EINSTELLUNG_ZAEHLER,
                   {"datum": routing._heute(), "anzahl": routing.TAGESGRENZE})
    client = _Client()
    ergebnis = routing.fuer_stellen(db, [_stelle()], START, client=client)
    assert ergebnis["befund"] == routing.KONTINGENT
    assert client.anfragen == []


def test_der_zaehler_beginnt_jeden_tag_neu(db):
    db.set_setting(routing.EINSTELLUNG_ZAEHLER,
                   {"datum": "2000-01-01", "anzahl": routing.TAGESGRENZE})
    assert routing.anfragen_heute(db) == 0


def test_schluessel_wird_erst_nach_erfolgreicher_probe_gespeichert(db):
    abgelehnt = routing.schluessel_setzen(db, SCHLUESSEL,
                                          client=_Client(status=401))
    assert abgelehnt["befund"] == routing.SCHLUESSEL_ABGELEHNT
    assert not routing.konfiguriert(db)
    ok = routing.schluessel_setzen(db, SCHLUESSEL, client=_Client())
    assert ok["status"] == "eingerichtet"
    assert routing.schluessel(db) == SCHLUESSEL


def test_offensichtlich_kein_schluessel_kostet_keine_anfrage(db):
    client = _Client()
    for unsinn in ("", "kurz", "mit leerzeichen darin und lang genug"):
        assert routing.schluessel_setzen(db, unsinn, client=client).get("fehler")
    assert client.anfragen == []


def test_der_status_nennt_den_schluessel_nie(db):
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    stand = routing.status(db)
    assert stand["konfiguriert"] is True
    assert SCHLUESSEL not in json.dumps(stand)
    assert "Koordinaten" in stand["datenweitergabe"]


def test_entfernen_setzt_zurueck(db):
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    routing.schluessel_entfernen(db)
    assert not routing.konfiguriert(db)


# ========================================================= Datenbank


def _gespeichert(db, nr=1):
    return dict(db.connect().execute(
        "SELECT hash, distance_km, fahrstrecke_km, fahrzeit_min, route_quelle, "
        "lat, lon FROM jobs WHERE hash LIKE ?", (f"%r950{nr:03d}",)).fetchone())


def test_save_jobs_schreibt_die_route(db):
    db.save_jobs([_stelle(fahrstrecke_km=390.4, fahrzeit_min=235,
                          route_quelle="openrouteservice")])
    zeile = _gespeichert(db)
    assert zeile["fahrstrecke_km"] == 390.4
    assert zeile["distance_km"] == 271.5, "die Luftlinie bleibt eine Messung"


def test_ein_erneuter_suchlauf_ohne_route_loescht_sie_nicht(db):
    """DoD 8e: die Route kostet eine Anfrage, REPLACE darf sie nicht nullen."""
    db.save_jobs([_stelle(fahrstrecke_km=390.4, fahrzeit_min=235,
                          route_quelle="openrouteservice")])
    db.save_jobs([_stelle()])
    assert _gespeichert(db)["fahrstrecke_km"] == 390.4


def test_eine_neue_route_ersetzt_die_bewahrte(db):
    db.save_jobs([_stelle(fahrstrecke_km=390.4, fahrzeit_min=235,
                          route_quelle="openrouteservice")])
    db.save_jobs([_stelle(fahrstrecke_km=401.0, fahrzeit_min=240,
                          route_quelle="openrouteservice")])
    assert _gespeichert(db)["fahrstrecke_km"] == 401.0


def test_set_fahrstrecke_ohne_wert_ueberschreibt_nichts(db):
    db.save_jobs([_stelle(fahrstrecke_km=390.4, fahrzeit_min=235)])
    hash_ = _gespeichert(db)["hash"]
    assert db.set_fahrstrecke(hash_) is False
    assert db.set_fahrstrecke(hash_, None, lat=51.0, lon=9.0) is True
    zeile = _gespeichert(db)
    assert zeile["fahrstrecke_km"] == 390.4 and zeile["lat"] == 51.0


def test_routen_cache_gehoert_zu_einem_loeschbereich():
    from bewerbungs_assistent.services import loeschbereiche

    zugeordnet = {t for tabellen in loeschbereiche.BEREICHE.values()
                  for t in tabellen}
    assert "routen_cache" in zugeordnet, \
        "die Tabelle traegt die Koordinaten des Wohnorts (#1025)"


# ================================================== AK 6: eine Zahl


def _quelltext(obj) -> str:
    return inspect.getsource(obj)


@pytest.mark.parametrize("pfad", [
    "bewerbungs_assistent.job_scraper:calculate_score",
    "bewerbungs_assistent.job_scraper:fit_analyse",
    "bewerbungs_assistent.services.scoring_service:apply_scoring_adjustments",
    "bewerbungs_assistent.services.stellen_automatik:_zahl_widerspricht",
])
def test_ak6_jeder_preisweg_fragt_preis_km(pfad):
    """Vier Leser mit eigener Wahl waeren #963 zum wiederholten Mal."""
    modul, name = pfad.split(":")
    code = _quelltext(getattr(importlib.import_module(modul), name))
    assert "preis_km(" in code
    assert 'job.get("distance_km")' not in code


def test_ak6_die_fahrstrecke_kostet_im_scoring_regler_mehr(db):
    from bewerbungs_assistent.services.scoring_service import (
        apply_scoring_adjustments)

    nah = apply_scoring_adjustments({"distance_km": 20}, 50, db)
    weit = apply_scoring_adjustments(
        {"distance_km": 20, "fahrstrecke_km": 400}, 50, db)
    assert weit["final_score"] < nah["final_score"]


# ================================================ Aufrufer (DoD 8c)


def test_der_suchlauf_rechnet_die_route_nach_allen_filtern_vor_dem_speichern():
    """Vor den Filtern kostete die Route Kontingent fuer verworfene Stellen,
    nach dem Speichern kaeme sie nicht mehr in die Datenbank."""
    from bewerbungs_assistent import job_scraper

    code = inspect.getsource(job_scraper)
    route = code.index("_routing.fuer_stellen(db, unique")
    assert code.index("_automatik(db, unique") < route
    assert route < code.index("save_stats = db.save_jobs(unique)")


def test_die_manuelle_anlage_setzt_koordinaten_und_route():
    from bewerbungs_assistent.tools import jobs

    code = inspect.getsource(jobs)
    anlage = code[code.index("def stelle_manuell_anlegen("):]
    anlage = anlage[:anlage.index("@mcp.tool()")]
    assert 'job["lat"], job["lon"] = _koord' in anlage
    assert "_routing.fuer_stellen(db, [job]" in anlage


# ============================================== MCP-Werkzeug


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


def test_werkzeug_status_ohne_schluessel_zeigt_den_weg(db):
    antwort = _call(_mcp(db), "fahrstrecken_verwalten", {})
    assert antwort["konfiguriert"] is False
    assert "Dashboard" in antwort["naechster_schritt"]


def test_werkzeug_nimmt_keinen_schluessel_entgegen():
    """Ein Schluessel, der durch den Chat geht, stuende im Verlauf."""
    from bewerbungs_assistent.tools import jobs

    code = inspect.getsource(jobs)
    kopf = code[code.index("def fahrstrecken_verwalten("):]
    kopf = kopf[:kopf.index(")")]
    assert "schluessel" not in kopf.lower()


def test_werkzeug_nachziehen_vorschau_und_lauf(db, monkeypatch):
    from bewerbungs_assistent.services import geocoding_service

    db.save_jobs([_stelle(1), _stelle(2)])
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    monkeypatch.setattr(geocoding_service, "get_user_coordinates",
                        lambda _db: START)
    client = _Client()
    monkeypatch.setattr(
        routing, "_abrufen",
        lambda key, start, ziele, client=None, _c=client: _abrufen_ersatz(
            _c, key, start, ziele))
    mcp = _mcp(db)

    vorschau = _call(mcp, "fahrstrecken_verwalten", {"aktion": "nachziehen"})
    assert vorschau["status"] == "vorschau"
    assert vorschau["wuerde_berechnen"] == 2
    assert vorschau["eindeutige_zielorte"] == 1
    assert client.anfragen == [], "die Vorschau fragt nichts ab"

    lauf = _call(mcp, "fahrstrecken_verwalten",
                 {"aktion": "nachziehen", "dry_run": False})
    assert lauf["berechnet"] == 2
    assert "scores_neu_berechnen" in lauf["naechster_schritt"]
    assert _gespeichert(db, 1)["fahrstrecke_km"] == 390.4
    assert SCHLUESSEL not in json.dumps(lauf) + json.dumps(vorschau)

    danach = _call(mcp, "fahrstrecken_verwalten", {})
    assert danach["offen"] == 0 and danach["davon_mit_fahrstrecke"] == 2


def _abrufen_ersatz(client, key, start, ziele):
    client.anfragen.append({"ziele": list(ziele)})
    return [{"km": 390.4, "minuten": 235} for _ in ziele], routing.OK


# ================================================ Dashboard


@pytest.fixture
def client(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    vorher = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app)
    finally:
        dash._db = vorher


def test_endpunkt_speichert_nur_nach_probe_und_zeigt_den_schluessel_nie(
        client, db, monkeypatch):
    monkeypatch.setattr(routing, "schluessel_pruefen",
                        lambda key, client=None: routing.SCHLUESSEL_ABGELEHNT)
    abgelehnt = client.post("/api/routing", json={"schluessel": SCHLUESSEL})
    assert abgelehnt.status_code == 400
    assert not routing.konfiguriert(db)

    monkeypatch.setattr(routing, "schluessel_pruefen",
                        lambda key, client=None: routing.OK)
    ok = client.post("/api/routing", json={"schluessel": SCHLUESSEL})
    stand = client.get("/api/routing")
    weg = client.delete("/api/routing")
    assert ok.status_code == 200 and ok.json()["konfiguriert"] is True
    assert stand.json()["konfiguriert"] is True
    assert weg.json()["konfiguriert"] is False
    for antwort in (abgelehnt, ok, stand, weg):
        assert SCHLUESSEL not in antwort.text


def test_die_stellenliste_traegt_die_entfernung_samt_art(client, db):
    db.save_jobs([_stelle(1, fahrstrecke_km=390.4, fahrzeit_min=235,
                          route_quelle="openrouteservice"),
                  _stelle(2, lat=None, lon=None, location="Anderswo",
                          url="https://example.com/950/anders")])
    jobs = {j["title"]: j for j in client.get("/api/jobs").json()}
    assert jobs["Rolle 1"]["entfernung"]["entfernung_art"] == "fahrstrecke"
    assert "3 Std 55 Min" in jobs["Rolle 1"]["entfernung"]["entfernung_text"]
    assert jobs["Rolle 2"]["entfernung"]["entfernung_art"] == "luftlinie"


# ================================================ Oberflaeche


def test_die_karte_steht_im_quellen_tab_und_die_liste_zeigt_die_fahrzeit():
    settings = (_repo() / "frontend/src/pages/SettingsPage.jsx").read_text(
        encoding="utf-8")
    quellen = settings[settings.index('settingsTab === "quellen"'):]
    quellen = quellen[:quellen.index("settingsTab ===", 30)]
    assert "<RoutingCard" in quellen, \
        "der Quellen-Tab gibt es auf beiden Linien, Erweiterungen nicht"
    assert 'type="password"' in settings[settings.index("function RoutingCard"):]
    jobs = (_repo() / "frontend/src/pages/JobsPage.jsx").read_text(
        encoding="utf-8")
    assert "job.entfernung?.entfernung_text" in jobs
