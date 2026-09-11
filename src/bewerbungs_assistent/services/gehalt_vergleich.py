"""Ein Jahresaequivalent, zwei Rechenwege (#1017).

Die Frage "verdient man an dieser Stelle genug" wurde an DREI Orten
beantwortet, und sie kannten verschiedene Regeln:

| Ort | Schaetzung neutral | kennt `stuendlich` |
|---|---|---|
| `fit_analyse` | ja, seit #827/#918 | ja, seit #920 |
| `scoring_service` (Regler) | ja, seit #827 | ja, seit #920 |
| `calculate_score` | **nein** | **nein** |

`calculate_score` schreibt den Wert, der als `jobs.score` in der
Datenbank landet und die Trefferliste sortiert — also ausgerechnet der
Weg, auf den es ankommt. Das ist #963/#987/#991/#992 zum sechzehnten
Mal: zwei Rechenwege, einer kennt eine Regel, die der andere nicht hat.

Gemessen am Bestand des Melders: **976 von 984** aktiven Stellen tragen
ein GESCHAETZTES Gehalt. Am hiesigen Bestand (2.535 Stellen, Kopie):
2.406 geschaetzt, 60 echt, 69 ohne Angabe. Der Gehaltsbonus beruhte
damit bei 95 Prozent aller Stellen auf einer Zahl, die in der Anzeige
nie stand.

## Was dieses Modul entscheidet — und was nicht

Es bildet ein JAHRESAEQUIVALENT aus `salary_min`, `salary_type`,
`employment_type` und den Wunschwerten, und es sagt, ob dieser
Vergleich ueberhaupt tragfaehig ist. Es vergibt KEINE Punkte: wie viel
ein erfuellter Gehaltswunsch wert ist, entscheidet jeder Rechenweg
weiter selbst (der Basis-Score kennt `w["gehalt"]`, der Regler rechnet
in Prozentschritten). Ein gemeinsames Nadeloehr fuer die MESSUNG, nicht
fuer die Bewertung.

## Warum eine Schaetzung keine Punkte bringt (#827)

`estimate_salary` vergibt eine von wenigen schematischen Spannen. Das
ist eine Aussage ueber die Schaetzlogik, nicht ueber die Stelle. Bei
der Dimension mit dem hoechsten Gewicht waere auch die Haelfte davon
Scheingenauigkeit. Wichtig ist die Form der Antwort: `GESCHAETZT` ist
NICHT dasselbe wie `OHNE_ANGABE` und beide sind nicht "verdient zu
wenig" — genau diese Verwechslung hat #989 abgeschafft. Der Aufrufer
bekommt drei unterscheidbare Zustaende und kann sie benennen.
"""
from __future__ import annotations

# Zustaende. Nur bei VERGLEICHBAR gibt es ueberhaupt etwas zu rechnen.
VERGLEICHBAR = "vergleichbar"
GESCHAETZT = "geschaetzt"
OHNE_ANGABE = "ohne_angabe"
OHNE_WUNSCH = "ohne_wunsch"

# Umrechnungsfaktoren. Sie standen bisher als Zahlenliterale in beiden
# Rechenwegen; 220 Arbeitstage und 8 Stunden sind die Annahme, die
# `fit_analyse` seit #920 benutzt.
TAGE_PRO_JAHR = 220
STUNDEN_PRO_TAG = 8

# Ab wie weit unter dem Wunsch ein Risiko gemeldet wird (aus fit_analyse).
DEUTLICH_DARUNTER = 0.8


def _zahl(wert) -> float:
    try:
        return float(wert or 0)
    except (TypeError, ValueError):
        return 0.0


def _stuendlich(criteria: dict) -> tuple:
    """Wunsch fuer einen Stundensatz — mit derselben Rueckfallkette wie
    `fit_analyse` seit #920: erst der Stundensatz, dann der Tagessatz,
    dann das Jahresgehalt. Der Rueckfall ist noetig, weil die meisten
    Profile keinen Stundensatz pflegen."""
    stunde = _zahl(criteria.get("min_stundensatz"))
    if stunde:
        return stunde * STUNDEN_PRO_TAG * TAGE_PRO_JAHR, f"{stunde:g} EUR/Stunde"
    tag = _zahl(criteria.get("min_tagessatz"))
    if tag:
        return tag * TAGE_PRO_JAHR, f"{tag:g} EUR/Tag"
    jahr = _zahl(criteria.get("min_gehalt"))
    return jahr, f"{jahr:g} EUR/Jahr"


def _taeglich(criteria: dict) -> tuple:
    tag = _zahl(criteria.get("min_tagessatz"))
    if tag:
        return tag * TAGE_PRO_JAHR, f"{tag:g} EUR/Tag"
    jahr = _zahl(criteria.get("min_gehalt"))
    return jahr, f"{jahr:g} EUR/Jahr"


def vergleich(job: dict, criteria: dict) -> dict:
    """Das Jahresaequivalent einer Stelle gegen den Wunsch.

    Rueckgabe immer ein dict, nie None — ein Aufrufer, der auf `None`
    pruefen muss, baut sich die naechste stille Null.

        stand      einer der vier Zustaende oben
        job_jahr   Jahresaequivalent der Stelle, sonst None
        wunsch_jahr Jahresaequivalent des Wunsches, sonst None
        erfuellt   True, wenn die Stelle den Wunsch erreicht
        deutlich_darunter True unter 80 Prozent des Wunsches
        job_text / wunsch_text  fertige Beschriftung samt EINHEIT
        grund      Klartext, wenn nicht vergleichbar
    """
    leer = {
        "stand": OHNE_ANGABE, "job_jahr": None, "wunsch_jahr": None,
        "erfuellt": False, "deutlich_darunter": False,
        "job_text": "", "wunsch_text": "", "grund": "",
    }

    betrag = _zahl(job.get("salary_min"))
    if not betrag:
        leer["grund"] = "Die Anzeige nennt kein Gehalt."
        return leer

    if job.get("salary_estimated"):
        # #827: geschaetzt ist nicht "zu wenig" und nicht "keine Angabe".
        leer["stand"] = GESCHAETZT
        leer["grund"] = "Gehalt: nur Schaetzung — neutral (#827)"
        return leer

    art = (job.get("salary_type") or "jaehrlich").lower()
    anstellung = (job.get("employment_type") or "festanstellung").lower()

    if art == "stuendlich":
        job_jahr = betrag * STUNDEN_PRO_TAG * TAGE_PRO_JAHR
        wunsch_jahr, wunsch_text = _stuendlich(criteria)
        job_text = f"{betrag:g} EUR/Stunde (~{int(job_jahr)} EUR/Jahr)"
    elif art == "taeglich" or anstellung == "freelance":
        job_jahr = betrag * TAGE_PRO_JAHR
        wunsch_jahr, wunsch_text = _taeglich(criteria)
        job_text = f"{betrag:g} EUR/Tag (~{int(job_jahr)} EUR/Jahr)"
    else:
        job_jahr = betrag
        wunsch_jahr = _zahl(criteria.get("min_gehalt"))
        wunsch_text = f"{wunsch_jahr:g} EUR/Jahr"
        job_text = f"{betrag:g} EUR/Jahr"

    if not wunsch_jahr:
        return {
            "stand": OHNE_WUNSCH, "job_jahr": job_jahr, "wunsch_jahr": None,
            "erfuellt": False, "deutlich_darunter": False,
            "job_text": job_text, "wunsch_text": "",
            "grund": "Kein Wunschwert gesetzt — es gibt nichts zu vergleichen.",
        }

    return {
        "stand": VERGLEICHBAR,
        "job_jahr": job_jahr,
        "wunsch_jahr": wunsch_jahr,
        "erfuellt": job_jahr >= wunsch_jahr,
        "deutlich_darunter": job_jahr < wunsch_jahr * DEUTLICH_DARUNTER,
        "job_text": job_text,
        "wunsch_text": wunsch_text,
        "grund": "",
    }
