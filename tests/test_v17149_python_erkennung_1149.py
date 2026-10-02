"""#1149 Punkt 5 — die Python-Erkennung der Unix-Installer.

Zwei Fehler, beide mit Attrappen nachgestellt (kein echter Mac):

A) `installer/install.sh` las die Version mit `grep -oP`. Das grep von macOS (BSD) kennt `-P`
   nicht. Weil die Pipe mit `cut` endete, lief der Rückfall nach `||` nie: „Python 3.11+ nicht
   gefunden!“ trotz installiertem 3.12 oder 3.13.
B) `INSTALLIEREN.command` (beim Nachstellen gefunden) las sie mit `s/.*3\\.\\([0-9]*\\).*/\\1/p`.
   Das `.*` greift so weit wie möglich und nimmt das LETZTE „3.“ im Text: bei „Python 3.13.5“
   die „3.5“ statt der „3.13“. Jede Fassung 3.13.x galt als zu alt (Nebenversion 5), obwohl 3.13
   neuer ist als die verlangte 3.11.

Die Tests ziehen den Schritt „Python prüfen“ aus der Datei und führen ihn unter `set -e` aus, mit
einem falschen Interpreter als Shell-Funktion (nie über den Pfad: ein echter darf nicht erreichbar
sein) und wahlweise einem BSD-grep, das `-P` ablehnt. Sie brauchen ein lauffähiges bash (unter
Windows Git-Bash; der WSL-Stub in System32 zählt nicht) und überspringen sonst.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0

DATEIEN = {
    "install.sh": (ROOT / "installer" / "install.sh", "# ── 1. Python pruefen", "# ── 2. venv erstellen",
                   "Python 3.11+ nicht gefunden"),
    "INSTALLIEREN.command": (ROOT / "INSTALLIEREN.command", "# ── 1. Python pruefen",
                             "# ── 2. Virtuelle Umgebung", "Python 3.11 oder neuer wird benoetigt"),
}

RICHTIG = ["Python 3.11.0", "Python 3.11.9", "Python 3.12.3", "Python 3.12.4", "Python 3.13.0",
           "Python 3.13.1", "Python 3.13.5", "Python 3.14.0"]
ZU_ALT = ["Python 3.10.14", "Python 3.9.13", "Python 3.8.10", "Python 2.7.18"]


def _bash():
    """Ein bash, das wirklich ausführt und Windows-Pfade versteht (nicht der WSL-Stub)."""
    namen = ("bash.exe", "bash") if sys.platform == "win32" else ("bash",)
    ordner = os.environ.get("PATH", "").split(os.pathsep)
    if sys.platform == "win32":
        for variable in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
            basis = os.environ.get(variable)
            if basis:
                ordner += [str(Path(basis) / u) for u in ("Git/bin", "Git/usr/bin", "Programs/Git/bin")]
    for o in ordner:
        for name in namen:
            pfad = Path(o) / name if o else None
            if not (pfad and pfad.is_file()) or "system32" in str(pfad).lower():
                continue
            try:
                if subprocess.run([str(pfad), "-c", "true"], capture_output=True, timeout=30,
                                  creationflags=OHNE_FENSTER).returncode == 0:
                    return str(pfad)
            except (OSError, subprocess.SubprocessError):
                continue
    return None


@pytest.fixture(scope="module")
def bash():
    pfad = _bash()
    if not pfad:
        pytest.skip("kein lauffaehiges bash (WSL ohne Distribution?)")
    return pfad


def _schritt(name: str) -> str:
    datei, von, bis, _ = DATEIEN[name]
    zeilen = datei.read_text(encoding="utf-8").splitlines()
    a = next(i for i, z in enumerate(zeilen) if z.startswith(von))
    b = next(i for i, z in enumerate(zeilen) if i > a and z.startswith(bis))
    return "\n".join(zeilen[a:b])


# Die Attrappen: ein BSD-grep, das `-P` ablehnt wie auf macOS; und `command -v`, das nur die genannten Namen findet.
BSD_GREP = ('grep() { for a in "$@"; do case "$a" in -*P*) echo "grep: invalid option -- P" >&2; return 2;; '
            'esac; done; builtin command grep "$@"; }\n')


def _vorspann(vorhanden: dict, bsd_grep: bool) -> str:
    funktionen = "".join(f'{n}() {{ echo "{v}"; }}\n' for n, v in vorhanden.items())
    namen = " ".join(vorhanden)
    command = ('command() { if [ "$1" = "-v" ]; then case " ' + namen + ' " in *" $2 "*) return 0;; esac; '
               'return 1; fi; builtin command "$@"; }\n')
    return (
        "set -e\nRED='';GREEN='';YELLOW='';CYAN='';BOLD='';NC=''\n"
        'ok() { echo "OK: $*"; }\nwarn() { echo "WARN: $*"; }\ninfo() { echo "INFO: $*"; }\n'
        'fail() { echo "FAIL: $*"; }\nPLATFORM=macos\n'
        + funktionen + command + (BSD_GREP if bsd_grep else ""))


def _lauf(bash, name, vorhanden: dict, bsd_grep: bool):
    skript = _vorspann(vorhanden, bsd_grep) + _schritt(name) + '\necho "PYTHON=$PYTHON"\n'
    r = subprocess.run([bash, "-s"], input=skript.encode("utf-8"), capture_output=True, timeout=120,
                       creationflags=OHNE_FENSTER)
    return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")


@pytest.mark.parametrize("bsd_grep", [False, True], ids=["gnu-grep", "bsd-grep"])
@pytest.mark.parametrize("version", RICHTIG)
@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_python_ab_3_11_wird_erkannt(bash, name, version, bsd_grep):
    code, aus = _lauf(bash, name, {"python3": version}, bsd_grep)
    assert code == 0, f"{version} nicht erkannt (Exit {code}): {aus}"
    assert "PYTHON=python3" in aus, aus
    assert "nicht gefunden" not in aus and "wird benoetigt" not in aus


@pytest.mark.parametrize("bsd_grep", [False, True], ids=["gnu-grep", "bsd-grep"])
@pytest.mark.parametrize("version", ZU_ALT)
@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_ein_zu_altes_python_wird_abgelehnt(bash, name, version, bsd_grep):
    code, aus = _lauf(bash, name, {"python3": version}, bsd_grep)
    assert code == 1, f"{version} wurde nicht abgelehnt (Exit {code}): {aus}"
    assert "PYTHON=" not in aus
    assert DATEIEN[name][3] in aus, aus


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_die_reihenfolge_der_kandidaten_bleibt(bash, name):
    """python3.13 vor python3.12 vor python3: der erste brauchbare gewinnt; ein zu altes wird übersprungen."""
    code, aus = _lauf(bash, name, {"python3.13": "Python 3.13.5", "python3.12": "Python 3.12.4"}, True)
    assert code == 0 and "PYTHON=python3.13" in aus, aus
    code, aus = _lauf(bash, name, {"python3.12": "Python 3.12.4", "python3": "Python 3.9.13"}, True)
    assert code == 0 and "PYTHON=python3.12" in aus, aus
    code, aus = _lauf(bash, name, {"python3.11": "Python 3.10.2", "python3": "Python 3.12.4"}, True)
    assert code == 0 and "PYTHON=python3" in aus, aus
    # Beide brauchbar: die genannte Fassung (python3.13) kommt vor dem allgemeinen python3.
    code, aus = _lauf(bash, name, {"python3": "Python 3.12.4", "python3.13": "Python 3.13.5"}, True)
    assert code == 0 and "PYTHON=python3.13" in aus, aus


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_ohne_jedes_python_bricht_der_installer_mit_hinweis_ab(bash, name):
    code, aus = _lauf(bash, name, {}, True)
    assert code == 1 and "PYTHON=" not in aus
    assert DATEIEN[name][3] in aus


# ── Die Attrappen stellen den alten Fehler wirklich nach (sonst wären die Tests oben leer) ──────────

ALT_INSTALL_SH = ("""minor=$(echo "$ver" | grep -oP '3\\.(\\d+)' | head -1 | cut -d. -f2 2>/dev/null """
                  """|| echo "$ver" | sed -n 's/.*3\\.\\([0-9]*\\).*/\\1/p')""")
ALT_COMMAND = """minor=$(echo "$ver" | sed -n 's/.*3\\.\\([0-9]*\\).*/\\1/p')"""


def _alte_minor(bash, ausdruck: str, ver: str, bsd_grep: bool) -> str:
    skript = (BSD_GREP if bsd_grep else "") + f'ver="{ver}"\n{ausdruck}\necho "[$minor]"\n'
    r = subprocess.run([bash, "-s"], input=skript.encode("utf-8"), capture_output=True, timeout=60,
                       creationflags=OHNE_FENSTER)
    return r.stdout.decode("utf-8", "replace").strip()


def test_1149_die_attrappe_stellt_den_fehler_des_bsd_grep_nach(bash):
    assert _alte_minor(bash, ALT_INSTALL_SH, "Python 3.12.4", bsd_grep=False) == "[12]"
    assert _alte_minor(bash, ALT_INSTALL_SH, "Python 3.12.4", bsd_grep=True) == "[]", \
        "mit dem BSD-grep muss der alte Ausdruck leer bleiben (der Rückfall lief nie)"


@pytest.mark.parametrize("ver,falsch", [("Python 3.13.0", "[0]"), ("Python 3.13.5", "[5]")])
def test_1149_der_alte_command_ausdruck_las_die_patchnummer_statt_der_nebenversion(bash, ver, falsch):
    assert _alte_minor(bash, ALT_COMMAND, ver, bsd_grep=False) == falsch


# ── Ohne bash lesbar ───────────────────────────────────────────────────────────────────────────────

def test_1149_kein_unix_skript_ruft_grep_mit_p_auf():
    """`grep -P` gibt es auf macOS nicht. Kommentare zählen nicht."""
    gefunden = []
    kandidaten = [ROOT / "INSTALLIEREN.command", ROOT / "DEINSTALLIEREN.command",
                  ROOT / "Dashboard starten.command"] + sorted((ROOT / "installer").glob("*.sh"))
    for datei in kandidaten:
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if zeile.strip().startswith("#"):
                continue
            if re.search(r"\bgrep\s+-[A-Za-z]*P", zeile):
                gefunden.append(f"{datei.name}:{nr}: {zeile.strip()}")
    assert not gefunden, "grep -P in einem Unix-Skript:\n" + "\n".join(gefunden)


def test_1149_der_dashboard_starter_verweist_mac_nutzer_auf_den_doppelklick_installer():
    text = (ROOT / "Dashboard starten.command").read_text(encoding="utf-8")
    assert "INSTALLIEREN.command" in text
    assert "bash installer/install.sh" not in text, "ein Doppelklick-Nutzer hat kein Terminal"
