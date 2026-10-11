"""Testlauf 11.10.2026 (Werkstatt-PC), Fund PP26 -- Beta-Exit-Punkt 3.

Die Oberflaeche verspricht fuer die Texterkennung "installiert nach AppData (kein Admin noetig)". Auf dem frischen
Windows 11 ohne Administratorrechte scheiterte sie: das Setup von Tesseract verlangt in seinem Manifest Rechte, aus einem
Programm ohne Erhoehung laesst es sich gar nicht starten (WinError 740), und die Oberflaeche zeigte den rohen Text.
Mit `__COMPAT_LAYER=RunAsInvoker` lief das Setup durch, installierte aber "nur fuer mich" nach
`%LOCALAPPDATA%\\Programs\\Tesseract-OCR` und ignorierte das Ziel `/D=`. PBP fand es dort nicht, der Deinstaller raeumte es
nicht ab, und das deutsche Sprachpaket kam nicht mit.

Hier steht, was jetzt gilt -- ohne echtes Setup, ohne Netz; der Beleg mit dem echten Setup ist der Testlauf auf dem
Werkstatt-PC (Block D).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

WURZEL = Path(__file__).resolve().parents[1]
BAT = WURZEL / "DEINSTALLIEREN.bat"
GROESSE = 2 * 1024 * 1024
nur_windows = pytest.mark.skipif(os.name != "nt", reason="braucht Windows (cmd.exe, PowerShell)")


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


@pytest.fixture
def umgebung(tmp_db, tmp_path, monkeypatch):
    """Komponenten-Ordner und LOCALAPPDATA im Temp-Verzeichnis, Windows-Zweig, kein Netz, keine fremde Installation."""
    from bewerbungs_assistent.services import components
    ordner = tmp_path / "components"
    lokal = tmp_path / "Local"
    lokal.mkdir()
    monkeypatch.setattr(components, "components_dir", lambda: ordner)
    monkeypatch.setenv("LOCALAPPDATA", str(lokal))
    assert str(tmp_path) in str(components.components_dir()), "Komponenten-Ordner nicht isoliert"
    monkeypatch.setattr(components.sys, "platform", "win32")
    # Die Erkennung bleibt ECHT (um sie geht es) -- nur die Rechner-Umgebung wird neutralisiert:
    monkeypatch.setattr(components.shutil, "which", lambda name: None)
    definition = components.COMPONENT_DEFS["tesseract"]
    monkeypatch.setitem(definition, "bekannte_pfade_win", [])
    download = dict(definition["windows_download"])
    download["sha256"] = hashlib.sha256(b"x" * GROESSE).hexdigest()
    monkeypatch.setitem(definition, "windows_download", download)
    monkeypatch.setattr(components, "time", SimpleNamespace(sleep=lambda s: None, monotonic=lambda: 0.0))
    monkeypatch.setattr(components, "_binary_version", lambda b: "5.4.0")

    def _dl(url, target, progress, lo=0, hi=80):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x" * GROESSE)

    monkeypatch.setattr(components, "_download", _dl)

    def kein_echter_installer(*a, **kw):
        raise AssertionError("Im Test darf kein echter Installer laufen")

    monkeypatch.setattr(components.subprocess, "run", kein_echter_installer)
    return SimpleNamespace(db=tmp_db, ordner=ordner, lokal=lokal, c=components, definition=definition,
                           benutzer=lokal / "Programs" / "Tesseract-OCR",
                           binary_name=definition["binary_name"], uninstaller=definition["deinstaller_name"])


def _setup_legt_ab(umgebung, wohin: Path, mit_deinstaller=True):
    """Testdoppel des Setups: legt das Programm an einen Ort (ohne Erhoehung: 'nur fuer mich') und meldet Erfolg."""
    def _lauf(argv, **kw):
        wohin.mkdir(parents=True, exist_ok=True)
        (wohin / umgebung.binary_name).write_text("x")
        if mit_deinstaller:
            (wohin / umgebung.uninstaller).write_text("x")
        (wohin / "tessdata").mkdir(exist_ok=True)
        (wohin / "tessdata" / "eng.traineddata").write_text("x")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return _lauf


def _dateien(ordner: Path) -> list[str]:
    if not ordner.exists():
        return []
    return sorted(p.relative_to(ordner).as_posix() for p in ordner.rglob("*") if p.is_file())


# ══ Start ohne Erhoehung ═════════════════════════════════════════════════════════════════════════════════════════

def test_das_setup_startet_ohne_erhoehung(umgebung, monkeypatch):
    c = umgebung.c
    gesehen = {}

    def lauf(argv, **kw):
        gesehen["env"] = kw.get("env") or {}
        gesehen["argv"] = argv
        return _setup_legt_ab(umgebung, umgebung.benutzer)(argv, **kw)

    monkeypatch.setattr(c.subprocess, "run", lauf)
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "installiert", ergebnis
    assert "RunAsInvoker" in gesehen["env"].get("__COMPAT_LAYER", "").split(), "ohne diese Umgebung fragt Windows nach Rechten"
    assert gesehen["argv"][1] == "/S" and gesehen["argv"][2].startswith("/D="), "der Aufruf selbst bleibt wie er war"


def test_eine_vorhandene_kompatibilitaetsschicht_bleibt_erhalten(umgebung, monkeypatch):
    c = umgebung.c
    monkeypatch.setenv("__COMPAT_LAYER", "WIN7RTM")
    assert c._setup_umgebung()["__COMPAT_LAYER"].split() == ["WIN7RTM", "RunAsInvoker"]
    monkeypatch.setenv("__COMPAT_LAYER", "RunAsInvoker")
    assert c._setup_umgebung()["__COMPAT_LAYER"].split() == ["RunAsInvoker"], "nicht doppelt"


def test_ausserhalb_von_windows_aendert_sich_die_umgebung_nicht(umgebung, monkeypatch):
    c = umgebung.c
    monkeypatch.setattr(c.sys, "platform", "linux")
    monkeypatch.delenv("__COMPAT_LAYER", raising=False)
    assert "__COMPAT_LAYER" not in c._setup_umgebung()


def test_fordert_windows_trotzdem_rechte_steht_es_in_alltagssprache(umgebung, monkeypatch):
    c = umgebung.c

    def lauf(argv, **kw):
        exc = OSError(740, "Der angeforderte Vorgang erfordert eine Erhöhung")
        exc.winerror = 740
        raise exc

    monkeypatch.setattr(c.subprocess, "run", lauf)
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler"
    text = ergebnis["fehler"]
    assert "Administratorrechte" in text and "tesseract.exe" in text, "sagt, was los ist und was der Mensch tun kann"
    assert "WinError" not in text and "740" not in text, "kein roher Systemtext in der Oberflaeche"
    assert umgebung.db.get_component_state("tesseract")["last_error"] == text
    assert _dateien(umgebung.ordner) == [], "nichts bleibt liegen"


# ══ Der tatsaechliche Ort ════════════════════════════════════════════════════════════════════════════════════════

def test_ohne_administratorrechte_wird_der_ort_nur_fuer_mich_gefunden_und_gemerkt(umgebung, monkeypatch):
    """Der Fall vom Werkstatt-PC: das Setup ignoriert /D= und legt das Programm unter LOCALAPPDATA ab."""
    c = umgebung.c
    monkeypatch.setattr(c.subprocess, "run", _setup_legt_ab(umgebung, umgebung.benutzer))
    ergebnis = c.install_component(umgebung.db, "tesseract")
    echt = umgebung.benutzer / umgebung.binary_name
    assert ergebnis["status"] == "installiert" and ergebnis["binary"] == str(echt), ergebnis
    assert umgebung.db.get_component_state("tesseract")["install_path"] == str(echt)
    marker = c.eigene_installation("tesseract")
    assert marker and marker["verzeichnis"] == str(umgebung.benutzer)
    assert marker["deinstaller"] == str(umgebung.benutzer / umgebung.uninstaller)
    assert marker["binary"] == str(echt) and marker["version"] == "5.4.0"
    status = c.get_component_status(umgebung.db, "tesseract")
    assert status["verfuegbar"] is True and status["quelle"] == "pbp", "gilt als von PBP installiert -- 'Entfernen' ist da"


def test_wo_das_setup_dem_ziel_folgt_gibt_es_keinen_marker(umgebung, monkeypatch):
    c = umgebung.c

    def lauf(argv, **kw):
        return _setup_legt_ab(umgebung, Path(argv[2][len("/D="):]))(argv, **kw)

    monkeypatch.setattr(c.subprocess, "run", lauf)
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "installiert"
    assert c.eigene_installation("tesseract") is None
    assert (umgebung.ordner / "tesseract" / umgebung.binary_name).is_file()


def test_ist_nirgends_etwas_angekommen_bleibt_nichts_liegen(umgebung, monkeypatch):
    c = umgebung.c
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="", stderr=""))
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler" and "nicht gefunden" in ergebnis["fehler"]
    assert c.eigene_installation("tesseract") is None
    assert _dateien(umgebung.ordner) == []


def test_eine_vorhandene_installation_nur_fuer_mich_wird_als_extern_erkannt(umgebung):
    c = umgebung.c
    umgebung.benutzer.mkdir(parents=True)
    (umgebung.benutzer / umgebung.binary_name).write_text("x")
    status = c.get_component_status(umgebung.db, "tesseract")
    assert status["verfuegbar"] is True and status["quelle"] == "extern"
    # und sie wird nicht noch einmal geladen
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "installiert" and "heruntergeladen" in ergebnis["hinweis"]


def test_der_bekannte_ort_haengt_an_localappdata_und_gilt_nur_unter_windows(umgebung, monkeypatch):
    c = umgebung.c
    assert c._benutzer_ordner_win(umgebung.definition) == umgebung.benutzer
    monkeypatch.setattr(c.sys, "platform", "linux")
    assert c._benutzer_ordner_win(umgebung.definition) is None
    monkeypatch.setattr(c.sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA")
    assert c._benutzer_ordner_win(umgebung.definition) is None


# ══ Entfernen ════════════════════════════════════════════════════════════════════════════════════════════════════

def _installiert(umgebung, monkeypatch):
    c = umgebung.c
    monkeypatch.setattr(c.subprocess, "run", _setup_legt_ab(umgebung, umgebung.benutzer))
    assert c.install_component(umgebung.db, "tesseract")["status"] == "installiert"
    # das deutsche Sprachpaket legt PBP selbst dazu -- es gehoert nicht zum Setup
    (umgebung.benutzer / "tessdata" / "deu.traineddata").write_text("x")


def test_entfernen_nutzt_das_eigene_deinstallationsprogramm_ohne_erhoehung(umgebung, monkeypatch):
    c = umgebung.c
    _installiert(umgebung, monkeypatch)
    aufrufe = []

    def deinstaller(argv, **kw):
        aufrufe.append((argv, kw.get("env") or {}))
        (umgebung.benutzer / umgebung.binary_name).unlink()      # das Setup raeumt sein Programm weg ...
        return SimpleNamespace(returncode=0, stdout="", stderr="")  # ... und kehrt sofort zurueck

    monkeypatch.setattr(c.subprocess, "run", deinstaller)
    ergebnis = c.uninstall_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "entfernt" and ergebnis["pbp_installation_geloescht"] is True, ergebnis
    argv, env = aufrufe[0]
    assert argv == [str(umgebung.benutzer / umgebung.uninstaller), "/S"]
    assert "RunAsInvoker" in env.get("__COMPAT_LAYER", "").split()
    assert not umgebung.benutzer.exists(), "auch, was PBP selbst hineingelegt hat (Sprachdaten), geht mit"
    assert not (umgebung.ordner / "tesseract").exists()
    assert umgebung.db.get_component_state("tesseract")["status"] == "nicht_installiert"


def test_ohne_deinstallationsprogramm_geht_der_von_pbp_angelegte_ordner_trotzdem(umgebung, monkeypatch):
    c = umgebung.c
    _installiert(umgebung, monkeypatch)
    (umgebung.benutzer / umgebung.uninstaller).unlink()
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: pytest.fail("kein Programm, nichts zu starten"))
    assert c.uninstall_component(umgebung.db, "tesseract")["status"] == "entfernt"
    assert not umgebung.benutzer.exists()


def test_ein_marker_der_auf_einen_fremden_ort_zeigt_wird_verweigert(umgebung, monkeypatch, tmp_path):
    """Der Marker allein nennt keinen Pfad, der geloescht wird: nur der eine Ort, an dem das Setup ohne Rechte installiert."""
    c = umgebung.c
    fremd = tmp_path / "Eigene Dateien"
    fremd.mkdir()
    (fremd / "wichtig.txt").write_text("nicht loeschen")
    (umgebung.ordner / "tesseract").mkdir(parents=True)
    (umgebung.ordner / "tesseract" / c.EIGENE_INSTALLATION).write_text(
        json.dumps({"verzeichnis": str(fremd), "binary": str(fremd / "tesseract.exe")}), encoding="utf-8")
    umgebung.db.set_component_state("tesseract", "installiert", install_path=str(fremd / "tesseract.exe"))
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: pytest.fail("nichts starten"))
    ergebnis = c.uninstall_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler" and "unerwarteten Ort" in ergebnis["fehler"]
    assert (fremd / "wichtig.txt").read_text() == "nicht loeschen"
    assert umgebung.db.get_component_state("tesseract")["status"] == "installiert", "die Registrierung bleibt"


@pytest.mark.parametrize("wo", ["wurzel", "programme"])
def test_auch_ein_uebergeordneter_ordner_wird_nie_angefasst(umgebung, monkeypatch, wo):
    """LOCALAPPDATA selbst oder Programs sind keine Tesseract-Installation."""
    c = umgebung.c
    ziel = umgebung.lokal if wo == "wurzel" else umgebung.lokal / "Programs"
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "anderes.txt").write_text("x")
    (umgebung.ordner / "tesseract").mkdir(parents=True)
    (umgebung.ordner / "tesseract" / c.EIGENE_INSTALLATION).write_text(
        json.dumps({"verzeichnis": str(ziel)}), encoding="utf-8")
    ergebnis = c.uninstall_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler"
    assert (ziel / "anderes.txt").is_file()


def test_ein_kaputter_marker_wird_nicht_als_installation_gelesen(umgebung):
    c = umgebung.c
    (umgebung.ordner / "tesseract").mkdir(parents=True)
    (umgebung.ordner / "tesseract" / c.EIGENE_INSTALLATION).write_text("{kein json", encoding="utf-8")
    assert c.eigene_installation("tesseract") is None


def test_liegt_in_vergleicht_ohne_grosskleinschreibung_wie_unter_windows(umgebung):
    c = umgebung.c
    assert c._liegt_in(Path("C:/Users/x/AppData/Local/Programs/Tesseract-OCR"),
                       Path("c:/users/x/appdata/local/programs/tesseract-ocr")) or os.name != "nt"
    assert c._liegt_in(umgebung.benutzer / "tessdata", umgebung.benutzer)
    assert not c._liegt_in(umgebung.benutzer.parent / "Tesseract-OCR-fremd", umgebung.benutzer)


# ══ Uebersicht Speicher & Downloads ══════════════════════════════════════════════════════════════════════════════

def test_die_speicheruebersicht_nennt_den_echten_ort_mit_groesse(umgebung, monkeypatch):
    c = umgebung.c
    _installiert(umgebung, monkeypatch)
    (umgebung.benutzer / "tessdata" / "deu.traineddata").write_bytes(b"x" * 5000)
    from bewerbungs_assistent.services import speicher
    ort = speicher._ort_komponenten(umgebung.db, 5.0)
    eintrag = [e for e in ort["eintraege"] if "Programmordner" in e["name"]]
    assert eintrag, ort
    assert eintrag[0]["pfad"] == str(umgebung.benutzer) and eintrag[0]["bytes"] >= 5000


# ══ Hinweise in Alltagssprache ═══════════════════════════════════════════════════════════════════════════════════

def test_der_sprachhinweis_nennt_keine_werkzeugnamen(umgebung, monkeypatch):
    from bewerbungs_assistent.services import ocr_service
    monkeypatch.setattr(ocr_service, "available_languages", lambda db: ["eng"])
    sprachen, hinweis = ocr_service._pick_langs(umgebung.db)
    assert sprachen == "eng" and hinweis
    for jargon in ("ensure_language", "komponente_installieren", "'eng'", "'deu'"):
        assert jargon not in hinweis, f"Werkzeug- und Codewoerter gehoeren nicht in einen Satz fuer Menschen: {jargon}"
    assert "Erweiterungen" in hinweis, "sagt, wo es weitergeht"


def test_ohne_sprachdaten_steht_kein_werkzeugname_im_fehler(umgebung, monkeypatch, tmp_path):
    from bewerbungs_assistent.services import ocr_service
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(ocr_service, "find_component_binary", lambda db, name: str(tmp_path / "tesseract.exe"))
    monkeypatch.setattr(ocr_service, "_pick_langs", lambda db: ("", ""))
    erg = ocr_service.ocr_pdf(umgebung.db, pdf)
    assert erg["status"] == "fehler" and "ensure_language" not in erg["fehler"]
    assert "Erweiterungen" in erg["fehler"]


def test_die_oberflaeche_verspricht_nichts_was_nicht_stimmt():
    """Der Knopf sagt 'kein Admin noetig' -- dieser Test haelt fest, dass der Satz wirklich dort steht (und damit gilt)."""
    quelle = (WURZEL / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert "kein Admin nötig" in quelle


# ══ Deinstaller (Windows) ════════════════════════════════════════════════════════════════════════════════════════

def _bat() -> str:
    return BAT.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def _unterprogramm() -> str:
    text = _bat()
    return text[text.index(":: --- texterkennung Anfang"):text.index(":: --- texterkennung Ende")]


def test_die_bat_ruft_es_in_schritt_5_auf_und_nennt_die_komponenten_am_anfang():
    text = _bat()
    aufruf = text.index("call :texterkennung_entfernen")
    assert text.index("[5/7] Entferne Runtime-Dateien") < aufruf < text.index("[6/7] Optional: Backup")
    assert "Nachinstallierte Komponenten" in text.split("Hinweis:")[0], "die Liste am Anfang nennt es"


def test_die_bat_fasst_nur_den_einen_ort_an_und_nur_mit_dem_marker():
    u = _unterprogramm()
    assert 'if not exist "%BASE_INSTALL%\\components\\tesseract\\pbp-installation.json" exit /b 9' in u
    assert "Programs\\Tesseract-OCR" in u and "RunAsInvoker" in u
    assert "Remove-Item -LiteralPath $d" in u and "-Recurse" in u
    # Das Deinstallationsprogramm des Setups kehrt sofort zurueck (es kopiert sich nach TEMP): es wird gewartet, bis das
    # Programm wirklich weg ist -- erst dann raeumt der Rest auf. Ohne die Schleife liefe `Remove-Item` mitten hinein.
    assert "Test-Path -LiteralPath (Join-Path $d 'tesseract.exe')" in u and "Start-Sleep -Seconds 1" in u


def _lauf_texterkennung(tmp_path: Path, lokal: Path, basis: Path):
    assert str(tmp_path) in str(lokal) and str(tmp_path) in str(basis), "QA-Isolation: nie der echte LOCALAPPDATA"
    log = tmp_path / "protokoll.txt"
    kopf = ["@echo off", "setlocal EnableDelayedExpansion", f'set "LOCALAPPDATA={lokal}"', f'set "BASE_INSTALL={basis}"',
            f'set "LOGFILE={log}"', "call :texterkennung_entfernen", "echo ERGEBNIS=!errorlevel!", "exit /b 0", ""]
    bat = tmp_path / "tess.bat"
    bat.write_bytes(("\r\n".join(kopf) + _unterprogramm().replace("\n", "\r\n")).encode("cp850", errors="replace"))
    r = subprocess.run(["cmd.exe", "/c", str(bat)], capture_output=True, creationflags=0x08000000, timeout=180)
    ausgabe = (r.stdout + r.stderr).decode("cp850", errors="replace")
    protokoll = log.read_text(encoding="cp850", errors="replace") if log.exists() else ""
    ergebnis = next((z.split("=", 1)[1].strip() for z in ausgabe.splitlines() if z.startswith("ERGEBNIS=")), None)
    return ergebnis, ausgabe, protokoll


def _marker_und_programm(tmp_path: Path, mit_marker=True, mit_deinstaller=True, name="Local"):
    lokal = tmp_path / name
    basis = lokal / "BewerbungsAssistent"
    ziel = lokal / "Programs" / "Tesseract-OCR"
    (ziel / "tessdata").mkdir(parents=True)
    (ziel / "tessdata" / "deu.traineddata").write_bytes(b"x" * 100)
    if mit_deinstaller:
        # eine beliebige, harmlose Programmdatei unter dem Namen des Deinstallationsprogramms
        shutil.copy2(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "whoami.exe", ziel / "tesseract-uninstall.exe")
    if mit_marker:
        (basis / "components" / "tesseract").mkdir(parents=True)
        (basis / "components" / "tesseract" / "pbp-installation.json").write_text(
            json.dumps({"verzeichnis": str(ziel)}), encoding="utf-8")
    return lokal, basis, ziel


@nur_windows
def test_die_bat_entfernt_die_von_pbp_eingerichtete_texterkennung(tmp_path):
    lokal, basis, ziel = _marker_und_programm(tmp_path)
    ergebnis, ausgabe, protokoll = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "0", (ausgabe, protokoll)
    assert not ziel.exists(), "auch die nachgeladenen Sprachdaten gehen mit"
    assert "Texterkennung entfernt" in protokoll


@nur_windows
def test_die_bat_fasst_ohne_marker_nichts_an(tmp_path):
    """Eine Tesseract-Installation, die der Mensch selbst angelegt hat, gehoert ihm: kein Marker, keine Hand dran."""
    lokal, basis, ziel = _marker_und_programm(tmp_path, mit_marker=False)
    ergebnis, ausgabe, _ = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "9", ausgabe
    assert (ziel / "tessdata" / "deu.traineddata").is_file()


@nur_windows
def test_die_bat_kommt_auch_ohne_deinstallationsprogramm_und_ohne_ordner_zurecht(tmp_path):
    lokal, basis, ziel = _marker_und_programm(tmp_path, mit_deinstaller=False)
    ergebnis, ausgabe, _ = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "0" and not ziel.exists(), ausgabe
    # ein zweites Mal: Marker da, Ordner schon weg
    ergebnis2, ausgabe2, protokoll2 = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis2 == "0", ausgabe2
    assert "nicht vorhanden" in protokoll2


@nur_windows
def test_die_bat_vertraegt_leerzeichen_und_klammern_im_pfad(tmp_path):
    lokal, basis, ziel = _marker_und_programm(tmp_path, name="O'Brien Test (privat)")
    ergebnis, ausgabe, protokoll = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "0" and not ziel.exists(), (ausgabe, protokoll)


# ══ Kleinigkeiten aus demselben Lauf ═════════════════════════════════════════════════════════════════════════════

def test_die_gefahrenzone_zeigt_keine_markdown_zeichen_als_text():
    """Die Oberflaeche zeigt Klartext: `**` stand dort woertlich ("**Mit den aussortierten Stellen ...**")."""
    from bewerbungs_assistent.services import loeschbereiche
    for bereich, text in loeschbereiche.BESCHREIBUNG.items():
        assert "**" not in text and "__" not in text, f"{bereich}: {text}"
    assert "Lernsignale" in loeschbereiche.BESCHREIBUNG["stellen"], "der Hinweis selbst bleibt"
