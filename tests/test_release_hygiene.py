"""Release-Hygiene-Regressionstests fuer Backups und Release-Gate."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from bewerbungs_assistent.database import create_backup


def test_create_backup_captures_wal_changes(tmp_path):
    """Backups muessen auch im WAL-Modus eine lesbare, vollstaendige DB erzeugen."""
    db_path = tmp_path / "wal-test.db"
    backup_dir = tmp_path / "backups"

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.execute("INSERT INTO demo(value) VALUES ('persisted')")
        conn.commit()
        conn.execute("INSERT INTO demo(value) VALUES ('only_in_wal')")
        conn.commit()

        backup_path = create_backup(db_path, backup_dir)
    finally:
        conn.close()

    assert backup_path is not None

    backup_conn = sqlite3.connect(str(backup_path))
    try:
        rows = [row[0] for row in backup_conn.execute("SELECT value FROM demo ORDER BY id").fetchall()]
    finally:
        backup_conn.close()

    assert rows == ["persisted", "only_in_wal"]


def test_release_check_script_passes():
    """Der Release-Gate muss auf dem aktuellen Checkout gruene Ergebnisse liefern.

    Mit `CI=1` wie auf GitHub: der Hauptschluessel zum Signieren liegt nur auf dem Release-Rechner, und die Fixture
    `_update_ohne_vertraute_schluessel` (conftest) lenkt den Ort der Schluessel bewusst ins Leere. Ohne `CI` verlangt das
    Tor bei einer STABILEN Version den Schluessel (Fehler) und liesse diesen Test lokal rot werden, sobald die Version
    stabil ist (1.8.0: aufgefallen in der vollen Suite vom 12.10.2026, auf GitHub war er gruen). Dass das Tor mit dem
    echten Schluessel signiert und gegen die eingetragenen prueft, zeigt `python release_check.py` auf dem Release-Rechner.
    """
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "release_check.py"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "CI": "1"},
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
