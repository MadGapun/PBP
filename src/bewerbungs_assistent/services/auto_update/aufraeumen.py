"""Aufraeumen: Reste, alte Fassungen, Belegung durch laufende Prozesse (#1093 Akzeptanzkriterium 12).

Das Auto-Update darf den Rechner nicht zumuellen, und es darf nie etwas loeschen, das gerade
benutzt wird. Beides in einem Modul, weil es dieselbe Frage ist: **wer benutzt diesen Ordner?**

Eine Fassung ist belegt, solange ein lebender Prozess eine Marke in
`versions/<fassung>/.in_benutzung/` hat (der Startbaustein legt sie an und entfernt sie beim
Beenden). Eine Marke von einem toten Prozess — oder von einem Prozess, dessen Kennung
inzwischen ein anderes Programm hat — zaehlt nicht und wird entfernt. Geloescht wird nur,
was NICHT belegt ist; was sich nicht loeschen laesst (gesperrte Datei), wird gemeldet und beim
naechsten Start erneut versucht.

Geschuetzt ist ausserdem immer: die aktuelle Fassung, die vorige (Rueckweg), die zuletzt
gestartete und die, in der dieser Prozess selbst laeuft.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import fassung as _fassung
from . import layout
from .fehler import UpdateFehler

#: Eine Sperre, die aelter ist, gilt als verwaist, auch wenn ihre Prozesskennung noch lebt (neu vergeben).
SPERRE_MAX_ALTER_S = 6 * 3600
#: Ein unfertiger Fassungsordner (ohne `.fertig`) darf so lange liegen, bevor er als Rest gilt.
UNFERTIG_MAX_ALTER_S = 2 * 3600


# ── Lebt dieser Prozess noch? ─────────────────────────────────────────────────────────

def _iso_zu_epoche(iso):
    try:
        return datetime.fromisoformat(str(iso)).timestamp()
    except (TypeError, ValueError):
        return None


def prozess_lebt(pid, start_iso=None) -> bool:
    """Lebt der Prozess `pid`, und ist es noch derselbe, der die Marke angelegt hat?

    Unter Windows: Exit-Code `STILL_ACTIVE` und Erstellzeit nicht NACH der Marke (eine
    wiederverwendete Kennung gehoert zu einem neueren Prozess). Kann der Zustand nicht
    festgestellt werden (Zugriff verweigert), gilt der Prozess als lebend: im Zweifel nichts loeschen.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _windows_lebt(pid, _iso_zu_epoche(start_iso))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_lebt(pid: int, marke_epoche) -> bool:  # pragma: no cover — nur unter Windows
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ctypes.get_last_error() == 5  # Zugriff verweigert: es gibt ihn, wir duerfen nicht fragen
    try:
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
            return True
        if code.value != 259:  # STILL_ACTIVE
            return False
        if marke_epoche is None:
            return True
        erstellt, ende, kern, nutzer = (wintypes.FILETIME() for _ in range(4))
        if not k32.GetProcessTimes(h, ctypes.byref(erstellt), ctypes.byref(ende), ctypes.byref(kern), ctypes.byref(nutzer)):
            return True
        ft = (erstellt.dwHighDateTime << 32) | erstellt.dwLowDateTime
        erstellt_epoche = (ft - 116444736000000000) / 1e7
        return erstellt_epoche <= marke_epoche + 5
    finally:
        k32.CloseHandle(h)


# ── Belegung ───────────────────────────────────────────────────────────────────────────

def belegungen(app, version: str, *, aufraeumen: bool = True) -> list:
    """Die Marken lebender Prozesse an dieser Fassung. Tote Marken werden (auf Wunsch) entfernt."""
    ordner = layout.pfade(app).fassung(version) / layout.BELEGUNG
    lebend = []
    try:
        dateien = list(ordner.glob("*.json"))
    except OSError:
        return lebend
    for d in dateien:
        try:
            daten = json.loads(d.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            daten = {}
        if isinstance(daten, dict) and prozess_lebt(daten.get("pid"), daten.get("start")):
            lebend.append(daten)
        elif aufraeumen:
            try:
                d.unlink()
            except OSError:
                pass
    return lebend


# ── Sperre: hoechstens ein Update zugleich ──────────────────────────────────────────────

@contextmanager
def sperre(app):
    """Nur ein Update zugleich — MCP-Server und Dashboard teilen den Programmordner."""
    p = layout.pfade(app).sperre
    inhalt = json.dumps({"pid": os.getpid(), "start": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    for versuch in (1, 2):
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if versuch == 2 or not _sperre_verwaist(p):
                raise UpdateFehler("gesperrt") from None
            try:
                p.unlink()
            except OSError:
                raise UpdateFehler("gesperrt") from None
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(inhalt)
        break
    try:
        yield
    finally:
        try:
            p.unlink()
        except OSError:
            pass


def _sperre_verwaist(p: Path) -> bool:
    try:
        daten = json.loads(p.read_text(encoding="utf-8"))
        start = _iso_zu_epoche(daten.get("start"))
        if start is not None and time.time() - start > SPERRE_MAX_ALTER_S:
            return True
        return not prozess_lebt(daten.get("pid"), daten.get("start"))
    except (OSError, ValueError, AttributeError):
        return True  # unlesbar: verwaist


# ── Loeschen ─────────────────────────────────────────────────────────────────────────

def _schreibbar_machen(funktion, pfad, _info):
    try:
        os.chmod(pfad, stat.S_IWRITE)
        funktion(pfad)
    except OSError:
        pass


def ordner_loeschen(pfad) -> bool:
    """Loescht einen Ordner samt Inhalt; gibt zurueck, ob er danach weg ist. Schreibgeschuetztes wird freigegeben."""
    pfad = Path(pfad)
    if not pfad.exists():
        return True
    shutil.rmtree(pfad, onerror=_schreibbar_machen)
    return not pfad.exists()


def groesse(pfad) -> int:
    """Bytes unter `pfad` (Datei oder Ordner); ein fehlender Pfad ist 0."""
    pfad = Path(pfad)
    try:
        if pfad.is_file():
            return pfad.stat().st_size
        gesamt = 0
        for wurzel, _ordner, dateien in os.walk(pfad):
            for name in dateien:
                try:
                    gesamt += os.path.getsize(os.path.join(wurzel, name))
                except OSError:
                    pass
        return gesamt
    except OSError:
        return 0


def arbeit_leeren(app, *, eigene_sperre: bool = False) -> int:
    """Leert den Arbeitsordner (Downloads, `.part`, entpackte Reste), solange kein ANDERES Update laeuft.

    `eigene_sperre=True`: der Aufrufer haelt die Sperre selbst (das Update, das gerade aufraeumt).
    Gibt die freigegebenen Bytes zurueck.
    """
    p = layout.pfade(app)
    if not eigene_sperre and p.sperre.exists() and not _sperre_verwaist(p.sperre):
        return 0
    frei = groesse(p.arbeit)
    if p.arbeit.exists():
        ordner_loeschen(p.arbeit)
    return frei


def reste_entfernen(app) -> list:
    """Angefangene Installationen (`*.neu`, `*.tmp-*`, unfertige Ordner ueber 2 Stunden) wegraeumen."""
    p = layout.pfade(app)
    entfernt = []
    if not p.versionen.is_dir():
        return entfernt
    jetzt = time.time()
    for kind in p.versionen.iterdir():
        if not kind.is_dir():
            continue
        name = kind.name
        rest = name.endswith(".neu") or ".tmp-" in name
        unfertig = (_fassung.gueltig(name) and not (kind / layout.FERTIG).exists()
                    and jetzt - kind.stat().st_mtime > UNFERTIG_MAX_ALTER_S)
        if (rest or unfertig) and ordner_loeschen(kind):
            entfernt.append(name)
    return entfernt


def fassungen_aufraeumen(app, behalten: int, *, geschuetzt=()) -> dict:
    """Loescht alte Fassungen: behalten werden die aktuelle und `behalten` Vorgaenger.

    Ergebnis: {'geloescht': [...], 'behalten': [...], 'uebersprungen': {fassung: grund}, 'frei_bytes': n}.
    """
    p = layout.pfade(app)
    status = layout.lese_status(app)
    aktuell = layout.aktuelle_fassung(app)
    schutz = {v for v in (aktuell, status.get("vorherige"), layout.laufende_fassung(), *geschuetzt) if v}
    start = status.get("start")
    if isinstance(start, dict) and start.get("version"):
        schutz.add(start["version"])
    gescheitert = {v for v in (status.get("gescheitert") or []) if isinstance(v, str)}

    alle = layout.installierte_fassungen(app)  # neueste zuerst
    bericht = {"geloescht": [], "behalten": [], "uebersprungen": {}, "frei_bytes": 0}
    if not aktuell or not layout.fassung_gueltig(app, aktuell):
        # Unklar, welche Fassung gilt: dann wird NICHTS geloescht (der Startbaustein waehlt beim naechsten Start selbst).
        bericht["behalten"] = list(alle)
        bericht["uebersprungen"]["*"] = "aktuell.txt fehlt oder zeigt auf keine fertige Fassung"
        return bericht
    schluessel_aktuell = _fassung.schluessel(aktuell)

    aeltere = [v for v in alle if schluessel_aktuell is not None and _fassung.schluessel(v) < schluessel_aktuell]
    zu_behalten = set(aeltere[:max(behalten, 0)])
    for v in alle:
        if v in schutz or v in zu_behalten:
            bericht["behalten"].append(v)
            continue
        if schluessel_aktuell is not None and _fassung.schluessel(v) > schluessel_aktuell and v not in gescheitert:
            bericht["behalten"].append(v)  # neuer als die aktuelle und nicht gescheitert: wartet auf das Umschalten
            continue
        if belegungen(app, v):
            bericht["uebersprungen"][v] = "wird gerade benutzt"
            bericht["behalten"].append(v)
            continue
        groesse_vorher = groesse(p.fassung(v))
        if ordner_loeschen(p.fassung(v)):
            bericht["geloescht"].append(v)
            bericht["frei_bytes"] += groesse_vorher
        else:
            bericht["uebersprungen"][v] = "ließ sich nicht vollständig löschen (Datei gesperrt), nächster Versuch beim Start"
            bericht["behalten"].append(v)
    return bericht
