"""Tool-Module für den Bewerbungs-Assistent MCP Server.

Alle 47 MCP-Tools sind in 8 Domain-Module aufgeteilt:
- profil: Profil-Verwaltung (14 Tools)
- dokumente: Dokument-Analyse und Import/Export (8 Tools)
- jobs: Jobsuche und Stellenverwaltung (5 Tools)
- bewerbungen: Bewerbungs-Management (4 Tools)
- suche: Suchkriterien und Blacklist (2 Tools)
- export_tools: PDF/DOCX-Export (2 Tools)
- analyse: Erweiterte KI-Features (9 Tools)
- workflows: Workflow-Starter (3 Tools) — Prompts als Tools für claude.ai
"""

import functools
import os
import time
from collections import deque
from threading import Lock

from . import profil, dokumente, jobs, bewerbungen, suche, export_tools, analyse, workflows, kontakte, elwosa


# === Tool-Timing Telemetrie (#636, beta.60) ============================
# Ringbuffer mit den letzten Tool-Calls fuer Diagnose. Hilft Timeouts
# einzugrenzen — wenn ein Tool 30+s braucht oder gar nicht zurueckkommt,
# sieht man das im pbp_diagnose-Output. Threadsafe.

_TOOL_CALL_LOG = deque(maxlen=200)
_TOOL_CALL_LOG_LOCK = Lock()
_SLOW_TOOL_THRESHOLD_SEC = 5.0


def record_tool_call(name: str, duration_sec: float, status: str = "ok",
                     args_summary: str = "", error: str = "") -> None:
    """Schreibt einen Tool-Call-Eintrag ins Ringbuffer."""
    with _TOOL_CALL_LOG_LOCK:
        _TOOL_CALL_LOG.append({
            "name": name,
            "duration_sec": round(duration_sec, 3),
            "status": status,
            "args_summary": args_summary[:120],
            "error": error[:200],
            "at": time.time(),
            "pid": os.getpid(),
        })


def get_recent_tool_calls(limit: int = 50) -> list:
    """Liefert die letzten N Tool-Calls (neueste zuerst)."""
    with _TOOL_CALL_LOG_LOCK:
        snapshot = list(_TOOL_CALL_LOG)
    return list(reversed(snapshot[-limit:]))


def get_slow_tool_calls(limit: int = 20, threshold_sec: float | None = None) -> list:
    """Liefert die langsamsten Tool-Calls aus dem Ringbuffer."""
    threshold = threshold_sec if threshold_sec is not None else _SLOW_TOOL_THRESHOLD_SEC
    with _TOOL_CALL_LOG_LOCK:
        snapshot = list(_TOOL_CALL_LOG)
    slow = [e for e in snapshot if e["duration_sec"] >= threshold]
    return sorted(slow, key=lambda e: e["duration_sec"], reverse=True)[:limit]


def time_tool(logger, name: str):
    """Decorator-Faktory fuer Tool-Funktionen.

    Misst Dauer, schreibt einen Eintrag ins Telemetrie-Buffer und loggt
    Warnings bei Slow-Calls. Verwendet von hot-paths (#636) — nicht alle
    Tools, sondern jene die in Issue-Reports auftauchen.

    Verwendung:
        gate = time_tool(logger, "bewerbung_status_aendern")
        @mcp.tool()
        @gate
        def bewerbung_status_aendern(...): ...
    """
    def decorator(fn):
        @functools.wraps(fn)  # WICHTIG: Pydantic/FastMCP brauchen die
                              # Original-Signatur fuer Schema-Generation
        def wrapper(*args, **kwargs):
            t0 = time.time()
            err = ""
            try:
                result = fn(*args, **kwargs)
                status = "ok"
                if isinstance(result, dict) and (result.get("fehler") or result.get("error")):
                    status = "fehler"
                    err = str(result.get("fehler") or result.get("error"))[:200]
                return result
            except Exception as exc:
                status = "exception"
                err = f"{type(exc).__name__}: {exc}"[:200]
                raise
            finally:
                dur = time.time() - t0
                # Args-Summary: nur erste 120 Zeichen
                try:
                    summary_parts = []
                    if args:
                        summary_parts.append(f"args={len(args)}")
                    if kwargs:
                        summary_parts.append(", ".join(
                            f"{k}={str(v)[:30]}" for k, v in list(kwargs.items())[:3]
                        ))
                    args_summary = "; ".join(summary_parts)
                except Exception:
                    args_summary = ""
                record_tool_call(name, dur, status, args_summary, err)
                if dur >= _SLOW_TOOL_THRESHOLD_SEC:
                    logger.warning(
                        "SLOW MCP-Tool: %s dauerte %.2fs (status=%s)",
                        name, dur, status,
                    )
                else:
                    logger.info("Tool %s: %.3fs (%s)", name, dur, status)
        return wrapper
    return decorator


# === Granulare KI-Steuerung (#425, beta.56) ============================
# Shared gate-Helper. Returnt None wenn erlaubt, sonst ein dict das die
# Tools direkt zurueckgeben koennen.

_KI_FEATURE_LABELS = {
    "jobsuche": "Jobsuche via Claude",
    "dokumentenanalyse": "Dokumentenanalyse",
    "stellenanalyse": "Stellenanalyse / Fit-Bewertung",
    "bewerbungserstellung": "Bewerbungs-Erstellung",
    "coaching": "Interview- und Verhandlungs-Coaching",
    "ersterfassung": "Profil-Ersterfassung via Claude",
    "guidance": "KI-Hinweise im Dashboard",
}


def ki_gate(db, feature: str) -> dict | None:
    """Pruefung vor jeder KI-Operation (#425).

    Liefert None wenn erlaubt, sonst ein Fehler-Dict das das Tool direkt
    zurueckgeben kann. Beachtet Master-Switch + Feature-Toggle.
    """
    try:
        if db.is_ki_feature_enabled(feature):
            return None
    except Exception:
        return None
    label = _KI_FEATURE_LABELS.get(feature, feature)
    cfg = db.get_ki_features()
    if not cfg.get("master", True):
        grund = "KI-Master-Switch ist aus"
        wo = "Settings -> KI-Unterstuetzung -> Master"
    else:
        grund = f"Feature '{label}' ist deaktiviert"
        wo = f"Settings -> KI-Unterstuetzung -> {label}"
    return {
        "fehler": grund,
        "feature": feature,
        "ki_blockiert": True,
        "hinweis": (
            f"{grund}. Du kannst es im Dashboard wieder einschalten: {wo}."
        ),
    }


def register_all(mcp, db, logger):
    """Registriert alle Tools beim MCP-Server."""
    profil.register(mcp, db, logger)
    dokumente.register(mcp, db, logger)
    jobs.register(mcp, db, logger)
    bewerbungen.register(mcp, db, logger)
    suche.register(mcp, db, logger)
    export_tools.register(mcp, db, logger)
    analyse.register(mcp, db, logger)
    workflows.register(mcp, db, logger)
    kontakte.register(mcp, db, logger)  # v1.7.0 #563
    elwosa.register(mcp, db, logger)    # v1.7.0-beta.37 #599
