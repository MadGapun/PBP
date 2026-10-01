"""#1134 — eine fehlgeschlagene Update-Pruefung blieb eine Stunde stehen.

Befund (01.10.2026): eine Installation (v1.7.141) zeigte "Update-Stand
unbekannt", obwohl die neue Version laengst auf GitHub lag. Zwei Ursachen:
der Server merkte sich auch einen FEHLSCHLAG eine Stunde lang, und die
Oberflaeche fragte nur einmal beim Laden der Seite.

Gemessen vorher: erste Abfrage (Netz weg) -> "unbekannt"; zweite Abfrage
kurz danach (Netz wieder da) -> weiter "unbekannt", dieselbe gemerkte
Antwort, kein neuer Netzaufruf; erst nach der Stunde "geprueft".
"""
import os
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import update_quelle as uq  # noqa: E402


# ══ Reine Funktionen ═══════════════════════════════════════════════

def test_1134_fehlschlag_pause_waechst_und_ist_gedeckelt():
    assert [uq.fehlschlag_pause_s(n) for n in (1, 2, 3, 4, 5, 50)] == \
        [120, 240, 480, 900, 900, 900]


def test_1134_fehlschlag_pause_bei_unsinn_ist_die_kurzeste():
    for n in (0, -3, None):
        assert uq.fehlschlag_pause_s(n) == uq.FEHLSCHLAG_PAUSE_S


def test_1134_ein_fehlschlag_gilt_viel_kuerzer_als_ein_erfolg():
    """Der Kern: nie wieder eine Stunde 'unbekannt' nach einem Netzfehler."""
    assert uq.FEHLSCHLAG_PAUSE_S <= 300
    assert uq.fehlschlag_pause_s(1) < uq.STANDARD_PAUSE_S / 10
    assert uq.FEHLSCHLAG_PAUSE_MAX_S < uq.STANDARD_PAUSE_S


def test_1134_mit_restzeit_laesst_das_original_unberuehrt():
    original = {"stand": "geprueft"}
    kopie = uq.mit_restzeit(original, 42.9)
    assert kopie["wieder_fragen_nach_s"] == 42
    assert "wieder_fragen_nach_s" not in original
    assert uq.mit_restzeit(original, 0)["wieder_fragen_nach_s"] == 5
    assert uq.mit_restzeit(original, -9)["wieder_fragen_nach_s"] == 5


# ══ Der Endpunkt ═══════════════════════════════════════════════════

def _antwort(status=200, daten=None):
    class _Resp:
        status_code = status

        def json(self):
            return daten or {}
    return _Resp()


class _Netz:
    """Ein Netz, das sich umschalten laesst; zaehlt die Aufrufe."""

    def __init__(self):
        from bewerbungs_assistent import __version__
        self.modus = "aus"
        self.aufrufe = 0
        self.version = uq.linie_von(__version__) + ".999"

    def klasse(self):
        netz = self

        class _Client:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, headers=None):
                netz.aufrufe += 1
                if netz.modus == "aus":
                    raise OSError("kein Netz")
                if "elwosa" in url:
                    return _antwort(404)
                return _antwort(200, {"tag_name": "v" + netz.version,
                                      "html_url": "https://example.com/r"})
        return _Client


def _leer(dash):
    dash._update_cache.update(
        {"ts": 0, "data": None, "pause_s": 3600, "fehlversuche": 0})


@pytest.fixture
def umgebung(monkeypatch, tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    monkeypatch.setattr(dash, "_db", None)  # Quellen: die Vorgabe
    _leer(dash)
    netz = _Netz()
    monkeypatch.setattr("httpx.AsyncClient", netz.klasse())
    yield TestClient(dash.app), dash, netz
    _leer(dash)
    os.environ.pop("BA_DATA_DIR", None)


def test_1134_nach_einem_fehlschlag_findet_die_naechste_abfrage_das_update(umgebung):
    """DER Fall aus dem Befund — ohne eine Stunde zu warten."""
    tc, dash, netz = umgebung
    erste = tc.get("/api/update-check").json()
    assert erste["stand"] == "unbekannt"
    assert 5 <= erste["wieder_fragen_nach_s"] <= uq.FEHLSCHLAG_PAUSE_S
    aufrufe = netz.aufrufe

    # Das Netz ist wieder da; innerhalb der kurzen Frist kommt noch die
    # gemerkte Antwort, aber ohne neuen Netzaufruf.
    netz.modus = "an"
    gemerkt = tc.get("/api/update-check").json()
    assert gemerkt["stand"] == "unbekannt" and netz.aufrufe == aufrufe

    # Nach der kurzen Frist (nicht nach einer Stunde) wird neu gefragt.
    dash._update_cache["ts"] -= uq.FEHLSCHLAG_PAUSE_S + 1
    zweite = tc.get("/api/update-check").json()
    assert zweite["stand"] == "geprueft"
    assert zweite["update_available"] is True
    assert zweite["latest_version"] == netz.version


def test_1134_ein_erfolg_bleibt_eine_stunde_gemerkt(umgebung):
    tc, dash, netz = umgebung
    netz.modus = "an"
    erste = tc.get("/api/update-check").json()
    assert erste["stand"] == "geprueft"
    assert 3500 <= erste["wieder_fragen_nach_s"] <= 3600
    aufrufe = netz.aufrufe
    zweite = tc.get("/api/update-check").json()
    assert zweite["stand"] == "geprueft" and netz.aufrufe == aufrufe
    assert zweite["wieder_fragen_nach_s"] <= erste["wieder_fragen_nach_s"]


def test_1134_jetzt_pruefen_umgeht_den_speicher_aber_nicht_dichter_als_15_sekunden(umgebung):
    tc, dash, netz = umgebung
    assert tc.get("/api/update-check").json()["stand"] == "unbekannt"
    netz.modus = "an"
    aufrufe = netz.aufrufe
    # Ein Klick unmittelbar nach der Pruefung trifft GitHub nicht noch einmal.
    zu_frueh = tc.get("/api/update-check?frisch=1").json()
    assert zu_frueh["stand"] == "unbekannt" and netz.aufrufe == aufrufe
    # Nach dem Mindestabstand geht der Klick durch — lange vor Ablauf der Frist.
    dash._update_cache["ts"] -= uq.MIN_ABSTAND_FRISCH_S + 1
    assert uq.MIN_ABSTAND_FRISCH_S + 1 < uq.FEHLSCHLAG_PAUSE_S
    frisch = tc.get("/api/update-check?frisch=1").json()
    assert frisch["stand"] == "geprueft" and frisch["update_available"] is True
    assert netz.aufrufe > aufrufe


def test_1134_ohne_frisch_wird_der_speicher_nie_umgangen(umgebung):
    """Seitenaufrufe duerfen GitHub nicht im Sekundentakt abfragen."""
    tc, dash, netz = umgebung
    netz.modus = "an"
    tc.get("/api/update-check")
    aufrufe = netz.aufrufe
    dash._update_cache["ts"] -= uq.MIN_ABSTAND_FRISCH_S + 1
    for _ in range(3):
        tc.get("/api/update-check")
    assert netz.aufrufe == aufrufe


def test_1134_wiederholte_fehlschlaege_werden_seltener_gefragt(umgebung):
    tc, dash, netz = umgebung
    fristen = []
    for _ in range(5):
        antwort = tc.get("/api/update-check").json()
        assert antwort["stand"] == "unbekannt"
        fristen.append(antwort["wieder_fragen_nach_s"])
        dash._update_cache["ts"] -= dash._update_cache["pause_s"] + 1
    assert fristen == [120, 240, 480, 900, 900]


def test_1134_ein_erfolg_setzt_die_zaehlung_zurueck(umgebung):
    tc, dash, netz = umgebung
    for _ in range(3):
        tc.get("/api/update-check")
        dash._update_cache["ts"] -= dash._update_cache["pause_s"] + 1
    netz.modus = "an"
    assert tc.get("/api/update-check").json()["stand"] == "geprueft"
    dash._update_cache["ts"] -= dash._update_cache["pause_s"] + 1
    netz.modus = "aus"
    nach_erfolg = tc.get("/api/update-check").json()
    assert nach_erfolg["stand"] == "unbekannt"
    assert nach_erfolg["wieder_fragen_nach_s"] <= uq.FEHLSCHLAG_PAUSE_S


def test_1134_die_antwort_traegt_weiterhin_alle_bisherigen_felder(umgebung):
    tc, dash, netz = umgebung
    res = tc.get("/api/update-check").json()
    for feld in ("current_version", "latest_version", "update_available",
                 "release_url", "linie", "stand", "geprueft_am",
                 "quellen_versucht", "hinweis"):
        assert feld in res, feld
    assert "UNBEKANNT" in res["hinweis"]
    assert len(res["quellen_versucht"]) == 2


# ══ Die Oberflaeche: Bauform und Registrierung ═════════════════════

def _quelle(*teile):
    return (ROOT.joinpath(*teile)).read_text(encoding="utf-8-sig")


def test_1134_die_oberflaeche_fragt_wieder_und_raeumt_den_timer_auf():
    app = _quelle("frontend", "src", "App.jsx")
    assert 'from "@/lib/updateStand"' in app
    assert "setTimeout(() => frage(false), naechsteFrageMs(data))" in app
    assert "clearTimeout(timer)" in app
    # Die alte Fassung — ein einziger Aufruf beim Laden — darf nicht zurueckkehren.
    assert 'optionalApi("/api/update-check").then(' not in app
    # Jede Antwort ersetzt die vorige, sonst bliebe "unbekannt" stehen.
    assert "if (data) setUpdateInfo(data);" in app
    assert '"/api/update-check?frisch=1"' in app


def test_1134_die_seitenleiste_bietet_einen_weg_weiter():
    leiste = _quelle("frontend", "src", "components", "Sidebar.jsx")
    assert "data-update-pruefen" in leiste
    assert "Jetzt prüfen" in leiste and "Prüfe …" in leiste
    assert "brand.updateGrund" in leiste


def test_1134_der_node_test_laeuft_in_der_ci():
    ci = _quelle(".github", "workflows", "tests.yml")
    assert "node frontend/src/lib/updateStand.test.mjs" in ci


def test_1134_server_und_oberflaeche_nennen_dieselbe_untergrenze():
    """Die Oberflaeche fragt nie dichter als alle 30 s; der Server nie
    dichter als alle 15 s per Klick. Beides haelt GitHubs Grenze
    (60 Anfragen je Stunde ohne Anmeldung) auch bei Dauerbetrieb ein."""
    lib = _quelle("frontend", "src", "lib", "updateStand.js")
    assert "FRAGE_MIN_MS = 30 * 1000" in lib
    assert uq.MIN_ABSTAND_FRISCH_S >= 10
    # Schlimmster Dauerbetrieb: nur Fehlschlaege -> hoechstens 4 Fragen je Stunde
    assert 3600 / uq.FEHLSCHLAG_PAUSE_MAX_S <= 4


# ══ Im Browser: der Weg, den ein Mensch sieht ═════════════════════

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None
    PlaywrightError = Exception


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


@pytest.fixture
def live(monkeypatch, tmp_path):
    """Echter Dashboard-Server mit einem Netz, das sich umschalten laesst."""
    import socket
    import time
    import urllib.request

    import uvicorn

    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database, get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    monkeypatch.setattr(dash, "_db", db)
    _leer(dash)
    netz = _Netz()
    monkeypatch.setattr("httpx.AsyncClient", netz.klasse())

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
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

    yield f"http://127.0.0.1:{port}", dash, netz

    srv.should_exit = True
    t.join(timeout=10)
    _leer(dash)
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def test_1134_jetzt_pruefen_holt_das_update_nach(browser, live):
    url, dash, netz = live
    page = browser.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_selector('[data-update-stand="unbekannt"]', timeout=15000)
        assert page.locator("[data-update-pruefen]").inner_text().strip() == "Jetzt prüfen"
        # Das Tooltip nennt den Grund und wann PBP erneut fragt.
        titel = page.locator('[data-update-stand="unbekannt"]').get_attribute("title")
        assert "keine Verbindung" in titel and "erneut" in titel, titel
        # Das Netz ist wieder da; der Mindestabstand zur letzten Pruefung ist um.
        netz.modus = "an"
        dash._update_cache["ts"] -= uq.MIN_ABSTAND_FRISCH_S + 1
        page.click("[data-update-pruefen]")
        page.wait_for_selector('[data-update-stand="neu"]', timeout=15000)
        assert page.locator('[data-update-stand="unbekannt"]').count() == 0
    finally:
        page.close()


def test_1134_die_seite_fragt_nach_einem_fehlschlag_von_selbst_wieder(browser, live):
    url, dash, netz = live
    page = browser.new_page()
    try:
        page.clock.install()  # falsche Uhr: die Wartezeit laeuft nicht in Echtzeit
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_selector('[data-update-stand="unbekannt"]', timeout=15000)
        netz.modus = "an"
        dash._update_cache["ts"] -= uq.FEHLSCHLAG_PAUSE_S + 1  # Frist des Servers um
        page.clock.fast_forward((uq.FEHLSCHLAG_PAUSE_S + 10) * 1000)
        page.wait_for_selector('[data-update-stand="neu"]', timeout=15000)
    finally:
        page.close()


def test_1134_ein_lange_offenes_dashboard_erfaehrt_von_einer_neuen_version(browser, live):
    """Vorher blieb eine spaeter erschienene Version unsichtbar, bis die
    Seite neu geladen wurde."""
    from bewerbungs_assistent import __version__
    url, dash, netz = live
    netz.modus = "an"
    netz.version = __version__  # aktuell: kein Hinweis
    page = browser.new_page()
    try:
        page.clock.install()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(500)
        assert page.locator("[data-update-stand]").count() == 0
        netz.version = uq.linie_von(__version__) + ".999"  # inzwischen erschienen
        dash._update_cache["ts"] -= uq.STANDARD_PAUSE_S + 1
        page.clock.fast_forward((uq.STANDARD_PAUSE_S + 60) * 1000)
        page.wait_for_selector('[data-update-stand="neu"]', timeout=15000)
    finally:
        page.close()


def test_1134_ein_behobener_fehler_raeumt_die_unbekannt_anzeige_weg(browser, live):
    """Auch wenn es KEIN Update gibt: 'Update-Stand unbekannt' darf nicht
    stehen bleiben, nachdem die Pruefung wieder funktioniert (vorher
    ersetzte nur ein gefundenes Update die Anzeige)."""
    from bewerbungs_assistent import __version__
    url, dash, netz = live
    netz.version = __version__  # aktuell: nichts zu melden
    page = browser.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_selector('[data-update-stand="unbekannt"]', timeout=15000)
        netz.modus = "an"
        dash._update_cache["ts"] -= uq.MIN_ABSTAND_FRISCH_S + 1
        page.click("[data-update-pruefen]")
        page.wait_for_selector('[data-update-stand="unbekannt"]',
                               state="detached", timeout=15000)
        assert page.locator("[data-update-stand]").count() == 0
    finally:
        page.close()
