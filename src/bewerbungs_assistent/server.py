"""MCP Server for Bewerbungs-Assistent — Composition Root.

Initialisiert Logging, Datenbank und MCP-Server.
Registriert alle Tools, Resources und Prompts aus den jeweiligen Modulen.
Startet das Web-Dashboard in einem Hintergrund-Thread.
"""

import sys
import os
import json
import threading
import logging
import functools

from fastmcp import FastMCP

from .database import Database, get_data_dir
from .heartbeat import write_heartbeat

# Logging: Datei + stderr (stdout ist für MCP-Protokoll reserviert!)
from .logging_config import setup_logging
setup_logging(console=True)
logger = logging.getLogger("bewerbungs_assistent")

# Initialize database
db = Database()
db.initialize()

# #303: Zombie-Background-Jobs bereinigen (status='running' von vorherigem Absturz)
try:
    conn = db.connect()
    zombie_count = conn.execute(
        "UPDATE background_jobs SET status='abgebrochen', "
        "message='Server-Neustart: Job war noch als running markiert', "
        "updated_at=datetime('now') "
        "WHERE status IN ('running', 'pending')"
    ).rowcount
    conn.commit()
    if zombie_count:
        logger.info("Zombie-Jobs bereinigt: %d Jobs auf 'abgebrochen' gesetzt", zombie_count)
except Exception as e:
    logger.warning("Zombie-Job-Cleanup fehlgeschlagen: %s", e)

# Create MCP server
mcp = FastMCP(
    "Bewerbungs-Assistent",
)


# ============================================================
# Zentrale Tool-Aufruf-Protokollierung via FastMCP Middleware
# ============================================================

from fastmcp.server.middleware import Middleware


class HeartbeatMiddleware(Middleware):
    """Loggt jeden Tool-Aufruf, schreibt Heartbeat und erzwingt Timeouts (#303)."""

    # Tools die länger laufen dürfen (z.B. Jobsuche mit Scrapern)
    LONG_RUNNING_TOOLS = {"jobsuche_starten", "jobsuche_status"}
    DEFAULT_TIMEOUT = 60  # Sekunden
    LONG_TIMEOUT = 300    # 5 Minuten für Scraper-Tools

    async def on_call_tool(self, context, call_next):
        import asyncio
        tool_name = context.message.name if context.message else "unknown"
        logger.info("Tool aufgerufen: %s", tool_name)
        write_heartbeat(tool_name)

        timeout = self.LONG_TIMEOUT if tool_name in self.LONG_RUNNING_TOOLS else self.DEFAULT_TIMEOUT

        try:
            result = await asyncio.wait_for(call_next(context), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error("Tool %s Timeout nach %ds", tool_name, timeout)
            # Strukturierter Fehler statt Silence (#303)
            from fastmcp.tools.tool import ToolResult
            from mcp.types import TextContent
            error_msg = json.dumps({
                "error": "timeout",
                "tool": tool_name,
                "timeout_seconds": timeout,
                "message": (
                    f"Tool '{tool_name}' hat nach {timeout} Sekunden nicht geantwortet. "
                    f"Mögliche Ursache: DB-Lock oder externer Service nicht erreichbar. "
                    f"Bitte versuche es erneut."
                ),
            }, ensure_ascii=False)
            return ToolResult(content=[TextContent(type="text", text=error_msg)])
        except Exception as e:
            logger.error("Tool %s Fehler: %s", tool_name, e, exc_info=True)
            raise


mcp.add_middleware(HeartbeatMiddleware())


# ============================================================
# Tools, Resources und Prompts registrieren
# ============================================================

from .tools import register_all
from .resources import register_resources
from .prompts import register_prompts

register_all(mcp, db, logger)
register_resources(mcp, db, logger)
register_prompts(mcp, db, logger)


# ============================================================
# Server runner
# ============================================================

def run_server():
    """Start the MCP server with optional web dashboard."""
    import atexit
    import signal

    _dashboard_server = None

    # Start web dashboard in background thread (with managed uvicorn.Server for clean shutdown)
    try:
        from .dashboard import app as dashboard_app
        import uvicorn
        from . import dashboard as _dashboard_module
        _dashboard_module._db = db  # Set shared database reference

        dash_port = int(os.environ.get("BA_DASHBOARD_PORT", "8200"))

        # Port-Konflikt pruefen (#293)
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", dash_port)) == 0:
                logger.warning(
                    "Port %d ist bereits belegt — vermutlich laeuft eine andere PBP-Instanz. "
                    "Dashboard wird nicht erneut gestartet, MCP-Server laeuft trotzdem.",
                    dash_port,
                )
                _dashboard_server = None
            else:
                config = uvicorn.Config(
                    dashboard_app, host="127.0.0.1", port=dash_port, log_level="warning",
                )
                _dashboard_server = uvicorn.Server(config)

                dashboard_thread = threading.Thread(target=_dashboard_server.run, daemon=True)
                dashboard_thread.start()
                logger.info("Web Dashboard gestartet auf http://localhost:%d", dash_port)
    except Exception as e:
        logger.warning("Dashboard konnte nicht gestartet werden: %s", e)

    # Clean shutdown handler — stops dashboard + closes DB
    def _cleanup():
        logger.info("Bewerbungs-Assistent wird beendet...")
        if _dashboard_server:
            try:
                _dashboard_server.should_exit = True
                logger.info("Dashboard-Server gestoppt")
            except Exception as ex:
                logger.warning("Dashboard-Stop Fehler: %s", ex)
        try:
            db.close()
            logger.info("Datenbank geschlossen")
        except Exception as ex:
            logger.warning("DB-Close Fehler: %s", ex)

    atexit.register(_cleanup)

    # Signal handlers for graceful shutdown
    def _signal_handler(signum, frame):
        logger.info("Signal %s empfangen, beende...", signum)
        _cleanup()
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
        if hasattr(signal, "SIGBREAK"):  # Windows
            signal.signal(signal.SIGBREAK, _signal_handler)
    except (OSError, ValueError):
        pass  # Signals not available in all contexts

    # Heartbeat beim Start schreiben (#295) — Dashboard zeigt sofort "Verbunden"
    write_heartbeat("server_start")

    # Run MCP server (blocks on stdio)
    from . import __version__
    logger.info("Bewerbungs-Assistent MCP Server v%s gestartet", __version__)
    mcp.run(transport="stdio")
