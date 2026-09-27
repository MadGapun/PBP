"""#1037 im Browser: der Haken fuer die Fahrstrecke. Beleg ist die
Einstellung in der Datenbank nach dem Klick."""
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

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "pbp.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
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
    yield f"http://127.0.0.1:{port}", db
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


def _suche(browser, url):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(f"{url}/#suche", wait_until="domcontentloaded", timeout=30000)
    haken = page.get_by_test_id("fahrstrecke-haken")
    haken.wait_for(timeout=15000)
    return page, haken


def test_ohne_schluessel_gesperrt_mit_weg_zum_schluessel(browser, server):
    url, db = server
    page, haken = _suche(browser, url)
    try:
        box = haken.get_by_role("checkbox")
        assert box.is_disabled() and not box.is_checked()
        assert "nur Auto" in haken.inner_text()
        assert "nicht für Bus und Bahn" in haken.inner_text()
        page.get_by_test_id("fahrstrecke-zum-schluessel").click()
        page.get_by_test_id("routing-card").wait_for(timeout=10000)
        assert "(nur Auto)" in page.get_by_test_id("routing-card").inner_text()
    finally:
        page.close()


def test_mit_schluessel_setzt_der_klick_den_haken(browser, server):
    url, db = server
    from bewerbungs_assistent.services import routing
    db.set_setting(routing.EINSTELLUNG_SCHLUESSEL, "test-schluessel-ohne-bedeutung-1037")
    page, haken = _suche(browser, url)
    try:
        assert haken.get_by_test_id("fahrstrecke-schluessel-da").count() == 1
        box = haken.get_by_role("checkbox")
        assert box.is_enabled() and not box.is_checked()
        box.click()
        for _ in range(50):
            if routing.aktiv(db):
                break
            time.sleep(0.1)
        assert routing.aktiv(db) is True
        box.click()
        for _ in range(50):
            if not routing.haken(db):
                break
            time.sleep(0.1)
        assert routing.haken(db) is False
    finally:
        page.close()
