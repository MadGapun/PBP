"""Was an einem Termin hängt, zieht mit (#1123).

Der Fall (29.09.2026): Der Arbeitgeber verschob ein Interview vom 30.09.
auf den 07.10. Der Termin wurde in PBP richtig geändert. Zwei Dinge
blieben stehen: die Vorbereitungs-Aufgabe („… am 30.09., 11:00 Uhr“,
fällig 28.09.) stand als „überfällig seit 1 Tagen“, obwohl noch eine
Woche Zeit war, und eine Routine-Nachfassung blieb offen. Der Nutzer:
„Warum wurden die Aufgaben nicht nachgezogen? Ich denke, das muss auch
immer mitgenommen werden.“

`meeting_bearbeiten` schrieb nur `application_meetings`. Das Dashboard
rief dieselbe Datenbankfunktion auf und war genauso blind. Deshalb steht
die Regel hier, an EINER Stelle, und beide Wege rufen sie (D35-Muster:
ein Kommentar „dieselbe Logik wie“ hält nichts zusammen).

Regeln
------

* **Verschoben:** Gibt es genau EINE offene Vorbereitungs-Aufgabe zu
  dieser Bewerbung, wandert ihre Fälligkeit um dieselbe Zahl Tage mit.
  Titel und Beschreibung werden NICHT umgeschrieben (Freitext, teils vom
  Nutzer ergänzt); stattdessen kommt eine Zeile „Termin verschoben von …
  auf …“ an die Beschreibung, und die Antwort sagt, ob der Titel noch das
  alte Datum nennt. Bei mehreren Aufgaben wird nicht geraten: die Antwort
  nennt sie unter `vorbereitung_pruefen`.
* **Abgesagt oder gelöscht:** Die Vorbereitung wird zum Hinfälligsetzen
  VORGESCHLAGEN, nicht stillschweigend geändert.
* **Bestätigt oder verschoben:** Der Arbeitgeber hat geantwortet — offene
  Nachfrage-Erinnerungen erledigen sich (`nachfass_abgleich`).
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from . import nachfass_abgleich

logger = logging.getLogger(__name__)


def _termin(db, meeting_id: str) -> dict | None:
    zeile = db.connect().execute(
        "SELECT * FROM application_meetings WHERE id=?", (meeting_id,)).fetchone()
    return dict(zeile) if zeile else None


def _tag(wert: str) -> date | None:
    try:
        return date.fromisoformat(str(wert or "")[:10])
    except ValueError:
        return None


def _lesbar(wert: str) -> str:
    """`2026-09-30T11:00:00` -> `30.09.2026 11:00` (ohne Uhrzeit: nur das Datum)."""
    roh = str(wert or "")
    tag = _tag(roh)
    if not tag:
        return roh
    text = tag.strftime("%d.%m.%Y")
    zeit = roh[11:16]
    return f"{text} {zeit}" if zeit and zeit != "00:00" else text


def offene_vorbereitungen(db, app_id: str) -> list[dict]:
    """Offene Vorbereitungs-Aufgaben einer Bewerbung."""
    if not app_id:
        return []
    return [t for t in db.list_tasks(application_id=app_id, nur_offen=True)
            if (t.get("typ") or "") == "vorbereitung"]


def _pruefliste(todos: list[dict], grund: str) -> dict:
    return {
        "vorbereitung_pruefen": [
            {"todo_id": t["id"], "titel": t.get("titel", ""),
             "faellig_am": (t.get("faellig_am") or "")[:10],
             "hinfaellig_mit": f"todo_hinfaellig('{t['id']}')"}
            for t in todos],
        "vorbereitung_hinweis": grund,
    }


def _vorbereitung_nachziehen(db, app_id: str, alt: str, neu: str) -> dict:
    alt_tag, neu_tag = _tag(alt), _tag(neu)
    if not (alt_tag and neu_tag) or alt_tag == neu_tag:
        return {}      # nur die Uhrzeit: die Fälligkeit ist ein Tag
    todos = offene_vorbereitungen(db, app_id)
    if not todos:
        return {}
    if len(todos) > 1:
        return _pruefliste(
            todos, "Der Termin wurde verschoben, es gibt mehrere offene "
                   "Vorbereitungs-Aufgaben dazu. Bitte prüfen, welche noch "
                   "zum neuen Termin passt.")
    todo = todos[0]
    verschiebung = (neu_tag - alt_tag).days
    faellig_alt = _tag(todo.get("faellig_am"))
    zeile = f"Termin verschoben von {_lesbar(alt)} auf {_lesbar(neu)}."
    beschreibung = ((todo.get("beschreibung") or "").rstrip() + "\n" + zeile).strip()
    aenderung = {"beschreibung": beschreibung}
    faellig_neu = None
    if faellig_alt:
        # Derselbe Abstand zum Termin — aber nie in der Vergangenheit (das
        # wäre sofort „überfällig“, ohne dass jemand etwas versäumt hat)
        # und nie nach dem neuen Termin.
        faellig_neu = min(max(faellig_alt + timedelta(days=verschiebung),
                              date.today()), neu_tag)
        aenderung["faellig_am"] = faellig_neu.isoformat()
    db.update_task(todo["id"], aenderung)
    titel = todo.get("titel") or ""
    return {"vorbereitung_angepasst": {
        "todo_id": todo["id"],
        "faellig_alt": faellig_alt.isoformat() if faellig_alt else "",
        "faellig_neu": faellig_neu.isoformat() if faellig_neu else "",
        "titel_nennt_altes_datum": alt_tag.strftime("%d.%m.") in titel,
        "hinweis": ("Fälligkeit zieht mit. Titel und Beschreibung wurden "
                    "nicht umgeschrieben; die Beschreibung trägt eine Zeile "
                    "zur Verschiebung."),
    }}


_DATUM_IM_TEXT = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})?")


def _daten_im_text(text: str) -> set[tuple[int, int]]:
    """(Tag, Monat) jedes Datums im Text; das Jahr zählt nicht."""
    gefunden = set()
    for m in _DATUM_IM_TEXT.finditer(text or ""):
        tag, monat = int(m.group(1)), int(m.group(2))
        if 1 <= tag <= 31 and 1 <= monat <= 12:
            gefunden.add((tag, monat))
    return gefunden


def abweichende_vorbereitungen(db) -> list[dict]:
    """Vorbereitungs-Aufgaben, deren Text ein Datum nennt, das nicht mehr
    zu einem Termin der Bewerbung passt (#1123). Nur Befund, schreibt nichts.

    Gelesen werden der Titel und die Zeile „Termin: …“ der Beschreibung —
    nicht der ganze Text: eine Beschreibung nennt auch das Bewerbungsdatum
    oder ein Datum aus einer Mail, und das wäre ein Fehlalarm. Die
    Verschiebungszeile („Termin verschoben von … auf …“) trägt bewusst
    beide Daten und zählt nicht.

    Ohne kommenden Termin gibt es nichts zu vergleichen.
    """
    befunde = []
    heute = date.today()
    for t in db.list_tasks(nur_offen=True):
        if (t.get("typ") or "") != "vorbereitung" or not t.get("application_id"):
            continue
        termine = [
            m for m in db.get_meetings_for_application(t["application_id"])
            if (m.get("status") or "") != "abgesagt"
            and (_tag(m.get("meeting_date")) or date.min) >= heute]
        if not termine:
            continue
        gueltig = {(d.day, d.month) for m in termine
                   if (d := _tag(m.get("meeting_date")))}
        zeilen = [t.get("titel") or ""]
        zeilen += [z for z in (t.get("beschreibung") or "").splitlines()
                   if z.strip().lower().startswith("termin:")]
        genannt = set().union(*(_daten_im_text(z) for z in zeilen))
        fremd = sorted(genannt - gueltig)
        if fremd:
            befunde.append({
                "todo_id": t["id"],
                "titel": t.get("titel") or "",
                "genannt": [f"{tag:02d}.{monat:02d}." for tag, monat in fremd],
                "termine": sorted(
                    {_lesbar(m.get("meeting_date")) for m in termine}),
            })
    return befunde


def folgen(db, vorher: dict | None, nachher: dict | None) -> dict:
    """Die Folgen einer Termin-Änderung für Aufgaben und Nachfassungen."""
    if not vorher or not nachher:
        return {}
    app_id = nachher.get("application_id") or ""
    if not app_id:
        return {}
    ergebnis: dict = {}
    abgesagt = ((nachher.get("status") or "") == "abgesagt"
                and (vorher.get("status") or "") != "abgesagt")
    verschoben = (str(vorher.get("meeting_date") or "")
                  != str(nachher.get("meeting_date") or ""))
    if abgesagt:
        todos = offene_vorbereitungen(db, app_id)
        if todos:
            ergebnis.update(_pruefliste(
                todos, "Der Termin wurde abgesagt. Die Vorbereitung ist "
                       "womöglich hinfällig — nicht stillschweigend geändert."))
    elif verschoben:
        ergebnis.update(_vorbereitung_nachziehen(
            db, app_id, vorher.get("meeting_date"), nachher.get("meeting_date")))
    bestaetigt = ((nachher.get("status") or "") == "bestaetigt"
                  and (vorher.get("status") or "") != "bestaetigt")
    if (verschoben or bestaetigt) and not abgesagt:
        erledigt = nachfass_abgleich.kontakt_gemeldet(
            db, app_id, "Termin vereinbart oder verschoben")
        if erledigt:
            ergebnis["nachfassung_erledigt"] = erledigt
    return ergebnis


def aendern(db, meeting_id: str, updates: dict,
            profile_id: str | None = None) -> dict:
    """Ändert einen Termin samt Folgen. `{"geaendert": False}` bei Misserfolg.

    Wirft wie `update_meeting` ein `ValueError` bei unlesbarer Zeit.
    """
    vorher = _termin(db, meeting_id)
    if not db.update_meeting(meeting_id, updates, profile_id=profile_id):
        return {"geaendert": False}
    try:
        return {"geaendert": True, **folgen(db, vorher, _termin(db, meeting_id))}
    except Exception as exc:  # noqa: BLE001 — die Änderung selbst steht
        logger.warning("Termin-Folgen (#1123) nicht durchgezogen: %s", exc)
        return {"geaendert": True}


def loeschen(db, meeting_id: str, profile_id: str | None = None) -> dict:
    """Löscht einen Termin; die Antwort nennt die Vorbereitung, die nun
    womöglich hinfällig ist."""
    termin = _termin(db, meeting_id)
    if not db.delete_meeting(meeting_id, profile_id=profile_id):
        return {"geloescht": False}
    ergebnis: dict = {"geloescht": True}
    try:
        todos = offene_vorbereitungen(db, (termin or {}).get("application_id") or "")
        if todos:
            ergebnis.update(_pruefliste(
                todos, "Der Termin wurde gelöscht. Die Vorbereitung ist "
                       "womöglich hinfällig — nicht stillschweigend geändert."))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Termin-Folgen beim Löschen (#1123): %s", exc)
    return ergebnis
