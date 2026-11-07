"""#1282 Punkt 2: die Modulliste der Gesundheitsauskunft nennt nur Pakete, die PBP wirklich einbindet.

`pdfplumber` stand in der Liste, ohne dass PBP es je benutzt; die Auskunft zeigte "pdfplumber: null", und wer sie las (Diagnose, Fehlerbericht),
hielt das fehlende Paket fuer einen Fehler. Der Test haelt die Liste gegen `pyproject.toml` und gegen den Quelltext.
"""
import importlib
import os
import re
import shutil
import tempfile
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent


@pytest.fixture
def dash():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v181_1282_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    _dash_mod._db = db
    yield _dash_mod
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _pakete_aus_pyproject() -> set[str]:
    text = (WURZEL / "pyproject.toml").read_text(encoding="utf-8")
    namen = set()
    for m in re.finditer(r'^\s*"([A-Za-z0-9_.\-]+)\s*(?:[<>=!~\[][^"]*)?"\s*,?\s*(?:#.*)?$', text, re.M):
        namen.add(m.group(1).lower().replace("_", "-"))
    return namen


def test_die_modulliste_nennt_kein_paket_das_pbp_nicht_benutzt(dash):
    assert "pdfplumber" not in dash.GESUNDHEIT_MODULE
    pakete = _pakete_aus_pyproject()
    for importname, paket in dash.GESUNDHEIT_MODULE.items():
        assert paket.lower() in pakete, f"{paket} steht nicht in pyproject.toml"


def test_jedes_genannte_modul_wird_im_quelltext_eingebunden(dash):
    quelltext = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                          for p in (WURZEL / "src" / "bewerbungs_assistent").rglob("*.py"))
    for importname in dash.GESUNDHEIT_MODULE:
        assert re.search(rf"^\s*(?:from|import)\s+{re.escape(importname)}\b", quelltext, re.M), \
            f"{importname} wird nirgends eingebunden"


def test_pdfplumber_wird_nirgends_eingebunden():
    quelltext = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                          for p in (WURZEL / "src" / "bewerbungs_assistent").rglob("*.py"))
    assert not re.search(r"^\s*(?:from|import)\s+pdfplumber\b", quelltext, re.M)


def test_die_auskunft_zeigt_genau_diese_module(dash):
    from fastapi.testclient import TestClient
    daten = TestClient(dash.app).get("/api/health").json()
    assert set(daten["modules"]) == set(dash.GESUNDHEIT_MODULE)
    assert "pdfplumber" not in daten["modules"]
