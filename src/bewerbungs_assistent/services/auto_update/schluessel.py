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

Stuende hier KEIN Schluessel, pruefte das Auto-Update nur die Pruefsumme
(`SIGNATUR_ERFORDERLICH` waere dann False) — und die Oberflaeche sagte es ehrlich. Seit der Eintragung
wird NICHTS ohne gueltige Signatur installiert: jedes Update-Archiv braucht `SHA256SUMS.sig`
(`scripts/build_update_archive.py --schluessel-datei <geheimer Schluessel>`).
"""
from __future__ import annotations

#: Name -> oeffentlicher Schluessel (64 Hex-Zeichen). Eingetragen am 03.10.2026 (Hauptschluessel auf dem Rechner, auf dem
#: Releases gebaut werden; Notfallschluessel offline). Der GEHEIME Teil steht nie in diesem Repository.
VERTRAUTE_SCHLUESSEL: dict = {
    "haupt": "26b556a97515c05f25357138b922fe23b1823279cf98c98faf6f772616fa7013",
    "notfall": "4c188976d33fcb0538675aa0a66e34686f746763c03c943c4042d57efbdb36cf",
}


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
