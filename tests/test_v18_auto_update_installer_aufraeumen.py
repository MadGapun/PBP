"""Auto-Update (#1093, Anforderung 14): der Installer raeumt sich selbst auf — und nur sich selbst.

Ein Fehltreffer hier loescht Dateien des Menschen. Deshalb gibt es mehr Faelle, in denen NICHT geloescht wird,
als solche, in denen geloescht wird: jeder Weigerungsgrund hat seinen eigenen Test.
"""
import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import _installer_aufraeumen as ia  # noqa: E402


@pytest.fixture
def heim(tmp_path, monkeypatch):
    """Ein eigenes Benutzerverzeichnis, damit nichts im echten 'Downloads' gesucht wird."""
    h = tmp_path / "heim"
    (h / "Downloads").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: h))
    return h


def installer_ordner(ziel: Path) -> Path:
    (ziel / "src" / "bewerbungs_assistent").mkdir(parents=True)
    (ziel / "src" / "bewerbungs_assistent" / "__init__.py").write_text("x", encoding="utf-8")
    (ziel / "INSTALLIEREN.bat").write_text("@echo off", encoding="utf-8")
    (ziel / "_programm_einrichten.py").write_text("pass", encoding="utf-8")
    return ziel


def zip_mit_installer(pfad: Path, mit=True) -> Path:
    with zipfile.ZipFile(pfad, "w") as zf:
        zf.writestr("PBP-1.8.0/INSTALLIEREN.bat" if mit else "PBP-1.8.0/README.md", "x")
    return pfad


@pytest.fixture
def lage(tmp_path, heim):
    programm = tmp_path / "lokal" / "BewerbungsAssistent" / "app"
    daten = tmp_path / "lokal" / "BewerbungsAssistent" / "data"
    programm.mkdir(parents=True)
    daten.mkdir(parents=True)
    basis = installer_ordner(heim / "Downloads" / "PBP-1.8.0")
    return basis, programm, daten


# ══ Einstellung ═══════════════════════════════════════════════════════════════════════════

def db_mit(daten: Path, wert):
    conn = sqlite3.connect(daten / "pbp.db")
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    if wert is not None:
        conn.execute("INSERT INTO settings VALUES ('installer_aufraeumen', ?)", (json.dumps(wert),))
    conn.commit()
    conn.close()


def test_ohne_datenbank_oder_einstellung_wird_gefragt(tmp_path):
    assert ia.einstellung(tmp_path) == "fragen"
    db_mit(tmp_path, None)
    assert ia.einstellung(tmp_path) == "fragen"


@pytest.mark.parametrize("wert", ["immer", "nie", "fragen"])
def test_die_einstellung_wird_gelesen(tmp_path, wert):
    db_mit(tmp_path, wert)
    assert ia.einstellung(tmp_path) == wert


@pytest.mark.parametrize("wert", ["vielleicht", 5, ["immer"], None])
def test_eine_kaputte_einstellung_bedeutet_fragen_nie_loeschen(tmp_path, wert):
    db_mit(tmp_path, wert if wert is not None else "x")
    assert ia.einstellung(tmp_path) == "fragen"


def test_eine_unlesbare_datenbank_bedeutet_fragen(tmp_path):
    (tmp_path / "pbp.db").write_bytes(b"das ist keine Datenbank" * 50)
    assert ia.einstellung(tmp_path) == "fragen"


# ══ Plan: was geloescht werden darf ═══════════════════════════════════════════════════════

def test_ein_entpackter_installer_darf_aufgeraeumt_werden(lage):
    basis, programm, daten = lage
    zip_mit_installer(basis.parent / "PBP-1.8.0.zip")
    p = ia.plan(basis, "1.8.0", programm, daten)
    assert p["ordner"] == str(basis) and p["grund"] == "" and p["zips"] == [str(basis.parent / "PBP-1.8.0.zip")]


def test_ohne_zip_wird_nur_der_ordner_geplant(lage):
    basis, programm, daten = lage
    assert ia.plan(basis, "1.8.0", programm, daten)["zips"] == []


@pytest.mark.parametrize("fehlt", ["INSTALLIEREN.bat", "_programm_einrichten.py", "src/bewerbungs_assistent/__init__.py"])
def test_ein_ordner_ohne_die_erkennungsdateien_ist_kein_installer(lage, fehlt):
    basis, programm, daten = lage
    (basis / fehlt).unlink()
    p = ia.plan(basis, "1.8.0", programm, daten)
    assert p["ordner"] is None and fehlt in p["grund"]


def test_ein_git_arbeitsordner_wird_nie_geloescht(lage):
    basis, programm, daten = lage
    (basis / ".git").mkdir()
    p = ia.plan(basis, "1.8.0", programm, daten)
    assert p["ordner"] is None and "Git" in p["grund"]


def test_der_programmordner_und_der_datenordner_sind_tabu_auch_wenn_sie_wie_ein_installer_aussehen(tmp_path, heim):
    for name in ("programm", "daten"):
        ordner = installer_ordner(tmp_path / name)
        andere = tmp_path / "anderer"
        andere.mkdir(exist_ok=True)
        args = (ordner, "1.8.0", ordner if name == "programm" else andere, ordner if name == "daten" else andere)
        assert ia.plan(*args)["ordner"] is None, name


def test_ein_ordner_in_oder_ueber_dem_programmordner_wird_nicht_geloescht(tmp_path, heim):
    programm = tmp_path / "BewerbungsAssistent" / "app"
    daten = tmp_path / "BewerbungsAssistent" / "data"
    programm.mkdir(parents=True)
    daten.mkdir(parents=True)
    innen = installer_ordner(programm / "innen")
    assert ia.plan(innen, "1.8.0", programm, daten)["ordner"] is None
    aussen = installer_ordner(tmp_path)                 # enthaelt Programm- und Datenordner
    assert ia.plan(aussen, "1.8.0", programm, daten)["ordner"] is None


def test_das_benutzerverzeichnis_und_laufwerkswurzeln_sind_tabu(heim, tmp_path, lage):
    _, programm, daten = lage
    installer_ordner(heim)                              # das Benutzerverzeichnis selbst sieht wie ein Installer aus
    assert ia.plan(heim, "1.8.0", programm, daten)["ordner"] is None
    # ein Ordner, der das Benutzerverzeichnis ENTHAELT
    ueber = installer_ordner(tmp_path / "ueber")
    heim2 = ueber / "heim2"
    heim2.mkdir()
    import unittest.mock as m
    with m.patch.object(Path, "home", classmethod(lambda cls: heim2)):
        assert ia.plan(ueber, "1.8.0", programm, daten)["ordner"] is None


def test_ein_nicht_vorhandener_ordner_wird_abgewiesen(lage):
    _, programm, daten = lage
    assert ia.plan(programm.parent / "gibts-nicht", "1.8.0", programm, daten)["ordner"] is None


# ══ ZIP-Kandidaten ════════════════════════════════════════════════════════════════════════

def test_zips_werden_nur_mit_genauem_namen_und_installer_inhalt_genommen(tmp_path, heim):
    basis = installer_ordner(tmp_path / "entpackt" / "PBP-1.8.0")
    neben = zip_mit_installer(tmp_path / "entpackt" / "PBP-1.8.0.zip")             # neben dem Installationsordner
    downloads = zip_mit_installer(heim / "Downloads" / "pbp-1.8.0.zip")             # Gross-/Kleinschreibung egal
    zip_mit_installer(heim / "Downloads" / "PBP-1.8.1.zip")                         # andere Fassung
    zip_mit_installer(heim / "Downloads" / "PBP-1.8.0-kopie.zip")                   # anderer Name
    zip_mit_installer(heim / "Downloads" / "Lebenslauf.zip")
    zip_mit_installer(heim / "PBP-1.8.0.zip")                                        # weder neben dem Installer noch in Downloads
    gefunden = ia.zip_kandidaten(basis, "1.8.0")
    assert sorted(str(p) for p in gefunden) == sorted([str(neben), str(downloads)])


def test_ein_zip_ohne_installer_darin_wird_nicht_genommen(lage):
    basis, _, _ = lage
    zip_mit_installer(basis.parent / "PBP-1.8.0.zip", mit=False)
    assert ia.zip_kandidaten(basis, "1.8.0") == []


def test_ein_kaputtes_zip_wird_uebersprungen(lage):
    basis, _, _ = lage
    (basis.parent / "PBP-1.8.0.zip").write_bytes(b"PK\x03\x04 kaputt")
    assert ia.zip_kandidaten(basis, "1.8.0") == []


# ══ Loeschen ═════════════════════════════════════════════════════════════════════════════

def test_lauf_loescht_ordner_und_zips(lage):
    basis, _, _ = lage
    z = zip_mit_installer(basis.parent / "PBP-1.8.0.zip")
    assert ia.lauf(str(basis), [str(z)], versuche=2, pause=0) is True
    assert not basis.exists() and not z.exists()


def test_lauf_versucht_es_wieder_solange_der_ordner_gesperrt_ist(lage, monkeypatch):
    basis, _, _ = lage
    zaehler = {"n": 0}
    echt = ia._loeschen_versuchen

    def gesperrt_dann_frei(ordner, zips):
        zaehler["n"] += 1
        return False if zaehler["n"] < 3 else echt(ordner, zips)

    monkeypatch.setattr(ia, "_loeschen_versuchen", gesperrt_dann_frei)
    assert ia.lauf(str(basis), [], versuche=5, pause=0) is True
    assert zaehler["n"] == 3 and not basis.exists()


def test_lauf_gibt_nach_den_versuchen_auf_ohne_etwas_zu_beschaedigen(lage, monkeypatch):
    basis, _, _ = lage
    monkeypatch.setattr(ia, "_loeschen_versuchen", lambda o, z: False)
    assert ia.lauf(str(basis), [], versuche=3, pause=0) is False
    assert basis.exists()


def test_loeschen_starten_loescht_nicht_selbst_sondern_startet_einen_abgetrennten_helfer(lage, monkeypatch):
    basis, programm, daten = lage
    z = zip_mit_installer(basis.parent / "PBP-1.8.0.zip")
    aufrufe = []
    monkeypatch.setattr(ia.subprocess, "Popen", lambda cmd, **kw: aufrufe.append((cmd, kw)))
    p = ia.loeschen_starten(basis, "1.8.0", programm, daten)
    assert p["ordner"] == str(basis)
    assert basis.exists() and z.exists(), "das Loeschen darf nicht im Aufrufer geschehen"
    cmd, kw = aufrufe[0]
    assert cmd[2] == "lauf" and json.loads(cmd[3]) == {"ordner": str(basis), "zips": [str(z)]}
    assert str(basis) not in cmd[1], "der Helfer laeuft aus einer Kopie ausserhalb des zu loeschenden Ordners"
    assert kw["cwd"] != str(basis)
    if sys.platform == "win32":
        assert kw["creationflags"] & 0x00000008 and kw["creationflags"] & 0x08000000      # abgetrennt, ohne Fenster


def test_loeschen_starten_tut_bei_verweigerung_gar_nichts(lage, monkeypatch):
    basis, programm, daten = lage
    (basis / ".git").mkdir()
    aufrufe = []
    monkeypatch.setattr(ia.subprocess, "Popen", lambda cmd, **kw: aufrufe.append(cmd))
    p = ia.loeschen_starten(basis, "1.8.0", programm, daten)
    assert p["ordner"] is None and aufrufe == [] and basis.exists()


def test_der_kommandozeilenweg(lage, tmp_path):
    basis, programm, daten = lage
    db_mit(daten, "immer")
    py = sys.executable
    r = subprocess.run([py, str(WURZEL / "_installer_aufraeumen.py"), "einstellung", str(daten)], capture_output=True, text=True)
    assert r.stdout.strip() == "immer" and r.returncode == 0
    r = subprocess.run([py, str(WURZEL / "_installer_aufraeumen.py"), "plan", str(basis), "1.8.0", str(programm), str(daten)],
                       capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["ordner"] == str(basis) and basis.exists()
    (basis / "INSTALLIEREN.bat").unlink()
    r = subprocess.run([py, str(WURZEL / "_installer_aufraeumen.py"), "plan", str(basis), "1.8.0", str(programm), str(daten)],
                       capture_output=True, text=True)
    assert r.returncode == 1
    r = subprocess.run([py, str(WURZEL / "_installer_aufraeumen.py"), "unsinn"], capture_output=True, text=True)
    assert r.returncode == 2


def test_nur_standardbibliothek():
    import ast
    baum = ast.parse((WURZEL / "_installer_aufraeumen.py").read_text(encoding="utf-8"))
    module = set()
    for k in ast.walk(baum):
        if isinstance(k, ast.Import):
            module.update(a.name.split(".")[0] for a in k.names)
        elif isinstance(k, ast.ImportFrom) and k.level == 0:
            module.add((k.module or "").split(".")[0])
    assert sorted(m for m in module if m not in sys.stdlib_module_names) == []
