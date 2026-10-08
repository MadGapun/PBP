"""Auto-Update (#1093): der Installer legt den Programmordner mit Versionsordnern an.

`_programm_einrichten.py` ist der Teil von `INSTALLIEREN.bat`, der frueher ein `xcopy` von `src` war. Er ist
Python, damit sich seine Zusagen testen lassen — das `.bat` ruft ihn nur auf.

Zusagen: die neue Fassung steht vollstaendig da, bevor `aktuell.txt` umgeschaltet wird; scheitert etwas, ist
`aktuell.txt` unberuehrt; der alte Aufbau (`app/src`) verschwindet erst danach; ein zweiter Lauf desselben
Installers aendert nichts Falsches.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "src"))

import _programm_einrichten as einrichten_modul  # noqa: E402
import bewerbungs_assistent_boot as boot  # noqa: E402

PYTHON = sys.executable


def basis_bauen(ziel: Path, version: str = "1.8.0", *, mit_launcher=True, extra=None) -> Path:
    """Ein entpackter Installationsordner: kleines Programm, ECHTER Startbaustein, ECHTER Starter."""
    (ziel / "src" / "bewerbungs_assistent").mkdir(parents=True)
    (ziel / "src" / "bewerbungs_assistent" / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    (ziel / "src" / "bewerbungs_assistent" / "__main__.py").write_text("print('lief')\n", encoding="utf-8")
    (ziel / "src" / "bewerbungs_assistent" / "__pycache__").mkdir()
    (ziel / "src" / "bewerbungs_assistent" / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\0")
    shutil.copytree(WURZEL / "src" / "bewerbungs_assistent_boot", ziel / "src" / "bewerbungs_assistent_boot",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (ziel / "start_dashboard.py").write_text("print('dashboard')\n", encoding="utf-8")
    (ziel / "_selftest.py").write_text("print('OK')\n", encoding="utf-8")
    if mit_launcher:
        (ziel / "installer" / "boot").mkdir(parents=True)
        shutil.copy2(WURZEL / "installer" / "boot" / "start_dashboard_launcher.py",
                     ziel / "installer" / "boot" / "start_dashboard_launcher.py")
    for name, inhalt in (extra or {}).items():
        p = ziel / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(inhalt, encoding="utf-8")
    return ziel


def lauf(basis: Path, app: Path):
    return subprocess.run([PYTHON, str(WURZEL / "_programm_einrichten.py"), str(basis), str(app)],
                          capture_output=True, text=True, timeout=120)


def status(app: Path) -> dict:
    return json.loads((app / "update_status.json").read_text(encoding="utf-8"))


# ══ Frische Installation ═══════════════════════════════════════════════════════════════

def test_eine_frische_installation_legt_alles_an(tmp_path):
    basis, app = basis_bauen(tmp_path / "zip"), tmp_path / "app"
    r = lauf(basis, app)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[OK] Version 1.8.0 eingerichtet" in r.stdout
    assert (app / "aktuell.txt").read_text().strip() == "1.8.0"
    ordner = app / "versions" / "1.8.0"
    assert (ordner / ".fertig").is_file() and (ordner / "manifest.json").is_file()
    assert (ordner / "src" / "bewerbungs_assistent" / "__init__.py").is_file()
    assert (ordner / "start_dashboard.py").is_file() and (ordner / "_selftest.py").is_file()
    assert not list(ordner.rglob("__pycache__")), "Bytecode gehoert nicht in die Fassung"
    assert (app / "boot" / "bewerbungs_assistent_boot" / "__init__.py").is_file()
    assert (app / "start_dashboard.py").read_text(encoding="utf-8").startswith('"""PBP Dashboard-Starter')
    assert not (app / "src").exists() and not list((app / "versions").glob("*.neu"))
    assert boot.gueltige_fassungen(app) == ["1.8.0"] and boot.lese_aktuell(app) == "1.8.0"
    assert json.loads((ordner / "manifest.json").read_text())["installiert_mit"] == "installer"


def test_die_eingerichtete_fassung_startet_ueber_den_startbaustein(tmp_path):
    """Der ganze Weg im echten Prozess: python -m bewerbungs_assistent_boot, aus dem Programmordner heraus."""
    basis, app = basis_bauen(tmp_path / "zip"), tmp_path / "app"
    assert lauf(basis, app).returncode == 0
    env = {**os.environ, "PYTHONPATH": str(app / "boot"), "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PBP_APP_DIR", None)
    r = subprocess.run([PYTHON, "-m", "bewerbungs_assistent_boot"], capture_output=True, text=True, env=env, timeout=60,
                       cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "lief" in r.stdout          # der Startbaustein fand den Programmordner ohne PBP_APP_DIR (er liegt unter app/boot)


def test_der_starter_im_programmordner_startet_das_dashboard_der_aktuellen_fassung(tmp_path):
    basis, app = basis_bauen(tmp_path / "zip"), tmp_path / "app"
    assert lauf(basis, app).returncode == 0
    env = {k: v for k, v in os.environ.items() if k not in ("PBP_APP_DIR", "PYTHONPATH")}
    r = subprocess.run([PYTHON, str(app / "start_dashboard.py")], capture_output=True, text=True, env=env, timeout=60,
                       cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "dashboard" in r.stdout


# ══ Update eines alten Aufbaus ═════════════════════════════════════════════════════════

def alter_aufbau(app: Path):
    (app / "src" / "bewerbungs_assistent").mkdir(parents=True)
    (app / "src" / "bewerbungs_assistent" / "__init__.py").write_text('__version__ = "1.7.150"\n', encoding="utf-8")
    (app / "_selftest.py").write_text("print('alt')\n", encoding="utf-8")
    (app / "python").mkdir()
    (app / "python" / "python312._pth").write_bytes(b"python312.zip\r\n.\r\n../src\r\nimport site\r\n")
    (app / "Dashboard starten.bat").write_text("@echo off\r\n", encoding="utf-8")


def test_der_alte_aufbau_wird_ersetzt_nicht_zusammengeworfen(tmp_path):
    basis, app = basis_bauen(tmp_path / "zip"), tmp_path / "app"
    alter_aufbau(app)
    r = lauf(basis, app)
    assert r.returncode == 0, r.stdout
    assert not (app / "src").exists() and not (app / "_selftest.py").exists()
    pth = (app / "python" / "python312._pth").read_bytes()
    assert pth == b"python312.zip\r\n.\r\nimport site\r\n../boot\r\n", pth        # Zeilenenden bleiben, ../src weg, ../boot da
    assert (app / "Dashboard starten.bat").exists(), "was nicht zum Aufbau gehoert, bleibt"


def test_pth_anpassen_ist_idempotent_und_aktiviert_import_site(tmp_path):
    (tmp_path / "python312._pth").write_bytes(b"python312.zip\n.\n#import site\n../src\n")
    assert einrichten_modul.pth_anpassen(tmp_path) is True
    erster = (tmp_path / "python312._pth").read_bytes()
    assert erster == b"python312.zip\n.\nimport site\n../boot\n"
    assert einrichten_modul.pth_anpassen(tmp_path) is False
    assert (tmp_path / "python312._pth").read_bytes() == erster
    assert einrichten_modul.pth_anpassen(tmp_path / "gibtsnicht") is False


# ══ Zweite Installation ════════════════════════════════════════════════════════════════

def test_eine_neuere_installation_behaelt_die_alte_fassung_und_merkt_sie_als_rueckweg(tmp_path):
    app = tmp_path / "app"
    assert lauf(basis_bauen(tmp_path / "zip1", "1.8.0"), app).returncode == 0
    assert lauf(basis_bauen(tmp_path / "zip2", "1.8.1"), app).returncode == 0
    assert boot.gueltige_fassungen(app) == ["1.8.1", "1.8.0"]
    assert boot.lese_aktuell(app) == "1.8.1" and status(app)["vorherige"] == "1.8.0"
    assert "start" not in status(app), "eine frische Installation hat keinen 'gescheiterten' Start in der Vorgeschichte"


def test_der_rueckweg_ist_die_zuletzt_bestaetigte_fassung(tmp_path):
    app = tmp_path / "app"
    lauf(basis_bauen(tmp_path / "zip1", "1.8.0"), app)
    lauf(basis_bauen(tmp_path / "zip2", "1.8.1"), app)
    s = status(app)
    s["bestaetigt"] = "1.8.0"                              # 1.8.1 wurde nie gestartet
    (app / "update_status.json").write_text(json.dumps(s), encoding="utf-8")
    lauf(basis_bauen(tmp_path / "zip3", "1.8.2"), app)
    assert status(app)["vorherige"] == "1.8.0"


def test_dieselbe_fassung_noch_einmal_ersetzt_den_ordner_und_vergisst_ihr_scheitern(tmp_path):
    app = tmp_path / "app"
    lauf(basis_bauen(tmp_path / "zip", "1.8.0"), app)
    (app / "versions" / "1.8.0" / "alt.txt").write_text("Rest")
    s = status(app)
    s.update(gescheitert=["1.8.0", "1.8.5"], rueckgang={"von": "1.8.0", "nach": "1.7.0", "gemeldet": False},
             start={"version": "1.8.0", "versuche": 2, "bestaetigt": False})
    (app / "update_status.json").write_text(json.dumps(s), encoding="utf-8")
    assert lauf(tmp_path / "zip", app).returncode == 0
    assert not (app / "versions" / "1.8.0" / "alt.txt").exists()
    s = status(app)
    assert s["gescheitert"] == ["1.8.5"] and "rueckgang" not in s and "start" not in s


def test_eine_aeltere_version_als_die_installierte_wird_gemeldet(tmp_path):
    app = tmp_path / "app"
    lauf(basis_bauen(tmp_path / "zip2", "1.8.1"), app)
    r = lauf(basis_bauen(tmp_path / "zip1", "1.8.0"), app)
    assert r.returncode == 0 and "AELTERE Version" in r.stdout and boot.lese_aktuell(app) == "1.8.0"


# ══ Fehler ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("fehlt", ["start_dashboard.py", "_selftest.py", "installer/boot/start_dashboard_launcher.py",
                                   "src/bewerbungs_assistent_boot", "src/bewerbungs_assistent/__init__.py"])
def test_fehlt_etwas_wird_nichts_veraendert(tmp_path, fehlt):
    app = tmp_path / "app"
    lauf(basis_bauen(tmp_path / "zip1", "1.8.0"), app)
    vorher = sorted(p.relative_to(app).as_posix() for p in app.rglob("*"))
    basis = basis_bauen(tmp_path / "zip2", "1.8.1")
    ziel = basis / fehlt
    shutil.rmtree(ziel) if ziel.is_dir() else ziel.unlink()
    r = lauf(basis, app)
    assert r.returncode == 1 and "[FEHLER]" in r.stdout
    assert sorted(p.relative_to(app).as_posix() for p in app.rglob("*")) == vorher
    assert boot.lese_aktuell(app) == "1.8.0"


def test_eine_ungueltige_versionsnummer_wird_abgewiesen(tmp_path):
    basis = basis_bauen(tmp_path / "zip", "banane")
    r = lauf(basis, tmp_path / "app")
    assert r.returncode == 1 and "keine gueltige Versionsnummer" in r.stdout
    assert not (tmp_path / "app" / "aktuell.txt").exists()


def test_bricht_das_kopieren_mittendrin_ab_bleibt_aktuell_txt_unberuehrt_und_der_rest_weg(tmp_path, monkeypatch):
    app = tmp_path / "app"
    lauf(basis_bauen(tmp_path / "zip1", "1.8.0"), app)
    basis = basis_bauen(tmp_path / "zip2", "1.8.1")
    echt = shutil.copytree
    zaehler = {"n": 0}

    def zickig(quelle, ziel, *a, **kw):
        zaehler["n"] += 1
        if zaehler["n"] == 2:                                  # der Startbaustein, nach dem Programm
            raise OSError("Platte voll")
        return echt(quelle, ziel, *a, **kw)

    monkeypatch.setattr(einrichten_modul.shutil, "copytree", zickig)
    with pytest.raises(OSError):
        einrichten_modul.einrichten(basis, app)
    assert boot.lese_aktuell(app) == "1.8.0"
    assert not list((app / "versions").glob("*.neu"))


def test_ein_gesperrter_alter_ordner_ist_ein_abbruch_mit_klarem_grund(tmp_path, monkeypatch):
    app = tmp_path / "app"
    lauf(basis_bauen(tmp_path / "zip1", "1.8.0"), app)

    def sperre(pfad):
        raise einrichten_modul.Abbruch(f"{pfad} laesst sich nicht entfernen (gesperrt?)")

    monkeypatch.setattr(einrichten_modul, "_loeschen", sperre)
    with pytest.raises(einrichten_modul.Abbruch):
        einrichten_modul.einrichten(basis_bauen(tmp_path / "zip2", "1.8.0"), app)
    assert boot.lese_aktuell(app) == "1.8.0"


def test_falscher_aufruf_gibt_exit_1_mit_hinweis():
    r = subprocess.run([PYTHON, str(WURZEL / "_programm_einrichten.py")], capture_output=True, text=True, timeout=30)
    assert r.returncode == 1 and "Aufruf:" in r.stderr


# ══ Die echte Quelle ═════════════════════════════════════════════════════════════════════

def test_der_echte_quellbaum_laesst_sich_einrichten_und_wird_vom_startbaustein_gefunden(tmp_path):
    """Nicht das Spielzeug-Programm, sondern dieses Repository: was der Installer aus dem ZIP macht."""
    basis = tmp_path / "zip"
    shutil.copytree(WURZEL / "src", basis / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("start_dashboard.py", "_selftest.py"):
        shutil.copy2(WURZEL / name, basis / name)
    (basis / "installer" / "boot").mkdir(parents=True)
    shutil.copy2(WURZEL / "installer" / "boot" / "start_dashboard_launcher.py", basis / "installer" / "boot")
    app = tmp_path / "app"
    r = lauf(basis, app)
    assert r.returncode == 0, r.stdout
    from bewerbungs_assistent import __version__
    assert boot.gueltige_fassungen(app) == [__version__]
    assert (app / "versions" / __version__ / "src" / "bewerbungs_assistent" / "server.py").is_file()


# ══ Claude-Konfiguration und Selbsttest ═════════════════════════════════════════════════

def _setup_claude():
    import importlib.util
    spec = importlib.util.spec_from_file_location("setup_claude_boot_pruefling", WURZEL / "_setup_claude.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_die_claude_konfiguration_startet_den_startbaustein_wenn_er_eingerichtet_ist(tmp_path):
    sc = _setup_claude()
    app = tmp_path / "app"
    lauf(basis_bauen(tmp_path / "zip"), app)
    such = sc._suchpfad_im_programmordner(str(app))
    assert Path(such) == app / "boot" and sc.startmodul_fuer(such) == "bewerbungs_assistent_boot"
    eintrag = sc.eintrag_bauen("C:/x/python.exe", such, "C:/daten")
    assert eintrag["args"] == ["-m", "bewerbungs_assistent_boot"] and eintrag["env"]["PYTHONPATH"] == str(app / "boot")


def test_ohne_startbaustein_bleibt_es_beim_alten_aufbau(tmp_path):
    sc = _setup_claude()
    app = tmp_path / "app"
    (app / "src").mkdir(parents=True)
    such = sc._suchpfad_im_programmordner(str(app))
    assert Path(such) == app / "src" and sc.startmodul_fuer(such) == "bewerbungs_assistent"
    assert sc.eintrag_bauen("C:/x/python.exe", such, "C:/daten")["args"] == ["-m", "bewerbungs_assistent"]


def test_im_entwicklermodus_zeigt_pythonpath_auf_src_und_startet_das_programm_selbst(tmp_path):
    """`<Projekt>/src` enthaelt beide Pakete (Programm und Startbaustein); gestartet wird immer das Programm."""
    sc = _setup_claude()
    assert sc.startmodul_fuer(str(WURZEL / "src")) == "bewerbungs_assistent"
    assert sc.startmodul_fuer(str(tmp_path / "boot")) == "bewerbungs_assistent", "ein Ordner namens boot ohne versions/ daneben"


def test_eigene_einstellungen_im_bisherigen_eintrag_bleiben_auch_beim_wechsel_auf_den_startbaustein(tmp_path):
    sc = _setup_claude()
    alt = {"command": "x", "args": ["-m", "bewerbungs_assistent"],
           "env": {"BA_DATA_DIR": "D:/meine-daten", "BA_DASHBOARD_PORT": "8300", "PYTHONPATH": "C:/alt/src"}}
    app = tmp_path / "app"
    lauf(basis_bauen(tmp_path / "zip"), app)
    neu = sc.eintrag_bauen("C:/x/python.exe", sc._suchpfad_im_programmordner(str(app)), "C:/daten", alt)
    assert neu["env"]["BA_DATA_DIR"] == "D:/meine-daten" and neu["env"]["BA_DASHBOARD_PORT"] == "8300"
    assert neu["env"]["PYTHONPATH"] == str(app / "boot") and neu["args"] == ["-m", "bewerbungs_assistent_boot"]


def test_der_selbsttest_findet_zusatzpakete_der_fassung_im_site_ordner(tmp_path):
    """Der echte Selbsttest, aus einem Fassungsordner mit `site/` heraus: das Programm zuerst, dann die Zusatzpakete,
    und beides VOR den Paketen der Laufzeit (so wie der Startbaustein es beim Start der Fassung einrichtet)."""
    ordner = tmp_path / "fassung"
    shutil.copytree(WURZEL / "src", ordner / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(WURZEL / "_selftest.py", ordner / "_selftest.py")
    (ordner / "site").mkdir()
    (ordner / "site" / "nur_hier_zu_finden.py").write_text("X = 1\n", encoding="utf-8")
    wrapper = (f"import runpy, sys\nrunpy.run_path(r'{ordner / '_selftest.py'}', run_name='__main__')\n"
               "import nur_hier_zu_finden\nprint('PFAD', sys.path[0], sys.path[1])\n")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "BA_DATA_DIR")}
    r = subprocess.run([PYTHON, "-c", wrapper], capture_output=True, text=True, env=env, timeout=180, cwd=str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"PFAD {ordner / 'src'} {ordner / 'site'}" in r.stdout
    assert r.stdout.count("OK") >= 1
