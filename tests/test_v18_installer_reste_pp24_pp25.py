"""Testlauf 11.10.2026 (Werkstatt-PC): zwei Reste, die der Installer hinterliess.

PP24 -- Der Aufraeum-Helfer (`_installer_aufraeumen.py`) starb beim ersten Versuch. Haelt ein Fenster (Explorer, Konsole)
den entpackten Ordner, wirft das zweite `os.rmdir` aus der Rueckruffunktion von `shutil.rmtree` heraus einen
`PermissionError` (WinError 32). Er lief bis in den Prozess hinein; vorgesehen sind 200 Versuche im Abstand von 3 s. Es
blieben ein leerer Ordner `PBP-...` und die Kopie des Helfers im Temp-Ordner. Die vorhandenen Tests ersetzten
`_loeschen_versuchen` ganz -- genau die Stelle, an der es krachte, lief nie. Auf dem Entwicklungsrechner fiel es nicht auf:
dort loescht Windows den gehaltenen Ordner trotzdem.

PP25 -- `get-pip.py` entpackt sich nach `%TEMP%\\tmpXXXX\\pip.zip` und kann das unter Windows nicht selbst loeschen (die
Datei ist noch geladen): 1,7 MB blieben nach jeder Installation liegen, die pip nachlaedt.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import _installer_aufraeumen as ia  # noqa: E402

BAT = WURZEL / "INSTALLIEREN.bat"
nur_windows = pytest.mark.skipif(os.name != "nt", reason="braucht Windows (cmd.exe)")


def _ordner(basis: Path) -> Path:
    (basis / "src" / "bewerbungs_assistent").mkdir(parents=True)
    (basis / "src" / "bewerbungs_assistent" / "__init__.py").write_text("x", encoding="utf-8")
    (basis / "INSTALLIEREN.bat").write_text("@echo off", encoding="utf-8")
    (basis / "_programm_einrichten.py").write_text("pass", encoding="utf-8")
    return basis


# ══ PP24 ═════════════════════════════════════════════════════════════════════════════════════════════════════════

def test_pp24_ein_gehaltener_ordner_beendet_den_helfer_nicht(tmp_path, monkeypatch):
    """Der echte Fehlerweg: `os.rmdir` scheitert am Ordner selbst -- erst im Durchgang, dann noch einmal in der Rueckruffunktion."""
    basis = _ordner(tmp_path / "PBP-1.8.0")
    echt = os.rmdir
    versuche = {"n": 0}

    def rmdir(pfad, *a, **kw):
        if os.path.normcase(str(pfad)) == os.path.normcase(str(basis)):
            versuche["n"] += 1
            if versuche["n"] <= 2:      # Durchgang 1: der Aufruf und der Wiederholungsversuch der Rueckruffunktion
                raise PermissionError(13, "Der Prozess kann nicht auf die Datei zugreifen, da sie von einem anderen Prozess verwendet wird", str(pfad))
        return echt(pfad, *a, **kw)

    monkeypatch.setattr(os, "rmdir", rmdir)
    # Vorher: PermissionError bis hierher durchgereicht, der Ordner bleibt, der Helfer ist tot.
    assert ia.lauf(str(basis), [], versuche=5, pause=0) is True
    assert versuche["n"] >= 3, "es gab einen zweiten Durchgang"
    assert not basis.exists()


def test_pp24_ist_der_ordner_dauerhaft_gehalten_gibt_der_helfer_ohne_absturz_auf(tmp_path, monkeypatch):
    basis = _ordner(tmp_path / "PBP-1.8.0")
    echt = os.rmdir

    def rmdir(pfad, *a, **kw):
        if os.path.normcase(str(pfad)) == os.path.normcase(str(basis)):
            raise PermissionError(13, "gehalten", str(pfad))
        return echt(pfad, *a, **kw)

    monkeypatch.setattr(os, "rmdir", rmdir)
    assert ia.lauf(str(basis), [], versuche=3, pause=0) is False, "kein Absturz: der Aufrufer raeumt danach seine Kopie weg"
    assert basis.exists()


def test_pp24_die_rueckruffunktion_wirft_nie(tmp_path):
    def immer_gehalten(pfad):
        raise PermissionError(13, "gehalten", str(pfad))

    datei = tmp_path / "x.txt"
    datei.write_text("x")
    ia._freigeben(immer_gehalten, str(datei), None)           # kein Wurf
    ia._freigeben(immer_gehalten, str(tmp_path / "gibt-es-nicht"), None)   # auch chmod darf scheitern


def test_pp24_die_rueckruffunktion_nimmt_einem_ordner_nie_das_lesen(tmp_path, monkeypatch):
    """Unter POSIX hiesse `chmod(S_IWRITE)` bei einem Ordner 0o200: nicht mehr lesbar, der naechste Durchgang scheitert am Oeffnen.
    (Fund des unabhaengigen Pruefers: die Tests liefen unter Linux als Nicht-root rot.)"""
    import stat as _stat
    gesetzt = []
    monkeypatch.setattr(ia.os, "chmod", lambda p, mode: gesetzt.append((str(p), mode)))
    ordner = tmp_path / "ordner"
    ordner.mkdir()
    datei = tmp_path / "datei.txt"
    datei.write_text("x")
    ia._freigeben(lambda p: None, str(ordner), None)
    ia._freigeben(lambda p: None, str(datei), None)
    (pfad_ordner, modus_ordner), (pfad_datei, modus_datei) = gesetzt
    assert modus_ordner & _stat.S_IRUSR and modus_ordner & _stat.S_IWUSR and modus_ordner & _stat.S_IXUSR
    assert modus_datei & _stat.S_IWRITE and modus_datei & _stat.S_IREAD


def test_pp24_auch_ein_aufruf_ohne_argumente_der_rueckruffunktion_beendet_nichts(tmp_path):
    """`shutil.rmtree` ruft die Rueckruffunktion auch mit `os.open` auf (zweiter Durchgang, Ordner nicht lesbar): `fn(pfad)` ist dann
    ein TypeError, kein OSError."""
    ia._freigeben(os.open, str(tmp_path), None)


def test_pp24_ein_durchgang_wirft_nie(tmp_path, monkeypatch):
    basis = _ordner(tmp_path / "PBP-1.8.0")

    def kaputt(*a, **kw):
        raise PermissionError(13, "gehalten")

    monkeypatch.setattr(ia.shutil, "rmtree", kaputt)
    assert ia._loeschen_versuchen(str(basis), []) is False
    assert basis.exists()


def test_pp24_die_zips_gehen_auch_wenn_der_ordner_noch_gehalten_wird(tmp_path, monkeypatch):
    basis = _ordner(tmp_path / "PBP-1.8.0")
    z = tmp_path / "PBP-1.8.0.zip"
    z.write_bytes(b"x")
    monkeypatch.setattr(ia.shutil, "rmtree", lambda *a, **kw: (_ for _ in ()).throw(PermissionError(13, "gehalten")))
    assert ia._loeschen_versuchen(str(basis), [str(z)]) is False
    assert not z.exists() and basis.exists()


# ══ PP25 ═════════════════════════════════════════════════════════════════════════════════════════════════════════

def _bat() -> str:
    return BAT.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def _pip_unterprogramm() -> str:
    text = _bat()
    start = text.index("\n:pip_beschaffen\n") + 1      # die Sprungmarke am Zeilenanfang, nicht `call :pip_beschaffen`
    ende = text.index("exit /b !PIP_RC!\n", start) + len("exit /b !PIP_RC!\n")
    return text[start:ende]


def test_pp25_get_pip_laeuft_nur_noch_ueber_das_unterprogramm():
    text = _bat()
    aufrufe = [z for z in text.splitlines() if "get-pip" not in z.lower() and 'GETPIP_PATH' in z and '"%PYTHON%"' in z]
    assert len(aufrufe) == 1, aufrufe
    assert text.count("call :pip_beschaffen") == 2, "beim ersten Einrichten und in :fix_pip"
    u = _pip_unterprogramm()
    assert u.index('set "TEMP=') < u.index('"%PYTHON%" "%GETPIP_PATH%"') < u.index('set "TEMP=!PIP_TEMP_VORHER!"')
    assert u.index('set "TMP=') < u.index('"%PYTHON%"') < u.index('set "TMP=!PIP_TMP_VORHER!"')
    assert u.rindex('rmdir /s /q "!PIP_TMP!"') > u.index('set "TMP=!PIP_TMP_VORHER!"'), "aufgeraeumt wird nach dem Lauf"
    assert "exit /b !PIP_RC!" in u and 'set "PIP_RC=!errorlevel!"' in u


def _lauf_pip(tmp_path: Path, rc: int):
    """Das ECHTE Unterprogramm mit einem Stand-in fuer get-pip.py (legt wie das Original `<TEMP>\\tmpXXXX\\pip.zip` an)."""
    py_ordner = tmp_path / "python"
    py_ordner.mkdir()
    temp = tmp_path / "Temp"
    temp.mkdir()
    log = tmp_path / "protokoll.txt"
    getpip = tmp_path / "get-pip.py"
    getpip.write_text(
        "import os, sys, tempfile\n"
        "d = tempfile.mkdtemp()\n"
        "open(os.path.join(d, 'pip.zip'), 'wb').write(b'x' * 100)\n"
        "print('TMPDIR=' + d)\n"
        f"sys.exit({rc})\n", encoding="utf-8")
    kopf = ["@echo off", "setlocal EnableDelayedExpansion", f'set "PYTHON={sys.executable}"', f'set "PYTHON_DIR={py_ordner}"',
            f'set "GETPIP_PATH={getpip}"', f'set "LOGFILE={log}"', f'set "TEMP={temp}"', f'set "TMP={temp}"',
            "call :pip_beschaffen", "echo RC=!errorlevel!", "echo TEMP_DANACH=!TEMP!", "echo TMP_DANACH=!TMP!", "exit /b 0", ""]
    bat = tmp_path / "pip.bat"
    bat.write_bytes(("\r\n".join(kopf) + _pip_unterprogramm().replace("\n", "\r\n")).encode("cp850", errors="replace"))
    r = subprocess.run(["cmd.exe", "/c", str(bat)], capture_output=True, creationflags=0x08000000, timeout=120)
    ausgabe = (r.stdout + r.stderr).decode("cp850", errors="replace")
    protokoll = log.read_text(encoding="cp850", errors="replace") if log.exists() else ""
    return ausgabe, protokoll, temp, py_ordner


@nur_windows
def test_pp25_nichts_bleibt_im_temp_ordner_liegen_und_temp_ist_danach_wieder_wie_vorher(tmp_path):
    ausgabe, protokoll, temp, py_ordner = _lauf_pip(tmp_path, rc=0)
    assert "RC=0" in ausgabe, ausgabe
    assert f"TEMP_DANACH={temp}" in ausgabe and f"TMP_DANACH={temp}" in ausgabe, "die Umgebung ist danach wieder die alte"
    assert "pip-tmp" in protokoll, "get-pip hat wirklich im eigenen Ordner gearbeitet"
    assert list(temp.iterdir()) == [], "kein tmpXXXX im Temp-Ordner des Benutzers"
    assert not (py_ordner / "pip-tmp").exists(), "der eigene Ordner ist weg, bevor die Laufzeit kopiert wird"


@nur_windows
def test_pp25_ein_fehlschlag_von_get_pip_geht_unveraendert_nach_oben(tmp_path):
    ausgabe, _, temp, py_ordner = _lauf_pip(tmp_path, rc=3)
    assert "RC=3" in ausgabe, ausgabe
    assert list(temp.iterdir()) == [] and not (py_ordner / "pip-tmp").exists()
