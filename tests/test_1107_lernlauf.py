"""#1107: der Lernlauf haelt "Lernen aus" ein, laeuft nicht doppelt und
bleibt nach einem Neustart nicht als laufend stehen.

Die Tests pruefen das Verhalten, nicht den Text der Automatik-Karte
(H25: was die Datenschutz-Anzeige verspricht, muss der Code halten).
"""
from __future__ import annotations

import ast
import os
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Lernen"})
    yield d
    _warten()
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _warten():
    for t in threading.enumerate():
        if t.name == "automatik-lernen":
            t.join(timeout=15)


def _anzahl(db, tabelle, bedingung="1=1"):
    return db.connect().execute(f"SELECT COUNT(*) FROM {tabelle} WHERE {bedingung}").fetchone()[0]


@pytest.fixture
def regeln(monkeypatch):
    """Die Regeln liefern immer einen Kandidaten — so ist sichtbar, ob
    gespeichert wurde. Die Muster-Stufe wird still gestellt."""
    from bewerbungs_assistent.services import lerninsights
    gerufen = []

    def ableiten(db, budget_sekunden=20):
        gerufen.append(1)
        # #792: dieselbe Form wie der echte Rueckgabewert
        return {"kandidaten": [], "regeln_gelaufen": ["zeitmuster"],
                "regeln_mit_ergebnis": [], "regeln_uebersprungen": [],
                "regel_fehler": {}, "dauer_ms": 0, "abgebrochen": False}
    monkeypatch.setattr(lerninsights, "kandidaten_ableiten", ableiten)
    import bewerbungs_assistent.dashboard as dash
    monkeypatch.setattr(dash, "_run_analyze_user_patterns", lambda *a, **k: {"status": "test"})
    return gerufen


# ── AK 1: Lernen aus heisst aus, auf beiden Wegen ───────────────────

def test_knopf_weg_mit_lernen_aus(db, regeln):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    db.set_profile_setting("learning_enabled", False)
    dash._db = db
    antwort = TestClient(dash.app).post("/api/automatik/run-now", json={"kind": "lernen"}).json()
    _warten()
    assert antwort["status"] == "lernen_aus"
    assert "Datenschutz" in antwort["grund"]
    assert regeln == [], "die Regeln liefen trotzdem"
    assert _anzahl(db, "background_jobs", "job_type='lernen'") == 0
    assert db.get_automatik_settings()["lernen_last_at"] == "", "als gelaufen vermerkt"


def test_zeitplan_weg_mit_lernen_aus(db, regeln):
    from bewerbungs_assistent.services import automatik_scheduler as sch
    db.set_profile_setting("learning_enabled", False)
    db.set_automatik_settings(lernen_intervall_tage=db._AUTOMATIK_INTERVALS[-1])
    sch._tick(db)
    _warten()
    assert regeln == []
    assert _anzahl(db, "background_jobs", "job_type='lernen'") == 0
    # Vermerkt, damit nicht jeder Tick es erneut versucht.
    assert db.get_automatik_settings()["lernen_last_at"]


def test_mit_lernen_an_laufen_die_regeln(db, regeln):
    from bewerbungs_assistent.services import automatik_scheduler as sch
    assert sch.run_lernen_now(db)["status"] == "gestartet"
    _warten()
    assert regeln == [1]
    job = db.get_running_background_job("lernen")
    assert job is None, "nach dem Ende gilt der Lauf nicht mehr als laufend"


# ── AK 2: kein zweiter Lauf ─────────────────────────────────────────

def test_zweiter_start_waehrend_des_laufs(db, monkeypatch):
    from bewerbungs_assistent.services import automatik_scheduler as sch
    from bewerbungs_assistent.services import lerninsights
    import bewerbungs_assistent.dashboard as dash
    halt, drin = threading.Event(), threading.Event()

    def ableiten(db, budget_sekunden=20):
        drin.set()
        halt.wait(10)
        return {"kandidaten": [], "regeln_gelaufen": [], "regeln_mit_ergebnis": [],
                "regeln_uebersprungen": [], "regel_fehler": {}, "dauer_ms": 0,
                "abgebrochen": False}
    monkeypatch.setattr(lerninsights, "kandidaten_ableiten", ableiten)
    monkeypatch.setattr(dash, "_run_analyze_user_patterns", lambda *a, **k: {})
    try:
        assert sch.run_lernen_now(db)["status"] == "gestartet"
        assert drin.wait(5)
        assert sch.run_lernen_now(db)["status"] == "laeuft_bereits"
        dash._db = db
        from fastapi.testclient import TestClient
        r = TestClient(dash.app).post("/api/automatik/run-now", json={"kind": "lernen"}).json()
        assert r["status"] == "laeuft_bereits"
        assert db.get_automatik_settings()["lernen_last_at"] == "", \
            "ein abgewiesener Start gilt nicht als Lauf"
    finally:
        halt.set()
        _warten()


# ── AK 3: nach dem Neustart abgebrochen ─────────────────────────────

def test_unterbrochener_lauf_gilt_nach_neustart_als_abgebrochen(db):
    alt = db.create_background_job("lernen", {})
    db.connect().execute("UPDATE background_jobs SET status='laeuft' WHERE id=?", (alt,))
    neu = db.create_background_job("jobsuche", {})
    db.connect().commit()
    assert db.unterbrochene_jobs_abbrechen() == 2
    assert db.get_background_job(alt)["status"] == "abgebrochen"
    assert db.get_background_job(neu)["status"] == "abgebrochen"


def test_server_ruft_die_bereinigung():
    text = (SRC / "server.py").read_text(encoding="utf-8")
    assert "db.unterbrochene_jobs_abbrechen()" in text


# ── AK 4: eine Liste der Status ─────────────────────────────────────

def test_unbekannter_status_wird_abgewiesen(db):
    jid = db.create_background_job("lernen", {})
    with pytest.raises(ValueError):
        db.update_background_job(jid, "laeuft")


def test_jeder_geschriebene_status_steht_in_der_liste():
    from bewerbungs_assistent.database import Database
    erlaubt = set(Database.BACKGROUND_JOB_STATUS)
    funde = []
    for p in SRC.rglob("*.py"):
        baum = ast.parse(p.read_text(encoding="utf-8-sig"))
        for n in ast.walk(baum):
            if (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "update_background_job"
                    and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)):
                if n.args[1].value not in erlaubt:
                    funde.append(f"{p.name}:{n.lineno}: {n.args[1].value!r}")
    assert not funde, funde
