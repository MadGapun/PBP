"""Per-Typ-Handler fuer Dokumente (#655, E14, beta.77).

Jeder bekannte `doc_type` hat einen Handler der:
- `extract_fields(doc) -> dict` — typspezifische Felder aus dem Doku-Text
  herauszieht (z.B. Recruiter-Name, Termin, Plattform). Best-Effort,
  liefert leere Felder wenn nichts erkennbar — nie Exception.
- `suggest_action(doc) -> str` — was sollte Claude/User damit machen?
  Kurzer Aktions-Vorschlag (1 Satz). Format: "Tool-Vorschlag — Begruendung".

Idee: statt Claude raten zu lassen "was mache ich mit diesem Dokument?",
liefert das Handler-System pro Typ klare strukturierte Hinweise.

Verwendung:
    from .services.document_handlers import handle_doc, list_known_types

    info = handle_doc(doc_dict)  # {fields: {...}, action: "...", typ: "..."}
    types = list_known_types()   # alle bekannten Typen + Beschreibung
"""
from __future__ import annotations

import re
from typing import Callable

# ── Bekannte Doku-Typen mit Beschreibung ────────────────────────────

KNOWN_TYPES: dict[str, dict] = {
    "lebenslauf": {
        "beschreibung": "CV — eigene Profildaten, Stationen, Skills",
        "claude_action": "Nutze dokument_profil_extrahieren um Daten ins Profil zu ziehen",
    },
    "anschreiben": {
        "beschreibung": "Bewerbungsschreiben fuer eine konkrete Firma",
        "claude_action": "Verknuepfe mit der zugehoerigen Bewerbung",
    },
    "zeugnis": {
        "beschreibung": "Arbeits-/Ausbildungszeugnis",
        "claude_action": "Stationen/Skills daraus extrahieren falls noch nicht im Profil",
    },
    "arbeitszeugnis": {
        "beschreibung": "Arbeitszeugnis (Synonym zu 'zeugnis')",
        "claude_action": "Stationen/Skills daraus extrahieren falls noch nicht im Profil",
    },
    "ausbildungszeugnis": {
        "beschreibung": "Schul-/Studienzeugnis",
        "claude_action": "Education ins Profil ueberfuehren",
    },
    "zertifikat": {
        "beschreibung": "Fachzertifikat (PMP, ITIL, Cloud-Cert, ...)",
        "claude_action": "Als Skill mit Validitaets-Datum hinzufuegen",
    },
    "foto": {
        "beschreibung": "Bewerbungsfoto / Portraet",
        "claude_action": "Keine Aktion noetig — nur Anhang fuer kuenftige Bewerbungen",
    },
    "stellenbeschreibung": {
        "beschreibung": "Stellenanzeigen-Text (oft als PDF/DOCX)",
        "claude_action": "Mit stelle_manuell_anlegen ins System uebernehmen falls noch nicht vorhanden",
    },
    "projektliste": {
        "beschreibung": "Liste eigener Projekte (Freelance-typisch)",
        "claude_action": "Projekte ins Profil aufnehmen, Verknuepfung mit Positionen pruefen",
    },
    "portfolio": {
        "beschreibung": "Eigene Arbeitsproben/Mappe",
        "claude_action": "Als Anhang fuer kuenftige Bewerbungen verknuepfen",
    },
    "referenz": {
        "beschreibung": "Referenzschreiben, Empfehlungen, interne Reference-Files",
        "claude_action": "Inhalt fuer Bewerbungs-Argumentation merken",
    },
    "vorlage": {
        "beschreibung": "CV-/Anschreiben-Vorlage (nicht firmenspezifisch)",
        "claude_action": "Als Basis fuer kuenftige Bewerbungen behalten",
    },
    "vorbereitung": {
        "beschreibung": "Interview-Vorbereitung, Spickzettel, Antworten-Sammlung",
        "claude_action": "Mit Stilarchiv/interview_reflexion verknuepfen",
    },
    "interview_transkript": {
        "beschreibung": "Wortprotokoll/Mitschrift eines Interviews",
        "claude_action": "interview_reflexion_speichern fuer strukturierte Auswertung",
    },
    "interview_einladung": {
        "beschreibung": "Initiale Termin-Anfrage fuer ein Vorstellungsgespraech",
        "claude_action": "Status auf 'interview' aendern + Termin im Kalender anlegen",
    },
    "interview_bestaetigung": {
        "beschreibung": "Bestaetigung eines bereits angefragten Termins (#655)",
        "claude_action": "Termin im Kalender bestaetigen + bewerbung_notiz mit Eckdaten",
    },
    "projekt_update": {
        "beschreibung": "Zwischenfeedback/Status-Update vom Recruiter (#655)",
        "claude_action": "bewerbung_notiz mit dem Update-Inhalt + ggf. nachfass_planen",
    },
    "gespraechs_feedback": {
        "beschreibung": "Persoenliche Rueckmeldung nach einem Gespraech (#655)",
        "claude_action": "bewerbung_notiz mit Feedback + interview_reflexion_speichern",
    },
    "vermittler_korrespondenz": {
        "beschreibung": "Allgemeine Recruiter-Korrespondenz die nichts Neues fragt (#655)",
        "claude_action": "bewerbung_notiz, sonst archivieren",
    },
    "eingangsbestaetigung": {
        "beschreibung": "Bestaetigungs-Mail nach eingereichter Bewerbung",
        "claude_action": "Status auf 'eingangsbestaetigung' aendern",
    },
    "absage": {
        "beschreibung": "Ablehnung der Bewerbung",
        "claude_action": "Status auf 'abgelehnt' + ggf. ablehnungs_muster anwenden",
    },
    "angebot": {
        "beschreibung": "Vertrags-/Projekt-Angebot",
        "claude_action": "Status auf 'angebot' + bewerbung_notiz mit Konditionen",
    },
    "recruiter_anfrage": {
        "beschreibung": "Inbound-Mail von Headhuntern/Recruitern mit Stelle/Projekt",
        "claude_action": "recruiter_anfrage_ablehnen ODER stelle_manuell_anlegen + bewerbung_erstellen",
    },
    "sonstiges": {
        "beschreibung": "Nicht klassifiziertes Dokument",
        "claude_action": "Manuell sichten oder doc_type via update_document_type setzen",
    },
}


# ── Per-Typ-Extraktoren ─────────────────────────────────────────────


_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_DATE_RE = re.compile(
    r"\b(\d{1,2}\.\d{1,2}\.\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|"
    r"\d{1,2}\s+(?:Jan|Feb|M[aä]r|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)[a-z]*\s+\d{2,4})\b",
    re.I,
)
_PHONE_RE = re.compile(r"\+?\d{1,3}[\s\-]?\(?\d{2,5}\)?[\s\-/]?\d{3,}[\s\-]?\d{2,}")
# Zeit-Regex strikt: ":" als Trenner (nicht "."), sonst kollidiert mit
# Datums-Pattern "19.05.2026" → "19.05" als Zeit. Alternativ matched
# auch "1300 Uhr" wenn explizit "Uhr" / "am" / "pm" / Zeitzone folgt.
_TIME_RE = re.compile(
    r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:Uhr|am|pm|CE[ST]|CET)?\b"
    r"|\b\d{4}\s*(?:Uhr|am|pm|CE[ST]|CET)\b",
    re.I,
)
_PLATFORM_RE = re.compile(
    r"\b(?:Zoom|Microsoft\s+Teams|MS\s+Teams|Teams|Google\s+Meet|"
    r"Webex|Skype|Hangouts|GoToMeeting|BigBlueButton)\b",
    re.I,
)


def _extract_recruiter_anfrage(doc: dict) -> dict:
    text = (doc.get("extracted_text") or "")[:5000]
    emails = _EMAIL_RE.findall(text)
    phones = _PHONE_RE.findall(text)
    return {
        "kontakt_emails": list(dict.fromkeys(emails))[:3],
        "kontakt_telefon": phones[0] if phones else None,
        "hat_link": bool(re.search(r"https?://", text)),
    }


def _extract_interview_einladung(doc: dict) -> dict:
    text = (doc.get("extracted_text") or "")[:5000]
    dates = _DATE_RE.findall(text)
    times = _TIME_RE.findall(text)
    platforms = _PLATFORM_RE.findall(text)
    return {
        "moegliches_datum": dates[0] if dates else None,
        "moegliche_uhrzeit": times[0] if times else None,
        "platform": platforms[0] if platforms else None,
    }


def _extract_interview_bestaetigung(doc: dict) -> dict:
    # Gleiche Felder wie Einladung — verschiedene `claude_action`
    return _extract_interview_einladung(doc)


def _extract_projekt_update(doc: dict) -> dict:
    text = (doc.get("extracted_text") or "")[:5000]
    # Heuristik: kurze Updates haben oft "Stand:", "Status:", "Hinweis:"
    status_hint = ""
    for marker in ("Status:", "Stand:", "Hinweis:", "Zwischenstand:"):
        idx = text.find(marker)
        if idx >= 0:
            # Naechsten Satz nach dem Marker (bis Punkt/Newline)
            chunk = text[idx + len(marker): idx + len(marker) + 200]
            status_hint = chunk.split("\n", 1)[0].strip()
            break
    return {
        "status_hinweis": status_hint or None,
        "naechster_kontakt": (
            "kw" in text.lower()
            or "naechste woche" in text.lower()
            or "next week" in text.lower()
        ),
    }


def _extract_gespraechs_feedback(doc: dict) -> dict:
    text = (doc.get("extracted_text") or "")[:5000]
    text_l = text.lower()
    positives = sum(
        1 for w in (
            "passt", "gut", "positiv", "begeistert",
            "interessant", "passt sehr gut", "passt gut",
            "good fit", "looking forward", "next round",
        )
        if w in text_l
    )
    negatives = sum(
        1 for w in (
            "leider", "abschliessend", "nicht passend",
            "anders entschieden", "anderen kandidaten",
            "unfortunately", "another candidate",
        )
        if w in text_l
    )
    if positives > negatives:
        signal = "positiv"
    elif negatives > positives:
        signal = "negativ"
    else:
        signal = "neutral"
    return {
        "tendenz": signal,
        "positiv_marker": positives,
        "negativ_marker": negatives,
    }


def _extract_absage(doc: dict) -> dict:
    text_l = (doc.get("extracted_text") or "").lower()[:5000]
    return {
        "begruendung_enthalten": any(
            kw in text_l
            for kw in (
                "begruendung", "begründung", "leider entschieden",
                "andere kandidaten",
            )
        ),
        "feedback_einholbar": "rueckmeldung" in text_l or "feedback" in text_l,
    }


def _extract_eingangsbestaetigung(doc: dict) -> dict:
    return {"keine_aktion_noetig": True}


def _extract_default(doc: dict) -> dict:
    return {}


# Mapping `doc_type` -> Extraktor
EXTRACTORS: dict[str, Callable[[dict], dict]] = {
    "recruiter_anfrage": _extract_recruiter_anfrage,
    "interview_einladung": _extract_interview_einladung,
    "interview_bestaetigung": _extract_interview_bestaetigung,
    "projekt_update": _extract_projekt_update,
    "gespraechs_feedback": _extract_gespraechs_feedback,
    "absage": _extract_absage,
    "eingangsbestaetigung": _extract_eingangsbestaetigung,
}


# ── Public API ──────────────────────────────────────────────────────


def handle_doc(doc: dict) -> dict:
    """Liefert structured info fuer ein Doku.

    Args:
        doc: Dict mit mind. `doc_type`, `extracted_text`. `filename`/`id`
            optional.

    Returns:
        {typ, beschreibung, claude_action, fields}
    """
    doc_type = doc.get("doc_type") or "sonstiges"
    type_info = KNOWN_TYPES.get(doc_type, KNOWN_TYPES["sonstiges"])
    extractor = EXTRACTORS.get(doc_type, _extract_default)
    try:
        fields = extractor(doc)
    except Exception:
        fields = {}
    return {
        "typ": doc_type,
        "beschreibung": type_info["beschreibung"],
        "claude_action": type_info["claude_action"],
        "fields": fields,
    }


def list_known_types() -> list[dict]:
    """Listet alle bekannten Doku-Typen + Beschreibung + Action.

    Frontend/Claude-Discovery: zeigt was PBP fuer welchen Typ kann.
    """
    return [
        {
            "typ": typ,
            "beschreibung": info["beschreibung"],
            "claude_action": info["claude_action"],
            "hat_extraktor": typ in EXTRACTORS,
        }
        for typ, info in KNOWN_TYPES.items()
    ]
