"""Ein kaputter Datensatz kostet einen Datensatz, nicht die Quelle (#813).

Gefunden bei der Quellenpflege am 08.09.2026. `himalayas` stand seit dem
01.09. automatisch abgeschaltet, Begruendung "5 stille Laeufe in Serie".
Live nachgemessen: die API antwortet mit HTTP 200 und liefert 20 Stellen.

Der Adapter starb an der ERSTEN davon. Das Feld `seniority` kommt
inzwischen als Liste (`['Senior']`) statt als String, `.lower()` warf
einen `AttributeError`, und das grosszuegige `except Exception` um die
ganze Schleife gab eine leere Liste zurueck. Nach aussen sah das aus wie
"diese Quelle hat gerade nichts" — fuenf Mal, dann schaltete die
Automatik sie ab.

**Das ist die teuerste Bauform einer stillen Null**, weil sie sich selbst
bestaetigt: der Fehler erzeugt Leere, die Leere erzeugt die Abschaltung,
und die Abschaltung verhindert, dass der Fehler je wieder auffaellt.

Gezaehlt am selben Tag: **zehn Adapter** fuehren eine Zuordnungsschleife
ohne Schutz je Datensatz, zwei davon (`remoteok`, `remotive`) liefern
produktiv. Deshalb steht die Antwort hier einmal und nicht zehnmal.

Die Regel dazu: **ein Feldumbau an der Quelle darf Treffer kosten, aber
nie die Quelle.** Wer 20 Stellen schickt und bei einer davon ein Feld
umbaut, soll 19 Stellen liefern und eine Meldung — nicht null Stellen
und Schweigen.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("bewerbungs_assistent.scraper.satzweise")

# Wie viele kaputte Saetze in Folge, bevor der Verdacht nicht mehr dem
# Datensatz gilt, sondern dem Adapter. Darunter ist es ein Ausreisser,
# darueber ein Feldumbau — und der gehoert gemeldet, nicht weggezaehlt.
VERDACHT_AB_ANTEIL = 0.5


def zuordnen(rohdaten, abbildung, quelle: str = "") -> tuple:
    """Bildet Rohdaten auf Stellen ab und ueberlebt einzelne Ausreisser.

    Args:
        rohdaten: die Objekte der Quelle.
        abbildung: Funktion Rohobjekt -> Stelle (oder None zum Auslassen).
        quelle: Name fuer die Log-Zeile.

    Returns:
        `(stellen, befund)`. `befund` traegt `gesamt`, `abgebildet`,
        `fehlerhaft`, `ausgelassen` und — wenn etwas schiefging —
        `erster_fehler` samt `feldformen` des ausloesenden Satzes. Das
        ist der Unterschied zwischen "hat nichts geliefert" und "hat
        geliefert, wir konnten es nicht lesen".
    """
    stellen, fehlerhaft, ausgelassen = [], 0, 0
    erster_fehler = None
    ausloeser = None

    for roh in (rohdaten or []):
        try:
            eintrag = abbildung(roh)
        except Exception as exc:            # noqa: BLE001 - Absicht
            fehlerhaft += 1
            if erster_fehler is None:
                erster_fehler = f"{type(exc).__name__}: {exc}"[:200]
                ausloeser = roh
            continue
        if eintrag is None:
            ausgelassen += 1
            continue
        stellen.append(eintrag)

    gesamt = len(rohdaten or [])
    befund = {"gesamt": gesamt, "abgebildet": len(stellen),
              "fehlerhaft": fehlerhaft, "ausgelassen": ausgelassen}
    if not fehlerhaft:
        return stellen, befund

    befund["erster_fehler"] = erster_fehler
    befund["feldformen"] = feldformen(ausloeser)
    anteil = fehlerhaft / gesamt if gesamt else 0
    if anteil >= VERDACHT_AB_ANTEIL:
        # Nicht ein Ausreisser, sondern ein Feldumbau: laut melden, damit
        # es nicht wieder fuenf stille Laeufe braucht.
        befund["verdacht"] = "feldumbau"
        logger.warning(
            "%s: %d von %d Datensaetzen nicht lesbar (%s). Das sieht nach "
            "einem Feldumbau an der Quelle aus, nicht nach Ausreissern. "
            "Feldformen des ersten Fehlers: %s",
            quelle or "Quelle", fehlerhaft, gesamt, erster_fehler,
            befund["feldformen"])
    else:
        logger.info("%s: %d von %d Datensaetzen uebersprungen (%s)",
                    quelle or "Quelle", fehlerhaft, gesamt, erster_fehler)
    return stellen, befund


def feldformen(roh, grenze: int = 14) -> dict:
    """Welchen TYP hatte jedes Feld? Das ist die Diagnose, die zaehlt.

    Bei `himalayas` lautete die Antwort `seniority: list` statt `str` —
    das eine Wort, das die Ursache benennt. Werte bleiben draussen: hier
    stehen Stellenanzeigen drin, und eine Log-Zeile ist kein Ort fuer
    fremde Daten.
    """
    if not isinstance(roh, dict):
        return {"_typ": type(roh).__name__}
    return {schluessel: type(wert).__name__
            for schluessel, wert in list(roh.items())[:grenze]}


def text_aus(wert) -> str:
    """Ein Feld als Text lesen, egal ob es String, Liste oder Zahl ist.

    Quellen bauen Felder um, ohne es anzukuendigen: aus `"Senior"` wurde
    bei himalayas `["Senior"]`. Ein Adapter, der `.lower()` direkt auf
    das Feld ruft, ist gegen so etwas nicht gewappnet.
    """
    if wert is None:
        return ""
    if isinstance(wert, str):
        return wert
    if isinstance(wert, (list, tuple, set)):
        return " ".join(text_aus(w) for w in wert if w is not None)
    if isinstance(wert, dict):
        for schluessel in ("name", "label", "text", "title", "value"):
            if wert.get(schluessel):
                return text_aus(wert[schluessel])
        return ""
    return str(wert)
