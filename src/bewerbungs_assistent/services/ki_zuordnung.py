"""Welches Werkzeug braucht welche KI-Funktion (H25, #1087 G5, A8).

Die Schalter unter "Claude (Cloud)" sperren Funktionen, bei denen Inhalte
an Claude gehen. Bis v1.7.134 sass die Pruefung in neun Werkzeugen
einzeln; `extraktion_starten` (liefert Claude den Text des Lebenslaufs)
und `workflow_starten('ersterfassung')` liefen daran vorbei. Jetzt steht
die Zuordnung hier, und `tools.register_all` setzt die Sperre beim
Registrieren um jedes genannte Werkzeug — ein neues Werkzeug braucht nur
eine Zeile, keine eigene Pruefung.
"""
from __future__ import annotations

from .menue import pfad

# Werkzeug -> (Funktion, Alternative ohne KI oder None)
ZUORDNUNG: dict[str, tuple[str, str | None]] = {
    "jobsuche_starten": ("jobsuche", (
        f"Die interne Suche im Dashboard ({pfad('interne_suche')}) läuft "
        "unabhängig vom Schalter und nutzt deine aktiven Quellen.")),
    "extraktion_starten": ("dokumentenanalyse", (
        "Dokumente bleiben im Dashboard sichtbar; das Profil lässt sich "
        f"von Hand pflegen ({pfad('profil')}).")),
    "dokument_profil_extrahieren": ("dokumentenanalyse", None),
    "dokumente_batch_analysieren": ("dokumentenanalyse", None),
    "fit_analyse": ("stellenanalyse", None),
    "skill_gap_analyse": ("stellenanalyse", None),
    "lebenslauf_angepasst_exportieren": ("bewerbungserstellung", (
        "Der Standard-Lebenslauf (ohne KI-Anpassung) über "
        "lebenslauf_exportieren bleibt jederzeit nutzbar.")),
    "fachprofil_exportieren": ("bewerbungserstellung", None),
    "anschreiben_exportieren": ("bewerbungserstellung", None),
    "ablehnungs_muster": ("coaching", None),
    "ersterfassung_starten": ("ersterfassung", (
        f"Profil von Hand pflegen ({pfad('profil')}) oder über die "
        "einzelnen Werkzeuge (profil_bearbeiten, position_hinzufuegen, "
        "skill_hinzufuegen ...).")),
}

# workflow_starten entscheidet nach dem Namen des Ablaufs.
WORKFLOW_FUNKTION: dict[str, str] = {
    "ersterfassung": "ersterfassung",
    "jobsuche_workflow": "jobsuche",
    "bewerbung_schreiben": "bewerbungserstellung",
    "bewerbung_schreiben_lebenslauf": "bewerbungserstellung",
    "bewerbung_schreiben_anschreiben": "bewerbungserstellung",
    "auto_bewerbung": "bewerbungserstellung",
    "bewerbung_vorbereitung": "bewerbungserstellung",
    "interview_vorbereitung": "coaching",
    "interview_simulation": "coaching",
    "gehaltsverhandlung": "coaching",
    "netzwerk_strategie": "coaching",
    "ablehnungs_coaching": "coaching",
    "profil_erweiterung": "dokumentenanalyse",
    "dokumente_verarbeiten": "dokumentenanalyse",
}


def funktion_fuer(werkzeug: str, argumente: dict | None = None) -> tuple[str | None, str | None]:
    """(Funktion, Alternative) fuer einen Aufruf; (None, None) = frei."""
    if werkzeug == "workflow_starten":
        name = str((argumente or {}).get("name") or "").strip().lower()
        return WORKFLOW_FUNKTION.get(name), None
    return ZUORDNUNG.get(werkzeug, (None, None))
