"""In-Memory-Register fuer laufende Hintergrund-Arbeit (#915, v1.7.17).

Wenn ein schreibendes MCP-Tool in sein Wall-Clock-Budget laeuft, soll das
Timeout-Ergebnis benennen koennen, WER gerade arbeitet — der Auto-Engine
kennt seinen eigenen Zustand. Bewusst OHNE Datenbank: im Ereignisfall ist
die DB-Schicht moeglicherweise genau die blockierte Ressource (die Lehre
aus pbp_mcp_diagnose, das im Vorfall vom 17.08. selbst nicht antwortete).

Threadsafe; haelt nur den aktuellsten Eintrag je Thread plus den zuletzt
beendeten. Kein Ersatz fuer die background_jobs-Tabelle (#799) — das hier
ist die Notbeleuchtung, die auch bei DB-Blockade an bleibt.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

_LOCK = threading.Lock()
# thread_ident -> {"task": str, "seit": float}
_AKTIV: dict = {}
_ZULETZT: dict | None = None


def task_beginnt(name: str) -> None:
    with _LOCK:
        _AKTIV[threading.get_ident()] = {"task": name, "seit": time.time()}


def task_endet(name: str) -> None:
    global _ZULETZT
    with _LOCK:
        eintrag = _AKTIV.pop(threading.get_ident(), None)
        if eintrag and eintrag.get("task") == name:
            _ZULETZT = {"task": name,
                        "dauer_sek": round(time.time() - eintrag["seit"], 1),
                        "beendet_vor_sek": 0.0,
                        "_beendet_um": time.time()}


@contextmanager
def laufender_task(name: str):
    task_beginnt(name)
    try:
        yield
    finally:
        task_endet(name)


def aktuelle_tasks() -> list:
    """Alle gerade laufenden Hintergrund-Tasks (aeltester zuerst)."""
    jetzt = time.time()
    with _LOCK:
        eintraege = sorted(_AKTIV.values(), key=lambda e: e["seit"])
        return [{"task": e["task"],
                 "laeuft_seit_sek": round(jetzt - e["seit"], 1)}
                for e in eintraege]


def zuletzt_beendet() -> dict | None:
    with _LOCK:
        if _ZULETZT is None:
            return None
        out = dict(_ZULETZT)
    out["beendet_vor_sek"] = round(time.time() - out.pop("_beendet_um"), 1)
    return out
