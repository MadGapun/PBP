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
    # v1.7.0-beta.24: Profil-basiertes Auto-Aussortieren via lokaler AI
    "stellen_auto_aussortieren",
    # v1.7.0-beta.20: Recruiter-Anfragen-Tools
    "recruiter_anfrage_ablehnen",
    "bewerbung_zu_anfrage_konvertieren",
    # v1.7.7 (#753, H18): Firmen-Stand in einem Call — nie aus Gedaechtnis
    "firma_kontext",
    "profil_status",
    "profil_zusammenfassung",
    # v1.7.3 (#741): STAR-Volltext aller Projekte + Projekt-IDs
    "projekte_anzeigen",
    # v1.7.5 (#742, A20): Umlaut-Restaurierung Altbestand (Dry-Run-Default)
    "profil_umlaute_reparieren",
    "profil_bearbeiten",
    "profil_erstellen",
    "position_hinzufuegen",
    "projekt_hinzufuegen",
    "ausbildung_hinzufuegen",
    "skill_hinzufuegen",
    "skill_zeitraeume_anzeigen",
    "skill_zeitraum_hinzufuegen",
    "skill_zeitraum_loeschen",
    "skills_bereinigen",
    "stelle_vergleichen",
    "stellenbeschreibung_nachladen",
    "stellen_qualitaet_pruefen",
    "onboarding_hints_anzeigen",
    "onboarding_hint_dismiss",
    "dokument_typen_anzeigen",
    # v1.7.7 (#750, E18): OCR-Text nachtragen mit Provenienz-Pflicht
    "dokument_text_setzen",
    "dokumente_korrespondenz_abschliessen",
    "dokument_archivieren",
    "dokument_reaktivieren",
    "dokumente_bulk_archivieren",
    "dokumente_routing_plan_erstellen",
    "dokument_aktion_ausfuehren",
    "quellen_aus_urls_korrigieren",
    "quellen_health_check",
    "verwaiste_stellenrefs_bereinigen",
    # v1.7.9 (#763/#764): Bestands-Heilung fuer URL-Qualitaet und die
    # Divergenz zwischen applications.job_hash und application_jobs
    "stellen_urls_heilen",
    "bewerbungs_stellen_abgleichen",
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
    "aehnliche_stellen_finden",
    "aufwand_uebersicht",
    "bewerbung_stelle_entknuepfen",
    "bewerbung_stelle_verknuepfen",
    "bewerbung_stellen_anzeigen",
    "jobsuche_starten",
    "kontakt_anlegen",
    "kontakt_anzeigen",
    "kontakt_bearbeiten",
    "kontakt_entknuepfen",
    "kontakt_loeschen",
    "kontakt_verknuepfen",
    "kontakte_auflisten",
    "kontakte_zu_bewerbung",
    "interview_reflexion_speichern",
    "interview_reflexion_lesen",
    "interview_reflexionen_anzeigen",
    "kosten_anzeigen",
    "kosten_erfassen",
    "kosten_loeschen",
    "meeting_aufwand_setzen",
    "jobsuche_status",
    "stelle_bewerten",
    "stelle_reaktivieren",
    "stelle_wiedergaenger_pruefen",
    "todo_anlegen",
    "todo_erledigen",
    "todo_reaktivieren",
    "todos_anzeigen",
    "ablehnungsgruende_anzeigen",
    "ablehnungsgrund_anlegen",
    "ablehnungsgrund_umbenennen",
    "ablehnungsgrund_aktivieren_setzen",
    "ablehnungsgrund_loeschen",
    "stellen_anzeigen",
    "fit_analyse",
    "bewerbung_erstellen",
    "bewerbung_status_aendern",
    "bewerbungen_anzeigen",
    "statistiken_abrufen",
    "suchkriterien_setzen",
    "blacklist_anwenden",
    "blacklist_verwalten",
    "lebenslauf_exportieren",
    "lebenslauf_angepasst_exportieren",
    "fachprofil_exportieren",
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
    "bewerbung_loeschen",
    "bewerbung_bearbeiten",
    "bewerbung_notiz",
    "bewerbung_details",
    "antwort_formulieren",
    "dokument_verknuepfen",
    "google_jobs_url",
    "linkedin_browser_search",
    "stelle_manuell_anlegen",
    "kennlerngespraech_abschliessen",
    "profil_report_exportieren",
    "suchkriterien_bearbeiten",
    "suchkriterien_anzeigen",
    # v1.7.0-beta.32 (#564): Portal-spezifische Such-Profile
    "suchprofil_lesen",
    "suchprofil_aktualisieren",
    "suchprofile_auflisten",
    # v1.7.0-beta.37 (#599): Elwosa-Bridge
    "elwosa_lesen",
    "elwosa_schreiben",
    "elwosa_pause",
    "elwosa_tonfall",
    "elwosa_linie_vorschlagen",
    "elwosa_status",
    # v1.7.0-beta.39 (#608 + #606): Kontakt-Kategorien + Auto-Import
    "kontakt_kategorien_auflisten",
    "kontakt_kategorie_anlegen",
    "kontakt_kategorie_bearbeiten",
    "kontakt_kategorie_loeschen",
    "kontakte_aus_bestand_importieren",
    "kontakte_aus_bewerbungen_extrahieren",
    "scoring_konfigurieren",
    "scores_neu_berechnen",
    "stilarchiv_kontext",
    "stilarchiv_outcome_setzen",
    "stilarchiv_speichern",
    "scoring_vorschau",
    "bewerbungsbericht_exportieren",
    "keyword_vorschlaege",
    "pbp_diagnose",
    "recherche_speichern",
    # v1.5.4: Write-Back-Gaps (#443-#448)
    "meeting_hinzufuegen",
    "meeting_bearbeiten",
    "meeting_loeschen",
    "meetings_anzeigen",
    "email_verknuepfen",
    "email_loeschen",
    "emails_anzeigen",
    "stelle_bearbeiten",
    "stelle_mergen",
    "stil_auswertung",
    "dokument_entverknuepfen",
    "dokument_loeschen",
    "dokument_status_setzen",
    # v1.5.6: Scraper Health (#432)
    "scraper_diagnose",
    # v1.5.7: Journey-Abschluss (#453, #455)
    "follow_up_erledigen",
    "follow_up_hinfaellig",
    "follow_up_verschieben",
    "position_aus_bewerbung_uebernehmen",
    # v1.6.3: Anti-DB-Bypass-Pattern (#514)
    "stellen_bulk_bewerten",
    "pbp_capabilities",
    "pbp_grenze_melden",
    # v1.7.0-beta.56 (#425): Granulare KI-Steuerung
    "ki_features_lesen",
    "ki_features_setzen",
    "telemetrie_status",
    "telemetrie_setzen",
    "automatik_status",
    "automatik_setzen",
    # v1.7.0-beta.60 (#636): MCP-Tool-Telemetrie fuer Hang/Timeout-Diagnose
    "pbp_mcp_diagnose",
    # v1.7.0-beta.60 (#631): Status-Wechsel-Datum nachtraeglich aenderbar
    "bewerbung_event_datum_setzen",
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
    "ablehnungs_coaching",
    "auto_bewerbung",
    "faq",
    "bewerbung_vorbereitung",
    "profil_sync",
    "tipps_und_tricks",
    # v1.7.4 (#746, H17): Melde-Hilfe — Sofortloesung + anonymisierter Report
    "problem_melden",
    # v1.7.0-beta.37 (#599): Elwosa-Bridge-Prompts
    "elwosa_status_anzeigen",
    "elwosa_pause_anfordern",
    "elwosa_antworten",
    "elwosa_linie_lehren",
    "elwosa_zurueckholen",
    # v1.7.0-beta.58 (#634): Sammel-Prompt fuer alle Doku-Typen
    "dokumente_verarbeiten",
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
    if hasattr(mcp, "call_tool"):
        result = await mcp.call_tool(name, arguments or {})
    else:
        tool = await mcp.get_tool(name)
        result = await tool.run(arguments or {})
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
        if hasattr(mcp, "list_tools"):
            tools = await mcp.list_tools()
        else:
            tools = list((await mcp.get_tools()).values())
        if hasattr(mcp, "list_prompts"):
            prompts = await mcp.list_prompts()
        else:
            prompts = list((await mcp.get_prompts()).values())
        if hasattr(mcp, "list_resources"):
            resources = await mcp.list_resources()
        else:
            resources = list((await mcp.get_resources()).values())
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
        assert len(tools) == 183  # v1.7.9 (#763/#764): + stellen_urls_heilen + bewerbungs_stellen_abgleichen; davor v1.7.7 181
        assert len(prompts) == 25  # v1.7.4 (#746): + problem_melden
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
