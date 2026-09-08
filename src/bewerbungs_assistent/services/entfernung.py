"""Die Entfernung sagt, was sie ist (#950).

Gemeldet am 21.08.2026 anhand einer Stelle in Nordhessen: PBP wies
`entfernung_km: 271.5` aus. Die Fahrstrecke betraegt rund 390 km — vier
Stunden je Richtung. Der Nutzer hat nachgefragt, weil die Zahl ihm zu
niedrig vorkam.

**Genau das ist der Fehler: an der Zahl steht nicht, was sie ist.** Ein
Feld namens `entfernung_km` wird als Wegstrecke gelesen, nicht als
Luftlinie. Bei einer 30-km-Grenze faellt die Differenz nicht auf, bei
Fernstellen entscheidet sie ueber die Einschaetzung.

**Und die Zahl ist inzwischen mehr als eine Anzeige.** Zum Zeitpunkt von
#167 war die Entfernung ein Malus in Stufen; seit #910 wird sie gegen
das Gehalt verrechnet. Ein systematisch zu niedriger Kilometerwert
faellt damit zugunsten weit entfernter Stellen aus. Eine Groesse, die
nur angezeigt wird, darf ungenau sein — eine, gegen die gerechnet wird,
sollte es nicht.

**Was dieses Modul NICHT tut:** es aendert keinen Malus und keine
Bewertung. Die Leitlinie bleibt Recall vor Praezision (#910: Entfernung
ist ein Preis, kein Ausschluss). Es geht allein darum, dass die Zahl
bedeutet, was sie vorgibt.

**Der Umrechnungsfaktor ist eine Faustregel, keine Messung.** #167 nahm
1,3 an; im gemeldeten Fall lag er bei 390/271,5 = 1,44. Er haengt an der
Streckenfuehrung: entlang einer durchgehenden Autobahn niedrig, quer zur
Verkehrsachse oder um Gewaesser herum deutlich hoeher — fuer den
norddeutschen Raum mit Elbquerungen ist 1,3 optimistisch. Deshalb steht
hier 1,4, und deshalb traegt jede damit gebildete Zahl das Wort
"geschaetzt". Die richtige Antwort ist ein echtes Routing samt Fahrzeit
(AK 3/4 aus #950, braucht einen API-Schluessel) — bis dahin ist eine
gekennzeichnete Schaetzung ehrlicher als eine Luftlinie, die wie eine
Fahrstrecke aussieht.
"""
from __future__ import annotations

# Luftlinie -> Fahrstrecke. Faustregel, siehe Modul-Docstring.
FAHRSTRECKEN_FAKTOR = 1.4

# Unterhalb dieser Entfernung ist die Unterscheidung ohne Belang: der
# Unterschied liegt im Bereich weniger Kilometer, und eine
# Schaetzzahl daneben zu stellen suggeriert eine Genauigkeit, die es
# nicht gibt.
AB_KM_RELEVANT = 25.0

ART_LUFTLINIE = "luftlinie"


def fahrstrecke_schaetzung(luftlinie_km) -> float | None:
    """Grobe Fahrstrecke aus der Luftlinie — oder None, wenn sinnlos."""
    try:
        km = float(luftlinie_km)
    except (TypeError, ValueError):
        return None
    if km < AB_KM_RELEVANT:
        return None
    return round(km * FAHRSTRECKEN_FAKTOR)


def beschriftung(luftlinie_km) -> str:
    """Wie die Zahl in einem Text genannt wird.

    Nie eine blosse Kilometerzahl — die wird als Wegstrecke gelesen.
    """
    try:
        km = float(luftlinie_km)
    except (TypeError, ValueError):
        return ""
    fahrt = fahrstrecke_schaetzung(km)
    if fahrt is None:
        return f"{km:g} km Luftlinie"
    return f"{km:g} km Luftlinie (~{fahrt:g} km Fahrstrecke, geschaetzt)"


def befund(luftlinie_km) -> dict:
    """Der vollstaendige Befund zu einer Entfernung.

    Returns:
        Leeres dict, wenn keine Entfernung vorliegt — ein Aufrufer soll
        nicht zwischen "0 km" und "unbekannt" raten muessen (#965/#989).
    """
    try:
        km = float(luftlinie_km)
    except (TypeError, ValueError):
        return {}
    ergebnis = {
        "entfernung_km": km,
        "entfernung_art": ART_LUFTLINIE,
        "entfernung_text": beschriftung(km),
    }
    fahrt = fahrstrecke_schaetzung(km)
    if fahrt is not None:
        ergebnis["fahrstrecke_km_geschaetzt"] = fahrt
        ergebnis["fahrstrecke_hinweis"] = (
            f"Schaetzung aus der Luftlinie (Faktor {FAHRSTRECKEN_FAKTOR}), "
            "keine berechnete Route. Je nach Streckenfuehrung liegt der "
            "wirkliche Wert darueber oder darunter."
        )
    return ergebnis
