"""#1098 im Browser: Sicherung anlegen und einen Stand vormerken. Beleg ist\ndie Ablage nach dem Klick."""
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
    db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                        "status": "beworben"})
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
    for th in threading.enumerate():
        if th.name.startswith("pbp-sicherung"):
            th.join(timeout=10)
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


def test_sicherung_in_den_einstellungen(browser, server):
    url, db = server
    from bewerbungs_assistent.services import sicherung
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(f"{url}/#einstellungen", wait_until="domcontentloaded", timeout=30000)
        reiter = page.locator("[data-settings-reiter]")
        reiter.wait_for(timeout=15000)
        reiter.get_by_role("button", name="Datenschutz", exact=True).click()
        karte = page.get_by_test_id("sicherung-karte")
        karte.wait_for(timeout=10000)
        assert "Noch keine Sicherung" in karte.inner_text()
        karte.get_by_role("button", name="Jetzt sichern").click()
        for _ in range(100):
            if sicherung.liste(db):
                break
            page.wait_for_timeout(100)
        name = sicherung.liste(db)[0]["name"]
        page.reload(wait_until="domcontentloaded")
        page.locator("[data-settings-reiter]").get_by_role("button", name="Datenschutz", exact=True).click()
        karte = page.get_by_test_id("sicherung-karte")
        karte.locator("summary").click()
        karte.get_by_role("button", name="Diesen Stand wiederherstellen").first.click()
        karte.get_by_role("button", name="Ja, beim nächsten Start einspielen").click()
        page.get_by_test_id("sicherung-vorgemerkt").wait_for(timeout=10000)
        assert sicherung.vormerkung(db) == name
    finally:
        page.close()
