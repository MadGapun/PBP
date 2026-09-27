"""#1036 im Browser: eine eingetragene 0 km bleibt 0, ein leeres Feld
zeigt die Vorgabe des Servers. Beleg ist die Datenbank."""
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

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "pbp.db")
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


def test_null_km_landet_als_null_in_der_datenbank(browser, server):
    url, db = server
    db.set_search_criteria("max_entfernung", {"festanstellung": 25})
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(f"{url}/#suche", wait_until="domcontentloaded", timeout=30000)
        feld = page.get_by_label("Maximale Entfernung Festanstellung in km")
        feld.wait_for(timeout=15000)
        assert feld.input_value() == "25"
        feld.fill("0")
        for _ in range(80):
            if (db.get_search_criteria().get("max_entfernung") or {}).get("festanstellung") == 0:
                break
            time.sleep(0.1)
        assert db.get_search_criteria()["max_entfernung"]["festanstellung"] == 0
        feld.fill("")
        for _ in range(80):
            if "festanstellung" not in (db.get_search_criteria().get("max_entfernung") or {}):
                break
            time.sleep(0.1)
        assert "festanstellung" not in db.get_search_criteria()["max_entfernung"]
        assert feld.get_attribute("placeholder") == "50"
    finally:
        page.close()
