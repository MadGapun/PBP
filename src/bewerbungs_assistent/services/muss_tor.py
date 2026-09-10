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

## Die Vorgabe wird ABGELEITET, nicht gesetzt (v1.7.69)

Die erste Fassung dieses Moduls hatte `hart` fest als Vorgabe, und die
Begruendung stand unten: gemessen am Bestand EINES Nutzers. Der
Einwand dagegen war berechtigt — **eine Voreinstellung, die an einem
fremden Lebenslauf kalibriert wurde, ist fuer alle anderen geraten.**
Fuer die Pflegekraft aus dem Issue ist `hart` schlicht falsch.

Der Unterschied zwischen beiden Faellen ist aber benennbar, und PBP
kann ihn selbst entscheiden:

* Nennen die Pflichtbegriffe **Techniken** ("PLM", "SAP", "Python"),
  ist ihr Fehlen ein echter Beleg fuer ein anderes Fachgebiet -> `hart`.
* Nennen sie einen **Beruf** ("Pflegefachkraft", "Erzieherin"), sagt
  ihr Fehlen wenig, weil derselbe Beruf viele Namen hat -> `gewichtet`.

Entschieden wird an der Schwelle, die seit v1.7.36 (#987) die
Alternativbezeichnungen absichert und dort GEMESSEN wurde: ein Beruf
zieht die Berufs-Facette an sich (18-39 %), eine Technologie streut
(10-13 %). Die Einordnung entsteht aus derselben Netzabfrage wie die
Synonyme, wird abgelegt und ab da gelesen — ein Score darf nicht am
Netz haengen.

**Ein einziger Berufsbegriff genuegt fuer `gewichtet`.** Das Tor oeffnet,
sobald IRGENDEIN Pflichtbegriff trifft; gefaehrdet ist also der
Begriff, der umbenannt sein kann. Die Schieflage der Kosten zeigt in
dieselbe Richtung: `gewichtet` kostet hoechstens 50 zusaetzlich
abgelegte, markierte und nachrangig einsortierte Anzeigen je Lauf —
`hart` kostet im Zweifel den ganzen Beruf.

**`unbekannt` faellt auf `hart` zurueck**, also auf das bisherige
Verhalten. Das ist nicht dasselbe wie "Technik": ein Netzausfall darf
keine Voreinstellung setzen (#989). Und wer es ausdruecklich einstellt,
schlaegt die Ableitung immer.

## Was die Messung am Bestand wirklich hergab

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

Die Messung bleibt gueltig — sie sagt nur etwas anderes, als ich
zuerst daraus gemacht habe. Sie belegt, dass das Tor **bei einem
Technik-Profil** mit dem Urteil des Menschen uebereinstimmt, und genau
dafuer leitet die Regel oben jetzt `hart` ab. Was sie NICHT belegt, ist
eine Voreinstellung fuer alle anderen.

Ihr eigentlicher Ertrag war ein verworfener Entwurf: ein Rueckgriff auf
die KANN-Liste haette 1.539 der 1.900 Anzeigen zurueckgeholt, also fast
alle. Diese Zahl ist NICHT profilabhaengig — sie folgt aus der Laenge
einer typischen KANN-Liste (hier 83 Eintraege) und gilt fuer jeden.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

EINSTELLUNG = "muss_tor"

AUTOMATISCH = "automatisch"
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
    AUTOMATISCH: (
        "Vorgabe. PBP entscheidet anhand deiner Pflichtbegriffe: nennen "
        "sie Techniken, gilt 'hart'; nennen sie einen Beruf, gilt "
        "'gewichtet'. Laesst sich die Frage nicht beantworten, bleibt "
        "es bei 'hart' — also beim bisherigen Verhalten."),
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


def abgeleitet(arten: dict[str, str] | None) -> tuple[str, str]:
    """Welche Betriebsart folgt aus den Begriffsarten — und warum.

    Ein einziger BERUF unter den Pflichtbegriffen genuegt fuer
    `gewichtet`: das Tor oeffnet, sobald irgendein Begriff trifft, also
    ist der umbenennbare Begriff der gefaehrdete. `unbekannt` zaehlt
    NICHT als Technik — sonst setzte ein Netzausfall eine
    Voreinstellung (#989).

    Returns:
        `(betriebsart, begruendung)`. Die Begruendung geht in die
        Tool-Antwort: eine Vorgabe, die sich selbst setzt, muss sagen
        koennen warum.
    """
    arten = arten or {}
    berufe = sorted(k for k, v in arten.items() if v == "beruf")
    techniken = sorted(k for k, v in arten.items() if v == "technik")
    if berufe:
        return GEWICHTET, (
            (f"Einer deiner Pflichtbegriffe nennt einen Beruf "
             if len(berufe) == 1 else
             f"{len(berufe)} deiner Pflichtbegriffe nennen einen Beruf ")
            + f"({', '.join(berufe[:3])}"
            + (" …" if len(berufe) > 3 else "")
            + "). Derselbe Beruf heisst in vielen Anzeigen anders — "
              "sein Fehlen ist deshalb kein Beleg fuer ein anderes "
              "Fachgebiet.")
    if techniken:
        return HART, (
            f"Deine Pflichtbegriffe nennen Techniken "
            f"({', '.join(techniken[:3])}"
            + (" …" if len(techniken) > 3 else "")
            + "). Kommt eine davon in einer Anzeige nicht vor, ist das "
              "ein echter Beleg fuer ein anderes Fachgebiet.")
    return HART, (
        "Die Art deiner Pflichtbegriffe ist noch nicht bestimmt — es "
        "bleibt beim bisherigen Verhalten. Die Einordnung entsteht beim "
        "naechsten Suchlauf.")


def modus(db, criteria: dict | None = None) -> str:
    """Die geltende Betriebsart — eingestellt oder abgeleitet.

    Eine ausdrueckliche Einstellung schlaegt die Ableitung immer. Ohne
    sie entscheidet die Art der Pflichtbegriffe (siehe `abgeleitet`);
    das ist die Vorgabe und braucht keine Nutzeraktion.
    """
    try:
        wert = db.get_profile_setting(EINSTELLUNG, None)
    except Exception as exc:  # pragma: no cover — nie eine Suche stoppen
        logger.debug("MUSS-Tor-Modus nicht lesbar: %s", exc)
        return HART
    if wert in (HART, GEWICHTET):
        return wert
    # `automatisch`, nichts gesetzt oder Unsinn im Bestand: ableiten.
    arten = (criteria or {}).get("_muss_begriffsart")
    if arten is None:
        try:
            from . import scoring_kriterien
            arten = scoring_kriterien.gespeicherte_arten(db)
        except Exception as exc:  # pragma: no cover — nie eine Suche stoppen
            logger.debug("Begriffsarten nicht lesbar: %s", exc)
            arten = {}
    return abgeleitet(arten)[0]


def modus_setzen(db, wert: str) -> dict:
    """Setzt die Betriebsart; unbekannte Werte werden abgewiesen.

    Abgewiesen statt still auf die Vorgabe gekippt: ein Tippfehler, der
    als Erfolg gemeldet wird, ist die Bauform aus #980 und #988.
    """
    if wert not in MODI:
        return {"fehler": f"'{wert}' ist keine Betriebsart. Moeglich: "
                          + ", ".join(sorted(MODI))}
    db.set_profile_setting(EINSTELLUNG, wert)
    if wert == AUTOMATISCH:
        return {
            "status": "gesetzt",
            "muss_tor": wert,
            "bedeutet": MODI[wert],
            "gilt_jetzt": modus(db),
            "hinweis": ("PBP entscheidet ab jetzt selbst. Der aktuelle "
                        "Stand steht in suchkriterien_anzeigen."),
        }
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
