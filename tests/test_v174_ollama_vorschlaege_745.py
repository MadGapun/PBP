"""Tests fuer v1.7.4 — #745 (F24): Ollama-gestuetzte Keyword-/Jobtitel-Vorschlaege.

Lokale KI bevorzugt, Heuristik-Fallback unveraendert; keyword_vorschlaege
faellt bei leerem Stellen-Bestand auf Profil-Basis zurueck (#744-Anteil)
statt in die alte Sackgasse ("starte zuerst eine Jobsuche").
Kein echtes Ollama in Tests — Service wird gemockt.
"""
import asyncio
import logging
from unittest.mock import patch

import pytest

from bewerbungs_assistent.services.llm_service import (
    Backend,
    TaskKind,
    TaskResult,
    build_profil_kurztext,
    _parse_extract_keywords,
    _parse_suggest_job_titles,
)


# =====================================================================
# Parser + Profil-Kurztext (pure functions)
# =====================================================================

class TestParser:
    def test_parse_extract_keywords_sauber(self):
        raw = "MUSS: PLM, Teamcenter, Projektleitung\nPLUS: Python, NX, Migration"
        out = _parse_extract_keywords(raw)
        assert out["keywords_muss"] == ["PLM", "Teamcenter", "Projektleitung"]
        assert out["keywords_plus"] == ["Python", "NX", "Migration"]

    def test_parse_extract_keywords_messy(self):
        raw = (
            "Hier sind die Begriffe:\n"
            "MUSS: - PLM, • Teamcenter,\n"
            "PLUS: 1. Python, 2. NX Open,\n"
            "Viel Erfolg!"
        )
        out = _parse_extract_keywords(raw)
        assert "PLM" in out["keywords_muss"]
        assert "Teamcenter" in out["keywords_muss"]
        assert "Python" in out["keywords_plus"]
        assert "NX Open" in out["keywords_plus"]
        # Floskel-Zeilen ohne MUSS:/PLUS:-Praefix werden ignoriert
        assert all("Erfolg" not in k for k in out["keywords_muss"] + out["keywords_plus"])

    def test_parse_extract_keywords_leer(self):
        out = _parse_extract_keywords("")
        assert out == {"keywords_muss": [], "keywords_plus": []}

    def test_parse_suggest_job_titles(self):
        raw = "Projektleiter PLM, PLM Consultant, Senior Systems Engineer"
        out = _parse_suggest_job_titles(raw)
        assert out["titel"] == [
            "Projektleiter PLM", "PLM Consultant", "Senior Systems Engineer"]

    def test_parse_suggest_job_titles_mit_bullets_und_limit(self):
        raw = "- Titel A lang\n- Titel B lang\n" + ",".join(
            f"Weiterer Titel {i}" for i in range(10))
        out = _parse_suggest_job_titles(raw)
        assert len(out["titel"]) <= 6


class TestProfilKurztext:
    def test_enthaelt_positionen_skills_projekte_ohne_pii(self):
        profile = {
            "name": "Max Privatperson",
            "email": "max@example.com",
            "summary": "Erfahrener PLM-Berater.",
            "positions": [{
                "title": "Lead Engineer", "company": "Musterfirma",
                "technologies": "Teamcenter, NX",
                "projects": [{"name": "Migration X", "role": "Projektleiter"}],
            }],
            "skills": [
                {"name": "PLM", "category": "fachlich", "level": 5},
                {"name": "Python", "category": "tool", "level": 4},
            ],
        }
        text = build_profil_kurztext(profile)
        assert "Lead Engineer bei Musterfirma" in text
        assert "Teamcenter" in text
        assert "Migration X" in text
        assert "PLM" in text
        # Personenbezogene Daten bleiben draussen
        assert "Max Privatperson" not in text
        assert "max@example.com" not in text

    def test_leeres_profil(self):
        assert build_profil_kurztext(None) == ""
        assert build_profil_kurztext({}) == ""


# =====================================================================
# Tool-Ebene (DB isoliert, LLM gemockt)
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


def _mcp_mit(db, modul):
    from fastmcp import FastMCP
    mcp = FastMCP("test")
    modul.register(mcp, db, logging.getLogger("test"))
    return mcp


class _FakeLocalService:
    """Simuliert einen laufenden Ollama mit festem Payload."""

    def __init__(self, payload):
        self._payload = payload

    def select_backend(self, task):
        return Backend.LOCAL

    def run(self, task, payload):
        return TaskResult(backend=Backend.LOCAL, success=True, payload=self._payload)


def _profil_befuellen(db):
    pos_id = db.add_position({"company": "Musterfirma", "title": "PLM Consultant"})
    db.add_project(pos_id, {"name": "Teamcenter-Migration", "role": "Lead"})
    for name, cat, lvl in [("Teamcenter", "tool", 5), ("PLM", "fachlich", 5),
                           ("Kommunikation", "soft_skill", 4)]:
        db.add_skill({"name": name, "category": cat, "level": lvl})


class TestKeywordVorschlaegeProfilPfad:
    def test_heuristik_fallback_ohne_ollama(self, tmp_db):
        """Frisches Profil, 0 Stellen, lokale KI aus (Default user_state=off):
        Vorschlaege kommen aus Jobtiteln + fachlichen Skills."""
        from bewerbungs_assistent.tools import analyse
        _profil_befuellen(tmp_db)
        tmp_db.add_job_title("PLM Consultant", source="auto",
                             profile_id=tmp_db.get_active_profile_id())
        mcp = _mcp_mit(tmp_db, analyse)
        out = _call(mcp, "keyword_vorschlaege", {})
        assert out["aktive_stellen"] == 0
        assert out["quelle"] == "heuristik_profil"
        assert "PLM Consultant" in out["profil_vorschlaege"]["muss"]
        assert "Teamcenter" in out["profil_vorschlaege"]["plus"]
        # Soft Skills sind keine Suchbegriffe
        assert "Kommunikation" not in out["profil_vorschlaege"]["plus"]
        assert "suchkriterien_setzen" in out["hinweis"]

    def test_lokale_ki_pfad(self, tmp_db):
        from bewerbungs_assistent.tools import analyse
        _profil_befuellen(tmp_db)
        fake = _FakeLocalService(
            {"keywords_muss": ["PLM", "Teamcenter"], "keywords_plus": ["NX", "Migration"]})
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=fake):
            mcp = _mcp_mit(tmp_db, analyse)
            out = _call(mcp, "keyword_vorschlaege", {})
        assert out["quelle"] == "lokale_ki"
        assert out["profil_vorschlaege"]["muss"] == ["PLM", "Teamcenter"]
        assert out["profil_vorschlaege"]["plus"] == ["NX", "Migration"]

    def test_bereits_gesetzte_keywords_nicht_nochmal(self, tmp_db):
        from bewerbungs_assistent.tools import analyse
        _profil_befuellen(tmp_db)
        tmp_db.set_search_criteria("keywords_muss", ["PLM"])
        fake = _FakeLocalService(
            {"keywords_muss": ["PLM", "Teamcenter"], "keywords_plus": ["plm", "NX"]})
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=fake):
            mcp = _mcp_mit(tmp_db, analyse)
            out = _call(mcp, "keyword_vorschlaege", {})
        assert "PLM" not in out["profil_vorschlaege"]["muss"]
        assert "plm" not in out["profil_vorschlaege"]["plus"]

    def test_ki_feature_gate_blockt_lokale_ki(self, tmp_db):
        """master=False → Heuristik, auch wenn Ollama liefe."""
        from bewerbungs_assistent.tools import analyse
        _profil_befuellen(tmp_db)
        tmp_db.set_ki_features(master=False)
        fake = _FakeLocalService(
            {"keywords_muss": ["DarfNichtKommen"], "keywords_plus": []})
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=fake):
            mcp = _mcp_mit(tmp_db, analyse)
            out = _call(mcp, "keyword_vorschlaege", {})
        assert out["quelle"] == "heuristik_profil"
        assert "DarfNichtKommen" not in out["profil_vorschlaege"]["muss"]

    def test_kein_profil(self, tmp_path):
        from bewerbungs_assistent.database import Database
        from bewerbungs_assistent.tools import analyse
        db = Database(tmp_path / "leer.db")
        db.initialize()
        try:
            mcp = _mcp_mit(db, analyse)
            out = _call(mcp, "keyword_vorschlaege", {})
            assert "ersterfassung" in out["nachricht"]
        finally:
            db.close()


class TestJobtitelVorschlagenLokaleKI:
    def test_ohne_titel_generiert_lokale_ki(self, tmp_db):
        from bewerbungs_assistent.tools import profil
        _profil_befuellen(tmp_db)
        fake = _FakeLocalService({"titel": ["PLM Consultant", "Projektleiter PLM"]})
        with patch("bewerbungs_assistent.services.llm_service.get_llm_service",
                   return_value=fake):
            mcp = _mcp_mit(tmp_db, profil)
            out = _call(mcp, "jobtitel_vorschlagen", {})
        assert out["status"] == "ok"
        assert out["generiert_von"] == "lokale_ki"
        assert set(out["hinzugefuegt"]) == {"PLM Consultant", "Projektleiter PLM"}
        gespeichert = tmp_db.get_suggested_job_titles(tmp_db.get_active_profile_id())
        assert {t["title"] for t in gespeichert} == {"PLM Consultant", "Projektleiter PLM"}

    def test_ohne_titel_ohne_ollama_klarer_hinweis(self, tmp_db):
        from bewerbungs_assistent.tools import profil
        _profil_befuellen(tmp_db)
        mcp = _mcp_mit(tmp_db, profil)
        out = _call(mcp, "jobtitel_vorschlagen", {})
        assert out["status"] == "keine_titel"
        assert "jobtitel_vorschlagen(titel=[...])" in out["nachricht"]

    def test_mit_titel_wie_bisher(self, tmp_db):
        """Regression: expliziter Aufruf mit Titeln bleibt unveraendert."""
        from bewerbungs_assistent.tools import profil
        mcp = _mcp_mit(tmp_db, profil)
        out = _call(mcp, "jobtitel_vorschlagen",
                    {"titel": ["Software-Architekt"], "quelle": "auto"})
        assert out["status"] == "ok"
        assert out["hinzugefuegt"] == ["Software-Architekt"]
        assert "generiert_von" not in out
