"""Welche Art von Stelle ist das? (#1015)

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

#: Die Werte, die `suchkriterien_setzen` als `stellentypen` annimmt.
BEKANNTE_ARTEN = (FESTANSTELLUNG, FREELANCE, TEILZEIT, PRAKTIKUM,
                  WERKSTUDENT)

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
    (TEILZEIT, (
        r"\bteilzeit\b",
        r"\bpart[-\s]?time\b",
    )),
)

#: Wird die Vollzeit-Alternative im selben Titel genannt, ist die
#: Stelle nicht "Teilzeit", sondern "auch Teilzeit".
_VOLLZEIT = re.compile(
    r"\bvoll[-\s/]?\s*(?:teil)?zeit\b"
    r"|\bfull[-\s]?time\b", re.IGNORECASE)

_KOMPILIERT = tuple(
    (art, tuple(re.compile(m, re.IGNORECASE) for m in muster))
    for art, muster in _MUSTER)


def erkenne(job: dict) -> dict:
    """Die Stellenart einer Stelle — mit Beleg.

    Rueckgabe immer ein dict:

        art      eine der BEKANNTE_ARTEN
        beleg    "titel" wenn der Titel sie ausweist, sonst "quelle"
        wort     das gefundene Wort, wenn der Beleg aus dem Titel kommt
        belegt   True nur bei einem Titelbeleg — nur dann darf
                 ueberhaupt ausgeschlossen werden
    """
    von_quelle = (job.get("employment_type") or "").strip().lower()
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
    gewuenscht = [str(t).strip().lower()
                  for t in (criteria.get("stellentypen") or []) if t]
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
