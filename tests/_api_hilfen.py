"""Gemeinsame Hilfen der Tests zum API-Weg (#1236): ein Testdoppel fuer den Transport und fertige Antworten.

Nichts hier erreicht das Netz. Der Transport ist eine Funktion mit der Signatur des echten
(`url, kopf, body, zeitlimit -> (status, kopfzeilen, koerper)`), die der Test mit
`api_backend.transport_setzen` einhaengt. Der Schluessel in den Tests ist ein erfundener Wert; er wird erst
zur Laufzeit zusammengesetzt, damit kein Muster eines echten Schluessels im Quelltext steht.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

#: Ein erfundener Schluessel. Er sieht aus wie ein echter, ist aber keiner und wird nirgends gesendet.
TESTSCHLUESSEL = "sk-" + "ant-api03-" + "ERFUNDENER" + "-Testwert-" + "0123456789abcdefXYZ"


def antwort(text: str = "PASST | Titel und Profil passen.", ein: int | None = 100, aus: int | None = 20, *,
            stop: str | None = "end_turn", request_id: str = "req_test", extra_bloecke=None, nutzung=True):
    """Eine 200-Antwort der Messages-API: (200, Kopfzeilen, Koerper)."""
    daten: dict = {
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
        "content": list(extra_bloecke or []) + [{"type": "text", "text": text}],
        "stop_reason": stop,
    }
    if nutzung:
        daten["usage"] = {"input_tokens": ein, "output_tokens": aus}
    return 200, {"request-id": request_id}, json.dumps(daten).encode("utf-8")


def fehlerantwort(status: int, art: str = "invalid_request_error", meldung: str = "Fehler", *, kopf=None):
    """Eine Fehlerantwort der API mit der dokumentierten Form."""
    koerper = json.dumps({"type": "error", "error": {"type": art, "message": meldung},
                          "request_id": "req_fehler"}).encode("utf-8")
    return status, dict(kopf or {}), koerper


class FakeTransport:
    """Spielt eine Liste von Antworten ab (oder wirft Ausnahmen) und merkt sich jede Anfrage.

    Eine Antwort ist ein Tupel (status, kopf, koerper) oder eine Ausnahme-Instanz; die letzte wiederholt sich,
    wenn mehr Anfragen kommen als Antworten da sind.
    """

    def __init__(self, *antworten, entscheider=None):
        """`entscheider(aufruf)` (optional) antwortet je Anfrage nach deren Inhalt, statt die Liste abzuspielen."""
        self.antworten = list(antworten) or [antwort()]
        self.entscheider = entscheider
        self.aufrufe: list[dict] = []

    def __call__(self, url, kopf, body, zeitlimit):
        self.aufrufe.append({"url": url, "kopf": dict(kopf), "body": json.loads(body.decode("utf-8")),
                             "roh": body, "zeitlimit": zeitlimit})
        if self.entscheider is not None:
            eintrag = self.entscheider(self.aufrufe[-1])
            if isinstance(eintrag, BaseException):
                raise eintrag
            return eintrag
        nr = min(len(self.aufrufe), len(self.antworten)) - 1
        eintrag = self.antworten[nr]
        if isinstance(eintrag, BaseException):
            raise eintrag
        return eintrag

    @property
    def anzahl(self) -> int:
        return len(self.aufrufe)

    @property
    def prompt(self) -> str:
        return self.aufrufe[-1]["body"]["messages"][0]["content"]


class Schlafen:
    """Ersatz fuer time.sleep: merkt sich die Wartezeiten, schlaeft nie."""

    def __init__(self):
        self.zeiten: list[float] = []

    def __call__(self, sekunden):
        self.zeiten.append(sekunden)
