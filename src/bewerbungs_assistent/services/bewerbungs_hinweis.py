"""Habe ich mich hier schon beworben? - eine Frage, eine Antwort (#1126).

Stellensuchende interessiert bei einer neuen Stelle vor allem eines:
"Habe ich mich da schon beworben?" Die Erkennung dafuer gibt es seit C30
(#782): `find_repost_of_application` in `duplicate_detection.py`. Sie war
aber nur in drei Werkzeugen fuer Claude angeschlossen - wer PBP im
Dashboard nutzt, sah nie, dass er sich schon beworben hatte. Gemessen am
29.09.2026 auf einer isolierten Datenbank: Werkzeug `stellen_anzeigen` ja,
`GET /api/jobs` nein, `GET /api/jobs/{hash}` nein.

Dieses Modul ist der EINE Weg dorthin. Alle Anschluesse - Werkzeuge,
Dashboard-Liste und -Detail, Suchlauf-Automatik - fragen `fuer_stelle`,
und keiner baut die Antwort nach (L1: eine Frage, eine Funktion). Die
Antwort hat zwei Arten:

* ``wiederholung`` - diese Stelle ist eine Bewerbung, die es schon gab
  (gleiche Anzeige oder Firma + Titel). Die starke Aussage.
* ``vermittler`` - eine laufende Bewerbung ueber einen Vermittler nennt
  diese Firma als Endkunden (#1076). Die schwache: PBP fragt, der Mensch
  prueft.

Nichts hier schreibt. Eine Liste abzurufen darf nichts veraendern (#945).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

WIEDERHOLUNG = "wiederholung"
VERMITTLER = "vermittler"


def _vermittler_hinweis(job: dict, bewerbung: dict) -> dict:
    from .anzeigenamen import datum_text, status_text
    firma = job.get("company") or ""
    vermittler = bewerbung.get("company") or ""
    titel = bewerbung.get("title") or ""
    datum = (bewerbung.get("applied_at") or bewerbung.get("created_at")
             or "")[:10]
    am = f" am {datum_text(datum)}" if datum else ""
    return {
        "art": VERMITTLER,
        "bewerbung_id": (bewerbung.get("id") or "")[:8],
        "bewerbung_id_voll": bewerbung.get("id") or "",
        "beworben_am": datum,
        "status": bewerbung.get("status") or "",
        "laeuft": True,
        "sicher": False,
        "titel_damals": titel,
        "firma_damals": vermittler,
        "match_grund": "vermittler_endkunde",
        "kurz": f"Schon beworben? Läuft über {vermittler}",
        "warnung": (
            f"Über {vermittler} läuft{am} eine Bewerbung („{titel}“), die "
            f"{firma} als Endkunden nennt (Stand: "
            f"{status_text(bewerbung.get('status'))}). Prüfen, ob es "
            "dieselbe Stelle ist — sonst landet eine zweite Bewerbung am "
            "Vermittler vorbei beim selben Arbeitgeber."),
    }


def fuer_stelle(job: dict, bewerbungen, db=None) -> Optional[dict]:
    """Die Antwort auf "habe ich mich hier schon beworben?" - oder None.

    Args:
        job: die Stelle (hash, title, company, url).
        bewerbungen: alle Bewerbungen, einmal geladen (`db.get_applications()`).
        db: nur fuer den dokumentierten Absagegrund im Text; ohne `db`
            bleibt der Grund aus der Bewerbung.

    Returns:
        Das Ergebnis von `find_repost_of_application` (Art
        ``wiederholung``) oder der Vermittler-Hinweis (Art ``vermittler``);
        beide tragen `warnung` (Satz fuer Claude), `kurz` (eine Zeile fuer
        die Karte), `laeuft`, `bewerbung_id_voll` und `sicher`.
    """
    from ..duplicate_detection import (
        bewerbungen_ohne_eigene, find_repost_of_application,
        find_vermittler_bewerbung)
    from .bewerbung_status import laeuft

    treffer = find_repost_of_application(job, bewerbungen, db=db)
    if treffer:
        return treffer
    laufende = [a for a in bewerbungen_ohne_eigene(job, bewerbungen)
                if laeuft(a.get("status"))]
    bewerbung = find_vermittler_bewerbung(job.get("company") or "", laufende)
    return _vermittler_hinweis(job, bewerbung) if bewerbung else None


def als_felder(hinweis: dict) -> dict:
    """Die Felder, unter denen ein Hinweis an eine Stelle gehaengt wird.

    Dieselben Namen in Werkzeug-Antworten und Dashboard - so laesst sich
    ein Test schreiben, der beide Wege gegeneinander haelt.
    """
    return {
        "repost_warnung": hinweis["warnung"],
        "repost_details": {k: v for k, v in hinweis.items() if k != "warnung"},
    }


def anreichern(db, jobs: list, *, bewerbungen=None) -> int:
    """Haengt jedem Treffer seinen Hinweis an (`repost_warnung`,
    `repost_details`) und meldet, wie viele einen bekamen.

    Die Bewerbungen werden EINMAL geladen, nicht je Stelle. Ein Fehler
    stoppt nie eine Liste.
    """
    if not jobs:
        return 0
    if bewerbungen is None:
        try:
            bewerbungen = db.get_applications()
        except Exception as exc:  # pragma: no cover - nie eine Liste stoppen
            logger.debug("Bewerbungen nicht lesbar (#1126): %s", exc)
            return 0
    if not bewerbungen:
        return 0
    anzahl = 0
    for job in jobs:
        try:
            hinweis = fuer_stelle(job, bewerbungen, db=db)
        except Exception as exc:  # pragma: no cover - nie eine Liste stoppen
            logger.debug("Hinweis fuer %s nicht berechenbar (#1126): %s",
                         job.get("hash"), exc)
            continue
        if hinweis:
            job.update(als_felder(hinweis))
            anzahl += 1
    return anzahl


def ist_wiederholung(job: dict, bewerbungen) -> bool:
    """Gab es diese Stelle schon als Bewerbung?

    Nur die starke Aussage (Art ``wiederholung``); der Vermittler-Verdacht
    ist eine Frage an den Menschen und haelt die Automatik nicht auf.
    """
    from ..duplicate_detection import find_repost_of_application
    return find_repost_of_application(job, bewerbungen) is not None
