"""#1149 Punkt 6 — ein fehlgeschlagener Frontend-Bau beendet den Unix-Installer nicht mehr lautlos.

Befund (01.10.2026, nachgebildet): `installer/install.sh` und `INSTALLIEREN.command` laufen
unter `set -e`. Schritt 4 („Dashboard bauen“) rief `pnpm --dir … install --quiet 2>/dev/null` auf;
endet das mit Exit 1 (kein Netz, Registry gesperrt, alte Node-Version), beendet `set -e` den
Installer ohne ein Wort — Datenordner und Claude-Eintrag kommen nie. Das fertig gebaute Dashboard
liegt dem ZIP und dem Tag aber bei; der Bau ist eine Zugabe, kein Muss.

Die Tests ziehen den Schritt aus der Datei und führen ihn unter `set -e` aus, mit einem falschen
`pnpm` als Shell-Funktion (nie über den Pfad: ein echtes pnpm darf nicht erreichbar sein; unter
Windows zerlegt Git-Bash einen Pfad wie `C:/…` an der Doppelpunkt-Trennung). Sie brauchen ein lauffähiges bash (unter Windows Git-Bash; der
WSL-Stub in System32 zählt nicht) und überspringen sonst.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0

DATEIEN = {
    "install.sh": (ROOT / "installer" / "install.sh", "# ── 4. Frontend bauen", "# ── 5. Test"),
    "INSTALLIEREN.command": (ROOT / "INSTALLIEREN.command", "# ── 4. Frontend bauen", "# ── 5. Datenverzeichnis"),
}


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
    datei, von, bis = DATEIEN[name]
    zeilen = datei.read_text(encoding="utf-8").splitlines()
    a = next(i for i, z in enumerate(zeilen) if z.startswith(von))
    b = next(i for i, z in enumerate(zeilen) if i > a and z.startswith(bis))
    return "\n".join(zeilen[a:b])


def _lauf(bash, tmp_path, name, install_exit=None, bau_exit=0):
    """Führt den Schritt „Frontend bauen“ unter `set -e` aus. `install_exit` und `bau_exit` sind die
    Exit-Codes, die das falsche pnpm für `install` und `run build` liefert (`install_exit=None`: es gibt
    gar kein pnpm). Das falsche pnpm meldet jeden Aufruf als „PNPM: …“, damit man sieht, dass der Bau
    wirklich versucht wurde. Gibt (Rückgabewert, Ausgabe) zurück; „WEITER“ steht nur da, wenn der
    Installer nach dem Schritt weiterläuft."""
    projekt = tmp_path / "projekt"
    (projekt / "frontend").mkdir(parents=True)
    # Das falsche pnpm ist eine Funktion; `command -v pnpm` findet sie, ein echtes pnpm bleibt unerreichbar.
    falsch = ""
    if install_exit is not None:
        falsch = ("pnpm() { case \"$1\" in --version) echo 9.9.9; return 0;; esac; echo \"PNPM: $3 $4\"; "
                  "case \"$3\" in install) return " + str(install_exit) + ";; run) return "
                  + str(bau_exit) + ";; esac; return 0; }\n")
    else:
        falsch = ("command() { if [ \"$1\" = \"-v\" ] && [ \"$2\" = \"pnpm\" ]; then return 1; fi; "
                  "builtin command \"$@\"; }\nnpm() { return 1; }\n")
    skript = (
        "set -e\nRED='';GREEN='';YELLOW='';CYAN='';NC=''\n"
        "ok() { echo \"OK: $*\"; }\nwarn() { echo \"WARN: $*\"; }\ninfo() { echo \"INFO: $*\"; }\n"
        f"PLATFORM=linux\nPROJECT_DIR='{projekt.as_posix()}'\n" + falsch
        + _schritt(name) + "\necho WEITER\n")
    r = subprocess.run([bash, "-s"], input=skript.encode("utf-8"), capture_output=True, timeout=120,
                       creationflags=OHNE_FENSTER)
    return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")


# Was der Anwender liest, wenn der Bau nicht klappt (install.sh trennt die beiden Fälle, das .command nicht).
WARNUNG_INSTALL = {"install.sh": "Frontend-Abhaengigkeiten liessen sich nicht installieren",
                   "INSTALLIEREN.command": "Dashboard-Bau fehlgeschlagen"}
WARNUNG_BAU = {"install.sh": "Frontend-Bau fehlgeschlagen", "INSTALLIEREN.command": "Dashboard-Bau fehlgeschlagen"}


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_ein_fehlgeschlagenes_pnpm_install_beendet_den_installer_nicht(bash, tmp_path, name):
    code, aus = _lauf(bash, tmp_path, name, install_exit=1)
    assert "WEITER" in aus, f"der Installer ist stehen geblieben (Exit {code}): {aus}"
    assert code == 0
    assert "WARN:" in aus and "fertig gebaute Dashboard liegt bei" in aus, aus
    assert WARNUNG_INSTALL[name] in aus, aus
    assert "gebaut" not in aus.replace("fertig gebaute", ""), "Erfolg gemeldet, obwohl der Bau scheiterte"


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_ein_fehlgeschlagener_bau_nach_gelungener_installation_beendet_den_installer_nicht(bash, tmp_path, name):
    """Der zweite Weg: `install` klappt, erst `run build` scheitert (kaputte Node-Version, Speicher)."""
    code, aus = _lauf(bash, tmp_path, name, install_exit=0, bau_exit=1)
    assert "WEITER" in aus, f"der Installer ist stehen geblieben (Exit {code}): {aus}"
    assert code == 0
    assert "PNPM: run build" in aus, "der Bau wurde gar nicht versucht"
    assert "WARN:" in aus and "fertig gebaute Dashboard liegt bei" in aus, aus
    assert WARNUNG_BAU[name] in aus, aus
    assert "gebaut" not in aus.replace("fertig gebaute", ""), "Erfolg gemeldet, obwohl der Bau scheiterte"


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_ein_gelungener_bau_wird_gemeldet(bash, tmp_path, name):
    code, aus = _lauf(bash, tmp_path, name, install_exit=0, bau_exit=0)
    assert code == 0 and "WEITER" in aus, aus
    assert "WARN:" not in aus
    assert "gebaut" in aus
    # Installieren und Bauen laufen wirklich, in dieser Reihenfolge — ein stummer Erfolg ohne Bau gilt nicht.
    assert "PNPM: install" in aus and "PNPM: run build" in aus, aus
    assert aus.index("PNPM: install") < aus.index("PNPM: run build")


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_ohne_pnpm_und_ohne_node_laeuft_der_installer_weiter(bash, tmp_path, name):
    """Der unveränderte Zweig: kein pnpm, kein npm, kein node auf dem Pfad."""
    projekt = tmp_path / "projekt"
    (projekt / "frontend").mkdir(parents=True)
    leer = tmp_path / "leer"
    leer.mkdir()
    skript = (
        "set -e\nRED='';GREEN='';YELLOW='';CYAN='';NC=''\n"
        "ok() { echo \"OK: $*\"; }\nwarn() { echo \"WARN: $*\"; }\ninfo() { echo \"INFO: $*\"; }\n"
        f"PLATFORM=linux\nPROJECT_DIR='{projekt.as_posix()}'\n"
        "command() { if [ \"$1\" = \"-v\" ]; then return 1; fi; builtin command \"$@\"; }\n"
        + _schritt(name) + "\necho WEITER\n")
    r = subprocess.run([bash, "-s"], input=skript.encode("utf-8"), capture_output=True, timeout=120,
                       creationflags=OHNE_FENSTER)
    aus = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    assert r.returncode == 0 and "WEITER" in aus, aus
    assert "WARN:" in aus


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_kein_pnpm_aufruf_steht_mehr_ungeschuetzt_unter_set_e(name):
    """Auch ohne bash lesbar: jeder pnpm-Aufruf des Schritts steht in einer if-Bedingung."""
    schritt = _schritt(name)
    for zeile in schritt.splitlines():
        s = zeile.strip()
        if s.startswith(("pnpm ", "pnpm\t")):
            pytest.fail(f"pnpm-Aufruf ohne Absicherung unter set -e: {s}")
    assert "if pnpm" in schritt


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1149_die_skripte_haben_set_e_und_den_schritt_noch(name):
    """Der Wächter prüft, was er prüfen soll: `set -e` steht im Skript, und der Schritt ist da."""
    datei, _, _ = DATEIEN[name]
    text = datei.read_text(encoding="utf-8")
    assert "\nset -e\n" in text
    assert "pnpm --dir" in _schritt(name)
