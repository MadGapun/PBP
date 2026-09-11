r"""Was in der Anzeige als Gehalt steht (#1018).

Die LESENDE Seite der Gehalts-Dimension. Das Gegenstueck ist
`services/gehalt_vergleich.py` (#1017), das aus einem gelesenen Wert
und den Wunschwerten ein Jahresaequivalent bildet. Hier geht es allein
um die Frage: **steht in diesem Text ueberhaupt ein Gehalt, und
welches?**

Gemeldet am 11.09.2026: "Teilzeit: 30-35 Stunden pro Woche" landete als
`salary_min 30 / salary_max 35 / stuendlich` in der Datenbank — und mit
`salary_estimated = 0`, galt also als BELEGT. Seit v1.7.78 verlieren
geschaetzte Gehaelter ihren Bonus im Score, belegte behalten ihn: eine
falsche Zahl mit vollem Vertrauen ist damit die teuerste verbliebene
Form.

## Am Bestand gemessen, und deutlicher als der Bericht

Ueber 1.337 Anzeigen mit Text (Kopie, Original nie angefasst):

| | |
|---|---|
| `stuendlich`-Treffer der alten Fassung | 12 |
| davon in Wahrheit ARBEITSZEITEN | **10** |
| echte Stundensaetze | 2 |

Der lehrreichste Fall trug beides im selben Satz: *"32-40h/Woche, 100%
Remote. Stundensatz: 60 EUR/h."* Genommen wurden die **32-40**. Die
Ursache steht im alten Muster: jeder Teil vor den Zahlen war optional,
ein Waehrungszeichen wurde nirgends verlangt, und als Nachsatz genuegte
das Wort "Stunde" — auf das "Stunden" ebenso passt.

Zwei weitere Befunde kamen aus derselben Messung und standen in keinem
Bericht:

**348 der 1.337 Beschreibungen tragen Markdown-Escapes** (`43\.933
\- 52\.962 € / Jahr`). Allein ihre Entschaerfung findet vier echte
Jahresgehaelter, die bis hierher verloren gingen.

**Monatsangaben gab es gar kein Muster.** Drei Anzeigen im Bestand
nennen ihr Gehalt monatlich — in Teilzeitanzeigen ist das die uebliche
Form, und der einzige belastbare Wert der Anzeige wurde verworfen,
waehrend die Arbeitszeit gespeichert wurde.

## Die Regel: ohne Waehrung kein Gehalt

Ein Kandidat zaehlt nur, wenn ein Waehrungszeichen oder ein
ausdrueckliches Rate-Wort (`Stundensatz`, `Tagessatz`, `Gehalt`) am
Treffer HAENGT — nicht irgendwo in der Naehe steht. Die Naehe genuegt
nicht, und das ist gemessen: im Fall oben stand `Stundensatz: 60 EUR/h`
keine zwanzig Zeichen neben der Arbeitszeit.

Damit loest sich auch der Vorrang von selbst: eine Arbeitszeit ohne
Waehrung ist gar kein Kandidat, also gewinnt das Gehalt daneben, ohne
dass irgendwo eine Rangfolge zwischen "Zahl mit Waehrung" und "Zahl
ohne" stehen muss.

## Monatsgehaelter werden umgerechnet, nicht als eigene Art gefuehrt

`salary_type` kennt drei Werte, und sie werden an rund zwanzig Stellen
ausgewertet. Ein vierter haette ueberall einen Zweig gebraucht, den man
vergessen kann — genau die Bauform, aus der #1015 entstanden ist. Ein
Monatsgehalt wird deshalb mit zwoelf multipliziert und als
`jaehrlich` gefuehrt; `monat_erkannt` sagt, woher der Wert kam.
"""
from __future__ import annotations

import re

MONATE_PRO_JAHR = 12

#: Plausibilitaetsgrenzen je Art — unveraendert aus der alten Fassung
#: uebernommen, damit diese Aenderung nichts ausserhalb ihres Anlasses
#: verschiebt. Der Monatsbereich ist neu.
GRENZEN = {
    "jaehrlich": (20000, 300000),
    "monatlich": (800, 30000),
    "taeglich": (200, 5000),
    "stuendlich": (10, 500),
}

#: Rangfolge, wenn mehrere Kandidaten ueberleben. Die Jahresangabe ist
#: in einer Anzeige die Schlagzeile, ein Stundenwert daneben die
#: Ergaenzung. In der Praxis kollidiert das selten: eine Freelance-
#: Anzeige nennt einen Tagessatz und kein Jahresgehalt.
RANG = ("jaehrlich", "monatlich", "taeglich", "stuendlich")

# Wortgrenzen sind PFLICHT (#1026, Befund 2). Ohne sie qualifiziert
# jede Zeichenfolge, die mit "Eur" beginnt, eine benachbarte Zahl als
# Betrag — "Europastr.", "Eurotunnel", "europaweit". Dritter Fall
# dieser Klasse nach "ki" in "Kita" (#970) und "us" in "Kundenservice"
# (#996), und in #1018 wurde die Wortgrenze bei `p. a.` ausdruecklich
# nachgezogen und hier vergessen. Dieselbe Regel, zwei Stellen, eine
# davon uebersehen.
#
# `€` braucht keine Wortgrenze — es ist kein Wortzeichen, und die
# Grenze wuerde sich daran anders verhalten als erwartet.
_WAEHRUNG = r"(?:€|\bEUR\b|\bEURO\b)"
# Der Dezimaltrenner ist im Deutschen das Komma — in Anzeigen steht
# aber auch der Punkt, und zwar genau dort, wo die k-Schreibweise
# benutzt wird ("72.5-103k EUR", gemessen). Die erste Alternative
# verlangt hinter dem Punkt DREI Ziffern (Tausendertrennung), "72.5"
# faellt also durch und wurde vom Rest des Musters als blosse "5"
# gelesen — aus 72.500 bis 103.000 wurde damit eine Spanne von 5 bis
# 103, die an der Plausibilitaetsgrenze scheitert. Danach griff der
# Einzelwert-Pfad und machte 103k zur UNTERGRENZE, obwohl es die
# Obergrenze ist.
#
# Dritter Befund zu #1026, im Bericht nicht enthalten: gefunden beim
# Nachmessen der eigenen Aenderung an 1.337 Anzeigen.
_ZAHL = (r"(?:\d{1,3}(?:[.\s]\d{3})+|\d{1,6})"
         r"(?:[.,]\d{1,2}(?!\d))?")
_BIS = r"\s*(?:-|–|—|bis)\s*"

# Eine Zahl neben einer Wochenangabe ist Arbeitszeit, kein Lohn. Auch
# auf Englisch: "12-20 hours per week" stand so im Bestand.
_ARBEITSZEIT = re.compile(
    r"(?:stunden|stundenwoche|std\.?|h|hours?)\s*"
    r"(?:[-–/]|pro|per|je|in der|die)?\s*"
    r"(?:woche|week|wo\b)"
    r"|wochen(?:arbeits)?(?:stunden|zeit)",
    re.IGNORECASE)

#: So weit hinter dem Treffer wird noch nach einer Wochenangabe gesucht.
#: 25 Zeichen decken "Stunden pro Woche" und "Std. / Woche" ab, ohne den
#: naechsten Satz mitzunehmen.
_NACHLAUF = 25


def _entschaerfen(text: str) -> str:
    """Markdown-Escapes weg, Sonderstriche vereinheitlichen.

    348 von 1.337 Beschreibungen im Bestand tragen `\\.` und `\\-` —
    die Quellen liefern Markdown, und ein escapter Tausenderpunkt macht
    aus `43.933` etwas, das kein Zahlenmuster mehr trifft.
    """
    text = re.sub(r"\\([.\-–,])", r"\1", text or "")
    return text.replace("\u00a0", " ")


def _zahl(roh: str) -> float:
    """"72.500" ist ein Tausender, "72.5" eine Dezimalzahl.

    Der Punkt ist im Deutschen der Tausendertrenner und im Englischen
    das Komma-Aequivalent. Unterscheiden laesst sich das an der Zahl der
    Ziffern dahinter: DREI heisst Tausender, eine oder zwei heissen
    Dezimalstelle. Ein Text, in dem beides vorkommt, ist damit
    lesbar — und "72.5-103k" ergibt 72,5 statt 5.
    """
    roh = (roh or "").strip().replace(" ", "")
    roh = re.sub(r"\.(?=\d{3}(?:\D|$))", "", roh)
    roh = roh.replace(",", ".")
    return float(roh)


def _muster(art: str) -> tuple:
    """Die Muster einer Art, jeweils MIT Pflicht-Beleg.

    Drei Bauformen je Art, damit eine genannte Spanne nie durch eine
    gerechnete ersetzt wird (das war der zweite Randbefund des Melders:
    "Stundensatz 30-35 EUR" ergab 30 bis 33, weil die Einheit zwischen
    Praefix und Zahlen steht und nur das Einzelmuster griff):

    1. Spanne mit Waehrung/Einheit HINTER den Zahlen
    2. Spanne mit Rate-Wort VOR den Zahlen
    3. Einzelwert — nur wenn keine Spanne gefunden wurde
    """
    if art == "jaehrlich":
        rate = r"(?:jahresgehalt|jahreseinkommen|gehalt|verdienst)"
        # `p.a.` braucht den Punkt UND eine rechte Wortgrenze. Ohne sie
        # passt das Muster auf jedes "Pa" — am Bestand gemessen wurden
        # so "23.800 Patient:innen" und "100.000 Paletten-Stellplaetze"
        # zu Jahresgehaeltern. Vierter Fall nach "ki" in "Kita" (#970),
        # "us" in "Kundenservice" (#996) und "intern" in
        # "International" (#1015) — und der erste, den ich beim Bauen
        # dieser Regel selbst eingebaut habe.
        einheit = (r"(?:brutto|p\.\s*a\.?\b|pro\s+jahr|/\s*jahr"
                   r"|j[äa]hrlich|per\s+(?:year|annum))")
    elif art == "monatlich":
        rate = r"(?:monatsgehalt|gehalt|verdienst)"
        einheit = r"(?:pro\s+monat|/\s*monat|monatlich|mtl\.?|im\s+monat)"
    elif art == "taeglich":
        rate = r"(?:tagessatz|tages-?satz)"
        einheit = r"(?:pro\s+tag|/\s*tag|t[äa]glich|/\s*d\b|per\s+day)"
    else:
        rate = r"(?:stundensatz|stunden-?satz|rate)"
        einheit = (r"(?:pro\s+stunde|/\s*stunde|/\s*std\.?|/\s*h\b"
                   r"|per\s+hour|/\s*hour|stundenlohn)")

    # Die Waehrung ALLEIN genuegt nur beim Jahresgehalt: dort macht die
    # Groessenordnung (20.000 bis 300.000) die Art eindeutig. Bei den
    # anderen drei ist die Einheit Pflicht — sonst passt "900-1100 EUR"
    # gleichzeitig auf Monat, Tag und Stunde, und der erste Rang
    # gewinnt. Genau das ist meiner ersten Fassung passiert: aus
    # "Tagessatz 900-1100 EUR" wurden 10.800 Euro im Jahr.
    if art == "jaehrlich":
        # Ohne Waehrungszeichen genuegt nur ein GELD-Wort, nie eine
        # blosse Zeitangabe — sonst steht die Regel aus dem Modulkopf
        # ("ohne Waehrung kein Gehalt") nur im Text und nicht im Code.
        beleg_dahinter = (
            rf"(?:{_WAEHRUNG}\s*{einheit}?"
            rf"|(?:brutto|jahresgehalt|jahreseinkommen))")
    else:
        beleg_dahinter = rf"(?:{_WAEHRUNG}\s*)?{einheit}"

    return (
        # 1. Spanne, Beleg dahinter: "60.000 - 80.000 EUR brutto",
        #    "140-150 EUR/h", "3.750 - 4.050 € / Monat"
        re.compile(
            rf"({_ZAHL})\s*k?{_BIS}({_ZAHL})\s*k?\s*{beleg_dahinter}",
            re.IGNORECASE),
        # 2. Spanne, Rate-Wort davor: "Stundensatz 30-35 EUR",
        #    "Gehalt: 58.000 - 62.000 Euro"
        re.compile(
            rf"{rate}\s*[:\s]\s*(?:{_WAEHRUNG}\s*)?({_ZAHL})\s*k?{_BIS}"
            rf"({_ZAHL})\s*k?\s*(?:{_WAEHRUNG})?",
            re.IGNORECASE),
        # 3. Einzelwert, Beleg auf einer der beiden Seiten.
        #    `beleg_dahinter` ist DASSELBE wie in Muster 1 — meine erste
        #    Fassung schrieb hier `einheit` direkt hin und liess damit
        #    "40.000 pro Jahr" ohne Waehrung durch, waehrend das
        #    Spannen-Muster es abwies. Dieselbe Regel an zwei Orten,
        #    verschieden umgesetzt: genau die Bauform, um die es in
        #    diesem Projekt seit #963 geht.
        re.compile(
            rf"(?:{rate}\s*[:\s]\s*(?:{_WAEHRUNG}\s*)?({_ZAHL})\s*k?"
            rf"|({_ZAHL})\s*k?\s*{beleg_dahinter}"
            rf"|{_WAEHRUNG}\s*({_ZAHL})\s*k?\s*{einheit})",
            re.IGNORECASE),
    )


_KOMPILIERT = {art: _muster(art) for art in GRENZEN}


def _ist_arbeitszeit(art: str, text: str, ende: int) -> bool:
    """Folgt dem Treffer eine Wochenangabe?

    Die Pruefung gilt NUR fuer Stundenwerte. Ein Jahresgehalt laesst
    sich mit einer Wochenarbeitszeit nicht verwechseln — meine erste
    Fassung prueste jede Art und verwarf damit "Gehalt: 58.000 - 62.000
    Euro, Wochenstunden: 35" als Arbeitszeit. Danach griff das
    Einzelmuster und ERFAND ein Maximum von 63.800; die genannte Spanne
    war weg. Das ist genau der zweite Randbefund des Melders, nur von
    mir neu gebaut — gefunden hat es die Trefferliste am Bestand.
    """
    if art != "stuendlich":
        return False
    return bool(_ARBEITSZEIT.search(text[ende:ende + _NACHLAUF]))


def _kandidat(art: str, text: str, treffer, gerechnet: bool) -> dict | None:
    werte = [g for g in treffer.groups() if g]
    if not werte:
        return None
    try:
        zahlen = [_zahl(w) for w in werte]
    except ValueError:
        return None

    # k-Schreibweise: "60k-80k" steht im Treffer als 60 und 80.
    if re.search(r"\d\s*k\b", treffer.group(0), re.IGNORECASE):
        zahlen = [z * 1000 for z in zahlen if z < 1000] or zahlen

    unten, oben = GRENZEN[art]
    if not (unten <= zahlen[0] <= oben):
        return None

    if len(zahlen) >= 2:
        s_min, s_max = min(zahlen[0], zahlen[1]), max(zahlen[0], zahlen[1])
        # **Beide Werte muessen die Grenze passieren** (#1026, Befund 1).
        # Vorher wurde nur `zahlen[0]` geprueft — bei einer Spanne kam
        # der zweite ungeprueft durch. Aus "Telefon 01234-56789-10"
        # wurde damit ein Jahresgehalt von 10 bis 56.789 EUR, und zwar
        # als BELEGT gespeichert, weil 56.789 die Grenze passierte.
        #
        # Verworfen wird die ganze Fundstelle, nicht nur der eine Wert:
        # eine halbe Spanne ist keine Angabe, und lieber gar kein Wert
        # als ein falscher (#989). Im gemessenen Bestand des Melders
        # ist der Fehltreffer der EINZIGE Jahreswert unter 15.000 — die
        # Untergrenze faengt also nichts weg, was echt waere.
        if not (unten <= s_min <= oben and unten <= s_max <= oben):
            return None
    else:
        # Ein Einzelwert bekommt eine Spanne von 10 Prozent — aber NUR
        # hier. Eine genannte Spanne wird nie durch eine gerechnete
        # ersetzt (Randbefund 2 des Melders).
        s_min, s_max = zahlen[0], round(zahlen[0] * 1.1, 2)

    return {
        "art": art,
        "min": s_min,
        "max": s_max,
        "gerechnete_spanne": gerechnet,
        "fundstelle": " ".join(treffer.group(0).split())[:80],
    }


def extrahieren(text: str) -> dict:
    """Das Gehalt aus einem Anzeigentext — oder eine Begruendung.

    Rueckgabe immer ein dict, nie None:

        min / max   Werte, sonst None
        art         "jaehrlich" / "taeglich" / "stuendlich", sonst None
        monat_erkannt   True, wenn die Anzeige monatlich rechnet (der
                    Wert steht dann schon als Jahresbetrag da)
        fundstelle  der Textausschnitt, auf dem das beruht
        grund       Klartext, wenn nichts gefunden wurde
    """
    leer = {"min": None, "max": None, "art": None, "monat_erkannt": False,
            "gerechnete_spanne": False, "fundstelle": "", "grund": ""}
    if not text:
        leer["grund"] = "Kein Text."
        return leer

    sauber = _entschaerfen(text)
    gefunden: list = []

    for art, muster in _KOMPILIERT.items():
        spanne_gefunden = False
        # Wo eine Spanne zwar TRAF, aber an der Plausibilitaetsgrenze
        # scheiterte (#1026). Der Einzelwert-Pfad darf sich aus einer
        # verworfenen Spanne nicht den plausiblen Teil herausgreifen:
        # aus "Jahresgehalt 10 - 56789 EUR" wurde sonst ein Gehalt von
        # 56.789, und aus "Gehalt: 5 - 250000 Euro" eines von 250.000.
        # Das ist derselbe Befund wie der gemeldete, eine Ebene weiter —
        # die Zahl stammt aus einer Fundstelle, die als Ganzes
        # unglaubwuerdig ist.
        #
        # Gemerkt wird die STELLE im Text, nicht ein Schalter fuer die
        # ganze Art: sonst verloere eine Anzeige mit einer
        # Telefonnummer VORNE ihr echtes Gehalt weiter HINTEN.
        verworfen: list = []
        for nummer, m in enumerate(muster):
            # Muster 3 ist der Einzelwert und tritt nur an, wenn fuer
            # diese Art keine Spanne gefunden wurde.
            if nummer == 2 and spanne_gefunden:
                continue
            for treffer in m.finditer(sauber):
                if _ist_arbeitszeit(art, sauber, treffer.end()):
                    continue
                if nummer == 2 and any(
                        treffer.start() < ende and anfang < treffer.end()
                        for anfang, ende in verworfen):
                    continue
                k = _kandidat(art, sauber, treffer, gerechnet=(nummer == 2))
                if k:
                    gefunden.append(k)
                    if nummer < 2:
                        spanne_gefunden = True
                elif nummer < 2:
                    verworfen.append((treffer.start(), treffer.end()))

    if not gefunden:
        leer["grund"] = (
            "Keine Zahl mit Waehrung oder Rate-Wort gefunden. Eine Zahl "
            "neben dem Wort 'Stunden' ist ohne Waehrung fast immer "
            "Arbeitszeit.")
        return leer

    gefunden.sort(key=lambda k: (RANG.index(k["art"]), k["gerechnete_spanne"]))
    beste = gefunden[0]

    monat = beste["art"] == "monatlich"
    return {
        "min": (round(beste["min"] * MONATE_PRO_JAHR, 2) if monat
                else beste["min"]),
        "max": (round(beste["max"] * MONATE_PRO_JAHR, 2) if monat
                else beste["max"]),
        "art": "jaehrlich" if monat else beste["art"],
        "monat_erkannt": monat,
        "gerechnete_spanne": beste["gerechnete_spanne"],
        "fundstelle": beste["fundstelle"],
        "grund": "",
    }


def als_tupel(text: str) -> tuple:
    """Die alte Rueckgabeform `(min, max, art)`.

    `extract_salary_from_text` hat zahlreiche Aufrufer, die genau dieses
    Tupel entpacken. Der Umbau der Erkennung soll sie nicht anfassen
    muessen — wer den Befund braucht, ruft `extrahieren`.
    """
    erg = extrahieren(text)
    return erg["min"], erg["max"], erg["art"]


def gesund(s_min, s_max) -> tuple:
    """`salary_min > salary_max` kommt nicht in die Datenbank.

    Im hiesigen Bestand gibt es keine solche Zeile mehr; der Melder hat
    eine gesehen (75 bei 30), deren Herkunft sich nicht mehr
    rekonstruieren liess. Das ist also ein Riegel gegen den Rueckfall
    und keine Reparatur — und er gehoert an das Nadeloehr, nicht in die
    Erkennung, weil die Werte auch aus einer Quelle kommen koennen.
    """
    if s_min is None or s_max is None:
        return s_min, s_max
    try:
        if float(s_min) > float(s_max):
            return s_max, s_min
    except (TypeError, ValueError):
        return s_min, s_max
    return s_min, s_max
