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

# Logging: Datei + stderr (stdout ist fuer MCP-Protokoll reserviert!)
from .logging_config import setup_logging
setup_logging(console=True)
logger = logging.getLogger("bewerbungs_assistent")

# Initialize database
db = Database()
db.initialize()

# Create MCP server
mcp = FastMCP(
    "Bewerbungs-Assistent",
)


# ============================================================
# Zentrale Tool-Aufruf-Protokollierung
# ============================================================

_original_tool = mcp.tool

def _logged_tool(*args, **kwargs):
    """Wrapper: Loggt jeden Tool-Aufruf und Fehler in die Log-Datei."""
    decorator = _original_tool(*args, **kwargs)
    def wrapper(func):
        @functools.wraps(func)
        def logged_func(*a, **kw):
            logger.info("Tool aufgerufen: %s", func.__name__)
            try:
                result = func(*a, **kw)
                if isinstance(result, dict) and "fehler" in result:
                    logger.warning("Tool %s: %s", func.__name__, result["fehler"])
                return result
            except Exception as e:
                logger.error("Tool %s Fehler: %s", func.__name__, e, exc_info=True)
                raise
        return decorator(logged_func)
    return wrapper

mcp.tool = _logged_tool


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

    # Run MCP server (blocks on stdio)
    from . import __version__
    logger.info("Bewerbungs-Assistent MCP Server v%s gestartet", __version__)
    mcp.run(transport="stdio")
