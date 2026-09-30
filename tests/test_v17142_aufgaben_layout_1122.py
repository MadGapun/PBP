"""#1122 im Browser: der Aufgaben-Tab läuft nicht über den rechten Rand.

Beobachtung (29.09.2026, Dashboard v1.7.141, Elwosa-Leiste offen): „Die
Aufgaben haben noch weitere Optionen, das sehe ich gar nicht. Kein
Scrollbalken. Aber noch schlimmer, dass ich überhaupt scrollen muss.“ —
gemeint war das WAAGERECHTE Scrollen; senkrecht ist in Ordnung.

Der Beleg ist eine Messung am gebauten Bundle: die Seite ist nicht breiter
als das Fenster, und die Knöpfe jeder Zeile liegen im Sichtbereich, auch
mit einem 120 Zeichen langen Titel und einer Beschreibung ohne
Umbruchstelle. Das Bundle wird gebaut getestet (nach JSX-Änderungen neu
bauen: `cd frontend && pnpm exec vite build`).
"""
from __future__ import annotations

import os
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

LANGER_TITEL = ("PLM Dokumentenmanager & Prozessmanager (m/w/d) - Aufbau & "
                "Strukturierung bei einem Marineschiffbauer im Norden Deutschlands")
OHNE_UMBRUCH = ("Ansprechpartner: Vorname Nachname "
                "(vorname.nachname@sehr-langer-firmenname-ohne-umbruch.example.com)"
                " und die Kennung ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _tag(tage: int) -> str:
    return (date.today() + timedelta(days=tage)).isoformat()


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
    app = db.add_application({"title": LANGER_TITEL, "company": "Musterwerft Nord GmbH",
                              "status": "beworben", "applied_at": _tag(-20)})
    # Elf Einträge wie im Screenshot: sechs überfällig, der Rest verteilt.
    faellig = [-9, -8, -6, -4, -3, -1, 0, 2, 5, 12, 40]
    for i, tage in enumerate(faellig):
        db.add_task({"titel": LANGER_TITEL if i % 2 == 0 else f"Kurze Aufgabe {i}",
                     "beschreibung": OHNE_UMBRUCH, "typ": "custom",
                     "faellig_am": _tag(tage),
                     **({"application_id": app} if i % 3 == 0 else {})})
    db.add_follow_up(app, _tag(-2), "nachfass", template=OHNE_UMBRUCH)
    dash._db = db
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(dash.app, host="127.0.0.1", port=port,
                                        log_level="warning"))
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


def _aufgaben(browser, url, breite=1280):
    page = browser.new_page(viewport={"width": breite, "height": 900})
    page.goto(f"{url}/#aufgaben", wait_until="domcontentloaded", timeout=30000)
    # Auf den Zustand warten: die Überschrift der Gruppe, nicht auf Zeit.
    page.get_by_role("heading", name="Überfällig", exact=False).first.wait_for(timeout=20000)
    return page


MESSUNG = """() => {
  const fenster = document.documentElement.clientWidth;
  const main = document.querySelector('main');
  const zeilen = [...document.querySelectorAll('main div.group')];
  const rand = fenster;
  const ausserhalb = [];
  for (const z of zeilen) {
    for (const el of z.querySelectorAll('button, input[type=date]')) {
      const r = el.getBoundingClientRect();
      if (r.width && (r.right > rand + 0.5 || r.left < -0.5)) {
        ausserhalb.push((el.getAttribute('title') || el.getAttribute('aria-label') || el.tagName));
      }
    }
  }
  // Eine Beschreibung ohne Umbruchstelle wird an der Zeilenkante abgeschnitten
  // statt umgebrochen: der Text ist dann breiter als sein Kasten.
  const abgeschnitten = [...document.querySelectorAll('main p.line-clamp-2')]
    .filter((p) => p.scrollWidth > p.clientWidth + 1).length;
  return {
    fenster,
    seite: document.documentElement.scrollWidth,
    main: main.scrollWidth, mainSichtbar: main.clientWidth,
    zeilen: zeilen.length, ausserhalb, abgeschnitten,
  };
}"""


@pytest.mark.parametrize("breite", [1280, 1024])
def test_aufgaben_tab_laeuft_nicht_ueber_den_rand(browser, server, breite):
    url, _ = server
    page = _aufgaben(browser, url, breite)
    try:
        m = page.evaluate(MESSUNG)
        assert m["zeilen"] >= 11, m
        assert m["seite"] <= m["fenster"], f"Seite ist breiter als das Fenster: {m}"
        assert m["main"] <= m["mainSichtbar"], f"Inhalt breiter als der Bereich: {m}"
        assert m["ausserhalb"] == [], f"Knöpfe außerhalb des Sichtbereichs: {m}"
        assert m["abgeschnitten"] == 0, f"Beschreibung ohne Umbruch wird abgeschnitten: {m}"
    finally:
        page.close()


def test_aufgaben_tab_zeigt_die_knoepfe_jeder_zeile(browser, server):
    url, _ = server
    page = _aufgaben(browser, url)
    try:
        breite = page.viewport_size["width"]
        zeilen = page.locator("main div.group")
        for i in range(zeilen.count()):
            for titel in ("Verschieben", "Hinfällig (gegenstandslos geworden)"):
                # `is_visible` sagt nur „hat eine Größe“, nicht „liegt im
                # Fenster“ — deshalb die Lage.
                box = zeilen.nth(i).get_by_title(titel).bounding_box()
                assert box and box["x"] >= 0 and box["x"] + box["width"] <= breite, (i, titel, box)
    finally:
        page.close()


def test_langer_titel_bleibt_im_detail_erreichbar(browser, server):
    """Wer den Titel in der Zeile nicht ganz sieht, öffnet die Zeile."""
    url, _ = server
    page = _aufgaben(browser, url)
    try:
        page.locator("main div.group").first.locator("div.cursor-pointer").click()
        dialog = page.get_by_role("dialog")
        dialog.wait_for(state="visible", timeout=10000)
        assert "Aufbau & Strukturierung" in dialog.inner_text()
    finally:
        page.close()
