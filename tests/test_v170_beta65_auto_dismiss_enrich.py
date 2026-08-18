"""Tests fuer v1.7.0-beta.65 — Auto-Dismiss-Hook-Fix + Score-Anreicherung (#638).

beta.63 hatte zwei Bugs im _maybe_auto_dismiss_after_search-Hook:
- svc.run_task() existiert nicht (heisst run()) -> AttributeError verschluckt
- Parser liefert 'decision' nicht 'verdict'
Dadurch lief der Auto-Dismiss nie durch. Hier verifiziert + Stufe 2
(Score-Anreicherung fuer duenne Beschreibungen) getestet.
"""
from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta65_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test", "skills": [{"name": "PLM"}],
                     "positions": [{"title": "Senior Engineer"}]})
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


class _FakeStatus:
    ollama_available = True
    user_state = "active"
    selected_model = "mock:7b"
    error = None


class _FakeResult:
    def __init__(self, decision, reason=""):
        self.success = True
        self.payload = {"decision": decision, "reason": reason}


class _FakeSvc:
    def __init__(self, decisions):
        # decisions: dict title-substr -> decision
        self._decisions = decisions
    def get_status(self, force_refresh=False):
        return _FakeStatus()
    def warmup(self, model=None):
        return {"status": "warm"}
    def run(self, task, payload):
        title = payload.get("job_title", "")
        for key, dec in self._decisions.items():
            if key in title:
                return _FakeResult(dec, "begruendung")
        return _FakeResult("UNSICHER")


def _seed_jobs(db):
    db.save_jobs([
        {"hash": "h-fit", "title": "Senior PLM Architect", "company": "GoodCo",
         "source": "test", "url": "u1", "description": "x" * 500, "score": 70},
        {"hash": "h-bad", "title": "Junior Zeichner", "company": "OldCo",
         "source": "test", "url": "u2", "description": "y" * 500, "score": 10},
        # Duenne Beschreibung + Score 0 -> Kandidat fuer Anreicherung
        {"hash": "h-thin", "title": "PLM Consultant", "company": "ThinCo",
         "source": "test", "url": "u3", "description": "kurz", "score": 0},
    ])


def test_auto_dismiss_now_actually_dismisses(setup_env, monkeypatch):
    db = setup_env
    _seed_jobs(db)
    db.set_profile_setting("auto_dismiss_after_search", "true")
    # Background-Job anlegen + auf erledigt setzen
    job_id = db.create_background_job("jobsuche", {})
    db.update_background_job(job_id, "fertig", progress=100, result={})

    from bewerbungs_assistent.services import llm_service
    fake = _FakeSvc({
        "Senior PLM Architect": "PASST",
        "Junior Zeichner": "PASST_NICHT",
        "PLM Consultant": "PASST",
    })
    monkeypatch.setattr(llm_service, "get_llm_service", lambda d: fake)

    from bewerbungs_assistent.tools.jobs import _maybe_auto_dismiss_after_search
    _maybe_auto_dismiss_after_search(db, job_id)

    conn = db.connect()
    bad = conn.execute("SELECT is_active, dismiss_reason FROM jobs WHERE hash LIKE '%h-bad'").fetchone()
    assert bad["is_active"] == 0, "PASST_NICHT-Stelle haette aussortiert werden muessen"
    # v1.7.17 (#913): der 'auto:<grund>:<text>'-Rohwert wird beim
    # Schreiben normalisiert — Grund in dismiss_reason, LLM-Begruendung
    # in dismiss_note. Die Ollama-Statistik zaehlt beide Formate.
    assert bad["dismiss_reason"] == "profil_match_negativ"


def test_score_enrichment_for_thin_description(setup_env, monkeypatch):
    db = setup_env
    _seed_jobs(db)
    db.set_profile_setting("auto_dismiss_after_search", "true")
    job_id = db.create_background_job("jobsuche", {})
    db.update_background_job(job_id, "fertig", progress=100, result={})

    from bewerbungs_assistent.services import llm_service
    fake = _FakeSvc({
        "Senior PLM Architect": "PASST",
        "Junior Zeichner": "PASST_NICHT",
        "PLM Consultant": "PASST",
    })
    monkeypatch.setattr(llm_service, "get_llm_service", lambda d: fake)

    from bewerbungs_assistent.tools.jobs import _maybe_auto_dismiss_after_search
    _maybe_auto_dismiss_after_search(db, job_id)

    conn = db.connect()
    thin = conn.execute("SELECT score, is_active FROM jobs WHERE hash LIKE '%h-thin'").fetchone()
    assert thin["is_active"] == 1, "PASST-Stelle darf nicht aussortiert werden"
    assert thin["score"] == 35, f"Score-Anreicherung griff nicht: {thin['score']}"


def test_fat_description_not_enriched(setup_env, monkeypatch):
    """Stelle mit voller Beschreibung + hohem Score wird NICHT angefasst."""
    db = setup_env
    _seed_jobs(db)
    db.set_profile_setting("auto_dismiss_after_search", "true")
    job_id = db.create_background_job("jobsuche", {})
    db.update_background_job(job_id, "fertig", progress=100, result={})

    from bewerbungs_assistent.services import llm_service
    fake = _FakeSvc({"Senior PLM Architect": "PASST"})
    monkeypatch.setattr(llm_service, "get_llm_service", lambda d: fake)

    from bewerbungs_assistent.tools.jobs import _maybe_auto_dismiss_after_search
    _maybe_auto_dismiss_after_search(db, job_id)

    conn = db.connect()
    fit = conn.execute("SELECT score FROM jobs WHERE hash LIKE '%h-fit'").fetchone()
    assert fit["score"] == 70, "voller Score wurde faelschlich ueberschrieben"


def test_result_recorded_in_background_job(setup_env, monkeypatch):
    db = setup_env
    _seed_jobs(db)
    db.set_profile_setting("auto_dismiss_after_search", "true")
    job_id = db.create_background_job("jobsuche", {})
    db.update_background_job(job_id, "fertig", progress=100, result={})

    from bewerbungs_assistent.services import llm_service
    fake = _FakeSvc({"Junior Zeichner": "PASST_NICHT", "PLM Consultant": "PASST",
                     "Senior PLM Architect": "PASST"})
    monkeypatch.setattr(llm_service, "get_llm_service", lambda d: fake)

    from bewerbungs_assistent.tools.jobs import _maybe_auto_dismiss_after_search
    _maybe_auto_dismiss_after_search(db, job_id)

    job = db.get_background_job(job_id)
    erg = job.get("result") or {}
    assert "auto_aussortiert" in erg
    assert erg["auto_aussortiert"]["aussortiert"] >= 1
    assert "score_angereichert" in erg["auto_aussortiert"]
