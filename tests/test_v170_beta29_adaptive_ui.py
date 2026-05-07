"""Tests fuer v1.7.0-beta.29 — #594 Stufe 4: Adaptive UI.

scope-Heuristik im LLM-Parser + /api/learning/hints + Frontend-Integration.
"""
import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta29_")
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


# ============= scope-Heuristik im Parser ===============

def test_heuristic_scope_stellen():
    from bewerbungs_assistent.services.llm_service import (
        _heuristic_scope_for_insight
    )
    s = _heuristic_scope_for_insight(
        "filter_recommendation",
        "Score-Filter ueber 70 als Default",
        "Du wendest filter_score>=70 fast jedes Mal an.",
    )
    assert s == "page:stellen"


def test_heuristic_scope_bewerbungen():
    from bewerbungs_assistent.services.llm_service import (
        _heuristic_scope_for_insight
    )
    s = _heuristic_scope_for_insight(
        "workflow_optimization",
        "Anschreiben-Workflow oft abgebrochen",
        "Bewerbungen werden in 60% der Faelle abgebrochen.",
    )
    assert s == "page:bewerbungen"


def test_heuristic_scope_kontakte():
    from bewerbungs_assistent.services.llm_service import (
        _heuristic_scope_for_insight
    )
    s = _heuristic_scope_for_insight(
        "ux_friction",
        "Kontakte hat viele Klicks",
        "LinkedIn-Felder sind versteckt.",
    )
    assert s == "page:kontakte"


def test_heuristic_scope_einstellungen():
    from bewerbungs_assistent.services.llm_service import (
        _heuristic_scope_for_insight
    )
    s = _heuristic_scope_for_insight(
        "ux_friction",
        "Lokale AI-Modell wird oft gewechselt",
        "Modell-Einstellungen koennten besser sichtbar sein.",
    )
    assert s == "page:einstellungen"


def test_heuristic_scope_ux_friction_falls_back_to_dashboard():
    from bewerbungs_assistent.services.llm_service import (
        _heuristic_scope_for_insight
    )
    s = _heuristic_scope_for_insight(
        "ux_friction",
        "Allgemeine Beobachtung",
        "Etwas was zu nichts passt",
    )
    assert s == "page:dashboard"


def test_parser_includes_scope_in_output():
    from bewerbungs_assistent.services.llm_service import (
        _parse_analyze_user_patterns
    )
    raw = (
        "filter_recommendation|Score-Filter ueber 70|"
        "Du wendest filter_score>=70 fast jedes Mal an"
    )
    out = _parse_analyze_user_patterns(raw)
    assert out["count"] == 1
    assert out["insights"][0]["scope"] == "page:stellen"


# ============= /api/learning/hints API ===============

def test_hints_empty_when_no_insights(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/learning/hints?page=stellen")
    j = r.json()
    assert j["hints"] == []
    assert j["page"] == "stellen"


def test_hints_filter_by_page(setup_env):
    db = setup_env
    db.upsert_learning_insight({
        "kind": "filter_recommendation",
        "title": "Score >= 70",
        "scope": "page:stellen",
        "details": {"recommendation": "Default setzen"},
        "score": 0.9,
    })
    db.upsert_learning_insight({
        "kind": "ux_friction",
        "title": "Anschreiben Abbruch",
        "scope": "page:bewerbungen",
        "details": {"recommendation": "UX pruefen"},
        "score": 0.8,
    })

    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)

    r1 = client.get("/api/learning/hints?page=stellen")
    j1 = r1.json()
    assert j1["count"] == 1
    assert j1["hints"][0]["title"] == "Score >= 70"

    r2 = client.get("/api/learning/hints?page=bewerbungen")
    j2 = r2.json()
    assert j2["count"] == 1
    assert j2["hints"][0]["title"] == "Anschreiben Abbruch"


def test_hints_global_when_no_page(setup_env):
    db = setup_env
    db.upsert_learning_insight({
        "kind": "positive_signal",
        "title": "Power-User",
        "scope": "global",
        "details": {"recommendation": "Weiter so"},
    })
    db.upsert_learning_insight({
        "kind": "filter_recommendation",
        "title": "Score Filter",
        "scope": "page:stellen",
        "details": {"recommendation": "x"},
    })

    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/learning/hints?page=")
    j = r.json()
    titles = {h["title"] for h in j["hints"]}
    assert "Power-User" in titles
    assert "Score Filter" not in titles


def test_hints_respects_limit(setup_env):
    db = setup_env
    for i in range(5):
        db.upsert_learning_insight({
            "kind": "filter_recommendation",
            "title": f"Hint {i}",
            "scope": "page:stellen",
            "details": {"recommendation": f"R{i}"},
            "score": 1.0 - (i * 0.1),
        })
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/learning/hints?page=stellen&limit=2")
    j = r.json()
    assert len(j["hints"]) == 2


def test_hints_excludes_dismissed(setup_env):
    db = setup_env
    iid = db.upsert_learning_insight({
        "kind": "ux_friction",
        "title": "X",
        "scope": "page:stellen",
        "details": {"recommendation": "y"},
    })
    db.dismiss_learning_insight(iid)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/learning/hints?page=stellen")
    assert r.json()["count"] == 0


# ============= Frontend-Component vorhanden ===============

def test_adaptive_hint_banner_component_exists():
    p = PROJECT_ROOT / "frontend" / "src" / "components" / "AdaptiveHintBanner.jsx"
    assert p.exists(), "AdaptiveHintBanner.jsx fehlt"
    content = p.read_text(encoding="utf-8")
    assert "/api/learning/hints" in content
    assert "STORAGE_KEY" in content


def test_jobs_page_uses_adaptive_hint_banner():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "JobsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "AdaptiveHintBanner" in content
    assert 'page="stellen"' in content


def test_applications_page_uses_adaptive_hint_banner():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "ApplicationsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "AdaptiveHintBanner" in content
    assert 'page="bewerbungen"' in content


def test_dashboard_page_uses_adaptive_hint_banner():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "DashboardPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "AdaptiveHintBanner" in content
    assert 'page="dashboard"' in content
