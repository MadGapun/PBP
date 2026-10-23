"""#1238 - Installer bauen den MCP-Eintrag neu und verlieren dabei die eigenen Einstellungen (env).

Befund (16.10.2026, beim Bau des optionalen API-Wegs #1236): wer den Schluessel unter `env` des Eintrags
`bewerbungs-assistent` in der Konfiguration von Claude Desktop eintraegt (`PBP_ANTHROPIC_API_KEY`), verliert ihn
beim naechsten Ueberinstallieren, ohne Hinweis. `_setup_claude.py` (der Weg von INSTALLIEREN.bat,
INSTALLIEREN.command und installer/install.sh) uebernimmt `env` seit v1.7.145; `installer/install.ps1`,
`installer/setup_gui.py` und `switch_mode.py` bauten den Eintrag jedes Mal neu.

Fund im selben Block von install.ps1: ohne Konfigurationsdatei oder ohne "mcpServers" in ihr schrieb das Skript
KEINEN PBP-Eintrag, meldete aber "geschrieben" (ein per Add-Member angehaengter Eintrag steht bei einer
Hashtable nicht im JSON).

EINE Regel fuer alle Schreiber (wie `_setup_claude.eintrag_bauen`): was im bisherigen `env` steht, bleibt;
`BA_DATA_DIR` wird nur gesetzt, wenn keiner da ist; `PYTHONPATH` folgt immer der Installation. Ein Kommentar
"dieselbe Logik wie" haelt nichts zusammen (L1-L3), deshalb reichen die Tests JEDEM Schreiber dieselbe
Beispielkonfiguration und verlangen dasselbe Ergebnis.

Dazu der ECHTE Schritt 7 von install.ps1 als Ganzes (nur unter Windows, mit Attrappen fuer Kopieren und Loeschen): die
Funktion allein beweist nicht, dass der Schritt sie mit den richtigen Variablen aufruft.

Nichts davon beruehrt die echte Konfiguration: Pfade kommen aus tmp_path, Umgebungsvariablen aus monkeypatch,
und vor jedem Schreiben steht eine Isolationspruefung.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0
BOM = b"\xef\xbb\xbf"
SCHLUESSEL = "nur-ein-testwert"  # kein echter Schluessel

# Der fremde Server traegt einen Pfad mit Umlaut, scharfem s und U+0142: Benutzernamen sehen so aus (L44), und ein Schreiber,
# der die Datei in der falschen Kodierung liest, zerlegt sie. Als Escapes geschrieben, damit die Quelle ASCII bleibt.
FREMDER_SERVER = {"command": "npx", "args": ["-y", "server-filesystem", "C:/Beispiel/M\u00fcller-Stra\u00dfe \u0142"]}
EINSTELLUNGEN = {"theme": "dark", "quickEntryShortcut": "Ctrl+Alt+Space"}
ALT = {
    "mcpServers": {
        "filesystem": FREMDER_SERVER,
        "bewerbungs-assistent": {
            "command": "C:/alt/python.exe", "args": ["-m", "bewerbungs_assistent"],
            "env": {"BA_DATA_DIR": "D:/MeineBewerbungen", "PBP_ANTHROPIC_API_KEY": SCHLUESSEL,
                    "BA_DASHBOARD_PORT": "8300", "PYTHONPATH": "C:/alt/src"},
        },
    },
    "preferences": EINSTELLUNGEN,
}


# -- Hilfen -------------------------------------------------------------

def _laden(name, pfad):
    spec = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _legen(cp, inhalt, bom=False):
    """Legt die Ausgangsdatei ab. `inhalt`: dict, roher Text oder None (keine Datei)."""
    if inhalt is None:
        return
    cp.parent.mkdir(parents=True, exist_ok=True)
    roh = inhalt if isinstance(inhalt, str) else json.dumps(inhalt, indent=2, ensure_ascii=False)
    cp.write_bytes((BOM if bom else b"") + roh.encode("utf-8"))


def _lesen(cp):
    return json.loads(Path(cp).read_bytes().decode("utf-8-sig"))


@pytest.fixture
def heim(tmp_path, monkeypatch):
    """Eine fremde Benutzerumgebung: nichts der echten Claude-Konfiguration ist erreichbar."""
    h = tmp_path / "home"
    (h / "AppData" / "Roaming").mkdir(parents=True)
    (h / "AppData" / "Local").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.setenv("APPDATA", str(h / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(h / "AppData" / "Local"))
    assert os.path.expanduser("~").startswith(str(h)), "Umgebung nicht isoliert"
    return h


def _isoliert(pfad, heim):
    assert str(heim) in str(pfad), f"Konfiguration nicht isoliert: {pfad}"


# -- Die Schreiber: je einer, alle mit derselben Rueckgabe -------------
# Jeder liefert (neue_konfiguration, erwarteter_python, erwarteter_suchpfad). suchpfad None = der Schreiber setzt
# keinen PYTHONPATH (die GUI-Installation ist editierbar, sie braucht keinen).

def _schreiber_setup_claude(tmp_path, heim, monkeypatch, inhalt, bom):
    sc = _laden("setup_claude_1238", ROOT / "_setup_claude.py")
    cp = heim / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    _isoliert(cp, heim)
    _legen(cp, inhalt, bom)
    assert sc.config_schreiben(str(cp), "C:/neu/python.exe", "C:/neu/src", "C:/Standard/data")
    return _lesen(cp), "C:/neu/python.exe", "C:/neu/src"


def _schreiber_setup_claude_skript(tmp_path, heim, monkeypatch, inhalt, bom):
    """Der echte Aufruf von INSTALLIEREN.bat, INSTALLIEREN.command und installer/install.sh."""
    sc = _laden("setup_claude_1238_skript", ROOT / "_setup_claude.py")
    cp = Path(sc.get_claude_config_paths()[0])
    _isoliert(cp, heim)
    _legen(cp, inhalt, bom)
    _modus, python_exe, src_dir, _daten = sc.detect_mode(str(ROOT))
    r = subprocess.run([sys.executable, str(ROOT / "_setup_claude.py")], env=dict(os.environ),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=OHNE_FENSTER)
    assert r.returncode == 0, r.stdout + r.stderr
    return _lesen(cp), python_exe, src_dir


def _schreiber_switch_mode(tmp_path, heim, monkeypatch, inhalt, bom):
    monkeypatch.syspath_prepend(str(ROOT))  # `from _setup_claude import ...` liegt neben dem Skript
    sm = _laden("switch_mode_1238", ROOT / "switch_mode.py")
    cp = Path(sm.CONFIG_PATH)
    _isoliert(cp, heim)
    py = tmp_path / "dev" / "python.exe"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("", encoding="utf-8")
    src = tmp_path / "dev" / "src"
    (src / "bewerbungs_assistent").mkdir(parents=True, exist_ok=True)
    (src / "bewerbungs_assistent" / "__init__.py").write_text('__version__ = "0.0.0"\n', encoding="utf-8")
    sm.MODES["dev"].update(python=str(py), src=str(src), data_dir=str(tmp_path / "daten"))
    _legen(cp, inhalt, bom)
    sm.switch_to("dev")
    return _lesen(cp), str(py), str(src)


def _setup_gui_laden(monkeypatch):
    """Das Modul bricht ohne tkinter mit sys.exit ab und soll hier nie ein Fenster zeigen: eine Attrappe."""
    tk = types.ModuleType("tkinter")
    for teil in ("ttk", "filedialog", "messagebox"):
        unter = types.ModuleType(f"tkinter.{teil}")
        setattr(tk, teil, unter)
        monkeypatch.setitem(sys.modules, f"tkinter.{teil}", unter)
    monkeypatch.setitem(sys.modules, "tkinter", tk)
    return _laden("setup_gui_1238", ROOT / "installer" / "setup_gui.py")


def _schreiber_setup_gui(tmp_path, heim, monkeypatch, inhalt, bom):
    gui = _setup_gui_laden(monkeypatch)
    cp = heim / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    _isoliert(cp, heim)
    _legen(cp, inhalt, bom)
    protokoll = []
    ich = types.SimpleNamespace(_log=lambda text, art="info": protokoll.append((art, text)))
    gui.InstallerApp._configure_claude(ich, "C:/neu/.venv/Scripts/python.exe", "C:/Standard/BewerbungsAssistent")
    assert not [p for p in protokoll if p[0] == "warn"], protokoll
    return _lesen(cp), "C:/neu/.venv/Scripts/python.exe", None


# -- install.ps1: die Funktion wird aus der Datei gezogen und in PowerShell ausgefuehrt ---

def _powershell():
    for name in (("powershell", "pwsh") if sys.platform == "win32" else ("pwsh", "powershell")):
        pfad = shutil.which(name)
        if pfad:
            return pfad
    return None


def _install_ps1_text():
    return (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8")


STUB_KENNZEICHEN = "ist VERALTET und tut nichts mehr"  # Kopfzeile des Stubs der 1.8-Linie (#1149)


def _install_ps1_voll():
    """True: der volle PowerShell-Installer (Stable-Linie). False: der Stub der 1.8-Linie (#1149, 'veraltet'), der nichts
    mehr tut und die Konfiguration nicht anfasst. Der Stub wird an SEINEM Text erkannt, nicht daran, dass die Funktion fehlt:
    fehlt sie im vollen Installer (alter Stand, ausgebaut), muessen die Tests rot werden, nicht still ueberspringen."""
    return STUB_KENNZEICHEN not in _install_ps1_text()


def _ps_funktion():
    m = re.search(r"# BEGIN MCP-EINTRAG.*?# END MCP-EINTRAG", _install_ps1_text(), re.S)
    assert m, "install.ps1: der Abschnitt MCP-EINTRAG fehlt"
    return m.group(0)


def _ps_oder_ueberspringen():
    """PowerShell, wenn es etwas auszufuehren gibt; sonst Ueberspringen mit Grund."""
    if not _install_ps1_voll():
        pytest.skip("install.ps1 ist ein Stub (veraltet, #1149): es gibt nichts auszufuehren")
    ps = _powershell()
    if not ps:
        pytest.skip("weder powershell noch pwsh vorhanden")
    return ps


def _q(wert):
    return "'" + str(wert).replace("'", "''") + "'"


def _ps_lauf(tmp_path, cp, python, suchpfad, daten):
    """Fuehrt Write-PbpClaudeConfig aus install.ps1 aus. Gibt (Ausgabe, Rueckgabe-True) zurueck."""
    ps = _ps_oder_ueberspringen()
    skript = (
        "$ErrorActionPreference = 'Stop'\n"
        "function Write-Info($m) { Write-Host \"INFO: $m\" }\n"
        "function Write-Warn($m) { Write-Host \"WARN: $m\" }\n"
        + _ps_funktion() + "\n"
        f"$r = Write-PbpClaudeConfig -Pfad {_q(cp)} -Python {_q(python)} -Src {_q(suchpfad)} -DataDir {_q(daten)}\n"
        "if ($r -is [bool]) { Write-Host \"ERGEBNIS: $r\" } else { Write-Host \"ERGEBNIS: kein einzelner Wahrheitswert\" }\n"
    )
    datei = tmp_path / "lauf.ps1"
    datei.write_bytes(BOM + skript.encode("utf-8"))  # mit BOM: Windows PowerShell 5.1 liest sonst als ANSI
    befehl = [ps, "-NoProfile", "-NonInteractive"]
    if sys.platform == "win32":
        befehl += ["-ExecutionPolicy", "Bypass"]
    r = subprocess.run(befehl + ["-File", str(datei)], capture_output=True, timeout=180,
                       creationflags=OHNE_FENSTER)
    aus = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    return aus, "ERGEBNIS: True" in aus


def _schreiber_install_ps1(tmp_path, heim, monkeypatch, inhalt, bom):
    cp = heim / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    _isoliert(cp, heim)
    _legen(cp, inhalt, bom)
    aus, geprueft = _ps_lauf(tmp_path, cp, "C:/neu/python.exe", "C:/neu/src", "C:/Standard/data")
    assert geprueft, aus
    return _lesen(cp), "C:/neu/python.exe", "C:/neu/src"


SCHREIBER = {
    "setup_claude": _schreiber_setup_claude,
    "setup_claude_skript": _schreiber_setup_claude_skript,
    "switch_mode": _schreiber_switch_mode,
    "setup_gui": _schreiber_setup_gui,
    "install_ps1": _schreiber_install_ps1,
}
alle_schreiber = pytest.mark.parametrize("schreiber", list(SCHREIBER))


def _pruefe_bleibt(neu, python, suchpfad):
    """Das gemeinsame Verhalten: Fremdes bleibt, Eigenes im env bleibt, nur die eigenen Schluessel folgen."""
    assert neu["mcpServers"]["filesystem"] == FREMDER_SERVER, "ein fremder Server wurde veraendert"
    assert neu["preferences"] == EINSTELLUNGEN, "fremde Einstellungen wurden veraendert"
    eintrag = neu["mcpServers"]["bewerbungs-assistent"]
    assert eintrag["command"] == python
    assert eintrag["args"][0] == "-m"
    env = eintrag["env"]
    assert env["PBP_ANTHROPIC_API_KEY"] == SCHLUESSEL, "der Schluessel des API-Wegs ging verloren"
    assert env["BA_DASHBOARD_PORT"] == "8300"
    assert env["BA_DATA_DIR"] == "D:/MeineBewerbungen", "ein verlegter Datenordner ging verloren"
    if suchpfad is None:
        assert "PYTHONPATH" not in env, "ein alter PYTHONPATH wuerde den alten Programmstand laden"
    else:
        assert env["PYTHONPATH"] == suchpfad, "PYTHONPATH muss der Installation folgen"


# -- Das Verhalten, fuer jeden Schreiber -------------------------------

@alle_schreiber
def test_eigene_env_bleibt(schreiber, tmp_path, heim, monkeypatch):
    """DER Fall aus #1238: Schluessel, Datenordner und Port unter env ueberleben den Installerlauf."""
    neu, python, suchpfad = SCHREIBER[schreiber](tmp_path, heim, monkeypatch, ALT, False)
    _pruefe_bleibt(neu, python, suchpfad)


@alle_schreiber
def test_auch_eine_datei_mit_bom_wird_gelesen(schreiber, tmp_path, heim, monkeypatch):
    """Windows PowerShell 5.1 (und der Deinstaller bis v1.7.144) schreiben ein BOM; die Datei gilt nicht als defekt."""
    neu, python, suchpfad = SCHREIBER[schreiber](tmp_path, heim, monkeypatch, ALT, True)
    _pruefe_bleibt(neu, python, suchpfad)


@alle_schreiber
def test_ein_zweiter_lauf_aendert_nichts(schreiber, tmp_path, heim, monkeypatch):
    """Ueberinstallieren ueber das Ergebnis des ersten Laufs: dasselbe, nichts geht beim zweiten Mal verloren."""
    erst, _, _ = SCHREIBER[schreiber](tmp_path, heim, monkeypatch, ALT, False)
    zweit, python, suchpfad = SCHREIBER[schreiber](tmp_path, heim, monkeypatch, erst, False)
    assert zweit == erst
    _pruefe_bleibt(zweit, python, suchpfad)


@alle_schreiber
def test_ohne_alten_eintrag_gelten_die_vorgaben(schreiber, tmp_path, heim, monkeypatch):
    ohne = {"mcpServers": {"filesystem": FREMDER_SERVER}, "preferences": EINSTELLUNGEN}
    neu, python, suchpfad = SCHREIBER[schreiber](tmp_path, heim, monkeypatch, ohne, False)
    assert neu["mcpServers"]["filesystem"] == FREMDER_SERVER
    assert neu["preferences"] == EINSTELLUNGEN
    env = neu["mcpServers"]["bewerbungs-assistent"]["env"]
    assert env["BA_DATA_DIR"], "ohne alten Eintrag braucht BA_DATA_DIR den Vorgabewert"
    assert env.get("PYTHONPATH") == suchpfad
    assert neu["mcpServers"]["bewerbungs-assistent"]["command"] == python


@alle_schreiber
def test_ein_alter_eintrag_ohne_env_bekommt_die_vorgaben(schreiber, tmp_path, heim, monkeypatch):
    alt = {"mcpServers": {"bewerbungs-assistent": {"command": "C:/alt/python.exe", "args": ["-m", "x"]}}}
    neu, python, suchpfad = SCHREIBER[schreiber](tmp_path, heim, monkeypatch, alt, False)
    eintrag = neu["mcpServers"]["bewerbungs-assistent"]
    assert eintrag["command"] == python
    assert eintrag["env"]["BA_DATA_DIR"]
    assert eintrag["env"].get("PYTHONPATH") == suchpfad


@alle_schreiber
def test_ohne_konfigurationsdatei_steht_der_eintrag_danach_drin(schreiber, tmp_path, heim, monkeypatch):
    """Frische Maschine: es gibt noch keine Datei. install.ps1 schrieb hier `mcpServers: {}` und meldete Erfolg."""
    neu, python, suchpfad = SCHREIBER[schreiber](tmp_path, heim, monkeypatch, None, False)
    eintrag = neu["mcpServers"]["bewerbungs-assistent"]
    assert eintrag["command"] == python
    assert eintrag["env"]["BA_DATA_DIR"]
    assert eintrag["env"].get("PYTHONPATH") == suchpfad


@alle_schreiber
def test_eine_datei_ohne_mcpservers_bekommt_den_eintrag_und_behaelt_ihr_uebriges(schreiber, tmp_path, heim, monkeypatch):
    """Claude Desktop legt die Datei oft nur mit `preferences` an. install.ps1 verlor hier den PBP-Eintrag."""
    neu, python, suchpfad = SCHREIBER[schreiber](tmp_path, heim, monkeypatch, {"preferences": EINSTELLUNGEN}, False)
    assert neu["preferences"] == EINSTELLUNGEN
    assert neu["mcpServers"]["bewerbungs-assistent"]["command"] == python
    assert neu["mcpServers"]["bewerbungs-assistent"]["env"].get("PYTHONPATH") == suchpfad


# -- Nur PowerShell: ungewoehnliche Dateien ----------------------------

@pytest.mark.parametrize("name,inhalt", [
    ("leer", ""),
    ("liste", "[]"),
    ("text", '"nur ein Text"'),
    ("zahl", "5"),
    ("defekt", '{ "mcpServers": { '),
    ("mcpservers_ist_eine_liste", '{"mcpServers": [], "preferences": {"theme": "dark"}}'),
    ("env_ist_text", '{"mcpServers": {"bewerbungs-assistent": {"command": "x", "env": "kaputt"}}}'),
])
def test_ps_ungewoehnliche_dateien_enden_mit_einem_geprueften_eintrag(name, inhalt, tmp_path):
    """Nie ein Absturz, nie ein Eintrag, der nur behauptet wird: am Ende steht PBP in der Datei."""
    cp = tmp_path / "Claude" / "claude_desktop_config.json"
    _legen(cp, inhalt)
    aus, geprueft = _ps_lauf(tmp_path, cp, "C:/neu/python.exe", "C:/neu/src", "C:/Standard/data")
    assert geprueft, aus
    eintrag = _lesen(cp)["mcpServers"]["bewerbungs-assistent"]
    assert eintrag["env"] == {"BA_DATA_DIR": "C:/Standard/data", "PYTHONPATH": "C:/neu/src"}
    assert eintrag["command"] == "C:/neu/python.exe"


def test_ps_die_probe_meldet_einen_fehlenden_eintrag(tmp_path):
    """Die Probe liest die Datei nach dem Schreiben noch einmal: ohne Eintrag darf die Funktion nicht True melden."""
    ps = _ps_oder_ueberspringen()
    cp = tmp_path / "Claude" / "claude_desktop_config.json"
    funktion = _ps_funktion()
    # Ein untergeschobenes Schreiben, das den Eintrag weglaesst: die Probe muss es merken.
    kaputt = funktion.replace("[System.IO.File]::WriteAllText($Pfad, $json,",
                              "[System.IO.File]::WriteAllText($Pfad, '{\"mcpServers\": {}}',")
    assert kaputt != funktion, "Schreibzeile in install.ps1 nicht gefunden"
    skript = ("$ErrorActionPreference = 'Stop'\nfunction Write-Info($m) {}\nfunction Write-Warn($m) {}\n" + kaputt + "\n"
              f"$r = Write-PbpClaudeConfig -Pfad {_q(cp)} -Python 'p' -Src 's' -DataDir 'd'\n"
              "Write-Host \"ERGEBNIS: $r\"\n")
    datei = tmp_path / "lauf.ps1"
    datei.write_bytes(BOM + skript.encode("utf-8"))
    befehl = [ps, "-NoProfile", "-NonInteractive"] + (["-ExecutionPolicy", "Bypass"] if sys.platform == "win32" else [])
    r = subprocess.run(befehl + ["-File", str(datei)], capture_output=True, timeout=180, creationflags=OHNE_FENSTER)
    aus = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    assert "ERGEBNIS: False" in aus, aus


@pytest.mark.skipif(sys.platform != "win32", reason="Schritt 7 baut Windows-Pfade (%APPDATA%\\Claude); die Funktion laeuft ueberall")
@pytest.mark.parametrize("vorher", [ALT, None], ids=["mit_eigenem_env", "ohne_konfigurationsdatei"])
def test_ps_schritt_7_als_ganzes_traegt_ein_und_laesst_das_env_stehen(vorher, tmp_path, heim):
    """Die Funktion allein beweist nicht, dass Schritt 7 sie richtig aufruft (Variablennamen, Reihenfolge). Der ECHTE
    Schritt 7 aus der Datei laeuft hier mit Attrappen fuer Kopieren und Loeschen. Schutz gegen das echte Profil, dreifach:
    APPDATA und LOCALAPPDATA zeigen in den Temp-Ordner (das Skript bricht sonst ab), Copy-Item und Remove-Item sind
    Attrappen, und der Test prueft die Pfade vorher selbst."""
    ps = _ps_oder_ueberspringen()
    cp = heim / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    _isoliert(cp, heim)
    _legen(cp, vorher)
    text = _install_ps1_text()
    m = re.search(r"# \S+ STEP 7:.*?(?=# \S+ STEP 8:)", text, re.S)
    assert m, "install.ps1: Schritt 7 nicht gefunden"
    skript = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$erlaubt = {_q(heim)}\n"
        "if (-not ($env:APPDATA.StartsWith($erlaubt) -and $env:LOCALAPPDATA.StartsWith($erlaubt))) { throw 'NICHT ISOLIERT' }\n"
        "function Write-Step($a, $b, $c) { }\n"
        "function Write-OK($m) { Write-Host \"OK: $m\" }\n"
        "function Write-Info($m) { Write-Host \"INFO: $m\" }\n"
        "function Write-Warn($m) { Write-Host \"WARN: $m\" }\n"
        "function Copy-Item { param($Path, $Destination, [switch]$Recurse) New-Item -ItemType Directory -Force -Path $Destination | Out-Null }\n"
        "function Remove-Item { param($Path, [switch]$Recurse, [switch]$Force) Write-Host \"WEG: $Path\" }\n"
        "$totalSteps = 8\n"
        f"$projectDir = {_q(tmp_path / 'projekt')}\n"
        + m.group(0)
    )
    datei = tmp_path / "schritt7.ps1"
    datei.write_bytes(BOM + skript.encode("utf-8"))
    befehl = [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(datei)]
    r = subprocess.run(befehl, capture_output=True, timeout=180, creationflags=OHNE_FENSTER)
    aus = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    assert r.returncode == 0, aus
    assert "OK: Claude Desktop MCP-Konfiguration geschrieben" in aus, aus
    assert "WARN:" not in aus, aus
    daten = heim / "AppData" / "Local" / "BewerbungsAssistent"
    eintrag = _lesen(cp)["mcpServers"]["bewerbungs-assistent"]
    assert os.path.normcase(eintrag["command"]) == os.path.normcase(str(daten / "python" / "Scripts" / "python.exe"))
    env = eintrag["env"]
    assert os.path.normcase(env["PYTHONPATH"]) == os.path.normcase(str(daten / "src"))
    if vorher is None:
        assert os.path.normcase(env["BA_DATA_DIR"]) == os.path.normcase(str(daten))
    else:
        assert env["BA_DATA_DIR"] == "D:/MeineBewerbungen"
        assert env["PBP_ANTHROPIC_API_KEY"] == SCHLUESSEL
        assert _lesen(cp)["mcpServers"]["filesystem"] == FREMDER_SERVER


# -- Wer schreibt die Konfiguration? Eine Liste, die man nicht vergisst -

# Dateien, die `mcpServers` anfassen, und was sie tun. Kommt eine neue hinzu, schlaegt der Test an: erst hier
# einordnen und einen Fall in SCHREIBER ergaenzen, dann ist der Verlust von env fuer sie ausgeschlossen.
SCHREIBT = {"_setup_claude.py", "installer/setup_gui.py", "switch_mode.py"}
# install.ps1 schreibt in der Stable-Linie (voller Installer), in der 1.8-Linie ist es ein Stub (#1149) und nennt die Konfiguration nicht.
SCHREIBT_NUR_VOLL = {"installer/install.ps1"}
ENTFERNT_NUR = {"DEINSTALLIEREN.bat", "installer/deinstallieren.sh"}
TEXTENDUNGEN = {".py", ".ps1", ".sh", ".bat", ".command", ".js", ".mjs", ".cmd"}


def _dateien_mit_mcpservers():
    gefunden = set()
    for ordner in (ROOT, ROOT / "installer", ROOT / "src", ROOT / "scripts", ROOT / "tools", ROOT / "plugins"):
        if not ordner.is_dir():
            continue
        dateien = ordner.iterdir() if ordner == ROOT else ordner.rglob("*")
        for p in dateien:
            if not p.is_file() or p.suffix.lower() not in TEXTENDUNGEN or "node_modules" in p.parts:
                continue
            if p.relative_to(ROOT).as_posix().startswith("tests/"):
                continue
            if "mcpServers" in p.read_text(encoding="utf-8", errors="replace"):
                gefunden.add(p.relative_to(ROOT).as_posix())
    return gefunden


def test_jeder_schreiber_der_konfiguration_ist_erfasst():
    unbekannt = _dateien_mit_mcpservers() - SCHREIBT - SCHREIBT_NUR_VOLL - ENTFERNT_NUR
    assert not unbekannt, (
        f"{sorted(unbekannt)} beruehren `mcpServers`: einordnen (SCHREIBT oder ENTFERNT_NUR) und, wenn sie den "
        "Eintrag schreiben, einen Fall in SCHREIBER ergaenzen (#1238: env des Menschen muss bleiben)")


def test_die_erfassten_schreiber_gibt_es_noch():
    """Eine Liste, die auf verschwundene Dateien zeigt, prueft nichts mehr."""
    gefunden = _dateien_mit_mcpservers()
    assert SCHREIBT <= gefunden, sorted(SCHREIBT - gefunden)
    assert ENTFERNT_NUR <= gefunden, sorted(ENTFERNT_NUR - gefunden)
    assert ("installer/install.ps1" in gefunden) == _install_ps1_voll(), "install.ps1: voller Installer und Liste passen nicht zusammen"


# Der AUFRUF zaehlt, nicht jede Erwaehlung des Namens (Hinweiszeilen nennen ihn auch, dort steht er in maskierten
# Anfuehrungszeichen oder ohne). `$PYTHON` steht mit und ohne Anfuehrungszeichen (der Release-Zweig quotet es, #1216),
# am Zeilenanfang oder in einer Befehlsersetzung `$(...)` (#1219: dort wird die Ausgabe gelesen).
UNIX_AUFRUF = r'(?:^|[\s(])"?\$PYTHON"?\s+"\$PROJECT_DIR/_setup_claude\.py"'
AUFRUF = {
    "installer/install.sh": UNIX_AUFRUF,
    "INSTALLIEREN.command": UNIX_AUFRUF,
    "INSTALLIEREN.bat": r'^"%PYTHON%"\s+"%BASEDIR%\\_setup_claude\.py"',
}


@pytest.mark.parametrize("datei", list(AUFRUF))
def test_diese_installer_rufen_setup_claude_auf_und_schreiben_nichts_selbst(datei):
    """macOS, Linux und der Doppelklick-Weg unter Windows gehen ueber _setup_claude.py (env bleibt, v1.7.145)."""
    text = (ROOT / datei).read_text(encoding="utf-8", errors="replace")
    assert re.search(AUFRUF[datei], text, re.M), f"{datei} ruft _setup_claude.py nicht mehr auf"
    assert "mcpServers" not in text, f"{datei} baut den Eintrag selbst"


def test_der_weg_des_auto_updates_beruehrt_die_claude_konfiguration_nicht():
    """Das Programm selbst schreibt nie in die Konfiguration von Claude Desktop; das tun nur die Installer."""
    treffer = []
    for p in (ROOT / "src").rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        if "mcpServers" in text or "claude_desktop_config" in text:
            treffer.append(p.relative_to(ROOT).as_posix())
    assert not treffer, f"ein Programmteil beruehrt die Claude-Konfiguration: {treffer}; env des Menschen muss bleiben"


def test_install_ps1_stub_fasst_die_konfiguration_nicht_an():
    """Ab 1.8 ist install.ps1 ein Stub (#1149): er weist auf INSTALLIEREN.bat und beruehrt die Konfiguration nie."""
    if _install_ps1_voll():
        pytest.skip("voller Installer: die Funktionstests gelten")
    text = _install_ps1_text()
    assert "INSTALLIEREN.bat" in text
    for verboten in ("mcpServers", "claude_desktop_config", "ConvertTo-Json", "Add-Member"):
        assert verboten not in text, f"der Stub nennt {verboten}"


def test_install_ps1_baut_den_eintrag_nur_in_der_funktion():
    if not _install_ps1_voll():
        pytest.skip("install.ps1 ist ein Stub (veraltet, #1149)")
    text = _install_ps1_text()
    ausserhalb = text.replace(_ps_funktion(), "")
    assert "Write-PbpClaudeConfig -Pfad" in ausserhalb, "Schritt 7 ruft die Funktion nicht auf"
    assert 'Add-Member -NotePropertyName "bewerbungs-assistent"' not in ausserhalb, "ein zweiter Eintragsbau"
    assert "ConvertTo-Json" not in ausserhalb, "die Konfiguration wird ausserhalb der Funktion geschrieben"
