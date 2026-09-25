"""Menuepfade des Dashboards an einer Stelle (H30, #1087 G12).

Antworten und Anleitungen nannten Wege, die es nicht gibt:
"Einstellungen → Job-Quellen" (der Reiter heisst "Quellen"), "Settings ->
KI-Unterstuetzung" (englisch, und der Schalter lag unter "Lokale KI"),
"Dashboard -> Stellen -> 'Jetzt suchen'" (der Knopf heisst "Interne
Jobsuche starten"). Hier stehen die echten Namen; ein Test haelt die
Reiter gegen `SettingsPage.jsx` und verbietet frei getippte Pfade.
"""
from __future__ import annotations

TRENNER = " › "

# Reiter der Einstellungen, so wie sie im Dashboard heissen.
EINSTELLUNGEN_REITER = {
    "quellen": "Quellen",
    "lokale_ki": "Lokale KI",
    "claude": "Claude (Cloud)",
    "erweiterungen": "Erweiterungen",
    "automatik": "Automatik",
    "ablehnungsgruende": "Bewertung",
    "system": "System",
    "erscheinungsbild": "Erscheinungsbild",
    "datenschutz": "Datenschutz",
}

MENUE = {
    **{k: "Einstellungen" + TRENNER + v for k, v in EINSTELLUNGEN_REITER.items()},
    "stellen": "Stellen",
    "interne_suche": "Stellen" + TRENNER + "Interne Jobsuche starten",
    "bewerbungen": "Bewerbungen",
    "profil": "Profil",
    "dokumente": "Dokumente",
    "aufgaben": "Aufgaben",
    "kalender": "Kalender",
    "statistiken": "Statistiken",
}


def pfad(schluessel: str) -> str:
    """Der Menuepfad, etwa 'Einstellungen › Quellen'."""
    return MENUE[schluessel]
