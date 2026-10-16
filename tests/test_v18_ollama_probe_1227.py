"""#1227 (dritter Lauf, Werkstatt-PC): die Ollama-Abfrage kostete ohne Ollama unter Windows 4 s.

Gemessen auf einem Windows-11-PC ohne Ollama: ein `cProfile`-Lauf von `/api/components` in einem frischen Prozess zeigte
4,08 s von 4,60 s in `LLMService._check_ollama` (`urlopen(timeout=2.0)`); die Verbindungsprobe auf Port 11434 brauchte
2,02 s (127.0.0.1), 2,01 s (::1) und 4,07 s (localhost), jeweils ein Zeitablauf: die Firewall des PCs beantwortet das SYN an
einen geschlossenen Loopback-Port nicht. `/api/components` war ein `async def`-Handler und hielt dabei den ganzen Server an.

Hier steht, was jetzt gilt. Die Tests brauchen weder Ollama noch Netz noch eine echte Firewall: den Zeitablauf unterlegt ein
Testdoppel (das Budget ist die SUMME der uebergebenen Zeitablaeufe, nicht die Wanduhr), ein lauschender Server steht auf der
Schleife.
"""
from __future__ import annotations

import http.server
import inspect
import json
import socket
import threading
import time
import urllib.request
from types import SimpleNamespace

import pytest


@pytest.fixture
def llm(monkeypatch):
    from bewerbungs_assistent.services import llm_service
    llm_service.reset_llm_service()
    yield llm_service
    llm_service.reset_llm_service()


def _dienst(llm, endpunkt="http://localhost:11434"):
    dienst = llm.LLMService(db=None)
    dienst._status.ollama_endpoint = endpunkt
    return dienst


def _nichts_nimmt_an(llm, monkeypatch):
    """Eine Firewall, die jedes SYN verwirft: jede Verbindung laeuft in ihren Zeitablauf. Merkt sich (Adresse, Zeitablauf)."""
    gesehen = []

    def verbinden(adresse, timeout=None, **_kw):
        gesehen.append((adresse, timeout))
        raise TimeoutError("timed out")

    monkeypatch.setattr(llm, "socket", SimpleNamespace(create_connection=verbinden))
    return gesehen


def _antwort_server(host, modelle):
    """Ein kleiner Server, der wie Ollama auf /api/tags antwortet. Gibt (Server, Port) zurueck."""
    nutzlast = json.dumps({"models": [{"name": n, "size": 1, "modified_at": "2026-01-01T00:00:00Z",
                                       "details": {"family": "llama", "parameter_size": "8B"}} for n in modelle]}).encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200 if self.path == "/api/tags" else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(nutzlast)))
            self.end_headers()
            self.wfile.write(nutzlast)

        def log_message(self, *a):  # still
            pass

    klasse = http.server.ThreadingHTTPServer
    if ":" in host:
        class V6(http.server.ThreadingHTTPServer):
            address_family = socket.AF_INET6
        klasse = V6
    server = klasse((host, 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="ollama-attrappe").start()
    return server, server.server_address[1]


# ── das Budget ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_ohne_ollama_ist_die_summe_der_zeitablaeufe_hoechstens_1_2_s(llm, monkeypatch):
    gesehen = _nichts_nimmt_an(llm, monkeypatch)

    def kein_urlopen(*_a, **_kw):
        raise AssertionError("ohne annehmende Adresse darf `urlopen` nicht laufen (zweiter Zeitablauf von 2 s)")

    monkeypatch.setattr(urllib.request, "urlopen", kein_urlopen)
    dienst = _dienst(llm)
    dienst._check_ollama()
    assert [a for a, _t in gesehen] == [("127.0.0.1", 11434), ("::1", 11434)], "beide Schleifenadressen, IPv4 zuerst"
    zeiten = [t for _a, t in gesehen]
    assert all(t is not None and t <= 0.6 for t in zeiten), f"jede Probe hat einen kurzen Zeitablauf: {zeiten}"
    assert sum(zeiten) <= 1.2, f"vorher 2 x 2,0 s; jetzt hoechstens 1,2 s in Summe, hier {sum(zeiten)}"
    assert dienst._status.ollama_available is False
    assert dienst._status.available_models == []


def test_get_status_ohne_ollama_nennt_nicht_erreichbar_und_cacht(llm, monkeypatch):
    gesehen = _nichts_nimmt_an(llm, monkeypatch)
    dienst = _dienst(llm)
    status = dienst.get_status(force_refresh=True)
    assert status.ollama_available is False and status.error
    n = len(gesehen)
    dienst.get_status()                       # der Zwischenspeicher (30 s) gilt weiter
    assert len(gesehen) == n, "innerhalb der 30 s keine neue Probe"


# ── ein laufendes Ollama wird weiter erkannt ───────────────────────────────────────────────────────────────────────────

def test_ein_lauschender_server_auf_ipv4_wird_erkannt(llm):
    server, port = _antwort_server("127.0.0.1", ["llama3:8b", "qwen2.5:7b"])
    try:
        dienst = _dienst(llm, f"http://localhost:{port}")
        dienst._check_ollama()
        assert dienst._status.ollama_available is True
        assert dienst._status.available_models == ["llama3:8b", "qwen2.5:7b"]
        assert dienst._status.models_detail[0]["family"] == "llama"
        assert dienst._status.error is None
    finally:
        server.shutdown()
        server.server_close()


def test_ein_lauschender_server_nur_auf_ipv6_wird_erkannt(llm):
    try:
        server, port = _antwort_server("::1", ["llama3:8b"])
    except OSError:
        pytest.skip("kein IPv6 auf der Schleife")
    try:
        dienst = _dienst(llm, f"http://localhost:{port}")
        dienst._check_ollama()
        assert dienst._status.ollama_available is True, "::1 wird probiert und ist auch das Ziel der Abfrage"
        assert dienst._status.available_models == ["llama3:8b"]
    finally:
        server.shutdown()
        server.server_close()


def test_die_abfrage_geht_an_die_annehmende_adresse_nicht_an_localhost(llm, monkeypatch):
    """Sonst folgte auf die Probe ein zweiter Verbindungsaufbau ueber `localhost` -- mit dem Zeitablauf der anderen Adresse."""
    gesehen = []

    class Antwort:
        status = 200

        def read(self):
            return b'{"models": []}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(anfrage, timeout=None):
        gesehen.append(anfrage.full_url)
        return Antwort()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm, "socket", SimpleNamespace(create_connection=lambda adresse, timeout=None, **k: _Verbindung()))
    dienst = _dienst(llm)
    dienst._check_ollama()
    assert gesehen == ["http://127.0.0.1:11434/api/tags"]
    assert dienst._status.ollama_endpoint == "http://localhost:11434", "die angezeigte Adresse bleibt, wie sie war"


class _Verbindung:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_ein_fremder_endpunkt_geht_den_bisherigen_weg(llm, monkeypatch):
    gesehen = []

    class Antwort:
        status = 200

        def read(self):
            return b'{"models": [{"name": "m:1"}]}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(anfrage, timeout=None):
        gesehen.append((anfrage.full_url, timeout))
        return Antwort()

    def keine_probe(*_a, **_kw):
        raise AssertionError("ein Endpunkt, der nicht localhost ist, bekommt keine Schleifenprobe")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm, "socket", SimpleNamespace(create_connection=keine_probe))
    dienst = _dienst(llm, "http://192.0.2.7:11434")
    dienst._check_ollama()
    assert gesehen == [("http://192.0.2.7:11434/api/tags", 2.0)]
    assert dienst._status.available_models == ["m:1"]


# ── der Handler ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_der_handler_der_erweiterungen_ist_kein_async_handler():
    import bewerbungs_assistent.dashboard as dash
    assert not inspect.iscoroutinefunction(dash.api_components_overview), (
        "ein `async def`-Handler mit Ollama-Abfrage und Programmsuche haelt den Ereignis-Thread an (#1227)")


def test_waehrend_die_erweiterungen_warten_antworten_die_anderen_seiten(llm, tmp_path, monkeypatch):
    """Dieselbe Funktion, die der Server ausliefert, in einer kleinen App mit EINER Ereignisschleife: ein zweiter Aufruf
    darf nicht hinter der langsamen Abfrage stehen."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    from bewerbungs_assistent.database import Database

    db = Database(tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"

    class Langsam:
        def get_status(self, force_refresh=False):
            time.sleep(1.5)
            return SimpleNamespace(ollama_available=False, available_models=[])

    from bewerbungs_assistent.services import components
    monkeypatch.setattr(components, "components_dir", lambda: tmp_path / "components")
    assert str(tmp_path) in str(components.components_dir()), "Komponenten-Ordner nicht isoliert"
    monkeypatch.setattr(llm, "get_llm_service", lambda db=None: Langsam())
    vorher = dash._db
    dash._db = db
    try:
        mini = FastAPI()
        mini.get("/api/components")(dash.api_components_overview)

        @mini.get("/api/ping")
        async def ping():
            return {"ok": True}

        with TestClient(mini) as client:           # als Kontext: EINE Ereignisschleife fuer alle Anfragen
            antworten = {}
            langsam = threading.Thread(target=lambda: antworten.update(k=client.get("/api/components")), daemon=True)
            langsam.start()
            time.sleep(0.3)                         # die langsame Anfrage steckt jetzt in der Abfrage
            t0 = time.monotonic()
            assert client.get("/api/ping").json() == {"ok": True}
            dauer = time.monotonic() - t0
            langsam.join(timeout=10)
        assert antworten["k"].status_code == 200
        assert dauer < 0.8, f"die zweite Anfrage stand hinter der langsamen ({dauer:.2f} s)"
    finally:
        dash._db = vorher
        db.close()
