"""Tests fuer v1.7.0-beta.45 — Wiki-Snippets als Elwosa-Hints (#623)."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNIPPETS_DIR = PROJECT_ROOT / "docs" / "wiki-snippets"


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta45_")
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


# ============= Snippet-Loader ===============

def test_snippets_dir_exists():
    assert SNIPPETS_DIR.is_dir(), "docs/wiki-snippets/ fehlt"


def test_snippets_loaded_at_module_import():
    """services/wiki_snippets.py laedt im Modul-Import — pruefen dass es klappt."""
    from bewerbungs_assistent.services import wiki_snippets
    snippets = wiki_snippets.get_all_snippets()
    assert len(snippets) >= 12, f"Nur {len(snippets)} Snippets geladen — erwartet 12+"


def test_snippets_have_required_fields():
    from bewerbungs_assistent.services import wiki_snippets
    for s in wiki_snippets.get_all_snippets():
        assert s.get("id"), f"Snippet ohne id: {s}"
        assert s.get("page_route"), f"Snippet ohne page_route: {s}"
        assert s.get("wiki_page"), f"Snippet ohne wiki_page: {s}"
        assert s.get("body"), f"Snippet ohne body: {s}"


def test_snippet_ids_unique():
    from bewerbungs_assistent.services import wiki_snippets
    ids = [s["id"] for s in wiki_snippets.get_all_snippets()]
    assert len(ids) == len(set(ids)), "Doppelte Snippet-IDs"


def test_all_snippets_pass_tonfall_validator():
    """Snippet-Bodies werden als Elwosa-Linien gepostet und muessen Sprach-DNA-konform sein."""
    from bewerbungs_assistent.services import wiki_snippets
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    failures = []
    for s in wiki_snippets.get_all_snippets():
        try:
            validate_tonfall(s["body"])
        except Exception as e:
            failures.append(f"{s['id']}: {e}")
    assert not failures, "Snippets verstossen gegen Tonfall:\n" + "\n".join(failures)


def test_all_snippets_use_wiki_link_markup():
    """Jeder Snippet sollte mindestens einen [link:wiki:Page|...] enthalten."""
    from bewerbungs_assistent.services import wiki_snippets
    missing = []
    for s in wiki_snippets.get_all_snippets():
        if "[link:wiki:" not in s["body"]:
            missing.append(s["id"])
    assert not missing, f"Snippets ohne Wiki-Link: {missing}"


def test_pick_snippet_for_route_returns_route_snippet():
    from bewerbungs_assistent.services import wiki_snippets
    s = wiki_snippets.pick_snippet_for_route("stellen")
    assert s is not None
    # Route ist 'stellen' oder 'global' (Fallback-Pool)
    assert s["page_route"] in ("stellen", "global")


def test_pick_snippet_for_route_excludes_seen_ids():
    from bewerbungs_assistent.services import wiki_snippets
    all_stellen = wiki_snippets.get_snippets_for_route("stellen")
    if len(all_stellen) < 2:
        pytest.skip("Brauche mind. 2 Snippets fuer 'stellen'")
    seen_ids = {all_stellen[0]["id"]}
    # Wiederholt picken — wenn fresh-Pool nicht leer, kommt nie all_stellen[0]
    fresh_count_others = sum(
        1 for _ in range(20)
        if (s := wiki_snippets.pick_snippet_for_route("stellen", seen_ids))
        and s["id"] != all_stellen[0]["id"]
    )
    assert fresh_count_others == 20, "seen_ids wurde nicht respektiert"


def test_pick_snippet_for_route_unknown_route_uses_global_only():
    from bewerbungs_assistent.services import wiki_snippets
    s = wiki_snippets.pick_snippet_for_route("nonexistent-route")
    # Fallback auf 'global'
    assert s is not None
    assert s["page_route"] == "global"


# ============= Endpoint /api/wiki/request-hint ===============

def test_endpoint_400_when_page_missing(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/wiki/request-hint", json={})
    assert r.status_code == 400


def test_endpoint_returns_silent_when_elwosa_disabled(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=False)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/wiki/request-hint", json={"page": "stellen"})
    assert r.status_code == 200
    j = r.json()
    assert j["posted"] == 0
    assert j["reason"] == "elwosa_disabled"


def test_endpoint_posts_hint_first_visit(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/wiki/request-hint", json={"page": "stellen"})
    assert r.status_code == 200
    j = r.json()
    assert j["posted"] == 1
    assert "snippet_id" in j
    assert "wiki_page" in j
    # Verifiziere dass die Linie im elwosa_messages-Stream steht
    msgs = db.get_elwosa_messages()
    assert any(m["trigger_kind"] == "wiki_hint" for m in msgs)


def test_endpoint_dedup_per_route_per_day(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # Erster Aufruf postet
    r1 = client.post("/api/wiki/request-hint", json={"page": "stellen"})
    assert r1.json()["posted"] == 1
    # Zweiter Aufruf (selbe Route, gleicher Tag) postet NICHT
    r2 = client.post("/api/wiki/request-hint", json={"page": "stellen"})
    j2 = r2.json()
    assert j2["posted"] == 0
    assert j2["reason"] == "already_today_for_route"


def test_endpoint_different_routes_post_independently(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r1 = client.post("/api/wiki/request-hint", json={"page": "stellen"})
    r2 = client.post("/api/wiki/request-hint", json={"page": "bewerbungen"})
    assert r1.json()["posted"] == 1
    assert r2.json()["posted"] == 1


def test_endpoint_unknown_route_uses_global_pool(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/wiki/request-hint", json={"page": "completely-unknown"})
    j = r.json()
    # Fallback auf global-Snippets — sollte trotzdem posten
    assert j["posted"] == 1


# ============= Markup-Validator akzeptiert link:wiki ===============

def test_validator_accepts_wiki_link():
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    validate_tonfall("Mehr im Wiki: [link:wiki:Tab-Stellen|nachlesen]")


def test_strip_markup_removes_wiki_link():
    from bewerbungs_assistent.services.elwosa import strip_markup
    assert strip_markup(
        "Mehr im Wiki: [link:wiki:Tab-Stellen|nachlesen]"
    ) == "Mehr im Wiki: nachlesen"


# ============= Reload-Funktion ===============

def test_reload_snippets_works():
    from bewerbungs_assistent.services import wiki_snippets
    n = wiki_snippets.reload_snippets()
    assert n >= 12
