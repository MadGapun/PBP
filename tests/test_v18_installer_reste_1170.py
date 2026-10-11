"""Installer-Reste (#1170, Gegenprobe vom 06.10.2026 auf einem frischen Windows 11): PP20, PP21, PP23.

* PP20  Nach dem Aufräumen am Ende der Installation blieb ein leerer Ordner liegen, solange das Dashboard-Fenster offen war: das
        Fenster erbt den Arbeitsordner des Installers und hält ihn fest (dieselbe Klasse wie PP13 beim Deinstaller).
* PP21  Nach jeder Neuinstallation blieb ein Fenster „[FEHLER] Dashboard ist mit Fehlercode -1 beendet“ mit „Pause“ stehen: der
        Installer beendete das alte Python, das Fenster, das es gestartet hatte, meldete den Abbruch.
* PP23  Temp-Reste: je Selbsttest ein Ordner mit Datenbank und Protokoll (rund 0,6 MB) und die Kopie des Aufräum-Helfers.

Die Zeilen aus der .bat werden wie in den Tests des Deinstallers gelesen; der Prozessfilter läuft gegen ERFUNDENE Prozesse (Stop-Process
wird nie ausgeführt: das träfe die echte Installation auf diesem Rechner).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BAT = (ROOT / "INSTALLIEREN.bat").read_text(encoding="utf-8")
nur_windows = pytest.mark.skipif(os.name != "nt", reason="braucht Windows PowerShell")
POWERSHELL = "powershell"


def _prozessfilter() -> str:
    zeile = next(z for z in BAT.splitlines() if "Get-CimInstance Win32_Process" in z and "Stop-Process" in z)
    von = zeile.index("Where-Object {") + len("Where-Object {")
    return zeile[von:zeile.index("} | ForEach-Object")].strip()


# ── PP21 ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_pp21_der_filter_nennt_das_dashboard_fenster():
    assert "Dashboard starten\\.bat" in _prozessfilter()


@nur_windows
def test_pp21_der_filter_trifft_das_alte_fenster_und_nie_den_installer_selbst():
    faelle = {
        "python-pbp": ("python.exe", "python.exe -m bewerbungs_assistent", True),
        "python-start": ("python.exe", "python.exe start_dashboard.py", True),
        "python-fremd": ("python.exe", "python.exe meine_anwendung.py", False),
        "dashboard-fenster": ("cmd.exe", 'cmd.exe /K "C:\\Users\\x\\AppData\\Local\\BewerbungsAssistent\\app\\Dashboard starten.bat"', True),
        "dashboard-fenster-min": ("cmd.exe", 'C:\\WINDOWS\\system32\\cmd.exe /c ""C:\\Users\\x\\AppData\\Local\\BewerbungsAssistent\\app\\Dashboard starten.bat" "',
                                  True),
        "installer-selbst": ("cmd.exe", 'cmd.exe /c ""C:\\Users\\x\\Downloads\\PBP-1.8.0\\INSTALLIEREN.bat""', False),
        "fremdes-cmd": ("cmd.exe", "cmd.exe /c dir C:\\", False),
        "powershell-des-installers": ("powershell.exe", "powershell -Command Get-CimInstance Dashboard starten.bat", False),
    }
    zeilen = ", ".join(
        "[pscustomobject]@{N='%s'; Name='%s'; CommandLine='%s'; ExecutablePath=''}" % (n, name, cl.replace("'", "''"))
        for n, (name, cl, _) in faelle.items())
    befehl = "$o = @(%s); $o | Where-Object { %s } | ForEach-Object { $_.N }" % (zeilen, _prozessfilter())
    r = subprocess.run([POWERSHELL, "-NoProfile", "-Command", befehl], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert set(r.stdout.split()) == {n for n, (_, _, soll) in faelle.items() if soll}, r.stdout


# ── PP20 ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_pp20_das_dashboard_fenster_bekommt_den_programmordner_als_arbeitsordner():
    zeile = next(z for z in BAT.splitlines() if z.startswith('start "PBP-Dashboard"'))
    assert '/D "%APP_DIR%"' in zeile, zeile
    # /D steht VOR dem Programm, sonst wäre es dessen Argument
    assert zeile.index('/D "%APP_DIR%"') < zeile.index("Dashboard starten.bat"), zeile


# ── PP23 ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_pp23_der_helfer_loescht_seine_eigene_kopie(tmp_path):
    ziel = tmp_path / "entpackt"
    ziel.mkdir()
    (ziel / "datei.txt").write_text("x", encoding="utf-8")
    kopie = tmp_path / "pbp_installer_aufraeumen.py"
    kopie.write_bytes((ROOT / "_installer_aufraeumen.py").read_bytes())
    r = subprocess.run([sys.executable, str(kopie), "lauf", json.dumps({"ordner": str(ziel), "zips": []})],
                       capture_output=True, text=True, timeout=60, cwd=str(tmp_path))
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert not ziel.exists(), "der entpackte Ordner ist weg"
    assert not kopie.exists(), "die Kopie des Helfers löscht sich am Ende selbst"


def test_pp23_die_urspruengliche_datei_bleibt_beim_aufruf_aus_dem_repo_stehen(tmp_path):
    ziel = tmp_path / "entpackt"
    ziel.mkdir()
    r = subprocess.run([sys.executable, str(ROOT / "_installer_aufraeumen.py"), "lauf", json.dumps({"ordner": str(ziel), "zips": []})],
                       capture_output=True, text=True, timeout=60, cwd=str(tmp_path))
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert (ROOT / "_installer_aufraeumen.py").is_file()


@nur_windows
def test_pp23_der_selbsttest_hinterlaesst_kein_datenverzeichnis(tmp_path):
    """Der importierte Server hält Datenbank und Protokoll offen; Windows löscht keine geöffnete Datei. Ein abgetrennter Helfer räumt nach."""
    temp = tmp_path / "temp"
    temp.mkdir()
    env = {**os.environ, "TMP": str(temp), "TEMP": str(temp), "PYTHONPATH": str(ROOT / "src")}
    env.pop("BA_DATA_DIR", None)
    r = subprocess.run([sys.executable, str(ROOT / "_selftest.py")], capture_output=True, text=True, timeout=180, env=env, cwd=str(tmp_path))
    assert r.returncode == 0, (r.stdout[-800:], r.stderr[-800:])
    assert "OK" in r.stdout
    # der Helfer läuft abgetrennt und braucht ein paar Sekunden
    ende = time.time() + 60
    reste = list(temp.iterdir())
    while reste and time.time() < ende:
        time.sleep(1)
        reste = list(temp.iterdir())
    assert not reste, f"Reste im Temp-Ordner: {[p.name for p in reste]}"


def test_pp23_der_helfer_des_selbsttests_bekommt_einen_eigenen_arbeitsordner():
    """Der Aufräum-Helfer erbt sonst den Arbeitsordner des Selbsttests — und das ist der entpackte Ordner der neuen Version (die
    Installation startet den Selbsttest dort und benennt den Ordner gleich danach um). Auf jedem System prüfbar: der Aufruf nennt
    `cwd`."""
    import ast
    baum = ast.parse((ROOT / "_selftest.py").read_text(encoding="utf-8"))
    aufrufe = [n for n in ast.walk(baum)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "Popen"]
    assert aufrufe, "der Helfer wird nicht mehr über Popen gestartet — Test anpassen"
    for a in aufrufe:
        assert any(k.arg == "cwd" for k in a.keywords), "Popen des Helfers ohne cwd: er hält den entpackten Ordner fest"


@nur_windows
def test_pp23_der_entpackte_ordner_laesst_sich_nach_dem_selbsttest_sofort_umbenennen(tmp_path):
    """Gemessen am Kandidaten: ohne eigenen Arbeitsordner des Helfers scheiterte der erste `os.replace` immer mit WinError 32
    und gelang erst nach einer Sekunde Wiederholung; die Installation gibt nach fünf Versuchen auf."""
    entpackt = tmp_path / "entpackt"
    entpackt.mkdir()
    temp = tmp_path / "temp"
    temp.mkdir()
    env = {**os.environ, "TMP": str(temp), "TEMP": str(temp), "PYTHONPATH": str(ROOT / "src")}
    env.pop("BA_DATA_DIR", None)
    r = subprocess.run([sys.executable, str(ROOT / "_selftest.py")], capture_output=True, text=True, timeout=180, env=env,
                       cwd=str(entpackt))
    assert r.returncode == 0, (r.stdout[-800:], r.stderr[-800:])
    ziel = tmp_path / "neu"
    os.replace(entpackt, ziel)  # sofort, ohne Wiederholung — genau wie die Installation es zuerst versucht
    assert ziel.is_dir()
