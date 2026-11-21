"""#1425: Der Installer entpackt Python auch, wenn er aus PowerShell 7 startet.

Die eigentliche Probe ist der Job `installer` der Windows-Probe (PowerShell 7
auf dem Runner). Dieser Test haelt nur die Bauform fest.
"""
from pathlib import Path

BAT = Path(__file__).resolve().parents[1] / "INSTALLIEREN.bat"


def test_modulpfad_wird_vor_dem_entpacken_geleert():
    zeilen = BAT.read_text(encoding="utf-8").splitlines()
    entpacken = next(i for i, z in enumerate(zeilen)
                     if z.startswith("powershell") and "Expand-Archive" in z)
    leeren = [i for i, z in enumerate(zeilen) if z.strip() == 'set "PSModulePath="']
    assert leeren and leeren[0] < entpacken
