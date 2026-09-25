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
* `AUSGABE_NOTBREMSE` — was eine MCP-Antwort hoechstens traegt.

v1.7.122 (#1064) hat die zweite Groesse korrigiert. Bis dahin stand
dort 2000 — dieselbe Zahl wie die alte Speicher-Kappung, und damit
setzte die Ausgabe genau den Fehler fort, den #952 in der Ablage behoben
hatte: `fit_analyse` lieferte den Anzeigentext nach 2000 Zeichen
abgeschnitten, mitten im Wort, und **nichts in der Antwort sagte es**.
Seit #1003/#1007 ist die Detailanalyse der einzige Weg zu einem
gespeicherten Urteil — gefaellt wurde es also ueber Aufgaben statt ueber
Anforderungen.

Gemessen am Bestand (2.271 Anzeigen mit Text, 21.09.2026): die laengste
hat 11.741 Zeichen, keine erreicht 12.000. Und bei **29,5 %** der
Anzeigen ueber 2.000 Zeichen beginnt der Anforderungsteil ERST hinter
der alten Grenze. Die Notbremse liegt deshalb bei 20.000: kein realer
Text kommt ihr nahe, eine Seite mit mitgeliefertem Menue schon.

Und wenn sie doch greift, dann sichtbar. `ausgabe()` gibt den Befund
mit heraus, statt ihn dem Aufrufer zu ueberlassen — eine stille
Kuerzung ist teurer als eine fehlende (#989).
"""
from __future__ import annotations

# Notbremse fuer die Ablage. Bewusst weit oberhalb jeder realen Anzeige.
SPEICHER_MAX = 200_000

# Notbremse fuer eine Antwort. Ebenfalls oberhalb jeder realen Anzeige —
# sie soll entartete Seiten abfangen, nicht lange Stellenanzeigen.
AUSGABE_NOTBREMSE = 20_000

# Die historische Kappungsgrenze. Ein Bestandstext von exakt dieser
# Laenge ist mit an Sicherheit grenzender Wahrscheinlichkeit gekappt:
# dass eine Anzeige zufaellig auf genau 2000 Zeichen endet, kommt
# praktisch nicht vor.
ALTE_KAPPUNG = 2000

# v1.7.109 (#1048): Kappungen EINZELNER Quellen, die #952 nicht erfasst
# hat. Die Quelle `hays` schnitt die Beschreibung bei 500 Zeichen ab —
# gemessen an einer Bestandskopie 48 von 48 Stellen exakt 500, live 8 von 8
# Anzeigen zwischen 1.527 und 3.311 Zeichen lang. Die Grenze gilt nur fuer
# ihre Quelle: 500 Zeichen sind bei jeder anderen Quelle eine gewoehnliche
# kurze Anzeige, und sie als gekappt zu fuehren waere ein Fehlalarm (#929).
QUELLEN_KAPPUNG = {"hays": 500}


def fuer_speicher(text) -> str:
    """Anzeigentext fuer die Ablage — vollstaendig, nur mit Notbremse."""
    if not text:
        return ""
    return str(text)[:SPEICHER_MAX]


def ausgabe(text, ab: int = 0,
            grenze: int = AUSGABE_NOTBREMSE) -> tuple[str, dict]:
    """Anzeigentext fuer eine Antwort — zusammen mit dem Befund darueber.

    Gibt `(stueck, befund)` zurueck. Der Befund nennt immer die
    Gesamtlaenge und das Gelieferte; ist etwas abgeschnitten, nennt er
    ausserdem den Weg zum Rest.

    Die Bauform ist Absicht: bis v1.7.121 gab es eine Funktion, die
    nur den gekuerzten Text lieferte, und der Aufrufer musste von sich
    aus daran denken, die Kuerzung zu melden. Er hat es nicht getan
    (#1064). Wer hier den Text bekommt, bekommt den Befund mit.
    """
    voll = str(text or "")
    ab = max(0, int(ab or 0))
    stueck = voll[ab:ab + grenze]
    befund = {
        "zeichen_gesamt": len(voll),
        "zeichen_geliefert": len(stueck),
        "ab_zeichen": ab,
        "vollstaendig": ab == 0 and len(stueck) == len(voll),
    }
    if not befund["vollstaendig"]:
        weiter = ab + len(stueck)
        befund["gekuerzt"] = True
        if weiter < len(voll):
            befund["weiter_ab_zeichen"] = weiter
            befund["hinweis"] = (
                f"Dieser Anzeigentext ist {len(voll)} Zeichen lang; "
                f"geliefert sind die Zeichen {ab} bis {weiter}. Der "
                "Anforderungsteil steht meist am Ende. Hole den Rest mit "
                f"fit_analyse(hash, beschreibung_ab={weiter}), BEVOR du "
                "ein Urteil mit stelle_urteil_speichern() festhaeltst."
            )
        else:
            befund["hinweis"] = (
                f"Geliefert sind die Zeichen {ab} bis {weiter} von "
                f"{len(voll)}; der Anfang fehlt. Mit "
                "fit_analyse(hash) kommt er zurueck."
            )
    return stueck, befund


def kappungs_grenze(text, quelle=None) -> int | None:
    """Die Grenze, an der ein Text abgeschnitten wurde — sonst None.

    Die allgemeine Grenze aus #952 gilt fuer jede Quelle, eine Grenze aus
    `QUELLEN_KAPPUNG` nur fuer ihre eigene (#1048). Ohne Quelle wird nur
    die allgemeine geprueft — genau das Verhalten bis v1.7.108.
    """
    if not text:
        return None
    laenge = len(str(text))
    if laenge == ALTE_KAPPUNG:
        return ALTE_KAPPUNG
    grenze = QUELLEN_KAPPUNG.get(str(quelle or "").strip().lower())
    if grenze and laenge == grenze:
        return grenze
    return None


def ist_gekappt(text, quelle=None) -> bool:
    """True, wenn ein Text eine bekannte Kappungsgrenze exakt trifft.

    Bewusst als Berechnung beim Lesen statt als Spalte: der Bestand
    traegt kein Kennzeichen, und eine Migration koennte es nicht
    nachtraeglich wissen. Die Laenge ist der Beleg — bei einer
    quellen-eigenen Grenze zusammen mit der Quelle.
    """
    return kappungs_grenze(text, quelle) is not None


def kappungs_hinweis(text, quelle=None) -> str:
    """Erklaerender Satz fuer Tool-Antworten, sonst leer."""
    grenze = kappungs_grenze(text, quelle)
    if grenze is None:
        return ""
    herkunft = ("Altbestand vor v1.7.23" if grenze == ALTE_KAPPUNG
                else "die Quelle kappte bis v1.7.108")
    return (
        f"Der gespeicherte Anzeigentext ist exakt {grenze} Zeichen "
        f"lang und damit sehr wahrscheinlich abgeschnitten ({herkunft}). "
        "Der Anforderungsteil steht meist am Ende und fehlt "
        "dann. Mit stellenbeschreibung_nachladen() laesst er sich "
        "vollstaendig holen."
    )
