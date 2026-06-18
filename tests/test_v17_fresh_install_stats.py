"""Regression: Fresh-Install-Schema-Luecke `applications.is_imported`.

Die Spalte wurde nur per Migration v21->v22 (ALTER TABLE) hinzugefuegt, fehlte
aber im CREATE TABLE in SCHEMA_SQL. Folge: eine FRISCH initialisierte DB (Schema
direkt auf aktueller Version, Migration laeuft nicht) hatte die Spalte nicht ->
`get_extended_stats()` (nutzt `COALESCE(a.is_imported, 0)`) crashte mit
`sqlite3.OperationalError: no such column: a.is_imported` -> Statistik-Tab
HTTP 500 fuer JEDE Neuinstallation. Migrierte Alt-DBs waren nicht betroffen.
"""
import os
import shutil
import tempfile
import importlib

import pytest


@pytest.fixture
def fresh_db():
    tmp = tempfile.mkdtemp(prefix="pbp_freshstats_")
    os.environ["BA_DATA_DIR"] = tmp
    import bewerbungs_assistent.database as dbm
    importlib.reload(dbm)
    db = dbm.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db
    db.close()
    shutil.rmtree(tmp, ignore_errors=True)


def test_fresh_install_applications_has_is_imported(fresh_db):
    cols = [r[1] for r in fresh_db.connect()
            .execute("PRAGMA table_info(applications)").fetchall()]
    assert "is_imported" in cols, (
        "is_imported fehlt im CREATE TABLE applications (nur per Migration) "
        "-> bricht Neuinstallationen"
    )


def test_fresh_install_extended_stats_no_crash(fresh_db):
    # Vor dem Fix: sqlite3.OperationalError: no such column: a.is_imported
    res = fresh_db.get_extended_stats()
    assert isinstance(res, dict)
