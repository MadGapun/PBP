"""#1069 AK 4 — das Dashboard sagt, wenn der Stand unbekannt ist.

Der Server liefert seit v1.7.122 `stand: "unbekannt"`, wenn keine
Update-Quelle geantwortet hat. Das allein genuegt nicht: bis hierher las
die Oberflaeche nur `update_available`, und ein `false` sah aus wie
"alles aktuell" — genau der Zustand, den das Issue beschreibt.

Ein Grep im JSX belegt das nicht (v1.7.71 MERKE 9). Hier laeuft der
Server, der Browser rendert, und der Text wird gelesen.
"""
import os
import socket
import threading

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server_mit_antwort(tmp_path, monkeypatch):
    """Startet das Dashboard und laesst die Update-Pruefung antworten."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    dash._db = db

    def _starten(antwort):
        dash._update_cache.update({"ts": 0, "data": None, "pause_s": 3600})

        class _Client:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, headers=None):
                if antwort == "kein_netz":
                    raise OSError("kein Netz")

                class _R:
                    status_code = 200

                    def json(self_inner):
                        return antwort
                return _R()

        monkeypatch.setattr("httpx.AsyncClient", _Client)
        port = _free_port()
        cfg = uvicorn.Config(dash.app, host="127.0.0.1", port=port,
                             log_level="warning")
        srv = uvicorn.Server(cfg)
        srv.install_signal_handlers = lambda: None
        t = threading.Thread(target=srv.run, daemon=True)
        t.start()
        import time
        import urllib.request
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status",
                                       timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        return f"http://127.0.0.1:{port}", srv, t

    laeufe = []

    def starten(antwort):
        url, srv, t = _starten(antwort)
        laeufe.append((srv, t))
        return url

    yield starten

    for srv, t in laeufe:
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


def _text(browser, url):
    page = browser.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(600)
        return page.inner_text("body")
    finally:
        page.close()


def test_1069_dashboard_sagt_wenn_der_stand_unbekannt_ist(
        browser, server_mit_antwort):
    """AK 4 woertlich: kein stilles "alles aktuell"."""
    url = server_mit_antwort("kein_netz")
    text = _text(browser, url)
    assert "Stand unbekannt" in text
    assert "keine Update-Quelle" in text.lower() or \
           "Update-Quelle" in text


def test_1069_bei_erreichbarer_quelle_kein_hinweis(
        browser, server_mit_antwort):
    """Die Gegenrichtung — sonst steht der Hinweis immer da und wird
    nach dem zweiten Mal ignoriert (#929)."""
    from bewerbungs_assistent import __version__
    url = server_mit_antwort({"version": __version__})
    text = _text(browser, url)
    assert "Stand unbekannt" not in text


def test_1069_neue_version_wird_weiterhin_angeboten(
        browser, server_mit_antwort):
    """Der alte Banner aus #286 bleibt — die Absicht von damals gilt."""
    from bewerbungs_assistent.services.update_quelle import linie_von
    from bewerbungs_assistent import __version__
    url = server_mit_antwort({"version": linie_von(__version__) + ".999",
                              "download_url": "https://example.com/d"})
    text = _text(browser, url)
    assert "Neue Version" in text
    assert "Stand unbekannt" not in text
