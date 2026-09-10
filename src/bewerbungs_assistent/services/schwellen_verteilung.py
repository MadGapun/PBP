"""Der Schwellenregler kommt aus der Verteilung, nicht aus einer festen Zahl (#892).

**Nicht zu verwechseln mit `score_verteilung.py` (#986).** Das Modul
dort beantwortet: "welchen Score hatten die Stellen, auf die ich mich
BEWORBEN habe" — eine Kennzahl ueber das eigene Urteil. Dieses hier
beantwortet: "wie sind die Scores im BESTAND verteilt" — die Grundlage
fuer den Schwellenregler. Zwei Fragen, zwei Module; der aehnliche Name
hat beim Bauen bereits einmal zum Ueberschreiben gefuehrt (die Lehre
aus #799, wo `learned_insights` neben `learning_insights` entstand).

Zwei Befunde des Melders, und beide sind nachgemessen.

## Befund 1 — der Regler deckt die Skala nicht ab

Er liess sich nur bis 20 setzen. Gemessen am 10.09.2026 ueber 2.491
Stellen: **Median 1, p90 23, Maximum 110.** Der Regler erreichte damit
nicht einmal das oberste Zehntel und war praktisch wirkungslos.

Der Grund fuer die Spannweite ist bekannt: `total_score` ist keine
Prozentzahl, sondern eine Punktsumme, deren Obergrenze aus der LAENGE
der MUSS-Liste folgt (#999). Eine feste Reglergrenze kann es deshalb
gar nicht geben — sie haengt am Profil.

## Befund 2 — die Empfehlung stuetzt sich auf den falschen Score

Viele Scores entstehen erst NACH dem Nachladen der Beschreibung. Der
belegte Fall des Melders: eine Stelle ging **0 -> 72 -> 75**, waehrend
der Text nachwuchs. Bei Schwelle 70 waere sie im Zustand 0 unsichtbar
gewesen und haette die Detailanalyse nie erreicht.

**Teilwiderspruch, und er gehoert dazu:** ueber den GANZEN Bestand
gemessen liegt der Median MIT Anzeigentext (0,0) sogar unter dem ohne
(1,0). Das ist kein Gegenbeweis, sondern eine andere Frage — das
MUSS-Tor setzt fachfremde Anzeigen mit Text sauber auf 0, waehrend
textlose einen Titeltreffer behalten. Der Einzelfall des Melders bleibt
richtig; nur die Aggregatzahl sagt ihn nicht.

## Warum die Empfehlung trotzdem den Erst-Score braucht

Weil `min_score_schwelle` beim SPEICHERN filtert (#1008) — die Zahl,
gegen die sie wirkt, ist der Wert bei der Anlage. Eine Empfehlung aus
den heutigen Scores empfiehlt also gegen die falsche Verteilung.

`jobs.initial_score` gab es nicht, folglich gibt es auch keinen
historischen Vergleich — dieselbe Lage wie bei #1003 AK 3. Ab jetzt
wird er geschrieben; die Messung wird damit kuenftig moeglich, statt
weiter geraten zu werden. Fuer den Altbestand steht der aktuelle Wert
drin, **ausdruecklich als rekonstruiert gekennzeichnet**: ein
rekonstruierter Wert, der wie ein gemessener aussieht, waere #987.
"""
from __future__ import annotations

import logging
import statistics

logger = logging.getLogger(__name__)

# Unter so wenigen Stellen ist eine Verteilung keine Verteilung. Dann
# faellt der Regler auf einen festen Bereich zurueck und SAGT das —
# eine aus vier Werten errechnete Empfehlung waere Scheingenauigkeit.
MIN_STELLEN = 20
RUECKFALL_MAX = 20.0


def verteilung(db, *, nur_aktive: bool = True) -> dict:
    """Die Score-Verteilung, aus der sich der Regler ableitet.

    Returns:
        dict mit `min`, `median`, `p90`, `max`, `anzahl`, den drei
        Farbgrenzen und `belastbar`. Bei zu wenigen Stellen steht
        `belastbar: False` und der Rueckfallbereich — mit Begruendung.
    """
    zeilen = _werte(db, nur_aktive=nur_aktive)
    # #892: gerechnet wird gegen die ERST-Scores, weil die Schwelle beim
    # Speichern wirkt (#1008). Wo keiner steht, traegt der aktuelle Wert
    # — gekennzeichnet, siehe `rekonstruiert`.
    werte = sorted(z["wert"] for z in zeilen)
    rekonstruiert = sum(1 for z in zeilen if z["rekonstruiert"])

    if len(werte) < MIN_STELLEN:
        return {
            "belastbar": False,
            "anzahl": len(werte),
            "min": 0.0,
            "max": RUECKFALL_MAX,
            "median": None,
            "empfehlung": None,
            "grund": (
                f"Nur {len(werte)} Stellen im Bestand — unter {MIN_STELLEN} "
                "ergibt eine Verteilung keine belastbare Empfehlung. Der "
                f"Regler laeuft solange von 0 bis {RUECKFALL_MAX:g}."),
        }

    median = statistics.median(werte)
    p90 = werte[int(len(werte) * 0.9)]
    hoechst = werte[-1]
    # Die Reglergrenze liegt am tatsaechlichen Hoechstwert, aufgerundet.
    # Sie fest zu setzen war der gemeldete Fehler.
    obergrenze = float(max(RUECKFALL_MAX, hoechst))

    return {
        "belastbar": True,
        "anzahl": len(werte),
        "min": float(werte[0]),
        "median": float(median),
        "p90": float(p90),
        "max": float(hoechst),
        "regler_max": obergrenze,
        "empfehlung": float(median),
        "rekonstruierte_werte": rekonstruiert,
        "zonen": _zonen(median, p90, obergrenze),
        # #892 AK 7: wie viele Stellen bei welcher Einstellung sichtbar
        # blieben — je ganzem Schritt. Der Regler soll den Satz zeigen,
        # ohne bei jeder Bewegung nachzufragen; die RECHNUNG bleibt
        # trotzdem hier, der Client liest nur ab. Eine Zaehlschleife im
        # JavaScript waere eine zweite Fassung derselben Regel.
        "sichtbar_ab": _leiter(werte, obergrenze),
        "grundlage": (
            "Erst-Scores (Wert beim Speichern). Die Schwelle wirkt beim "
            "Speichern, nicht in der Liste — deshalb ist das die "
            "richtige Verteilung."
            if rekonstruiert < len(werte) else
            "Aktuelle Scores, weil fuer den Altbestand kein Erst-Score "
            "vorliegt. Ab dieser Version wird er mitgeschrieben; die "
            "Empfehlung wird damit mit der Zeit genauer."),
    }


def _leiter(werte: list, obergrenze: float) -> list:
    """[Schwelle, Anzahl sichtbarer Stellen] je ganzem Schritt."""
    leiter = []
    hoechste = int(obergrenze) + 1
    for schwelle in range(0, hoechste + 1):
        leiter.append([schwelle, sum(1 for v in werte if v >= schwelle)])
    return leiter


def _zonen(median: float, p90: float, obergrenze: float) -> list:
    """Die drei Farbbereiche des Reglers.

    Die Grenzen sind nachrechenbar und stehen als Zahlen dabei — eine
    Farbe ohne nachvollziehbare Grenze ist eine Behauptung.
    """
    return [
        {"farbe": "gruen", "von": 0.0, "bis": round(median, 1),
         "bedeutung": ("Bis zum Median geht nichts Relevantes verloren — "
                       "die Haelfte aller Stellen liegt darueber.")},
        {"farbe": "gelb", "von": round(median, 1), "bis": round(p90, 1),
         "bedeutung": ("Hier fallen einzelne Stellen weg, die nach dem "
                       "Nachladen der Beschreibung hoeher laegen.")},
        {"farbe": "rot", "von": round(p90, 1), "bis": round(obergrenze, 1),
         "bedeutung": ("Oberhalb des obersten Zehntels — hier werden "
                       "systematisch gute Stellen aussortiert.")},
    ]


def wirkung(db, schwelle: float, *, nur_aktive: bool = True) -> dict:
    """Was diese Einstellung konkret bedeutet — in Klartext.

    Eine Zahl am Regler sagt nichts. "Bei 35 bleiben 128 von 340
    sichtbar" schon.
    """
    zeilen = _werte(db, nur_aktive=nur_aktive)
    gesamt = len(zeilen)
    if not gesamt:
        return {"text": "Noch keine Stellen im Bestand.", "sichtbar": 0,
                "gesamt": 0}
    grenze = float(schwelle or 0)
    sichtbar = sum(1 for z in zeilen if z["wert"] >= grenze)
    text = (f"Bei {grenze:g} bleiben {sichtbar} von {gesamt} Stellen "
            "sichtbar.")
    if sichtbar == 0:
        text += (" Also KEINE — die Schwelle liegt ueber dem hoechsten "
                 "vorkommenden Score.")
    elif sichtbar == gesamt:
        text += " Also alle — diese Schwelle filtert nichts."
    return {"text": text, "sichtbar": sichtbar, "gesamt": gesamt,
            "schwelle": grenze}


def _werte(db, *, nur_aktive: bool = True) -> list:
    """Je Stelle der Erst-Score — oder ersatzweise der aktuelle."""
    frage = ("SELECT COALESCE(score, 0) AS score, initial_score, "
             "initial_score_rekonstruiert FROM jobs")
    if nur_aktive:
        frage += " WHERE is_active=1"
    try:
        zeilen = db.connect().execute(frage).fetchall()
    except Exception as exc:  # pragma: no cover — Spalten fehlen noch
        logger.debug("Verteilung nicht lesbar: %s", exc)
        return []
    ergebnis = []
    for z in zeilen:
        roh = z["initial_score"]
        if roh is None:
            ergebnis.append({"wert": float(z["score"] or 0),
                             "rekonstruiert": True})
        else:
            ergebnis.append({"wert": float(roh),
                             "rekonstruiert": bool(
                                 z["initial_score_rekonstruiert"])})
    return ergebnis
