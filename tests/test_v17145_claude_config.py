"""v1.7.145 — Installer und Deinstaller gehen mit der Claude-Konfiguration sorgfaeltig um.

Befunde (01.10.2026, Prueferbericht Installation, nachgestellt):
* Der Deinstaller schrieb die Konfiguration mit Windows PowerShell 5.1 zurueck
  (Set-Content -Encoding UTF8 = MIT BOM). Beim naechsten Installerlauf las
  _setup_claude.py mit "utf-8", fand das BOM "defekt" und ueberschrieb die
  GANZE Datei mit nur dem PBP-Eintrag: alle anderen MCP-Server und
  Einstellungen des Menschen waren weg, auf dem Bildschirm stand "[OK]".
* Ein Update baute den PBP-Eintrag neu und verwarf BA_DATA_DIR (verlegter
  Datenordner) und BA_DASHBOARD_PORT: das Profil erschien leer.
* Der Deinstaller meldete "[OK] Backup erstellt", auch wenn keines entstanden
  war (gesperrte Datenbank), und loeschte danach endgueltig.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "DEINSTALLIEREN.bat"
BOM = b"\xef\xbb\xbf"


@pytest.fixture(scope="module")
def sc():
    spec = importlib.util.spec_from_file_location("setup_claude_pruefling", ROOT / "_setup_claude.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)  # nur Funktionen, kein Lauf beim Import
    return modul


ANDERE = {
    "mcpServers": {
        "filesystem": {"command": "npx", "args": ["-y", "server-filesystem", "C:/Beispiel"]},
        "bewerbungs-assistent": {
            "command": "C:/alt/python.exe", "args": ["-m", "bewerbungs_assistent"],
            "env": {"BA_DATA_DIR": "D:/MeineBewerbungen", "BA_DASHBOARD_PORT": "8300",
                    "PYTHONPATH": "C:/alt/src"}},
    },
    "preferences": {"theme": "dark", "quickEntryShortcut": "Ctrl+Alt+Space"},
}


def _schreibe(pfad, daten, mit_bom=False):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(daten, indent=2, ensure_ascii=False).encode("utf-8")
    pfad.write_bytes((BOM if mit_bom else b"") + text)


# ══ _setup_claude.py ═══════════════════════════════════════════════

def test_eine_datei_mit_bom_gilt_nicht_als_defekt(sc, tmp_path):
    cp = tmp_path / "Claude" / "claude_desktop_config.json"
    _schreibe(cp, ANDERE, mit_bom=True)
    config, problem = sc.lese_config(str(cp))
    assert config is not None, problem
    assert set(config["mcpServers"]) == {"filesystem", "bewerbungs-assistent"}


def test_andere_server_und_einstellungen_bleiben_erhalten(sc, tmp_path):
    """DER Fall aus dem Befund: Deinstaller-Ausgabe mit BOM, dann Neuinstallation."""
    cp = tmp_path / "Claude" / "claude_desktop_config.json"
    _schreibe(cp, ANDERE, mit_bom=True)
    assert sc.config_schreiben(str(cp), "C:/neu/python.exe", "C:/neu/src", "C:/Standard/data")
    neu = json.loads(cp.read_bytes().decode("utf-8"))
    assert "filesystem" in neu["mcpServers"]
    assert neu["preferences"] == ANDERE["preferences"]
    assert neu["mcpServers"]["bewerbungs-assistent"]["command"] == "C:/neu/python.exe"


def test_geschrieben_wird_ohne_bom(sc, tmp_path):
    cp = tmp_path / "Claude" / "claude_desktop_config.json"
    _schreibe(cp, ANDERE, mit_bom=True)
    sc.config_schreiben(str(cp), "p", "s", "d")
    assert not cp.read_bytes().startswith(BOM)


def test_eigener_datenordner_und_port_ueberleben_das_update(sc, tmp_path):
    cp = tmp_path / "Claude" / "claude_desktop_config.json"
    _schreibe(cp, ANDERE)
    sc.config_schreiben(str(cp), "C:/neu/python.exe", "C:/neu/src", "C:/Standard/data")
    env = json.loads(cp.read_text(encoding="utf-8"))["mcpServers"]["bewerbungs-assistent"]["env"]
    assert env["BA_DATA_DIR"] == "D:/MeineBewerbungen"
    assert env["BA_DASHBOARD_PORT"] == "8300"
    assert env["PYTHONPATH"] == "C:/neu/src"  # folgt immer der Installation


def test_ohne_alten_eintrag_gelten_die_vorgaben(sc):
    e = sc.eintrag_bauen("p.exe", "src", "data")
    assert e == {"command": "p.exe", "args": ["-m", "bewerbungs_assistent"],
                 "env": {"BA_DATA_DIR": "data", "PYTHONPATH": "src"}}


def test_eine_kaputte_datei_wird_erst_gesichert_dann_ersetzt(sc, tmp_path):
    cp = tmp_path / "Claude" / "claude_desktop_config.json"
    cp.parent.mkdir(parents=True)
    kaputt = '{"mcpServers": {"filesystem": {"command": "npx"'  # abgeschnitten
    cp.write_text(kaputt, encoding="utf-8")
    assert sc.config_schreiben(str(cp), "p", "s", "d") is True
    kopien = list(cp.parent.glob("claude_desktop_config.json.pbp-defekt-*"))
    assert len(kopien) == 1 and kopien[0].read_text(encoding="utf-8") == kaputt
    assert "bewerbungs-assistent" in json.loads(cp.read_text(encoding="utf-8"))["mcpServers"]


def test_ohne_moegliche_kopie_bleibt_die_datei_unberuehrt(sc, tmp_path, monkeypatch):
    cp = tmp_path / "Claude" / "claude_desktop_config.json"
    cp.parent.mkdir(parents=True)
    cp.write_text("{kaputt", encoding="utf-8")

    def nein(*a, **kw):
        raise OSError("keine Rechte")

    monkeypatch.setattr(sc.shutil, "copy2", nein)
    assert sc.config_schreiben(str(cp), "p", "s", "d") is False
    assert cp.read_text(encoding="utf-8") == "{kaputt"


@pytest.mark.parametrize("inhalt", ["[]", '"text"', '{"mcpServers": []}', ""])
def test_unerwartete_formen_gelten_als_nicht_lesbar(sc, tmp_path, inhalt):
    cp = tmp_path / "c.json"
    cp.write_text(inhalt, encoding="utf-8")
    config, problem = sc.lese_config(str(cp))
    assert config is None and problem


def test_ende_zu_ende_als_skript(tmp_path):
    """Der echte Aufruf aus dem Installer: python _setup_claude.py, eigene Umgebung."""
    home = tmp_path / "home"
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home),
               APPDATA=str(home / "AppData" / "Roaming"),
               LOCALAPPDATA=str(home / "AppData" / "Local"))
    r = subprocess.run([sys.executable, str(ROOT / "_setup_claude.py")], env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    configs = list(home.rglob("claude_desktop_config.json"))
    assert configs, r.stdout
    assert "bewerbungs-assistent" in json.loads(configs[0].read_text(encoding="utf-8"))["mcpServers"]
