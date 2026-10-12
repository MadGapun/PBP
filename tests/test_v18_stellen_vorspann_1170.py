"""#1170 U16: der Vorspann der Stellen-Seite — im Browser, gegen das gebaute Bundle.

Befund der Bedienungsprüfung: bis zur ersten Stelle lagen rund 900 px Vorspann (Hinweiskarte, „Diese Quellen laufen nur über den
Browser“, vier Kennzahlkacheln, „Auf Kurs“, Filter). Jetzt: die Browser-Karte steht nur, wenn Browser-Quellen gewählt sind (die
„optionalen“ allein waren für jede Installation da), und die vier Kennzahlen stehen ab 1024 px in einer Zeile.

Gemessen am ungefilterten Bild mit sechs Stellen, 1440 px breit: erste Stellenkarte vorher bei y = 908, jetzt bei etwa 730.
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

TEXT = ("Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse "
        "und begleiten die Einfuehrung eines neuen PLM-Systems. Ihr Profil: abgeschlossenes Studium.")
KARTE = "Diese Quellen laufen nur über den Browser"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("vorspann1170")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    for i in range(6):
        db.save_jobs([{"hash": f"v{i:03d}", "title": f"PLM Administrator {i} (m/w/d)", "company": f"Beispielwerk {i} GmbH",
                       "location": "Musterstadt", "url": f"https://karriere.beispiel-{i}.example/jobs/{i}",
                       "source": "stepstone", "description": TEXT, "score": 10 + i}])
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


def _seite(browser, umgebung, quellen, breite=1440):
    umgebung["db"].set_profile_setting("active_sources", quellen)
    ctx = browser.new_context(viewport={"width": breite, "height": 900})
    page = ctx.new_page()
    page.goto(f"{umgebung['url']}/#stellen", wait_until="load", timeout=30000)
    page.locator("#page-stellen").wait_for(timeout=20000)
    page.locator("[data-stellenkarte]").first.wait_for(timeout=20000)
    page.wait_for_timeout(1000)     # die Browser-Quellen kommen mit einer eigenen Anfrage
    return ctx, page


def test_ohne_browser_quelle_steht_keine_karte_da_und_die_erste_stelle_ist_weiter_oben(browser, umgebung):
    ctx, page = _seite(browser, umgebung, ["bundesagentur", "arbeitnow"])
    try:
        assert KARTE not in page.locator("#page-stellen").inner_text()
        y = page.locator("[data-stellenkarte]").first.bounding_box()["y"]
        # #1171 Baustein 5: die Kennzahlen sind eine Zeile (Vorgabe zu), die Suchstand-Zeile steht in ihr: vorher 908,
        # nach U16 etwa 730, jetzt etwa 400 - die erste Stelle samt Knoepfen liegt im ersten Bildschirm.
        assert y < 520, f"die erste Stelle beginnt bei y = {y:.0f} (vorher 908)"
    finally:
        ctx.close()


def test_mit_gewaehlter_browser_quelle_steht_die_karte_da(browser, umgebung):
    ctx, page = _seite(browser, umgebung, ["bundesagentur", "linkedin"])
    try:
        assert KARTE in page.locator("#page-stellen").inner_text()
        assert page.get_by_role("button", name="Browser-Quellen mit Claude").count() == 1
        assert "LinkedIn" in page.locator("#page-stellen").inner_text()
    finally:
        ctx.close()


def _zeilen(page):
    """Die y-Werte der vier Kennzahlen, gerundet - gleiche Zahl = gleiche Zeile. Seit #1171 Baustein 5 liegen sie hinter
    dem Schalter des Listenkopfs (Vorgabe zu): erst aufklappen, wie ein Mensch es taete."""
    kopf = page.locator('[data-listen-uebersicht="stellen"]')
    if kopf.get_attribute("data-offen") != "ja":
        kopf.locator("[data-listen-uebersicht-schalter]").click()
    page.locator("[data-stellen-kennzahlen] > div").first.wait_for(timeout=5000)
    boxen = [b.bounding_box() for b in page.locator("[data-stellen-kennzahlen] > div").all()]
    return [round(b["y"]) for b in boxen]


def test_die_vier_kennzahlen_stehen_ab_1024_px_in_einer_zeile(browser, umgebung):
    ctx, page = _seite(browser, umgebung, ["bundesagentur", "arbeitnow"], breite=1100)
    try:
        ys = _zeilen(page)
        assert len(ys) == 4 and max(ys) - min(ys) <= 2, ys
    finally:
        ctx.close()


def test_in_einem_schmalen_fenster_stehen_sie_zu_zweit(browser, umgebung):
    ctx, page = _seite(browser, umgebung, ["bundesagentur", "arbeitnow"], breite=760)
    try:
        ys = _zeilen(page)
        assert len(ys) == 4 and len(set(ys)) == 2, ys
    finally:
        ctx.close()
