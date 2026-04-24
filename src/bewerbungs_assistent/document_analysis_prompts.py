"""Prompt-Templates fuer die Dokumenten-Analyse (#496).

Zentrale Registry von typ-spezifischen Analyse-Prompts. Beim Klick auf
"Analysieren" im Dashboard waehlt PBP automatisch das passende Template
anhand von doc_type, Dateiname und bereits extrahiertem Text. Der Nutzer
kann das Template manuell ueberschreiben (Dropdown im UI).

Neue Templates hier ergaenzen, nicht hart in dashboard.py kodieren.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .services.email_service import STATUS_PATTERNS


# ---------------------------------------------------------------------------
# Template-Registry
# ---------------------------------------------------------------------------
# Jedes Template: label (UI-Name) + focus (Analyse-Schwerpunkte als Liste) +
# apply_to_profile (True = Ergebnis auch ins Profil extrahieren).

TEMPLATES: dict[str, dict[str, Any]] = {
    "eingangsbestaetigung": {
        "label": "Bewerbungsbestaetigung",
        "apply_to_profile": False,
        "focus": [
            "Tonalitaet: Standard-Autoantwort oder personalisiert?",
            "Timeline-Hinweise: Bearbeitungsdauer oder naechster Schritt genannt?",
            "Kontaktperson (Name, Rolle, E-Mail) falls erkennbar",
            "Referenz-/Kennzeichen der Bewerbung",
            "Empfohlene naechste Aktion (abwarten / nachfassen / Unterlagen nachreichen)",
            "Empfohlene Follow-up-Frist",
        ],
    },
    "stellenausschreibung": {
        "label": "Stellenausschreibung",
        "apply_to_profile": False,
        "focus": [
            "Must-Have-Kriterien (harte K.O.-Kriterien vs. Wunschliste)",
            "Versteckte Anforderungen (was zwischen den Zeilen gefordert wird)",
            "Gehalts-Indikatoren (explizit, Tarifverweis, Signalworte)",
            "Arbeitsmodell (Vor-Ort / Hybrid / Remote)",
            "Entscheiderrolle (HR vs. Fachabteilung)",
            "Gap-Analyse gegen das aktive Profil",
            "Anschreiben-Hooks: 3 Punkte, die das Anschreiben adressieren sollte",
        ],
    },
    "absage": {
        "label": "Absage",
        "apply_to_profile": False,
        "focus": [
            "Ablehnungsgrund: explizit oder generisch?",
            "Personalisiert oder Standardtext?",
            "Tuer offen fuer spaeter? (Talentpool, andere Stellen)",
            "Empfehlung: Kontakt warm halten oder abhaken?",
            "Lessons-Learned zur Passung / zum Prozess",
            "Follow-up-Empfehlung (Talentpool-Registrierung, LinkedIn-Kontakt)",
        ],
    },
    "gespraechsnotiz": {
        "label": "Gespraechs-/Interview-Notiz",
        "apply_to_profile": False,
        "focus": [
            "Commitments: Wer hat was fuer wann zugesagt?",
            "Offene Fragen (beide Seiten)",
            "Signale: Interesse vs. Zurueckhaltung",
            "Entscheider identifiziert?",
            "Naechste Schritte (explizit oder implizit)",
            "Empfohlene Follow-up-Aktion und -Frist",
        ],
    },
    "vertrag": {
        "label": "Vertrag / Angebot",
        "apply_to_profile": False,
        "focus": [
            "Vertragliche Eckdaten (Gehalt, Boni, Urlaub, Kuendigungsfrist, Probezeit)",
            "Abweichungen vom Marktueblichen",
            "Potenzielle Verhandlungspunkte",
            "Unklare / schwammige Klauseln",
            "Rote Flaggen (Wettbewerbsverbote, Rueckzahlungsklauseln, Verfuegbarkeitspflichten)",
            "Empfehlung: akzeptieren / verhandeln / ablehnen (mit Begruendung)",
        ],
    },
    "profil_aufbau": {
        "label": "Profil-Dokument (CV, Zeugnis, Zertifikat)",
        "apply_to_profile": True,
        "focus": [
            "Profilrelevante Informationen vollstaendig extrahieren",
            "Positionen, Ausbildungen, Skills, Sprachen, Projekte erkennen",
            "Konflikte mit bestehenden Profildaten markieren",
        ],
    },
    "fallback": {
        "label": "Sonstiges (Fallback)",
        "apply_to_profile": False,
        "focus": [
            "Kerninhalt kurz zusammenfassen",
            "Strukturierte Daten extrahieren (Personen, Firmen, Daten, Kennzeichen)",
            "Relevanz fuer den Bewerbungsprozess",
            "Empfohlene naechste Aktion",
        ],
    },
}


# ---------------------------------------------------------------------------
# Auswahl-Logik
# ---------------------------------------------------------------------------

_PROFILE_DOC_TYPES = {
    "lebenslauf",
    "lebenslauf_vorlage",
    "anschreiben",
    "anschreiben_vorlage",
    "zeugnis",
    "zertifikat",
    "bescheinigung",
    "referenz",
    "projektliste",
}

_STELLENBESCHREIBUNG_KEYWORDS = ("stellenausschreibung", "stellenbeschreibung",
                                 "job-description", "ausschreibung")
_NOTIZ_KEYWORDS = ("gespraechsnotiz", "gespraech", "interview-notiz",
                    "notiz", "protokoll", "interview-prep", "vorbereitung")
_VERTRAG_KEYWORDS = ("vertrag", "offer", "contract", "arbeitsvertrag", "angebot")


def select_template_key(document: dict) -> str:
    """Waehlt automatisch das passende Template-Key anhand von doc_type,
    Dateiname und extrahiertem Text.
    """
    doc_type = str(document.get("doc_type") or "").lower()
    filename = str(document.get("filename") or "").lower()
    text = str(document.get("extracted_text") or "").lower()[:4000]

    # Profil-Dokumente (CV, Zeugnis, Zertifikat, Anschreiben, ...)
    if doc_type in _PROFILE_DOC_TYPES:
        return "profil_aufbau"

    # Stellenbeschreibung
    if doc_type == "stellenbeschreibung":
        return "stellenausschreibung"
    if any(kw in filename for kw in _STELLENBESCHREIBUNG_KEYWORDS):
        return "stellenausschreibung"

    # Interview-Vorbereitung / Gespraechsnotiz
    if doc_type == "vorbereitung":
        return "gespraechsnotiz"
    if any(kw in filename for kw in _NOTIZ_KEYWORDS):
        return "gespraechsnotiz"

    # Vertrag / Angebot
    if any(kw in filename for kw in _VERTRAG_KEYWORDS):
        return "vertrag"

    # E-Mail-Dokumente: STATUS_PATTERNS matchen
    if doc_type in {"mail_eingang", "mail_ausgang"} or Path(filename).suffix.lower() in {".eml", ".msg"}:
        for status, patterns in STATUS_PATTERNS.items():
            if any(p in text for p in patterns):
                if status == "eingangsbestaetigung":
                    return "eingangsbestaetigung"
                if status == "abgelehnt":
                    return "absage"
                if status == "angebot":
                    return "vertrag"
                if status == "interview":
                    return "gespraechsnotiz"

    return "fallback"


def available_templates() -> list[dict[str, Any]]:
    """Liste aller Templates fuer UI-Dropdown."""
    return [
        {"key": key, "label": tpl["label"], "apply_to_profile": tpl["apply_to_profile"]}
        for key, tpl in TEMPLATES.items()
    ]


# ---------------------------------------------------------------------------
# Prompt-Builder
# ---------------------------------------------------------------------------

def build_prompt(document: dict, template_key: str | None = None) -> dict[str, Any]:
    """Baut den Analyse-Prompt fuer ein Dokument.

    Args:
        document: dict mit mindestens id, filename, doc_type, extraction_status,
                  extracted_text, app_company, app_title.
        template_key: Optional. Wenn None, automatische Auswahl.

    Returns:
        dict mit keys: prompt (str), template (str), label (str), apply_to_profile (bool).
    """
    if not template_key or template_key not in TEMPLATES:
        template_key = select_template_key(document)

    template = TEMPLATES[template_key]
    focus_lines = "\n".join(f"- {line}" for line in template["focus"])

    document_id = str(document.get("id") or "")
    filename = str(document.get("filename") or "Unbekannte Datei")
    doc_type_label = str(document.get("doc_type_label") or document.get("doc_type") or "Dokument")
    extraction_status = str(document.get("extraction_status") or "nicht_extrahiert")
    is_email = Path(filename).suffix.lower() in {".eml", ".msg"}
    extracted_available = bool(str(document.get("extracted_text") or "").strip())

    # Bewerbungs-Kontext
    app_company = str(document.get("app_company") or "").strip()
    app_title = str(document.get("app_title") or "").strip()
    app_label = " \u2014 ".join(p for p in (app_company, app_title) if p)

    header_lines = [
        f"Bitte analysiere im aktiven PBP-Profil das Dokument \u201E{filename}\u201C "
        f"(Template: {template['label']}).",
        "",
        f"- Dokument-ID: {document_id}",
        f"- Dateiname: {filename}",
        f"- Dokumenttyp in PBP: {doc_type_label}",
        f"- Aktueller Extraktionsstatus: {extraction_status}",
    ]
    if app_label:
        header_lines.insert(1, "")
        header_lines.insert(1, f"Verknuepft mit Bewerbung: {app_label}")

    workflow_lines = [
        "",
        "Ablauf:",
        f"1. Nutze `extraktion_starten(document_ids=[\"{document_id}\"], force=True)`, "
        f"damit wirklich nur dieses Dokument geladen wird.",
    ]

    if template["apply_to_profile"]:
        workflow_lines.extend([
            "2. Analysiere den Inhalt vollstaendig auf profilrelevante Informationen.",
            "3. Speichere das Ergebnis mit `extraktion_ergebnis_speichern(...)`.",
            "4. Wende verwertbare Daten mit `extraktion_anwenden(...)` direkt auf das aktive Profil an.",
            "5. Fasse danach kurz zusammen: was uebernommen wurde, was unklar blieb, welche Ergaenzung noch fehlt.",
        ])
    else:
        workflow_lines.extend([
            "2. Analysiere den Inhalt entlang der unten genannten Fokus-Punkte.",
            "3. Liefere das Ergebnis als strukturierte Zusammenfassung zurueck.",
            "4. Wenn konkrete Folgeaktionen sichtbar werden (Follow-up planen, Status aendern, Notiz speichern), "
            "nenne die passenden PBP-Tools (`nachfass_planen`, `bewerbung_status_aendern`, `bewerbung_notiz`).",
        ])

    focus_block = [
        "",
        "Fokus der Analyse:",
        focus_lines,
    ]

    footer_lines = ["", "Wichtig:",
                    "- Stelle keine Rueckfrage, ob du das Dokument analysieren sollst. Fang direkt an.",
                    "- Arbeite nur im aktiven Profil."]
    if is_email:
        footer_lines.append(
            "- Es handelt sich um eine E-Mail-Datei: Betreff, Absender, Nachrichtentext und "
            "erkennbare Anhaenge beruecksichtigen."
        )
    if not extracted_available:
        footer_lines.append(
            "- Falls das Dokument keinen lesbaren Text liefert, melde das klar zurueck und "
            "nenne den wahrscheinlichsten Grund."
        )

    prompt = "\n".join(header_lines + workflow_lines + focus_block + footer_lines)

    return {
        "prompt": prompt,
        "template": template_key,
        "label": template["label"],
        "apply_to_profile": template["apply_to_profile"],
    }
