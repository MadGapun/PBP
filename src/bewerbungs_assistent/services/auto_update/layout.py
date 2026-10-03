"""Wo liegt was im Programmordner (#1093).

Der Programmordner ist nicht der Datenordner: hier liegt nur Code (Laufzeit, Startbaustein,
Fassungen), dort liegen Datenbank, Dokumente und Sicherungen. Die Auto-Update-Funktion
fasst den Datenordner nie an, und die Loesch-Funktion der Datenschutzauskunft nie
den Programmordner (`versions`).

Den Programmordner kennt PBP nur aus der Umgebung: der Startbaustein setzt `PBP_APP_DIR`
und `PBP_FASSUNG`, bevor die Fassung startet. Es gibt BEWUSST keinen Rueckfall auf
`%LOCALAPPDATA%` — ein Test (oder ein Entwicklerstart aus dem Quellbaum) kann so nie
den echten Programmordner treffen: ohne Umgebungsvariable gibt es hier nichts zu tun
und die Oberflaeche sagt das.

Die Dateinamen sind der Vertrag mit dem Startbaustein und kommen von dort.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from bewerbungs_assistent_boot import (  # noqa: F401  (Vertrag, hier wieder ausgegeben)
    AKTUELL, BELEGUNG, ENV_APP, ENV_FASSUNG, FERTIG, FORMAT, STATUS, VERSIONEN, fassung_gueltig,
    gueltige_fassungen, lese_aktuell, lese_status, schreibe_atomar, schreibe_status,
)

#: Arbeitsordner fuer Downloads und Entpacken. Wird nach jedem Lauf und bei jedem Start geleert.
ARBEIT = "update"
#: Sperrdatei: es laeuft hoechstens EIN Update (MCP-Server und Dashboard teilen den Programmordner).
SPERRE = "update.sperre"


@dataclass(frozen=True)
class Pfade:
    app: Path
    versionen: Path
    aktuell: Path
    status: Path
    arbeit: Path
    sperre: Path

    def fassung(self, version: str) -> Path:
        return self.versionen / version


def programmordner():
    """Der Programmordner aus der Umgebung, oder None (nicht ueber den Installer eingerichtet)."""
    roh = os.environ.get(ENV_APP)
    if not roh:
        return None
    p = Path(roh)
    return p if p.is_dir() else None


def laufende_fassung():
    """Die Fassung, in der dieser Prozess laeuft (vom Startbaustein gesetzt), oder None."""
    wert = os.environ.get(ENV_FASSUNG)
    return wert or None


def pfade(app) -> Pfade:
    app = Path(app)
    return Pfade(app=app, versionen=app / VERSIONEN, aktuell=app / AKTUELL, status=app / STATUS,
                 arbeit=app / ARBEIT, sperre=app / SPERRE)


def plattform_unterstuetzt() -> bool:
    """Zuerst nur Windows: nur dort gibt es den Installer mit Versionsordnern."""
    return sys.platform == "win32"


def verfuegbarkeit():
    """(ok, Grund). Der Grund ist ein Satz fuer den Menschen, nie ein Fachwort."""
    if not plattform_unterstuetzt():
        return False, ("Das automatische Aktualisieren gibt es zurzeit nur unter Windows. "
                       "Neue Versionen installierst du hier von Hand.")
    if programmordner() is None or laufende_fassung() is None:
        return False, ("Diese PBP-Installation wurde nicht über den Installer eingerichtet "
                       "(zum Beispiel aus dem Quellcode gestartet). Das automatische "
                       "Aktualisieren steht deshalb nicht zur Verfügung.")
    return True, ""


def installierte_fassungen(app) -> list:
    """Alle fertig installierten Fassungen, die neueste zuerst."""
    return gueltige_fassungen(app)


def aktuelle_fassung(app):
    """Die Fassung, die der naechste Start benutzt (`aktuell.txt`)."""
    return lese_aktuell(app)
