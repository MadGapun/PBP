"""#1301 im Browser: jede Anstellungsform hat auf Stellen- und Bewerbungskarte
dieselbe Farbe, beim Namen, im hellen und im dunklen Modus.

Gegen das GEBAUTE Bundle (nach JSX-Aenderungen `pnpm exec vite build`).
Testdaten fiktiv. Geprueft wird die BERECHNETE Farbe im Browser, nicht der
Quelltext: ein Ton ohne Tailwind-Regel faellt still auf die Grundfarbe
zurueck, und das sieht nur der Browser.

Mit `PBP_FARBEN_BILDER=<ordner>` legt der Test je Modus ein Bildschirmfoto ab.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402

TEXT = "Wir suchen Unterstützung in der Projektsteuerung. Aufgaben: Planung und Abstimmung. " * 3

#: Titel ohne Formbegriffe, damit die Erkennung aus dem Titel nichts umstellt.
STELLEN = {
    "festanstellung": "Planung Musterprojekt Eins",
    "freelance": "Planung Musterprojekt Zwei",
    "zeitarbeit": "Planung Musterprojekt Drei",
    "praktikum": "Planung Musterprojekt Vier",
    "werkstudent": "Planung Musterprojekt Fuenf",
    "ausbildung": "Planung Musterprojekt Sechs",
    "": "Planung Musterprojekt Ohne Angabe",
}
NAME = {"festanstellung": "Festanstellung", "freelance": "Freelance", "zeitarbeit": "Zeitarbeit",
        "praktikum": "Praktikum", "werkstudent": "Werkstudent", "ausbildung": "Ausbildung",
        "": "Form unbekannt"}
#: Die Textfarbe des Abzeichens je Modus (styles.css); unbekannt = muted.
FARBE = {
    "dark": {"festanstellung": "rgb(129, 161, 255)", "freelance": "rgb(94, 234, 212)",
             "zeitarbeit": "rgb(180, 150, 255)", "praktikum": "rgb(251, 146, 60)",
             "werkstudent": "rgb(222, 220, 80)", "ausbildung": "rgb(214, 170, 130)",
             "": "rgb(140, 152, 178)"},
    "light": {"festanstellung": "rgb(37, 99, 235)", "freelance": "rgb(11, 124, 114)",
              "zeitarbeit": "rgb(109, 40, 217)", "praktikum": "rgb(194, 65, 12)",
              "werkstudent": "rgb(104, 108, 0)", "ausbildung": "rgb(120, 74, 44)",
              "": "rgb(100, 112, 136)"},
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
    db.save_jobs([
        {"hash": f"st1301{i}", "title": titel, "company": "Musterfirma GmbH",
         "url": f"https://example.com/1301/{i}", "source": "manuell", "description": TEXT,
         "location": "Musterstadt", "employment_type": form or "festanstellung"}
        for i, (form, titel) in enumerate(STELLEN.items())
    ])
    conn = db.connect()
    # Ohne Angabe: der Bestand kennt Stellen ohne Form (Altdaten, Bewerbungen ohne Stelle).
    conn.execute("UPDATE jobs SET employment_type=NULL WHERE title=?", (STELLEN[""],))
    conn.commit()
    for form in ("freelance", "zeitarbeit"):
        aid = db.add_application({"title": f"Bewerbung {NAME[form]}", "company": "Musterfirma GmbH",
                                  "status": "beworben"})
        db.update_application(aid, {"employment_type": form})
    db.add_application({"title": "Bewerbung ohne Angabe", "company": "Musterfirma GmbH", "status": "beworben"})
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


def _seite(browser, url, modus, ziel):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1400})
    ctx.add_init_script(f"try {{ localStorage.setItem('pbp-theme-mode', '{modus}'); }} catch (e) {{}}")
    page = ctx.new_page()
    page.goto(f"{url}/#{ziel}", wait_until="domcontentloaded", timeout=30000)
    expect(page.locator("html")).to_have_attribute("data-theme", modus, timeout=20000)
    return ctx, page


def _abzeichen_farbe(marke):
    return marke.evaluate("el => getComputedStyle(el.firstElementChild).color")


def _rand(karte):
    return karte.evaluate("el => getComputedStyle(el).borderTopColor")


@pytest.mark.parametrize("modus", ["dark", "light"])
def test_stellenkarten_zeigen_jede_form_in_ihrer_farbe(server, browser, modus):
    url, _db = server
    ctx, page = _seite(browser, url, modus, "stellen")
    try:
        raender = {}
        for form, titel in STELLEN.items():
            karte = page.locator("[data-stellenkarte]").filter(
                has=page.get_by_role("heading", name=titel, exact=True))
            expect(karte).to_have_count(1, timeout=20000)
            marke = karte.locator("[data-anstellungsform]")
            expect(marke).to_have_text(NAME[form])
            expect(marke).to_have_attribute("data-anstellungsform", form or "unbekannt")
            # Die Farbe steht nie allein: das Abzeichen erklaert sie.
            assert "Anstellungsform" in (marke.get_attribute("title") or "")
            assert _abzeichen_farbe(marke) == FARBE[modus][form], (modus, form)
            raender[form] = _rand(karte)
        # Jede Form einen eigenen Rand; Festanstellung ist markiert, unbekannt nicht wie sie.
        assert len(set(raender.values())) == len(raender), raender
        if os.environ.get("PBP_FARBEN_BILDER"):
            ziel = Path(os.environ["PBP_FARBEN_BILDER"])
            ziel.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(ziel / f"stellen_{modus}.png"), full_page=True)
    finally:
        ctx.close()


@pytest.mark.parametrize("modus", ["dark", "light"])
def test_bewerbungskarten_unterscheiden_freelance_und_zeitarbeit(server, browser, modus):
    url, _db = server
    ctx, page = _seite(browser, url, modus, "bewerbungen")
    try:
        farben, raender = {}, {}
        for form, titel in (("freelance", "Bewerbung Freelance"), ("zeitarbeit", "Bewerbung Zeitarbeit"),
                            ("", "Bewerbung ohne Angabe")):
            karte = page.locator("[data-bewerbungskarte]").filter(
                has=page.get_by_role("heading", name=titel, exact=True))
            expect(karte).to_have_count(1, timeout=20000)
            marke = karte.locator("[data-anstellungsform]")
            expect(marke).to_have_text(NAME[form])
            farben[form] = _abzeichen_farbe(marke)
            raender[form] = _rand(karte)
            assert farben[form] == FARBE[modus][form], (modus, form)
        assert len(set(raender.values())) == 3, raender
        if os.environ.get("PBP_FARBEN_BILDER"):
            ziel = Path(os.environ["PBP_FARBEN_BILDER"])
            page.screenshot(path=str(ziel / f"bewerbungen_{modus}.png"), full_page=True)
    finally:
        ctx.close()
