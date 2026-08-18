"""Einheitliche Antworten fuer leere Zustaende (#927, v1.7.21).

Leitlinie: **Benutzerfuehrung ist oberste Prioritaet — jeder Flow fuehrt
zum naechsten logischen Schritt.** Gemessen am 18.08.2026 endeten 18 von
53 einstiegsnahen Tools im leeren Zustand in einer Sackgasse: technisch
korrekt (`{"anzahl": 0}`), aber ohne jede Antwort auf die Frage, die der
Nutzer wirklich hat — *was kann ich hier tun?*

Die Zielgruppe sind Menschen ohne Technikwissen. Fuer sie ist ein leeres
JSON-Objekt kein Ergebnis, sondern ein Stopp.

Zwei Bausteine:

* `kein_profil()` — statt 17 unterschiedlich formulierter Fehlermeldungen
  ueberall dieselbe, die den Weg zur gefuehrten Ersterfassung nennt.
* `leer(...)` — haengt an eine leere Liste einen Satz, der weiterfuehrt.

Bewusst KEIN Roman: ein Satz, der zum naechsten Schritt fuehrt. Wer
schon weiss, was er tut, wird von zwei Zeilen nicht aufgehalten.
"""
from __future__ import annotations

from typing import Any

# Der Einstieg. Wird an genau einer Stelle formuliert, damit die
# Anleitung nicht in 17 Varianten auseinanderlaeuft.
ERSTERFASSUNG_HINWEIS = (
    "Es ist noch kein Profil angelegt — PBP weiss also noch nichts ueber "
    "dich. Am einfachsten geht das gefuehrt: sag Claude einfach "
    "\"Starte die Ersterfassung\". Dann werden Lebenslauf, Kenntnisse und "
    "Suchwuensche Schritt fuer Schritt aufgenommen. Wer lieber selbst "
    "anfaengt: profil_erstellen(name, email) legt ein leeres Profil an."
)


def kein_profil(aktion: str = "") -> dict:
    """Einheitliche Antwort, wenn noch kein Profil existiert (#927).

    Args:
        aktion: Optional, was der Nutzer gerade versucht hat — wird in
            die Erklaerung eingewoben ("... um <aktion> zu koennen").
    """
    grund = "Dafuer braucht PBP zuerst ein Profil."
    if aktion:
        grund = f"Um {aktion} zu koennen, braucht PBP zuerst ein Profil."
    return {
        "status": "kein_profil",
        "fehler": "Kein aktives Profil vorhanden.",
        "erklaerung": grund,
        "naechster_schritt": ERSTERFASSUNG_HINWEIS,
    }


def leer(daten: dict, hinweis: str, naechster_schritt: str = "") -> dict:
    """Ergaenzt eine leere Antwort um einen Wegweiser (#927).

    Args:
        daten: das bisherige Antwort-Dict (bleibt unveraendert erhalten).
        hinweis: ein Satz, der den leeren Zustand einordnet.
        naechster_schritt: optional der konkrete Tool-Aufruf.
    """
    out = dict(daten)
    text = hinweis
    if naechster_schritt:
        text = f"{hinweis} {naechster_schritt}"
    out["hinweis"] = text
    return out


def ist_leer(wert: Any) -> bool:
    """True fuer die ueblichen 'nichts da'-Formen."""
    if wert is None:
        return True
    if isinstance(wert, (list, tuple, dict, str)):
        return len(wert) == 0
    if isinstance(wert, (int, float)):
        return wert == 0
    return False
