# -*- coding: utf-8 -*-
"""Baut die beiden Dinge fuer Block E5 des Testlaufs (Vorabversion von selbst, #1199/#1222) aus dem Stand dieses Repos.

Aufruf:
    python docs/internal/testlauf/probe_vorab_bauen.py <Installer-Fassung> <Update-Fassung> <Ausgabeordner> [--quelle <Repo-Wurzel>]

Beispiel:
    python docs/internal/testlauf/probe_vorab_bauen.py 1.9.0-rc.1 1.9.0-rc.2 C:/Temp/probe_vorab

Ergebnis:
    <Ausgabeordner>/PBP-<Installer-Fassung>.zip     der Installer zum Installieren von Hand (wie das ZIP einer Veroeffentlichung:
                                                     ein Ordner `PBP-<Fassung>/` mit allen versionierten Dateien)
    <Ausgabeordner>/update/pbp-update-<Update-Fassung>.zip, SHA256SUMS, SHA256SUMS.sig
                                                     die drei Dateien der Probe-Veroeffentlichung (als VORABVERSION gekennzeichnet)

Warum zwei Fassungen: Ein Auto-Update kann nur ein Programm ausfuehren, das den Schalter und die Installation einer Vorabversion
KENNT. Das echte `1.8.0-rc.3` kann es nicht (#1222). Darum bekommt die Installation hier den Stand dieses Repos mit der Nummer
`1.9.0-rc.1`, und das Update den Stand mit `1.9.0-rc.2`. Der Rest (Prueffolge, Signatur, Selbsttest) ist der echte.
Bewusst die Linie 1.9: die stabilen Probe-Veroeffentlichungen der anderen Bloecke (v1.8.x) liegen in einer anderen Linie
und kommen nicht dazwischen (ein Linienwechsel geschieht nie von selbst).

Der Schluessel zum Signieren verlaesst den Rechner nie (`~/PBP-Signatur`); hochgeladen werden nur die drei Dateien in das PROBE-Repository.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

VORAB = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,4}-(alpha|beta|rc)\.[0-9]{1,3}")


def _versionieren(wurzel: Path, fassung: str) -> None:
    """Die Fassung an den drei Stellen setzen (`release_check.py` verlangt sie gleich)."""
    ersetzungen = (
        (wurzel / "pyproject.toml", r'^version\s*=\s*"[^"]+"', f'version = "{fassung}"'),
        (wurzel / "src" / "bewerbungs_assistent" / "__init__.py", r'^__version__\s*=\s*"[^"]+"', f'__version__ = "{fassung}"'),
        (wurzel / "frontend" / "package.json", r'^(\s*)"version"\s*:\s*"[^"]+"', rf'\1"version": "{fassung}"'),
    )
    for pfad, muster, neu in ersetzungen:
        if not pfad.is_file():
            continue
        roh = pfad.read_bytes().decode("utf-8")
        text, n = re.subn(muster, neu, roh, count=1, flags=re.M)
        if n != 1:
            raise SystemExit(f"FEHLER: Fassung in {pfad.name} nicht gefunden")
        pfad.write_bytes(text.encode("utf-8"))


def _kopieren(quelle: Path, ziel: Path) -> None:
    """Alle versionierten Dateien (nicht `.git`, nicht Gebautes ausserhalb von git)."""
    dateien = subprocess.run(["git", "ls-files", "-z"], cwd=str(quelle), capture_output=True, check=True).stdout.split(b"\0")
    for roh in dateien:
        if not roh:
            continue
        rel = roh.decode("utf-8")
        s = quelle / rel
        if not s.is_file():
            continue
        z = ziel / rel
        z.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, z)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("installer_fassung", help="Vorab-Fassung fuer den Installer von Hand, z. B. 1.9.0-rc.1")
    p.add_argument("update_fassung", help="Vorab-Fassung des Updates, z. B. 1.9.0-rc.2 (neuer, gleiche Linie)")
    p.add_argument("ausgabe", help="Zielordner")
    p.add_argument("--quelle", default=str(Path(__file__).resolve().parents[3]), help="Repo-Wurzel (Vorgabe: dieses Repo)")
    a = p.parse_args()
    for f in (a.installer_fassung, a.update_fassung):
        if not VORAB.fullmatch(f):
            print(f"FEHLER: {f!r} ist keine Vorab-Fassung (X.Y.Z-rc.N)", file=sys.stderr)
            return 2
    wurzel = Path(a.quelle).resolve()
    aus = Path(a.ausgabe).resolve()
    aus.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pbp_probe_vorab_") as tmp:
        tmp = Path(tmp)
        # 1) der Installer zum Installieren von Hand: ein ZIP mit einem Ordner PBP-<Fassung>/
        ordner = tmp / f"PBP-{a.installer_fassung}"
        _kopieren(wurzel, ordner)
        _versionieren(ordner, a.installer_fassung)
        ziel_zip = aus / f"PBP-{a.installer_fassung}.zip"
        with zipfile.ZipFile(ziel_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for datei in sorted(ordner.rglob("*")):
                if datei.is_file():
                    zf.write(datei, datei.relative_to(tmp).as_posix())
        print(f"Installer: {ziel_zip} ({ziel_zip.stat().st_size // 1024} KB)")
        # 2) das Update als Vorabversion: dieselbe Quelle, andere Nummer, signiert
        inhalt = tmp / "update_inhalt"
        _kopieren(wurzel, inhalt)
        _versionieren(inhalt, a.update_fassung)
        update_aus = aus / "update"
        r = subprocess.run([sys.executable, str(wurzel / "scripts" / "build_update_archive.py"), "--ordner", str(inhalt),
                            "--ausgabe", str(update_aus), "--vorabversion"], cwd=str(wurzel))
        if r.returncode != 0:
            return r.returncode
    print(f"Update: {update_aus} (pbp-update-{a.update_fassung}.zip, SHA256SUMS, SHA256SUMS.sig)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
