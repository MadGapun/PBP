"""Dieselbe Sache zweimal anlegen? (#1148 Punkt 8)

`position_hinzufuegen`, `ausbildung_hinzufuegen`, `projekt_hinzufuegen`,
`todo_anlegen`, `kontakt_anlegen` und `kosten_erfassen` legten bei JEDEM Aufruf
neu an. Wiederholt ein Client einen Aufruf (nach einer Zeitüberschreitung,
nach einer unklaren Antwort), steht danach alles doppelt im Profil — und
niemand merkt es, weil beide Zeilen für sich stimmen.

Dieses Modul sagt nur, OB es die Sache schon gibt, und liefert deren ID. Die
Werkzeuge antworten dann mit `bereits_vorhanden` statt zu verdoppeln.

Abgrenzung (DoD 8d): nicht zu verwechseln mit
- `termin_dubletten` (Termine, #804, gleiche Termine finden und bereinigen),
- `stellen_dublette` (Stellen, #317/#670, Wiederholungs-Stellen).
Dies hier ist der Schutz am Schreibweg für Profil-Elemente, Aufgaben, Kontakte
und Kosten.

Die Regeln sind bewusst eng: gleich ist, was in den Angaben übereinstimmt, die
einen Eintrag ausmachen. Ein anderer Titel, eine andere Firma, ein anderes
Datum macht daraus eine neue Sache.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _n(wert) -> str:
    """Vergleichsform: kleingeschrieben, Leerraum zusammengezogen."""
    return " ".join(str(wert or "").casefold().split())


def _monat(wert) -> str:
    """'2020-03', '2020-03-01' und '2020-03-15' sind derselbe Monat."""
    return _n(wert)[:7]


def _jahr(wert) -> str:
    return _n(wert)[:4]


def position(db, company, title, start_date) -> str | None:
    """ID einer Position mit gleicher Firma, gleichem Titel und gleichem Beginn."""
    for p in (db.get_profile() or {}).get("positions", []):
        if (_n(p.get("company")) == _n(company)
                and _n(p.get("title")) == _n(title)
                and _monat(p.get("start_date")) == _monat(start_date)):
            return p.get("id")
    return None


def ausbildung(db, institution, degree, field_of_study, start_date) -> str | None:
    """ID einer Ausbildung mit gleicher Einrichtung, gleichem Abschluss und
    gleicher Fachrichtung (Beginn: dasselbe Jahr, wenn beide eines nennen)."""
    for e in (db.get_profile() or {}).get("education", []):
        if (_n(e.get("institution")) == _n(institution)
                and _n(e.get("degree")) == _n(degree)
                and _n(e.get("field_of_study")) == _n(field_of_study)):
            a, b = _jahr(e.get("start_date")), _jahr(start_date)
            if not a or not b or a == b:
                return e.get("id")
    return None


def projekt(db, position_id, name) -> str | None:
    """ID eines Projekts gleichen Namens in DERSELBEN Position."""
    for p in (db.get_profile() or {}).get("positions", []):
        if p.get("id") != position_id:
            continue
        for pr in (p.get("projects") or []):
            if _n(pr.get("name")) == _n(name):
                return pr.get("id")
    return None


def todo(db, bewerbung_id, titel, faellig_am) -> str | None:
    """ID einer noch OFFENEN Aufgabe mit gleichem Titel, gleicher Bewerbung und
    gleicher Fälligkeit. Eine erledigte zählt nicht: dieselbe Aufgabe darf
    wiederkehren."""
    ziel = bewerbung_id or None
    for t in db.list_tasks(nur_offen=True):
        if ((t.get("application_id") or None) == ziel
                and _n(t.get("titel")) == _n(titel)
                and (t.get("faellig_am") or None) == (faellig_am or None)):
            return t.get("id")
    return None


def kontakt(db, name, email, firma) -> str | None:
    """ID eines Kontakts mit gleichem Namen, der nicht erkennbar ein anderer ist.

    Gleich, wenn der Name übereinstimmt UND (die E-Mail übereinstimmt ODER die
    Firma übereinstimmt ODER beide Seiten weder E-Mail noch Firma nennen).
    Zwei Menschen gleichen Namens bei verschiedenen Firmen sind zwei Kontakte.
    """
    for c in db.list_contacts(search=str(name or "").strip(), mit_vorschlaegen=True):
        if _n(c.get("full_name")) != _n(name):
            continue
        mail_a, mail_b = _n(c.get("email")), _n(email)
        firma_a, firma_b = _n(c.get("company")), _n(firma)
        if mail_a and mail_b:
            if mail_a == mail_b:
                return c.get("id")
            continue
        if firma_a and firma_b:
            if firma_a == firma_b:
                return c.get("id")
            continue
        if not (mail_a or firma_a or mail_b or firma_b):
            return c.get("id")
        # Eine Seite nennt Firma oder E-Mail, die andere nicht: nicht sicher
        # dieselbe Person — dann wird angelegt (und der Mensch kann mergen).
    return None


#: Ein Aufruf, der sich in dieser Zeit mit gleichen Angaben wiederholt, gilt als
#: Wiederholung. Danach ist es eine neue Zahlung (zwei gleiche Fahrkarten an
#: einem Tag sind möglich).
KOSTEN_FENSTER_MIN = 10


def kosten_wiederholung(db, bewerbung_id, kategorie, betrag, beschreibung,
                        datum, jetzt: datetime | None = None) -> str | None:
    """ID einer Kostenposition mit gleichen Angaben, die eben erst angelegt wurde."""
    jetzt = jetzt or datetime.now(timezone.utc)
    grenze = jetzt - timedelta(minutes=KOSTEN_FENSTER_MIN)
    for k in db.list_application_costs(application_id=bewerbung_id or None, kind=kategorie):
        if (bewerbung_id or None) != (k.get("application_id") or None):
            continue
        if (round(float(k.get("amount") or 0), 2) != round(float(betrag or 0), 2)
                or _n(k.get("description")) != _n(beschreibung)
                or _n(k.get("incurred_at"))[:10] != _n(datum)[:10]):
            continue
        try:
            angelegt = datetime.fromisoformat(str(k.get("created_at")).replace("Z", "+00:00"))
            if angelegt.tzinfo is None:
                angelegt = angelegt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if angelegt >= grenze:
            return k.get("id")
    return None


def antwort(bereich: str, vorhandene_id: str, was: str, aendern: str = "") -> dict:
    """Die Antwort der Werkzeuge: nichts angelegt, und wo das Vorhandene steht."""
    out = {
        "status": "bereits_vorhanden",
        "bereich": bereich,
        "id": vorhandene_id,
        "hinweis": (f"{was} gibt es schon (ID {vorhandene_id}) — es wurde nichts "
                    "angelegt." + (f" {aendern}" if aendern else "")),
    }
    return out
