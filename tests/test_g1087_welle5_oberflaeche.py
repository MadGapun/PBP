"""Welle 5 aus #1087 im gerenderten Dashboard.

* H31 (G13): ein Link aus Claude (`#bewerbungen/<id>`) oeffnet die
  Timeline der Bewerbung, `#stellen/<hash>` springt zur Stelle.
* H21 (G1): der Expertenmodus laesst sich im Reiter System schalten.
"""
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
    db.save_profile({"name": "Erika Musterfrau"})
    aid = db.add_application({"title": "Sachbearbeitung Einkauf",
                              "company": "Musterbetrieb GmbH", "status": "beworben"})
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
    yield f"http://127.0.0.1:{port}", db, aid
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


def test_h31_link_aus_claude_oeffnet_die_timeline(browser, server):
    url, _db, aid = server
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(f"{url}/#bewerbungen/{aid}", wait_until="load", timeout=30000)
        page.wait_for_selector("text=Timeline - Sachbearbeitung Einkauf", timeout=15000)
    finally:
        page.close()


def test_h31_link_im_laufenden_dashboard(browser, server):
    """Auch ein Wechsel des Hash bei offener Seite springt (hashchange)."""
    url, _db, aid = server
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(f"{url}/#dashboard", wait_until="load", timeout=30000)
        page.wait_for_timeout(500)
        page.evaluate(f"window.location.hash = 'bewerbungen/{aid}'")
        page.wait_for_selector("text=Timeline - Sachbearbeitung Einkauf", timeout=15000)
    finally:
        page.close()


def test_h21_expertenmodus_im_reiter_system(browser, server):
    url, db, _aid = server
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(f"{url}/#einstellungen", wait_until="networkidle", timeout=30000)
        page.get_by_role("button", name="System", exact=True).first.click()
        karte = page.locator("[data-expertenmodus]")
        karte.wait_for(timeout=15000)
        assert "Ausgeschaltet" in karte.inner_text()
        karte.get_by_role("button", name="Einschalten").click()
        karte.get_by_text("Eingeschaltet").wait_for(timeout=10000)
        assert db.get_setting("expertenmodus") is True
    finally:
        page.close()
