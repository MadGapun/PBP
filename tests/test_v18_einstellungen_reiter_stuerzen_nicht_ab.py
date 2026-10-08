"""Praxisprobe 1.8 (05.10.2026): der Reiter „Erweiterungen“ stürzte ab — und kein Test hat es gesehen.

Befund auf einem frischen Windows ohne Texterkennung: Einstellungen › Erweitert › Erweiterungen zeigte „Dieser Bereich ist
abgestürzt“ (`läuft is not defined`). Ursache: der Umlaut-Austausch aus #1087 G66 (50f071b3) hatte in `SettingsPage.jsx` aus dem
Variablennamen `laeuft` an EINER Stelle `läuft` gemacht. Der Zweig wird nur erreicht, wenn eine Komponente NICHT installiert ist —
also bei jeder frischen Installation. Auf dem Entwicklungsrechner ist die Texterkennung installiert, die Demos zeigten „Extern
gefunden“ und gingen nie dorthin. Gebaut hat es trotzdem: Vite meldet keine unbekannten Namen.

Zweiter Befund aus demselben Absturz: die Absturz-Grenze galt je SEITE. Nach dem Absturz eines Reiters zeigten auch System, Logs und
Gefahrenzone nur noch die Fehlerkarte, und die Unterpunkte der Seitenleiste taten nichts mehr (die Seite, die ihr Ereignis hört, war
ausgehängt) — bis man neu lud. Jetzt hat jeder Reiter seine eigene Grenze.

Dieser Test öffnet JEDEN Reiter der Einstellungen im echten Browser gegen die gebaute Oberfläche und verlangt: kein Seitenfehler,
kein Absturz-Fenster. Die Komponenten stehen dabei fest auf „nicht installiert“ — unabhängig davon, was auf dem Rechner liegt, der den
Test ausführt.
"""
import os
import re
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # ohne Browser-Paket entfallen nur die Browser-Tests, die Pruefer-Tests laufen weiter
    PlaywrightError = Exception
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
ABSTURZ = "Dieser Bereich ist abgestürzt"


def _reiter() -> list:
    quelle = (ROOT / "frontend" / "src" / "lib" / "einstellungenReiter.js").read_text(encoding="utf-8-sig")
    return re.findall(r'\{\s*id:\s*"([a-z_]+)"', quelle)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _reiter_waehlen(page, reiter: str) -> None:
    # derselbe Weg wie die Unterpunkte in der Seitenleiste: ein Ereignis wählt den Reiter
    page.evaluate("id => document.dispatchEvent(new CustomEvent('settings-nav', {detail: {tab: id}}))", reiter)
    page.wait_for_timeout(400)


@pytest.fixture
def server(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.services import components
    import bewerbungs_assistent.dashboard as dash

    # Keine Komponente ist installiert — egal, was auf dem Rechner liegt, der den Test ausführt
    monkeypatch.setattr(components, "find_component_binary", lambda db, name: None)
    monkeypatch.setattr(components, "_playwright_chromium_dir", lambda: None)

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
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


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


def test_1170_die_reiterliste_wird_gelesen():
    ids = _reiter()
    assert len(ids) >= 15 and "erweiterungen" in ids and "updates" in ids and "speicher" in ids, ids


def test_1170_jeder_einstellungsreiter_zeichnet_ohne_absturz(server, browser):
    page = browser.new_page(viewport={"width": 1400, "height": 950})
    fehler = []
    page.on("pageerror", lambda e: fehler.append(str(e)[:200]))
    page.goto(server + "/#einstellungen")
    page.wait_for_load_state("networkidle")
    abgestuerzt = []
    for reiter in _reiter():
        _reiter_waehlen(page, reiter)
        if page.get_by_text(ABSTURZ).count():
            abgestuerzt.append(reiter)
    page.close()
    assert not fehler, f"Seitenfehler: {fehler}"
    assert not abgestuerzt, f"abgestürzt: {abgestuerzt}"


def test_1170_erweiterungen_ohne_installierte_komponente_zeigt_nicht_installiert(server, browser):
    """DER Fall aus der Praxisprobe: nichts installiert."""
    page = browser.new_page(viewport={"width": 1400, "height": 950})
    fehler = []
    page.on("pageerror", lambda e: fehler.append(str(e)[:200]))
    page.goto(server + "/#einstellungen")
    page.wait_for_load_state("networkidle")
    _reiter_waehlen(page, "erweiterungen")
    page.wait_for_selector("text=Optionale Komponenten", timeout=15000)
    assert page.get_by_text("Nicht installiert").count() >= 1, "die Karte muss sagen, dass die Komponente fehlt"
    assert page.get_by_text(ABSTURZ).count() == 0
    # und die Installation lässt sich anbieten (der Knopf steht nur bei einer fehlenden Komponente da)
    assert page.get_by_role("button", name=re.compile("installieren", re.I)).count() >= 1
    page.close()
    assert not fehler, f"Seitenfehler: {fehler}"


def test_1170_ein_absturz_in_einem_reiter_legt_die_anderen_nicht_lahm(server, browser):
    """Der Fehler selbst ist behoben — hier wird ein ANDERER absichtlich herbeigeführt (kaputte Antwort der Komponenten-Liste).

    Verlangt: die Fehlerkarte erscheint NUR im betroffenen Reiter; die Reiterleiste bleibt; ein Wechsel (Seitenleisten-Ereignis ODER
    Klick auf einen Reiter) zeigt den anderen Reiter wieder ganz normal.
    """
    page = browser.new_page(viewport={"width": 1400, "height": 950})
    page.route("**/api/components", lambda route: route.fulfill(
        status=200, content_type="application/json", body='{"komponenten": "kaputt"}'))
    page.goto(server + "/#einstellungen")
    page.wait_for_load_state("networkidle")

    _reiter_waehlen(page, "erweiterungen")
    page.wait_for_selector(f"text={ABSTURZ}", timeout=15000)
    assert page.locator("[data-settings-reiter]").count() == 1, "die Reiterleiste muss stehen bleiben"

    # Weg 1: der Unterpunkt in der Seitenleiste (er schickt das Ereignis, das die Einstellungsseite hört)
    page.get_by_label("Hauptnavigation").get_by_role("button", name="Erscheinungsbild", exact=True).click()
    page.wait_for_selector("text=Was auf dem Dashboard erscheint.", timeout=15000)
    assert page.get_by_text(ABSTURZ).count() == 0, "der Absturz darf nicht an den anderen Reitern haengen bleiben"

    # und zurück: der kaputte Reiter ist weiter kaputt (ehrlich), aber wieder nur er
    _reiter_waehlen(page, "erweiterungen")
    page.wait_for_selector(f"text={ABSTURZ}", timeout=15000)

    # Weg 2: der Klick auf einen Reiter der Leiste
    page.locator("[data-settings-reiter]").get_by_role("button", name="Datenschutz", exact=True).click()
    page.wait_for_selector("text=Wo liegen deine Daten und was wird wohin gesendet.", timeout=15000)
    assert page.get_by_text(ABSTURZ).count() == 0
    page.close()


def _seiten() -> list:
    quelle = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8-sig")
    block = quelle[quelle.index("const TAB_CONFIG = ["):]
    block = block[:block.index("\n];")]
    return re.findall(r'\{\s*id:\s*"([a-z_]+)"', block)


def test_1170_die_seitenliste_wird_gelesen():
    ids = _seiten()
    assert len(ids) == 11 and {"dashboard", "stellen", "einstellungen"} <= set(ids), ids


def test_1170_jede_seite_zeichnet_mit_frischer_datenbank_ohne_absturz(server, browser):
    """Dieselbe Lücke wie bei den Reitern, eine Ebene höher: eine frische Installation hat nichts — keine Stellen, keine Bewerbungen,
    keine Kontakte. Zweige, die nur dann laufen, sah vorher kein Test."""
    fehler = []
    abgestuerzt = []
    for seite in _seiten():
        # je Seite ein frisches Fenster, wie beim ersten Oeffnen; "networkidle" gibt es nicht — manche Seiten fragen laufend nach
        page = browser.new_page(viewport={"width": 1400, "height": 950})
        page.on("pageerror", lambda e, s=seite: fehler.append(f"{s}: {str(e)[:200]}"))
        page.goto(f"{server}/#{seite}", wait_until="load", timeout=30000)
        page.wait_for_timeout(1500)
        if page.get_by_text(ABSTURZ).count():
            abgestuerzt.append(seite)
        page.close()
    assert not fehler, f"Seitenfehler: {fehler}"
    assert not abgestuerzt, f"abgestürzt: {abgestuerzt}"


def _pruefer():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ui_texte_pruefen_1170", ROOT / "scripts" / "ui_texte_pruefen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


PROBE = '''export default function Probe({ a }) {
  const laeuft = !a;
  return (
    <div>
      {a ? (
        <Badge tone="success">Installiert</Badge>
      ) : laeuft ? (
        <Badge tone="amber">Installation läuft</Badge>
      ) : (
        <Badge tone="neutral">Nicht installiert</Badge>
      )}
      <p>Das ist eine Uebung fuer Staerken</p>
    </div>
  );
}
'''


def test_1170_der_textpruefer_haelt_code_zwischen_tags_nicht_fuer_text(tmp_path):
    """URSACHE des Absturzes: der Prüfer las `) : laeuft ? (` zwischen zwei Tags als Text und verlangte „läuft“. Die Umstellung
    machte daraus an dieser einen Stelle einen Namen, den es nicht gab."""
    datei = tmp_path / "Probe.jsx"
    datei.write_text(PROBE, encoding="utf-8")
    p = _pruefer()
    gelesen = [t for _, t in p.texte(datei)]
    gefunden = [w for t in gelesen for w in p.umlaut_funde(t)]
    assert "laeuft" not in gefunden, f"Code als Text gelesen: {gelesen}"
    # die Schärfe bleibt: echte Umschrift in einem echten Textknoten wird weiter gefunden
    assert gefunden == ["Uebung", "fuer", "Staerken"], gefunden


def test_1170_das_programm_nutzt_den_namen_einheitlich():
    """Der Name der Variablen steht überall gleich da — nie wieder an einer Stelle anders (Umlaut-Austausch in einem Namen)."""
    quelle = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert "const laeuft =" in quelle and ") : laeuft ? (" in quelle
    assert not re.search(r"(?<![\"'`>\w])läuft(?![\w])\s*\?", quelle), "ein Name mit Umlaut vor einem '?': Verzweigung im Code"
