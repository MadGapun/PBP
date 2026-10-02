"""#1149 Punkt 1 — scheitert der Start an der Datenbank, bleibt eine Spur.

Befund (01.10.2026, Prüfbereich Installation und erster Start): `server.py`
rief `db.initialize()` beim Import ungeschützt. Mit gesperrtem
Sicherungsordner endete der Start über `python -m bewerbungs_assistent` (so
startet Claude Desktop PBP) mit Exit 1 und einem Traceback auf stderr;
`pbp.log` blieb mit 0 Bytes leer, der Dashboard-Port wurde nie gebunden.
Der Installer verweist für Fehler aber auf `pbp.log`.

Jetzt: eine Meldung in Klartext im Log UND auf stderr (Grund, Datenordner,
häufige Ursachen), danach derselbe Fehler wie vorher — der Start scheitert
weiter, aber nicht mehr stumm.

Die Startversuche laufen in Unterprozessen mit eigenem `BA_DATA_DIR` im
Temp-Ordner; die echte Datenbank wird nie berührt.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0
MELDUNG = "PBP konnte die Datenbank nicht öffnen"


def _lauf(code: str, daten: Path, timeout: int = 180):
    env = dict(os.environ)
    env.update({
        "BA_DATA_DIR": str(daten), "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8",
        "BA_DASHBOARD_PORT": "8269", "PBP_NETZ_PRUEFUNG": "0",
    })
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=OHNE_FENSTER)


def _datenordner_mit_alter_datenbank(tmp_path: Path) -> Path:
    """Eine Datenbank mit alter Schemaversion: beim Start wäre ein Pflicht-Backup nötig."""
    daten = tmp_path / "daten"
    daten.mkdir()
    r = _lauf("from bewerbungs_assistent.database import Database\n"
              "db = Database()\nprint(db.db_path)\ndb.initialize()\ndb.close()\n", daten)
    assert r.returncode == 0, r.stderr[-800:]
    assert str(daten).lower() in r.stdout.lower(), f"Datenbank nicht isoliert: {r.stdout}"
    conn = sqlite3.connect(str(daten / "pbp.db"))
    conn.execute("UPDATE settings SET value='40' WHERE key='schema_version'")
    conn.commit()
    conn.close()
    return daten


def test_1149_ein_start_ohne_datenbank_hinterlaesst_eine_spur_im_log(tmp_path):
    daten = _datenordner_mit_alter_datenbank(tmp_path)
    # Sicherungsordner unbenutzbar: eine Datei mit dem Namen des Ordners.
    sicherung = daten / "backups"
    if sicherung.exists():
        shutil.rmtree(sicherung)
    sicherung.write_text("das ist kein Ordner", encoding="utf-8")

    r = _lauf("import bewerbungs_assistent.server", daten)

    assert r.returncode != 0, "der Start muss weiter scheitern, nur nicht mehr stumm"
    assert MELDUNG in r.stderr, r.stderr[-600:]
    log = (daten / "logs" / "pbp.log")
    assert log.exists() and log.stat().st_size > 0, "pbp.log ist leer geblieben"
    text = log.read_text(encoding="utf-8", errors="replace")
    assert MELDUNG in text
    assert "Pre-Migration-Backup fehlgeschlagen" in text, "der Grund fehlt im Log"
    assert str(daten).lower() in text.lower(), "der Datenordner fehlt im Log"
    assert "Traceback" in text, "die Fehlerspur (Traceback) gehört ins Log"


def test_1149_ein_gesunder_start_meldet_keinen_fehler(tmp_path):
    daten = tmp_path / "daten"
    daten.mkdir()
    r = _lauf("import bewerbungs_assistent.server", daten)
    assert r.returncode == 0, r.stderr[-800:]
    assert MELDUNG not in r.stderr
    log = daten / "logs" / "pbp.log"
    assert not log.exists() or MELDUNG not in log.read_text(encoding="utf-8", errors="replace")


def test_1149_die_meldung_nennt_grund_ordner_und_ursachen(caplog, capsys):
    from bewerbungs_assistent import server
    with caplog.at_level("CRITICAL", logger="bewerbungs_assistent"):
        server._start_ohne_datenbank_melden(RuntimeError("Platte voll"))
    err = capsys.readouterr().err
    for ausgabe in (err, caplog.text):
        assert MELDUNG in ausgabe
        assert "Platte voll" in ausgabe
        assert "Datenordner:" in ausgabe
        assert "Schreibrecht" in ausgabe and "backups" in ausgabe


def test_1149_die_meldung_nennt_den_klassennamen_wenn_der_fehler_keinen_text_hat(capsys):
    from bewerbungs_assistent import server
    server._start_ohne_datenbank_melden(PermissionError())
    assert "PermissionError" in capsys.readouterr().err


def test_1149_server_py_ruft_initialize_nicht_mehr_ungeschuetzt():
    quelle = (SRC / "bewerbungs_assistent" / "server.py").read_text(encoding="utf-8-sig")
    i = quelle.index("db = Database()")
    block = quelle[i:i + 400]
    assert "try:" in block and "db.initialize()" in block and "_start_ohne_datenbank_melden" in block
