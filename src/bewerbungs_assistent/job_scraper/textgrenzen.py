"""Wo eine Laengenbegrenzung fuer Anzeigentexte hingehoert (#952, v1.7.23).

Bis v1.7.22 kappte **jeder** Quellen-Adapter den Anzeigentext bei 2000
Zeichen, bevor er gespeichert wurde — 38 Stellen in 26 Adaptern. Die
Begrenzung sass damit in der **Ablage** statt in der **Ausgabe**, und
das ist die falsche Ebene:

Stellenanzeigen sind fast durchgaengig gleich aufgebaut —
Unternehmensvorstellung, Aufgaben, Anforderungen, Benefits. Der
laengste und informationsaermste Teil steht vorn. Eine Kappung nach
2000 Zeichen schneidet deshalb bevorzugt genau das ab, was ueber die
Passung entscheidet: Abschluss, Berufsjahre, Sprachen, Arbeitsmodell,
Befristung.

Die Folgen reichten weit: das MUSS-Tor (#940) sah nur den halben Text,
die Ausschluss-Keywords ebenso, `fit_analyse` begruendete ihr Urteil
mit Keywords, die im gekappten Bereich gestanden haben konnten, und der
Auto-Refetch (#622) holte zuverlaessig immer wieder denselben halben
Text. Nichts davon war sichtbar — der Fehler meldete `status: ok`.

Seit v1.7.22 wiegt das schwerer, nicht leichter: das praezisere Tor hat
einen unbeabsichtigten Puffer entfernt. Vorher konnte ein zerstreuter
Wortfund im vorderen Teil eine Stelle noch durchtragen, deren echtes
Fachsignal hinter Zeichen 2000 stand.

Deshalb hier zwei getrennte Groessen:

* `SPEICHER_MAX` — reine Notbremse gegen entartete Seiten, nicht gegen
  lange Anzeigen. Eine ausfuehrliche Stellenanzeige liegt bei 4.000 bis
  8.000 Zeichen; 200.000 erreicht keine, wohl aber eine Seite, die
  versehentlich ihr komplettes Menue mitliefert.
* `AUSGABE_MAX` — was eine MCP-Antwort zeigt. Diese Begrenzung ist
  berechtigt und bleibt; sie darf nur nicht die Datenhaltung bestimmen.
"""
from __future__ import annotations

# Notbremse fuer die Ablage. Bewusst weit oberhalb jeder realen Anzeige.
SPEICHER_MAX = 200_000

# Was eine Antwort zeigt (die alte Speicher-Grenze, jetzt an der
# richtigen Stelle).
AUSGABE_MAX = 2000

# Die historische Kappungsgrenze. Ein Bestandstext von exakt dieser
# Laenge ist mit an Sicherheit grenzender Wahrscheinlichkeit gekappt:
# dass eine Anzeige zufaellig auf genau 2000 Zeichen endet, kommt
# praktisch nicht vor.
ALTE_KAPPUNG = 2000


def fuer_speicher(text) -> str:
    """Anzeigentext fuer die Ablage — vollstaendig, nur mit Notbremse."""
    if not text:
        return ""
    return str(text)[:SPEICHER_MAX]


def fuer_ausgabe(text, grenze: int = AUSGABE_MAX) -> str:
    """Anzeigentext fuer eine Antwort — hier ist Kuerzen richtig."""
    if not text:
        return ""
    return str(text)[:grenze]


def ist_gekappt(text) -> bool:
    """True, wenn ein Text die historische Grenze exakt trifft.

    Bewusst als Berechnung beim Lesen statt als Spalte: der Bestand
    traegt kein Kennzeichen, und eine Migration koennte es nicht
    nachtraeglich wissen. Die Laenge ist der Beleg.
    """
    if not text:
        return False
    return len(str(text)) == ALTE_KAPPUNG


def kappungs_hinweis(text) -> str:
    """Erklaerender Satz fuer Tool-Antworten, sonst leer."""
    if not ist_gekappt(text):
        return ""
    return (
        f"Der gespeicherte Anzeigentext ist exakt {ALTE_KAPPUNG} Zeichen "
        "lang und damit sehr wahrscheinlich abgeschnitten (Altbestand vor "
        "v1.7.23). Der Anforderungsteil steht meist am Ende und fehlt "
        "dann. Mit stellenbeschreibung_nachladen() laesst er sich "
        "vollstaendig holen."
    )
