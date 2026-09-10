"""Den Altbestand aus `jobs.research_notes` an seinen Ort bringen (#956).

Seit v1.7.70 schreibt niemand mehr in die Spalte. Was drinsteht, bleibt
bis hierher liegen — und es sind zwei verschiedene Sorten:

* **Recherche** (113 von 143, gemessen am 10.09.2026) — gehoert in die
  Tabelle `research_notes`, zu allen anderen Recherchen.
* **Aussortier-Protokoll** (30 von 143) — gehoert nach
  `jobs.dismiss_note`, wo Freitext zu einer Aussortierung seit #913
  hingehoert.

**Alles in einen Topf zu schieben waere kein Aufraeumen, sondern eine
zweite Verwechslung** — dann stuenden Aussortier-Vermerke in der
Recherche-Liste. Deshalb trennt dieser Lauf die beiden Sorten.

## Vorgabe ist ZAEHLEN, nicht Verschieben

`dry_run=True` ist der Default, wie bei `stellen_urls_heilen` und
`bewerbungs_stellen_abgleichen`. Ein Lauf, der ungefragt 143 Datensaetze
umschreibt, ist keine Migration, sondern eine Ueberraschung.

## Idempotent, und zwar durch Leeren

Nach dem Verschieben wird die Spalte geleert. Der zweite Lauf findet
deshalb nichts mehr — ohne Merkliste, ohne Zeitstempel, ohne eine
zweite Wahrheit darueber, was schon gelaufen ist.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _kandidaten(db) -> list:
    """Alle Stellen mit Inhalt in der alten Spalte."""
    try:
        return db.connect().execute(
            "SELECT hash, research_notes, dismiss_note, is_active "
            "FROM jobs WHERE research_notes IS NOT NULL "
            "AND TRIM(research_notes) != ''"
        ).fetchall()
    except Exception as exc:  # pragma: no cover — nie einen Lauf stoppen
        logger.debug("Kandidaten nicht lesbar: %s", exc)
        return []


def zusammenfuehren(db, *, dry_run: bool = True, max_stellen: int = 0) -> dict:
    """Verschiebt den Altbestand — oder zaehlt ihn nur.

    Args:
        dry_run: Vorgabe True. Es wird NICHTS geschrieben, nur gezaehlt.
        max_stellen: 0 = alle.

    Returns:
        dict mit den Zahlen je Sorte und einer Stichprobe OHNE Inhalte —
        eine Recherche-Notiz kann alles enthalten, auch einen Namen.
    """
    from . import recherche_ablage

    zeilen = _kandidaten(db)
    if max_stellen > 0:
        zeilen = zeilen[:max_stellen]

    recherche = protokoll = fehler = 0
    proben: list[dict] = []

    for zeile in zeilen:
        inhalt = (zeile["research_notes"] or "").strip()
        if not inhalt:
            continue
        hash_ = zeile["hash"]
        art = "protokoll" if recherche_ablage.ist_protokoll(inhalt) else "recherche"
        if len(proben) < 10:
            proben.append({
                "stelle": str(hash_)[-8:],
                "art": art,
                "zeichen": len(inhalt),
            })

        if dry_run:
            if art == "protokoll":
                protokoll += 1
            else:
                recherche += 1
            continue

        try:
            if art == "protokoll":
                _protokoll_umziehen(db, zeile, inhalt)
                protokoll += 1
            else:
                ergebnis = recherche_ablage.speichern(
                    db, inhalt, job_hash=hash_,
                    bewerbung_id=_bewerbung_zu(db, hash_))
                if ergebnis.get("status") != "gespeichert":
                    fehler += 1
                    continue
                recherche += 1
            # Erst wenn der Inhalt sicher woanders liegt.
            db.update_job(hash_, {"research_notes": ""})
        except Exception as exc:  # pragma: no cover
            logger.debug("Umzug fehlgeschlagen (%s): %s", hash_, exc)
            fehler += 1

    return {
        "status": "vorschau" if dry_run else "verschoben",
        "kandidaten": len(zeilen),
        "recherche": recherche,
        "protokoll": protokoll,
        "fehler": fehler,
        # KEINE Notizinhalte — nur Art und Groessenordnung.
        "stichprobe": proben,
        "hinweis": (
            "Vorschau — es wurde nichts geschrieben. Mit dry_run=False "
            "wird verschoben; ein zweiter Lauf findet danach nichts mehr."
            if dry_run else
            "Die alte Spalte ist fuer diese Stellen geleert. Recherchen "
            "stehen jetzt bei allen anderen, Protokolle bei der "
            "Aussortierung."),
    }


def _protokoll_umziehen(db, zeile, inhalt: str) -> None:
    """Protokolltext nach `dismiss_note` — ohne den Status anzufassen.

    Bewusst KEIN `dismiss_job`: der Aufruf wuerde `is_active` auf 0
    setzen und einen Zeitpunkt schreiben. Eine Stelle, die aus welchem
    Grund auch immer wieder aktiv ist, waere danach still wieder
    aussortiert — eine Migration darf den Bestand einordnen, nicht ueber
    ihn entscheiden.
    """
    vorhanden = (zeile["dismiss_note"] or "").strip()
    if vorhanden:
        neu = f"{vorhanden}; {inhalt}"
    else:
        neu = inhalt
    db.connect().execute(
        "UPDATE jobs SET dismiss_note=? WHERE hash=?",
        (neu[:500], zeile["hash"]),
    )
    db.connect().commit()


def _bewerbung_zu(db, job_hash: str) -> str:
    """Die Bewerbung zu dieser Stelle — falls es eine gibt.

    Gemessen: nur **5 von 143** Stellen mit Notizblock haengen an einer
    Bewerbung. Genau deshalb geht der Rest job-gebunden in die Tabelle
    (`job_hash` samt Index gibt es dort seit #674) — waere die Tabelle
    nur bewerbungsgebunden, waeren 138 Eintraege nicht migrierbar.
    """
    try:
        roh = str(job_hash or "")
        kurz = roh.split(":", 1)[-1]
        zeile = db.connect().execute(
            "SELECT id FROM applications WHERE job_hash IN (?, ?) LIMIT 1",
            (roh, kurz),
        ).fetchone()
        return zeile["id"] if zeile else ""
    except Exception:  # pragma: no cover
        return ""
