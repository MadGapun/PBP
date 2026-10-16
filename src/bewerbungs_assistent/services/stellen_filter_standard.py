"""Die ausdrücklich gesetzte Voreinstellung der Filter in der Stellenliste (#1158 Punkt 5).

Bis v1.7.150 gab es zwei Zustände: „keine Einschränkung“ (Start und „Filter zurücksetzen“) und den gemerkten Zustand des
Browsers. Wer immer mit denselben Filtern öffnen will (zum Beispiel „Beworbene ausblenden“ an, alles andere aus), musste sie
nach jedem Verlassen der Liste neu einstellen. Jetzt kann der Mensch seinen Zustand als Voreinstellung festhalten:

* Sie gilt bei jedem **Öffnen von PBP** (Neuladen, Neustart), nicht beim Wechsel zwischen den Seiten.
* Ohne Voreinstellung bleibt alles, wie es war: der gemerkte Zustand des Browsers.
* „Filter zurücksetzen“ zeigt weiter ALLE offenen Stellen (die verbindliche Anforderung aus dem Issue); es ist keine
  Voreinstellung und wird nie von ihr verändert.

Gespeichert wird je Profil auf dem Server (nicht im Browser): sie überlebt gesperrten Browserspeicher und gilt in jedem
Browser. Der Server prüft Schlüssel und Typen streng; die Oberfläche liest nur, was sie kennt (`filterAusSpeicher`).
"""
from __future__ import annotations

import re

#: Welche Filter der Seite eine Voreinstellung tragen darf, und von welchem Typ. Nicht dabei: der Suchtext (ein vergessener
#: Suchtext würde die Liste beim Öffnen unbemerkt verkürzen) und die Ansicht (aktiv/aussortiert ist Navigation).
SCHLUESSEL: dict = {
    "source": str,
    "minScore": str,
    "remote": str,
    "salaryOnly": bool,
    "sort": str,
    "employmentType": str,
    "arbeitsumfang": str,
    "hideApplied": bool,
    "missingDescriptionOnly": bool,
    "pruefstand": str,
    "rahmenAusblenden": bool,
    "schwelleAusblenden": bool,
}

EINSTELLUNG = "stellen_filter_standard"
MAX_TEXT = 100
_ZAHL = re.compile(r"-?\d+(?:[.,]\d+)?")


def pruefen(daten) -> dict:
    """Prüft eine Voreinstellung streng und gibt die bereinigte Fassung zurück; wirft `ValueError` mit dem Grund."""
    if not isinstance(daten, dict) or not daten:
        raise ValueError("Die Voreinstellung muss die Filter als Objekt nennen.")
    ergebnis: dict = {}
    for schluessel, wert in daten.items():
        if schluessel not in SCHLUESSEL:
            raise ValueError(f"Unbekannter Filter: {schluessel!r}.")
        erwartet = SCHLUESSEL[schluessel]
        if not isinstance(wert, erwartet) or (erwartet is str and isinstance(wert, bool)):
            raise ValueError(f"Der Filter {schluessel!r} hat den falschen Typ.")
        if erwartet is str:
            if len(wert) > MAX_TEXT or any(ord(c) < 32 for c in wert):
                raise ValueError(f"Der Filter {schluessel!r} hat einen ungültigen Text.")
            if schluessel == "minScore" and wert.strip() and not _ZAHL.fullmatch(wert.strip()):
                raise ValueError("Mindestpunkte müssen eine Zahl sein (auch 0 und negative Werte) oder leer.")
        ergebnis[schluessel] = wert
    return ergebnis


def lesen(db):
    """Die gespeicherte Voreinstellung oder `None`. Ein kaputter Eintrag gilt als „keine“, nie als Fehler."""
    try:
        wert = db.get_profile_setting(EINSTELLUNG, None)
    except Exception:  # noqa: BLE001 -- die Liste darf daran nie scheitern
        return None
    if not isinstance(wert, dict):
        return None
    try:
        return pruefen(wert)
    except ValueError:
        return None


def setzen(db, daten) -> dict:
    gepruefte = pruefen(daten)
    db.set_profile_setting(EINSTELLUNG, gepruefte)
    return gepruefte


def loeschen(db) -> None:
    db.set_profile_setting(EINSTELLUNG, None)
