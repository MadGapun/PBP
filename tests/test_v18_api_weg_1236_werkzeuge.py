"""#1236 Stufe 2 -- der API-Weg im MCP-Layer (#514) und im Dashboard-Server.

Die Werkzeuge `api_weg_anzeigen`, `api_weg_einstellen`, `api_weg_pruefen` gibt es NUR, wenn beim Start des Servers ein
Schluessel in der Umgebung steht. Ohne ihn ist die Werkzeugliste genau die von vorher (Abnahmekriterium 1: kein sichtbarer
Unterschied) -- das prueft schon `test_mcp_registry.py` mit der festen Zahl 281 und der festen Namensliste; hier steht der
ausdrueckliche Fall dazu. Der Transport ist ein Testdoppel, kein Test erreicht das Netz.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from _api_hilfen import FakeTransport, TESTSCHLUESSEL, antwort, fehlerantwort  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

from bewerbungs_assistent.database import Database  # noqa: E402
from bewerbungs_assistent.services import api_backend, werkzeug_katalog, werkzeug_schutz  # noqa: E402
from bewerbungs_assistent.tools import register_all  # noqa: E402

NAMEN = {"api_weg_anzeigen", "api_weg_einstellen", "api_weg_pruefen"}


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "API-Test"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def schluessel(monkeypatch):
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)
    return TESTSCHLUESSEL


def _server(db):
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("test.api_weg"))
    return mcp


def _tools(mcp):
    return {t.name: t for t in asyncio.run(mcp.list_tools())}


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


# ============================================================ Ohne Schluessel gibt es sie nicht

def test_ohne_schluessel_werden_die_werkzeuge_nicht_registriert(db):
    namen = set(_tools(_server(db)))
    assert not (NAMEN & namen), "Ohne Schluessel darf die Werkzeugliste nicht anders sein als vorher"


def test_die_bedingung_steht_im_quelltext_und_nirgends_sonst():
    """Eine Bedingung, die jemand 'aufraeumt', waere genau der sichtbare Unterschied, den Abnahmekriterium 1 verbietet."""
    quelle = (ROOT / "src" / "bewerbungs_assistent" / "tools" / "__init__.py").read_text(encoding="utf-8-sig")
    assert "if _api_backend.schluessel_vorhanden():\n        api_weg.register(mcp, db, logger)" in quelle
    assert quelle.count("api_weg.register(") == 1


def test_mit_schluessel_sind_es_genau_diese_drei(db, schluessel):
    ohne = None
    import os as _os
    schl = _os.environ.pop(api_backend.ENV_SCHLUESSEL)
    try:
        ohne = set(_tools(_server(db)))
    finally:
        _os.environ[api_backend.ENV_SCHLUESSEL] = schl
    mit = set(_tools(_server(db)))
    assert mit - ohne == NAMEN and not (ohne - mit)


def test_tag_annotation_und_beschreibung_wie_bei_jedem_werkzeug(db, schluessel):
    werkzeuge = _tools(_server(db))
    for name in NAMEN:
        w = werkzeuge[name]
        assert set(w.tags) & set(werkzeug_katalog.TAGS) == {"einstellung"}, (name, w.tags)
        assert werkzeug_katalog.tag(name) == "einstellung" and not werkzeug_katalog.ausgeblendet(name)
        assert 20 <= len(w.description) <= 600, (name, len(w.description))
        assert not re.search(r"#\d{3,4}|\bv1\.\d|beta\.\d", w.description), name
    assert werkzeug_schutz.annotations_fuer("api_weg_anzeigen") == {"readOnlyHint": True}
    assert werkzeug_schutz.annotations_fuer("api_weg_einstellen") == {}
    assert werkzeug_schutz.annotations_fuer("api_weg_pruefen") == {}


def test_die_parametertexte_stehen_im_eingabeschema(db, schluessel):
    w = _tools(_server(db))["api_weg_einstellen"]
    props = w.parameters["properties"]
    assert set(props) == {"aufgaben", "modelle", "budget_usd", "bestaetigt"}
    assert "vollständige Liste" in props["aufgaben"]["description"]
    assert "US-Dollar" in props["budget_usd"]["description"]
    assert "NACHDEM" in props["bestaetigt"]["description"]


def test_die_namen_stehen_nicht_in_der_liste_der_registrierten_werkzeuge_ohne_schluessel():
    """`API_WEG` steht bewusst NICHT in EINSTELLUNG: ein Guard haelt jede Liste dort gegen die registrierten Werkzeuge."""
    assert werkzeug_katalog.API_WEG == NAMEN
    assert not (NAMEN & set(werkzeug_katalog.EINSTELLUNG))
    assert not (NAMEN & set(werkzeug_katalog.WARTUNG) | NAMEN & set(werkzeug_katalog.ENTWICKLER))


# ============================================================ Verhalten

def test_anzeigen_nennt_den_stand_und_nie_den_schluessel(db, schluessel):
    mcp = _server(db)
    erg = _call(mcp, "api_weg_anzeigen")
    assert erg["sichtbar"] and erg["schluessel_gesetzt"] and erg["variable"] == api_backend.ENV_SCHLUESSEL
    assert [a["id"] for a in erg["aufgaben"]] == ["match_job_to_skills", "validate_job_quality"]
    assert all(a["gesendet"] and a["nicht_gesendet"] for a in erg["aufgaben"]), "Die Feldliste je Aufgabe steht dabei"
    assert erg["budget"]["gesetzt"] is False and erg["verbrauch"]["aufrufe"] == 0
    assert "naechster_schritt" in erg and "Anthropic Console" in erg["naechster_schritt"]
    assert TESTSCHLUESSEL not in json.dumps(erg) and TESTSCHLUESSEL[:14] not in json.dumps(erg)


def test_einstellen_fragt_erst_mit_der_feldliste_und_speichert_nichts(db, schluessel):
    mcp = _server(db)
    erg = _call(mcp, "api_weg_einstellen", {"aufgaben": ["match_job_to_skills"], "budget_usd": 3})
    assert erg["status"] == "bestaetigung_noetig"
    assert "verlassen" in erg["text"] and erg["aufgaben"][0]["gesendet"]
    assert "bestaetigt=True" in erg["naechster_schritt"] and "ausdrücklich ja" in erg["naechster_schritt"]
    assert api_backend.freigaben_lesen(db) == {} and api_backend.budget_lesen(db) is None


def test_einstellen_mit_bestaetigung_speichert_und_zeigt_den_neuen_stand(db, schluessel):
    mcp = _server(db)
    erg = _call(mcp, "api_weg_einstellen", {"aufgaben": ["match_job_to_skills"], "budget_usd": "2,50", "bestaetigt": True})
    assert erg["status"] == "gespeichert" and erg["freigegeben"] == ["match_job_to_skills"]
    stand = erg["stand"]
    assert stand["budget"]["usd"] == 2.5
    match = next(a for a in stand["aufgaben"] if a["id"] == "match_job_to_skills")
    assert match["freigegeben"] and match["bereit"] and match["modell"] == "claude-haiku-5-5"
    assert not next(a for a in stand["aufgaben"] if a["id"] == "validate_job_quality")["freigegeben"]


def test_sperren_und_modell_und_budget_brauchen_keine_bestaetigung(db, schluessel):
    mcp = _server(db)
    _call(mcp, "api_weg_einstellen", {"aufgaben": ["match_job_to_skills"], "budget_usd": 1, "bestaetigt": True})
    erg = _call(mcp, "api_weg_einstellen", {"modelle": {"match_job_to_skills": "claude-sonnet-5-5"}, "budget_usd": 4})
    assert erg["status"] == "gespeichert" and erg["stand"]["budget"]["usd"] == 4.0
    assert next(a for a in erg["stand"]["aufgaben"] if a["id"] == "match_job_to_skills")["modell"] == "claude-sonnet-5-5"
    erg = _call(mcp, "api_weg_einstellen", {"aufgaben": []})
    assert erg["gesperrt"] == ["match_job_to_skills"]
    assert api_backend.freigaben_lesen(db) == {}


def test_einstellen_weist_unsinn_ab_und_nennt_den_grund(db, schluessel):
    mcp = _server(db)
    erg = _call(mcp, "api_weg_einstellen", {"aufgaben": ["extract_contacts"], "bestaetigt": True})
    assert erg["status"] == "fehler" and "läuft nicht über die API" in erg["text"] and "stand" in erg
    erg = _call(mcp, "api_weg_einstellen", {"budget_usd": "viel"})
    assert erg["status"] == "fehler" and "kein gültiger Betrag" in erg["text"]
    assert _call(mcp, "api_weg_einstellen", {})["status"] == "unveraendert"


def test_ohne_bestaetigung_oder_mit_unsinn_wird_nichts_freigegeben(db, schluessel):
    """Fehlt `bestaetigt` oder ist es False, kommt nur die Feldliste; ein Wert, der kein Ja ist, weist schon das Schema ab.
    (Ein JSON-`true` als Text 'true' liest FastMCP als True: das ist dasselbe Ja und kein Fehler dieser Werkzeuge.)"""
    mcp = _server(db)
    for ohne in ({}, {"bestaetigt": False}):
        erg = _call(mcp, "api_weg_einstellen", {"aufgaben": ["match_job_to_skills"], **ohne})
        assert erg["status"] == "bestaetigung_noetig", ohne
    for unsinn in ("ja", "vielleicht", "nein", None, [True], {"ja": 1}):
        with pytest.raises(Exception):
            _call(mcp, "api_weg_einstellen", {"aufgaben": ["match_job_to_skills"], "bestaetigt": unsinn})
    assert api_backend.freigaben_lesen(db) == {}


def test_pruefen_fragt_erst_und_prueft_dann_mit_dem_testdoppel(db, schluessel):
    mcp = _server(db)
    transport = FakeTransport(antwort("ok", ein=12, aus=1))
    api_backend.transport_setzen(transport)
    erg = _call(mcp, "api_weg_pruefen")
    assert erg["status"] == "bestaetigung_noetig" and "Bruchteil eines Cents" in erg["text"] and transport.anzahl == 0
    erg = _call(mcp, "api_weg_pruefen", {"bestaetigt": True})
    assert erg["ergebnis"] == "gueltig" and transport.anzahl == 1
    assert erg["stand"]["pruefung"]["ergebnis"] == "gueltig"
    assert TESTSCHLUESSEL not in json.dumps(erg)


def test_eine_misslungene_probe_im_werkzeug_sagt_den_grund(db, schluessel):
    mcp = _server(db)
    api_backend.transport_setzen(FakeTransport(fehlerantwort(402, "billing_error", "Billing")))
    erg = _call(mcp, "api_weg_pruefen", {"bestaetigt": True})
    assert erg["ergebnis"] == "unklar" and erg["code"] == "guthaben_leer" and "Guthaben" in erg["text"]
    assert erg["stand"]["pruefung"]["ergebnis"] == "unklar"


def test_capabilities_nennen_den_weg_nur_dort_wo_es_ihn_gibt(db, monkeypatch):
    mcp = _server(db)
    ohne = _call(mcp, "pbp_capabilities", {"kategorie": "einstellungen"})
    assert "api_weg_anzeigen" not in json.dumps(ohne)
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)
    mit = _call(_server(db), "pbp_capabilities", {"kategorie": "einstellungen"})
    assert any("api_weg_anzeigen" in zeile for zeile in mit["tools"])


# ============================================================ Dashboard-Endpunkte

@pytest.fixture
def client(db, monkeypatch):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    monkeypatch.setattr(dash, "_db", db)
    return TestClient(dash.app)


def test_get_ohne_schluessel_ist_minimal(client):
    assert client.get("/api/api-weg").json() == {"sichtbar": False, "schluessel_gesetzt": False}


def test_get_mit_schluessel_zeigt_den_stand_ohne_den_schluessel(client, schluessel):
    erg = client.get("/api/api-weg").json()
    assert erg["sichtbar"] and erg["schluessel_gesetzt"]
    assert TESTSCHLUESSEL not in json.dumps(erg)
    assert [m["id"] for m in erg["modelle"]] == ["claude-haiku-5-5", "claude-sonnet-5-5"]
    assert erg["modelle"][0]["preis"] == "0,10 / 0,50 US-Dollar je Million Tokens (Eingabe / Ausgabe)"


def test_put_fragt_erst_und_speichert_nach_der_bestaetigung(client, db, schluessel):
    antwort_ = client.put("/api/api-weg", json={"aufgaben": ["validate_job_quality"]})
    assert antwort_.status_code == 400
    erg = antwort_.json()
    assert erg["status"] == "bestaetigung_noetig" and erg["error"] == erg["text"] and "verlassen" in erg["error"]
    assert api_backend.freigaben_lesen(db) == {}
    ok = client.put("/api/api-weg", json={"aufgaben": ["validate_job_quality"], "budget_usd": 2, "bestaetigt": True})
    assert ok.status_code == 200 and ok.json()["status"] == "gespeichert"
    stand = ok.json()["stand"]
    assert next(a for a in stand["aufgaben"] if a["id"] == "validate_job_quality")["bereit"] is True


def test_put_mit_text_statt_true_gilt_nicht_als_bestaetigt(client, db, schluessel):
    for falsch in ("true", "ja", 1, "True"):
        r = client.put("/api/api-weg", json={"aufgaben": ["validate_job_quality"], "bestaetigt": falsch})
        assert r.status_code == 400, falsch
    assert api_backend.freigaben_lesen(db) == {}


def test_put_weist_unsinn_ab(client, schluessel):
    r = client.put("/api/api-weg", json={"aufgaben": ["gibt_es_nicht"], "bestaetigt": True})
    assert r.status_code == 400 and "läuft nicht über die API" in r.json()["error"]
    r = client.put("/api/api-weg", json={"budget_usd": "abc"})
    assert r.status_code == 400 and "kein gültiger Betrag" in r.json()["error"]


def test_put_ohne_schluessel_kann_nicht_freigeben_aber_sperren(client, db, monkeypatch):
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)
    assert client.put("/api/api-weg", json={"aufgaben": ["validate_job_quality"], "bestaetigt": True}).status_code == 200
    monkeypatch.delenv(api_backend.ENV_SCHLUESSEL)
    r = client.put("/api/api-weg", json={"aufgaben": ["validate_job_quality", "match_job_to_skills"], "bestaetigt": True})
    assert r.status_code == 400 and api_backend.ENV_SCHLUESSEL in r.json()["error"]
    assert client.put("/api/api-weg", json={"aufgaben": []}).status_code == 200
    assert api_backend.freigaben_lesen(db) == {}


def test_pruefen_braucht_die_bestaetigung_und_nutzt_dann_den_transport(client, db, schluessel):
    transport = FakeTransport(antwort("ok"))
    api_backend.transport_setzen(transport)
    r = client.post("/api/api-weg/pruefen", json={})
    assert r.status_code == 400 and r.json()["status"] == "bestaetigung_noetig" and transport.anzahl == 0
    r = client.post("/api/api-weg/pruefen", json={"bestaetigt": "ja"})
    assert r.status_code == 400 and transport.anzahl == 0
    r = client.post("/api/api-weg/pruefen", json={"bestaetigt": True})
    assert r.status_code == 200 and r.json()["ergebnis"] == "gueltig" and transport.anzahl == 1
    assert r.json()["stand"]["pruefung"]["ergebnis"] == "gueltig"
    assert TESTSCHLUESSEL not in r.text


def test_pruefen_ohne_schluessel_sagt_es(client):
    r = client.post("/api/api-weg/pruefen", json={"bestaetigt": True})
    assert r.status_code == 200 and r.json()["code"] == "kein_schluessel"
    assert r.json()["stand"] == {"sichtbar": False, "schluessel_gesetzt": False}


# ============================================================ Datenschutz-Anzeige

def test_die_datenschutz_anzeige_hat_die_vierte_zeile_nur_nach_einer_freigabe(client, db, schluessel):
    ohne = client.get("/api/privacy-info").json()["data_flow"]
    assert set(ohne) == {"local_only", "sent_to_claude", "external_requests"}, "Ohne Freigabe bleibt die Auskunft, wie sie war"
    api_backend.einstellungen_setzen(db, aufgaben=["match_job_to_skills"], bestaetigt=True)
    mit = client.get("/api/privacy-info").json()["data_flow"]
    assert set(mit) == {"local_only", "sent_to_claude", "external_requests", "sent_to_api"}
    zeilen = mit["sent_to_api"]
    assert "ruft selbst die Anthropic-API auf" in zeilen[0]
    assert any("deine letzte Berufsbezeichnung" in z for z in zeilen)
    assert any("abschalten unter Einstellungen › Lokale KI" in z for z in zeilen)
    from bewerbungs_assistent.services import datenschutz
    assert "sent_to_api" not in datenschutz.DATENFLUSS, "Die Vorlage selbst bleibt unveraendert"
    assert client.get("/api/privacy-info").json()["data_flow"]["sent_to_api"] == zeilen
    api_backend.einstellungen_setzen(db, aufgaben=[])
    assert "sent_to_api" not in client.get("/api/privacy-info").json()["data_flow"]


def test_die_datenschutz_zeilen_ohne_schluessel_aber_mit_freigabe_bleiben_ehrlich(db, schluessel, monkeypatch):
    api_backend.einstellungen_setzen(db, aufgaben=["match_job_to_skills"], bestaetigt=True)
    monkeypatch.delenv(api_backend.ENV_SCHLUESSEL)
    from bewerbungs_assistent.services import datenschutz
    assert "sent_to_api" in datenschutz.datenfluss(db), (
        "Eine gespeicherte Freigabe ist eine Freigabe, auch wenn der Schluessel gerade fehlt: die Anzeige verschweigt sie nicht")
