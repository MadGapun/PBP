"""Die Rohdaten-Blaetter der Excel-Datei (#798): Ereignisse, Termine, Kennzahlen.

Die Kennzahlen kommen aus `bericht_daten` und tragen je Zeile ihren Zeitraum
und Bezug. Datumswerte sind echte Datumszellen, Kopfzeile fest, mit Filter.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from . import bericht_daten as _kern
from .anzeigenamen import status_text
from .nachweis_daten import TERMIN_TEXT

_MEETING_STATUS = {
    "geplant": "Geplant", "bestaetigt": "Bestätigt", "durchgefuehrt": "Durchgeführt",
    "abgeschlossen": "Abgeschlossen", "abgesagt": "Abgesagt", "verschoben": "Verschoben",
}
_KENNZAHLEN = (
    ("bewerbungen", "Bewerbungen"), ("laufen", "Laufende Verfahren"),
    ("laufen_aus_frueher", "Davon aus früheren Zeiträumen"), ("mit_gespraech", "Mit Gespräch"),
    ("angebote", "Angebote"), ("absagen", "Absagen"), ("versandet", "Ohne Rückmeldung abgelaufen"),
    ("zurueckgezogen", "Selbst zurückgezogen"), ("nachfassen_faellig", "Nachfassen fällig"),
)
_DAUERN = (
    ("bis_antwort", "Tage bis zur ersten Antwort"), ("bis_gespraech", "Tage bis zum ersten Gespräch"),
    ("bis_absage_ohne_gespraech", "Tage bis zur Absage ohne Gespräch"),
    ("bis_absage_nach_gespraech", "Tage bis zur Absage nach Gespräch"),
)


def _datum(wert) -> Optional[date]:
    try:
        return date.fromisoformat(str(wert or "")[:10])
    except ValueError:
        return None


def _im(tag: Optional[date], von: str, bis: str) -> bool:
    if not (von or bis):
        return True
    if tag is None:
        return False
    t = tag.isoformat()
    return (not von or t >= von[:10]) and (not bis or t <= bis[:10])


def ereignisse(db, von: str = "", bis: str = "") -> list:
    apps = {a["id"]: a for a in db.get_applications()}
    zeilen = []
    for r in db.connect().execute("SELECT application_id, status, event_date FROM application_events "
                                  "ORDER BY event_date").fetchall():
        a = apps.get(r["application_id"])
        tag = _datum(r["event_date"])
        if a and _im(tag, von, bis):
            zeilen.append([tag, a.get("company") or "", a.get("title") or "", status_text(r["status"])])
    return zeilen


def termine(db, von: str = "", bis: str = "") -> list:
    apps = {a["id"]: a for a in db.get_applications()}
    zeilen = []
    for r in db.connect().execute("SELECT application_id, meeting_date, meeting_type, status "
                                  "FROM application_meetings ORDER BY meeting_date").fetchall():
        a = apps.get(r["application_id"])
        tag = _datum(r["meeting_date"])
        if a and _im(tag, von, bis):
            art = r["meeting_type"] or "interview"
            zeilen.append([tag, a.get("company") or "", a.get("title") or "",
                           TERMIN_TEXT.get(art, "Sonstiger Termin"),
                           _MEETING_STATUS.get(r["status"] or "", r["status"] or "")])
    return zeilen


def kennzahlen(db, von: str = "", bis: str = "") -> list:
    """Je Zeile: Kennzahl, Wert als Text, Anzahl, Basis, Bezug, Zeitraum."""
    d = _kern.bericht_daten(db, von, bis)
    zeitraum = d["zeitraum"]["text"]
    zeilen = []
    for k, name in _KENNZAHLEN:
        w = d["kennzahlen"][k]
        zeilen.append([name, w["text"], w.get("anzahl"), w.get("basis"), w["bezug"], zeitraum])
    for k, name in _DAUERN:
        w = d["dauer"][k]
        zeilen.append([name, w["text"], w.get("anzahl"), None, w["bezug"], zeitraum])
    return zeilen


def _blatt(wb, titel: str, kopf: list, zeilen: list, breiten: list):
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    ws = wb.create_sheet(titel)
    for spalte, text in enumerate(kopf, 1):
        z = ws.cell(row=1, column=spalte, value=text)
        z.font = Font(bold=True)
        z.fill = PatternFill("solid", fgColor="E6E6E6")
    for r, zeile in enumerate(zeilen, 2):
        for spalte, wert in enumerate(zeile, 1):
            z = ws.cell(row=r, column=spalte, value=wert)
            if isinstance(wert, date):
                z.number_format = "DD.MM.YYYY"
    for spalte, breite in enumerate(breiten, 1):
        ws.column_dimensions[get_column_letter(spalte)].width = breite
    ws.freeze_panes = "A2"
    if zeilen:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(kopf))}{len(zeilen) + 1}"


def blaetter_ergaenzen(db, pfad, von: str = "", bis: str = "") -> None:
    """Haengt Ereignisse, Termine und Kennzahlen an die Excel-Datei an."""
    from openpyxl import load_workbook

    wb = load_workbook(str(pfad))
    _blatt(wb, "Ereignisse", ["Datum", "Firma", "Stelle", "Ereignis"], ereignisse(db, von, bis),
           [14, 34, 40, 26])
    _blatt(wb, "Termine", ["Datum", "Firma", "Stelle", "Art", "Stand"], termine(db, von, bis),
           [14, 34, 40, 24, 16])
    _blatt(wb, "Kennzahlen", ["Kennzahl", "Wert", "Anzahl", "Basis", "Bezug", "Zeitraum"],
           kennzahlen(db, von, bis), [36, 44, 10, 10, 14, 28])
    wb.save(str(pfad))
