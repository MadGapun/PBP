"""Welle 6 aus #1087 im gerenderten Dashboard.

* G61: Top-Stellen nur mit Punkten ueber 0; Bewerbungen pro Woche mit
  beschriftetem Umschalter; kein 0-EUR-Gehalt.
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

TEXT = ("Wir suchen eine Sachbearbeitung im Einkauf. Aufgaben: Disposition, "
        "Bestellabwicklung mit SAP MM, Lieferantenkommunikation. ") * 3


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
        {"hash": "g61gut", "title": "Sachbearbeitung Einkauf", "company": "Musterbetrieb GmbH",
         "url": "https://example.com/g61gut", "source": "manuell", "description": TEXT,
         "location": "Hamburg", "score": 5},
        {"hash": "g61neg", "title": "Lagerhelfer Nachtschicht", "company": "Beispiel AG",
         "url": "https://example.com/g61neg", "source": "manuell", "description": "Lager " * 30,
         "location": "Hamburg", "score": -2},
    ])
    db.add_application({"title": "Einkauf", "company": "Musterbetrieb GmbH", "status": "beworben"})
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


def test_g61_dashboard_kennzahlen(browser, server):
    url, _db = server
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(f"{url}/#dashboard", wait_until="networkidle", timeout=30000)
        umschalter = page.locator("[data-wochen-ansicht]")
        umschalter.wait_for(timeout=15000)
        assert "seit der ersten Bewerbung" in umschalter.inner_text()
        umschalter.get_by_role("button", name="letzte 30 Tage").click()
        assert umschalter.get_by_role("button", name="letzte 30 Tage").get_attribute("aria-pressed") == "true"
        text = page.inner_text("body")
        assert "Bew. / Woche" not in text
        assert "0 – 0 EUR" not in text
        top = page.get_by_role("heading", name="Top-Stellen").locator("xpath=ancestor::section[1]")
        top.get_by_text("Sachbearbeitung Einkauf").first.wait_for(timeout=10000)
        assert "Lagerhelfer Nachtschicht" not in top.inner_text()
    finally:
        page.close()


def _seite(browser, url, reiter):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(f"{url}/#{reiter}", wait_until="networkidle", timeout=30000)
    return page


def test_g67_dialog_fragt_vor_dem_verwerfen(browser, server):
    url, _db = server
    page = _seite(browser, url, "kontakte")
    try:
        page.get_by_role("button", name="Neuer Kontakt").first.click()
        page.get_by_placeholder("z.B. Maria Mustermann").fill("Erika Beispiel")
        page.keyboard.press("Escape")
        frage = page.locator("[data-verwerfen-frage]")
        frage.wait_for(timeout=5000)
        frage.get_by_role("button", name="Weiter bearbeiten").click()
        assert page.get_by_placeholder("z.B. Maria Mustermann").input_value() == "Erika Beispiel"
        page.locator("[data-modal-schliessen]").last.click()
        page.locator("[data-verwerfen-frage]").get_by_role("button", name="Verwerfen").click()
        page.get_by_placeholder("z.B. Maria Mustermann").wait_for(state="detached", timeout=5000)
    finally:
        page.close()


def test_g67_statuswechsel_mit_rueckgaengig(browser, server):
    url, db = server
    aid = db.get_applications()[0]["id"]
    page = _seite(browser, url, "bewerbungen")
    try:
        page.get_by_role("button", name="Beworben", exact=True).first.click()
        page.get_by_text("Abgelehnt", exact=True).last.click()
        toast = page.get_by_text("die Bewerbung ist jetzt im Archiv")
        toast.wait_for(timeout=10000)
        page.get_by_role("button", name="Rückgängig").first.click()
        page.get_by_text("Zurückgesetzt auf").wait_for(timeout=10000)
        assert db.get_application(aid)["status"] == "beworben"
    finally:
        page.close()


def test_g67_folgenreiches_fragt_im_eigenen_dialog(browser, server):
    url, db = server
    cid = db.add_contact({"full_name": "Erika Beispiel", "company": "Musterbetrieb GmbH"})
    page = _seite(browser, url, "kontakte")
    try:
        page.get_by_text("Erika Beispiel").first.click()
        page.get_by_role("button", name="Löschen").first.click()
        dialog = page.locator("[data-bestaetigung]")
        dialog.wait_for(timeout=5000)
        dialog.get_by_role("button", name="Abbrechen").click()
        page.wait_for_timeout(500)
        assert any(k["id"] == cid for k in db.list_contacts())
        page.get_by_role("button", name="Löschen").first.click()
        page.locator("[data-bestaetigung]").get_by_role("button", name="Ja").click()
        page.get_by_text("Kontakt gelöscht").wait_for(timeout=5000)
        assert not any(k["id"] == cid for k in db.list_contacts())
    finally:
        page.close()
