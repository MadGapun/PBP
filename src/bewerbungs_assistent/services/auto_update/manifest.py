"""Die Beschreibung im Update-Archiv (`manifest.json`) und ob sie zu DIESEM Rechner passt (#1093).

Das Manifest steht IM Archiv und ist damit durch Pruefsumme und Signatur des Archivs
abgesichert; es wird nach dem Entpacken gelesen. Es beantwortet vier Fragen:

* Welche Fassung ist das, und gehoert sie zu meiner Linie? (nie ein Linienwechsel)
* Laeuft sie auf meiner Python-Laufzeit, mit meinem Startbaustein?
* Welche Pakete braucht sie, und sind sie da?
* Darf sie ueberhaupt automatisch installiert werden (`auto_update_moeglich`)?

Antwort "nein" auf eine dieser Fragen ist kein Fehler im Sinn eines Defekts, sondern ein
ehrlicher Hinweis: "Dieses Update braucht den Installer". Es wird nichts installiert, und
die Oberflaeche sagt, was zu tun ist.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from bewerbungs_assistent_boot import FORMAT as BOOT_FORMAT

from . import fassung as _fassung
from .fehler import UpdateFehler

MANIFEST_FORMAT = 1


@dataclass(frozen=True)
class Manifest:
    version: str
    linie: str
    boot_format: int
    python_min: tuple
    python_unter: tuple
    schema: object  # int oder None
    requirements: tuple
    requirements_optional: tuple
    auto_update_moeglich: bool
    braucht_installer: str
    changelog: tuple
    erstellt: str
    rohdaten: dict = field(default_factory=dict, compare=False, repr=False)


def _ganzzahl_tupel(wert, name: str) -> tuple:
    if not isinstance(wert, str):
        raise UpdateFehler("manifest", detail=f"{name}: Text erwartet")
    teile = wert.split(".")
    if not 1 <= len(teile) <= 3 or not all(t.isascii() and t.isdigit() for t in teile):
        raise UpdateFehler("manifest", detail=f"{name}: '{wert}' ist keine Versionsangabe")
    return tuple(int(t) for t in teile)


def _textliste(wert, name: str) -> tuple:
    if wert is None:
        return ()
    if not isinstance(wert, list) or not all(isinstance(x, str) for x in wert):
        raise UpdateFehler("manifest", detail=f"{name}: Liste aus Text erwartet")
    return tuple(wert)


def lesen(daten, *, erwartete_version: str) -> Manifest:
    """Aus Bytes, Text oder einem Pfad ein geprueftes Manifest machen."""
    try:
        if isinstance(daten, (str, Path)) and not (isinstance(daten, str) and daten.lstrip().startswith("{")):
            daten = Path(daten).read_bytes()
        if isinstance(daten, (bytes, bytearray)):
            daten = bytes(daten).decode("utf-8-sig")
        roh = json.loads(daten)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise UpdateFehler("manifest", detail=f"nicht lesbar: {exc}") from exc
    if not isinstance(roh, dict):
        raise UpdateFehler("manifest", detail="Objekt erwartet")
    if roh.get("format") != MANIFEST_FORMAT:
        raise UpdateFehler("braucht_installer", "Dieses Update hat ein neueres Format als diese Installation versteht. "
                           "Es braucht den Installer.", detail=f"format {roh.get('format')!r}")
    version = roh.get("version")
    if not _fassung.ist_stabil(version):
        raise UpdateFehler("manifest", detail=f"version {version!r} ist keine stabile Fassung")
    if version != erwartete_version:
        raise UpdateFehler("manifest", detail=f"enthaelt {version}, erwartet {erwartete_version}")
    linie = roh.get("linie")
    if linie != _fassung.linie(version):
        raise UpdateFehler("manifest", detail=f"linie {linie!r} passt nicht zu {version}")
    boot_format = roh.get("boot_format", 1)
    if not isinstance(boot_format, int) or isinstance(boot_format, bool) or boot_format < 1:
        raise UpdateFehler("manifest", detail="boot_format: Ganzzahl ab 1 erwartet")
    python = roh.get("python")
    if python is None:
        python = {}
    if not isinstance(python, dict):
        raise UpdateFehler("manifest", detail="python: Objekt erwartet")
    schema = roh.get("schema")
    if schema is not None and (not isinstance(schema, int) or isinstance(schema, bool) or schema < 1):
        raise UpdateFehler("manifest", detail="schema: Ganzzahl erwartet")
    moeglich = roh.get("auto_update_moeglich", True)
    if not isinstance(moeglich, bool):
        raise UpdateFehler("manifest", detail="auto_update_moeglich: ja/nein erwartet")
    return Manifest(
        version=version,
        linie=linie,
        boot_format=boot_format,
        python_min=_ganzzahl_tupel(python.get("min", "3.11"), "python.min"),
        python_unter=_ganzzahl_tupel(python.get("unter", "4"), "python.unter"),
        schema=schema,
        requirements=_textliste(roh.get("requirements"), "requirements"),
        requirements_optional=_textliste(roh.get("requirements_optional"), "requirements_optional"),
        auto_update_moeglich=moeglich,
        braucht_installer=str(roh.get("braucht_installer") or "")[:300],
        changelog=_textliste(roh.get("changelog"), "changelog")[:8],
        erstellt=str(roh.get("erstellt") or "")[:40],
        rohdaten=roh,
    )


def fuer_diesen_rechner_pruefen(m: Manifest, *, laufende_fassung: str, python=None, boot_format=None) -> None:
    """Wirft `UpdateFehler`, wenn dieses Update hier nicht automatisch installiert werden darf."""
    python = tuple(python if python is not None else sys.version_info[:3])
    boot_format = BOOT_FORMAT if boot_format is None else boot_format
    if _fassung.linie(laufende_fassung) != m.linie:
        raise UpdateFehler("braucht_installer", "Das ist eine andere Version-Linie. Ein Wechsel der Linie "
                           "geschieht nie automatisch.", detail=f"{laufende_fassung} -> {m.version}")
    if not _fassung.ist_neuer(m.version, laufende_fassung):
        raise UpdateFehler("schon_aktuell", detail=f"{m.version} ist nicht neuer als {laufende_fassung}")
    if not m.auto_update_moeglich:
        raise UpdateFehler("braucht_installer", m.braucht_installer or None, detail="auto_update_moeglich=false")
    if m.boot_format > boot_format:
        raise UpdateFehler("braucht_installer", "Dieses Update braucht einen neueren Startbaustein. "
                           "Es braucht den Installer.", detail=f"boot_format {m.boot_format} > {boot_format}")
    if not (m.python_min <= python[:len(m.python_min)] and python[:len(m.python_unter)] < m.python_unter):
        raise UpdateFehler("braucht_installer", "Dieses Update braucht eine andere Python-Laufzeit. "
                           "Es braucht den Installer.", detail=f"Python {python} ausserhalb {m.python_min}..{m.python_unter}")
