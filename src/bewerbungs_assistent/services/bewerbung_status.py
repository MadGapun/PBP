"""Welche Bewerbungsstatus es gibt, und was sie bedeuten (#1103).

Seit #779 gibt es `arbeitgeber_ausgefallen`. Mehrere eigene Listen kannten
ihn nicht: die Kopfzeile zaehlte solche Bewerbungen als aktiv, und der
Schutz aus #743 gegen automatisches Verknuepfen mit abgeschlossenen
Bewerbungen griff nicht. Eine neue Statusangabe an EINER Stelle
nachzutragen reicht nur, wenn es nur eine Stelle gibt.

Es gibt nicht eine Menge "abgeschlossen", sondern mehrere Fragen. Jede
hat hier einen Namen:

* ``ARCHIV`` — endete ohne Erfolg. Sie gilt nicht mehr als laufend, ihre
  Stelle nicht mehr als beworben, neue Mails und Dokumente gehoeren nicht
  automatisch dorthin.
* ``ABGESCHLOSSEN`` — der Vorgang ist vorbei, erfolgreich oder nicht.
  `angenommen` gehoert dazu, zum Archiv nicht: eine angenommene Bewerbung
  blendet niemand aus.

Ein Guard (tests/test_1103_bewerbung_status.py) verbietet eigene Listen
mit "abgelehnt" und "zurueckgezogen" ausserhalb dieses Moduls; Listen, die
eine andere Frage beantworten, stehen dort mit Begruendung.
"""
from __future__ import annotations

#: Alle gueltigen Status, in der Reihenfolge eines Bewerbungsverlaufs.
ALLE = (
    "in_vorbereitung", "offen", "beworben", "eingangsbestaetigung",
    "interview", "zweitgespraech", "interview_abgeschlossen", "angebot",
    "angenommen", "abgelehnt", "zurueckgezogen", "abgelaufen",
    # v1.7.10 (#779/D27): Prozess endete ohne Zutun des Bewerbers.
    "arbeitgeber_ausgefallen",
)

#: Endete ohne Erfolg.
ARCHIV = ("abgelehnt", "zurueckgezogen", "abgelaufen", "arbeitgeber_ausgefallen")

#: Vorbei, erfolgreich oder nicht.
ABGESCHLOSSEN = ARCHIV + ("angenommen",)


def laeuft(status) -> bool:
    """Laeuft der Vorgang noch?"""
    return (status or "") not in ABGESCHLOSSEN


_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

#: Woerter, die Menschen sagen, wenn sie einen Status meinen. Sie werden NIE
#: als Filter angewandt (raten waere falsch: "abgesagt" kann Absage oder
#: Rueckzug heissen), aber als Vorschlag genannt.
UMGANGSSPRACHE = {
    "absage": "abgelehnt",
    "eingeladen": "interview",
    "einladung": "interview",
    "vorstellungsgespraech": "interview",
    "zusage": "angebot",
    "ruecknahme": "zurueckgezogen",
}


def status_aus_text(text) -> str | None:
    """Der Status, den ein Text meint — oder None, wenn es ihn nicht gibt (#1146).

    Gross-/Kleinschreibung, Umlaute statt Umschrift ("Zweitgespräch",
    "zurückgezogen") und Leerzeichen oder Bindestrich statt Unterstrich
    ("in Vorbereitung") sind gleichgueltig. Weiter wird NICHT geraten: Ein
    Filter, der nichts trifft, ist keine leere Liste, sondern ein Fehler,
    den der Aufrufer mit den gueltigen Werten beantwortet.
    """
    roh = (text or "").strip().lower().translate(_UMSCHRIFT)
    roh = "_".join(roh.replace("-", " ").replace("_", " ").split())
    return roh if roh in ALLE else None


def vorschlag_fuer(text) -> str | None:
    """Der Status, den ein umgangssprachliches Wort meist meint, sonst None."""
    roh = (text or "").strip().lower().translate(_UMSCHRIFT)
    return UMGANGSSPRACHE.get(roh)
