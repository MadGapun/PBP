"""Signierschluessel fuer das Auto-Update (#1093): erzeugen, finden, pruefen, sichern.

    python scripts/update_schluessel.py stand      # wo liegen die Schluessel, passen sie, gibt es eine Sicherung?
    python scripts/update_schluessel.py sichern    # beide Schluessel in die Sicherung kopieren und gegenpruefen
    python scripts/update_schluessel.py erzeugen --ausgabe C:/geheim/pbp-update-haupt.hex
    python scripts/update_schluessel.py oeffentlich --datei C:/geheim/pbp-update-haupt.hex
    python scripts/update_schluessel.py pruefen --datei C:/geheim/pbp-update-haupt.hex

Wer PBP benutzt, braucht keinen Schluessel. Nur wer Updates veroeffentlicht, signiert sie damit; PBP prueft die
Signatur mit den oeffentlichen Schluesseln in `services/auto_update/schluessel.py` und installiert nichts ohne gueltige.

**Automatisch (seit 03.10.2026):** Die Schluessel liegen an einem festen Ort, `~/PBP-Signatur` (umlenkbar mit
`PBP_SIGNATUR_ORDNER`): der Hauptschluessel als `pbp-update-haupt.hex`, der Notfallschluessel als
`pbp-update-notfall.hex` in einem Unterordner. `scripts/build_update_archive.py` nimmt den Hauptschluessel von dort,
wenn weder `--schluessel-datei` noch `PBP_UPDATE_SCHLUESSEL_DATEI` etwas anderes sagt, und `release_check.py` prueft
vor jedem Release, dass er da ist, zu einem eingetragenen Schluessel passt und dass es eine Sicherung gibt. Die
Sicherung liegt im OneDrive-Ordner (`%OneDrive%/PBP-Signatur-Sicherung`, umlenkbar mit `PBP_SIGNATUR_SICHERUNG`);
in ein Git-Arbeitsverzeichnis wird nie gesichert.

Der GEHEIME Schluessel (32 Zufallsbytes als 64 Hex-Zeichen in einer Datei) darf nie in ein Repository,
nie in ein Issue, nie in einen Chat. Wer ihn hat, kann Updates signieren, die alle Installationen
mit eingeschaltetem Auto-Update ohne Rueckfrage ausfuehren.

Zwei Schluessel sind Absicht:

* der **Hauptschluessel** liegt auf dem Rechner, auf dem Releases gebaut werden;
* der **Notfallschluessel** wird nur gebraucht, wenn der Hauptschluessel verloren geht oder abhanden kommt.

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

SIGNATUR_ORDNER_ENV = "PBP_SIGNATUR_ORDNER"
SICHERUNG_ENV = "PBP_SIGNATUR_SICHERUNG"
HAUPT_NAME = "pbp-update-haupt.hex"
NOTFALL_NAME = "pbp-update-notfall.hex"
SICHERUNG_UNTERORDNER = "PBP-Signatur-Sicherung"

LIESMICH = """Sicherung der Signaturschluessel fuer PBP-Updates (#1093).

Mit diesen Dateien werden PBP-Updates beim Veroeffentlichen signiert. Wer PBP nur benutzt, braucht sie nicht.
Nicht weitergeben, nicht in ein Repository, nicht in einen Chat.

Wiederherstellen (zum Beispiel nach einem neuen Rechner):
  pbp-update-haupt.hex    nach  <Benutzerordner>/PBP-Signatur/
  pbp-update-notfall.hex  nach  <Benutzerordner>/PBP-Signatur/notfall/
Pruefen: python scripts/update_schluessel.py stand
"""


def _nur_fuer_mich(pfad: Path) -> None:
    """Zugriff auf die Datei auf den angemeldeten Benutzer beschraenken (Windows: icacls, sonst chmod 600)."""
    if sys.platform == "win32":
        subprocess.run(["icacls", str(pfad), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:(R,W)"],
                       capture_output=True, check=False)
    else:
        os.chmod(pfad, 0o600)


def signatur_ordner() -> Path:
    """Der feste Ort der Schluessel: `~/PBP-Signatur`, sonst was `PBP_SIGNATUR_ORDNER` sagt."""
    return Path(os.environ.get(SIGNATUR_ORDNER_ENV) or (Path.home() / "PBP-Signatur"))


def sicherungs_ordner() -> Path | None:
    """Wohin gesichert wird: `PBP_SIGNATUR_SICHERUNG`, sonst `%OneDrive%/PBP-Signatur-Sicherung`, sonst None."""
    eigen = os.environ.get(SICHERUNG_ENV)
    if eigen:
        return Path(eigen)
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    return Path(onedrive) / SICHERUNG_UNTERORDNER if onedrive else None


def hauptschluessel() -> Path | None:
    datei = signatur_ordner() / HAUPT_NAME
    return datei if datei.is_file() else None


def notfallschluessel() -> Path | None:
    ordner = signatur_ordner()
    if not ordner.is_dir():
        return None
    treffer = sorted(ordner.rglob(NOTFALL_NAME))
    return treffer[0] if treffer else None


def _lesen_roh(datei: Path) -> bytes:
    roh = bytes.fromhex(Path(datei).read_text(encoding="utf-8").strip())
    if len(roh) != 32:
        raise ValueError(f"{datei} enthaelt {len(roh)} statt 32 Byte")
    return roh


def _lesen(datei: Path) -> bytes:
    try:
        return _lesen_roh(datei)
    except ValueError as exc:
        raise SystemExit(f"FEHLER: {exc}") from exc


def name_im_code(datei) -> str | None:
    """Unter welchem Namen steht der oeffentliche Teil im Code? None: nicht eingetragen oder nicht lesbar."""
    try:
        oeffentlich = ed25519.geheim_zu_oeffentlich(_lesen_roh(datei))
    except Exception:
        return None
    for name, roh in schluessel.schluessel_bytes().items():
        if roh == oeffentlich:
            return name
    return None


def stand() -> dict:
    """Wo liegen die Schluessel, passen sie zum Code, ist die Sicherung vollstaendig? Liest nur."""
    haupt, notfall, sicherung = hauptschluessel(), notfallschluessel(), sicherungs_ordner()
    gesichert = []
    if sicherung is not None:
        for name, datei_name in (("haupt", HAUPT_NAME), ("notfall", NOTFALL_NAME)):
            kopie = sicherung / datei_name
            gesichert.append(kopie.is_file() and name_im_code(kopie) == name)
    return {
        "ordner": str(signatur_ordner()),
        "hauptschluessel": str(haupt) if haupt else None,
        "haupt_im_code": name_im_code(haupt) if haupt else None,
        "notfallschluessel": str(notfall) if notfall else None,
        "notfall_im_code": name_im_code(notfall) if notfall else None,
        "sicherung": str(sicherung) if sicherung else None,
        "sicherung_vollstaendig": bool(gesichert) and all(gesichert),
    }


def _im_git_arbeitsbaum(pfad: Path) -> bool:
    """Liegt `pfad` (oder sein naechster vorhandener Elternordner) in einem Git-Arbeitsverzeichnis?"""
    p = Path(pfad).absolute()
    while not p.exists() and p.parent != p:
        p = p.parent
    p = p.resolve()
    return any((teil / ".git").exists() for teil in (p, *p.parents))


def sichern(ziel=None) -> int:
    """Beide Schluessel nach `ziel` (Vorgabe: die Sicherung) kopieren und gegenpruefen. Ueberschreibt nie einen anderen."""
    ziel = Path(ziel) if ziel else sicherungs_ordner()
    if ziel is None:
        print("FEHLER: kein Ziel fuer die Sicherung (kein OneDrive-Ordner gefunden). Ziel angeben: --ziel <Ordner>",
              file=sys.stderr)
        return 1
    if _im_git_arbeitsbaum(ziel):
        print(f"FEHLER: {ziel} liegt in einem Git-Arbeitsverzeichnis. Schluessel kommen nie in ein Repository.",
              file=sys.stderr)
        return 1
    quellen = [(HAUPT_NAME, hauptschluessel()), (NOTFALL_NAME, notfallschluessel())]
    fehlend = [name for name, quelle in quellen if quelle is None]
    if fehlend:
        print(f"FEHLER: nicht gefunden in {signatur_ordner()}: {', '.join(fehlend)}", file=sys.stderr)
        return 1
    for name, quelle in quellen:
        kopie = ziel / name
        if kopie.exists() and kopie.read_bytes().strip() != quelle.read_bytes().strip():
            print(f"FEHLER: {kopie} gibt es schon mit ANDEREM Inhalt. Ein Schluessel wird nie ueberschrieben.",
                  file=sys.stderr)
            return 1
    ziel.mkdir(parents=True, exist_ok=True)
    for name, quelle in quellen:
        kopie = ziel / name
        if not kopie.exists():
            kopie.write_bytes(quelle.read_bytes())
            _nur_fuer_mich(kopie)
        if ed25519.geheim_zu_oeffentlich(_lesen_roh(kopie)) != ed25519.geheim_zu_oeffentlich(_lesen_roh(quelle)):
            print(f"FEHLER: die Kopie {kopie} stimmt nicht mit dem Original ueberein.", file=sys.stderr)
            return 1
    (ziel / "LIESMICH.txt").write_text(LIESMICH, encoding="utf-8")
    print(f"Gesichert und gegengeprueft: {ziel} ({HAUPT_NAME}, {NOTFALL_NAME})")
    return 0


def stand_ausgeben() -> int:
    s = stand()
    print(f"Schluesselordner: {s['ordner']}")
    for art, datei, name in (("Hauptschluessel", s["hauptschluessel"], s["haupt_im_code"]),
                             ("Notfallschluessel", s["notfallschluessel"], s["notfall_im_code"])):
        if not datei:
            print(f"{art}: FEHLT")
        else:
            print(f"{art}: {datei} ({'im Code als ' + repr(name) if name else 'NICHT im Code eingetragen'})")
    if not s["sicherung"]:
        print("Sicherung: kein Ziel (kein OneDrive-Ordner)")
    else:
        print(f"Sicherung: {s['sicherung']} ({'vollstaendig' if s['sicherung_vollstaendig'] else 'FEHLT oder unvollstaendig'})")
    alles_gut = bool(s["haupt_im_code"] and s["notfall_im_code"] and s["sicherung_vollstaendig"])
    return 0 if alles_gut else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="befehl", required=True)
    sub.add_parser("erzeugen").add_argument("--ausgabe", required=True, type=Path)
    sub.add_parser("oeffentlich").add_argument("--datei", required=True, type=Path)
    sub.add_parser("pruefen").add_argument("--datei", required=True, type=Path)
    sub.add_parser("stand")
    sub.add_parser("sichern").add_argument("--ziel", type=Path, default=None)
    a = p.parse_args(argv)
    if a.befehl == "erzeugen":
        return erzeugen(a.ausgabe)
    if a.befehl == "stand":
        return stand_ausgeben()
    if a.befehl == "sichern":
        return sichern(a.ziel)
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
    print("Sichere ihn jetzt: python scripts/update_schluessel.py sichern (nie in ein Repository, nie in einen Chat).")
    print(f"Oeffentlicher Schluessel (in services/auto_update/schluessel.py eintragen):\n    {oeffentlich}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
