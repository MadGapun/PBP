"""#1316 im Browser: Notizen im Stellen-Dialog anlegen, verschieben und loeschen. Beleg ist die Datenbank nach dem Klick.

Gegen das GEBAUTE Bundle (nach JSX-Aenderungen `pnpm exec vite build`). Gewartet wird auf Zustaende, nicht auf Zeit.
Testdaten fiktiv (Musterfirma GmbH).
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

TEXT = "Wir suchen Unterstützung in der Projektsteuerung. Aufgaben: Planung und Abstimmung. " * 4


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
    db.save_jobs([
        {"hash": "st1316a", "title": "Projektsteuerung Musterprojekt", "company": "Musterfirma GmbH",
         "url": "https://example.com/1316a", "source": "manuell", "description": TEXT,
         "location": "Musterstadt", "employment_type": "festanstellung", "remote_level": "unbekannt"},
        {"hash": "st1316b", "title": "Projektsteuerung Altbestand", "company": "Musterfirma GmbH",
         "url": "https://example.com/1316b", "source": "manuell",
         "description": TEXT + "\n---\nMeine alte Rechnung",
         "location": "Musterstadt", "employment_type": "freelance", "remote_level": "unbekannt"},
    ])
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


def _details(browser, url, titel):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"{url}/#stellen", wait_until="domcontentloaded", timeout=30000)
    page.get_by_role("heading", name=titel).first.wait_for(timeout=20000)
    page.get_by_role("heading", name=titel).first.click()
    page.get_by_role("heading", name="Stellendetails").wait_for(state="visible")
    page.get_by_test_id("stellen-notizen").wait_for(state="visible")
    return page


def _notizen(db, h):
    return [dict(z) for z in db.connect().execute(
        "SELECT * FROM job_notes WHERE job_hash=? ORDER BY id", (db.resolve_job_hash(h),))]


def test_notiz_anlegen_und_loeschen(browser, server):
    url, db = server
    page = _details(browser, url, "Projektsteuerung Musterprojekt")
    try:
        bereich = page.get_by_test_id("stellen-notizen")
        expect(bereich.get_by_text("Noch keine Notiz")).to_be_visible()
        bereich.get_by_role("button", name="Notiz hinzufügen").click()
        bereich.get_by_label("Neue Notiz").fill("Umsatz bei 40 %\nUmsatz bei 50 %")
        bereich.get_by_role("button", name="Notiz speichern").click()
        eintrag = bereich.get_by_test_id("stellen-notiz")
        expect(eintrag).to_have_count(1)
        expect(eintrag.first).to_contain_text("von dir")
        z = _notizen(db, "st1316a")
        assert [(n["herkunft"], n["text"]) for n in z] == [("mensch", "Umsatz bei 40 %\nUmsatz bei 50 %")]
        assert db.get_job("st1316a")["description"] == TEXT, "die Beschreibung bleibt unberuehrt"
        # Loeschen fragt nach
        eintrag.first.get_by_role("button", name="Notiz löschen").click()
        dialog = page.get_by_role("dialog").filter(has_text="Notiz löschen?")
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name="Löschen", exact=True).click()
        expect(eintrag).to_have_count(0)
        assert _notizen(db, "st1316a") == []
    finally:
        page.close()


def test_oeffnen_setzt_den_fokus_nicht_in_die_notizen(browser, server):
    """Ein Eingabefeld im Dialog bekaeme beim Oeffnen den Fokus: der Dialog spraenge ans Ende, und die Seite frischte nichts
    mehr auf (ein Urteil von Claude kaeme im offenen Dialog nicht an, test_v18_wege_1171). Das Feld erscheint erst auf Klick."""
    url, _db = server
    page = _details(browser, url, "Projektsteuerung Musterprojekt")
    try:
        expect(page.get_by_test_id("stellen-notizen").get_by_label("Neue Notiz")).to_have_count(0)
        assert page.evaluate("document.activeElement.tagName") not in ("TEXTAREA", "INPUT")
    finally:
        page.close()


def test_altbestand_nur_auf_klick(browser, server):
    url, db = server
    page = _details(browser, url, "Projektsteuerung Altbestand")
    try:
        bereich = page.get_by_test_id("stellen-notizen")
        expect(bereich.get_by_test_id("notizteil-hinweis")).to_be_visible()
        assert _notizen(db, "st1316b") == [], "Anzeigen darf nichts verschieben"
        bereich.get_by_role("button", name="In die Notizen verschieben").click()
        dialog = page.get_by_role("dialog").filter(has_text="Notizteil verschieben?")
        expect(dialog).to_contain_text("Meine alte Rechnung")
        dialog.get_by_role("button", name="Verschieben", exact=True).click()
        expect(bereich.get_by_test_id("stellen-notiz")).to_have_count(1)
        expect(bereich.get_by_test_id("notizteil-hinweis")).to_have_count(0)
        assert [(n["herkunft"], n["text"]) for n in _notizen(db, "st1316b")] == [("migriert", "Meine alte Rechnung")]
        assert db.get_job("st1316b")["description"] == TEXT.strip()
    finally:
        page.close()
