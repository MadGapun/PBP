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

Abgrenzung: Zeitstempel fuer die Datenbank (das `_jetzt()` der Dienste) und
die Ortszeit eines Termins (`termin_zeit.jetzt_lokal`) lesen ihre eigene Uhr
und bleiben dort. Hier geht es um das Datum, mit dem gerechnet wird.
"""
from __future__ import annotations

from datetime import date


def heute() -> date:
    """Das heutige Datum der Maschine (Ortszeit)."""
    return date.today()
