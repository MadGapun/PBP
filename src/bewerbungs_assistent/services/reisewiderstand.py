"""Nicht jeder Kilometer kostet gleich viel (#965 Befund 2).

Vom Nutzer am 02.09.2026 eingebracht:

    Der Wohnort liegt am Nordufer der Elbe, westlich von Hamburg. Nach
    Sueden gibt es genau drei Wege: den Elbtunnel auf der A7, die
    Elbbruecken durch die Stadt oder die Faehre. Alle drei sind entweder
    staugefaehrdet oder taktgebunden. Nach Norden gibt es diese Barriere
    nicht.

**Zwei Stellen mit derselben Kilometerzahl sind damit nicht gleich
weit** — und der Unterschied ist kein Aufschlag, den man mitteln
koennte, sondern eine Streuung, die den Arbeitsweg unplanbar macht.

**Das Muster ist allgemein, nicht lokal.** Fluesse ohne dichte
Querungen, Meerengen, Gebirgskaemme, Inseln und Grenzen erzeugen
dasselbe; ein Mensch in Koeln, Rostock oder Konstanz hat dieselbe Frage
mit anderer Geografie. Deshalb kennt dieses Modul keine Elbe, sondern
nur Richtungen und Aufschlaege.

**Warum kein Routing-Dienst.** Das Issue nennt zwei Wege. Eine
Routenberechnung loest das Problem am Ursprung, kostet aber eine externe
Abfrage je Stelle — und trifft ausgerechnet die Streuung nicht, sondern
nur den Mittelwert. Der konfigurierbare Widerstand bleibt lokal und
macht die Annahme **sichtbar und aenderbar**: der Mensch sieht die
Regel, statt sie zu erraten. Das ist die Entscheidung des Melders, und
sie passt zu diesem Projekt.

**Was der Aufschlag NICHT tut: er veraendert die ausgewiesene Entfernung
nicht.** Die bleibt, was sie ist (#950). Er wirkt allein auf den
Entfernungs-MALUS — auf den Preis, nicht auf die Messung. Sonst haette
PBP wieder eine Zahl, die etwas anderes bedeutet, als sie sagt.
"""
from __future__ import annotations

EINSTELLUNG = "reisewiderstand"

# Himmelsrichtungen, in denen eine Barriere liegen kann. Der Vergleich
# laeuft ueber die Koordinaten des Wohnorts, nicht ueber Ortsnamen —
# damit gilt die Regel fuer jede Geografie.
RICHTUNGEN = ("norden", "sueden", "osten", "westen")

# Ein Aufschlag ohne Obergrenze waere ein versteckter Ausschluss; die
# Entscheidung "Entfernung ist ein Preis" (#910/#988) gilt weiter.
MAX_AUFSCHLAG_KM = 500.0


def _zahl(wert, vorgabe=None):
    try:
        return float(wert)
    except (TypeError, ValueError):
        return vorgabe


def regel_pruefen(richtung: str, aufschlag_km, name: str = "") -> dict:
    """Prueft eine Regel, bevor sie gespeichert wird.

    Returns:
        `{"ok": True, "regel": {...}}` oder `{"ok": False, "fehler": ...}`.
        Eine Regel, die nicht wirken kann, gehoert abgewiesen und nicht
        gespeichert — sonst entsteht wieder eine Einstellung, die
        aussieht als wirke sie (#988).
    """
    r = (richtung or "").strip().lower()
    if r not in RICHTUNGEN:
        return {"ok": False,
                "fehler": (f"richtung muss eine von {', '.join(RICHTUNGEN)} "
                           f"sein, nicht '{richtung}'.")}
    km = _zahl(aufschlag_km)
    if km is None or km <= 0:
        return {"ok": False,
                "fehler": "aufschlag_km muss eine Zahl groesser 0 sein."}
    if km > MAX_AUFSCHLAG_KM:
        return {"ok": False,
                "fehler": (f"aufschlag_km ist auf {MAX_AUFSCHLAG_KM:g} "
                           "begrenzt — ein unbegrenzter Aufschlag waere ein "
                           "versteckter Ausschluss, und Entfernung ist ein "
                           "Preis (#910).")}
    return {"ok": True, "regel": {"richtung": r, "aufschlag_km": km,
                                  "name": (name or "").strip()[:60]}}


def regeln_lesen(kriterien: dict) -> list:
    """Die gespeicherten Regeln — leere Liste, wenn keine gesetzt sind."""
    roh = (kriterien or {}).get(EINSTELLUNG)
    if not isinstance(roh, list):
        return []
    gueltig = []
    for eintrag in roh:
        if not isinstance(eintrag, dict):
            continue
        geprueft = regel_pruefen(eintrag.get("richtung"),
                                 eintrag.get("aufschlag_km"),
                                 eintrag.get("name", ""))
        if geprueft["ok"]:
            gueltig.append(geprueft["regel"])
    return gueltig


def richtung_von(job_lat, job_lon, wohn_lat, wohn_lon) -> set:
    """In welchen Richtungen liegt das Ziel vom Wohnort aus?

    Ein Ziel kann in zwei Richtungen zugleich liegen (suedwestlich ist
    sueden UND westen) — beide Regeln greifen dann.
    """
    jl, jo = _zahl(job_lat), _zahl(job_lon)
    wl, wo = _zahl(wohn_lat), _zahl(wohn_lon)
    if None in (jl, jo, wl, wo):
        return set()
    richtungen = set()
    if jl < wl:
        richtungen.add("sueden")
    elif jl > wl:
        richtungen.add("norden")
    if jo < wo:
        richtungen.add("westen")
    elif jo > wo:
        richtungen.add("osten")
    return richtungen


def aufschlag(kriterien: dict, job: dict) -> tuple:
    """Wieviel Aufschlag traegt DIESE Stelle — und warum?

    Returns:
        `(km, belege)`. `km` ist 0.0, wenn keine Regel greift; `belege`
        ist eine Liste lesbarer Zeilen fuer `scoring_vorschau` (AK 7:
        die Regel muss nachvollziehbar sein, nicht nur wirksam).
    """
    regeln = regeln_lesen(kriterien)
    if not regeln or not isinstance(job, dict):
        return 0.0, []
    # Ohne aufgeloeste Entfernung gibt es keinen Malus, auf den ein
    # Aufschlag wirken koennte — und eine unbekannte Entfernung soll
    # nicht ueber Umwege doch bestraft werden (#989).
    if job.get("distance_km") is None:
        return 0.0, []

    ziel = richtung_von(job.get("lat"), job.get("lon"),
                        (kriterien or {}).get("standort_lat"),
                        (kriterien or {}).get("standort_lon"))
    if not ziel:
        return 0.0, []

    summe, belege = 0.0, []
    for regel in regeln:
        if regel["richtung"] in ziel:
            summe += regel["aufschlag_km"]
            bezeichnung = regel["name"] or f"Barriere im {regel['richtung'].title()}"
            belege.append(
                f"{bezeichnung}: +{regel['aufschlag_km']:g} km, weil das "
                f"Ziel im {regel['richtung'].title()} liegt")
    return round(summe, 1), belege
