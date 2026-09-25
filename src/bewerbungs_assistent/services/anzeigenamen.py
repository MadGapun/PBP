"""Anzeigenamen statt Rohwerte — G65 (#1087 D2).

Gespeichert wird ein Schluessel (`mit_dokumenten`, `zu_junior`,
`jobspy_indeed`), gezeigt werden soll ein Wort. Bis v1.7.133 stand der
Schluessel an mehreren Stellen im Klartext: im Nachfass-Text
("Beworben per: mit_dokumenten — Stand: beworben"), auf Diagrammachsen
und in der Gruendeliste der Einstellungen.

Die GESPEICHERTEN Werte bleiben unveraendert — das hier ist nur die
Beschriftung. Das Gegenstueck im Browser ist `frontend/src/lib/anzeige.js`;
ein Test haelt beide Tabellen gleich.

Abgrenzung: `services/anzeigenalter.py` rechnet das ALTER einer Anzeige
(#949) und hat mit diesem Modul nichts zu tun.
"""
from __future__ import annotations

import re

STATUS_TEXT = {
    "in_vorbereitung": "In Vorbereitung",
    "offen": "Offen",
    "beworben": "Beworben",
    "eingangsbestaetigung": "Eingangsbestätigung",
    "in_pruefung": "In Prüfung",
    "interview": "Interview",
    "interview_abgeschlossen": "Interview abgeschlossen",
    "zweitgespraech": "Zweitgespräch",
    "zweitgespraech_abgeschlossen": "Zweitgespräch abgeschlossen",
    "angebot": "Angebot",
    "zugesagt": "Zugesagt",
    "angenommen": "Angenommen",
    "abgelehnt": "Abgelehnt",
    "zurueckgezogen": "Zurückgezogen",
    "abgelaufen": "Abgelaufen",
    "arbeitgeber_ausgefallen": "Arbeitgeber ausgefallen",
}

GRUND_TEXT = {
    "zu_weit_entfernt": "Zu weit entfernt",
    "gehalt_zu_niedrig": "Gehalt zu niedrig",
    "falsches_fachgebiet": "Falsches Fachgebiet",
    "falsche_branche": "Falsche Branche",
    "falsches_system": "Falsches System",
    "zu_junior": "Zu junior",
    "zu_senior": "Zu senior",
    "unpassendes_arbeitsmodell": "Unpassendes Arbeitsmodell",
    "firma_uninteressant": "Firma uninteressant",
    "zeitarbeit": "Zeitarbeit",
    "befristet": "Befristet",
    "bereits_beworben": "Bereits beworben",
    "duplikat": "Duplikat",
    "kein_hochschulabschluss": "Kein Hochschulabschluss",
    "sonstiges": "Sonstiges",
}

BEWERBUNGSART_TEXT = {
    "mit_dokumenten": "mit Unterlagen",
    "elektronisch": "per E-Mail",
    "ueber_portal": "über ein Portal",
}


def _schluessel(wert) -> str:
    return re.sub(r"[\s_]+", "_", str(wert or "").strip().lower())


def status_text(wert) -> str:
    roh = str(wert or "").strip()
    return STATUS_TEXT.get(_schluessel(roh), roh.replace("_", " "))


def grund_text(wert, katalog=()) -> str:
    """Ein Ablehnungsgrund als Wort.

    `katalog` sind die Beschriftungen aus `dismiss_reasons` — ein eigener
    Grund steht dort so, wie der Mensch ihn geschrieben hat ("Falsches
    System"), gespeichert ist er klein ("falsches system").
    """
    roh = str(wert or "").strip()
    schluessel = _schluessel(roh)
    if schluessel in GRUND_TEXT:
        return GRUND_TEXT[schluessel]
    for label in katalog or ():
        if _schluessel(label) == schluessel and label != label.lower():
            return str(label)
    text = roh.replace("_", " ")
    return text[:1].upper() + text[1:]


def bewerbungsart_text(wert) -> str:
    roh = str(wert or "").strip()
    return BEWERBUNGSART_TEXT.get(_schluessel(roh), roh.replace("_", " "))


def datum_text(wert) -> str:
    """ISO-Datum als TT.MM.JJJJ; alles andere unveraendert."""
    roh = str(wert or "")[:10]
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", roh)
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else roh


def quelle_text(schluessel) -> str:
    """Der Name einer Quelle aus der Registry, sonst der Schluessel."""
    roh = str(schluessel or "").strip()
    try:
        from ..job_scraper import SOURCE_REGISTRY
        eintrag = SOURCE_REGISTRY.get(roh)
        if eintrag and eintrag.get("name"):
            return str(eintrag["name"])
    except Exception:
        pass
    return roh or "unbekannt"
