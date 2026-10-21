"""#1233 (F51) - die Hilfe zum Fragen am GERENDERTEN Bild.

Ein durchlaufender Build ist kein Beleg dafuer, dass die Seite rendert (v1.7.64 MERKE 1): hier wird gefragt und geklickt. Geprueft wird, was ein
Mensch sieht und tut: eine Frage im Hilfe-Dialog, die Karten mit Quelle, die Wege weiter (oeffnen, Wiki, Prompt kopieren), die ehrliche
Antwort auf eine Frage ausserhalb von PBP, die Eingabe in der Seitenleiste (nur bei laufender lokaler KI), die Kurzantwort der KI (gestellt:
der Server liefert sie nicht echt) und der Schalter in den Einstellungen. Fragen bleiben nirgends liegen.
"""
from __future__ import annotations

import json
import os
import re
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
from playwright.sync_api import expect, sync_playwright  # noqa: E402
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
        # #1254: die Antwort steht im Bereich des Verlaufs (ueber dem Feld), nicht mehr im Block des Feldes
        verlauf = seite.locator("[data-elwosa-liste]")
        antwort = verlauf.locator('[data-hilfe-antwort="gefunden"]')
        antwort.wait_for(state="visible")
        assert antwort.locator("[data-hilfe-karte]").count() == 1, "kompakt: zuerst nur der beste Treffer"
        mehr = verlauf.get_by_role("button", name="weitere Treffer zeigen")
        if mehr.count():
            mehr.first.click()
            assert antwort.locator("[data-hilfe-karte]").count() > 1
        verlauf.locator('[data-hilfe-aktion="oeffnen"]').first.click()
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


# ── #1247 (PP39): das Schliessen des Hilfe-Dialogs fragt nicht nach "ungespeicherten Eingaben" ──────────────
# Die Gegenseite (ein Dialog mit Formular fragt weiter) deckt test_g67_dialog_fragt_vor_dem_verwerfen in test_g1087_welle6_oberflaeche.py ab.

def _ruhig(seite):
    """Erst wenn die Seite fertig geladen hat: ein Klick unmittelbar nach dem Laden traf zweimal in zehn Laeufen auf einen Dialog, der ohne
    die Rueckfrage zuging (Zustand der Seite beim Start, nicht der Schutz)."""
    seite.wait_for_load_state("networkidle")


def _geschlossen_ohne_rueckfrage(seite):
    seite.get_by_role("heading", name="Hilfe & Support").wait_for(state="detached", timeout=5000)
    assert seite.locator("[data-verwerfen-frage]").count() == 0


def test_1247_eine_getippte_frage_loest_beim_schliessen_keine_rueckfrage_aus(live, browser):
    """Der Dialog hat kein Formular: die Frage wird nirgends gespeichert (der Reiter sagt es selbst). Die Rueckfrage "Deine Eingaben sind
    noch nicht gespeichert. Verwerfen?" erschien trotzdem, weil `Modal` jede Eingabe als Aenderung zaehlt (vierter Werkstatt-PC-Lauf)."""
    kontext, seite = _seite(browser, live)
    try:
        _ruhig(seite)
        _hilfe_oeffnen(seite)
        seite.locator("[data-hilfe-eingabe]").fill("Wie aktualisiere ich PBP?")
        seite.locator("[data-modal-schliessen]").last.click()
        _geschlossen_ohne_rueckfrage(seite)
    finally:
        kontext.close()


def test_1247_auch_escape_schliesst_nach_einer_frage_ohne_rueckfrage(live, browser):
    kontext, seite = _seite(browser, live)
    try:
        _ruhig(seite)
        _hilfe_oeffnen(seite)
        seite.locator("[data-hilfe-eingabe]").fill("Wie aktualisiere ich PBP?")
        seite.keyboard.press("Escape")
        _geschlossen_ohne_rueckfrage(seite)
    finally:
        kontext.close()


def test_1247_das_filterfeld_der_prompts_loest_keine_rueckfrage_aus(live, browser):
    """Dieselbe Ursache, anderer Reiter: auch ein Suchfeld im Dialog ist keine ungespeicherte Aenderung."""
    kontext, seite = _seite(browser, live)
    try:
        _ruhig(seite)
        _hilfe_oeffnen(seite)
        seite.get_by_role("button", name="Prompts", exact=True).click()
        seite.get_by_placeholder("Filter nach Titel oder Beschreibung...").fill("Interview")
        seite.locator("[data-modal-schliessen]").last.click()
        _geschlossen_ohne_rueckfrage(seite)
    finally:
        kontext.close()



# ── #1254 (F57): die Fragen und Elwosa teilen sich EINEN Bereich zum Scrollen ──────────────────────
#
# Nutzerrueckmeldung zu rc.4: Stellt man in der Seitenleiste eine Frage, schrumpft der Elwosa-Verlauf auf zwei Zeilen, weil die Antworten in einem
# eigenen Scroller darunter wachsen. Gewuenscht ist EIN Bereich. Gemessen wird am gerenderten Bild (Zahl der Scrollbereiche, Hoehe des Verlaufs,
# was im Blick ist), nicht am Quelltext: #907 hatte "genau EIN Scroll-Container" schon einmal als Zielbild, und kein Test hat bemerkt, dass #1233
# es aufhob, weil keiner die Hoehe mass.

SCROLLBEREICHE = """
(wurzel) => [...wurzel.querySelectorAll('*')].filter((e) => {
  const o = getComputedStyle(e).overflowY;
  return (o === 'auto' || o === 'scroll') && e.getClientRects().length > 0;
}).length
"""

# Steht der Anfang der Antwort oben im sichtbaren Teil des Verlaufs? (`nr`: die wievielte Antwort, von 0 an gezaehlt). Bei einer Antwort, die hoeher
# ist als der Bereich, liegt ihre Oberkante knapp unter dem oberen Rand (4 px Abstand), nicht irgendwo im Bild.
ANFANG_IM_BLICK = """
(nr) => {
  const liste = document.querySelector('[data-elwosa-liste]').getBoundingClientRect();
  const a = document.querySelectorAll('[data-elwosa-liste] [data-hilfe-antwort]')[nr];
  if (!a) return false;
  const oben = a.getBoundingClientRect().top - liste.top;
  return oben >= -1 && oben <= 40;
}
"""


def _elwosa_nachrichten(db, anzahl=10):
    """Elwosa hat schon etwas gesagt: so viele Nachrichten, dass der Verlauf scrollt (die Seitenleiste holt die letzten zehn)."""
    for nr in range(anzahl):
        db.add_elwosa_message(
            f"Nachricht {nr + 1}: Elwosa sagt etwas, das in der schmalen Seitenleiste auf mehrere Zeilen umbricht.",
            trigger_kind="test", trigger_ref=f"t1254-{nr}",
        )


def _seite_mit_verlauf(browser, live, platz=None, ohne_herzschlag=False, anzahl=10):
    """Die Seite mit zehn Nachrichten Elwosas (`anzahl`) und laufender KI. `platz`: so hoch (px) ist der Bereich fuer Elwosa - ein kleiner Platz, der nicht
    vom Fenster und von der Hoehe des Menues abhaengt (die gibt die Maschine vor); ohne Angabe gilt, was das Fenster hergibt.
    `ohne_herzschlag`: der Herzschlag der Seite (`/api/elwosa/heartbeat`) schreibt Elwosa von sich aus gelegentlich eine weitere Zeile; wer prueft, was
    GANZ UNTEN steht, laesst nichts dazwischenkommen (der Verlauf wird trotzdem nachgeladen, nur der Herzschlag schreibt nichts)."""
    _elwosa_nachrichten(live["db"], anzahl)
    kontext = browser.new_context(viewport={"width": 1440, "height": 960})
    seite = kontext.new_page()
    seite.add_init_script(KOPIEREN)
    _ki_status(seite, "active")
    if ohne_herzschlag:
        seite.route("**/api/elwosa/heartbeat", lambda route: route.fulfill(status=200, content_type="application/json", body="{}"))
    seite.goto(live["url"] + "#dashboard", wait_until="domcontentloaded")
    seite.locator("div#root").wait_for(state="visible")
    seite.locator("[data-sidebar-hilfe]").wait_for(state="visible", timeout=15000)
    seite.wait_for_function("(n) => document.querySelectorAll('[data-elwosa-nachricht]').length >= n", arg=min(8, anzahl), timeout=15000)
    if platz:
        seite.locator("[data-elwosa-chat]").evaluate("(el, px) => { el.style.maxHeight = px + 'px'; }", platz)
    return kontext, seite


def _gefragt(seite, text):
    """Fragt in der Seitenleiste und wartet, bis die Antwort auf DIESE Frage da ist - gleich wo sie steht: wo, pruefen die Tests (die Fragen eines
    Tests sind verschieden; nach der fuenften Frage bleibt die Zahl der Antworten gleich, darum wird nicht gezaehlt)."""
    _fragen(seite, seite.locator("[data-sidebar-hilfe]"), text)
    seite.wait_for_function(
        "(t) => [...document.querySelectorAll('[data-hilfe-frage-text]')].some((e) => e.textContent.includes(t))", arg=text[:60], timeout=15000)


def test_1254_nach_einer_frage_gibt_es_in_der_seitenleiste_einen_einzigen_scrollbereich(live, browser):
    kontext, seite = _seite_mit_verlauf(browser, live)
    try:
        wurzel = seite.locator("[data-elwosa-chat]")
        vorher = wurzel.evaluate(SCROLLBEREICHE)
        _gefragt(seite, "Wie aktualisiere ich PBP?")
        nachher = wurzel.evaluate(SCROLLBEREICHE)
        assert (vorher, nachher) == (1, 1), f"Bereiche zum Scrollen vor der Frage: {vorher}, danach: {nachher} - gewuenscht ist EINER"
    finally:
        kontext.close()


# Der Platz, den Elwosa neben dem Verlauf braucht: Kopf, Feld, Rand. Er aendert sich nicht, wenn Antworten dazukommen - der Verlauf behaelt seine Hoehe.
# (Die Hoehe des Verlaufs selbst eignet sich nicht zum Vergleich: der Kopf der Seitenleiste waechst nach dem Laden um eine Zeile, sobald die
# Pruefung auf Updates antwortet, und nimmt dem Fuss dieselbe Hoehe weg.)
DRUMHERUM = """
() => document.querySelector('[data-elwosa-chat]').getBoundingClientRect().height
    - document.querySelector('[data-elwosa-liste]').getBoundingClientRect().height
"""


def test_1254_der_elwosa_verlauf_behaelt_seine_hoehe_wenn_antworten_dazukommen(live, browser):
    kontext, seite = _seite_mit_verlauf(browser, live)
    try:
        vorher = seite.evaluate(DRUMHERUM)
        _gefragt(seite, "Wie aktualisiere ich PBP?")
        nach_eins = seite.evaluate(DRUMHERUM)
        _gefragt(seite, "Wie lege ich eine Bewerbung an?")
        nach_zwei = seite.evaluate(DRUMHERUM)
        assert abs(nach_eins - vorher) <= 2 and abs(nach_zwei - vorher) <= 2, (
            f"neben dem Verlauf braucht Elwosa {vorher:.0f} px, nach der ersten Frage {nach_eins:.0f}, nach der zweiten {nach_zwei:.0f}: "
            "die Antworten nehmen dem Verlauf die Hoehe")
    finally:
        kontext.close()


def test_1254_die_antwort_steht_im_verlauf_und_die_eingabe_bleibt_sichtbar_daneben(live, browser):
    kontext, seite = _seite_mit_verlauf(browser, live)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        assert liste.locator("[data-hilfe-trennzeile]").count() == 0, "die Trennzeile steht, bevor etwas gefragt wurde"
        # der Rahmen fuer Vorleseprogramme ist schon da, bevor etwas gefragt wird: nur dann meldet es die neue Antwort
        ansage = seite.locator('[data-elwosa-chat] [data-hilfe-ansage][aria-live="polite"]')
        assert ansage.count() == 1, "der Rahmen fuer die Meldung einer neuen Antwort fehlt oder meldet nichts"
        _gefragt(seite, "Wie aktualisiere ich PBP?")
        assert liste.locator('[data-hilfe-antwort="gefunden"]').count() == 1, "die Antwort steht nicht im Bereich des Verlaufs"
        assert liste.locator("[data-hilfe-eingabe]").count() == 0, "die Eingabe scrollt mit weg"
        assert liste.locator("[data-hilfe-trennzeile]").count() == 1, "die Trennzeile fehlt"
        assert "Fragen zur Bedienung" in liste.locator("[data-hilfe-trennzeile]").text_content()      # inner_text() waere GROSS geschrieben (CSS)
        assert liste.locator("[data-elwosa-nachricht]").count() >= 8, "Elwosas Nachrichten sind verschwunden"
        # nach der Zeit: die Nachrichten, die schon da waren, stehen VOR der Frage und ihrer Antwort (nicht danach, nicht am Anfang)
        davor = seite.evaluate(
            "() => { const a = document.querySelector('[data-elwosa-liste] [data-hilfe-antwort]'); "
            "return [...document.querySelectorAll('[data-elwosa-liste] [data-elwosa-nachricht]')]"
            ".every((m) => Boolean(m.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING)); }")
        assert davor, "die Antwort steht vor Nachrichten Elwosas, die aelter sind"
        expect(ansage).to_contain_text("Wie aktualisiere ich PBP?")
        expect(seite.locator("[data-hilfe-eingabe]")).to_be_in_viewport()
    finally:
        kontext.close()


def test_1254_die_neue_antwort_ist_mit_ihrem_anfang_im_blick(live, browser):
    """Auch dann, wenn sie hoeher ist als der Bereich: erst die Frage und der erste Treffer, der Rest darunter zum Scrollen."""
    kontext, seite = _seite_mit_verlauf(browser, live, platz=200)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        _gefragt(seite, "Wie aktualisiere ich PBP?")
        antwort = liste.locator("[data-hilfe-antwort]").first
        assert antwort.bounding_box()["height"] > liste.bounding_box()["height"], "der Fall ist keiner: die Antwort passt in den Bereich"
        seite.wait_for_function(ANFANG_IM_BLICK, arg=0, timeout=5000)
        assert seite.evaluate(ANFANG_IM_BLICK, 0)
    finally:
        kontext.close()


def test_1254_zwei_fragen_stehen_der_reihe_nach_und_die_neueste_ist_im_blick(live, browser):
    kontext, seite = _seite_mit_verlauf(browser, live, platz=200)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        _gefragt(seite, "Wie aktualisiere ich PBP?")
        _gefragt(seite, "Wie lege ich eine Bewerbung an?")
        fragen = liste.locator("[data-hilfe-frage-text]").all_inner_texts()
        assert [f.removeprefix("Frage: ").strip() for f in fragen] == ["Wie aktualisiere ich PBP?", "Wie lege ich eine Bewerbung an?"], fragen
        assert liste.locator("[data-hilfe-trennzeile]").count() == 1, "die Trennzeile steht einmal vor der Reihe der Antworten, nicht je Frage"
        seite.wait_for_function(ANFANG_IM_BLICK, arg=1, timeout=5000)
        assert seite.locator("[data-elwosa-chat]").evaluate(SCROLLBEREICHE) == 1
    finally:
        kontext.close()


def test_1254_der_hilfe_dialog_zeigt_die_neueste_antwort_oben(live, browser):
    """Der Dialog bleibt, wie er war (Eingabe oben, die neueste Antwort darunter zuerst); nur die Seitenleiste ordnet wie ein Chat."""
    kontext, seite = _seite(browser, live)
    try:
        _hilfe_oeffnen(seite)
        dialog = seite.locator('[data-hilfe-frage="voll"]')
        _fragen(seite, dialog, "Wie aktualisiere ich PBP?")
        dialog.locator('[data-hilfe-antwort]').first.wait_for(state="visible")
        _fragen(seite, dialog, "Wie lege ich eine Bewerbung an?")
        seite.wait_for_function("() => document.querySelectorAll('[data-hilfe-frage=\"voll\"] [data-hilfe-antwort]').length === 2", timeout=15000)
        fragen = dialog.locator("[data-hilfe-frage-text]").all_inner_texts()
        assert [f.removeprefix("Frage: ").strip() for f in fragen] == ["Wie lege ich eine Bewerbung an?", "Wie aktualisiere ich PBP?"], fragen
    finally:
        kontext.close()


def test_1254_eine_neue_nachricht_elwosas_kommt_unter_die_antwort_und_ist_zu_sehen(live, browser):
    """Wie in einem Chat steht, was neu ist, UNTEN - auch nach einer Frage. Sonst ginge jede Meldung Elwosas, die nach der Antwort kommt,
    oberhalb der Antworten unter, und wer unten liest, sieht sie nie."""
    kontext, seite = _seite_mit_verlauf(browser, live, platz=200, ohne_herzschlag=True)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        _gefragt(seite, "Wie aktualisiere ich PBP?")
        # wer die Antwort liest, steht am Ende des Bereichs; erst wenn die Seite das Scroll-Ereignis behandelt hat (zwei Bilder spaeter), kommt etwas
        # Neues: sonst entscheidet sie noch nach der Lage VOR dem Scrollen (auf einem langsamen Rechner ein Wettlauf, auf der CI beobachtet)
        liste.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        seite.evaluate("() => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)))")
        seite.wait_for_function("() => { const l = document.querySelector('[data-elwosa-liste]'); return l.scrollHeight - l.scrollTop - l.clientHeight < 30; }")
        live["db"].add_elwosa_message("Neu nach der Antwort: die Suche ist fertig.", trigger_kind="test", trigger_ref="t1254-neu")
        seite.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")        # holt den Verlauf sofort, wie der Takt von 30 Sekunden
        neu = liste.get_by_text("Neu nach der Antwort")
        neu.wait_for(state="attached", timeout=10000)
        nach_der_antwort = seite.evaluate(
            "() => { const a = document.querySelector('[data-hilfe-antwort]'); "
            "const n = [...document.querySelectorAll('[data-elwosa-nachricht]')].find((m) => m.textContent.includes('Neu nach der Antwort')); "
            "return Boolean(a.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING); }")
        assert nach_der_antwort, "die neue Nachricht steht ueber der Antwort"
        expect(neu).to_be_in_viewport()
    finally:
        kontext.close()


def test_1254_die_sechste_frage_verdraengt_die_aelteste_und_ist_im_blick(live, browser):
    """Der Verlauf haelt hoechstens fuenf Fragen; die neueste steht unten und mit ihrem Anfang im Blick."""
    fragen = ["Wie aktualisiere ich PBP?", "Wie lege ich eine Bewerbung an?", "Wo liegen meine Daten auf dem Rechner?",
              "Wie melde ich einen Fehler?", "Wie hole ich einen früheren Stand meiner Daten zurück?",
              "Wo stelle ich ein, dass sich PBP selbst aktualisiert?"]
    kontext, seite = _seite_mit_verlauf(browser, live, platz=200)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        for frage in fragen:
            _gefragt(seite, frage)
        gezeigt = [f.removeprefix("Frage: ").strip() for f in liste.locator("[data-hilfe-frage-text]").all_inner_texts()]
        assert gezeigt == fragen[1:], gezeigt
        assert liste.locator("[data-hilfe-trennzeile]").count() == 1
        seite.wait_for_function(ANFANG_IM_BLICK, arg=4, timeout=5000)
    finally:
        kontext.close()


def test_1254_eine_lange_frage_ohne_leerzeichen_macht_keine_waagerechte_leiste(live, browser):
    """Eine eingefuegte Adresse (bis 400 Zeichen) darf den Bereich nicht breiter machen als die Seitenleiste."""
    kontext, seite = _seite_mit_verlauf(browser, live)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        _gefragt(seite, "https://beispiel.example/" + "a" * 300)
        breiter = liste.evaluate("el => el.scrollWidth - el.clientWidth")
        assert breiter <= 1, f"der Bereich ist {breiter} px breiter als sichtbar: eine waagerechte Leiste"
    finally:
        kontext.close()


# ── #1256 (F58): die Marke "N neu" und das Mitscrollen bei geaenderter Hoehe ───────────────────────────────────────────
#
# Zwei aeltere Maengel im Mitscrollen des Elwosa-Stroms (Sticky-Bottom aus #611), beim Messen von #1254 aufgefallen. Es geht um EINE Frage: sieht der
# Mensch, dass Elwosa etwas gesagt hat? (1) Die Marke "N neu" zaehlte die Nachrichten der Liste; der Verlauf holt nur zehn, bei voller Liste blieb die
# Zahl gleich - die Marke kam im Normalfall nie, und nach einem Ausblenden kam sie ohne Anlass. (2) Das Mitscrollen merkte sich "am Ende" nur aus einem
# Scroll-Ereignis; aenderte sich die Hoehe ohne Scrollen (der Kopf der Seitenleiste waechst um eine Zeile, das Fenster wird kleiner), rutschte das Ende
# aus dem Bild, und eine Meldung danach blieb verdeckt. Gemessen wird am gerenderten Bild. Die Erwartung an die Zahl in der Marke kommt aus dem Bild
# selbst (wie viele Meldungen unter der zuletzt gelesenen stehen), nicht aus einer festen Zahl: die Seite legt beim Laden von sich aus Zeilen an
# (Wiki-Hinweis, Welt-Zeile des Herzschlags), und die haengen von der Uhr ab.

MARKE = re.compile(r"\d+ neu")

ABSTAND_ZUM_ENDE = """
() => { const l = document.querySelector('[data-elwosa-liste]'); return l.scrollHeight - l.scrollTop - l.clientHeight; }
"""

# Liegt die Nachricht mit diesem Text ganz im sichtbaren Teil des Bereichs? (null: sie steht nicht im Verlauf)
NACHRICHT_IM_BEREICH = """
(text) => {
  const liste = document.querySelector('[data-elwosa-liste]').getBoundingClientRect();
  const m = [...document.querySelectorAll('[data-elwosa-nachricht]')].find((e) => e.textContent.includes(text));
  if (!m) return null;
  const r = m.getBoundingClientRect();
  return r.top >= liste.top - 1 && r.bottom <= liste.bottom + 1;
}
"""

# Wie viele Nachrichten stehen UNTER der mit diesem Text? (-1: sie steht nicht mehr im Verlauf)
NACHRICHTEN_NACH = """
(text) => {
  const alle = [...document.querySelectorAll('[data-elwosa-nachricht]')].map((e) => e.textContent);
  const i = alle.findIndex((t) => t.includes(text));
  return i < 0 ? -1 : alle.length - 1 - i;
}
"""

# Der Kopf der Seitenleiste waechst um eine Zeile, wie "Update-Stand unbekannt / Jetzt pruefen" (gemessen: 38 px samt Abstand). Die Zeile kommt an dieselbe
# Stelle wie die echte, in den Statusblock oben; Elwosa bekommt dadurch 38 px weniger Hoehe, ohne dass jemand scrollt.
KOPF_WAECHST = """
(px) => {
  const block = document.querySelector('aside .brand-title').parentElement;
  const zeile = document.createElement('span');
  zeile.setAttribute('data-test-kopfzeile', '');
  zeile.style.cssText = 'display:block;height:' + (px - 6) + 'px';
  block.appendChild(zeile);
}
"""
# derselbe Handgriff im selben Augenblick, in dem die Meldung mit diesem Text im Verlauf steht: die Seite ist dann gerade ans Ende gesprungen, das
# Scroll-Ereignis zu diesem Sprung kommt erst im naechsten Bild und rechnet schon mit der neuen Hoehe (ein Beobachter der Seite laeuft als
# Mikroaufgabe gleich nach dem Einfuegen, noch vor dem naechsten Bild)
KOPF_WAECHST_MIT_DER_MELDUNG = (
    "({px, text}) => { const beobachter = new MutationObserver(() => { "
    "if ([...document.querySelectorAll('[data-elwosa-nachricht]')].some((e) => e.textContent.includes(text))) { beobachter.disconnect(); ("
    + KOPF_WAECHST.strip() + ")(px); } }); beobachter.observe(document.querySelector('[data-elwosa-liste]'), { childList: true, subtree: true }); }"
)


def _bilder(seite):
    """Laesst die Seite ein paar Bilder zeichnen: Scroll-Ereignisse und Beobachter der Groesse laufen zu Beginn des naechsten Bildes."""
    seite.evaluate("() => new Promise((fertig) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(fertig, 60))))")


def _meldung(live, text, nr):
    live["db"].add_elwosa_message(text, trigger_kind="test", trigger_ref=f"t1256-{nr}")


def _holen(seite, text):
    """Holt den Verlauf sofort (wie der Takt von 30 Sekunden) und wartet, bis die Meldung mit diesem Text im Verlauf steht."""
    seite.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
    seite.wait_for_function(
        "(t) => [...document.querySelectorAll('[data-elwosa-nachricht]')].some((e) => e.textContent.includes(t))", arg=text, timeout=10000)
    _bilder(seite)


def _nach_oben(seite):
    seite.locator("[data-elwosa-liste]").evaluate("l => { l.scrollTop = 0; }")
    _bilder(seite)


def _ans_ende(seite):
    seite.locator("[data-elwosa-liste]").evaluate("l => { l.scrollTop = l.scrollHeight; }")
    seite.wait_for_function(
        "() => { const l = document.querySelector('[data-elwosa-liste]'); return l.scrollHeight - l.scrollTop - l.clientHeight < 2; }", timeout=5000)
    _bilder(seite)


def _zuletzt_gelesen(seite):
    """Die neueste Nachricht, die gerade im Verlauf steht (ihr Anfang als Schluessel): alles, was danach kommt, ist neu."""
    return seite.evaluate("() => [...document.querySelectorAll('[data-elwosa-nachricht]')].pop().textContent.slice(0, 60)")


def _ohne_wiki_hinweis(live):
    """Die Seite legt 0,8 s nach dem Laden einen Wiki-Hinweis fuer ihre Route an. Hier liegt er schon da, als aelteste Zeile ausserhalb des Fensters:
    sonst haengt die Zahl der Zeilen waehrend des Tests davon ab, wie schnell die Maschine ist."""
    live["db"].add_elwosa_message("Hinweis aus dem Wiki: die Seiten findest du im Menü links.", trigger_kind="wiki_hint", trigger_ref="dashboard:t1256")


def _marke_neu_pruefen(live, browser, anzahl):
    """Elwosa hat `anzahl` Nachrichten gesagt, der Mensch liest ganz oben, dann kommt eine neue: die Marke "N neu" steht da, N stimmt, der Mensch wird
    nicht nach unten gezogen, und ein Klick fuehrt ans Ende und raeumt die Marke weg."""
    _ohne_wiki_hinweis(live)
    kontext, seite = _seite_mit_verlauf(browser, live, platz=200, anzahl=anzahl)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        marke = seite.locator("[data-elwosa-chat]").get_by_role("button", name=MARKE)
        seite.wait_for_timeout(1500)          # die Seite hat ihre ersten Zeilen geholt
        _nach_oben(seite)
        assert seite.evaluate(ABSTAND_ZUM_ENDE) > 100, "der Fall ist keiner: der Verlauf scrollt nicht"
        gelesen = _zuletzt_gelesen(seite)
        _meldung(live, "Neu, waehrend oben gelesen wird: die Suche ist fertig.", 1)
        _holen(seite, "waehrend oben gelesen wird")
        erwartet = seite.evaluate(NACHRICHTEN_NACH, gelesen)
        assert erwartet >= 1, "der Fall ist keiner: die neue Meldung steht nicht unter der zuletzt gelesenen"
        assert marke.count() == 1, f"keine Marke 'N neu', obwohl {erwartet} neue Meldung(en) unter dem Bild liegen (Verlauf mit {anzahl} Nachrichten)"
        assert marke.inner_text().strip() == f"{erwartet} neu", marke.inner_text()
        assert liste.evaluate("l => l.scrollTop") < 60, "wer oben liest, wird nach unten gezogen"
        marke.click()
        _bilder(seite)
        assert seite.evaluate(ABSTAND_ZUM_ENDE) < 2, "der Klick auf die Marke fuehrt nicht ans Ende"
        assert marke.count() == 0, "die Marke bleibt nach dem Klick stehen"
    finally:
        kontext.close()


def test_1256_die_marke_neu_erscheint_auch_bei_voller_liste(live, browser):
    """Der Normalfall: der Verlauf holt zehn Nachrichten und ist voll, eine neue schiebt die aelteste hinaus - die Zahl der Nachrichten bleibt zehn."""
    _marke_neu_pruefen(live, browser, 10)


def test_1256_bei_kurzer_liste_zeigt_die_marke_weiter_die_neuen(live, browser):
    """Das ging schon: bei kurzer Liste waechst die Zahl wirklich. Es muss so bleiben (Gegenstueck zum Normalfall)."""
    _marke_neu_pruefen(live, browser, 4)


def test_1256_die_marke_zaehlt_mit_und_beginnt_am_ende_von_vorn(live, browser):
    _ohne_wiki_hinweis(live)
    kontext, seite = _seite_mit_verlauf(browser, live, platz=200)
    try:
        marke = seite.locator("[data-elwosa-chat]").get_by_role("button", name=MARKE)
        seite.wait_for_timeout(1500)
        _nach_oben(seite)
        gelesen = _zuletzt_gelesen(seite)
        _meldung(live, "Erste neue Meldung: die Suche ist fertig.", 1)
        _holen(seite, "Erste neue Meldung")
        eins = seite.evaluate(NACHRICHTEN_NACH, gelesen)
        assert marke.count() == 1 and marke.inner_text().strip() == f"{eins} neu", f"nach der ersten Meldung: {marke.count()} Marke(n), erwartet '{eins} neu'"
        _meldung(live, "Zweite neue Meldung: ein Termin steht an.", 2)
        _meldung(live, "Dritte neue Meldung: eine Nachfrage ist faellig.", 3)
        _holen(seite, "Dritte neue Meldung")
        drei = seite.evaluate(NACHRICHTEN_NACH, gelesen)
        assert drei >= eins + 2, "der Fall ist keiner: die letzten Meldungen stehen nicht unter der ersten"
        assert marke.count() == 1 and marke.inner_text().strip() == f"{drei} neu", f"nach drei Meldungen: erwartet '{drei} neu', steht '{marke.all_inner_texts()}'"
        # wer bis ans Ende liest, hat alles gesehen: die Marke verschwindet, und die naechste Meldung zaehlt wieder von vorn
        _ans_ende(seite)
        assert marke.count() == 0, "am Ende steht noch eine Marke"
        _nach_oben(seite)
        gelesen = _zuletzt_gelesen(seite)
        _meldung(live, "Vierte neue Meldung: das Profil ist vollstaendig.", 4)
        _holen(seite, "Vierte neue Meldung")
        wieder = seite.evaluate(NACHRICHTEN_NACH, gelesen)
        assert wieder < drei, "der Fall ist keiner: die Zahl haette von vorn beginnen muessen"
        assert marke.count() == 1 and marke.inner_text().strip() == f"{wieder} neu", f"nach dem Ende: erwartet '{wieder} neu', steht '{marke.all_inner_texts()}'"
    finally:
        kontext.close()


def test_1256_das_ausblenden_einer_nachricht_macht_keine_marke(live, browser):
    """Wer oben liest und eine Nachricht ausblendet, bekommt beim naechsten Holen eine AELTERE ins Fenster: die Zahl der Nachrichten steigt von neun
    auf zehn, neu ist nichts."""
    for nr in range(2):
        _meldung(live, f"Aeltere Nachricht {nr + 1}: sie wartet ausserhalb des Fensters.", f"alt-{nr}")
    _ohne_wiki_hinweis(live)
    kontext, seite = _seite_mit_verlauf(browser, live, platz=200)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        marke = seite.locator("[data-elwosa-chat]").get_by_role("button", name=MARKE)
        seite.wait_for_timeout(1500)
        _nach_oben(seite)
        liste.locator("[data-elwosa-nachricht]").first.get_by_role("button", name="Diese Nachricht ausblenden").click()
        seite.wait_for_function("() => document.querySelectorAll('[data-elwosa-nachricht]').length === 9", timeout=5000)
        seite.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
        seite.wait_for_function(
            "() => [...document.querySelectorAll('[data-elwosa-nachricht]')].some((e) => e.textContent.includes('Hinweis aus dem Wiki'))", timeout=10000)
        _bilder(seite)
        assert marke.count() == 0, f"die Marke zeigt '{marke.all_inner_texts()}', obwohl nichts neu ist: nur eine aeltere Nachricht rueckte ins Fenster"
    finally:
        kontext.close()


def test_1256_wird_der_bereich_niedriger_bleibt_das_ende_im_bild(live, browser):
    """Der Kopf der Seitenleiste waechst nach dem Laden um eine Zeile und nimmt Elwosa 38 px Hoehe. Wer unten liest, bleibt unten, auch ohne zu scrollen."""
    kontext, seite = _seite_mit_verlauf(browser, live)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        _ans_ende(seite)
        vorher = liste.evaluate("l => l.clientHeight")
        seite.evaluate(KOPF_WAECHST, 38)
        _bilder(seite)
        assert vorher - liste.evaluate("l => l.clientHeight") >= 30, "der Fall ist keiner: der Bereich ist nicht niedriger geworden"
        abstand = seite.evaluate(ABSTAND_ZUM_ENDE)
        assert abstand < 2, f"das Ende liegt {abstand:.0f} px unter dem Bild: die letzte Meldung ist abgeschnitten"
    finally:
        kontext.close()


def test_1256_eine_meldung_nach_sprung_und_hoehenaenderung_bleibt_nicht_verdeckt(live, browser):
    """Eine Meldung kommt, der Bereich springt ans Ende, und noch vor dem Scroll-Ereignis zu diesem Sprung waechst der Kopf. Das Ereignis rechnet
    mit der neuen Hoehe (38 px, mehr als die Toleranz), haelt den Menschen fuer "nicht am Ende", und die NAECHSTE Meldung liegt unter dem Bild."""
    kontext, seite = _seite_mit_verlauf(browser, live)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        # "gelesen" melden loest nach jeder neuen Meldung einen zweiten Aufbau der Liste aus; kommt er vor dem Scroll-Ereignis, springt die Liste dabei
        # noch einmal ans Ende und heilt den Fehler zufaellig. Hier entscheidet allein das Ereignis: die Anfrage wird angehalten.
        seite.route("**/api/elwosa/messages/mark-read", lambda route: route.abort())
        _ans_ende(seite)
        vorher = liste.evaluate("l => l.clientHeight")
        seite.evaluate(KOPF_WAECHST_MIT_DER_MELDUNG, {"px": 38, "text": "Erste Meldung"})
        _meldung(live, "Erste Meldung: die Suche ist fertig.", 1)
        _holen(seite, "Erste Meldung")
        assert vorher - liste.evaluate("l => l.clientHeight") >= 30, "der Fall ist keiner: der Bereich ist nicht niedriger geworden"
        _meldung(live, "Zweite Meldung: ein Termin steht an.", 2)
        _holen(seite, "Zweite Meldung")
        im_bild = seite.evaluate(NACHRICHT_IM_BEREICH, "Zweite Meldung")
        assert im_bild is True, f"die zweite Meldung liegt unter dem Bild (Abstand zum Ende {seite.evaluate(ABSTAND_ZUM_ENDE):.0f} px)"
    finally:
        kontext.close()


def test_1256_wer_oben_liest_wird_bei_hoehenaenderung_und_neuer_meldung_nicht_nach_unten_gezogen(live, browser):
    """Die Gegenseite: das Halten des Endes gilt nur fuer den, der am Ende steht."""
    kontext, seite = _seite_mit_verlauf(browser, live)
    try:
        liste = seite.locator("[data-elwosa-liste]")
        seite.wait_for_timeout(1500)
        _nach_oben(seite)
        seite.evaluate(KOPF_WAECHST, 38)
        _bilder(seite)
        _meldung(live, "Meldung beim Lesen oben: die Suche ist fertig.", 1)
        _holen(seite, "beim Lesen oben")
        assert liste.evaluate("l => l.scrollTop") < 60, "wer oben liest, wird nach unten gezogen"
        assert seite.evaluate(NACHRICHT_IM_BEREICH, "beim Lesen oben") is False, "der Fall ist keiner: die neue Meldung liegt im Bild"
    finally:
        kontext.close()


def test_1256_nach_dem_wiedereinblenden_steht_der_verlauf_am_ende(live, browser):
    """Elwosa ausblenden (Auge) und wieder einblenden: der Bereich ist neu und stand bisher oben, bei den aeltesten Nachrichten, bis zufaellig eine neue
    kam."""
    kontext, seite = _seite_mit_verlauf(browser, live)
    try:
        seite.get_by_role("button", name="Für 30 Minuten ausblenden").click()
        seite.get_by_role("button", name="Elwosa wieder einblenden").click()
        seite.locator("[data-elwosa-liste]").wait_for(state="visible")
        _bilder(seite)
        abstand = seite.evaluate(ABSTAND_ZUM_ENDE)
        assert abstand < 2, f"der Verlauf steht {abstand:.0f} px ueber dem Ende: er zeigt die aeltesten Nachrichten"
    finally:
        kontext.close()
