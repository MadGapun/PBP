"""Signierschluessel fuer das Auto-Update (#1093) erzeugen und pruefen.

    python scripts/update_schluessel.py erzeugen --ausgabe C:/geheim/pbp-update-haupt.hex
    python scripts/update_schluessel.py oeffentlich --datei C:/geheim/pbp-update-haupt.hex
    python scripts/update_schluessel.py pruefen --datei C:/geheim/pbp-update-haupt.hex

Der GEHEIME Schluessel (32 Zufallsbytes als 64 Hex-Zeichen in einer Datei) darf nie in ein Repository,
nie in ein Issue, nie in einen Chat. Wer ihn hat, kann Updates signieren, die alle Installationen
mit eingeschaltetem Auto-Update ohne Rueckfrage ausfuehren.

Zwei Schluessel sind Absicht:

* der **Hauptschluessel** liegt auf dem Rechner, auf dem Releases gebaut werden;
* der **Notfallschluessel** liegt woanders (USB-Stick, Passwortverwaltung) und wird nur gebraucht, wenn
  der Hauptschluessel verloren geht oder abhanden kommt.

Beide oeffentlichen Schluessel stehen in `services/auto_update/schluessel.py`. Geht der Hauptschluessel
verloren, signiert der Notfallschluessel ein Update, das einen neuen Hauptschluessel eintraegt.
"""
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from bewerbungs_assistent.services.auto_update import ed25519, schluessel  # noqa: E402


def _nur_fuer_mich(pfad: Path) -> None:
    """Zugriff auf die Datei auf den angemeldeten Benutzer beschraenken (Windows: icacls, sonst chmod 600)."""
    if sys.platform == "win32":
        subprocess.run(["icacls", str(pfad), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:(R,W)"],
                       capture_output=True, check=False)
    else:
        os.chmod(pfad, 0o600)


def erzeugen(ausgabe: Path) -> int:
    if ausgabe.exists():
        print(f"FEHLER: {ausgabe} gibt es schon. Ein Schluessel wird nie ueberschrieben.", file=sys.stderr)
        return 1
    ausgabe.parent.mkdir(parents=True, exist_ok=True)
    geheim = os.urandom(32)
    ausgabe.write_text(geheim.hex() + "\n", encoding="utf-8")
    _nur_fuer_mich(ausgabe)
    oeffentlich = ed25519.geheim_zu_oeffentlich(geheim).hex()
    print(f"Geheimer Schluessel geschrieben: {ausgabe}")
    print("Sichere ihn jetzt (nicht in ein Repository, nicht in einen Chat).")
    print(f"Oeffentlicher Schluessel (in services/auto_update/schluessel.py eintragen):\n    {oeffentlich}")
    return 0


def _lesen(datei: Path) -> bytes:
    roh = bytes.fromhex(datei.read_text(encoding="utf-8").strip())
    if len(roh) != 32:
        raise SystemExit(f"FEHLER: {datei} enthaelt {len(roh)} statt 32 Byte")
    return roh


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="befehl", required=True)
    sub.add_parser("erzeugen").add_argument("--ausgabe", required=True, type=Path)
    sub.add_parser("oeffentlich").add_argument("--datei", required=True, type=Path)
    sub.add_parser("pruefen").add_argument("--datei", required=True, type=Path)
    a = p.parse_args(argv)
    if a.befehl == "erzeugen":
        return erzeugen(a.ausgabe)
    oeffentlich = ed25519.geheim_zu_oeffentlich(_lesen(a.datei)).hex()
    if a.befehl == "oeffentlich":
        print(oeffentlich)
        return 0
    vertraut = {n: b.hex() for n, b in schluessel.schluessel_bytes().items()}
    for name, hexwert in vertraut.items():
        if hexwert == oeffentlich:
            print(f"OK: der Schluessel ist im Code als '{name}' eingetragen.")
            return 0
    print("NICHT eingetragen: der oeffentliche Schluessel zu dieser Datei steht nicht in schluessel.py.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
