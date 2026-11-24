"""Was die Quelle geliefert hat, bevor der Adapter gefiltert hat (#995).

Gemeldet am 08.09.2026 aus der Quellenpflege zu #813:

    | Was die API liefert                          | 20 |
    | Was der Adapter nach seinem `_matches` zurueckgibt |  0 |
    | Was als `letzte_rohtreffer` in der Diagnose steht  |  0 |

**`letzte_rohtreffer` heisst nicht ueberall dasselbe.** Zehn Adapter
filtern intern nach den Suchbegriffen, bevor sie zurueckgeben; bei ihnen
ist die als "Rohtreffer" ausgewiesene Zahl bereits das Ergebnis des
Keyword-Filters. Damit sehen zwei voellig verschiedene Zustaende gleich
aus:

1. **Die Quelle liefert nichts** — Endpunkt tot, Bot-Block, leeres
   Ergebnis.
2. **Die Quelle liefert, aber nichts passt zum Profil** — ein
   internationales Remote-Board hat fuer eine regionale Fachsuche
   schlicht keine Treffer.

Beide erscheinen als 0, beide zaehlen als stiller Lauf, und beide
fuehren nach fuenf Laeufen zur automatischen Abschaltung. Genau so wurde
`himalayas` am 01.09. stillgelegt — es sah nach Fall 2 aus und war Fall
1 (ein Feldumbau, siehe #813).

Das ist derselbe Fehlertyp wie #989: **eine fehlende Unterscheidung
wirkt wie eine negative Auskunft.**

**Warum ein Register und kein Rueckgabewert.** Der saubere Weg waere,
dass jeder Adapter `(stellen, befund)` zurueckgibt — das beruehrt aber
alle 26 Adapter und ihre Aufrufer. Hier meldet stattdessen jeder Adapter
im Vorbeigehen, wie viele Datensaetze die Quelle geliefert hat; der
Sammler liest den Stand am Ende des Laufs. Ein Adapter, der nichts
meldet, verhaelt sich wie bisher — `stand()` gibt dann `None` zurueck,
und **`None` heisst "nicht gemeldet", nicht "null gesehen"** (#989).

Die Quellen laufen in einem ThreadPool mit bis zu vier Arbeitern, je
Quelle aber genau einmal. Ein Lock genuegt daher; thread-lokale Ablage
waere sogar falsch, weil Adapter und Sammler in verschiedenen Threads
laufen.
"""
from __future__ import annotations

import threading

_LOCK = threading.Lock()
_GESEHEN: dict[str, int] = {}


def lauf_beginnen() -> None:
    """Vor jedem Suchlauf: die Zahlen des letzten Laufs verwerfen.

    Ohne das wuerde ein Adapter, der diesmal gar nicht lief, den Stand
    von gestern melden — eine alte Zahl ist schlimmer als keine.
    """
    with _LOCK:
        _GESEHEN.clear()
        _DURCHLASS.clear()
        _HTTP.clear()


def melde(quelle: str, anzahl: int) -> None:
    """Ein Adapter meldet, wie viele Datensaetze die Quelle geliefert hat.

    Additiv, weil die meisten Adapter seitenweise holen.
    """
    if not quelle:
        return
    try:
        wert = int(anzahl)
    except (TypeError, ValueError):
        return
    if wert < 0:
        return
    with _LOCK:
        _GESEHEN[quelle] = _GESEHEN.get(quelle, 0) + wert


def stand(quelle: str):
    """Wie viele Datensaetze hat diese Quelle im laufenden Lauf geliefert?

    Returns:
        Die Anzahl, oder `None` wenn der Adapter nichts gemeldet hat.
        Der Unterschied ist der Kern des Issues.
    """
    with _LOCK:
        return _GESEHEN.get(quelle)


def alle() -> dict:
    """Der ganze Stand — fuer Diagnose und Tests."""
    with _LOCK:
        return dict(_GESEHEN)


# #1394: was NACH dem adaptereigenen Keyword-Filter uebrig blieb. Eine Quelle
# ohne eigene Suche (arbeitnow, remoteok) liefert den allgemeinen Feed; erst
# die Gegenueberstellung geliefert / durchgelassen / mit Treffer im Titel
# macht einen undichten Filter sichtbar (stilles Zuviel, Gegenstueck zu #1334).
_DURCHLASS: dict[str, dict[str, int]] = {}


def melde_durchlass(quelle: str, durchgelassen: int, im_titel: int) -> None:
    if not quelle:
        return
    with _LOCK:
        d = _DURCHLASS.setdefault(quelle, {"durchgelassen": 0, "im_titel": 0})
        d["durchgelassen"] += int(durchgelassen)
        d["im_titel"] += int(im_titel)


def durchlass(quelle: str):
    """`{"durchgelassen": n, "im_titel": m}` oder `None` (= nicht gemeldet)."""
    with _LOCK:
        d = _DURCHLASS.get(quelle)
        return dict(d) if d is not None else None


def bilanz() -> dict:
    """Je Quelle mit Filter: geliefert / durch den Filter / mit Pflichttreffer im Titel."""
    with _LOCK:
        quellen = dict(_DURCHLASS)
        gesehen = dict(_GESEHEN)
    return {q: {"geliefert": gesehen.get(q), "durch_filter": d["durchgelassen"],
                "mit_pflichttreffer_im_titel": d["im_titel"]}
            for q, d in quellen.items()}


# #1435: Was die Quelle auf HTTP-Ebene geantwortet hat. SOLCOM fragte eine
# Adresse ab, die mit 404 (spaeter 403) antwortete; der Adapter schrieb das
# nur ins Debug-Log und gab eine leere Liste zurueck. Der Lauf galt als
# "ok ohne Treffer", nach fuenf Laeufen war die Quelle still abgeschaltet,
# ohne dass irgendwo ein Fehler stand. Wie bei `melde`: ein Register statt
# eines Rueckgabewerts, damit kein Adapter seine Signatur aendern muss.
_HTTP: dict[str, dict[int, int]] = {}


def melde_http(quelle: str, status) -> None:
    """Ein Adapter meldet den Status einer Antwort (auch 200)."""
    if not quelle:
        return
    try:
        code = int(status)
    except (TypeError, ValueError):
        return
    with _LOCK:
        d = _HTTP.setdefault(quelle, {})
        d[code] = d.get(code, 0) + 1


def http_ok(quelle: str, antwort) -> bool:
    """`antwort.status_code == 200` — und der Status wird dabei gemeldet."""
    code = getattr(antwort, "status_code", None)
    melde_http(quelle, code)
    return code == 200


def http_befund(quelle: str):
    """`{status: anzahl}` des laufenden Laufs, oder `None` (= nicht gemeldet)."""
    with _LOCK:
        d = _HTTP.get(quelle)
        return dict(d) if d is not None else None


def http_fehlschlag(quelle: str):
    """Ist JEDE gemeldete Antwort ein Fehler? Dann `(haeufigster_status, anzahl_fehler)`.

    Eine Quelle mit mindestens einer 200 ist nicht kaputt (eine einzelne
    verschwundene Firma bei Greenhouse darf die Quelle nicht abschalten),
    und eine Quelle, die nichts meldet, wird nicht beurteilt.
    """
    d = http_befund(quelle)
    if not d or any(200 <= code < 300 for code in d):
        return None
    status = max(d, key=lambda code: d[code])
    return status, sum(d.values())
