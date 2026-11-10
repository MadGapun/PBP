"""#1323 im Browser: Einstellungen › Ablehnungsgründe › „Standardgründe wiederherstellen“.

Zwei Schritte: der Knopf zeigt die Vorschau (was zurückkommt, was wieder
eingeschaltet wird) und ändert nichts; erst „Wiederherstellen“ schreibt.
Eigene Gründe bleiben.

Gegen das GEBAUTE Bundle (nach JSX-Aenderungen `pnpm exec vite build`).
Testdaten fiktiv.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _id(db, label):
    return next(r["id"] for r in db.get_dismiss_reasons() if r["label"] == label)


def _aktiv(db, label):
    zeilen = db.connect().execute(
        "SELECT is_active FROM dismiss_reasons WHERE LOWER(label)=?", (label.lower(),)).fetchall()
    return [bool(z[0]) for z in zeilen]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    # Zwei abgeschaltet (seit 1.8.3 heisst Loeschen eines Standardgrunds so), einer ganz weg (bis 1.8.2).
    db.delete_dismiss_reason(_id(db, "zu_junior"))
    db.delete_dismiss_reason(_id(db, "befristet"))
    con = db.connect()
    con.execute("DELETE FROM dismiss_reasons WHERE label='zeitarbeit'")
    con.commit()
    db.add_dismiss_reason("kein_homeoffice")
    db.set_dismiss_reason_active(_id(db, "kein_homeoffice"), False)
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
    yield f"http://127.0.0.1:{port}", db
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


def test_knopf_zeigt_vorschau_und_stellt_nach_bestaetigung_her(server, browser):
    url, db = server
    ctx = browser.new_context(viewport={"width": 1440, "height": 1400})
    page = ctx.new_page()
    try:
        page.goto(f"{url}/#einstellungen", wait_until="domcontentloaded", timeout=30000)
        page.locator("[data-erweitert-schalter]").click()
        page.locator("[data-erweitert-reiter]").get_by_role("button", name="Ablehnungsgründe", exact=True).click()
        knopf = page.locator("[data-standardgruende-wiederherstellen]")
        expect(knopf).to_be_visible(timeout=20000)
        expect(page.locator("[data-grund-schalter='zu_junior']")).to_have_text("Einschalten", timeout=10000)

        knopf.click()
        vorschau = page.locator("[data-standardgruende-vorschau]")
        expect(vorschau).to_be_visible(timeout=10000)
        expect(vorschau.locator("[data-wiederherstellen-neu]")).to_have_count(1, timeout=10000)
        expect(vorschau.locator("[data-wiederherstellen-neu='zeitarbeit']")).to_have_count(1)
        expect(vorschau.locator("[data-wiederherstellen-an]")).to_have_count(2)
        expect(vorschau.locator("[data-wiederherstellen-an='zu_junior']")).to_have_count(1)
        expect(vorschau.locator("[data-wiederherstellen-an='befristet']")).to_have_count(1)
        # die Vorschau hat nichts geschrieben
        assert _aktiv(db, "zu_junior") == [False] and _aktiv(db, "zeitarbeit") == []

        page.locator("[data-standardgruende-bestaetigen]").click()
        expect(vorschau).to_have_count(0, timeout=10000)
        expect(page.locator("[data-grund-schalter='zu_junior']")).to_have_text("Abschalten", timeout=10000)
        expect(page.locator("[data-grund-schalter='befristet']")).to_have_text("Abschalten")
        expect(page.locator("[data-grund-schalter='zeitarbeit']")).to_have_text("Abschalten")
        # der eigene Grund bleibt abgeschaltet
        expect(page.locator("[data-grund-schalter='kein_homeoffice']")).to_have_text("Einschalten")
        assert _aktiv(db, "zu_junior") == [True] and _aktiv(db, "zeitarbeit") == [True]
        assert _aktiv(db, "kein_homeoffice") == [False]
    finally:
        ctx.close()
