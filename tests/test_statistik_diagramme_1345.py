"""#1345: Die aelteren Diagramme der Statistik-Seite widersprechen der Uebersicht nicht mehr.

Browser-Teil gegen das GEBAUTE Bundle. Testdaten fiktiv, Datenbank isoliert.
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

from bewerbungs_assistent.services.bericht_daten import dauer  # noqa: E402


def _bestand(db):
    db.save_profile({"name": "Erika Musterfrau"})
    pid = db.get_active_profile_id()
    c = db.connect()
    for tag in ("2026-03-03", "2026-05-04", "2026-05-20", "2026-09-02"):
        aid = db.add_application({"title": "Planer", "company": "Musterfirma GmbH", "status": "beworben",
                                  "applied_at": tag, "source": "stepstone"})
        c.execute("UPDATE applications SET applied_at=? WHERE id=?", (tag, aid))
    # Ein Monat nur mit neuen Stellen, dazu Punkte, die zwischen die alten Klassen fielen.
    for i, (monat, punkte) in enumerate((("2026-07-10", 3.5), ("2026-07-11", -2), ("2026-07-12", 12))):
        c.execute("INSERT INTO jobs (hash, title, company, source, score, found_at, is_active, is_pinned, profile_id) "
                  "VALUES (?, 'Stelle', 'Musterfirma GmbH', 'stepstone', ?, ?, 1, 0, ?)",
                  (f"{pid}:h{i}", punkte, monat, pid))
    c.commit()


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database

    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    _bestand(d)
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def test_verlauf_folgt_dem_gewaehlten_zeitraum(db):
    t = db.get_timeline_stats("month", von="2026-05-01", bis="2026-05-31")
    assert t["periods"] == ["2026-05"]
    assert t["applications"]["2026-05"] == 2


def test_alles_zeigt_den_ganzen_verlauf_auch_bei_monaten(db):
    t = db.get_timeline_stats("month", time_range="alles")
    assert sum(t["applications"].values()) == 4


def test_abschnitt_nur_mit_neuen_stellen_fehlt_nicht(db):
    t = db.get_timeline_stats("month", time_range="alles")
    assert "2026-07" in t["periods"]
    assert t["applications"]["2026-07"] == 0 and t["jobs_found"]["2026-07"] == 3


@pytest.mark.parametrize("kaputt", ["2026-05-01' OR 1=1 --", "gestern", "2026-13-40"])
def test_ungueltiges_datum_gelangt_nicht_in_die_abfrage(db, kaputt):
    t = db.get_timeline_stats("month", time_range="alles", von=kaputt)
    assert sum(t["applications"].values()) == 4


def test_punkte_klassen_ohne_falsche_zehn_plus(db):
    v = db.get_score_stats()["score_distribution"]
    assert v == {"0": 1, "1-3": 1, "10+": 1}


def test_dauer_nennt_ganze_tage_ohne_komma_null():
    text = dauer({"anzahl": 12, "median_tage": 4.0, "min_tage": 3.0, "max_tage": 9.0})["text"]
    assert text == "4 Tage (Median aus 12 Fällen, 3 bis 9 Tage)"


@pytest.fixture
def server(db):
    import bewerbungs_assistent.dashboard as dash

    dash._db = db
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
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


@pytest.fixture(scope="module")
def browser():
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def test_seite_ohne_widerspruch_mit_bezug_und_tabelle(server, browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="de-DE")
    page = ctx.new_page()
    try:
        page.goto(f"{server}/#statistiken", wait_until="domcontentloaded")
        karte = page.get_by_role("heading", name="Bewerbungen und neue Stellen im Zeitverlauf").locator("xpath=ancestor::*[.//details][1]")
        expect(karte).to_contain_text("gesamter Verlauf", timeout=20000)
        # Erst lesen, wenn die Uebersicht steht; ihr Satz zu nachgetragenen Bewerbungen nennt "Antwortzeit" zu Recht.
        expect(page.locator("[data-statistik-kern]")).to_contain_text("Meine Suche", timeout=20000)
        text = page.inner_text("body")
        for alt in ("Trefferquote", "Importiert", "Ø Antwortzeit", "Schnellste Antwort", "Diese Woche", "Outcome"):
            assert alt not in text, alt

        karte.get_by_text("Als Tabelle anzeigen").click()
        expect(karte.locator("table")).to_contain_text("Jul 26")

        with page.expect_response(lambda r: "/api/stats/timeline" in r.url and "from=2026-05-01" in r.url
                                  and "to=2026-05-31" in r.url):
            page.get_by_label("Zeitraum von").fill("01.05.2026")
            page.get_by_label("Zeitraum bis").fill("31.05.2026")
        expect(karte).to_contain_text("01.05.2026 bis 31.05.2026")
        expect(karte.locator("table")).not_to_contain_text("Jul 26")
        assert "opacity-60" not in (page.locator("#page-statistiken").get_attribute("class") or "")
    finally:
        ctx.close()


def test_handy_breite_ohne_waagerechtes_scrollen(server, browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="de-DE")
    page = ctx.new_page()
    try:
        page.goto(f"{server}/#statistiken", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Woher die Stellen kommen")).to_be_visible(timeout=20000)
        ueber = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert ueber <= 0, f"{ueber}px waagerecht zu breit"
    finally:
        ctx.close()
