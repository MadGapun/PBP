"""#1216-#1220 (Funde der unabhängigen Prüfung des Release-Zweigs, 14.10.2026): Unix-Installer und Deinstaller.

* #1216 — `$PYTHON` stand ohne Anführungszeichen als Befehl: ein Leerzeichen im Ordnernamen (macOS nennt einen zweiten Download
  `PBP-1.8.0 2`) ließ den Befehl zerfallen, und unter `set -e` endete der Installer ohne ein Wort.
* #1217 — der Funktionstest öffnete über den Import von `server` die ECHTE Datenbank, bevor er auf ein Temp-Verzeichnis umbog.
* #1218 — die Prozesssuche traf auch ein fremdes `start_dashboard.py` und jeden Testlauf, der den Namen als Argument trägt.
* #1219 — Erfolgsmeldungen ohne Probe: grüner Schluss bei stehengebliebenem MCP-Eintrag, unerreichbarer Fehlerzweig unter `set -e`,
  ein gescheitertes `pip --upgrade pip` beendete den Installer lautlos, `ja` galt nicht als Ja.
* #1220 — `dashboard_urteil` war fail-open: ohne lesbare Fassung galt jede antwortende Fassung als „ok“.

Die Verhaltenstests führen die ECHTEN Abschnitte aus den Dateien aus (nie nachgebaut), mit einem Wrapper statt Python; alle Ordner
liegen in tmp_path, alle Namen sind Platzhalter.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0
DATEIEN = {"install.sh": ROOT / "installer" / "install.sh", "INSTALLIEREN.command": ROOT / "INSTALLIEREN.command"}

# Der Abschnitt "Python/venv/pip", "Funktionstest" und "Claude einrichten" je Datei: von-Marke, bis-Marke.
PIP = {"install.sh": ("# ── 2. venv erstellen", "# ── 4. Frontend bauen"),
       "INSTALLIEREN.command": ("# ── 2. Virtuelle Umgebung", "# ── 4. Frontend bauen")}
CLAUDE = {"install.sh": ("# ── 7. Claude Desktop konfigurieren", "# ── FERTIG"),
          "INSTALLIEREN.command": ("# ── 6. Claude Desktop konfigurieren", "# ── Fertig")}


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


def _lauf(bash, skript: str, timeout=120):
    r = subprocess.run([bash, "-s"], input=skript.encode("utf-8"), capture_output=True, timeout=timeout, creationflags=OHNE_FENSTER)
    return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")


def _text(name: str) -> str:
    return DATEIEN[name].read_text(encoding="utf-8")


def _abschnitt(name: str, marken: dict) -> str:
    text = _text(name)
    a = text.index(marken[name][0])
    return text[a:text.index(marken[name][1], a)]


def _funktionen(name: str) -> str:
    text = _text(name)
    return text[text.index("# --- dashboard-funktionen Anfang"):text.index("# --- dashboard-funktionen Ende")]


def _u(pfad: Path) -> str:
    """Der Pfad, wie ihn ein Unix-Prozess in seiner Befehlszeile traegt (unter Git-Bash `/c/...` statt `C:/...`)."""
    p = pfad.as_posix()
    if sys.platform == "win32" and len(p) > 1 and p[1] == ":":
        return "/" + p[0].lower() + p[2:]
    return p


def _wrapper(pfad: Path, rumpf: str) -> Path:
    """Ein ausfuehrbares Skript, das den Python-Aufruf ersetzt."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(("#!/bin/sh\n" + rumpf + "\n").encode("utf-8"))
    pfad.chmod(0o755)
    return pfad


# ══ #1216: $PYTHON in Anführungszeichen ═══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("name", list(DATEIEN))
def test_1216_kein_python_aufruf_steht_ohne_anfuehrungszeichen(name):
    for nr, zeile in enumerate(_text(name).split("\n"), 1):
        if zeile.lstrip().startswith("#"):
            continue
        assert not re.search(r'(?<!")\$PYTHON\b', zeile), f"{name}:{nr} $PYTHON ohne Anfuehrungszeichen: {zeile.strip()}"
        assert not re.search(r"\$\{PYTHON\}", zeile), f"{name}:{nr}: {zeile.strip()}"


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1216_die_python_schritte_laufen_in_einem_ordner_mit_leerzeichen(bash, tmp_path, name):
    """macOS legt den zweiten Download als `PBP-1.8.0 2` an: die ECHTEN Zeilen von venv bis pip/Chromium laufen durch."""
    projekt = tmp_path / "PBP-1.8.0 2"
    protokoll = tmp_path / "aufrufe.txt"
    assert str(tmp_path) in str(projekt)
    _wrapper(projekt / ".venv" / "bin" / "python", f'echo "$@" >> "{protokoll.as_posix()}"')
    skript = ("set -e\nok() { :; }\ninfo() { :; }\nwarn() { echo \"WARN: $*\"; }\nfail() { echo \"FAIL: $*\"; exit 1; }\n"
              "YELLOW=''\nNC=''\nMODE=update\n"
              f"VENV_DIR='{(projekt / '.venv').as_posix()}'\nPROJECT_DIR='{projekt.as_posix()}'\nPYTHON=/nirgends\n"
              + _abschnitt(name, PIP) + "\necho DURCH\n")
    code, aus = _lauf(bash, skript)
    assert code == 0 and "DURCH" in aus, aus
    aufrufe = protokoll.read_text(encoding="utf-8").splitlines()
    assert any(z.startswith("-m pip install -e ") and projekt.as_posix() in z and "[all]" not in z for z in aufrufe), aufrufe
    assert any("-m playwright install chromium" in z for z in aufrufe), aufrufe


# ══ #1219: ein gescheitertes pip-Update beendet den Installer nicht ═══════════════════════════════════════

@pytest.mark.parametrize("name", list(DATEIEN))
def test_1219_ein_gescheitertes_pip_update_beendet_den_installer_nicht(bash, tmp_path, name):
    projekt = tmp_path / "PBP"
    protokoll = tmp_path / "aufrufe.txt"
    _wrapper(projekt / ".venv" / "bin" / "python",
             f'echo "$@" >> "{protokoll.as_posix()}"\ncase "$*" in *--upgrade*) exit 1 ;; esac')
    skript = ("set -e\nok() { :; }\ninfo() { :; }\nwarn() { echo \"WARN: $*\"; }\nfail() { echo \"FAIL: $*\"; exit 1; }\n"
              "YELLOW=''\nNC=''\nMODE=update\n"
              f"VENV_DIR='{(projekt / '.venv').as_posix()}'\nPROJECT_DIR='{projekt.as_posix()}'\nPYTHON=/nirgends\n"
              + _abschnitt(name, PIP) + "\necho DURCH\n")
    code, aus = _lauf(bash, skript)
    assert code == 0 and "DURCH" in aus and "pip liess sich nicht aktualisieren" in aus, aus
    assert any(z.startswith("-m pip install -e ") for z in protokoll.read_text(encoding="utf-8").splitlines()), "danach geht es weiter"


# ══ #1217: der Funktionstest rührt die echte Datenbank nicht an ══════════════════════════════════════════

def _test_abschnitt() -> str:
    text = _text("install.sh")
    return text[text.index("# ── 5. Test"):text.index("# ── 6. Datenverzeichnis")]


def _funktionstest_lauf(bash, tmp_path, vorgabe: str | None):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    assert str(tmp_path) in str(home), "QA-Isolation: nie das echte Heimatverzeichnis"
    protokoll = tmp_path / "datenordner.txt"
    py = _wrapper(tmp_path / "PBP" / ".venv" / "bin" / "python",
                  f'printf "%s" "$BA_DATA_DIR" > "{protokoll.as_posix()}"\n'
                  f'test -d "$BA_DATA_DIR" && echo "TEMP_DA" >> "{protokoll.as_posix()}.da"\nexit 0')
    vorab = f"export BA_DATA_DIR='{vorgabe}'\n" if vorgabe else "unset BA_DATA_DIR\n"
    skript = (f"set -e\nexport HOME='{home.as_posix()}'\n{vorab}ok() {{ :; }}\ninfo() {{ :; }}\nwarn() {{ :; }}\n"
              "fail() { echo \"FAIL: $*\"; }\nYELLOW=''\nNC=''\n"
              f"PYTHON='{py.as_posix()}'\n" + _test_abschnitt() + '\necho "NACHHER=$BA_DATA_DIR"\n')
    code, aus = _lauf(bash, skript)
    return home, protokoll, code, aus


def test_1217_der_funktionstest_laeuft_auf_einem_temp_verzeichnis_nicht_auf_dem_echten_ordner(bash, tmp_path):
    home, protokoll, code, aus = _funktionstest_lauf(bash, tmp_path, None)
    assert code == 0, aus
    benutzt = protokoll.read_text(encoding="utf-8")
    assert benutzt and ".bewerbungs-assistent" not in benutzt, f"der Test lief auf dem echten Ordner: {benutzt}"
    assert Path(str(protokoll) + ".da").exists(), "das Temp-Verzeichnis lag beim Aufruf vor"
    assert not Path(benutzt).exists(), "und wird danach wieder entfernt"
    assert f"NACHHER={home.as_posix()}/.bewerbungs-assistent" in aus, "der echte Ordner gilt erst nach dem Test (Schritt 6)"


def test_1217_ein_eigener_datenordner_bleibt_nach_dem_test_gesetzt(bash, tmp_path):
    eigener = tmp_path / "mein-datenordner"
    home, protokoll, code, aus = _funktionstest_lauf(bash, tmp_path, eigener.as_posix())
    assert code == 0, aus
    assert protokoll.read_text(encoding="utf-8") != eigener.as_posix(), "der Test lief nicht auf dem eigenen Ordner"
    assert f"NACHHER={eigener.as_posix()}" in aus


def test_1217_ein_gescheiterter_funktionstest_bricht_ab_und_raeumt_auf(bash, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    protokoll = tmp_path / "datenordner.txt"
    py = _wrapper(tmp_path / "PBP" / ".venv" / "bin" / "python", f'printf "%s" "$BA_DATA_DIR" > "{protokoll.as_posix()}"\nexit 1')
    skript = (f"set -e\nexport HOME='{home.as_posix()}'\nunset BA_DATA_DIR\nok() {{ echo \"OK: $*\"; }}\n"
              "fail() { echo \"FAIL: $*\"; }\nYELLOW=''\nNC=''\n"
              f"PYTHON='{py.as_posix()}'\n" + _test_abschnitt() + '\necho "ZU_WEIT"\n')
    code, aus = _lauf(bash, skript)
    assert code == 1 and "FAIL: Funktionstest fehlgeschlagen" in aus and "ZU_WEIT" not in aus, aus
    assert not Path(protokoll.read_text(encoding="utf-8")).exists(), "auch beim Scheitern wird aufgeraeumt"


def test_1217_im_funktionstest_steht_der_temp_ordner_vor_dem_ersten_import():
    text = _test_abschnitt()
    assert text.index('BA_DATA_DIR="$TEST_DIR"') < text.index("import os"), "gesetzt VOR dem ersten Import"
    assert text.index("from bewerbungs_assistent.server import mcp") < text.index("db = Database()")
    assert "assert d in str(db.db_path)" in text, "die Isolation wird nach dem Oeffnen geprueft (CLAUDE.md: QA-Isolation)"
    echt = text.index('export BA_DATA_DIR="${BA_DATA_DIR:-$HOME/.bewerbungs-assistent}"')
    assert echt > text.index("-c \""), "der echte Ordner wird erst NACH dem Test gesetzt"


# ══ #1218: die Prozesssuche ═════════════════════════════════════════════════════════════════════════════

def _fremd_urteile(bash, tmp_path, zeilen: list[str]) -> list[int]:
    skript = "info() { :; }\nPROJECT_DIR=/nirgends\n" + _funktionen("install.sh") + "\n"
    for z in zeilen:
        skript += "skript_ist_fremd '" + z.replace("'", "'\\''") + "'; echo \"RC=$?\"\n"
    code, aus = _lauf(bash, skript)
    assert code == 0, aus
    return [int(m) for m in re.findall(r"^RC=(\d+)$", aus, re.M)]


def test_1218_nachweislich_fremde_skripte_gelten_als_fremd_alles_andere_nicht(bash, tmp_path):
    pbp = tmp_path / "PBP-1.8.0 2"
    (pbp / "src" / "bewerbungs_assistent").mkdir(parents=True)
    (pbp / "start_dashboard.py").write_text("x", encoding="utf-8")
    app = tmp_path / "app"
    (app / "versions" / "1.8.0").mkdir(parents=True)
    (app / "start_dashboard.py").write_text("x", encoding="utf-8")
    fremd = tmp_path / "andere-app"
    fremd.mkdir()
    (fremd / "start_dashboard.py").write_text("x", encoding="utf-8")
    py_mit_leerzeichen = tmp_path / "py dir" / "bin"
    assert str(tmp_path) in str(fremd)
    zeilen = [
        f"/usr/bin/python3 {_u(pbp)}/start_dashboard.py",                # PBP, Pfad mit Leerzeichen
        f"/usr/bin/python3 {_u(app)}/start_dashboard.py",                # Programmordner der Auto-Update-Fassung
        f"/usr/bin/python3 {_u(fremd)}/start_dashboard.py",              # fremd: Datei da, kein PBP daneben
        f"{_u(py_mit_leerzeichen)}/python {_u(fremd)}/start_dashboard.py --port 8300",   # fremd, Python mit Leerzeichen
        "python3 start_dashboard.py",                                           # relativ: nicht lesbar -> nicht fremd
        "/usr/bin/python3 /nirgends/start_dashboard.py",                        # Datei nicht da -> nicht fremd
        "/usr/bin/python3 -m pytest tests/test_start_dashboard.py",             # nennt den Namen nur als Teil eines anderen
        "",
    ]
    assert _fremd_urteile(bash, tmp_path, zeilen) == [1, 1, 0, 0, 1, 1, 1, 1]


def test_1218_das_muster_trifft_pbp_und_keinen_testlauf_oder_fremden_namen(bash, tmp_path):
    ja = ["python3 start_dashboard.py", "python3.12 start_dashboard.py", "/home/x/pbp/.venv/bin/python /home/x/pbp/start_dashboard.py",
          "/home/x/pbp/.venv/bin/python /home/x/PBP-1.8.0 2/start_dashboard.py --port 8201"]
    nein = ["python -m pytest tests/test_start_dashboard.py", "/usr/bin/python3 -m pytest /home/x/pbp/tests/test_start_dashboard.py",
            "python3 mein_start_dashboard.py", "vim /home/x/pbp/start_dashboard.py", "grep -r start_dashboard.py ."]
    skript = ("info() { :; }\nPROJECT_DIR=/nirgends\n" + _funktionen("install.sh")
              + "\nwhile IFS= read -r z; do if printf '%s\\n' \"$z\" | grep -E -i -q \"$DASH_MUSTER\"; then echo \"JA|$z\"; else echo \"NEIN|$z\"; fi; done <<'PROBEN'\n"
              + "\n".join(ja + nein) + "\nPROBEN\n")
    code, aus = _lauf(bash, skript)
    assert code == 0, aus
    for z in ja:
        assert f"JA|{z}" in aus, f"muss getroffen werden: {z}\n{aus}"
    for z in nein:
        assert f"NEIN|{z}" in aus, f"darf nicht getroffen werden: {z}\n{aus}"


def test_1218_dashboard_pids_laesst_ein_fremdes_skript_in_ruhe(bash, tmp_path):
    pbp = tmp_path / "pbp"
    (pbp / "src" / "bewerbungs_assistent").mkdir(parents=True)
    (pbp / "start_dashboard.py").write_text("x", encoding="utf-8")
    fremd = tmp_path / "fremd"
    fremd.mkdir()
    (fremd / "start_dashboard.py").write_text("x", encoding="utf-8")
    skript = ("info() { :; }\nPROJECT_DIR=/nirgends\n" + _funktionen("install.sh") + "\n"
              "pgrep() { printf '%s\\n' 111 222 333; }\n"
              "ps() {\n  case \"$2\" in\n"
              f"    111) echo \"/usr/bin/python3 {_u(fremd)}/start_dashboard.py\" ;;\n"
              f"    222) echo \"/usr/bin/python3 {_u(pbp)}/start_dashboard.py\" ;;\n"
              "    333) echo \"python3 start_dashboard.py\" ;;\n  esac\n}\n"
              'echo "PIDS=[$(dashboard_pids | tr "\\n" " ")]"\n')
    code, aus = _lauf(bash, skript)
    assert code == 0 and "PIDS=[222 333 ]" in aus, aus


# ══ #1219: der Fehlerzweig nach _setup_claude.py und die Meldung ════════════════════════════════════════

def _claude_lauf(bash, tmp_path, name, python_rumpf: str):
    home = tmp_path / "home"
    if name == "install.sh":
        config_dir = home / ".config" / "Claude"
        vorspann = 'PLATFORM=linux\n'
    else:
        config_dir = home / "Library" / "Application Support" / "Claude"
        vorspann = ''
    config_dir.mkdir(parents=True)
    assert str(tmp_path) in str(config_dir)
    projekt = tmp_path / "PBP 1.8.0 2"
    py = _wrapper(projekt / ".venv" / "bin" / "python", python_rumpf)
    skript = (f"set -e\nexport HOME='{home.as_posix()}'\nok() {{ echo \"OK: $*\"; }}\ninfo() {{ :; }}\n"
              "warn() { echo \"WARN: $*\"; }\nfail() { echo \"FAIL: $*\"; }\nYELLOW=''\nNC=''\nCYAN=''\nBOLD=''\n"
              f"PROJECT_DIR='{projekt.as_posix()}'\nPYTHON='{py.as_posix()}'\n"
              + _abschnitt(name, CLAUDE) + '\necho "WEITER fehler=${CLAUDE_FEHLER:-0} kopie=[${CLAUDE_KOPIE:-}]"\n')
    return _lauf(bash, skript)


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1219_ein_fehlschlag_von_setup_claude_erreicht_den_fehlerzweig(bash, tmp_path, name):
    """Unter `set -e` beendete der Fehlschlag das Skript an dieser Stelle; der Zweig mit dem Handgriff lief nie."""
    code, aus = _claude_lauf(bash, tmp_path, name, 'echo "[CLAUDE] kaputt"\nexit 1')
    assert code == 0, aus
    assert "WEITER fehler=1" in aus, aus
    assert "WARN:" in aus and "manuell" in aus.lower() and "_setup_claude.py" in aus
    assert "PBP 1.8.0 2" in aus, "der Handgriff nennt den Pfad - in Anfuehrungszeichen, damit das Leerzeichen kopierbar bleibt"
    assert "OK: Claude Desktop konfiguriert" not in aus


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1219_eine_gesicherte_defekte_konfiguration_wird_fuer_den_schluss_gemerkt(bash, tmp_path, name):
    kopie = (tmp_path / "home" / "claude_desktop_config.json.pbp-defekt-20261014-101500").as_posix()
    code, aus = _claude_lauf(
        bash, tmp_path, name,
        f'echo "[CLAUDE] x: Config nicht lesbar (Expecting value); Kopie gesichert: {kopie}"\necho "[CLAUDE] Config geschrieben: x"\nexit 0')
    assert code == 0, aus
    assert f"kopie=[{kopie}]" in aus and "fehler=0" in aus, aus
    assert "OK: Claude Desktop konfiguriert" in aus


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1219_der_schluss_kennt_die_gelbe_fassung_und_die_kopie(name):
    text = _text(name)
    assert 'if [ "${CLAUDE_FEHLER:-0}" = "1" ]; then' in text and 'if [ -n "${CLAUDE_KOPIE:-}" ]; then' in text
    gelb = text.index('"${YELLOW}╔')
    gruen = text.index('"${GREEN}╔')
    assert gelb < gruen, "die Bedingung steht vor dem gruenen Kasten"


def _deinstallieren(bash, tmp_path, inhalt: bytes | None, eingabe: str = "j\nn\nn\n"):
    home = tmp_path / "home"
    if sys.platform == "darwin":
        config = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        config = home / ".config" / "Claude" / "claude_desktop_config.json"
    config.parent.mkdir(parents=True)
    if inhalt is not None:
        config.write_bytes(inhalt)
    assert str(tmp_path) in str(home), "QA-Isolation: nie das echte Heimatverzeichnis"
    eingabe_datei = tmp_path / "eingabe.txt"
    eingabe_datei.write_bytes(eingabe.encode("utf-8"))       # Bytes: write_text haengt unter Windows ein CR an jede Zeile ("j\r")
    skript = (f'python3() {{ "{Path(sys.executable).as_posix()}" "$@"; }}\nexport -f python3\n'
              f'export HOME="{home.as_posix()}"\n'
              f'bash "{(ROOT / "installer" / "deinstallieren.sh").as_posix()}" < "{eingabe_datei.as_posix()}"\n')
    code, aus = _lauf(bash, skript)
    return config, code, aus


def test_1219_bleibt_der_mcp_eintrag_stehen_ist_die_deinstallation_nicht_abgeschlossen(bash, tmp_path):
    config, code, aus = _deinstallieren(bash, tmp_path, b'{"mcpServers": {"filesystem": ')
    assert code == 1, aus
    assert "NICHT ganz abgeschlossen" in aus and "von Hand" in aus and str(config).replace("\\", "/") in aus.replace("\\", "/"), aus
    assert "Deinstallation abgeschlossen" not in aus, "kein gruener Kasten"


def test_1219_wurde_der_eintrag_entfernt_endet_die_deinstallation_gruen(bash, tmp_path):
    roh = json.dumps({"mcpServers": {"bewerbungs-assistent": {"command": "python"}}}).encode("utf-8")
    config, code, aus = _deinstallieren(bash, tmp_path, roh)
    assert code == 0 and "Deinstallation abgeschlossen" in aus and "NICHT ganz" not in aus, aus


def test_1219_ohne_eintrag_ist_die_deinstallation_ebenfalls_vollstaendig(bash, tmp_path):
    config, code, aus = _deinstallieren(bash, tmp_path, b'{"mcpServers": {"filesystem": {"command": "npx"}}}')
    assert code == 0 and "Deinstallation abgeschlossen" in aus, aus


@pytest.mark.parametrize("antwort", ["j", "J", "ja", "Ja", "JA", "y", "yes"])
def test_1219_ja_gilt_wie_j(bash, tmp_path, antwort):
    roh = json.dumps({"mcpServers": {"bewerbungs-assistent": {"command": "python"}}}).encode("utf-8")
    config, code, aus = _deinstallieren(bash, tmp_path, roh, eingabe=f"{antwort}\nn\nn\n")
    assert "Abgebrochen" not in aus and "MCP-Eintrag entfernt" in aus, aus


@pytest.mark.parametrize("antwort", ["", "n", "nein", "vielleicht"])
def test_1219_alles_andere_bricht_ab_ohne_etwas_zu_aendern(bash, tmp_path, antwort):
    roh = json.dumps({"mcpServers": {"bewerbungs-assistent": {"command": "python"}}}).encode("utf-8")
    config, code, aus = _deinstallieren(bash, tmp_path, roh, eingabe=f"{antwort}\n")
    assert code == 0 and "Abgebrochen" in aus, aus
    assert config.read_bytes() == roh


def test_1219_der_doppelklick_deinstaller_reicht_den_exitcode_durch_und_haelt_das_fenster_offen():
    text = (ROOT / "DEINSTALLIEREN.command").read_text(encoding="utf-8")
    assert 'bash "$SKRIPT" || ERGEBNIS=$?' in text, "set -e haette das Fenster sofort geschlossen"
    assert text.index('bash "$SKRIPT" || ERGEBNIS=$?') < text.rindex("read -p") < text.index('exit "$ERGEBNIS"')


# ══ #1220: ohne lesbare Fassung gilt nichts als "ok" ════════════════════════════════════════════════════

@pytest.mark.parametrize("name", list(DATEIEN))
def test_1220_ohne_lesbare_fassung_gilt_keine_antwort_als_ok(bash, tmp_path, name):
    leer = tmp_path / "projekt"
    leer.mkdir()
    skript = (f"set -e\ninfo() {{ :; }}\nPROJECT_DIR='{leer.as_posix()}'\n" + _funktionen(name)
              + '\necho "FASSUNG=[$NEUE_FASSUNG]"\necho "STAND=$(dashboard_urteil "1.8.0")"\necho "KEINS=$(dashboard_urteil "")"\n')
    code, aus = _lauf(bash, skript)
    assert code == 0 and "FASSUNG=[]" in aus, aus
    assert "STAND=unbekannt" in aus and "KEINS=keins" in aus, aus


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1220_die_fassung_wird_aus_der_echten_init_datei_gelesen(bash, name):
    """Das `sed` lief nur gegen eine synthetische Datei - hier gegen die echte, damit eine geaenderte Schreibweise auffaellt."""
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', (ROOT / "src" / "bewerbungs_assistent" / "__init__.py").read_text(encoding="utf-8"), re.M)
    skript = (f"set -e\ninfo() {{ :; }}\nPROJECT_DIR='{ROOT.as_posix()}'\n" + _funktionen(name) + '\necho "FASSUNG=[$NEUE_FASSUNG]"\n')
    code, aus = _lauf(bash, skript)
    assert code == 0 and f"FASSUNG=[{m.group(1)}]" in aus, aus


@pytest.mark.parametrize("name", list(DATEIEN))
def test_1220_die_schlussmeldung_kennt_den_ausgang_unbekannt(name):
    text = _text(name)
    schluss = text[text.index('DASH_URTEIL="$(dashboard_urteil'):]
    assert 'elif [ "$DASH_URTEIL" = "unbekannt" ]' in schluss
    assert schluss.index('"unbekannt"') < schluss.index('"alt"'), "ein eigener Zweig, kein Teil von ok oder alt"
