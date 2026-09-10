"""Ist das dieselbe Stelle? — eine Frage, eine Antwort (#951).

Bis v1.7.71 wurde diese Frage an ZWEI Stellen mit VERSCHIEDENEN Regeln
beantwortet, und die schwaechere lief ausgerechnet im Suchlauf:

* `save_jobs` verglich ueber `_dedup_key` — Titel und Firma exakt, nach
  Entfernen aller Nicht-Alphanumerischen. Klammerzusaetze wurden nur bei
  der FIRMA entfernt, beim Titel nicht.
* `stelle_manuell_anlegen` verglich ueber `find_duplicate_job` — mit
  URL-Abgleich und Titel-Aehnlichkeit. Dort entscheidet das Ergebnis
  bereits darueber, ob ueberhaupt eine Zeile entsteht.

## Was die Messung ergeben hat (10.09.2026, 2.491 Stellen)

| Regel | gefundene Paare |
|---|---:|
| Suchlauf (`_dedup_key`, exakt) | 53 |
| manueller Weg (`find_duplicate_job`) | 128 |
| **nur vom staerkeren Weg** | **76** |

Die 76 sind keine Grenzfaelle, sondern genau die gemeldeten Varianten:
`(Senior) X` gegen `X`, `und` gegen `and`, Bindestrich-Varianten — und
Paare mit IDENTISCHER URL bei abweichendem Titel, die der Suchlauf
durchliess.

Das ist das Muster aus #991 und #1008 zum vierzehnten Mal: **ein
Nadeloehr nuetzt nichts, solange ein Aufrufer daran vorbeigeht** — und
hier ging der wichtigste Aufrufer vorbei.

## Warum die Erkennung trotzdem nicht schaerfer aussortiert

Die Nutzervorgabe im Issue ist eindeutig:

    "Recall vor Praezision: zwei getrennte Eintraege sind aergerlich,
    eine faelschlich verschmolzene Stelle ist schlimmer, weil dabei
    Information verschwindet."

Deshalb zwei Sicherheitsstufen statt einer Wahrheit:

* `SICHER` — identische Detail-URL (nach Entfernen der
  Tracking-Parameter) oder identischer normalisierter Titel bei
  gleicher Firma. Beides ist nachrechenbar, kein Urteil.
* `VERDACHT` — Titel-Aehnlichkeit. Wird MARKIERT, nicht
  zusammengefuehrt. `stelle_mergen` (#470) bleibt der Weg fuer den
  bestaetigten Fall.

Ein Mehrfachfund erzeugt bewusst **keinen Score-Bonus**. Eine breit
gestreute Stelle ist oft eine schwer besetzbare, nicht eine bessere —
Streuung ist nicht Passung.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

SICHER = "sicher"
VERDACHT = "verdacht"

GRUND_TEXT = {
    "url": "Identische Anzeigen-URL (ohne Tracking-Parameter)",
    "titel_firma": "Gleiche Firma, gleicher Titel nach Normalisierung",
    "aehnlich": "Gleiche Firma, aehnlicher Titel — bitte selbst pruefen",
}

# Tracking-Parameter, die beim Vergleich wegfallen. Dieselbe Liste wie
# im Newsletter-Ingest — sie steht dort seit #525 und wird von hier
# mitbenutzt, statt sie ein zweites Mal zu tippen. Genau darum geht es
# in diesem Issue.
_TRACKING_PARAM = re.compile(
    r"[?&](?:utm_[a-z]+|trk|trkEmail|refId|tracking|mkt_tok|cid|ecid"
    r"|otpToken|midToken|eid|source|src|ref|gh_src|jobid_source)"
    r"=[^&#]*", re.I)

# Geschlechtszusaetze und Rollen-Klammern. Sie stehen in fast jedem
# deutschen Stellentitel und in beliebig vielen Schreibweisen — genau
# die Varianten, die im Issue als Beleg stehen.
_ZUSATZ = re.compile(
    r"\(\s*(?:m\s*[/|w]\s*w\s*[/|d]\s*d|m\s*/\s*f\s*/\s*d|w\s*/\s*m\s*/\s*d"
    r"|all\s+genders?|gn|d\s*/\s*m\s*/\s*w|m\s*/\s*w|divers)\s*\)",
    re.I)

# Schreibvarianten, die denselben Beruf meinen. Bewusst KURZ und
# belegbar: jede Zeile stammt aus einem beobachteten Paar. Eine
# waschende Liste waere die Gegenrichtung des Fehlers — sie wuerde
# verschiedene Stellen zusammenziehen.
_GLEICHBEDEUTEND = (
    (r"\bsr\b\.?", "senior"),
    (r"\bjr\b\.?", "junior"),
    (r"\bmgr\b\.?", "manager"),
    (r"\bund\b", "and"),
)

# Alle Strichvarianten, die ein Mensch als Bindestrich meint.
_STRICHE = dict.fromkeys(map(ord, "‐‑‒–—―"), "-")


def url_schluessel(url) -> str:
    """Die Anzeigen-URL ohne Tracking-Parameter, klein und ohne Endstrich.

    Zwei Portale verlinken dieselbe Anzeige regelmaessig mit
    unterschiedlichen Kampagnen-Parametern. Ohne diese Bereinigung sieht
    derselbe Link zweimal verschieden aus.
    """
    roh = (url or "").strip()
    if not roh:
        return ""
    ohne = _TRACKING_PARAM.sub("", roh)
    # Ein uebrig gebliebenes '?' oder '&' am Ende ist kein Unterschied.
    ohne = re.sub(r"[?&]+$", "", ohne)
    # Das erste verbliebene '&' wird wieder zum '?', sonst ist die URL
    # syntaktisch kaputt und zwei bereinigte Formen weichen ab.
    if "?" not in ohne and "&" in ohne:
        ohne = ohne.replace("&", "?", 1)
    return ohne.rstrip("/").lower()


def titel_schluessel(titel) -> str:
    """Der Stellentitel auf seinen Kern reduziert.

    Entfernt Geschlechtszusaetze und Klammerinhalte, vereinheitlicht
    Striche und die belegten Kurzformen. Was uebrig bleibt, sind
    Buchstaben und Ziffern.

    Bewusst KEINE Aehnlichkeitsrechnung: dieser Schluessel entscheidet
    ueber `SICHER`, und darueber darf nichts entscheiden, was man nicht
    nachrechnen kann (dieselbe Ueberlegung wie bei der Gruppierung in
    #1012).
    """
    t = (titel or "").strip().lower().translate(_STRICHE)
    t = _ZUSATZ.sub(" ", t)
    # Alle uebrigen Klammerzusaetze — im Titel stehen dort Standorte,
    # Vertragsarten und Hinweise, nie der Beruf selbst.
    t = re.sub(r"\([^)]*\)", " ", t)
    for muster, ersatz in _GLEICHBEDEUTEND:
        t = re.sub(muster, ersatz, t)
    return re.sub(r"[^a-z0-9äöüß]+", "", t)


def firma_schluessel(firma) -> str:
    """Die Firma ohne Rechtsform und Klammerzusatz."""
    from ..duplicate_detection import normalize_company_name
    return normalize_company_name(firma) or ""


def _sicher_gleich(a: dict, b: dict) -> str:
    """Nachrechenbare Gleichheit — oder ''."""
    ua, ub = url_schluessel(a.get("url")), url_schluessel(b.get("url"))
    if ua and ub and ua == ub:
        return "url"
    fa, fb = firma_schluessel(a.get("company") or a.get("firma")), \
        firma_schluessel(b.get("company") or b.get("firma"))
    if not fa or not fb or fa != fb:
        return ""
    ta = titel_schluessel(a.get("title") or a.get("titel"))
    tb = titel_schluessel(b.get("title") or b.get("titel"))
    if ta and tb and ta == tb:
        return "titel_firma"
    return ""


def finde(stelle: dict, kandidaten) -> dict | None:
    """Die eine Antwort auf "ist das dieselbe Stelle?".

    Args:
        stelle: die neu hereinkommende Stelle (title/company/url).
        kandidaten: bereits bekannte Stellen.

    Returns:
        ``{"stelle": <kandidat>, "sicherheit": SICHER|VERDACHT,
        "grund": str, "text": str}`` oder None.

        `SICHER` heisst: nachgerechnet, keine Meinung. `VERDACHT`
        heisst: sieht danach aus, entscheidet aber der Mensch — die
        Nutzervorgabe lautet Recall vor Praezision.
    """
    if not stelle:
        return None
    liste = [k for k in (kandidaten or []) if k]
    for kandidat in liste:
        grund = _sicher_gleich(stelle, kandidat)
        if grund:
            return {"stelle": kandidat, "sicherheit": SICHER,
                    "grund": grund, "text": GRUND_TEXT[grund]}

    # Erst wenn nichts nachrechenbar gleich ist, kommt die
    # Aehnlichkeit — und die entscheidet nichts, sie markiert nur.
    try:
        from ..duplicate_detection import find_duplicate_job
        treffer = find_duplicate_job(
            stelle.get("company") or stelle.get("firma") or "",
            stelle.get("title") or stelle.get("titel") or "",
            stelle.get("url") or "",
            liste,
        )
    except Exception as exc:  # pragma: no cover — nie einen Lauf stoppen
        logger.debug("Aehnlichkeitspruefung fehlgeschlagen: %s", exc)
        return None
    if not treffer:
        return None
    return {"stelle": treffer["job"], "sicherheit": VERDACHT,
            "grund": "aehnlich", "text": GRUND_TEXT["aehnlich"],
            "aehnlichkeit": treffer.get("grund")}


def bestand_pruefen(db, *, max_stellen: int = 0) -> dict:
    """Findet Mehrfacheintraege im ALTBESTAND — und schreibt nichts (#951).

    Der Bestand ist gewachsen, bevor es die Erkennung gab. Ein Lauf, der
    ihn ungefragt umbaut, waere keine Diagnose, sondern eine
    Ueberraschung — dieselbe Entscheidung wie bei `stellen_urls_heilen`
    und der Recherche-Zusammenfuehrung.

    Getrennt nach Sicherheit:

    * `sicher` — identische URL oder identischer normalisierter Titel
      bei gleicher Firma. Nachrechenbar.
    * `verdacht` — nur aehnlich. Hier entscheidet der Mensch;
      `stelle_mergen` (#470) ist der Weg.

    Returns:
        dict mit Zahlen und einer Stichprobe OHNE Firmennamen — der
        Bericht kann in einem Issue landen.
    """
    try:
        zeilen = [dict(r) for r in db.connect().execute(
            "SELECT hash, title, company, url, source, is_active "
            "FROM jobs WHERE company IS NOT NULL AND TRIM(company) != ''"
        ).fetchall()]
    except Exception as exc:  # pragma: no cover
        logger.debug("Bestand nicht lesbar: %s", exc)
        return {"status": "fehler", "fehler": str(exc)[:200]}

    if max_stellen > 0:
        zeilen = zeilen[:max_stellen]

    # Gruppierung ueber die beiden nachrechenbaren Schluessel.
    nach_schluessel: dict[str, list] = {}
    for j in zeilen:
        for schluessel in _schluessel_von(j):
            nach_schluessel.setdefault(schluessel, []).append(j)

    gruppen = [v for v in nach_schluessel.values() if len(v) > 1]
    # Eine Stelle kann ueber URL UND Titel in dieselbe Gruppe fallen —
    # doppelt gezaehlte Gruppen zusammenfassen.
    gesehen: set = set()
    eindeutige: list = []
    for g in gruppen:
        kennung = tuple(sorted(j["hash"] for j in g))
        if kennung in gesehen:
            continue
        gesehen.add(kennung)
        eindeutige.append(g)

    ueber_quellen = sum(
        1 for g in eindeutige if len({j.get("source") for j in g}) > 1)
    proben = []
    for g in eindeutige[:15]:
        proben.append({
            "stellen": [str(j["hash"])[-8:] for j in g],
            "quellen": sorted({(j.get("source") or "unbekannt") for j in g}),
            "aktive": sum(1 for j in g if j.get("is_active")),
        })

    return {
        "status": "vorschau",
        "geprueft": len(zeilen),
        "gruppen": len(eindeutige),
        "zweitfunde": sum(len(g) - 1 for g in eindeutige),
        "gruppen_mit_mehreren_quellen": ueber_quellen,
        # KEINE Firmennamen und keine Titel — der Bericht ist zum Teilen.
        "stichprobe": proben,
        "hinweis": (
            "Vorschau — es wurde nichts geschrieben und nichts "
            "zusammengefuehrt. Fuer einen bestaetigten Fall ist "
            "`stelle_mergen` der Weg (#470)."),
    }


def _schluessel_von(job: dict) -> list:
    """Die nachrechenbaren Schluessel einer Stelle."""
    schluessel = []
    u = url_schluessel(job.get("url"))
    if u:
        schluessel.append("u:" + u)
    f = firma_schluessel(job.get("company"))
    t = titel_schluessel(job.get("title"))
    if f and t:
        schluessel.append(f"t:{f}|{t}")
    return schluessel
