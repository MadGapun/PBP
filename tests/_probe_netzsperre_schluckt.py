"""Probe fuer die Netzsperre (#1236) -- KEIN Test der Suite (Unterstrich: wird nicht eingesammelt).

`test_v18_netzsperre_1236.py` startet diese Datei in einem eigenen pytest-Lauf, mit der echten `conftest.py`, und
liest das Ergebnis: Eine Sperre zaehlt erst, wenn sie aufgerufen wird (8c). Die drei Faelle:

* `test_lokal_ist_erlaubt` -- eine Verbindung auf den eigenen Rechner geht durch,
* `test_ein_geschluckter_versuch` -- der Code fuer den Versuch faengt jeden Fehler ab; der Test bleibt im
  Rumpf gruen und muss trotzdem am Ende scheitern (Fehler beim Abbau),
* `test_der_schluessel_ist_weg` -- der Entwickler hat einen echten Schluessel in der Umgebung; die Suite sieht ihn nicht.
"""
import os
import socket
import urllib.request


def test_lokal_ist_erlaubt():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.create_connection(server.getsockname(), timeout=2):
            pass


def test_ein_geschluckter_versuch():
    try:
        urllib.request.urlopen("http://example.com/", timeout=2)
    except Exception:  # noqa: BLE001 -- genau das tut Code, der jede Netzstoerung schluckt
        pass


def test_der_schluessel_ist_weg():
    assert os.environ.get("PBP_ANTHROPIC_API_KEY") is None
