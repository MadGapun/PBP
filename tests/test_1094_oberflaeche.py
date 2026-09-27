"""#1094 im Browser: das Status-Auswahlfeld setzt dieselben Folgen wie
Claude. Beleg ist die Datenbank nach dem Klick (v1.7.105 MERKE 2)."""
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
from playwright.sync_api import sync_playwright  # noqa: E402

TEXT = "Wir suchen Unterstützung im Einkauf. Aufgaben: Bestellungen, Lieferanten. " * 4


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
    db.save_jobs([{"hash": "st1094", "title": "Sachbearbeitung Einkauf",
                   "company": "Musterbetrieb GmbH", "url": "https://example.com/1094",
                   "source": "manuell", "description": TEXT, "location": "Hamburg"}])
    aid = db.add_application({"title": "Sachbearbeitung Einkauf", "company": "Musterbetrieb GmbH",
                              "job_hash": "st1094", "status": "in_vorbereitung", "applied_at": ""})
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
    yield f"http://127.0.0.1:{port}", db, aid
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


def test_auswahlfeld_beworben_setzt_die_folgen(browser, server):
    url, db, aid = server
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(f"{url}/#bewerbungen", wait_until="networkidle", timeout=30000)
        page.get_by_role("combobox", name="In Vorbereitung", exact=True).first.click()
        page.get_by_text("Beworben", exact=True).last.click()
        page.get_by_text("Erinnerung zum Nachfassen am").wait_for(timeout=10000)
        app = db.get_application(aid)
        assert app["status"] == "beworben"
        assert (app.get("applied_at") or "").strip()
        assert not db.get_job("st1094")["is_active"]
        assert [fu for fu in db.get_pending_follow_ups() if fu["application_id"] == aid]
        # Rueckgaengig nimmt alles zurueck
        page.get_by_role("button", name="Rückgängig").first.click()
        page.get_by_text("Zurückgesetzt auf").wait_for(timeout=10000)
        app = db.get_application(aid)
        assert app["status"] == "in_vorbereitung" and not (app.get("applied_at") or "")
        assert db.get_job("st1094")["is_active"]
        assert not [fu for fu in db.get_pending_follow_ups() if fu["application_id"] == aid]
    finally:
        page.close()
