"""Welle 4 aus #1087 im gerenderten Dashboard (G62, G72).

* G62: die Karte traegt EINE Kernaussage, einen Grund und den
  Rahmen-Daumen; Kennung und Quelle stehen im Menue "Für Claude
  kopieren"; "Genauer prüfen" bietet zwei Wege; die Filterleiste zeigt
  Suche plus "Filter (n)", keine Seitengroesse.
* G72: verweigert der Browser die Zwischenablage, steht der Text in einem
  Fenster zum Selbstkopieren — keine englische Browsermeldung.
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
from playwright.sync_api import sync_playwright  # noqa: E402

TEXT = ("Wir suchen eine Sachbearbeitung im Einkauf. Aufgaben: Disposition, "
        "Bestellabwicklung mit SAP MM, Lieferantenkommunikation. "
        "Anforderungen: kaufmaennische Ausbildung, Englisch. ") * 3


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    db.set_search_criteria("keywords_muss", ["einkauf", "sap mm"])
    db.save_jobs([{"hash": "g62ui", "title": "Sachbearbeitung Einkauf",
                   "company": "Musterbetrieb GmbH", "url": "https://example.com/g62ui",
                   "source": "manuell", "description": TEXT, "remote_level": "hybrid",
                   "location": "Hamburg", "score": 4}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE '%g62ui'").fetchone()["hash"]
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
    yield f"http://127.0.0.1:{port}", db, voll
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


def _stellen(browser, url, clipboard_kaputt=False):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    if clipboard_kaputt:
        page.add_init_script(
            "Object.defineProperty(navigator, 'clipboard', {value: {writeText: () => "
            "Promise.reject(new DOMException(\"Failed to execute 'writeText' on 'Clipboard'\"))}});")
    page.goto(f"{url}/#stellen", wait_until="load", timeout=30000)
    page.locator("[data-kernaussage]").first.wait_for(timeout=15000)
    return page


def test_g62_karte_eine_kernaussage_und_ein_menue(browser, server):
    url, _db, voll = server
    page = _stellen(browser, url)
    try:
        karte = page.locator("[data-stellenkarte]").first
        text = karte.inner_text()
        assert page.locator("[data-kernaussage]").count() == 1
        # Keine Kennung und kein Quellenschluessel als Abzeichen.
        assert voll.split(":")[-1][:8] not in text
        assert "manuell" not in text
        assert "Ungeprüft:" not in text and "Fachlich:" not in text
        assert "Fit-Analyse" not in text
        # Fakten als Zeile, nicht als Abzeichen.
        assert "Hybrid" in page.locator("[data-karten-fakten]").first.inner_text()
        # Das Menue traegt Kennung und Quelle.
        page.locator("[data-fuer-claude]").first.click()
        menue = page.get_by_role("menu").first
        assert "Quelle: manuell" in menue.inner_text()
        assert menue.get_by_role("menuitem", name="Kennung kopieren").count() == 1
    finally:
        page.close()


def _oben_liegt(page, locator, frist=10.0):
    """Liegt das Element an seiner Mitte wirklich oben? (#1113)

    `inner_text()` und Rollen-Suchen finden auch verdeckte Elemente — so
    rutschte ein Menue unter der naechsten Karte durch. Gewartet wird auf
    den Zustand, nicht auf Zeit: waehrend die Liste noch rendert, liegt
    kurz etwas anderes an der Stelle."""
    locator.scroll_into_view_if_needed()
    ende = time.monotonic() + frist
    while True:
        if _oben_jetzt(locator) or time.monotonic() > ende:
            return _oben_jetzt(locator)
        page.wait_for_timeout(100)


def _oben_jetzt(locator):
    return locator.evaluate(
        """(el) => {
            const r = el.getBoundingClientRect();
            const oben = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            return !!oben && (oben === el || el.contains(oben));
        }""")


def test_1113_zwei_direkte_knoepfe(browser, server):
    url, _db, _voll = server
    page = _stellen(browser, url)
    try:
        assert page.locator("[data-genauer-pruefen]").count() == 0
        lokal = page.locator("[data-punkte-ansehen]").first
        claude = page.locator("[data-mit-claude-bewerten]").first
        assert lokal.inner_text().strip() == "Punkte ansehen"
        assert claude.inner_text().strip() == "Bewerten mit Claude"
        assert _oben_liegt(page, lokal) and _oben_liegt(page, claude)
        lokal.click()
        page.get_by_role("heading", name="Woher die Punkte kommen", exact=False).wait_for(timeout=15000)
        page.get_by_role("button", name="Bewerten mit Claude").last.wait_for(timeout=15000)
    finally:
        page.close()


def test_1113_fuer_claude_menue_liegt_ueber_der_naechsten_karte(browser, server):
    url, db, _voll = server
    # Eine Folgekarte, die das Menue ueberdecken koennte.
    db.save_jobs([{"hash": "g62ui2", "title": "Sachbearbeitung Einkauf Zwei",
                   "company": "Musterbetrieb GmbH", "url": "https://example.com/g62ui2",
                   "source": "manuell", "description": TEXT, "remote_level": "hybrid",
                   "location": "Hamburg", "score": 3}])
    page = _stellen(browser, url)
    try:
        page.locator("[data-stellenkarte]").nth(1).wait_for(timeout=15000)
        # Der Risikofall: eine kurze Karte, deren Menue in die Folgekarte
        # ragt. Bei normaler Hoehe endet das Menue in der eigenen Karte,
        # und der Test waere ohne den Fix gruen geblieben (Gegenprobe).
        # Als Stylesheet, damit ein Neuzeichnen der Liste es nicht verliert.
        karte = page.locator("[data-fuer-claude]").first.evaluate(
            """(el) => {
                const karte = el.closest('[data-stellenkarte]');
                return {id: karte.id, hoehe: Math.ceil(
                    el.getBoundingClientRect().bottom - karte.getBoundingClientRect().top) + 8};
            }""")
        assert karte["id"], "Karte ohne id"
        page.add_style_tag(content=(
            '[id="%s"] { height: %dpx !important; min-height: 0 !important;'
            ' overflow: visible !important; }' % (karte["id"], karte["hoehe"])))
        page.wait_for_function(
            "(k) => { const e = document.getElementById(k.id); return !!e && e.getBoundingClientRect().height <= k.hoehe + 1; }",
            arg=karte)
        page.locator("[data-fuer-claude]").first.click()
        menue = page.get_by_role("menu").first
        menue.wait_for(timeout=5000)
        # Vorbedingung: das Menue ueberschneidet die Folgekarte tatsaechlich.
        lage = page.evaluate("""() => {
            const m = document.querySelector('[role=menu]').getBoundingClientRect();
            const k = document.querySelectorAll('[data-stellenkarte]')[1].getBoundingClientRect();
            return m.left < k.right && k.left < m.right && m.top < k.bottom && k.top < m.bottom;
        }""")
        assert lage, "Aufbau falsch: das Menue reicht nicht in die Folgekarte"
        for eintrag in menue.get_by_role("menuitem").all():
            assert _oben_liegt(page, eintrag), eintrag.inner_text()
        page.keyboard.press("Escape")
        menue.wait_for(state="detached", timeout=5000)
        page.locator("[data-fuer-claude]").first.click()
        page.get_by_role("menu").first.wait_for(timeout=5000)
        page.locator("[data-filter-knopf]").click()
        page.get_by_role("menu").first.wait_for(state="detached", timeout=5000)
    finally:
        page.close()


def test_g62_filterleiste_suche_plus_filter_n(browser, server):
    url, _db, _voll = server
    page = _stellen(browser, url)
    try:
        knopf = page.locator("[data-filter-knopf]")
        # Vorgaben wirken (beworbene, Rahmen, Schwelle) und stehen da.
        assert knopf.inner_text().strip().startswith("Filter (")
        assert "(0)" not in knopf.inner_text()
        assert "ausgeblendet" in page.locator("[data-filter-zusammenfassung]").inner_text()
        assert page.locator("[data-filter-feld]").count() == 0
        assert "pro Seite" not in page.inner_text("body")
        knopf.click()
        page.locator("[data-filter-feld]").wait_for(timeout=5000)
        assert "Rahmen passt nicht ausblenden" in page.locator("[data-filter-feld]").inner_text()
        assert page.get_by_role("button", name="Aussortiert").count() >= 1
    finally:
        page.close()


def test_g72_fehlschlag_zeigt_text_zum_selbstkopieren(browser, server):
    url, _db, _voll = server
    page = _stellen(browser, url, clipboard_kaputt=True)
    try:
        page.locator("[data-mit-claude-bewerten]").first.click()
        feld = page.locator("[data-manuell-kopieren]")
        feld.wait_for(timeout=10000)
        assert "stelle_urteil_speichern" in feld.input_value()  # H29: neuer Name
        body = page.inner_text("body")
        assert "Kopieren hat nicht geklappt" in body
        assert "Failed to execute" not in body
    finally:
        page.close()
