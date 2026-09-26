"""Wohin gehoert eine Notiz — ins Profil oder an eine Bewerbung? (#1056, D47)

## Der Befund

Die informellen Profilnotizen sollen beschreiben, wer der Mensch ist:
Arbeitsweise, Kommunikationsmuster, Coaching-Hinweise. Am 17.09.2026
enthielten sie in einem Bestand 27 Sektionen mit rund 40.000 Zeichen —
davon drei Sektionen mit 11.700 Zeichen, die ausschliesslich EINE
Bewerbung betrafen (Analyse eines Erstgespraechs, eine Nachlese, die
Vorbereitung auf ein Zweitgespraech, das nie stattfand). Die Bewerbung
war seit zwei Monaten abgelehnt.

Zwei Folgen ueber die Unordnung hinaus:

1. **Jede Ausgabe, die das Profil liest, bekommt Bewerbungsdetails
   mit** — Anschreiben, Dossiers, die Vorbereitung fuer eine ANDERE
   Firma. Namen, Aussagen des Gespraechspartners, interne Prozessangaben
   in einem Kontext, der an Dritte gehen kann.
2. **Korrekturen kommen nicht dort an, wo die Erstfassung steht.** Die
   Timeline trug eine falsche Sprecherzuordnung; die Korrektur landete
   im Profil, die falsche Fassung blieb stehen. Zwei Orte fuer dieselbe
   Sache heisst: einer ist veraltet, und niemand weiss welcher.

Ursache: die Werkzeuge, die Transkripte auswerten, schreiben ueber
`profil_bearbeiten(bereich='notizen', aktion='anhang')`, ohne zu fragen,
ob das Ergebnis den Menschen beschreibt oder eine Bewerbung.
Nutzeraussage woertlich: *Notizen zu Stellen und Bewerbungen gehoeren
da raus und in die Bewerbungstimeline.*

## Die Regel

**Die Ueberschrift entscheidet, nicht der Text.** Eine Sektion, deren
Ueberschrift GENAU EINE Firma aus den eigenen Bewerbungen nennt, ist
bewerbungsbezogen. Eine Sektion ueber ein Verhaltensmuster, die Firmen
als Beispiele nennt ("Kommunikationsstil, belegt an Gespraechen bei X
und Y"), ist es nicht: dort ist die Firma Beleg, nicht Gegenstand — und
sie nennt typischerweise mehrere. Eine Firma, die nur im Text vorkommt,
loest nichts aus; sonst wuerde jeder Coaching-Hinweis mit einem
Beispiel verschoben.

**Eindeutig oder unsicher.** Nennt die Ueberschrift eine Firma mit genau
einer Bewerbung, ist das Ziel eindeutig. Gibt es mehrere Bewerbungen bei
dieser Firma, wird gefragt, nicht geraten (AK 2).

**Verschieben und Loeschen in einem Zug, nach Bestaetigung.** Erst der
Eintrag an der Bewerbung, dann das Entfernen aus dem Profil; schlaegt
das Erste fehl, bleibt das Zweite aus. Nie eine stille Aenderung.

## Was hier NICHT passiert

Kein Umbau vorhandener Timeline-Eintraege, keine Zusammenfuehrung mit
`interview_reflexion_speichern` (#464) — das ist ein strukturierter
Fragebogen, in den sich Freitext nicht giessen laesst. Die Antwort nennt
ihn als Weg fuer die naechste Reflexion.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

EINDEUTIG = "eindeutig"
UNSICHER = "unsicher"

#: Markiert eine verschobene Sektion in der Timeline — damit die Herkunft
#: lesbar bleibt und ein zweiter Lauf sie nicht noch einmal anlegt.
VERSCHOBEN_MARKE = "[aus Profilnotizen verschoben]"


# ── Sektionen ───────────────────────────────────────────────────────

def sektionen(blob: str) -> list[list]:
    """Zerlegt den Notizblock in `[name, [zeilen]]`, Reihenfolge erhalten.

    Das ist DER Parser fuer `informal_notes` — `profil_bearbeiten`
    (lesen, ersetzen, loeschen) und das Aufraeumen lesen dasselbe
    Format ueber dieselbe Funktion. Zwei Parser fuer ein Format waeren
    #963 in eigener Sache.
    """
    erg: list[list] = []
    cur = None
    for ln in (blob or "").split("\n"):
        st = ln.strip()
        if st.startswith("## "):
            cur = [st[3:].strip(), []]
            erg.append(cur)
        elif cur is not None and st:
            cur[1].append(ln.rstrip())
    return erg


def zusammensetzen(sektionen_liste: list[list]) -> str:
    """Die Umkehrung von `sektionen` — in der Form, die `profil_bearbeiten`
    seit #680 schreibt."""
    return "\n\n".join(
        f"## {n}\n" + "\n".join(zeilen) for n, zeilen in sektionen_liste
    ).strip()


# ── Bewerbungsbezug ─────────────────────────────────────────────────

def _firmen_der_bewerbungen(db) -> dict[str, list[dict]]:
    """Normalisierter Firmenname -> Bewerbungen bei dieser Firma."""
    from .wiedergaenger import normalize_company
    try:
        bewerbungen = db.get_applications() or []
    except Exception as exc:  # pragma: no cover
        logger.debug("Bewerbungen nicht lesbar (#1056): %s", exc)
        return {}
    firmen: dict[str, list[dict]] = {}
    for app in bewerbungen:
        norm = normalize_company(app.get("company"))
        if not norm:
            continue
        firmen.setdefault(norm, []).append({
            "bewerbung_id": app.get("id"),
            "firma": app.get("company"),
            "titel": app.get("title") or app.get("position") or "",
            "status": app.get("status"),
        })
    return firmen


def _enthaelt_firma(text: str, norm: str) -> bool:
    """Steht die (normalisierte) Firma als Wortfolge im Text?

    Verglichen wird nach derselben Normalisierung wie beim Wiedergaenger
    (#671, #1028): Kleinschreibung, Interpunktion raus, Rechtsform raus.
    "Interview bei Musterfirma GmbH" enthaelt "musterfirma".
    """
    from .wiedergaenger import normalize_company
    t = " " + re.sub(r"\s+", " ", re.sub(r"[^a-zäöüß0-9\s]", " ",
                                         str(text or "").lower())) + " "
    return f" {norm} " in t or (
        # Auch der ganze Text kann eine Firma sein ("## Musterfirma").
        normalize_company(text) == norm)


def bewerbungsbezug(db, ueberschrift: str, text: str = "") -> dict | None:
    """Gehoert eine Sektion zu einer Bewerbung — und zu welcher?

    Returns:
        None, wenn kein Bezug; sonst ein dict mit `sicherheit`
        (eindeutig/unsicher), `firma`, `kandidaten` und `grund`.
    """
    firmen = _firmen_der_bewerbungen(db)
    if not firmen:
        return None
    in_ueberschrift = [n for n in firmen if _enthaelt_firma(ueberschrift, n)]
    if len(in_ueberschrift) != 1:
        # Keine Firma: kein Bezug. Zwei und mehr: die Firmen sind Beleg,
        # nicht Gegenstand (AK 5) — das ist die Sektion "belegt an
        # Gespraechen bei X und Y".
        return None
    norm = in_ueberschrift[0]
    kandidaten = firmen[norm]
    return {
        "sicherheit": EINDEUTIG if len(kandidaten) == 1 else UNSICHER,
        "firma": kandidaten[0]["firma"],
        "kandidaten": kandidaten,
        "grund": (f"Die Überschrift nennt '{kandidaten[0]['firma']}' — dazu "
                  f"{'gibt es eine Bewerbung' if len(kandidaten) == 1 else f'gibt es {len(kandidaten)} Bewerbungen'}."),
    }


# ── Aufraeumen im Bestand ───────────────────────────────────────────

def vorschlaege(db) -> list[dict]:
    """Welche Profilsektionen gehoeren an eine Bewerbung (AK 3).

    Schreibt nichts. Je Vorschlag: Sektion, Zeichen, Zielbewerbung(en)
    und ob die Zuordnung eindeutig ist.
    """
    try:
        profil = db.get_profile() or {}
    except Exception:  # pragma: no cover
        return []
    erg = []
    for name, zeilen in sektionen(profil.get("informal_notes") or ""):
        bezug = bewerbungsbezug(db, name, "\n".join(zeilen))
        if not bezug:
            continue
        erg.append({
            "sektion": name,
            "zeichen": len("\n".join(zeilen)),
            "zeilen": len(zeilen),
            "sicherheit": bezug["sicherheit"],
            "firma": bezug["firma"],
            "ziel": bezug["kandidaten"],
            "grund": bezug["grund"],
        })
    return erg


def verschieben(db, sektion: str, bewerbung_id: str) -> dict:
    """Verschiebt EINE Sektion an EINE Bewerbung — nach Bestaetigung (AK 4).

    Reihenfolge ist Inhalt: erst der Eintrag in der Timeline, dann das
    Entfernen aus dem Profil. Schlaegt der Eintrag fehl, bleibt die
    Sektion stehen — verloren geht nichts.
    """
    profil = db.get_profile()
    if not profil:
        return {"fehler": "Kein Profil vorhanden."}
    app = db.get_application(bewerbung_id)
    if not app:
        return {"fehler": f"Bewerbung '{bewerbung_id}' nicht gefunden."}
    alle = sektionen(profil.get("informal_notes") or "")
    ziel = (sektion or "").strip()
    idx = next((i for i, (n, _) in enumerate(alle)
                if n.strip().upper() == ziel.upper()), None)
    if idx is None:
        return {"fehler": f"Sektion '{sektion}' steht nicht in den Profilnotizen.",
                "vorhanden": [n for n, _ in alle]}
    name, zeilen = alle[idx]
    text = "\n".join(zeilen).strip()
    if not text:
        return {"fehler": f"Sektion '{name}' ist leer — nichts zu verschieben."}

    notiz = f"{VERSCHOBEN_MARKE} {name}\n{text}"
    try:
        db.add_application_note(bewerbung_id, notiz)
    except Exception as exc:
        return {"fehler": f"Timeline-Eintrag fehlgeschlagen: {exc}",
                "hinweis": "Die Sektion bleibt im Profil — nichts ist verloren."}

    alle.pop(idx)
    db.save_profile({
        "name": profil.get("name"), "email": profil.get("email"),
        "phone": profil.get("phone"), "address": profil.get("address"),
        "city": profil.get("city"), "plz": profil.get("plz"),
        "country": profil.get("country"), "birthday": profil.get("birthday"),
        "nationality": profil.get("nationality"),
        "summary": profil.get("summary"),
        "informal_notes": zusammensetzen(alle),
        "preferences": profil.get("preferences", {}),
    })
    return {
        "status": "verschoben",
        "sektion": name,
        "zeichen": len(text),
        "bewerbung_id": bewerbung_id,
        "firma": app.get("company"),
        "titel": app.get("title"),
        "naechster_schritt": (
            f"bewerbung_details('{bewerbung_id}') zeigt die Timeline. Für "
            "die nächste Interview-Nachlese: interview_reflexion_speichern "
            "(#464) — strukturiert, an der Bewerbung."),
    }
