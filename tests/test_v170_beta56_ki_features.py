"""Tests fuer v1.7.0-beta.56 — Granulare KI-Steuerung (#425).

Drei Schichten:
- DB: get/set/is_enabled mit Master-AND-Specific Logik
- MCP-Tools: ki_features_lesen + ki_features_setzen
- API-Endpoints: GET/PUT /api/settings/ki-features
- Backend-Gates: jobsuche_starten + fit_analyse blockt bei master=False
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta56_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= DB-Schicht ============

def test_default_features_all_true(setup_env):
    db = setup_env
    cfg = db.get_ki_features()
    assert set(cfg.keys()) == set(db.KI_FEATURES)
    assert all(cfg.values())


def test_set_features_partial_update(setup_env):
    db = setup_env
    cfg = db.set_ki_features(jobsuche=False, coaching=False)
    assert cfg["jobsuche"] is False
    assert cfg["coaching"] is False
    assert cfg["dokumentenanalyse"] is True  # unangetastet
    assert cfg["master"] is True


def test_set_features_unknown_field_raises(setup_env):
    db = setup_env
    with pytest.raises(ValueError):
        db.set_ki_features(blubb=False)


def test_is_ki_feature_enabled_master_aus_blockiert_alles(setup_env):
    db = setup_env
    db.set_ki_features(master=False)
    for f in db.KI_FEATURES:
        if f == "master":
            continue
        assert db.is_ki_feature_enabled(f) is False


def test_is_ki_feature_enabled_specific_aus(setup_env):
    db = setup_env
    db.set_ki_features(jobsuche=False)
    assert db.is_ki_feature_enabled("jobsuche") is False
    assert db.is_ki_feature_enabled("coaching") is True


def test_is_ki_feature_enabled_unknown_passt_durch(setup_env):
    db = setup_env
    # Unbekannte Features blocken nicht (Defensive: keine False-Negatives
    # bei zukuenftigen Tools die noch nicht in KI_FEATURES sind).
    assert db.is_ki_feature_enabled("unbekannt") is True


# ============= MCP-Tool-Schicht ============

def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _make_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import analyse, jobs, dokumente, export_tools, workflows
    mcp = FastMCP("test")
    import logging
    log = logging.getLogger("test")
    analyse.register(mcp, db, log)
    jobs.register(mcp, db, log)
    dokumente.register(mcp, db, log)
    export_tools.register(mcp, db, log)
    workflows.register(mcp, db, log)
    return mcp


def test_mcp_ki_features_lesen(setup_env):
    db = setup_env
    mcp = _make_mcp(db)
    result = _call(mcp, "ki_features_lesen", {})
    assert "features" in result
    assert result["alle_aktiv"] is True
    assert result["master_aus"] is False


def test_mcp_ki_features_setzen(setup_env):
    db = setup_env
    mcp = _make_mcp(db)
    result = _call(mcp, "ki_features_setzen", {"jobsuche": False})
    assert result["status"] == "gespeichert"
    assert result["features"]["jobsuche"] is False
    # In DB persistiert?
    assert db.get_ki_features()["jobsuche"] is False


def test_mcp_ki_features_setzen_ohne_args(setup_env):
    db = setup_env
    mcp = _make_mcp(db)
    result = _call(mcp, "ki_features_setzen", {})
    assert "fehler" in result
    assert "aktueller_stand" in result


# ============= Backend-Gates ============

def test_gate_jobsuche_blockt_wenn_master_aus(setup_env):
    db = setup_env
    db.set_ki_features(master=False)
    mcp = _make_mcp(db)
    result = _call(mcp, "jobsuche_starten", {"keywords": ["test"]})
    assert result.get("ki_blockiert") is True
    assert result["feature"] == "jobsuche"
    assert "Master" in result["hinweis"]


def test_gate_jobsuche_blockt_wenn_jobsuche_aus(setup_env):
    db = setup_env
    db.set_ki_features(jobsuche=False)
    mcp = _make_mcp(db)
    result = _call(mcp, "jobsuche_starten", {"keywords": ["test"]})
    assert result.get("ki_blockiert") is True
    assert result["feature"] == "jobsuche"
    assert "Jobsuche" in result["hinweis"]
    # Hinweis auf Dashboard-Button als Alternative
    assert "Dashboard" in result.get("alternative", "")


def test_gate_fit_analyse_blockt(setup_env):
    db = setup_env
    db.set_ki_features(stellenanalyse=False)
    mcp = _make_mcp(db)
    result = _call(mcp, "fit_analyse", {"job_hash": "egal"})
    assert result.get("ki_blockiert") is True
    assert result["feature"] == "stellenanalyse"


def test_gate_anschreiben_blockt_bewerbungserstellung(setup_env):
    db = setup_env
    db.set_ki_features(bewerbungserstellung=False)
    mcp = _make_mcp(db)
    result = _call(mcp, "anschreiben_exportieren", {
        "text": "Test",
        "stelle": "Eng",
        "firma": "X",
    })
    assert result.get("ki_blockiert") is True


def test_gate_dokument_profil_extrahieren(setup_env):
    db = setup_env
    db.set_ki_features(dokumentenanalyse=False)
    mcp = _make_mcp(db)
    result = _call(mcp, "dokument_profil_extrahieren", {"document_id": "x"})
    assert result.get("ki_blockiert") is True


def test_gate_ablehnungs_muster_coaching(setup_env):
    db = setup_env
    db.set_ki_features(coaching=False)
    mcp = _make_mcp(db)
    result = _call(mcp, "ablehnungs_muster", {})
    assert result.get("ki_blockiert") is True


def test_gate_ersterfassung(setup_env):
    db = setup_env
    db.set_ki_features(ersterfassung=False)
    mcp = _make_mcp(db)
    result = _call(mcp, "ersterfassung_starten", {})
    assert result.get("ki_blockiert") is True


# ============= API-Endpoints ============

def test_api_get_ki_features(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/settings/ki-features")
    assert r.status_code == 200
    data = r.json()
    assert "features" in data
    assert all(data["features"].values())


def test_api_put_ki_features_top_level(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/settings/ki-features",
                    json={"jobsuche": False, "coaching": False})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["features"]["jobsuche"] is False
    assert data["features"]["coaching"] is False
    assert data["features"]["master"] is True


def test_api_put_ki_features_wrapped(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/settings/ki-features",
                    json={"features": {"master": False}})
    assert r.status_code == 200
    assert r.json()["features"]["master"] is False


def test_api_put_ki_features_leerer_body_ist_400(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/settings/ki-features", json={})
    assert r.status_code == 400


def test_api_put_ki_features_unbekannte_keys_ignoriert(setup_env):
    """Unbekannte Keys werden uebersprungen (kein Fehler), bekannte greifen."""
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/settings/ki-features",
                    json={"jobsuche": False, "blubb": True})
    assert r.status_code == 200
    assert r.json()["features"]["jobsuche"] is False
