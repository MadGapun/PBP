"""MCP Heartbeat — schreibt Zeitstempel bei jedem Tool-Aufruf.

Das Dashboard liest diese Datei um den Verbindungsstatus anzuzeigen.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from .database import get_data_dir

logger = logging.getLogger("bewerbungs_assistent.heartbeat")

_HEARTBEAT_FILE = "mcp_heartbeat.json"

# Throttle: maximal alle 10 Sekunden schreiben
_last_write: float = 0.0
_THROTTLE_SECONDS = 10


def write_heartbeat(tool_name: str) -> None:
    """Schreibt Heartbeat-Datei mit Zeitstempel und Tool-Name."""
    global _last_write
    now = time.monotonic()
    if now - _last_write < _THROTTLE_SECONDS:
        return
    _last_write = now

    try:
        path = get_data_dir() / _HEARTBEAT_FILE
        data = {
            "last_tool_call": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:
        logger.debug("Heartbeat schreiben fehlgeschlagen: %s", e)


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
    """Ermittelt Verbindungsstatus basierend auf Heartbeat.

    Returns:
        {"status": "connected"|"unknown"|"disconnected",
         "last_tool_call": ISO-Timestamp oder None,
         "last_tool": Tool-Name oder None}
    """
    hb = read_heartbeat()
    if hb is None:
        return {"status": "disconnected", "last_tool_call": None, "last_tool": None}

    last_call = hb.get("last_tool_call")
    if not last_call:
        return {"status": "disconnected", "last_tool_call": None, "last_tool": None}

    try:
        last_dt = datetime.fromisoformat(last_call)
        age_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
    except (ValueError, TypeError):
        return {"status": "unknown", "last_tool_call": last_call, "last_tool": hb.get("tool")}

    if age_seconds < 300:  # 5 Minuten
        status = "connected"
    elif age_seconds < 3600:  # 1 Stunde
        status = "unknown"
    else:
        status = "disconnected"

    return {
        "status": status,
        "last_tool_call": last_call,
        "last_tool": hb.get("tool"),
    }
