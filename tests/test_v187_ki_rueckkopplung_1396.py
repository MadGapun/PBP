"""#1396 Schicht 3 - Rueckkopplung, Trefferquote und `ki_lernstand`.

Widerspricht der Mensch oder Claude der lokalen KI, wird das als Gegenbeispiel
gespeichert (`ollama_lag_richtig=0`) und bevorzugt gezeigt. Die Trefferquote
trennt Ergebnis und Grund, hat einen Verlauf und nennt "noch zu wenig", statt
eine Zahl zu erfinden. Alle Datenbanken sind isoliert (BA_DATA_DIR).
"""
from __future__ import annotations

import asyncio
import logging
import os

import pytest

TEXT = "Aufgaben und Anforderungen der Stelle im Team, mit Erfahrung. " * 3


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test 1396c"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung, titel="Projektleiter Maschinenbau"):
    db.save_jobs([{
        "hash": kennung, "title": titel, "company": "Musterwerk Nord GmbH",
        "location": "Hamburg", "url": f"https://example.com/1396c/{kennung}",
        "source": "stepstone", "description": TEXT, "score": 20,
    }])
    return db.resolve_job_hash(kennung)


def _ki_sagt(db, voll, urteil, grund="Falsche Branche."):
    from bewerbungs_assistent.services import ki_lernen
    assert ki_lernen.merke_urteil(db, voll, urteil, grund)
    if urteil == "PASST_NICHT":
        assert db.dismiss_job(voll, "profil_match_negativ", herkunft="automatik",
                              notiz=f"[Auto-Aussortierung] {grund}",
                              entschieden_von="ollama")


def _z(db, voll):
    return dict(db.connect().execute("SELECT * FROM jobs WHERE hash=?", (voll,)).fetchone())


# -- Die Gegenprobe an jedem Entscheidungsweg --------------------------------

def test_zurueckholen_einer_aussortierten_stelle_ist_ein_gegenbeispiel(db):
    from bewerbungs_assistent.services import ki_beispiele
    voll = _stelle(db, "r1")
    _ki_sagt(db, voll, "PASST_NICHT")
    assert _z(db, voll)["ollama_lag_richtig"] is None, "Ohne Mensch keine Gegenprobe."
    assert db.restore_job(voll)
    z = _z(db, voll)
    assert z["ollama_lag_richtig"] == 0 and z["ollama_geprueft_am"]
    pool = ki_beispiele.pool_laden(db)
    assert [(p["klasse"], p["gegenbeispiel"]) for p in pool] == [("passt", True)]


def test_claude_widerspricht_der_ki(db):
    voll = _stelle(db, "c1")
    _ki_sagt(db, voll, "PASST_NICHT")
    assert db.set_job_analysis(voll, "EMPFOHLEN", "Passt nach dem Lesen doch gut.")
    z = _z(db, voll)
    assert z["entschieden_von"] == "claude" and z["ollama_lag_richtig"] == 0
    # und Claude bestaetigt die KI
    voll2 = _stelle(db, "c2", "Erzieher Kita")
    _ki_sagt(db, voll2, "PASST_NICHT")
    db.set_job_analysis(voll2, "NICHT_EMPFOHLEN", "Fachfremd.")
    assert _z(db, voll2)["ollama_lag_richtig"] == 1


def test_mensch_sortiert_aus_wo_die_ki_passt_sagte_und_umgekehrt(db):
    a = _stelle(db, "m1")
    _ki_sagt(db, a, "PASST")
    db.dismiss_job(a, "zu_junior")
    assert _z(db, a)["ollama_lag_richtig"] == 0
    b = _stelle(db, "m2")
    _ki_sagt(db, b, "PASST", "Passt.")
    db.set_job_analysis(b, "EMPFOHLEN", "ok")
    assert _z(db, b)["ollama_lag_richtig"] == 1


def test_unsicher_ist_keine_behauptung(db):
    voll = _stelle(db, "u1")
    _ki_sagt(db, voll, "UNSICHER")
    db.dismiss_job(voll, "zu_junior")
    assert _z(db, voll)["ollama_lag_richtig"] is None


def test_eine_reparatur_ist_kein_wort_des_menschen(db):
    voll = _stelle(db, "p1")
    _ki_sagt(db, voll, "PASST_NICHT")
    db.restore_job(voll, durch_mensch=False)
    assert _z(db, voll)["ollama_lag_richtig"] is None


def test_die_eigene_entscheidung_der_ki_ist_keine_gegenprobe(db):
    voll = _stelle(db, "e1")
    _ki_sagt(db, voll, "PASST_NICHT")
    assert _z(db, voll)["ollama_lag_richtig"] is None  # nur Mensch/Claude zaehlen


def test_grund_getrennt_vom_ergebnis(db):
    # Ergebnis stimmt (beide: passt nicht), Grund trifft den Standardgrund.
    a = _stelle(db, "g1")
    _ki_sagt(db, a, "PASST_NICHT", "Falsche Branche, Fertigung statt Handel.")
    db.set_job_analysis(a, "NICHT_EMPFOHLEN", "x")
    db.dismiss_job(a, "falsche_branche", herkunft="ich")
    z = _z(db, a)
    assert z["ollama_lag_richtig"] == 1 and z["ollama_grund_traf"] == 1
    # Ergebnis stimmt, Grund ist ein anderer.
    b = _stelle(db, "g2")
    _ki_sagt(db, b, "PASST_NICHT", "Die Stelle ist zu junior.")
    db.dismiss_job(b, "zu_weit_entfernt", herkunft="ich")
    zb = _z(db, b)
    assert zb["ollama_lag_richtig"] == 1 and zb["ollama_grund_traf"] == 0
    # Grund der KI laesst sich keinem Standardgrund zuordnen: unbekannt, nicht geraten.
    c = _stelle(db, "g3")
    _ki_sagt(db, c, "PASST_NICHT", "Wirkt nicht stimmig.")
    db.dismiss_job(c, "zu_junior", herkunft="ich")
    assert _z(db, c)["ollama_grund_traf"] is None


# -- Lernstand ---------------------------------------------------------------

def _bewertet(db, n_richtig, n_falsch):
    for i in range(n_richtig):
        v = _stelle(db, f"lr{i}", f"Sachbearbeiter Einkauf {i}")
        _ki_sagt(db, v, "PASST_NICHT", "Falsche Branche.")
        db.dismiss_job(v, "falsche_branche", herkunft="ich")
    for i in range(n_falsch):
        v = _stelle(db, f"lf{i}", f"Projektleiter Anlagenbau {i}")
        _ki_sagt(db, v, "PASST_NICHT", "Falsche Branche.")
        db.restore_job(v)


def test_lernstand_nennt_noch_zu_wenig_statt_einer_zahl(db):
    from bewerbungs_assistent.services import ki_lernen
    _bewertet(db, 2, 1)
    st = ki_lernen.lernstand(db)
    assert st["bewertet"] == 3 and st["trefferquote_prozent"] is None
    assert st["datenbasis_ausreichend"] is False and "erst 3" in st["satz"]
    leer_db = ki_lernen.lernstand(db, min_basis=3)
    assert leer_db["trefferquote_prozent"] == pytest.approx(66.7, abs=0.1)


def test_lernstand_zahlen_fehlerbilder_abweichungen_verlauf(db):
    from bewerbungs_assistent.services import ki_lernen
    _bewertet(db, 6, 2)
    offen = _stelle(db, "off1")
    _ki_sagt(db, offen, "PASST_NICHT")  # noch keine Gegenprobe
    unsicher = _stelle(db, "uns1")
    ki_lernen.merke_urteil(db, unsicher, "UNSICHER")
    st = ki_lernen.lernstand(db)
    assert (st["gesehen"], st["bewertet"], st["richtig"], st["falsch"]) == (10, 8, 6, 2)
    assert st["unsicher"] == 1 and st["offen"] == 1
    assert st["trefferquote_prozent"] == 75.0 and st["datenbasis_ausreichend"]
    assert st["fehlerbilder"][0]["ki_sagte"] == "PASST_NICHT"
    assert st["fehlerbilder"][0]["richtig_war"] == "passt"
    assert st["fehlerbilder"][0]["anzahl"] == 2
    assert len(st["groesste_abweichungen"]) == 2
    assert st["groesste_abweichungen"][0]["ki_sagte"] == "PASST_NICHT"
    assert st["grund"]["bewertet"] == 6 and st["grund"]["traf"] == 6
    assert st["verlauf"] and sum(w["bewertet"] for w in st["verlauf"]) == 8
    assert "75.0 %" in st["satz"] and "Gegenbeispiele" in st["satz"]


def test_lernstand_ohne_ki_urteil_ist_ehrlich_leer(db):
    from bewerbungs_assistent.services import ki_lernen
    st = ki_lernen.lernstand(db)
    assert st["gesehen"] == 0 and st["trefferquote_prozent"] is None
    assert "noch keine Stelle beurteilt" in st["satz"]


# -- Werkzeug und Dashboard ---------------------------------------------------

def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def test_werkzeug_ki_lernstand(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent import tools
    from bewerbungs_assistent.tools import analyse
    mcp = FastMCP("test")
    analyse.register(mcp, db, logging.getLogger("test"))
    _bewertet(db, 6, 1)
    erg = _call(mcp, "ki_lernstand")
    assert erg["bewertet"] == 7 and erg["trefferquote_prozent"] is not None
    assert erg["ki_an"] is False and "naechster_schritt" in erg
    assert tools is not None


def test_api_genauigkeit_traegt_den_lernstand(db, monkeypatch):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent import dashboard
    monkeypatch.setattr(dashboard, "_db", db)
    _bewertet(db, 5, 0)
    erg = TestClient(dashboard.app).get("/api/llm/accuracy").json()
    assert "auto_aussortiert_gesamt" in erg, "die alten Felder bleiben"
    assert erg["lernstand"]["trefferquote_prozent"] == 100.0
    assert erg["lernstand"]["satz"]
