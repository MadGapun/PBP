"""Ausgaben von Konsolenprogrammen richtig lesen (#1182).

Windows-Programme wie `tasklist`, `taskkill` oder `powershell` schreiben in der Kodierung der KONSOLE (OEM; auf einem deutschen
Windows cp850, dort ist das „ü“ das Byte 0x81). Pythons Textmodus (`text=True`) liest mit der des SYSTEMS (ANSI, cp1252), in der
0x81 nicht definiert ist. Für ASCII stimmt beides, darum fällt es nie auf — bis ein Satz ein „ü“ trägt. Dann bricht der Lese-Thread
von `subprocess` ab, druckt einen Traceback ins Fenster, und `stdout` ist `None`.

Der Fund (08.10.2026): `tasklist` meldet „… Kriterien ausgeführt.“, wenn Claude Desktop nicht läuft; PBP fragt das beim Start, und im
Dashboard-Fenster stand ein `UnicodeDecodeError`. Das Ergebnis der Prüfung stimmte nur zufällig („läuft nicht“).

Regel für jeden Aufruf, der die Ausgabe eines Konsolenprogramms LIEST:

* Reicht es, nach ASCII-Text zu suchen (`claude.exe`, `ok`), dann Bytes lesen (kein `text=True`) und mit `text_lesen` verwandeln.
* Sonst `encoding=konsole_kodierung(), errors="replace"` angeben.

Ein Wächter-Test (`tests/test_v18_konsole_ausgabe_1182.py`) verlangt bei jedem `text=True` im Quelltext ein `encoding=` oder
`errors=`. Verwandt: #1163 (Zeichen außerhalb der Zeichentabelle im Benutzernamen), L44.
"""
from __future__ import annotations

import sys


def konsole_kodierung() -> str:
    """Die Kodierung, in der Konsolenprogramme auf diesem System schreiben: `oem` unter Windows, sonst UTF-8."""
    return "oem" if sys.platform == "win32" else "utf-8"


def text_lesen(roh, kodierung: str | None = None) -> str:
    """Bytes (oder schon Text, oder nichts) in Text verwandeln — mit der Kodierung der Konsole, nie mit einem Abbruch.

    Unlesbare Zeichen werden zu Ersatzzeichen; wer nach ASCII-Text sucht, merkt davon nichts. `kodierung` ueberschreibt die der Konsole
    (der Test waehlt so UTF-8, damit er auf jedem Betriebssystem etwas sieht).
    """
    if roh is None:
        return ""
    if isinstance(roh, str):
        return roh
    try:
        return bytes(roh).decode(kodierung or konsole_kodierung(), errors="replace")
    except LookupError:       # eine Kodierung „oem“ gibt es nur unter Windows
        return bytes(roh).decode("utf-8", errors="replace")
