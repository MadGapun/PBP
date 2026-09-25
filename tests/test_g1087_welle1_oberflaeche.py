"""Welle 1 aus #1087 — Defekte im Kernweg der Oberflaeche (G57, G58).

Belegt im gerenderten Dashboard gegen eine isolierte Datenbank, nicht per
Grep (v1.7.71 MERKE 9):

* G57 (D3): eine importierte Mail oeffnet sich im Dokumente-Tab — vorher
  stuerzte der Bereich mit "buildReplyMailto is not defined" ab.
* G57 (D4): Termin-Loeschen in der Timeline nimmt den Termin wirklich aus
  der Ansicht — vorher rief der Knopf `loadTimeline()`, das es nicht gibt.
* G57 (D5): der Zusage-Dialog zeigt Umlaute statt `\\u00e4`.
* G57 (D6): Sprung aus Dokumente und Kalender landet in der Timeline der
  Bewerbung statt oben in der Liste.
* G58 (C6, D7): deutsche Feldbeschriftungen, Vorgabe "Ich will mich
  bewerben", ein Verb.
"""
import os
import socket
import threading
import time
import urllib.request
from datetime import datetime, timedelta

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

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    app_id = db.add_application({"title": "Sachbearbeitung Einkauf",
                                 "company": "Musterbetrieb GmbH", "status": "beworben"})
    db.add_email({"application_id": None, "subject": "Einladung zum Gespraech",
                  "sender": "Personal <personal@example.com>",
                  "recipients": "erika@example.com", "sent_date": "2026-09-20",
                  "direction": "eingang", "body_text": "Wir laden Sie ein ..."})
    db.add_document({"filename": "anschreiben.pdf", "doc_type": "anschreiben",
                     "extracted_text": "Sehr geehrte Damen und Herren ...",
                     "extraction_status": "angewendet",
                     "linked_application_id": app_id})
    morgen = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0)
    db.add_meeting({"application_id": app_id, "title": "Vorstellungsgespraech",
                    "meeting_date": morgen.strftime("%Y-%m-%dT%H:%M"),
                    "meeting_type": "interview", "status": "geplant"})
    db.save_jobs([{"hash": "g58stelle1", "title": "Disposition Lager",
                   "company": "Lagerhaus Nord GmbH", "url": "https://example.com/g58",
                   "source": "manuell", "description": "Ein Anzeigentext. " * 12,
                   "score": 5}])

    dash._db = db
    port = _free_port()
    cfg = uvicorn.Config(dash.app, host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(cfg)
    srv.install_signal_handlers = lambda: None
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}", db, app_id
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


def _seite(browser, url, tab):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    fehler = []
    page.on("pageerror", lambda e: fehler.append(str(e)))
    # Nicht "networkidle": der Stellen-Tab fragt den Suchlauf-Status
    # regelmaessig ab und wird nie still.
    page.goto(f"{url}/#{tab}", wait_until="load", timeout=30000)
    page.wait_for_timeout(2000)
    return page, fehler


def test_g57_mail_oeffnet_sich_im_dokumente_tab(browser, server):
    url, _db, _aid = server
    page, fehler = _seite(browser, url, "dokumente")
    try:
        page.get_by_text("Einladung zum Gespraech").first.click()
        page.wait_for_selector("text=Bewerbung zuordnen", timeout=10000)
        text = page.inner_text("body")
        assert "abgestürzt" not in text
        assert "Antworten" in text
        # Die Bewerbungen stehen zur Auswahl — vorher kam keine Liste an.
        # SelectInput ist ein Knopf mit Panel, also erst oeffnen.
        page.get_by_text("— Nicht zugeordnet —").first.click()
        page.wait_for_timeout(400)
        assert "Sachbearbeitung Einkauf @ Musterbetrieb GmbH" in page.inner_text("body")
        assert not [f for f in fehler if "not defined" in f], fehler
    finally:
        page.close()


def test_g57_sprung_aus_dokumenten_landet_in_der_timeline(browser, server):
    url, _db, _aid = server
    page, _ = _seite(browser, url, "dokumente")
    try:
        page.get_by_role("button", name="Musterbetrieb GmbH — Sachbearbeitung Einkauf").first.click()
        page.wait_for_selector("text=Timeline - Sachbearbeitung Einkauf", timeout=10000)
    finally:
        page.close()


def test_g57_sprung_aus_dem_kalender_landet_in_der_timeline(browser, server):
    url, _db, _aid = server
    page, _ = _seite(browser, url, "kalender")
    try:
        page.get_by_text("Vorstellungsgespraech").first.click()
        page.wait_for_selector("text=Timeline - Sachbearbeitung Einkauf", timeout=10000)
    finally:
        page.close()


def test_g57_termin_loeschen_nimmt_ihn_aus_der_timeline(browser, server):
    url, db, aid = server
    page, fehler = _seite(browser, url, "kalender")
    try:
        page.get_by_text("Vorstellungsgespraech").first.click()
        dialog = page.locator("text=Timeline - Sachbearbeitung Einkauf")
        dialog.wait_for(timeout=10000)
        page.get_by_title("Termin löschen").first.click()
        # G67 (#1087 H5): der eigene Bestaetigungsdialog statt window.confirm.
        page.locator("[data-bestaetigung]").get_by_role("button", name="Ja").click()
        page.wait_for_timeout(1500)
        assert not [f for f in fehler if "not defined" in f], fehler
        con = db.connect()
        n = con.execute("SELECT COUNT(*) FROM application_meetings WHERE application_id=?",
                        (aid,)).fetchone()[0]
        assert n == 0
        assert page.get_by_title("Termin löschen").count() == 0
    finally:
        page.close()


def test_g57_zusage_dialog_hat_umlaute(browser, server):
    url, _db, _aid = server
    page, _ = _seite(browser, url, "bewerbungen")
    try:
        # SelectInput ist seit G71 ein combobox mit Liste (#1027): oeffnen, Wert waehlen.
        page.get_by_role("combobox", name="Beworben", exact=True).first.click()
        page.get_by_text("Angenommen", exact=True).last.click()
        # Auf den ZUSTAND warten (den Knopf im Dialogfuss), nicht auf den
        # Titel: auf dem Linux-Runner stand der Titel schon da, der Rest
        # des Dialogs noch nicht (v1.7.93 MERKE 9).
        # exact=True: "Später (7 Tage)" steht an anderer Stelle der Seite
        # und liess die erste Fassung gar nicht warten.
        page.get_by_role("button", name="Später", exact=True).first.wait_for(state="visible", timeout=15000)
        # Beide Knoepfe als ZUSTAND pruefen statt einen Schnappschuss von
        # body zu lesen: in der vollen Suite lag zwischen Warten und Lesen
        # ein Neuaufbau, und body enthielt den Dialog nicht mehr.
        page.get_by_role("button", name="Übernehmen und speichern").first.wait_for(
            state="visible", timeout=15000)
        text = page.inner_text("body")
        assert "\\u00" not in text
    finally:
        page.close()


def test_g58_neue_bewerbung_spricht_deutsch(browser, server):
    url, _db, _aid = server
    page, _ = _seite(browser, url, "bewerbungen")
    try:
        page.get_by_role("button", name="Bewerbung anlegen").first.click()
        page.wait_for_selector("text=Stellentitel", timeout=10000)
        text = page.inner_text("body")
        for label in ("Stellentitel", "Firma", "Link zur Anzeige", "Wo stehst du?"):
            assert label in text, label
        for roh in ("applied_at",):
            assert roh not in text
        # Vorgabe: vorbereiten, kein Datum.
        assert "Ich will mich bewerben" in text
        assert "Beworben am" not in text
    finally:
        page.close()


def test_g58_bewerbung_aus_stelle_startet_mit_vorbereitung(browser, server):
    url, db, _aid = server
    page, _ = _seite(browser, url, "stellen")
    try:
        page.get_by_role("button", name="Bewerbung anlegen").first.click()
        page.wait_for_selector("text=Wo stehst du?", timeout=10000)
        text = page.inner_text("body")
        assert "Stellentitel" in text
        assert "Ich will mich bewerben" in text
        assert "Beworben am" not in text
        page.get_by_role("button", name="Bewerbung speichern").click()
        page.wait_for_timeout(1500)
        row = db.connect().execute(
            "SELECT status, applied_at FROM applications WHERE title='Disposition Lager'").fetchone()
        assert row["status"] == "in_vorbereitung"
        assert not row["applied_at"]
    finally:
        page.close()
