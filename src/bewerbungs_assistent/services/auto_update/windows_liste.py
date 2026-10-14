"""Der Eintrag in „Apps & Features“ (Windows) nennt die Fassung, die läuft (#1228).

`DisplayVersion` unter `HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\PBP` schreibt nur der Installer
(`INSTALLIEREN.bat`). Das Auto-Update und das Zurückschalten änderten ihn nie: wer PBP nur per Auto-Update aktuell hielt,
sah in der Windows-Liste dauerhaft die Fassung seiner Erstinstallation (gemessen im dritten Lauf auf dem Werkstatt-PC:
laufend 1.9.0-rc.2, Registry 1.9.0-rc.1).

Abgeglichen wird beim Start (`lauf.beim_start`) — das deckt Auto-Update, Zurückschalten und den automatischen Rückfall des
Startbausteins ab, ohne dessen eingefrorenen Vertrag zu berühren. Regeln, die sich nicht aufweichen lassen:

* **Nur ein vorhandener Eintrag, nur `DisplayVersion`.** PBP legt den Schlüssel nie an (das tut der Installer) und fasst
  keinen anderen Wert an.
* **Nur der eigene Eintrag.** `InstallLocation` muss auf den Programmordner zeigen, der gerade läuft. Ein Test oder ein
  Entwicklerstart mit fremdem Programmordner verändert so nie die echte Installation.
* **Jeder Fehler ist still.** Die Windows-Liste ist eine Anzeige; ihretwegen startet PBP nie langsamer oder gar nicht.
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("bewerbungs_assistent.auto_update")

SCHLUESSEL = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PBP"


def _kanon(pfad) -> str:
    """Der echte Pfad: Verknuepfungen (Junction, Symlink), 8.3-Namen und Schreibweise werden aufgeloest. Der Startbaustein leitet
    den Programmordner aus `Path(__file__).resolve()` ab, der Installer schreibt `%LOCALAPPDATA%\\...` -- beides nennt denselben
    Ordner, aber nicht immer dieselbe Zeichenfolge."""
    return os.path.normcase(os.path.realpath(str(pfad)))


def _gleicher_ort(a, b) -> bool:
    try:
        return _kanon(a) == _kanon(b)
    except Exception:  # noqa: BLE001
        return False


def abgleichen(version, programmordner, *, plattform=None, winreg=None) -> str:
    """Setzt `DisplayVersion` auf `version`, wenn der eigene Eintrag da ist und etwas anderes nennt.

    Gibt zurück: ``gesetzt`` | ``gleich`` | ``kein_eintrag`` | ``anderer_ort`` | ``nicht_windows`` | ``nichts_zu_tun`` | ``fehler``.
    """
    if (plattform or sys.platform) != "win32":
        return "nicht_windows"
    if not version or programmordner is None:
        return "nichts_zu_tun"
    try:
        if winreg is None:
            import winreg as _winreg  # nur unter Windows vorhanden
            winreg = _winreg
        try:
            schluessel = winreg.OpenKey(winreg.HKEY_CURRENT_USER, SCHLUESSEL, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            return "kein_eintrag"
        with schluessel:
            try:
                ort = winreg.QueryValueEx(schluessel, "InstallLocation")[0]
            except FileNotFoundError:
                return "anderer_ort"
            if not _gleicher_ort(ort, programmordner):
                return "anderer_ort"
            try:
                aktuell = winreg.QueryValueEx(schluessel, "DisplayVersion")[0]
            except FileNotFoundError:
                aktuell = None
            if aktuell == str(version):
                return "gleich"
            winreg.SetValueEx(schluessel, "DisplayVersion", 0, winreg.REG_SZ, str(version))
            logger.info("Windows-Liste: DisplayVersion %s -> %s", aktuell, version)
            return "gesetzt"
    except Exception:  # noqa: BLE001 — eine Anzeige darf den Start nie aufhalten
        logger.debug("Windows-Liste nicht abgeglichen", exc_info=True)
        return "fehler"
