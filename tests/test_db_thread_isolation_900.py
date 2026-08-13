# -*- coding: utf-8 -*-
"""Regressionstests fuer A28/#900 — eine SQLite-Connection je Thread.

Vorher teilten sich alle Threads einer Database-Instanz EINE Connection
(check_same_thread=False): Transaktionen verschraenkten sich, jeder Thread
sah die uncommitteten Zwischenstaende der anderen (belegter Fall: der
#857-Flake). Diese Tests schlagen auf der alten geteilten Connection fehl.
"""

import threading

import pytest

from bewerbungs_assistent.database import Database


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    yield d
    d.close()


def test_jeder_thread_bekommt_eigene_connection(db):
    haupt = db.connect()
    fremd = {}

    def worker():
        fremd["conn"] = db.connect()

    t = threading.Thread(target=worker, name="pbp-test-conn")
    t.start()
    t.join(5)
    assert fremd["conn"] is not haupt, (
        "Worker-Thread bekam dieselbe Connection wie der Haupt-Thread — "
        "die A28-Isolation greift nicht"
    )
    # Zweiter Aufruf im selben Thread liefert dieselbe Connection (Cache)
    assert db.connect() is haupt


def test_fremde_offene_transaktion_bleibt_unsichtbar(db):
    """Kern von #900: Ein Worker haelt eine UNCOMMITTETE Transaktion.
    Der Haupt-Thread darf sie nicht sehen, sein eigener Commit darf sie
    nicht mitcommitten, und der Worker-Rollback darf fremde Daten nicht
    anfassen. Auf der geteilten Connection war all das verletzt."""
    db.set_setting("vorher", "bleibt")

    offen_gesetzt = threading.Event()
    weiter = threading.Event()

    def worker():
        conn = db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) "
            "VALUES ('offen', '\"unfertig\"')")
        offen_gesetzt.set()          # Transaktion bewusst OFFEN halten
        weiter.wait(10)
        conn.rollback()

    t = threading.Thread(target=worker, name="pbp-test-txn")
    t.start()
    assert offen_gesetzt.wait(5), "Worker kam nicht zum Zug"

    # Haupt-Thread sieht die fremde, uncommittete Zeile NICHT
    # (geteilte Connection: sichtbar, weil dieselbe Transaktion)
    assert db.get_setting("offen") is None

    weiter.set()
    t.join(10)

    # Worker-Rollback hat nur die eigene Transaktion verworfen
    assert db.get_setting("offen") is None
    assert db.get_setting("vorher") == "bleibt"

    # Haupt-Thread schreibt und liest ungestoert weiter
    db.set_setting("nachher", "auch")
    assert db.get_setting("nachher") == "auch"


def test_rollback_if_stale_wirkt_nur_auf_eigenen_thread(db):
    """#708-Sicherheitsnetz, A28-praezisiert: Der Rollback an einer
    Ausfuehrungs-Grenze darf laufende Writes ANDERER Threads nicht
    verwerfen."""
    offen_gesetzt = threading.Event()
    weiter = threading.Event()
    ergebnis = {}

    def worker():
        conn = db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) "
            "VALUES ('worker_write', '\"laeuft\"')")
        offen_gesetzt.set()
        weiter.wait(10)
        conn.commit()                # Worker committet SELBST
        ergebnis["fertig"] = True

    t = threading.Thread(target=worker, name="pbp-test-stale")
    t.start()
    assert offen_gesetzt.wait(5)

    # Haupt-Thread (ohne eigene offene Txn) ruft das Sicherheitsnetz —
    # frueher haette das die offene Worker-Transaktion mit zurueckgerollt.
    assert db.rollback_if_stale("test") is False

    weiter.set()
    t.join(10)
    assert ergebnis.get("fertig")
    assert db.get_setting("worker_write") == "laeuft"


def test_close_schliesst_alle_thread_connections(db, tmp_path):
    def worker():
        db.connect()

    threads = [threading.Thread(target=worker, name=f"pbp-test-close-{i}")
               for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)

    db.close()
    # Nach close() ist ein Neuaufbau moeglich (frische Registry/Locals)
    db2 = Database(tmp_path / "test.db")
    db2.initialize()
    assert db2.get_setting("schema_version") is not None
    db2.close()
