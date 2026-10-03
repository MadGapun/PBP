"""Stilarchiv: bei gleichem Zeitstempel gilt die später angelegte Version als neuere (Fund aus dem Python-3.12-Lauf).

Der Installer richtet Python 3.12 ein. Auf Windows tickt die Systemuhr dort nur alle ~15,6 ms; zwei Versionen, die
schneller hintereinander gespeichert werden, tragen denselben Zeitstempel. `ORDER BY created_at DESC` allein ließ die
Reihenfolge dann dem Zufall. Python 3.13 hat eine feinere Uhr, deshalb zeigte nur der Lauf in einer 3.12-Umgebung den
Fehler (`test_577_stilarchiv_kontext_tool_with_data`: erwartet "Firma 2", bekam "Firma 1").

Der Test hier macht den Gleichstand ZUVERLÄSSIG, statt auf die Uhr des Rechners zu hoffen.
"""
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def db(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17150_stilarchiv_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    datenbank = _db_mod.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Test"})
    # Jede Anlage bekommt GENAU denselben Zeitstempel: der Gleichstand, den die 3.12-Uhr von selbst erzeugt.
    monkeypatch.setattr(_db_mod, "_now", lambda: "2026-10-02T12:00:00.000000+00:00")
    yield datenbank
    datenbank.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _ablegen(db, titel, **extra):
    return db.add_document_version({"kind": "cover_letter", "title": titel, "content": f"Text zu {titel}.", **extra})


def test_bei_gleichem_zeitstempel_kommt_die_zuletzt_angelegte_zuerst(db):
    for i in range(3):
        _ablegen(db, f"Firma {i}")
    titel = [v["title"] for v in db.get_recent_document_versions("cover_letter", limit=10)]
    assert titel == ["Firma 2", "Firma 1", "Firma 0"]


def test_das_limit_schneidet_die_aeltesten_ab_nicht_die_neuesten(db):
    for i in range(5):
        _ablegen(db, f"Firma {i}")
    titel = [v["title"] for v in db.get_recent_document_versions("cover_letter", limit=2)]
    assert titel == ["Firma 4", "Firma 3"]


def test_ein_spaeterer_zeitstempel_gewinnt_weiterhin_vor_der_anlagereihenfolge(db, monkeypatch):
    """Der Tie-Breaker darf die eigentliche Sortierung nicht überstimmen."""
    import bewerbungs_assistent.database as _db_mod
    monkeypatch.setattr(_db_mod, "_now", lambda: "2026-10-02T12:00:05.000000+00:00")
    _ablegen(db, "spaeter datiert, zuerst angelegt")
    monkeypatch.setattr(_db_mod, "_now", lambda: "2026-10-02T12:00:01.000000+00:00")
    _ablegen(db, "frueher datiert, zuletzt angelegt")
    titel = [v["title"] for v in db.get_recent_document_versions("cover_letter", limit=10)]
    assert titel == ["spaeter datiert, zuerst angelegt", "frueher datiert, zuletzt angelegt"]


def test_der_filter_auf_versionen_mit_ergebnis_behaelt_die_reihenfolge(db):
    _ablegen(db, "alt", outcome="interview")
    _ablegen(db, "ohne Ergebnis")
    _ablegen(db, "neu", outcome="abgelehnt")
    titel = [v["title"] for v in db.get_recent_document_versions("cover_letter", limit=10, only_with_outcome=True)]
    assert titel == ["neu", "alt"]
