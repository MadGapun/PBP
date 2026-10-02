"""#1149 Punkt 4 — ein belegter Port heißt nicht „PBP läuft bereits“.

Befund (01.10.2026, Prüfbereich Installation): hält ein fremdes Programm
Port 8200, schrieb `start_dashboard.py` „PBP laeuft bereits … Das Dashboard
ist schon erreichbar!“ und öffnete den Browser; der MCP-Server schrieb nur
eine Log-Warnung; der Gesundheitstest des Installers prüfte allein auf HTTP
200. Gemessen mit einem fremden Programm auf einem Testport.

Jetzt unterscheidet PBP: auf `/api/health` antwortet nur ein PBP mit
`pbp_version`. Alle Server hier sind Attrappen auf freien Testports; der
echte Port 8200 wird nie berührt.
"""
import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "INSTALLIEREN.bat"
OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0
nur_windows = pytest.mark.skipif(os.name != "nt", reason="braucht cmd.exe und PowerShell")


# ── Attrappen ────────────────────────────────────────────────────────────────

def _handler(antworten):
    """antworten: {pfad: (status, inhaltstyp, text)}; `*` gilt für alle übrigen Pfade."""
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            status, typ, text = antworten.get(self.path) or antworten.get("*") or (404, "text/plain", "nicht da")
            roh = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)

        def log_message(self, *args):  # still
            pass
    return H


@pytest.fixture()
def server():
    """Startet Attrappen-Server; gibt eine Funktion `starte(antworten) -> port` zurück."""
    laufende = []

    def starte(antworten):
        s = ThreadingHTTPServer(("127.0.0.1", 0), _handler(antworten))
        threading.Thread(target=s.serve_forever, daemon=True).start()
        laufende.append(s)
        return s.server_address[1]

    yield starte
    for s in laufende:
        s.shutdown()
        s.server_close()


PBP = {"/api/health": (200, "application/json", json.dumps({"pbp_version": "1.7.149", "platform": "Windows"}))}
FREMD_STARTSEITE = {"/": (200, "text/html", "<html>Ein anderes Programm</html>")}          # alles andere 404
FREMD_ALLES_200 = {"*": (200, "text/html", "<html>Single-Page-App, antwortet auf jeden Pfad</html>")}
FREMD_JSON = {"/api/health": (200, "application/json", json.dumps({"status": "ok"}))}      # kein PBP
FREMD_FEHLER = {"/api/health": (500, "application/json", json.dumps({"pbp_version": "x"}))}


def _frei():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── Erkennung ────────────────────────────────────────────────────────────────

def test_1149_ein_pbp_wird_am_gesundheitstest_erkannt(server):
    from bewerbungs_assistent.services.dashboard_halter import ist_pbp
    assert ist_pbp(server(PBP)) is True


@pytest.mark.parametrize("antworten", [FREMD_STARTSEITE, FREMD_ALLES_200, FREMD_JSON, FREMD_FEHLER],
                         ids=["nur Startseite", "antwortet auf alles", "JSON ohne pbp_version", "Status 500"])
def test_1149_ein_fremdes_programm_gilt_nicht_als_pbp(server, antworten):
    from bewerbungs_assistent.services.dashboard_halter import ist_pbp
    assert ist_pbp(server(antworten)) is False


def test_1149_ohne_server_ist_es_kein_pbp_und_es_dauert_nicht():
    import time
    from bewerbungs_assistent.services.dashboard_halter import ist_pbp
    t0 = time.monotonic()
    assert ist_pbp(_frei(), timeout=1.0) is False
    assert time.monotonic() - t0 < 3.0


def test_1149_ein_server_der_nie_antwortet_haelt_den_start_nicht_auf():
    import time
    from bewerbungs_assistent.services.dashboard_halter import ist_pbp
    stumm = socket.socket()
    stumm.bind(("127.0.0.1", 0))
    stumm.listen(5)
    ergebnis = []
    # In einem Thread, damit eine verlorene Zeitgrenze den Test nicht für immer aufhält.
    t = threading.Thread(target=lambda: ergebnis.append(ist_pbp(stumm.getsockname()[1], timeout=0.5)),
                         daemon=True)
    try:
        t0 = time.monotonic()
        t.start()
        t.join(8)
        assert not t.is_alive(), "ist_pbp hält sich nicht an die Zeitgrenze"
        assert ergebnis == [False]
        assert time.monotonic() - t0 < 5.0
    finally:
        stumm.close()


# ── Was der MCP-Prozess daraus macht ────────────────────────────────────────

@pytest.fixture()
def halter():
    from bewerbungs_assistent.services import dashboard_halter
    dashboard_halter.zuruecksetzen()
    yield dashboard_halter
    dashboard_halter.zuruecksetzen()


def _starte_dashboard_auf(port, monkeypatch):
    from unittest.mock import MagicMock
    from bewerbungs_assistent import server as srv
    monkeypatch.setenv("BA_DASHBOARD_PORT", str(port))
    from bewerbungs_assistent import dashboard as dash
    monkeypatch.setattr(dash, "_db", MagicMock(), raising=False)
    return srv.dashboard_im_hintergrund_starten(MagicMock(), port)


def test_1149_der_mcp_prozess_merkt_sich_ein_fremdes_programm(server, halter, monkeypatch):
    port = server(FREMD_STARTSEITE)
    assert _starte_dashboard_auf(port, monkeypatch) is None
    z = halter.lesen()
    assert z["halter"] == halter.FREMDES and z["port"] == port


def test_1149_der_mcp_prozess_haelt_ein_anderes_pbp_weiter_fuer_ein_pbp(server, halter, monkeypatch):
    port = server(PBP)
    assert _starte_dashboard_auf(port, monkeypatch) is None
    assert halter.lesen()["halter"] == halter.ANDERER


def test_1149_pbp_diagnose_nennt_das_fremde_programm_als_warnung(halter):
    halter.setzen(halter.FREMDES, port=8200)
    halter.pruefintervall_merken(300)
    a = halter.beschreiben()
    assert a["art"] == "warnung"
    assert "8200" in a["meldung"] and "anderen Programm" in a["meldung"] and "kein PBP" in a["meldung"]
    assert "alle 5 Minuten" in a["meldung"]
    assert "PBP-Fenster" not in a["meldung"], "das war die falsche Behauptung"


def test_1149_ein_anderes_pbp_bleibt_eine_info(halter):
    halter.setzen(halter.ANDERER, port=8200)
    assert halter.beschreiben()["art"] == "info"


# ── start_dashboard.py (Desktop-Verknüpfung) ─────────────────────────────────

def test_1149_start_dashboard_sagt_bei_einem_fremden_programm_die_wahrheit(server, tmp_path):
    port = server(FREMD_STARTSEITE)
    env = dict(os.environ, BA_DATA_DIR=str(tmp_path / "daten"), BA_DASHBOARD_PORT=str(port),
               PYTHONIOENCODING="utf-8")
    (tmp_path / "daten").mkdir()
    r = subprocess.run([sys.executable, str(ROOT / "start_dashboard.py")], env=env, cwd=str(tmp_path),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL, creationflags=OHNE_FENSTER, timeout=120)
    ausgabe = r.stdout + r.stderr
    assert r.returncode == 1, ausgabe[-800:]
    assert f"Port {port} wird von einem ANDEREN Programm benutzt" in ausgabe
    assert "PBP laeuft bereits" not in ausgabe
    assert "Das Dashboard ist schon erreichbar" not in ausgabe


def test_1149_start_dashboard_kennt_den_weg_fuer_ein_laufendes_pbp_weiter():
    quelle = (ROOT / "start_dashboard.py").read_text(encoding="utf-8")
    i = quelle.index("if not ist_pbp(port):")
    rest = quelle[i:]
    assert "sys.exit(1)" in rest[:1800]
    assert "PBP laeuft bereits auf" in rest and "_open_in_chrome" in rest
    # die Reihenfolge: erst die Frage, ob es ein PBP ist, dann die „läuft bereits“-Meldung
    assert rest.index("sys.exit(1)") < rest.index("PBP laeuft bereits auf")


# ── Der Gesundheitstest des Installers ───────────────────────────────────────

def _gesundheitsschleife() -> str:
    zeilen = BAT.read_text(encoding="utf-8-sig").replace("\r\n", "\n").splitlines()
    a = next(i for i, z in enumerate(zeilen) if z.strip() == 'set "DASH_OK=0"')
    b = next(i for i, z in enumerate(zeilen) if i > a and z.strip() == ":dash_ready")
    return "\n".join(zeilen[a:b + 1])


def test_1149_der_gesundheitstest_fragt_nach_dem_inhalt_nicht_nur_nach_dem_status():
    text = _gesundheitsschleife()
    assert "/api/health" in text and "pbp_version" in text
    assert "-Uri 'http://localhost:8200/')" not in text, "die Startseite antwortet auch bei einem fremden Programm"
    # Das Dashboard lauscht nur auf IPv4. Mit `localhost` versucht Windows PowerShell zuerst ::1 und
    # brauchte dafür gemessen mehr als die Sekunde Zeitgrenze (1,3 s, "Zeitlimit überschritten") —
    # der Test schlug bei laufendem Dashboard 30 Mal fehl, der Abschluss wurde gelb.
    zeile = next(z for z in text.splitlines() if "Invoke-WebRequest" in z)
    assert "http://127.0.0.1:8200/api/health" in zeile and "localhost" not in zeile


def _in_cmd(port: int) -> str:
    """Die echte Schleife der BAT; nur der Port ist getauscht und die Zahl der Versuche verkürzt."""
    schleife = _gesundheitsschleife().replace("8200", str(port)).replace("(1,1,30)", "(1,1,2)")
    skript = ("@echo off\r\nsetlocal enabledelayedexpansion\r\n" + schleife.replace("\n", "\r\n")
              + "\r\necho ERGEBNIS DASH_OK=!DASH_OK!\r\n")
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        datei = Path(t) / "schleife.bat"
        datei.write_bytes(skript.encode("utf-8"))
        r = subprocess.run(["cmd", "/d", "/c", str(datei)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                           creationflags=OHNE_FENSTER, timeout=180)
    return r.stdout


@nur_windows
@pytest.mark.parametrize("antworten,erwartet", [
    (PBP, "1"),
    (FREMD_STARTSEITE, "0"),
    (FREMD_ALLES_200, "0"),
    (FREMD_JSON, "0"),
])
def test_1149_cmd_der_gesundheitstest_der_bat_erkennt_nur_ein_pbp(server, antworten, erwartet):
    aus = _in_cmd(server(antworten))
    assert f"ERGEBNIS DASH_OK={erwartet}" in aus, aus


@nur_windows
def test_1149_cmd_ohne_server_ist_das_dashboard_nicht_bereit():
    assert "ERGEBNIS DASH_OK=0" in _in_cmd(_frei())
