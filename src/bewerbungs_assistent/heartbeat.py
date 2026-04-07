"""MCP Heartbeat — schreibt Zeitstempel bei jedem Tool-Aufruf + periodisch (#304).

Das Dashboard liest diese Datei um den Verbindungsstatus anzuzeigen.
Periodischer Heartbeat alle 30s zeigt, dass der MCP-Server-Prozess lebt,
auch wenn gerade kein Tool aufgerufen wird.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .database import get_data_dir

logger = logging.getLogger("bewerbungs_assistent.heartbeat")

_HEARTBEAT_FILE = "mcp_heartbeat.json"

# Throttle: maximal alle 10 Sekunden schreiben (für Tool-Calls)
_last_write: float = 0.0
_THROTTLE_SECONDS = 10

# Periodischer Heartbeat (#304)
_PERIODIC_INTERVAL = 30  # Sekunden
_periodic_thread: threading.Thread | None = None


def _write_heartbeat_file(tool_name: str, is_alive: bool = False) -> None:
    """Schreibt Heartbeat-Datei."""
    try:
        path = get_data_dir() / _HEARTBEAT_FILE
        data = {
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "last_tool_call": datetime.now(timezone.utc).isoformat() if not is_alive else None,
            "tool": tool_name,
            "type": "alive" if is_alive else "tool_call",
        }
        # Merge with existing data to preserve last_tool_call
        if is_alive:
            existing = read_heartbeat()
            if existing:
                data["last_tool_call"] = existing.get("last_tool_call")
                data["tool"] = existing.get("tool", tool_name)
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:
        logger.debug("Heartbeat schreiben fehlgeschlagen: %s", e)


def write_heartbeat(tool_name: str) -> None:
    """Schreibt Heartbeat-Datei mit Zeitstempel und Tool-Name (throttled)."""
    global _last_write
    now = time.monotonic()
    if now - _last_write < _THROTTLE_SECONDS:
        return
    _last_write = now
    _write_heartbeat_file(tool_name, is_alive=False)


def start_periodic_heartbeat() -> None:
    """Startet periodischen Heartbeat-Thread (#304).

    Schreibt alle 30 Sekunden einen Alive-Heartbeat, damit das Dashboard
    erkennen kann, dass der MCP-Server-Prozess lebt — auch ohne Tool-Calls.
    """
    global _periodic_thread
    if _periodic_thread and _periodic_thread.is_alive():
        return

    def _periodic():
        while True:
            _write_heartbeat_file("alive_ping", is_alive=True)
            time.sleep(_PERIODIC_INTERVAL)

    _periodic_thread = threading.Thread(target=_periodic, daemon=True, name="heartbeat-periodic")
    _periodic_thread.start()
    logger.debug("Periodischer Heartbeat gestartet (alle %ds)", _PERIODIC_INTERVAL)


def read_heartbeat() -> dict | None:
    """Liest Heartbeat-Datei. Gibt None zurueck wenn nicht vorhanden."""
    try:
        path = get_data_dir() / _HEARTBEAT_FILE
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return None


def get_connection_status() -> dict:
    """Ermittelt Verbindungsstatus basierend auf Heartbeat (#304).

    Statusübergänge:
    - connected: Heartbeat < 90s alt (Server lebt + sendet periodisch)
    - unknown:   Heartbeat 90s-300s alt (kurzer Ausfall, prüfe...)
    - disconnected: Heartbeat > 300s alt oder nicht vorhanden

    Returns:
        {"status": "connected"|"unknown"|"disconnected",
         "last_tool_call": ISO-Timestamp oder None,
         "last_tool": Tool-Name oder None,
         "seconds_since_heartbeat": int oder None}
    """
    hb = read_heartbeat()
    if hb is None:
        return {"status": "disconnected", "last_tool_call": None, "last_tool": None,
                "seconds_since_heartbeat": None}

    # Nutze last_heartbeat (periodisch) statt last_tool_call
    heartbeat_ts = hb.get("last_heartbeat") or hb.get("last_tool_call")
    if not heartbeat_ts:
        return {"status": "disconnected", "last_tool_call": None, "last_tool": None,
                "seconds_since_heartbeat": None}

    try:
        last_dt = datetime.fromisoformat(heartbeat_ts)
        age_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
    except (ValueError, TypeError):
        return {"status": "unknown", "last_tool_call": hb.get("last_tool_call"),
                "last_tool": hb.get("tool"), "seconds_since_heartbeat": None}

    # Engere Schwellen dank periodischem Heartbeat (alle 30s)
    if age_seconds < 90:       # 3x Heartbeat-Intervall
        status = "connected"
    elif age_seconds < 300:    # 5 Minuten
        status = "unknown"
    else:
        status = "disconnected"

    return {
        "status": status,
        "last_tool_call": hb.get("last_tool_call"),
        "last_tool": hb.get("tool"),
        "seconds_since_heartbeat": round(age_seconds),
    }
