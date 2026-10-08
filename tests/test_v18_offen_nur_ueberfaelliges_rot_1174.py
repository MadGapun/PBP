"""Dashboard › Offen: rot ist nur, was überfällig ist (#1174, G87).

Der Nutzer (07.10.2026, Beta 17): „Das ‚Offen‘ ist warnungsrot. Das wurde wahrscheinlich so übernommen, als wir die verschiedenen
Todo- und Offene-Punkte-Listen zusammengefasst haben. Eigentlich möchte ich nur die Überfälligen rot hervorgehoben haben und die
anderen normal.“

Ursache: `OffenBlock` färbte Rahmen, Hintergrund und Symbol der GANZEN Karte coral, sobald auch nur eine Zeile überfällig war
(`dringend`). Seit v1.7.31 (auch Stable). Jetzt bleibt die Karte ruhig; rot sind die Überschrift „Überfällig“ und das Datum ihrer
Zeilen. „Heute“ und „Diese Woche“ sind unverändert.

Die Farben werden als BERECHNETE Werte im gebauten Bundle geprüft, nicht als Klassennamen: ein Klassenname sagt nicht, was der
Mensch sieht. Als Maßstab dienen Sonden mit den Token-Klassen (`text-coral`, `text-muted`, `text-ink`).

Das gebaute Bundle wird getestet (nach JSX-Änderungen neu bauen: `cd frontend && pnpm exec vite build`).
"""
from __future__ import annotations

import os
import re
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
FRONTEND = REPO / "frontend" / "src"


def _tag(tage: int) -> str:
    return (date.today() + timedelta(days=tage)).isoformat()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _server(tmp_path, *, ueberfaellig: bool):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    app = db.add_application({"title": "Disponent Lager", "company": "Beispiel AG", "status": "beworben", "applied_at": _tag(-20)})
    if ueberfaellig:
        db.add_task({"titel": "Zeugnis anfordern", "typ": "custom", "faellig_am": _tag(-1), "application_id": app})
    db.add_task({"titel": "Unterlagen heraussuchen", "typ": "custom", "faellig_am": _tag(0), "application_id": app})
    db.add_follow_up(app, _tag(3), "nachfass")
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
    return db, dash, srv, t, f"http://127.0.0.1:{port}"


def _abbauen(db, dash, srv, t):
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def mit_ueberfaelligem(tmp_path):
    db, dash, srv, t, url = _server(tmp_path, ueberfaellig=True)
    yield url
    _abbauen(db, dash, srv, t)


@pytest.fixture
def ohne_ueberfaelliges(tmp_path):
    db, dash, srv, t, url = _server(tmp_path, ueberfaellig=False)
    yield url
    _abbauen(db, dash, srv, t)


@pytest.fixture(scope="module")
def browser():
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


FARBEN_JS = """() => {
  const sonde = (klasse) => { const e = document.createElement('span'); e.className = klasse; document.body.appendChild(e);
                              const f = getComputedStyle(e).color; e.remove(); return f; };
  const farbe = (sel) => { const e = document.querySelector(sel); return e ? getComputedStyle(e).color : null; };
  const alle = (sel) => [...document.querySelectorAll(sel)].map((e) => getComputedStyle(e).color);
  const karte = document.querySelector('[data-offen-karte]');
  return {
    coral: sonde('text-coral'), muted: sonde('text-muted'), ink: sonde('text-ink'),
    symbol: farbe('[data-offen-symbol]'),
    klasse: karte ? karte.className : null,
    gruppen: Object.fromEntries([...document.querySelectorAll('[data-offen-gruppe]')].map((e) => [e.dataset.offenGruppe, getComputedStyle(e).color])),
    daten: [...document.querySelectorAll('[data-offen-datum]')].map((e) => [e.dataset.offenDatum, getComputedStyle(e).color]),
  };
}"""


def _farben(browser, url):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        page.goto(f"{url}/#dashboard", wait_until="load", timeout=30000)
        page.locator("[data-offen-karte]").wait_for(timeout=30000)
        page.locator("[data-offen-datum]").first.wait_for(timeout=15000)
        return page.evaluate(FARBEN_JS)
    finally:
        page.close()


def test_mit_ueberfaelligem_ist_die_karte_ruhig_und_nur_das_ueberfaellige_rot(browser, mit_ueberfaelligem):
    f = _farben(browser, mit_ueberfaelligem)
    assert f["coral"] != f["muted"] != f["ink"], "die Sonden unterscheiden sich — sonst prueft dieser Test nichts"
    # die Karte: kein Rot, nirgends (Rahmen, Hintergrund und Symbol waren es)
    assert "coral" not in f["klasse"], f["klasse"]
    assert f["symbol"] == f["muted"], "das Wecker-Symbol ist neutral, auch wenn etwas ueberfaellig ist"
    # die Gruppen: nur „Ueberfaellig“ ist rot
    assert f["gruppen"]["ueberfaellig"] == f["coral"]
    assert f["gruppen"]["heute"] == f["ink"] and f["gruppen"]["diese_woche"] == f["muted"]
    # die Daten: nur die der ueberfaelligen Zeilen
    rot = [g for g, farbe in f["daten"] if farbe == f["coral"]]
    assert rot == ["ueberfaellig"], f["daten"]
    assert {g for g, _ in f["daten"]} >= {"ueberfaellig", "heute", "diese_woche"}, "alle drei Gruppen standen da"
    assert all(farbe == f["muted"] for g, farbe in f["daten"] if g != "ueberfaellig")


def test_ohne_ueberfaelliges_sieht_der_block_so_aus_wie_bisher(browser, ohne_ueberfaelliges):
    f = _farben(browser, ohne_ueberfaelliges)
    assert "coral" not in f["klasse"] and f["symbol"] == f["muted"]
    assert "ueberfaellig" not in f["gruppen"]
    assert all(farbe == f["muted"] for _g, farbe in f["daten"])
    assert f["gruppen"]["heute"] == f["ink"]


def test_der_quelltext_haelt_die_karte_ruhig():
    q = (FRONTEND / "components" / "OffenBlock.jsx").read_text(encoding="utf-8")
    assert "dringend" not in re.sub(r"//[^\n]*", "", q), "die Karte faerbt sich nicht mehr nach „irgendetwas ist ueberfaellig“"
    assert re.search(r'<Card className="rounded-2xl" data-offen-karte>', q)
    assert 'key === "ueberfaellig" ? "text-coral" : "text-muted"' in q
