"""Welle 7 aus #1087 im gerenderten Dashboard (G71).

Heller Modus, Dialog mit Fokusfalle, Auswahlfeld mit Tastatur und die
Suche auf dem Handy — gemessen am gerenderten Bild, nicht am Quelltext.
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
        "Bestellabwicklung, Lieferantenkommunikation. ") * 3


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
        {"hash": "g71eins", "title": "Sachbearbeitung Einkauf", "company": "Musterbetrieb GmbH",
         "url": "https://example.com/g71eins", "source": "manuell", "description": TEXT,
         "location": "Hamburg", "score": 5},
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


HELLIGKEIT = """(el) => {
  const farbe = (wert) => (wert.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
  const lum = (rgb) => {
    const k = rgb.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2];
  };
  const s = getComputedStyle(el);
  return { hinten: lum(farbe(s.backgroundColor)), text: lum(farbe(s.color)) };
}"""


def _seite(browser, url, reiter, hell=False, breite=1400):
    page = browser.new_page(viewport={"width": breite, "height": 900})
    if hell:
        page.add_init_script("try { localStorage.setItem('pbp-theme-mode', 'light'); } catch (e) {}")
    page.goto(f"{url}/#{reiter}", wait_until="networkidle", timeout=30000)
    return page


def test_g71_suche_und_auswahl_im_hellen_modus(browser, server):
    url, _db = server
    page = _seite(browser, url, "bewerbungen", hell=True)
    try:
        assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "light"
        suche = page.locator("[data-globale-suche] input[type=search]")
        suche.fill("Einkauf")
        panel = page.locator("[data-suchergebnisse]")
        panel.wait_for(timeout=10000)
        werte = panel.evaluate(HELLIGKEIT)
        assert werte["hinten"] > 0.8, werte
        eintrag = panel.locator("p.text-ink").first
        assert eintrag.evaluate(HELLIGKEIT)["text"] < 0.1
        page.keyboard.press("Escape")
        auswahl = page.get_by_role("combobox", name="Beworben", exact=True).first
        auswahl.click()
        liste = page.get_by_role("listbox")
        liste.wait_for(timeout=5000)
        hinten = liste.locator("xpath=..").evaluate(HELLIGKEIT)["hinten"]
        assert hinten > 0.8, hinten
    finally:
        page.close()


def test_g71_dialog_haelt_den_fokus_und_gibt_ihn_zurueck(browser, server):
    url, _db = server
    page = _seite(browser, url, "kontakte")
    try:
        knopf = page.get_by_role("button", name="Neuer Kontakt").first
        knopf.click()
        dialog = page.get_by_role("dialog")
        dialog.wait_for(timeout=5000)
        assert dialog.get_attribute("aria-modal") == "true"
        titel = page.evaluate(
            "() => { const d = document.querySelector('[role=dialog]'); "
            "return document.getElementById(d.getAttribute('aria-labelledby'))?.textContent; }")
        assert titel
        for _ in range(25):
            page.keyboard.press("Tab")
            assert page.evaluate("() => !!document.activeElement.closest('[role=dialog]')")
        for _ in range(5):
            page.keyboard.press("Shift+Tab")
            assert page.evaluate("() => !!document.activeElement.closest('[role=dialog]')")
        page.keyboard.press("Escape")
        dialog.wait_for(state="detached", timeout=5000)
        # Der Fokus steht wieder auf dem KNOPF, nicht auf der Seite (body
        # enthaelt den Knopftext ebenfalls — die Gegenprobe hat es gezeigt).
        assert page.evaluate(
            "() => document.activeElement.tagName === 'BUTTON' "
            "&& document.activeElement.textContent.includes('Neuer Kontakt')")
    finally:
        page.close()


def test_g71_auswahlfeld_mit_der_tastatur(browser, server):
    url, db = server
    page = _seite(browser, url, "bewerbungen")
    try:
        auswahl = page.get_by_role("combobox", name="Beworben", exact=True).first
        auswahl.focus()
        page.keyboard.press("ArrowDown")
        page.get_by_role("listbox").wait_for(timeout=5000)
        assert auswahl.get_attribute("aria-expanded") == "true"
        aktiv = auswahl.get_attribute("aria-activedescendant")
        assert aktiv and page.locator(f"[id='{aktiv}']").get_attribute("aria-selected") == "true"
        page.keyboard.press("ArrowDown")
        neu = page.locator(f"[id='{auswahl.get_attribute('aria-activedescendant')}']").inner_text()
        page.keyboard.press("Enter")
        page.get_by_role("listbox").wait_for(state="detached", timeout=5000)
        assert neu.strip() and neu.strip() != "Beworben"
    finally:
        page.close()


def test_g71_hinweise_haben_eine_live_region(browser, server):
    url, _db = server
    page = _seite(browser, url, "dashboard")
    try:
        bereich = page.locator("[data-toast-bereich]")
        assert bereich.get_attribute("aria-live") == "polite"
        # Kein sichtbarer Bereich, der nur aus seinem Einklapp-Griff besteht.
        leer = page.evaluate("""() => [...document.querySelectorAll('.dashboard-bereich')]
            .filter((s) => s.children.length < 2 && s.getClientRects().length > 0).length""")
        assert leer == 0
    finally:
        page.close()


def test_g71_suche_auf_dem_handy(browser, server):
    url, _db = server
    page = _seite(browser, url, "bewerbungen", breite=390)
    try:
        feld = page.locator("[data-globale-suche] input[type=search]")
        assert not feld.is_visible()
        page.locator("[data-suche-mobil]").click()
        feld.wait_for(state="visible", timeout=5000)
        feld.fill("Einkauf")
        page.locator("[data-suchergebnisse]").wait_for(timeout=10000)
        breite = page.evaluate("document.documentElement.scrollWidth")
        assert breite <= 391, breite
    finally:
        page.close()
