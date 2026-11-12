"""#1376 im Browser: der Einrichtungsdialog merkt den erreichten Schritt je
Profil; ein Neuladen beginnt nicht wieder bei Schritt 1. Der Test wartet auf
Zustaende (Datenbank, aktive Schaltflaeche), nicht auf Zeit."""
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

AKTIV = "button.glass-tab-active"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    pid = db.create_profile("Erika Musterfrau", "erika@example.com")
    db.set_user_preference(f"profile_onboarding_started_{pid}", True)
    db.set_user_preference(f"profile_onboarding_completed_{pid}", False)
    db.set_user_preference(f"profile_onboarding_dismissed_{pid}", False)
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
    yield f"http://127.0.0.1:{port}", db, pid
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
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


def _oeffnen(page, url):
    page.goto(url, wait_until="domcontentloaded")
    page.locator("#profile-onboarding-overlay").wait_for(state="visible", timeout=10000)


def _aktiver_schritt(page, text):
    page.locator(f"#profile-onboarding-overlay {AKTIV}", has_text=text).wait_for(state="visible", timeout=10000)


def test_der_erreichte_schritt_ueberlebt_das_neuladen(browser, server):
    url, db, pid = server
    page = browser.new_page(viewport={"width": 1440, "height": 960})
    try:
        _oeffnen(page, url)
        _aktiver_schritt(page, "1. Unterlagen")
        page.locator("#profile-onboarding-overlay button", has_text="3. Quellen").click()
        _aktiver_schritt(page, "3. Quellen")
        # Zustand abwarten: der Schritt steht in der Datenbank
        page.wait_for_function(
            "async (k) => (await (await fetch('/api/user-preferences/' + k)).json()).value === 'sources'",
            arg=f"profile_onboarding_step_{pid}", timeout=10000)
        assert db.get_user_preference(f"profile_onboarding_step_{pid}") == "sources"
        page.reload(wait_until="domcontentloaded")
        page.locator("#profile-onboarding-overlay").wait_for(state="visible", timeout=10000)
        _aktiver_schritt(page, "3. Quellen")
    finally:
        page.close()


@pytest.mark.parametrize("wert", ["unsinn", "", 7])
def test_ungueltiger_wert_faellt_auf_den_ersten_schritt_zurueck(browser, server, wert):
    url, db, pid = server
    db.set_user_preference(f"profile_onboarding_step_{pid}", wert)
    page = browser.new_page(viewport={"width": 1440, "height": 960})
    try:
        _oeffnen(page, url)
        _aktiver_schritt(page, "1. Unterlagen")
    finally:
        page.close()


def test_fremder_schritt_eines_anderen_profils_zaehlt_nicht(browser, server):
    url, db, pid = server
    db.set_user_preference(f"profile_onboarding_step_fremdes-profil", "jobs")
    page = browser.new_page(viewport={"width": 1440, "height": 960})
    try:
        _oeffnen(page, url)
        _aktiver_schritt(page, "1. Unterlagen")
    finally:
        page.close()
