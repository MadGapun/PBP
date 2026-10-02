"""Wer haelt das Dashboard — und damit den Planer? (#1155)

Das Dashboard liegt auf EINEM Port (8200). Zwei PBP-Prozesse koennen ihn nicht
teilen: der MCP-Prozess, den Claude Desktop startet, und das eigenstaendige
Dashboard (Desktop-Verknuepfung). Wer zuerst da ist, hat das Dashboard — und
den Planer (taegliche Sicherung, geplante Suche, Lernen). Der zweite startet
beides nicht, damit nichts doppelt laeuft.

Bis v1.7.147 blieb es dabei: schloss man das andere Fenster, gab es bis zum
Neustart von Claude Desktop weder Dashboard noch Sicherung noch geplante Suche,
und die Karte "Sicherungen" versprach weiter "PBP sichert einmal am Tag von
selbst". Jetzt sieht der Prozess, der den Port nicht bekam, in Abstaenden
nach (`server.dashboard_nachholen_starten`) und uebernimmt, sobald er frei ist.

Dieses Modul haelt nur den Stand, damit `pbp_diagnose` ihn nennen kann, ohne
`server` zu importieren (das oeffnet beim Import eine Datenbank).
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

EIGENER = "eigener_prozess"
ANDERER = "anderer_prozess"
KEINER = "keiner"

_lock = threading.Lock()
_zustand: dict = {}


def zuruecksetzen() -> None:
    """Zurueck auf "noch nicht entschieden" (Start und Tests)."""
    with _lock:
        _zustand.clear()
        _zustand.update({
            "halter": KEINER, "port": None, "seit": None, "server": None,
            "fehler": "", "entschieden": False, "pruefintervall_s": None,
            "nachhol_versuche": 0,
        })


zuruecksetzen()


def setzen(halter: str, port: int | None = None, server=None, fehler: str = "") -> None:
    """Haelt fest, wer das Dashboard in diesem Prozess hat."""
    with _lock:
        _zustand.update({
            "halter": halter, "port": port, "server": server, "fehler": fehler,
            "entschieden": True,
            "seit": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })


def pruefintervall_merken(sekunden: float | None) -> None:
    with _lock:
        _zustand["pruefintervall_s"] = sekunden


def versuch_zaehlen() -> None:
    with _lock:
        _zustand["nachhol_versuche"] = _zustand.get("nachhol_versuche", 0) + 1


def server():
    """Der uvicorn-Server dieses Prozesses (zum sauberen Beenden) oder None."""
    with _lock:
        return _zustand.get("server")


def lesen() -> dict:
    """Der Stand ohne das Server-Objekt."""
    with _lock:
        return {k: v for k, v in _zustand.items() if k != "server"}


def beschreiben() -> dict | None:
    """Eine Auskunft fuer `pbp_diagnose`, oder None, solange nichts entschieden ist.

    Rueckgabe: {"art": "info"|"warnung", "meldung": str}
    """
    z = lesen()
    if not z["entschieden"]:
        return None
    port = z["port"]
    if z["halter"] == EIGENER:
        return {"art": "info",
                "meldung": (f"Dashboard und Planer (tägliche Sicherung, geplante Suche) "
                            f"laufen in diesem Prozess (Port {port}).")}
    if z["halter"] == ANDERER:
        intervall = z.get("pruefintervall_s")
        minuten = max(1, round(intervall / 60)) if intervall else None
        wann = (f" Schließt du es, übernimmt dieser Prozess innerhalb von etwa "
                f"{minuten} {'Minute' if minuten == 1 else 'Minuten'}."
                if minuten else "")
        return {"art": "info",
                "meldung": (f"Port {port} gehört einem anderen PBP-Fenster: dort laufen "
                            f"das Dashboard und der Planer (tägliche Sicherung, geplante "
                            f"Suche).{wann}")}
    return {"art": "warnung",
            "meldung": ("Das Dashboard läuft in keinem Prozess"
                        + (f": {z['fehler']}" if z.get("fehler") else "")
                        + ". Die tägliche Sicherung und die geplante Suche laufen so nicht.")}
