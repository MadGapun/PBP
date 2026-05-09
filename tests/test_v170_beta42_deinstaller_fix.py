"""Tests fuer v1.7.0-beta.42 — Deinstaller-Fix (#620).

Stellt sicher, dass DEINSTALLIEREN.bat die Self-Relocation-Stanza und
die korrekte Step-Reihenfolge enthaelt. Reine Datei-Inspektion — die
echte Bat-Ausfuehrung ist Windows-only und liegt nicht im pytest-Scope.
"""
from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEINSTALL_BAT = PROJECT_ROOT / "DEINSTALLIEREN.bat"


@pytest.fixture
def bat_content() -> str:
    return DEINSTALL_BAT.read_text(encoding="utf-8", errors="replace")


def test_deinstall_bat_exists():
    assert DEINSTALL_BAT.exists(), "DEINSTALLIEREN.bat fehlt im Repo-Root"


def test_self_relocation_stanza_present(bat_content: str):
    """#620 Bug 1: Wenn .bat aus %APP_DIR% laeuft, muss sie sich nach
    %TEMP% kopieren und neu starten — sonst loescht sie sich beim
    rmdir APP_DIR selbst und cmd.exe bricht ab."""
    assert ":pbp_relocate" in bat_content
    assert "PBP_DEINST_RELOCATED" in bat_content
    assert "%TEMP%" in bat_content
    # Der Vergleich BASEDIR == APP_DIR muss vor dem Sprung stehen
    assert "PBP_APP_DIR_CHECK" in bat_content


def test_registry_removal_before_app_dir_removal(bat_content: str):
    """#620 Bug 1 Defense-in-Depth: Registry-Eintrag muss VOR
    rmdir APP_DIR entfernt werden. Falls Self-Relocation versagt,
    bleibt mindestens der Apps-&-Features-Eintrag NICHT haengen."""
    reg_idx = bat_content.find(
        'reg delete "HKCU\\SOFTWARE\\Microsoft\\Windows'
        '\\CurrentVersion\\Uninstall\\PBP"'
    )
    rmdir_app_idx = bat_content.find(
        'call :remove_path "%APP_DIR%"'
    )
    assert reg_idx > 0, "Registry-Loeschung fehlt"
    assert rmdir_app_idx > 0, "APP_DIR-Loeschung fehlt"
    assert reg_idx < rmdir_app_idx, (
        "Registry muss VOR rmdir APP_DIR entfernt werden (#620)"
    )


def test_base_install_cleanup_at_end(bat_content: str):
    """#620 Bug 2: Stamm-Ordner BASE_INSTALL muss am Ende per `rmdir`
    (ohne /s) entfernt werden — entfernt nur wenn leer, also nur wenn
    der User die Daten freiwillig geloescht hat."""
    # Suche nach rmdir auf BASE_INSTALL OHNE /s-Flag (sicherheits-rmdir)
    assert 'rmdir "%BASE_INSTALL%"' in bat_content
    # Gleichzeitig pruefen dass die Stelle NICHT /s nutzt
    idx = bat_content.find('rmdir "%BASE_INSTALL%"')
    snippet = bat_content[idx:idx+60]
    assert "/s" not in snippet.lower(), (
        "BASE_INSTALL-Cleanup darf nur leere Verzeichnisse entfernen "
        "— /s wuerde Daten zerstoeren"
    )


def test_data_dir_still_optional(bat_content: str):
    """Daten-Loeschung bleibt opt-in (LOESCHEN-Bestaetigung)."""
    assert 'tippe LOESCHEN'.lower() in bat_content.lower() or 'Tippe LOESCHEN' in bat_content
