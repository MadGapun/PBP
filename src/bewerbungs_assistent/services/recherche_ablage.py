"""Recherche liegt an EINEM Ort (#956).

PBP hielt Firmenrecherche in zwei getrennten Speichern:

1. `jobs.research_notes` — eine Freitextspalte an der STELLE (#240/#463),
   gespeist vom Eingabefeld im Bewerbungs-Detail.
2. Tabelle `research_notes` — an der BEWERBUNG (#673/#674), gespeist von
   `firmen_recherche`, `skill_gap_analyse`, `branchen_trends` und
   `recherche_speichern`.

Die Trennung war keine Fachentscheidung, sondern der Rest davon, dass
#673/#674 das bessere Modell nachgeliefert haben, ohne das aeltere
abzuraeumen. Derselbe Fehlertyp wie #764 (`applications.job_hash` gegen
`application_jobs`): neues Modell eingefuehrt, altes bleibt daneben
stehen und driftet. Sichtbar wurde es daran, dass ueber gespeicherten
Recherchen ein LEERES Eingabefeld stand — wer es sah, schloss daraus,
es sei nichts gespeichert.

## Was die Messung am Bestand ergeben hat (10.09.2026)

Der Vorschlag im Issue lautete, die Spalten-Inhalte in die
bewerbungsgebundene Tabelle zu migrieren. Gemessen sieht es anders aus:

* **143** Stellen tragen einen Inhalt in `jobs.research_notes`,
* davon haengen **5** an einer Bewerbung — der Rest an gar keiner,
* und **30 der 143 sind ueberhaupt keine Recherche**, sondern
  Aussortier-Protokoll ("[Auto-Aussortierung] …", abgelehnte
  Recruiter-Anfragen).

Daraus folgen zwei Ziele statt einem:

* **Recherche** geht in die Tabelle `research_notes`. Die kann seit
  jeher auch an einer STELLE haengen (`job_hash`, eigener Index) — ohne
  das waeren 138 der 143 Eintraege nicht migrierbar gewesen.
* **Protokoll** geht nach `jobs.dismiss_note`. Dafuer gibt es die
  Spalte seit #913, und `dismiss_job` ist ohnehin das Nadeloehr jedes
  Aussortier-Writes.

**Ein Aussortier-Protokoll in einer Recherche-Liste waere kein
Aufraeumen, sondern eine zweite Verwechslung** — deshalb trennt die
Migration die beiden Sorten, statt alles in einen Topf zu schieben.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Die Kategorie, unter der eine von Hand geschriebene Firmennotiz
# abgelegt wird. Dieselbe wie bei `firmen_recherche` — es ist dieselbe
# Sache, nur mit einem Menschen als Verfasser.
KATEGORIE_MANUELL = "firmenrecherche"

# Woran ein Protokoll-Eintrag im Altbestand zu erkennen ist. Bewusst
# eine kurze, belegte Liste statt einer Heuristik: jeder dieser Marker
# stammt aus einem der drei Schreibwege, die es gab.
PROTOKOLL_MARKER = (
    "[Auto-Aussortierung]",
    "Recruiter-Anfrage abgelehnt",
    "Bewerbung zurueck in Anfrage",
    "Bewerbung zurück in Anfrage",
)


def ist_protokoll(text) -> bool:
    """Ist dieser Spalteninhalt ein Aussortier-Protokoll, keine Recherche?"""
    inhalt = str(text or "")
    return any(marker in inhalt for marker in PROTOKOLL_MARKER)


def speichern(db, text: str, *, kategorie: str = KATEGORIE_MANUELL,
              bewerbung_id: str = "", job_hash: str = "") -> dict:
    """Legt einen Recherche-Eintrag ab — der eine Weg dorthin.

    Wer eine Recherche speichert, ruft das hier. Ein zweiter Weg auf
    eine andere Spalte waere genau die Bauform, die dieses Projekt
    inzwischen elfmal gekostet hat (#963, #913, #976, #987, #991, #992,
    #994, #1008, #1012, #1011).

    Returns:
        dict mit `status` ('gespeichert', 'leer', 'fehler').
        Wirft nie: eine Notiz darf den Vorgang nicht kippen, an dem sie
        haengt.
    """
    inhalt = (text or "").strip()
    if not inhalt:
        return {"status": "leer", "grund": "kein Text"}
    try:
        neu_id = db.add_research_note(
            kategorie=(kategorie or KATEGORIE_MANUELL),
            text=inhalt,
            bewerbung_id=bewerbung_id or None,
            job_hash=job_hash or None,
        )
        return {"status": "gespeichert", "id": neu_id,
                "kategorie": kategorie or KATEGORIE_MANUELL}
    except Exception as exc:  # pragma: no cover — kippt nie den Vorgang
        logger.debug("Recherche nicht ablegbar: %s", exc)
        return {"status": "fehler", "fehler": str(exc)}


def lesen(db, *, bewerbung_id: str = "", job_hash: str = "") -> list:
    """Alle Recherchen zu einer Bewerbung ODER Stelle.

    Der Lese-Kasten im Bewerbungs-Detail haengt an der BEWERBUNG, der
    Entwurf im Eingabefeld hing bisher an der STELLE. Beides aus einer
    Quelle zu holen ist der ganze Punkt dieses Issues.
    """
    try:
        return db.get_research_notes(
            bewerbung_id=bewerbung_id or None,
            job_hash=job_hash or None,
        ) or []
    except Exception as exc:  # pragma: no cover — nie eine Seite stoppen
        logger.debug("Recherchen nicht lesbar: %s", exc)
        return []
