"""Woher PBP erfaehrt, dass es eine neue Version gibt (#1069).

Bis v1.7.121 fragte die Pruefung ausschliesslich
`api.github.com/repos/MadGapun/PBP/releases/latest`. Das ist der einzige
Weg, auf dem eine installierte Kopie von einer neuen Version erfaehrt —
und er steht auf einem Bein. Faellt GitHub als Quelle weg (Repo privat,
Umzug der Entwicklung, geaenderter Pfad), bleibt die Anzeige stumm:
`update_available` ist dann dauerhaft False, **ohne Fehlermeldung**. Der
Mensch merkt nicht, dass er nichts mehr erfaehrt.

Das ist #989 an der Update-Pruefung: "konnte nicht nachsehen" sah aus
wie "alles aktuell".

Drei Aenderungen:

* **Mehrere Quellen, der Reihe nach.** Welche, steht in der
  Konfiguration (`update_quellen`), nicht im Code.
* **Die Linie zaehlt.** Wer auf 1.7 stable sitzt, soll keine 1.8-Beta
  als Update angeboten bekommen.
* **Antwortet keine Quelle, sagt PBP das.** `stand: unbekannt` statt
  eines stillen "aktuell".

**Gemessen am 21.09.2026:** der ELWOSA-Endpunkt antwortet mit HTTP 404 —
die Domain gibt es, die Route noch nicht. Er steht trotzdem an erster
Stelle, weil er fuer den Umzug gedacht ist; bis dahin ist der Rueckfall
auf GitHub der reale Pfad und wird damit von Anfang an benutzt statt
nur behauptet.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Die Vorgabe. Ueberschreibbar ueber die Einstellung `update_quellen`,
#: damit eine Installation umziehen kann, ohne auf ein Update zu warten
#: — was bei einer kaputten Update-Pruefung ein Widerspruch waere.
STANDARD_QUELLEN = [
    {
        "name": "elwosa",
        "url": "https://elwosa.de/api/projects/pbp/releases/latest",
        "art": "elwosa",
    },
    {
        "name": "github",
        "url": "https://api.github.com/repos/MadGapun/PBP/releases/latest",
        "art": "github",
    },
]

#: Wie lange eine Antwort gilt, wenn die Quelle nichts anderes sagt.
STANDARD_PAUSE_S = 3600


def linie_von(version: str) -> str:
    """'1.7.122' -> '1.7'. Die Linie, auf der eine Installation sitzt."""
    teile = (version or "").split(".")
    return ".".join(teile[:2]) if len(teile) >= 2 else (version or "")


def quellen(db=None) -> list[dict]:
    """Die konfigurierte Quellenliste, sonst die Vorgabe."""
    if db is None:
        return list(STANDARD_QUELLEN)
    try:
        eigene = db.get_setting("update_quellen", None)
    except Exception:  # pragma: no cover — nie die Pruefung kippen
        eigene = None
    if not eigene:
        return list(STANDARD_QUELLEN)
    gueltig = [q for q in eigene
               if isinstance(q, dict) and q.get("url") and q.get("art")]
    return gueltig or list(STANDARD_QUELLEN)


def _passt_zur_linie(version: str, linie: str) -> bool:
    """Gehoert diese Version zur Linie der Installation?

    Ohne Linie kein Filter. Eine 1.8-Beta ist fuer eine 1.7-Installation
    kein Update, auch wenn die Zahl groesser ist.
    """
    return not linie or linie_von(version) == linie


def auswerten(art: str, daten: dict, aktuell: str, linie: str) -> dict | None:
    """Die Antwort EINER Quelle deuten — ohne Netz, damit testbar.

    Rueckgabe: {"version", "url", "name", "pause_s"} oder None, wenn die
    Antwort nichts Brauchbares enthaelt.
    """
    if not isinstance(daten, dict):
        return None
    if art == "github":
        version = (daten.get("tag_name") or "").lstrip("v")
        url = daten.get("html_url") or ""
        name = daten.get("name") or ""
        pause = STANDARD_PAUSE_S
    else:
        version = str(daten.get("version") or "").lstrip("v")
        url = daten.get("download_url") or daten.get("url") or ""
        name = daten.get("notiz") or daten.get("name") or ""
        try:
            pause = int(daten.get("poll_after_seconds") or STANDARD_PAUSE_S)
        except (TypeError, ValueError):
            pause = STANDARD_PAUSE_S
    if not version:
        return None
    if not _passt_zur_linie(version, linie):
        return None
    return {"version": version, "url": url, "name": name,
            "pause_s": max(60, pause)}


def ist_neuer(kandidat: str, aktuell: str) -> bool:
    try:
        from packaging.version import Version
        return Version(kandidat) > Version(aktuell)
    except Exception:
        return bool(kandidat) and kandidat != aktuell
