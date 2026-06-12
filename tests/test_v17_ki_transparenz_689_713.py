"""Regression beta.104 — F21 (#689) + F24 (#713):

- GET /api/local-ai/auto-dismissed listet Auto-Aussortierungen inkl.
  geparster KI-Begruendung aus dem dismiss_reason-Format 'auto:...:...'
- Elwosa-Tipps: aktive onboarding_hints werden als Linien mit
  Navigations- und Prompt-Link ausgespielt (Vorrang vor TIP_LINES)
"""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_689_")
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
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    _dash_mod._db = db
    yield db, _dash_mod
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _add_auto_dismissed_job(db, title="Junior Zeichner", company="X GmbH",
                            begruendung="Senior-Profil passt nicht zu Junior-Stelle"):
    import hashlib
    h = hashlib.md5(f"{company}:{title}".encode()).hexdigest()[:12]
    db.save_jobs([{
        "hash": h, "title": title, "company": company,
        "url": f"https://example.com/{h}", "source": "manuell",
        "description": "Testbeschreibung fuer die Stelle",
    }])
    resolved = db.resolve_job_hash(h) or h
    conn = db.connect()
    conn.execute(
        "UPDATE jobs SET is_active=0, dismiss_reason=? WHERE hash=?",
        (f"auto:profil_match_negativ:{begruendung}", resolved),
    )
    conn.commit()
    return resolved


# ============= F21: /api/local-ai/auto-dismissed =============

def test_689_auto_dismissed_endpoint(setup_env):
    db, dash = setup_env
    _add_auto_dismissed_job(db)
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)
    r = client.get("/api/local-ai/auto-dismissed")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1, data
    item = data["items"][0]
    assert item["title"] == "Junior Zeichner"
    assert item["begruendung"] == "Senior-Profil passt nicht zu Junior-Stelle"


def test_689_endpoint_ignoriert_manuelle_aussortierungen(setup_env):
    db, dash = setup_env
    h = _add_auto_dismissed_job(db)
    # zusaetzlich eine MANUELL aussortierte Stelle
    conn = db.connect()
    conn.execute(
        "UPDATE jobs SET dismiss_reason='zu_weit_entfernt' WHERE hash=?", (h,))
    conn.commit()
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)
    assert client.get("/api/local-ai/auto-dismissed").json()["count"] == 0


# ============= F24: Elwosa-Feature-Tipps =============

def test_713_hint_wird_zur_linie_mit_links(setup_env, monkeypatch):
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa

    fake_hints = [{
        "id": "g11_suchprofile_anlegen", "tab": "stellen",
        "title": "Tipp: Suchprofile sparen Zeit",
        "body": "Du hast schon mehrere Bewerbungen — aber noch kein Suchprofil. Mehr Text.",
        "cta_label": "Suchprofil aus aktuellen Kriterien erstellen",
        "cta_tool": "suchprofil_aktualisieren",
    }]
    import bewerbungs_assistent.services.onboarding_hints as oh
    monkeypatch.setattr(oh, "list_active_hints", lambda _db: fake_hints)

    linien = elwosa._feature_tipp_linien(db)
    assert len(linien) == 1
    line = linien[0]
    assert "[link:page:stellen|Ansehen]" in line
    assert "[link:prompt:" in line and "suchprofil_aktualisieren" in line
    assert len(line) <= 280
    assert "!" not in line  # Sprach-DNA


def test_713_ohne_hints_faellt_auf_tip_pool_zurueck(setup_env, monkeypatch):
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    import bewerbungs_assistent.services.onboarding_hints as oh
    monkeypatch.setattr(oh, "list_active_hints", lambda _db: [])
    assert elwosa._feature_tipp_linien(db) == []
