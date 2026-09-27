"""#1037 Punkte 1, 2, 4 und AK 6: Fahrstrecke nur fuers Auto, und der
Schluessel ist nicht mehr der Schalter.

Bis hierher schaltete ein gespeicherter Routing-Schluessel alles ein:
Suchlauf, Score, Regler, Auto-Aussortierung. Wer mit Bus und Bahn pendelt,
bekam Autofahrzeiten, und nirgends stand, dass es ums Auto geht.

Alle Firmen und Orte sind Platzhalter.
"""
from __future__ import annotations

import ast
import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

SCHLUESSEL = "test-schluessel-ohne-bedeutung-1037"


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "haken.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.switch_profile(datenbank.create_profile("Haken"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _routing():
    from bewerbungs_assistent.services import routing
    return routing


def _stelle():
    return {"title": "Sachbearbeitung Einkauf", "company": "Musterfirma",
            "distance_km": 271.5, "fahrstrecke_km": 390.4,
            "fahrzeit_min": 235, "route_quelle": "openrouteservice"}


# ============================================================ der Haken


def test_ohne_haken_ist_nichts_aktiv_auch_mit_schluessel(db):
    r = _routing()
    assert r.aktiv(db) is False, "Vorgabe: aus"
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    assert r.konfiguriert(db) is True
    assert r.aktiv(db) is False, "ein Schluessel allein schaltet nichts ein"
    db.set_setting(r.EINSTELLUNG_AKTIV, True)
    assert r.aktiv(db) is True


def test_haken_ohne_schluessel_zaehlt_nicht(db):
    r = _routing()
    db.set_setting(r.EINSTELLUNG_AKTIV, True)
    assert r.aktiv(db) is False


def test_haken_setzen_ohne_schluessel_wird_abgewiesen(db):
    r = _routing()
    erg = r.haken_setzen(db, True)
    assert erg.get("fehler") and erg["befund"] == r.KEIN_SCHLUESSEL
    assert r.haken(db) is False
    # Abnehmen geht immer.
    assert r.haken_setzen(db, False)["status"] == "aus"


def test_haken_setzen_und_abnehmen(db):
    r = _routing()
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    an = r.haken_setzen(db, True)
    assert an["status"] == "an" and r.aktiv(db)
    assert "Auto" in an["hinweis"]
    aus = r.haken_setzen(db, False)
    assert aus["status"] == "aus" and not r.aktiv(db)
    assert "Luftlinie" in aus["hinweis"]


def test_schluessel_speichern_setzt_keinen_haken(db, monkeypatch):
    r = _routing()
    monkeypatch.setattr(r, "schluessel_pruefen", lambda key, client=None: r.OK)
    erg = r.schluessel_setzen(db, SCHLUESSEL)
    assert erg["status"] == "eingerichtet"
    assert r.haken(db) is False and r.aktiv(db) is False
    assert "Haken" in erg["naechster_schritt"]
    assert "nur Auto" in erg["naechster_schritt"]


def test_schluessel_entfernen_nimmt_den_haken_ab(db):
    r = _routing()
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    db.set_setting(r.EINSTELLUNG_AKTIV, True)
    r.schluessel_entfernen(db)
    assert r.haken(db) is False
    # Ein neuer Schluessel ist danach nicht ungefragt wieder an.
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    assert r.aktiv(db) is False


def test_status_nennt_haken_und_auto_aber_nie_den_schluessel(db):
    r = _routing()
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    stand = r.status(db)
    assert stand["haken"] is False and stand["aktiv"] is False
    assert "Auto" in stand["nur_auto"]
    assert SCHLUESSEL not in str(stand)


# ======================================================== die Uebernahme


def test_uebernahme_setzt_den_haken_fuer_einen_bestand_mit_schluessel(db):
    r = _routing()
    # Zustand wie vor #1037: Schluessel da, der Haken existiert noch nicht.
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    db.connect().execute("DELETE FROM settings WHERE key IN (?, ?)",
                         (r.EINSTELLUNG_AKTIV, r.EINSTELLUNG_UEBERNAHME))
    db.connect().commit()
    assert r.uebernahme(db) is True
    assert r.aktiv(db) is True
    assert db.get_setting(r.EINSTELLUNG_HAKEN_UEBERNOMMEN) is True
    # Nur einmal: wer ihn danach abnimmt, bekommt ihn nicht zurueck.
    r.haken_setzen(db, False)
    assert r.uebernahme(db) is False
    assert r.aktiv(db) is False


def test_schluessel_nach_dem_update_bleibt_ohne_haken(db):
    """Die Uebernahme lief beim ersten Start (ohne Schluessel). Wer danach
    einen Schluessel eintraegt, bekommt den Haken NICHT beim naechsten Start
    geschenkt — die Vorgabe ist aus (AK 2)."""
    r = _routing()
    assert db.get_setting(r.EINSTELLUNG_UEBERNAHME) is True
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    db.connect().execute("DELETE FROM settings WHERE key=?",
                         (r.EINSTELLUNG_AKTIV,))
    db.connect().commit()
    db.initialize()
    assert r.haken(db) is False


def test_uebernahme_ohne_schluessel_setzt_nichts(db):
    r = _routing()
    db.connect().execute("DELETE FROM settings WHERE key=?",
                         (r.EINSTELLUNG_UEBERNAHME,))
    db.connect().commit()
    assert r.uebernahme(db) is False
    assert r.haken(db) is False
    assert not db.get_setting(r.EINSTELLUNG_HAKEN_UEBERNOMMEN, False)


def test_uebernahme_laesst_einen_gesetzten_haken_in_ruhe(db):
    r = _routing()
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    db.set_setting(r.EINSTELLUNG_AKTIV, False)
    db.connect().execute("DELETE FROM settings WHERE key=?",
                         (r.EINSTELLUNG_UEBERNAHME,))
    db.connect().commit()
    assert r.uebernahme(db) is False
    assert r.haken(db) is False


def test_initialize_fuehrt_die_uebernahme_aus(db):
    r = _routing()
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    db.connect().execute("DELETE FROM settings WHERE key IN (?, ?)",
                         (r.EINSTELLUNG_AKTIV, r.EINSTELLUNG_UEBERNAHME))
    db.connect().commit()
    db.initialize()
    assert r.aktiv(db) is True


def test_frische_datenbank_hat_den_haken_aus(db):
    r = _routing()
    assert r.haken(db) is False
    assert db.get_setting(r.EINSTELLUNG_UEBERNAHME) is True


def test_hinweis_nur_nach_uebernahme_und_solange_der_haken_steht(db):
    from bewerbungs_assistent.services import onboarding_hints as oh
    r = _routing()
    ids = lambda: {h["id"] for h in oh.list_active_hints(db)}  # noqa: E731
    assert "f1037_fahrstrecke_haken" not in ids()
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    db.connect().execute("DELETE FROM settings WHERE key IN (?, ?)",
                         (r.EINSTELLUNG_AKTIV, r.EINSTELLUNG_UEBERNAHME))
    db.connect().commit()
    r.uebernahme(db)
    assert "f1037_fahrstrecke_haken" in ids()
    r.haken_setzen(db, False)
    assert "f1037_fahrstrecke_haken" not in ids()


# ================================================ Kriterien und Rechnung


def test_kriterien_folgen_dem_haken_nicht_dem_schluessel(db):
    r = _routing()
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    assert "_fahrstrecke_zaehlt" not in db.get_search_criteria()
    db.set_setting(r.EINSTELLUNG_AKTIV, True)
    assert db.get_search_criteria()["_fahrstrecke_zaehlt"] is True


def test_ohne_haken_rechnet_der_score_mit_der_luftlinie(db):
    from bewerbungs_assistent.services import entfernung
    r = _routing()
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    assert entfernung.preis_km(_stelle(), db.get_search_criteria()) == 271.5
    db.set_setting(r.EINSTELLUNG_AKTIV, True)
    assert entfernung.preis_km(_stelle(), db.get_search_criteria()) == 390.4


# ================================================ Anzeige (AK 1 und 6)


def test_anzeige_luftlinie_vorn_route_mit_dem_auto():
    from bewerbungs_assistent.services import entfernung
    b = entfernung.befund(_stelle(), {"_fahrstrecke_zaehlt": True})
    assert b["entfernung_text"] == (
        "271.5 km Luftlinie · 390.4 km / 3 Std 55 Min mit dem Auto")
    assert b["entfernung_text"].startswith("271.5 km Luftlinie")


def test_anzeige_ohne_haken_nennt_keine_gespeicherte_fahrzeit():
    from bewerbungs_assistent.services import entfernung
    b = entfernung.befund(_stelle(), {})
    assert b["entfernung_art"] == entfernung.ART_LUFTLINIE
    assert "3 Std" not in b["entfernung_text"]
    assert "fahrzeit_text" not in b


def test_route_ohne_fahrzeit_sagt_trotzdem_auto():
    from bewerbungs_assistent.services import entfernung
    job = dict(_stelle(), fahrzeit_min=None)
    b = entfernung.befund(job, {"_fahrstrecke_zaehlt": True})
    assert b["entfernung_text"].endswith("390.4 km mit dem Auto")


def test_eine_schreibweise_fuer_auto():
    from bewerbungs_assistent.services import entfernung
    r = _routing()
    assert r.NUR_AUTO is entfernung.NUR_AUTO


def test_neuer_ort_nennt_die_luftlinie():
    from bewerbungs_assistent.services import stelle_aendern
    assert stelle_aendern._luftlinie(12) == "12 km Luftlinie"


# ============================================================== Guards


def _quellen():
    for p in (_repo() / "src" / "bewerbungs_assistent").rglob("*.py"):
        if "static" in p.parts:
            continue
        yield p, ast.parse(p.read_text(encoding="utf-8-sig"))


def test_niemand_ausser_routing_fragt_konfiguriert_als_schalter():
    """#1037 Punkt 2: die Bedingung haengt an EINER Stelle (`aktiv`).
    `konfiguriert` sagt nur, ob ein Schluessel da ist — als Schalter
    gelesen waere es die alte Regel an einem zweiten Ort (#963)."""
    funde = []
    for p, baum in _quellen():
        if p.name == "routing.py" and p.parent.name == "services":
            continue
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.Call)
                    and isinstance(knoten.func, ast.Attribute)
                    and knoten.func.attr == "konfiguriert"):
                funde.append(f"{p.name}:{knoten.lineno}")
    assert not funde, funde


def test_jede_routenabfrage_steht_hinter_aktiv():
    """Ohne Haken fragt kein Suchlauf Routen ab: jede Funktion, die
    `fuer_stellen` aufruft, prueft vorher `aktiv` (bzw. den Stand daraus)."""
    fehlt = []
    for p, baum in _quellen():
        if p.name == "routing.py" and p.parent.name == "services":
            continue
        for fn in ast.walk(baum):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            code = ast.unparse(fn)
            if ".fuer_stellen(" not in code:
                continue
            innere = [f for f in ast.walk(fn) if f is not fn and isinstance(
                f, (ast.FunctionDef, ast.AsyncFunctionDef))
                and ".fuer_stellen(" in ast.unparse(f)]
            if innere:
                continue  # die innerste Funktion zaehlt
            if ".aktiv(" not in code and "stand['aktiv']" not in code:
                fehlt.append(f"{p.name}:{fn.name}")
    assert not fehlt, fehlt


def test_jeder_befund_einer_stelle_bekommt_die_kriterien():
    """Sonst stuende an der Stelle eine Fahrzeit, mit der nichts rechnet."""
    fehlt = []
    for p, baum in _quellen():
        if p.name == "entfernung.py":
            continue
        for k in ast.walk(baum):
            if (isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
                    and k.func.attr == "befund"
                    and "entfernung" in ast.unparse(k.func.value)):
                if len(k.args) + len(k.keywords) < 2:
                    fehlt.append(f"{p.name}:{k.lineno}")
    assert not fehlt, fehlt


def test_oberflaeche_sagt_nur_auto():
    web = _repo() / "frontend" / "src"
    haken = (web / "components" / "FahrstreckeHaken.jsx").read_text(encoding="utf-8")
    assert "Echte Fahrstrecke und Fahrzeit verwenden (nur Auto)" in haken
    assert "nicht für Bus und Bahn" in haken
    assert 'tab: "quellen_details"' in haken, "Link zum Schluessel"
    einst = (web / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert 'title="Fahrstrecke und Fahrzeit (nur Auto)"' in einst
    profil = (web / "pages" / "ProfilePage.jsx").read_text(encoding="utf-8-sig")
    assert "<FahrstreckeHaken" in profil


def test_schluesselkarte_steht_oben_in_quellen_im_detail():
    """Punkt 4: nicht mehr am Seitenende unter der Quellen-Gesundheit."""
    einst = (_repo() / "frontend" / "src" / "pages"
             / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    block = einst.split('settingsTab === "quellen_details"', 1)[1]
    assert block.index("<RoutingCard") < block.index("<SourceSelectionList")
    assert block.index("<RoutingCard") < block.index("<ScraperHealthCard")


def test_rueckfrage_beim_entfernen_beschreibt_was_danach_gilt():
    einst = (_repo() / "frontend" / "src" / "pages"
             / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    frage = einst.split("Routing-Schlüssel entfernen?", 1)[1].split('"', 1)[0]
    assert "Haken" in frage and "Luftlinie" in frage
    assert "schon eine Fahrstrecke" in frage


# ================================================= Endpunkt und Werkzeug


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


def test_endpunkt_haken(client, db):
    r = _routing()
    ohne = client.put("/api/routing/aktiv", json={"aktiv": True})
    assert ohne.status_code == 400
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    an = client.put("/api/routing/aktiv", json={"aktiv": True})
    assert an.status_code == 200 and an.json()["aktiv"] is True
    assert "nur Auto" in an.json()["hinweis"]
    aus = client.put("/api/routing/aktiv", json={"aktiv": False})
    assert aus.json()["aktiv"] is False
    for antwort in (ohne, an, aus):
        assert SCHLUESSEL not in antwort.text


def test_endpunkt_schluessel_sagt_dass_er_nichts_einschaltet(client, db,
                                                            monkeypatch):
    r = _routing()
    monkeypatch.setattr(r, "schluessel_pruefen", lambda key, client=None: r.OK)
    ok = client.post("/api/routing", json={"schluessel": SCHLUESSEL})
    assert ok.status_code == 200
    assert "Haken" in ok.json()["hinweis"]
    assert ok.json()["aktiv"] is False
    weg = client.delete("/api/routing")
    assert "Haken" in weg.json()["hinweis"]


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


def test_werkzeug_schaltet_und_nachziehen_braucht_den_haken(db):
    r = _routing()
    mcp = _mcp(db)
    db.set_setting(r.EINSTELLUNG_SCHLUESSEL, SCHLUESSEL)
    stand = _call(mcp, "fahrstrecken_verwalten", {})
    assert "Haken" in stand["naechster_schritt"]
    nach = _call(mcp, "fahrstrecken_verwalten", {"aktion": "nachziehen"})
    assert nach.get("fehler") and "Haken" in nach["fehler"]
    an = _call(mcp, "fahrstrecken_verwalten", {"aktion": "einschalten"})
    assert an["aktiv"] is True
    aus = _call(mcp, "fahrstrecken_verwalten", {"aktion": "ausschalten"})
    assert aus["aktiv"] is False


def test_werkzeug_einschalten_ohne_schluessel(db):
    erg = _call(_mcp(db), "fahrstrecken_verwalten", {"aktion": "einschalten"})
    assert erg.get("fehler")
    assert _routing().haken(db) is False
