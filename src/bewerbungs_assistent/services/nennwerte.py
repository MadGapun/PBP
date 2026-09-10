"""Was ich mindestens nehme — und was ich sage (#931).

Ein Feld erfuellte zwei Zwecke, die einander widersprechen:

1. **Filterschwelle** — ab welchem Betrag ist eine Stelle ueberhaupt
   interessant? Dort gehoert der NIEDRIGSTE noch akzeptable Wert hin,
   sonst filtert die Suche brauchbare Stellen weg.
2. **Nennwert** — was sage ich, wenn im Gespraech nach der
   Gehaltsvorstellung gefragt wird? Dort gehoert ein HOEHERER Wert hin,
   weil von der genannten Zahl nach unten verhandelt wird, nie nach
   oben.

Beides in ein Feld zu zwingen ist kein Komfortproblem. Der Nutzer
beschreibt die Folge:

    "die selbst genannte Untergrenze ist ueber Monate gewandert, und in
    Verhandlungen wird Flexibilitaet signalisiert, bevor eine Zahl der
    Gegenseite auf dem Tisch liegt."

Ein festgeschriebener Nennwert, der nicht erst im Gespraech entsteht,
ist die Gegenmassnahme.

## Die eine Regel, die dieses Modul durchsetzt

**Nur die Minimum-Werte wirken im Scoring. Die Wunschwerte sind reine
Merkposten und duerfen die Suche nicht beeinflussen.**

Das ist der Kern des Issues, und es ist eine Regel, die man leicht
versehentlich bricht: ein Wunschwert, der in die Kriterien geraet,
sieht dort aus wie jeder andere Regler. Deshalb liegt die Trennung
hier und nicht verstreut bei den Aufrufern — und deshalb steht ein
Regressionstest daneben, der denselben Score mit und ohne gesetzten
Wunschwert nachrechnet.

## Der Wunschwert ist eine Vorbelegung, keine Festlegung

Was tatsaechlich genannt wird, entscheidet der Mensch je Vorgang. Die
Zahl steht vor dem Termin fest, statt im Gespraech gebildet zu werden —
mehr will sie nicht sein.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Die drei Paare. Links das Feld, das FILTERT; rechts das, das nur
# erinnert. Die Zuordnung steht genau hier — eine zweite Liste
# irgendwo waere die Bauform, die dieses Projekt vierzehnmal gekostet
# hat.
PAARE = {
    "min_gehalt": "wunsch_gehalt",
    "min_tagessatz": "wunsch_tagessatz",
    "min_stundensatz": "wunsch_stundensatz",
}

WUNSCH_FELDER = tuple(PAARE.values())

BEZEICHNUNG = {
    "wunsch_gehalt": "Wunsch-Jahresgehalt",
    "wunsch_tagessatz": "Wunsch-Tagessatz",
    "wunsch_stundensatz": "Wunsch-Stundensatz",
}


def aus_scoring_entfernen(kriterien: dict) -> dict:
    """Die Wunschwerte gehoeren nicht in die Rechnung (#931).

    Wird auf dem Weg in das Scoring aufgerufen. Ein Wunschwert, der
    stehen bleibt, wirkt dort wie jeder andere Regler — und genau das
    soll er nicht.

    Gibt eine KOPIE zurueck; die Kriterien des Aufrufers bleiben
    unberuehrt, damit die Anzeige sie weiter zeigen kann.
    """
    if not isinstance(kriterien, dict):
        return kriterien
    if not any(f in kriterien for f in WUNSCH_FELDER):
        return kriterien
    sauber = dict(kriterien)
    for feld in WUNSCH_FELDER:
        sauber.pop(feld, None)
    return sauber


def lesen(db) -> dict:
    """Die gesetzten Wunschwerte, als Zahlen."""
    werte = {}
    try:
        kriterien = db.get_search_criteria() or {}
    except Exception as exc:  # pragma: no cover
        logger.debug("Kriterien nicht lesbar: %s", exc)
        return werte
    for feld in WUNSCH_FELDER:
        roh = kriterien.get(feld)
        if roh in (None, "", 0):
            continue
        try:
            werte[feld] = float(roh)
        except (TypeError, ValueError):  # pragma: no cover
            continue
    return werte


def uebersicht(db) -> dict:
    """Minimum und Wunschwert nebeneinander — getrennt benannt.

    Beide in einer Zahl auszugeben waere genau die Vermischung, wegen
    der dieses Issue entstanden ist.
    """
    try:
        kriterien = db.get_search_criteria() or {}
    except Exception:  # pragma: no cover
        kriterien = {}
    zeilen = []
    for minimum, wunsch in PAARE.items():
        m, w = kriterien.get(minimum), kriterien.get(wunsch)
        if m in (None, "", 0) and w in (None, "", 0):
            continue
        eintrag = {"feld": minimum, "minimum": _zahl(m), "wunsch": _zahl(w)}
        if eintrag["minimum"] is not None and eintrag["wunsch"] is not None:
            if eintrag["wunsch"] < eintrag["minimum"]:
                # Kein Block — nur der Hinweis. Es kann Absicht sein.
                eintrag["hinweis"] = (
                    "Der Nennwert liegt UNTER deinem Minimum. Von der "
                    "genannten Zahl wird nach unten verhandelt, nie nach "
                    "oben — gemeint war vermutlich der hoehere Wert.")
        zeilen.append(eintrag)
    return {
        "werte": zeilen,
        "bedeutung": {
            "minimum": ("Filterschwelle — ab hier ist eine Stelle "
                        "interessant. Wirkt im Scoring."),
            "wunsch": ("Nennwert fuers Gespraech. Merkposten — wirkt "
                       "NICHT im Scoring und filtert nichts."),
        },
    }


def vorbelegung(db, stellenart: str = "festanstellung") -> dict | None:
    """Was in einer neuen Bewerbung als Gehaltsvorstellung vorsteht.

    Ueberschreibbar je Bewerbung — was tatsaechlich genannt wird,
    entscheidet der Mensch je Vorgang.
    """
    werte = lesen(db)
    if not werte:
        return None
    art = (stellenart or "").strip().lower()
    if art in ("freelance", "freiberuflich", "projekt"):
        feld = "wunsch_tagessatz"
    elif art in ("teilzeit", "werkstudent", "minijob"):
        feld = "wunsch_stundensatz"
    else:
        feld = "wunsch_gehalt"
    if feld not in werte:
        return None
    return {
        "feld": feld,
        "wert": werte[feld],
        "bezeichnung": BEZEICHNUNG[feld],
        "hinweis": ("Vorbelegung aus deinen Suchkriterien. Was du "
                    "tatsaechlich nennst, entscheidest du je Stelle."),
    }


def _zahl(wert):
    if wert in (None, "", 0):
        return None
    try:
        return float(wert)
    except (TypeError, ValueError):  # pragma: no cover
        return None
