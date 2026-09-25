"""#1063 AK 4 — die Oberflaeche zeigt je Stufe ihre Wirkung.

Das Akzeptanzkriterium lautet woertlich: *"Die Oberflaeche zeigt je
Stufe, wie viele Stellen des Bestands sie sichtbar laesst."* Ein Grep im
JSX belegt das nicht (v1.7.71 MERKE 9) — hier laeuft der Server, der
Browser rendert, und der Text wird gelesen.

Geprueft wird dabei BEIDES, was an einer Stufe haengt: wie viele Stellen
sichtbar bleiben, und wie viele eigene Bewerbungen darunter gelegen
haetten. Die zweite Zahl ist die teurere — was die Speicher-Schwelle
verwirft, kommt nie in den Bestand.
"""
import os
import socket
import threading
import time
import urllib.request

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _stelle(db, kennung, score, aktiv=True):
    db.save_jobs([{
        "hash": kennung, "title": f"Stelle {kennung}",
        "company": f"Musterbetrieb {kennung}",
        "url": f"https://example.com/{kennung}", "source": "manuell",
        "description": "Ein Anzeigentext. " * 10, "score": score,
    }])
    conn = db.connect()
    voll = conn.execute("SELECT hash FROM jobs WHERE hash LIKE ?",
                        (f"%{kennung}",)).fetchone()["hash"]
    conn.execute("UPDATE jobs SET score=?, fachscore=? WHERE hash=?",
                 (score, score, voll))
    if not aktiv:
        conn.execute(
            "UPDATE jobs SET is_active=0, "
            "dismiss_reason='falsches_fachgebiet' WHERE hash=?", (voll,))
    conn.commit()
    return voll.split(":", 1)[-1]


@pytest.fixture
def server(tmp_path):
    """Dashboard mit einem Bestand, aus dem sich Stufen rechnen lassen."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})

    # 24 Bewerbungen und 24 Aussortierte — ueber MIN_WERTE, sonst
    # bleiben die Stufen zu Recht ungerechnet.
    for i in range(24):
        voll = _stelle(db, f"o63b{i:03d}", 10 + i)
        db.add_application({"title": f"Stelle o63b{i:03d}",
                            "company": f"Musterbetrieb o63b{i:03d}",
                            "status": "beworben", "job_hash": voll})
    for i in range(24):
        _stelle(db, f"o63a{i:03d}", i % 9, aktiv=False)
    for i in range(10):
        _stelle(db, f"o63x{i:03d}", i * 4)

    dash._db = db
    port = _free_port()
    cfg = uvicorn.Config(dash.app, host="127.0.0.1", port=port,
                         log_level="warning")
    srv = uvicorn.Server(cfg)
    srv.install_signal_handlers = lambda: None
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status",
                                   timeout=1)
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


def _profil_scoring(browser, url):
    """Oeffnet den Scoring-Abschnitt der Profilseite."""
    page = browser.new_page()
    page.goto(f"{url}/#profil", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(900)
    return page


def test_1063_jede_stufe_nennt_ihre_wirkung(browser, server):
    """AK 4: wie viele Stellen bleiben sichtbar — je Stufe."""
    url, _db = server
    page = _profil_scoring(browser, url)
    try:
        page.wait_for_selector("text=Offensichtliches aus", timeout=15000)
        text = page.inner_text("body")
        for name in ("Alles zeigen", "Offensichtliches aus", "Locker",
                     "Ausgewogen", "Streng", "Nur Volltreffer"):
            assert name in text, f"Stufe fehlt in der Oberflaeche: {name}"
        assert "Stellen bleiben sichtbar" in text
        # C96 (#1087): "ab 7 Punkten" statt "ab Score 7".
        assert "Punkten" in text
    finally:
        page.close()


def test_1063_die_kostenseite_steht_daneben(browser, server):
    """Die teurere Zahl: wie viele eigene Bewerbungen laegen darunter.

    "Wie viele bleiben sichtbar" allein zeigt nur die eine Haelfte der
    Rechnung — die Stufe sieht dann billig aus.
    """
    url, _db = server
    page = _profil_scoring(browser, url)
    try:
        page.wait_for_selector("text=Offensichtliches aus", timeout=15000)
        assert "eigenen Bewerbungen lägen darunter" in page.inner_text("body")
    finally:
        page.close()


def test_1063_beide_bereiche_sind_einstellbar(browser, server):
    """Speichern und Liste sind zwei verschiedene Dinge (#1008).

    Der Listen-Bereich hatte bis hierher ueberhaupt keine Oberflaeche —
    `schwellenwert/auto_ignore` war nur ueber ein Werkzeug erreichbar.
    """
    url, _db = server
    page = _profil_scoring(browser, url)
    try:
        page.wait_for_selector("text=Offensichtliches aus", timeout=15000)
        text = page.inner_text("body")
        assert "Beim Speichern während der Suche" in text
        assert "Beim Ausblenden in der Liste" in text
        assert "unwiederbringlich" in text
    finally:
        page.close()


def test_1063_ein_klick_setzt_die_stufe_in_der_datenbank(browser, server):
    """Der Beleg ist der BESTAND, nicht der Toast (v1.7.105 MERKE 2)."""
    url, db = server
    from bewerbungs_assistent.services import schwellen_stufen as st

    assert st.gewaehlte_stufe(db, st.LISTE) == st.VORGABE
    page = _profil_scoring(browser, url)
    try:
        page.wait_for_selector("text=Beim Ausblenden in der Liste",
                               timeout=15000)
        # Innerhalb des Listen-Blocks klicken — der Name steht auch im
        # Speichern-Block, ein zu breiter Locator misst den Test
        # (v1.7.103 MERKE 6). Dieser Fall hat den Label-Fehler aus
        # #1027 gefunden: im <label> von Field landete JEDER Klick auf
        # der obersten Stufe.
        block = page.locator('[data-stufenbereich="liste"]').first
        block.get_by_role("button", name="Locker", exact=False).first.click()
        page.wait_for_timeout(1200)
        assert st.gewaehlte_stufe(db, st.LISTE) == "locker"
        # Der andere Bereich bleibt unberuehrt.
        assert st.gewaehlte_stufe(db, st.SPEICHERN) == st.VORGABE
    finally:
        page.close()


def test_1063_die_zahl_bleibt_erreichbar(browser, server):
    """AK 1: nicht der Normalweg, aber nicht weg."""
    url, _db = server
    page = _profil_scoring(browser, url)
    try:
        page.wait_for_selector("text=Offensichtliches aus", timeout=15000)
        assert "für Fortgeschrittene" in page.inner_text("body")
    finally:
        page.close()
