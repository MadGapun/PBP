"""Ollama mit PBP starten — auf Wunsch, nicht von allein (#1001).

Nutzerwunsch vom 09.09.2026:

    "Ich moechte die Option haben, dass ich Ollama automatisch mit PBP
    starte."

PBP konnte Ollama schon vorher starten — aber nur auf Knopfdruck
(`POST /api/llm/start`, #637). Nach einem Neustart des Rechners, einem
Taskmanager-Stop oder ohne eingerichteten Ollama-Dienst stand die lokale
KI auf "nicht erreichbar", bis jemand das Dashboard oeffnet und den Knopf
drueckt. Die Hintergrund-Aufgaben (Auto-Aussortierung, Lernlauf) liefen
zu dem Zeitpunkt laengst — nur eben ohne lokale KI.

Drei Entscheidungen, die dieses Modul traegt:

(1) **Die Vorgabe ist AUS.** Einen fremden Prozess ungefragt zu starten
    ist eine Nebenwirkung, die niemand bestellt hat. Wer sie will, sagt
    es einmal; danach gilt es.

(2) **Es gibt genau EINE Start-Logik.** `ollama_starten()` wird vom
    Autostart UND vom Knopf im Dashboard aufgerufen. Eine zweite Fassung
    daneben waere das Muster aus #963/#991/#992 zum achten Mal — und
    diesmal an einer Stelle, an der die beiden Fassungen mit Sicherheit
    auseinanderlaufen (Binary-Suche, Detach-Flags).

(3) **Fuenf Ausgaenge, nicht "geht" und "geht nicht".** `abgeschaltet`,
    `lokale_ki_aus`, `lief_bereits`, `gestartet`, `nicht_installiert`
    (plus `fehler`) bedeuten voellig Verschiedenes und verlangen
    verschiedene naechste Schritte. Sie zu einer Absage zu verschmelzen
    waere genau der Fehler aus #989.

Der Prozess wird LOSGELOEST gestartet: endet PBP, laeuft Ollama weiter.
Andersherum verschwaende ein Modell mitten in einem Lauf. Wer Ollama mit
PBP beenden will, sagt es seit #1086 ausdruecklich (Einstellung
`llm_local_autostop`, Knopf, Desktop-Verknuepfung) — siehe unten.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)

# Der Schluessel in `profile_settings`. Bewusst in derselben Familie wie
# `llm_local_state` und `llm_local_model` — wer die lokale KI sucht,
# findet alle drei Einstellungen nebeneinander.
AUTOSTART_SCHLUESSEL = "llm_local_autostart"

# Am Profil, nicht im Browser: PBP startet haeufig ueber Claude Desktop,
# und dort sieht niemand das Dashboard.
VORGABE = False

# Windows: DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
_WIN_LOSGELOEST = 0x00000008 | 0x00000200

_autostart_thread: threading.Thread | None = None

# Hat DIESER PBP-Prozess Ollama gestartet? Die Einstellung "nur wenn PBP
# es gestartet hat" (#1086) fragt genau das — ein Ollama, das schon vorher
# lief, gehoert jemand anderem.
_von_pbp_gestartet: int | None = None


# -- Wo liegt Ollama? -------------------------------------------------

def _bekannte_orte() -> list:
    """Installationsorte, die Ollamas eigene Installer benutzen.

    Der PATH allein genuegt nicht: startet PBP als MCP-Server, erbt es
    die Umgebung von Claude Desktop, und die ist nicht die der
    Anmelde-Shell. Ein `which`-Fehlschlag wuerde dort als "nicht
    installiert" gemeldet, obwohl Ollama danebensteht — dieselbe
    Verwechslung von "nicht gefunden" mit "nicht vorhanden", die #989
    beschreibt.
    """
    if sys.platform == "win32":
        return [
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Programs", "Ollama", "ollama.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""),
                         "Ollama", "ollama.exe"),
        ]
    if sys.platform == "darwin":
        return [
            "/usr/local/bin/ollama",
            "/opt/homebrew/bin/ollama",
            "/Applications/Ollama.app/Contents/Resources/ollama",
        ]
    return ["/usr/local/bin/ollama", "/usr/bin/ollama",
            os.path.expanduser("~/.local/bin/ollama")]


def binary_finden():
    """Pfad zur Ollama-Binary oder None."""
    gefunden = shutil.which("ollama")
    if gefunden:
        return gefunden
    for pfad in _bekannte_orte():
        if pfad and os.path.isfile(pfad):
            return pfad
    return None


# -- Die Einstellung --------------------------------------------------

def autostart_gewuenscht(db) -> bool:
    """Liest die Einstellung. Fehlt sie, gilt die Vorgabe (AUS)."""
    try:
        wert = db.get_profile_setting(AUTOSTART_SCHLUESSEL,
                                      "true" if VORGABE else "false")
    except Exception:
        return VORGABE
    return str(wert).strip().lower() in ("true", "1", "yes", "an", "ja")


def lokale_ki_zustand(db) -> str:
    """`off` / `paused` / `active` — derselbe Schluessel, den
    `llm_service` liest (dort `llm_local_state`)."""
    try:
        wert = db.get_profile_setting("llm_local_state", "off")
    except Exception:
        return "off"
    wert = str(wert).strip().lower()
    return wert if wert in ("off", "paused", "active") else "off"


def darf_starten(autostart: bool, zustand: str):
    """Die Torfrage, absichtlich OHNE Datenbank und ohne Netz.

    Rueckgabe: (ja, status, begruendung).

    Die Bedingung `zustand == 'active'` ist dieselbe, die der
    Warmup-Loop aus #638 schon kennt: wer die lokale KI abbestellt hat,
    soll keinen Dienst im Arbeitsspeicher haben. Wer den Autostart
    trotzdem gesetzt hat, bekommt das GESAGT — eine Einstellung, die
    stillschweigend nichts tut, ist der Fehler aus #988.
    """
    if not autostart:
        return (False, "abgeschaltet",
                "Der Autostart ist aus. Das ist die Vorgabe — PBP startet "
                "keine fremden Programme, solange niemand darum bittet.")
    if zustand != "active":
        return (False, "lokale_ki_aus",
                "Der Autostart ist an, aber die lokale KI steht auf "
                "'" + zustand + "'. PBP startet Ollama deshalb nicht — ein "
                "Dienst, den du gerade abbestellt hast, soll keinen "
                "Arbeitsspeicher belegen. Setze die lokale KI auf 'active', "
                "dann greift der Autostart.")
    return (True, "bereit", "Autostart ist an und die lokale KI ist aktiv.")


def autostart_setzen(db, an: bool) -> dict:
    """Setzt die Einstellung und sagt, was sie ab jetzt bewirkt."""
    db.set_profile_setting(AUTOSTART_SCHLUESSEL, "true" if an else "false")
    antwort = autostart_lesen(db)
    if an and not antwort["ollama_gefunden"]:
        # Sofort sagen, statt beim naechsten Start still zu scheitern.
        antwort["warnung"] = (
            "Ollama ist auf diesem Rechner nicht zu finden. Die "
            "Einstellung ist gespeichert, wirkt aber erst nach der "
            "Installation: https://ollama.com/download")
    return antwort


def autostart_lesen(db) -> dict:
    """Der Lesepfad — dieselbe Antwortform wie `autostart_setzen`."""
    an = autostart_gewuenscht(db)
    zustand = lokale_ki_zustand(db)
    _, status, begruendung = darf_starten(an, zustand)
    return {
        "autostart": an,
        "lokale_ki": zustand,
        "wirkung": status,
        "hinweis": begruendung,
        "ollama_gefunden": binary_finden() is not None,
    }


# -- Der Start selbst (EINE Fassung, zwei Aufrufer) -------------------

def ollama_starten(db) -> dict:
    """Startet `ollama serve` losgeloest — oder sagt, warum nicht.

    Wird vom Autostart UND vom Knopf `POST /api/llm/start` aufgerufen.
    """
    from .llm_service import get_llm_service

    try:
        stand = get_llm_service(db).get_status(force_refresh=True)
        laeuft = bool(stand.ollama_available)
        endpunkt = stand.ollama_endpoint
    except Exception as exc:      # Statuscheck darf den Start nie verhindern
        logger.debug("Ollama-Statuscheck fehlgeschlagen: %s", exc)
        laeuft, endpunkt = False, "http://localhost:11434"

    if laeuft:
        return {"status": "lief_bereits", "endpoint": endpunkt}

    binary = binary_finden()
    if binary is None:
        return {
            "status": "nicht_installiert",
            "fehler": "Ollama wurde weder im PATH noch an den bekannten "
                      "Installationsorten gefunden.",
            "hilfe_url": "https://ollama.com/download",
            "hinweis": "Lade Ollama von ollama.com/download herunter. "
                       "PBP erkennt es danach von selbst.",
        }

    kwargs = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        # Losgeloest: endet PBP, laeuft Ollama weiter.
        kwargs["creationflags"] = _WIN_LOSGELOEST
    else:
        kwargs["start_new_session"] = True

    try:
        prozess = subprocess.Popen([binary, "serve"], **kwargs)
    except FileNotFoundError:
        return {
            "status": "nicht_installiert",
            "fehler": "Gefundener Pfad liess sich nicht starten: " + binary,
            "hilfe_url": "https://ollama.com/download",
        }
    except OSError as exc:
        return {"status": "fehler", "fehler": "Start fehlgeschlagen: %s" % exc}

    global _von_pbp_gestartet
    _von_pbp_gestartet = prozess.pid
    return {
        "status": "gestartet",
        "pid": prozess.pid,
        "binary": binary,
        "hinweis": "Ollama wurde gestartet. Der Status wechselt in den "
                   "naechsten 10-30 Sekunden auf 'verfuegbar'.",
    }


# -- Der Aufruf beim Start von PBP ------------------------------------

def beim_start(db) -> dict:
    """Wird beim Hochfahren von PBP gerufen — von BEIDEN Startwegen.

    Haelt PBP nicht auf: die Torfrage sind zwei lokale Lesevorgaenge, der
    Rest laeuft in einem Thread. Ein fehlendes Ollama darf den Start von
    PBP unter keinen Umstaenden verzoegern oder abbrechen.
    """
    global _autostart_thread

    ja, status, begruendung = darf_starten(autostart_gewuenscht(db),
                                           lokale_ki_zustand(db))
    if not ja:
        logger.debug("Ollama-Autostart uebersprungen: %s", status)
        return {"status": status, "hinweis": begruendung}

    if _autostart_thread is not None and _autostart_thread.is_alive():
        return {"status": "laeuft_schon",
                "hinweis": "Ein Startversuch laeuft bereits."}

    def _versuch():
        try:
            ergebnis = ollama_starten(db)
        except Exception as exc:   # niemals den Startpfad beschaedigen
            logger.warning("Ollama-Autostart fehlgeschlagen: %s", exc)
            return
        if ergebnis.get("status") == "gestartet":
            logger.info("Ollama automatisch gestartet (PID %s)",
                        ergebnis.get("pid"))
        elif ergebnis.get("status") == "lief_bereits":
            logger.debug("Ollama lief bereits — nichts zu tun.")
        else:
            logger.warning("Ollama-Autostart: %s (%s)",
                           ergebnis.get("status"), ergebnis.get("fehler"))

    _autostart_thread = threading.Thread(target=_versuch, daemon=True,
                                         name="ollama-autostart")
    _autostart_thread.start()
    return {"status": "wird_versucht", "hinweis": begruendung}


# -- Beenden (#1086) ----------------------------------------------------
#
# Nutzerwunsch vom 25.09.2026: Ollama belegt Arbeitsspeicher, auch wenn
# PBP stundenlang nicht mehr benutzt wird. Den meisten Speicher belegt das
# geladene Modell, und der Warmup-Loop aus #638 haelt es warm, solange PBP
# laeuft. Drei Wege, dieselbe Beenden-Logik:
#
# * der Knopf im Einstellungen-Tab (mit Rueckfrage im Dialog),
# * eine Desktop-Verknuepfung, die vor dem Beenden fragt,
# * die Einstellung "beim Beenden von PBP".
#
# Die Rueckfrage fuer die Einstellung kommt beim EINSCHALTEN: PBP endet
# meist, wenn Claude Desktop geschlossen wird, und dann gibt es kein
# Fenster mehr, in dem jemand antworten koennte.

AUTOSTOP_SCHLUESSEL = "llm_local_autostop"

#: Die drei Werte der Einstellung, mit dem Satz, der sie erklaert.
AUTOSTOP_WERTE = {
    "aus": "PBP laesst Ollama beim Beenden laufen.",
    "gestartet": "PBP beendet Ollama beim Beenden, wenn PBP es selbst "
                 "gestartet hat. Ein Ollama, das schon vorher lief, bleibt.",
    "immer": "PBP beendet Ollama beim Beenden immer — auch wenn es schon "
             "vorher lief oder ein anderes Programm es benutzt.",
}
AUTOSTOP_VORGABE = "aus"

#: Windows: die Tray-App startet den Dienst neu, wenn nur er endet —
#: deshalb beide, die App zuerst.
_WIN_PROZESSE = ("ollama app.exe", "ollama.exe")
_WIN_OHNE_FENSTER = 0x08000000   # CREATE_NO_WINDOW

_beim_beenden_gelaufen = False


def autostop_lesen(db) -> dict:
    try:
        wert = str(db.get_profile_setting(AUTOSTOP_SCHLUESSEL,
                                          AUTOSTOP_VORGABE)).strip().lower()
    except Exception:
        wert = AUTOSTOP_VORGABE
    if wert not in AUTOSTOP_WERTE:
        wert = AUTOSTOP_VORGABE
    return {"beim_beenden": wert, "wirkung": AUTOSTOP_WERTE[wert],
            "moegliche_werte": dict(AUTOSTOP_WERTE),
            "von_pbp_gestartet": _von_pbp_gestartet is not None}


def autostop_setzen(db, wert: str, bestaetigt: bool = False) -> dict:
    """Setzt die Einstellung. 'immer' nur mit Bestaetigung — beendet
    wird dann auch ein Ollama, das jemand anderem gehoert."""
    wert = (wert or "").strip().lower()
    if wert not in AUTOSTOP_WERTE:
        return {"fehler": "Wert muss 'aus', 'gestartet' oder 'immer' sein.",
                "aktueller_stand": autostop_lesen(db)}
    if wert == "immer" and not bestaetigt:
        return {"status": "rueckfrage",
                "frage": "Wirklich IMMER beenden? Dann endet Ollama mit PBP "
                         "auch, wenn es schon vorher lief oder ein anderes "
                         "Programm es gerade benutzt. PBP kann dich beim "
                         "Beenden nicht mehr fragen.",
                "aktueller_stand": autostop_lesen(db)}
    db.set_profile_setting(AUTOSTOP_SCHLUESSEL, wert)
    return autostop_lesen(db)


def _systemdienst_aktiv() -> bool:
    if not sys.platform.startswith("linux") or not shutil.which("systemctl"):
        return False
    try:
        r = subprocess.run(["systemctl", "is-active", "ollama"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() == "active"
    except Exception:
        return False


def ollama_beenden() -> dict:
    """Beendet Ollama — oder sagt, warum nicht.

    Ausgaenge: `beendet`, `lief_nicht`, `systemdienst`, `fehler`.
    """
    global _von_pbp_gestartet
    if _systemdienst_aktiv():
        return {"status": "systemdienst",
                "hinweis": "Ollama laeuft als Systemdienst und startet nach "
                           "einem Beenden von selbst neu. Beenden mit "
                           "'sudo systemctl stop ollama', dauerhaft mit "
                           "'sudo systemctl disable ollama'."}
    beendet = []
    try:
        if sys.platform == "win32":
            for name in _WIN_PROZESSE:
                r = subprocess.run(["taskkill", "/F", "/T", "/IM", name],
                                   capture_output=True, timeout=15,
                                   creationflags=_WIN_OHNE_FENSTER)
                if r.returncode == 0:
                    beendet.append(name)
        else:
            namen = ("Ollama", "ollama") if sys.platform == "darwin" else ("ollama",)
            for name in namen:
                r = subprocess.run(["pkill", "-x", name],
                                   capture_output=True, timeout=15)
                if r.returncode == 0:
                    beendet.append(name)
    except FileNotFoundError as exc:
        return {"status": "fehler",
                "fehler": "Werkzeug zum Beenden fehlt: %s" % exc}
    except Exception as exc:
        return {"status": "fehler", "fehler": str(exc)}
    if not beendet:
        return {"status": "lief_nicht",
                "hinweis": "Ollama lief nicht — es gibt nichts zu beenden."}
    _von_pbp_gestartet = None
    return {"status": "beendet", "prozesse": beendet,
            "hinweis": "Ollama ist beendet, das Modell ist aus dem "
                       "Arbeitsspeicher. Neu starten mit dem Knopf "
                       "'Ollama starten' oder beim naechsten Start von PBP, "
                       "falls der Autostart an ist."}


def beim_beenden(db) -> dict:
    """Wird gerufen, wenn PBP endet — von BEIDEN Startwegen.

    Schnell und ohne Ausnahme nach aussen: ein Fehler hier darf das
    Beenden von PBP nicht aufhalten. Laeuft je Prozess hoechstens einmal
    (atexit und Signal koennen beide feuern).
    """
    global _beim_beenden_gelaufen
    if _beim_beenden_gelaufen:
        return {"status": "schon_gelaufen"}
    _beim_beenden_gelaufen = True
    try:
        wert = autostop_lesen(db)["beim_beenden"]
    except Exception:
        wert = AUTOSTOP_VORGABE
    if wert == "aus":
        return {"status": "abgeschaltet"}
    if wert == "gestartet" and _von_pbp_gestartet is None:
        return {"status": "nicht_von_pbp",
                "hinweis": "Ollama wurde nicht von diesem PBP gestartet "
                           "und bleibt deshalb."}
    try:
        ergebnis = ollama_beenden()
    except Exception as exc:
        logger.warning("Ollama beim Beenden nicht gestoppt: %s", exc)
        return {"status": "fehler", "fehler": str(exc)}
    logger.info("Ollama beim Beenden von PBP: %s", ergebnis.get("status"))
    return ergebnis


# -- Desktop-Verknuepfung ------------------------------------------------

#: Das Skript hinter der Verknuepfung unter Windows. Bewusst ohne
#: Klammerbloecke (#990: eine Klammer im Text beendet einen Block) und
#: ohne Umlaute (Codepage der Konsole).
WINDOWS_SKRIPT = "\r\n".join([
    "@echo off",
    "title Ollama beenden",
    "echo Ollama beenden?",
    "echo Das beendet den Dienst der lokalen KI und gibt den Arbeitsspeicher des Modells frei.",
    "echo PBP startet Ollama wieder mit dem Knopf Ollama starten oder mit dem Autostart.",
    "echo.",
    "choice /C JN /M \"Wirklich beenden\"",
    "if errorlevel 2 goto abbruch",
    "set BEENDET=0",
    "taskkill /F /T /IM \"ollama app.exe\" >nul 2>&1 && set BEENDET=1",
    "taskkill /F /T /IM \"ollama.exe\" >nul 2>&1 && set BEENDET=1",
    "if \"%BEENDET%\"==\"1\" goto beendet",
    "echo Ollama lief nicht.",
    "goto ende",
    ":beendet",
    "echo Ollama ist beendet.",
    "goto ende",
    ":abbruch",
    "echo Abgebrochen, Ollama laeuft weiter.",
    ":ende",
    "timeout /t 4 >nul",
    "",
])

UNIX_SKRIPT = "\n".join([
    "#!/bin/sh",
    "echo 'Ollama beenden?'",
    "echo 'Das beendet den Dienst der lokalen KI und gibt den Arbeitsspeicher frei.'",
    "printf 'Wirklich beenden? [j/N] '",
    "read antwort",
    "case \"$antwort\" in",
    "  j|J|y|Y)",
    "    if pkill -x Ollama 2>/dev/null || pkill -x ollama 2>/dev/null; then",
    "      echo 'Ollama ist beendet.'",
    "    else",
    "      echo 'Ollama lief nicht.'",
    "    fi ;;",
    "  *) echo 'Abgebrochen, Ollama laeuft weiter.' ;;",
    "esac",
    "sleep 3",
    "",
])

VERKNUEPFUNG_NAME = "Ollama beenden"


def _desktop_ordner():
    from pathlib import Path
    if sys.platform == "win32":
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[Environment]::GetFolderPath('Desktop')"],
                capture_output=True, text=True, timeout=20,
                creationflags=_WIN_OHNE_FENSTER)
            pfad = r.stdout.strip()
            if pfad:
                return Path(pfad)
        except Exception:
            pass
    return Path.home() / "Desktop"


def verknuepfung_anlegen(desktop=None) -> dict:
    """Legt die Verknuepfung "Ollama beenden" auf dem Desktop an.

    Unter Windows liegt das Skript im PBP-Datenordner, auf dem Desktop
    nur die Verknuepfung (mit dem Ollama-Symbol, wenn es zu finden ist).
    Unter macOS und Linux eine ausfuehrbare Datei, die ebenfalls fragt.
    """
    from pathlib import Path
    from ..database import get_data_dir

    ziel = Path(desktop) if desktop else _desktop_ordner()
    if not ziel.is_dir():
        return {"status": "fehler",
                "fehler": "Desktop-Ordner nicht gefunden: %s" % ziel}
    ordner = get_data_dir() / "werkzeuge"
    ordner.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        skript = ordner / "ollama_beenden.bat"
        skript.write_bytes(WINDOWS_SKRIPT.encode("ascii"))
        lnk = ziel / (VERKNUEPFUNG_NAME + ".lnk")
        umgebung = dict(os.environ, PBP_LNK=str(lnk), PBP_ZIEL=str(skript),
                        PBP_ICON=binary_finden() or "")
        befehl = ("$s=(New-Object -ComObject WScript.Shell)"
                  ".CreateShortcut($env:PBP_LNK);"
                  "$s.TargetPath=$env:PBP_ZIEL;"
                  "$s.Description='Ollama beenden (PBP)';"
                  "if($env:PBP_ICON){$s.IconLocation=$env:PBP_ICON};"
                  "$s.Save()")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", befehl],
                               capture_output=True, text=True, timeout=30,
                               env=umgebung, creationflags=_WIN_OHNE_FENSTER)
        except Exception as exc:
            return {"status": "fehler", "fehler": str(exc)}
        if r.returncode != 0 or not lnk.exists():
            return {"status": "fehler",
                    "fehler": (r.stderr or "Verknuepfung nicht angelegt").strip()[:300]}
        return {"status": "angelegt", "verknuepfung": str(lnk), "skript": str(skript)}

    endung = ".command" if sys.platform == "darwin" else ".sh"
    datei = ziel / (VERKNUEPFUNG_NAME + endung)
    datei.write_bytes(UNIX_SKRIPT.encode("utf-8"))
    datei.chmod(0o755)
    return {"status": "angelegt", "verknuepfung": str(datei)}
