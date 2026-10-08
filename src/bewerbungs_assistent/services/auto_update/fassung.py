"""Versionsnummern: was ist eine gueltige Fassung, welche ist neuer, welche ist stabil (#1093).

Streng mit Absicht. Eine Fassungsnummer wird zum Ordnernamen UND zum Teil einer
Download-Adresse; eine zu grosszuegige Pruefung (`\\d` laesst arabische Ziffern
zu, `$` ein Zeilenende am Schluss, ein Punkt-Punkt wird zum Pfad) macht aus einer
Zahl einen Angriffsweg. Deshalb nur ASCII-Ziffern und `fullmatch`.

Das gleiche Muster steht im Startbaustein (`bewerbungs_assistent_boot`), der sich nie
aendert. `tests/test_v18_auto_update_boot.py` haelt beide gegeneinander.

Und `packaging` ist hier bewusst NICHT im Spiel: in der Laufzeit des Installers fehlt
es unter Umstaenden, und die Pruefung "ist das eine Vorabversion?" darf nicht
still auf "nein" fallen, weil ein Import scheitert (so war es in
`update_quelle._ist_vorabversion`).
"""
from __future__ import annotations

import re

_FASSUNG = re.compile(r"([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,4})(?:-(alpha|beta|rc)\.([0-9]{1,3}))?", re.ASCII)
_RANG = {None: 9, "rc": 3, "beta": 2, "alpha": 1}


def schluessel(fassung):
    """Vergleichswert; None, wenn es keine gueltige Fassung ist."""
    m = _FASSUNG.fullmatch(fassung) if isinstance(fassung, str) else None
    if not m:
        return None
    major, minor, patch, art, nr = m.groups()
    return (int(major), int(minor), int(patch), _RANG[art], int(nr or 0))


def gueltig(fassung) -> bool:
    return schluessel(fassung) is not None


def ist_stabil(fassung) -> bool:
    """Eine fertige Fassung (X.Y.Z). Vorabversionen (Alpha, Beta, RC) sind es nie."""
    m = _FASSUNG.fullmatch(fassung) if isinstance(fassung, str) else None
    return bool(m) and m.group(4) is None


def linie(fassung):
    """'1.8.3' -> '1.8'; None bei ungueltiger Fassung."""
    m = _FASSUNG.fullmatch(fassung) if isinstance(fassung, str) else None
    return f"{int(m.group(1))}.{int(m.group(2))}" if m else None


def ist_neuer(kandidat, aktuell) -> bool:
    """Ist `kandidat` echt neuer als `aktuell`? Bei einer ungueltigen Seite: False."""
    k, a = schluessel(kandidat), schluessel(aktuell)
    return k is not None and a is not None and k > a


def aus_tag(tag):
    """'v1.8.1' -> '1.8.1'. Nur mit fuehrendem 'v' und gueltiger Fassung, sonst None."""
    if not isinstance(tag, str) or not tag.startswith("v"):
        return None
    rest = tag[1:]
    return rest if gueltig(rest) else None


def tag_aus(fassung: str) -> str:
    if not gueltig(fassung):
        raise ValueError(f"Keine gültige Fassung: {fassung!r}")
    return "v" + fassung
