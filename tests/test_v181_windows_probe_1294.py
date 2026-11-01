"""#1294: Die Windows-Probe in der CI ist angeschlossen und fasst ausserhalb der CI nichts an.

Die Probe selbst laeuft nur auf `windows-latest` (sie installiert und deinstalliert wirklich). Hier wird geprueft, was sich
ueberall pruefen laesst: der Workflow ruft nur Befehle auf, die das Skript kennt, beobachtet nur Dateien, die es gibt, das
Skript verweigert sich ausserhalb der CI, und die Einordnung der Port-Antworten stimmt (sie entscheidet ueber jedes Ergebnis).
"""
import importlib.util
import re
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
WORKFLOW = WURZEL / ".github" / "workflows" / "windows-probe.yml"
SKRIPT = WURZEL / "scripts" / "windows_probe.py"


@pytest.fixture(scope="module")
def probe():
    spec = importlib.util.spec_from_file_location("windows_probe", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _text():
    return WORKFLOW.read_text(encoding="utf-8")


def _pfade(ereignis):
    """Die Pfadliste unter `on.<ereignis>.paths` (ohne YAML-Bibliothek: die Suite braucht sonst keine)."""
    zeilen = _text().splitlines()
    i = zeilen.index(f"  {ereignis}:")
    j = next(k for k in range(i + 1, len(zeilen)) if zeilen[k].strip() == "paths:")
    pfade = []
    for zeile in zeilen[j + 1:]:
        if not zeile.startswith("      - "):
            break
        pfade.append(zeile[len("      - "):].strip())
    return pfade


def test_workflow_laeuft_auf_windows():
    text = _text()
    assert re.findall(r"^  ([a-z]+):\n    if:", text, re.M) == ["installer", "update"]
    assert re.findall(r"runs-on: (\S+)", text) == ["windows-latest", "windows-latest"]


def test_workflow_ruft_nur_bekannte_befehle():
    bekannt = set(re.findall(r'sub\.add_parser\("([a-z-]+)"\)', SKRIPT.read_text(encoding="utf-8")))
    befehle = set(re.findall(r"windows_probe\.py +([a-z-]+)", _text()))
    assert {"installieren", "haenger", "fremd", "deinstallieren", "update-vorbereiten", "update"} <= befehle
    assert befehle <= bekannt


def test_beobachtete_pfade_gibt_es():
    for ereignis in ("pull_request", "push"):
        pfade = _pfade(ereignis)
        assert len(pfade) >= 10, f"{ereignis}: Pfadliste nicht gefunden"
        for pfad in pfade:
            assert list(WURZEL.glob(pfad.replace("/**", ""))), f"{ereignis}: {pfad} trifft keine Datei"
    assert _pfade("pull_request") == _pfade("push")


def test_probe_verweigert_sich_ausserhalb_der_ci(probe, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("PBP_PROBE_ERLAUBT", raising=False)
    monkeypatch.setattr(probe.sys, "platform", "win32")
    aufgerufen = []
    monkeypatch.setattr(probe, "cmd_deinstallieren", lambda a: aufgerufen.append(a))
    assert probe.main(["deinstallieren"]) == 2
    assert aufgerufen == []


class _Gesund(BaseHTTPRequestHandler):
    def do_GET(self):
        koerper = b'{"pbp_version": "9.9.9"}' if self.path == "/api/health" else b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(koerper)))
        self.end_headers()
        self.wfile.write(koerper)

    def log_message(self, *a):
        pass


def _freier_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_health_erkennt_pbp(probe, monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Gesund)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(probe, "PORT", server.server_address[1])
        art, daten = probe.health(timeout=3)
        assert art == "pbp" and daten["pbp_version"] == "9.9.9"
    finally:
        server.shutdown()


def test_health_haengender_port_ist_keine_antwort(probe, monkeypatch):
    lauscher = socket.socket()
    lauscher.bind(("127.0.0.1", 0))
    lauscher.listen(8)                    # nimmt nie an: wie das angehaltene Dashboard und das fremde Programm der Probe
    try:
        monkeypatch.setattr(probe, "PORT", lauscher.getsockname()[1])
        assert probe.health(timeout=1)[0] == "keine_antwort"
    finally:
        lauscher.close()


def test_health_freier_port(probe, monkeypatch):
    # Windows wiederholt den Verbindungsversuch an einem geschlossenen Port rund zwei Sekunden lang, bevor es ablehnt.
    monkeypatch.setattr(probe, "PORT", _freier_port())
    assert probe.health(timeout=6)[0] == "frei"
