"""Tests fuer v1.7.4 — #744 (G17): Gefuehrte Einsteiger-Kette.

Backend-Anteil: Smart-Default-Quellen in jobsuche_starten (Empfehlung bei
keine_quellen + Uebernahme beim ersten expliziten Lauf), 0-Treffer-Diagnostik
(zero_treffer_diagnose), Wizard-Phase 5 im Ersterfassungs-Prompt,
kennlerngespraech_abschliessen fuehrt zur ersten Suche weiter.
Kein Live-HTTP: run_search wird gestubbt.
"""
import asyncio
import logging
from unittest.mock import patch

import pytest

from bewerbungs_assistent.job_scraper import zero_treffer_diagnose


# =====================================================================
# 0-Treffer-Diagnostik (pure function)
# =====================================================================

class TestZeroTrefferDiagnose:
    def test_alles_bereits_bekannt(self):
        d = zero_treffer_diagnose(
            {"duplikate_db": 7, "blacklist": 2}, {"bundesagentur": {"status": "ok"}},
            ok_count=1, error_count=0, timeout_count=0)
        assert "9" in d and "bekannt" in d

    def test_keine_quelle_gelaufen(self):
        d = zero_treffer_diagnose({}, {}, ok_count=0, error_count=0, timeout_count=0)
        assert "Keine Quelle wurde tatsaechlich durchsucht" in d

    def test_alle_quellen_fehler(self):
        d = zero_treffer_diagnose(
            {}, {"a": {"status": "error"}, "b": {"status": "timeout"}},
            ok_count=0, error_count=1, timeout_count=1)
        assert "1 Fehler" in d and "1 Timeout" in d

    def test_alle_uebersprungen(self):
        d = zero_treffer_diagnose(
            {}, {"a": {"status": "skipped"}}, ok_count=0, error_count=0, timeout_count=0)
        assert "uebersprungen" in d

    def test_quellen_ok_aber_keywords_treffen_nichts(self):
        d = zero_treffer_diagnose(
            {}, {"a": {"status": "ok"}, "b": {"status": "ok"}},
            ok_count=2, error_count=0, timeout_count=0)
        assert "fehlerfrei" in d and "Keywords" in d


# =====================================================================
# jobsuche_starten: Smart-Defaults (DB isoliert, run_search gestubbt)
# =====================================================================

@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _jobs_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import jobs
    mcp = FastMCP("test")
    jobs.register(mcp, db, logging.getLogger("test"))
    return mcp


def _stub_run_search(db, job_id, params):
    """Ersatz fuer die echte Suche — markiert den Job sofort als fertig."""
    db.update_background_job(job_id, "fertig", progress=100,
                             message="stub", result={"total": 0})


def _wait_job_beendet(db, job_id, timeout=5.0):
    """Wartet bis der Hintergrund-Job durch ist — verhindert Races zwischen
    Stub-Thread (Commit) und Test-Asserts sowie Patch-Exit vor Thread-Start."""
    import time
    start = time.time()
    while time.time() - start < timeout:
        job = db.get_background_job(job_id)
        if job and job.get("status") in ("fertig", "fehler"):
            return job
        time.sleep(0.05)
    return db.get_background_job(job_id)


class TestSmartDefaultQuellen:
    def test_keine_quellen_empfiehlt_starter_satz(self, tmp_db):
        tmp_db.set_search_criteria("keywords_muss", ["PLM"])
        mcp = _jobs_mcp(tmp_db)
        out = _call(mcp, "jobsuche_starten", {})
        assert out["status"] == "keine_quellen"
        assert out["empfohlene_start_quellen"] == [
            "bundesagentur", "arbeitnow", "jobspy_indeed"]
        assert "jobsuche_starten(quellen=" in out["nachricht"]

    def test_erster_expliziter_lauf_uebernimmt_quellen(self, tmp_db):
        tmp_db.set_search_criteria("keywords_muss", ["PLM"])
        with patch("bewerbungs_assistent.job_scraper.run_search", _stub_run_search):
            mcp = _jobs_mcp(tmp_db)
            out = _call(mcp, "jobsuche_starten",
                        {"quellen": ["bundesagentur", "arbeitnow", "jobspy_indeed"]})
            _wait_job_beendet(tmp_db, out.get("job_id"))
        assert out["status"] == "gestartet"
        assert out["quellen_als_aktiv_uebernommen"] == [
            "bundesagentur", "arbeitnow", "jobspy_indeed"]
        assert tmp_db.get_profile_setting("active_sources", []) == [
            "bundesagentur", "arbeitnow", "jobspy_indeed"]

    def test_bestehende_quellen_werden_nicht_ueberschrieben(self, tmp_db):
        tmp_db.set_search_criteria("keywords_muss", ["PLM"])
        tmp_db.set_profile_setting("active_sources", ["hays"])
        with patch("bewerbungs_assistent.job_scraper.run_search", _stub_run_search):
            mcp = _jobs_mcp(tmp_db)
            out = _call(mcp, "jobsuche_starten", {"quellen": ["bundesagentur"]})
            _wait_job_beendet(tmp_db, out.get("job_id"))
        assert out["status"] == "gestartet"
        assert "quellen_als_aktiv_uebernommen" not in out
        assert tmp_db.get_profile_setting("active_sources", []) == ["hays"]


# =====================================================================
# Wizard-Phase 5 + kennlerngespraech_abschliessen
# =====================================================================

class TestWizardPhase5:
    def test_prompt_enthaelt_phase_5_kette(self, tmp_db):
        from bewerbungs_assistent.prompts import build_kennlerngespraech_prompt
        text = build_kennlerngespraech_prompt(tmp_db)
        assert "PHASE 5" in text
        assert "keyword_vorschlaege()" in text
        assert "suchkriterien_setzen" in text
        assert "jobsuche_starten(quellen=['bundesagentur', 'arbeitnow'," in text
        assert "diagnose" in text
        assert "ollama.com/download" in text
        # Der Wizard darf nach Phase 4 nicht mehr im Quellen-Tab enden
        assert "direkt mit dem Schritt 'Quellen'" not in text

    def test_abschliessen_fuehrt_zur_ersten_suche(self, tmp_db):
        from bewerbungs_assistent.tools import profil
        from fastmcp import FastMCP
        mcp = FastMCP("test")
        profil.register(mcp, tmp_db, logging.getLogger("test"))
        out = _call(mcp, "kennlerngespraech_abschliessen", {})
        assert out["status"] == "ok"
        assert out["naechster_schritt"] == "erste_suche"
        assert "keyword_vorschlaege()" in out["nachricht"]
        assert "jobsuche_starten" in out["nachricht"]
        # UI-Signal bleibt stabil (Frontend wertet es aus)
        assert out["ui_signal"] == "profile_onboarding_conversation=complete"
