"""Kein Pflichttreffer — unsichtbar oder weit unten? (#968)

Das MUSS-Tor aus #940 fragt praezise, ob eine Anzeige ueberhaupt in
Frage kommt. Trifft kein einziger Pflichtbegriff, setzt es den Score auf
0 — und die Schwelle im Suchlauf verwirft die Stelle danach, sie wird
gar nicht erst gespeichert. Gemessen in #813: **312 von 389 Rohtreffern
starben so**, bevor ein Mensch sie gesehen hat.

Das Issue verlangt die Umkehr: kein Pflichttreffer soll *weit unten*
heissen, nicht *unsichtbar*.

## Warum ein blosses Weglassen des Tors nichts bewirkt

Der Fachscore ist zugleich das Tor UND die Bezugsgroesse des
Rahmen-Deckels (#942): `deckel = faktor * fachscore`. Ohne
Pflichttreffer ist der Fachscore 0, also auch der Deckel — der positive
Rahmen wird vollstaendig weggeschnitten und die Stelle landet wieder
bei 0. **Wer nur das `return 0` entfernt, aendert gar nichts.**

Deshalb ist die Gewichtung ein eigener, benannter Rechenweg: der Rahmen
darf sich ausdruecken, aber gedeckelt (`MAX_OHNE_MUSS`) und immer
nachrangig. Damit bleibt die Entscheidung aus #942 unangetastet — ein
Bonus ersetzt keine fachliche Passung, er ordnet nur innerhalb der
Gruppe, ueber die PBP fachlich nichts weiss.

## Warum die Vorgabe trotzdem `hart` bleibt

Gemessen am 09.09.2026 gegen den echten Bestand (2.491 Anzeigen, Kopie
im Temp-Verzeichnis):

* 1.900 Anzeigen oeffnen das Tor nicht,
* **1.402 davon (74 %) hat der Mensch selbst mit einem
  Ablehnungsgrund aussortiert**, ganz ueberwiegend
  `falsches_fachgebiet`,
* und 1.539 davon tragen mindestens einen KANN-Treffer.

Das Tor stimmt in diesem Bestand also mit dem Urteil des Menschen
ueberein, und ein Rueckgriff auf die KANN-Liste haette ausgerechnet die
fachfremden Anzeigen zurueckgeholt: 85 % aller Anzeigen tragen
irgendeinen KANN-Treffer, die Liste taugt nicht als Unterscheidung.

Die Vorgabe umzustellen haette diesem Nutzer rund 1.400 bereits
abgelehnte Anzeigen zurueck in die Liste gelegt. **Das Issue verlangt
die Gewichtung als Vorgabe; diese Messung spricht dagegen, und die
Entscheidung gehoert deshalb dem Menschen und nicht mir.** Beide
Betriebsarten sind gebaut, umschaltbar und dokumentiert — was fehlt,
ist allein die Voreinstellung.

Der Unterschied zwischen den beiden Beispielen ist dabei benennbar:
wessen Pflichtbegriffe **Techniken** nennen, dem sagt ihr Fehlen
wirklich etwas ("kommt in der Anzeige nicht vor" heisst dann "anderes
Fachgebiet"). Wessen Pflichtbegriffe einen **Beruf** nennen, dem sagt
ihr Fehlen wenig, weil derselbe Beruf viele Namen hat — das ist der
Fall aus dem Issue, und dafuer gibt es seit #969 die amtlichen
Alternativbezeichnungen. Die Gewichtung ist die Auffanglinie fuer
alles, was auch die nicht abdeckt.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

EINSTELLUNG = "muss_tor"

HART = "hart"
GEWICHTET = "gewichtet"

# Wieviel eine Stelle ohne Pflichttreffer hoechstens tragen darf, als
# Anteil dessen, was EIN Pflichttreffer wert ist.
#
# Der erste Entwurf nahm hier eine feste Zahl (5,0) — und der eigene
# Test hat ihn sofort widerlegt: mit genau einem MUSS-Begriff ist ein
# echter Treffer 2 Punkte wert und die Stelle kommt samt Rahmen-Deckel
# auf 3,0. Eine voellig fachfremde Anzeige haette also 5,0 getragen und
# damit MEHR als die passende. Das ist exakt die Umkehrung, gegen die
# #942 gebaut wurde — durch die Hintertuer wieder eingebaut. Dieselbe
# Falle wie der Nebenbefund aus v1.7.50 MERKE (5): bei einer kurzen
# MUSS-Liste ist der Fachscore so klein, dass jeder absolute Wert
# daneben zu gross ist.
#
# Deshalb relativ: hoechstens die HAELFTE eines einzelnen
# Pflichttreffers. Damit steht eine Stelle ohne Fachbezug immer unter
# einer mit — bei jeder Gewichtung, ohne dass jemand nachrechnen muss.
ANTEIL_EINES_TREFFERS = 0.5

# Absolute Obergrenze, falls jemand das MUSS-Gewicht sehr hoch dreht.
MAX_OHNE_MUSS = 5.0

# Wieviele solcher Stellen ein Suchlauf hoechstens behaelt. Ohne diese
# Grenze waere `gewichtet` eine unbegrenzte Ablage: im dokumentierten
# Lauf aus #813 waren es 312 in EINEM Durchgang. Eine stille Flut waere
# schlimmer als eine benannte Grenze — der Trichter sagt, wieviele
# uebrig blieben (#813, #989).
MAX_JE_LAUF = 50

MODI = {
    HART: (
        "Vorgabe. Ohne Pflichttreffer faellt die Stelle heraus — sie "
        "wird gar nicht erst gespeichert. Richtig, wenn die "
        "Pflichtbegriffe Techniken nennen: dann ist ihr Fehlen ein "
        "echter Beleg fuer ein anderes Fachgebiet."),
    GEWICHTET: (
        "Ohne Pflichttreffer steht die Stelle weit unten statt "
        "nirgends. Sie kann nie ueber einer Stelle mit Pflichttreffer "
        "stehen und traegt hoechstens die Haelfte dessen, was ein "
        "einzelner Pflichttreffer wert ist. Richtig, wenn die "
        "Pflichtbegriffe einen Beruf nennen — derselbe Beruf heisst in "
        "vielen Anzeigen anders."),
}


def modus(db) -> str:
    """Wie der Nutzer es eingestellt hat — Vorgabe `hart`."""
    try:
        wert = db.get_profile_setting(EINSTELLUNG, None)
    except Exception as exc:  # pragma: no cover — nie eine Suche stoppen
        logger.debug("MUSS-Tor-Modus nicht lesbar: %s", exc)
        return HART
    return wert if wert in MODI else HART


def modus_setzen(db, wert: str) -> dict:
    """Setzt die Betriebsart; unbekannte Werte werden abgewiesen.

    Abgewiesen statt still auf die Vorgabe gekippt: ein Tippfehler, der
    als Erfolg gemeldet wird, ist die Bauform aus #980 und #988.
    """
    if wert not in MODI:
        return {"fehler": f"'{wert}' ist keine Betriebsart. Moeglich: "
                          + ", ".join(sorted(MODI))}
    db.set_profile_setting(EINSTELLUNG, wert)
    return {
        "status": "gesetzt",
        "muss_tor": wert,
        "bedeutet": MODI[wert],
        "hinweis": (
            "Wirkt ab dem naechsten Suchlauf. Der gespeicherte Bestand "
            "aendert sich dadurch nicht — bereits verworfene Stellen "
            "sind weg und kommen nicht zurueck."
            if wert == GEWICHTET else
            "Wirkt ab dem naechsten Suchlauf. Bereits gespeicherte "
            "Stellen ohne Pflichttreffer bleiben stehen; "
            "scores_neu_berechnen() setzt sie auf 0."),
    }


def gewichtet_aktiv(criteria: dict | None) -> bool:
    """Rechnet dieser Lauf mit Gewichtung statt mit Ausschluss?

    Gelesen wird ausschliesslich aus den Kriterien — dort legt
    `scoring_kriterien.fuer_scoring` die Einstellung ab. Ein zweiter
    DB-Zugriff mitten in der Score-Berechnung waere genau die Bauform
    aus #987: derselbe Rechenweg mit verschiedenen Eingaben.
    """
    return (criteria or {}).get("_muss_tor_modus") == GEWICHTET


def obergrenze(muss_gewicht: float) -> float:
    """Wieviel eine Stelle ohne Pflichttreffer hoechstens tragen darf.

    Relativ zum Wert EINES Pflichttreffers, siehe
    `ANTEIL_EINES_TREFFERS`. Ist das Gewicht unbrauchbar, gilt die
    absolute Grenze — eine fehlende Angabe darf nie in einen
    unbegrenzten Wert kippen.
    """
    try:
        wert = float(muss_gewicht)
    except (TypeError, ValueError):
        return MAX_OHNE_MUSS
    if wert <= 0:
        return MAX_OHNE_MUSS
    return min(MAX_OHNE_MUSS, wert * ANTEIL_EINES_TREFFERS)


def ersatz_score(rahmen_plus: float, rahmen_minus: float,
                 muss_gewicht: float = 0) -> float:
    """Der Score einer Stelle ohne Pflichttreffer.

    Der Rahmen zaehlt ungedeckelt (es gibt keinen Fachscore, an dem man
    ihn relativieren koennte — dieselbe Ausnahme wie beim Kaltstart
    ohne MUSS-Liste), aber nach oben begrenzt: nie mehr als ein halber
    Pflichttreffer. Nach UNTEN gibt es keine Grenze ausser der Null —
    ein Malus muss die Stelle weiter druecken koennen (#942).
    """
    roh = float(rahmen_plus or 0) - float(rahmen_minus or 0)
    return round(max(0.0, min(obergrenze(muss_gewicht), roh)), 1)


def ohne_pflichttreffer(job: dict, criteria: dict | None) -> bool:
    """Traegt diese gespeicherte Stelle keinen Pflichttreffer?

    Fuer die Liste, also fuer Stellen aus der Datenbank. Gelesen wird
    der gespeicherte `fachscore` — er ist seit #1008 gemeinsam mit dem
    Gesamtscore geschrieben und damit die einzige Angabe, die zum
    gespeicherten Score passt. Den Text erneut gegen die Begriffe zu
    halten waere ein zweiter Rechenweg (#963).

    Ohne konfigurierte Pflichtbegriffe gibt es nichts zu verfehlen —
    dann ist die Antwort immer False (Kaltstart, #967).
    """
    muss = [k for k in ((criteria or {}).get("keywords_muss") or [])
            if str(k).strip()]
    if not muss:
        return False
    fach = job.get("fachscore")
    if fach is None:
        # Altbestand ohne Teilscores: eine Luecke gehoert benannt, nicht
        # gefuellt (#989). "Unbekannt" ist nicht "kein Treffer".
        return False
    try:
        return float(fach) <= 0
    except (TypeError, ValueError):
        return False


def sortierschluessel(job: dict, criteria: dict | None = None) -> int:
    """0 = mit Pflichttreffer, 1 = ohne.

    Das ist AK 4 des Issues, und es steht bewusst in der SORTIERUNG und
    nicht im Score: eine Stelle mit Pflichttreffer, die ein Malus nach
    unten gezogen hat, soll abstuerzen duerfen (#942) — sie darf dabei
    nur nicht unter eine Stelle rutschen, ueber deren Fach nichts
    bekannt ist. Dieselbe Bauform wie `datenguete.sortierschluessel`
    (#989).
    """
    return 1 if ohne_pflichttreffer(job, criteria) else 0


def marke(job: dict, criteria: dict | None = None) -> dict | None:
    """Was an der Zeile steht — oder None, wenn es einen Treffer gibt.

    AK 3: die Rangfolge muss nachvollziehbar bleiben. Eine Stelle, die
    ohne erkennbaren Grund unten steht, sieht aus wie ein Fehler.
    """
    if not ohne_pflichttreffer(job, criteria):
        return None
    return {
        "ohne_pflichttreffer": True,
        "text": "Kein Pflichtbegriff getroffen",
        "erklaerung": (
            "Keiner deiner MUSS-Begriffe kommt in dieser Anzeige vor. "
            "Sie steht deshalb hinter allen Stellen, die einen "
            "treffen."),
    }
