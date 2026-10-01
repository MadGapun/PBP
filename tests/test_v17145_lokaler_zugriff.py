"""v1.7.145 — nur das Dashboard selbst darf PBP veraendern.

Befund (01.10.2026, Sicherheitspruefung): Jede Webseite, die im selben
Browser offen war, konnte per "einfacher" Anfrage (POST mit
Content-Type text/plain, kein Preflight) an http://localhost:8200 das
Profil ueberschreiben, einen Ordner einlesen lassen, die Datenbank
leeren, auf Werkseinstellung zuruecksetzen oder den Deinstaller starten.
Die Bestaetigungswoerter stehen im Body, den der Angreifer selbst schreibt.

Gemessen vorher (TestClient): POST von Origin http://evil.example -> 200,
Profilname geaendert; Origin "null" -> 200; Host-Kopfzeile evil.example ->
200 (DNS-Rebinding). Nachher: 403, Profil unveraendert.
"""
import json
import os
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import lokaler_zugriff as lz  # noqa: E402


# ══ Reine Funktionen ═══════════════════════════════════════════════

@pytest.mark.parametrize("kopf,erlaubt", [
    ("localhost:8200", True), ("127.0.0.1:8200", True), ("[::1]:8200", True),
    ("LOCALHOST:8200", True), ("localhost", True), ("testserver", True),
    ("evil.example:8200", False), ("localhost.evil.example", False),
    ("127.0.0.1.evil.example:8200", False), ("0.0.0.0:8200", False),
    ("192.168.1.5:8200", False), ("", False), (None, False),
])
def test_host_nur_lokale_namen(kopf, erlaubt):
    assert lz.host_erlaubt(kopf) is erlaubt


def test_host_weitere_namen_nur_ueber_die_umgebung(monkeypatch):
    monkeypatch.delenv("BA_ERLAUBTE_HOSTS", raising=False)
    assert lz.host_erlaubt("mein-rechner:8200") is False
    monkeypatch.setenv("BA_ERLAUBTE_HOSTS", "mein-rechner, pbp.local")
    assert lz.host_erlaubt("mein-rechner:8200") is True
    assert lz.host_erlaubt("PBP.local") is True
    assert lz.host_erlaubt("anderer:8200") is False


@pytest.mark.parametrize("origin,host,erlaubt", [
    (None, "localhost:8200", True),                       # curl, Skripte, Setup
    ("http://localhost:8200", "localhost:8200", True),    # die eigene Seite
    ("http://127.0.0.1:8200", "127.0.0.1:8200", True),
    ("http://localhost:8200", "127.0.0.1:8200", False),   # anderer Name
    ("http://localhost:8260", "localhost:8200", False),   # andere Seite, anderer Port
    ("http://evil.example", "localhost:8200", False),
    ("null", "localhost:8200", False),                    # Sandbox, data:, file://
    ("", "localhost:8200", False),
    ("moz-extension://abc", "localhost:8200", False),
    ("http://localhost:8200", "", False),
    ("http://localhost:8200", None, False),
])
def test_herkunft_nur_die_eigene(origin, host, erlaubt):
    assert lz.herkunft_erlaubt(origin, host) is erlaubt


def test_herkunft_weitere_nur_ueber_die_umgebung(monkeypatch):
    monkeypatch.delenv("BA_ERLAUBTE_HERKUENFTE", raising=False)
    assert lz.herkunft_erlaubt("http://localhost:5173", "localhost:8200") is False
    monkeypatch.setenv("BA_ERLAUBTE_HERKUENFTE", "http://localhost:5173")
    assert lz.herkunft_erlaubt("http://localhost:5173", "localhost:8200") is True
    assert lz.herkunft_erlaubt("http://localhost:5174", "localhost:8200") is False


def test_lesen_von_fremder_herkunft_bleibt_moeglich():
    """Ein GET aendert nichts, und die Same-Origin-Policy verbirgt die
    Antwort vor der fremden Seite; Bilder, Schriften und Links bleiben heil."""
    assert lz.pruefen("GET", "/api/status", "localhost:8200", "http://evil.example")[0]
    assert lz.pruefen("HEAD", "/", "localhost:8200", "http://evil.example")[0]


def test_ingest_api_ist_von_der_herkunftspruefung_ausgenommen_nicht_vom_host():
    """Add-ons (moz-extension://) sprechen die Ingest-API mit Schluessel an."""
    assert lz.pruefen("POST", "/api/v1/ingest/email", "localhost:8200",
                      "moz-extension://abc") == (True, "")
    assert lz.pruefen("POST", "/api/v1/ingest/ping", "evil.example", None)[0] is False
    # ... aber jeder andere Pfad bleibt geschuetzt
    assert lz.pruefen("POST", "/api/v1/andere", "localhost:8200",
                      "moz-extension://abc")[0] is False


@pytest.mark.parametrize("methode", ["POST", "PUT", "PATCH", "DELETE", "post"])
def test_jede_schreibende_methode_wird_geprueft(methode):
    assert lz.pruefen(methode, "/api/profile", "localhost:8200",
                      "http://evil.example")[0] is False


# ══ Der Endpunkt ═══════════════════════════════════════════════════

@pytest.fixture
def umgebung(monkeypatch, tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database, get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Beispiel Person"})
    monkeypatch.setattr(dash, "_db", db)
    monkeypatch.delenv("BA_ERLAUBTE_HOSTS", raising=False)
    monkeypatch.delenv("BA_ERLAUBTE_HERKUENFTE", raising=False)
    yield TestClient(dash.app), dash, db
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def _name(db):
    return (db.get_profile() or {}).get("name")


def test_fremde_seite_kann_das_profil_nicht_aendern(umgebung):
    """DER Fall aus dem Befund: einfache Anfrage ohne Preflight."""
    tc, dash, db = umgebung
    r = tc.post("/api/profile", content=json.dumps({"name": "Angriff von aussen"}),
                headers={"Content-Type": "text/plain", "Origin": "http://evil.example"})
    assert r.status_code == 403
    assert "PBP-Oberfläche" in r.json()["error"] or "PBP-Oberflaeche" in r.json()["error"]
    assert _name(db) == "Beispiel Person"


@pytest.mark.parametrize("origin", ["null", "http://localhost:8260",
                                    "https://evil.example", "moz-extension://abc"])
def test_auch_andere_fremde_herkuenfte_werden_abgelehnt(umgebung, origin):
    tc, dash, db = umgebung
    r = tc.post("/api/profile", json={"name": "Angriff"}, headers={"Origin": origin})
    assert r.status_code == 403 and _name(db) == "Beispiel Person"


def test_die_eigene_seite_darf_schreiben(umgebung):
    tc, dash, db = umgebung
    r = tc.post("/api/profile", json={"name": "Eigene Aenderung"},
                headers={"Origin": "http://testserver"})
    assert r.status_code == 200, r.text
    assert _name(db) == "Eigene Aenderung"


def test_aufrufe_ohne_origin_bleiben_moeglich(umgebung):
    """curl, Skripte, Plugins, das Installer-Setup: keine Browser-Anfrage."""
    tc, dash, db = umgebung
    r = tc.post("/api/profile", json={"name": "Per Skript"})
    assert r.status_code == 200 and _name(db) == "Per Skript"


def test_fremder_host_wird_abgelehnt_auch_beim_lesen(umgebung):
    """DNS-Rebinding: ein fremder Name zeigt auf 127.0.0.1, die Antworten
    waeren fuer die fremde Seite sonst lesbar."""
    tc, dash, db = umgebung
    assert tc.get("/api/status", headers={"Host": "evil.example:8200"}).status_code == 403
    assert tc.get("/", headers={"Host": "evil.example:8200"}).status_code == 403
    assert tc.get("/api/status", headers={"Host": "localhost:8200"}).status_code == 200


def test_weiterer_host_ueber_die_umgebung(umgebung, monkeypatch):
    tc, dash, db = umgebung
    monkeypatch.setenv("BA_ERLAUBTE_HOSTS", "mein-rechner")
    assert tc.get("/api/status", headers={"Host": "mein-rechner:8200"}).status_code == 200


def test_die_ablehnung_sagt_dem_menschen_was_zu_tun_ist(umgebung):
    tc, dash, db = umgebung
    text = tc.get("/api/status", headers={"Host": "evil.example"}).json()["error"]
    assert "localhost" in text and "BA_ERLAUBTE_HOSTS" in text


def test_jede_schreibende_route_ist_geschuetzt(umgebung, monkeypatch):
    """Nicht nur /api/profile: ALLE Routen, die etwas aendern. Die Pruefung
    sitzt vor dem Routing, ein kuenftig hinzugefuegter Endpunkt ist also
    automatisch dabei; dieser Test haelt das fest.

    Sicherheitsnetz: faende die Pruefung einmal NICHT statt, duerfte dieser
    Test keinen Prozess starten (Deinstaller, Ollama, Explorer).
    """
    tc, dash, db = umgebung

    def boom(*a, **kw):
        raise AssertionError("im Test darf kein Prozess starten")

    monkeypatch.setattr("subprocess.Popen", boom)
    monkeypatch.setattr("subprocess.run", boom)
    if hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", boom, raising=False)

    gepruefte = []
    for route in dash.app.routes:
        methoden = getattr(route, "methods", None) or set()
        pfad = getattr(route, "path", "")
        if not pfad.startswith("/api/") or pfad.startswith(lz.AUSGENOMMENE_PRAEFIXE):
            continue
        for methode in sorted(methoden & lz.SCHREIBENDE_METHODEN):
            ziel = pfad.replace("{", "").replace("}", "")
            r = tc.request(methode, ziel, content="{}",
                           headers={"Content-Type": "text/plain",
                                    "Origin": "http://evil.example"})
            assert r.status_code == 403, f"{methode} {pfad}: {r.status_code}"
            gepruefte.append((methode, pfad))
    assert len(gepruefte) >= 50, f"nur {len(gepruefte)} schreibende Routen gefunden"
    assert _name(db) == "Beispiel Person"


# ══ Im Browser: eine fremde Seite auf einem anderen Port ═══════════

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


def _freier_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live(monkeypatch, tmp_path):
    """Echter Dashboard-Server und daneben eine 'fremde Seite' auf anderem Port."""
    import http.server
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
    db.save_profile({"name": "Beispiel Person"})
    monkeypatch.setattr(dash, "_db", db)
    monkeypatch.delenv("BA_ERLAUBTE_HOSTS", raising=False)
    monkeypatch.delenv("BA_ERLAUBTE_HERKUENFTE", raising=False)

    port = _freier_port()
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

    # Die "fremde Seite": nur eine leere HTML-Datei, das Skript laeuft im Browser
    angriff_port = _freier_port()
    seite = (tmp_path / "angriff.html")
    seite.write_text("<!doctype html><title>fremd</title><p>fremde Seite</p>", encoding="utf-8")

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(tmp_path), **kw)

        def log_message(self, *a):
            pass

    fremd = http.server.ThreadingHTTPServer(("127.0.0.1", angriff_port), _Handler)
    ft = threading.Thread(target=fremd.serve_forever, daemon=True)
    ft.start()

    yield f"http://127.0.0.1:{port}", f"http://127.0.0.1:{angriff_port}/angriff.html", db

    fremd.shutdown()
    fremd.server_close()
    srv.should_exit = True
    t.join(timeout=10)
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


ANGRIFF_JS = """async (ziel) => {
  const antworten = [];
  // genau die Form aus dem Befund: einfache Anfrage ohne Vorab-Frage
  for (const [pfad, body] of [
      ["/api/profile", {name: "Angriff von aussen"}],
      ["/api/danger/leeren", {confirm: "LOESCHEN", bereiche: ["alles"]}],
      ["/api/reset", {confirm: "RESET"}]]) {
    try {
      await fetch(ziel + pfad, {method: "POST", mode: "no-cors",
        headers: {"Content-Type": "text/plain"}, body: JSON.stringify(body)});
      antworten.push("gesendet");
    } catch (e) { antworten.push("Fehler: " + e.message); }
  }
  return antworten;
}"""


def test_eine_fremde_seite_kann_pbp_im_browser_nicht_veraendern(browser, live):
    dashboard, fremde_seite, db = live
    seite = browser.new_page()
    try:
        seite.goto(fremde_seite, wait_until="load", timeout=30000)
        seite.evaluate(ANGRIFF_JS, dashboard)
        # Die Anfragen sind raus; die Datenbank muss unveraendert sein.
        assert (db.get_profile() or {}).get("name") == "Beispiel Person"
    finally:
        seite.close()


def test_die_eigene_oberflaeche_schreibt_weiterhin(browser, live):
    """Die Gegenrichtung: ein Schutz, der das Dashboard selbst aussperrt, ist keiner."""
    dashboard, fremde_seite, db = live
    seite = browser.new_page()
    try:
        seite.goto(dashboard, wait_until="networkidle", timeout=30000)
        status = seite.evaluate(
            """async () => (await fetch('/api/profile', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: 'Aus der eigenen Oberflaeche'})})).status""")
        assert status == 200
        assert (db.get_profile() or {}).get("name") == "Aus der eigenen Oberflaeche"
    finally:
        seite.close()


def test_jede_antwort_traegt_die_schutz_kopfzeilen(umgebung):
    """Kein Einbetten durch fremde Seiten (Clickjacking), kein Inhaltstyp-Raten."""
    tc, dash, db = umgebung
    for antwort in (tc.get("/api/status"), tc.get("/"),
                    tc.get("/api/status", headers={"Host": "evil.example"}),   # auch die Ablehnung
                    tc.post("/api/profile", json={"name": "x"})):
        assert antwort.headers["x-frame-options"] == "SAMEORIGIN"
        assert antwort.headers["content-security-policy"] == "frame-ancestors 'self'"
        assert antwort.headers["x-content-type-options"] == "nosniff"
