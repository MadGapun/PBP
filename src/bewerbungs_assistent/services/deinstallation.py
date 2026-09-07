"""Wege zur Deinstallation — auf jeder Plattform einer (#975, I11).

Externes Feedback eines fruehen Testers (05.09.2026): *"Ich konnte das
nicht mal von PC und Laptop deinstallieren, weil das nicht wie ein
normales Programm oder eine Website aufgebaut war."*

Der Deinstaller EXISTIERT auf allen drei Plattformen. Was fehlte, waren
die Wege dorthin:

* Die Gefahrenzone im Dashboard antwortete auf allem ausser Windows mit
  HTTP 400 und dem Satz "bitte den Skript-Pfad
  installer/deinstallieren.sh im Repo nutzen" — den Pfad kennt nur, wer
  das Repo hat. Genau die Sackgassen-Definition aus G23/#927: technisch
  korrekte Antwort, keine Antwort auf die Frage.
* Der Text darueber versprach auf jeder Plattform dasselbe (Registry,
  Desktop-Verknuepfung), obwohl es davon nur unter Windows etwas gibt.

Dieses Modul beantwortet beides an einer Stelle: **was auf DIESEM
Rechner entfernt wird** und **wie der Deinstaller startet**. Es fuehrt
selbst nichts aus, ausser wenn `starten()` gerufen wird — und auch dann
nur in einem eigenen Fenster, in dem der Mensch jeden Schritt
bestaetigt.
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path


def _system() -> str:
    return platform.system()


def repo_wurzel() -> Path:
    """Das Verzeichnis, in dem INSTALLIEREN/DEINSTALLIEREN liegen."""
    return Path(__file__).resolve().parents[3]


# Was der jeweilige Deinstaller wirklich anfasst. Bewusst je Plattform
# getrennt: eine gemeinsame Liste waere auf zwei von drei falsch.
ENTFERNT = {
    "Windows": [
        "Programmdateien unter %LOCALAPPDATA%\\BewerbungsAssistent",
        "Registry-Eintrag (Programme und Features)",
        "Desktop-Verknuepfung",
        "MCP-Eintrag in Claude Desktop",
        "Nachinstallierte Komponenten (z. B. Tesseract)",
    ],
    "Darwin": [
        "MCP-Eintrag in Claude Desktop",
        "Datenverzeichnis ~/.bewerbungs-assistent (nur auf Nachfrage)",
        "Playwright-Chromium-Cache (nur auf Nachfrage)",
    ],
    "Linux": [
        "MCP-Eintrag in Claude Desktop",
        "Datenverzeichnis ~/.bewerbungs-assistent (nur auf Nachfrage)",
        "Playwright-Chromium-Cache (nur auf Nachfrage)",
    ],
}

# Was NICHT verschwindet. Der Unix-Deinstaller sagte bisher nur "der
# Quellcode bleibt" und verschwieg `.venv` und den Chromium-Cache —
# mehrere hundert Megabyte, die nach dem Loeschen des Projektordners
# liegenbleiben, ohne dass jemand davon weiss.
BLEIBT = {
    "Windows": ["Claude Desktop", "Ollama"],
    "Darwin": [
        "Der Projektordner samt Quellcode und .venv — den loeschst du "
        "selbst, wenn du ihn nicht mehr brauchst",
        "Claude Desktop", "Ollama",
    ],
    "Linux": [
        "Der Projektordner samt Quellcode und .venv — den loeschst du "
        "selbst, wenn du ihn nicht mehr brauchst",
        "Claude Desktop", "Ollama",
    ],
}


def deinstaller_pfad() -> Path | None:
    """Der Deinstaller dieser Plattform, oder None."""
    if _system() == "Windows":
        basis = os.environ.get("LOCALAPPDATA", "")
        if not basis:
            return None
        installiert = (Path(basis) / "BewerbungsAssistent" / "app"
                       / "DEINSTALLIEREN.bat")
        # BEWUSST kein Rueckfall auf die Kopie im Repo-Root. Sie entfernt
        # `%LOCALAPPDATA%\BewerbungsAssistent` — aus einem Dev-Checkout
        # heraus wuerde sie also die INSTALLIERTE Version des Nutzers
        # abraeumen, obwohl er nur im Quellcode arbeitet. Lieber "nicht
        # gefunden" melden als das Falsche treffen.
        return installiert if installiert.is_file() else None

    skript = repo_wurzel() / "installer" / "deinstallieren.sh"
    return skript if skript.is_file() else None


def befehl() -> str:
    """Der Befehl zum Kopieren — der Rueckfallweg, der immer geht."""
    pfad = deinstaller_pfad()
    if not pfad:
        return ""
    if _system() == "Windows":
        return f'"{pfad}"'
    return f'bash "{pfad}"'


def auskunft() -> dict:
    """Alles, was die Oberflaeche ueber die Deinstallation wissen muss."""
    system = _system()
    pfad = deinstaller_pfad()
    return {
        "plattform": {"Windows": "windows", "Darwin": "macos"}.get(system, "linux"),
        "gefunden": pfad is not None,
        "pfad": str(pfad) if pfad else "",
        "befehl": befehl(),
        "entfernt": ENTFERNT.get(system, ENTFERNT["Linux"]),
        "bleibt": BLEIBT.get(system, BLEIBT["Linux"]),
        "doppelklick": {
            "Windows": "DEINSTALLIEREN.bat",
            "Darwin": "DEINSTALLIEREN.command",
        }.get(system, ""),
        # Bewusst NICHT "hinweis": das Feld traegt in `starten()` den
        # Handlungs-Hinweis. Zwei verschiedene Saetze unter einem Namen
        # heisst, dass einer den anderen ueberschreibt.
        "hinweis_fremdsoftware": (
            "Claude Desktop und Ollama muessen separat deinstalliert "
            "werden — PBP fasst sie nicht an."),
    }


def _terminal_kommando(pfad: Path) -> list[str] | None:
    """Ein Terminal, das dieses System hat. None, wenn keines gefunden wird.

    Ohne Terminal liefe der Deinstaller ohne sichtbare Ausgabe — und
    seine Fragen ("Datenverzeichnis loeschen?") kaeme niemand zu Gesicht.
    Dann lieber gar nicht starten und den Befehl zum Kopieren zeigen.
    """
    if _system() == "Darwin":
        return ["open", "-a", "Terminal", str(pfad)]
    for term, args in (
        ("x-terminal-emulator", ["-e"]),
        ("gnome-terminal", ["--"]),
        ("konsole", ["-e"]),
        ("xfce4-terminal", ["-e"]),
        ("xterm", ["-e"]),
    ):
        if shutil.which(term):
            return [term, *args, "bash", str(pfad)]
    return None


def starten() -> dict:
    """Deinstaller in einem eigenen Fenster starten.

    Gibt es kein Terminal, kommt der fertige Befehl zurueck statt einer
    Fehlermeldung — ein Weg, der nicht funktioniert, ist immer noch
    besser als eine Sackgasse.
    """
    pfad = deinstaller_pfad()
    if not pfad:
        return {
            **auskunft(),
            "status": "nicht_gefunden",
            "fehler": (
                "Der Deinstaller wurde nicht gefunden. Du laeufst "
                "vermutlich aus einer Entwickler-Version, oder die "
                "Installation war unvollstaendig."),
        }

    if _system() == "Windows":
        # Detached: eigenes Fenster, eigener Prozess-Baum, damit der
        # Deinstaller den Dashboard-Prozess gefahrlos beenden kann
        # (Schritt [1/7] :stop_pbp_processes in der .bat).
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_CONSOLE = 0x00000010
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", "/D", str(pfad.parent),
                 "cmd.exe", "/c", str(pfad)],
                creationflags=(DETACHED_PROCESS | CREATE_NEW_CONSOLE
                               | CREATE_NEW_PROCESS_GROUP),
                close_fds=True,
            )
        except Exception as exc:
            return {**auskunft(), "status": "befehl", "fehler": str(exc)}
        return {
            **auskunft(),
            "status": "gestartet",
            "hinweis": ("Ein neues Konsolen-Fenster ist offen. Folge den "
                        "Anweisungen dort."),
        }

    kommando = _terminal_kommando(pfad)
    if not kommando:
        return {
            **auskunft(),
            "status": "befehl",
            "hinweis": ("Kein Terminal gefunden. Diesen Befehl in einem "
                        "Terminal ausfuehren:"),
        }
    try:
        subprocess.Popen(kommando, start_new_session=True, close_fds=True)
    except Exception as exc:
        return {**auskunft(), "status": "befehl", "fehler": str(exc)}
    return {
        **auskunft(),
        "status": "gestartet",
        "hinweis": ("Ein Terminal-Fenster ist offen. Folge den Anweisungen "
                    "dort — nichts wird ohne deine Bestaetigung geloescht."),
    }
