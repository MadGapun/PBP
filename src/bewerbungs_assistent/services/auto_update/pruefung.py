"""Pruefsumme und Signatur eines Update-Archivs (#1093 Akzeptanzkriterium 7).

Zwei getrennte Fragen:

* **Signatur** (`signatur_pruefen`): stammt die Datei `SHA256SUMS` von jemandem, dessen
  Schluessel in `schluessel.py` steht? Ohne Schluessel im Code entfaellt diese
  Pruefung (und die Oberflaeche sagt es); mit Schluessel wird NICHTS ohne gueltige
  Signatur installiert.
* **Pruefsumme** (`archiv_pruefen`): ist das geladene Archiv genau das, was in der
  signierten Liste steht?

Erst beides zusammen schliesst ein ausgetauschtes Release aus: die Signatur verhindert,
dass der Angreifer die Liste mit austauscht; die Pruefsumme, dass er das Archiv tauscht,
ohne die Liste anzufassen.

Die Signatur steht in `SHA256SUMS.sig` als Base64 von 64 Byte und gilt fuer die
Bytes von `SHA256SUMS` — genau diese, ohne jede Umformung.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from . import ed25519, schluessel as _schl
from .fehler import UpdateFehler

_ZEILE = re.compile(r"([0-9a-fA-F]{64})[ \t]+\*?([^\r\n]+?)[ \t]*", re.ASCII)


@dataclass(frozen=True)
class Pruefergebnis:
    sha256: str
    signiert: bool
    schluessel: str  # Name des Schluessels, der die Liste signiert hat ("" ohne Signatur)


def sha256_datei(pfad, *, block: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        while True:
            stueck = f.read(block)
            if not stueck:
                break
            h.update(stueck)
    return h.hexdigest()


def summen_lesen(text: str) -> dict:
    """`SHA256SUMS` im Format von `sha256sum`: '<64 Hex>  <Name>' je Zeile -> {Name: Hex (klein)}.

    Ein Name, der zweimal mit verschiedenen Summen auftaucht, ist ein Fehler (keine Wahl treffen).
    Namen mit Pfadanteil sind ein Fehler: die Liste nennt Dateien, keine Orte.
    """
    ergebnis = {}
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        m = _ZEILE.fullmatch(zeile)
        if not m:
            raise UpdateFehler("pruefsumme", "Die Prüfsummenliste ist nicht lesbar.", detail=zeile[:80])
        summe, name = m.group(1).lower(), m.group(2)
        if "/" in name or "\\" in name or name in (".", ".."):
            raise UpdateFehler("pruefsumme", "Die Prüfsummenliste nennt einen ungültigen Dateinamen.", detail=name[:80])
        if name in ergebnis and ergebnis[name] != summe:
            raise UpdateFehler("pruefsumme", "Die Prüfsummenliste widerspricht sich.", detail=name[:80])
        ergebnis[name] = summe
    return ergebnis


def signatur_lesen(text) -> bytes:
    """Die 64 Byte aus der Base64-Datei; alles andere ist 'keine gueltige Signatur'."""
    try:
        roh = text if isinstance(text, (bytes, bytearray)) else str(text).encode("ascii")
        daten = base64.b64decode(b"".join(roh.split()), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError, TypeError) as exc:
        raise UpdateFehler("signatur", detail="Base64 nicht lesbar") from exc
    if len(daten) != 64:
        raise UpdateFehler("signatur", detail=f"{len(daten)} statt 64 Byte")
    return daten


def signatur_pruefen(summen_bytes: bytes, signatur_text, *, schluessel=None) -> str:
    """Prueft die Signatur ueber `SHA256SUMS`. Gibt den Namen des passenden Schluessels zurueck.

    Ist KEIN Schluessel konfiguriert, ist keine Signatur verlangt und es wird "" zurueckgegeben.
    Ist einer konfiguriert, gilt: keine Signatur, kaputte Signatur oder fremde Signatur -> Fehler.
    """
    if not _schl.signatur_erforderlich(schluessel):
        return ""
    if signatur_text is None or (isinstance(signatur_text, (str, bytes)) and not signatur_text.strip()):
        raise UpdateFehler("signatur", detail="keine Signaturdatei")
    daten = signatur_lesen(signatur_text)
    for name, oeffentlich in _schl.schluessel_bytes(schluessel).items():
        if ed25519.pruefen(oeffentlich, bytes(summen_bytes), daten):
            return name
    raise UpdateFehler("signatur", detail="kein vertrauter Schluessel passt")


def archiv_pruefen(archiv, archiv_name: str, summen_bytes: bytes, *, signiert_von: str = "") -> Pruefergebnis:
    """Stimmt die Summe des geladenen Archivs mit der Liste ueberein?"""
    try:
        summen = summen_lesen(bytes(summen_bytes).decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise UpdateFehler("pruefsumme", "Die Prüfsummenliste ist nicht lesbar.", detail="kein UTF-8") from exc
    erwartet = summen.get(archiv_name)
    if not erwartet:
        raise UpdateFehler("pruefsumme", "Das Archiv steht nicht in der Prüfsummenliste.", detail=archiv_name)
    tatsaechlich = sha256_datei(Path(archiv))
    if tatsaechlich != erwartet:
        raise UpdateFehler("pruefsumme", detail=f"erwartet {erwartet[:12]}…, geladen {tatsaechlich[:12]}…")
    return Pruefergebnis(sha256=tatsaechlich, signiert=bool(signiert_von), schluessel=signiert_von)
