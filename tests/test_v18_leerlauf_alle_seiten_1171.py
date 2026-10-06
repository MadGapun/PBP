"""Jede Seite des Dashboards ist im Leerlauf still (#1171, Lehre L61).

Auf der Seite „Stellen“ lief ein Abfrage-Effekt in einer Endlosschleife (270 bis 470 Anfragen pro Sekunde, Hauptthread zu zwei
Dritteln beschaeftigt, seit v0.23.0). Kein Absturz, keine Meldung: der Rechner wird nur lauter. Ein einzelner Test fuer genau
diese Seite haelt den einen Fehler fern; dieser hier sieht JEDE Seite an — eine kuenftige Schleife an anderer Stelle faellt so
auf, bevor jemand den Luefter hoert.

Gemessen wird nach dem Aufbau: erst abwarten, bis kein Netzverkehr mehr laeuft (der Start laedt jede Seite zweimal), dann drei Sekunden zaehlen.
Gesund sind einzelne Anfragen (das Dashboard fragt alle paar Sekunden nach Aenderungen); der Fehler machte hunderte pro Sekunde.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TEXT = ("Wir suchen eine Sachbearbeitung im Einkauf. Aufgaben: Disposition, Bestellabwicklung mit SAP MM, "
        "Lieferantenkommunikation. Anforderungen: kaufmaennische Ausbildung, Englisch. ") * 3
SEITEN = ["dashboard", "profil", "suche", "dokumente", "stellen", "bewerbungen", "kontakte", "aufgaben", "kalender",
          "statistiken", "einstellungen"]
GRENZE = 10  # Anfragen in drei Sekunden; gemessen gesund: 1 bis 2 (die Abfrage nach Aenderungen alle 2 s), die Schleife machte 800 bis 1.400


def _tag(tage: int) -> str:
    return (date.today() + timedelta(days=tage)).isoformat()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("leerlauf")
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    db.save_jobs([{"hash": f"ll{n}", "title": f"Sachbearbeitung Einkauf {n}", "company": f"Musterbetrieb {n} GmbH",
                   "url": f"https://example.com/ll{n}", "source": "manuell", "description": TEXT, "remote_level": "hybrid",
                   "location": "Hamburg", "score": 10 - n} for n in range(6)])
    app = db.add_application({"title": "Disponent Lager", "company": "Beispiel AG", "status": "beworben", "applied_at": _tag(-20)})
    kontakt = db.add_contact({"full_name": "Kim Beispiel", "company": "Beispiel AG", "position": "Personalreferentin"})
    db.link_contact(kontakt, "application", app, role="Personalabteilung")
    db.add_follow_up(app, _tag(-2), "nachfass")
    db.add_task({"titel": "Zeugnis anfordern", "typ": "custom", "faellig_am": _tag(-1), "application_id": app})
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


@pytest.mark.parametrize("seite", SEITEN)
def test_seite_ist_im_leerlauf_still(browser, server, seite):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    anfragen = []
    page.on("request", lambda r: anfragen.append(r.url.replace(server, "").split("?")[0]) if "/api/" in r.url else None)
    try:
        page.goto(f"{server}/#{seite}", wait_until="load", timeout=30000)
        page.wait_for_function("t => !document.body.innerText.includes(t)", arg="wird vorbereitet", timeout=20000)
        # Der Start laedt jede Seite zweimal. Gewartet wird auf den Zustand (kein Netzverkehr mehr), nicht auf eine Zeit; eine Seite,
        # die nie ruhig wird, faellt unten mit Zahlen auf statt hier mit einer Zeitueberschreitung.
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightError:
            pass
        page.wait_for_timeout(1000)
        davor = len(anfragen)
        page.wait_for_timeout(3000)
        im_leerlauf = anfragen[davor:]
        haeufigste = max(set(im_leerlauf), key=im_leerlauf.count) if im_leerlauf else ""
        assert len(im_leerlauf) < GRENZE, (
            f"Seite {seite}: {len(im_leerlauf)} Anfragen in 3 s im Leerlauf, am haeufigsten {haeufigste} "
            f"({im_leerlauf.count(haeufigste)}x)")
    finally:
        page.close()


def test_alle_seiten_des_dashboards_sind_erfasst():
    """Kommt eine Seite dazu, muss sie hier mit — sonst bleibt sie ungeprueft (Lehre 8c: ein Schutz zaehlt erst, wenn er aufgerufen wird)."""
    import re
    utils = (REPO / "frontend" / "src" / "utils.js").read_text(encoding="utf-8-sig")
    block = utils[utils.index("export const PAGE_IDS"):]
    block = block[:block.index("];")]
    ids = re.findall(r'"([a-z]+)"', block)
    assert set(ids) == set(SEITEN), f"PAGE_IDS und diese Liste weichen ab: {sorted(set(ids) ^ set(SEITEN))}"
