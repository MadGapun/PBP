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

from . import profil, dokumente, jobs, bewerbungen, suche, export_tools, analyse, workflows, kontakte, elwosa


# === Granulare KI-Steuerung (#425, beta.56) ============================
# Shared gate-Helper. Returnt None wenn erlaubt, sonst ein dict das die
# Tools direkt zurueckgeben koennen.

_KI_FEATURE_LABELS = {
    "jobsuche": "Jobsuche via Claude",
    "dokumentenanalyse": "Dokumentenanalyse",
    "stellenanalyse": "Stellenanalyse / Fit-Bewertung",
    "bewerbungserstellung": "Bewerbungs-Erstellung",
    "coaching": "Interview- und Verhandlungs-Coaching",
    "ersterfassung": "Profil-Ersterfassung via Claude",
    "guidance": "KI-Hinweise im Dashboard",
}


def ki_gate(db, feature: str) -> dict | None:
    """Pruefung vor jeder KI-Operation (#425).

    Liefert None wenn erlaubt, sonst ein Fehler-Dict das das Tool direkt
    zurueckgeben kann. Beachtet Master-Switch + Feature-Toggle.
    """
    try:
        if db.is_ki_feature_enabled(feature):
            return None
    except Exception:
        return None
    label = _KI_FEATURE_LABELS.get(feature, feature)
    cfg = db.get_ki_features()
    if not cfg.get("master", True):
        grund = "KI-Master-Switch ist aus"
        wo = "Settings -> KI-Unterstuetzung -> Master"
    else:
        grund = f"Feature '{label}' ist deaktiviert"
        wo = f"Settings -> KI-Unterstuetzung -> {label}"
    return {
        "fehler": grund,
        "feature": feature,
        "ki_blockiert": True,
        "hinweis": (
            f"{grund}. Du kannst es im Dashboard wieder einschalten: {wo}."
        ),
    }


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
    elwosa.register(mcp, db, logger)    # v1.7.0-beta.37 #599
