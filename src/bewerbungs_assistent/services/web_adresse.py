"""Adressen von aussen sind Text von aussen (v1.7.145).

Eine Adresse in einer Stelle, einer Bewerbung oder einem Termin stammt aus
einem Portal, einer Mail, einer Einladung oder einem Plugin. Als Link
angezeigt oder geoeffnet, fuehrt ``javascript:`` im Ursprung der Oberflaeche
Code aus (voller Zugriff auf die lokale API und damit auf Profil,
Dokumente und Bewerbungen); ``file:`` liest lokale Dateien. Erlaubt sind nur
``http`` und ``https``.

Dieselbe Regel gilt in der Oberflaeche (``frontend/src/lib/webAdresse.js``);
``tests/test_v17145_web_adresse.py`` haelt beide Fassungen gegeneinander.
"""
from __future__ import annotations

from urllib.parse import urlsplit

ERLAUBTE_SCHEMEN = frozenset({"http", "https"})


def ist_web_adresse(url) -> bool:
    """Eine absolute http(s)-Adresse mit Rechnernamen, ohne Steuerzeichen.

    Steuerzeichen (Tabulator, Zeilenumbruch) mitten im Schema ("java\tscript:")
    ueberspringen Browser beim Lesen; deshalb gilt so etwas nie als Adresse.
    """
    if not isinstance(url, str):
        return False
    s = url.strip()
    if not s or any(ord(c) < 32 or ord(c) == 127 for c in s):
        return False
    try:
        teile = urlsplit(s)
    except ValueError:
        return False
    return teile.scheme.lower() in ERLAUBTE_SCHEMEN and bool(teile.netloc)


def web_adresse_oder_leer(url) -> str:
    """Die Adresse, wenn sie http(s) ist, sonst ein leerer Text."""
    return url.strip() if ist_web_adresse(url) else ""
