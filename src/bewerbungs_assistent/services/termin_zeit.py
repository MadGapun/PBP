"""Eine Form fuer Terminzeiten (#1102).

Termine wurden in der Form gespeichert, in der sie ankamen, und danach als
Text verglichen. `"2026-04-18 14:00" < "2026-04-18T09:30"` — ein Leerzeichen
sortiert vor `T`, also fehlte jeder Termin von heute in dieser Form bei den
kommenden. Eine Einladung mit Zeitzone (`...+00:00`) landete im Kalender
zwei Stunden zu frueh, weil der Export die Zone wegliess.

Die Regeln:

* Gespeichert wird **Ortszeit ohne Zone** als `YYYY-MM-DDTHH:MM`
  (Sekunden nur, wenn sie nicht 0 sind). Eine Angabe mit Zone wird in die
  Ortszeit umgerechnet — danach ist der Textvergleich richtig.
* Ein **reines Datum** ist ein ganztaegiger Termin und bleibt `YYYY-MM-DD`.
* Die deutsche Form `18.04.2026 14:00` wird umgewandelt.
* **Unlesbares wird abgewiesen**, nicht gespeichert (`ValueError`, der Satz
  nennt die erlaubten Formen). Ein Termin, den nichts einordnen kann, waere
  nie "kommend" und nie "vergangen".
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

FORMEN = "2026-04-18T14:00, 2026-04-18 14:00, 18.04.2026 14:00 oder 2026-04-18 (ganztägig)"

_DEUTSCH = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:[ ,T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?(?:\s*Uhr)?$")
_NUR_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _format(dt: datetime) -> str:
    if dt.second:
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    return dt.strftime("%Y-%m-%dT%H:%M")


def ist_ganztaegig(wert) -> bool:
    return bool(_NUR_DATUM.match(str(wert or "").strip()))


def normalisieren(wert) -> str:
    """Die gespeicherte Form eines Terminzeitpunkts. Wirft ValueError."""
    text = str(wert or "").strip()
    if not text:
        raise ValueError("Kein Termindatum angegeben. Erlaubt: " + FORMEN)
    if _NUR_DATUM.match(text):
        try:
            datetime.strptime(text, "%Y-%m-%d")  # prueft das Datum selbst
        except ValueError:
            raise ValueError(f"„{text}“ ist kein gültiges Datum. Erlaubt: {FORMEN}")
        return text
    m = _DEUTSCH.match(text)
    if m:
        tag, monat, jahr, std, minute, sek = m.groups()
        try:
            dt = datetime(int(jahr), int(monat), int(tag),
                          int(std or 0), int(minute or 0), int(sek or 0))
        except ValueError:
            raise ValueError(f"„{text}“ ist kein gültiges Datum. Erlaubt: {FORMEN}")
        return _format(dt) if std is not None else dt.strftime("%Y-%m-%d")
    iso = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        raise ValueError(f"„{text}“ lässt sich nicht als Termin lesen. Erlaubt: {FORMEN}")
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)  # in die Ortszeit
    return _format(dt)


def normalisieren_oder_lassen(wert) -> tuple[str, bool]:
    """Fuer den Bestand: (neuer Wert, geaendert). Unlesbares bleibt stehen."""
    try:
        neu = normalisieren(wert)
    except ValueError:
        return str(wert or ""), False
    return neu, neu != str(wert or "")


def jetzt_lokal() -> str:
    """Der Vergleichswert fuer "kommend": Ortszeit in derselben Form."""
    return _format(datetime.now().replace(microsecond=0))


def lesbar(wert) -> str:
    """`2026-09-30T11:00:00` -> `30.09.2026 11:00`; ohne Uhrzeit (oder bei 00:00)
    nur das Datum. Unlesbares bleibt stehen. Eine Fassung fuer Antworten und
    Verlaufszeilen (vorher in `termin_folgen`)."""
    roh = str(wert or "")
    try:
        tag = datetime.strptime(roh[:10], "%Y-%m-%d")
    except ValueError:
        return roh
    text = tag.strftime("%d.%m.%Y")
    zeit = roh[11:16]
    return f"{text} {zeit}" if zeit and zeit != "00:00" else text


def ende_korrigieren(beginn, ende, dauer_min=None) -> tuple:
    """(gueltiges Ende oder None, geaendert) — v1.7.146, #1140.

    Ein Ende zaehlt nur, wenn es NACH dem Beginn liegt. Bis v1.7.145
    schrieb das Kalender-Formular das Ende in UTC statt in Ortszeit: aus
    "14:00, 60 Minuten" wurde im Sommer das Ende 13:00, im Winter 14:00.
    Die ICS-Datei war damit ungueltig, und die Kollisionspruefung sah keine
    Ueberschneidung. Ein solches Ende wird aus Beginn + Dauer gerechnet; fehlt
    die Dauer, bleibt es leer (unbekannt) statt falsch.

    Unberuehrt bleiben: ein fehlendes Ende, ein ganztaegiger Termin und alles,
    was sich nicht lesen laesst (das meldet `normalisieren`, nicht diese
    Funktion). Erwartet die gespeicherte Form (Ortszeit ohne Zone).
    """
    if not ende or ist_ganztaegig(beginn):
        return ende, False
    try:
        b = datetime.fromisoformat(str(beginn).strip())
        e = datetime.fromisoformat(str(ende).strip())
    except ValueError:
        return ende, False
    if e > b:
        return ende, False
    try:
        dauer = int(dauer_min) if dauer_min not in (None, "") else 0
    except (TypeError, ValueError):
        dauer = 0
    if dauer > 0:
        return _format(b + timedelta(minutes=dauer)), True
    return None, True
