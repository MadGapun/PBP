"""Praxisprobe 1.8 (05.10.2026), Teil Deinstallation: drei Funde auf einem frischen Windows 11 mit Claude aus dem Store.

PP9  Der Knopf „Deinstaller starten“ (Gefahrenzone) funktionierte unter Windows nie. `starten()` setzte DETACHED_PROCESS und
     CREATE_NEW_CONSOLE zugleich; CreateProcess lehnt das ab („OSError: [WinError 87]“). Der Fehler wurde gefangen, die
     Oberfläche sagte „Kein Terminal gefunden“. Die Tests mockten `Popen` und prüften die Flags nie gegen das Betriebssystem.
PP11 Der Deinstaller las nur `%APPDATA%\\Claude\\claude_desktop_config.json`. Der Installer schreibt den Eintrag aber auch in die
     Store-Pakete (`Packages\\Claude_*\\LocalCache\\Roaming\\Claude`) — und genau die liest die Store-Fassung. Nach „PBP komplett
     deinstallieren“ blieb der Eintrag stehen; Claude meldete danach bei jedem Start einen Server ohne Programm.
PP12 Das Konsolenfenster des Dashboards (`cmd /K "Dashboard starten.bat"`) blieb nach der Deinstallation stehen.

Die Verhaltenstests führen die echten PowerShell-Zeilen aus der BAT-Datei aus (Windows PowerShell 5.1); APPDATA und LOCALAPPDATA
zeigen dabei auf einen Temp-Ordner. QA-Isolation: nie gegen die echte Claude-Konfiguration dieses Rechners.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
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
