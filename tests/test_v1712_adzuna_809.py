"""Tests fuer v1.7.12 — #809 (B31): Adzuna-Zugang eintragbar.

Der Adapter war seit #654 fertig und lieferte nie etwas — es gab kein
Eingabefeld fuer die Keys, und die Quelle sah wie defekt aus, obwohl nur
die Registrierung fehlte. Kern der Umsetzung: Speichern loest sofort
einen Testabruf aus; kaputte Keys landen NICHT in den Settings.
"""
import importlib
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest


@pytest.fixture
def client_db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_809_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    yield TestClient(dash.app), db
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


class _FakeResponse:
    def __init__(self, status_code=200, results=1):
        self.status_code = status_code
        self._results = results

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return {"results": [{"id": i} for i in range(self._results)]}


def test_809_status_unkonfiguriert(client_db):
    client, db = client_db
    r = client.get("/api/quellen/adzuna")
    assert r.status_code == 200
    daten = r.json()
    assert daten["konfiguriert"] is False
    assert "registrierungs_url" in daten


def test_809_speichern_testet_zuerst(client_db):
    client, db = client_db
    with patch("httpx.get", return_value=_FakeResponse(200, results=1)):
        r = client.post("/api/quellen/adzuna",
                        json={"app_id": "abc", "app_key": "xyz"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "verbunden"
    assert db.get_setting("adzuna_app_id") == "abc"
    assert client.get("/api/quellen/adzuna").json()["konfiguriert"] is True


def test_809_kaputte_keys_werden_nicht_gespeichert(client_db):
    """Ein abgelehnter Key darf nicht als 'konfiguriert' enden — sonst
    entsteht genau der stille Zustand wieder, nur eine Ebene tiefer."""
    client, db = client_db
    with patch("httpx.get", return_value=_FakeResponse(401)):
        r = client.post("/api/quellen/adzuna",
                        json={"app_id": "falsch", "app_key": "falsch"})
    assert r.status_code == 400
    assert "lehnt die Keys ab" in r.json()["error"]
    assert not db.get_setting("adzuna_app_id", ""), \
        "abgelehnte Keys duerfen nicht gespeichert werden"


def test_809_leere_eingabe_wird_abgelehnt(client_db):
    client, db = client_db
    r = client.post("/api/quellen/adzuna", json={"app_id": "", "app_key": ""})
    assert r.status_code == 400
