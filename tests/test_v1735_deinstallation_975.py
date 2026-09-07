"""Tests fuer v1.7.35 — #975 (I11): Wege zur Deinstallation.

Externes Feedback eines fruehen Testers (05.09.2026): *"Ich konnte das
nicht mal von PC und Laptop deinstallieren."*

Der Deinstaller EXISTIERT auf allen drei Plattformen — die Wege dorthin
fehlten. Die Gefahrenzone antwortete auf allem ausser Windows mit HTTP
400 und einem Repo-Pfad; der Text darueber versprach ueberall dasselbe,
obwohl es Registry und Desktop-Verknuepfung nur unter Windows gibt.

Das ist die Sackgassen-Definition aus G23/#927: technisch korrekte
Antwort, keine Antwort auf die Frage des Menschen.

**Diese Tests fuehren NIEMALS einen Deinstaller aus.** Sie pruefen die
Auskunft, die Pfad-Erkennung und den Aufbau der Skripte; `starten()`
wird nur mit gemocktem `subprocess.Popen` aufgerufen.
"""
import subprocess
from pathlib import Path

import pytest

from bewerbungs_assistent.services import deinstallation

WURZEL = Path(__file__).resolve().parents[1]


# ── Auskunft je Plattform ───────────────────────────────────────────

@pytest.mark.parametrize("system,erwartet", [
    ("Windows", "windows"), ("Darwin", "macos"), ("Linux", "linux"),
])
def test_975_jede_plattform_bekommt_eine_auskunft(monkeypatch, system, erwartet):
    monkeypatch.setattr(deinstallation, "_system", lambda: system)
    a = deinstallation.auskunft()
    assert a["plattform"] == erwartet
    assert a["entfernt"], system
    assert a["bleibt"], system


def test_975_registry_wird_nur_unter_windows_versprochen(monkeypatch):
    """Der gemeldete Fehler: der Text versprach auf jeder Plattform
    "Programmdateien, Registry-Eintrag, Desktop-Verknuepfung"."""
    monkeypatch.setattr(deinstallation, "_system", lambda: "Darwin")
    text = " ".join(deinstallation.auskunft()["entfernt"]).lower()
    assert "registry" not in text
    assert "verknuepfung" not in text
    monkeypatch.setattr(deinstallation, "_system", lambda: "Windows")
    text = " ".join(deinstallation.auskunft()["entfernt"]).lower()
    assert "registry" in text


def test_975_unix_nennt_was_liegen_bleibt(monkeypatch):
    """Befund 3: `.venv` und der Chromium-Cache standen nirgends —
    mehrere hundert MB, die nach dem Loeschen des Ordners bleiben."""
    for system in ("Darwin", "Linux"):
        monkeypatch.setattr(deinstallation, "_system", lambda s=system: s)
        entfernt = " ".join(deinstallation.auskunft()["entfernt"]).lower()
        bleibt = " ".join(deinstallation.auskunft()["bleibt"]).lower()
        assert "playwright" in entfernt or "chromium" in entfernt, system
        assert ".venv" in bleibt, system


def test_975_hinweis_kollidiert_nicht_mit_dem_handlungshinweis():
    """Zwei verschiedene Saetze unter einem Namen heisst, dass einer den
    anderen ueberschreibt — genau das ist mir hier passiert."""
    a = deinstallation.auskunft()
    assert "hinweis" not in a
    assert "hinweis_fremdsoftware" in a


def test_975_befehl_ist_kopierbar(monkeypatch, tmp_path):
    """Der Rueckfallweg: wenn sich kein Fenster oeffnen laesst, muss
    wenigstens ein Befehl dastehen, den man einfuegen kann."""
    skript = tmp_path / "deinstallieren.sh"
    skript.write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setattr(deinstallation, "_system", lambda: "Linux")
    monkeypatch.setattr(deinstallation, "deinstaller_pfad", lambda: skript)
    assert deinstallation.befehl() == f'bash "{skript}"'


# ── Starten: nie wirklich, immer gemockt ────────────────────────────

def test_975_macos_oeffnet_ein_terminal(monkeypatch, tmp_path):
    skript = tmp_path / "deinstallieren.sh"
    skript.write_text("#!/bin/bash\n", encoding="utf-8")
    gerufen = {}

    def _popen(cmd, **kwargs):
        gerufen["cmd"] = cmd
        return object()

    monkeypatch.setattr(deinstallation, "_system", lambda: "Darwin")
    monkeypatch.setattr(deinstallation, "deinstaller_pfad", lambda: skript)
    monkeypatch.setattr(subprocess, "Popen", _popen)
    erg = deinstallation.starten()
    assert erg["status"] == "gestartet"
    assert gerufen["cmd"][:3] == ["open", "-a", "Terminal"]
    assert "Terminal-Fenster" in erg["hinweis"]


def test_975_ohne_terminal_kommt_der_befehl_statt_einer_absage(
        monkeypatch, tmp_path):
    """Der Kern des Issues: keine Sackgasse mehr."""
    skript = tmp_path / "deinstallieren.sh"
    skript.write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setattr(deinstallation, "_system", lambda: "Linux")
    monkeypatch.setattr(deinstallation, "deinstaller_pfad", lambda: skript)
    monkeypatch.setattr(deinstallation, "_terminal_kommando", lambda p: None)
    erg = deinstallation.starten()
    assert erg["status"] == "befehl"
    assert erg["befehl"].startswith("bash ")
    assert str(skript) in erg["befehl"]


def test_975_fehlender_deinstaller_wird_erklaert(monkeypatch):
    monkeypatch.setattr(deinstallation, "deinstaller_pfad", lambda: None)
    erg = deinstallation.starten()
    assert erg["status"] == "nicht_gefunden"
    assert "Entwickler-Version" in erg["fehler"]
    # Auch im Fehlerfall steht da, was der Deinstaller getan haette.
    assert erg["entfernt"]


def test_975_linux_probiert_bekannte_terminals(monkeypatch, tmp_path):
    skript = tmp_path / "deinstallieren.sh"
    skript.write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setattr(deinstallation, "_system", lambda: "Linux")
    monkeypatch.setattr(deinstallation.shutil, "which",
                        lambda name: "/usr/bin/konsole" if name == "konsole" else None)
    kommando = deinstallation._terminal_kommando(skript)
    assert kommando is not None
    assert kommando[0] == "konsole"
    assert str(skript) in kommando


# ── Die Skripte selbst ──────────────────────────────────────────────

def test_975_doppelklick_deinstaller_existiert():
    """Befund 2: Windows hatte Doppelklick, der Mac einen Terminalbefehl
    mit Unterordner-Pfad."""
    assert (WURZEL / "DEINSTALLIEREN.bat").is_file()
    assert (WURZEL / "DEINSTALLIEREN.command").is_file()
    assert (WURZEL / "INSTALLIEREN.command").is_file()


def test_975_command_ruft_nur_das_skript_auf():
    """Er soll ein duenner Wrapper sein, kein zweiter Deinstaller —
    sonst laufen die beiden auseinander (Lehre aus #963/#976)."""
    text = (WURZEL / "DEINSTALLIEREN.command").read_text(encoding="utf-8")
    assert "installer/deinstallieren.sh" in text
    assert "rm -rf" not in text, "Der Wrapper darf selbst nichts loeschen"


@pytest.mark.parametrize("skript", [
    "installer/deinstallieren.sh", "DEINSTALLIEREN.command",
    "installer/install.sh", "INSTALLIEREN.command",
])
def test_975_shell_skripte_parsen(skript):
    """`bash -n` statt Ausfuehren — ein Syntaxfehler im Deinstaller faellt
    sonst erst dem Menschen auf, der ihn braucht."""
    import shutil as _sh
    if not _sh.which("bash"):
        pytest.skip("bash nicht verfuegbar")
    # Der Inhalt kommt ueber stdin, nicht als Pfad: unter Windows ist das
    # bash auf dem PATH haeufig das aus WSL, und das sieht "D:/..." nicht.
    # Ueber stdin gibt es gar keinen Pfad zu uebersetzen.
    erg = subprocess.run(
        ["bash", "-n"],
        input=(WURZEL / skript).read_bytes(),
        capture_output=True)
    # BYTES, nicht text=True: unter Windows kodiert der Textmodus stdin
    # als cp1252 und stolpert ueber das erste Haekchen im Skript. Genau
    # die Falle aus #929, dort im PII-Pruefer.
    assert erg.returncode == 0, erg.stderr.decode("utf-8", "replace")


def test_975_unix_deinstaller_fragt_vor_jedem_schritt():
    """Kein Deinstaller loescht Nutzerdaten ohne ausdrueckliche
    Bestaetigung (Akzeptanzkriterium)."""
    text = (WURZEL / "installer" / "deinstallieren.sh").read_text(encoding="utf-8")
    for stelle in ('rm -rf "$DATA_DIR"', 'rm -rf "$PW_CACHE"'):
        assert stelle in text, stelle
        vorher = text[:text.index(stelle)]
        # Zwischen der letzten Abfrage und dem Loeschen darf nichts
        # anderes stehen als die Auswertung der Antwort.
        assert "read -p" in vorher.rsplit("echo", 1)[-1] or "read -p" in vorher[-400:], stelle


def test_975_chromium_cache_wird_standardmaessig_behalten():
    """Andere Werkzeuge auf dem Rechner koennen ihn nutzen. Ein
    Deinstaller, der fremde Dinge mitnimmt, ist schlimmer als einer,
    der zu wenig entfernt."""
    text = (WURZEL / "installer" / "deinstallieren.sh").read_text(encoding="utf-8")
    assert "Chromium-Cache loeschen? (j/N)" in text, "Vorgabe muss NEIN sein"


def test_975_installer_nennen_den_rueckweg():
    """Symmetrie: wer installiert, soll wissen, wie er es wieder los
    wird."""
    for skript in ("INSTALLIEREN.command", "installer/install.sh"):
        text = (WURZEL / skript).read_text(encoding="utf-8")
        assert "DEINSTALLIEREN" in text, skript


def test_975_readme_kennt_das_wort_deinstallation():
    """Befund 4: das README ist die erste Anlaufstelle und enthielt es
    nicht."""
    text = (WURZEL / "README.md").read_text(encoding="utf-8")
    assert "### Deinstallation" in text
    assert "DEINSTALLIEREN.command" in text
    assert "DEINSTALLIEREN.bat" in text


def test_975_gefahrenzone_fragt_den_server_nach_der_plattform():
    """Die Listen standen fest im JSX und waren auf zwei von drei
    Plattformen falsch."""
    seite = (WURZEL / "frontend" / "src" / "pages"
             / "SettingsPage.jsx").read_text(encoding="utf-8")
    block = seite[seite.index("function UninstallSection"):]
    block = block[:block.index("\n}\n")]
    assert "/api/danger/uninstaller" in block
    assert "info?.entfernt" in block
    assert "Registry-Eintrag" not in block, "Kein fester Plattform-Text mehr"
