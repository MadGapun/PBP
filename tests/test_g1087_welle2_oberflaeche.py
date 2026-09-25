"""Welle 2 aus #1087 im gerenderten Dashboard (C96, C97).

Belegt am Bildschirm, nicht per Grep: dieselbe Stelle zeigt auf der
Karte, im Dashboard, im Fit-Dialog und in der Bewerbungs-Timeline
denselben Text "x von y Punkten", und die Faktoren im Dialog addieren
sich zu genau dieser Zahl.
"""
import os
import re
import socket
import threading
import time
import urllib.request

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TEXT = ("Wir suchen Unterstuetzung im Einkauf mit SAP MM und Disposition. "
        "Lieferantenmanagement, Verhandlung mit Lieferanten, Englisch. " * 6)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash
    from bewerbungs_assistent.job_scraper import fit_analyse
    from bewerbungs_assistent.services import scoring_kriterien

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    db.set_search_criteria("keywords_muss", ["einkauf", "sap mm", "disposition"])
    db.set_search_criteria("keywords_plus", ["englisch", "verhandlung"])
    db.save_jobs([{"hash": "c96ui", "title": "Sachbearbeitung Einkauf",
                   "company": "Musterbetrieb GmbH", "url": "https://example.com/c96ui",
                   "source": "manuell", "description": TEXT, "remote_level": "remote",
                   "location": "Hamburg", "score": 0}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE '%c96ui'").fetchone()["hash"]
    frisch = fit_analyse(db.get_job(voll), scoring_kriterien.fuer_scoring(db))["total_score"]
    db.update_job(voll, {"score": frisch})
    db.set_scoring_config("keyword", "verhandlung", 2)
    db.set_scoring_config("remote", "remote", 5)

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


PUNKTE = re.compile(r"(-?\d+(?:,\d)?) (?:von (\d+(?:,\d)?) )?Punkte?n?")


def _seite(browser, url, tab):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(f"{url}/#{tab}", wait_until="load", timeout=30000)
    page.wait_for_timeout(2000)
    return page


def test_c96_karte_und_dialog_zeigen_dieselbe_zahl(browser, server):
    url, _db, _voll = server
    page = _seite(browser, url, "stellen")
    try:
        karte = page.get_by_title("Punkte von Hand setzen").first.inner_text().strip()
        assert PUNKTE.search(karte), karte
        page.get_by_role("button", name="Fit-Analyse").first.click()
        dialog = page.locator("[data-punkte-dialog]").first
        dialog.wait_for(timeout=10000)
        assert dialog.inner_text().strip() == karte
        # Die Faktoren addieren sich zur Zahl.
        zahl = float(PUNKTE.search(karte).group(1).replace(",", "."))
        werte = []
        for zeile in page.locator("[data-faktoren-fach] > div").all():
            teil = zeile.locator("span").last.inner_text().strip().replace(",", ".")
            werte.append(float(teil))
        assert werte and abs(sum(werte) - zahl) < 0.05, (werte, zahl)
        text = page.inner_text("body")
        assert "Gesamtscore" not in text
        assert "Zählen nicht in die Punkte" in text
    finally:
        page.close()


def test_c96_dashboard_und_timeline_zeigen_dieselbe_zahl(browser, server):
    url, db, voll = server
    page = _seite(browser, url, "stellen")
    karte = page.get_by_title("Punkte von Hand setzen").first.inner_text().strip()
    page.close()

    page = _seite(browser, url, "dashboard")
    try:
        # Auf den Zustand warten, nicht auf eine Dauer: unter Last stand
        # nach zwei Sekunden noch der Ladezustand da.
        page.get_by_text(karte).first.wait_for(timeout=20000)
        assert karte in page.inner_text("body"), "Dashboard nennt eine andere Zahl"
    finally:
        page.close()

    # Mit einer Bewerbung greift der Regler "Beworben-Bonus" — die Zahl
    # aendert sich also zu Recht. Verglichen wird deshalb Timeline gegen
    # dieselbe Liste NACH dem Anlegen, nicht gegen die Karte von vorher.
    db.add_application({"title": "Sachbearbeitung Einkauf", "company": "Musterbetrieb GmbH",
                        "status": "beworben", "job_hash": voll})
    page = _seite(browser, url, "bewerbungen")
    try:
        js = page.request.get(f"{url}/api/jobs?active=true").json()
        js = js["jobs"] if isinstance(js, dict) else js
        erwartet = _text(js[0]["punkte"], js[0].get("punkte_max"))
        page.get_by_text("Sachbearbeitung Einkauf").first.click()
        page.wait_for_selector("text=Timeline - Sachbearbeitung Einkauf", timeout=10000)
        assert erwartet in page.inner_text("body"), (erwartet, "Timeline nennt eine andere Zahl")
    finally:
        page.close()


def _text(punkte, maximum):
    """Wie lib/score.js punkteText formatiert."""
    def zahl(x):
        x = round(float(x), 1)
        return (f"{x:g}").replace(".", ",")
    p = round(float(punkte), 1)
    if maximum and 0 <= p <= float(maximum):
        return f"{zahl(p)} von {zahl(maximum)} Punkten"
    return "1 Punkt" if p == 1 else f"{zahl(p)} Punkte"
