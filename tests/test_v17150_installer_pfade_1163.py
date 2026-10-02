"""Installer-Helfer und Selbsttest: Pfade mit Zeichen ausserhalb der ANSI-Zeichentabelle (#1163, ab v1.7.150).

INSTALLIEREN.bat ruft die Hilfsprogramme mit `>> "%LOGFILE%" 2>&1` auf: die Ausgabe geht in eine DATEI, und dort gilt die
Zeichentabelle des Rechners (auf deutschem Windows cp1252). Ein Benutzername mit einem Zeichen ausserhalb (ł, ş, ř, griechisch,
kyrillisch) liess `_setup_claude.py` (Claude-Konfiguration), `_sicherung_vor_update.py` (Sicherung vor dem Update) und
`_selftest.py` abstuerzen -- ohne dass an PBP selbst etwas falsch gewesen waere. Auf Rechnern mit einfachem Namen faellt das nie auf.

Deshalb erzwingen die Tests die enge Zeichentabelle (`PYTHONIOENCODING=cp1252`) und laufen in einem Ordner mit solchen Zeichen:
sonst sind sie auf einem UTF-8-Rechner gruen und auf dem Zielrechner rot (L44).

Dieselbe Datei steht in der 1.7- und der 1.8-Linie. Die Helfer der 1.8-Linie (`_programm_einrichten.py`, `_installer_aufraeumen.py`)
und der Selbsttest des Auto-Updates stehen in `test_v18_auto_update_pfade.py`.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent

#: Orte und Buchstaben, die in keiner westeuropaeischen Zeichentabelle (cp1252/cp850) stehen -- bewusst keine Personennamen.
FREMDER_NAME = "Łódź Şişli (Büro) Ελλάδα"


def _env(basis: Path, **zusatz) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONUTF8", "PYTHONPATH", "PBP_APP_DIR", "PBP_FASSUNG", "BA_DATA_DIR")}
    # Claude-Konfiguration: Windows liest APPDATA/LOCALAPPDATA, die anderen Systeme das Heimatverzeichnis -- alles unter tmp_path
    env.update(PYTHONIOENCODING="cp1252", APPDATA=str(basis / "AppData" / "Roaming"),
               LOCALAPPDATA=str(basis / "AppData" / "Local"), HOME=str(basis), USERPROFILE=str(basis),
               PBP_GEOCODING="0", PBP_BERUFE_LOOKUP="0", PBP_NETZ_PRUEFUNG="0", PYTHONDONTWRITEBYTECODE="1")
    env.update(zusatz)
    return env


@pytest.fixture
def installer(tmp_path):
    """Ein entpackter Installer in einem Ordner mit fremden Zeichen; Claude-Konfiguration und Datenordner liegen daneben (isoliert)."""
    basis = tmp_path / FREMDER_NAME
    ordner = basis / "PBP-entpackt"
    ordner.mkdir(parents=True)
    for name in ("_setup_claude.py", "_sicherung_vor_update.py"):
        shutil.copy2(WURZEL / name, ordner / name)
    (basis / "AppData" / "Roaming").mkdir(parents=True)
    (basis / "AppData" / "Local").mkdir(parents=True)

    def lauf(*args):
        return subprocess.run([sys.executable, *args], cwd=str(ordner), env=_env(basis), capture_output=True, timeout=120,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    return type("Installer", (), {"basis": basis, "ordner": ordner, "lauf": staticmethod(lauf)})


def _ausgabe(r) -> str:
    return r.stdout.decode("cp1252", "replace")


def _kein_absturz(r):
    fehler = r.stderr.decode("cp1252", "replace")
    assert "UnicodeEncodeError" not in fehler, fehler[-800:]


def test_die_claude_konfiguration_wird_auch_bei_fremden_zeichen_im_pfad_geschrieben(installer):
    r = installer.lauf("_setup_claude.py")
    _kein_absturz(r)
    assert r.returncode == 0, _ausgabe(r)[-600:] + r.stderr.decode("cp1252", "replace")[-600:]
    konfigurationen = list(installer.basis.rglob("claude_desktop_config.json"))
    assert konfigurationen, "die Konfiguration steht unter dem Benutzerordner des Tests (nicht in der echten)"
    assert all(str(installer.basis) in str(k) for k in konfigurationen)
    assert _ausgabe(r).strip().splitlines()[-1] == "OK"


def test_die_sicherung_vor_dem_update_klappt_auch_bei_fremden_zeichen_im_pfad(installer):
    """Die Sicherung ist der Schritt, vor dem der Installer warnt, wenn er nicht gelingt: schon die Erfolgsmeldung mit dem Zielpfad musste halten."""
    import sqlite3

    db = installer.basis / "Daten" / "pbp.db"
    db.parent.mkdir()
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE settings (key TEXT, value TEXT)")
        con.execute("INSERT INTO settings VALUES ('a', 'b')")
    sicherungen = installer.basis / "Daten" / "backups"
    r = installer.lauf("_sicherung_vor_update.py", str(db), str(sicherungen))
    _kein_absturz(r)
    assert r.returncode == 0, _ausgabe(r)[-600:]
    assert _ausgabe(r).startswith("OK ") and list(sicherungen.glob("*"))


def test_die_fehlermeldung_der_sicherung_mit_fremden_zeichen_im_pfad_bleibt_lesbar(installer):
    """Der Abbruchgrund steht auf der Ausgabe -- er ist der einzige Hinweis, den jemand in der Protokolldatei findet."""
    r = installer.lauf("_sicherung_vor_update.py", str(installer.basis / "fehlt.db"), str(installer.basis / "Sicherungen"))
    _kein_absturz(r)
    assert r.returncode == 2 and "FEHLER" in _ausgabe(r)


def test_der_echte_selbsttest_besteht_in_einem_pfad_mit_fremden_zeichen_auch_bei_enger_zeichentabelle(tmp_path):
    """Die Datei, die der Installer wirklich ausfuehrt. `PYTHONIOENCODING=cp1252` erzwingt die enge Tabelle (so wie ein deutscher
    Windows-Rechner sie fuer umgeleitete Ausgabe hat): ohne die Absicherung in `_selftest.py` bricht schon der erste `print` ab."""
    ziel = tmp_path / FREMDER_NAME / "fassung"
    ziel.mkdir(parents=True)
    shutil.copytree(WURZEL / "src", ziel / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(WURZEL / "_selftest.py", ziel / "_selftest.py")
    env = _env(tmp_path / FREMDER_NAME, BA_DATA_DIR=str(tmp_path / "daten"))
    r = subprocess.run([sys.executable, str(ziel / "_selftest.py")], capture_output=True, env=env, cwd=str(ziel), timeout=240,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    aus = r.stdout.decode("cp1252", "replace")
    assert r.returncode == 0, aus[-800:] + "\n" + r.stderr.decode("cp1252", "replace")[-1500:]
    assert aus.strip().splitlines()[-1] == "OK"
    assert "Pfad:" in aus and "\\u0141" in aus and "\\u017a" in aus, "der Pfad steht in der Ausgabe, das »Ł« als Ersatzschreibung"
