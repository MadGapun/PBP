"""#1396 im Browser: die Karte "Wie gut urteilt die lokale KI?" unter Einstellungen > Lokale KI.

Der Test wartet auf Zustaende (Karte sichtbar, Satz geladen), nicht auf Zeit. Die echte
lokale KI (Ollama, Port 11434) wird nie erreicht: `PBP_LLM_MOCK=1` ersetzt die Erkennung.
Gegen das GEBAUTE Bundle (nach JSX-Aenderungen `pnpm exec vite build`).
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TEXT = "Aufgaben: Konstruktion von Maschinen. Anforderungen: Erfahrung im Team. " * 2


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    os.environ["PBP_LLM_MOCK"] = "1"
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.services import ki_lernen, llm_service
    import bewerbungs_assistent.dashboard as dash

    llm_service.reset_llm_service()
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    pid = db.create_profile("Erika Musterfrau", "erika@example.com")
    db.set_user_preference(f"profile_onboarding_completed_{pid}", True)
    db.set_profile_setting("llm_local_state", "active")
    for i in range(6):
        db.save_jobs([{"hash": f"b{i}", "title": f"Konstrukteur Variante {i}", "company": "Musterwerk Nord GmbH",
                       "url": f"https://example.com/browser/{i}", "source": "stepstone",
                       "description": TEXT, "score": 10}])
        voll = db.resolve_job_hash(f"b{i}")
        ki_lernen.merke_urteil(db, voll, "PASST_NICHT", "Falsche Branche.")
        db.dismiss_job(voll, "profil_match_negativ", herkunft="automatik",
                       notiz="[Auto-Aussortierung] Falsche Branche.", entschieden_von="ollama")
        if i == 0:
            db.restore_job(voll)            # Mensch holt zurueck: die KI lag falsch
        else:
            db.dismiss_job(voll, "falsche_branche", herkunft="ich")  # Mensch bestaetigt
    dash._db = db
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(dash.app, host="127.0.0.1", port=port, log_level="warning"))
    srv.install_signal_handlers = lambda: None
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    llm_service.reset_llm_service()
    os.environ.pop("PBP_LLM_MOCK", None)
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture(scope="module")
def browser():
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def test_die_karte_zeigt_trefferquote_satz_und_abweichung(browser, server):
    page = browser.new_page(viewport={"width": 1440, "height": 1400})
    try:
        page.goto(f"{server}/#einstellungen", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_function(
            "() => document.querySelector('[data-settings-reiter]') !== null", timeout=15000)
        page.evaluate("() => document.dispatchEvent(new CustomEvent('settings-nav', {detail: {tab: 'ai'}}))")
        karte = page.locator("[data-testid=ki-lernstand]")
        karte.wait_for(state="visible", timeout=15000)
        satz = page.locator("[data-testid=ki-lernstand-satz]")
        satz.wait_for(state="visible", timeout=10000)
        text = karte.inner_text()
        assert "wie gut urteilt die lokale ki?" in text.lower()
        assert "83.3 %" in text                      # 5 von 6 richtig
        assert "Gegenbeispiele" in satz.inner_text()  # was der Mensch tun kann: zurueckholen
        assert "Es gibt nichts einzustellen" in text
        assert "Die KI sagte passt nicht, richtig war passt" in text
    finally:
        page.close()
