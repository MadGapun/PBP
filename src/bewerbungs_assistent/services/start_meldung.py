"""Wenn der Start der Desktop-Verknuepfung am Port endet, soll das jemand sehen (#1393).

Am 16.11.2026 endete der Klick auf die Verknuepfung nach `port_selbsthilfe` ohne
Zeile im Log und ohne Fenster: der Nutzer klickte ein zweites Mal. Hier steht das
Ende im Log, und wo kein Terminal davor sitzt (unter Windows ein Start ohne
Konsole), erscheint ein Meldungsfenster. Proben und Tests (PBP_KEIN_BROWSER)
bekommen nie ein Fenster.
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("bewerbungs_assistent.start_meldung")


def _messagebox(titel: str, text: str) -> None:  # pragma: no cover - nur Windows, nur interaktiv
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, text, titel, 0x40 | 0x1000)  # Info, im Vordergrund


def start_endet(port: int, ergebnis: str, *, ist_terminal: bool | None = None, plattform: str | None = None,
                box=None, env=None) -> bool:
    """Loggt das Ende des Starts; zeigt es, wenn niemand ein Terminal sieht. True, wenn ein Fenster erschien."""
    logger.warning("Start endet: Port %d bleibt belegt (Ergebnis=%s) — das Dashboard wurde nicht gestartet", port, ergebnis)
    env = os.environ if env is None else env
    plattform = plattform or sys.platform
    if ist_terminal is None:
        ist_terminal = bool(getattr(sys.stdin, "isatty", lambda: False)()) if sys.stdin is not None else False
    if ist_terminal or plattform != "win32" or env.get("PBP_KEIN_BROWSER"):
        return False
    text = (f"Das Dashboard konnte nicht gestartet werden: Der Anschluss {port} wird schon von einem Programm "
            "benutzt, das nicht antwortet.\n\nEinzelheiten stehen in der Logdatei pbp.log. Beende PBP über den "
            "Task-Manager (Prozess „python“) oder starte den Rechner neu und öffne PBP dann zuerst.")
    try:
        (box or _messagebox)("PBP startet nicht", text)
        return True
    except Exception as exc:  # noqa: BLE001 — eine Meldung darf den Abbruch nie verhindern
        logger.warning("Meldungsfenster nicht angezeigt: %s", exc)
        return False
