"""Welle 4 aus #1087 im gerenderten Dashboard (G62, G72).

* G62: die Karte traegt EINE Kernaussage, einen Grund und den
  Rahmen-Daumen; Kennung und Quelle stehen im Menue "Für Claude
  kopieren"; "Genauer prüfen" bietet zwei Wege; die Filterleiste zeigt
  Suche plus "Filter (n)", keine Seitengroesse.
* G72: verweigert der Browser die Zwischenablage, steht der Text in einem
  Fenster zum Selbstkopieren — keine englische Browsermeldung.
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
        "Bestellabwicklung mit SAP MM, Lieferantenkommunikation. "
        "Anforderungen: kaufmaennische Ausbildung, Englisch. ") * 3


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
    db.set_search_criteria("keywords_muss", ["einkauf", "sap mm"])
    db.save_jobs([{"hash": "g62ui", "title": "Sachbearbeitung Einkauf",
                   "company": "Musterbetrieb GmbH", "url": "https://example.com/g62ui",
                   "source": "manuell", "description": TEXT, "remote_level": "hybrid",
                   "location": "Hamburg", "score": 4}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE '%g62ui'").fetchone()["hash"]
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
    yield f"http://127.0.0.1:{port}", db, voll
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


def _stellen(browser, url, clipboard_kaputt=False):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    if clipboard_kaputt:
        page.add_init_script(
            "Object.defineProperty(navigator, 'clipboard', {value: {writeText: () => "
            "Promise.reject(new DOMException(\"Failed to execute 'writeText' on 'Clipboard'\"))}});")
    page.goto(f"{url}/#stellen", wait_until="load", timeout=30000)
    page.locator("[data-kernaussage]").first.wait_for(timeout=15000)
    return page


def test_g62_karte_eine_kernaussage_und_ein_menue(browser, server):
    url, _db, voll = server
    page = _stellen(browser, url)
    try:
        karte = page.locator("[data-stellenkarte]").first
        text = karte.inner_text()
        assert page.locator("[data-kernaussage]").count() == 1
        # Keine Kennung und kein Quellenschluessel als Abzeichen.
        assert voll.split(":")[-1][:8] not in text
        assert "manuell" not in text
        assert "Ungeprüft:" not in text and "Fachlich:" not in text
        assert "Fit-Analyse" not in text
        # Fakten als Zeile, nicht als Abzeichen.
        assert "Hybrid" in page.locator("[data-karten-fakten]").first.inner_text()
        # Das Menue traegt Kennung und Quelle.
        page.locator("[data-fuer-claude]").first.click()
        menue = page.get_by_role("menu").first
        assert "Quelle: manuell" in menue.inner_text()
        assert menue.get_by_role("menuitem", name="Kennung kopieren").count() == 1
    finally:
        page.close()


def test_g62_genauer_pruefen_bietet_zwei_wege(browser, server):
    url, _db, _voll = server
    page = _stellen(browser, url)
    try:
        page.locator("[data-genauer-pruefen]").first.click()
        menue = page.get_by_role("menu").first
        assert "Sofort prüfen" in menue.inner_text()
        assert "Detailbewertung mit Claude" in menue.inner_text()
        menue.get_by_role("menuitem").filter(has_text="Sofort prüfen").click()
        page.get_by_text("Detailbewertung mit Claude").last.wait_for(timeout=15000)
    finally:
        page.close()


def test_g62_filterleiste_suche_plus_filter_n(browser, server):
    url, _db, _voll = server
    page = _stellen(browser, url)
    try:
        knopf = page.locator("[data-filter-knopf]")
        # Vorgaben wirken (beworbene, Rahmen, Schwelle) und stehen da.
        assert knopf.inner_text().strip().startswith("Filter (")
        assert "(0)" not in knopf.inner_text()
        assert "ausgeblendet" in page.locator("[data-filter-zusammenfassung]").inner_text()
        assert page.locator("[data-filter-feld]").count() == 0
        assert "pro Seite" not in page.inner_text("body")
        knopf.click()
        page.locator("[data-filter-feld]").wait_for(timeout=5000)
        assert "Rahmen passt nicht ausblenden" in page.locator("[data-filter-feld]").inner_text()
        assert page.get_by_role("button", name="Aussortiert").count() >= 1
    finally:
        page.close()


def test_g72_fehlschlag_zeigt_text_zum_selbstkopieren(browser, server):
    url, _db, _voll = server
    page = _stellen(browser, url, clipboard_kaputt=True)
    try:
        page.locator("[data-genauer-pruefen]").first.click()
        page.get_by_role("menu").first.get_by_role("menuitem").filter(has_text="mit Claude").click()
        feld = page.locator("[data-manuell-kopieren]")
        feld.wait_for(timeout=10000)
        assert "stelle_analyse_speichern" in feld.input_value()
        body = page.inner_text("body")
        assert "Kopieren hat nicht geklappt" in body
        assert "Failed to execute" not in body
    finally:
        page.close()
