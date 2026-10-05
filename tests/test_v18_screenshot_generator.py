"""Praxisprobe 1.8 (05.10.2026), Teil Schaufenster: das Titelbild des Wikis zeigte die Fehlerkarte „Dieser Bereich ist abgestürzt“.

`docs/screenshots/00c_dashboard_vollstaendig.png` (Wiki-Start, „Erste Schritte“, README) stammt aus dem Lauf zu v1.7.137 und
zeigt „Failed to execute 'removeChild' on 'Node'“. Ursache war der Generator, nicht die Anwendung: `_dismiss_toasts` löschte mit
`el.remove()` alles mit `[role="status"]` — darunter den Hinweis „Claude Desktop ist nicht verbunden“, einen Knoten, den React
verwaltet. Wechselte der Zustand danach auf „verbunden“, wollte React den Knoten entfernen, der schon fort war, und stürzte ab.
Der Generator speicherte das Bild, ohne hinzusehen.

Diese Tests stellen den Ablauf nach: Hinweis steht da → Toast-Aufräumen → Verbindung kommt. Die Gegenprobe führt die ALTE
Anweisung aus und verlangt, dass sie abstürzt — sonst bewiese der Test nichts.
"""
import importlib.util
import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:
    PlaywrightError = Exception
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
ABSTURZ = "Dieser Bereich ist abgestürzt"
ALTE_ANWEISUNG = """
    document.querySelectorAll('[class*="toast"], [class*="Toast"], [role="alert"], [role="status"]')
        .forEach(el => el.remove());
"""


def _generator():
    spec = importlib.util.spec_from_file_location("generate_screenshots_pp7", ROOT / "docs" / "screenshots" / "generate_screenshots.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database, get_data_dir
    import bewerbungs_assistent.dashboard as dash
    gen = _generator()

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    assert str(tmp_path) in str(get_data_dir()), f"Datenordner nicht isoliert: {get_data_dir()}"
    gen.musterprofile.seed_all(db)
    dash._db = db
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(dash.app, host="127.0.0.1", port=port, log_level="warning"))
    srv.install_signal_handlers = lambda: None
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(300):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}", db, gen
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture(scope="module")
def browser():
    if sync_playwright is None:
        pytest.skip("Playwright nicht installiert")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def _aenderung(db) -> None:
    """Eine Änderung, die das Token der Live-Aktualisierung bewegt (Anzahl der Stellen) — die Seite fragt dann den Status neu ab.
    Einstellungen zählen NICHT zum Token; mit `set_setting` kam der Wechsel nur zufällig an."""
    db.save_jobs([{"hash": f"pp7{time.time_ns()}", "title": "Sachbearbeitung Einkauf", "company": "Musterbetrieb GmbH",
                   "url": f"https://example.com/pp7/{time.time_ns()}", "source": "manuell",
                   "description": "Aufgaben: Disposition und Bestellabwicklung. " * 3, "score": 1}])


def _zone(page):
    """Die Kennung des Hinweises, den die Seite gerade zeigt (None: keiner, oder der Knoten wurde von außen aus dem Baum genommen)."""
    el = page.locator("[data-hinweiszone]")
    return el.first.get_attribute("data-hinweiszone") if el.count() else None


class _Verkehr:
    """Merkt sich, wann die Seite zuletzt Daten bekommen hat und ob der Takt der Live-Aktualisierung schon lief.

    Der Hinweis „Claude Desktop ist nicht verbunden“ erscheint nach 0,3 Sekunden, noch bevor die Seite fertig geladen hat. Wer jetzt
    schon in den Baum greift, erwischt sie mitten im Aufbau: der Wechsel kam dann in rund jedem zehnten Lauf nie an (die Seite hielt
    ihren Stand, die Änderung ging am noch nicht gesetzten Ausgangswert des Takts vorbei), und es gab keinen Absturz zu sehen."""

    def __init__(self, page):
        self.letzte = time.monotonic()
        self.takt = 0
        page.on("response", self._antwort)

    def _antwort(self, r):
        if "/api/" not in r.url:
            return
        if "live-update-token" in r.url:
            self.takt += 1
        else:
            self.letzte = time.monotonic()

    def abwarten(self, page, stille=1.5, hoechstens=30):
        """Ruhig heißt: der Takt lief mindestens zweimal (der Ausgangswert steht), und seit `stille` Sekunden kam nichts Neues."""
        ende = time.monotonic() + hoechstens
        while time.monotonic() < ende:
            if self.takt >= 2 and time.monotonic() - self.letzte >= stille:
                return
            page.wait_for_timeout(200)             # lässt Playwright die Antworten einsammeln (time.sleep täte das nicht)
        raise AssertionError("die Seite wurde nicht ruhig: sie lädt weiter")


def _bis(ziel, db, sekunden=60):
    """Ruft `ziel()` auf, bis es etwas anderes als None liefert, und bewegt dabei alle drei Sekunden den Bestand.

    Die Seite fragt nur nach, wenn sich der Bestand bewegt hat (Token der Live-Aktualisierung). Kam die EINE Änderung zu früh, noch vor
    dem Herzschlag, sah das Dashboard den Wechsel nie (Seitenleiste und Dashboard fragen unabhängig voneinander): der Test war in
    jedem dritten Lauf rot. Jetzt kommt alle drei Sekunden eine neue Änderung, bis das Ziel erreicht ist.
    """
    ende = time.monotonic() + sekunden
    naechste = 0.0
    while time.monotonic() < ende:
        ergebnis = ziel()
        if ergebnis is not None:
            return ergebnis
        if time.monotonic() >= naechste:
            _aenderung(db)
            naechste = time.monotonic() + 3
        time.sleep(0.25)
    return None


def _ablauf(browser, url, db, aufraeumen) -> str:
    """Hinweis steht da → aufräumen → die Verbindung kommt. Rückgabe: 'abgestuerzt' oder 'ok'."""
    from bewerbungs_assistent import heartbeat
    page = browser.new_page(viewport={"width": 1280, "height": 900}, color_scheme="light")
    fehler = []
    page.on("pageerror", lambda e: fehler.append(str(e)))

    def _abgestuerzt() -> bool:
        # entweder die Fehlerkarte oder ein ungefangener Fehler von React („removeChild“)
        return bool(page.get_by_text(ABSTURZ).count()) or any("removeChild" in f for f in fehler)

    def _ziel():
        if _abgestuerzt():
            return "abgestuerzt"
        # „ok“ heißt: die Seitenleiste zeigt „verbunden“ UND das Dashboard hat den Hinweis „verbindung“ übernommen (weg oder ein anderer).
        # Beim Aufräumen von außen (alte Anweisung) ist der Knoten schon aus dem Baum; dann gilt allein der Absturz.
        if page.get_by_text("Claude Desktop: verbunden").count() and vorher == "verbindung" and _zone(page) != "verbindung":
            time.sleep(2)                           # dem Wechsel Zeit lassen, einen Knoten zu entfernen, den es nicht mehr gibt
            return "abgestuerzt" if _abgestuerzt() else "ok"
        return None

    verkehr = _Verkehr(page)
    try:
        page.goto(url + "/#dashboard")
        page.wait_for_selector("text=Claude Desktop ist nicht verbunden", timeout=60000)
        verkehr.abwarten(page)
        aufraeumen(page)
        vorher = "verbindung" if _zone(page) == "verbindung" else None
        # Jetzt „verbindet“ sich Claude: frischer Herzschlag, dazu Änderungen, die die Seite zum Nachfragen bringen
        heartbeat._write_heartbeat_file("pp7", is_alive=False)
        ergebnis = _bis(_ziel, db)
        if ergebnis is None:
            raise AssertionError(f"die Seite hat den Verbindungswechsel nicht übernommen; Fehler: {fehler[:2]}")
        return ergebnis
    finally:
        page.close()


def test_pp7_das_aufraeumen_des_generators_laesst_react_in_ruhe(server, browser):
    url, db, gen = server
    assert _ablauf(browser, url, db, gen._dismiss_toasts) == "ok"


def test_pp7_gegenprobe_die_alte_anweisung_stuerzt_die_seite_ab(server, browser):
    url, db, _ = server
    ergebnis = _ablauf(browser, url, db, lambda page: page.evaluate(ALTE_ANWEISUNG))
    assert ergebnis == "abgestuerzt", "der Test stellt die Ursache nicht nach — dann beweist er nichts"


def test_pp7_der_generator_speichert_kein_bild_einer_abgestuerzten_seite(server, browser):
    url, db, gen = server
    from bewerbungs_assistent import heartbeat
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    fehler = []
    page.on("pageerror", lambda e: fehler.append(str(e)))
    verkehr = _Verkehr(page)
    try:
        page.goto(url + "/#dashboard")
        page.wait_for_selector("text=Claude Desktop ist nicht verbunden", timeout=60000)
        verkehr.abwarten(page)
        # Absturz absichtlich herbeiführen: den React-Knoten selbst entfernen und den Zustand wechseln lassen
        page.evaluate(ALTE_ANWEISUNG)
        heartbeat._write_heartbeat_file("pp7", is_alive=False)
        abgestuerzt = _bis(lambda: True if (page.get_by_text(ABSTURZ).count() or any("removeChild" in f for f in fehler)) else None, db)
        assert abgestuerzt, "der Absturz ließ sich nicht herbeiführen"
        time.sleep(1)                       # die Seite setzt sich (Karte oder leerer Baum), bevor der Generator hinsieht
        # Jede Aufnahme des Generators läuft über _dismiss_toasts — dort sitzt die Prüfung
        with pytest.raises(RuntimeError, match="abgestuerzt"):
            gen._dismiss_toasts(page)
        with pytest.raises(RuntimeError, match="abgestuerzt"):
            gen._pruefe_kein_absturz(page)
    finally:
        page.close()


def test_pp7_kein_bild_im_repo_zeigt_die_fehlerkarte():
    """Die Fehlerkarte hat einen grauen Block (194,196,199) mit roter Schrift; er füllt dort rund 27.000 Pixel. Der Wert für
    ein gesundes Bild liegt unter 300 (Schriftkanten, Rahmen)."""
    from PIL import Image
    ziel = (194, 196, 199)
    gefunden = {}
    for png in sorted((ROOT / "docs" / "screenshots").glob("*.png")):
        bild = Image.open(png).convert("RGB")
        farben = bild.getcolors(maxcolors=bild.width * bild.height) or []      # (Anzahl, Farbe); getdata() ist veraltet (Pillow 14)
        gefunden[png.name] = sum(n for n, p in farben if abs(p[0] - ziel[0]) + abs(p[1] - ziel[1]) + abs(p[2] - ziel[2]) <= 6)
    assert gefunden, "keine Screenshots gefunden"
    schlecht = {n: z for n, z in gefunden.items() if z > 5000}
    assert not schlecht, f"zeigt die Fehlerkarte: {schlecht}"
