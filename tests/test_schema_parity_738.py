"""Schema-Parity-Tests (#738, A19) — Sicherheitsnetz gegen die #737-Fehlerklasse.

#737-Hergang: `applications.is_imported` kam per Migration (v21->v22), fehlte
aber im CREATE TABLE (SCHEMA_SQL). Migrierte Alt-DBs hatten die Spalte,
frische Neu-DBs nicht -> /api/stats/extended lieferte HTTP 500 fuer jeden
Neu-User. Solche Luecken treffen ausschliesslich Neuinstallationen und sind
im Testbetrieb unsichtbar. Diese Tests machen die Fehlerklasse zur CI-Pflicht:

1. Doppel-Migrations-Trick: `_migrate` ist idempotent — auf einer FRISCHEN
   DB nochmal die komplette Kette v1->aktuell laufen lassen. Jede Spalte/
   Tabelle, die dabei NEU entsteht, fehlt per Definition in SCHEMA_SQL.
   Deckt alle Migrationen ohne Fixture ab (#737-Richtung: fresh crasht).
2. v31-Fixture-Vergleich (Generalprobe #705): eine echte v1.6.x-DB
   hochmigrieren und spaltenweise ZWEISEITIG gegen einen Fresh-Install
   vergleichen — faengt auch die Gegenrichtung (Spalte nur in SCHEMA_SQL,
   kein Migrationspfad -> Upgrader verlieren sie).
3. Selbsttest des Mechanismus: kuenstlich entfernte CREATE-TABLE-Spalte
   MUSS als Drift erkannt werden (Done-Kriterium aus #738).

HARTE ISOLATIONS-REGEL (DB-Vorfall 2026-06-10): BA_DATA_DIR (NICHT
PBP_DATA_DIR), jeder Test asserted db_path im Temp-Verzeichnis.
"""
import importlib
import os
import shutil
import tempfile
from pathlib import Path

import pytest


def _schema_snapshot(conn) -> dict:
    """{tabelle: set(spaltennamen)} fuer alle Nicht-SQLite-Systemtabellen."""
    tables = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    return {
        t: {row[1] for row in conn.execute(f"PRAGMA table_info({t})").fetchall()}
        for t in tables
    }


def _drift(before: dict, after: dict) -> dict:
    """Spalten/Tabellen, die in `after` neu sind — d.h. nur per Migration
    entstehen und in SCHEMA_SQL fehlen (#737-Klasse)."""
    result = {}
    for table, cols in after.items():
        missing = cols - before.get(table, set())
        if missing:
            result[table] = sorted(missing)
    return result


def test_fresh_schema_enthaelt_alle_migrations_spalten(tmp_path):
    """Doppel-Migrations-Trick: die volle Migrationskette darf auf einer
    frisch initialisierten DB NICHTS mehr anlegen."""
    from bewerbungs_assistent.database import Database, SCHEMA_VERSION

    db = Database(tmp_path / "fresh.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    try:
        conn = db.connect()
        before = _schema_snapshot(conn)
        # Alle Migrationen idempotent drueberlaufen lassen (erwarteter
        # Log-Noise wie 'duplicate column name' ist ok)
        db._migrate(1, SCHEMA_VERSION)
        after = _schema_snapshot(conn)
        drift = _drift(before, after)
        assert not drift, (
            "Schema-Drift: diese Spalten existieren nur per Migration und "
            f"fehlen im CREATE TABLE (SCHEMA_SQL) — #737-Fehlerklasse: {drift}"
        )
    finally:
        db.close()


@pytest.fixture
def v31_env():
    """v31-DB aus der Generalprobe-Fixture (#705) in isoliertem BA_DATA_DIR."""
    from test_v17_migration_generalprobe_705 import _create_full_v16x_db

    tmpdir = tempfile.mkdtemp(prefix="pbp_parity_738_")
    data_dir = Path(tmpdir) / "data"
    data_dir.mkdir()
    db_path = data_dir / "pbp.db"
    _create_full_v16x_db(db_path)
    os.environ["BA_DATA_DIR"] = str(data_dir)
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    yield data_dir, tmpdir, _db_mod
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def test_migrierte_v31_db_ist_spaltenidentisch_zu_fresh_install(v31_env):
    """Ansatz A aus #738: hochmigrierte v1.6.x-DB (Baseline v31, aelteste
    reale Upgrade-Basis) vs. Fresh-Install — Spaltensets pro Tabelle muessen
    in BEIDE Richtungen identisch sein."""
    data_dir, tmpdir, _db_mod = v31_env
    Database = _db_mod.Database

    alt = Database()
    assert str(data_dir) in str(alt.db_path), f"DB nicht isoliert: {alt.db_path}"
    alt.initialize()  # Migration v31 -> SCHEMA_VERSION

    fresh = Database(Path(tmpdir) / "fresh.db")
    fresh.initialize()
    assert tmpdir in str(fresh.db_path), f"DB nicht isoliert: {fresh.db_path}"

    try:
        snap_migriert = _schema_snapshot(alt.connect())
        snap_fresh = _schema_snapshot(fresh.connect())

        probleme = []
        for table in sorted(set(snap_migriert) | set(snap_fresh)):
            m = snap_migriert.get(table)
            f = snap_fresh.get(table)
            if m is None:
                probleme.append(
                    f"Tabelle '{table}' existiert nur im Fresh-Install — "
                    "Migrationspfad fehlt (Upgrader von v1.6.x verlieren sie)"
                )
            elif f is None:
                probleme.append(
                    f"Tabelle '{table}' existiert nur nach Migration — "
                    "fehlt in SCHEMA_SQL (#737-Klasse)"
                )
            else:
                nur_migriert = m - f
                nur_fresh = f - m
                if nur_migriert:
                    probleme.append(
                        f"{table}: Spalten nur nach Migration (fehlen in "
                        f"SCHEMA_SQL, #737-Klasse): {sorted(nur_migriert)}"
                    )
                if nur_fresh:
                    probleme.append(
                        f"{table}: Spalten nur im Fresh-Install (kein "
                        f"Migrationspfad fuer Upgrader): {sorted(nur_fresh)}"
                    )
        assert not probleme, "Schema-Parity verletzt:\n- " + "\n- ".join(probleme)
    finally:
        alt.close()
        fresh.close()


def test_v16x_fresh_install_upgrade_bekommt_is_imported(v31_env):
    """Regression fuer den Fund dieses Parity-Tests (2026-07-02): das
    v1.6.x-SCHEMA_SQL enthielt `applications.is_imported` nicht (#737).
    Eine v1.6.x-NEUinstallation, die auf v1.7.x upgradet, bekam die Spalte
    nie (v22-Migration laeuft ab schema_version 31 nicht mehr) — der
    Statistik-Endpoint crashte weiter mit HTTP 500. Das Safety-Net in
    initialize() muss die Spalte idempotent nachziehen."""
    data_dir, tmpdir, _db_mod = v31_env
    db = _db_mod.Database()
    assert str(data_dir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.initialize()
    try:
        conn = db.connect()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(applications)")}
        assert "is_imported" in cols, (
            "Safety-Net hat applications.is_imported nicht nachgezogen — "
            "v1.6.x-Fresh-Install-Upgrader crashen im Statistik-Tab (#737)"
        )
        # Die urspruenglich crashende Abfrage-Form aus get_extended_stats
        row = conn.execute(
            "SELECT COUNT(*) FROM applications a WHERE COALESCE(a.is_imported, 0) = 0"
        ).fetchone()
        assert row[0] >= 0
    finally:
        db.close()


def test_selbsttest_kuenstlich_entfernte_spalte_wird_erkannt(tmp_path, monkeypatch):
    """Done-Kriterium aus #738: wird eine CREATE-TABLE-Spalte kuenstlich
    entfernt, MUSS der Parity-Check rot werden. Sentinel ist
    dismiss_reasons.is_active (v45) — bewusst NICHT applications.is_imported,
    denn dafuer existiert seit v1.7.3 ein Safety-Net in initialize(),
    das die Entfernung sofort selbst reparieren wuerde."""
    import bewerbungs_assistent.database as _db_mod

    original = _db_mod.SCHEMA_SQL
    kaputt = original.replace(
        ",\n    -- v45 (#663 C20): Deaktivierung statt Loeschen, "
        "damit Statistik erhalten bleibt\n"
        "    is_active INTEGER NOT NULL DEFAULT 1\n",
        "\n",
    )
    assert kaputt != original, "Testaufbau: is_active-Zeile nicht gefunden"
    monkeypatch.setattr(_db_mod, "SCHEMA_SQL", kaputt)

    db = _db_mod.Database(tmp_path / "kaputt.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    try:
        conn = db.connect()
        before = _schema_snapshot(conn)
        db._migrate(1, _db_mod.SCHEMA_VERSION)
        after = _schema_snapshot(conn)
        drift = _drift(before, after)
        assert drift.get("dismiss_reasons") == ["is_active"], (
            f"Kuenstlicher Drift wurde nicht erkannt: {drift}"
        )
    finally:
        db.close()
