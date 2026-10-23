"""#1228 (dritter Lauf, Block E5): „Apps & Features“ nennt die Fassung, die laeuft.

Gemessen auf dem Werkstatt-PC nach Auto-Update und Neustart: laufend 1.9.0-rc.2, Registry `DisplayVersion` 1.9.0-rc.1. Den Eintrag
schreibt nur der Installer. Hier: der Abgleich beim Start -- ohne echte Registry (ein Testdoppel fuer `winreg`), mit den Regeln, die
sich nicht aufweichen lassen: nur ein vorhandener Eintrag, nur `DisplayVersion`, nur der eigene Ort, jeder Fehler still.
"""
from __future__ import annotations

import os
import subprocess

import pytest
from _au_hilfen import FakeDb, programmordner

from bewerbungs_assistent.services.auto_update import lauf, layout, windows_liste


class FakeWinreg:
    """Gerade genug von `winreg`: ein Schluessel mit Werten, Zugriffe werden mitgeschrieben."""
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self, werte=None, *, schluessel=windows_liste.SCHLUESSEL, schreiben_scheitert=False):
        self.werte = None if werte is None else dict(werte)
        self.schluessel = schluessel
        self.schreiben_scheitert = schreiben_scheitert
        self.geoeffnet = []
        self.geschrieben = []

    def OpenKey(self, wurzel, pfad, reserviert=0, zugriff=1):  # noqa: N802
        self.geoeffnet.append((wurzel, pfad, zugriff))
        if self.werte is None or wurzel != self.HKEY_CURRENT_USER or pfad != self.schluessel:
            raise FileNotFoundError(pfad)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def QueryValueEx(self, schluessel, name):  # noqa: N802
        if name not in self.werte:
            raise FileNotFoundError(name)
        return (self.werte[name], self.REG_SZ)

    def SetValueEx(self, schluessel, name, reserviert, art, wert):  # noqa: N802
        if self.schreiben_scheitert:
            raise PermissionError("kein Schreibrecht")
        self.geschrieben.append((name, art, wert))
        self.werte[name] = wert


APP = r"C:\Users\x\AppData\Local\BewerbungsAssistent\app"


def _eintrag(version="1.9.0-rc.1", ort=APP):
    return {"DisplayVersion": version, "InstallLocation": ort, "DisplayName": "PBP"}


# ── die Regeln ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_ein_veralteter_eintrag_wird_auf_die_laufende_fassung_gesetzt():
    reg = FakeWinreg(_eintrag("1.9.0-rc.1"))
    assert windows_liste.abgleichen("1.9.0-rc.2", APP, plattform="win32", winreg=reg) == "gesetzt"
    assert reg.werte["DisplayVersion"] == "1.9.0-rc.2"
    assert reg.geschrieben == [("DisplayVersion", FakeWinreg.REG_SZ, "1.9.0-rc.2")], "genau dieser eine Wert"
    assert reg.werte["InstallLocation"] == APP and reg.werte["DisplayName"] == "PBP", "sonst nichts angefasst"


def test_ein_gleicher_eintrag_wird_nicht_geschrieben():
    reg = FakeWinreg(_eintrag("1.9.0-rc.2"))
    assert windows_liste.abgleichen("1.9.0-rc.2", APP, plattform="win32", winreg=reg) == "gleich"
    assert reg.geschrieben == []


def test_ohne_eintrag_wird_keiner_angelegt():
    reg = FakeWinreg(None)
    assert windows_liste.abgleichen("1.9.0-rc.2", APP, plattform="win32", winreg=reg) == "kein_eintrag"
    assert reg.geschrieben == [] and reg.werte is None


def test_ein_eintrag_an_einem_anderen_ort_wird_nicht_angefasst():
    """Ein Test oder ein Entwicklerstart mit fremdem Programmordner darf die echte Installation nie veraendern."""
    reg = FakeWinreg(_eintrag("1.8.0", ort=r"D:\Anderswo\app"))
    assert windows_liste.abgleichen("1.9.0-rc.2", APP, plattform="win32", winreg=reg) == "anderer_ort"
    assert reg.geschrieben == [] and reg.werte["DisplayVersion"] == "1.8.0"


def test_ein_eintrag_ohne_ort_wird_nicht_angefasst():
    reg = FakeWinreg({"DisplayVersion": "1.8.0"})
    assert windows_liste.abgleichen("1.9.0-rc.2", APP, plattform="win32", winreg=reg) == "anderer_ort"
    assert reg.geschrieben == []


def test_der_ort_wird_ohne_beachtung_von_gross_klein_und_abschluss_verglichen():
    reg = FakeWinreg(_eintrag("1.9.0-rc.1", ort=APP.upper() + "\\"))
    if os.name == "nt":
        assert windows_liste.abgleichen("1.9.0-rc.2", APP, plattform="win32", winreg=reg) == "gesetzt"


def _verknuepfung(ziel, link) -> bool:
    """Ein Symlink, sonst unter Windows eine Junction (braucht kein Recht). False, wenn beides nicht geht."""
    try:
        os.symlink(ziel, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(ziel)], capture_output=True)
        return r.returncode == 0
    return False


def test_ein_verknuepfter_ordner_gilt_als_derselbe_ort(tmp_path):
    """Der Startbaustein nennt den aufgeloesten Pfad, der Installer die Zeichenfolge aus der Umgebung."""
    echt = tmp_path / "echt"
    echt.mkdir()
    link = tmp_path / "link"
    if not _verknuepfung(echt, link):
        pytest.skip("keine Verknuepfung moeglich")
    reg = FakeWinreg(_eintrag("1.9.0-rc.1", ort=str(link)))
    assert windows_liste.abgleichen("1.9.0-rc.2", echt, plattform="win32", winreg=reg) == "gesetzt"
    reg = FakeWinreg(_eintrag("1.9.0-rc.1", ort=str(echt)))
    assert windows_liste.abgleichen("1.9.0-rc.2", link, plattform="win32", winreg=reg) == "gesetzt"


def test_ein_schreibfehler_ist_still():
    reg = FakeWinreg(_eintrag("1.9.0-rc.1"), schreiben_scheitert=True)
    assert windows_liste.abgleichen("1.9.0-rc.2", APP, plattform="win32", winreg=reg) == "fehler"


def test_ein_unerwarteter_fehler_ist_still():
    class Kaputt(FakeWinreg):
        def OpenKey(self, *a, **kw):  # noqa: N802
            raise RuntimeError("unerwartet")

    assert windows_liste.abgleichen("1.9.0-rc.2", APP, plattform="win32", winreg=Kaputt(_eintrag())) == "fehler"


def test_nicht_windows_tut_nichts():
    reg = FakeWinreg(_eintrag())
    assert windows_liste.abgleichen("1.9.0-rc.2", APP, plattform="linux", winreg=reg) == "nicht_windows"
    assert reg.geoeffnet == []


@pytest.mark.parametrize("version,ordner", [(None, APP), ("", APP), ("1.9.0", None)])
def test_ohne_fassung_oder_ordner_gibt_es_nichts_zu_tun(version, ordner):
    reg = FakeWinreg(_eintrag())
    assert windows_liste.abgleichen(version, ordner, plattform="win32", winreg=reg) == "nichts_zu_tun"
    assert reg.geoeffnet == []


# ── der Start ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_der_start_gleicht_die_windows_liste_mit_der_laufenden_fassung_ab(tmp_path, monkeypatch):
    app = programmordner(tmp_path / "pc", fassungen=("1.9.0-rc.1", "1.9.0-rc.2"))
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.9.0-rc.2")
    gesehen = []
    monkeypatch.setattr(windows_liste, "abgleichen", lambda version, ordner, **kw: gesehen.append((version, ordner)) or "gesetzt")
    erg = lauf.beim_start(FakeDb(), bestaetigung_nach=0)
    assert erg["verfuegbar"] is True and erg["windows_liste"] == "gesetzt"
    assert gesehen == [("1.9.0-rc.2", app)]


def test_ein_fehler_im_abgleich_haelt_den_start_nicht_auf(tmp_path, monkeypatch):
    app = programmordner(tmp_path / "pc", fassungen=("1.9.0-rc.1",))
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.9.0-rc.1")

    def kaputt(*a, **kw):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(windows_liste, "abgleichen", kaputt)
    erg = lauf.beim_start(FakeDb(), bestaetigung_nach=0)
    assert erg["verfuegbar"] is True and "windows_liste" not in erg


def test_der_start_mit_fremdem_programmordner_laesst_die_echte_registry_unberuehrt(tmp_path, monkeypatch):
    """Die Suite laeuft auf Rechnern mit echter Installation: ohne den Vergleich des Ortes schriebe sie dort DisplayVersion."""
    if os.name != "nt":
        pytest.skip("Registry nur unter Windows")
    import winreg
    echt = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, windows_liste.SCHLUESSEL, 0, winreg.KEY_READ) as k:
            echt = (winreg.QueryValueEx(k, "DisplayVersion")[0], winreg.QueryValueEx(k, "InstallLocation")[0])
    except OSError:
        pytest.skip("auf diesem Rechner gibt es keinen Eintrag zu schuetzen")
    app = programmordner(tmp_path / "pc", fassungen=("9.9.9",))
    assert str(tmp_path) in str(app)
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "9.9.9")
    erg = lauf.beim_start(FakeDb(), bestaetigung_nach=0)
    assert erg["windows_liste"] in ("anderer_ort", "kein_eintrag")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, windows_liste.SCHLUESSEL, 0, winreg.KEY_READ) as k:
        assert (winreg.QueryValueEx(k, "DisplayVersion")[0], winreg.QueryValueEx(k, "InstallLocation")[0]) == echt
