"""Auto-Update (#1093): Pfade mit fremden Zeichen — der Programmordner liegt im Benutzerordner, und der heisst nicht immer »Max«.

Windows-Benutzernamen mit Umlauten, Leerzeichen, Klammern oder Buchstaben ausserhalb der westlichen Zeichentabelle (Polnisch,
Tuerkisch, Griechisch) gehoeren zum Alltag. Der Fassungsordner liegt darunter, und der Selbsttest druckt den Pfad. Jede Stelle,
die einen Unterprozess startet und dessen Ausgabe liest, muss damit zurechtkommen — unabhaengig davon, welche Zeichentabelle der
Rechner eingestellt hat.

Die Prozess-Ende-zu-Ende-Faelle (Start, Rueckfall, MCP-Server in einem Pfad mit Umlauten) stehen in `test_v18_auto_update_e2e.py`;
hier stehen die Stellen, die Ausgabe von Unterprozessen LESEN.
"""
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from bewerbungs_assistent.services.auto_update import abhaengigkeiten, installation  # noqa: E402
from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler  # noqa: E402

#: Buchstaben, die in keiner westeuropaeischen Zeichentabelle (cp1252/cp850) stehen, und ein paar, die in UTF-8 auf Bytes enden,
#: welche cp1252 nicht kennt (0x81, 0x8D, 0x8F, 0x90, 0x9D).
FREMDER_NAME = "Łódź Şişli (Büro) Ελλάδα"
BYTES_OHNE_CP1252 = "Á Í Ï Ð Ý"


def _selbsttest_ordner(tmp_path: Path, skript: str) -> Path:
    ordner = tmp_path / FREMDER_NAME / "versions" / "1.8.1"
    ordner.mkdir(parents=True)
    (ordner / "_selftest.py").write_text(textwrap.dedent(skript), encoding="utf-8")
    return ordner


# ══ Der Selbsttest vor dem Umschalten ═════════════════════════════════════════════════════

def test_der_selbsttest_liest_utf8_auch_wenn_die_zeichentabelle_des_rechners_eine_andere_ist(tmp_path):
    """Das Kind schreibt UTF-8-Bytes, die cp1252 nicht kennt; mit `text=True` kippte schon das Lesen den Selbsttest."""
    ordner = _selbsttest_ordner(tmp_path, f'''
        import sys
        sys.stdout.buffer.write("[TEST] Pfad: {FREMDER_NAME} {BYTES_OHNE_CP1252}\\n".encode("utf-8"))
        sys.stdout.buffer.write(b"OK\\n")
        sys.stdout.buffer.flush()
    ''')
    installation.selbsttest_starten(ordner)          # wirft nicht


def test_der_selbsttest_darf_den_pfad_drucken_auch_wenn_die_zeichentabelle_des_rechners_ihn_nicht_kennt(tmp_path):
    """`print` mit einem »Ł« scheitert, sobald die Standardausgabe eine Zeichentabelle ohne »Ł« hat (umgeleitet: die des Rechners)."""
    ordner = _selbsttest_ordner(tmp_path, f'''
        print("[TEST] Pfad: {FREMDER_NAME}")
        print("OK")
    ''')
    installation.selbsttest_starten(ordner)


def test_ein_selbsttest_der_fehlschlaegt_bleibt_ein_fehlschlag_auch_mit_fremden_zeichen_in_der_meldung(tmp_path):
    ordner = _selbsttest_ordner(tmp_path, f'''
        import sys
        print("[TEST] FEHLER: Pfad {FREMDER_NAME} nicht lesbar")
        sys.exit(1)
    ''')
    with pytest.raises(UpdateFehler) as e:
        installation.selbsttest_starten(ordner)
    assert "FEHLER" in str(e.value.detail)


def test_der_echte_selbsttest_besteht_in_einem_pfad_mit_fremden_zeichen_auch_bei_enger_zeichentabelle(tmp_path):
    """Die Datei, die ein Release wirklich mitbringt. `PYTHONIOENCODING=cp1252` erzwingt die enge Tabelle (so wie ein deutscher
    Windows-Rechner sie fuer umgeleitete Ausgabe hat): ohne die Absicherung in `_selftest.py` bricht schon der erste `print` ab."""
    ziel = tmp_path / FREMDER_NAME / "fassung"
    ziel.mkdir(parents=True)
    shutil.copytree(WURZEL / "src", ziel / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(WURZEL / "_selftest.py", ziel / "_selftest.py")
    daten = tmp_path / "daten"
    env = {k: v for k, v in os.environ.items() if k not in ("PBP_APP_DIR", "PBP_FASSUNG", "BA_DATA_DIR", "PYTHONPATH", "PYTHONUTF8")}
    env.update(PYTHONIOENCODING="cp1252", BA_DATA_DIR=str(daten), PBP_GEOCODING="0", PBP_BERUFE_LOOKUP="0",
               PBP_NETZ_PRUEFUNG="0", PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, str(ziel / "_selftest.py")], capture_output=True, env=env, cwd=str(ziel), timeout=240,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    aus = r.stdout.decode("cp1252", "replace")
    assert r.returncode == 0, aus[-800:] + "\n" + r.stderr.decode("cp1252", "replace")[-1500:]
    assert aus.strip().splitlines()[-1] == "OK"
    assert "Pfad:" in aus and "\\u0141" in aus and "\\u017a" in aus, "der Pfad steht in der Ausgabe, das »Ł« als Ersatzschreibung"


# ══ pip fuer neue Pakete ══════════════════════════════════════════════════════════════════

class _Aufzeichner:
    def __init__(self):
        self.kw = {}

    def __call__(self, befehl, **kw):
        self.kw = kw
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()


def test_pip_wird_mit_utf8_gestartet_und_gelesen(tmp_path):
    """pip nennt den Zielpfad in seiner Ausgabe. Gleiche Zusage wie beim Selbsttest: UTF-8 auf beiden Seiten."""
    ziel = tmp_path / FREMDER_NAME / "site"
    a = _Aufzeichner()
    abhaengigkeiten.bereitstellen(["httpx>=0.28"], ziel, runner=a, freier_platz=10 ** 12)
    assert a.kw["encoding"] == "utf-8" and a.kw["errors"] == "replace" and "text" not in a.kw
    assert a.kw["env"]["PYTHONIOENCODING"] == "utf-8"


# ══ Die Helfer des Installers ═════════════════════════════════════════════════════════════
#
# INSTALLIEREN.bat ruft sie mit `>> "%LOGFILE%" 2>&1` auf: die Ausgabe geht in eine DATEI, und dort gilt die Zeichentabelle des
# Rechners. Ein Benutzername mit »ł« oder »ş« im Pfad liess `_setup_claude.py` (Claude-Konfiguration) und `_sicherung_vor_update.py`
# (Sicherung vor dem Update) abstuerzen -- ohne dass irgendetwas an PBP selbst falsch gewesen waere.

HELFER = ("_setup_claude.py", "_sicherung_vor_update.py", "_programm_einrichten.py", "_installer_aufraeumen.py")


@pytest.fixture
def installer(tmp_path):
    """Ein entpackter Installer in einem Ordner mit fremden Zeichen; Claude-Konfiguration und Datenordner liegen daneben (isoliert)."""
    basis = tmp_path / FREMDER_NAME
    ordner = basis / "PBP-1.8.0"
    ordner.mkdir(parents=True)
    for name in HELFER:
        shutil.copy2(WURZEL / name, ordner / name)
    (basis / "AppData" / "Roaming").mkdir(parents=True)
    (basis / "AppData" / "Local").mkdir(parents=True)

    def lauf(*args):
        env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONUTF8", "PYTHONPATH", "PBP_APP_DIR", "PBP_FASSUNG", "BA_DATA_DIR")}
        # Claude-Konfiguration: Windows liest APPDATA/LOCALAPPDATA, die anderen Systeme das Heimatverzeichnis -- alles unter tmp_path
        env.update(PYTHONIOENCODING="cp1252", APPDATA=str(basis / "AppData" / "Roaming"),
                   LOCALAPPDATA=str(basis / "AppData" / "Local"), HOME=str(basis), USERPROFILE=str(basis))
        return subprocess.run([sys.executable, *args], cwd=str(ordner), env=env, capture_output=True, timeout=120,
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
    """Die Sicherung ist der Schritt, der ein Update abbricht, wenn er nicht gelingt: schon die Erfolgsmeldung mit dem Zielpfad musste halten."""
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


def test_fehlermeldungen_der_helfer_mit_fremden_zeichen_im_pfad_bleiben_lesbar(installer):
    """Der Abbruchgrund steht auf der Ausgabe -- er ist der einzige Hinweis, den jemand in der Protokolldatei findet."""
    r = installer.lauf("_sicherung_vor_update.py", str(installer.basis / "fehlt.db"), str(installer.basis / "Sicherungen"))
    _kein_absturz(r)
    assert r.returncode == 2 and "FEHLER" in _ausgabe(r)

    r = installer.lauf("_programm_einrichten.py", str(installer.basis / "gibt es nicht"), str(installer.basis / "Programm"))
    _kein_absturz(r)
    assert r.returncode == 1 and "[FEHLER]" in _ausgabe(r)

    r = installer.lauf("_installer_aufraeumen.py", "plan", str(installer.ordner), "1.8.0", str(installer.basis / "Programm"),
                       str(installer.basis / "Daten"))
    _kein_absturz(r)
    assert r.returncode == 1 and json.loads(_ausgabe(r))["ordner"] is None
