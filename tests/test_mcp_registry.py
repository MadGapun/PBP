"""Smoke tests for the modular MCP registry."""

import asyncio
import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.database import Database  # noqa: E402
from bewerbungs_assistent.prompts import register_prompts  # noqa: E402
from bewerbungs_assistent.resources import register_resources  # noqa: E402
from bewerbungs_assistent.tools import register_all  # noqa: E402


EXPECTED_TOOL_NAMES = {
    "profil_status",
    "profil_zusammenfassung",
    "profil_bearbeiten",
    "profil_erstellen",
    "position_hinzufuegen",
    "projekt_hinzufuegen",
    "ausbildung_hinzufuegen",
    "skill_hinzufuegen",
    "profile_auflisten",
    "profil_wechseln",
    "neues_profil_erstellen",
    "profil_loeschen",
    "erfassung_fortschritt_lesen",
    "erfassung_fortschritt_speichern",
    "kennlerngespraech_abschliessen",
    "dokument_profil_extrahieren",
    "dokumente_zur_analyse",
    "extraktion_starten",
    "extraktion_ergebnis_speichern",
    "extraktion_anwenden",
    "extraktions_verlauf",
    "profil_exportieren",
    "profil_importieren",
    "jobsuche_starten",
    "jobsuche_status",
    "stelle_bewerten",
    "stellen_anzeigen",
    "fit_analyse",
    "bewerbung_erstellen",
    "bewerbung_status_aendern",
    "bewerbungen_anzeigen",
    "statistiken_abrufen",
    "suchkriterien_setzen",
    "blacklist_verwalten",
    "lebenslauf_exportieren",
    "lebenslauf_angepasst_exportieren",
    "anschreiben_exportieren",
    "gehalt_extrahieren",
    "gehalt_marktanalyse",
    "firmen_recherche",
    "branchen_trends",
    "skill_gap_analyse",
    "ablehnungs_muster",
    "nachfass_planen",
    "nachfass_anzeigen",
    "bewerbung_stil_tracken",
    "workflow_starten",
    "jobsuche_workflow_starten",
    "ersterfassung_starten",
    "analyse_plan_erstellen",
    "dokumente_batch_analysieren",
    "dokumente_bulk_markieren",
    "bewerbungs_dokumente_erkennen",
    "jobtitel_vorschlagen",
    "jobtitel_verwalten",
    "lebenslauf_bewerten",
}

EXPECTED_PROMPT_NAMES = {
    "ersterfassung",
    "bewerbung_schreiben",
    "interview_vorbereitung",
    "profil_ueberpruefen",
    "profil_analyse",
    "willkommen",
    "jobsuche_workflow",
    "bewerbungs_uebersicht",
    "interview_simulation",
    "gehaltsverhandlung",
    "netzwerk_strategie",
    "profil_erweiterung",
}

EXPECTED_RESOURCE_NAMES = {
    "profil://aktuell",
    "jobs://aktiv",
    "jobs://aussortiert",
    "bewerbungen://alle",
    "bewerbungen://statistik",
    "config://suchkriterien",
}


def _build_test_server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()

    mcp = FastMCP("PBP Test")
    logger = logging.getLogger("test.mcp_registry")
    register_all(mcp, db, logger)
    register_resources(mcp, db, logger)
    register_prompts(mcp, db, logger)
    return mcp, db


async def _run_tool(mcp, name, arguments=None):
    result = await mcp.call_tool(name, arguments or {})
    if hasattr(result, 'structured_content') and result.structured_content:
        return result.structured_content
    # Fallback: parse text content
    import json
    for c in (result.content if hasattr(result, 'content') else []):
        if hasattr(c, 'text'):
            try:
                return json.loads(c.text)
            except (json.JSONDecodeError, TypeError):
                return {"text": c.text}
    return {}


def _collect_names(mcp):
    """Collect tool, prompt and resource names from the MCP server."""
    async def _gather():
        tools = await mcp.list_tools()
        prompts = await mcp.list_prompts()
        resources = await mcp.list_resources()
        return (
            {t.name for t in tools},
            {p.name for p in prompts},
            {str(r.uri) for r in resources},
        )
    return asyncio.run(_gather())


def test_mcp_registry_counts(tmp_path):
    """Server registriert alle erwarteten Tools, Prompts und Resources."""
    mcp, db = _build_test_server(tmp_path)
    try:
        tools, prompts, resources = _collect_names(mcp)
        assert len(tools) == 56
        assert len(prompts) == 12
        assert len(resources) == 6
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_mcp_public_interface_names_are_stable(tmp_path):
    """Die oeffentliche MCP-Schnittstelle bleibt namentlich stabil."""
    mcp, db = _build_test_server(tmp_path)
    try:
        tools, prompts, resources = _collect_names(mcp)
        assert tools == EXPECTED_TOOL_NAMES
        assert prompts == EXPECTED_PROMPT_NAMES
        assert resources == EXPECTED_RESOURCE_NAMES
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_representative_tools_smoke_run(tmp_path):
    """Mindestens ein repraesentatives Tool pro Modul laeuft auf leerer Test-DB."""
    mcp, db = _build_test_server(tmp_path)
    try:
        export_result = asyncio.run(_run_tool(mcp, "lebenslauf_exportieren", {}))
        assert "fehler" in export_result

        db.save_profile({"name": "Smoke Test"})

        profil_result = asyncio.run(_run_tool(mcp, "profil_status", {}))
        dokumente_result = asyncio.run(_run_tool(mcp, "dokumente_zur_analyse", {}))
        jobs_result = asyncio.run(_run_tool(mcp, "stellen_anzeigen", {}))
        bewerbungen_result = asyncio.run(_run_tool(mcp, "bewerbungen_anzeigen", {}))
        suche_result = asyncio.run(
            _run_tool(
                mcp,
                "suchkriterien_setzen",
                {"keywords_muss": ["Python"], "regionen": ["Hamburg"]},
            )
        )
        analyse_result = asyncio.run(_run_tool(mcp, "gehalt_marktanalyse", {}))

        assert profil_result["status"] == "vorhanden"
        assert dokumente_result["status"] == "ok"
        assert jobs_result["anzahl"] == 0
        assert bewerbungen_result["anzahl"] == 0
        assert suche_result["status"] == "gespeichert"
        assert analyse_result["anzahl"] == 0
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_kennlerngespraech_abschliessen_sets_onboarding_signal(tmp_path):
    """Das Abschluss-Tool signalisiert der UI den Wechsel zum Quellen-Schritt."""
    mcp, db = _build_test_server(tmp_path)
    try:
        profile_id = db.create_profile("Signal Test", "signal@example.com")

        result = asyncio.run(_run_tool(mcp, "kennlerngespraech_abschliessen", {}))

        assert result["status"] == "ok"
        assert result["profil_id"] == profile_id
        assert result["naechster_schritt"] == "quellen"
        assert db.get_user_preference(f"profile_onboarding_conversation_{profile_id}") == "complete"
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_ersterfassung_workflow_uses_current_backend_prompt(tmp_path):
    """Workflow-Wrapper fuer ersterfassung zieht den Prompt aus prompts.py."""
    mcp, db = _build_test_server(tmp_path)
    try:
        db.create_profile("Prompt Test", "prompt@example.com")

        result = asyncio.run(_run_tool(mcp, "workflow_starten", {"name": "ersterfassung"}))

        assert "kennlerngespraech_abschliessen()" in result["anweisungen"]
        assert "Jobboersen" in result["anweisungen"]
        assert "Super, dein Profil ist fertig!" not in result["anweisungen"]
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_document_extraction_tool_is_profile_scoped(tmp_path):
    """dokument_profil_extrahieren darf nur Dokumente des aktiven Profils liefern."""
    mcp, db = _build_test_server(tmp_path)
    try:
        profile_a = db.create_profile("Profil A", "a@example.com")
        doc_a = db.add_document({
            "filename": "a_cv.pdf",
            "filepath": "/tmp/a_cv.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": "Profil A Inhalt",
            "profile_id": profile_a,
        })

        profile_b = db.create_profile("Profil B", "b@example.com")
        doc_b = db.add_document({
            "filename": "b_cv.pdf",
            "filepath": "/tmp/b_cv.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": "Profil B Inhalt",
            "profile_id": profile_b,
        })

        leaked = asyncio.run(_run_tool(mcp, "dokument_profil_extrahieren", {"document_id": doc_a}))
        own = asyncio.run(_run_tool(mcp, "dokument_profil_extrahieren", {"document_id": doc_b}))

        assert "fehler" in leaked
        assert own["status"] == "ok"
        assert own["dokument"]["id"] == doc_b

        db.switch_profile(profile_a)
        own_a = asyncio.run(_run_tool(mcp, "dokument_profil_extrahieren", {"document_id": doc_a}))
        assert own_a["status"] == "ok"
        assert own_a["dokument"]["id"] == doc_a
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_application_style_tracking_tool_is_profile_scoped(tmp_path):
    """bewerbung_stil_tracken darf keine Bewerbung aus anderem Profil anfassen."""
    mcp, db = _build_test_server(tmp_path)
    try:
        profile_a = db.create_profile("Profil A", "a@example.com")
        app_a = db.add_application({"title": "A", "company": "Firma A", "status": "beworben"})

        profile_b = db.create_profile("Profil B", "b@example.com")
        app_b = db.add_application({"title": "B", "company": "Firma B", "status": "beworben"})

        leaked = asyncio.run(_run_tool(mcp, "bewerbung_stil_tracken", {
            "bewerbung_id": app_a,
            "stil": "direkt",
        }))
        own = asyncio.run(_run_tool(mcp, "bewerbung_stil_tracken", {
            "bewerbung_id": app_b,
            "stil": "direkt",
        }))

        assert db.get_active_profile_id() == profile_b
        assert "fehler" in leaked
        assert own["status"] == "gespeichert"
        assert own["bewerbung_id"] == app_b
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_jobsuche_workflow_uses_only_active_profile_data(tmp_path):
    """jobsuche_workflow darf nur Kriterien/Quellen des aktiven Profils verwenden."""
    mcp, db = _build_test_server(tmp_path)
    try:
        profile_a = db.create_profile("Profil A", "a@example.com")
        db.set_search_criteria("keywords_muss", ["A_ONLY"])
        db.set_setting("active_sources", ["bundesagentur"])
        db.set_setting("last_search_at", "2026-03-10T09:00:00")

        profile_b = db.create_profile("Profil B", "b@example.com")
        db.set_search_criteria("keywords_muss", ["B_ONLY"])
        db.set_setting("active_sources", ["stepstone"])
        db.set_setting("last_search_at", "2026-03-12T09:00:00")

        assert db.get_active_profile_id() == profile_b
        workflow_b = asyncio.run(_run_tool(mcp, "workflow_starten", {"name": "jobsuche_workflow"}))
        assert "B_ONLY" in workflow_b["anweisungen"]
        assert "stepstone" in workflow_b["anweisungen"]
        assert "A_ONLY" not in workflow_b["anweisungen"]

        db.switch_profile(profile_a)
        workflow_a = asyncio.run(_run_tool(mcp, "workflow_starten", {"name": "jobsuche_workflow"}))
        assert "A_ONLY" in workflow_a["anweisungen"]
        assert "bundesagentur" in workflow_a["anweisungen"]
        assert "B_ONLY" not in workflow_a["anweisungen"]
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)
