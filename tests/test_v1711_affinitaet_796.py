"""Tests fuer v1.7.11 — #796 (A25): SQLite-Spalten-Affinitaet bei Text-IDs.

Belegter Fall 25.07.2026: `dokument_verknuepfen()` scheitert reproduzierbar
mit "FOREIGN KEY constraint failed" fuer Bewerbungen, deren 8-stellige
Hex-ID zugleich eine gueltige Zahl in wissenschaftlicher Notation ist:

    '42061e46' -> 4.2061e+50      (Wert ist nicht mehr die ID)
    '1e960980' -> inf             (Ueberlauf — kollidiert mit ALLEN)

Der Ueberlauf-Fall ist der gefaehrlichere: `inf = inf` ist wahr, also
meldet jede Pruefung per SELECT solche Zeilen als sauber, obwohl sie
rechnerisch zu jeder ueberlaufenden Bewerbung passen.
"""
import importlib
import os
import shutil
import sqlite3
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1711_796_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_796_die_falle_selbst(tmp_path):
    """Der Mechanismus, isoliert nachgestellt — ohne PBP-Code."""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE a (id TEXT PRIMARY KEY)")
    c.execute("CREATE TABLE d (id TEXT, linked_application_id INTEGER "
              "REFERENCES a(id))")
    c.execute("INSERT INTO a VALUES ('42061e46')")
    c.execute("INSERT INTO d VALUES ('x', '42061e46')")
    row = c.execute("SELECT linked_application_id AS v, "
                    "typeof(linked_application_id) AS t FROM d").fetchone()
    assert row[1] == "real", "Ohne Fix wird der Text zur Zahl"
    assert row[0] != "42061e46"

    # Und der Ueberlauf-Fall
    c.execute("INSERT INTO d VALUES ('y', '1e960980')")
    row2 = c.execute("SELECT linked_application_id FROM d "
                     "WHERE id='y'").fetchone()
    assert row2[0] == float("inf"), "1e960980 laeuft ueber"


def _alt_zustand_herstellen(db):
    """Baut den Zustand einer gewachsenen DB nach: documents-Spalte mit
    INTEGER-Affinitaet, plus zwei Bewerbungen mit kritischen IDs."""
    conn = db.connect()
    pid = db.get_active_profile_id()
    conn.execute("PRAGMA writable_schema=ON")
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='documents'").fetchone()["sql"]
    conn.execute(
        "UPDATE sqlite_master SET sql=? WHERE type='table' AND name='documents'",
        (sql.replace("linked_application_id TEXT",
                     "linked_application_id INTEGER"),))
    conn.execute("PRAGMA writable_schema=OFF")
    conn.commit()
    # Verbindung neu aufbauen, damit SQLite das geaenderte Schema liest
    db.close()
    conn = db.connect()
    conn.execute("PRAGMA foreign_keys=OFF")  # Alt-Zustand simulieren

    for aid in ("42061e46", "1e960980", "aabbccdd"):
        conn.execute(
            "INSERT INTO applications (id, profile_id, company, title, status, "
            "created_at, updated_at) VALUES (?,?,?,?,'beworben','2026-01-01','2026-01-01')",
            (aid, pid, f"Firma {aid[:4]}", "Rolle"))
    # Dokumente: eines wissenschaftlich verunglueckt, eines inf, eines sauber
    for did, target in (("d1", "42061e46"), ("d2", "1e960980"),
                        ("d3", "aabbccdd")):
        conn.execute(
            "INSERT INTO documents (id, filename, doc_type, "
            "linked_application_id, profile_id, created_at) "
            "VALUES (?,?,'sonstiges',?,?,'2026-01-01')",
            (did, f"{did}.pdf", target, pid))
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def test_796_altzustand_wird_erkannt(setup_env):
    db, _ = setup_env
    conn = _alt_zustand_herstellen(db)
    # Vorbedingung: die Werte sind tatsaechlich verunglueckt
    typen = {r["t"]: r["n"] for r in conn.execute(
        "SELECT typeof(linked_application_id) AS t, COUNT(*) AS n "
        "FROM documents WHERE linked_application_id IS NOT NULL "
        "GROUP BY typeof(linked_application_id)").fetchall()}
    assert typen.get("real", 0) >= 2, f"Repro fehlgeschlagen: {typen}"

    from bewerbungs_assistent.services.spalten_affinitaet import pruefe
    diag = pruefe(db)
    assert diag["handlungsbedarf"] is True
    befund = next(b for b in diag["befunde"]
                  if b["spalte"] == "linked_application_id")
    assert befund["affinitaet_falsch"] is True
    assert befund["betroffene_zeilen"] >= 2


def test_796_heilung_uebersetzt_zurueck_und_leert_mehrdeutiges(setup_env):
    db, _ = setup_env
    conn = _alt_zustand_herstellen(db)
    from bewerbungs_assistent.services.spalten_affinitaet import heilen, pruefe

    vorschau = heilen(db, dry_run=True)
    assert vorschau["status"] == "vorschau"
    unveraendert = conn.execute(
        "SELECT typeof(linked_application_id) AS t FROM documents "
        "WHERE id='d1'").fetchone()["t"]
    assert unveraendert == "real", "dry_run darf nichts aendern"

    res = heilen(db, dry_run=False)
    assert res["status"] == "ausgefuehrt"
    # Die Heilung baut die Verbindung neu auf (Schema-Reload) — frisch holen
    conn = db.connect()
    block = next(e for e in res["ergebnis"]
                 if e["spalte"] == "linked_application_id")
    # d1 (4.2061e+50) ist eindeutig rueckuebersetzbar
    assert block["geheilt"] >= 1
    d1 = conn.execute("SELECT linked_application_id AS v FROM documents "
                      "WHERE id='d1'").fetchone()["v"]
    assert d1 == "42061e46", f"Rueckuebersetzung fehlgeschlagen: {d1!r}"
    # d2 lief zu `inf` ueber. Solange nur EINE Bewerbung ueberlaeuft, ist
    # auch dieser Wert eindeutig aufloesbar — die Rueckuebersetzung geht
    # ueber die echten IDs, nicht ueber Raten. Der Issue ging hier von
    # Totalverlust aus; tatsaechlich wird mehr gerettet.
    d2 = conn.execute("SELECT linked_application_id AS v FROM documents "
                      "WHERE id='d2'").fetchone()["v"]
    assert d2 == "1e960980", f"inf-Fall haette aufloesbar sein muessen: {d2!r}"
    # Saubere Verknuepfung bleibt unangetastet
    d3 = conn.execute("SELECT linked_application_id AS v FROM documents "
                      "WHERE id='d3'").fetchone()["v"]
    assert d3 == "aabbccdd"


def test_796_mehrdeutiger_ueberlauf_wird_geleert_statt_geraten(setup_env):
    """Zwei ueberlaufende IDs: beide ergeben `inf`, die Zuordnung ist damit
    nicht mehr rekonstruierbar. Dann lieber keine Verknuepfung als eine
    falsche — eine falsche faellt niemandem auf."""
    db, _ = setup_env
    conn = _alt_zustand_herstellen(db)
    pid = db.get_active_profile_id()
    conn.execute("PRAGMA foreign_keys=OFF")
    # Zweite ueberlaufende Bewerbung + Dokument darauf
    conn.execute(
        "INSERT INTO applications (id, profile_id, company, title, status, "
        "created_at, updated_at) VALUES ('2e990111',?,'Firma Z','Rolle',"
        "'beworben','2026-01-01','2026-01-01')", (pid,))
    conn.execute(
        "INSERT INTO documents (id, filename, doc_type, "
        "linked_application_id, profile_id, created_at) "
        "VALUES ('d4','d4.pdf','sonstiges','2e990111',?,'2026-01-01')", (pid,))
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")

    from bewerbungs_assistent.services.spalten_affinitaet import heilen
    res = heilen(db, dry_run=False)
    conn = db.connect()
    block = next(e for e in res["ergebnis"]
                 if e["spalte"] == "linked_application_id")
    assert block["geleert"] >= 2, block
    assert block["nicht_rekonstruierbar"], "Der Fall muss benannt werden"
    assert any(len(u["moegliche_ziele"]) > 1
               for u in block["nicht_rekonstruierbar"]), block
    for did in ("d2", "d4"):
        v = conn.execute("SELECT linked_application_id AS v FROM documents "
                         f"WHERE id='{did}'").fetchone()["v"]
        assert v is None, f"{did} haette geleert werden muessen, ist {v!r}"


def test_796_nach_heilung_ist_die_falle_zu(setup_env):
    """Der eigentliche Zweck: neue Verknuepfungen bleiben Text."""
    db, _ = setup_env
    conn = _alt_zustand_herstellen(db)
    from bewerbungs_assistent.services.spalten_affinitaet import heilen
    heilen(db, dry_run=False)
    conn = db.connect()

    conn.execute(
        "UPDATE documents SET linked_application_id='42061e46' WHERE id='d3'")
    conn.commit()
    row = conn.execute("SELECT linked_application_id AS v, "
                       "typeof(linked_application_id) AS t FROM documents "
                       "WHERE id='d3'").fetchone()
    assert row["t"] == "text", f"Spalte immer noch numerisch: {row['t']}"
    assert row["v"] == "42061e46"


def test_796_idempotent(setup_env):
    db, _ = setup_env
    _alt_zustand_herstellen(db)
    from bewerbungs_assistent.services.spalten_affinitaet import heilen
    heilen(db, dry_run=False)
    zweit = heilen(db, dry_run=False)
    assert zweit["status"] == "nichts_zu_tun", zweit


def test_796_frische_db_ist_sauber(setup_env):
    """Neuinstallationen duerfen die Heilung gar nicht erst brauchen."""
    db, _ = setup_env
    from bewerbungs_assistent.services.spalten_affinitaet import pruefe
    assert pruefe(db)["handlungsbedarf"] is False


def test_796_verknuepfen_funktioniert_nach_heilung(setup_env):
    """Der gemeldete Ausgangsfall: dokument_verknuepfen scheiterte."""
    db, _ = setup_env
    conn = _alt_zustand_herstellen(db)
    from bewerbungs_assistent.services.spalten_affinitaet import heilen
    heilen(db, dry_run=False)
    conn = db.connect()

    conn.execute(
        "INSERT INTO documents (id, filename, doc_type, profile_id, created_at) "
        "VALUES ('neu1','neu.pdf','sonstiges',?,'2026-01-01')",
        (db.get_active_profile_id(),))
    conn.commit()
    # Genau der Aufruf, der vorher am Fremdschluessel scheiterte
    conn.execute(
        "UPDATE documents SET linked_application_id=? WHERE id='neu1'",
        ("42061e46",))
    conn.commit()
    row = conn.execute("SELECT linked_application_id AS v FROM documents "
                       "WHERE id='neu1'").fetchone()
    assert row["v"] == "42061e46"
