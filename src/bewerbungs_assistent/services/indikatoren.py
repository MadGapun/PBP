"""Die beiden Daumen an der Stelle — an EINER Stelle gerechnet (#1052).

Der Fachwert sagt etwas ueber die Anzeige, der Rahmen ueber die
Lebensumstaende. Beide werden als Daumen angezeigt, und beide tragen
zwei getrennte Kanaele: die RICHTUNG kommt aus den Angaben, die FARBE
sagt, wie belegt diese Angaben sind. Ein grauer Daumen nach unten
heisst "sieht schlecht aus, aber ungeprueft" — damit ist der Indikator
nie nutzlos und nie erfunden (Nutzervorgabe 15.09.2026).

**Warum ein eigenes Modul.** Die Liste gibt es zweimal: als
`stellen_anzeigen` (MCP) und als `GET /api/jobs` (Stellen-Tab). Beide
brauchen dieselbe Auskunft, und zwei Fassungen davon waeren das Muster,
das dieses Projekt seit #963 immer wieder gekostet hat — zuletzt in
genau dieser Liste (#1008: derselbe Feldname trug in beiden Wegen
verschiedene Zahlen).

**Warum ein Kontext statt eines Aufrufs je Stelle.** Die Schwellen
entstehen aus der ganzen Bewerbungshistorie; sie je Zeile neu zu rechnen
hiesse, den Bestand hundertmal zu lesen. Dieselbe Bauform wie die
Synonyme in #987 und die Datenguete in #989: einmal je Aufruf
vorbereiten, dann je Zeile anwenden.

**Der Rahmen ist ein Indikator, kein Tor** (Nutzerantwort 15.09.2026).
Er sortiert nichts um und schliesst nichts aus. Was mit seiner Auskunft
geschieht, entscheidet ein Filter, den der Mensch bedient.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def kontext(db, criteria: dict | None = None) -> dict:
    """Alles, was fuer ALLE Zeilen dasselbe ist.

    Args:
        criteria: die angereicherten Kriterien. Fehlen sie, kommen sie
            aus `scoring_kriterien.fuer_scoring` — am Nadeloehr aus #987
            vorbei zu lesen war dort der teuerste Fehler der Reihe.
    """
    from . import fachwert, scoring_kriterien

    try:
        krit = criteria if criteria is not None else scoring_kriterien.fuer_scoring(db)
    except Exception as exc:  # pragma: no cover — nie eine Liste stoppen
        logger.debug("Kriterien nicht lesbar: %s", exc)
        krit = {}
    try:
        schwellen = fachwert.schwellen(db, krit)
    except Exception as exc:  # pragma: no cover
        logger.debug("Schwellen nicht bestimmbar: %s", exc)
        schwellen = {"grundlage_fehlt": "Die Schwellen liessen sich nicht "
                                        "bestimmen."}
    try:
        from ..job_scraper import fach_maximum
        erreichbar = fach_maximum(krit)
    except Exception as exc:  # pragma: no cover
        logger.debug("Fachmaximum nicht bestimmbar: %s", exc)
        erreichbar = 0.0
    return {"kriterien": krit, "schwellen": schwellen,
            "fach_maximum": erreichbar}


def _fach_belegt(job: dict) -> bool:
    """Steht hinter dem Fachwert ein Anzeigentext?

    Ohne Beschreibung ist der Fachwert aus dem Titel geraten — er ist
    nicht falsch, er ist ungeprueft (#756, #989). Das ist genau der
    Unterschied, den die Farbe traegt.
    """
    from . import datenguete

    text = (job.get("description") or "").strip()
    return len(text) >= datenguete.MIN_BESCHREIBUNG


def fuer_stelle(job: dict, ktx: dict) -> dict:
    """Beide Daumen fuer EINE Stelle.

    Returns:
        {"fach": {...}, "rahmen": {...}, "fach_maximum": float} — die
        Marken selbst, damit der Aufrufer entscheidet, wie er sie
        ablegt. Geschrieben wird hier nichts.
    """
    from . import fachwert, rahmen

    ktx = ktx or {}
    try:
        # v1.7.127 (#1082): der Fachwert OHNE die Rahmen-Regler. Die
        # Liste traegt in `score` den Wert samt Entfernung, Remote und
        # Gehalt — damit zeigte der Fachdaumen einer fachlich starken
        # Stelle in 450 km nach unten, also genau die Vermischung, die
        # die beiden Daumen aufheben sollen.
        _fach = job.get("fach_score")
        fach = fachwert.daumen(_fach if _fach is not None else job.get("score"),
                               ktx.get("schwellen") or {},
                               belegt=_fach_belegt(job))
    except Exception as exc:  # pragma: no cover — nie eine Liste stoppen
        logger.debug("Fachdaumen uebersprungen: %s", exc)
        fach = None
    try:
        rahmen_marke = rahmen.daumen(job, ktx.get("kriterien") or {})
    except Exception as exc:  # pragma: no cover
        logger.debug("Rahmendaumen uebersprungen: %s", exc)
        rahmen_marke = None
    befund: dict = {}
    if fach:
        befund["fach"] = fach
    if rahmen_marke:
        befund["rahmen"] = rahmen_marke
    if ktx.get("fach_maximum"):
        # #1052 AK 2: was fachlich ueberhaupt erreichbar waere. Die Zahl
        # steht als DETAIL daneben, nie als Anteil — es gibt weder eine
        # Ober- noch eine Untergrenze (Nutzerwort 16.09.2026), und ein
        # Prozentwert haette beide behauptet.
        befund["fach_maximum"] = ktx["fach_maximum"]
    return befund


def anhaengen(jobs: list, ktx: dict) -> None:
    """Haengt jeder Stelle ihre beiden Daumen an (in place).

    Die Felder heissen `fach_daumen` und `rahmen_daumen`. **Keine
    Summe** — die beiden stehen nebeneinander, und das ist das erste
    Akzeptanzkriterium von #1052.
    """
    for job in jobs or []:
        befund = fuer_stelle(job, ktx)
        if befund.get("fach"):
            job["fach_daumen"] = befund["fach"]
        if befund.get("rahmen"):
            job["rahmen_daumen"] = befund["rahmen"]
        if befund.get("fach_maximum"):
            job["fach_maximum"] = befund["fach_maximum"]
        # v1.7.127 (#1082 AK 3): der naehere Standort aus der Anzeige —
        # sonst sieht man einer Entfernung nicht an, woher sie kommt.
        try:
            from . import standorte
            weiterer = standorte.naechster(job, ktx.get("kriterien") or {})
            if weiterer:
                job["naechster_standort"] = weiterer
        except Exception as exc:  # pragma: no cover
            logger.debug("Standorte uebersprungen: %s", exc)


def rahmen_passt_nicht(job: dict) -> bool:
    """Taugt fuer den Filter "Rahmen passt nicht ausblenden".

    BELEGT und "runter" — beides zusammen. Ein grauer Daumen nach unten
    heisst "ungeprueft", und etwas Ungeprueftes auszublenden waere
    genau die Verwechslung aus #989: fehlende Information wirkt wie eine
    negative Auskunft.
    """
    from . import rahmen

    marke = job.get("rahmen_daumen") or {}
    return (marke.get("richtung") == rahmen.RUNTER
            and marke.get("farbe") == rahmen.BELEGT)
