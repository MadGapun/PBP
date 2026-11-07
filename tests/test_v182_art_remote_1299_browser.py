"""#1299 im Browser: Anstellungsform und Remote im Stellen-Detail aendern. Beleg ist die Datenbank nach dem Klick.

Gegen das GEBAUTE Bundle (nach JSX-Aenderungen `pnpm exec vite build`). Testdaten fiktiv.
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

TEXT = "Wir suchen Unterstützung in der Projektsteuerung. Aufgaben: Planung und Abstimmung. " * 4


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
    db.save_jobs([
        {"hash": "st1299a", "title": "Projektsteuerung Musterprojekt", "company": "Musterfirma GmbH",
         "url": "https://example.com/1299a", "source": "manuell", "description": TEXT,
         "location": "Musterstadt", "employment_type": "festanstellung", "remote_level": "unbekannt"},
    ])
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


def _bearbeiten(browser, url):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"{url}/#stellen", wait_until="domcontentloaded", timeout=30000)
    page.get_by_role("heading", name="Projektsteuerung Musterprojekt").first.wait_for(timeout=20000)
    page.get_by_role("heading", name="Projektsteuerung Musterprojekt").first.click()
    page.get_by_role("heading", name="Stellendetails").wait_for(state="visible")
    page.get_by_role("button", name="Bearbeiten").first.click()
    page.get_by_test_id("stelle-merkmale").wait_for(state="visible")
    return page


def _zeile(db):
    return dict(db.connect().execute("SELECT * FROM jobs WHERE hash=?",
                                     (db.resolve_job_hash("st1299a"),)).fetchone())


def test_auswahl_setzt_art_und_remote_von_hand(browser, server):
    url, db = server
    page = _bearbeiten(browser, url)
    try:
        # Eigene Auswahlliste (G71): Rolle combobox, Eintraege als option.
        auswahl = page.get_by_test_id("stelle-merkmale").get_by_role("combobox")
        auswahl.nth(0).click()
        page.get_by_role("option", name="Freelance", exact=True).click()
        auswahl.nth(2).click()
        page.get_by_role("option", name="Remote", exact=True).click()
        page.get_by_role("button", name="Speichern", exact=True).click()
        page.get_by_text("kein Suchlauf überschreibt").first.wait_for(timeout=10000)
        z = _zeile(db)
        assert (z["employment_type"], z["remote_level"]) == ("freelance", "remote")
        assert (z["art_quelle"], z["remote_quelle"], z["umfang_quelle"]) == ("mensch", "mensch", None)
    finally:
        page.close()


def test_unberuehrte_auswahl_markiert_nichts(browser, server):
    url, db = server
    page = _bearbeiten(browser, url)
    try:
        page.locator("textarea").first.fill(TEXT + " Ergänzung.")
        page.get_by_role("button", name="Speichern", exact=True).click()
        page.get_by_text("Stelle aktualisiert").first.wait_for(timeout=10000)
        z = _zeile(db)
        assert "Ergänzung" in z["description"]
        assert (z["art_quelle"], z["remote_quelle"], z["umfang_quelle"]) == (None, None, None)
    finally:
        page.close()
