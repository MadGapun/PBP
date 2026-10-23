"""#1139: „Bewerbungen im Blick behalten“ im Browser — gegen das gebaute Bundle, mit echtem Server und echter Datenbank.

Die Karte nennt das Intervall (Vorgabe „Täglich“) und den nächsten Lauf, hat den Schalter „Beim täglichen Lauf von selbst abschließen“
(Vorgabe aus) und sagt beim letzten Lauf, ob er von selbst oder per Knopf kam. Jede Änderung wird ECHT gespeichert (Datenbank), nicht
nur angezeigt.

Gebaut wird mit `cd frontend && pnpm exec vite build`, wenn sich das Frontend ändert. Die übrigen Schritte der Runde sind hier leere
Ersatzfunktionen (kein Netz, keine KI); das Abschließen selbst ist echt.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from bewerbungs_assistent.services import aufraeum_runde  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

SCHRITTE = ("_run_followup_ueberholt", "_run_auto_followup_reconciler", "_run_auto_classify_emails", "_run_auto_classify_documents",
            "_run_auto_deep_analysis", "_run_analyze_user_patterns", "_run_scraper_probe", "_run_extract_contacts",
            "_run_auto_refetch_descriptions", "_run_snapshot_backfill", "_run_url_aging_check", "_run_check_stale_applications",
            "_run_elwosa_speak")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("runde1139")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    dash._db = db
    mp = pytest.MonkeyPatch()
    for name in SCHRITTE:
        mp.setattr(dash, name, lambda *a, **k: {})
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
    yield {"url": f"http://127.0.0.1:{port}", "db": db}
    srv.should_exit = True
    t.join(timeout=10)
    mp.undo()
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


def _karte(browser, umgebung):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = ctx.new_page()
    page.goto(f"{umgebung['url']}/#einstellungen", wait_until="load", timeout=30000)
    page.get_by_role("button", name="Erweitert").first.wait_for(timeout=20000)
    reiter = page.get_by_role("button", name="Automatik", exact=True)
    if reiter.count() == 0:
        page.locator("[data-erweitert-schalter]").click()
    reiter.first.click()
    karte = page.locator("[data-testid=aufraeum-runde-karte]")
    karte.wait_for(timeout=15000)
    return ctx, page, karte


def _warte(bedingung, sekunden=15):
    ende = time.time() + sekunden
    while time.time() < ende:
        if bedingung():
            return True
        time.sleep(0.2)
    return False


def test_die_karte_nennt_vorgabe_und_wahrheit(browser, umgebung):
    ctx, page, karte = _karte(browser, umgebung)
    try:
        text = " ".join(karte.inner_text().split())
        assert "einmal am Tag von selbst" in text and "Von selbst prüfen" in text
        assert karte.locator("button[role=combobox]").first.inner_text().strip() == "Täglich"
        assert "Nächster Lauf" in karte.locator("[data-testid=aufraeum-naechster-lauf]").inner_text()
        assert not karte.locator("[data-testid=expire-automatisch]").is_checked(), "das Abschließen ist vorgabemäßig aus"
        assert "noch nie" in karte.locator("[data-testid=aufraeum-letzter-lauf]").inner_text()
    finally:
        ctx.close()


def test_der_schalter_und_das_intervall_werden_echt_gespeichert(browser, umgebung):
    db = umgebung["db"]
    ctx, page, karte = _karte(browser, umgebung)
    try:
        # kein .check(): das Feld ist gesteuert und kippt erst, wenn der Server geantwortet hat
        karte.locator("[data-testid=expire-automatisch]").click()
        assert _warte(lambda: aufraeum_runde.expire_automatisch(db)), "der Schalter wurde nicht gespeichert"
        assert _warte(lambda: karte.locator("[data-testid=expire-automatisch]").is_checked())

        karte.locator("button[role=combobox]").first.click()
        page.get_by_role("option", name="Wöchentlich", exact=True).click()
        assert _warte(lambda: db.get_automatik_settings()["aufraeumen_intervall_tage"] == 7)

        karte.locator("button[role=combobox]").first.click()
        page.get_by_role("option", name="Aus", exact=True).click()
        assert _warte(lambda: db.get_automatik_settings()["aufraeumen_intervall_tage"] == 0)
        assert _warte(lambda: "Jetzt prüfen" in karte.locator("[data-testid=aufraeum-naechster-lauf]").inner_text())
    finally:
        ctx.close()
        db.set_automatik_settings(aufraeumen_intervall_tage=1)
        aufraeum_runde.expire_automatisch_setzen(db, False)


def test_jetzt_pruefen_schliesst_ab_und_das_protokoll_nennt_den_knopf(browser, umgebung):
    db = umgebung["db"]
    aid = db.add_application({"company": "Altbetrieb GmbH", "title": "Konstrukteurin", "status": "beworben",
                              "applied_at": (datetime.now() - timedelta(days=150)).date().isoformat()})
    conn = db.connect()
    conn.execute("DELETE FROM application_events WHERE application_id=?", (aid,))
    conn.commit()
    assert not aufraeum_runde.expire_automatisch(db)
    ctx, page, karte = _karte(browser, umgebung)
    try:
        karte.get_by_role("button", name="Jetzt prüfen").click()
        assert _warte(lambda: db.connect().execute("SELECT status FROM applications WHERE id=?", (aid,)).fetchone()["status"]
                      == "abgelaufen"), "der Knopf schließt immer ab - auch bei ausgeschaltetem Schalter"
        assert _warte(lambda: "(per Knopf)" in karte.locator("[data-testid=aufraeum-letzter-lauf]").inner_text())
        assert "noch nie" not in karte.locator("[data-testid=aufraeum-letzter-lauf]").inner_text()
    finally:
        ctx.close()
