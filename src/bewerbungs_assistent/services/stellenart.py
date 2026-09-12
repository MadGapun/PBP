"""Welche Art von Stelle ist das — und in welchem Umfang? (#1015, #1023)

## Zwei Fragen, nicht eine (#1023)

Der zweite Melder-Bericht hat den Entwurf dieses Moduls widerlegt, und
er hat recht:

    Eine Stelle hat eine Anstellungsform UND einen Umfang.
    "Festanstellung in Teilzeit" ist der Normalfall, im Ein-Feld-Modell
    aber nicht ausdrueckbar. Der Adapter muss sich entscheiden und
    waehlt immer die Vertragsart; der Umfang faellt weg.

Am Bestand gemessen: **0 von 1.282 Stellen tragen `teilzeit`**, waehrend
103 aktive Titel es nennen — 102 davon gespeichert als
`festanstellung`. Solange `teilzeit` in derselben Liste steht wie
`freelance`, muss jede Erkennung eine Entscheidung treffen, die es
nicht zu treffen gibt.

Deshalb jetzt **zwei Dimensionen**:

* `ANSTELLUNGSFORMEN` — festanstellung, zeitarbeit, freelance,
  praktikum, werkstudent, ausbildung. Sie ist es, die im Suchprofil
  gewaehlt wird und ueber aktiv/ausgeblendet entscheidet.
* `UMFAENGE` — vollzeit, teilzeit, beides, unbekannt. Er wird
  ANGEZEIGT und gefiltert, sortiert aber **nie** automatisch aus: er
  steht bei 993 von 1.110 Stellen gar nicht da, ist oft verhandelbar,
  und ein Ausschluss darauf traefe vor allem die, bei denen die Angabe
  nur fehlt (dieselbe Linie wie Remote #989 und Entfernung #910/#988).

`beides` ist ein eigener Wert und kein Notbehelf: "Vollzeit / Teilzeit"
ist keine Mehrdeutigkeit, sondern eine Zusage. Ein Etikett mit nur zwei
Werten macht daraus eine Falschangabe, egal welches es waehlt.

**`befristet` ist bewusst KEINE Anstellungsform**, sondern ein
Kennzeichen am Vertrag — der Melder hat ausdruecklich darum gebeten.
Es steht weiter im Scoring-Vokabular und wird hier nur erkannt.

## Rangfolge der Erkennung (#1023)

1. **Strukturiertes Feld der Quelle**, wo vorhanden — die BA-Detail-API
   liefert `arbeitszeitVollzeit` / `arbeitszeitTeilzeit*` und
   `istArbeitnehmerUeberlassung`, jobspy ein `job_type`. Keines davon
   kam im Projekt vor.
2. **Titel.** Starkes Signal: bei allen 36 Ausbildungsstellen und allen
   103 Teilzeit-Stellen des Melders steht es dort.
3. **Beschreibung.** Schwach — sie darf MARKIEREN und nie allein
   ausschliessen. "Erfahrung durch Praktikum wuenschenswert" ist eine
   Anforderung, keine Praktikumsstelle.

## Der urspruengliche Anlass (#1015)

Gemeldet am 10.09.2026: in den Suchkriterien steht `festanstellung,
freelance`, ein Pflichtpraktikum lag trotzdem aktiv und bewertbar in
der Liste. Zwei getrennte Fehler dahinter.

**Erstens hat `stellentypen` keinen filternden Leser.** Am Code
nachgesehen gibt es genau drei, und keiner davon filtert:
`datenguete.py` setzt eine Marke `VERLETZT` und laesst die Stelle
stehen, `tools/jobs.py` warnt nur, wenn fuer einen Typ gar keine Quelle
laeuft (#906), `tools/suche.py` verteilt `max_entfernung_km` darueber
(#1000). Weder `save_jobs` noch `calculate_score` sehen das Feld. Das
ist #1000 ein zweites Mal — nur schlimmer, weil hier sogar ein Befund
entsteht, der aussieht als greife etwas.

**Zweitens gibt es gar keine zentrale Typ-Erkennung.**
`bundesagentur.py` schreibt fuer JEDE Stelle `festanstellung` fest
verdrahtet, `stellenanzeigen_de.py` an zwei Stellen ebenso, andere
Adapter leiten ab, Freelance-Portale setzen zu Recht `freelance`.
Dasselbe Titelmuster fuehrt deshalb zwangslaeufig zu verschiedenen
Typen, je nachdem welche Quelle es geliefert hat — genau die
Beobachtung des Melders, dass zwei Pflichtpraktika unterschiedlich
eingeordnet wurden.

## Nur POSITIVER Beleg, nie ein Verdacht

Die Erkennung liest den Titel und ueberschreibt die Angabe der Quelle
nur, wenn dort ein eindeutiger Begriff steht. Alles andere bleibt, wie
die Quelle es gemeldet hat. Das ist dieselbe Bauform wie die
DACH-Pruefung aus #996: drei Zustaende statt zwei, und ausgeschlossen
wird nur, was BELEGT ist — ein falscher Ausschluss ist teurer als ein
zu hoher Score (#827).

## Was die Messung an den Markern geaendert hat

Am echten Bestand (2.535 Titel, Kopie) gegengeprueft, und die Messung
hat die erste Fassung zweimal korrigiert:

**`intern` ohne rechte Wortgrenze ist unbrauchbar.** `\\bintern`
trifft "International", "Internal", "Internationaler" — 11 von 14
Treffern waren Fehlalarme, darunter ein Senior IT Projektmanager, der
damit als Praktikum ausgeschlossen worden waere. Das ist "ki" in
"Kita" (#970) und "us" in "Kundenservice" (#996) zum dritten Mal. Mit
`\\bintern\\b` bleiben 11 echte Praktika uebrig, kein Fehlalarm.

**"Teilzeit" steht in 10 von 16 Titeln neben "Vollzeit".** Die Stelle
wird als BEIDES angeboten ("Vollzeit oder Teilzeit", "Voll/Teilzeit",
"[Full-time / part-time]"). Sie als Teilzeit einzuordnen und dann
auszuschliessen wuerde eine Vollzeitstelle wegwerfen. Deshalb gilt
Teilzeit nur, wenn die Vollzeit-Alternative NICHT dasteht.

## Die Grenze, und sie gehoert benannt

Eine Liste findet nur, was in ihr steht (#742, #1006). Ein Praktikum,
das sich im Titel nicht zu erkennen gibt, bleibt bei der Angabe der
Quelle — also meistens `festanstellung`. Das ist das Verhalten von
vorher und damit harmlos; es heisst nur, dass diese Erkennung eine
Verbesserung ist und keine Garantie.
"""
from __future__ import annotations

import re

FESTANSTELLUNG = "festanstellung"
FREELANCE = "freelance"
TEILZEIT = "teilzeit"
PRAKTIKUM = "praktikum"
WERKSTUDENT = "werkstudent"
# v1.7.84 (#1023): zwei Formen, die es im Vokabular nicht gab.
# `ausbildung` kam ueber die Pflichtbegriffe herein (36 aktive Stellen
# im gemessenen Bestand) und war nicht abwaehlbar — der Melder musste
# sich dafuer einen eigenen Ablehnungsgrund anlegen. `zeitarbeit` liess
# sich im Scoring bestrafen, aber nicht auswaehlen.
AUSBILDUNG = "ausbildung"
ZEITARBEIT = "zeitarbeit"

#: Die ANSTELLUNGSFORM — was im Suchprofil gewaehlt wird und ueber
#: aktiv/ausgeblendet entscheidet. `teilzeit` steht hier bewusst NICHT
#: mehr: das ist ein Umfang (#1023).
ANSTELLUNGSFORMEN = (FESTANSTELLUNG, ZEITARBEIT, FREELANCE, PRAKTIKUM,
                     WERKSTUDENT, AUSBILDUNG)

VOLLZEIT = "vollzeit"
BEIDES = "beides"
UNBEKANNT = "unbekannt"

#: Der UMFANG — angezeigt und filterbar, aber nie ein Ausschlussgrund.
#: `beides` ist ein eigener Wert: "Vollzeit / Teilzeit" ist eine Zusage,
#: keine Mehrdeutigkeit.
UMFAENGE = (VOLLZEIT, TEILZEIT, BEIDES, UNBEKANNT)

#: Die Werte, die `suchkriterien_setzen` als `stellentypen` annimmt.
#: `teilzeit` bleibt hier als ALTWERT erlaubt, damit eine gepflegte
#: Auswahl nicht beim Speichern verschwindet — sie wird in den Umfang
#: uebersetzt. Ein Wert, den ein Mensch gesetzt hat, wird nicht still
#: verworfen (#988).
BEKANNTE_ARTEN = ANSTELLUNGSFORMEN + (TEILZEIT,)

#: Was Quellen schreiben, das in keinem Vokabular steht (#1023
#: Befund 3: "drei Vokabulare, keins deckungsgleich"). Am Bestand
#: gefunden: `arbeitnehmerueberlassung` als `employment_type` — ein
#: Wert, den weder die Suchkriterien noch das Scoring-Vokabular noch
#: die Adapter-Zuordnung kennen. Er blieb damit unfilterbar UND
#: unbewertbar, obwohl er genau das sagt, was der Melder sucht.
_QUELLEN_ALIAS = {
    "arbeitnehmerueberlassung": ZEITARBEIT,
    "arbeitnehmerüberlassung": ZEITARBEIT,
    "personaldienstleistung": ZEITARBEIT,
    "temporaer": ZEITARBEIT,
    "vollzeit": FESTANSTELLUNG,   # ein UMFANG im Formfeld — s. #1023
    "fulltime": FESTANSTELLUNG,
    "full_time": FESTANSTELLUNG,
    "permanent": FESTANSTELLUNG,
    "contract": FREELANCE,
    "freiberuflich": FREELANCE,
    "apprenticeship": AUSBILDUNG,
    "duales studium": WERKSTUDENT,
}


def normalisiere_form(wert) -> str:
    """Die Angabe einer Quelle auf das Vokabular abbilden.

    Unbekanntes wird NICHT geraten, sondern durchgereicht — dann faellt
    es in `unzugeordnete_formen` auf, statt still zu `festanstellung` zu
    werden. Eine fehlende Zuordnung ist eine Luecke und keine Aussage
    (#989).
    """
    w = (wert or "").strip().lower()
    if not w:
        return ""
    if w in ANSTELLUNGSFORMEN:
        return w
    return _QUELLEN_ALIAS.get(w, w)


#: Was eine Quelle schreibt, wenn sie es nicht weiss. Diese Angaben
#: duerfen von einem Titelbeleg ueberschrieben werden; ein Freelance-
#: Portal, das `freelance` meldet, weiss dagegen etwas ueber sich
#: selbst und bleibt unangetastet.
VORGABE_ARTEN = (FESTANSTELLUNG, "", "unbekannt", None)

# Reihenfolge zaehlt: "Working Student/Intern" ist eine Werkstudenten-
# stelle, die nebenbei "Intern" sagt. Beide Arten stehen ohnehin selten
# in derselben Wunschliste, aber geraten wird hier nichts.
_MUSTER = (
    (WERKSTUDENT, (
        r"\bwerkstudent(?:in)?\b",
        r"\bworking\s+student\b",
        r"\bstudentische\s+hilfskraft\b",
        r"\bduales\s+studium\b",
        r"\bdualer\s+student\b",
    )),
    (PRAKTIKUM, (
        r"\bpraktikum\b",
        r"\bpflichtpraktikum\b",
        r"\bpraktikant(?:in|en)?\b",
        r"\bpraktikumsplatz\b",
        r"\bpraktikumsstelle\b",
        r"\binternship\b",
        # Rechte Wortgrenze ist Pflicht — ohne sie trifft es
        # "International" und "Internal". Am Bestand gemessen: 11 von
        # 14 Treffern waren Fehlalarme.
        r"\bintern\b",
    )),
    # v1.7.84 (#1023): zwei Formen, die es im Vokabular nicht gab.
    (AUSBILDUNG, (
        # "Ausbildung zum/zur ..." im TITEL ist eine Ausbildungsstelle.
        # "Ausbildung im Bereich X wuenschenswert" waere eine
        # ANFORDERUNG — die steht in der Beschreibung, und dieses
        # Muster liest nur den Titel.
        r"\bausbildung\b",
        r"\bauszubildende(?:r|n)?\b",
        r"\bazubi\b",
        r"\bapprentice(?:ship)?\b",
    )),
    (ZEITARBEIT, (
        r"\bzeitarbeit\b",
        r"\barbeitnehmer(?:ueber|über)lassung\b",
        r"\bpersonaldienstleist",
    )),
)

#: Wird die Vollzeit-Alternative im selben Titel genannt, ist die
#: Stelle nicht "Teilzeit", sondern "auch Teilzeit".
#:
#: v1.7.84 (#1023): `[-\s/]?` liess nur EIN Trennzeichen zu und verfehlte
#: damit die haeufigste Schreibweise ueberhaupt — "Voll-/Teilzeit" traegt
#: zwei ("-" und "/"). Die Stelle galt dann als reine Teilzeitstelle,
#: obwohl der Titel ausdruecklich beides anbietet. Gefunden beim
#: Durchspielen der Beispiele aus dem Bericht, nicht vom Nachdenken.
_VOLLZEIT = re.compile(
    r"\bvoll[-\s/]*(?:teil)?zeit\b"
    r"|\bfull[-\s/]*(?:part[-\s]?)?time\b", re.IGNORECASE)

#: Der UMFANG aus dem Titel — eine EIGENE Dimension (#1023). Eine
#: Stelle traegt beide Merkmale: "Werkstudent (Teilzeit)" ist Form UND
#: Umfang, und bis v1.7.83 musste sich die Erkennung fuer eines
#: entscheiden.
_UMFANG_MUSTER = (
    (TEILZEIT, (
        r"\bteilzeit\b",
        r"\bpart[-\s]?time\b",
    )),
    (VOLLZEIT, (
        r"\bvollzeit\b",
        r"\bfull[-\s]?time\b",
    )),
)

#: `befristet` ist KEINE Anstellungsform, sondern ein Kennzeichen am
#: Vertrag — ausdruecklicher Wunsch des Melders. Es wird erkannt und
#: angezeigt, entscheidet aber nichts.
_BEFRISTET = re.compile(
    r"\bbefristet\b|\bbefristung\b|\bzeitlich\s+befristet\b"
    r"|\bfixed[-\s]?term\b|\bbefristete[rsn]?\b", re.IGNORECASE)

_KOMPILIERT = tuple(
    (art, tuple(re.compile(m, re.IGNORECASE) for m in muster))
    for art, muster in _MUSTER)

_UMFANG_KOMPILIERT = tuple(
    (wert, tuple(re.compile(m, re.IGNORECASE) for m in muster))
    for wert, muster in _UMFANG_MUSTER)


def erkenne(job: dict) -> dict:
    """Die Stellenart einer Stelle — mit Beleg.

    Rueckgabe immer ein dict:

        art      eine der BEKANNTE_ARTEN
        beleg    "titel" wenn der Titel sie ausweist, sonst "quelle"
        wort     das gefundene Wort, wenn der Beleg aus dem Titel kommt
        belegt   True nur bei einem Titelbeleg — nur dann darf
                 ueberhaupt ausgeschlossen werden
    """
    von_quelle = normalisiere_form(job.get("employment_type"))
    ergebnis = {
        "art": von_quelle or FESTANSTELLUNG,
        "beleg": "quelle",
        "wort": "",
        "belegt": False,
    }

    titel = (job.get("title") or "").strip()
    if not titel:
        return ergebnis

    # Eine Quelle, die etwas ueber sich selbst weiss, wird nicht
    # ueberschrieben — ein Freelance-Portal meldet `freelance`, und das
    # ist keine Vorgabe, sondern eine Auskunft.
    if von_quelle and von_quelle not in VORGABE_ARTEN:
        return ergebnis

    for art, muster in _KOMPILIERT:
        for m in muster:
            treffer = m.search(titel)
            if not treffer:
                continue
            if art == TEILZEIT and _VOLLZEIT.search(titel):
                # "Vollzeit oder Teilzeit" ist beides — und damit
                # kein Grund, eine Vollzeitstelle wegzuwerfen.
                continue
            return {
                "art": art,
                "beleg": "titel",
                "wort": treffer.group(0),
                "belegt": True,
            }
    return ergebnis


def unerwuenscht(job: dict, criteria: dict) -> dict | None:
    """Ist diese Stelle BELEGT von einer Art, die nicht gesucht wird?

    Gibt nur dann etwas zurueck, wenn beides gilt: der Nutzer hat
    `stellentypen` gepflegt, UND die Art steht im Titel. Ohne Titelbeleg
    passiert nichts — die Angabe der Quelle ist dafuer zu unzuverlaessig
    (`bundesagentur` schreibt fuer jede Stelle `festanstellung`).
    """
    # v1.7.84 (#1023): auf die ANSTELLUNGSFORMEN reduziert. Stand in
    # der gepflegten Auswahl nur `teilzeit` — bis #1023 ein zulaessiger
    # Wert —, haette die rohe Liste JEDE Stelle mit belegter Form
    # ausgeschlossen, weil keine davon "teilzeit" heisst. Die
    # Reduktion faengt das ab: bleibt nichts uebrig, wird nicht
    # gefiltert.
    gewuenscht = fuer_form(criteria.get("stellentypen"))
    if not gewuenscht:
        return None

    befund = erkenne(job)
    if not befund["belegt"] or befund["art"] in gewuenscht:
        return None
    return {
        "art": befund["art"],
        "wort": befund["wort"],
        "grund": (
            f"Der Titel weist die Stelle als '{befund['art']}' aus "
            f"(\"{befund['wort']}\"); deine Stellentypen sind "
            f"{', '.join(gewuenscht)}."
        ),
    }


# ============================================================== #1023
# Der UMFANG — zweite Dimension, eigener Rechenweg


def umfang_erkennen(job: dict) -> dict:
    """Vollzeit, Teilzeit, beides — oder ehrlich unbekannt.

    Rangfolge wie vom Melder vorgeschlagen: strukturiertes Feld der
    Quelle, dann Titel, dann Beschreibung. Die Beschreibung MARKIERT
    nur; sie fuehrt nie zu `teilzeit`, sondern hoechstens zu `beides` —
    "auch in Teilzeit moeglich" im Fliesstext ist ein Angebot, keine
    Festlegung.

    Rueckgabe:
        umfang   einer aus UMFAENGE
        beleg    "quelle" / "titel" / "beschreibung" / "" (unbekannt)
        wort     der gefundene Beleg, soweit es einen gibt

    **Der Umfang schliesst nie etwas aus.** Er steht bei 993 von 1.110
    Stellen gar nicht da; ein Ausschluss darauf traefe vor allem die,
    bei denen die Angabe nur fehlt.
    """
    leer = {"umfang": UNBEKANNT, "beleg": "", "wort": ""}

    # (1) Strukturiertes Feld — wo eine Quelle es liefert, ist es die
    #     verlaesslichste Angabe. Sie kommt als `arbeitsumfang` herein,
    #     weil die Adapter sie dort ablegen.
    von_quelle = (job.get("arbeitsumfang") or "").strip().lower()
    if von_quelle in UMFAENGE and von_quelle != UNBEKANNT:
        return {"umfang": von_quelle, "beleg": "quelle", "wort": von_quelle}

    titel = (job.get("title") or "").strip()
    if titel:
        gefunden = _umfang_aus_text(titel)
        if gefunden:
            return {"umfang": gefunden[0], "beleg": "titel",
                    "wort": gefunden[1]}

    # (3) Beschreibung: schwaches Signal. Nennt sie Teilzeit, heisst das
    #     "geht auch" — also `beides`, nie `teilzeit` allein.
    text = (job.get("description") or "")
    if text:
        gefunden = _umfang_aus_text(text)
        if gefunden:
            wert = BEIDES if gefunden[0] == TEILZEIT else gefunden[0]
            return {"umfang": wert, "beleg": "beschreibung",
                    "wort": gefunden[1]}
    return leer


def _umfang_aus_text(text: str) -> tuple | None:
    """(umfang, wort) oder None.

    Stehen BEIDE Werte da, ist die Antwort `beides` — und das ist der
    eigentliche Gewinn der zweiten Dimension. "Vollzeit / Teilzeit" ist
    eine Zusage; ein Etikett mit zwei Werten macht daraus eine
    Falschangabe, egal welches es waehlt.
    """
    treffer = {}
    for wert, muster in _UMFANG_KOMPILIERT:
        for m in muster:
            t = m.search(text)
            if t:
                treffer[wert] = t.group(0)
                break
    # "Voll-/Teilzeit" und "Voll/Teilzeit" nennen Vollzeit, ohne dass
    # das Wort vollstaendig dasteht — dafuer gibt es _VOLLZEIT.
    if TEILZEIT in treffer and VOLLZEIT not in treffer:
        if _VOLLZEIT.search(text):
            return (BEIDES, treffer[TEILZEIT])
    if len(treffer) == 2:
        return (BEIDES, f"{treffer[VOLLZEIT]} / {treffer[TEILZEIT]}")
    for wert in (TEILZEIT, VOLLZEIT):
        if wert in treffer:
            return (wert, treffer[wert])
    return None


def befristet_erkennen(job: dict) -> dict:
    """Ein Kennzeichen am Vertrag, keine Anstellungsform (#1023).

    Der Melder ausdruecklich: *"`befristet` bitte nicht als
    Auswahloption, sondern als Kennzeichen an der Stelle — es ist eine
    Eigenschaft des Vertrags, keine Anstellungsform."*
    """
    if job.get("befristet") in (1, True, "1", "ja"):
        return {"befristet": True, "beleg": "quelle", "wort": ""}
    for feld, beleg in (("title", "titel"), ("description", "beschreibung")):
        t = _BEFRISTET.search(job.get(feld) or "")
        if t:
            return {"befristet": True, "beleg": beleg, "wort": t.group(0)}
    return {"befristet": False, "beleg": "", "wort": ""}


def merkmale(job: dict) -> dict:
    """Beide Merkmale auf einmal — das Nadeloehr fuer Aufrufer.

    `save_jobs`, der Nachzieh-Lauf und die Anzeige fragen hier, statt
    drei Funktionen einzeln zu rufen und die Zusammensetzung je neu zu
    erfinden. Dieselbe Ueberlegung wie bei `fuer_scoring` (#931) und
    `gehalt_vergleich` (#1017).
    """
    form = erkenne(job)
    um = umfang_erkennen(job)
    bef = befristet_erkennen(job)
    return {
        "form": form["art"],
        "form_beleg": form["beleg"],
        "form_wort": form["wort"],
        "form_belegt": form["belegt"],
        "umfang": um["umfang"],
        "umfang_beleg": um["beleg"],
        "umfang_wort": um["wort"],
        "befristet": bef["befristet"],
        "befristet_beleg": bef["beleg"],
    }


def fuer_form(gewuenscht) -> list:
    """Die gewaehlten `stellentypen`, auf Anstellungsformen reduziert.

    Ein gepflegtes `teilzeit` aus der Zeit vor #1023 ist KEINE
    Anstellungsform mehr. Es hier still mitzufiltern haette jede
    Vollzeitstelle ausgeschlossen; es zu verwerfen und nichts zu sagen
    waere #988. Also faellt es aus der FORM-Auswahl heraus und lebt als
    Umfang weiter — `suchkriterien_anzeigen` benennt das.
    """
    return [w for w in (
        str(t).strip().lower() for t in (gewuenscht or []) if t)
        if w in ANSTELLUNGSFORMEN]


def umfang_aus_auswahl(gewuenscht) -> str:
    """Steht in der alten `stellentypen`-Auswahl ein Umfang?

    Gibt `teilzeit` zurueck, wenn der Mensch das frueher gewaehlt hat —
    damit die Oberflaeche es als Umfang-Vorauswahl uebernehmen kann,
    statt dass die Einstellung beim Umbau verdunstet.
    """
    for t in (gewuenscht or []):
        if str(t).strip().lower() == TEILZEIT:
            return TEILZEIT
    return ""
