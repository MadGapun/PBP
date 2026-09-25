"""Ein Wert je Stelle, an allen Orten (C96, #1087 C1) — und was er bedeutet (H24, G4).

Befund aus dem UX-Review: dieselbe Stelle trug auf der Karte "Fachwert 5",
im Dashboard "Score 5", im Fit-Dialog "Gesamtscore 7" (mit Faktoren, die
zusammen 12 ergaben), in der Bewerbungs-Timeline eine dritte Zahl und in
`stellen_anzeigen` eine vierte. Die Ursachen waren verschieden:

* Liste und Dashboard zeigten den Wert NACH allen Scoring-Reglern, also
  auch nach Entfernungs-, Remote- und Gehaltsreglern — und nannten ihn
  "Fachwert". Seit v1.7.117 gehoert der Rahmen aber nicht in die Zahl.
* Die Timeline zeigte den gespeicherten Wert ohne jeden Regler.
* Der Fit-Dialog rechnete frisch und listete Fach- UND Rahmenfaktoren
  untereinander, als wuerden sie sich addieren.

Entscheidung (#1087): angezeigt wird ueberall der **Fachwert nach
v1.7.117 mit den Begriffs-Reglern, ohne die Rahmen-Regler** — also
`fach_score` aus `apply_scoring_adjustments`. Der Rahmen steht nur als
Daumen daneben. Die Zahl heisst "Punkte"; wo ein Hoechstwert erreichbar
ist, steht er dabei ("7 von 26 Punkten").

Alle Orte rufen `anreichern` (Listen) bzw. `fuer_frisch` (Fit-Dialog),
keiner rechnet selbst. Ein Test vergleicht die Orte an einer festen
Stelle.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# H24 (#1087 G4): EIN Satz fuer alle Prompts, Antworten und Hilfetexte.
# Prompts sagten "Fit-Score (0-20 Punkte) ... wie gut sie zu deinem Profil
# passt", "Dein Match liegt bei X%" und "erhoeht den Match-Score um bis zu
# 30%". Der Code sagt: der Lebenslauf geht nicht ein, eine feste Skala
# gibt es nicht, und Prozent sind keine Aussage ueber Passung.
SCORE_BEDEUTUNG = (
    "Die Punkte zeigen, wie gut eine Anzeige deine Suchbegriffe trifft "
    "(Pflicht- und Wunschbegriffe, abzueglich Ausschlussbegriffe). Mehr "
    "ist besser. Sie sind kein Urteil darueber, ob du passt — dein "
    "Lebenslauf geht nicht ein, und Ort, Gehalt und Arbeitsmodell stehen "
    "getrennt daneben. Es gibt keine Prozentangabe und keine feste Skala; "
    "wo ein Hoechstwert erreichbar ist, steht er dabei."
)

# Faktoren des Fit-Dialogs, die in die Punkte eingehen. Alles andere
# (Entfernung, Remote, Gehalt, Kompetenzen) ist Rahmen oder Information.
FACH_PRAEFIXE = (
    "MUSS-Keywords", "PLUS-Keywords", "MINUS-Keywords",
    "Abzuege ueber Deckel", "Wunschbegriffe ueber Deckel",
    "Kein MUSS-Keyword", "AUSSCHLUSS-Keyword", "Ausserhalb des erreichbaren",
)
REGLER_LABEL = "Deine Regler für Begriffe"


def _anpassung(db, job: dict, basis: float) -> dict:
    try:
        from .scoring_service import apply_scoring_adjustments
        return apply_scoring_adjustments(job, basis, db) or {}
    except Exception as exc:  # pragma: no cover - nie eine Anzeige stoppen
        logger.debug("Regler nicht anwendbar: %s", exc)
        return {}


def maximum(db) -> float | None:
    """Fachlicher Hoechstwert aus den Kriterien, None wenn keiner erreichbar."""
    try:
        from . import scoring_kriterien
        from ..job_scraper import fach_maximum
        wert = float(fach_maximum(scoring_kriterien.fuer_scoring(db)) or 0)
    except Exception as exc:  # pragma: no cover
        logger.debug("Hoechstwert nicht bestimmbar: %s", exc)
        return None
    return round(wert, 1) if wert > 0 else None


def _runden(wert) -> float:
    try:
        return round(float(wert or 0), 1)
    except (TypeError, ValueError):
        return 0.0


def fuer_gespeichert(db, job: dict) -> float:
    """Punkte aus dem gespeicherten Fachwert plus Begriffs-Regler."""
    basis = _runden(job.get("score"))
    erg = _anpassung(db, job, basis)
    return _runden(erg.get("fach_score", erg.get("final_score", basis)))


def anreichern(db, jobs: list, hoechstwert: float | None = ...) -> list:
    """Setzt `punkte` und `punkte_max` an jede Stelle (in place).

    Hat der Aufrufer die Regler schon angewandt (`fach_score` steht da),
    wird nichts doppelt gerechnet.
    """
    if hoechstwert is ...:
        hoechstwert = maximum(db)
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        if "fach_score" in job:
            job["punkte"] = _runden(job["fach_score"])
        else:
            job["punkte"] = fuer_gespeichert(db, job)
        job["punkte_max"] = hoechstwert
    return jobs


def fuer_frisch(db, job: dict, analyse: dict) -> dict:
    """Punkte aus einer frischen `fit_analyse`, samt Faktoren, die sich
    genau zu dieser Zahl addieren.

    Die Begriffs-Regler stehen als eigene Zeile, damit die Summe stimmt.
    Weicht der gespeicherte Stand ab (der Anzeigentext oder die Kriterien
    haben sich seit der letzten Bewertung geaendert), wird das benannt,
    statt zwei Zahlen ohne Erklaerung nebeneinander zu stellen.
    """
    basis = _runden(analyse.get("total_score"))
    erg = _anpassung(db, job, basis)
    punkte = _runden(erg.get("fach_score", erg.get("final_score", basis)))
    fach = dict(analyse.get("faktoren_fach") or {})
    regler = round(punkte - basis, 1)
    if regler:
        fach[REGLER_LABEL] = regler
    gespeichert = fuer_gespeichert(db, job)
    hoechst = maximum(db)
    ergebnis = {
        "punkte": punkte,
        "punkte_max": hoechst,
        "punkte_text": text(punkte, hoechst),
        "faktoren_fach": fach,
        "faktoren_rahmen": dict(analyse.get("faktoren_rahmen") or {}),
        "punkte_gespeichert": gespeichert,
        "score_bedeutung": SCORE_BEDEUTUNG,
    }
    if abs(gespeichert - punkte) >= 0.05:
        ergebnis["punkte_hinweis"] = (
            f"In der Liste steht noch {gespeichert:g} — das ist der Stand der "
            f"letzten Bewertung. Mit dem heutigen Anzeigentext und deinen "
            f"heutigen Suchbegriffen sind es {punkte:g}. „Punkte neu "
            f"berechnen“ in den Einstellungen gleicht die Liste an.")
    return ergebnis


def text(punkte, hoechstwert=None) -> str:
    """"7 von 26 Punkten" oder "7 Punkte" (Anzeige in Antworten)."""
    p = _runden(punkte)
    if hoechstwert and 0 <= p <= hoechstwert:
        return f"{p:g} von {hoechstwert:g} Punkten"
    return f"{p:g} Punkte" if p != 1 else "1 Punkt"


def faktoren_teilen(factors: dict, neigung_label: str | None = None) -> tuple[dict, dict]:
    """Trennt die Faktoren in Fach (addieren sich zur Zahl) und Rahmen."""
    fach, rahmen = {}, {}
    for label, wert in (factors or {}).items():
        if (str(label).startswith(FACH_PRAEFIXE)
                or (neigung_label and label == neigung_label)):
            fach[label] = wert
        else:
            rahmen[label] = wert
    return fach, rahmen
