"""#1412 D1-D5, D8 im Browser gegen das GEBAUTE Bundle.

Isolierte Datenbank (BA_DATA_DIR), erfundene Daten. Gewartet wird auf
Zustaende (sichtbarer Text, gespeicherter Stand), nie auf Zeit.
"""
import os
import sys
import threading
from pathlib import Path

import httpx
import pytest
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

pw = pytest.importorskip("playwright")  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from test_dashboard_browser import (  # noqa: E402
    _dismiss_setup_overlay, _free_port, _wait_for_server, _warte_auf_datenbank)
from test_v188_mail_eingang_1412 import ABSAGE_KNAPP, EINLADUNG, eml  # noqa: E402


@pytest.fixture
def live(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Mail Browser", "email": "bewerber@example.com",
                     "summary": "Testprofil"})
    dash._db = db
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(dash.app, host="127.0.0.1", port=port,
                                           log_level="warning"))
    server.install_signal_handlers = lambda: None
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    _wait_for_server(base)
    yield {"base": base, "db": db, "tmp": tmp_path}
    server.should_exit = True
    t.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture(scope="module")
def browser():
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def _bewerbung(db, titel="Fachkraft Lagerlogistik", firma="Musterbau GmbH"):
    return db.add_application({"title": titel, "company": firma, "status": "beworben"})


def _oeffne(page, base, hash_):
    page.goto(base + hash_, wait_until="domcontentloaded")
    page.locator("div#root").wait_for(state="visible")
    _dismiss_setup_overlay(page)


def _timeline_oeffnen(page, base, titel):
    _oeffne(page, base, "#bewerbungen")
    page.get_by_role("heading", name=titel).first.click()
    page.locator('[data-abschnitt="dokumente"]').wait_for(state="visible")


def _datei_waehlen(page, pfad):
    with page.expect_file_chooser() as fc:
        page.get_by_text("Datei hierher ziehen oder klicken zum Upload").click()
    fc.value.set_files(str(pfad))


@pytest.mark.parametrize("roh", [True, False], ids=["roh-utf8", "kodiert"])
def test_mail_ohne_zuordnung_spaeter_zuordnen_termin_bleibt(live, browser, roh):
    """D1+D3: Mail ohne Zuordnung hochladen, spaeter zuordnen, Termin ist da."""
    db = live["db"]
    app_id = _bewerbung(db)
    inhalt = eml("Einladung zum Gespräch", EINLADUNG, roh=roh)
    r = httpx.post(live["base"] + "/api/emails/upload",
                   files={"file": ("einladung.eml", inhalt, "message/rfc822")})
    assert r.status_code == 200, r.text
    assert r.json()["match"]["application"] is None
    assert db.get_meetings_for_application(app_id) == []

    ctx = browser.new_context(viewport={"width": 1440, "height": 960})
    page = ctx.new_page()
    try:
        _oeffne(page, live["base"], "#dokumente")
        mail = page.get_by_text("Einladung zum Gespräch", exact=False).first
        mail.wait_for(state="visible")
        mail.click()
        page.get_by_text("Bewerbung zuordnen").wait_for(state="visible")
        page.get_by_role("combobox").last.click()
        page.get_by_role("option", name="Fachkraft Lagerlogistik @ Musterbau GmbH").click()
        page.get_by_role("button", name="Zuordnen", exact=True).click()
        _warte_auf_datenbank(
            lambda: len(db.get_meetings_for_application(app_id)) == 1,
            was="Termin nach spaeter Zuordnung")
    finally:
        ctx.close()


def test_zuordnung_nennt_kandidaten_oben(live, browser):
    """D2: bei mehreren passenden Bewerbungen stehen sie mit 'Passt' oben in der Liste."""
    db = live["db"]
    _bewerbung(db)
    _bewerbung(db)
    _bewerbung(db, "Buchhalter", "Andere AG")
    r = httpx.post(live["base"] + "/api/emails/upload",
                   files={"file": ("m.eml", eml(
                       "Ihre Bewerbung als Fachkraft Lagerlogistik bei Musterbau",
                       EINLADUNG), "message/rfc822")})
    assert r.json()["match"]["mehrdeutig"] is True
    ctx = browser.new_context(viewport={"width": 1440, "height": 960})
    page = ctx.new_page()
    try:
        _oeffne(page, live["base"], "#dokumente")
        page.get_by_text("Ihre Bewerbung als Fachkraft", exact=False).first.click()
        page.get_by_text("Bewerbung zuordnen").wait_for(state="visible")
        page.locator("[data-mehrdeutig]").wait_for(state="visible")
        page.get_by_role("combobox").last.click()
        optionen = page.get_by_role("option")
        page.get_by_role("option", name="Passt:").first.wait_for(state="visible")
        namen = [t.strip() for t in optionen.all_inner_texts()]
        assert namen[1].startswith("Passt:") and namen[2].startswith("Passt:"), namen
        assert not namen[3].startswith("Passt:"), namen
    finally:
        ctx.close()


def test_absage_in_bewerbung_ziehen_status_erst_nach_klick(live, browser):
    """D4+D5: Meldung nennt die Absage; der Status folgt erst nach dem Klick."""
    db = live["db"]
    app_id = _bewerbung(db)
    datei = live["tmp"] / "Ihre Bewerbung als Fachkraft.eml"
    datei.write_bytes(eml("Ihre Bewerbung als Fachkraft", ABSAGE_KNAPP))
    ctx = browser.new_context(viewport={"width": 1440, "height": 960})
    page = ctx.new_page()
    try:
        _timeline_oeffnen(page, live["base"], "Fachkraft Lagerlogistik")
        _datei_waehlen(page, datei)
        page.get_by_text("Status erkannt: Absage", exact=False).wait_for(state="visible")
        doc = _warte_auf_datenbank(
            lambda: next(iter(db._get_documents(db.get_active_profile_id())), None),
            was="Dokument gespeichert")
        assert doc["doc_type"] == "absage", doc["doc_type"]
        assert db.get_application(app_id)["status"] == "beworben", "nie still gesetzt"
        page.get_by_role("button", name="Status „Absage“ übernehmen").click()
        _warte_auf_datenbank(lambda: db.get_application(app_id)["status"] == "abgelehnt",
                             was="Status nach Klick")
    finally:
        ctx.close()


def test_einladung_in_bewerbung_ziehen_nennt_termin(live, browser):
    """D5: die Meldung nennt den angelegten Termin (Kopfzeilen roh in UTF-8)."""
    db = live["db"]
    app_id = _bewerbung(db)
    datei = live["tmp"] / "mail.eml"
    datei.write_bytes(eml("Ihre Bewerbung", EINLADUNG, roh=True))
    ctx = browser.new_context(viewport={"width": 1440, "height": 960})
    page = ctx.new_page()
    try:
        _timeline_oeffnen(page, live["base"], "Fachkraft Lagerlogistik")
        _datei_waehlen(page, datei)
        page.get_by_text("Termin 01.12., 10:00 Uhr angelegt", exact=False).wait_for(
            state="visible")
        _warte_auf_datenbank(lambda: len(db.get_meetings_for_application(app_id)) == 1,
                             was="Termin angelegt")
    finally:
        ctx.close()


def test_aufgabe_datum_ist_deutsch(live, browser):
    """D8: das Datumsfeld nimmt TT.MM.JJJJ (auch im englischen Browser) und speichert ISO."""
    db = live["db"]
    app_id = _bewerbung(db)
    ctx = browser.new_context(viewport={"width": 1440, "height": 960}, locale="en-US")
    page = ctx.new_page()
    try:
        _timeline_oeffnen(page, live["base"], "Fachkraft Lagerlogistik")
        feld = page.get_by_label("Erledigt bis")
        feld.scroll_into_view_if_needed()
        assert feld.get_attribute("placeholder") == "TT.MM.JJJJ"
        feld.fill("01.12.2099")
        page.get_by_placeholder("Neue Aufgabe").fill("Unterlagen prüfen")
        page.get_by_role("button", name="Aufgabe hinzufügen").click()

        def gespeichert():
            zeilen = db.connect().execute(
                "SELECT faellig_am FROM tasks WHERE application_id=?", (app_id,)).fetchall()
            return any(z["faellig_am"] == "2099-12-01" for z in zeilen)
        _warte_auf_datenbank(gespeichert, was="Aufgabe mit deutschem Datum")
    finally:
        ctx.close()
