"""v1.7.145 — Der Deinstaller schreibt die Claude-Konfiguration ohne BOM zurueck
und sagt ehrlich, wenn das Backup fehlt.

Befund (01.10.2026, Prueferbericht Installation, nachgestellt):
Der Deinstaller schrieb claude_desktop_config.json mit Windows PowerShell 5.1
(Set-Content -Encoding UTF8 = MIT BOM) zurueck. Der Installer fand die Datei
beim naechsten Lauf "defekt" und ersetzte sie komplett (siehe
test_v17145_claude_config.py). Ausserdem stand "[OK] Backup erstellt" auch
dann auf dem Bildschirm, wenn gar kein Backup entstanden war, und danach
durfte der Mensch endgueltig loeschen.

Die Strukturtests laufen ueberall, die Verhaltenstests fuehren die echten
PowerShell-Zeilen aus der BAT-Datei aus und brauchen Windows PowerShell.
"""
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "DEINSTALLIEREN.bat"
BOM = b"\xef\xbb\xbf"
POWERSHELL = shutil.which("powershell")
nur_windows = pytest.mark.skipif(
    os.name != "nt" or not POWERSHELL, reason="braucht Windows PowerShell 5.1")


def _bat():
    return BAT.read_text(encoding="utf-8", errors="replace")


def _befehl(zeile):
    """Der Text hinter `-Command "` bis zur schliessenden Anfuehrung."""
    start = zeile.index('-Command "') + len('-Command "')
    ende = zeile.index('" ', start) if '" ' in zeile[start:] else zeile.rindex('"')
    return zeile[start:ende]


def _zeile_nach(marke, enthaelt):
    """Erste Zeile mit `enthaelt` hinter der Zeile `marke`; eine Sprungmarke
    (beginnt mit ':') zaehlt nur als Zeile fuer sich, nicht als `call :marke`."""
    zeilen = _bat().splitlines()
    if marke.startswith(":"):
        ab = next(i for i, z in enumerate(zeilen) if z.strip() == marke)
    else:
        ab = next(i for i, z in enumerate(zeilen) if marke in z)
    return next(z for z in zeilen[ab:] if enthaelt in z)


def _lauf(befehl, env_zusatz):
    env = dict(os.environ)
    env.update(env_zusatz)
    return subprocess.run(
        [POWERSHELL, "-ExecutionPolicy", "Bypass", "-NoProfile", "-Command", befehl],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


# ══ Struktur: gilt auf jedem System ════════════════════════════════

def test_die_konfiguration_wird_ohne_bom_geschrieben():
    z = _zeile_nach(":remove_claude_entry", "powershell")
    assert "UTF8Encoding($false)" in z and "WriteAllText" in z
    assert "Set-Content" not in z and "Out-File" not in z


def test_das_backup_meldet_ok_nur_nach_pruefung_der_datei():
    z = _zeile_nach("Erstelle Backup", "Compress-Archive")
    assert z.index("Test-Path '!BACKUP_ZIP!'") < z.index("[OK] Backup erstellt")
    assert "exit 2" in z and "NICHT erstellt" in z


def test_nach_einem_fehlgeschlagenen_backup_steht_die_warnung_vor_der_loeschfrage():
    t = _bat()
    assert 'BACKUP_FEHLER' in t
    assert t.index('if "!BACKUP_FEHLER!"=="1"') < t.index("Tippe LOESCHEN")


# ══ Verhalten: die echten Zeilen, ausgefuehrt ══════════════════════

ANDERE = {
    "mcpServers": {
        "filesystem": {"command": "npx", "args": ["-y", "server-filesystem", "C:/Beispiel"]},
        "bewerbungs-assistent": {"command": "C:/alt/python.exe", "args": ["-m", "bewerbungs_assistent"]},
    },
    "preferences": {"theme": "dark"},
}


def _config(tmp_path, daten=ANDERE, mit_bom=True, roh=None):
    ordner = tmp_path / "AppData" / "Roaming"
    datei = ordner / "Claude" / "claude_desktop_config.json"
    datei.parent.mkdir(parents=True)
    inhalt = roh if roh is not None else json.dumps(daten, indent=2).encode("utf-8")
    datei.write_bytes((BOM if mit_bom else b"") + inhalt)
    return ordner, datei


def _entfernen(ordner):
    """Der Deinstaller sucht auch unter LOCALAPPDATA/Packages (Store-Fassung) - die muss auf den Temp-Ordner zeigen, sonst
    liefe der Test gegen die ECHTE Claude-Konfiguration dieses Rechners (QA-Isolation)."""
    z = _zeile_nach(":remove_claude_entry", "powershell")
    lokal = ordner.parent / "Local"
    assert str(ordner.parent).lower() != os.environ.get("LOCALAPPDATA", "").lower()
    return _lauf(_befehl(z), {"APPDATA": str(ordner), "LOCALAPPDATA": str(lokal)})


@nur_windows
def test_entfernen_laesst_andere_server_stehen_und_schreibt_ohne_bom(tmp_path):
    ordner, datei = _config(tmp_path)
    original = datei.read_bytes()
    r = _entfernen(ordner)
    assert r.returncode == 0, r.stdout + r.stderr
    neu = datei.read_bytes()
    assert not neu.startswith(BOM)
    daten = json.loads(neu.decode("utf-8"))
    assert list(daten["mcpServers"]) == ["filesystem"]
    assert daten["preferences"] == {"theme": "dark"}
    assert Path(str(datei) + ".pbp-backup").read_bytes() == original


@nur_windows
def test_ohne_pbp_eintrag_bleibt_die_datei_unberuehrt(tmp_path):
    daten = {"mcpServers": {"filesystem": {"command": "npx"}}}
    ordner, datei = _config(tmp_path, daten)
    original = datei.read_bytes()
    assert _entfernen(ordner).returncode == 1
    assert datei.read_bytes() == original


@nur_windows
def test_eine_unlesbare_datei_wird_nicht_angefasst(tmp_path):
    ordner, datei = _config(tmp_path, roh=b'{"mcpServers": {"filesystem": ')
    original = datei.read_bytes()
    assert _entfernen(ordner).returncode == 3
    assert datei.read_bytes() == original


@nur_windows
def test_nach_dem_deinstaller_ueberlebt_der_rest_die_neuinstallation(tmp_path):
    """DER Fall aus dem Befund: erst entfernen, dann neu installieren."""
    ordner, datei = _config(tmp_path)
    assert _entfernen(ordner).returncode == 0
    spec = importlib.util.spec_from_file_location("setup_claude_pruefling", ROOT / "_setup_claude.py")
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    assert sc.config_schreiben(str(datei), "C:/neu/python.exe", "C:/neu/src", "C:/neu/data")
    daten = json.loads(datei.read_bytes().decode("utf-8"))
    assert set(daten["mcpServers"]) == {"filesystem", "bewerbungs-assistent"}
    assert daten["preferences"] == {"theme": "dark"}


def _backup_befehl(daten_ordner, ziel):
    z = _zeile_nach("Erstelle Backup", "Compress-Archive")
    befehl = _befehl(z)
    return befehl.replace("%DATA_DIR%", str(daten_ordner)).replace("!BACKUP_ZIP!", str(ziel))


@nur_windows
def test_ein_backup_wird_gemeldet_wenn_die_datei_da_ist(tmp_path):
    daten = tmp_path / "data"
    daten.mkdir()
    (daten / "pbp.db").write_bytes(b"x" * 2048)
    ziel = tmp_path / "PBP-Backup.zip"
    r = _lauf(_backup_befehl(daten, ziel), {})
    assert r.returncode == 0, r.stdout + r.stderr
    assert ziel.is_file() and ziel.stat().st_size > 0
    assert "[OK] Backup erstellt" in r.stdout


@nur_windows
def test_ein_fehlgeschlagenes_backup_meldet_keinen_erfolg(tmp_path):
    daten = tmp_path / "data"
    daten.mkdir()
    (daten / "pbp.db").write_bytes(b"x" * 2048)
    ziel = tmp_path / "gibt-es-nicht" / "PBP-Backup.zip"  # Zielordner fehlt
    r = _lauf(_backup_befehl(daten, ziel), {})
    assert r.returncode == 2, r.stdout + r.stderr
    assert "[OK]" not in r.stdout and "NICHT erstellt" in r.stdout
    assert not ziel.exists()


@nur_windows
def test_ohne_datenordner_gibt_es_nichts_zu_sichern(tmp_path):
    r = _lauf(_backup_befehl(tmp_path / "fehlt", tmp_path / "x.zip"), {})
    assert r.returncode == 1 and "[OK]" not in r.stdout
