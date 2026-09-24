"""Den Text eines Dokuments lesen — ueber PBP, nicht ueber SQL (#1083).

Gemeldet am 24.09.2026: um eine an eine Bewerbung verknuepfte Absagemail
zu lesen, gab es keinen MCP-Weg. `bewerbung_details` nannte Dateiname,
Typ und Status, `dokument_text_setzen` schreibt nur. Claude las deshalb
lesend per SQL — gegen die MCP-first-Regel (#514), und fuer andere
Nutzer nicht nachvollziehbar.

Die Folge im Praxisfall wiegt schwerer als der Umweg: der Absagegrund
einer frueheren Bewerbung stand seit Monaten in PBP und wurde nie
ausgewertet. Eine Neuausschreibung derselben Rolle galt zunaechst als
"zweite Chance"; mit dem Grund gelesen lautete das Urteil anders.

**Paginiert wie die Fit-Analyse.** Eine Mail samt Verlauf kann lang
sein; der Aufruf liefert eine Seite und sagt, wo die naechste beginnt.
Gekappt wird nie still (#1064).
"""
from __future__ import annotations

import re

#: Zeichen je Seite — dieselbe Groessenordnung wie die Ausgabe der
#: Fit-Analyse (#1064): lang genug fuer jede Absage, kurz genug fuer
#: einen Werkzeugaufruf.
SEITE = 8000

#: Dokumenttypen, deren Anfang `bewerbung_details` mitliefert.
KORRESPONDENZ_MIT_TEXT = frozenset({
    "absage", "recruiter_anfrage", "vermittler_korrespondenz",
    "gespraechs_feedback", "email",
})

_ABSAGE_SIGNAL = re.compile(
    r"leider|entschieden|absage|nicht\s+(?:weiter\s+)?ber(?:ue|ü)cksichtig|"
    r"anderen?\s+(?:kandidat|bewerber)|nicht\s+in\s+die\s+engere|"
    r"passt\s+nicht|nicht\s+passend|unfortunately|decided|other\s+candidate",
    re.IGNORECASE)


def seite(text: str, ab_zeichen: int = 0, laenge: int = SEITE) -> dict:
    """Eine Seite eines Textes samt Angabe, ob und wo es weitergeht."""
    text = text or ""
    try:
        ab = max(0, int(ab_zeichen or 0))
    except (TypeError, ValueError):
        ab = 0
    stueck = text[ab:ab + laenge]
    ende = ab + len(stueck)
    befund = {
        "text": stueck,
        "ab_zeichen": ab,
        "bis_zeichen": ende,
        "gesamt_zeichen": len(text),
        "vollstaendig": ab == 0 and ende >= len(text),
    }
    if ende < len(text):
        befund["weiter_ab_zeichen"] = ende
    return befund


def anfang(text: str, zeilen: int = 6, zeichen: int = 400) -> str:
    """Die ersten nicht-leeren Zeilen — fuer eine Vorschau."""
    teile = [z.strip() for z in (text or "").splitlines() if z.strip()]
    auszug = "\n".join(teile[:zeilen])
    return auszug[:zeichen] + (" …" if len(auszug) > zeichen else "")


def ablehnungs_auszug(text: str, zeichen: int = 400) -> str:
    """Die Saetze, in denen eine Absage ihren Grund nennt.

    Kein Sprachmodell, keine Deutung: die Saetze mit einem Absage-Signal,
    in Reihenfolge. Findet sich keines, der Anfang des Textes — eine
    Zusammenfassung, die nichts findet, darf nicht leer aussehen.
    """
    saetze = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    treffer = [s.strip() for s in saetze if s.strip() and _ABSAGE_SIGNAL.search(s)]
    auszug = " ".join(treffer) if treffer else anfang(text, zeilen=4, zeichen=zeichen)
    auszug = re.sub(r"\s+", " ", auszug).strip()
    return auszug[:zeichen] + (" …" if len(auszug) > zeichen else "")


def ablehnungsgrund(db, bewerbung_id: str) -> dict | None:
    """Der dokumentierte Grund einer Absage — aus der Bewerbung oder der Mail.

    Erst das Feld der Bewerbung (von Hand gepflegt), dann das juengste
    verknuepfte Absage-Dokument mit Text.
    """
    if not bewerbung_id:
        return None
    conn = db.connect()
    app = conn.execute(
        "SELECT rejection_reason FROM applications WHERE id=?",
        (bewerbung_id,)).fetchone()
    if app and (app["rejection_reason"] or "").strip():
        return {"quelle": "bewerbung", "text": app["rejection_reason"].strip()[:400]}
    zeile = conn.execute(
        "SELECT id, filename, doc_type, extracted_text FROM documents "
        "WHERE linked_application_id=? AND doc_type IN "
        f"({','.join('?' * len(KORRESPONDENZ_MIT_TEXT))}) "
        "AND extracted_text IS NOT NULL AND TRIM(extracted_text) != '' "
        "ORDER BY CASE WHEN doc_type='absage' THEN 0 ELSE 1 END, "
        "created_at DESC LIMIT 1",
        (bewerbung_id, *sorted(KORRESPONDENZ_MIT_TEXT))).fetchone()
    if not zeile:
        return None
    return {"quelle": "dokument", "dokument_id": zeile["id"],
            "dateiname": zeile["filename"],
            "text": ablehnungs_auszug(zeile["extracted_text"])}
