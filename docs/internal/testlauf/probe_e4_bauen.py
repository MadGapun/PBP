# -*- coding: utf-8 -*-
"""Baut zwei praeparierte Probe-Veroeffentlichungen, die PBP ABLEHNEN muss (Testlauf, Block E4).

Aufruf:
    python docs/internal/testlauf/probe_e4_bauen.py <gutes-archiv.zip> <Fassung-falsche-Summe> <Fassung-fremde-Signatur> <Ausgabeordner>

Beispiel (dritter Lauf):
    python docs/internal/testlauf/probe_e4_bauen.py C:/Temp/probe_dist/pbp-update-1.8.3.zip 1.8.4 1.8.5 C:/Temp/probe_e4

a) <Fassung-falsche-Summe>: gueltig signierte Summenliste, aber die Pruefsumme passt nicht zum Archiv.
b) <Fassung-fremde-Signatur>: richtige Pruefsumme, aber mit einem frisch erzeugten, fremden Schluessel signiert.

Der echte Schluessel verlaesst den Rechner nie; hochgeladen werden nur Archiv, Summenliste und Signatur. Am Ende werden beide Pakete mit den
Pruefungen des Programms gegengelesen: sie muessen abgelehnt werden.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import shutil
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WURZEL / "src"))
sys.path.insert(0, str(WURZEL / "scripts"))

from bewerbungs_assistent.services.auto_update import ed25519, pruefung  # noqa: E402
import update_schluessel as us  # noqa: E402


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    gut, v_summe, v_fremd, aus = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
    if not gut.is_file():
        print("FEHLER: Archiv fehlt:", gut)
        return 2
    haupt = us.stand()["hauptschluessel"]
    if not haupt:
        print("FEHLER: kein Hauptschluessel am festen Ort (siehe scripts/update_schluessel.py stand)")
        return 2
    echt = bytes.fromhex(Path(haupt).read_text(encoding="ascii").strip())
    fremd = secrets.token_bytes(32)
    shutil.rmtree(aus, ignore_errors=True)

    def paket(ordner: Path, fassung: str, summe_falsch: bool, geheim: bytes) -> None:
        ordner.mkdir(parents=True)
        name = f"pbp-update-{fassung}.zip"
        ziel = ordner / name
        shutil.copy2(gut, ziel)
        echte = hashlib.sha256(ziel.read_bytes()).hexdigest()
        summe = ("0" * 63 + "1") if summe_falsch else echte
        summen = f"{summe}  {name}\n".encode("ascii")
        (ordner / "SHA256SUMS").write_bytes(summen)
        sig = ed25519.signieren(geheim, summen)
        (ordner / "SHA256SUMS.sig").write_text(base64.b64encode(sig).decode("ascii") + "\n", encoding="ascii")
        print(fassung, "| Summe in der Liste:", summe[:16], "| echte Summe:", echte[:16], "|",
              "FALSCHE SUMME" if summe_falsch else "richtige Summe", "| signiert mit:", "ECHTEM Schluessel" if geheim == echt else "FREMDEM Schluessel")

    paket(aus / "a_falsche_summe", v_summe, True, echt)
    paket(aus / "b_fremde_signatur", v_fremd, False, fremd)

    fehler = 0
    for ordner, fassung in ((aus / "a_falsche_summe", v_summe), (aus / "b_fremde_signatur", v_fremd)):
        summen = (ordner / "SHA256SUMS").read_bytes()
        sig = (ordner / "SHA256SUMS.sig").read_text()
        try:
            von = pruefung.signatur_pruefen(summen, sig)
            try:
                pruefung.archiv_pruefen(ordner / f"pbp-update-{fassung}.zip", f"pbp-update-{fassung}.zip", summen, signiert_von=von)
                print(fassung, "-> ANGENOMMEN (Fehler!)")
                fehler += 1
            except Exception as exc:  # noqa: BLE001
                print(fassung, "-> Signatur ok, Archiv abgelehnt:", type(exc).__name__, str(exc)[:80])
        except Exception as exc:  # noqa: BLE001
            print(fassung, "-> Signatur abgelehnt:", type(exc).__name__, str(exc)[:80])
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
