"""#1187 Stufe 3: die Karte „Stellen zu prüfen“ auf dem Dashboard — im Browser, gegen das gebaute Bundle.

Nach einem Browserlauf ist der nächste Schritt in PBP, nicht im Chat: die Karte nennt, wie viele Stellen auf das Urteil des
Menschen warten (und führt mit dem Filter „Prüfstand: nur ungeprüfte“ in die Liste), und was Claude nach dem Lesen aussortiert
hat — mit Grund und einem Klick auf „Zurückholen“, ohne die Karte zu verlassen.

Gebaut wird mit `cd frontend && pnpm exec vite build`, wenn sich das Frontend ändert. Alle Firmen sind erfunden.
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
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

TEXT = ("Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse "
        "und begleiten die Einfuehrung eines neuen PLM-Systems. Ihr Profil: abgeschlossenes Studium, mehrjaehrige "
        "Erfahrung im Maschinenbau.")
FIRMEN = ["Nordlicht Werke GmbH", "Sonnenhof Systeme AG", "Kupferberg Anlagenbau GmbH", "Wiesengrund Software GmbH",
          "Tannenwald Logistik AG", "Seeblick Elektronik GmbH"]
TITEL = ["PLM Systemadministrator (m/w/d)", "Teamcenter Berater (m/w/d)", "Konstruktionsleiter Maschinenbau (m/w/d)",
         "IT-Projektleiter ERP (m/w/d)", "Einkaufsleiter Beschaffung (m/w/d)", "Qualitaetsingenieur Elektronik (m/w/d)"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("zupruefen1187")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
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
    yield {"url": f"http://127.0.0.1:{port}", "db": db}
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


def _warte(bedingung, sekunden=15):
    ende = time.time() + sekunden
    while time.time() < ende:
        if bedingung():
            return True
        time.sleep(0.2)
    return False


def _leeren(db):
    conn = db.connect()
    conn.execute("DELETE FROM jobs")
    conn.commit()


def _job(db, i, **kw):
    j = {"hash": f"z{i:04d}", "title": TITEL[i % len(TITEL)], "company": FIRMEN[i % len(FIRMEN)],
         "location": "Musterstadt", "url": f"https://karriere.beispiel-{i}.example/jobs/{i}", "source": "stepstone",
         "description": TEXT, "score": 10}
    j.update(kw)
    db.save_jobs([j])
    return j["hash"]


def _seite(browser, url, ziel):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1100})
    page = ctx.new_page()
    page.goto(f"{url}/#{ziel}", wait_until="load", timeout=30000)
    return ctx, page


def test_ohne_wartende_stellen_steht_keine_karte_da(browser, umgebung):
    _leeren(umgebung["db"])
    ctx, page = _seite(browser, umgebung["url"], "dashboard")
    try:
        page.locator("#page-dashboard").wait_for(timeout=20000)
        page.wait_for_timeout(1200)
        assert page.locator("[data-stellen-zu-pruefen]").count() == 0
    finally:
        ctx.close()


def test_die_karte_nennt_was_wartet_und_fuehrt_mit_dem_filter_in_die_liste(browser, umgebung):
    db = umgebung["db"]
    _leeren(db)
    for i in range(3):
        _job(db, i)
    beurteilt = _job(db, 3)
    assert db.set_job_analysis(beurteilt, "BEDINGT", "Methodenluecke")
    ctx, page = _seite(browser, umgebung["url"], "dashboard")
    try:
        karte = page.locator("[data-stellen-zu-pruefen]")
        karte.wait_for(timeout=20000)
        text = " ".join(karte.inner_text().split())
        assert "3 neue Stellen warten auf dein Urteil" in text and "insgesamt 3 ungeprüft" in text
        assert "Claude" not in text, "nichts von Claude aussortiert: die Zeile gibt es nicht"
        karte.get_by_role("button", name="Stellen prüfen").click()
        page.locator("#page-stellen").wait_for(timeout=20000)
        assert _warte(lambda: page.locator("[data-stellenkarte]").count() == 3), \
            f"die Liste nach dem Sprung hat {page.locator('[data-stellenkarte]').count()} Karten statt 3"
        titel = " ".join(page.locator("#page-stellen").inner_text().split())
        assert TITEL[3] not in titel, "die beurteilte Stelle gehoert nicht in 'nur ungepruefte'"
    finally:
        ctx.close()


def test_was_claude_aussortiert_hat_ist_in_der_karte_zurueckholbar(browser, umgebung):
    db = umgebung["db"]
    _leeren(db)
    a = _job(db, 0)
    b = _job(db, 1)
    assert db.dismiss_job(a, "falsches_fachgebiet", herkunft="claude")
    assert db.dismiss_job(b, "zu_weit_entfernt", herkunft="claude")
    ctx, page = _seite(browser, umgebung["url"], "dashboard")
    try:
        karte = page.locator("[data-stellen-zu-pruefen]")
        karte.wait_for(timeout=20000)
        kopf = " ".join(karte.locator("[data-zu-pruefen-claude]").inner_text().split())
        assert "2 Stellen hat Claude nach dem Lesen aussortiert" in kopf and "Du kannst sie zurückholen" in kopf
        assert karte.locator("[data-zu-pruefen-liste]").count() == 0, "eingeklappt: die Liste steht noch nicht da"
        karte.get_by_role("button", name="Ansehen").click()
        zeilen = karte.locator("[data-zu-pruefen-zeile]")
        zeilen.first.wait_for(timeout=5000)
        assert zeilen.count() == 2
        erste = " ".join(zeilen.filter(has_text=TITEL[0]).inner_text().split())
        assert FIRMEN[0] in erste and "Falsches Fachgebiet" in erste, erste
        # zurueckholen: echt (Datenbank), und die Karte zaehlt neu
        zeilen.filter(has_text=TITEL[0]).get_by_role("button", name="Zurückholen").click()
        assert _warte(lambda: (db.get_job(a) or {}).get("is_active") == 1), "die Stelle wurde nicht zurueckgeholt"
        assert not (db.get_job(a).get("dismissed_by") or ""), "die Herkunft faellt mit dem Aussortieren"
        assert _warte(lambda: karte.locator("[data-zu-pruefen-zeile]").count() == 1)
        text = " ".join(karte.inner_text().split())
        assert "1 Stelle hat Claude nach dem Lesen aussortiert" in text
        assert "1 neue Stelle wartet auf dein Urteil" in text, "die zurueckgeholte Stelle wartet wieder auf das Urteil"
        # ... und der Weg in die Liste zeigt die Herkunft
        karte.get_by_role("button", name="In der Liste öffnen").click()
        page.locator("#page-stellen").wait_for(timeout=20000)
        assert _warte(lambda: "von Claude gelesen und aussortiert" in page.locator("#page-stellen").inner_text()), \
            "die Ausgeblendet-Liste zeigt die Herkunft nicht"
    finally:
        ctx.close()
