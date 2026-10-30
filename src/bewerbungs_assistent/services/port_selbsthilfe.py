"""Der Start trifft auf einen belegten Port: ehrlich melden, und einen eigenen haengenden Prozess beenden (#1290).

Aufgerufen von `start_dashboard.py` (Desktop-Verknuepfung), BEVOR das Dashboard startet. Drei Ausgaenge:

* `PBP`   — dort antwortet ein PBP: der Aufrufer sagt "laeuft bereits" und oeffnet den Browser.
* `FREI`  — der Port war belegt, ist es aber nicht mehr (ein eigener, haengender Prozess wurde beendet): normal weiterstarten.
* `BELEGT`— der Port bleibt belegt; die Meldung (mit Name und Kennung, wenn bekannt) ist schon ausgegeben.

Beendet wird nur ein Prozess, der EINDEUTIG ein eigener PBP-Prozess ist (`port_besitzer.ist_eigener_pbp`) UND dessen Port
nicht antwortet (`keine_antwort`). Zusaetzlich gilt:

* Hat Claude Desktop den Prozess gestartet (`unter_claude`), haengt der MCP-Weg daran: nie automatisch, nur nach einer Frage
  im Konsolenfenster (Vorgabe NEIN). Ohne Fenster steht nur der genaue Befehl in der Meldung.
* Fremde Prozesse und "unbekannt" werden nie beendet; ebenso nie der eigene Prozess und dessen Elternprozess.
* Vor dem harten Beenden wird geprueft, dass die Kennung noch immer den Port haelt (Kennungen werden wiederverwendet).

Alles Aeussere ist austauschbar (Besitzer-Suche, Beenden, Uhr, Frage, Ausgabe), damit Tests keinen echten Prozess treffen
ausser ihrem Hilfsprozess.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time

from . import dashboard_halter as _halter
from . import port_besitzer as _besitzer

logger = logging.getLogger(__name__)

PBP = "pbp"
FREI = "frei"
BELEGT = "belegt"

#: So lange darf ein hoefliches Beenden dauern, bevor hart beendet wird, und so lange wartet der Start auf den freien Port.
HOEFLICH_S = 5.0
PORT_FREI_S = 10.0

KEIN_FENSTER = 0x08000000 if sys.platform == "win32" else 0


def port_frei(port: int, host: str = "127.0.0.1") -> bool:
    """True, wenn niemand auf dem Port lauscht (eine abgelehnte Verbindung); Zeitueberschreitung heisst belegt."""
    return not _halter.port_belegt(port, host=host)


def beenden(pid: int, hart: bool) -> bool:
    """Beendet einen Prozess: hoeflich (Windows `taskkill`, Unix SIGTERM) oder hart (`/F`, SIGKILL). True, wenn der Aufruf lief."""
    pid = int(pid)
    if pid <= 4 or pid == os.getpid():
        return False
    try:
        if sys.platform == "win32":
            argv = ["taskkill", "/PID", str(pid)] + (["/F"] if hart else [])
            subprocess.run(argv, capture_output=True, timeout=15, stdin=subprocess.DEVNULL, creationflags=KEIN_FENSTER)
            return True
        os.kill(pid, signal.SIGKILL if hart else signal.SIGTERM)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Prozess %s liess sich nicht beenden: %s", pid, exc)
        return False


def darf_beenden(besitzer: dict, eigene_pids=None) -> tuple[bool, str]:
    """Darf PBP diesen Prozess von sich aus anfassen? (ja/nein, Grund). Die einzige Stelle, die das entscheidet."""
    eigene = set(eigene_pids if eigene_pids is not None else (os.getpid(), os.getppid()))
    if not besitzer.get("bekannt") or not besitzer.get("pid"):
        return False, "unbekannt"
    if besitzer["pid"] in eigene:
        return False, "eigener_prozess"
    if not besitzer.get("ist_eigener_pbp"):
        return False, "fremd"
    return True, "eigener_pbp"


def _beenden_und_warten(port: int, besitzer: dict, *, finde_besitzer, beende, frei, uhr, pause,
                        hoeflich_s: float, frei_s: float) -> bool:
    """Hoeflich, nach `hoeflich_s` hart; wartet bis zu `frei_s` auf den freien Port. True, wenn er frei ist."""
    pid = besitzer["pid"]
    beende(pid, False)
    ende = uhr() + hoeflich_s
    while uhr() < ende:
        if frei(port):
            return True
        pause(0.2)
    if frei(port):
        return True
    # Hart: nur, wenn dieselbe Kennung den Port noch immer haelt und noch immer ein eigener PBP-Prozess ist.
    jetzt = finde_besitzer(port)
    if not jetzt.get("bekannt") or jetzt.get("pid") != pid or not darf_beenden(jetzt)[0]:
        return frei(port)
    beende(pid, True)
    ende = uhr() + frei_s
    while uhr() < ende:
        if frei(port):
            return True
        pause(0.2)
    return frei(port)


def _meldung_ausgeben(port: int, auskunft: str, besitzer: dict, ausgabe) -> None:
    ausgabe("")
    ausgabe("  ====================================================")
    ausgabe("  " + _halter.belegt_text(port, auskunft, besitzer))
    ausgabe("")
    ausgabe("  So geht es weiter:")
    if besitzer.get("bekannt") and besitzer.get("pid"):
        ausgabe(f"  1. Beende den Prozess:  {_halter.beenden_befehl(besitzer['pid'])}")
        if besitzer.get("unter_claude"):
            ausgabe("     (Claude verliert dann die Verbindung zu PBP, bis Claude Desktop")
            ausgabe("     neu gestartet wird.)")
    else:
        ausgabe("  1. Beende das Programm, das den Port belegt, oder starte")
        ausgabe("     den Rechner neu und öffne PBP dann zuerst.")
    if not (besitzer.get("bekannt") and besitzer.get("pid")):
        ausgabe(f"  2. Wer wissen will, welches Programm es ist:  netstat -ano | findstr :{port}")
    ausgabe("  ====================================================")
    ausgabe("")


def port_pruefen(port: int, *, ausgabe=print, ist_terminal=None, frage=input, auskunft_von=None, finde_besitzer=None,
                 beende=None, frei=None, uhr=time.monotonic, pause=time.sleep, hoeflich_s: float = HOEFLICH_S,
                 frei_s: float = PORT_FREI_S) -> str:
    """Der Port ist belegt (der Aufrufer hat das gesehen): `PBP`, `FREI` oder `BELEGT` (Meldung ist ausgegeben)."""
    auskunft_von = auskunft_von or _halter.port_auskunft
    finde_besitzer = finde_besitzer or _besitzer.besitzer_von_port
    beende = beende or beenden
    frei = frei or port_frei
    if ist_terminal is None:
        ist_terminal = bool(getattr(sys.stdin, "isatty", lambda: False)()) if sys.stdin is not None else False

    auskunft = auskunft_von(port)
    if auskunft == _halter.ANTWORT_PBP:
        return PBP
    besitzer = finde_besitzer(port)
    erlaubt, grund = darf_beenden(besitzer)
    logger.warning("Port %d belegt: Auskunft=%s, Kennung=%s, Name=%s, eigen=%s, unter_claude=%s, Entscheidung=%s",
                   port, auskunft, besitzer.get("pid"), besitzer.get("name"), besitzer.get("ist_eigener_pbp"),
                   besitzer.get("unter_claude"), grund if not erlaubt else "pruefen")

    if auskunft == _halter.ANTWORT_KEINE and erlaubt:
        if besitzer.get("unter_claude"):
            # Der MCP-Weg haengt an diesem Prozess: nur auf ausdruecklichen Wunsch.
            _meldung_ausgeben(port, auskunft, besitzer, ausgabe)
            if ist_terminal:
                ausgabe("  Claude Desktop hat diesen Prozess gestartet. Beendest du ihn, verliert Claude die Verbindung")
                ausgabe("  zu PBP, bis Claude Desktop neu gestartet wird.")
                try:
                    antwort = str(frage("  Jetzt beenden und das Dashboard hier starten? [j/N] ")).strip().casefold()
                except (EOFError, OSError):
                    antwort = ""
                if antwort in ("j", "ja", "y", "yes"):
                    logger.warning("Haengender PBP-Prozess %s (unter Claude) auf Wunsch beendet", besitzer["pid"])
                    if _beenden_und_warten(port, besitzer, finde_besitzer=finde_besitzer, beende=beende, frei=frei,
                                           uhr=uhr, pause=pause, hoeflich_s=hoeflich_s, frei_s=frei_s):
                        return FREI
                    ausgabe("  Der Prozess ließ sich nicht beenden. Beende ihn von Hand (siehe oben).")
            return BELEGT
        ausgabe("")
        ausgabe(f"  {_halter.belegt_text(port, auskunft, besitzer)}")
        ausgabe("  PBP beendet ihn jetzt und startet das Dashboard neu ...")
        logger.warning("Haengender PBP-Prozess %s wird beendet (nicht von Claude gestartet)", besitzer["pid"])
        if _beenden_und_warten(port, besitzer, finde_besitzer=finde_besitzer, beende=beende, frei=frei, uhr=uhr,
                               pause=pause, hoeflich_s=hoeflich_s, frei_s=frei_s):
            return FREI
        ausgabe("  Der Prozess ließ sich nicht beenden.")
        _meldung_ausgeben(port, auskunft, besitzer, ausgabe)
        return BELEGT

    _meldung_ausgeben(port, auskunft, besitzer, ausgabe)
    return BELEGT
