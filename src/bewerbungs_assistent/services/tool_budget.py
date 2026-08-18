"""Wall-Clock-Budget fuer schreibende MCP-Tools (#915, v1.7.17).

Belegter Vorfall 17.08.: `todo_anlegen`, `meeting_hinzufuegen` und
`pbp_mcp_diagnose` blieben je 4 Minuten ohne JEDE Antwort, bis der
MCP-Client abbrach — ohne Wirkung, ohne Fehlermeldung, waehrend parallele
Lese-Aufrufe sofort zurueckkamen. Ein `database is locked` waere nach dem
busy_timeout (30 s) sichtbar gewesen; es kam nichts. Die Blockade sass
also OBERHALB von SQLite auf Python-Ebene — und genau dagegen hilft nur
eine harte Wall-Clock-Grenze im Tool-Pfad selbst.

Mechanik: der Tool-Body laeuft in einem kleinen, festen Thread-Pool
(A28/#900: jeder Thread hat seine eigene SQLite-Connection, der Pool
haelt die Zahl klein statt je Aufruf eine neue zu leaken). Antwortet er
nicht innerhalb des Budgets, bekommt der Client ein schemakonformes
Ergebnis mit `status='timeout'` statt Stille — inklusive der gerade
laufenden Hintergrund-Tasks (hintergrund_status, bewusst DB-frei).

WICHTIG (Idempotenz, dokumentierter Vertrag): Python kann den Worker
nicht abbrechen. Der Aufruf laeuft serverseitig weiter und kann SPAETER
noch wirken. Deshalb steht im Timeout-Ergebnis die Anweisung, vor einer
Wiederholung erst zu LESEN — ein einzelner add/update ist transaktional
atomar, halbe Datensaetze entstehen nicht, Dubletten durch blindes
Wiederholen schon.
"""
from __future__ import annotations

import functools
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutureTimeout

from .hintergrund_status import aktuelle_tasks, zuletzt_beendet

logger = logging.getLogger(__name__)

# Deutlich ueber dem SQLite-busy_timeout (30 s), damit ein ECHTES
# 'database is locked' noch als solches ankommt, und deutlich unter dem
# 4-Minuten-Timeout des MCP-Clients.
BUDGET_SEK_DEFAULT = 45.0

# Klein halten: mehr als eine Handvoll gleichzeitig haengender Writes
# bedeutet ohnehin, dass der Server Hilfe braucht — und jeder
# Pool-Thread haelt eine eigene DB-Connection (A28).
#
# WICHTIG zum Thread-Namen (v1.7.18): NICHT mit "pbp-" praefixen. Der
# Test-Drain aus A22/#759 (conftest.pytest_runtest_teardown) joint jeden
# "pbp-*"-Thread mit 15 s Timeout, bevor eine Fixture die DB schliesst.
# Pool-Worker sind aber IDLE-Dauerlaeufer — sie beenden sich nie, also
# lief der Join jedes Mal voll aus: 15 s pro Test, in Summe ueber eine
# halbe Stunde CI-Laufzeit (Timeout). Statt des Thread-Todes wartet der
# Drain jetzt auf LEERLAUF (warte_auf_leerlauf) — das ist ohnehin die
# richtige Bedingung: kein laufender Auftrag = keine aktive Connection.
_EXECUTOR = ThreadPoolExecutor(max_workers=4,
                               thread_name_prefix="pbpbudget-worker")

# Zaehler laufender Auftraege (nicht der Threads) — Grundlage fuer
# warte_auf_leerlauf.
_LAUFEND = 0
_LAUFEND_LOCK = threading.Lock()
_LEERLAUF = threading.Event()
_LEERLAUF.set()


def _auftrag_beginnt() -> None:
    global _LAUFEND
    with _LAUFEND_LOCK:
        _LAUFEND += 1
        _LEERLAUF.clear()


def _auftrag_endet() -> None:
    global _LAUFEND
    with _LAUFEND_LOCK:
        _LAUFEND = max(0, _LAUFEND - 1)
        if _LAUFEND == 0:
            _LEERLAUF.set()


def warte_auf_leerlauf(timeout: float = 5.0) -> bool:
    """Wartet, bis kein Budget-Auftrag mehr laeuft (True = leer).

    Fuer Test-Teardown und geordnetes Herunterfahren: Pool-Worker leben
    weiter, aber ohne laufenden Auftrag halten sie keine aktive
    DB-Arbeit — genau das ist die Bedingung, unter der db.close()
    gefahrlos ist (A22-Segfault-Schutz).
    """
    return _LEERLAUF.wait(timeout=timeout)


def _budget_sek() -> float:
    try:
        return float(os.environ.get("PBP_TOOL_BUDGET_SEK",
                                    BUDGET_SEK_DEFAULT))
    except (TypeError, ValueError):
        return BUDGET_SEK_DEFAULT


def timeout_ergebnis(tool_name: str, budget: float,
                     lese_tool: str) -> dict:
    """Schemakonformes Ergebnis fuer ein gerissenes Budget."""
    return {
        "status": "timeout",
        "fehler": (f"{tool_name} hat innerhalb von {budget:.0f}s nicht "
                   "geantwortet (Wall-Clock-Budget, #915)."),
        "grund": ("blockierter Aufruf im Tool-Pfad — DB-Schicht oder "
                  "haengende Hintergrund-Arbeit; ein SQLite-Lock haette "
                  "sich vorher als 'database is locked' gemeldet"),
        "hintergrund_tasks": aktuelle_tasks(),
        "hintergrund_zuletzt": zuletzt_beendet(),
        "hinweis": (
            "Der Aufruf laeuft serverseitig weiter und kann SPAETER noch "
            f"wirken. Vor einer Wiederholung IMMER erst mit {lese_tool} "
            "pruefen, ob der Datensatz inzwischen da ist — blindes "
            "Wiederholen erzeugt Dubletten. Hilft ein zweiter Versuch "
            "nicht: MCP-Server neu starten und das Muster in #915 melden."
        ),
    }


def mit_budget(tool_name: str, lese_tool: str = "dem passenden "
               "*_anzeigen-Tool"):
    """Decorator: fuehrt den Tool-Body im Budget-Pool aus.

    Bei Ueberschreitung des Budgets kommt ein `status='timeout'`-Dict
    zurueck statt Stille. Exceptions des Bodys propagieren unveraendert.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            budget = _budget_sek()

            def _lauf():
                try:
                    return fn(*args, **kwargs)
                finally:
                    _auftrag_endet()

            _auftrag_beginnt()
            future = _EXECUTOR.submit(_lauf)
            try:
                return future.result(timeout=budget)
            except _FutureTimeout:
                logger.error(
                    "Wall-Clock-Budget gerissen: %s antwortete nach %.0fs "
                    "nicht (laufende Hintergrund-Tasks: %s)",
                    tool_name, budget, aktuelle_tasks())
                return timeout_ergebnis(tool_name, budget, lese_tool)
        return wrapper
    return decorator


def mit_kurzbudget(fn, budget: float, fallback):
    """Einen einzelnen Aufruf mit eigenem kurzem Budget absichern.

    Fuer optionale Anreicherungen (z.B. den DB-Teil von
    pbp_mcp_diagnose): blockiert der Aufruf, kommt `fallback` zurueck
    und die Diagnose bleibt antwortfaehig.
    """
    def _lauf():
        try:
            return fn()
        finally:
            _auftrag_endet()

    _auftrag_beginnt()
    future = _EXECUTOR.submit(_lauf)
    try:
        return future.result(timeout=budget)
    except _FutureTimeout:
        return fallback
    except Exception as exc:  # Anreicherung darf nie kippen
        logger.debug("Kurzbudget-Aufruf fehlgeschlagen: %s", exc)
        return fallback
