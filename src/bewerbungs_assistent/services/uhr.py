"""Die Uhr fuer Rechnungen "bis heute" (#1237).

Eine Rechnung "bis heute" (die Berufsjahre einer laufenden Position, die
Luecke im Werdegang) nimmt das Datum von hier und traegt nie eine
Jahreszahl im Code. Bis v1.7.158 stand an drei Stellen eine feste 2026:
ab dem 01.01.2027 fehlte jeder laufenden Position ein Jahr, ab 2028 zwei,
und die Karrierestufe, die die lokale KI beim Aussortieren bekommt, kippte
zu spaet (Mid-Level erst nach 6 statt 5, Senior erst nach 11 statt 10
Jahren).

Tests setzen `heute` auf einen festen Tag
(`monkeypatch.setattr(uhr, "heute", lambda: date(2027, 1, 1))`). Darum
rufen die Stellen `uhr.heute()` ueber das Modul auf und importieren die
Funktion nie mit `from .uhr import heute` (dann wirkte das Festhalten im
Test nicht mehr). Der Waechter `tests/test_berufsjahre_laufendes_jahr_1237.py`
haelt feste Jahreszahlen aus dem Quelltext.

Abgrenzung: die Ortszeit eines Termins (`termin_zeit.jetzt_lokal`) liest ihre
eigene Uhr und bleibt dort. Hier geht es um das Datum, mit dem gerechnet wird -
und seit #1386 (unten) um den Zeitstempel, der in die Datenbank geschrieben wird.
"""
from __future__ import annotations

from datetime import date


def heute() -> date:
    """Das heutige Datum der Maschine (Ortszeit)."""
    return date.today()


# -- Zeitstempel fuer die Datenbank (#1386) ---------------------------------
#
# Gespeicherte Zeitpunkte gab es in ZWEI Formen: `2026-11-11T19:30:09+00:00`
# (UTC mit Zone, das `_now()` der Datenbank) und `2026-11-11T20:29:03`
# (Ortszeit ohne Zone, ein nacktes `datetime.now()` als Text). Sortiert und
# verglichen wird als Text. In der Zeitzone Berlin stand die Anlage-Notiz
# (20:29) deshalb ueber "beworben" (19:30), und "Letzte Notiz" zeigte die
# aeltere Notiz.
#
# Regel: WER SCHREIBT, nimmt `jetzt()`. WER LIEST UND ORDNET, nimmt
# `zeitpunkt()`/`nach_zeit()`: sie machen aus beiden Formen denselben
# Zeitpunkt (Altbestand ohne Zone = Ortszeit). Ein Waechter
# (`tests/test_v187_zeitstempel_1386.py`) haelt fest, welche Stellen noch
# Ortszeit ohne Zone schreiben, und begruendet jede Ausnahme.
from datetime import datetime, timezone


def jetzt() -> str:
    """Der Zeitpunkt "jetzt" fuer alles, was gespeichert wird: UTC mit Zone."""
    return datetime.now(timezone.utc).isoformat()


def zeitpunkt(text) -> datetime | None:
    """Ein gespeicherter Zeitpunkt als Zeitpunkt MIT Zone, oder None.

    Mit Zone gespeichert gilt die Zone; ohne Zone ist es Ortszeit (so wurde
    der Altbestand geschrieben). Ein reines Datum gilt als 00:00 Ortszeit.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.astimezone()


def zeit_schluessel(text) -> tuple:
    """Sortierschluessel: gleiche Zeitpunkte gleich, Unlesbares zuerst."""
    dt = zeitpunkt(text)
    return (0, 0.0) if dt is None else (1, dt.timestamp())


def nach_zeit(eintraege, feld: str = "event_date", rueckwaerts: bool = False) -> list:
    """Eintraege nach ihrem Zeitpunkt ordnen (stabil; gleiche Zeit nach `id`)."""
    def schluessel(e):
        return (zeit_schluessel(e.get(feld)), e.get("id") or 0)
    return sorted(eintraege or [], key=schluessel, reverse=rueckwaerts)
