"""Praxisprobe 1.8 (05.10.2026), Teil Deinstallation: drei Funde auf einem frischen Windows 11 mit Claude aus dem Store.

PP9  Der Knopf „Deinstaller starten“ (Gefahrenzone) funktionierte unter Windows nie. `starten()` setzte DETACHED_PROCESS und
     CREATE_NEW_CONSOLE zugleich; CreateProcess lehnt das ab („OSError: [WinError 87]“). Der Fehler wurde gefangen, die
     Oberfläche sagte „Kein Terminal gefunden“. Die Tests mockten `Popen` und prüften die Flags nie gegen das Betriebssystem.
PP11 Der Deinstaller las nur `%APPDATA%\\Claude\\claude_desktop_config.json`. Der Installer schreibt den Eintrag aber auch in die
     Store-Pakete (`Packages\\Claude_*\\LocalCache\\Roaming\\Claude`) — und genau die liest die Store-Fassung. Nach „PBP komplett
     deinstallieren“ blieb der Eintrag stehen; Claude meldete danach bei jedem Start einen Server ohne Programm.
PP12 Das Konsolenfenster des Dashboards (`cmd /K "Dashboard starten.bat"`) blieb nach der Deinstallation stehen.
PP13 (Gegenprobe desselben Tages) Gestartet über den Knopf im Dashboard, meldete der Deinstaller in Schritt [5/7], der App-Ordner
     „konnte nicht entfernt werden“, und ein leerer Ordner blieb liegen. Ursache: das neue Fenster hatte den App-Ordner als
     Arbeitsordner (`start /D <Ordner der .bat>`), und die cmd.exe wartet auf die nach %TEMP% verschobene Kopie — ein Prozess hält
     seinen Arbeitsordner fest. Gilt genauso für den Doppelklick auf die .bat im App-Ordner.
PP16 (Gegenprobe) Die nach %TEMP% verschobene Kopie des Deinstallers (rund 15 KB) blieb liegen: Schritt [5/7] hat die Ursprungsdatei
     gelöscht, und die wartende cmd.exe bricht vor dem `del` in der NÄCHSTEN Zeile still ab, weil sie die Datei nicht mehr lesen kann.
PP17 (Gegenprobe) Die Konfiguration von Claude wurde in der Formatierung von Windows PowerShell neu geschrieben (rund siebenmal so
     groß, Inhalt gleich) und behielt `"mcpServers": {}`. Jetzt wird nur der Eintrag aus dem Text genommen; der Rest bleibt Byte für Byte.

Die Verhaltenstests führen die echten PowerShell-Zeilen aus der BAT-Datei aus (Windows PowerShell 5.1); APPDATA und LOCALAPPDATA
zeigen dabei auf einen Temp-Ordner. QA-Isolation: nie gegen die echte Claude-Konfiguration dieses Rechners.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from bewerbungs_assistent.services import deinstallation

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "DEINSTALLIEREN.bat"
POWERSHELL = shutil.which("powershell")
nur_windows = pytest.mark.skipif(
    os.name != "nt" or not POWERSHELL, reason="braucht Windows PowerShell 5.1")

DETACHED_PROCESS = 0x00000008
CREATE_NEW_CONSOLE = 0x00000010


def _bat() -> str:
    return BAT.read_text(encoding="utf-8", errors="replace")


# ── PP9: die Flags, mit denen der Deinstaller-Knopf ein Fenster öffnet ─────────────────────────────

def _starten_mit_aufzeichnung(monkeypatch, tmp_path, popen):
    bat = tmp_path / "DEINSTALLIEREN.bat"
    bat.write_text("@echo off\r\n", encoding="utf-8")
    monkeypatch.setattr(deinstallation, "_system", lambda: "Windows")
    monkeypatch.setattr(deinstallation, "deinstaller_pfad", lambda: bat)
    monkeypatch.setattr(subprocess, "Popen", popen)
    return deinstallation.starten()


def test_pp9_unter_windows_schliessen_sich_abgeloest_und_neue_konsole_nicht_aus(monkeypatch, tmp_path):
    """Die Regel des Betriebssystems, als Maske geprüft: beides zugleich ist ein ungültiger Parameter."""
    gesehen = {}

    def _popen(cmd, **kw):
        gesehen.update(kw)
        gesehen["cmd"] = cmd
        return object()

    erg = _starten_mit_aufzeichnung(monkeypatch, tmp_path, _popen)
    flags = gesehen["creationflags"]
    assert not (flags & DETACHED_PROCESS and flags & CREATE_NEW_CONSOLE), hex(flags)
    assert flags & DETACHED_PROCESS, "der Deinstaller soll in einem eigenen Prozess-Baum laufen"
    assert erg["status"] == "gestartet"
    # Das Fenster öffnet `start`, nicht der äußere cmd.exe
    assert gesehen["cmd"][:4] == ["cmd.exe", "/c", "start", ""]


@nur_windows
def test_pp9_das_betriebssystem_nimmt_genau_diese_flags_an(monkeypatch, tmp_path):
    """Der Test, der gefehlt hat: dieselben Flags, aber ein harmloser Befehl, wirklich gestartet. Mit der alten Maske wirft das
    `OSError: [WinError 87]`. Ohne neue Konsole öffnet sich dabei kein Fenster."""
    echtes_popen = subprocess.Popen
    gestartet = []

    def _popen(cmd, **kw):
        p = echtes_popen(["cmd.exe", "/c", "exit", "0"], **kw)
        gestartet.append(p)
        return p

    erg = _starten_mit_aufzeichnung(monkeypatch, tmp_path, _popen)
    assert erg["status"] == "gestartet", erg
    assert gestartet and gestartet[0].wait(timeout=30) == 0


@nur_windows
def test_pp9_die_alte_maske_wird_vom_betriebssystem_abgelehnt():
    """Belegt die Ursache und hält den Test oben ehrlich: wäre die Maske erlaubt, wäre er wertlos."""
    with pytest.raises(OSError):
        subprocess.Popen(["cmd.exe", "/c", "exit", "0"],
                         creationflags=DETACHED_PROCESS | CREATE_NEW_CONSOLE | 0x00000200)


def test_pp9_scheitert_der_start_sagt_der_hinweis_warum_und_nennt_den_doppelklick(monkeypatch, tmp_path):
    def _popen(cmd, **kw):
        raise OSError(87, "Falscher Parameter")

    erg = _starten_mit_aufzeichnung(monkeypatch, tmp_path, _popen)
    assert erg["status"] == "befehl" and "Falscher Parameter" in erg["fehler"]
    assert "DEINSTALLIEREN.bat" in erg["hinweis"] and "Kein Terminal" not in erg["hinweis"]
    assert erg["befehl"]


def test_pp9_die_oberflaeche_zeigt_den_hinweis_des_servers():
    jsx = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert "setBefehlHinweis(result.hinweis" in jsx
    assert "{befehlHinweis}" in jsx


# ── PP13: ein Prozess hält seinen Arbeitsordner fest ───────────────────────────────────────────────

def test_pp13_das_neue_fenster_startet_nicht_im_ordner_der_bat(monkeypatch, tmp_path):
    """`start /D <Ordner>` macht den Ordner zum Arbeitsordner der neuen cmd.exe. Die wartet auf die verschobene Kopie des
    Deinstallers und hält den App-Ordner damit fest, den Schritt [5/7] löschen will."""
    gesehen = {}

    def _popen(cmd, **kw):
        gesehen["cmd"] = cmd
        return object()

    _starten_mit_aufzeichnung(monkeypatch, tmp_path, _popen)       # die .bat liegt in tmp_path
    cmd = gesehen["cmd"]
    assert "/D" in cmd, "ohne /D erbt das Fenster den Arbeitsordner des Dashboards"
    ordner = Path(cmd[cmd.index("/D") + 1])
    assert ordner != tmp_path, "nie der Ordner der .bat"
    assert ordner == Path(tempfile.gettempdir())


def test_pp13_die_bat_verlaesst_ihren_ordner_bevor_sie_sich_verschiebt():
    """Der Doppelklick im App-Ordner hat denselben Arbeitsordner; deshalb reicht der Start-Parameter allein nicht."""
    zeilen = [z.strip() for z in _bat().splitlines()]
    block = zeilen[zeilen.index(":pbp_relocate"):zeilen.index(":pbp_main")]
    wechsel = next(i for i, z in enumerate(block) if z.lower().startswith("cd /d") and "%temp%" in z.lower())
    umzug = next(i for i, z in enumerate(block) if z.lower().startswith("cmd /c"))
    assert wechsel < umzug, "erst den Ordner wechseln, dann auf die verschobene Kopie warten"


def _umzugskopf() -> str:
    """Der Anfang der echten Datei bis vor `:pbp_main`: die Selbst-Verschiebung nach %TEMP%."""
    text = _bat()
    return text[:text.index("\n:pbp_main")]


@nur_windows
def test_pp13_nach_dem_umzug_laesst_sich_der_app_ordner_loeschen(tmp_path):
    """Der Fehler wörtlich, mit dem ECHTEN Anfang der Datei: Start wie im Praxisfall (Arbeitsordner = App-Ordner), dahinter ein
    Platzhalter, der tut, was Schritt [5/7] tut. Der echte Deinstaller läuft hier nie — alles liegt im Temp-Ordner des Tests."""
    lokal = tmp_path / "AppData" / "Local"
    app = lokal / "BewerbungsAssistent" / "app"
    app.mkdir(parents=True)
    temp = tmp_path / "Temp"
    temp.mkdir()
    marke = tmp_path / "ergebnis.txt"
    rumpf = [":pbp_main",
             f'rmdir /s /q "{app}" >nul 2>&1',
             f'if exist "{app}" (echo GESPERRT> "{marke}") else (echo WEG> "{marke}")',
             "exit /b 0"]
    skript = app / "DEINSTALLIEREN.bat"
    skript.write_bytes(("\r\n".join(_umzugskopf().splitlines() + [""] + rumpf) + "\r\n").encode("utf-8"))
    env = dict(os.environ, LOCALAPPDATA=str(lokal), TEMP=str(temp), TMP=str(temp))
    env.pop("PBP_DEINST_RELOCATED", None)
    # QA-Isolation: nichts davon zeigt auf die echte Installation dieses Rechners
    assert str(tmp_path) in env["LOCALAPPDATA"] and str(tmp_path) in env["TEMP"]
    subprocess.run(["cmd.exe", "/c", str(skript)], cwd=str(app), env=env, capture_output=True, timeout=60)
    assert marke.exists(), "der Platzhalter lief gar nicht — der Umzug hat nicht stattgefunden"
    assert marke.read_text().strip() == "WEG", "die wartende cmd.exe hält den App-Ordner als Arbeitsordner fest"
    assert not app.exists()


# ── PP16: die verschobene Kopie räumt sich selbst weg ──────────────────────────────────────────

def test_pp16_aufruf_aufraeumen_und_beenden_stehen_in_einer_zeile():
    """Eine Zeile wird vor dem Aufruf ganz gelesen; was in der NÄCHSTEN Zeile steht, liest cmd erst danach von der Platte."""
    zeilen = [z.strip() for z in _bat().splitlines()]
    block = zeilen[zeilen.index(":pbp_relocate"):zeilen.index(":pbp_main")]
    aufruf = next(z for z in block if z.lower().startswith("cmd /c"))
    assert "del /q" in aufruf.lower() and "pbp_reloc_bat" in aufruf.lower(), aufruf
    assert aufruf.lower().rstrip().endswith("exit /b 0"), aufruf
    assert not any(z.lower().startswith("del ") for z in block), "ein eigenes `del` in der nächsten Zeile läuft nie"


@nur_windows
def test_pp16_nach_der_deinstallation_liegt_keine_kopie_mehr_in_temp(tmp_path):
    """Mit dem ECHTEN Anfang der Datei: der Platzhalter löscht, wie Schritt [5/7], die Ursprungsdatei. Ohne die Reparatur bleibt die
    Kopie im Temp-Ordner liegen. Alles liegt im Temp-Ordner des Tests."""
    lokal = tmp_path / "AppData" / "Local"
    app = lokal / "BewerbungsAssistent" / "app"
    app.mkdir(parents=True)
    temp = tmp_path / "Temp"
    temp.mkdir()
    marke = tmp_path / "gelaufen.txt"
    skript = app / "DEINSTALLIEREN.bat"
    # `%PBP_BASEDIR%` zeigt in der verschobenen Kopie auf den Temp-Ordner (die Kopf-Zeilen setzen es neu), deshalb der volle Pfad
    rumpf = [":pbp_main",
             f'del /Q "{skript}"',
             f'echo ok> "{marke}"',
             "exit /b 0"]
    skript.write_bytes(("\r\n".join(_umzugskopf().splitlines() + [""] + rumpf) + "\r\n").encode("utf-8"))
    env = dict(os.environ, LOCALAPPDATA=str(lokal), TEMP=str(temp), TMP=str(temp))
    env.pop("PBP_DEINST_RELOCATED", None)
    assert str(tmp_path) in env["LOCALAPPDATA"] and str(tmp_path) in env["TEMP"]
    subprocess.run(["cmd.exe", "/c", str(skript)], cwd=str(app), env=env, capture_output=True, timeout=60)
    assert marke.exists(), "der Platzhalter lief nicht — der Umzug hat nicht stattgefunden"
    assert not skript.exists(), "ohne gelöschte Ursprungsdatei beweist der Test nichts"
    assert list(temp.glob("PBP-Deinstaller-*.bat")) == [], "die verschobene Kopie blieb liegen"


# ── PP11: die Store-Konfiguration ──────────────────────────────────────────────────────────────

def _befehl_entfernen() -> str:
    zeilen = _bat().splitlines()
    ab = next(i for i, z in enumerate(zeilen) if z.strip() == ":remove_claude_entry")
    zeile = next(z for z in zeilen[ab:] if "powershell" in z)
    start = zeile.index('-Command "') + len('-Command "')
    return zeile[start:zeile.index('" ', start)]


def _lauf(tmp_path):
    roaming, lokal = tmp_path / "AppData" / "Roaming", tmp_path / "AppData" / "Local"
    env = dict(os.environ, APPDATA=str(roaming), LOCALAPPDATA=str(lokal))
    # QA-Isolation: beide Ordner liegen im Temp-Verzeichnis dieses Tests
    assert str(tmp_path) in env["APPDATA"] and str(tmp_path) in env["LOCALAPPDATA"]
    return subprocess.run([POWERSHELL, "-ExecutionPolicy", "Bypass", "-NoProfile", "-Command", _befehl_entfernen()],
                          env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def _config(ordner: Path, mit_pbp=True, roh=None) -> Path:
    datei = ordner / "claude_desktop_config.json"
    datei.parent.mkdir(parents=True, exist_ok=True)
    daten = {"mcpServers": {"filesystem": {"command": "npx"}}, "preferences": {"theme": "dark"}}
    if mit_pbp:
        daten["mcpServers"]["bewerbungs-assistent"] = {"command": "C:/alt/python.exe", "args": ["-m", "bewerbungs_assistent"]}
    datei.write_bytes(roh if roh is not None else json.dumps(daten, indent=2).encode("utf-8"))
    return datei


def _eintraege(datei: Path) -> list:
    return sorted(json.loads(datei.read_bytes().decode("utf-8-sig"))["mcpServers"])


@nur_windows
def test_pp11_standardpfad_und_store_paket_werden_beide_bereinigt(tmp_path):
    std = _config(tmp_path / "AppData" / "Roaming" / "Claude")
    store = _config(tmp_path / "AppData" / "Local" / "Packages" / "Claude_pzs8sxrjxfjjc" / "LocalCache" / "Roaming" / "Claude")
    r = _lauf(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _eintraege(std) == ["filesystem"] and _eintraege(store) == ["filesystem"]
    assert json.loads(store.read_bytes().decode("utf-8"))["preferences"] == {"theme": "dark"}
    assert Path(str(store) + ".pbp-backup").is_file() and Path(str(std) + ".pbp-backup").is_file()
    assert not store.read_bytes().startswith(b"\xef\xbb\xbf")


@nur_windows
def test_pp11_der_fall_der_praxisprobe_nur_das_store_paket_hat_die_datei(tmp_path):
    """Auf dem Prüf-Rechner lag die Konfiguration NUR im Store-Paket; der Standardordner existierte vor der Installation nicht."""
    store = _config(tmp_path / "AppData" / "Local" / "Packages" / "Claude_pzs8sxrjxfjjc" / "LocalCache" / "Roaming" / "Claude")
    r = _lauf(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _eintraege(store) == ["filesystem"]


@nur_windows
def test_pp11_auch_der_andere_paketname_wird_gefunden(tmp_path):
    store = _config(tmp_path / "AppData" / "Local" / "Packages" / "AnthropicPBC.Claude_abc123" / "LocalCache" / "Roaming" / "Claude")
    assert _lauf(tmp_path).returncode == 0
    assert _eintraege(store) == ["filesystem"]


@nur_windows
def test_pp11_eine_unlesbare_store_datei_wird_gemeldet_und_nicht_angefasst(tmp_path):
    std = _config(tmp_path / "AppData" / "Roaming" / "Claude")
    kaputt = _config(tmp_path / "AppData" / "Local" / "Packages" / "Claude_x" / "LocalCache" / "Roaming" / "Claude",
                     roh=b'{"mcpServers": {"filesystem": ')
    original = kaputt.read_bytes()
    r = _lauf(tmp_path)
    assert r.returncode == 3, "der Mensch muss erfahren, dass hier noch von Hand aufzuräumen ist"
    assert kaputt.read_bytes() == original
    assert _eintraege(std) == ["filesystem"], "die lesbare Datei wird trotzdem bereinigt"


@nur_windows
def test_pp11_ohne_jede_datei_bleibt_es_bei_code_4(tmp_path):
    assert _lauf(tmp_path).returncode == 4


@nur_windows
def test_pp11_ohne_pbp_eintrag_wird_nichts_veraendert(tmp_path):
    std = _config(tmp_path / "AppData" / "Roaming" / "Claude", mit_pbp=False)
    store = _config(tmp_path / "AppData" / "Local" / "Packages" / "Claude_x" / "LocalCache" / "Roaming" / "Claude", mit_pbp=False)
    vorher = (std.read_bytes(), store.read_bytes())
    assert _lauf(tmp_path).returncode == 1
    assert (std.read_bytes(), store.read_bytes()) == vorher
    assert not Path(str(store) + ".pbp-backup").exists()


@nur_windows
def test_pp11_installer_und_deinstaller_kennen_dieselben_orte(tmp_path, monkeypatch):
    """Was `_setup_claude.py` schreibt, räumt der Deinstaller weg — gleiche Liste, nicht zwei, die auseinanderlaufen."""
    roaming, lokal = tmp_path / "AppData" / "Roaming", tmp_path / "AppData" / "Local"
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(lokal))
    for paket in ("Claude_pzs8sxrjxfjjc",):
        (lokal / "Packages" / paket / "LocalCache" / "Roaming" / "Claude").mkdir(parents=True)
    spec = importlib.util.spec_from_file_location("setup_claude_pruefling_pp11", ROOT / "_setup_claude.py")
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    geschrieben = [Path(p) for p in sc.get_claude_config_paths()]
    assert len(geschrieben) == 2, geschrieben
    for p in geschrieben:                               # der Installer legt den Eintrag in beide
        _config(p.parent)
    assert _lauf(tmp_path).returncode == 0
    assert all(_eintraege(p) == ["filesystem"] for p in geschrieben)


# ── PP12: das Konsolenfenster des Dashboards ───────────────────────────────────────────────────

def _prozessfilter() -> str:
    zeile = next(z for z in _bat().splitlines() if "Get-CimInstance Win32_Process" in z)
    von = zeile.index("Where-Object {") + len("Where-Object {")
    return zeile[von:zeile.index("} | ForEach-Object")].strip()


def test_pp12_der_deinstaller_schliesst_auch_das_dashboard_fenster():
    assert "Dashboard starten\\.bat" in _prozessfilter()


@nur_windows
def test_pp12_der_filter_trifft_nur_pbp_und_nie_den_deinstaller_selbst():
    faelle = {
        "python-pbp": ("python.exe", "python.exe -m bewerbungs_assistent", True),
        "python-fremd": ("python.exe", "python.exe meine_anwendung.py", False),
        "dashboard-fenster": ("cmd.exe", 'cmd.exe /K "C:\\Users\\x\\AppData\\Local\\BewerbungsAssistent\\app\\Dashboard starten.bat"', True),
        "deinstaller-selbst": ("cmd.exe", 'cmd.exe /c ""C:\\Temp\\PBP-Deinstaller-1.bat""', False),
        "fremdes-cmd": ("cmd.exe", "cmd.exe /c dir C:\\", False),
    }
    zeilen = "; ".join(
        "[pscustomobject]@{N='%s'; Name='%s'; CommandLine='%s'}" % (n, name, cl.replace("'", "''"))
        for n, (name, cl, _) in faelle.items())
    befehl = ("$o = @(%s); $o | Where-Object { %s } | ForEach-Object { $_.N }" % (zeilen.replace("; [", ", ["), _prozessfilter()))
    r = subprocess.run([POWERSHELL, "-NoProfile", "-Command", befehl], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    getroffen = set(r.stdout.split())
    assert getroffen == {n for n, (_, _, soll) in faelle.items() if soll}, getroffen


@nur_windows
def test_pp11_ein_schreibfehler_wird_als_fehler_gemeldet_nicht_als_kein_eintrag(tmp_path):
    """Vorher endete ein Fehler beim Schreiben als Exit-Code 1 — und der Deinstaller sagte „MCP-Eintrag war nicht vorhanden“,
    obwohl er noch da war."""
    import stat
    std = _config(tmp_path / "AppData" / "Roaming" / "Claude")
    original = std.read_bytes()
    os.chmod(std, stat.S_IREAD)                        # schreibgeschützt: WriteAllText wirft UnauthorizedAccessException
    try:
        r = _lauf(tmp_path)
        assert r.returncode == 5, (r.returncode, r.stdout, r.stderr)
        assert std.read_bytes() == original
    finally:
        os.chmod(std, stat.S_IWRITE | stat.S_IREAD)


# ── PP17: nur der Eintrag verschwindet, der Rest der Datei bleibt, wie er ist ───────────────────

EINTRAG = r'''"bewerbungs-assistent": {
      "command": "C:\\Users\\x\\python.exe",
      "args": ["-m", "bewerbungs_assistent"],
      "env": {"BA_DATA_DIR": "C:\\Users\\x\\data"}
    }'''
ANDERER = r'''"filesystem": {
      "command": "npx",
      "args": ["-y", "server"]
    }'''
ZWEITER = r'''"zweiter": {
      "command": "node"
    }'''
# Klammern, Anführungszeichen und Rückstriche IN Texten dürfen das Zählen der Klammern nicht stören
KNIFFLIG = r'''"bewerbungs-assistent": {
      "command": "x",
      "args": ["--note", "ende } und { auf \" zu \\ und }"],
      "env": {"A": "}", "B": "\\"}
    }'''
# Was ein Neuschreiben über ConvertTo-Json verändert: Umlaute als Escape werden zu Zeichen, leere Listen und verschachtelte Werte
# bekommen anderen Leerraum; Zahlen wie 2.50 und die große Zahl müssen dabei genauso bleiben, wie sie dastehen
REST = r'''"preferences": {
    "theme": "dark",
    "zahl": 12345678901234567890,
    "komma": 2.50,
    "text": "Gr\u00fc\u00dfe \u00e4 \"zitiert\" }{",
    "leer": [],
    "tief": {"a": {"b": [1, null, true]}}
  }'''


def _fall(eintraege: list, nachher: list) -> tuple:
    kopf, fuss = '{\n  "mcpServers": {\n    ', '\n  },\n  ' + REST + '\n}\n'
    return (kopf + ',\n    '.join(eintraege) + fuss, kopf + ',\n    '.join(nachher) + fuss)


FAELLE_PP17 = {
    "letzter": _fall([ANDERER, EINTRAG], [ANDERER]),
    "erster": _fall([EINTRAG, ANDERER], [ANDERER]),
    "mittlerer": _fall([ANDERER, EINTRAG, ZWEITER], [ANDERER, ZWEITER]),
    "kniffliger-text": _fall([ANDERER, KNIFFLIG, ZWEITER], [ANDERER, ZWEITER]),
    "einziger": ('{\n  "mcpServers": {\n    ' + EINTRAG + '\n  },\n  "n": 1\n}\n', '{\n  "mcpServers": {},\n  "n": 1\n}\n'),
    "kompakt": ('{"mcpServers":{"a":{"command":"x"},"bewerbungs-assistent":{"command":"y","args":["z"]}},"n":1}',
                '{"mcpServers":{"a":{"command":"x"}},"n":1}'),
    # derselbe Schlüssel steht VOR mcpServers in einem anderen Zusammenhang: gesucht wird erst hinter dem Wort mcpServers
    "gleichnamiger-schluessel-davor": (
        '{\n  "preferences": {\n    "notiz": {"bewerbungs-assistent": {"k": 1}}\n  },\n  "mcpServers": {\n'
        '    "filesystem": {"command": "npx"},\n    "bewerbungs-assistent": {"command": "x"}\n  }\n}\n',
        '{\n  "preferences": {\n    "notiz": {"bewerbungs-assistent": {"k": 1}}\n  },\n  "mcpServers": {\n'
        '    "filesystem": {"command": "npx"}\n  }\n}\n'),
}


@nur_windows
@pytest.mark.parametrize("name", sorted(FAELLE_PP17))
def test_pp17_nur_der_eintrag_verschwindet_der_rest_bleibt_byte_fuer_byte(tmp_path, name):
    vorher, nachher = FAELLE_PP17[name]
    std = _config(tmp_path / "AppData" / "Roaming" / "Claude", roh=vorher.encode("utf-8"))
    r = _lauf(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert std.read_bytes().decode("utf-8") == nachher
    assert "(nur der Eintrag entfernt)" in r.stdout, r.stdout
    assert Path(str(std) + ".pbp-backup").read_bytes() == vorher.encode("utf-8"), "die Sicherung ist die Datei von vorher"


@nur_windows
@pytest.mark.parametrize("name", ["letzter", "erster", "einziger"])
def test_pp17_windows_zeilenenden_bleiben_erhalten(tmp_path, name):
    vorher, nachher = (t.replace("\n", "\r\n") for t in FAELLE_PP17[name])
    std = _config(tmp_path / "AppData" / "Roaming" / "Claude", roh=vorher.encode("utf-8"))
    assert _lauf(tmp_path).returncode == 0
    assert std.read_bytes().decode("utf-8") == nachher


@nur_windows
def test_pp17_der_alte_weg_haette_die_datei_umgeschrieben(tmp_path):
    """Belegt, was die Reparatur verhindert: über ConvertTo-Json setzt Windows PowerShell zwei Leerzeichen hinter jeden Doppelpunkt, rückt
    tief ein und lässt die Datei um ein Vielfaches wachsen (in der Praxisprobe von rund 2 auf rund 15 KB). Hält den Test oben ehrlich —
    wäre das nicht so, bewiese „der Rest bleibt Byte für Byte“ nichts."""
    vorher, _ = FAELLE_PP17["letzter"]
    r = subprocess.run([POWERSHELL, "-NoProfile", "-Command",
                        "$o = ConvertFrom-Json -InputObject ([Console]::In.ReadToEnd()); ConvertTo-Json -InputObject $o -Depth 15"],
                       input=vorher, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0, r.stderr
    assert '":  ' in r.stdout, "zwei Leerzeichen hinter dem Doppelpunkt"
    assert len(r.stdout) > 2 * len(vorher)
    assert vorher not in r.stdout


@nur_windows
def test_pp17_findet_das_wort_nur_als_eintrag_und_faellt_sonst_auf_den_alten_weg_zurueck(tmp_path):
    """Steht ein gleichnamiger Schlüssel tiefer in einem anderen Server VOR dem echten Eintrag, würde das Streichen im Text die falsche
    Stelle treffen. Die Prüfung (Ergebnis gegen die erwartete Fassung) bemerkt das; dann gilt der bisherige Weg, und der echte Eintrag
    verschwindet trotzdem."""
    vorher = ('{\n  "mcpServers": {\n    "filesystem": {\n      "command": "npx",\n'
              '      "env": {"bewerbungs-assistent": {"k": 1}}\n    },\n'
              '    "bewerbungs-assistent": {"command": "x"}\n  }\n}\n')
    std = _config(tmp_path / "AppData" / "Roaming" / "Claude", roh=vorher.encode("utf-8"))
    r = _lauf(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "(neu geschrieben)" in r.stdout, r.stdout
    daten = json.loads(std.read_bytes().decode("utf-8"))
    assert sorted(daten["mcpServers"]) == ["filesystem"], "der echte Eintrag ist weg"
    assert daten["mcpServers"]["filesystem"]["env"] == {"bewerbungs-assistent": {"k": 1}}, "der gleichnamige Schlüssel tiefer drin bleibt"
    assert Path(str(std) + ".pbp-backup").read_bytes() == vorher.encode("utf-8")


@nur_windows
def test_pp17_ein_schluessel_mit_escape_schreibweise_faellt_auf_den_alten_weg_zurueck(tmp_path):
    """Der Schlüssel ist für JSON derselbe, steht im Text aber anders (`\\u002d` für den Bindestrich): der Text-Weg findet ihn nicht."""
    vorher = '{\n  "mcpServers": {\n    "bewerbungs\\u002dassistent": {"command": "x"},\n    "filesystem": {"command": "npx"}\n  }\n}\n'
    std = _config(tmp_path / "AppData" / "Roaming" / "Claude", roh=vorher.encode("utf-8"))
    r = _lauf(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "(neu geschrieben)" in r.stdout, r.stdout
    assert sorted(json.loads(std.read_bytes().decode("utf-8"))["mcpServers"]) == ["filesystem"]
