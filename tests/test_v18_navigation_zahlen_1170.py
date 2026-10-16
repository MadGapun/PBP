"""#1170 U17: eine Navigation in den Einstellungen, und das Wort hinter der Zahl in der Seitenleiste.

Befund der Bedienungsprüfung: „Einstellungen hat zwei Navigationen (Reiter oben, Unterpunkte links) mit je 16 Einträgen, die
Reiterzeile bricht um. Die orangen Zahlen in der Seitenleiste (Profil 4 bis 6, Stellen 2, Einstellungen 1) bedeuten Verschiedenes
(offene Lücken, Anzahl, Warnung) und erklären sich nur per Hover.“

Gesehen am Bild: die 16 Unterpunkte füllten die Seitenleiste bis zum unteren Rand, der Elwosa-Chat darunter verschwand, und nichts
zeigte, welcher Reiter gerade offen ist. Jetzt führen die Reiter der Seite (Grundlagen vorn, Erweitert dahinter, der gewählte
markiert); der Pfad oben nennt den Reiter. Die Zahl in der Seitenleiste trägt ihr Wort („8 Lücken“, „143 aktiv“, „2 fällig“,
„1 Hinweis“) — der Hover-Titel bleibt.
"""
from __future__ import annotations

import os
import re
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

from bewerbungs_assistent.services import workspace_service as ws

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend" / "src"


# ══ Das Wort hinter der Zahl: Server ═══════════════════════════════════════════════════════════════════════

def test_das_wort_steht_nur_wo_es_eine_zahl_gibt():
    assert ws._badge_kurz(0, 0, 0, 0) == {}
    assert ws._badge_kurz(12, 0, 0, 0) == {"stellen": "aktiv"}
    assert ws._badge_kurz(0, 3, 0, 0) == {"bewerbungen": "fällig"}
    assert ws._badge_kurz(0, 0, 0, 5) == {"profil": "Lücken"}
    assert ws._badge_kurz(0, 0, 1, 0) == {"einstellungen": "Hinweis"}


def test_einzahl_und_mehrzahl():
    assert ws._badge_kurz(0, 0, 0, 1)["profil"] == "Lücke"
    assert ws._badge_kurz(0, 0, 0, 2)["profil"] == "Lücken"
    assert ws._badge_kurz(0, 0, 1, 0)["einstellungen"] == "Hinweis"
    assert ws._badge_kurz(0, 0, 2, 0)["einstellungen"] == "Hinweise"


def _summary(jobs=0, faellig=0, quellen=1, suche="ok", fehlend=()):
    profil = {"personal_data": {"name": "Erika Musterfrau"}} if fehlend is not None else None
    return ws.build_workspace_summary(
        profile=profil,
        jobs=[{"hash": f"j{i}", "score": 1, "description": "x" * 80} for i in range(jobs)],
        applications=[],
        source_summary={"active": quellen, "total": 5},
        search_status={"status": suche},
        follow_up_summary={"total": faellig, "due": faellig},
    )


def test_jedes_wort_gehoert_zu_einer_zahl_und_jede_zahl_hat_ihr_wort():
    """Eine Zahl ohne Wort waere der Befund selbst, ein Wort ohne Zahl ein Rest."""
    for fall in (_summary(jobs=7, faellig=2, quellen=0), _summary(jobs=0, faellig=0, quellen=3, suche="dringend"),
                 _summary(jobs=1, faellig=0, quellen=2)):
        nav = fall["navigation"]
        zahlen = {k for k, v in {"profil": nav["profile_badge"], "stellen": nav["jobs_badge"],
                                 "bewerbungen": nav["applications_badge"], "einstellungen": nav["settings_badge"]}.items() if v}
        assert set(nav["kurz"]) == zahlen, (nav, zahlen)


def test_die_zahlen_selbst_sind_unveraendert_und_der_titel_bleibt():
    nav = _summary(jobs=7, faellig=2, quellen=0)["navigation"]
    assert nav["jobs_badge"] == "7" and nav["applications_badge"] == "2" and nav["settings_badge"] == "1"
    assert nav["kurz"]["stellen"] == "aktiv" and nav["kurz"]["bewerbungen"] == "fällig"
    assert "warten" in nav["titel"]["stellen"] and "fällig" in nav["titel"]["bewerbungen"]


# ══ Eine Navigation: Quelltext ═════════════════════════════════════════════════════════════════════════════

def test_die_seitenleiste_fuehrt_keine_unterpunkte_der_einstellungen_mehr():
    app = (FRONTEND / "App.jsx").read_text(encoding="utf-8-sig")
    block = app[app.index('page === "einstellungen"'):]
    block = block[:block.index('page === "kontakte"')]
    assert "sidebarSubNavigation = null;" in block
    assert "SETTINGS_REITER.map" not in block


def test_die_seite_meldet_ihren_reiter_ueber_den_kontext():
    """Ein Ereignis ginge beim ersten Zeichnen verloren: Kind-Effekte laufen vor denen der App."""
    seite = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    app = (FRONTEND / "App.jsx").read_text(encoding="utf-8-sig")
    assert "setSubPath?.(SETTINGS_REITER.find" in seite
    assert "setSubPath: setCurrentSubPath," in app
    assert "settings-tab-aktiv" not in seite + app
    # der Sprung von aussen (Elwosa, Hinweise) bleibt: derselbe Weg wie bisher
    assert 'addEventListener("settings-nav"' in seite


# ══ Im Browser ═════════════════════════════════════════════════════════════════════════════════════════════

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TEXT = ("Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse "
        "und begleiten die Einfuehrung eines neuen PLM-Systems. Ihr Profil: abgeschlossenes Studium.")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("navigation1170")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    for i in range(3):
        db.save_jobs([{"hash": f"n{i:03d}", "title": f"PLM Administrator {i} (m/w/d)", "company": f"Beispielwerk {i} GmbH",
                       "location": "Musterstadt", "url": f"https://karriere.beispiel-{i}.example/jobs/{i}",
                       "source": "stepstone", "description": TEXT, "score": 10 + i}])
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


def _warte(bedingung, sekunden=10):
    ende = time.time() + sekunden
    while time.time() < ende:
        if bedingung():
            return True
        time.sleep(0.1)
    return False


def test_in_den_einstellungen_gibt_es_eine_navigation_und_der_pfad_nennt_den_reiter(browser, umgebung):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#einstellungen", wait_until="load", timeout=30000)
        page.locator("[data-settings-reiter]").wait_for(timeout=20000)
        seitenleiste = page.locator("aside[aria-label='Hauptnavigation'] nav")
        # keine eingerueckte Unterliste unter "Einstellungen"
        assert seitenleiste.locator("ul ul").count() == 0, "die Seitenleiste fuehrt wieder Unterpunkte"
        assert "Erscheinungsbild" not in " ".join(seitenleiste.inner_text().split())
        # der Reiter der Seite ist markiert, und der Pfad oben nennt ihn
        assert _warte(lambda: "Quellen" in page.locator("header").inner_text())
        page.locator("[data-settings-reiter]").get_by_role("button", name="Erscheinungsbild", exact=True).click()
        assert _warte(lambda: "Erscheinungsbild" in page.locator("header").inner_text()), page.locator("header").inner_text()
        assert page.locator("[data-settings-reiter]").get_by_role("button", name="Erscheinungsbild", exact=True) \
            .get_attribute("aria-pressed") == "true"
        # ein Reiter aus "Erweitert": die Gruppe klappt auf, der Pfad folgt
        page.locator("[data-erweitert-schalter]").click()
        page.locator("[data-erweitert-reiter]").get_by_role("button", name="Updates", exact=True).click()
        assert _warte(lambda: "Updates" in page.locator("header").inner_text()), page.locator("header").inner_text()
    finally:
        ctx.close()


def test_der_elwosa_chat_bleibt_auch_in_den_einstellungen_im_bild(browser, umgebung):
    """Die 16 Unterpunkte fuellten die Seitenleiste bis zum unteren Rand; der Chat darunter hatte keine Hoehe mehr."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#einstellungen", wait_until="load", timeout=30000)
        page.locator("[data-settings-reiter]").wait_for(timeout=20000)
        page.wait_for_timeout(800)
        nav_unten = page.evaluate("document.querySelector(\"aside[aria-label='Hauptnavigation'] nav\").getBoundingClientRect().bottom")
        assert nav_unten < 640, f"die Navigation reicht bis y = {nav_unten:.0f} - darunter bleibt kein Platz fuer den Chat"
    finally:
        ctx.close()


def test_die_zahl_in_der_seitenleiste_traegt_ihr_wort(browser, umgebung):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#dashboard", wait_until="load", timeout=30000)
        page.locator("#tab-badge-stellen").wait_for(timeout=20000)
        stellen = page.locator("[data-tab-badge-gruppe='stellen']")
        assert _warte(lambda: " ".join(stellen.inner_text().split()) == "3 aktiv"), stellen.inner_text()
        # die Zahl selbst bleibt eine Zahl (Bestandsvertrag: `#tab-badge-<seite>`)
        assert page.locator("#tab-badge-stellen").inner_text().strip() == "3"
        profil = page.locator("[data-tab-badge-gruppe='profil']")
        assert _warte(lambda: re.fullmatch(r"\d+ Lücken?", " ".join(profil.inner_text().split())) is not None), profil.inner_text()
    finally:
        ctx.close()
