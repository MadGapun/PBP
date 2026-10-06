"""Hotfix v1.7.154 (#1171): die Seite „Stellen“ ist im Leerlauf still.

Gemessen an v1.7.153 (isolierte Demo, headless Chromium, fuenf Sekunden nach dem Laden, niemand tut etwas):

    Bewerbungen, Dashboard, Kontakte   Hauptthread 0,0 %      0,4 Anfragen/s
    Stellen                            Hauptthread 66 %     270 bis 470 Anfragen/s

Die Seite fragte pausenlos „laeuft eine Suche?“. Ursache: eine Funktion aus `useEffectEvent` (`syncRunningSearch`) stand in der
Abhaengigkeitsliste des Abfrage-Effekts. Sie ist bei jedem Zeichnen eine NEUE Funktion, und jede Antwort setzt `searchJob` neu
(neues Objekt) — der Effekt startete sich nach jeder Antwort selbst neu. Die Zeile steht seit v0.23.0 (Maerz 2026) im Code.
Kein Absturz, keine Meldung: der Rechner wird nur lauter und der Akku leerer.

Das gebaute Bundle wird getestet (nach JSX-Aenderungen neu bauen: `cd frontend && pnpm exec vite build`).
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

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend" / "src"
TEXT = ("Wir suchen eine Sachbearbeitung im Einkauf. Aufgaben: Disposition, Bestellabwicklung mit SAP MM, "
        "Lieferantenkommunikation. Anforderungen: kaufmaennische Ausbildung, Englisch. ") * 3


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
    db.save_jobs([{"hash": "lz1", "title": "Sachbearbeitung Einkauf", "company": "Musterbetrieb GmbH", "url": "https://example.com/lz1",
                   "source": "manuell", "description": TEXT, "remote_level": "hybrid", "location": "Hamburg", "score": 8}])
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


def test_stellen_seite_fragt_im_leerlauf_nicht_hunderte_male(browser, server):
    """Gesund sind einzelne Anfragen alle paar Sekunden (die Suche wird alle 30 Sekunden erfragt); der Fehler machte rund 270 bis
    470 pro Sekunde."""
    url, _db = server
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    anfragen = []
    page.on("request", lambda r: anfragen.append(r.url) if "/api/" in r.url else None)
    try:
        page.goto(f"{url}/#stellen", wait_until="load", timeout=30000)
        page.locator("[data-stellenkarte]").first.wait_for(timeout=15000)
        page.wait_for_timeout(1500)  # der Start laedt zweimal; danach muss Ruhe sein
        davor = len(anfragen)
        page.wait_for_timeout(3000)
        im_leerlauf = anfragen[davor:]
        assert len(im_leerlauf) < 30, f"{len(im_leerlauf)} Anfragen in 3 s im Leerlauf, zum Beispiel {sorted(set(im_leerlauf))[:3]}"
    finally:
        page.close()


def test_suche_von_claude_steht_nach_wenigen_sekunden_auf_der_seite(browser, server):
    """Der Gegenpart zur Ruhe im Leerlauf: Startet Claude eine Jobsuche, aendert sich die Datenbank so, dass das Dashboard kein
    Nachladen ausloest — die Seite muss selbst nachfragen. Mit der Endlosschleife sah sie die Suche sofort (durch Zufall, weil sie
    staendig fragte); mit einer Frage nur alle 30 Sekunden waere es bis zu eine halbe Minute spaeter (gemessen: 26 s). Jetzt fragt
    sie alle fuenf Sekunden. Zeit ist hier die Messgroesse, die Grenze ist grosszuegig."""
    url, db = server
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(f"{url}/#stellen", wait_until="load", timeout=30000)
        page.locator("[data-stellenkarte]").first.wait_for(timeout=15000)
        jid = db.create_background_job("jobsuche", {})
        db.update_background_job(jid, "running", 40, "Quelle Test | 3 neue Treffer")
        page.wait_for_function("() => document.body.innerText.includes('Jobsuche läuft')", timeout=12000)
        db.update_background_job(jid, "fertig", 100, "fertig")
        page.wait_for_function("() => !document.body.innerText.includes('Jobsuche läuft')", timeout=12000)
    finally:
        page.close()


def test_kein_effekt_ereignis_in_einer_abhaengigkeitsliste():
    """`useEffectEvent` liefert bei jedem Zeichnen eine NEUE Funktion. Steht sie in der Abhaengigkeitsliste eines Effekts, startet
    der Effekt bei jedem Zeichnen neu — und setzt der Effekt dabei Zustand, entsteht eine Endlosschleife (die Stellen-Seite fragte
    so hunderte Male pro Sekunde). Der Bestand unten ist gemessen unauffaellig und bewusst nicht angefasst; NEUE Faelle schlagen an,
    und wer einen behebt, streicht ihn hier."""
    bestand = {
        ("App.jsx", "syncHash"), ("App.jsx", "syncLiveUpdates"),
        ("components/GlobalDocumentDropZone.jsx", "setDragState"), ("components/GlobalDocumentDropZone.jsx", "hideOverlay"),
        ("components/GlobalDocumentDropZone.jsx", "processFiles"),
        ("components/ProfileOnboarding.jsx", "pollConversationState"), ("components/ProfileOnboarding.jsx", "syncProfileDuringConversation"),
        ("components/ProfileOnboarding.jsx", "syncJobsDuringWorkflow"),
    }
    gefunden = set()
    for datei in list(FRONTEND.rglob("*.jsx")) + list(FRONTEND.rglob("*.js")):
        text = datei.read_text(encoding="utf-8-sig")
        for name in re.findall(r"const\s+(\w+)\s*=\s*useEffectEvent\(", text):
            for liste in re.findall(r"\},\s*\[([^\]]*)\]\s*\)", text):
                if re.search(rf"\b{name}\b", liste):
                    gefunden.add((str(datei.relative_to(FRONTEND)).replace("\\", "/"), name))
    assert gefunden - bestand == set(), f"neue Effekt-Ereignisse in Abhaengigkeitslisten: {sorted(gefunden - bestand)}"
    assert bestand - gefunden == set(), f"behoben? Dann hier streichen: {sorted(bestand - gefunden)}"
