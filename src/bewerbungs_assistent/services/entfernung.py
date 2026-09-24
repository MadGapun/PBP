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
"geschaetzt".

## Seit v1.7.94: die echte Fahrstrecke (#950 AK 3-6)

Ist ein Routing-Schluessel eingerichtet (`services/routing.py`), traegt
eine Stelle zusaetzlich `fahrstrecke_km`, `fahrzeit_min` und
`route_quelle`. `distance_km` bleibt dabei die Luftlinie — eine Messung
behaelt ihre Bedeutung.

**`preis_km` ist die eine Stelle, die entscheidet, gegen welche Zahl
gerechnet wird.** Basis-Score, Fit-Analyse, Scoring-Regler und die
Aussortier-Automatik fragen sie, statt `distance_km` selbst zu lesen.
Vier Leser mit je eigener Wahl waeren #963 zum wiederholten Mal: der
eine rechnet mit der Fahrstrecke, der andere noch mit der Luftlinie, und
dieselbe Stelle traegt zwei Scores.
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
ART_FAHRSTRECKE = "fahrstrecke"


def _zahl(wert) -> float | None:
    if wert is None or isinstance(wert, bool):
        return None
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def preis_km(job, criteria=None) -> float | None:
    """Die Zahl, gegen die gerechnet wird (#950 AK 6).

    Die Fahrstrecke, sobald sie vorliegt — sonst die Luftlinie wie bisher.
    Eine Fahrstrecke von 0 oder darunter ist kein Beleg, sondern ein
    kaputter Wert; dann gilt die Luftlinie.

    v1.7.100 (#1037 Punkt 3): die Fahrstrecke zaehlt nur, wenn die
    Kriterien `_fahrstrecke_zaehlt` tragen — `get_search_criteria` setzt
    das genau dann, wenn ein Routing-Schluessel eingerichtet ist. Ohne
    Schluessel gilt die Luftlinie, auch an Stellen, an denen noch eine
    Fahrstrecke gespeichert ist. Genau das verspricht die Rueckfrage beim
    Entfernen des Schluessels. Ohne Kriterien (`None`) bleibt es beim
    bisherigen Verhalten; ein Guard verlangt, dass jeder Rechenweg sie
    uebergibt.
    """
    if not isinstance(job, dict):
        return None
    zaehlt = (criteria is None
              or (isinstance(criteria, dict)
                  and criteria.get("_fahrstrecke_zaehlt") is True))
    fahrt = _zahl(job.get("fahrstrecke_km"))
    if zaehlt and fahrt is not None and fahrt > 0:
        wert, ist_fahrt = fahrt, True
    else:
        wert, ist_fahrt = _zahl(job.get("distance_km")), False
    # v1.7.127 (#1082 AK 3): nennt die Anzeige einen naeheren Standort,
    # zaehlt dieser. Er hat nur eine Luftlinie — steht daneben eine
    # Fahrstrecke, wird er mit derselben Faustregel umgerechnet, sonst
    # verglichen wir zwei verschiedene Groessen.
    if isinstance(criteria, dict) and criteria.get("_standorte"):
        from . import standorte
        weiterer = standorte.naechster(job, criteria)
        if weiterer:
            km = weiterer["luftlinie_km"]
            if ist_fahrt:
                km = round(km * FAHRSTRECKEN_FAKTOR, 1)
            if wert is None or km < wert:
                return km
    return wert


def fahrzeit_text(minuten) -> str:
    """"45 Min", "1 Std", "3 Std 55 Min" — oder leer."""
    m = _zahl(minuten)
    if m is None or m < 0:
        return ""
    m = int(round(m))
    if m < 60:
        return f"{m} Min"
    stunden, rest = divmod(m, 60)
    return f"{stunden} Std {rest} Min" if rest else f"{stunden} Std"


def fahrstrecke_schaetzung(luftlinie_km) -> float | None:
    """Grobe Fahrstrecke aus der Luftlinie — oder None, wenn sinnlos."""
    km = _zahl(luftlinie_km)
    if km is None or km < AB_KM_RELEVANT:
        return None
    return round(km * FAHRSTRECKEN_FAKTOR)


def beschriftung(luftlinie_km) -> str:
    """Wie die Zahl in einem Text genannt wird.

    Nie eine blosse Kilometerzahl — die wird als Wegstrecke gelesen.
    """
    km = _zahl(luftlinie_km)
    if km is None:
        return ""
    fahrt = fahrstrecke_schaetzung(km)
    if fahrt is None:
        return f"{km:g} km Luftlinie"
    return f"{km:g} km Luftlinie (~{fahrt:g} km Fahrstrecke, geschaetzt)"


def _befund_fahrstrecke(job: dict, fahrt: float) -> dict:
    luft = _zahl(job.get("distance_km"))
    minuten = _zahl(job.get("fahrzeit_min"))
    text = f"{fahrt:g} km Fahrstrecke"
    zeit = fahrzeit_text(minuten)
    if zeit:
        text += f", {zeit}"
    if luft is not None:
        text += f" ({luft:g} km Luftlinie)"
    ergebnis = {
        "entfernung_km": fahrt,
        "entfernung_art": ART_FAHRSTRECKE,
        "entfernung_text": text,
        "fahrstrecke_km": fahrt,
    }
    if luft is not None:
        ergebnis["luftlinie_km"] = luft
    if zeit:
        ergebnis["fahrzeit_min"] = int(round(minuten))
        ergebnis["fahrzeit_text"] = zeit
    if job.get("route_quelle"):
        ergebnis["route_quelle"] = job["route_quelle"]
    return ergebnis


def befund(wert) -> dict:
    """Der vollstaendige Befund zu einer Entfernung.

    Args:
        wert: die ganze Stelle (bevorzugt — dann kennt der Befund auch die
            Fahrstrecke) oder, wie bis v1.7.93, die Luftlinie als Zahl.

    Returns:
        Leeres dict, wenn keine Entfernung vorliegt — ein Aufrufer soll
        nicht zwischen "0 km" und "unbekannt" raten muessen (#965/#989).
    """
    if isinstance(wert, dict):
        fahrt = _zahl(wert.get("fahrstrecke_km"))
        if fahrt is not None and fahrt > 0:
            return _befund_fahrstrecke(wert, fahrt)
        wert = wert.get("distance_km")
    km = _zahl(wert)
    if km is None:
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
            "wirkliche Wert darueber oder darunter. Mit einem "
            "Routing-Schluessel rechnet PBP die echte Fahrstrecke samt "
            "Fahrzeit."
        )
    return ergebnis


#: Vorgabe, wenn fuer eine Anstellungsform keine Grenze eingetragen ist.
#: Stand vorher DOPPELT im Code (calculate_score und fit_analyse), und die
#: Automatik nahm stattdessen den groessten Profilwert (#1036).
VORGABE_GRENZE_KM = {
    "festanstellung": 50,
    "zeitarbeit": 50,
    "ausbildung": 50,
    "praktikum": 50,
    "werkstudent": 50,
    "teilzeit": 30,
    "freelance": 200,
}
VORGABE_GRENZE_SONST = 50


def grenze_km(criteria, art) -> float:
    """Die Entfernungsgrenze fuer eine Anstellungsform — an EINER Stelle.

    Reihenfolge:
      1. `max_entfernung[art]` — der Wert, den der Mensch fuer genau diese
         Form eingetragen hat
      2. die Vorgabe je Form

    **Nicht** der groesste Profilwert. So stand es in der Automatik: eine
    Ausbildungsstelle bekam dort die 200 km von Freelance, im Score aber
    50 km — dieselbe Stelle, zwei Grenzen (#963, #1036).

    **Und nicht `max_entfernung_km`.** `suchkriterien_setzen` uebersetzt
    ihn seit #1000 in die Karte; ein Altwert, der danebensteht, wird dort
    BENANNT statt umgedeutet. Ihn hier als Rueckfall zu lesen waere genau
    die stille Neudeutung, die #1000 ausschliesst. Mit dieser Reihenfolge
    aendert sich der Score um keinen Punkt; nur die Automatik rechnet
    jetzt wie er.
    """
    criteria = criteria if isinstance(criteria, dict) else {}
    form = (art or "festanstellung").strip().lower()
    karte = criteria.get("max_entfernung") or {}
    if isinstance(karte, dict):
        wert = _zahl(karte.get(form))
        if wert is not None and wert > 0:
            return wert
    return float(VORGABE_GRENZE_KM.get(form, VORGABE_GRENZE_SONST))
