"""Regression #723: DB-Schreib-Kontention zwischen Dashboard- und MCP-Prozess.

Dashboard (Port 8200) und MCP-Server sind zwei Prozesse mit je eigener
Connection auf dieselbe pbp.db. SQLite erlaubt nur EINEN Writer. Ohne
busy_timeout scheitert der zweite Write sofort mit 'database is locked' —
oder, schlimmer, eine geleakte Transaktion blockiert dauerhaft bis zum
4-Min-Client-Timeout.

Zwei-Schicht-Absicherung (verifiziert hier):
  1. busy_timeout (BUSY_TIMEOUT_MS): ein contended Write WARTET, bis der
     andere Writer committet, statt sofort zu scheitern oder ewig zu haengen.
  2. rollback_if_stale (#708, eigener Test): raeumt geleakte Transaktionen.

HARTE ISOLATIONS-REGEL: db.db_path muss im Temp-Verzeichnis liegen
(BA_DATA_DIR, NICHT PBP_DATA_DIR).
"""
import importlib
import os
import shutil
import sqlite3
import tempfile
import threading
import time

import pytest


@pytest.fixture
def db_file():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_723_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    path = str(db.db_path)
    db.close()
    yield path
    shutil.rmtree(tmpdir, ignore_errors=True)


def _raw(path, busy_ms=None):
    c = sqlite3.connect(path, timeout=0)  # timeout=0: SQLite-Default-Busy aus,
    c.execute("PRAGMA journal_mode=WAL")  # nur unser busy_timeout zaehlt
    if busy_ms is not None:
        c.execute(f"PRAGMA busy_timeout={busy_ms}")
    return c


def test_723_production_connection_hat_30s_timeout(db_file):
    """Die echte Database.connect() setzt BUSY_TIMEOUT_MS (#723)."""
    from bewerbungs_assistent.database import Database, BUSY_TIMEOUT_MS
    db = Database()
    conn = db.connect()
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == BUSY_TIMEOUT_MS
    assert BUSY_TIMEOUT_MS >= 15000  # genug Puffer fuer Bulk-Writes
    db.close()


def test_723_ohne_timeout_scheitert_write_sofort(db_file):
    """Beleg fuer das Grundproblem: OHNE busy_timeout scheitert der zweite
    Writer praktisch sofort (nicht erst nach langer Wartezeit)."""
    holder = _raw(db_file)
    holder.execute("BEGIN IMMEDIATE")  # haelt den Write-Lock
    holder.execute("INSERT INTO settings (key, value) VALUES ('h', '1')")

    writer = _raw(db_file, busy_ms=0)  # KEIN Warten
    t0 = time.perf_counter()
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        writer.execute("INSERT INTO settings (key, value) VALUES ('w', '1')")
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f"haette sofort scheitern muessen, dauerte {elapsed:.2f}s"
    holder.rollback(); holder.close(); writer.close()


def test_723_mit_busy_timeout_wartet_statt_sofort_zu_scheitern(db_file):
    """Mit busy_timeout WARTET der zweite Writer die volle Spanne, bevor er
    aufgibt — das heilt das 'sofort database is locked'-Verhalten."""
    holder = _raw(db_file)
    holder.execute("BEGIN IMMEDIATE")
    holder.execute("INSERT INTO settings (key, value) VALUES ('h', '1')")

    writer = _raw(db_file, busy_ms=700)
    t0 = time.perf_counter()
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        writer.execute("INSERT INTO settings (key, value) VALUES ('w', '1')")
    elapsed = time.perf_counter() - t0
    # Hat ~700ms gewartet (nicht sofort gescheitert, nicht ewig gehaengt)
    assert 0.5 <= elapsed < 5.0, f"unerwartete Wartezeit {elapsed:.2f}s"
    holder.rollback(); holder.close(); writer.close()


def test_723_contended_write_geht_durch_wenn_lock_freigegeben(db_file):
    """Kernbeweis: ein contended Write HAENGT NICHT in den Client-Timeout,
    sondern geht durch, sobald der andere Writer committet."""
    lock_held = threading.Event()

    def _hold_then_release():
        # SQLite-Connections sind thread-gebunden — Holder lebt komplett hier.
        h = _raw(db_file)
        h.execute("BEGIN IMMEDIATE")  # haelt den Write-Lock
        h.execute("INSERT INTO settings (key, value) VALUES ('h', '1')")
        lock_held.set()
        time.sleep(0.4)
        h.commit()  # gibt den Write-Lock frei
        h.close()

    worker = threading.Thread(target=_hold_then_release)
    worker.start()
    assert lock_held.wait(2.0), "Holder hat den Lock nicht rechtzeitig genommen"

    writer = _raw(db_file, busy_ms=30000)  # wie Produktion
    t0 = time.perf_counter()
    writer.execute("INSERT INTO settings (key, value) VALUES ('w', '1')")
    writer.commit()
    elapsed = time.perf_counter() - t0
    worker.join()

    # Write hat auf die Freigabe gewartet und ist DURCHGEGANGEN — kein Hang.
    assert elapsed < 5.0, f"Write haengt ({elapsed:.2f}s) statt durchzugehen"
    val = writer.execute("SELECT value FROM settings WHERE key='w'").fetchone()[0]
    assert val == "1", "contended Write wurde nicht persistiert"
    writer.close()
