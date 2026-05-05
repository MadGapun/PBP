"""Tool-Module für den Bewerbungs-Assistent MCP Server.

Alle 47 MCP-Tools sind in 8 Domain-Module aufgeteilt:
- profil: Profil-Verwaltung (14 Tools)
- dokumente: Dokument-Analyse und Import/Export (8 Tools)
- jobs: Jobsuche und Stellenverwaltung (5 Tools)
- bewerbungen: Bewerbungs-Management (4 Tools)
- suche: Suchkriterien und Blacklist (2 Tools)
- export_tools: PDF/DOCX-Export (2 Tools)
- analyse: Erweiterte KI-Features (9 Tools)
- workflows: Workflow-Starter (3 Tools) — Prompts als Tools für claude.ai
"""

from . import profil, dokumente, jobs, bewerbungen, suche, export_tools, analyse, workflows, kontakte


def register_all(mcp, db, logger):
    """Registriert alle Tools beim MCP-Server."""
    profil.register(mcp, db, logger)
    dokumente.register(mcp, db, logger)
    jobs.register(mcp, db, logger)
    bewerbungen.register(mcp, db, logger)
    suche.register(mcp, db, logger)
    export_tools.register(mcp, db, logger)
    analyse.register(mcp, db, logger)
    workflows.register(mcp, db, logger)
    kontakte.register(mcp, db, logger)  # v1.7.0 #563
