"""Von Claude erzeugte Unterlagen als Dokumente der Bewerbung (#1382).

`bewerbung_bearbeiten(cv_path=..., cover_letter_path=...)` schrieb nur zwei
Textfelder an die Bewerbung. Der Dialog (Dokumente) und das ZIP lesen aber
die Tabelle `documents`; die Felder hatten einen Setzer und keinen Leser
(Lehre 4). Hier steht der EINE Weg, der aus einem Pfad ein Dokument der
Bewerbung macht - fuer den Werkzeugaufruf und fuer den Altbestand.

Regeln:
* Nur Dateien, die es gibt; ein Pfad ins Leere wird gemeldet, nicht
  eingetragen (ein Dokument, das sich nicht oeffnen laesst, waere ein
  neuer stiller Fehler).
* Keine Dublette: dieselbe Datei (Pfad, normalisiert) an derselben
  Bewerbung wird nicht ein zweites Mal angelegt.
* Additiv: es wird nie etwas geloescht oder umgehaengt.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Feld an der Bewerbung -> Dokumenttyp
FELDER = (("cv_path", "lebenslauf"), ("cover_letter_path", "anschreiben"))


def _schluessel(pfad: str) -> str:
    return os.path.normcase(os.path.abspath(str(pfad)))


def unterlage_registrieren(db, application_id: str, pfad: str, doc_type: str,
                           profile_id: str | None = None) -> str:
    """Legt die Datei als Dokument der Bewerbung an.

    Rueckgabe: "neu" | "vorhanden" | "nicht_gefunden" | "leer".
    """
    pfad = (pfad or "").strip()
    if not pfad:
        return "leer"
    datei = Path(pfad)
    if not datei.is_file():
        return "nicht_gefunden"
    key = _schluessel(pfad)
    for d in db.get_documents_for_application(str(application_id)):
        if d.get("filepath") and _schluessel(d["filepath"]) == key:
            return "vorhanden"
    daten = {
        "filename": datei.name,
        "filepath": str(datei),
        "doc_type": doc_type,
        "linked_application_id": str(application_id),
    }
    if profile_id:
        daten["profile_id"] = profile_id
    doc_id = db.add_document(daten)
    # Eigene Ausgabe: es gibt nichts auszulesen, sie soll nicht in der
    # Warteschlange "zur Analyse" auftauchen.
    db.update_document_extraction_status(doc_id, "angewendet")
    return "neu"


def felder_registrieren(db, application_id: str, cv_path: str = "",
                        cover_letter_path: str = "",
                        profile_id: str | None = None) -> dict:
    """Wie `unterlage_registrieren`, fuer beide Felder; Antwort je Feld."""
    werte = {"cv_path": cv_path, "cover_letter_path": cover_letter_path}
    erg = {}
    for feld, typ in FELDER:
        if (werte.get(feld) or "").strip():
            erg[feld] = unterlage_registrieren(
                db, application_id, werte[feld], typ, profile_id)
    return erg


def altbestand_nachziehen(db) -> int:
    """Zieht Bewerbungen mit gesetzten Pfaden einmalig nach (additiv).

    Idempotent: ein zweiter Lauf legt nichts mehr an. Gibt die Zahl der
    neu angelegten Dokumente zurueck.
    """
    neu = 0
    conn = db.connect()
    rows = conn.execute(
        "SELECT id, profile_id, cv_path, cover_letter_path FROM applications "
        "WHERE COALESCE(cv_path,'')<>'' OR COALESCE(cover_letter_path,'')<>''"
    ).fetchall()
    for r in rows:
        try:
            erg = felder_registrieren(db, r["id"], r["cv_path"] or "",
                                      r["cover_letter_path"] or "",
                                      r["profile_id"])
        except Exception as e:  # ein kaputter Eintrag stoppt den Rest nicht
            logger.debug("Unterlagen-Nachzug %s: %s", r["id"], e)
            continue
        neu += sum(1 for v in erg.values() if v == "neu")
    if neu:
        logger.info("Safety-Net #1382: %d Unterlage(n) als Dokument "
                    "nachgezogen", neu)
    return neu
