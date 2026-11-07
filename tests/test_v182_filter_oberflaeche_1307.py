"""#1307/#1308 im Browser (gegen das GEBAUTE Bundle): Sprachfilter, gespeicherte Ansicht und Sprach-Abzeichen im Stellen-Tab,
die Regeln unter Einstellungen › Automatik (An/Aus, Anlegen ohne Claude). Gewartet wird auf Zustaende, nicht auf Zeit.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
import uvicorn  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from bewerbungs_assistent.services import gespeicherte_filter as gf  # noqa: E402

EN = ("We are looking for an engineer to join our team in Berlin. You will design and test components, work closely "
      "with colleagues from production, and support our customers. Requirements: a degree in engineering, at least "
      "three years of experience, and strong communication skills. We offer a competitive salary and a modern office.")
DE = ("Wir suchen für unseren Standort in Hamburg eine Ingenieurin oder einen Ingenieur. Deine Aufgaben: du "
      "konstruierst Bauteile, prüfst sie und arbeitest eng mit der Fertigung zusammen. Dein Profil: abgeschlossenes "
      "Studium, mehrere Jahre Erfahrung und gute Kenntnisse in CAD. Wir bieten ein Team, flexible Arbeitszeiten und "
      "Homeoffice.")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("filter1307")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    d = Database(db_path=tmp / "test.db")
    d.initialize()
    assert str(tmp) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    for kennung, titel, text in (("o_en", "Design Engineer", EN), ("o_de", "Konstrukteur", DE),
                                 ("o_kurz", "Monteur", "Kurztext.")):
        d.save_jobs([{"hash": kennung, "title": titel, "company": "Musterfirma GmbH", "source": "manuell",
                      "url": f"https://example.com/{kennung}", "description": text, "score": 5}])
    gf.anlegen(d, "Konstruktion", "ansicht", {"titel_enthaelt": ["konstrukteur"]})
    dash._db = d
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
    yield {"url": f"http://127.0.0.1:{port}", "db": d}
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    d.close()
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


def _waehle(page, bereich, feld, eintrag):
    """Die Auswahlfelder sind eigene Listen (G71: Rolle combobox, Eintraege als option), kein <select>."""
    bereich.get_by_label(feld).first.click()
    page.get_by_role("option", name=eintrag, exact=True).click()


def _titel_sichtbar(page, titel):
    page.get_by_text(titel, exact=True).first.wait_for(timeout=15000)


def test_sprachfilter_ansicht_und_abzeichen_im_stellen_tab(browser, umgebung):
    ctx = browser.new_context(viewport={"width": 1500, "height": 950})
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#stellen", wait_until="load", timeout=30000)
        knopf = page.locator("[data-filter-knopf]")
        knopf.wait_for(timeout=30000)
        _titel_sichtbar(page, "Design Engineer")
        # das Abzeichen steht nur an der englischen Stelle
        page.locator("[data-sprache=en]").first.wait_for(timeout=10000)
        assert page.locator("[data-sprache]").count() == 1
        if knopf.get_attribute("aria-expanded") != "true":
            knopf.click()
        _waehle(page, page, "Sprache der Anzeige", "Ohne rein englische")
        page.wait_for_function("() => !document.body.innerText.includes('Design Engineer')", timeout=15000)
        _titel_sichtbar(page, "Monteur")          # unbekannte Sprache bleibt stehen
        _titel_sichtbar(page, "Konstrukteur")
        _waehle(page, page, "Sprache der Anzeige", "Sprache: alle")
        _titel_sichtbar(page, "Design Engineer")
        _waehle(page, page, "Gespeicherte Ansicht", "Konstruktion")
        page.wait_for_function("() => !document.body.innerText.includes('Design Engineer')"
                               " && !document.body.innerText.includes('Monteur')", timeout=15000)
        _titel_sichtbar(page, "Konstrukteur")
    finally:
        ctx.close()


def test_regeln_unter_automatik_anlegen_und_ausschalten(browser, umgebung):
    d = umgebung["db"]
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(f"{umgebung['url']}/#einstellungen", wait_until="domcontentloaded", timeout=30000)
        reiter = page.locator("[data-settings-reiter]")
        reiter.wait_for(timeout=15000)
        automatik = reiter.get_by_role("button", name="Automatik", exact=True)
        if not automatik.is_visible():
            reiter.get_by_role("button", name="Erweitert").first.click()
        automatik.click()
        karte = page.get_by_test_id("stellen-regeln-card")
        karte.wait_for(timeout=15000)
        assert "Noch keine eigene Regel" in karte.inner_text()
        _waehle(page, karte, "Grund", "Sonstiges")
        karte.get_by_role("button", name="Regel anlegen").click()
        karte.locator("[data-regel='Rein englische Anzeigen']").wait_for(timeout=15000)
        regel = gf.holen(d, "Rein englische Anzeigen")
        assert regel and regel["art"] == "regel" and regel["bedingungen"] == {"sprache": ["en"]} and regel["aktiv"]
        assert {j["hash"] for j in d.get_active_jobs()} == {"o_en", "o_de", "o_kurz"}, "anlegen sortiert nichts aus"
        karte.get_by_label("Regel Rein englische Anzeigen an oder aus").click()
        for _ in range(50):
            if not gf.holen(d, "Rein englische Anzeigen")["aktiv"]:
                break
            page.wait_for_timeout(100)
        assert gf.holen(d, "Rein englische Anzeigen")["aktiv"] is False
        karte.get_by_text("ruht", exact=True).wait_for(timeout=10000)
    finally:
        page.close()
