"""#798: Die Statistik-Seite zeigt dieselben Zahlen wie der Datenkern.

Gegen das GEBAUTE Bundle. Testdaten fiktiv, Datenbank isoliert.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.parse
import urllib.request

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402


def _frei() -> int:
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
    c = db.connect()
    for tag, status, g in (("2026-11-03", "beworben", 1), ("2026-11-04", "abgelehnt", 0),
                           ("2026-09-02", "beworben", 0)):
        aid = db.add_application({"title": "Planer", "company": "Musterfirma GmbH", "status": status,
                                  "applied_at": tag, "source": "stepstone"})
        c.execute("UPDATE applications SET status=?, applied_at=?, has_reached_interview=? WHERE id=?",
                  (status, tag, g, aid))
    c.commit()
    dash._db = db
    port = _frei()
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
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def test_zeitraum_gilt_fuer_uebersicht_und_alle_dokumente(server, browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1400})
    page = ctx.new_page()
    try:
        page.goto(f"{server}/#statistiken", wait_until="domcontentloaded", timeout=30000)
        kern = page.locator("[data-statistik-kern]")
        expect(kern).to_contain_text("gesamter Verlauf", timeout=20000)
        kachel = kern.locator('[data-kachel="Bewerbungen"]')
        expect(kachel).to_contain_text("3")
        for abschnitt in ("Wie steht es?", "Was steht an?", "Was funktioniert?", "Meine Suche"):
            expect(kern.get_by_role("heading", name=abschnitt, exact=True)).to_be_visible()

        page.get_by_label("Zeitraum von").fill("01.11.2026")
        page.get_by_label("Zeitraum bis").fill("30.11.2026")
        expect(kern).to_contain_text("01.11.2026 bis 30.11.2026", timeout=10000)
        expect(kachel).to_contain_text("2")
        expect(kern).to_contain_text("Die Stellensuche steht nur")

        for name, pfad in (("Nachweis", "/api/bericht/nachweis"), ("Auswertung", "/api/bericht/auswertung")):
            href = page.get_by_role("link", name=name, exact=True).get_attribute("href")
            teile = urllib.parse.urlparse(href)
            assert teile.path == pfad
            q = urllib.parse.parse_qs(teile.query)
            assert q["from"] == ["2026-11-01"] and q["to"] == ["2026-11-30"]
        roh = page.get_by_role("link", name="Rohdaten", exact=True).get_attribute("href")
        assert "format=xlsx" in roh and "from=2026-11-01" in roh
    finally:
        ctx.close()
