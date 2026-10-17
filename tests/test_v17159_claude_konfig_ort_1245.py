"""#1245 (vierter Werkstatt-PC-Lauf, 17.10.2026, PP37): der Installer trug PBP in Dateien ein, die Claude nicht liest.

Die aktuelle Store-Fassung von Claude Desktop (Paketversion 2.42304) liest ihre Konfiguration aus
`%LOCALAPPDATA%\\Claude-Data\\claude_<Paketkennung>\\claude_desktop_config.json`. `_setup_claude.py` kannte nur
`%APPDATA%\\Claude\\` und `Packages\\Claude_*\\LocalCache\\Roaming\\Claude\\`; beide Dateien gab es auf dem Rechner gar nicht. Der
Installer schrieb den Eintrag trotzdem dorthin und meldete "[OK] Claude Desktop konfiguriert", Claude startete PBP nie, und das
Dashboard sagte richtig "nicht verbunden". Mit dem Eintrag in der echten Datei startete Claude PBP sofort.

Der Deinstaller (PP37b) hat dieselbe Lücke; seine Verhaltenstests stehen bei PP11 in `test_v18_praxisprobe_deinstaller.py`.

Hier: die Pfadliste und das Schreiben von `_setup_claude.py`. Die Tests laufen auf jedem Betriebssystem (`sys.platform` wird auf
"win32" gesetzt; APPDATA und LOCALAPPDATA zeigen auf einen Temp-Ordner, nie auf die echte Claude-Konfiguration des Rechners).
Nur der Lauf als Skript braucht Windows.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "docs" / "internal" / "testlauf" / "pbp_probe.ps1"
nur_windows = pytest.mark.skipif(os.name != "nt", reason="braucht Windows")

# So sah die echte Datei auf dem Werkstatt-PC aus: Einstellungen von Claude selbst, kein einziger MCP-Server.
ECHTE_FORM = {
    "coworkUserFilesPath": "C:/Users/beispiel/Documents/Claude",
    "preferences": {"theme": "dark", "quickEntryShortcut": "Ctrl+Alt+Space"},
}


def _laden(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "_setup_claude.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture()
def win(tmp_path, monkeypatch):
    """`_setup_claude` als Windows-Lauf in einem Temp-Benutzerordner (QA-Isolation: APPDATA/LOCALAPPDATA im Test-Ordner)."""
    roaming, lokal = tmp_path / "AppData" / "Roaming", tmp_path / "AppData" / "Local"
    roaming.mkdir(parents=True)
    lokal.mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(lokal))
    assert str(tmp_path) in os.environ["APPDATA"] and str(tmp_path) in os.environ["LOCALAPPDATA"]
    modul = _laden("setup_claude_1245")
    monkeypatch.setattr(modul.sys, "platform", "win32")
    return SimpleNamespace(sc=modul, roaming=roaming, lokal=lokal,
                           standard=roaming / "Claude" / "claude_desktop_config.json")


def _claude_data(win, kennung="claude_pzs8sxrjxfjjc", mit_datei=True) -> Path:
    ordner = win.lokal / "Claude-Data" / kennung
    ordner.mkdir(parents=True)
    datei = ordner / "claude_desktop_config.json"
    if mit_datei:
        datei.write_bytes(json.dumps(ECHTE_FORM, indent=2).encode("utf-8"))
    return datei


def _pfade(win):
    return [Path(p) for p in win.sc.get_claude_config_paths()]


# ── die Pfadliste ───────────────────────────────────────────────────────────────────────────────

def test_der_datenordner_der_neuen_store_fassung_steht_in_der_liste(win):
    neu = _claude_data(win)
    assert _pfade(win) == [win.standard, neu], "der Standardpfad bleibt an erster Stelle (get_claude_config_path), der neue folgt"


def test_der_fall_der_praxisprobe_nur_claude_data_existiert(win):
    """Beide alten Orte fehlen, nur Claude-Data ist da: der neue Pfad muss in der Liste sein, sonst erreicht der Eintrag Claude nie."""
    neu = _claude_data(win)
    assert not win.standard.parent.exists() and not (win.lokal / "Packages").exists()
    assert neu in _pfade(win)


def test_ein_ordner_ohne_datei_zaehlt_auch(win):
    """Claude legt die Datei erst an, wenn jemand etwas einstellt; der Ordner allein zeigt, dass Claude hier zu Hause ist."""
    neu = _claude_data(win, mit_datei=False)
    assert neu in _pfade(win)


def test_ohne_claude_data_bleibt_die_liste_wie_vorher(win):
    assert _pfade(win) == [win.standard]
    paket = win.lokal / "Packages" / "Claude_pzs8sxrjxfjjc" / "LocalCache" / "Roaming" / "Claude"
    paket.mkdir(parents=True)
    assert _pfade(win) == [win.standard, paket / "claude_desktop_config.json"], "die Store-Fassung bis 2.3 (#361) bleibt bedient"


def test_alle_drei_orte_zugleich(win):
    paket = win.lokal / "Packages" / "Claude_pzs8sxrjxfjjc" / "LocalCache" / "Roaming" / "Claude"
    paket.mkdir(parents=True)
    neu = _claude_data(win)
    assert _pfade(win) == [win.standard, paket / "claude_desktop_config.json", neu]


def test_mehrere_pakete_unter_claude_data_werden_alle_bedient(win):
    a = _claude_data(win, "claude_aaaa")
    b = _claude_data(win, "claude_bbbb")
    assert _pfade(win) == [win.standard, a, b]


def test_fremdes_unter_claude_data_zaehlt_nicht(win):
    """Eine Datei namens `claude_x`, ein Zwischenspeicher, ein fremder Ordner: kein Ort für eine Konfiguration."""
    wurzel = win.lokal / "Claude-Data"
    wurzel.mkdir()
    (wurzel / "claude_datei").write_text("x")
    (wurzel / "Cache").mkdir()
    (wurzel / "crashpad").mkdir()
    (wurzel / "claude-code-verlauf").mkdir()
    assert _pfade(win) == [win.standard]


def test_ohne_localappdata_gibt_es_keinen_absturz_und_keinen_relativen_pfad(win, monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA")
    assert [str(p) for p in _pfade(win)] == [str(win.standard)]


def test_der_pfad_der_nicht_windows_systeme_bleibt_unberuehrt(win, monkeypatch):
    monkeypatch.setattr(win.sc.sys, "platform", "linux")
    _claude_data(win)
    pfade = win.sc.get_claude_config_paths()
    assert len(pfade) == 1 and "Claude-Data" not in pfade[0]


# ── das Schreiben und die Probe danach ──────────────────────────────────────────────────────────

def _schreiben(win, pfad):
    return win.sc.config_schreiben(str(pfad), "C:/pbp/python.exe", "C:/pbp/boot", "C:/pbp/data")


def test_der_eintrag_steht_danach_in_der_datei_die_claude_liest(win):
    neu = _claude_data(win)
    assert _schreiben(win, neu) is True
    config = json.loads(neu.read_bytes().decode("utf-8"))
    assert "bewerbungs-assistent" in config["mcpServers"]
    assert config["preferences"] == ECHTE_FORM["preferences"] and config["coworkUserFilesPath"] == ECHTE_FORM["coworkUserFilesPath"]
    assert not neu.read_bytes().startswith(b"\xef\xbb\xbf"), "ohne BOM"


def test_geschrieben_gilt_erst_nach_dem_zuruecklesen(win, monkeypatch, capsys):
    """DoD 8g: eine Meldung wie "geschrieben" steht erst nach einer Probe des Inhalts. Schreibt `json.dump` etwas ohne den Eintrag,
    darf die Datei nicht mitzaehlen."""
    neu = _claude_data(win)

    def leer(config, f, **kw):
        f.write('{"mcpServers": {}}')

    monkeypatch.setattr(win.sc.json, "dump", leer)
    assert _schreiben(win, neu) is False
    assert "nicht zu finden" in capsys.readouterr().out


def test_eine_nicht_beschreibbare_datei_zaehlt_nicht_und_stoppt_nichts(win):
    """Der Ordner der Datei ist in Wahrheit eine Datei: `makedirs` scheitert. Das ist ein Fehlschlag dieser Datei, kein Absturz."""
    kaputt = win.roaming / "Claude"
    kaputt.parent.mkdir(parents=True, exist_ok=True)
    kaputt.write_text("ich bin ein Ordner, sagt der Installer")
    assert _schreiben(win, kaputt / "claude_desktop_config.json") is False


def test_main_schreibt_die_uebrigen_dateien_auch_wenn_eine_scheitert(win, monkeypatch, capsys):
    neu = _claude_data(win)
    kaputt = win.roaming / "Claude"
    kaputt.write_text("Datei statt Ordner")
    # `main()` liest die Liste selbst: erst die kaputte, dann die echte
    monkeypatch.setattr(win.sc, "get_claude_config_paths", lambda: [str(kaputt / "claude_desktop_config.json"), str(neu)])
    win.sc.main()
    aus = capsys.readouterr().out
    assert "bewerbungs-assistent" in json.loads(neu.read_bytes().decode("utf-8"))["mcpServers"], aus
    assert "1 Config-Datei(en) geschrieben und geprueft" in aus and aus.strip().splitlines()[-1] == "OK"


def test_main_endet_mit_fehler_wenn_keine_datei_den_eintrag_hat(win, monkeypatch, capsys):
    kaputt = win.roaming / "Claude"
    kaputt.write_text("Datei statt Ordner")
    monkeypatch.setattr(win.sc, "get_claude_config_paths", lambda: [str(kaputt / "claude_desktop_config.json")])
    with pytest.raises(SystemExit) as e:
        win.sc.main()
    assert e.value.code == 1
    assert "FEHLER" in capsys.readouterr().out


# ── der Lauf als Skript, wie ihn der Installer macht ────────────────────────────────────────────

@nur_windows
def test_ende_zu_ende_als_skript_nur_claude_data_existiert(tmp_path):
    """Der Werkstatt-PC: APPDATA\\Claude und Packages fehlen, Claude-Data hat die echte Datei ohne MCP-Server."""
    home = tmp_path / "home"
    roaming, lokal = home / "AppData" / "Roaming", home / "AppData" / "Local"
    echte = lokal / "Claude-Data" / "claude_pzs8sxrjxfjjc" / "claude_desktop_config.json"
    echte.parent.mkdir(parents=True)
    echte.write_bytes(json.dumps(ECHTE_FORM, indent=2).encode("utf-8"))
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), APPDATA=str(roaming), LOCALAPPDATA=str(lokal))
    assert str(tmp_path) in env["APPDATA"] and str(tmp_path) in env["LOCALAPPDATA"]
    r = subprocess.run([sys.executable, str(ROOT / "_setup_claude.py")], env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == "OK"
    config = json.loads(echte.read_bytes().decode("utf-8"))
    assert "bewerbungs-assistent" in config["mcpServers"] and config["preferences"] == ECHTE_FORM["preferences"]
    assert "geschrieben und geprueft" in r.stdout


# ── die Probe des Werkstatt-PCs ─────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not PROBE.exists(), reason="die Probe gibt es nur in der 1.8-Linie")
def test_die_probe_listet_den_neuen_ort():
    text = PROBE.read_text(encoding="ascii")
    assert "Join-Path $LA 'Claude-Data'" in text, "die Probe sucht den Datenordner unter LOCALAPPDATA"
    assert "Join-Path $_.FullName 'claude_desktop_config.json'" in text
