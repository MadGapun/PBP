"""Welle 3 aus #1087 im gerenderten Dashboard (G59, G60, G63, B69).

* G59: ohne Profil EIN Einstieg mit Erklaerkasten, kein Overlay darueber.
* G60: hoechstens ein Hinweis, und nur auf dem Dashboard; die Seitenleiste
  nennt, was nicht verbunden ist, und faerbt Optionales nicht rot.
* G63: ohne Profil sagen Stellen- und Bewerbungen-Tab "Zuerst dein Profil".
* B69: die erste Quellenauswahl wird angezeigt, nicht still gesetzt.
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
from playwright.sync_api import expect  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _starten(tmp_path, mit_profil):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    if mit_profil:
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
    return f"http://127.0.0.1:{port}", db, srv, t, dash


def _stoppen(srv, t, dash, db):
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def ohne_profil(tmp_path):
    url, db, srv, t, dash = _starten(tmp_path, False)
    yield url, db
    _stoppen(srv, t, dash, db)


@pytest.fixture
def mit_profil(tmp_path):
    url, db, srv, t, dash = _starten(tmp_path, True)
    yield url, db
    _stoppen(srv, t, dash, db)


@pytest.fixture(scope="module")
def browser():
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def _seite(browser, url, tab):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(f"{url}/#{tab}", wait_until="load", timeout=30000)
    page.wait_for_timeout(2000)
    return page


def test_g59_ein_einstieg_ohne_overlay(browser, ohne_profil):
    url, _db = ohne_profil
    page = _seite(browser, url, "dashboard")
    try:
        page.locator("[data-erklaerkasten]").wait_for(timeout=10000)
        text = page.inner_text("body")
        assert "So arbeiten Dashboard und Claude zusammen" in text
        assert "Lebenslauf hochladen" in text and "Gespräch mit Claude starten" in text
        assert "Starte die Ersterfassung" in text
        expect(page.locator("#wizard-overlay")).to_have_count(0)
        assert "Willkommen beim Bewerbungs-Assistenten" not in text
        # Ohne Profil keine Hinweiszone — der Einstieg erklaert es selbst.
        expect(page.locator("[data-hinweiszone]")).to_have_count(0)
    finally:
        page.close()


def test_g60_seitenleiste_ohne_profil_nicht_rot(browser, ohne_profil):
    url, _db = ohne_profil
    page = _seite(browser, url, "dashboard")
    try:
        knopf = page.get_by_text("Claude Desktop: nicht verbunden").first
        knopf.wait_for(timeout=10000)
        klasse = knopf.locator("xpath=ancestor::button[1]").get_attribute("class") or ""
        assert "text-coral" not in klasse, klasse
        # Welcher Zustand die lokale KI hat, haengt vom Rechner ab (laeuft
        # dort ein Ollama?) — rot ist sie in keinem.
        ki = page.locator("button", has_text="Lokale KI:").first
        ki.wait_for(timeout=10000)
        assert "text-coral" not in (ki.get_attribute("class") or "")
    finally:
        page.close()


@pytest.mark.parametrize("tab,bereich", [("stellen", "Stellen"), ("bewerbungen", "Bewerbungen")])
def test_g63_ohne_profil_zuerst_das_profil(browser, ohne_profil, tab, bereich):
    url, _db = ohne_profil
    page = _seite(browser, url, tab)
    try:
        page.locator(f'[data-zuerst-profil="{bereich}"]').wait_for(timeout=10000)
        text = page.inner_text("body")
        assert "Zuerst dein Profil" in text
        assert "Auf Kurs" not in text
    finally:
        page.close()


def test_g60_hoechstens_ein_hinweis_nur_auf_dem_dashboard(browser, mit_profil):
    url, db = mit_profil
    db.set_profile_setting("active_sources", [])
    page = _seite(browser, url, "dashboard")
    try:
        page.locator("[data-hinweiszone]").first.wait_for(timeout=10000)
        expect(page.locator("[data-hinweiszone]")).to_have_count(1)
        # Ohne Verbindung steht die Verbindung vorn.
        assert page.locator("[data-hinweiszone]").get_attribute("data-hinweiszone") == "verbindung"
        assert "Keine Jobquellen aktiviert" not in page.inner_text("body")
    finally:
        page.close()
    page = _seite(browser, url, "aufgaben")
    try:
        expect(page.locator("[data-hinweiszone]")).to_have_count(0)
        expect(page.locator("#workspace-strip")).to_have_count(0)
        expect(page.locator("#source-banner")).to_have_count(0)
    finally:
        page.close()


def test_1280_erstauswahl_verschwindet_sofort_und_kommt_nicht_wieder(browser, mit_profil):
    """#1280: die Karte geht beim Klick weg, nicht erst nach der Antwort, und ein Neuaufbau waehrend der laufenden
    Bestaetigung (Reiterwechsel) zeigt sie nicht noch einmal. Die Bestaetigung wird dafuer beim Server festgehalten."""
    url, db = mit_profil
    page = _seite(browser, url, "einstellungen")
    gehalten = []
    try:
        page.locator("[data-erstauswahl]").wait_for(timeout=15000)
        page.route("**/api/sources/erstauswahl/bestaetigen", lambda route: gehalten.append(route))
        page.get_by_role("button", name="Passt so").click()
        page.wait_for_function("() => document.querySelectorAll('[data-erstauswahl]').length === 0", timeout=5000)
        assert gehalten, "die Bestaetigung ging nicht los"
        assert not (db.get_profile_setting("quellen_erstauswahl") or {}).get("bestaetigt")
        # Neuaufbau der Karte, solange der Server noch "offen" sagen wuerde
        page.get_by_role("button", name="Erscheinungsbild", exact=True).click()
        page.locator('button[aria-pressed="true"]', has_text="Erscheinungsbild").first.wait_for(timeout=10000)
        page.get_by_role("button", name="Quellen", exact=True).click()
        page.locator('button[aria-pressed="true"]', has_text="Quellen").first.wait_for(timeout=10000)
        page.wait_for_timeout(1500)  # Die Karte laedt ihre Daten selbst; sie haette Zeit gehabt, wieder zu erscheinen.
        assert page.locator("[data-erstauswahl]").count() == 0
        with page.expect_response(lambda r: r.url.endswith("/api/sources/erstauswahl/bestaetigen"), timeout=15000):
            gehalten[0].continue_()
        assert (db.get_profile_setting("quellen_erstauswahl") or {}).get("bestaetigt") is True
    finally:
        page.close()


def test_b69_erstauswahl_wird_gezeigt(browser, mit_profil):
    url, db = mit_profil
    page = _seite(browser, url, "einstellungen")
    try:
        page.locator("[data-erstauswahl]").wait_for(timeout=15000)
        text = page.locator("[data-erstauswahl]").inner_text()
        assert "ausgewählt" in text
        # #1271: auf Zustaende warten, nicht auf Zeit. Erst die Antwort des Servers (dann ist die Bestaetigung gespeichert), dann das
        # Verschwinden der Karte. Das Verschwinden allein reicht nicht: laedt die Seite wegen einer Aenderung neu, ist die Karte kurz weg,
        # obwohl der Server noch nicht geantwortet hat.
        with page.expect_response(lambda r: r.url.endswith("/api/sources/erstauswahl/bestaetigen"), timeout=15000):
            page.get_by_role("button", name="Passt so").click()
        page.locator("[data-erstauswahl]").first.wait_for(state="detached", timeout=15000)
        expect(page.locator("[data-erstauswahl]")).to_have_count(0)
        assert (db.get_profile_setting("quellen_erstauswahl") or {}).get("bestaetigt") is True
    finally:
        page.close()
