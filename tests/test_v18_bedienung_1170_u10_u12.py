"""#1170 U10 bis U12: Kopierknöpfe, einklappbare Erklärtexte, der Weg zur Texterkennung beim ersten Scan.

U10 Kopierknöpfe: (a) die Hilfe nennt den Knopf, wie er heißt („Mit Claude“, nicht „Kopieren“); (b) Anleitung und Prompt sind
dasselbe und stehen so da; (c) „Gespräch mit Claude starten“ kopiert den SATZ, den die Hilfe nennt — die lange Anleitung mit
Werkzeugnamen nur auf Wunsch; (d) die neuen 1.8-Seiten (Updates, Speicher & Downloads, Firmen, Quellenliste) haben je einen
„… erklären mit Claude“-Knopf.

U11 Erklärtexte: die langen Erklärabsätze lassen sich einklappen (Wahl je Text gemerkt), und ein Schalter unter Erscheinungsbild
klappt alle ein oder aus.

U12 Texterkennung: ein Scan ohne Text meldet beim Hochladen den Weg (Einstellungen › Erweiterungen) — vorher las die Seite das
Feld `ocr` der Antwort nie.

Die reine Rechnung prüfen `lib/erklaertexte.test.mjs` und `lib/uploadHinweis.test.mjs` (CI).
"""
from __future__ import annotations

import os
import re
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend" / "src"


def _lesen(*teile) -> str:
    return FRONTEND.joinpath(*teile).read_text(encoding="utf-8-sig")


# ══ U10: Quelltext ═════════════════════════════════════════════════════════════════════════════════════════

def test_die_hilfe_nennt_den_knopf_wie_er_heisst():
    app = _lesen("App.jsx")
    assert "Der Knopf „Mit Claude“" in app
    assert "Klick auf „Kopieren" not in app, "der Knopf heisst nicht „Kopieren“"
    assert "Prompts — fertige Anleitungen für Claude" in app, "Prompt und Anleitung sind dasselbe und stehen so da"
    schnell = _lesen("components", "SchnellzugriffKarten.jsx")
    assert "kopiert die Anleitung in die Zwischenablage" in schnell and "fertige Anleitungen" in schnell


def test_gespraech_starten_kopiert_den_satz_und_die_anleitung_nur_auf_wunsch():
    dash = _lesen("pages", "DashboardPage.jsx")
    schritt = dash[dash.index("Gespräch mit Claude starten") - 700: dash.index("Ausführliche Anleitung kopieren")]
    assert "copyPrompt(STARTSATZ" in schritt, "der Knopf kopiert den Satz"
    assert 'copyPrompt("/ersterfassung")' in dash, "die ausfuehrliche Anleitung bleibt erreichbar"
    assert dash.index("copyPrompt(STARTSATZ") < dash.index('copyPrompt("/ersterfassung")')
    onb = _lesen("components", "ProfileOnboarding.jsx")
    assert re.search(r"onClick=\{copyStartsatz\}", onb)
    kopieren = onb[onb.index("async function copyStartsatz"):]
    kopieren = kopieren[:kopieren.index("\n  }\n")]
    assert "copyPrompt(STARTSATZ" in kopieren and "CONVERSATION_COMMAND" not in kopieren
    lang = onb[onb.index("async function copyConversationCommand"):]
    assert "copyPrompt(CONVERSATION_COMMAND)" in lang[:lang.index("\n  }\n")]


@pytest.mark.parametrize("datei,titel", [
    (("components", "UpdatesTab.jsx"), "Updates erklären"),
    (("components", "SpeicherTab.jsx"), "Speicher erklären"),
    (("components", "FirmenAnsicht.jsx"), "Firmen erklären"),
    (("pages", "SettingsPage.jsx"), "Quellen erklären"),
])
def test_jede_neue_seite_hat_einen_mit_claude_knopf(datei, titel):
    text = _lesen(*datei)
    assert f"<MitClaude>{titel}</MitClaude>" in text
    assert "data-mit-claude-seite" in text
    # der Auftrag nennt das Werkzeug, mit dem Claude nachsieht, und aendert nichts ohne den Menschen
    i = text.index(f"<MitClaude>{titel}</MitClaude>")
    umfeld = text[max(0, i - 900): i]
    assert "copyPrompt(\"" in umfeld and re.search(r"(?:ohne meine|nichts ohne)", umfeld), umfeld[-400:]


# ══ U11/U12: im Browser ════════════════════════════════════════════════════════════════════════════════════

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _starten(db):
    import bewerbungs_assistent.dashboard as dash
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
    return srv, t, f"http://127.0.0.1:{port}"


def _beenden(srv, t):
    import bewerbungs_assistent.dashboard as dash
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bedienung1170")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    srv, t, url = _starten(db)
    yield {"url": url, "db": db, "tmp": tmp}
    _beenden(srv, t)
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def ohne_profil(tmp_path):
    """Eine eigene, leere Installation: der Willkommensbildschirm mit dem Erklaerkasten."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database

    db = Database(db_path=tmp_path / "leer.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    srv, t, url = _starten(db)
    yield {"url": url}
    _beenden(srv, t)
    db.close()


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


def _seite(browser, url, ziel, breite=1440):
    ctx = browser.new_context(viewport={"width": breite, "height": 1000})
    page = ctx.new_page()
    page.goto(f"{url}/#{ziel}", wait_until="load", timeout=30000)
    return ctx, page


def test_der_erklaerkasten_der_willkommensseite_klappt_ein_und_bleibt(browser, ohne_profil):
    ctx, page = _seite(browser, ohne_profil["url"], "dashboard")
    try:
        kasten = page.locator("[data-erklaerkasten]")
        kasten.wait_for(timeout=20000)
        assert kasten.get_attribute("data-offen") == "ja", "Vorgabe: aufgeklappt, wie bisher"
        assert "Knöpfe mit „… mit Claude“" in kasten.inner_text()
        kasten.get_by_role("button", name="So arbeiten Dashboard und Claude zusammen").click()
        assert _warte(lambda: kasten.get_attribute("data-offen") == "nein")
        assert "Knöpfe mit" not in kasten.inner_text()
        # die Wahl bleibt nach dem Neuladen
        page.reload(wait_until="load")
        kasten = page.locator("[data-erklaerkasten]")
        kasten.wait_for(timeout=20000)
        assert kasten.get_attribute("data-offen") == "nein"
        assert page.evaluate("window.localStorage.getItem('pbp-erklaerung-dashboard-zusammenarbeit')") == "zu"
    finally:
        ctx.close()


def test_der_schalter_klappt_alle_erklaertexte_ein_und_setzt_die_einzelwahlen_zurueck(browser, umgebung):
    ctx, page = _seite(browser, umgebung["url"], "einstellungen")
    try:
        page.locator("[data-settings-reiter]").wait_for(timeout=20000)
        # ein Erklaertext in Speicher & Downloads, einzeln eingeklappt
        page.locator("[data-erweitert-schalter]").click()
        page.locator("[data-erweitert-reiter]").get_by_role("button", name="Speicher & Downloads", exact=True).click()
        text = page.locator("[data-erklaertext='speicher-einleitung']")
        text.wait_for(timeout=20000)
        assert text.get_attribute("data-offen") == "ja"
        assert "Gelöscht wird nie ohne deine Bestätigung" in text.inner_text()
        text.get_by_role("button", name="Wird hier etwas gelöscht?").click()
        assert _warte(lambda: text.get_attribute("data-offen") == "nein")

        # der Schalter unter Erscheinungsbild: aus -> alles zu, Einzelwahlen weg; an -> alles auf
        page.locator("[data-settings-reiter]").get_by_role("button", name="Erscheinungsbild", exact=True).click()
        haken = page.locator("[data-erklaertexte-haken]")
        haken.wait_for(timeout=10000)
        assert haken.is_checked(), "Vorgabe: an"
        haken.click()
        assert _warte(lambda: page.evaluate("window.localStorage.getItem('pbp-erklaertexte')") == "0")
        assert page.evaluate("window.localStorage.getItem('pbp-erklaerung-speicher-einleitung')") is None, \
            "eine ausdrueckliche Wahl fuer alle gilt fuer alle"
        page.locator("[data-erweitert-reiter]").get_by_role("button", name="Speicher & Downloads", exact=True).click()
        text = page.locator("[data-erklaertext='speicher-einleitung']")
        text.wait_for(timeout=20000)
        assert text.get_attribute("data-offen") == "nein"
        # ein Klick auf die Ueberschrift oeffnet genau diesen Text und merkt es
        text.get_by_role("button", name="Wird hier etwas gelöscht?").click()
        assert _warte(lambda: text.get_attribute("data-offen") == "ja")
        assert page.evaluate("window.localStorage.getItem('pbp-erklaerung-speicher-einleitung')") == "auf"
        # zurueck auf an
        page.locator("[data-settings-reiter]").get_by_role("button", name="Erscheinungsbild", exact=True).click()
        page.locator("[data-erklaertexte-haken]").click()
        assert _warte(lambda: page.evaluate("window.localStorage.getItem('pbp-erklaertexte')") == "1")
    finally:
        ctx.close()


def _leeres_pdf(pfad: Path) -> None:
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=300, height=300)
    with open(pfad, "wb") as f:
        w.write(f)


def test_ein_scan_ohne_text_nennt_den_weg_zur_texterkennung(browser, umgebung, monkeypatch):
    """Der Server erkennt den Scan (Feld `ocr: erforderlich`); die Seite las das Feld nie."""
    from bewerbungs_assistent.services import ocr_service
    monkeypatch.setattr(ocr_service, "ocr_pdf", lambda db, pfad: {
        "status": "komponente_fehlt", "angebot": {"komponente": "tesseract", "name": "Texterkennung (Tesseract)"}})
    pdf = umgebung["tmp"] / "Zeugnis Scan 2019.pdf"
    _leeres_pdf(pdf)
    ctx, page = _seite(browser, umgebung["url"], "dokumente")
    try:
        page.locator("#page-dokumente").wait_for(timeout=20000)
        # Die Seite zeichnet sich einmal neu, sobald die erste Antwort da ist; ein Hochladen im selben Atemzug trifft ein
        # Eingabefeld, das gleich ersetzt wird. Der Mensch wartet darauf nicht - der Test tut es und versucht es erneut.
        page.wait_for_load_state("networkidle")
        hochgeladen = False
        for _ in range(4):
            try:
                with page.expect_response(lambda r: "/api/documents/upload" in r.url, timeout=6000):
                    page.locator("input[type='file']").first.set_input_files(str(pdf))
                hochgeladen = True
                break
            except PlaywrightError:
                page.wait_for_timeout(500)
        assert hochgeladen, "der Upload wurde nie abgeschickt"
        hinweis = page.get_by_text("ist ein Scan ohne Text")
        hinweis.first.wait_for(timeout=15000)
        text = " ".join(hinweis.first.inner_text().split())
        assert "Zeugnis Scan 2019.pdf" in text and "Einstellungen › Erweiterungen" in text
        page.get_by_role("button", name="Texterkennung einrichten").click()
        page.locator("[data-settings-reiter]").wait_for(timeout=20000)
        reiter = page.locator("[data-erweitert-reiter]").get_by_role("button", name="Erweiterungen", exact=True)
        reiter.wait_for(timeout=10000)
        assert reiter.get_attribute("aria-pressed") == "true"
    finally:
        ctx.close()
