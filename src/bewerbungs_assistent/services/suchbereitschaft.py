"""Ist genug da, um sinnvoll zu suchen? (#967, v1.7.27)

Gemessen am 02.09.2026 mit sechs Lebenslaeufen quer durch den
Arbeitsmarkt: nach `profil_erstellen()` liefert `get_search_criteria()`
ein leeres Objekt. Ohne Keywords vergibt `calculate_score` fuer jede
Stelle eine Null, und der Schwellenfilter verwirft alles darunter — 7
von 7 Anzeigen, unabhaengig vom Beruf.

`run_search` erwaehnte `keywords_muss` dabei **null Mal**. Es gab keine
Pruefung vor dem Lauf, keine Warnung und keinen Hinweis: die Suche lief
durch, holte Stellen von den Quellen und warf sie am Ende geschlossen
weg.

Das ist der erste Eindruck des Werkzeugs, und er trifft jeden neuen
Menschen. Wer PBP zum ersten Mal oeffnet, hat keinen Grund anzunehmen,
dass er selbst noch etwas eintragen muss — und keinen Anhaltspunkt, was.

**Zwei Wege statt einer leeren Liste.** Wenn das Profil etwas hergibt,
leitet PBP Suchbegriffe daraus ab und sagt, dass es das getan hat. Gibt
das Profil nichts her, endet der Aufruf mit einer klaren Ansage statt
mit null Treffern.

**Abgeleitet wird nur PLUS, nie MUSS.** Ein MUSS-Begriff ist ein
Ausschlusskriterium; ihn zu erraten wuerde genau die Stellen
unsichtbar machen, die der Mensch noch gar nicht benennen konnte. Die
Leitlinie lautet Recall vor Praezision: lieber ein Job zu viel in der
ersten Liste als eine Liste, die es nie gab.
"""
from __future__ import annotations

from typing import Optional

# Wie viele abgeleitete Begriffe sind sinnvoll? Genug fuer Breite, wenig
# genug, dass die Quellen nicht in Einzelabfragen ertrinken.
MAX_ABGELEITET = 8

# Woerter, die in Stellenbezeichnungen stehen, aber nichts ueber den
# Beruf sagen. Bewusst kurz — es geht um Zusaetze, nicht um eine
# Fachwortliste (die waere wieder auf ein Berufsfeld kalibriert).
_ZUSATZ = frozenset({
    "m/w/d", "w/m/d", "m/w/x", "m", "w", "d", "x",
    "senior", "junior", "leitende", "leitender", "stellv", "stellvertretende",
    "in", "und", "oder", "der", "die", "das", "fuer", "von", "mit",
    "vollzeit", "teilzeit", "befristet", "unbefristet",
})


def _saeubere(bezeichnung: str) -> str:
    """Klammerzusaetze und Geschlechtskuerzel aus einem Titel nehmen."""
    if not bezeichnung:
        return ""
    text = str(bezeichnung)
    for auf, zu in (("(", ")"), ("[", "]")):
        while auf in text and zu in text[text.index(auf):]:
            i = text.index(auf)
            j = text.index(zu, i)
            text = text[:i] + " " + text[j + 1:]
    teile = [t for t in text.replace("/", " ").split()
             if t.strip(" ,;.-").lower() not in _ZUSATZ]
    return " ".join(teile).strip(" ,;.-")


def ableiten(profil: Optional[dict]) -> list[str]:
    """Suchbegriffe aus dem Profil gewinnen.

    Reihenfolge nach Aussagekraft: zuerst vorgeschlagene Jobtitel (die
    hat jemand bewusst gesetzt), dann die Bezeichnungen der bisherigen
    Stationen, dann die Skills. Bewusst OHNE Fachwortliste — was der
    Mensch selbst aufgeschrieben hat, ist die verlaesslichste Quelle
    fuer sein Berufsfeld, egal welches.
    """
    profil = profil or {}
    kandidaten: list[str] = []

    for titel in profil.get("suggested_job_titles") or []:
        wert = titel.get("title") if isinstance(titel, dict) else titel
        gesaeubert = _saeubere(wert or "")
        if gesaeubert:
            kandidaten.append(gesaeubert)

    for pos in profil.get("positions") or []:
        gesaeubert = _saeubere((pos or {}).get("title") or "")
        if gesaeubert:
            kandidaten.append(gesaeubert)

    for skill in profil.get("skills") or []:
        name = ((skill or {}).get("name") or "").strip()
        if len(name) > 2:
            kandidaten.append(name)

    # Dubletten raus, Reihenfolge behalten.
    gesehen: list[str] = []
    for k in kandidaten:
        if not any(k.lower() == g.lower() for g in gesehen):
            gesehen.append(k)
    return gesehen[:MAX_ABGELEITET]


def pruefe(db) -> dict:
    """Vor dem Suchlauf: ist genug da, und wenn nicht, was tun?

    Gibt immer `bereit` und `quelle` zurueck. `quelle` ist eines von:

    * `kriterien` — der Mensch hat Suchbegriffe gesetzt, alles wie bisher
    * `profil`    — nichts gesetzt, aber aus dem Profil ableitbar
    * `leer`      — nichts gesetzt und nichts ableitbar
    """
    try:
        kriterien = db.get_search_criteria() or {}
    except Exception:
        kriterien = {}
    muss = [k for k in (kriterien.get("keywords_muss") or []) if str(k).strip()]
    plus = [k for k in (kriterien.get("keywords_plus") or []) if str(k).strip()]

    if muss or plus:
        return {"bereit": True, "quelle": "kriterien",
                "keywords_muss": muss, "keywords_plus": plus}

    try:
        profil = db.get_profile()
    except Exception:
        profil = None

    if not profil:
        return {
            "bereit": False,
            "quelle": "leer",
            "grund": "Es gibt noch kein Profil.",
            "naechster_schritt": (
                "Starte die Ersterfassung — am schnellsten geht es mit dem "
                "Lebenslauf: dokument_hochladen() und danach "
                "dokument_profil_extrahieren()."),
        }

    abgeleitet = ableiten(profil)
    if abgeleitet:
        return {
            "bereit": True,
            "quelle": "profil",
            "keywords_muss": [],
            "keywords_plus": abgeleitet,
            "hinweis": (
                "Es waren noch keine Suchbegriffe gesetzt. PBP hat "
                f"{len(abgeleitet)} aus deinem Profil abgeleitet und damit "
                "gesucht: " + ", ".join(abgeleitet) + ". Das ist ein "
                "Startpunkt, keine Festlegung — mit "
                "suchkriterien_setzen() machst du daraus deine eigenen."),
            "naechster_schritt": (
                "keyword_vorschlaege() zeigt, welche Begriffe in den "
                "gefundenen Anzeigen haeufig vorkommen."),
        }

    return {
        "bereit": False,
        "quelle": "leer",
        "grund": ("Das Profil enthaelt weder Stationen noch Faehigkeiten, "
                  "aus denen sich Suchbegriffe ableiten liessen."),
        "naechster_schritt": (
            "Lade deinen Lebenslauf hoch (dokument_hochladen, dann "
            "dokument_profil_extrahieren) oder setze Suchbegriffe direkt "
            "mit suchkriterien_setzen(keywords_plus=['<dein Beruf>'])."),
    }
