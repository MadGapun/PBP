"""#1149 Installer Teil 2, Rest (1.8.0): Ordnername, Deinstaller im TEMP-Ordner, Mac/Linux, Zahlen und Texte.

Befunde (01.10.2026, Durchsicht Installation/Update/erster Start), hier die, die in v1.7.149/v1.7.150 noch offen blieben:

* Punkt 8 — ein Ordnername mit `!` oder `'` oder `(1)` (so legt der Browser eine zweite Kopie an): das `!` verschwand aus jedem
  Pfad (unter `EnableDelayedExpansion`), ein Apostroph brach `Expand-Archive`, eine Klammer beendete einen Block.
  Der Mensch las "ZIP nicht entpackt" oder "als Administrator ausfuehren" — und ein Benutzername mit Apostroph machte aus dem
  Desktop-Backup des Deinstallers einen Syntaxfehler mit Exit 1, der als "kein Datenordner" galt: kein Backup, keine Warnung.
* Punkt 9a — beim Aufruf ueber "Apps & Features" laeuft der Deinstaller aus %TEMP%; `%~dp0` ist dann %TEMP% selbst, und
  `%TEMP%\\python`, `install_log.txt` und `python-*-embed-amd64.zip` wurden geloescht.
* Punkt 9d — `installer/deinstallieren.sh` meldete bei kaputter JSON-Datei "MCP-Eintrag war nicht vorhanden".
* Punkt 6 (Rest) — beim Update auf macOS/Linux blieb das Dashboard der alten Fassung auf dem Port; der Health-Check meldete
  "laeuft" gegen die ALTE Fassung (und ein fremdes Programm mit HTTP 200 gleich mit).
* Punkt 12 — `server.json` stand auf 1.7.0, `uv.lock` auf 1.5.7, `release_check` prueft beides nicht, `install.ps1` ist veraltet,
  LIESMICH/README ohne SmartScreen, die Fehlertexte nennen kein "Internet pruefen, nochmal starten".

Die Verhaltenstests fuehren die ECHTEN Zeilen aus den Dateien aus (nie nachgebaut): unter Windows cmd.exe und Windows
PowerShell, fuer Mac/Linux ein bash (unter Windows Git-Bash). Alle Ordner liegen in tmp_path; alle Namen sind Platzhalter.
"""
import functools
import http.server
import importlib
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0
POWERSHELL = shutil.which("powershell")
nur_windows = pytest.mark.skipif(sys.platform != "win32" or not POWERSHELL, reason="braucht cmd.exe und Windows PowerShell")

#: Ein Ordnername, der alles zugleich enthaelt, was Pfade sonst bricht (ausser `!`, das der Installer ablehnt).
UNGEWOEHNLICH = "Bewerber O'Brien (1) [privat]"


def _text(name: str) -> str:
    return (ROOT / name).read_bytes().decode("utf-8-sig").replace("\r\n", "\n")


def _bat_lauf(tmp_path, zeilen, env=None, eingabe=b"\r\n", name="harness.bat", cwd=None):
    """Schreibt die Zeilen in eine .bat und fuehrt sie mit cmd.exe aus. Rueckgabe: (Exitcode, Ausgabe)."""
    bat = tmp_path / name
    bat.write_bytes(("\r\n".join(zeilen) + "\r\n").encode("cp850", errors="replace"))
    umgebung = dict(os.environ)
    umgebung.update(env or {})
    r = subprocess.run(["cmd.exe", "/c", str(bat)], input=eingabe, capture_output=True, env=umgebung,
                       cwd=str(cwd or tmp_path), creationflags=OHNE_FENSTER, timeout=180)
    return r.returncode, (r.stdout + r.stderr).decode("cp850", errors="replace")


def _ps_zeilen(text: str, enthaelt: str) -> list[str]:
    """Die PowerShell-Zeilen der Datei, die `enthaelt` tragen (eingerueckte eingeschlossen)."""
    return [z.strip() for z in text.split("\n") if z.strip().lower().startswith("powershell") and enthaelt in z]


def _ps_lauf(tmp_path, zeile: str, env: dict):
    """Fuehrt EINE echte PowerShell-Zeile aus der BAT-Datei aus; die Pfade stehen wie im Installer in der Umgebung."""
    umgebung = {"LOGFILE": str(tmp_path / "ps_log.txt")}
    umgebung.update(env)
    return _bat_lauf(tmp_path, ["@echo off", "setlocal EnableDelayedExpansion", zeile, "echo EXIT=!errorlevel!"], umgebung,
                     name="ps_zeile.bat")


def _frei() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ══ Punkt 8: ein Ausrufezeichen im Ordnernamen ════════════════════════════════════════════════

def _kopf_bis_guard() -> str:
    text = _text("INSTALLIEREN.bat")
    ende = ":ort_ohne_ausrufezeichen\nendlocal\nsetlocal EnableDelayedExpansion\n"
    assert ende in text, "die Pruefung auf ein Ausrufezeichen fehlt am Kopf von INSTALLIEREN.bat"
    return text[:text.index(ende) + len(ende)]


def test_1149_8_das_ausrufezeichen_wird_vor_der_verzoegerten_expansion_geprueft():
    text = _text("INSTALLIEREN.bat")
    zeilen = text.split("\n")
    pruefung = next(i for i, z in enumerate(zeilen) if z.startswith('if "%PBP_START_ORT:!=%"'))
    erste_expansion = next(i for i, z in enumerate(zeilen) if z.strip().lower() == "setlocal enabledelayedexpansion")
    assert zeilen[pruefung - 2].strip().lower() == "setlocal disabledelayedexpansion", "die Pruefung braucht ausgeschaltete Expansion"
    assert pruefung < erste_expansion, "danach koennte man das Zeichen nicht mehr sehen"


@nur_windows
@pytest.mark.parametrize("ordner,erwartet_weiter", [
    ("PBP-1.8.0", True), ("PBP-1.8.0 (1)", True), ("Bewerber O'Brien", True), ("PBP!neu", False), ("Hallo! PBP", False),
])
def test_1149_8_ein_ordner_mit_ausrufezeichen_wird_abgelehnt_alle_anderen_laufen_weiter(tmp_path, ordner, erwartet_weiter):
    """Die ECHTEN Kopfzeilen von INSTALLIEREN.bat, aus einem Ordner dieses Namens gestartet."""
    ziel = tmp_path / ordner
    ziel.mkdir()
    assert str(tmp_path) in str(ziel)
    (ziel / "start.bat").write_bytes((_kopf_bis_guard() + "set \"X=a\"\necho WEITER_DE=!X!\nexit /b 0\n").replace("\n", "\r\n").encode("cp850"))
    r = subprocess.run(["cmd.exe", "/c", str(ziel / "start.bat")], input=b"\r\n", capture_output=True, creationflags=OHNE_FENSTER, timeout=60)
    aus = (r.stdout + r.stderr).decode("cp850", errors="replace")
    if erwartet_weiter:
        assert r.returncode == 0 and "WEITER_DE=a" in aus, aus
        assert "Ausrufe" not in aus, aus
    else:
        assert r.returncode == 1, aus
        assert "WEITER_DE" not in aus
        assert "Ausrufezeichen" in aus and "C:\\PBP" in aus, "die Meldung nennt den Weg: einen Ort ohne Ausrufezeichen"


@nur_windows
@pytest.mark.parametrize("ordner", ["PBP-1.8.0 (1)", "Bewerber O'Brien", "PBP [privat]"])
def test_1149_8_der_installer_erreicht_aus_einem_ungewoehnlichen_ordner_seine_erste_pruefung(tmp_path, ordner):
    """Ganz durch den Kopf bis zur Pruefung "ZIP entpackt?": Namen, Pfade, Protokoll - ohne Syntaxfehler."""
    ziel = tmp_path / ordner
    ziel.mkdir()
    shutil.copy2(ROOT / "INSTALLIEREN.bat", ziel / "INSTALLIEREN.bat")
    r = subprocess.run(["cmd.exe", "/c", str(ziel / "INSTALLIEREN.bat")], input=b"\r\n", capture_output=True, cwd=str(ziel),
                       creationflags=OHNE_FENSTER, timeout=120)
    aus = (r.stdout + r.stderr).decode("cp850", errors="replace")
    assert "ZIP wurde nicht richtig entpackt" in aus, aus
    assert "syntaktisch" not in aus and "nicht verarbeitet" not in aus, aus
    assert r.returncode == 1


@nur_windows
def test_1149_8_das_dashboard_startskript_meldet_einen_fehlenden_python_ordner_auch_mit_klammer(tmp_path):
    ziel = tmp_path / "Dashboard (1)"
    ziel.mkdir()
    shutil.copy2(ROOT / "Dashboard starten.bat", ziel / "Dashboard starten.bat")
    r = subprocess.run(["cmd.exe", "/c", str(ziel / "Dashboard starten.bat")], input=b"\r\n", capture_output=True, cwd=str(ziel),
                       creationflags=OHNE_FENSTER, timeout=120)
    aus = (r.stdout + r.stderr).decode("cp850", errors="replace")
    assert "Python nicht gefunden unter" in aus and "python\\python.exe" in aus, aus
    assert "syntaktisch" not in aus, aus


# ══ Punkt 8: ein Apostroph im Pfad (PowerShell bekommt Pfade ueber die Umgebung) ═════════════════

def _zip_mit(pfad: Path, dateien: dict):
    with zipfile.ZipFile(pfad, "w") as z:
        for name, inhalt in dateien.items():
            z.writestr(name, inhalt)


@nur_windows
def test_1149_8_python_wird_auch_aus_einem_ordner_mit_apostroph_entpackt(tmp_path):
    zeilen = _ps_zeilen(_text("INSTALLIEREN.bat"), "Expand-Archive")
    assert len(zeilen) == 1, zeilen
    basis = tmp_path / UNGEWOEHNLICH
    basis.mkdir()
    ziel = basis / "python"
    zip_pfad = basis / "python-3.12.10-embed-amd64.zip"
    _zip_mit(zip_pfad, {"python.exe": "x", "python312._pth": "python312.zip\n.\n#import site\n"})
    code, aus = _ps_lauf(tmp_path, zeilen[0], {"PY_ZIP_PATH": str(zip_pfad), "PYTHON_DIR": str(ziel)})
    assert (ziel / "python.exe").is_file(), aus
    assert "EXIT=0" in aus, aus


@nur_windows
def test_1149_8_die_pth_datei_wird_auch_in_einem_ordner_mit_apostroph_angepasst(tmp_path):
    zeilen = _ps_zeilen(_text("INSTALLIEREN.bat"), "#import site")
    assert len(zeilen) == 2, "der Weg mit frischem und der mit vorhandenem Python"
    basis = tmp_path / UNGEWOEHNLICH / "python"
    basis.mkdir(parents=True)
    for nr, zeile in enumerate(zeilen):
        pth = basis / f"python31{nr}._pth"
        pth.write_text("python312.zip\n.\n#import site\n", encoding="ascii")
        _ps_lauf(tmp_path, zeile, {"PTH_FILE": str(pth)})
        inhalt = pth.read_text(encoding="ascii")
        assert "\nimport site" in inhalt and "#import site" not in inhalt, (nr, inhalt)


@pytest.fixture
def dateiserver(tmp_path):
    """Ein kleiner HTTP-Server auf einem freien Port, der tmp_path/serve ausliefert."""
    ordner = tmp_path / "serve"
    ordner.mkdir()
    class _Still(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

    handler = functools.partial(_Still, directory=str(ordner))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield ordner, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@nur_windows
@pytest.mark.parametrize("marke,url_var,pfad_var", [("%PY_URL%", "PY_URL", "PY_ZIP_PATH"), ("%GETPIP_URL%", "GETPIP_URL", "GETPIP_PATH")])
def test_1149_8_der_powershell_download_schreibt_auch_in_einen_ordner_mit_apostroph(tmp_path, dateiserver, marke, url_var, pfad_var):
    ordner, basis_url = dateiserver
    (ordner / "datei.bin").write_bytes(b"inhalt-" + url_var.encode())
    zeilen = _ps_zeilen(_text("INSTALLIEREN.bat"), "Invoke-WebRequest")
    zeile = next(z for z in zeilen if marke in z)
    # Ohne eckige Klammern: `Invoke-WebRequest -OutFile` liest sie in Windows PowerShell 5.1 als Platzhalter (gemessen). Dieser Weg
    # ist ohnehin nur der Ersatz fuer ein fehlendes curl.exe (seit Windows 10 1803 an Bord); alle anderen Zeilen nehmen -LiteralPath.
    ziel = tmp_path / "Bewerber O'Brien (1)" / "ziel.bin"
    ziel.parent.mkdir()
    _ps_lauf(tmp_path, zeile, {url_var: f"{basis_url}/datei.bin", pfad_var: str(ziel)})
    assert ziel.is_file() and ziel.read_bytes() == b"inhalt-" + url_var.encode()


@nur_windows
def test_1149_8_die_sicherheitsblockade_wird_auch_in_einem_ordner_mit_apostroph_entfernt(tmp_path):
    zeilen = _ps_zeilen(_text("INSTALLIEREN.bat"), "Unblock-File")
    assert len(zeilen) == 2
    basis = tmp_path / UNGEWOEHNLICH
    basis.mkdir()
    for nr, zeile in enumerate(zeilen):
        datei = basis / f"aus_dem_netz_{nr}.txt"
        datei.write_text("x")
        with open(str(datei) + ":Zone.Identifier", "w") as ads:
            ads.write("[ZoneTransfer]\nZoneId=3\n")
        _ps_lauf(tmp_path, zeile, {"BASEDIR": str(basis)})
        with pytest.raises(OSError):
            open(str(datei) + ":Zone.Identifier").close()


@nur_windows
def test_1149_8_die_desktop_verknuepfung_entsteht_auch_bei_apostroph_im_benutzerordner(tmp_path):
    zeile = _ps_zeilen(_text("INSTALLIEREN.bat"), "CreateShortcut")[0]
    app = tmp_path / "Benutzer O'Brien" / "AppData" / "Local" / "BewerbungsAssistent" / "app"
    app.mkdir(parents=True)
    (app / "Dashboard starten.bat").write_text("@echo off\n")
    (app / "pbp.ico").write_bytes(b"\0" * 16)
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    assert str(tmp_path) in str(desktop), "QA-Isolation: nie der echte Desktop"
    _ps_lauf(tmp_path, zeile, {"APP_DIR": str(app), "PBP_DESKTOP": str(desktop)})
    lnk = desktop / "PBP Bewerbungs-Portal.lnk"
    assert lnk.is_file()
    lesen = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK); "
             "Write-Host ('ZIEL=' + $s.TargetPath); Write-Host ('ICON=' + $s.IconLocation)")
    r = subprocess.run([POWERSHELL, "-NoProfile", "-Command", lesen], env={**os.environ, "LNK": str(lnk)},
                       capture_output=True, text=True, creationflags=OHNE_FENSTER, timeout=60)
    assert f"ZIEL={app / 'Dashboard starten.bat'}" in r.stdout, r.stdout + r.stderr
    assert f"ICON={app / 'pbp.ico'},0" in r.stdout, r.stdout


@nur_windows
def test_1149_8_das_desktop_backup_des_deinstallers_klappt_bei_apostroph_im_pfad(tmp_path):
    """Vorher: Syntaxfehler (Exit 1) = "kein Datenordner" - kein Backup, keine Warnung, danach durfte der Mensch loeschen."""
    zeile = next(z for z in _ps_zeilen(_text("DEINSTALLIEREN.bat"), "Compress-Archive"))
    daten = tmp_path / "Benutzer O'Brien" / "data"
    daten.mkdir(parents=True)
    (daten / "pbp.db").write_bytes(b"x" * 4096)
    ziel = tmp_path / "Benutzer O'Brien" / "Desktop" / "PBP-Backup.zip"
    ziel.parent.mkdir()
    code, aus = _ps_lauf(tmp_path, zeile, {"DATA_DIR": str(daten), "BACKUP_ZIP": str(ziel)})
    assert ziel.is_file() and ziel.stat().st_size > 0, aus
    assert "EXIT=0" in aus and "[OK] Backup erstellt" in aus, aus


@nur_windows
@pytest.mark.parametrize("rc,fehler,protokoll", [(0, "0", "Desktop-Backup erstellt"), (1, "0", "uebersprungen"),
                                                  (2, "1", "NICHT erstellt")])
def test_1149_8_der_backup_exitcode_setzt_die_warnung_und_das_protokoll_stimmt(tmp_path, rc, fehler, protokoll):
    """Die echten Zeilen NACH dem PowerShell-Aufruf: nur Exit 2 oder mehr ist ein Fehlschlag, und das Protokoll sagt nicht
    "erstellt", wenn nichts entstand."""
    text = _text("DEINSTALLIEREN.bat")
    a = text.index('    set "BACKUP_RC=!errorlevel!"\n')
    zeilen = [z.strip() for z in text[a:text.index("\n)\n", a)].split("\n")]
    log = tmp_path / "log.txt"
    kopf = ["@echo off", "setlocal EnableDelayedExpansion", f'set "LOGFILE={log}"', 'set "BACKUP_FEHLER=0"', f"cmd /c exit /b {rc}"]
    code, aus = _bat_lauf(tmp_path, kopf + zeilen + ["echo FEHLER=!BACKUP_FEHLER!"])
    assert f"FEHLER={fehler}" in aus, aus
    inhalt = log.read_text(encoding="cp850")
    assert protokoll in inhalt, inhalt
    if rc < 2:
        assert "NICHT erstellt" not in inhalt
    if rc != 0:
        assert "Desktop-Backup erstellt" not in inhalt, "das Protokoll sagt \"erstellt\", obwohl nichts entstand"


def test_1149_8_kein_pfad_steckt_in_einer_powershell_zeile_der_batchdateien():
    """DoD 8c: die Regel haelt sich selbst. In keinem -Command steht ein %VAR% oder !VAR! (ausser Adressen): Pfade gehen ueber
    die Umgebung. Ein Apostroph im Pfad macht sonst aus dem Befehl einen Syntaxfehler."""
    befunde = []
    for name in ("INSTALLIEREN.bat", "DEINSTALLIEREN.bat", "Dashboard starten.bat"):
        for nr, zeile in enumerate(_text(name).split("\n"), 1):
            if "powershell" not in zeile.lower() or zeile.strip().lower().startswith(("::", "rem ")):
                continue
            m = re.search(r'-Command\s+"([^"]*)"', zeile)
            if not m:
                continue
            for v in re.finditer(r"%[A-Za-z_][A-Za-z0-9_]*%|![A-Za-z_][A-Za-z0-9_]*!", m.group(1)):
                if not v.group(0).strip("%!").endswith("_URL"):
                    befunde.append(f"{name}:{nr}: {v.group(0)}")
    assert not befunde, befunde


# ══ Punkt 8: Klammern in Pfaden (der Ordner "PBP-1.8.0 (1)" ist der haeufigste) ═══════════════

def _ohne_quotes(zeile: str) -> str:
    aus, q = [], False
    for ch in zeile:
        if ch == '"':
            q = not q
        elif not q:
            aus.append(ch)
    return "".join(aus)


PFAD_VARIABLEN = {"DIR", "BASEDIR", "PYTHON_DIR", "PYTHON", "SRC_DIR", "LOGFILE", "PY_ZIP_PATH", "GETPIP_PATH", "BASE_INSTALL",
                  "APP_DIR", "DATA_DIR", "LEGACY_RUNTIME", "LEGACY_SRC", "LOCAL_RUNTIME_DIR", "TARGET", "TARGET_LABEL",
                  "BACKUP_DB", "BACKUP_DIR", "PTH_FILE", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "TEMP", "TMP", "BACKUP_ZIP"}


def pfade_in_bloecken(text: str) -> list[tuple[int, str]]:
    """Zeilen INNERHALB eines ( ... )-Blocks, die einen Pfadwert ohne Anfuehrungszeichen aufloesen (%VAR%, nicht !VAR!).
    Hat der Wert eine Klammer, beendet sie den Block dort; mit !VAR! ist sie Daten."""
    treffer, tiefe = [], 0
    for nr, zeile in enumerate(text.split("\n"), 1):
        s = zeile.strip()
        if not s or s.lower().startswith(("::", "rem ")):
            continue
        vorher = tiefe
        t = _ohne_quotes(zeile).replace("^(", "").replace("^)", "")
        tiefe = max(0, tiefe + t.count("(") - t.count(")"))
        if vorher > 0:
            for m in re.finditer(r"%([A-Za-z_][A-Za-z0-9_]*)%", t):
                if m.group(1) in PFAD_VARIABLEN:
                    treffer.append((nr, s[:100]))
    return treffer


@pytest.mark.parametrize("name", ["INSTALLIEREN.bat", "DEINSTALLIEREN.bat", "Dashboard starten.bat"])
def test_1149_8_in_keinem_klammerblock_steht_ein_pfadwert_ohne_verzoegerte_expansion(name):
    assert pfade_in_bloecken(_text(name)) == []


def test_1149_8_der_klammerwaechter_findet_den_fall_und_laesst_die_reparierte_fassung_durch():
    kaputt = 'if exist "%X%" (\n    echo Ordner: %BASEDIR%\\python\n)\n'
    heil = 'if exist "%X%" (\n    echo Ordner: !BASEDIR!\\python\n    echo Log: "%LOGFILE%"\n)\necho %BASEDIR%\n'
    assert pfade_in_bloecken(kaputt) == [(2, "echo Ordner: %BASEDIR%\\python")]
    assert pfade_in_bloecken(heil) == []


@nur_windows
def test_1149_8_remove_path_meldet_auch_einen_ordner_mit_klammer(tmp_path):
    """Vorher: `"\\python" kann syntaktisch an dieser Stelle nicht verarbeitet werden` - der Ordner blieb liegen."""
    text = _text("DEINSTALLIEREN.bat")
    sub = text[text.index(":remove_path\n"):text.index("exit /b 0", text.index("echo         [OK] !TARGET_LABEL! entfernt")) + len("exit /b 0")]
    basis = tmp_path / "PBP-1.8.0 (1)"
    ziel = basis / "python"
    ziel.mkdir(parents=True)
    (ziel / "x.bin").write_bytes(b"1")
    kopf = ["@echo off", "setlocal EnableDelayedExpansion", f'set "LOGFILE={tmp_path / "log.txt"}"',
            f'call :remove_path "{ziel}" "Lokaler Python-Ordner in {basis}\\python"', "echo ENDE_ERREICHT", "exit /b 0", ""]
    code, aus = _bat_lauf(tmp_path, kopf + sub.split("\n"))
    assert not ziel.exists(), aus
    assert "[OK] Lokaler Python-Ordner in" in aus and "ENDE_ERREICHT" in aus and "syntaktisch" not in aus, aus


# ══ Punkt 9a: der Deinstaller laeuft aus %TEMP% ═══════════════════════════════════════════════

def _basedir_programm() -> str:
    text = _text("DEINSTALLIEREN.bat")
    rp = text[text.index(":remove_path\n"):text.index("exit /b 0", text.index("echo         [OK] !TARGET_LABEL! entfernt")) + len("exit /b 0")]
    a, b = text.index(":: --- basedir Anfang"), text.index(":: --- basedir Ende")
    return rp + "\n" + text[a:b]


def _fuelle(basis: Path):
    (basis / "python").mkdir(parents=True)
    (basis / "python" / "python.exe").write_bytes(b"x")
    (basis / "install_log.txt").write_text("log")
    (basis / "python-3.12.10-embed-amd64.zip").write_bytes(b"zip")
    (basis / "fremd.txt").write_text("gehoert mir")


def _basedir_lauf(tmp_path, basis: Path, temp: Path, relocated: bool, tmp_var: Path | None = None):
    assert str(tmp_path) in str(basis) and str(tmp_path) in str(temp), "QA-Isolation: nie der echte TEMP"
    kopf = ["@echo off", "setlocal EnableDelayedExpansion", f'set "LOGFILE={tmp_path / "log.txt"}"', f'set "BASEDIR={basis}"',
            'set "LOCAL_RUNTIME_DIR=%BASEDIR%\\python"', 'set "REMOVE_ERRORS=0"', "call :ordner_neben_dem_skript",
            "echo ENDE_ERREICHT", "exit /b 0", ""]
    env = {"TEMP": str(temp), "TMP": str(tmp_var or temp), "PBP_DEINST_RELOCATED": "1" if relocated else "0"}
    return _bat_lauf(tmp_path, kopf + _basedir_programm().split("\n"), env)


@nur_windows
def test_1149_9a_aus_dem_temp_ordner_bleibt_alles_neben_dem_skript_liegen(tmp_path):
    temp = tmp_path / "Temp"
    _fuelle(temp)
    code, aus = _basedir_lauf(tmp_path, temp, temp, relocated=True)
    assert "ENDE_ERREICHT" in aus, aus
    for name in ("python/python.exe", "install_log.txt", "python-3.12.10-embed-amd64.zip", "fremd.txt"):
        assert (temp / name).exists(), f"{name} geloescht - das ist nicht PBPs Datei: {aus}"


@nur_windows
def test_1149_9a_auch_ohne_umzugsmarke_wird_der_temp_ordner_selbst_nie_ausgeraeumt(tmp_path):
    """Wer den Deinstaller von Hand nach %TEMP% kopiert, hat die Marke nicht - der Ordner selbst zaehlt."""
    temp = tmp_path / "Temp"
    _fuelle(temp)
    # TMP zeigt woandershin: nur der Vergleich mit %TEMP% darf hier schuetzen (Gegenprobe i223).
    code, aus = _basedir_lauf(tmp_path, temp, temp, relocated=False, tmp_var=tmp_path / "Anderswo")
    assert (temp / "python" / "python.exe").exists() and (temp / "install_log.txt").exists(), aus


@nur_windows
def test_1149_9a_die_umzugsmarke_allein_genuegt(tmp_path):
    """Der umgezogene Deinstaller kann unter einer anderen Schreibweise von TEMP laufen (8.3-Kurzname): dann gleichen
    sich die Pfade nicht als Text, die Marke aber sagt es trotzdem."""
    basis = tmp_path / "AndereSchreibweise"
    _fuelle(basis)
    code, aus = _basedir_lauf(tmp_path, basis, tmp_path / "Temp", relocated=True)
    assert (basis / "python" / "python.exe").exists() and (basis / "install_log.txt").exists(), aus


@nur_windows
def test_1149_9a_auch_tmp_zaehlt_als_temp_ordner(tmp_path):
    basis = tmp_path / "Tmp"
    _fuelle(basis)
    code, aus = _basedir_lauf(tmp_path, basis, tmp_path / "Temp", relocated=False, tmp_var=basis)
    assert (basis / "python" / "python.exe").exists() and (basis / "install_log.txt").exists(), aus


def test_1149_9a_der_ablauf_ruft_die_pruefung_auf():
    """Die Tests rufen die Unterroutine selbst; dass Schritt [5/7] sie aufruft, sagt nur diese Zeile."""
    text = _text("DEINSTALLIEREN.bat")
    schritt = text[text.index("[5/7] Entferne Runtime-Dateien"):text.index("[6/7]")]
    assert "call :ordner_neben_dem_skript" in schritt
    assert "install_log.txt" not in schritt and "embed-amd64.zip" not in schritt, "die Aufraeumzeilen stehen nur in der Unterroutine"


@nur_windows
@pytest.mark.parametrize("ordner", ["PBP-1.8.0", "PBP-1.8.0 (1)"])
def test_1149_9a_im_entpackten_pbp_ordner_wird_weiter_aufgeraeumt(tmp_path, ordner):
    basis = tmp_path / "Downloads" / ordner
    _fuelle(basis)
    code, aus = _basedir_lauf(tmp_path, basis, tmp_path / "Temp", relocated=False)
    assert "ENDE_ERREICHT" in aus and "syntaktisch" not in aus, aus
    assert not (basis / "python").exists() and not (basis / "install_log.txt").exists()
    assert not (basis / "python-3.12.10-embed-amd64.zip").exists()
    assert (basis / "fremd.txt").exists(), "nur PBPs Dateien werden entfernt"


# ══ Punkt 6 (Rest) + 4: Mac/Linux — das alte Dashboard, der Health-Check ═════════════════════════

def _bash():
    try:
        from test_v17149_unix_installer_1149 import _bash as finde
    except ImportError:
        return shutil.which("bash")
    return finde()


@pytest.fixture(scope="module")
def bash():
    pfad = _bash()
    if not pfad:
        pytest.skip("kein lauffaehiges bash")
    return pfad


UNIX_DATEIEN = {"install.sh": ROOT / "installer" / "install.sh", "INSTALLIEREN.command": ROOT / "INSTALLIEREN.command"}


def _funktionen(name: str) -> str:
    text = UNIX_DATEIEN[name].read_text(encoding="utf-8")
    a, b = text.index("# --- dashboard-funktionen Anfang"), text.index("# --- dashboard-funktionen Ende")
    return text[a:b]


def test_1149_6_beide_unix_installer_tragen_dieselben_dashboard_funktionen():
    assert _funktionen("install.sh") == _funktionen("INSTALLIEREN.command")


def _bash_lauf(bash, skript: str, timeout=120):
    r = subprocess.run([bash, "-s"], input=skript.encode("utf-8"), capture_output=True, timeout=timeout, creationflags=OHNE_FENSTER)
    return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")


def _projekt(tmp_path, version="9.9.9") -> Path:
    p = tmp_path / "projekt"
    (p / "src" / "bewerbungs_assistent").mkdir(parents=True)
    (p / "src" / "bewerbungs_assistent" / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    return p


SERVER = '''
import http.server, json, signal, sys
port, modus, version = int(sys.argv[1]), sys.argv[2], sys.argv[3]
for arg in sys.argv[4:]:
    if arg == "ignoriere_term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    elif arg.startswith("marke="):
        def _term(*a, _m=arg[6:]):
            open(_m, "w").write("ok")
            sys.exit(0)
        signal.signal(signal.SIGTERM, _term)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/health" and modus == "pbp":
            body = json.dumps({"status": "ok", "pbp_version": version, "python_version": "3.12"}).encode()
        else:
            body = b"<html>ein fremdes Programm</html>"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass
http.server.HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


def _server_datei(tmp_path) -> Path:
    # Der Dateiname gleicht dem echten Dashboard: so erkennt ihn auch die Prozesssuche des Installers.
    ordner = tmp_path / "alt"
    ordner.mkdir(exist_ok=True)
    datei = ordner / "start_dashboard.py"
    datei.write_text(SERVER, encoding="utf-8")
    return datei


def _bereit(port: int, timeout=20):
    ende = time.time() + timeout
    while time.time() < ende:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


@pytest.mark.parametrize("name", list(UNIX_DATEIEN))
def test_1149_6_das_urteil_unterscheidet_neu_alt_und_nichts(bash, tmp_path, name):
    projekt = _projekt(tmp_path)
    skript = (f"set -e\ninfo() {{ echo \"INFO: $*\"; }}\nPROJECT_DIR='{projekt.as_posix()}'\n" + _funktionen(name)
              + '\necho "NEU=$(dashboard_urteil "9.9.9")"\necho "ALT=$(dashboard_urteil "9.8.0")"\n'
                'echo "KEINS=$(dashboard_urteil "")"\necho "FASSUNG=$NEUE_FASSUNG"\n')
    code, aus = _bash_lauf(bash, skript)
    assert code == 0, aus
    assert "NEU=ok" in aus and "ALT=alt" in aus and "KEINS=keins" in aus and "FASSUNG=9.9.9" in aus, aus


@pytest.mark.parametrize("modus,erwartet", [("pbp", "[9.9.9]"), ("fremd", "[]")])
def test_1149_4_ein_fremdes_programm_mit_http_200_gilt_nicht_als_pbp(bash, tmp_path, modus, erwartet):
    projekt = _projekt(tmp_path)
    port = _frei()
    server = subprocess.Popen([sys.executable, str(_server_datei(tmp_path)), str(port), modus, "9.9.9"], creationflags=OHNE_FENSTER)
    try:
        assert _bereit(port), "der Probe-Server startet nicht"
        skript = (f"set -e\ninfo() {{ echo \"INFO: $*\"; }}\nPROJECT_DIR='{projekt.as_posix()}'\nexport BA_DASHBOARD_PORT={port}\n"
                  + _funktionen("install.sh") + '\necho "STAND=[$(dashboard_stand)]"\n')
        code, aus = _bash_lauf(bash, skript)
    finally:
        server.kill()
        server.wait(timeout=30)
    assert f"STAND={erwartet}" in aus, aus


def test_1149_4_wo_nichts_antwortet_ist_der_stand_leer(bash, tmp_path):
    projekt = _projekt(tmp_path)
    skript = (f"set -e\ninfo() {{ echo \"INFO: $*\"; }}\nPROJECT_DIR='{projekt.as_posix()}'\nexport BA_DASHBOARD_PORT={_frei()}\n"
              + _funktionen("install.sh") + '\necho "STAND=[$(dashboard_stand)]"\n')
    code, aus = _bash_lauf(bash, skript)
    assert code == 0 and "STAND=[]" in aus, aus


def _beenden_skript(tmp_path, projekt, port, term_ignorieren=False, marke=None) -> str:
    server = _server_datei(tmp_path)
    zusatz = ' ignoriere_term' if term_ignorieren else (f' marke={marke.as_posix()}' if marke else '')
    return (f"set -e\ninfo() {{ echo \"INFO: $*\"; }}\nPROJECT_DIR='{projekt.as_posix()}'\nexport BA_DASHBOARD_PORT={port}\n"
            + _funktionen("install.sh") +
            f'\nPIDFILE="{(tmp_path / "pid.txt").as_posix()}"\n'
            f'"{Path(sys.executable).as_posix()}" "{server.as_posix()}" {port} pbp 0.9.0{zusatz} &\n'
            'echo $! > "$PIDFILE"\n'
            # Die Suche nach dem Prozess ist hier ersetzt (kein pgrep unter Windows); die Beendigung selbst ist die echte.
            'dashboard_pids() { for p in $(cat "$PIDFILE"); do if kill -0 "$p" 2>/dev/null; then echo "$p"; fi; done; return 0; }\n'
            'i=0; while [ -z "$(dashboard_stand)" ] && [ "$i" -lt 100 ]; do sleep 0.2; i=$((i+1)); done\n'
            'echo "VORHER=[$(dashboard_stand)]"\n'
            'alte_dashboards_beenden\n'
            'if [ -z "$(dashboard_pids)" ]; then echo PROZESS_WEG; else echo PROZESS_DA; fi\n'
            'echo "NACHHER=[$(dashboard_stand)]"\n')


def test_1149_6_ein_laufendes_altes_dashboard_wird_beendet(bash, tmp_path):
    projekt = _projekt(tmp_path)
    code, aus = _bash_lauf(bash, _beenden_skript(tmp_path, projekt, _frei()), timeout=180)
    assert code == 0, aus
    assert "VORHER=[0.9.0]" in aus, "die alte Fassung antwortete gar nicht erst"
    assert "PROZESS_WEG" in aus and "NACHHER=[]" in aus, aus
    assert "wird beendet" in aus, "der Mensch erfaehrt, dass ein laufendes Dashboard beendet wird"


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM-Semantik gibt es nur unter Unix")
def test_1149_6_zuerst_wird_hoeflich_beendet(bash, tmp_path):
    """Ein Dashboard bekommt erst SIGTERM und die Zeit, sauber zu enden (offene Datenbank), nicht gleich SIGKILL."""
    projekt = _projekt(tmp_path)
    marke = tmp_path / "sauber.txt"
    code, aus = _bash_lauf(bash, _beenden_skript(tmp_path, projekt, _frei(), marke=marke), timeout=180)
    assert "PROZESS_WEG" in aus, aus
    assert marke.exists(), "der Prozess bekam kein SIGTERM, sondern wurde gleich hart beendet"


@pytest.mark.parametrize("name", list(UNIX_DATEIEN))
def test_1149_6_das_alte_dashboard_wird_vor_dem_neuen_start_beendet_und_der_check_fragt_pbp(name):
    """Die Tests rufen die Funktionen selbst; dass der Installer sie in dieser Reihenfolge benutzt, sagen nur diese Zeilen."""
    text = UNIX_DATEIEN[name].read_text(encoding="utf-8")
    ende = text.index("# --- dashboard-funktionen Ende")
    aufruf = text.index("\nalte_dashboards_beenden\n", ende)
    start = text.index("nohup ", ende)
    assert aufruf < start, "erst das alte beenden, dann das neue starten"
    assert 'DASH_STAND="$(dashboard_stand)"' in text[ende:], "der Check fragt /api/health"
    assert "http://localhost:8200/ -o /dev/null" not in text, "ein bloesses HTTP 200 auf / zaehlt nicht mehr als laeuft"


@pytest.mark.parametrize("name", list(UNIX_DATEIEN))
def test_1149_6_die_schlussmeldung_unterscheidet_drei_ausgaenge(name):
    text = UNIX_DATEIEN[name].read_text(encoding="utf-8")
    schluss = text[text.index('DASH_URTEIL="$(dashboard_urteil'):]
    assert 'if [ "$DASH_URTEIL" = "ok" ]' in schluss
    assert 'elif [ "$DASH_URTEIL" = "alt" ]' in schluss and "Claude Desktop komplett beenden" in schluss
    assert "antwortet nicht nach 30 Sekunden" in schluss
    assert "$NEUE_FASSUNG" in schluss and "$DASH_STAND" in schluss, "die Meldung nennt beide Fassungen"


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM-Semantik gibt es nur unter Unix")
def test_1149_6_ein_dashboard_das_term_ignoriert_wird_hart_beendet(bash, tmp_path):
    projekt = _projekt(tmp_path)
    code, aus = _bash_lauf(bash, _beenden_skript(tmp_path, projekt, _frei(), term_ignorieren=True), timeout=180)
    assert "PROZESS_WEG" in aus and "NACHHER=[]" in aus, aus


def test_1149_6_ohne_laufendes_dashboard_wird_nichts_beendet_und_nichts_gemeldet(bash, tmp_path):
    projekt = _projekt(tmp_path)
    skript = (f"set -e\ninfo() {{ echo \"INFO: $*\"; }}\nPROJECT_DIR='{projekt.as_posix()}'\n" + _funktionen("install.sh")
              + '\ndashboard_pids() { return 0; }\nalte_dashboards_beenden\necho FERTIG\n')
    code, aus = _bash_lauf(bash, skript)
    assert code == 0 and "FERTIG" in aus and "beendet" not in aus, aus


def test_1149_6_die_prozesssuche_trifft_pbp_und_sonst_nichts(bash, tmp_path):
    """Die Suche nennt nur `python ... start_dashboard.py` - nie den MCP-Prozess, nie einen Editor mit dieser Datei."""
    projekt = _projekt(tmp_path)
    ja = ["/home/x/pbp/.venv/bin/python start_dashboard.py", "/home/x/pbp/.venv/bin/python /home/x/pbp/start_dashboard.py",
          "python3.12 start_dashboard.py",
          "/Library/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python /Users/x/PBP/start_dashboard.py"]
    nein = ["/home/x/pbp/.venv/bin/python -m bewerbungs_assistent", "vim /home/x/pbp/start_dashboard.py", "less start_dashboard.py",
            "vim /home/x/python/pbp/start_dashboard.py", "grep -r start_dashboard.py .", "/usr/bin/python3 anderes_skript.py"]
    proben = "\n".join(ja + nein)
    skript = (f"set -e\ninfo() {{ echo \"INFO: $*\"; }}\nPROJECT_DIR='{projekt.as_posix()}'\n" + _funktionen("install.sh")
              + "\nwhile IFS= read -r z; do if printf '%s\\n' \"$z\" | grep -E -i -q \"$DASH_MUSTER\"; then echo \"JA|$z\"; else echo \"NEIN|$z\"; fi; done <<'PROBEN'\n"
              + proben + "\nPROBEN\n")
    code, aus = _bash_lauf(bash, skript)
    assert code == 0, aus
    for z in ja:
        assert f"JA|{z}" in aus, f"muss getroffen werden: {z}\n{aus}"
    for z in nein:
        assert f"NEIN|{z}" in aus, f"darf nicht getroffen werden: {z}\n{aus}"


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("pgrep"), reason="braucht ein echtes pgrep")
def test_1149_6_pgrep_findet_ein_echtes_dashboard(bash, tmp_path):
    projekt = _projekt(tmp_path)
    port = _frei()
    server = subprocess.Popen([sys.executable, str(_server_datei(tmp_path)), str(port), "pbp", "0.9.0"])
    try:
        assert _bereit(port)
        skript = (f"set -e\ninfo() {{ echo \"INFO: $*\"; }}\nPROJECT_DIR='{projekt.as_posix()}'\n" + _funktionen("install.sh")
                  + '\necho "PIDS=[$(dashboard_pids | tr "\\n" " ")]"\n')
        code, aus = _bash_lauf(bash, skript)
    finally:
        server.kill()
        server.wait(timeout=30)
    assert f"{server.pid}" in aus, aus


# ══ Punkt 9d: deinstallieren.sh unterscheidet "nicht lesbar" von "kein Eintrag" ════════════════

def _deinstallieren(bash, tmp_path, inhalt: bytes | None):
    home = tmp_path / "home"
    if sys.platform == "darwin":
        config = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        config = home / ".config" / "Claude" / "claude_desktop_config.json"
    config.parent.mkdir(parents=True)
    if inhalt is not None:
        config.write_bytes(inhalt)
    assert str(tmp_path) in str(home), "QA-Isolation: nie das echte Heimatverzeichnis"
    skript = (f'python3() {{ "{Path(sys.executable).as_posix()}" "$@"; }}\nexport -f python3\n'
              f'export HOME="{home.as_posix()}"\nprintf "j\\nn\\nn\\n" | bash "{(ROOT / "installer" / "deinstallieren.sh").as_posix()}"\n')
    code, aus = _bash_lauf(bash, skript)
    return config, code, aus


def test_1149_9d_kaputtes_json_wird_nicht_als_kein_eintrag_gemeldet(bash, tmp_path):
    roh = b'{"mcpServers": {"filesystem": '
    config, code, aus = _deinstallieren(bash, tmp_path, roh)
    assert "nicht lesbar" in aus and "von Hand" in aus, aus
    assert "war nicht vorhanden" not in aus, "vorher: die Falschmeldung, und der Eintrag blieb stehen"
    assert config.read_bytes() == roh, "eine unlesbare Datei wird nicht angefasst"


def test_1149_9d_der_eintrag_wird_entfernt_der_rest_bleibt_und_eine_sicherung_entsteht(bash, tmp_path):
    import json
    roh = json.dumps({"mcpServers": {"filesystem": {"command": "npx"}, "bewerbungs-assistent": {"command": "python"}},
                      "preferences": {"theme": "dark"}}, indent=2).encode("utf-8")
    config, code, aus = _deinstallieren(bash, tmp_path, roh)
    assert "MCP-Eintrag entfernt" in aus, aus
    neu = json.loads(config.read_text(encoding="utf-8"))
    assert set(neu["mcpServers"]) == {"filesystem"} and neu["preferences"] == {"theme": "dark"}
    assert Path(str(config) + ".pbp-backup").read_bytes() == roh


def test_1149_9d_ohne_eintrag_bleibt_die_datei_unveraendert(bash, tmp_path):
    roh = b'{"mcpServers": {"filesystem": {"command": "npx"}}}'
    config, code, aus = _deinstallieren(bash, tmp_path, roh)
    assert "war nicht vorhanden" in aus and "nicht lesbar" not in aus, aus
    assert config.read_bytes() == roh and not Path(str(config) + ".pbp-backup").exists()


def test_1149_9d_ohne_konfiguration_steht_das_da(bash, tmp_path):
    config, code, aus = _deinstallieren(bash, tmp_path, None)
    assert "Claude-Config nicht gefunden" in aus, aus


# ══ Punkt 12: Zahlen und Texte ════════════════════════════════════════════════════════════════

def _init_version() -> str:
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', (ROOT / "src" / "bewerbungs_assistent" / "__init__.py").read_text(encoding="utf-8"), re.M)
    return m.group(1)


def test_1149_12_server_json_steht_auf_der_version_des_release():
    import json
    daten = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert daten["version"] == _init_version()
    assert all(p["version"] == _init_version() for p in daten["packages"])


def test_1149_12_eine_sperrdatei_steht_auf_dem_stand_oder_fehlt():
    """Eine uv.lock, die python-jobspy und pypdfium2 nicht kennt, ist schlimmer als keine."""
    lock = ROOT / "uv.lock"
    if not lock.exists():
        return
    m = re.search(r'name = "bewerbungs-assistent"\s*\nversion = "([^"]+)"', lock.read_text(encoding="utf-8"))
    assert m and m.group(1) == _init_version(), "uv.lock neu erzeugen (uv lock) oder entfernen"


@pytest.fixture
def release_check(tmp_path):
    """Ein Mini-Repo in tmp_path (nie das echte): zeigt, ob das Tor server.json & Co. wirklich liest. Das Tor selbst laeuft im
    Unterprozess (sein Import stellt sys.stdout um)."""
    (tmp_path / "src" / "bewerbungs_assistent").mkdir(parents=True)
    (tmp_path / "src" / "bewerbungs_assistent" / "__init__.py").write_text('__version__ = "2.0.0"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "2.0.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [2.0.0] - 2026-01-01\n", encoding="utf-8")
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text('{\n  "name": "x",\n  "version": "2.0.0"\n}\n', encoding="utf-8")
    (tmp_path / "server.json").write_text('{\n  "version": "2.0.0",\n  "packages": [{"version": "2.0.0"}]\n}\n', encoding="utf-8")
    return tmp_path


def _tor(wurzel, fix=False):
    """(Version, Fehlerliste) von release_check.check_versions() ueber einem Mini-Repo."""
    import json
    code = ("import json, sys, pathlib, release_check as r\n"
            "r.PROJECT_DIR = pathlib.Path(sys.argv[1])\n"
            "v = r.check_versions(fix=(sys.argv[2] == '1'))\n"
            "print('@@' + json.dumps({'version': v, 'fehler': r.ERRORS}))\n")
    r = subprocess.run([sys.executable, "-c", code, str(wurzel), "1" if fix else "0"], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120, creationflags=OHNE_FENSTER)
    zeile = next((z for z in r.stdout.splitlines() if z.startswith("@@")), None)
    assert zeile, r.stdout + r.stderr
    daten = json.loads(zeile[2:])
    return daten["version"], daten["fehler"]


def test_1149_12_das_tor_nimmt_ein_stimmiges_repo_an(release_check):
    version, fehler = _tor(release_check)
    assert version == "2.0.0" and fehler == []


@pytest.mark.parametrize("datei,inhalt,name", [
    ("server.json", '{\n  "version": "1.7.0",\n  "packages": [{"version": "2.0.0"}]\n}\n', "server.json"),
    ("server.json", '{\n  "version": "2.0.0",\n  "packages": [{"version": "1.7.0"}]\n}\n', "server.json (packages[1])"),
    ("frontend/package.json", '{\n  "version": "1.7.0"\n}\n', "frontend/package.json"),
])
def test_1149_12_das_tor_meldet_eine_veraltete_version_in_server_json_und_package_json(release_check, datei, inhalt, name):
    (release_check / datei).write_text(inhalt, encoding="utf-8")
    version, fehler = _tor(release_check)
    assert any(name in e for e in fehler), fehler


def test_1149_12_das_tor_meldet_eine_veraltete_sperrdatei(release_check):
    wurzel = release_check
    (wurzel / "uv.lock").write_text('[[package]]\nname = "bewerbungs-assistent"\nversion = "1.5.7"\n', encoding="utf-8")
    version, fehler = _tor(wurzel)
    assert any("uv.lock" in e and "1.5.7" in e for e in fehler), fehler


def test_1149_12_fix_zieht_server_json_und_package_json_nach(release_check):
    wurzel = release_check
    (wurzel / "server.json").write_text('{\n  "version": "1.7.0",\n  "packages": [{"version": "1.7.0"}]\n}\n', encoding="utf-8")
    (wurzel / "frontend" / "package.json").write_text('{\n  "name": "x",\n  "version": "1.7.0"\n}\n', encoding="utf-8")
    version, fehler = _tor(wurzel, fix=True)
    assert fehler == [], fehler
    assert (wurzel / "server.json").read_text(encoding="utf-8").count('"2.0.0"') == 2
    assert '"version": "2.0.0"' in (wurzel / "frontend" / "package.json").read_text(encoding="utf-8")


def test_1149_12_install_ps1_ist_ein_ehrlicher_hinweis_und_rein_ascii():
    """BOM-frei lesbar unter Windows PowerShell 5.1 (kein Mojibake), kein pip, endet mit Fehlercode."""
    roh = (ROOT / "installer" / "install.ps1").read_bytes()
    roh.decode("ascii")
    text = roh.decode("ascii")
    assert "INSTALLIEREN.bat" in text and "exit 1" in text
    code = "\n".join(z for z in text.split("\n") if not z.lstrip().startswith("#")).lower()
    assert "pip" not in code and "venv" not in code, "kein Installationsschritt mehr"


def test_1149_12_liesmich_verspricht_unter_macos_nicht_mehr_nichts_zu_installieren():
    roh = (ROOT / "docs" / "LIESMICH.txt").read_bytes().decode("utf-8-sig")
    assert "Du brauchst NICHTS selber installieren" not in roh
    assert "Python 3.11" in roh
    assert "Weitere Informationen" in roh and "Ausrufezeichen" in roh


def test_1149_12_readme_nennt_die_windows_warnung_und_das_ausrufezeichen():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    abschnitt = text[text.index("### Windows (Empfohlen)"):text.index("### macOS")]
    assert "Weitere Informationen" in abschnitt and "Ausrufezeichen" in abschnitt


@pytest.mark.parametrize("label", [":err_pip", ":err_packages"])
def test_1149_12_die_fehlertexte_sagen_was_als_naechstes_zu_tun_ist(label):
    text = _text("INSTALLIEREN.bat")
    a = text.index("\n" + label + "\n")
    stueck = text[a:text.index("exit /b 1", a)]
    assert "Internetverbindung" in stueck and "nochmal starten" in stueck and "Daten bleiben erhalten" in stueck
    assert "%LOGFILE%" in stueck, "das Log wird weiter genannt"
