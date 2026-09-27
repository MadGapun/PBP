"""#1095 im Browser: Aussortieren nennt den Lerneffekt, Bearbeiten\nrechnet neu. Beleg ist die Datenbank nach dem Klick."""
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

TEXT = "Wir suchen Unterstützung im Lager. Aufgaben: Kommissionierung. " * 4


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
    db.set_search_criteria("keywords_muss", ["einkauf"])
    db.save_jobs([
        {"hash": "st1095a", "title": "Sachbearbeitung Einkauf", "company": "Musterbetrieb GmbH",
         "url": "https://example.com/1095a", "source": "manuell", "description": TEXT,
         "location": "Hamburg"},
        {"hash": "st1095b", "title": "Lagerhilfe Einkauf", "company": "Beispiel AG",
         "url": "https://example.com/1095b", "source": "manuell", "description": TEXT,
         "location": "Hamburg"},
    ])
    # Regler auf -2 und elf Nennungen: die zwoelfte loest den Lerneffekt aus (#908)
    db.connect().execute("UPDATE scoring_config SET value=-2 "
                         "WHERE dimension='stellentyp' AND sub_key='zeitarbeit'")
    db.connect().commit()
    db.set_setting("dismiss_counts", {"zeitarbeit": 11})
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


def _stellen_seite(browser, url):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    # Die Stellenseite fragt laufend nach — "networkidle" kommt dort nie.
    page.goto(f"{url}/#stellen", wait_until="domcontentloaded", timeout=30000)
    page.get_by_role("heading", name="Sachbearbeitung Einkauf").first.wait_for(timeout=20000)
    return page


def test_aussortieren_lernt_und_sagt_es(browser, server):
    url, db = server
    page = _stellen_seite(browser, url)
    try:
        page.get_by_role("button", name="Passt nicht", exact=True).first.click()
        page.get_by_text("Warum passt diese Stelle nicht?").wait_for(state="visible")
        page.get_by_role("button", name="Zeitarbeit", exact=True).click()
        page.get_by_role("button", name="Aussortieren", exact=True).click()
        page.get_by_text("PBP hat gelernt").wait_for(timeout=10000)
        assert db.get_setting("dismiss_counts", {})["zeitarbeit"] == 12
        wert = db.connect().execute(
            "SELECT MIN(value) FROM scoring_config "
            "WHERE dimension='stellentyp' AND sub_key='zeitarbeit'").fetchone()[0]
        assert wert < -2
    finally:
        page.close()


def test_bearbeiten_rechnet_neu(browser, server):
    url, db = server
    vorher = db.get_job("st1095a")["score"]
    page = _stellen_seite(browser, url)
    try:
        page.get_by_role("heading", name="Sachbearbeitung Einkauf").first.click()
        page.get_by_role("heading", name="Stellendetails").wait_for(state="visible")
        page.get_by_role("button", name="Bearbeiten").first.click()
        feld = page.locator("textarea").first
        feld.fill("Einkauf, Einkauf und nochmal Einkauf: Bestellungen und Lieferanten. " * 4)
        page.get_by_role("button", name="Speichern", exact=True).click()
        page.get_by_text("Punkte neu berechnet").wait_for(timeout=10000)
        job = db.get_job("st1095a")
        assert "nochmal Einkauf" in job["description"]
        assert job["score"] != vorher
    finally:
        page.close()
