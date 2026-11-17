"""Ein Abgleich der Suchbegriffe fuer alle Quellen ohne eigene Suche (#1394).

Gemessen am 16.11.2026 (PBP 1.8.6): arbeitnow lieferte 300 Stellen, der
adaptereigene Filter liess 177 durch, davon waren 3 echte Treffer. Grund:
jeder Adapter verglich die Suchbegriffe als TEILWORT ("ECO" steckt in
"economy", "ECR" in "recruit" und "secret"). Das Scoring prueft dagegen
auf Wortgrenzen — Filter und Punkte waren sich nicht einig.

Eine Frage, eine Funktion fuer alle Quellen ohne eigene Suche. Lange Begriffe
(ab vier Zeichen) zaehlen am WORTANFANG ("Pflege" trifft "Pflegekraft", nie
"Kopfpflege"; Mehrwort als zusammenhaengende Phrase, Umlaute in beiden
Schreibweisen) — Recall vor Praezision, das Scoring entscheidet danach. KURZE
Begriffe (unter vier Zeichen: ECO, ECR, ECN, BOM, PLM): im Titel und in den
Tags als ganzes Wort in jeder Schreibweise, im Fliesstext nur als ganzes Wort in
GROSSSCHREIBUNG ("ECO-Prozess" ja, "eco-friendly" nein). Die Firma zaehlt nicht mit — ein Firmenname ist keine
Aussage ueber das Fach.
"""
from __future__ import annotations

import re

KURZ_BIS = 3  # "unter vier Zeichen": 1 bis 3


def _ist_kurz(kw: str) -> bool:
    return len(kw) <= KURZ_BIS and not re.search(r"\s", kw)


def _ganzes_wort(kw: str, text: str, *, gross: bool) -> bool:
    muster = r"(?<!\w)" + re.escape(kw.upper() if gross else kw) + r"(?!\w)"
    return re.search(muster, text, 0 if gross else re.IGNORECASE) is not None


def _wortanfang(kw: str, text: str) -> bool:
    """Lange Begriffe: am WORTANFANG, nach hinten offen ("Pflege" in "Pflegekraft").

    Deutsche Zusammensetzungen tragen das Fachwort vorn; ein ganzes-Wort-Zwang
    verlöre sie (Recall vor Präzision: das Scoring entscheidet danach). Nach vorn
    bleibt die Wortgrenze zu, damit nichts mitten im Wort trifft.
    Umlaute zaehlen in beiden Schreibweisen (ae/ä).
    """
    from . import _normalize_for_matching
    for nadel, heu in ((kw.lower(), text.lower()),
                       (_normalize_for_matching(kw), _normalize_for_matching(text))):
        teile = [re.escape(p) for p in re.split(r"[\s\-/]+", nadel) if p]
        if teile and re.search(r"(?<!\w)" + r"[\s\-/]+".join(teile), heu):
            return True
    return False


def treffer(keywords, titel: str = "", tags: str = "", text: str = "") -> list:
    """Die Suchbegriffe, die diese Anzeige wirklich treffen (Reihenfolge wie die Liste)."""
    kopf = f"{titel or ''} {tags or ''}"
    fliess = text or ""
    gefunden = []
    for roh in keywords or []:
        kw = str(roh or "").strip()
        if not kw:
            continue
        if _ist_kurz(kw):
            if _ganzes_wort(kw, kopf, gross=False) or _ganzes_wort(kw, fliess, gross=True):
                gefunden.append(roh)
        elif _wortanfang(kw, kopf) or _wortanfang(kw, fliess):
            gefunden.append(roh)
    return gefunden


def passt(keywords, titel: str = "", tags: str = "", text: str = "",
          quelle: str | None = None) -> bool:
    """Gilt die Anzeige als Treffer? Ohne Suchbegriffe passiert alles (der Score filtert danach).

    Mit `quelle` meldet der Aufruf zugleich, wie viele Anzeigen durchkamen und
    wie viele davon den Begriff schon im Titel oder in den Tags tragen.
    """
    if not keywords:
        return True
    gefunden = treffer(keywords, titel, tags, text)
    if quelle:
        from . import rohtreffer
        rohtreffer.melde_durchlass(
            quelle, durchgelassen=1 if gefunden else 0,
            im_titel=1 if gefunden and treffer(keywords, titel, tags, "") else 0)
    return bool(gefunden)
