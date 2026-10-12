"""#1184 (d): die Hinweise aus Google-Benachrichtigungen auf der Stellen-Seite — im Browser, gegen das gebaute Bundle.

Die Hinweise stehen eingeklappt über der Liste, sagen was sie sind (noch keine Stellen), nennen Firma, Ort und Portal, tragen die
vorbereitete Suche nach dem Original und lassen sich verwerfen — echt (Datenbank), nicht nur in der Anzeige.

Gebaut wird mit `cd frontend && pnpm exec vite build`, wenn sich das Frontend ändert.
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

from bewerbungs_assistent.services import stellen_hinweise  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("hinweise1184")
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


def _warte(bedingung, sekunden=15):
    ende = time.time() + sekunden
    while time.time() < ende:
        if bedingung():
            return True
        time.sleep(0.2)
    return False


def _treffer(titel, firma, ort="Hamburg", **kw):
    t = {"titel": titel, "firma": firma, "ort": ort, "portal": "XING", "vertragsart": "Vollzeit",
         "veroeffentlicht_am": "2026-09-30", "weiterverbreiter": False, "google_link": ""}
    t.update(kw)
    return t


def test_ohne_hinweise_steht_nichts_da(browser, umgebung):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#stellen", wait_until="load", timeout=30000)
        page.locator("#page-stellen").wait_for(timeout=20000)
        page.wait_for_timeout(800)
        assert page.locator("[data-stellen-hinweise]").count() == 0
    finally:
        ctx.close()


def test_die_hinweise_sind_eingeklappt_nennen_die_suche_und_lassen_sich_verwerfen(browser, umgebung):
    db = umgebung["db"]
    stellen_hinweise.merken(db, [_treffer("Teamcenter Administrator", "Hansa Marke GmbH", "Hamburg"),
                                 _treffer("PDM Berater", "Nordlicht GmbH", "Köln", weiterverbreiter=True)])
    stellen_hinweise.merken(db, [_treffer("Teamcenter Administrator", "Hansa Marke GmbH", "Berlin")])
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#stellen", wait_until="load", timeout=30000)
        block = page.locator("[data-stellen-hinweise]")
        block.wait_for(timeout=20000)
        kopf = " ".join(block.inner_text().split())
        assert "2 Hinweise aus Google-Benachrichtigungen — noch keine Stellen" in kopf
        assert "Hansa Marke GmbH" not in kopf, "eingeklappt: die Liste steht noch nicht da"
        block.get_by_role("button").first.click()
        zeile = block.locator("[data-hinweis]").filter(has_text="Teamcenter Administrator")
        zeile.wait_for(timeout=5000)
        text = " ".join(zeile.inner_text().split())
        assert "Hansa Marke GmbH" in text and "Hamburg; Berlin" in text and "über XING" in text
        assert "in 2 Mails" in text and "Orte widersprechen sich" in text
        assert "Kopie einer Sammelseite" in " ".join(
            block.locator("[data-hinweis]").filter(has_text="PDM Berater").inner_text().split())
        href = zeile.get_by_role("link", name="Original suchen").get_attribute("href")
        assert href.startswith("https://www.google.com/search?q=") and "Hansa" in href and "Karriere" in href
        zeile.get_by_role("button", name="Verwerfen").click()
        assert _warte(lambda: stellen_hinweise.zaehlen(db)["verworfen"] == 1), "der Hinweis wurde nicht verworfen"
        assert _warte(lambda: block.locator("[data-hinweis]").filter(has_text="Teamcenter Administrator").count() == 0)
        assert "1 Hinweis aus einer Google-Benachrichtigung" in " ".join(block.inner_text().split())
    finally:
        ctx.close()
