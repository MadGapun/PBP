"""#1171 Baustein 5 (G85): Listen zuerst — die erste Zeile jeder Liste liegt samt Hauptknopf im ersten Bildschirm.

Befund der Ist-Aufnahme (Issue #1171): vor der ersten Stelle lagen rund 900 px (vier Kennzahlkacheln, Hinweiskasten, Suchstand,
Filter, „Zuletzt aktualisiert“), bei den Bewerbungen waren es rund 600 px. Kennzahlen und Hinweis sind jetzt EINE Zeile
(`ListenUebersicht`), die auf Wunsch aufklappt; der Suchstand steht in ihr, die Filterkarten sind niedriger.

Gemessen wird im Browser gegen das GEBAUTE Bundle (nach JSX-Aenderungen neu bauen: `cd frontend && pnpm exec vite build`) bei den
zwei Fenstergroessen der Bedienungspruefung: 1366x768 (ein Laptop) und 1920x1080. Kein Quelltext-Grep — der haette nur belegt,
dass eine Zeichenkette dasteht.
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import urllib.request
from datetime import date, timedelta

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TEXT = ("Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse "
        "und begleiten die Einfuehrung eines neuen PLM-Systems. Ihr Profil: abgeschlossenes Studium. ") * 3
GROESSEN = [(1366, 768), (1920, 1080)]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post(url: str, pfad: str, daten: dict) -> dict:
    anfrage = urllib.request.Request(f"{url}{pfad}", data=json.dumps(daten).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(anfrage, timeout=10).read())


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("listen1171")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    for i in range(8):
        db.save_jobs([{"hash": f"l{i:03d}", "title": f"PLM Administrator {i} (m/w/d)", "company": f"Beispielwerk {i} GmbH",
                       "location": "Musterstadt", "url": f"https://karriere.beispiel-{i}.example/jobs/{i}",
                       "source": "stepstone", "description": TEXT, "score": 10 + i}])
    app_ids = [db.add_application({"title": f"Konstruktionsleiter {i}", "company": f"Seeblick {i} AG", "status": "beworben"})
               for i in range(4)]
    # EIN Entwurf: der Hinweis der Liste bekommt dadurch einen Knopf („Entwuerfe filtern“), der in der Zeile bleiben muss.
    db.add_application({"title": "Anlagenplaner", "company": "Entwurf Beispiel GmbH", "status": "entwurf"})
    for i in range(3):
        db.add_document({"filename": f"Anschreiben_Beispielwerk_{i}.pdf", "filepath": f"C:/beispiel/a{i}.pdf",
                         "doc_type": "anschreiben", "extracted_text": "Sehr geehrte Damen und Herren, hiermit bewerbe ich mich. " * 4})
    db.add_task({"application_id": app_ids[0], "titel": "Unterlagen nachreichen", "faellig_am": (date.today() + timedelta(days=3)).isoformat()})
    dash._db = db
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(dash.app, host="127.0.0.1", port=port, log_level="warning"))
    srv.install_signal_handlers = lambda: None
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{url}/api/status", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    for name in ("Erika Beispiel", "Max Muster", "Anna Probe"):
        _post(url, "/api/contacts", {"full_name": name, "company": "Beispielwerk GmbH", "tags": ["recruiter"]})
    yield {"url": url, "db": db}
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


def _seite(browser, url, route, breite, hoehe):
    ctx = browser.new_context(viewport={"width": breite, "height": hoehe})
    page = ctx.new_page()
    page.goto(f"{url}/#{route}", wait_until="load", timeout=30000)
    return ctx, page


# route -> (Haken der ersten Zeile, die Hauptknoepfe, die IN der Zeile liegen und mit ihr sichtbar sein muessen)
ZEILEN = {
    "stellen": ("[data-stellenkarte]", ["Bewerbung anlegen", "Passt nicht"]),
    "bewerbungen": ("[data-bewerbungskarte]", ["Timeline"]),
    "kontakte": ("[data-kontaktkarte]", []),
    "dokumente": ('[id^="dokument-"]', []),
    "aufgaben": ("[data-aufgabe-zur-bewerbung]", []),
}


@pytest.mark.parametrize("breite,hoehe", GROESSEN)
@pytest.mark.parametrize("route", list(ZEILEN))
def test_die_erste_zeile_liegt_samt_hauptknopf_im_ersten_bildschirm(browser, umgebung, route, breite, hoehe):
    haken, knoepfe = ZEILEN[route]
    ctx, page = _seite(browser, umgebung["url"], route, breite, hoehe)
    try:
        zeile = page.locator(haken).first
        zeile.wait_for(timeout=20000)
        page.wait_for_timeout(500)       # Hinweise und Zaehler kommen mit eigenen Anfragen
        box = zeile.bounding_box()
        assert box is not None
        assert box["y"] + box["height"] <= hoehe, (
            f"{route} bei {breite}x{hoehe}: die erste Zeile reicht bis y = {box['y'] + box['height']:.0f} — "
            f"unter die Falz ({hoehe}); man muesste scrollen, um den Hauptknopf zu erreichen")
        for name in knoepfe:
            knopf = zeile.get_by_role("button", name=name).first
            kb = knopf.bounding_box()
            assert kb is not None, f"{route}: der Knopf {name!r} fehlt in der ersten Zeile"
            assert kb["y"] + kb["height"] <= hoehe, f"{route} bei {breite}x{hoehe}: {name!r} liegt unter der Falz"
    finally:
        ctx.close()


@pytest.mark.parametrize("breite,hoehe", GROESSEN)
@pytest.mark.parametrize("route", list(ZEILEN))
def test_keine_liste_scrollt_seitwaerts(browser, umgebung, route, breite, hoehe):
    ctx, page = _seite(browser, umgebung["url"], route, breite, hoehe)
    try:
        page.locator(ZEILEN[route][0]).first.wait_for(timeout=20000)
        breiten = page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
        assert breiten[0] <= breiten[1] + 1, f"{route} bei {breite}: scrollt seitwaerts ({breiten})"
    finally:
        ctx.close()


@pytest.mark.parametrize("liste", ["stellen", "bewerbungen"])
def test_der_listenkopf_ist_zu_klappt_auf_und_merkt_sich_die_wahl(browser, umgebung, liste):
    ctx, page = _seite(browser, umgebung["url"], liste, 1366, 768)
    try:
        kopf = page.locator(f'[data-listen-uebersicht="{liste}"]')
        kopf.wait_for(timeout=20000)
        schalter = kopf.locator("[data-listen-uebersicht-schalter]")
        # Vorgabe: zu — die Liste beginnt im ersten Bildschirm
        assert kopf.get_attribute("data-offen") == "nein"
        assert page.locator("[data-listen-uebersicht-inhalt]").count() == 0
        assert schalter.get_attribute("aria-expanded") == "false"
        # ein Klick: Kennzahlen und Erklaerung stehen da
        schalter.click()
        assert kopf.get_attribute("data-offen") == "ja"
        assert page.locator("[data-listen-uebersicht-inhalt]").count() == 1
        assert schalter.get_attribute("aria-expanded") == "true"
        assert page.evaluate("(l) => window.localStorage.getItem('pbp-listenkopf-' + l)", liste) == "auf"
        # die Wahl ueberlebt ein Neuladen ...
        page.reload(wait_until="load")
        kopf.wait_for(timeout=20000)
        assert kopf.get_attribute("data-offen") == "ja"
        # ... und ein zweiter Klick klappt wieder zu
        kopf.locator("[data-listen-uebersicht-schalter]").click()
        assert kopf.get_attribute("data-offen") == "nein"
        assert page.evaluate("(l) => window.localStorage.getItem('pbp-listenkopf-' + l)", liste) == "zu"
    finally:
        ctx.close()


def test_der_suchstand_steht_in_der_zeile_des_listenkopfs(browser, umgebung):
    ctx, page = _seite(browser, umgebung["url"], "stellen", 1366, 768)
    try:
        status = page.locator('[data-listen-uebersicht="stellen"] [data-listen-uebersicht-status]')
        status.wait_for(timeout=20000)
        assert re.search(r"Noch nie gesucht|Aktualisiert|Jobsuche läuft", status.inner_text()), status.inner_text()
        # steht genau einmal da — keine eigene Zeile vor dem Kopf mehr
        assert page.get_by_text(re.compile(r"Noch nie gesucht|^Aktualisiert ")).count() == 1
        # „Zuletzt aktualisiert“ ist in der Filterkarte, also UEBER der ersten Stelle und nicht als eigene Zeile davor
        zuletzt = page.locator("[data-stellen-zuletzt]")
        assert zuletzt.count() == 1
        erste = page.locator("[data-stellenkarte]").first
        erste.wait_for(timeout=20000)
        assert zuletzt.bounding_box()["y"] + zuletzt.bounding_box()["height"] < erste.bounding_box()["y"]
        filterkarte = zuletzt.locator("xpath=ancestor::section[1]")
        assert filterkarte.locator("[data-filter-knopf]").count() == 1, "„Zuletzt aktualisiert“ gehoert in die Filterkarte"
    finally:
        ctx.close()


def test_der_eine_hinweis_mit_seinem_knopf_bleibt_in_der_zeile_wenn_der_kopf_zu_ist(browser, umgebung):
    ctx, page = _seite(browser, umgebung["url"], "bewerbungen", 1366, 768)
    try:
        kopf = page.locator('[data-listen-uebersicht="bewerbungen"]')
        kopf.wait_for(timeout=20000)
        assert kopf.get_attribute("data-offen") == "nein"
        knopf = kopf.get_by_role("button", name="Entwürfe filtern")
        knopf.wait_for(timeout=10000)
        assert knopf.is_visible()
        assert kopf.locator("[data-listen-uebersicht-titel]").inner_text().strip(), "der Hinweis braucht seinen Titel in der Zeile"
        # der Knopf wirkt: danach zeigt die Liste nur noch den Entwurf
        knopf.click()
        page.wait_for_function(
            "() => document.querySelectorAll('[data-bewerbungskarte]').length === 1", timeout=10000)
        assert "Anlagenplaner" in page.locator("[data-bewerbungskarte]").first.inner_text()
    finally:
        ctx.close()
