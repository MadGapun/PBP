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
