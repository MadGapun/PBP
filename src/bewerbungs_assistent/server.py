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
from .heartbeat import write_heartbeat, start_periodic_heartbeat, start_ollama_warmup_loop

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

# PBP-MCP Instruktionen — werden beim MCP-Initialize-Handshake an
# Claude Desktop gesendet und sind Teil des System-Kontextes fuer diesen
# Server.
#
# H28 (#1087 G10): bis v1.7.134 bestanden sie zu einem Drittel aus
# GitHub-Regeln und sagten nichts ueber die Menschen, die PBP nutzen,
# den Ton, den Einstieg, die Bedeutung der Punkte, erfundene
# Absagegruende, Loeschen, Datenschutz oder den Weg ins Dashboard. Die
# Regeln fuer Texte nach aussen stehen jetzt in pbp_grenze_melden und im
# Prompt problem_melden, wo sie gebraucht werden.
from .services.punkte import SCORE_BEDEUTUNG as _SCORE_BEDEUTUNG
from .services.ton import TON as _TON
from .services.datenschutz import KURZ as _DATENSCHUTZ
from .services.dashboard_link import dashboard_link as _dashboard_link

PBP_INSTRUCTIONS = f"""\
PBP (Persoenliches Bewerbungs-Portal) ist die Quelle fuer alles rund um
die Jobsuche dieses Menschen: Profil, Stellen, Bewerbungen, Dokumente,
Termine, Aufgaben, Statistik.

NUTZER UND TON
Menschen auf Jobsuche, oft ohne Technikwissen, manchmal nach vielen
Absagen muede. {_TON} Sprich Deutsch. Nenne keine Werkzeugnamen,
IDs oder Fachbegriffe, wenn ein Satz genuegt.

EINSTIEG
Rufe zu Beginn profil_status() auf. Die Antwort nennt den naechsten
Schritt; ohne Profil ist das die Ersterfassung ("Starte die
Ersterfassung"). Das Dashboard liegt unter {_dashboard_link()}; viele
Antworten tragen ein Feld dashboard_link, das direkt zur Stelle oder
Bewerbung fuehrt — nenne es, wenn der Mensch dort weitermachen will.

WAHRHEIT
- Firmen-Status nie aus dem Gedaechtnis: sobald eine Firma mit einer
  Wertung faellt ("kenne ich", "war abgesagt", "laeuft noch"), zuerst
  firma_kontext(firmenname) und nur dessen Ergebnis wiedergeben.
- Punkte: {_SCORE_BEDEUTUNG}
- Ein Urteil ueber eine Stelle entsteht erst, wenn du Anzeige und Profil
  gelesen hast (fit_analyse); halte es mit stelle_urteil_speichern fest.
- Absagegruende nie erfinden: nur aus der Liste, die das Werkzeug nennt,
  oder aus dem, was die Firma geschrieben hat.

SICHERHEIT UND DATENSCHUTZ
- NIEMALS direkt in die Datenbank (pbp.db) schreiben oder ueber andere
  Werkzeuge (Dateisystem, sqlite, Desktop Commander) an PBP-Daten gehen:
  das umgeht die PBP-Logik (Verlauf, Lerneffekte, Sicherungen).
- Vor jedem Loeschen die Vorschau zeigen und die Bestaetigung des
  Menschen abwarten; die Werkzeuge liefern die Vorschau von selbst.
- {_DATENSCHUTZ} Einzelne Bereiche lassen sich in den Einstellungen
  sperren; ein gesperrtes Werkzeug sagt das und nennt eine Alternative.

WERKZEUGWAHL
- Bei Unklarheit pbp_capabilities() — kuratierte Uebersicht nach
  Aufgaben.
- Viele Stellen auf einmal aussortieren: stellen_bulk_bewerten mit
  dry_run=True, dann anwenden — nicht hundertmal stelle_einordnen.
- Reparatur- und Diagnosewerkzeuge sind nur im Expertenmodus sichtbar
  (expertenmodus_setzen).
- Bietet PBP nichts Passendes: pbp_grenze_melden(...) statt eines
  stillen Umwegs. Die Antwort sagt, was vor einer Meldung zu tun ist.
"""

# Create MCP server
mcp = FastMCP(
    "Bewerbungs-Assistent",
    instructions=PBP_INSTRUCTIONS,
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
        finally:
            # #708: Bricht wait_for ein Tool mitten in einem Write ab (oder
            # leakt ein Fehlerpfad eine Transaktion), bliebe der Write-Lock
            # sonst dauerhaft offen — jeder weitere Write (auch der des
            # Dashboard-Threads) scheitert dann bis zum Neustart.
            try:
                db.rollback_if_stale(context=f"Tool '{tool_name}'")
            except Exception:
                pass


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

# H21 (#1087 G1): Wartungs- und Entwicklerwerkzeuge nur im Expertenmodus.
from .services import werkzeug_katalog as _werkzeug_katalog
_werkzeug_katalog.sichtbarkeit_anwenden(mcp, _werkzeug_katalog.beim_start_sichtbar(db))


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
        # #1086: Ollama auf Wunsch mit beenden — vor db.close(), weil die
        # Einstellung am Profil liegt. Vorgabe AUS.
        try:
            from .services import ollama_start
            ollama_start.beim_beenden(db)
        except Exception as ex:
            logger.warning("Ollama-Stop beim Beenden uebersprungen: %s", ex)
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
    # #304: Periodischer Heartbeat — Dashboard erkennt ob Server lebt (ohne Tool-Calls)
    start_periodic_heartbeat()
    # #638 (v1.7.0-beta.62): Ollama-Warmup-Loop — haelt das lokale Modell warm
    # damit der erste Aufruf nach Inaktivitaet nicht 50-60s Cold-Load kostet
    # (MCP-Timeout-Risiko). Nur aktiv wenn user_state='active'.
    start_ollama_warmup_loop(db)
    # #1001: Ollama auf Wunsch mitstarten. Vorgabe AUS; die Logik liegt in
    # services/ollama_start.py und wird auch vom Dashboard-Startweg und vom
    # Knopf im Einstellungen-Tab aufgerufen — eine Fassung, drei Aufrufer.
    try:
        from .services import ollama_start
        ollama_start.beim_start(db)
    except Exception as exc:
        logger.warning("Ollama-Autostart uebersprungen: %s", exc)

    # Run MCP server (blocks on stdio)
    from . import __version__
    logger.info("Bewerbungs-Assistent MCP Server v%s gestartet", __version__)
    mcp.run(transport="stdio")
