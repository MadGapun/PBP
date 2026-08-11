"""Auswertung ueber alle Interview-Reflexionen (#824/D31, v1.7.12).

Die Reflexionen (#464) waren Write-Only: chronologische Liste, keinerlei
Sicht QUER darueber — dabei liegt genau dort der Wert ("wir hatten ja
schon mehrere solcher Interviews, aus denen ich gerne meine Lehren ziehen
wuerde"). Komplett regelbasiert, kein Sprachmodell.

Grundsaetze:
- **Beobachtung, nicht Urteil.** "In n von m Nachbereitungen taucht X
  auf" — nie "du redest zu viel". Die Auswertung zaehlt, was in den
  eigenen Notizen steht; sie interpretiert nicht.
- **Fallzahl-Regel** (identisch zu #798): unterhalb MIN_FAELLE werden
  keine Muster ausgewiesen, nur Einzeleintraege. Zwei Vorkommen sind
  kein Muster.
- Unsicherheit steht IN der Aussage (#799-Muster), nicht in Fussnoten.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

# Unterhalb dieser Zahl Reflexionen gibt es keine Muster-Aussagen.
MIN_FAELLE = 4

# Woerter ohne Aussagekraft fuer die Wiederholungs-Analyse.
_STOPP = {
    "und", "oder", "aber", "der", "die", "das", "ein", "eine", "einen",
    "ich", "mich", "mir", "mein", "meine", "war", "ist", "hat", "habe",
    "hatte", "sehr", "auch", "noch", "nur", "nicht", "kein", "keine",
    "mit", "ohne", "fuer", "für", "von", "bei", "auf", "aus", "als",
    "dass", "wie", "was", "wir", "sie", "man", "sich", "zum", "zur",
    "den", "dem", "des", "im", "am", "um", "an", "in", "zu", "es",
    "gut", "schlecht", "lief", "wurde", "wurden", "haben", "wieder",
    "etwas", "mehr", "wenig", "viel", "ganz", "dann", "wenn", "weil",
}


def _kernwoerter(text: str) -> set:
    """Aussagekraeftige Woerter eines Freitexts (>= 4 Zeichen, kein Stopp)."""
    if not text:
        return set()
    woerter = re.findall(r"[a-zäöüß\-]{4,}", text.lower())
    return {w for w in woerter if w not in _STOPP}


def _wiederkehrend(reflexionen: list, feld: str) -> list:
    """Woerter, die in mehreren Reflexionen im selben Feld auftauchen."""
    zaehler: Counter = Counter()
    for r in reflexionen:
        for w in _kernwoerter(r.get(feld) or ""):
            zaehler[w] += 1
    gesamt = sum(1 for r in reflexionen if (r.get(feld) or "").strip())
    out = []
    for wort, n in zaehler.most_common(10):
        if n < 2 or gesamt < 2:
            continue
        out.append({
            "begriff": wort,
            "in_n_von_m": f"{n} von {gesamt}",
            "aussage": (f"In {n} von {gesamt} Nachbereitungen mit Eintrag "
                        f"taucht '{wort}' auf."),
        })
    return out[:5]


# Ausgaenge, die als "positiv" bzw. "negativ" zaehlen — alles andere
# (laufend) bleibt neutral und wird nicht gewertet.
_POSITIV = {"angebot", "angenommen", "zweitgespraech",
            "interview_abgeschlossen"}
_NEGATIV = {"abgelehnt", "abgelaufen", "zurueckgezogen",
            "arbeitgeber_ausgefallen"}


def lehren_auswerten(db) -> dict[str, Any]:
    """Regelbasierte Quer-Auswertung aller Reflexionen des Profils."""
    reflexionen = db.list_interview_reflections(limit=200)
    anzahl = len(reflexionen)

    # 1 — Antwortarchiv: direkteste Vorbereitungshilfe, ohne Mindestzahl.
    archiv = []
    for r in reflexionen:
        antwort = (r.get("wiederverwendbare_antwort") or "").strip()
        if not antwort:
            continue
        archiv.append({
            "antwort": antwort,
            "firma": r.get("company"),
            "rolle": r.get("title"),
            "datum": (r.get("created_at") or "")[:10],
            "reflexion_id": r.get("id"),
        })

    ergebnis: dict[str, Any] = {
        "anzahl_reflexionen": anzahl,
        "antwortarchiv": archiv,
    }

    # 2 — Offene naechste Schritte aus LAUFENDEN Verfahren. Ebenfalls
    # ohne Mindestzahl — das sind konkrete Merker, keine Muster.
    offene = []
    for r in reflexionen:
        steps = (r.get("next_steps") or "").strip()
        if not steps:
            continue
        app = db.get_application(r.get("application_id") or "") or {}
        if app.get("status") in _NEGATIV or app.get("status") in (
                "angenommen",):
            continue
        offene.append({
            "next_steps": steps,
            "firma": r.get("company"),
            "status": app.get("status", "unbekannt"),
            "seit": (r.get("created_at") or "")[:10],
            "bewerbung_id": r.get("application_id"),
        })
    ergebnis["offene_naechste_schritte"] = offene

    # 3-5 — Muster nur ab MIN_FAELLE (#798-Regel).
    if anzahl < MIN_FAELLE:
        ergebnis["muster"] = None
        ergebnis["muster_hinweis"] = (
            f"Erst ab {MIN_FAELLE} Reflexionen werden Muster ausgewiesen "
            f"(aktuell {anzahl}) — zwei Vorkommen sind kein Muster. Die "
            "Einzeleintraege stehen in interview_reflexionen_anzeigen.")
        return ergebnis

    muster: dict[str, Any] = {}
    selbstkritik = _wiederkehrend(reflexionen, "was_lief_schlecht")
    if selbstkritik:
        muster["wiederkehrende_selbstkritik"] = selbstkritik
    ueberraschungen = _wiederkehrend(reflexionen, "was_war_ueberraschend")
    if ueberraschungen:
        muster["wiederkehrende_ueberraschungen"] = ueberraschungen
        muster["ueberraschungs_hinweis"] = (
            "Dieselbe Art Ueberraschung mehrfach heisst: eine Frage fehlt "
            "in der VORBEREITUNG — die Luecke liegt in der Recherche, "
            "nicht im Gespraech.")
    staerken = _wiederkehrend(reflexionen, "was_lief_gut")
    if staerken:
        muster["wiederkehrende_staerken"] = staerken

    # Gefuehl gegen Ausgang — nur mit ausreichend abgeschlossenen Faellen.
    paare = []
    for r in reflexionen:
        g = r.get("gefuehl")
        if not g:
            continue
        app = db.get_application(r.get("application_id") or "") or {}
        status = app.get("status", "")
        if status in _POSITIV:
            paare.append((int(g), 1))
        elif status in _NEGATIV:
            paare.append((int(g), 0))
    if len(paare) >= MIN_FAELLE:
        gefuehl_schnitt = sum(g for g, _ in paare) / len(paare)
        positiv_quote = sum(o for _, o in paare) / len(paare)
        blick = {
            "faelle": len(paare),
            "gefuehl_schnitt": round(gefuehl_schnitt, 1),
            "positiver_ausgang_quote": round(positiv_quote * 100),
        }
        if gefuehl_schnitt >= 4 and positiv_quote < 0.4:
            blick["beobachtung"] = (
                f"Dein Bauchgefuehl nach Gespraechen liegt im Schnitt bei "
                f"{gefuehl_schnitt:.1f} von 5, der Ausgang war aber nur in "
                f"{round(positiv_quote * 100)} % der Faelle positiv — das "
                "Gefuehl direkt nach dem Gespraech ist bei dir ein "
                "unzuverlaessiger Prognostiker.")
        muster["gefuehl_gegen_ausgang"] = blick

    ergebnis["muster"] = muster or None
    if not muster:
        ergebnis["muster_hinweis"] = (
            "Keine wiederkehrenden Begriffe ueber die Reflexionen hinweg — "
            "das ist keine Luecke, sondern ein Befund.")
    return ergebnis
