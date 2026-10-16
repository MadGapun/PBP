"""#1226 (dritter Lauf, Block E5): der Schalter „Vorabversionen automatisch“ aendert die Frage — die Antwort wird neu geholt.

Befund auf dem Werkstatt-PC: auf 1.9.0-rc.1 liegt 1.9.0-rc.2 derselben Linie in der Quelle. Der Schalter war aus; nach dem Einschalten
nannte die Karte sofort „PBP wechselt die Versionslinie nie von selbst“ und den ZIP-Download als einzigen Weg. Ein Klick auf „Jetzt
pruefen“ zeigte danach „Neu: v1.9.0-rc.2“ mit „Jetzt installieren“. Das gemerkte Pruefergebnis kannte den Stand des Schalters nicht;
„Schalter an, kein neu“ wurde als „andere Linie“ gelesen, bis jemand neu pruefte.

Hier: das Ergebnis traegt den Schalterstand (`vorab`), der Zwischenspeicher gilt nur bei gleichem Stand, das Umschalten fragt die Quelle
gleich neu (Dashboard und Werkzeug), die Uebersicht zeigt nach dem Ausschalten keine Vorabversion mehr als „neu“. Das Netz ist ein
Testdoppel, der Programmordner liegt unter `tmp_path`.
"""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from _au_hilfen import FakeDb, FakeOeffner, eintrag, programmordner

from bewerbungs_assistent.services.auto_update import lauf, layout, quelle, zustand

LAUFEND = "1.9.0-rc.1"
NEUER = "1.9.0-rc.2"


def _liste(*, mit_vorab=True):
    eintraege = [eintrag(f"v{NEUER}", prerelease=True, signatur=True)] if mit_vorab else []
    return {quelle.API_FREIGABEN: json.dumps(eintraege).encode()}


@pytest.fixture
def u(tmp_path, monkeypatch):
    """Eine Vorab-Installation unter `tmp_path`; der Zwischenspeicher der Pruefung ist leer."""
    app = programmordner(tmp_path / "pc", fassungen=(LAUFEND,))
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", LAUFEND)
    lauf._PRUEFUNG.update(zeit=0.0, gilt_s=lauf.ERFOLG_GILT_S, ergebnis=None)
    yield SimpleNamespace(app=app)
    lauf._PRUEFUNG.update(zeit=0.0, gilt_s=lauf.ERFOLG_GILT_S, ergebnis=None)


def _pruefen(db, oeffner, u):
    return lauf.pruefen(db, oeffner=oeffner, laufende=LAUFEND, app=u.app)


# ── das Ergebnis traegt den Stand des Schalters, der Zwischenspeicher gilt nur dafuer ──────────────────────────────

def test_das_ergebnis_traegt_den_stand_des_schalters_und_eine_aenderung_holt_neu(u):
    db = FakeDb()
    erg = _pruefen(db, FakeOeffner(_liste()), u)
    assert erg["status"] == "aktuell" and erg["vorab"] is False, "ohne Schalter bleibt die Vorabversion unsichtbar"
    zustand.vorab_setzen(db, True)
    o = FakeOeffner(_liste())
    erg = _pruefen(db, o, u)          # keine 15 s vergangen: vorher gab der Zwischenspeicher das alte Ergebnis zurueck
    assert erg["status"] == "neu" and erg["version"] == NEUER and erg["vorab"] is True
    assert o.aufrufe, "die Quelle wurde neu gefragt"


def test_ohne_aenderung_des_schalters_gilt_der_zwischenspeicher_weiter(u):
    db = FakeDb()
    zustand.vorab_setzen(db, True)
    o = FakeOeffner(_liste())
    _pruefen(db, o, u)
    n = len(o.aufrufe)
    _pruefen(db, o, u)
    assert len(o.aufrufe) == n, "gleicher Stand: keine zweite Anfrage an GitHub"


def test_auch_ein_fehlschlag_traegt_den_stand_des_schalters(u):
    db = FakeDb()
    zustand.vorab_setzen(db, True)
    erg = _pruefen(db, FakeOeffner({}), u)
    assert erg["status"] == "keine_antwort" and erg["vorab"] is True
    assert lauf.letzte_pruefung(db)["vorab"] is True, "auch der gemerkte Stand auf der Platte"


# ── das Umschalten fragt gleich neu ──────────────────────────────────────────────────────────────────────────────

def test_einschalten_prueft_gleich_neu_und_die_uebersicht_nennt_die_vorabversion(u):
    db = FakeDb()
    _pruefen(db, FakeOeffner(_liste()), u)
    assert lauf.uebersicht(db)["neu"] is None
    o = FakeOeffner(_liste())
    assert lauf.vorab_einstellen(db, True, oeffner=o) is True
    assert o.aufrufe, "es wurde gleich geprueft"
    ue = lauf.uebersicht(db)
    assert ue["vorab"] is True and ue["pruefung"]["vorab"] is True
    assert ue["neu"] and ue["neu"]["version"] == NEUER


def test_ausschalten_prueft_neu_und_nimmt_die_vorabversion_zurueck(u):
    db = FakeDb()
    zustand.vorab_setzen(db, True)
    _pruefen(db, FakeOeffner(_liste()), u)
    assert lauf.uebersicht(db)["neu"]["version"] == NEUER
    o = FakeOeffner(_liste())
    assert lauf.vorab_einstellen(db, False, oeffner=o) is True
    assert o.aufrufe
    ue = lauf.uebersicht(db)
    assert ue["vorab"] is False and ue["neu"] is None
    assert ue["pruefung"]["status"] == "aktuell" and ue["pruefung"]["vorab"] is False


def test_derselbe_stand_prueft_nicht_noch_einmal(u):
    db = FakeDb()
    zustand.vorab_setzen(db, True)
    o = FakeOeffner(_liste())
    assert lauf.vorab_einstellen(db, True, oeffner=o) is False
    assert o.aufrufe == []


def test_eine_gescheiterte_pruefung_verhindert_das_umschalten_nicht(u):
    db = FakeDb()
    assert lauf.vorab_einstellen(db, True, oeffner=FakeOeffner({})) is True
    assert zustand.vorab(db) is True
    ue = lauf.uebersicht(db)
    assert ue["pruefung"]["status"] == "keine_antwort" and ue["pruefung"]["vorab"] is True
    assert ue["neu"] is None


def test_eine_unerwartete_ausnahme_der_pruefung_verhindert_das_umschalten_nicht(u, monkeypatch):
    db = FakeDb()

    def kaputt(*a, **kw):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(lauf, "pruefen", kaputt)
    assert lauf.vorab_einstellen(db, True) is True
    assert zustand.vorab(db) is True


def test_nach_dem_ausschalten_ohne_neue_pruefung_steht_keine_vorabversion_als_neu_da(u):
    """Das gemerkte Ergebnis stammt von eingeschaltetem Schalter; wer nur die Einstellung aendert (anderer Weg), sieht sie nicht."""
    db = FakeDb()
    zustand.vorab_setzen(db, True)
    _pruefen(db, FakeOeffner(_liste()), u)
    assert lauf.uebersicht(db)["neu"]["version"] == NEUER
    zustand.vorab_setzen(db, False)            # ohne vorab_einstellen: keine neue Pruefung
    assert lauf.uebersicht(db)["neu"] is None


def test_eine_stabile_neue_version_bleibt_auch_nach_dem_umschalten_neu(u):
    db = FakeDb()
    antwort = {quelle.API_FREIGABEN: json.dumps([eintrag("v1.9.0", signatur=True)]).encode()}
    _pruefen(db, FakeOeffner(antwort), u)
    assert lauf.uebersicht(db)["neu"]["version"] == "1.9.0"
    zustand.vorab_setzen(db, True)             # ohne neue Pruefung: die fertige Fassung ist weiter da
    assert lauf.uebersicht(db)["neu"]["version"] == "1.9.0"


# ── die Wege: Dashboard und Werkzeug ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def rest(tmp_path, u, monkeypatch):
    import bewerbungs_assistent.dashboard as dash
    from bewerbungs_assistent.database import Database
    from fastapi.testclient import TestClient

    db = Database(tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    vorher = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app), db
    finally:
        dash._db = vorher
        db.close()


def test_der_einstellungs_endpunkt_prueft_beim_umschalten_gleich_neu(rest, monkeypatch):
    client, db = rest
    aufrufe = []

    def fake_pruefen(db_, **kw):
        aufrufe.append(kw)
        return {"status": "aktuell"}

    monkeypatch.setattr(lauf, "pruefen", fake_pruefen)
    r = client.post("/api/auto-update/einstellungen", json={"vorab": 1})
    assert r.status_code == 200, r.text
    assert r.json()["vorab"] is True
    assert len(aufrufe) == 1 and aufrufe[0].get("frisch") is True
    r = client.post("/api/auto-update/einstellungen", json={"vorab": 1})
    assert r.status_code == 200 and len(aufrufe) == 1, "derselbe Stand: keine zweite Pruefung"
    r = client.post("/api/auto-update/einstellungen", json={"vorab": 0})
    assert r.json()["vorab"] is False and len(aufrufe) == 2


def test_der_endpunkt_prueft_nicht_bei_anderen_einstellungen(rest, monkeypatch):
    client, db = rest
    aufrufe = []
    monkeypatch.setattr(lauf, "pruefen", lambda db_, **kw: aufrufe.append(kw))
    r = client.post("/api/auto-update/einstellungen", json={"stufe": "hinweis"})
    assert r.status_code == 200 and aufrufe == []


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **_kw):
        def deko(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return deko


def test_das_werkzeug_prueft_beim_umschalten_gleich_neu(tmp_path, u, monkeypatch):
    from bewerbungs_assistent.tools import update as tool_update

    mcp = _FakeMCP()
    db = FakeDb()
    tool_update.register(mcp, db, logging.getLogger("test"))
    aufrufe = []
    monkeypatch.setattr(lauf, "pruefen", lambda db_, **kw: aufrufe.append(kw) or {"status": "aktuell"})
    erg = mcp.tools["update_einstellungen_setzen"](vorab=1)
    assert erg["status"] == "gesetzt" and erg["geaendert"] == ["vorab"] and erg["vorab"] is True
    assert len(aufrufe) == 1
    erg = mcp.tools["update_einstellungen_setzen"](vorab=1)
    assert len(aufrufe) == 1, "derselbe Stand: keine zweite Pruefung"
