"""Auto-Update (#1093): Pfade mit fremden Zeichen — der Programmordner liegt im Benutzerordner, und der heisst nicht immer »Max«.

Windows-Benutzernamen mit Umlauten, Leerzeichen, Klammern oder Buchstaben ausserhalb der westlichen Zeichentabelle (Polnisch,
Tuerkisch, Griechisch) gehoeren zum Alltag. Der Fassungsordner liegt darunter, und der Selbsttest druckt den Pfad. Jede Stelle,
die einen Unterprozess startet und dessen Ausgabe liest, muss damit zurechtkommen — unabhaengig davon, welche Zeichentabelle der
Rechner eingestellt hat.

Die Prozess-Ende-zu-Ende-Faelle (Start, Rueckfall, MCP-Server in einem Pfad mit Umlauten) stehen in `test_v18_auto_update_e2e.py`;
hier stehen die Stellen, die Ausgabe von Unterprozessen LESEN. Der Selbsttest als Datei, `_setup_claude.py` und `_sicherung_vor_update.py`
gibt es auch in der 1.7-Linie: `test_v17150_installer_pfade_1163.py`.
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
# Die Helfer, die es erst in der 1.8-Linie gibt. Gleiche Ursache wie bei `_setup_claude.py` und `_sicherung_vor_update.py`: die Ausgabe
# geht in die Protokolldatei des Installers, und dort gilt die Zeichentabelle des Rechners. Diese beiden und der Selbsttest stehen in
# `test_v17150_installer_pfade_1163.py` (dieselbe Datei in der 1.7- und der 1.8-Linie).

HELFER = ("_programm_einrichten.py", "_installer_aufraeumen.py")


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


def test_fehlermeldungen_der_helfer_mit_fremden_zeichen_im_pfad_bleiben_lesbar(installer):
    """Der Abbruchgrund steht auf der Ausgabe -- er ist der einzige Hinweis, den jemand in der Protokolldatei findet."""
    r = installer.lauf("_programm_einrichten.py", str(installer.basis / "gibt es nicht"), str(installer.basis / "Programm"))
    _kein_absturz(r)
    assert r.returncode == 1 and "[FEHLER]" in _ausgabe(r)

    r = installer.lauf("_installer_aufraeumen.py", "plan", str(installer.ordner), "1.8.0", str(installer.basis / "Programm"),
                       str(installer.basis / "Daten"))
    _kein_absturz(r)
    assert r.returncode == 1 and json.loads(_ausgabe(r))["ordner"] is None
