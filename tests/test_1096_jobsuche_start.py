"""#1096: Claude, Dashboard-Knopf und Automatik starten die Jobsuche ueber
denselben Weg — mit denselben Schritten und einem Fehlerzustand."""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Suche"})
    d.set_search_criteria("keywords_muss", ["einkauf"])
    d.set_search_criteria("stellentypen", ["festanstellung", "freelance"])
    d.set_profile_setting("active_sources", ["bundesagentur", "linkedin"])
    import bewerbungs_assistent.dashboard as dash
    dash._db = d
    nachlauf = []
    from bewerbungs_assistent.services import auto_aussortierung
    monkeypatch.setattr(auto_aussortierung, "nach_suche",
                        lambda _db, job_id: nachlauf.append(job_id))
    d.nachlauf = nachlauf
    yield d
    _warten()
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _warten():
    for t in threading.enumerate():
        if t.name.startswith("pbp-jobsuche"):
            t.join(timeout=10)


def _fertig_stub(db, job_id, params):
    db.update_background_job(job_id, "fertig", progress=100, result={"total": 0})


def _werkzeug(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1096")
    register_all(mcp, db, logging.getLogger("test.1096"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def _starten(db, weg):
    if weg == "claude":
        return _werkzeug(db, "jobsuche_starten", {})
    if weg == "dashboard":
        from fastapi.testclient import TestClient
        import bewerbungs_assistent.dashboard as dash
        return TestClient(dash.app).post("/api/jobsuche/start", json={}).json()
    from bewerbungs_assistent.services.automatik_scheduler import run_jobsuche_now
    return run_jobsuche_now(db)


# ── AK 4 und 2: dieselben Schritte ──────────────────────────────────

@pytest.mark.parametrize("weg", ["claude", "dashboard", "automatik"])
def test_jeder_weg_dieselben_schritte(db, monkeypatch, weg):
    import bewerbungs_assistent.job_scraper as js
    monkeypatch.setattr(js, "run_search", _fertig_stub)
    erg = _starten(db, weg)
    assert erg["status"] == "gestartet", erg
    _warten()
    job = db.get_background_job(erg["job_id"])
    p = job["params"]
    assert p["quellen"] == ["bundesagentur"]
    assert p["browser_quellen"] == ["linkedin"]          # #1049
    assert [b["stellentyp"] for b in p["stellentyp_ohne_quelle"]] == ["freelance"]  # #906
    assert p["herkunft"] == weg
    assert db.nachlauf == [erg["job_id"]], "Nachlauf (#1092) fehlt"


def test_lauf_hinweis_nennt_stellenart_ohne_quelle(db, monkeypatch):
    import bewerbungs_assistent.job_scraper as js
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    monkeypatch.setattr(js, "run_search", _fertig_stub)
    _starten(db, "automatik")
    _warten()
    last = TestClient(dash.app).get("/api/jobsuche/last").json()
    assert last["stellentyp_ohne_quelle"] == ["freelance"]
    assert last["quellen"]["nur_browser"] == 1


def test_automatik_uebernimmt_keine_erstauswahl(db, monkeypatch):
    import bewerbungs_assistent.job_scraper as js
    from bewerbungs_assistent.services import jobsuche_start
    monkeypatch.setattr(js, "run_search", _fertig_stub)
    db.set_profile_setting("active_sources", [])
    erg = jobsuche_start.starten(db, quellen=["bundesagentur"], herkunft="automatik")
    assert "erstauswahl" not in erg["schritte"]
    assert db.get_profile_setting("active_sources", []) == []
    _warten()
    erg = jobsuche_start.starten(db, quellen=["bundesagentur"], herkunft="claude")
    assert db.get_profile_setting("active_sources", []) == ["bundesagentur"]


# ── AK 3: Abbruch ist ein Fehler, danach laeuft ein neuer Start ──────

def test_abbruch_der_automatik_ist_fehler(db, monkeypatch):
    import bewerbungs_assistent.job_scraper as js

    def kaputt(_db, job_id, params):
        raise RuntimeError("Quelle antwortet nicht")
    monkeypatch.setattr(js, "run_search", kaputt)
    erg = _starten(db, "automatik")
    _warten()
    job = db.get_background_job(erg["job_id"])
    assert job["status"] == "fehler" and "Quelle antwortet nicht" in job["message"]
    monkeypatch.setattr(js, "run_search", _fertig_stub)
    assert _starten(db, "dashboard")["status"] == "gestartet"


def test_lauf_ohne_abschluss_ist_fehler(db, monkeypatch):
    import bewerbungs_assistent.job_scraper as js
    monkeypatch.setattr(js, "run_search", lambda *_a, **_k: None)
    erg = _starten(db, "automatik")
    _warten()
    assert db.get_background_job(erg["job_id"])["status"] == "fehler"
    assert db.nachlauf == []


def test_ohne_suchbegriffe_startet_kein_weg(db):
    db.set_search_criteria("keywords_muss", [])
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    r = TestClient(dash.app).post("/api/jobsuche/start", json={})
    assert r.status_code == 400 and "Suchbegriffe" in r.json()["nachricht"]
    assert _starten(db, "automatik")["status"] == "keine_suchbegriffe"
    assert _starten(db, "claude")["status"] == "keine_suchbegriffe"


# ── AK 1: Guard ─────────────────────────────────────────────────────

def test_nur_ein_ort_legt_den_suchjob_an():
    funde = []
    for p in SRC.rglob("*.py"):
        text = p.read_text(encoding="utf-8-sig")
        if 'create_background_job("jobsuche"' in text:
            funde.append(p.relative_to(SRC).as_posix())
    assert funde == ["services/jobsuche_start.py"], funde


# ── Watchdog: Zeitlimit je Quelle, ein fertiger Lauf bleibt fertig ───

def test_zeitlimit_richtet_sich_nach_den_quellen():
    from bewerbungs_assistent.job_scraper.jobspy_source import LINKEDIN_BUDGET_MAX
    from bewerbungs_assistent.services import jobsuche_start as js
    assert js.zeitlimit(["bundesagentur"]) == js.ZEITLIMIT_SEK
    assert js.zeitlimit(["bundesagentur", "jobspy_linkedin"]) == \
        js.ZEITLIMIT_SEK + LINKEDIN_BUDGET_MAX


def test_langlauf_quellen_wie_im_suchlauf():
    """Der Suchlauf fuehrt seine Langlaeufer in _LANGLAUF_SCHAETZER; der
    Watchdog muss dieselben kennen, sonst kappt er deren Budget."""
    import re
    from bewerbungs_assistent.services import jobsuche_start as js
    text = (SRC / "job_scraper" / "__init__.py").read_text(encoding="utf-8")
    zeile = re.search(r"_LANGLAUF_SCHAETZER = \{([^}]*)\}", text).group(1)
    assert set(re.findall(r'"([a-z_]+)"\s*:', zeile)) == set(js.LANGLAUF_QUELLEN)


def _watchdog_lauf(db, monkeypatch, fertig_vorher: bool):
    """Ein Lauf, der laenger als das Zeitlimit lebt; wahlweise hat die
    Suche selbst schon abgeschlossen (Nachladen laeuft noch)."""
    import bewerbungs_assistent.job_scraper as scr
    from bewerbungs_assistent.services import jobsuche_start as js
    monkeypatch.setattr(js, "ZEITLIMIT_SEK", 0.2)
    halt = threading.Event()

    def lang(db_, job_id, params):
        if fertig_vorher:
            db_.update_background_job(job_id, "fertig", progress=100, result={"total": 0})
        else:
            db_.update_background_job(job_id, "running", progress=10)
        halt.wait(5)
    monkeypatch.setattr(scr, "run_search", lang)
    erg = js.starten(db, herkunft="automatik")
    job_id = erg["job_id"]
    for t in threading.enumerate():
        if t.name == f"pbp-watchdog-{job_id[:8]}":
            t.join(timeout=5)
    status = (db.get_background_job(job_id) or {}).get("status")
    halt.set()
    return status


def test_watchdog_ueberschreibt_keinen_fertigen_lauf(db, monkeypatch):
    assert _watchdog_lauf(db, monkeypatch, fertig_vorher=True) == "fertig"


def test_watchdog_beendet_eine_haengende_suche(db, monkeypatch):
    assert _watchdog_lauf(db, monkeypatch, fertig_vorher=False) == "fehler"
