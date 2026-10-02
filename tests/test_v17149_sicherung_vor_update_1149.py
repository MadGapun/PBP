"""#1149 Punkt 2 — die „Sicherung vor dem Update“ des Installers sichert wirklich.

Befund (01.10.2026, Prüfbereich Installation, Update und erster Start):
`INSTALLIEREN.bat` kopierte `pbp.db` mit `copy` und ignorierte `pbp.db-wal`;
die Erfolgsmeldung stand unbedingt da, der Dateiname war fest und wurde bei
jedem Update überschrieben. Gemessen: bei offener Verbindung und 50
Schreibvorgängen hatte die Kopie 4 KB und „no such table“, die
SQLite-Sicherung alle 50 Zeilen. Bei einem Update laufen meist noch Claude
und PBP.

Jetzt ruft der Installer `_sicherung_vor_update.py` (nur Standardbibliothek)
mit der SQLite-Sicherungsfunktion. Die Tests laden das Skript wie der
Installer es aufruft und lesen die Zeilen aus `INSTALLIEREN.bat`.
"""
import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKRIPT = ROOT / "_sicherung_vor_update.py"
BAT = ROOT / "INSTALLIEREN.bat"
OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0


def _laden():
    spec = importlib.util.spec_from_file_location("_sicherung_vor_update", SKRIPT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture()
def modul():
    return _laden()


def _wal_datenbank(pfad: Path, zeilen: int = 50):
    """Eine Datenbank im WAL-Modus, deren letzte Schreibvorgänge NUR im WAL stehen.

    Die Verbindung bleibt offen zurück (wie bei laufendem PBP) und wird
    zurückgegeben; `wal_autocheckpoint=0` hält den WAL-Inhalt fest.
    """
    conn = sqlite3.connect(str(pfad))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE gespeichert (id INTEGER PRIMARY KEY, text TEXT)")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # Tabelle steht in der Hauptdatei ...
    for i in range(zeilen):                           # ... die Zeilen nur im WAL
        conn.execute("INSERT INTO gespeichert (text) VALUES (?)", (f"Zeile {i}",))
    conn.commit()
    return conn


def _zaehle(pfad: Path) -> int:
    conn = sqlite3.connect(str(pfad))
    try:
        return conn.execute("SELECT COUNT(*) FROM gespeichert").fetchone()[0]
    finally:
        conn.close()


# ══ Die Sicherung ist vollständig ═══════════════════════════════════════════

def test_1149_die_sicherung_enthaelt_was_nur_im_wal_steht(tmp_path, modul):
    db = tmp_path / "pbp.db"
    offen = _wal_datenbank(db)
    try:
        # Der alte Weg: eine Dateikopie. Sie verpasst den WAL-Inhalt.
        kopie = tmp_path / "kopie.db"
        shutil.copyfile(db, kopie)
        assert _zaehle(kopie) < 50, "die Messung stimmt nicht: die Dateikopie war vollständig"

        ziel = modul.sichern(db, tmp_path / "backups")

        assert _zaehle(ziel) == 50
    finally:
        offen.close()


def test_1149_der_name_traegt_zeitstempel_und_anlass(tmp_path, modul):
    db = tmp_path / "pbp.db"
    _wal_datenbank(db).close()
    ziel = modul.sichern(db, tmp_path / "backups")
    assert re.fullmatch(r"pbp-backup-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-vor_update\.db", ziel.name), ziel.name
    # derselbe Name wie in database.create_backup
    sys.path.insert(0, str(ROOT / "src"))
    from bewerbungs_assistent import database
    quelle = Path(database.__file__).read_text(encoding="utf-8-sig")
    assert 'f"pbp-backup-{timestamp}-vor_update.db"' in quelle


def test_1149_zwei_sicherungen_ueberschreiben_sich_nicht(tmp_path, modul):
    db = tmp_path / "pbp.db"
    _wal_datenbank(db).close()
    erste = modul.sichern(db, tmp_path / "backups")
    zweite = modul.sichern(db, tmp_path / "backups")
    assert erste != zweite
    assert erste.exists() and zweite.exists()
    assert _zaehle(erste) == _zaehle(zweite) == 50


def test_1149_es_bleiben_hoechstens_fuenf_und_fremde_dateien_unberuehrt(tmp_path, modul):
    db = tmp_path / "pbp.db"
    _wal_datenbank(db).close()
    ordner = tmp_path / "backups"
    ordner.mkdir()
    # sieben alte Sicherungen vor einem Update, mit absteigendem Alter
    alte = []
    for i in range(7):
        p = ordner / f"pbp-backup-2026-01-0{i + 1}_10-00-00-vor_update.db"
        p.write_bytes(b"alt")
        os.utime(p, (time.time() - 1000 * (10 - i), time.time() - 1000 * (10 - i)))
        alte.append(p)
    taeglich = ordner / "pbp-backup-2026-01-01_03-00-00-taeglich.db"
    taeglich.write_bytes(b"taeglich")
    eigene = ordner / "meine-notiz.txt"
    eigene.write_text("bleibt", encoding="utf-8")

    neu = modul.sichern(db, ordner)

    uebrig = sorted(p.name for p in ordner.iterdir() if "-vor_update" in p.name)
    assert len(uebrig) == 5, uebrig
    assert neu.name in uebrig
    assert alte[0].name not in uebrig and alte[1].name not in uebrig, "die ältesten gehen zuerst"
    assert taeglich.exists() and eigene.exists(), "andere Dateien gehören dem Installer nicht"


# ══ Ehrliche Meldung und Rückgabewerte ═══════════════════════════════════════

def _aufruf(db: Path, ordner: Path):
    """So ruft der Installer das Skript auf (eigener Prozess, Ausgabe und Rückgabewert)."""
    return subprocess.run([sys.executable, str(SKRIPT), str(db), str(ordner)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=OHNE_FENSTER, timeout=120)


def test_1149_der_installer_aufruf_meldet_ok_mit_pfad_und_rueckgabewert_0(tmp_path):
    db = tmp_path / "pbp.db"
    _wal_datenbank(db).close()
    r = _aufruf(db, tmp_path / "backups")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.startswith("OK "), r.stdout
    assert Path(r.stdout[3:].strip()).exists()
    assert len(r.stdout.strip().splitlines()) == 1


def test_1149_ohne_datenbank_ist_der_rueckgabewert_2_und_nichts_wird_angelegt(tmp_path):
    r = _aufruf(tmp_path / "gibt-es-nicht.db", tmp_path / "backups")
    assert r.returncode == 2
    assert r.stdout.startswith("FEHLER ")
    assert not (tmp_path / "backups").exists()


def test_1149_ein_unbrauchbarer_ordner_gibt_rueckgabewert_3(tmp_path):
    db = tmp_path / "pbp.db"
    _wal_datenbank(db).close()
    ordner = tmp_path / "backups"
    ordner.write_text("das ist eine Datei, kein Ordner", encoding="utf-8")
    r = _aufruf(db, ordner)
    assert r.returncode == 3, r.stdout
    assert r.stdout.startswith("FEHLER ")
    assert "OK" not in r.stdout.split()[0:1]


def test_1149_eine_kaputte_datenbank_gibt_fehler_und_hinterlaesst_keine_halbe_sicherung(tmp_path):
    db = tmp_path / "pbp.db"
    db.write_bytes(b"das ist keine SQLite-Datei" * 200)
    ordner = tmp_path / "backups"
    r = _aufruf(db, ordner)
    assert r.returncode in (3, 4), r.stdout
    assert r.stdout.startswith("FEHLER ")
    assert not list(ordner.glob("*.db")), "eine halbe Sicherung darf nicht liegen bleiben"


def test_1149_falscher_aufruf_gibt_rueckgabewert_64(tmp_path):
    r = subprocess.run([sys.executable, str(SKRIPT)], capture_output=True, text=True,
                       creationflags=OHNE_FENSTER, timeout=60)
    assert r.returncode == 64
    assert r.stdout.startswith("FEHLER ")


def test_1149_eine_sicherung_die_sich_nicht_lesen_laesst_zaehlt_nicht(tmp_path, modul, monkeypatch):
    """Eine Datei, die nur existiert, ist noch keine Sicherung."""
    db = tmp_path / "pbp.db"
    _wal_datenbank(db).close()
    echtes_urteil = modul._leseprobe

    def kaputt(ziel):
        ziel.write_bytes(b"abgeschnitten")
        return echtes_urteil(ziel)

    monkeypatch.setattr(modul, "_leseprobe", kaputt)
    with pytest.raises(modul._Unlesbar):
        modul.sichern(db, tmp_path / "backups")
    assert not list((tmp_path / "backups").glob("*.db"))


# ══ INSTALLIEREN.bat ruft das Skript auf und kopiert nicht mehr ═════════════

def _bat():
    return BAT.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def test_1149_die_bat_kopiert_die_datenbank_nicht_mehr_roh():
    zeilen = [z for z in _bat().splitlines() if not z.lstrip().startswith("::")]
    roh = [z for z in zeilen if re.search(r'\bcopy\s+"[^"]*pbp\.db"', z, re.IGNORECASE)]
    assert not roh, roh
    assert "pbp-backup-vor-update.db" not in "\n".join(zeilen), "der feste Dateiname wurde jedes Mal überschrieben"


def test_1149_die_bat_ruft_das_skript_mit_datenbank_und_ordner_auf():
    text = _bat()
    aufrufe = [z for z in text.splitlines() if "_sicherung_vor_update.py" in z and '"%PYTHON%"' in z
               and not z.lstrip().startswith("::")]
    assert len(aufrufe) == 1, aufrufe
    z = aufrufe[0]
    assert z.lstrip().startswith('"%PYTHON%"')
    assert '"!BACKUP_DB!"' in z and '"!BACKUP_DIR!"' in z
    assert '>> "%LOGFILE%" 2>&1' in z, "die Ausgabe des Skripts gehört ins Log"


def test_1149_die_erfolgsmeldung_steht_nur_im_erfolgszweig():
    text = _bat()
    i = text.index('"%PYTHON%" "%BASEDIR%\\_sicherung_vor_update.py"')
    block = text[i:i + 1400]
    nach_aufruf = block.splitlines()[1].strip()
    assert nach_aufruf == "if errorlevel 1 (", nach_aufruf
    fehler, erfolg = block.split(") else (", 1)
    assert "[WARNUNG]" in fehler and "NICHT gelungen" in fehler
    assert "[OK] Sicherung" not in fehler
    assert "[OK] Sicherung" in erfolg.split("\n)\n", 1)[0]
    # die Gründe stehen im Log; der Mensch bekommt den Weg zur Handarbeit genannt
    assert "!LOGFILE!" in fehler and "von Hand" in fehler and "bevor du PBP das naechste Mal startest" in fehler


def test_1149_beide_datenbank_standorte_werden_bedacht():
    text = _bat()
    assert 'if exist "%DATA_DIR%\\pbp.db" set "BACKUP_DB=%DATA_DIR%\\pbp.db"' in text
    assert 'if not defined BACKUP_DB if exist "%BASE_INSTALL%\\pbp.db" set "BACKUP_DB=%BASE_INSTALL%\\pbp.db"' in text


def test_1149_das_skript_gehoert_zu_den_geprueften_hilfsdateien_und_zum_zip():
    assert SKRIPT.exists()
    assert 'if not exist "%BASEDIR%\\_sicherung_vor_update.py" goto :err_setup_helper_missing' in _bat()
    attribute = (ROOT / ".gitattributes").read_text(encoding="utf-8-sig")
    assert "_sicherung_vor_update" not in attribute, "das Skript darf nicht aus dem ZIP ausgeschlossen werden"


def test_1149_das_skript_braucht_nur_die_standardbibliothek():
    quelle = SKRIPT.read_text(encoding="utf-8-sig")
    importe = set(re.findall(r"^(?:import|from)\s+([a-zA-Z_0-9]+)", quelle, re.MULTILINE))
    assert importe <= {"re", "sqlite3", "sys", "datetime", "pathlib"}, importe


# ══ Die echten Zeilen der BAT, in cmd.exe ausgeführt ═══════════════════════

nur_windows = pytest.mark.skipif(os.name != "nt", reason="braucht cmd.exe")


def _sicherungsblock() -> str:
    """Die Zeilen der BAT von `set "BACKUP_DIR=` bis vor die Migration, unverändert."""
    zeilen = _bat().splitlines()
    ab = next(i for i, z in enumerate(zeilen) if z.startswith('set "BACKUP_DIR=%DATA_DIR%'))
    bis = next(i for i, z in enumerate(zeilen) if z.startswith(":: Migration v1.4.x"))
    return "\n".join(zeilen[ab:bis])


def _in_cmd(tmp_path: Path, *, daten_db=False, flach_db=False, ordner_ist_datei=False,
            wurzel_name="Wurzel"):
    """Führt den Sicherungsblock der BAT mit echten Pfaden aus (Delayed Expansion wie im Installer)."""
    wurzel = tmp_path / wurzel_name
    daten = wurzel / "data"
    daten.mkdir(parents=True)
    laufend = None
    if daten_db:
        laufend = _wal_datenbank(daten / "pbp.db")
    if flach_db:
        _wal_datenbank(wurzel / "pbp.db").close()
    if ordner_ist_datei:
        (daten / "backups").write_text("kein Ordner", encoding="utf-8")
    log = tmp_path / "install_log.txt"
    skript = tmp_path / "block.bat"
    kopf = (
        "@echo off\r\nsetlocal enabledelayedexpansion\r\n"
        f'set "DATA_DIR={daten}"\r\nset "BASE_INSTALL={wurzel}"\r\nset "LOGFILE={log}"\r\n'
        f'set "PYTHON={sys.executable}"\r\nset "BASEDIR={ROOT}"\r\n'
    )
    skript.write_bytes((kopf + _sicherungsblock().replace("\n", "\r\n") + "\r\necho ENDE\r\n").encode("utf-8"))
    try:
        r = subprocess.run(["cmd", "/d", "/c", str(skript)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", creationflags=OHNE_FENSTER, timeout=180)
    finally:
        if laufend is not None:
            laufend.close()
    protokoll = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    return r, protokoll, daten / "backups"


@nur_windows
def test_1149_cmd_sichert_die_laufende_datenbank_vollstaendig(tmp_path):
    r, protokoll, backups = _in_cmd(tmp_path, daten_db=True)
    assert "ENDE" in r.stdout, r.stdout + r.stderr
    assert "[OK] Sicherung der Datenbank erstellt" in r.stdout, r.stdout
    assert "[WARNUNG]" not in r.stdout
    dateien = list(backups.glob("pbp-backup-*-vor_update.db"))
    assert len(dateien) == 1, dateien
    assert _zaehle(dateien[0]) == 50, "die Sicherung hat den Inhalt aus dem WAL nicht"
    assert "OK " in protokoll and str(backups).lower() in protokoll.lower()


@nur_windows
def test_1149_cmd_sichert_auch_die_datenbank_der_alten_flachen_struktur(tmp_path):
    r, protokoll, backups = _in_cmd(tmp_path, flach_db=True)
    assert "[OK] Sicherung der Datenbank erstellt" in r.stdout, r.stdout
    dateien = list(backups.glob("pbp-backup-*-vor_update.db"))
    assert len(dateien) == 1 and _zaehle(dateien[0]) == 50


@nur_windows
def test_1149_cmd_meldet_ein_scheitern_statt_ok(tmp_path):
    r, protokoll, backups = _in_cmd(tmp_path, daten_db=True, ordner_ist_datei=True)
    assert "ENDE" in r.stdout, "der Installer darf wegen der Sicherung nicht abbrechen"
    assert "[WARNUNG] Die Sicherung der Datenbank ist NICHT gelungen" in r.stdout, r.stdout
    assert "[OK] Sicherung" not in r.stdout
    assert "von Hand" in r.stdout
    assert "bevor du PBP das naechste Mal startest" in r.stdout, "wann die Handarbeit nötig ist"
    assert "FEHLER" in protokoll, "der Grund steht im Log"


@nur_windows
def test_1149_cmd_ohne_datenbank_sagt_nichts_ueber_eine_sicherung(tmp_path):
    r, protokoll, backups = _in_cmd(tmp_path)
    assert "ENDE" in r.stdout
    assert "Sicherung" not in r.stdout and not backups.exists()


@nur_windows
def test_1149_cmd_kommt_mit_klammern_und_leerzeichen_im_pfad_zurecht(tmp_path):
    r, protokoll, backups = _in_cmd(tmp_path, daten_db=True, wurzel_name="Ordner (alt) mit Leerzeichen")
    assert "ENDE" in r.stdout, r.stdout + r.stderr
    assert "[OK] Sicherung der Datenbank erstellt" in r.stdout, r.stdout
    assert len(list(backups.glob("pbp-backup-*-vor_update.db"))) == 1
