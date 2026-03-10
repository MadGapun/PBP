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
    tools = await mcp.get_tools()
    result = await tools[name].run(arguments or {})
    return result.structured_content


def test_mcp_registry_counts(tmp_path):
    """Server registriert alle erwarteten Tools, Prompts und Resources."""
    mcp, db = _build_test_server(tmp_path)
    try:
        async def collect():
            return await mcp.get_tools(), await mcp.get_prompts(), await mcp.get_resources()

        tools, prompts, resources = asyncio.run(collect())
        assert len(tools) == 44
        assert len(prompts) == 12
        assert len(resources) == 6
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_mcp_public_interface_names_are_stable(tmp_path):
    """Die oeffentliche MCP-Schnittstelle bleibt namentlich stabil."""
    mcp, db = _build_test_server(tmp_path)
    try:
        async def collect():
            return await mcp.get_tools(), await mcp.get_prompts(), await mcp.get_resources()

        tools, prompts, resources = asyncio.run(collect())
        assert set(tools) == EXPECTED_TOOL_NAMES
        assert set(prompts) == EXPECTED_PROMPT_NAMES
        assert set(resources) == EXPECTED_RESOURCE_NAMES
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
