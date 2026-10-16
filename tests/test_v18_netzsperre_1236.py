"""#1236 Stufe 1 -- die Netzsperre der Testsuite.

Der API-Weg ruft im Fehlerfall `api.anthropic.com` auf. Eine Suite, die das nur nicht tut, weil gerade kein
Schluessel in der Umgebung steht, schuetzt nichts: der Entwickler hat einen. Die Sperre (`tests/_netzsperre.py`,
eingehaengt in `conftest.py`) weist jede Verbindung zu einem nicht-lokalen Ziel ab, und sie laesst einen Test
scheitern, der einen Versuch hinterlaesst -- auch wenn der Code ihn schluckt.

Der Beweis, dass die Sperre aufgerufen wird (8c): ein eigener pytest-Lauf mit der echten `conftest.py`.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import _netzsperre
from _netzsperre import NetzGesperrt, ist_lokal

TESTS = Path(__file__).resolve().parent


@pytest.fixture
def versuche_quittieren():
    """Dieser Test macht ABSICHTLICH Versuche; er quittiert sie, damit die Fixture sie nicht als Fehler zaehlt."""
    yield _netzsperre.VERSUCHE
    _netzsperre.VERSUCHE.clear()


@pytest.mark.parametrize("host", ["localhost", "LOCALHOST", "127.0.0.1", "127.8.9.10", "::1", "[::1]", "0.0.0.0", "",
                                  None, "api.localhost", b"127.0.0.1"])
def test_lokale_ziele_sind_erlaubt(host):
    assert ist_lokal(host) is True


@pytest.mark.parametrize("host", ["api.anthropic.com", "example.com", "8.8.8.8", "192.168.1.5", "10.0.0.1",
                                  "169.254.1.1", "2001:db8::1", "localhost.example.com", "evil-localhost", "127.0.0.1.example.com"])
def test_alles_andere_ist_gesperrt(host):
    assert ist_lokal(host) is False


def test_eine_verbindung_nach_aussen_wird_abgewiesen_und_gemerkt(versuche_quittieren):
    with pytest.raises(NetzGesperrt) as info:
        socket.create_connection(("api.anthropic.com", 443), timeout=1)
    assert "api.anthropic.com:443" in str(info.value) and "Testsuite" in str(info.value)
    assert versuche_quittieren == ["api.anthropic.com:443"]


def test_eine_verbindung_zu_einer_ip_wird_abgewiesen_ohne_namensaufloesung(versuche_quittieren):
    with socket.socket() as s:
        s.settimeout(1)
        with pytest.raises(NetzGesperrt):
            s.connect(("93.184.216.34", 80))
        with pytest.raises(NetzGesperrt):
            s.connect_ex(("93.184.216.34", 80))
    assert versuche_quittieren == ["93.184.216.34:80", "93.184.216.34:80"]


def test_jede_namensaufloesung_nach_aussen_wird_abgewiesen(versuche_quittieren):
    for aufruf in (lambda: socket.getaddrinfo("example.com", 80), lambda: socket.gethostbyname("example.com"),
                   lambda: socket.gethostbyname_ex("example.com")):
        with pytest.raises(NetzGesperrt):
            aufruf()
    assert len(versuche_quittieren) == 3


def test_urllib_zur_anthropic_api_kommt_nicht_durch(versuche_quittieren):
    """Genau der Aufruf, um den es geht: der echte Transport des API-Wegs, ohne Testdoppel."""
    anfrage = urllib.request.Request("https://api.anthropic.com/v1/messages", data=b"{}", method="POST")
    with pytest.raises(urllib.error.URLError) as info:
        urllib.request.urlopen(anfrage, timeout=2)
    assert isinstance(info.value.reason, NetzGesperrt)
    assert versuche_quittieren and versuche_quittieren[0].startswith("api.anthropic.com")


def test_der_echte_transport_des_api_wegs_wird_gesperrt_und_als_kein_netz_benannt(versuche_quittieren, monkeypatch):
    """Ohne Testdoppel laeuft `_standard_transport` in die Sperre: ein benannter Grund, kein Netz."""
    from bewerbungs_assistent.services import api_backend
    from _api_hilfen import TESTSCHLUESSEL
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)
    modell = api_backend.vorgabe_modell()
    db = _wegwerf_datenbank()
    try:
        db.set_setting(api_backend.S_BUDGET, 1_000_000)
        with pytest.raises(api_backend.ApiFehler) as info:
            api_backend._aufruf(db, modell, "Prompt", 16, "probe", budget_pflicht=False)
        assert info.value.code == "kein_netz"
        assert TESTSCHLUESSEL not in info.value.text
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)
    assert versuche_quittieren, "Der Versuch muss gemerkt sein, auch wenn der API-Weg ihn als Grund meldet"


def _wegwerf_datenbank():
    import tempfile
    ordner = tempfile.mkdtemp(prefix="pbp-netzsperre-")
    os.environ["BA_DATA_DIR"] = ordner
    from bewerbungs_assistent.database import Database
    d = Database(db_path=Path(ordner) / "test.db")
    d.initialize()
    assert str(ordner) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    return d


def test_der_port_des_echten_ollama_ist_gesperrt_aber_kein_fehler_des_tests(versuche_quittieren):
    """Auf dem Rechner des Entwicklers laeuft ein echtes Ollama. Die Tests, die `get_status()` ohne Testdoppel rufen, nehmen an,
    dass keins laeuft -- so ist es auf jedem Rechner, und in der Suite sorgt die Sperre dafuer."""
    for ziel in ("127.0.0.1", "localhost", "::1"):
        with pytest.raises(NetzGesperrt) as info:
            socket.create_connection((ziel, 11434), timeout=1)
        assert "echten Ollama" in str(info.value)
    with socket.socket() as s:
        with pytest.raises(NetzGesperrt):
            s.connect(("127.0.0.1", 11434))
    assert versuche_quittieren == [], "Dass PBP nach Ollama fragt und nichts findet, ist sein Normalbetrieb"


def test_ollama_fragt_der_dienst_nicht_beim_echten_ollama(versuche_quittieren):
    from bewerbungs_assistent.services.llm_service import LLMService
    svc = LLMService()
    status = svc.get_status(force_refresh=True)
    assert status.ollama_available is False and status.available_models == []
    assert versuche_quittieren == []


def test_andere_lokale_ports_bleiben_offen():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        assert server.getsockname()[1] != 11434
        server.listen(1)
        with socket.create_connection(server.getsockname(), timeout=2):
            pass


def test_lokale_verbindungen_gehen_durch():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.create_connection(server.getsockname(), timeout=2) as client:
            verbunden, _ = server.accept()
            client.sendall(b"x")
            assert verbunden.recv(1) == b"x"
            verbunden.close()
    assert socket.getaddrinfo("localhost", 80)


def test_die_sperre_wirkt_auch_in_einem_eigenen_pytest_lauf_mit_der_echten_conftest():
    """8c: Gruen im Repo beweist nicht, dass ein Schutz greift -- ein eigener Lauf zeigt, dass die Fixture
    registriert ist, einen geschluckten Versuch am Ende meldet und den Schluessel des Entwicklers fernhaelt."""
    env = {**os.environ, "PBP_ANTHROPIC_API_KEY": "sk-" + "ant-api03-" + "ENTWICKLER" + "-Schluessel-123456"}
    env.pop("PYTEST_ADDOPTS", None)
    lauf = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "pytest", str(TESTS / "_probe_netzsperre_schluckt.py"), "-q",
         "-p", "no:cacheprovider", "--rootdir", str(TESTS.parent)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(TESTS.parent),
        timeout=180)
    ausgabe = lauf.stdout + lauf.stderr
    assert lauf.returncode == 1, ausgabe
    assert "ERROR at teardown of test_ein_geschluckter_versuch" in ausgabe, ausgabe
    assert "ERROR at teardown of test_lokal_ist_erlaubt" not in ausgabe, ausgabe
    assert "ERROR at teardown of test_der_schluessel_ist_weg" not in ausgabe, ausgabe
    assert "3 passed, 1 error" in ausgabe, ausgabe
    assert "example.com:80" in ausgabe, "Die Meldung nennt das Ziel des Versuchs"
