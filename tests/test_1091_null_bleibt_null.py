"""#1091: Eine eingetragene 0 wird nicht still zu einem anderen Wert.

Die Klasse: ein Rueckfall mit `or` bzw. `||`, der eine 0 fuer "fehlt"
haelt. Schon behoben bei `pageSize || ...` (v1.7.93) und bei
`followup_default_days ... or 7` (v1.7.136) — und jeweils an einer
Nachbarstelle stehen geblieben. Deshalb Guards ueber den ganzen Code.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"
FRONT = REPO / "frontend" / "src"


def _or_mit_zahl_nach_get_setting(baum) -> list:
    """`get_setting(...) or <Zahl ungleich 0>` — per Syntaxbaum, damit
    Kommentare und Docstrings, die die alte Bauform ERKLAEREN, nicht
    anschlagen."""
    funde = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.BoolOp) and isinstance(knoten.op, ast.Or):
            erster = knoten.values[0]
            if (isinstance(erster, ast.Call)
                    and getattr(erster.func, "attr", "") == "get_setting"
                    and any(isinstance(v, ast.Constant) and isinstance(v.value, int)
                            and v.value != 0 for v in knoten.values[1:])):
                funde.append(knoten.lineno)
    return funde


def test_kein_get_setting_or_zahl_im_backend():
    funde = []
    for p in SRC.rglob("*.py"):
        baum = ast.parse(p.read_text(encoding="utf-8-sig"))
        funde += [f"{p.relative_to(REPO)}:{z}" for z in _or_mit_zahl_nach_get_setting(baum)]
    assert not funde, f"0 würde zur Vorgabe: {funde}"


def test_guard_sieht_die_alte_bauform():
    alt = ast.parse('x = int(db.get_setting("a", 14) or 14)')
    assert _or_mit_zahl_nach_get_setting(alt) == [1]
    neu = ast.parse('x = db.get_setting_zahl("a", 14)')
    assert _or_mit_zahl_nach_get_setting(neu) == []


_INPUT = re.compile(r"<input\b(?:(?!/>).)*?/>", re.S)


def test_kein_oder_rueckfall_an_feldern_die_null_erlauben():
    funde = []
    for p in list(FRONT.rglob("*.jsx")):
        text = p.read_text(encoding="utf-8-sig")
        for m in _INPUT.finditer(text):
            block = m.group(0)
            if re.search(r"min=\{0\}|min=\"0\"", block) and re.search(r"\|\|\s*[1-9]", block):
                zeile = text[:m.start()].count("\n") + 1
                funde.append(f"{p.relative_to(REPO)}:{zeile}")
    assert not funde, f"Feld erlaubt 0, der Wert fällt aber auf eine Vorgabe: {funde}"


def test_schwelle_wird_nirgends_mit_oder_gelesen():
    text = (FRONT / "pages" / "ProfilePage.jsx").read_text(encoding="utf-8-sig")
    assert not re.search(r"min_score_schwelle\)\s*\|\|", text)


@pytest.fixture
def client(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path)
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    yield TestClient(dash.app), db
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def test_nachfassen_nach_interview_null_bleibt_null(client):
    """AK 2: nach dem Neuladen steht 0, nicht 14 — sonst schreibt das
    naechste Verlassen des Feldes die 14 zurueck."""
    tc, db = client
    assert tc.put("/api/settings/followup",
                  json={"followup_interview_delay_days": 0}).status_code == 200
    assert tc.get("/api/settings/followup").json()["followup_interview_delay_days"] == 0


def test_vorgabe_gilt_nur_ohne_wert(client):
    _tc, db = client
    assert db.get_setting_zahl("nie_gesetzt", 14) == 14
    db.set_setting("gesetzt_null", 0)
    assert db.get_setting_zahl("gesetzt_null", 14) == 0
    db.set_setting("unlesbar", "abc")
    assert db.get_setting_zahl("unlesbar", 14) == 14
