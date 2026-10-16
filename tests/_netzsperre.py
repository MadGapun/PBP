"""Die Netzsperre der Testsuite (#1236, Stufe 1).

Kein Test darf das Netz erreichen. Der API-Weg schickt sonst im Fehlerfall echte Anfragen an
`api.anthropic.com`, und eine Suite, die das nur nicht tut, weil gerade kein Schluessel in der Umgebung
steht, schuetzt nichts: der Entwickler hat einen.

Die Sperre sitzt an den drei Stellen, durch die jede Verbindung aus Python geht:

* `socket.getaddrinfo` (jede Namensaufloesung, auch asyncio),
* `socket.socket.connect` und `connect_ex` (jede Verbindung, auch mit einer Adresse statt eines Namens),
* `socket.gethostbyname` und Verwandte.

Erlaubt sind nur lokale Ziele: `localhost`, `127.0.0.0/8`, `::1`, die unbestimmte Adresse (so bindet und
erreicht man den eigenen Rechner) und Unix-Sockets -- ausser dem Port des echten Ollama (11434, siehe
`OLLAMA_PORT`). Der Browser-Test (Uvicorn im Thread) und jeder `TestClient` laufen darueber.

Ein Versuch wird NICHT nur abgewiesen, sondern gemerkt (`VERSUCHE`): Code, der jede Netzstoerung schluckt
(`except Exception`), hat sonst einen Test gruen gemacht, der gerade das Netz zu erreichen versuchte. Die
Fixture in `conftest.py` laesst deshalb jeden Test scheitern, der einen nicht-lokalen Versuch hinterlaesst.
"""
from __future__ import annotations

import ipaddress
import socket

VERSUCHE: list[str] = []

#: Auf dem Rechner des Entwicklers laeuft ein ECHTES Ollama (Port 11434). Ein Test, der dorthin verbindet, rechnet mit seinem
#: Modell, wuerde auf einem anderen Rechner etwas anderes sehen und verbraucht Arbeitsspeicher und Zeit. Die Verbindung wird
#: abgewiesen wie die zu einem Rechner, auf dem Ollama nicht laeuft -- das ist die Annahme der Tests, die `get_status()` ohne
#: Testdoppel rufen. Anders als beim Netz wird der Versuch NICHT als Fehler gemerkt: dass PBP nach Ollama fragt und nichts
#: findet, ist sein Normalbetrieb. Ein Test, der eine lokale KI braucht, braucht ein Testdoppel am Aufruf.
OLLAMA_PORT = 11434


class NetzGesperrt(ConnectionError):
    """In der Testsuite ist das Netz gesperrt. Ein Test, der das Netz braucht, braucht ein Testdoppel."""


def ist_lokal(host) -> bool:
    if host is None:
        return True
    if isinstance(host, (bytes, bytearray)):
        host = bytes(host).decode("ascii", "replace")
    text = str(host).strip().strip("[]").lower()
    if text in ("", "localhost", "0.0.0.0", "::", "::1"):
        return True
    if text.endswith(".localhost"):
        return True
    try:
        adresse = ipaddress.ip_address(text.split("%", 1)[0])
    except ValueError:
        return False
    return adresse.is_loopback or adresse.is_unspecified


def _abweisen(host, port=None):
    ziel = f"{host}:{port}" if port is not None else f"{host}"
    if ist_lokal(host) and _ollama(port):
        raise NetzGesperrt(f"Der Port des echten Ollama ist in der Testsuite gesperrt ({ziel}); ein Testdoppel gehört an den Aufruf.")
    VERSUCHE.append(ziel)
    raise NetzGesperrt(
        f"Netz gesperrt (Testsuite): Verbindungsversuch zu {ziel}. "
        "Ein Test darf das Netz nicht erreichen; ein Testdoppel gehört an den Transport.")


def _ollama(port) -> bool:
    try:
        return int(port) == OLLAMA_PORT
    except (TypeError, ValueError):
        return False


def einschalten(monkeypatch) -> None:
    """Sperrt Namensaufloesung und Verbindungen zu allem, was nicht lokal ist. Bis zum Ende des Tests."""
    echt_getaddrinfo = socket.getaddrinfo
    echt_connect = socket.socket.connect
    echt_connect_ex = socket.socket.connect_ex
    echt_gethostbyname = socket.gethostbyname
    echt_gethostbyname_ex = socket.gethostbyname_ex

    def getaddrinfo(host, port, *args, **kwargs):
        if not ist_lokal(host) or _ollama(port):
            _abweisen(host, port)
        return echt_getaddrinfo(host, port, *args, **kwargs)

    def _ziel(adresse):
        # (host, port) oder (host, port, flow, scope); ein Unix-Socket hat einen Pfad und ist lokal
        if isinstance(adresse, tuple) and adresse:
            return adresse[0], adresse[1] if len(adresse) > 1 else None
        return None, None

    def connect(self, adresse):
        host, port = _ziel(adresse)
        if host is not None and (not ist_lokal(host) or _ollama(port)):
            _abweisen(host, port)
        return echt_connect(self, adresse)

    def connect_ex(self, adresse):
        host, port = _ziel(adresse)
        if host is not None and (not ist_lokal(host) or _ollama(port)):
            _abweisen(host, port)
        return echt_connect_ex(self, adresse)

    def gethostbyname(host):
        if not ist_lokal(host):
            _abweisen(host)
        return echt_gethostbyname(host)

    def gethostbyname_ex(host):
        if not ist_lokal(host):
            _abweisen(host)
        return echt_gethostbyname_ex(host)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "gethostbyname", gethostbyname)
    monkeypatch.setattr(socket, "gethostbyname_ex", gethostbyname_ex)
