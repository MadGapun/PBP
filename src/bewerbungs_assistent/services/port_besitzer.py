"""Wer haelt einen Port? (#1290)

Am 30.10.2026 hielt ein haengender eigener PBP-Prozess den Port 8200; PBP schrieb "ein ANDERES Programm (kein PBP)", weil
es nur fragte, OB dort ein PBP antwortet, nie WEM der Port gehoert. Dieses Modul beantwortet die zweite Frage, damit
Meldungen Namen und Kennung nennen koennen und `port_selbsthilfe` einen eigenen, haengenden Prozess von einem fremden
unterscheiden kann.

Nur Standardbibliothek (psutil ist keine Abhaengigkeit):

* Windows: `netstat -ano -p TCP` fuer die Kennung, danach EIN PowerShell-Aufruf (`Get-CimInstance Win32_Process`) fuer
  Name, Kommandozeile, Elternprozess und Startzeit.
* macOS/Linux: `lsof -nP -iTCP:<port> -sTCP:LISTEN -Fp`, danach `ps`. Fehlt ein Werkzeug, bleibt es bei "unbekannt".

Regel: jeder Fehler heisst "unbekannt" (`bekannt` False), nie eine Ausnahme nach aussen, und im Zweifel ist ein Prozess
NICHT eigen. "Eigen" heisst: die Kommandozeile nennt `bewerbungs_assistent_boot` oder `start_dashboard.py` UND liegt im
eigenen Programmordner. Die Ausgabe der Konsolenprogramme wird als Bytes gelesen (OEM-Kodierung, L44/#1182).

Alles, was die Aussenwelt beruehrt, wird hereingereicht (`ausfuehren`, `plattform`, `ordner`), damit die Tests mit
gefaelschten Prozesslisten laufen.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .konsole import text_lesen

logger = logging.getLogger(__name__)

KEIN_FENSTER = 0x08000000 if sys.platform == "win32" else 0
#: Zeitgrenze je Hilfsprogramm. PowerShell braucht gemessen 1 bis 2 s zum Start.
ZEIT_S = 12.0
KOMMANDO_MAX = 300
#: Woran man einen PBP-Prozess in der Kommandozeile erkennt (klein geschrieben).
MARKEN = ("bewerbungs_assistent_boot", "start_dashboard.py")

_NETSTAT = re.compile(r"^\s*TCP\s+(\S+):(\d+)\s+(\S+):(\d+)\s+\S+\s+(\d+)\s*$", re.IGNORECASE)

_POWERSHELL = (
    "$ErrorActionPreference='Stop';"
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
    "$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}';"
    "if(-not $p){exit 3};"
    "$e=$null;if($p.ParentProcessId){$e=Get-CimInstance Win32_Process -Filter ('ProcessId='+$p.ParentProcessId)};"
    "$c=$null;if($p.CreationDate){$c=$p.CreationDate.ToString('yyyy-MM-dd HH:mm:ss')};"
    "[pscustomobject]@{name=$p.Name;cmd=$p.CommandLine;ppid=[int]$p.ParentProcessId;start=$c;pname=$e.Name}"
    "|ConvertTo-Json -Compress"
)


def unbekannt(port: int | None = None) -> dict:
    """Die Auskunft, wenn sich nichts feststellen laesst. Nichts daran erlaubt einen Eingriff."""
    return {"bekannt": False, "port": port, "pid": None, "name": "", "kommandozeile": "", "ppid": None,
            "eltern_name": "", "gestartet": "", "seit_text": "", "ist_eigener_pbp": False, "unter_claude": False}


# ── Aufruf von Hilfsprogrammen ────────────────────────────────────────────────────────

def _ausfuehren(argv: list[str], timeout: float = ZEIT_S, env: dict | None = None) -> bytes | None:
    """Fuehrt ein Hilfsprogramm unsichtbar aus; die Ausgabe als Bytes oder None bei jedem Fehler (auch Rueckgabewert != 0)."""
    try:
        r = subprocess.run(argv, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL,
                           creationflags=KEIN_FENSTER, env=env)
    except Exception as exc:  # noqa: BLE001 — Werkzeug fehlt, Zeitgrenze, kein Recht: alles heisst unbekannt
        logger.debug("Port-Besitzer: %s nicht ausfuehrbar: %s", argv[0], exc)
        return None
    return r.stdout if r.returncode == 0 else None


# ── Ausgaben lesen (rein, ohne Aussenwelt) ────────────────────────────────────────────

def parse_netstat(text: str, port: int) -> int | None:
    """Die Kennung des Prozesses, der `port` abhoert. None, wenn keiner oder mehrere verschiedene.

    Die Zustandsspalte ist uebersetzt ("ABHOEREN" auf einem deutschen Windows), darum zaehlt die Gegenseite: ein
    lauschender Eintrag hat dort Port 0.
    """
    pids = set()
    for zeile in str(text).splitlines():
        m = _NETSTAT.match(zeile)
        if m and int(m.group(2)) == int(port) and int(m.group(4)) == 0:
            pids.add(int(m.group(5)))
    return next(iter(pids)) if len(pids) == 1 else None


def parse_lsof(text: str) -> int | None:
    """`lsof -Fp` schreibt je Prozess eine Zeile `p<Kennung>`; None bei keiner oder mehreren verschiedenen."""
    pids = {int(z[1:]) for z in str(text).splitlines() if re.fullmatch(r"p\d+", z.strip())}
    return next(iter(pids)) if len(pids) == 1 else None


def parse_ps(text: str) -> dict | None:
    """`ps -o ppid=,lstart=,command=`: Elternkennung, Startzeit (5 Woerter, Sprache C) und Kommandozeile."""
    m = re.match(r"^\s*(\d+)\s+(\w{3}\s+\w{3}\s+\d+\s+\d\d:\d\d:\d\d\s+\d{4})\s+(.*)$", str(text).strip(), re.DOTALL)
    if not m:
        return None
    try:
        gestartet = datetime.strptime(re.sub(r"\s+", " ", m.group(2)), "%a %b %d %H:%M:%S %Y").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        gestartet = ""
    return {"ppid": int(m.group(1)), "gestartet": gestartet, "kommandozeile": m.group(3).strip()}


def parse_powershell(text: str) -> dict | None:
    try:
        d = json.loads(str(text).strip().lstrip("\ufeff"))
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    return {"name": str(d.get("name") or ""), "kommandozeile": str(d.get("cmd") or ""),
            "ppid": d.get("ppid") if isinstance(d.get("ppid"), int) and d.get("ppid") else None,
            "gestartet": str(d.get("start") or ""), "eltern_name": str(d.get("pname") or "")}


# ── Eigen oder fremd ──────────────────────────────────────────────────────────────────

def eigene_ordner() -> list[str]:
    """Der Programmordner dieser PBP-Installation: `PBP_APP_DIR` (Startbaustein), sonst der Ordner dieses Quellbaums.

    Bewusst KEIN `sys.prefix` und kein uebergeordneter Ordner: der koennte `C:\\` sein, und dann waere jeder Prozess "eigen".
    """
    roh = os.environ.get("PBP_APP_DIR")
    if roh:
        return [roh]
    try:
        return [str(Path(__file__).resolve().parents[3])]
    except (OSError, IndexError):
        return []


def _norm(pfad: str, windows: bool) -> str:
    return pfad.replace("/", "\\").casefold() if windows else pfad


def ist_eigene_kommandozeile(kommandozeile: str, ordner, plattform: str | None = None) -> bool:
    """Gehoert die Kommandozeile zu einem PBP-Prozess aus einem der eigenen Ordner? Im Zweifel nein."""
    plattform = plattform or sys.platform
    windows = plattform == "win32"
    if not kommandozeile or not ordner:
        return False
    zeile = _norm(kommandozeile, windows)
    if not any(marke in zeile.casefold() for marke in MARKEN):
        return False
    for o in ordner:
        if not o:
            continue
        wurzel = _norm(str(o), windows).rstrip("\\/") if windows else str(o).rstrip("/")
        trenner = "\\" if windows else "/"
        if wurzel and (wurzel + trenner) in zeile:
            return True
    return False


def unter_claude(eltern_name: str) -> bool:
    """Hat Claude Desktop (oder Claude Code) den Prozess gestartet? Dann haengt der MCP-Weg daran."""
    return "claude" in (eltern_name or "").casefold()


def _seit_text(gestartet: str) -> str:
    try:
        return datetime.strptime(gestartet, "%Y-%m-%d %H:%M:%S").strftime("%d.%m. %H:%M")
    except ValueError:
        return ""


# ── Der Besitzer ─────────────────────────────────────────────────────────────────────

def _fuellen(b: dict, details: dict | None, ordner, plattform: str) -> dict:
    if details:
        b["name"] = details.get("name") or b["name"]
        b["kommandozeile"] = (details.get("kommandozeile") or "")[:KOMMANDO_MAX]
        b["ppid"] = details.get("ppid")
        b["eltern_name"] = details.get("eltern_name") or ""
        b["gestartet"] = details.get("gestartet") or ""
        b["seit_text"] = _seit_text(b["gestartet"])
        b["ist_eigener_pbp"] = ist_eigene_kommandozeile(details.get("kommandozeile") or "", ordner, plattform)
        b["unter_claude"] = unter_claude(b["eltern_name"])
    return b


def _besitzer_windows(port: int, ausfuehren, ordner, plattform: str) -> dict:
    roh = ausfuehren(["netstat", "-ano", "-p", "TCP"], ZEIT_S, None)
    pid = parse_netstat(text_lesen(roh), port) if roh else None
    if pid is None:
        return unbekannt(port)
    b = dict(unbekannt(port), bekannt=True, pid=pid)
    skript = _POWERSHELL.replace("{pid}", str(int(pid)))
    roh = ausfuehren(["powershell", "-NoProfile", "-NonInteractive", "-Command", skript], ZEIT_S, None)
    details = parse_powershell(text_lesen(roh, "utf-8")) if roh else None
    return _fuellen(b, details, ordner, plattform)


def _besitzer_unix(port: int, ausfuehren, ordner, plattform: str) -> dict:
    roh = ausfuehren(["lsof", "-nP", f"-iTCP:{int(port)}", "-sTCP:LISTEN", "-Fp"], ZEIT_S, None)
    pid = parse_lsof(text_lesen(roh, "utf-8")) if roh else None
    if pid is None:
        return unbekannt(port)
    b = dict(unbekannt(port), bekannt=True, pid=pid)
    env = dict(os.environ, LC_ALL="C", LANG="C")
    roh = ausfuehren(["ps", "-o", "ppid=,lstart=,command=", "-p", str(int(pid))], ZEIT_S, env)
    details = parse_ps(text_lesen(roh, "utf-8")) if roh else None
    if details is None:
        return b
    roh = ausfuehren(["ps", "-o", "comm=", "-p", str(details["ppid"])], ZEIT_S, env)
    details["eltern_name"] = text_lesen(roh, "utf-8").strip() if roh else ""
    cmd = details["kommandozeile"]
    details["name"] = Path(cmd.split(" ", 1)[0]).name if cmd else ""
    return _fuellen(b, details, ordner, plattform)


def besitzer_von_port(port: int, *, ausfuehren=None, plattform: str | None = None, ordner=None) -> dict:
    """Wer lauscht auf `port` (Loopback)? Ein Woerterbuch mit `bekannt`, `pid`, `name`, `kommandozeile` (gekuerzt),
    `ppid`, `eltern_name`, `gestartet`/`seit_text`, `ist_eigener_pbp` und `unter_claude`.

    Jeder Fehler ergibt `unbekannt(port)`. `ausfuehren(argv, timeout, env) -> bytes|None`, `plattform` und `ordner`
    (Liste eigener Programmordner) sind fuer Tests austauschbar.
    """
    try:
        plattform = plattform or sys.platform
        ausfuehren = ausfuehren or _ausfuehren
        ordner = eigene_ordner() if ordner is None else list(ordner)
        if plattform == "win32":
            return _besitzer_windows(int(port), ausfuehren, ordner, plattform)
        return _besitzer_unix(int(port), ausfuehren, ordner, plattform)
    except Exception as exc:  # noqa: BLE001 — nie eine Ausnahme nach aussen
        logger.debug("Port-Besitzer fuer %s nicht feststellbar: %s", port, exc)
        return unbekannt(port)
