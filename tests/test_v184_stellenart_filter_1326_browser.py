"""#1326 im Browser: der Filter "Stellenart" auf der Bewerbungsseite zeigt
genau die gewaehlte Anstellungsform.

Vorher kannte er nur Festanstellung und Freelance; "Freelance" zeigte alles
ausser Festanstellung (auch Zeitarbeit, Praktikum ...), "Festanstellung"
zusaetzlich alle Bewerbungen ohne Angabe.

Gegen das GEBAUTE Bundle (nach JSX-Aenderungen `pnpm exec vite build`).
Testdaten fiktiv.
"""
from __future__ import annotations

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
from playwright.sync_api import expect, sync_playwright  # noqa: E402

#: Filterwert -> Titel der einen Bewerbung, die er zeigen muss.
BEWERBUNGEN = {
    "festanstellung": "Bewerbung Muster Festanstellung",
    "zeitarbeit": "Bewerbung Muster Zeitarbeit",
    "freelance": "Bewerbung Muster Freelance",
    "praktikum": "Bewerbung Muster Praktikum",
    "werkstudent": "Bewerbung Muster Werkstudent",
    "ausbildung": "Bewerbung Muster Ausbildung",
    "unbekannt": "Bewerbung Muster ohne Angabe",
}

#: Filterwert -> Text in der Auswahl, in der Reihenfolge der Liste.
TEXT = {
    "festanstellung": "Festanstellung", "zeitarbeit": "Zeitarbeit", "freelance": "Freelance",
    "praktikum": "Praktikum", "werkstudent": "Werkstudent", "ausbildung": "Ausbildung",
    "unbekannt": "Form unbekannt",
}


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
    for form, titel in BEWERBUNGEN.items():
        aid = db.add_application({"title": titel, "company": "Musterfirma GmbH", "status": "beworben"})
        if form != "unbekannt":
            db.update_application(aid, {"employment_type": form})
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


def test_filter_stellenart_zeigt_genau_die_gewaehlte_form(server, browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1400})
    page = ctx.new_page()
    try:
        page.goto(f"{server}/#bewerbungen", wait_until="domcontentloaded", timeout=30000)
        karten = page.locator("[data-bewerbungskarte]")
        expect(karten).to_have_count(len(BEWERBUNGEN), timeout=20000)
        # Eigene Auswahlliste (G71): Rolle combobox, benannt nach dem Feld.
        auswahl = page.get_by_role("combobox", name=re.compile(r"^Stellenart\b"))
        expect(auswahl).to_have_count(1)
        auswahl.click()
        namen = page.get_by_role("listbox").get_by_role("option").all_inner_texts()
        assert [n.strip() for n in namen] == ["Alle", *TEXT.values()], namen
        page.keyboard.press("Escape")
        for form, titel in BEWERBUNGEN.items():
            auswahl.click()
            page.get_by_role("option", name=TEXT[form], exact=True).click()
            expect(karten).to_have_count(1, timeout=10000)
            expect(karten.first).to_contain_text(titel)
        auswahl.click()
        page.get_by_role("option", name="Alle", exact=True).click()
        expect(karten).to_have_count(len(BEWERBUNGEN), timeout=10000)
    finally:
        ctx.close()
