"""Kein Name im Code, den es nicht gibt.

Python meldet einen unbekannten Namen erst, wenn die Zeile laeuft. Steht
sie in einem `try ... except Exception`, verschwindet der Fehler still —
und mit ihm die Auskunft, die dort entstehen sollte. So fehlte nach #1103
der Hinweis auf eine schon abgelehnte Bewerbung (`TERMINAL_STATUSES`), und
zwei Eingaben im Dashboard endeten mit einem Serverfehler statt einer
Meldung (`HTTPException` ohne Import). Dieselbe Klasse wie die
ReferenceErrors im Frontend (v1.7.131 MERKE 1).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"


def test_keine_undefinierten_namen():
    pytest.importorskip("pyflakes")
    r = subprocess.run([sys.executable, "-m", "pyflakes", str(SRC)],
                       capture_output=True, text=True)
    funde = [z for z in (r.stdout + r.stderr).splitlines()
             if "undefined name" in z or "may be undefined" in z]
    assert not funde, "\n".join(funde)


def test_schwellen_stufe_meldet_falsche_eingabe_lesbar(tmp_path):
    import os
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path)
    try:
        import bewerbungs_assistent.dashboard as dash
        from fastapi.testclient import TestClient
        dash._db = db
        r = TestClient(dash.app).post("/api/schwellen-stufe", json={"bereich": "gibtsnicht"})
        assert r.status_code == 400 and "Möglich" in r.json()["error"]
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)
