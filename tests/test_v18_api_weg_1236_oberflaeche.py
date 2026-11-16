"""#1236 Stufe 2 -- die Oberflaeche des API-Wegs im echten Browser gegen die gebaute Oberflaeche.

Ein Grep im JSX belegt nicht, dass die Karte erscheint (v1.7.71 MERKE 9): hier laeuft der Server, der Browser rendert, und der
Text wird gelesen. Geprueft wird vor allem das, was Abnahmekriterium 1 verlangt: ohne Schluessel und ohne Einstellung ist in der
Oberflaeche NICHTS zu sehen, und mit Schluessel steht die Feldliste VOR der Freigabe da.

Der Transport ist ein Testdoppel; kein Test erreicht das Netz.
"""
import os
import re
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _api_hilfen import FakeTransport, TESTSCHLUESSEL, antwort  # noqa: E402

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # ohne Browser-Paket entfallen nur die Browser-Tests
    PlaywrightError = Exception
    sync_playwright = None

from bewerbungs_assistent.services import api_backend  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _starten(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
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
    return db, dash, srv, t, f"http://127.0.0.1:{port}"


def _beenden(dash, srv, t, db):
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def ohne_schluessel(tmp_path):
    db, dash, srv, t, url = _starten(tmp_path)
    yield url, db
    _beenden(dash, srv, t, db)


@pytest.fixture
def mit_schluessel(tmp_path, monkeypatch):
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)
    db, dash, srv, t, url = _starten(tmp_path)
    yield url, db
    _beenden(dash, srv, t, db)


@pytest.fixture(scope="module")
def browser():
    if sync_playwright is None:
        pytest.skip("Playwright nicht installiert")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def _reiter(page, reiter):
    page.evaluate("id => document.dispatchEvent(new CustomEvent('settings-nav', {detail: {tab: id}}))", reiter)


def _offen(browser, url, reiter="ai"):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(f"{url}/#einstellungen", wait_until="load", timeout=30000)
    page.wait_for_selector("[data-settings-reiter]", timeout=20000)
    _reiter(page, reiter)
    return page


def _datenschutz_text(page):
    _reiter(page, "datenschutz")
    page.wait_for_selector("text=Wo liegen deine Daten und was wird wohin gesendet.", timeout=15000)
    page.wait_for_selector("text=Externe Anfragen:", timeout=15000)
    return page.inner_text("body")


# ============================================================ AK 1: ohne Schluessel und Einstellung nichts

def test_ohne_schluessel_und_ohne_freigabe_gibt_es_keine_karte(browser, ohne_schluessel):
    url, _db = ohne_schluessel
    page = _offen(browser, url)
    try:
        page.wait_for_selector("text=Lokale KI", timeout=15000)
        page.wait_for_timeout(600)  # die Antwort von /api/api-weg ist da, wenn die Seite fertig geladen hat
        assert page.locator("[data-api-weg]").count() == 0
        assert "Anthropic-API" not in page.inner_text("body")
        assert "Eigene Anthropic-API" not in page.inner_text("body")
        antwort_ = page.evaluate("fetch('/api/api-weg').then(r => r.json())")
        assert antwort_ == {"sichtbar": False, "schluessel_gesetzt": False}
        text = _datenschutz_text(page)
        assert "Direkt an die Anthropic-API" not in text and page.locator("[data-datenfluss-api]").count() == 0
    finally:
        page.close()


# ============================================================ Mit Schluessel: die Feldliste steht VOR der Freigabe

def test_mit_schluessel_zeigt_die_karte_die_feldliste_bevor_etwas_freigegeben_ist(browser, mit_schluessel):
    url, _db = mit_schluessel
    page = _offen(browser, url)
    try:
        page.wait_for_selector("[data-api-weg]", timeout=20000)
        karte = page.locator("[data-api-weg]")
        text = karte.inner_text()
        assert "Schlüssel gefunden" in text and "Noch nicht geprüft" in text, text
        assert "Ausnahme von „läuft komplett lokal“" in text
        # Block K (Werkstatt-PC, 17.10.2026): die Store-Fassung von Claude reicht Benutzervariablen nicht durch, `env` des Eintrags kommt an
        claude = karte.locator("[data-api-claude-schluessel]").inner_text()
        assert api_backend.ENV_SCHLUESSEL in claude and "env" in claude and "bewerbungs-assistent" in claude and "Microsoft Store" in claude, claude
        for aufgabe in ("match_job_to_skills", "validate_job_quality"):
            zeile = page.locator(f'[data-api-aufgabe="{aufgabe}"]')
            assert zeile.count() == 1
            assert page.locator(f'[data-api-status="{aufgabe}"]').inner_text() == "Aus"
            felder = zeile.locator("[data-api-felder]")
            assert felder.evaluate("d => d.open") is True, "Die Feldliste ist vor der Freigabe aufgeklappt"
        match = page.locator('[data-api-aufgabe="match_job_to_skills"]').inner_text()
        assert "deine letzte Berufsbezeichnung" in match and "Nicht gesendet:" in match
        assert "wird durch „[Firma]“ ersetzt" in match and "eigener Text wird zu „sonstiges“" in match
        assert "das heutige Datum und die Uhrzeit" in match
        assert TESTSCHLUESSEL not in page.content() and TESTSCHLUESSEL[:14] not in page.content()
        assert "Kein Budget gesetzt" in karte.locator("[data-api-budget-zeile]").inner_text()
    finally:
        page.close()


def test_freigeben_fragt_mit_der_feldliste_und_ohne_budget_ruht_der_weg(browser, mit_schluessel):
    url, db = mit_schluessel
    page = _offen(browser, url)
    try:
        page.wait_for_selector("[data-api-weg]", timeout=20000)
        page.locator('[data-api-aufgabe="match_job_to_skills"] label').first.click()
        page.wait_for_selector("text=Daten an die Anthropic-API senden?", timeout=10000)
        dialog = page.inner_text("body")
        assert "verlassen die genannten Angaben deinen Rechner" in dialog and "Anthropic" in dialog
        assert "deine letzte Berufsbezeichnung" in dialog
        assert api_backend.freigaben_lesen(db) == {}, "Vor der Bestaetigung ist nichts gespeichert"
        page.get_by_role("button", name="Ja, freigeben").click()
        page.wait_for_selector('[data-api-aufgabe="match_job_to_skills"] >> text=Freigegeben, aber gerade nicht genutzt', timeout=10000)
        zeile = page.locator('[data-api-aufgabe="match_job_to_skills"]').inner_text()
        assert "Es ist kein Budget gesetzt" in zeile, "Ohne Budget ruht der Weg, und die Karte sagt warum"
        assert set(api_backend.freigaben_lesen(db)) == {"match_job_to_skills"}
        assert page.locator('[data-api-status="validate_job_quality"]').inner_text() == "Aus", "Jede Aufgabe einzeln"
    finally:
        page.close()


def test_abbrechen_im_dialog_speichert_nichts(browser, mit_schluessel):
    url, db = mit_schluessel
    page = _offen(browser, url)
    try:
        page.wait_for_selector("[data-api-weg]", timeout=20000)
        page.locator('[data-api-aufgabe="validate_job_quality"] label').first.click()
        page.wait_for_selector("text=Daten an die Anthropic-API senden?", timeout=10000)
        page.get_by_role("button", name="Abbrechen").click()
        page.wait_for_timeout(500)
        assert api_backend.freigaben_lesen(db) == {}
        assert page.locator('[data-api-status="validate_job_quality"]').inner_text() == "Aus"
    finally:
        page.close()


def test_mit_budget_ist_die_aufgabe_bereit_und_die_datenschutz_anzeige_nennt_den_weg(browser, mit_schluessel):
    url, db = mit_schluessel
    api_backend.einstellungen_setzen(db, aufgaben=["validate_job_quality"], bestaetigt=True)
    page = _offen(browser, url)
    try:
        page.wait_for_selector("[data-api-weg]", timeout=20000)
        page.locator("[data-api-budget-eingabe]").fill("2,50")
        page.locator("[data-api-budget-speichern]").click()
        page.wait_for_selector("[data-api-aufgabe=\"validate_job_quality\"] >> text=Freigegeben und bereit", timeout=10000)
        assert api_backend.budget_lesen(db) == 2_500_000
        assert "Verbraucht 0,00 US-Dollar von 2,50 US-Dollar" in page.locator("[data-api-budget-zeile]").inner_text()
        assert page.locator('[data-api-modell="validate_job_quality"]').count() == 1, "Das Modell ist waehlbar, sobald freigegeben"
        text = _datenschutz_text(page)
        assert "Direkt an die Anthropic-API (dein API-Weg):" in text
        assert "Anzeigentexte auf Vollständigkeit prüfen" in text
        assert "Berufsbezeichnung" not in text.split("Direkt an die Anthropic-API")[1].split("Externe Anfragen")[0], (
            "Diese Aufgabe sendet nichts aus dem Profil, und die Anzeige sagt es nicht anders")
    finally:
        page.close()


def test_ein_ungueltiges_budget_wird_in_der_karte_abgewiesen(browser, mit_schluessel):
    url, db = mit_schluessel
    page = _offen(browser, url)
    try:
        page.wait_for_selector("[data-api-weg]", timeout=20000)
        page.locator("[data-api-budget-eingabe]").fill("viel")
        page.locator("[data-api-budget-speichern]").click()
        page.wait_for_selector("text=Das Budget braucht einen Betrag in US-Dollar", timeout=10000)
        assert api_backend.budget_lesen(db) is None
    finally:
        page.close()


def test_die_probe_fragt_erst_und_sagt_danach_gueltig(browser, mit_schluessel):
    url, db = mit_schluessel
    transport = FakeTransport(antwort("ok", ein=12, aus=1))
    api_backend.transport_setzen(transport)
    page = _offen(browser, url)
    try:
        page.wait_for_selector("[data-api-weg]", timeout=20000)
        assert "Noch nicht geprüft" in page.locator("[data-api-schluessel]").inner_text()
        page.locator("[data-api-pruefen]").click()
        page.wait_for_selector("text=Schlüssel prüfen?", timeout=10000)
        assert transport.anzahl == 0, "Ohne Bestaetigung geht nichts hinaus"
        page.get_by_role("button", name="Ja, prüfen").click()
        page.wait_for_selector("[data-api-schluessel] >> text=Gültig – die API hat die Probeanfrage angenommen", timeout=10000)
        assert transport.anzahl == 1
        assert api_backend.pruefung_lesen(db)["ergebnis"] == "gueltig"
        assert TESTSCHLUESSEL not in page.content()
    finally:
        page.close()


def test_eine_misslungene_probe_sagt_nicht_gueltig(browser, mit_schluessel):
    from _api_hilfen import fehlerantwort
    url, db = mit_schluessel
    api_backend.transport_setzen(FakeTransport(fehlerantwort(401, "authentication_error", "invalid x-api-key")))
    page = _offen(browser, url)
    try:
        page.wait_for_selector("[data-api-weg]", timeout=20000)
        page.locator("[data-api-pruefen]").click()
        page.get_by_role("button", name="Ja, prüfen").click()
        page.wait_for_selector("[data-api-schluessel] >> text=Die API hat den Schlüssel abgelehnt", timeout=10000)
        assert "Gültig" not in page.locator("[data-api-schluessel]").inner_text()
    finally:
        page.close()


# ============================================================ Freigabe ohne Schluessel: die Karte bleibt und sagt, dass der Weg ruht

def test_eine_freigabe_ohne_schluessel_bleibt_sichtbar_und_sagt_dass_der_weg_ruht(browser, tmp_path, monkeypatch):
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)
    db, dash, srv, t, url = _starten(tmp_path)
    try:
        api_backend.einstellungen_setzen(db, aufgaben=["match_job_to_skills"], budget_usd=1, bestaetigt=True)
        monkeypatch.delenv(api_backend.ENV_SCHLUESSEL)
        page = _offen(browser, url)
        try:
            page.wait_for_selector("[data-api-weg]", timeout=20000)
            text = page.locator("[data-api-weg]").inner_text()
            assert "Kein Schlüssel gefunden" in text and api_backend.ENV_SCHLUESSEL in text
            assert "der API-Weg ruht" in text
            assert page.locator("[data-api-pruefen]").is_disabled()
            # ohne Schluessel laesst sich nichts NEU freigeben, aber Wegnehmen geht immer
            assert page.locator('[data-api-aufgabe="validate_job_quality"] input').is_disabled()
            assert page.locator('[data-api-aufgabe="match_job_to_skills"] input').is_enabled()
        finally:
            page.close()
    finally:
        _beenden(dash, srv, t, db)


def test_der_hauptschalter_sperrt_die_aufgabe_und_die_karte_nennt_den_grund(browser, mit_schluessel):
    url, db = mit_schluessel
    api_backend.einstellungen_setzen(db, aufgaben=["match_job_to_skills"], budget_usd=1, bestaetigt=True)
    db.set_ki_features(master=False)
    page = _offen(browser, url)
    try:
        page.wait_for_selector("[data-api-weg]", timeout=20000)
        zeile = page.locator('[data-api-aufgabe="match_job_to_skills"]').inner_text()
        assert "Der KI-Hauptschalter ist aus" in zeile and "Claude (Cloud)" in zeile
    finally:
        page.close()


def test_die_seite_hat_keinen_absturz_und_keinen_seitenfehler(browser, mit_schluessel):
    url, _db = mit_schluessel
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    fehler = []
    page.on("pageerror", lambda e: fehler.append(str(e)[:200]))
    page.goto(f"{url}/#einstellungen", wait_until="load", timeout=30000)
    page.wait_for_selector("[data-settings-reiter]", timeout=20000)
    for reiter in ("ai", "datenschutz", "claude"):
        _reiter(page, reiter)
        page.wait_for_timeout(500)
        assert not page.get_by_text("Dieser Bereich ist abgestürzt").count()
    page.close()
    assert not fehler, fehler
