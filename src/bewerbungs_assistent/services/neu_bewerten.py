"""Punkte einer Menge von Stellen neu rechnen — EIN Weg (#1090).

Herausgeloest aus dem Werkzeug `scores_neu_berechnen`, weil der
Entfernungs-Nachzug aus #1090 nach einem neuen Standort dieselbe Rechnung
braucht. Eine zweite Schleife waere #963 an einer neuen Stelle.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("bewerbungs_assistent.neu_bewerten")


def neu_bewerten(db, jobs: list, criteria: dict) -> dict:
    """Rechnet `jobs` mit `criteria` neu und speichert, was sich aendert.
    `criteria` kommt aus `scoring_kriterien.fuer_scoring` (#987)."""
    from ..job_scraper import calculate_score
    recomputed = 0
    unchanged = 0
    deltas: list[int] = []
    # v1.7.17 (#917 Defekt D): der Batch setzte Scores STUMM auf 0 —
    # eine gute Stelle rutschte von 83 auf 0 (Ausschluss-Keyword in
    # einer redaktionellen Notiz) und niemand erfuhr warum, waehrend
    # stelle_bearbeiten denselben Fall sauber begruendet. Jetzt
    # liefert der Lauf fuer harte Nullungen und grosse Ruecklaeufe
    # den Grund mit.
    auffaellig: list[dict] = []
    for j in jobs:
        # v1.7.95 (#1035): `int()` rundet nicht, es schneidet ab — aus
        # 18,7 wurde 18, und 3,8 gegen 3,0 galt als unveraendert. Der
        # Score hat eine Nachkommastelle; so wird er verglichen und
        # gespeichert.
        old_score = round(float(j.get("score") or 0), 1)
        try:
            new_score = round(float(calculate_score(j, criteria)), 1)
        except Exception as e:
            logger.warning("Score-Recompute fuer %s fehlgeschlagen: %s",
                           j.get("hash"), e)
            continue
        # v1.7.22 (#942): Teilscores immer nachziehen, auch wenn die
        # Summe gleich bleibt — der Bestand hat sie noch gar nicht,
        # und ohne sie zeigt die Liste weiter nur eine nackte Zahl.
        _teile = {}
        if j.get("_fachscore") is not None:
            _teile = {"fachscore": j.get("_fachscore"),
                      "rahmenscore": j.get("_rahmenscore")}
        if new_score == old_score and _teile:
            try:
                db.update_job(j.get("hash"), _teile)
            except Exception:
                pass
        if new_score != old_score:
            try:
                db.update_job(j.get("hash"), {"score": new_score, **_teile})
                recomputed += 1
                deltas.append(new_score - old_score)
            except Exception as e:
                logger.warning("update_job fuer %s fehlgeschlagen: %s",
                               j.get("hash"), e)
                continue
            if new_score == 0 and j.get("_ko_ausschluss"):
                auffaellig.append({
                    "hash": j.get("hash"),
                    "titel": j.get("title"),
                    "alt": old_score, "neu": 0,
                    "grund": (f"Ausschluss-Keyword "
                              f"'{j['_ko_ausschluss']}' im Text — "
                              "harter K.o. Steht der Begriff in einer "
                              "redaktionellen Notiz, gehört sie "
                              "hinter eine '---'-Trennzeile (#603)."),
                })
            elif new_score - old_score <= -20:
                auffaellig.append({
                    "hash": j.get("hash"),
                    "titel": j.get("title"),
                    "alt": old_score, "neu": new_score,
                    "grund": "starker Rückgang — Kriterien/Regler "
                             "prüfen (scoring_vorschau zeigt die "
                             "Rechnung im Detail)",
                })
        else:
            unchanged += 1

    avg_delta = sum(deltas) / len(deltas) if deltas else 0
    result = {
        "status": "fertig",
        "verarbeitet": len(jobs),
        "geaendert": recomputed,
        "unveraendert": unchanged,
        "durchschnittliche_aenderung": round(avg_delta, 1),
        "max_anstieg": max(deltas) if deltas else 0,
        "max_rueckgang": min(deltas) if deltas else 0,
    }
    if auffaellig:
        result["auffaellige_aenderungen"] = auffaellig[:20]
        if len(auffaellig) > 20:
            result["auffaellige_aenderungen_gesamt"] = len(auffaellig)
    return result
