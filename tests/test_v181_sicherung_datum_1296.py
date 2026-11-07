"""#1296: Die Sicherung im Deinstaller gelingt auch bei einem Datumsformat, das nicht TT.MM.JJJJ ist.

Gefunden mit der Windows-Probe (#1294): auf einem Windows mit englischem Format liefert `%date%` "Sun 11/01/2026". Der Name
der Sicherung wurde aus Teilen davon geschnitten und enthielt dann Schraegstriche; `Compress-Archive` scheiterte immer.

Der Test fuehrt den Abschnitt [6/7] des echten Deinstallers aus und ueberschreibt `date` (in cmd ueberdeckt eine gesetzte
Variable die eingebaute). Ohne den Fix bleibt der Desktop leer.
"""
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe gibt es nur unter Windows")


def _abschnitt_6_von_7() -> list[str]:
    zeilen = (WURZEL / "DEINSTALLIEREN.bat").read_bytes().decode("utf-8", errors="replace").splitlines()
    von = next(i for i, z in enumerate(zeilen) if "[6/7]" in z)
    bis = next(i for i, z in enumerate(zeilen) if "[7/7]" in z)
    return zeilen[von:bis]


def _lauf(tmp_path: Path, datum_text: str) -> tuple[str, Path]:
    daten = tmp_path / "daten"
    daten.mkdir()
    (daten / "pbp.db").write_bytes(b"SQLite format 3\0" + b"\0" * 64)
    profil = tmp_path / "profil"
    (profil / "Desktop").mkdir(parents=True)
    kopf = ["@echo off", "setlocal EnableDelayedExpansion", f'set "LOGFILE={tmp_path / "protokoll.txt"}"',
            f'set "DATA_DIR={daten}"', f'set "USERPROFILE={profil}"', f'set "date={datum_text}"']
    bat = tmp_path / "abschnitt.bat"
    bat.write_bytes(("\r\n".join(kopf + _abschnitt_6_von_7() + ["echo NACH_DEM_ABSCHNITT_OK"]) + "\r\n").encode("utf-8"))
    r = subprocess.run(["cmd", "/c", str(bat)], input=b"j\r\n", capture_output=True, timeout=120,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return (r.stdout + r.stderr).decode("cp850", errors="replace"), profil / "Desktop"


@pytest.mark.parametrize("datum_text", ["Sun 11/01/2026", "2026-11-01", "01.11.2026"])
def test_sicherung_gelingt_bei_jedem_datumsformat(tmp_path, datum_text):
    ausgabe, desktop = _lauf(tmp_path, datum_text)
    assert "NACH_DEM_ABSCHNITT_OK" in ausgabe, ausgabe
    zips = list(desktop.glob("PBP-Backup-*.zip"))
    assert len(zips) == 1 and zips[0].stat().st_size > 0, (zips, ausgabe)
    assert re.fullmatch(r"PBP-Backup-\d{4}-\d{2}-\d{2}\.zip", zips[0].name), zips[0].name
    assert "Backup NICHT erstellt" not in ausgabe


def test_der_name_traegt_das_heutige_datum(tmp_path):
    _, desktop = _lauf(tmp_path, "Sun 11/01/2026")
    assert [p.name for p in desktop.glob("PBP-Backup-*.zip")] == [f"PBP-Backup-{date.today().isoformat()}.zip"]
