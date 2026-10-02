"""Welchen oeffentlichen Schluesseln vertraut das Auto-Update (#1093)?

Ein Update-Archiv wird mit einem GEHEIMEN Schluessel signiert, der nie bei GitHub
liegt (siehe `scripts/update_schluessel.py`). Hier stehen nur die OEFFENTLICHEN
Schluessel — Name und Wert in Hex (32 Byte). Eine Signatur ist gueltig, wenn sie zu
EINEM davon passt.

Mehrere Schluessel sind Absicht: ein zweiter, der nur als Notfall-Schluessel
aufbewahrt wird, erlaubt es, einen verlorenen oder gestohlenen Hauptschluessel zu
ersetzen, ohne dass alle Installationen von Hand neu installiert werden muessen
(ein Update, das mit dem Notfall-Schluessel signiert ist und einen neuen Hauptschluessel
mitbringt).

Solange hier KEIN Schluessel steht, prueft das Auto-Update nur die Pruefsumme
(`SIGNATUR_ERFORDERLICH` ist dann False) — und die Oberflaeche sagt es ehrlich. Sobald
einer eingetragen ist, wird NICHTS ohne gueltige Signatur installiert.
"""
from __future__ import annotations

#: Name -> oeffentlicher Schluessel (64 Hex-Zeichen). Wird beim ersten signierten Release gefuellt.
VERTRAUTE_SCHLUESSEL: dict = {}


def signatur_erforderlich(schluessel=None) -> bool:
    return bool(VERTRAUTE_SCHLUESSEL if schluessel is None else schluessel)


def schluessel_bytes(schluessel=None) -> dict:
    """Name -> 32 Byte. Eintraege, die kein gueltiges Hex mit 32 Byte sind, fallen heraus (sicherer Zustand)."""
    quelle = VERTRAUTE_SCHLUESSEL if schluessel is None else schluessel
    ergebnis = {}
    for name, hexwert in quelle.items():
        try:
            roh = bytes.fromhex(hexwert)
        except (ValueError, TypeError):
            continue
        if len(roh) == 32:
            ergebnis[str(name)] = roh
    return ergebnis
