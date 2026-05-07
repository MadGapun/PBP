"""Tests fuer v1.7.0-beta.30 — #594 Stufe 5: Telemetrie-Sharing.

User-Vorgaben:
- Default OFF
- Wochenweise (nicht taeglich)
- Konfigurierbares Intervall + Off-Schalter
- Empfaenger PBP-Service@Elwosa.de
- Nichts geht automatisch raus — User muss mailto klicken
- Privacy: nur signifikante Insights + aggregierte Zahlen
"""
import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta30_")
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


# ============= DB-Helper ===============

def test_telemetry_default_off(setup_env):
    db = setup_env
    s = db.get_telemetry_settings()
    assert s["enabled"] is False
    assert s["interval_days"] == 7  # Wochenweise default
    assert s["recipient"] == "PBP-Service@Elwosa.de"
    assert s["last_share_at"] == ""


def test_telemetry_set_enabled(setup_env):
    db = setup_env
    out = db.set_telemetry_settings(enabled=True)
    assert out["enabled"] is True


def test_telemetry_interval_validation(setup_env):
    db = setup_env
    db.set_telemetry_settings(interval_days=14)
    assert db.get_telemetry_settings()["interval_days"] == 14
    db.set_telemetry_settings(interval_days=0)  # explicit off
    assert db.get_telemetry_settings()["interval_days"] == 0
    with pytest.raises(ValueError):
        db.set_telemetry_settings(interval_days=3)  # invalid


def test_mark_telemetry_shared(setup_env):
    db = setup_env
    db.upsert_learning_insight({
        "kind": "filter_recommendation", "title": "X",
        "scope": "page:stellen", "details": {"recommendation": "y"},
    })
    ts = db.mark_telemetry_shared()
    assert ts
    s = db.get_telemetry_settings()
    assert s["last_share_at"] == ts
    # Insight wurde als is_shared=1 markiert
    items = db.list_learning_insights()
    assert items[0]["is_shared"] is True


# ============= Trigger-Logik ===============

def test_trigger_disabled_when_off(setup_env):
    from bewerbungs_assistent.dashboard import _telemetry_should_trigger
    out = _telemetry_should_trigger()
    assert out["due"] is False
    assert "telemetry_share_enabled=False" in out["reason"]


def test_trigger_disabled_when_interval_zero(setup_env):
    db = setup_env
    db.set_telemetry_settings(enabled=True, interval_days=0)
    from bewerbungs_assistent.dashboard import _telemetry_should_trigger
    out = _telemetry_should_trigger()
    assert out["due"] is False
    assert "deaktiviert" in out["reason"].lower()


def test_trigger_blocked_when_no_significant_insights(setup_env):
    db = setup_env
    db.set_telemetry_settings(enabled=True, interval_days=7)
    # Insight, aber unter Significance-Schwelle
    db.upsert_learning_insight({
        "kind": "filter_recommendation",
        "title": "Tiny",
        "scope": "page:stellen",
        "details": {"recommendation": "x"},
        "score": 0.3,
    })
    from bewerbungs_assistent.dashboard import _telemetry_should_trigger
    out = _telemetry_should_trigger()
    assert out["due"] is False
    assert "signifikant" in out["reason"].lower()


def test_trigger_due_when_significant_insight(setup_env):
    db = setup_env
    db.set_telemetry_settings(enabled=True, interval_days=7)
    db.upsert_learning_insight({
        "kind": "filter_recommendation",
        "title": "Big Pattern",
        "scope": "page:stellen",
        "details": {"recommendation": "Default setzen"},
        "score": 0.95,  # signifikant
    })
    from bewerbungs_assistent.dashboard import _telemetry_should_trigger
    out = _telemetry_should_trigger()
    assert out["due"] is True


def test_trigger_blocked_within_interval(setup_env):
    db = setup_env
    db.set_telemetry_settings(enabled=True, interval_days=7)
    db.upsert_learning_insight({
        "kind": "filter_recommendation", "title": "Big",
        "scope": "page:stellen",
        "details": {"recommendation": "x"}, "score": 0.95,
    })
    db.mark_telemetry_shared()
    from bewerbungs_assistent.dashboard import _telemetry_should_trigger
    out = _telemetry_should_trigger()
    assert out["due"] is False
    # Reason kann „faellig" oder „Tag" enthalten
    assert "faellig" in out["reason"].lower() or "tag" in out["reason"].lower()


# ============= Significance-Filter ===============

def test_significance_filter_score(setup_env):
    from bewerbungs_assistent.dashboard import _telemetry_significant_insights
    items = [
        {"score": 0.9, "observed_count": 1},  # high score → in
        {"score": 0.3, "observed_count": 6},  # observed >= 5 → in
        {"score": 0.3, "observed_count": 1},  # low both → out
    ]
    out = _telemetry_significant_insights(items)
    assert len(out) == 2


# ============= Mail-Generator + Privacy ===============

def test_mail_format_no_pii(setup_env):
    db = setup_env
    # Bewusst „Hot"-Profil-Daten setzen die NIE in der Telemetrie auftauchen duerfen
    db.save_profile({"name": "Markus Mustermann", "email": "max@private.com"})
    db.upsert_learning_insight({
        "kind": "filter_recommendation",
        "title": "Score >= 70",
        "scope": "page:stellen",
        "details": {"recommendation": "Default setzen"},
        "score": 0.95,
    })

    from bewerbungs_assistent.dashboard import (
        _build_telemetry_payload, _format_telemetry_mail
    )
    payload = _build_telemetry_payload()
    mail = _format_telemetry_mail(payload)
    body = mail["body"]

    # Privacy-Garantien — KEINE PII
    assert "Markus Mustermann" not in body
    assert "max@private.com" not in body
    # Insights sollten drin sein
    assert "Score >= 70" in body
    # Hinweis-Text
    assert "KEINE persoenlichen Daten" in body


def test_mail_subject_includes_version_and_count(setup_env):
    db = setup_env
    db.upsert_learning_insight({
        "kind": "ux_friction", "title": "X",
        "scope": "page:stellen",
        "details": {"recommendation": "y"}, "score": 0.9,
    })
    from bewerbungs_assistent.dashboard import (
        _build_telemetry_payload, _format_telemetry_mail
    )
    mail = _format_telemetry_mail(_build_telemetry_payload())
    assert "PBP-Telemetrie" in mail["subject"]
    assert "1.7.0-beta.30" in mail["subject"]


# ============= API ===============

def test_api_telemetry_settings_get_default(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/telemetry/settings")
    j = r.json()
    assert j["enabled"] is False
    assert j["interval_days"] == 7
    assert j["recipient"] == "PBP-Service@Elwosa.de"


def test_api_telemetry_settings_put(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/telemetry/settings",
                   json={"enabled": True, "interval_days": 14})
    j = r.json()
    assert j["enabled"] is True
    assert j["interval_days"] == 14


def test_api_telemetry_settings_invalid_interval(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/telemetry/settings", json={"interval_days": 5})
    assert r.status_code == 400


def test_api_telemetry_preview(setup_env):
    db = setup_env
    db.upsert_learning_insight({
        "kind": "filter_recommendation", "title": "Big",
        "scope": "page:stellen",
        "details": {"recommendation": "x"}, "score": 0.95,
    })
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/telemetry/preview")
    j = r.json()
    assert "payload" in j
    assert "mail" in j
    assert j["recipient"] == "PBP-Service@Elwosa.de"
    assert "subject" in j["mail"]
    assert "body" in j["mail"]


def test_api_telemetry_mark_shared(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/telemetry/mark-shared")
    assert r.status_code == 200
    j = r.json()
    assert "shared_at" in j


# ============= Frontend Component ===============

def test_settings_page_uses_telemetry_card():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "TelemetrySharingCard" in content
    assert "/api/telemetry/settings" in content
    assert "/api/telemetry/preview" in content
    assert "PBP-Service@Elwosa.de" in content
