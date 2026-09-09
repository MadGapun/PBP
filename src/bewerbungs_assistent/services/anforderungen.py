"""Wann sind zwei Suchbegriffe DIESELBE Anforderung (#1012).

Der Fachscore ist eine Summe ueber getroffene MUSS-Begriffe. Die
Summanden sind aber nicht unabhaengig: in einer gepflegten Liste sind
regelmaessig mehrere Eintraege Schreibweisen desselben Sachverhalts.

Gemessen beim Abschluss von #1003, mit drei Schreibweisen derselben
Rolle in der MUSS-Liste:

    Anzeige nennt den Sachverhalt einmal          ->  7,0 Punkte
    Anzeige nennt DENSELBEN in drei Schreibweisen -> 21,0 Punkte

Faktor 3 fuer eine blosse Umformulierung. Das verschiebt die
SORTIERUNG der Trefferliste und, ueber `min_score_schwelle`, sogar was
ueberhaupt gespeichert wird — eine geschwaetzige Anzeige steigt damit
ueber eine praezise.

Zur Abgrenzung ebenfalls gemessen: eine blosse WIEDERHOLUNG blaeht
nicht (20x genannt = 1x genannt). Jeder Begriff zaehlt ohnehin einmal.
Der Fehler sitzt allein in der Mehrfach-Vertretung eines Sachverhalts
**in der Kriterien-Liste**.

## Warum hier nichts geraten wird

Der naheliegende Weg waere eine Aehnlichkeitsrechnung oder eine
statistische Daempfung (IDF gibt es seit #778 als Opt-in). Beides
schaetzt. Dieses Modul gruppiert nur, was sich **belegen** laesst:

1. **Wortmengen-Enthaltensein** — "plm" steckt in "plm system".
   Wer beides in die MUSS-Liste schreibt, meint einen Sachverhalt.
2. **Abkuerzung und Ausschreibung** — die Anfangsbuchstaben von
   "product lifecycle management" ergeben "plm".
3. **PBPs eigene Synonym-Karte** (`_SYNONYM_MAP`, #183). Steht dort
   `plm -> teamcenter`, dann zaehlt der Matcher eine Anzeige mit "PLM"
   bereits als Treffer fuer "Teamcenter" — der zweite Punkt entsteht
   ohne jeden zusaetzlichen Inhalt. Zwei MUSS-Begriffe, die PBP selbst
   als dasselbe behandelt, sind dasselbe. Diese Beziehung ist im
   Projekt kuratiert und dokumentiert, also belegt.

Alles andere bleibt getrennt. Zwei Begriffe, die dasselbe MEINEN, aber
in keiner dieser Beziehungen stehen ("PDM" und "Teilestammpflege"),
gruppiert PBP NICHT — das waere geraten, und ein falsch
zusammengefasster Begriff kostet Punkte, die der Mensch gemeint hat.
**Lieber eine Blaehung uebrig lassen als eine Anforderung schlucken.**

## Die Gruppe zaehlt einmal, mit ihrem staerksten Mitglied

Nicht der Durchschnitt und nicht der erste Eintrag: der Mensch hat
einem Begriff vielleicht ein hoeheres Einzelgewicht gegeben (#778).
Die Gruppe ist so viel wert wie ihr wertvollstes Mitglied — nie mehr,
nie weniger.
"""
from __future__ import annotations

import re

_WORT = re.compile(r"[a-z0-9äöüß]+")

# Die Synonym-Karte aendert sich zur Laufzeit nicht.
_SYN_CACHE = None


def _worte(begriff) -> tuple[str, ...]:
    """Der Begriff als normalisierte Wortfolge."""
    return tuple(_WORT.findall(str(begriff or "").lower()))


def _akronym(worte: tuple[str, ...]) -> str:
    """Die Anfangsbuchstaben einer Wortfolge — "" bei einem Einzelwort."""
    if len(worte) < 2:
        return ""
    return "".join(w[0] for w in worte if w)


def dieselbe_anforderung(a, b) -> bool:
    """Belegen die beiden Begriffe denselben Sachverhalt?

    Nur die zwei beweisbaren Beziehungen — siehe Modul-Docstring. Die
    Funktion ist symmetrisch und sagt bei Gleichheit ebenfalls True.
    """
    wa, wb = _worte(a), _worte(b)
    if not wa or not wb:
        return False
    if wa == wb:
        return True
    # (1) Wortmengen-Enthaltensein: "plm" in "plm system".
    if set(wa) <= set(wb) or set(wb) <= set(wa):
        return True
    # (2) Abkuerzung gegen Ausschreibung.
    if len(wa) == 1 and wa[0] == _akronym(wb):
        return True
    if len(wb) == 1 and wb[0] == _akronym(wa):
        return True
    # (3) PBPs eigene Synonym-Karte.
    return _synonym_paar(" ".join(wa), " ".join(wb))


def _synonym_gruppen() -> list[frozenset]:
    """Die Synonym-Karte als Mengen — einmal gelesen, dann gemerkt.

    Der Import liegt in der Funktion: `job_scraper` ruft dieses Modul
    beim Rechnen auf, ein Modul-Import in die andere Richtung waere ein
    Ring.
    """
    global _SYN_CACHE
    if _SYN_CACHE is not None:
        return _SYN_CACHE
    try:
        from ..job_scraper import _SYNONYM_MAP
    except ImportError:  # pragma: no cover — ohne Karte gilt nur (1)+(2)
        _SYN_CACHE = []
        return _SYN_CACHE
    # ACHTUNG: `{...} | {...}` — beim ersten Anlauf stand hier eine
    # LISTE links, und `list | set` wirft einen TypeError. Ein
    # weitgefasstes `except Exception` hat ihn verschluckt: die Regel war
    # damit still abgeschaltet, und der Probelauf meldete "False" ohne
    # jeden Hinweis. Genau die stille Null, die dieses Projekt schon
    # mehrfach gekostet hat (#844, #995) — deshalb faengt der Block jetzt
    # nur den Import ab, nicht den Aufbau.
    _SYN_CACHE = [frozenset({str(k).lower()}
                            | {str(s).lower() for s in (v or [])})
                  for k, v in (_SYNONYM_MAP or {}).items()]
    return _SYN_CACHE


def _synonym_paar(a: str, b: str) -> bool:
    """Stehen beide Begriffe in derselben Synonym-Menge?"""
    return any(a in menge and b in menge for menge in _synonym_gruppen())


def gruppen(begriffe) -> list[list[str]]:
    """Teilt eine Begriffsliste in Gruppen gleicher Anforderungen.

    Die Reihenfolge der Eingabe bleibt erhalten — die erste Nennung
    fuehrt ihre Gruppe an. Transitiv: haengt A an B und B an C, sind
    alle drei eine Gruppe ("plm", "plm system", "product lifecycle
    management").
    """
    offen = [str(b) for b in (begriffe or []) if str(b).strip()]
    erg: list[list[str]] = []
    for begriff in offen:
        for gruppe in erg:
            if any(dieselbe_anforderung(begriff, m) for m in gruppe):
                gruppe.append(begriff)
                break
        else:
            erg.append([begriff])
    return erg


def zaehlbare_punkte(begriffe, punkte_fuer) -> list[float]:
    """Die Punkte einer Begriffsliste, je Anforderung nur einmal.

    Args:
        begriffe: die Begriffe, die gezaehlt werden sollen (Treffer —
            oder bei der Hoechstwert-Rechnung alle).
        punkte_fuer: Funktion Begriff -> Punkte.

    **Das ist das Nadeloehr.** Die MUSS-Liste wird an drei Stellen
    ausgewertet (`calculate_score`, `fit_analyse`, `score_maximum`);
    liefe eine davon daran vorbei, waere der Hoechstwert nicht mehr
    erreichbar und die 100-Prozent-Eigenschaft aus #999 gebrochen.
    """
    return [max(punkte_fuer(m) for m in gruppe)
            for gruppe in gruppen(begriffe)]


def zusammengefasst(begriffe) -> list[dict]:
    """Welche Begriffe wurden als EINE Anforderung gezaehlt (AK 4).

    Nur die Gruppen mit mehr als einem Mitglied — die anderen sind
    keine Nachricht. Ohne diese Auskunft waere die Zusammenfassung eine
    stille Score-Aenderung, und genau das ist in diesem Projekt schon
    mehrfach schiefgegangen (#987, #988).
    """
    return [{"gezaehlt_als": g[0], "begriffe": list(g)}
            for g in gruppen(begriffe) if len(g) > 1]
