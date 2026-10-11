# -*- coding: utf-8 -*-
"""Baut das signierte Probe-Archiv fuer den Auto-Update-Beweis (Testlauf 1.8.0, Block E2).

Aufruf:
    python docs/internal/testlauf/probe_archiv_bauen.py <Versionsnummer> <Ausgabeordner> [--quelle <Repo-Wurzel>]

Beispiel:
    python docs/internal/testlauf/probe_archiv_bauen.py 1.8.0 C:/Temp/probe_dist

Was es tut: kopiert `src/`, `start_dashboard.py` und `_selftest.py` des Repos in einen Wegwerf-Ordner, setzt dort `__version__` auf die
genannte STABILE Fassung (ein Update-Archiv einer Vorabversion wird nicht gebaut) und ruft `scripts/build_update_archive.py --ordner` auf.
Das Ergebnis sind genau die drei Dateien einer Veroeffentlichung: `pbp-update-<fassung>.zip`, `SHA256SUMS`, `SHA256SUMS.sig` —
signiert mit dem echten Schluessel von diesem Rechner (`~/PBP-Signatur`, siehe `scripts/update_schluessel.py`). Der Schluessel verlaesst den
Rechner nie; hochgeladen werden nur die drei Dateien, und zwar in das Probe-Repository, nie in das echte.

Der Inhalt ist der des Release-Kandidaten mit anderer Versionsnummer: das ist der Beweis, dass genau dieses Paket installiert, startet und
zurueckfaellt, nicht ein Testdouble.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("version", help="stabile Fassung, z. B. 1.8.0")
    p.add_argument("ausgabe", help="Zielordner fuer die drei Dateien")
    p.add_argument("--quelle", default=str(Path(__file__).resolve().parents[3]), help="Repo-Wurzel (Vorgabe: dieses Repo)")
    a = p.parse_args()
    if not re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,4}", a.version):
        print("FEHLER: eine stabile Fassung X.Y.Z ist verlangt", file=sys.stderr)
        return 2
    wurzel = Path(a.quelle).resolve()
    for n in ("src", "start_dashboard.py", "_selftest.py", "scripts/build_update_archive.py"):
        if not (wurzel / n).exists():
            print(f"FEHLER: {n} fehlt in {wurzel}", file=sys.stderr)
            return 2
    with tempfile.TemporaryDirectory(prefix="pbp_probe_") as tmp:
        ziel = Path(tmp) / "inhalt"
        shutil.copytree(wurzel / "src", ziel / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(wurzel / "start_dashboard.py", ziel / "start_dashboard.py")
        shutil.copy2(wurzel / "_selftest.py", ziel / "_selftest.py")
        init = ziel / "src" / "bewerbungs_assistent" / "__init__.py"
        text = init.read_text(encoding="utf-8")
        neu, n = re.subn(r'^__version__\s*=\s*"[^"]+"', f'__version__ = "{a.version}"', text, flags=re.M)
        if n != 1:
            print("FEHLER: __version__ nicht gefunden", file=sys.stderr)
            return 2
        init.write_text(neu, encoding="utf-8", newline="\n")
        r = subprocess.run([sys.executable, str(wurzel / "scripts" / "build_update_archive.py"), "--ordner", str(ziel),
                            "--ausgabe", str(Path(a.ausgabe).resolve())], cwd=str(wurzel))
        return r.returncode


if __name__ == "__main__":
    sys.exit(main())
