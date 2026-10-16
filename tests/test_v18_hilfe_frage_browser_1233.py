"""#1233 (F51) - die Hilfe zum Fragen am GERENDERTEN Bild.

Ein durchlaufender Build ist kein Beleg dafuer, dass die Seite rendert (v1.7.64 MERKE 1): hier wird gefragt und geklickt. Geprueft wird, was ein
Mensch sieht und tut: eine Frage im Hilfe-Dialog, die Karten mit Quelle, die Wege weiter (oeffnen, Wiki, Prompt kopieren), die ehrliche
Antwort auf eine Frage ausserhalb von PBP, die Eingabe in der Seitenleiste (nur bei laufender lokaler KI), die Kurzantwort der KI (gestellt:
der Server liefert sie nicht echt) und der Schalter in den Einstellungen. Fragen bleiben nirgends liegen.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

pw = pytest.importorskip("playwright")  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from browser_hilfen import einstellungen_reiter  # noqa: E402

KOPIEREN = """
(() => {
  window.__kopiert = "";
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: async (text) => { window.__kopiert = text; } },
    configurable: true,
  });
})();
"""


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _warte_auf_server(url: str, timeout: float = 10.0) -> None:
    ende = time.time() + timeout
    while time.time() < ende:
        try:
            if httpx.get(url, timeout=1.0).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"Dashboard unter {url} wurde nicht bereit")


@pytest.fixture
def live(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Max Tester", "email": "max@example.com", "summary": "Berater", "preferences": {"stellentyp": "festanstellung"}})
    dash._db = db
    port = _freier_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(dash.app, host="127.0.0.1", port=port, log_level="warning"))
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _warte_auf_server(url)
    yield {"url": url, "db": db}
    server.should_exit = True
    thread.join(timeout=10)
    dash._db = None
    for t in threading.enumerate():
        if t.name.startswith("pbp-"):
            t.join(timeout=10)
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture(scope="module")
def browser():
    try:
        with sync_playwright() as p:
            instanz = p.chromium.launch(headless=True)
            yield instanz
            instanz.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def _seite(browser, live, hash_="#dashboard"):
    kontext = browser.new_context(viewport={"width": 1440, "height": 960})
    seite = kontext.new_page()
    seite.add_init_script(KOPIEREN)
    seite.goto(live["url"] + hash_, wait_until="domcontentloaded")
    seite.locator("div#root").wait_for(state="visible")
    spaeter = seite.get_by_role("button", name="Später")
    if spaeter.count():
        try:
            spaeter.first.wait_for(state="visible", timeout=1500)
            spaeter.first.click()
        except PlaywrightError:
            pass
    return kontext, seite


def _hilfe_oeffnen(seite):
    seite.get_by_title("Hilfe & Support").click()
    seite.get_by_role("heading", name="Hilfe & Support").wait_for(state="visible")
    seite.get_by_role("button", name="Frag mich", exact=True).click()
    seite.locator('[data-hilfe-frage="voll"]').wait_for(state="visible")


def _fragen(seite, wo, text):
    feld = wo.locator("[data-hilfe-eingabe]")
    feld.fill(text)
    feld.press("Enter")


def test_eine_frage_im_hilfe_dialog_zeigt_karten_mit_quelle(live, browser):
    kontext, seite = _seite(browser, live)
    try:
        _hilfe_oeffnen(seite)
        assert "nicht gespeichert" in seite.locator('[data-hilfe-frage="voll"]').inner_text()
        _fragen(seite, seite.locator('[data-hilfe-frage="voll"]'), "Wie aktualisiere ich PBP?")
        antwort = seite.locator('[data-hilfe-antwort="gefunden"]')
        antwort.wait_for(state="visible")
        assert "Das habe ich dazu gefunden" in antwort.inner_text()
        karten = antwort.locator("[data-hilfe-karte]")
        assert 1 <= karten.count() <= 3
        assert karten.first.locator("h4").inner_text().strip()
        assert "›" in karten.first.locator("[data-hilfe-quelle]").inner_text(), "die Karte nennt ihre Quelle"
        assert "Wie aktualisiere ich PBP?" in antwort.locator("[data-hilfe-frage-text]").inner_text()
    finally:
        kontext.close()


def test_beispielfragen_stehen_vor_der_ersten_frage_und_fragen_beim_klick(live, browser):
    """Wer nicht weiss, was er fragen soll, bekommt Anhaltspunkte; nach der ersten Frage stehen sie nicht mehr im Weg."""
    kontext, seite = _seite(browser, live)
    try:
        _hilfe_oeffnen(seite)
        beispiele = seite.locator("[data-hilfe-beispiel]")
        assert beispiele.count() >= 3
        text = beispiele.first.inner_text().strip()
        beispiele.first.click()
        antwort = seite.locator('[data-hilfe-antwort="gefunden"]')
        antwort.wait_for(state="visible")
        assert text in antwort.locator("[data-hilfe-frage-text]").inner_text()
        assert seite.locator("[data-hilfe-beispiele]").count() == 0, "nach der ersten Frage stehen die Beispiele nicht mehr da"
    finally:
        kontext.close()


def test_oeffnen_fuehrt_in_den_richtigen_reiter_und_schliesst_den_dialog(live, browser):
    kontext, seite = _seite(browser, live)
    try:
        _hilfe_oeffnen(seite)
        _fragen(seite, seite.locator('[data-hilfe-frage="voll"]'), "Wo stelle ich ein, dass sich PBP selbst aktualisiert?")
        seite.locator("[data-hilfe-antwort]").wait_for(state="visible")
        knopf = seite.locator('[data-hilfe-aktion="oeffnen"]').first
        knopf.wait_for(state="visible")
        assert knopf.inner_text().startswith("Öffnen: ")
        knopf.click()
        seite.wait_for_function("() => location.hash.startsWith('#einstellungen')")
        seite.locator("[data-settings-reiter]").wait_for(state="visible")
        assert seite.get_by_role("heading", name="Hilfe & Support").count() == 0, "der Dialog bleibt nicht stehen"
    finally:
        kontext.close()


def test_der_wiki_link_geht_ins_projekt_wiki_in_neuem_tab(live, browser):
    kontext, seite = _seite(browser, live)
    try:
        _hilfe_oeffnen(seite)
        _fragen(seite, seite.locator('[data-hilfe-frage="voll"]'), "Wie hole ich einen früheren Stand meiner Daten zurück?")
        seite.locator("[data-hilfe-antwort]").wait_for(state="visible")
        link = seite.locator('[data-hilfe-aktion="wiki"]').first
        link.wait_for(state="visible")
        assert link.get_attribute("href").startswith("https://github.com/MadGapun/PBP/wiki/")
        assert link.get_attribute("target") == "_blank" and "noopener" in (link.get_attribute("rel") or "")
    finally:
        kontext.close()


def test_der_prompt_zum_kopieren_wird_zur_anleitung_aufgeloest(live, browser):
    kontext, seite = _seite(browser, live)
    try:
        _hilfe_oeffnen(seite)
        _fragen(seite, seite.locator('[data-hilfe-frage="voll"]'), "Ich habe ein Vorstellungsgespräch, wie bereite ich mich vor?")
        seite.locator("[data-hilfe-antwort]").wait_for(state="visible")
        knopf = seite.locator('[data-hilfe-aktion="prompt"]').first
        knopf.wait_for(state="visible")
        assert "mit Claude" in knopf.inner_text()
        knopf.click()
        seite.wait_for_function("() => window.__kopiert && window.__kopiert.length > 40")
        kopiert = seite.evaluate("() => window.__kopiert")
        assert not kopiert.strip().startswith("/"), "ein roher /name kaeme in Claude als 'diesen Skill gibt es nicht' an"
    finally:
        kontext.close()


def test_eine_frage_ausserhalb_bekommt_den_hinweis_und_den_satz_fuer_claude(live, browser):
    kontext, seite = _seite(browser, live)
    try:
        _hilfe_oeffnen(seite)
        _fragen(seite, seite.locator('[data-hilfe-frage="voll"]'), "Wie wird das Wetter morgen?")
        antwort = seite.locator('[data-hilfe-antwort="ausserhalb"]')
        antwort.wait_for(state="visible")
        assert "nur zur Bedienung von PBP" in antwort.inner_text()
        assert "Dafür ist Claude da" not in antwort.inner_text(), "der Hinweis sagt schon, dass Claude dafür da ist: nicht doppelt"
        assert antwort.locator("[data-hilfe-karte]").count() == 0
        antwort.locator("[data-hilfe-satz]").click()
        seite.wait_for_function("() => window.__kopiert && window.__kopiert.includes('Wetter')")
        assert seite.evaluate("() => window.__kopiert").startswith("Ich habe eine Frage zu PBP")
    finally:
        kontext.close()


def test_die_frage_bleibt_nirgends_liegen(live, browser):
    """Beim Fragen geht genau EINE schreibende Anfrage hinaus - die an die Hilfe, die nichts speichert - und der Browser behaelt nichts."""
    kontext, seite = _seite(browser, live)
    try:
        _hilfe_oeffnen(seite)
        seite.wait_for_timeout(1500)            # die Seitenleiste meldet sich beim Laden (Herzschlag); das gehoert nicht zur Frage
        geschrieben = []
        seite.on("request", lambda r: geschrieben.append(f"{r.method} {r.url}") if r.method != "GET" else None)
        _fragen(seite, seite.locator('[data-hilfe-frage="voll"]'), "Geheimfrage Zebrastreifen Quartz 7731 Update?")
        seite.locator("[data-hilfe-antwort]").wait_for(state="visible")
        seite.wait_for_timeout(500)
        assert len(geschrieben) == 1 and geschrieben[0].endswith("/api/hilfe/frage"), geschrieben
        speicher = seite.evaluate("() => JSON.stringify([localStorage, sessionStorage].map((s) => Object.entries(s)))")
        assert "Zebrastreifen" not in speicher, "die Frage steht im Browserspeicher"
    finally:
        kontext.close()
    db = live["db"]
    for tabelle in ("user_activity_events", "elwosa_messages"):
        zeilen = db.connect().execute(f"SELECT * FROM {tabelle}").fetchall()
        assert not any("Zebrastreifen" in str(tuple(z)) for z in zeilen), f"die Frage steht in {tabelle}"


# ── die Seitenleiste ───────────────────────────────────────────────────────────────────────────

def _ki_status(seite, ai_state):
    """Der Status der lokalen KI wie ihn die Seitenleiste liest - die Suite hat kein Ollama."""
    def behandeln(route):
        antwort = route.fetch()
        daten = antwort.json()
        daten["ai_state"] = ai_state
        daten["is_active"] = ai_state == "active"
        route.fulfill(response=antwort, json=daten)
    seite.route("**/api/elwosa/status", behandeln)


def test_die_seitenleiste_fragt_nur_bei_laufender_ki(live, browser):
    for zustand, sichtbar in (("active", True), ("paused", False)):
        kontext = browser.new_context(viewport={"width": 1440, "height": 960})
        seite = kontext.new_page()
        seite.add_init_script(KOPIEREN)
        _ki_status(seite, zustand)
        try:
            seite.goto(live["url"] + "#dashboard", wait_until="domcontentloaded")
            seite.locator("div#root").wait_for(state="visible")
            seite.wait_for_function("() => document.body.innerText.includes('Elwosa')", timeout=15000)
            if sichtbar:
                seite.locator("[data-sidebar-hilfe]").wait_for(state="visible", timeout=15000)
            else:
                seite.wait_for_timeout(500)
                assert seite.locator("[data-sidebar-hilfe]").count() == 0, f"bei {zustand} darf die Eingabe nicht erscheinen"
        finally:
            kontext.close()


def test_in_der_seitenleiste_erscheint_die_antwort_kompakt_mit_wegen(live, browser):
    kontext = browser.new_context(viewport={"width": 1440, "height": 960})
    seite = kontext.new_page()
    seite.add_init_script(KOPIEREN)
    _ki_status(seite, "active")
    try:
        seite.goto(live["url"] + "#dashboard", wait_until="domcontentloaded")
        seite.locator("div#root").wait_for(state="visible")
        leiste = seite.locator("[data-sidebar-hilfe]")
        leiste.wait_for(state="visible", timeout=15000)
        assert leiste.locator("[data-hilfe-beispiele]").count() == 0, "die schmale Seitenleiste zeigt keine Beispielfragen"
        _fragen(seite, leiste, "Wie aktualisiere ich PBP?")
        antwort = leiste.locator('[data-hilfe-antwort="gefunden"]')
        antwort.wait_for(state="visible")
        assert antwort.locator("[data-hilfe-karte]").count() == 1, "kompakt: zuerst nur der beste Treffer"
        mehr = leiste.get_by_role("button", name="weitere Treffer zeigen")
        if mehr.count():
            mehr.first.click()
            assert antwort.locator("[data-hilfe-karte]").count() > 1
        leiste.locator('[data-hilfe-aktion="oeffnen"]').first.click()
        seite.wait_for_function("() => location.hash.startsWith('#einstellungen')")
    finally:
        kontext.close()


# ── die Kurzantwort der lokalen KI (gestellt) ──────────────────────────────────────────────────

def _ki_antworten(seite, folge):
    """Haengt an jede Antwort der Hilfe einen Auftrag und liefert die Stande aus `folge` nacheinander."""
    stande = list(folge)

    def frage(route):
        antwort = route.fetch()
        daten = antwort.json()
        daten["ki"] = {"status": "laeuft", "job": "job1"}
        route.fulfill(response=antwort, json=daten)

    def ki(route):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(stande.pop(0) if len(stande) > 1 else stande[0]))
    seite.route("**/api/hilfe/frage", frage)
    seite.route("**/api/hilfe/ki/job1", ki)


def test_die_kurzantwort_erscheint_ueber_den_karten_und_nennt_ihre_herkunft(live, browser):
    kontext, seite = _seite(browser, live)
    _ki_antworten(seite, [{"status": "laeuft"}, {"status": "fertig", "text": "Du findest es unter Erweitert › Updates.", "quellen": ["faq:wie_aktualisiere_ich_pbp"]}])
    try:
        _hilfe_oeffnen(seite)
        _fragen(seite, seite.locator('[data-hilfe-frage="voll"]'), "Wie aktualisiere ich PBP?")
        seite.locator("[data-hilfe-ki]").wait_for(state="visible")
        seite.locator("[data-hilfe-ki-text]").wait_for(state="visible", timeout=10000)
        assert "Erweitert › Updates" in seite.locator("[data-hilfe-ki-text]").inner_text()
        assert "lokalen KI" in seite.locator("[data-hilfe-ki]").inner_text()
        assert seite.locator("[data-hilfe-karte]").count() >= 1, "die Karten stehen weiter da"
    finally:
        kontext.close()


def test_eine_verworfene_kurzantwort_zeigt_nichts_und_laesst_die_karten(live, browser):
    kontext, seite = _seite(browser, live)
    _ki_antworten(seite, [{"status": "verworfen", "grund": "ohne_quelle", "text": "", "quellen": []}])
    try:
        _hilfe_oeffnen(seite)
        _fragen(seite, seite.locator('[data-hilfe-frage="voll"]'), "Wie aktualisiere ich PBP?")
        seite.locator("[data-hilfe-karte]").first.wait_for(state="visible")
        seite.wait_for_timeout(2500)
        assert seite.locator("[data-hilfe-ki]").count() == 0
    finally:
        kontext.close()


# ── der Schalter ───────────────────────────────────────────────────────────────────────────────

def test_der_schalter_fuer_die_kurzantwort_ist_aus_und_wird_gespeichert(live, browser):
    db = live["db"]
    kontext, seite = _seite(browser, live, "#einstellungen")
    try:
        seite.locator("[data-settings-reiter]").wait_for(state="visible")
        einstellungen_reiter(seite, "Lokale KI")
        schalter = seite.locator("[data-hilfe-ki-schalter]")
        schalter.wait_for(state="attached", timeout=15000)
        assert not schalter.is_checked(), "Vorgabe: aus (Beta)"
        assert "Beta" in seite.locator("[data-hilfe-ki-karte]").inner_text()
        kaestchen = seite.locator("[data-hilfe-ki-karte] label").first       # das sichtbare Kaestchen (der Eingabe selbst ist verborgen)
        kaestchen.click()
        ende = time.time() + 10
        while time.time() < ende and db.get_profile_setting("hilfe_ki_formulieren", None) is not True:
            time.sleep(0.1)
        assert db.get_profile_setting("hilfe_ki_formulieren", None) is True
        kaestchen.click()
        ende = time.time() + 10
        while time.time() < ende and db.get_profile_setting("hilfe_ki_formulieren", None) is not False:
            time.sleep(0.1)
        assert db.get_profile_setting("hilfe_ki_formulieren", None) is False
    finally:
        kontext.close()
