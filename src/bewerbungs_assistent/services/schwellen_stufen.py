"""Die Score-Schwelle als benannte Stufe statt als Zahl (#1063).

PBP kennt zwei Schwellen, und beide waren Zahlen ohne Bezugsgroesse:

* `min_score_schwelle` entscheidet beim **Speichern** waehrend der Suche
* `schwellenwert/auto_ignore` blendet in der **Liste** aus

Drei Befunde des Melders (21.09.2026), alle nachgemessen:

1. **Die Zahl sagt nichts.** Ob 7 viel oder wenig ist, weiss nur, wer
   die Verteilung kennt. Ueber 2.780 Stellen: Median 1, p90 21, max 110
   — die 7 sah nach "eher niedrig" aus und verwarf 82 % des Bestands.
2. **Die Zahl verschiebt sich unter dem Nutzer.** Seit der
   Begriffsgruppierung (#1012) faellt der Score fuer dieselbe Anzeige
   niedriger aus; `suchkriterien_anzeigen` warnt selbst davor. Jede
   Aenderung an Gewichten, Listen oder Deckeln deutet eine feste Zahl um.
3. **Direkt ueber der Vorgabe liegt eine Klippe.** Von Schwelle 1 auf 2
   faellt der sichtbare Bestand von 1.710 auf 846 — ein Schritt von eins
   halbiert das Ergebnis.

Daraus folgt die Bauform: **gespeichert wird die STUFE, gerechnet wird
beim Lesen.** Damit bleibt die Wahl dieselbe, auch wenn sich die Zahl
dahinter verschiebt (AK 5) — genau die Eigenschaft, die einer festen
Zahl fehlt.

## Warum "Alles zeigen" die Vorgabe ist

Die Kosten sind nicht symmetrisch. Was die Speicher-Schwelle verwirft,
kommt nie in den Bestand und ist unwiederbringlich. Gemessen auf einer
Bestandskopie (57 bewertbare Bewerbungen, 2.765 Aussortierte):

    Alles zeigen           0,0     0 % der eigenen Bewerbungen verworfen
    Offensichtliches aus   3,5     7 %
    Locker                 7,0    12 %
    Ausgewogen             9,0    21 %
    Streng                17,0    49 %
    Nur Volltreffer       28,8    74 %

**Schon die mildeste Stufe haette 4 von 57 Stellen verworfen, auf die
sich der Mensch tatsaechlich beworben hat.** Deshalb steht diese Zahl
neben jeder Stufe — "wie viele bleiben sichtbar" allein zeigt nur die
eine Haelfte der Rechnung.

## Was hier NICHT gerechnet wird

Die Quantile kommen aus `score_verteilung._quantil` und die Werte aus
`fachwert._fachwerte`. Eine eigene Fassung waere das Muster, das dieses
Projekt vierzehnmal gekostet hat (#963) — und die Stufen muessen
dieselbe Rechnung benutzen wie der Fachdaumen und der Backtest, sonst
schlaegt der Backtest einen Wert vor, den keine Stufe trifft.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Die Bereiche, in denen eine Schwelle wirkt. Zwei verschiedene Dinge,
#: und ihre Verwechslung war schon #1008.
SPEICHERN = "speichern"
LISTE = "liste"
BEREICHE = (SPEICHERN, LISTE)

_EINSTELLUNG = {
    SPEICHERN: "schwelle_stufe_speichern",
    LISTE: "schwelle_stufe_liste",
}

#: Die Vorgabe. Bewusst die unterste (#1063): lieber zu viel sehen und
#: von Hand aussortieren, als nicht zu erfahren, dass es eine Stelle gab.
VORGABE = "alles_zeigen"

#: Die Stufen in ihrer Reihenfolge. `quelle` sagt, WORAUS sich der Wert
#: ergibt — eine Stufe ohne nachrechenbare Herkunft waere eine
#: Behauptung (dieselbe Regel wie bei den Reglerzonen in #892).
STUFEN = (
    {"schluessel": "alles_zeigen", "name": "Alles zeigen",
     "bedeutung": "Nichts wird ausgeblendet.",
     "quelle": None},
    {"schluessel": "offensichtliches_aus", "name": "Offensichtliches aus",
     "bedeutung": "Klare Fehlgriffe verschwinden.",
     "quelle": ("aussortiert", 0.5, "Median der aussortierten Stellen")},
    {"schluessel": "locker", "name": "Locker",
     "bedeutung": "Was du ueblicherweise wegklickst, bleibt draussen.",
     "quelle": ("aussortiert", 0.75,
                "oberes Viertel der aussortierten Stellen")},
    {"schluessel": "ausgewogen", "name": "Ausgewogen",
     "bedeutung": "Etwa das Niveau deiner schwaecheren Bewerbungen.",
     "quelle": ("beworben", 0.25, "unteres Viertel deiner Bewerbungen")},
    {"schluessel": "streng", "name": "Streng",
     "bedeutung": "Etwa das Niveau deiner mittleren Bewerbungen.",
     "quelle": ("beworben", 0.5, "Median deiner Bewerbungen")},
    {"schluessel": "nur_volltreffer", "name": "Nur Volltreffer",
     "bedeutung": "Nur das obere Viertel dessen, worauf du dich beworben hast.",
     "quelle": ("beworben", 0.75, "oberes Viertel deiner Bewerbungen")},
)

SCHLUESSEL = tuple(s["schluessel"] for s in STUFEN)

#: Ab wie vielen Werten eine Verteilung eine Stufe tragen kann —
#: dieselbe Grenze wie beim Fachdaumen (#1052). Darunter gibt es nur
#: "Alles zeigen", und PBP sagt warum.
MIN_WERTE = 20


def _quantil(sortiert: list, anteil: float) -> float:
    from .score_verteilung import _quantil as _q
    return _q(sortiert, anteil)


def _werte(db) -> tuple[list, list]:
    """(beworben, aussortiert) — ueber den Dienst, nicht ueber eigenes SQL.

    `applications.job_hash` traegt den oeffentlichen Hash, `jobs.hash`
    den profil-praefixierten; eigenes SQL laeuft dort zuverlaessig in
    die falsche Menge.
    """
    from . import fachwert
    try:
        return (sorted(fachwert._fachwerte(db, beworben=True)),
                sorted(fachwert._fachwerte(db, beworben=False)))
    except Exception as exc:  # pragma: no cover — nie einen Lauf kippen
        logger.debug("Werte fuer die Stufen nicht lesbar: %s", exc)
        return [], []


def stufen(db) -> dict:
    """Die sechs Stufen mit ihren heutigen Werten und Folgen.

    Returns:
        {"stufen": [...], "belastbar": bool, "grund": str|None}

        Je Stufe: schluessel, name, bedeutung, wert, herkunft,
        `sichtbar` (von `gesamt` aktiven Stellen) und
        `bewerbungen_darunter` — die Kostenseite.
    """
    beworben, aussortiert = _werte(db)
    quellen = {"beworben": beworben, "aussortiert": aussortiert}
    belastbar = (len(beworben) >= MIN_WERTE
                 and len(aussortiert) >= MIN_WERTE)

    try:
        aktiv = [float(j.get("score") or 0) for j in db.get_active_jobs()]
    except Exception:  # pragma: no cover
        aktiv = []

    ergebnis = []
    hoechster = 0.0
    for s in STUFEN:
        eintrag = {"schluessel": s["schluessel"], "name": s["name"],
                   "bedeutung": s["bedeutung"]}
        if s["quelle"] is None:
            eintrag.update({"wert": 0.0, "herkunft": "Keine Schwelle."})
        elif not belastbar:
            eintrag.update({
                "wert": None,
                "herkunft": s["quelle"][2],
                "nicht_berechenbar": True,
            })
            ergebnis.append(eintrag)
            continue
        else:
            topf, anteil, text = s["quelle"]
            roh = _quantil(quellen[topf], anteil)
            # Die Stufen muessen steigen. Ob die vorgeschlagenen Quellen
            # das hergeben, haengt am Bestand: ueberlappen Bewerbungen
            # und Aussortierte stark, kaeme "Locker" ueber "Ausgewogen"
            # zu liegen. Auf der gemessenen Kopie passt die Reihenfolge,
            # garantiert ist sie nicht.
            wert = max(roh, hoechster)
            eintrag.update({"wert": wert, "herkunft": text})
            if wert > roh:
                eintrag["angehoben_auf_vorstufe"] = round(roh, 1)
        hoechster = eintrag["wert"] or 0.0
        grenze = eintrag["wert"] or 0.0
        eintrag["sichtbar"] = sum(1 for x in aktiv if x >= grenze)
        # Die Kostenseite: wie viele Stellen, auf die du dich BEWORBEN
        # hast, haette diese Stufe verworfen? Ohne sie zeigt die Stufe
        # nur, was sie wegnimmt, nicht was sie kostet.
        eintrag["bewerbungen_darunter"] = sum(1 for x in beworben
                                              if x < grenze)
        ergebnis.append(eintrag)

    antwort = {
        "stufen": ergebnis,
        "gesamt_aktiv": len(aktiv),
        "bewerbungen_bewertbar": len(beworben),
        "aussortierte": len(aussortiert),
        "belastbar": belastbar,
    }
    if not belastbar:
        antwort["grund"] = (
            f"Fuer berechnete Stufen braucht es mindestens {MIN_WERTE} "
            f"bewertbare Bewerbungen und {MIN_WERTE} aussortierte Stellen; "
            f"vorhanden sind {len(beworben)} und {len(aussortiert)}. "
            "Solange bleibt es bei 'Alles zeigen' — eine Stufe aus einer "
            "Handvoll Werte waere geraten.")
    return antwort


def gewaehlte_stufe(db, bereich: str) -> str:
    """Die gespeicherte Stufe eines Bereichs, sonst die Vorgabe."""
    if bereich not in BEREICHE:
        raise ValueError(f"Unbekannter Bereich: {bereich}")
    try:
        wert = db.get_profile_setting(_EINSTELLUNG[bereich], None)
    except Exception:  # pragma: no cover
        wert = None
    return wert if wert in SCHLUESSEL else VORGABE


def stufe_setzen(db, bereich: str, schluessel: str) -> dict:
    """Setzt die Stufe — und sagt, was sie bedeutet."""
    if bereich not in BEREICHE:
        return {"fehler": f"Unbekannter Bereich '{bereich}'. "
                          f"Moeglich: {', '.join(BEREICHE)}."}
    if schluessel not in SCHLUESSEL:
        return {"fehler": f"Unbekannte Stufe '{schluessel}'. "
                          f"Moeglich: {', '.join(SCHLUESSEL)}."}
    db.set_profile_setting(_EINSTELLUNG[bereich], schluessel)
    befund = stufen(db)
    eintrag = next(s for s in befund["stufen"]
                   if s["schluessel"] == schluessel)
    return {"status": "gesetzt", "bereich": bereich, "stufe": eintrag,
            "belastbar": befund["belastbar"]}


def wert_fuer(db, bereich: str) -> float:
    """Die Zahl, gegen die gerechnet wird — aus der gewaehlten Stufe.

    Das ist das Nadeloehr: wer die Schwelle braucht, fragt hier. Beide
    Leser (Suchlauf und Listenfilter) gehen darueber, damit eine
    Aenderung an den Gewichten die STUFE nicht verschiebt (AK 5).
    """
    schluessel = gewaehlte_stufe(db, bereich)
    if schluessel == VORGABE:
        return 0.0
    try:
        eintrag = next(s for s in stufen(db)["stufen"]
                       if s["schluessel"] == schluessel)
    except StopIteration:  # pragma: no cover
        return 0.0
    return float(eintrag.get("wert") or 0.0)


#: Wo festgehalten wird, was die Umstellung vorgefunden hat. Ein
#: gesetzter Wert darf nicht still verschwinden (#1053, #211) — der
#: Hinweis nennt die alte Zahl und die Stufe, auf der sie jetzt liegt.
BELEG = "schwellen_stufen_umstellung"


def umstellen(db) -> dict:
    """Bestehende Zahlen einmalig auf die naechstliegende Stufe (AK 6).

    Idempotent: ist fuer einen Bereich schon eine Stufe gesetzt, bleibt
    sie. Wer nie eine Schwelle gesetzt hatte, merkt von der Umstellung
    nichts — er steht ohnehin auf "Alles zeigen".
    """
    from .schwellen_umstellung import gesetzte_schwellen
    ergebnis = {"umgestellt": [], "unveraendert": []}
    try:
        zahlen = gesetzte_schwellen(db)
    except Exception as exc:  # pragma: no cover
        logger.debug("Alte Schwellen nicht lesbar: %s", exc)
        return ergebnis

    paare = ((SPEICHERN, zahlen.get("min_score_schwelle") or 0),
             (LISTE, zahlen.get("auto_ignore") or 0))
    for bereich, zahl in paare:
        if gewaehlte_stufe(db, bereich) != VORGABE:
            ergebnis["unveraendert"].append(bereich)
            continue
        if not zahl or zahl <= 0:
            continue
        schluessel = naechste_stufe(db, zahl)
        if schluessel == VORGABE:
            # Es gibt noch keine berechenbaren Stufen. Dann wird NICHT
            # auf "Alles zeigen" umgestellt — das waere ein stilles
            # Abschalten der gesetzten Schwelle.
            ergebnis["unveraendert"].append(bereich)
            continue
        db.set_profile_setting(_EINSTELLUNG[bereich], schluessel)
        ergebnis["umgestellt"].append(
            {"bereich": bereich, "zahl_vorher": float(zahl),
             "stufe": schluessel})

    if ergebnis["umgestellt"]:
        try:
            alt = db.get_profile_setting(BELEG, None) or []
            db.set_profile_setting(BELEG, list(alt) + ergebnis["umgestellt"])
        except Exception as exc:  # pragma: no cover
            logger.debug("Umstellungs-Beleg nicht schreibbar: %s", exc)
    return ergebnis


def naechste_stufe(db, zahl) -> str:
    """Welche Stufe liegt einer gespeicherten Zahl am naechsten? (AK 6)

    Fuer die Umstellung: eine gesetzte 7 soll nicht verschwinden,
    sondern zu der Stufe werden, die ihr entspricht.
    """
    try:
        zahl = float(zahl or 0)
    except (TypeError, ValueError):
        return VORGABE
    if zahl <= 0:
        return VORGABE
    kandidaten = [s for s in stufen(db)["stufen"] if s.get("wert") is not None]
    if not kandidaten:
        return VORGABE
    return min(kandidaten, key=lambda s: abs(s["wert"] - zahl))["schluessel"]
