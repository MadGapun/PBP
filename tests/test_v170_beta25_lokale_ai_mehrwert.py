"""Tests fuer v1.7.0-beta.25 — Lokale AI bietet spuerbaren Mehrwert.

Findings: #591 (Modellname `—`) + #592 (Modelle ohne Terminal) plus
neuer Auto-Mail- und Auto-Doku-Klassifikations-Schritt in der Auto-Engine.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta25_")
    os.environ["BA_DATA_DIR"] = tmpdir
    os.environ.pop("PBP_LLM_MOCK", None)
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.services.llm_service as _llm_mod
    importlib.reload(_llm_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db, _dash_mod, _llm_mod
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _mock_status_active(svc, models=("llama3.2:3b",)):
    svc._status.ollama_available = True
    svc._status.available_models = list(models)
    svc._status.user_state = "active"
    svc._status.selected_model = models[0]
    svc._status.last_check_at = 9999999999


# ============= #591: Auto-Select wenn nur 1 Modell ===============

def test_591_auto_select_single_model(setup_env):
    """Wenn genau 1 Modell installiert + nichts ausgewaehlt → automatisch aktiv."""
    db, _, llm_mod = setup_env
    svc = llm_mod.LLMService(db)
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = b'{"models":[{"name":"llama3.2:3b","size":2000000000}]}'
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=fake_resp):
        s = svc.get_status(force_refresh=True)
    assert s.ollama_available is True
    assert s.available_models == ["llama3.2:3b"]
    assert s.selected_model == "llama3.2:3b"  # Auto-Select


def test_591_no_auto_select_when_multiple_models(setup_env):
    """Bei >1 Modellen wird NICHT automatisch ausgewaehlt — User entscheidet."""
    db, _, llm_mod = setup_env
    svc = llm_mod.LLMService(db)
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = (
        b'{"models":[{"name":"llama3.2:3b","size":2000000000},'
        b'{"name":"qwen2.5:7b","size":4000000000}]}'
    )
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=fake_resp):
        s = svc.get_status(force_refresh=True)
    assert len(s.available_models) == 2
    assert s.selected_model is None  # User muss explizit waehlen


# ============= #591/#592: models_detail in Status ===============

def test_models_detail_includes_size_and_metadata(setup_env):
    db, _, llm_mod = setup_env
    svc = llm_mod.LLMService(db)
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = (
        b'{"models":[{"name":"llama3.2:3b","size":2099826944,'
        b'"modified_at":"2026-04-01T10:00:00Z",'
        b'"details":{"family":"llama","parameter_size":"3B"}}]}'
    )
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=fake_resp):
        s = svc.get_status(force_refresh=True)
    assert len(s.models_detail) == 1
    detail = s.models_detail[0]
    assert detail["name"] == "llama3.2:3b"
    assert detail["size_bytes"] == 2099826944
    assert detail["family"] == "llama"
    assert detail["parameter_size"] == "3B"


def test_status_endpoint_returns_models_detail(setup_env):
    db, _, llm_mod = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = b'{"models":[{"name":"llama3.2:3b","size":2000000000}]}'
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=fake_resp):
        r = client.get("/api/llm/status")
    j = r.json()
    assert "models_detail" in j
    assert j["models_detail"][0]["name"] == "llama3.2:3b"
    assert j["models_detail"][0]["size_bytes"] == 2000000000


# ============= NEU: Auto-Mail-Klassifikation in Auto-Engine ===============

def test_auto_classify_emails_skips_when_no_local_ai(setup_env):
    """Ohne aktive lokale AI: skipped, kein Claude-Fallback."""
    db, dash, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("no")):
        r = client.post("/api/auto-actions/run")
    j = r.json()
    assert "mail_classify" in j
    assert j["mail_classify"]["skipped"] is True


def test_auto_classify_emails_classifies_when_active(setup_env):
    """Mit aktiver LLM werden eingehende Mails klassifiziert."""
    db, dash, llm_mod = setup_env
    db.set_profile_setting("llm_local_state", "active")
    pid = db.get_active_profile_id()
    aid = db.add_application({"title": "T", "company": "C"})
    db.add_email({
        "application_id": aid,
        "filename": "test.eml",
        "subject": "Einladung zum Erstgespraech",
        "sender": "anna@acme.com",
        "body_text": "Sehr geehrter Herr ...",
        "direction": "eingang",
    })

    svc = llm_mod.LLMService(db)
    _mock_status_active(svc)

    with patch.object(svc, "_ollama_generate", return_value="einladung_interview"):
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=svc):
            from fastapi.testclient import TestClient
            from bewerbungs_assistent.dashboard import app
            client = TestClient(app)
            r = client.post("/api/auto-actions/run")
    j = r.json()
    assert j["mail_classify"]["classified"] >= 1
    # Verifizieren: detected_status ist gesetzt
    conn = db.connect()
    row = conn.execute(
        "SELECT detected_status FROM application_emails WHERE application_id=?",
        (aid,)
    ).fetchone()
    assert row["detected_status"] == "einladung_interview"


def test_auto_classify_emails_idempotent(setup_env):
    """Mails mit detected_status werden nicht erneut klassifiziert."""
    db, dash, llm_mod = setup_env
    db.set_profile_setting("llm_local_state", "active")
    pid = db.get_active_profile_id()
    aid = db.add_application({"title": "T", "company": "C"})
    # Mail mit bereits gesetztem Status
    eid = db.add_email({
        "application_id": aid,
        "filename": "x.eml", "subject": "S", "sender": "a@b.de",
        "body_text": "...", "direction": "eingang",
        "detected_status": "absage",
    })

    svc = llm_mod.LLMService(db)
    _mock_status_active(svc)

    call_count = {"n": 0}
    def fake_gen(*a, **k):
        call_count["n"] += 1
        return "newsletter"

    with patch.object(svc, "_ollama_generate", side_effect=fake_gen):
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=svc):
            from fastapi.testclient import TestClient
            from bewerbungs_assistent.dashboard import app
            client = TestClient(app)
            r = client.post("/api/auto-actions/run").json()
    # Mail-Klassifikation darf NICHT erneut laufen (Mail hat schon detected_status).
    # v1.7.0-beta.39: Auto-Engine hat 7 Steps inkl. extract_contacts/elwosa —
    # LLM kann von DENEN aufgerufen werden, nur nicht von mail_classify.
    assert r.get("mail_classify", {}).get("classified", 0) == 0
    # Status bleibt absage
    row = db.connect().execute(
        "SELECT detected_status FROM application_emails WHERE id=?", (eid,)
    ).fetchone()
    assert row["detected_status"] == "absage"


# ============= NEU: Auto-Doku-Klassifikation ===============

def test_auto_classify_documents_classifies_sonstiges(setup_env):
    """Dokumente mit doc_type='sonstiges' + Text werden klassifiziert."""
    db, dash, llm_mod = setup_env
    db.set_profile_setting("llm_local_state", "active")
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO documents (id, profile_id, filename, doc_type, "
        "extracted_text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("d1", pid, "lebenslauf.pdf", "sonstiges",
         "Markus Mustermann, geb. 1980. Berufserfahrung: PLM Architect bei ACME...",
         "2026-05-01T10:00:00")
    )
    conn.commit()

    svc = llm_mod.LLMService(db)
    _mock_status_active(svc)

    with patch.object(svc, "_ollama_generate", return_value="lebenslauf"):
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=svc):
            from fastapi.testclient import TestClient
            from bewerbungs_assistent.dashboard import app
            client = TestClient(app)
            r = client.post("/api/auto-actions/run")
    j = r.json()
    assert j["document_classify"]["classified"] >= 1
    row = conn.execute("SELECT doc_type FROM documents WHERE id='d1'").fetchone()
    assert row["doc_type"] == "lebenslauf"


def test_auto_classify_documents_skips_already_classified(setup_env):
    """Doku mit doc_type != 'sonstiges' wird nicht angetastet."""
    db, dash, llm_mod = setup_env
    db.set_profile_setting("llm_local_state", "active")
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO documents (id, profile_id, filename, doc_type, "
        "extracted_text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("d_class", pid, "x.pdf", "anschreiben", "Sehr geehrte ...",
         "2026-05-01T10:00:00")
    )
    conn.commit()

    svc = llm_mod.LLMService(db)
    _mock_status_active(svc)

    call_count = {"n": 0}
    def fake_gen(*a, **k):
        call_count["n"] += 1
        return "lebenslauf"

    with patch.object(svc, "_ollama_generate", side_effect=fake_gen):
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=svc):
            from fastapi.testclient import TestClient
            from bewerbungs_assistent.dashboard import app
            client = TestClient(app)
            client.post("/api/auto-actions/run")
    assert call_count["n"] == 0
    row = conn.execute("SELECT doc_type FROM documents WHERE id='d_class'").fetchone()
    assert row["doc_type"] == "anschreiben"


# ============= Frontend-Komponenten ===============

def test_settings_page_has_model_detail_list():
    src = (PROJECT_ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert "ModelDetailList" in src
    assert "Weiteres Modell installieren" in src


def test_settings_page_has_tasks_explanation():
    src = (PROJECT_ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert "Was laeuft lokal?" in src
    assert "Doku-Klassifikation" in src
    assert "Stellen-Profil-Match" in src


# Hilfs-Import — MagicMock muss bereitstehen
from unittest.mock import MagicMock  # noqa: E402
