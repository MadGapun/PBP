"""Testlauf 11.10.2026 (Werkstatt-PC), Fund PP26 -- Beta-Exit-Punkt 3.

Die Oberflaeche verspricht fuer die Texterkennung "installiert nach AppData (kein Admin noetig)". Auf dem frischen
Windows 11 ohne Administratorrechte scheiterte sie: das Setup von Tesseract verlangt in seinem Manifest Rechte, aus einem
Programm ohne Erhoehung laesst es sich gar nicht starten (WinError 740), und die Oberflaeche zeigte den rohen Text.
Mit `__COMPAT_LAYER=RunAsInvoker` lief das Setup durch, installierte aber "nur fuer mich" nach
`%LOCALAPPDATA%\\Programs\\Tesseract-OCR` und ignorierte das Ziel `/D=`. PBP fand es dort nicht, der Deinstaller raeumte es
nicht ab, und das deutsche Sprachpaket kam nicht mit.

Hier steht, was jetzt gilt -- ohne echtes Setup, ohne Netz; der Beleg mit dem echten Setup ist der Testlauf auf dem
Werkstatt-PC (Block D). Die Tests laufen auch unter Linux (CI): die Windows-Pfade werden dort ueber `PureWindowsPath`
zerlegt, die Fixture setzt nur `sys.platform`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

WURZEL = Path(__file__).resolve().parents[1]
BAT = WURZEL / "DEINSTALLIEREN.bat"
GROESSE = 2 * 1024 * 1024
nur_windows = pytest.mark.skipif(os.name != "nt", reason="braucht Windows (cmd.exe, PowerShell)")


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **_kwargs):
        def decorator(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return decorator


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


def _marker_schreiben(umgebung, verzeichnis: Path, *, programm=True, abweichung=None) -> Path:
    """Ein Vermerk, wie PBP ihn nach einer Einrichtung hinterlaesst (mit Fingerabdruck der Programmdatei)."""
    c = umgebung.c
    verzeichnis.mkdir(parents=True, exist_ok=True)
    exe = verzeichnis / umgebung.binary_name
    marker = {"verzeichnis": str(verzeichnis), "binary": str(exe)}
    if programm:
        exe.write_bytes(b"MZ" + b"x" * 300)
        marker.update(c._fingerabdruck(exe))
    marker.update(abweichung or {})
    (umgebung.ordner / "tesseract").mkdir(parents=True, exist_ok=True)
    (umgebung.ordner / "tesseract" / c.EIGENE_INSTALLATION).write_text(json.dumps(marker), encoding="utf-8")
    return exe


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
    assert marker["binary_groesse"] == echt.stat().st_size and isinstance(marker["binary_erstellt"], int), "der Fingerabdruck"
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
    # Der Eintrag ist mit Backslash geschrieben; unter anderen Pfadregeln (CI) sind es zwei Ordner, nicht ein Name mit Backslash.
    assert c._benutzer_ordner_win(umgebung.definition).parts[-2:] == ("Programs", "Tesseract-OCR")
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


def test_das_entfernen_wartet_bis_das_programm_wirklich_weg_ist(umgebung, monkeypatch):
    """Das Deinstallationsprogramm des Setups kehrt sofort zurueck und raeumt erst danach: ohne die Wartezeit liefe der Rest mitten hinein."""
    c = umgebung.c
    _installiert(umgebung, monkeypatch)
    exe = umgebung.benutzer / umgebung.binary_name
    geschlafen = []

    def schlafen(sekunden):
        geschlafen.append(sekunden)
        if len(geschlafen) == 3:        # nach dem dritten Warten ist das Deinstallationsprogramm fertig
            exe.unlink()

    monkeypatch.setattr(c, "time", SimpleNamespace(sleep=schlafen, monotonic=lambda: 0.0))
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="", stderr=""))
    ergebnis = c.uninstall_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "entfernt", ergebnis
    assert len(geschlafen) >= 3, "es wurde gewartet, bis die Datei weg war"
    assert not umgebung.benutzer.exists()


def test_ohne_deinstallationsprogramm_geht_der_von_pbp_angelegte_ordner_trotzdem(umgebung, monkeypatch):
    c = umgebung.c
    _installiert(umgebung, monkeypatch)
    (umgebung.benutzer / umgebung.uninstaller).unlink()
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: pytest.fail("kein Programm, nichts zu starten"))
    assert c.uninstall_component(umgebung.db, "tesseract")["status"] == "entfernt"
    assert not umgebung.benutzer.exists()


@pytest.mark.parametrize("wie", ["groesse", "anlegezeit"])
def test_eine_spaeter_neu_angelegte_installation_am_selben_ort_wird_nicht_entfernt(umgebung, monkeypatch, wie):
    """Wer Tesseract nach PBP selbst am Standardort einrichtet, hat dieselben Dateinamen -- und diese Installation gehoert ihm."""
    c = umgebung.c
    _installiert(umgebung, monkeypatch)
    exe = umgebung.benutzer / umgebung.binary_name
    if wie == "groesse":
        exe.unlink()
        exe.write_bytes(b"neu angelegt" * 500)
    else:
        datei = umgebung.ordner / "tesseract" / c.EIGENE_INSTALLATION
        marker = json.loads(datei.read_text(encoding="utf-8"))
        marker["binary_erstellt"] += 1000          # die Datei dort ist nicht die, die PBP angelegt hat
        datei.write_text(json.dumps(marker), encoding="utf-8")
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: pytest.fail("nichts starten, nichts loeschen"))
    ergebnis = c.uninstall_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "entfernt" and ergebnis["pbp_installation_geloescht"] is False, ergebnis
    assert "nicht mehr von PBP" in ergebnis["hinweis"]
    assert exe.is_file() and (umgebung.benutzer / "tessdata" / "deu.traineddata").is_file(), "alles bleibt"
    assert not (umgebung.ordner / "tesseract").exists(), "nur der Vermerk geht"
    assert umgebung.db.get_component_state("tesseract")["status"] == "nicht_installiert"


def test_eine_neu_angelegte_installation_steht_nicht_mehr_als_pbps_in_der_uebersicht(umgebung, monkeypatch):
    c = umgebung.c
    _installiert(umgebung, monkeypatch)
    exe = umgebung.benutzer / umgebung.binary_name
    exe.unlink()
    exe.write_bytes(b"neu angelegt" * 500)
    from bewerbungs_assistent.services import speicher
    assert c.eigene_installation("tesseract") is None
    assert c.eigene_installation("tesseract", pruefen=False) is not None
    assert not [e for e in speicher._ort_komponenten(umgebung.db, 5.0)["eintraege"] if "Programmordner" in e["name"]]


def test_ein_marker_der_auf_einen_fremden_ort_zeigt_wird_verweigert(umgebung, monkeypatch, tmp_path):
    """Der Marker allein nennt keinen Pfad, der geloescht wird: nur der eine Ort, an dem das Setup ohne Rechte installiert."""
    c = umgebung.c
    fremd = tmp_path / "Eigene Dateien"
    _marker_schreiben(umgebung, fremd)            # Fingerabdruck stimmt -- der Ort ist trotzdem der falsche
    (fremd / "wichtig.txt").write_text("nicht loeschen")
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
    _marker_schreiben(umgebung, ziel)
    (ziel / "anderes.txt").write_text("x")
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: pytest.fail("nichts starten"))
    ergebnis = c.uninstall_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler"
    assert (ziel / "anderes.txt").is_file()


def test_ein_kaputter_marker_wird_nicht_als_installation_gelesen(umgebung):
    c = umgebung.c
    (umgebung.ordner / "tesseract").mkdir(parents=True)
    (umgebung.ordner / "tesseract" / c.EIGENE_INSTALLATION).write_text("{kein json", encoding="utf-8")
    assert c.eigene_installation("tesseract") is None


def test_ein_marker_ohne_fingerabdruck_gilt_nicht(umgebung):
    """Im Zweifel nichts loeschen: ein Vermerk, der die Datei nicht beschreibt, belegt nichts."""
    c = umgebung.c
    _marker_schreiben(umgebung, umgebung.benutzer, programm=True, abweichung={"binary_groesse": None, "binary_erstellt": None})
    assert c.eigene_installation("tesseract") is None
    assert c.eigene_installation("tesseract", pruefen=False) is not None


def test_liegt_in_vergleicht_ohne_grosskleinschreibung_wie_unter_windows(umgebung):
    c = umgebung.c
    assert c._liegt_in(Path("C:/Users/x/AppData/Local/Programs/Tesseract-OCR"),
                       Path("c:/users/x/appdata/local/programs/tesseract-ocr")) or os.name != "nt"
    assert c._liegt_in(umgebung.benutzer / "tessdata", umgebung.benutzer)
    assert not c._liegt_in(umgebung.benutzer.parent / "Tesseract-OCR-fremd", umgebung.benutzer)


# ══ Uebersicht Speicher & Downloads ══════════════════════════════════════════════════════════════════════════════

def test_die_speicheruebersicht_nennt_den_echten_ort_mit_groesse(umgebung, monkeypatch):
    _installiert(umgebung, monkeypatch)
    (umgebung.benutzer / "tessdata" / "deu.traineddata").write_bytes(b"x" * 5000)
    from bewerbungs_assistent.services import speicher
    ort = speicher._ort_komponenten(umgebung.db, 5.0)
    eintrag = [e for e in ort["eintraege"] if "Programmordner" in e["name"]]
    assert eintrag, ort
    assert eintrag[0]["pfad"] == str(umgebung.benutzer) and eintrag[0]["bytes"] >= 5000
    # und er zaehlt zur Summe des Ortes (vorher zeigte die Karte nur die paar Bytes des Vermerks)
    fertig = speicher._ort_fertig(ort, 5.0)
    assert fertig["bytes"] >= 5000 and fertig["vorhanden"] is True


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


def test_das_angebot_fuer_claude_nennt_den_echten_ort(umgebung):
    """Auf dieses Angebot hin gibt der Mensch seine Zustimmung: es nannte noch den PBP-Ordner, obwohl das Setup woanders ablegt."""
    from bewerbungs_assistent.tools import komponenten
    mcp = FakeMCP()
    komponenten.register(mcp, umgebung.db, logging.getLogger("test"))
    erg = mcp.tools["komponente_installieren"](name="tesseract")
    assert erg["status"] == "zustimmung_erforderlich", erg
    ziel = erg["angebot"]["ziel"]
    assert str(umgebung.benutzer) in ziel and "components" not in ziel, ziel
    assert "Administrator" in ziel


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
    assert "Test-Path -LiteralPath $b" in u and "Start-Sleep -Seconds 1" in u and "PBP_WARTEZEIT_S" in u
    # Entfernt wird nur dieselbe Datei, die PBP eingerichtet hat (Groesse und Anlegezeit aus dem Vermerk)
    assert "binary_groesse" in u and "binary_erstellt" in u and "CreationTimeUtc" in u and "exit 8" in u


def _lauf_texterkennung(tmp_path: Path, lokal: Path, basis: Path, wartezeit=None):
    assert str(tmp_path) in str(lokal) and str(tmp_path) in str(basis), "QA-Isolation: nie der echte LOCALAPPDATA"
    log = tmp_path / "protokoll.txt"
    kopf = ["@echo off", "setlocal EnableDelayedExpansion", f'set "LOCALAPPDATA={lokal}"', f'set "BASE_INSTALL={basis}"',
            f'set "LOGFILE={log}"']
    if wartezeit is not None:
        kopf.append(f'set "PBP_WARTEZEIT_S={wartezeit}"')
    kopf += ["call :texterkennung_entfernen", "echo ERGEBNIS=!errorlevel!", "exit /b 0", ""]
    bat = tmp_path / "tess.bat"
    bat.write_bytes(("\r\n".join(kopf) + _unterprogramm().replace("\n", "\r\n")).encode("cp850", errors="replace"))
    r = subprocess.run(["cmd.exe", "/c", str(bat)], capture_output=True, creationflags=0x08000000, timeout=180)
    ausgabe = (r.stdout + r.stderr).decode("cp850", errors="replace")
    protokoll = log.read_text(encoding="cp850", errors="replace") if log.exists() else ""
    ergebnis = next((z.split("=", 1)[1].strip() for z in ausgabe.splitlines() if z.startswith("ERGEBNIS=")), None)
    return ergebnis, ausgabe, protokoll


def _marker_und_programm(tmp_path: Path, *, mit_marker=True, mit_deinstaller=True, mit_exe=True, passt=True, name="Local"):
    """Die Lage nach einer Einrichtung durch PBP: Programmordner mit Sprachdaten, Vermerk mit Fingerabdruck der tesseract.exe."""
    from bewerbungs_assistent.services import components
    lokal = tmp_path / name
    basis = lokal / "BewerbungsAssistent"
    ziel = lokal / "Programs" / "Tesseract-OCR"
    (ziel / "tessdata").mkdir(parents=True)
    (ziel / "tessdata" / "deu.traineddata").write_bytes(b"x" * 100)
    exe = ziel / "tesseract.exe"
    if mit_exe:
        exe.write_bytes(b"MZ" + b"x" * 300)
    if mit_deinstaller:
        # eine beliebige, harmlose Programmdatei unter dem Namen des Deinstallationsprogramms
        shutil.copy2(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "whoami.exe", ziel / "tesseract-uninstall.exe")
    if mit_marker:
        marker = {"verzeichnis": str(ziel), "binary": str(exe)}
        if mit_exe:
            marker.update(components._fingerabdruck(exe))
            if not passt:
                marker["binary_erstellt"] += 1000
        (basis / "components" / "tesseract").mkdir(parents=True)
        (basis / "components" / "tesseract" / "pbp-installation.json").write_text(json.dumps(marker), encoding="utf-8")
    return lokal, basis, ziel, exe


@nur_windows
def test_die_bat_entfernt_die_von_pbp_eingerichtete_texterkennung(tmp_path):
    lokal, basis, ziel, _ = _marker_und_programm(tmp_path, mit_deinstaller=False)
    ergebnis, ausgabe, protokoll = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "0", (ausgabe, protokoll)
    assert not ziel.exists(), "auch die nachgeladenen Sprachdaten gehen mit"
    assert "Texterkennung entfernt" in protokoll


@nur_windows
def test_die_bat_startet_das_deinstallationsprogramm_und_gibt_nach_der_frist_auf_zu_warten(tmp_path):
    """Das Deinstallationsprogramm (hier eine harmlose Datei) loescht nichts: nach der Frist raeumt die bat den Ordner selbst."""
    lokal, basis, ziel, _ = _marker_und_programm(tmp_path)
    ergebnis, ausgabe, protokoll = _lauf_texterkennung(tmp_path, lokal, basis, wartezeit=3)
    assert ergebnis == "0", (ausgabe, protokoll)
    assert not ziel.exists()


@nur_windows
def test_die_bat_wartet_bis_das_programm_weg_ist_und_raeumt_erst_danach_auf(tmp_path):
    """Die Programmdatei bleibt vier Sekunden gesperrt (das Deinstallationsprogramm ist noch dabei). Ohne die Wartezeit scheiterte das Loeschen."""
    lokal, basis, ziel, exe = _marker_und_programm(tmp_path)
    halter = open(exe, "rb")                       # Python oeffnet ohne Loeschfreigabe
    timer = threading.Timer(4.0, halter.close)
    timer.start()
    try:
        ergebnis, ausgabe, protokoll = _lauf_texterkennung(tmp_path, lokal, basis, wartezeit=7)
    finally:
        timer.cancel()
        halter.close()
    assert ergebnis == "0", (ausgabe, protokoll)
    assert not ziel.exists()


@nur_windows
def test_die_bat_fasst_ohne_marker_nichts_an(tmp_path):
    """Eine Tesseract-Installation, die der Mensch selbst angelegt hat, gehoert ihm: kein Marker, keine Hand dran."""
    lokal, basis, ziel, exe = _marker_und_programm(tmp_path, mit_marker=False)
    ergebnis, ausgabe, _ = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "9", ausgabe
    assert (ziel / "tessdata" / "deu.traineddata").is_file() and exe.is_file()


@nur_windows
@pytest.mark.parametrize("fall", ["neu_angelegt", "programm_fehlt"])
def test_die_bat_fasst_eine_nicht_mehr_von_pbp_stammende_installation_nicht_an(tmp_path, fall):
    """Vermerk da, aber das Programm am Ort ist nicht (mehr) das von PBP: neu angelegt oder schon entfernt. Es bleibt, wie es ist."""
    if fall == "neu_angelegt":
        lokal, basis, ziel, exe = _marker_und_programm(tmp_path, passt=False)
    else:
        lokal, basis, ziel, exe = _marker_und_programm(tmp_path, mit_exe=False)
    ergebnis, ausgabe, protokoll = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "8", (ausgabe, protokoll)
    assert (ziel / "tessdata" / "deu.traineddata").is_file(), "nichts wird angefasst"
    assert "stammt nicht mehr von PBP" in protokoll


@nur_windows
def test_die_bat_kommt_auch_ohne_deinstallationsprogramm_und_ohne_ordner_zurecht(tmp_path):
    lokal, basis, ziel, _ = _marker_und_programm(tmp_path, mit_deinstaller=False)
    ergebnis, ausgabe, _ = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "0" and not ziel.exists(), ausgabe
    # ein zweites Mal: Marker da, Ordner schon weg
    ergebnis2, ausgabe2, protokoll2 = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis2 == "0", ausgabe2
    assert "nicht vorhanden" in protokoll2


@nur_windows
def test_die_bat_vertraegt_leerzeichen_apostroph_und_klammern_im_pfad(tmp_path):
    lokal, basis, ziel, _ = _marker_und_programm(tmp_path, mit_deinstaller=False, name="O'Brien Test (privat)")
    ergebnis, ausgabe, protokoll = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "0" and not ziel.exists(), (ausgabe, protokoll)


@nur_windows
def test_die_bat_meldet_eine_gesperrte_datei_und_der_lauf_geht_weiter(tmp_path):
    """Laeuft die Texterkennung noch, bleibt eine Datei gesperrt: der Deinstaller sagt es (Rueckgabe 1) und bricht nicht ab."""
    lokal, basis, ziel, _ = _marker_und_programm(tmp_path, mit_deinstaller=False)
    gesperrt = ziel / "tessdata" / "deu.traineddata"
    with open(gesperrt, "rb"):          # Python oeffnet ohne Loeschfreigabe: Remove-Item scheitert an dieser Datei
        ergebnis, ausgabe, protokoll = _lauf_texterkennung(tmp_path, lokal, basis)
    assert ergebnis == "1", (ausgabe, protokoll)
    assert "nicht vollstaendig entfernt" in protokoll
    assert gesperrt.exists(), "nichts wird erzwungen"


# ══ Kleinigkeiten aus demselben Lauf ═════════════════════════════════════════════════════════════════════════════

def test_die_gefahrenzone_zeigt_keine_markdown_zeichen_als_text():
    """Die Oberflaeche zeigt Klartext: `**` stand dort woertlich ("**Mit den aussortierten Stellen ...**")."""
    from bewerbungs_assistent.services import loeschbereiche
    for bereich, text in loeschbereiche.BESCHREIBUNG.items():
        assert "**" not in text and "__" not in text, f"{bereich}: {text}"
    assert "Lernsignale" in loeschbereiche.BESCHREIBUNG["stellen"], "der Hinweis selbst bleibt"


# ══ Der Weg aus der Oberflaeche (REST) ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def rest(umgebung, monkeypatch):
    """FastAPI-TestClient mit der Test-Datenbank; die Umgebung der Komponenten wie oben (Windows-Zweig, Temp-Ordner)."""
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    vorher = dash._db
    dash._db = umgebung.db
    try:
        yield TestClient(dash.app), umgebung
    finally:
        dash._db = vorher


def test_rest_entfernen_meldet_den_fehler_in_alltagssprache_mit_400(rest, monkeypatch):
    client, u = rest
    _marker_schreiben(u, u.lokal / "Fremd")
    antwort = client.delete("/api/components/tesseract")
    assert antwort.status_code == 400
    assert "unerwarteten Ort" in antwort.json()["error"], "die Oberflaeche zeigt genau diesen Text"


def test_rest_entfernen_ohne_adminrechte_installierter_texterkennung_klappt(rest, monkeypatch):
    client, u = rest
    c = u.c
    monkeypatch.setattr(c.subprocess, "run", _setup_legt_ab(u, u.benutzer))
    assert c.install_component(u.db, "tesseract")["status"] == "installiert"

    def deinstaller(argv, **kw):
        (u.benutzer / u.binary_name).unlink()
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(c.subprocess, "run", deinstaller)
    antwort = client.delete("/api/components/tesseract")
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["pbp_installation_geloescht"] is True
    assert not u.benutzer.exists()
    liste = client.get("/api/components").json()["komponenten"]
    tess = next(k for k in liste if k["name"] == "tesseract")
    assert tess["verfuegbar"] is False and tess["status"] == "nicht_installiert"


def test_das_entfernen_blockiert_den_ereignis_thread_nicht():
    """Das Deinstallationsprogramm des Setups kehrt sofort zurueck, danach wird bis zu einer Minute gewartet: nicht in `async def`."""
    import inspect
    import bewerbungs_assistent.dashboard as dash
    quelle = inspect.getsource(dash.api_component_uninstall)
    assert "run_in_threadpool(comp.uninstall_component" in quelle
