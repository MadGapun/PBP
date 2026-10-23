"""#1170 U15: die Seitenleiste in schmalen Fenstern — im Browser, gegen das gebaute Bundle.

Befund der Bedienungsprüfung: das Dashboard neben Claude Desktop (halbe Bildschirmbreite, rund 680 px) behielt die 240 px breite
Seitenleiste, der Inhalt bekam etwa 380 px; bei 420 px blieb nur ein Streifen. Unter 900 px ist die Leiste jetzt ohne eigene Wahl
eingeklappt (60 px, beim Daraufzeigen schwebt sie auf); die Wahl des Menschen wird je Breitenklasse gemerkt.

Die reine Rechnung prüft `frontend/src/lib/seitenleiste.test.mjs` (in der CI). Hier: was im Browser ankommt.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
BREIT = {"width": 1440, "height": 900}
SCHMAL = {"width": 700, "height": 900}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("seitenleiste1170")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
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
    yield {"url": f"http://127.0.0.1:{port}", "db": db}
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


def _warte(bedingung, sekunden=10):
    ende = time.time() + sekunden
    while time.time() < ende:
        if bedingung():
            return True
        time.sleep(0.1)
    return False


def _leiste(page):
    """('eingeklappt'|'ausgeklappt', Breite in px) - gemessen an der Seitenleiste, wie der Mensch sie sieht."""
    knopf = page.locator("header button[aria-label^='Sidebar']").first
    breite = page.locator("aside[aria-label='Hauptnavigation']").bounding_box()["width"]
    return ("eingeklappt" if knopf.get_attribute("aria-label") == "Sidebar ausklappen" else "ausgeklappt"), round(breite)


def _oeffnen(browser, url, groesse):
    ctx = browser.new_context(viewport=groesse)
    page = ctx.new_page()
    page.goto(f"{url}/#dashboard", wait_until="load", timeout=30000)
    page.locator("header button[aria-label^='Sidebar']").first.wait_for(timeout=20000)
    return ctx, page


def _gemerkt(page, schluessel):
    return page.evaluate("(k) => window.localStorage.getItem(k)", schluessel)


def test_im_schmalen_fenster_ist_die_leiste_ohne_wahl_eingeklappt(browser, umgebung):
    ctx, page = _oeffnen(browser, umgebung["url"], SCHMAL)
    try:
        assert _warte(lambda: _leiste(page) == ("eingeklappt", 60)), _leiste(page)
        inhalt = page.locator("#page-dashboard").bounding_box()["width"]
        assert inhalt > 560, f"der Inhalt bekommt {inhalt} px - zuvor rund 380"
    finally:
        ctx.close()


def test_im_breiten_fenster_bleibt_sie_wie_bisher_ausgeklappt(browser, umgebung):
    ctx, page = _oeffnen(browser, umgebung["url"], BREIT)
    try:
        assert _warte(lambda: _leiste(page) == ("ausgeklappt", 240)), _leiste(page)
    finally:
        ctx.close()


def test_die_wahl_wird_je_breitenklasse_gemerkt(browser, umgebung):
    ctx, page = _oeffnen(browser, umgebung["url"], SCHMAL)
    try:
        assert _warte(lambda: _leiste(page)[0] == "eingeklappt")
        # im schmalen Fenster ausklappen ...
        page.locator("header button[aria-label='Sidebar ausklappen']").first.click()
        assert _warte(lambda: _leiste(page) == ("ausgeklappt", 240)), _leiste(page)
        assert _gemerkt(page, "pbp-sidebar-collapsed-schmal") == "0"
        assert _gemerkt(page, "pbp-sidebar-collapsed") is None, "die Wahl fuer breite Fenster bleibt unberuehrt"
        # ... bleibt nach dem Neuladen
        page.reload(wait_until="load")
        page.locator("header button[aria-label^='Sidebar']").first.wait_for(timeout=20000)
        assert _warte(lambda: _leiste(page) == ("ausgeklappt", 240)), _leiste(page)
        # im breiten Fenster gilt die Wahl fuer breit - ausgeklappt ist dort die Vorgabe
        page.set_viewport_size(BREIT)
        assert _warte(lambda: _leiste(page) == ("ausgeklappt", 240)), _leiste(page)
        page.locator("header button[aria-label='Sidebar einklappen']").first.click()
        assert _warte(lambda: _leiste(page) == ("eingeklappt", 60)), _leiste(page)
        assert _gemerkt(page, "pbp-sidebar-collapsed") == "1"
        assert _gemerkt(page, "pbp-sidebar-collapsed-schmal") == "0", "die Wahl fuer schmal bleibt unberuehrt"
        # zurueck in das schmale Fenster: dort gilt weiter 'ausgeklappt'
        page.set_viewport_size(SCHMAL)
        assert _warte(lambda: _leiste(page) == ("ausgeklappt", 240)), _leiste(page)
    finally:
        ctx.close()


def test_eine_frueher_gemerkte_wahl_gilt_im_breiten_fenster_weiter(browser, umgebung):
    """Wer vor 1.8 im breiten Fenster eingeklappt hat, behaelt das (derselbe Schluessel wie bisher)."""
    ctx = browser.new_context(viewport=BREIT)
    page = ctx.new_page()
    try:
        page.add_init_script("window.localStorage.setItem('pbp-sidebar-collapsed', '1')")
        page.goto(f"{umgebung['url']}/#dashboard", wait_until="load", timeout=30000)
        page.locator("header button[aria-label^='Sidebar']").first.wait_for(timeout=20000)
        assert _warte(lambda: _leiste(page) == ("eingeklappt", 60)), _leiste(page)
    finally:
        ctx.close()
