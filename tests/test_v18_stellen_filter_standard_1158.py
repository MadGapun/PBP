"""#1158 Punkt 5: die ausdrücklich gesetzte Voreinstellung der Filter in der Stellenliste.

Offen geblieben war aus dem Issue: „Der Nutzer legt fest, welche Filter beim Öffnen an sind.“ Die verbindliche Anforderung bleibt
unberührt: „Filter zurücksetzen“ zeigt ALLE offenen Stellen; die Voreinstellung ist etwas anderes und gilt nur beim Öffnen.

Geprüft: der Dienst (strenge Schlüssel und Typen, je Profil), die Endpunkte, und im Browser, dass die Liste mit der Voreinstellung
beginnt, der Zurücksetzen-Knopf trotzdem ALLES zeigt und ohne Voreinstellung der gemerkte Zustand gilt.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from bewerbungs_assistent.services import stellen_filter_standard as sfs

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def db(tmp_path):
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "filter.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    yield d
    d.close()


GUELTIG = {"hideApplied": True, "rahmenAusblenden": False, "schwelleAusblenden": False, "minScore": "-50", "sort": "score_desc"}


# ══ Dienst ═══════════════════════════════════════════════════════════════════════════════

def test_ohne_voreinstellung_ist_es_none(db):
    assert sfs.lesen(db) is None


def test_setzen_und_lesen(db):
    assert sfs.setzen(db, GUELTIG) == GUELTIG
    assert sfs.lesen(db) == GUELTIG


def test_loeschen_hebt_sie_auf(db):
    sfs.setzen(db, GUELTIG)
    sfs.loeschen(db)
    assert sfs.lesen(db) is None


def test_die_voreinstellung_gehoert_zum_profil(db):
    sfs.setzen(db, GUELTIG)
    erstes = db.get_active_profile_id()
    db.switch_profile(db.create_profile("Zweites"))
    assert sfs.lesen(db) is None, "ein anderes Profil sieht sie nicht"
    sfs.setzen(db, {"hideApplied": False})
    db.switch_profile(erstes)
    assert sfs.lesen(db) == GUELTIG


@pytest.mark.parametrize("daten", [None, [], "text", 5, {}])
def test_keine_filter_ist_keine_voreinstellung(db, daten):
    with pytest.raises(ValueError):
        sfs.setzen(db, daten)
    assert sfs.lesen(db) is None


@pytest.mark.parametrize("daten", [
    {"unbekannt": True},
    {"query": "suchtext"},          # der Suchtext wird nie festgehalten
    {"view": "dismissed"},          # die Ansicht auch nicht
    {"hideApplied": "ja"},
    {"hideApplied": 1},
    {"minScore": 5},                # Text erwartet
    {"minScore": "viel"},
    {"minScore": "1e3"},
    {"source": "x" * 101},
    {"source": "a\nb"},
    {"salaryOnly": None},
])
def test_unbekannte_schluessel_und_falsche_typen_werden_abgelehnt(db, daten):
    with pytest.raises(ValueError):
        sfs.setzen(db, daten)
    assert sfs.lesen(db) is None


@pytest.mark.parametrize("wert", ["", "0", "-100", "12.5", "12,5", "5"])
def test_mindestpunkte_nehmen_auch_null_negative_werte_und_leer(db, wert):
    assert sfs.setzen(db, {"minScore": wert}) == {"minScore": wert}


def test_ein_kaputter_gespeicherter_eintrag_gilt_als_keine_voreinstellung(db):
    db.set_profile_setting(sfs.EINSTELLUNG, {"unbekannt": 1})
    assert sfs.lesen(db) is None
    db.set_profile_setting(sfs.EINSTELLUNG, "kaputt")
    assert sfs.lesen(db) is None


# ══ Endpunkte ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def client(db):
    import bewerbungs_assistent.dashboard as dash
    alt = dash._db
    dash._db = db
    from fastapi.testclient import TestClient
    yield TestClient(dash.app)
    dash._db = alt


def test_die_endpunkte(client, db):
    assert client.get("/api/stellen-filter-standard").json() == {"standard": None}
    r = client.put("/api/stellen-filter-standard", json={"standard": GUELTIG})
    assert r.status_code == 200 and r.json() == {"standard": GUELTIG}
    assert client.get("/api/stellen-filter-standard").json() == {"standard": GUELTIG}
    assert client.delete("/api/stellen-filter-standard").json() == {"standard": None}
    assert client.get("/api/stellen-filter-standard").json() == {"standard": None}


def test_der_endpunkt_lehnt_falsches_mit_400_ab(client):
    for body in ({"standard": {"unbekannt": 1}}, {"standard": {"hideApplied": "ja"}}, {"standard": {}}, {}):
        r = client.put("/api/stellen-filter-standard", json=body)
        assert r.status_code == 400 and r.json()["error"], body
    assert client.get("/api/stellen-filter-standard").json() == {"standard": None}


# ══ Browser ═══════════════════════════════════════════════════════════════════════════════

pytest.importorskip("playwright.sync_api")
import uvicorn  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("filter1158")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    d = Database(db_path=tmp / "test.db")
    d.initialize()
    assert str(tmp) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    # drei offene Stellen mit Staenden 100, 10 und -30: mit „Punkte ab 50“ fehlen zwei, und der Streifen sagt es
    for nr, punkte in ((1, 100), (2, 10), (3, -30)):
        d.save_jobs([{"hash": f"f1158-{nr}", "title": f"Planungsstelle {nr}", "company": f"Beispiel {nr} GmbH",
                      "url": f"https://example.com/f1158-{nr}", "source": "manuell", "description": "Aufgaben und Anforderungen. " * 6,
                      "score": punkte}])
    dash._db = d
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
    yield {"url": f"http://127.0.0.1:{port}", "db": d}
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    d.close()
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


def _filter_state(page):
    """Der Filterzustand, den die Seite im Browser merkt."""
    import json
    roh = page.evaluate("() => window.localStorage.getItem('pbp-stellen-filter-v1')")
    return json.loads(roh) if roh else None


def _seite(browser, umgebung, *, vorher_speicher=None):
    ctx = browser.new_context(viewport={"width": 1500, "height": 950})
    page = ctx.new_page()
    if vorher_speicher is not None:
        page.add_init_script(f"window.localStorage.setItem('pbp-stellen-filter-v1', {vorher_speicher!r});")
    page.goto(f"{umgebung['url']}/#stellen", wait_until="load", timeout=30000)
    knopf = page.locator("[data-filter-knopf]")
    knopf.wait_for(timeout=30000)
    if knopf.get_attribute("aria-expanded") != "true":
        knopf.click()
    page.locator("[data-filter-voreinstellung]").wait_for(timeout=15000)
    return ctx, page


def test_ohne_voreinstellung_gilt_der_gemerkte_zustand_und_sie_laesst_sich_speichern(browser, umgebung):
    d = umgebung["db"]
    sfs.loeschen(d)
    ctx, page = _seite(browser, umgebung, vorher_speicher='{"hideApplied": false, "rahmenAusblenden": true}')
    try:
        feld = page.locator("[data-filter-voreinstellung]")
        assert "Ohne Voreinstellung gilt beim Öffnen, wie du die Liste verlassen hast" in feld.inner_text()
        assert feld.get_by_role("button", name="Als Voreinstellung speichern").count() == 1
        assert feld.get_by_role("button", name="Voreinstellung aufheben").count() == 0
        assert _filter_state(page)["rahmenAusblenden"] is True, "der gemerkte Zustand gilt"
        feld.get_by_role("button", name="Als Voreinstellung speichern").click()
        for _ in range(50):
            if sfs.lesen(d):
                break
            page.wait_for_timeout(200)
        gespeichert = sfs.lesen(d)
        assert gespeichert and gespeichert["rahmenAusblenden"] is True and gespeichert["hideApplied"] is False
        assert "query" not in gespeichert and "view" not in gespeichert
        page.get_by_text("Gemerkt: Beim Öffnen von PBP gelten diese Filter.").first.wait_for(timeout=10000)
        assert "Beim Öffnen von PBP gilt deine Voreinstellung" in feld.inner_text()
        assert feld.get_by_role("button", name="Voreinstellung aufheben").count() == 1
        assert feld.get_by_role("button", name="Als Voreinstellung speichern").count() == 0, "sie gilt ja gerade"
    finally:
        ctx.close()


def test_mit_voreinstellung_beginnt_jedes_oeffnen_damit_nicht_mit_dem_gemerkten_zustand(browser, umgebung):
    d = umgebung["db"]
    sfs.setzen(d, {"hideApplied": True, "rahmenAusblenden": False, "schwelleAusblenden": False, "minScore": "-5"})
    # der Browser erinnert sich an etwas ANDERES (Rahmenfilter an, Punkte 99): die Voreinstellung geht vor
    ctx, page = _seite(browser, umgebung, vorher_speicher='{"rahmenAusblenden": true, "minScore": "99", "hideApplied": false}')
    try:
        page.wait_for_function(
            "() => JSON.parse(window.localStorage.getItem('pbp-stellen-filter-v1')||'{}').minScore === '-5'", timeout=15000)
        zustand = _filter_state(page)
        assert zustand["minScore"] == "-5" and zustand["rahmenAusblenden"] is False and zustand["hideApplied"] is True
        feld = page.locator("[data-filter-voreinstellung]")
        assert "Beim Öffnen von PBP gilt deine Voreinstellung" in feld.inner_text()
        assert feld.get_by_role("button", name="Zur Voreinstellung").count() == 0, "es gilt ja gerade die Voreinstellung"
    finally:
        ctx.close()


def test_filter_zuruecksetzen_bleibt_keine_einschraenkung_auch_mit_voreinstellung(browser, umgebung):
    """Die verbindliche Anforderung des Issues: zuruecksetzen zeigt ALLES; die Voreinstellung bleibt gespeichert."""
    d = umgebung["db"]
    sfs.setzen(d, {"hideApplied": True, "minScore": "50"})
    ctx, page = _seite(browser, umgebung)
    try:
        page.wait_for_function(
            "() => JSON.parse(window.localStorage.getItem('pbp-stellen-filter-v1')||'{}').minScore === '50'", timeout=15000)
        page.get_by_role("button", name="Filter zurücksetzen").first.wait_for(timeout=20000)
        assert "2 Stellen sind durch Filter ausgeblendet" in page.locator("body").inner_text()
        page.get_by_role("button", name="Filter zurücksetzen").first.click()
        page.wait_for_function(
            "() => JSON.parse(window.localStorage.getItem('pbp-stellen-filter-v1')||'{}').minScore === ''", timeout=15000)
        assert sfs.lesen(d)["minScore"] == "50", "die Voreinstellung bleibt, wie sie war"
        # und der Weg zurueck ist ein Klick
        page.locator("[data-filter-voreinstellung]").get_by_role("button", name="Zur Voreinstellung").click()
        page.wait_for_function(
            "() => JSON.parse(window.localStorage.getItem('pbp-stellen-filter-v1')||'{}').minScore === '50'", timeout=15000)
    finally:
        ctx.close()


def test_aufheben_loescht_sie_auf_dem_server(browser, umgebung):
    d = umgebung["db"]
    sfs.setzen(d, {"hideApplied": True})
    ctx, page = _seite(browser, umgebung)
    try:
        feld = page.locator("[data-filter-voreinstellung]")
        feld.get_by_role("button", name="Voreinstellung aufheben").click()
        for _ in range(50):
            if sfs.lesen(d) is None:
                break
            page.wait_for_timeout(200)
        assert sfs.lesen(d) is None
        assert "Ohne Voreinstellung" in feld.inner_text()
    finally:
        ctx.close()


def test_der_wechsel_zwischen_seiten_nimmt_den_zustand_der_sitzung_nicht_zurueck(browser, umgebung):
    """Die Voreinstellung gilt beim OEFFNEN von PBP, nicht bei jedem Betreten der Seite: wer innerhalb einer Sitzung einen
    Filter aendert, wegblaettert und zurueckkommt, findet seinen Zustand vor."""
    d = umgebung["db"]
    sfs.setzen(d, {"hideApplied": True, "minScore": "50"})
    ctx, page = _seite(browser, umgebung)
    try:
        page.wait_for_function(
            "() => JSON.parse(window.localStorage.getItem('pbp-stellen-filter-v1')||'{}').minScore === '50'", timeout=15000)
        page.get_by_role("button", name="Filter zurücksetzen").first.wait_for(timeout=20000)
        page.get_by_role("button", name="Filter zurücksetzen").first.click()
        page.wait_for_function(
            "() => JSON.parse(window.localStorage.getItem('pbp-stellen-filter-v1')||'{}').minScore === ''", timeout=15000)
        page.locator("button[data-page=dashboard]").click()
        page.wait_for_timeout(500)
        page.locator("button[data-page=stellen]").click()
        page.locator("[data-filter-knopf]").wait_for(timeout=15000)
        page.wait_for_timeout(1500)
        assert _filter_state(page)["minScore"] == "", "die Voreinstellung wird nicht beim Seitenwechsel erneut angewendet"
        assert sfs.lesen(d)["minScore"] == "50"
    finally:
        ctx.close()


def test_die_regeln_gelten_auch_im_node_test():
    """`lib/stellenFilter.js` hat einen Node-Test (in der CI ein eigener Schritt); er laeuft hier mit, damit auch die Gegenprobe ihn
    kennt und eine Regel nicht unbemerkt kippt, weil keine Browser-Szene sie beruehrt."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node nicht verfuegbar")
    r = subprocess.run([node, str(REPO / "frontend" / "src" / "lib" / "stellenFilter.test.mjs")], capture_output=True, text=True,
                       timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert r.returncode == 0, (r.stdout[-600:], r.stderr[-600:])


def test_die_seite_wartet_mit_der_ersten_liste_auf_die_voreinstellung():
    quelle = (REPO / "frontend" / "src" / "pages" / "JobsPage.jsx").read_text(encoding="utf-8-sig")
    assert "if (!voreinstellungBereit) return;" in quelle
    assert "[reloadKey, voreinstellungBereit]" in quelle
    assert "voreinstellungSchonAngewendet" in quelle
