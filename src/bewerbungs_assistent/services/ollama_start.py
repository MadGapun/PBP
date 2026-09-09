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
Andersherum verschwaende ein Modell mitten in einem Lauf.
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
