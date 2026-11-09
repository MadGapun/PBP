"""#1323: "Standardgruende wiederherstellen" - ein Knopf und ein Werkzeug, zwei Schritte.

Rest aus #1297 (v1.8.3): Standardgruende lassen sich abschalten und loeschen,
zurueck kam man nur einzeln. EINE Funktion
(`services.ablehnungsgruende.standardgruende_wiederherstellen`) fuer den
REST-Weg des Dashboards und das Werkzeug `ablehnungsgruende_wiederherstellen`.

Abnahme (Issue):
* nach dem Loeschen von drei Standardgruenden bringt ein Klick alle drei zurueck, aktiv
* ein bewusst abgeschalteter Grund steht in der Vorschau und wird erst nach
  Bestaetigung eingeschaltet
* eigene Gruende aendern sich nicht
Dazu: kein Doppel bei einem umbenannten Standardgrund, ein zweiter Aufruf tut nichts.
Testdaten fiktiv.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import os

import pytest


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.create_profile("Test", "test@example.com")
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _wh(db, bestaetigt=False):
    from bewerbungs_assistent.services.ablehnungsgruende import standardgruende_wiederherstellen
    return standardgruende_wiederherstellen(db, bestaetigt=bestaetigt)


def _id(db, label):
    return next(r["id"] for r in db.get_dismiss_reasons() if r["label"] == label)


def _zeilen(db):
    """Schnappschuss der Tabelle: (label, is_custom, is_active) je Zeile, sortiert."""
    return sorted((r["label"], r["is_custom"], r["is_active"]) for r in db.connect().execute(
        "SELECT label, is_custom, is_active FROM dismiss_reasons").fetchall())


def _aktiv(db, label):
    zeilen = db.connect().execute(
        "SELECT is_active FROM dismiss_reasons WHERE LOWER(label)=?", (label.lower(),)).fetchall()
    return [bool(z[0]) for z in zeilen]


def _roh_loeschen(db, label):
    """Wie Loeschen bis 1.8.2: die Zeile ist weg."""
    con = db.connect()
    con.execute("DELETE FROM dismiss_reasons WHERE LOWER(label)=?", (label,))
    con.commit()


def _stelle(db, kennung, grund):
    db.save_jobs([{"hash": kennung, "title": "PLM Berater (m/w/d)", "company": "Musterfirma GmbH",
                   "url": f"https://example.com/1323/{kennung}", "source": "manuell",
                   "_manual_entry": True, "description": "Beschreibungstext. " * 20, "score": 5}])
    h = db.resolve_job_hash(kennung)
    db.dismiss_job(h, grund, herkunft="ich")
    return h


# ------------------------------------------------------------ Funktion

def test_frische_datenbank_hat_nichts_zu_tun(db):
    erg = _wh(db)
    assert erg["status"] == "nichts_zu_tun"
    assert erg["anlegen"] == [] and erg["einschalten"] == []


def test_drei_geloeschte_kommen_mit_einem_aufruf_zurueck_aktiv(db):
    """Abnahme 1: drei Standardgruende geloescht (im Dashboard heisst das seit 1.8.3
    abschalten; bis 1.8.2 war die Zeile weg) - ein Aufruf bringt alle drei zurueck, aktiv."""
    db.delete_dismiss_reason(_id(db, "zu_junior"))          # 1.8.3: abschalten
    db.delete_dismiss_reason(_id(db, "befristet"))
    _roh_loeschen(db, "zeitarbeit")                          # bis 1.8.2: Zeile weg
    assert _aktiv(db, "zu_junior") == [False] and _aktiv(db, "zeitarbeit") == []

    vorschau = _wh(db)
    assert vorschau["status"] == "vorschau"
    assert vorschau["anlegen"] == ["zeitarbeit"]
    assert sorted(e["grund"] for e in vorschau["einschalten"]) == ["befristet", "zu_junior"]

    erg = _wh(db, bestaetigt=True)
    assert erg["status"] == "wiederhergestellt"
    for g in ("zu_junior", "befristet", "zeitarbeit"):
        assert _aktiv(db, g) == [True], g
    from bewerbungs_assistent.services.ablehnungsgruende import waehlbare_gruende
    assert {"zu_junior", "befristet", "zeitarbeit"} <= set(waehlbare_gruende(db))
    # angelegt wie der Seed: Standardzeile, nicht eigen
    zeile = db.connect().execute(
        "SELECT is_custom, profile_id FROM dismiss_reasons WHERE label='zeitarbeit'").fetchone()
    assert zeile["is_custom"] == 0 and zeile["profile_id"] == ""


def test_vorschau_aendert_nichts(db):
    """Abnahme 2: ein abgeschalteter Grund steht in der Vorschau und bleibt aus, bis bestaetigt wird."""
    db.set_dismiss_reason_active(_id(db, "kein_hochschulabschluss"), False)
    _roh_loeschen(db, "duplikat")
    vorher = _zeilen(db)
    erg = _wh(db)
    assert [e["grund"] for e in erg["einschalten"]] == ["kein_hochschulabschluss"]
    assert erg["anlegen"] == ["duplikat"]
    assert _zeilen(db) == vorher
    assert _aktiv(db, "kein_hochschulabschluss") == [False]
    _wh(db, bestaetigt=True)
    assert _aktiv(db, "kein_hochschulabschluss") == [True]


def test_vorschau_nennt_den_bestand(db):
    _stelle(db, "b1", "befristet")
    db.set_dismiss_reason_active(_id(db, "befristet"), False)
    eintrag = _wh(db)["einschalten"][0]
    assert eintrag == {"grund": "befristet", "label": "befristet", "stellen": 1}


def test_eigene_gruende_bleiben_unveraendert(db):
    """Abnahme 3: eigene Gruende - aktiv wie abgeschaltet - bleiben, wie sie sind."""
    db.add_dismiss_reason("kein_homeoffice")
    db.add_dismiss_reason("Reisetaetigkeit")
    db.set_dismiss_reason_active(_id(db, "Reisetaetigkeit"), False)
    db.set_dismiss_reason_active(_id(db, "zu_senior"), False)
    eigene = [z for z in _zeilen(db) if z[1] == 1]
    _wh(db, bestaetigt=True)
    assert [z for z in _zeilen(db) if z[1] == 1] == eigene
    assert _aktiv(db, "Reisetaetigkeit") == [False]
    assert _aktiv(db, "zu_senior") == [True]


def test_umbenannter_standardgrund_wird_nicht_doppelt_angelegt(db):
    """Ein Standardgrund unter anderer Schreibweise (ueber das Werkzeug umbenannt) ist
    derselbe Grund: keine zweite Zeile, ein abgeschalteter wird wieder eingeschaltet."""
    db.rename_dismiss_reason(_id(db, "zu_junior"), "Zu Junior")
    db.set_dismiss_reason_active(_id(db, "Zu Junior"), False)
    erg = _wh(db)
    assert "zu_junior" not in erg["anlegen"]
    assert erg["einschalten"] == [{"grund": "zu_junior", "label": "Zu Junior", "stellen": 0}]
    assert {"grund": "zu_junior", "label": "Zu Junior", "eigen": False,
            "aktiv": False} in erg["vorhanden_als"]
    _wh(db, bestaetigt=True)
    assert _aktiv(db, "zu_junior") == []
    assert _aktiv(db, "Zu Junior") == [True]


def test_eigener_grund_gleicher_schreibweise_bleibt_und_wird_nicht_gedoppelt(db):
    _roh_loeschen(db, "falsche_branche")
    db.add_dismiss_reason("Falsche Branche")
    db.set_dismiss_reason_active(_id(db, "Falsche Branche"), False)
    erg = _wh(db)
    assert erg["status"] == "nichts_zu_tun"
    assert {"grund": "falsche_branche", "label": "Falsche Branche", "eigen": True,
            "aktiv": False} in erg["vorhanden_als"]
    _wh(db, bestaetigt=True)
    assert _aktiv(db, "falsche_branche") == []
    assert _aktiv(db, "Falsche Branche") == [False]


def test_anderer_name_ist_ein_anderer_grund(db):
    """PBP raet nicht: `Zu wenig Erfahrung` ist kein erkennbarer Standardgrund."""
    db.rename_dismiss_reason(_id(db, "zu_junior"), "Zu wenig Erfahrung")
    erg = _wh(db, bestaetigt=True)
    assert erg["anlegen"] == ["zu_junior"]
    assert _aktiv(db, "zu_junior") == [True]
    assert _aktiv(db, "Zu wenig Erfahrung") == [True]


def test_zweiter_aufruf_tut_nichts(db):
    db.set_dismiss_reason_active(_id(db, "befristet"), False)
    _roh_loeschen(db, "zeitarbeit")
    assert _wh(db, bestaetigt=True)["status"] == "wiederhergestellt"
    nachher = _zeilen(db)
    zweiter = _wh(db, bestaetigt=True)
    assert zweiter["status"] == "nichts_zu_tun"
    assert _zeilen(db) == nachher


def test_geloescht_mit_bestand_kommt_nach_neustart_aus_und_dann_zurueck(db):
    """Zusammenspiel mit #1297: ein bis 1.8.2 geloeschter Grund mit Stellen kommt beim
    Start abgeschaltet zurueck - der Knopf schaltet ihn (nach Bestaetigung) ein."""
    _stelle(db, "g1", "zeitarbeit")
    _roh_loeschen(db, "zeitarbeit")
    db.initialize()  # Neustart
    assert _aktiv(db, "zeitarbeit") == [False]
    erg = _wh(db, bestaetigt=True)
    assert [e["grund"] for e in erg["einschalten"]] == ["zeitarbeit"]
    assert _aktiv(db, "zeitarbeit") == [True]
    db.initialize()  # und ein weiterer Start aendert daran nichts
    assert _aktiv(db, "zeitarbeit") == [True]


def test_systemgruende_bleiben_aussen_vor(db):
    from bewerbungs_assistent.services.ablehnungsgruende import SYSTEM_GRUENDE
    erg = _wh(db, bestaetigt=True)
    assert not set(erg["anlegen"]) & SYSTEM_GRUENDE
    for g in SYSTEM_GRUENDE:
        assert _aktiv(db, g) == [], g


# ------------------------------------------------------------ REST

@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent import dashboard
    dashboard._db = db
    try:
        yield TestClient(dashboard.app)
    finally:
        dashboard._db = None


def test_rest_zwei_schritte(db, client):
    db.set_dismiss_reason_active(_id(db, "befristet"), False)
    _roh_loeschen(db, "duplikat")
    url = "/api/dismiss-reasons/standard-wiederherstellen"
    r = client.post(url, json={})
    assert r.status_code == 200 and r.json()["status"] == "vorschau"
    assert _aktiv(db, "befristet") == [False] and _aktiv(db, "duplikat") == []
    # nur ein echtes true fuehrt aus
    assert client.post(url, json={"bestaetigt": "ja"}).json()["status"] == "vorschau"
    r = client.post(url, json={"bestaetigt": True})
    assert r.json()["status"] == "wiederhergestellt"
    assert _aktiv(db, "befristet") == [True] and _aktiv(db, "duplikat") == [True]
    assert client.post(url, json={"bestaetigt": True}).json()["status"] == "nichts_zu_tun"
    # der Weg kollidiert nicht mit /api/dismiss-reasons/{id}
    assert any(z["label"] == "duplikat" for z in client.get("/api/dismiss-reasons").json())


def test_rest_ohne_koerper_ist_vorschau(db, client):
    db.set_dismiss_reason_active(_id(db, "befristet"), False)
    r = client.post("/api/dismiss-reasons/standard-wiederherstellen")
    assert r.status_code == 200 and r.json()["status"] == "vorschau"
    assert _aktiv(db, "befristet") == [False]


# ------------------------------------------------------------ Werkzeug

def _server(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test 1323")
    register_all(mcp, db, logging.getLogger("test.1323"))
    return mcp


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def test_werkzeug_vorschau_dann_bestaetigung(db):
    mcp = _server(db)
    db.set_dismiss_reason_active(_id(db, "zu_junior"), False)
    db.add_dismiss_reason("kein_homeoffice")
    eigene = [z for z in _zeilen(db) if z[1] == 1]
    vorschau = _call(mcp, "ablehnungsgruende_wiederherstellen")
    assert vorschau["status"] == "vorschau"
    assert [e["grund"] for e in vorschau["einschalten"]] == ["zu_junior"]
    assert _aktiv(db, "zu_junior") == [False]
    erg = _call(mcp, "ablehnungsgruende_wiederherstellen", {"bestaetigung": True})
    assert erg["status"] == "wiederhergestellt"
    assert _aktiv(db, "zu_junior") == [True]
    assert [z for z in _zeilen(db) if z[1] == 1] == eigene
    assert _call(mcp, "ablehnungsgruende_wiederherstellen",
                 {"bestaetigung": True})["status"] == "nichts_zu_tun"


def test_werkzeug_ist_eingeordnet(db):
    from bewerbungs_assistent.services import werkzeug_katalog, werkzeug_schutz
    assert werkzeug_schutz.ZWEISTUFIG["ablehnungsgruende_wiederherstellen"] == "bestaetigung"
    assert "ablehnungsgruende_wiederherstellen" in werkzeug_katalog.EINSTELLUNG
    mcp = _server(db)

    async def _tool():
        return await mcp.get_tool("ablehnungsgruende_wiederherstellen")
    tool = asyncio.run(_tool())
    assert tool is not None
    schema = (tool.parameters or {}).get("properties", {})
    assert schema["bestaetigung"].get("default") is False
    assert tool.annotations.destructiveHint is True
    assert "#1323" not in (tool.description or "")
