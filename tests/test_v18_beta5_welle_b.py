"""Tests fuer v1.8.0-beta.5 — Welle B: Quellen.

B25 (#735): scraper_runs-Historie + Langzeit-Auswertung + Claude-Handoff.
B16 (#627): Custom-Karriereseiten als Handoff-Quellen (kein Auto-Scraping).
B18 (#656): Playwright/Chromium als I10-Komponente (Detection + Install
via `playwright install` — hier gemockt).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


def _tools(tmp_db):
    from bewerbungs_assistent.tools.jobs import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp.tools


# ── B25: Lauf-Historie ───────────────────────────────────────────────────


def test_update_scraper_health_schreibt_historie(tmp_db):
    tmp_db.update_scraper_health("adzuna", "ok", count=12, time_s=3.5,
                                 new_count=4)
    tmp_db.update_scraper_health("adzuna", "fehler", count=0, time_s=1.0,
                                 detail="timeout", error_class="server_weg")
    runs = tmp_db.get_scraper_runs("adzuna")
    assert len(runs) == 2
    neuester = runs[0]  # DESC
    assert neuester["state"] == "fail"
    assert neuester["error_class"] == "server_weg"
    assert runs[1]["state"] == "ok"
    assert runs[1]["new_count"] == 4


def test_langzeit_auswertung_trend_und_empfehlung(tmp_db):
    tools = _tools(tmp_db)
    # Ohne Daten: ehrlicher Hinweis
    assert tools["quellen_langzeit_auswertung"]()["status"] == "keine_daten"

    # Quelle A: liefert konstant -> behalten
    for _ in range(4):
        tmp_db.update_scraper_health("gut", "ok", count=10, new_count=3)
    # Quelle B: nur Fehler -> deaktivieren-Empfehlung
    for _ in range(4):
        tmp_db.update_scraper_health("kaputtquelle", "fehler", count=0,
                                     error_class="blockiert")
    # Quelle C: frueher Treffer, zuletzt nichts -> versiegt
    conn = tmp_db.connect()
    alt = (datetime.now() - timedelta(days=5)).isoformat()
    for i in range(2):
        conn.execute(
            "INSERT INTO scraper_runs (id, scraper_name, run_at, state, "
            "count, new_count) VALUES (?,?,?,?,?,?)",
            (f"alt{i}", "versiegt_quelle", alt, "ok", 5, 5))
    conn.commit()
    for _ in range(2):
        tmp_db.update_scraper_health("versiegt_quelle", "ok", count=0,
                                     new_count=0)

    result = tools["quellen_langzeit_auswertung"](tage=30)
    per = {q["quelle"]: q for q in result["quellen"]}
    assert per["gut"]["empfehlung"] == "behalten"
    assert per["gut"]["neu"] == 12
    assert per["kaputtquelle"]["empfehlung"].startswith("deaktivieren")
    assert per["kaputtquelle"]["fehlerklassen"] == {"blockiert": 4}
    assert per["versiegt_quelle"]["trend"] == "versiegt"


# ── B25: Handoff ─────────────────────────────────────────────────────────


def test_quelle_handoff_bekannte_und_unbekannte(tmp_db):
    tools = _tools(tmp_db)
    result = tools["quelle_handoff"](quelle="gulp", keyword="PLM Consultant")
    assert result["status"] == "handoff"
    assert "gulp.de" in result["url"]
    assert "PLM+Consultant" in result["url"]
    assert "querySelectorAll" in result["extraction_js"]
    assert "stelle_manuell_anlegen" in result["anleitung"]

    result = tools["quelle_handoff"](quelle="kimeta", keyword="PLM",
                                     ort="Hamburg")
    assert "kimeta.de" in result["url"] and "Hamburg" in result["url"]

    result = tools["quelle_handoff"](quelle="gibtsnicht", keyword="x")
    assert result["status"] == "kein_template"
    assert "custom_quelle_hinzufuegen" in result["hinweis"]


# ── B16: Custom-Quellen ──────────────────────────────────────────────────


def test_custom_quellen_lifecycle(tmp_db, monkeypatch):
    tools = _tools(tmp_db)
    r = tools["custom_quelle_hinzufuegen"](name="Acme Karriere",
                                           url="https://karriere.acme.example/jobs")
    assert r["status"] == "angelegt"
    # Duplikat + Validierung
    assert "fehler" in tools["custom_quelle_hinzufuegen"](
        name="Nochmal", url="https://karriere.acme.example/jobs/")
    assert "fehler" in tools["custom_quelle_hinzufuegen"](name="X", url="ftp://x")

    liste = tools["custom_quellen_anzeigen"]()
    assert liste["anzahl"] == 1
    quelle = liste["quellen"][0]
    assert quelle["handoff"]["url"] == "https://karriere.acme.example/jobs"
    assert "extraction_js" in quelle["handoff"]

    assert tools["custom_quelle_loeschen"](quelle_id=quelle["quelle_id"])["status"] == "geloescht"
    assert tools["custom_quellen_anzeigen"]()["anzahl"] == 0
    assert "fehler" in tools["custom_quelle_loeschen"](quelle_id="nix")


def test_health_check_pingt_custom_quellen(tmp_db, monkeypatch):
    tools = _tools(tmp_db)
    sid = tmp_db.add_custom_source("Acme", "https://karriere.acme.example")

    import bewerbungs_assistent.tools.jobs as jobs_mod
    import bewerbungs_assistent.job_scraper.health as health_mod
    monkeypatch.setattr(health_mod, "get_probable_sources", lambda: [])

    class FakeResp:
        status_code = 200

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kw):
            return FakeResp()

    import httpx
    monkeypatch.setattr(httpx, "Client", FakeClient)
    result = tools["quellen_health_check"](quellen=[], parallel=False)
    assert result["custom_quellen"][0]["reachable"] is True
    assert result["custom_quellen"][0]["http_status"] == 200
    state = tmp_db.get_custom_sources()[0]
    assert state["last_status"] == "HTTP 200"
    assert state["last_check_at"]


# ── B18: Playwright-Komponente ───────────────────────────────────────────


def test_playwright_komponente_detection(tmp_db, tmp_path, monkeypatch):
    from bewerbungs_assistent.services import components
    assert "playwright-chromium" in components.COMPONENT_DEFS

    # Chromium-Ordner vorhanden -> verfuegbar (Paket ist im venv installiert)
    fake_dir = tmp_path / "ms-playwright" / "chromium-1234"
    fake_dir.mkdir(parents=True)
    monkeypatch.setattr(components, "_playwright_chromium_dir",
                        lambda: str(fake_dir))
    status = components.get_component_status(tmp_db, "playwright-chromium")
    assert status["verfuegbar"] is True
    assert status["version"]  # playwright-Paketversion

    # Kein Chromium -> nicht installiert
    monkeypatch.setattr(components, "_playwright_chromium_dir", lambda: None)
    status = components.get_component_status(tmp_db, "playwright-chromium")
    assert status["verfuegbar"] is False


def test_playwright_install_ruft_playwright_install(tmp_db, tmp_path, monkeypatch):
    from bewerbungs_assistent.services import components
    calls = []
    monkeypatch.setattr(components, "_playwright_chromium_dir",
                        lambda: str(tmp_path) if calls else None)

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        assert cmd[1:] == ["-m", "playwright", "install", "chromium"]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(components.subprocess, "run", fake_run)
    result = components.install_component(tmp_db, "playwright-chromium")
    assert result["status"] == "installiert"
    assert len(calls) == 1
    assert tmp_db.get_component_state("playwright-chromium")["status"] == "installiert"
