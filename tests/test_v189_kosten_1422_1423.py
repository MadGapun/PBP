"""#1422 und #1423 (Hotfix 1.8.9): Kosten ohne Bewerbung im Dashboard, und die
Vorauswahl der Statistik-Seite bleibt bei einem manuellen Zeitraum nicht markiert.

Die Browser-Faelle laufen gegen das GEBAUTE Bundle (nach JSX-Aenderungen
`pnpm exec vite build`). Testdaten fiktiv, Datenbank isoliert (`BA_DATA_DIR`).
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
    aid = db.add_application({"title": "Bewerbung Muster", "company": "Musterfirma GmbH",
                              "status": "beworben", "applied_at": "2026-11-03"})
    db.add_application_cost({"application_id": aid, "kind": "reise", "amount": 24.9,
                             "description": "Fahrt zum Gespräch", "incurred_at": "2026-11-12"})
    db.add_application_cost({"kind": "tool", "amount": 38.4,
                             "description": "Abo Stellenbörse", "incurred_at": "2026-11-05"})
    db.add_application_cost({"kind": "pruefung", "amount": 10.0,
                             "description": "Gebühr ohne Datum"})
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


def _json(url, daten=None, methode="GET"):
    import json
    req = urllib.request.Request(
        url, method=methode,
        data=json.dumps(daten).encode() if daten is not None else None,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def test_api_liste_summe_und_ohne_datum(server):
    basis, _ = server
    status, antwort = _json(f"{basis}/api/costs")
    assert status == 200
    assert len(antwort["costs"]) == 3
    assert antwort["summe_eur"] == pytest.approx(73.3)
    assert antwort["ohne_datum"] == 1


def test_api_anlegen_ohne_bewerbung_und_pruefungen(server):
    basis, db = server
    status, antwort = _json(f"{basis}/api/costs", {
        "kind": "tool", "amount": 5, "description": "Abo", "incurred_at": "2026-11-20"}, "POST")
    assert status == 200 and antwort["status"] == "created"
    neu = [c for c in db.list_application_costs() if c["id"] == antwort["id"]][0]
    assert neu["application_id"] is None
    # Betrag 0 und ein kaputtes Datum werden mit einem deutschen Satz abgewiesen
    s0, a0 = _json(f"{basis}/api/costs", {"kind": "tool", "amount": 0}, "POST")
    assert s0 == 400 and "Betrag" in a0["error"]
    s1, a1 = _json(f"{basis}/api/costs", {"kind": "tool", "amount": 3,
                                         "incurred_at": "morgen"}, "POST")
    assert s1 == 400 and "Datum" in a1["error"]


def test_dashboard_kosten_anlegen_sehen_loeschen(server, browser):
    basis, _ = server
    ctx = browser.new_context(viewport={"width": 1440, "height": 1400})
    page = ctx.new_page()
    try:
        page.goto(f"{basis}/#statistiken", wait_until="domcontentloaded", timeout=30000)
        block = page.locator("[data-kosten-block]")
        expect(block).to_be_visible(timeout=20000)
        posten = block.locator("[data-kostenposten]")
        expect(posten).to_have_count(3)
        # Posten ohne Datum ist sichtbar markiert
        expect(block).to_contain_text("ohne Datum, zählt in keinem Zeitraum")
        expect(block.locator("[data-kosten-summe]")).to_contain_text("73,30 €")
        # anlegen
        block.get_by_label("Betrag in Euro").fill("12,50")
        block.get_by_label("Beschreibung der Kosten").fill("Bewerbungsfotos")
        block.get_by_role("button", name="Speichern").click()
        expect(posten).to_have_count(4, timeout=10000)
        expect(block.locator("[data-kosten-summe]")).to_contain_text("85,80 €")
        # löschen: erst nachfragen, dann löschen
        zeile = posten.filter(has_text="Bewerbungsfotos")
        zeile.get_by_role("button", name=re.compile(r"löschen$")).click()
        expect(zeile).to_contain_text("Wirklich löschen?")
        zeile.get_by_role("button", name="Ja, löschen").click()
        expect(posten).to_have_count(3, timeout=10000)
    finally:
        ctx.close()


def test_vorauswahl_nicht_markiert_bei_manuellem_zeitraum(server, browser):
    basis, _ = server
    ctx = browser.new_context(viewport={"width": 1440, "height": 1400})
    page = ctx.new_page()
    try:
        page.goto(f"{basis}/#statistiken", wait_until="domcontentloaded", timeout=30000)
        alles = page.get_by_role("button", name="Alles", exact=True)
        expect(alles).to_have_class(re.compile(r"text-sky"), timeout=20000)
        page.get_by_label("Zeitraum von").fill("01.11.2026")
        expect(alles).not_to_have_class(re.compile(r"text-sky"), timeout=10000)
        page.get_by_role("button", name="zurücksetzen").click()
        expect(alles).to_have_class(re.compile(r"text-sky"), timeout=10000)
    finally:
        ctx.close()
