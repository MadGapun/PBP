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

def _start_ohne_datenbank_melden(exc: BaseException) -> None:
    """Der Start scheitert beim Öffnen der Datenbank: Spur im Log und eine Zeile für Menschen (#1149).

    Auf dem Weg über Claude Desktop (`python -m bewerbungs_assistent`) blieb ein
    solcher Fehler ohne Spur: Traceback nur auf stderr, `pbp.log` leer, der
    Dashboard-Port nie gebunden — und der Installer verweist für Fehler auf
    `pbp.log`. Gemessen mit gesperrtem Sicherungsordner.
    """
    try:
        ordner = str(get_data_dir())
    except Exception:  # noqa: BLE001 — selbst der Ordner kann das Problem sein
        ordner = "(Datenordner nicht ermittelbar)"
    grund = str(exc).strip() or exc.__class__.__name__
    text = (
        f"PBP konnte die Datenbank nicht öffnen und startet deshalb nicht. Grund: {grund} "
        f"Datenordner: {ordner}. Häufige Ursachen: kein Schreibrecht oder kein freier Platz "
        "im Datenordner (auch im Unterordner 'backups'), die Datei ist von einem anderen "
        "Programm gesperrt oder beschädigt. Behebe die Ursache und starte PBP neu; "
        "Sicherungen der Datenbank liegen im Unterordner 'backups'."
    )
    try:
        logger.critical(text, exc_info=exc)
    except Exception:  # noqa: BLE001
        pass
    try:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001
        pass


# Initialize database
db = Database()
try:
    db.initialize()
except Exception as _start_fehler:
    _start_ohne_datenbank_melden(_start_fehler)
    raise

# #303: Zombie-Background-Jobs bereinigen (von vorherigem Absturz).
# #1107: als Methode, damit sie pruefbar ist; sie kennt auch das alte
# 'laeuft' des Lernlaufs.
try:
    zombie_count = db.unterbrochene_jobs_abbrechen()
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
PBP (Persönliches Bewerbungs-Portal) ist die Quelle für alles rund um
die Jobsuche dieses Menschen: Profil, Stellen, Bewerbungen, Dokumente,
Termine, Aufgaben, Statistik.

NUTZER UND TON
Menschen auf Jobsuche, oft ohne Technikwissen, manchmal nach vielen
Absagen müde. {_TON} Sprich Deutsch. Nenne keine Werkzeugnamen,
IDs oder Fachbegriffe, wenn ein Satz genügt.

EINSTIEG
Rufe zu Beginn profil_status() auf. Die Antwort nennt den nächsten
Schritt; ohne Profil ist das die Ersterfassung ("Starte die
Ersterfassung"). Das Dashboard liegt unter {_dashboard_link()}; viele
Antworten tragen ein Feld dashboard_link, das direkt zur Stelle oder
Bewerbung führt — nenne es, wenn der Mensch dort weitermachen will.

WAHRHEIT
- Firmen-Status nie aus dem Gedaechtnis: sobald eine Firma mit einer
  Wertung fällt ("kenne ich", "war abgesagt", "läuft noch"), zuerst
  firma_kontext(firmenname) und nur dessen Ergebnis wiedergeben.
- Punkte: {_SCORE_BEDEUTUNG}
- Ein Urteil über eine Stelle entsteht erst, wenn du Anzeige und Profil
  gelesen hast (fit_analyse); halte es mit stelle_urteil_speichern fest.
- Absagegründe nie erfinden: nur aus der Liste, die das Werkzeug nennt,
  oder aus dem, was die Firma geschrieben hat.

SICHERHEIT UND DATENSCHUTZ
- NIEMALS direkt in die Datenbank (pbp.db) schreiben oder über andere
  Werkzeuge (Dateisystem, sqlite, Desktop Commander) an PBP-Daten gehen:
  das umgeht die PBP-Logik (Verlauf, Lerneffekte, Sicherungen).
- Vor jedem Loeschen die Vorschau zeigen und die Bestaetigung des
  Menschen abwarten; die Werkzeuge liefern die Vorschau von selbst.
- {_DATENSCHUTZ} Einzelne Bereiche lassen sich in den Einstellungen
  sperren; ein gesperrtes Werkzeug sagt das und nennt eine Alternative.

WERKZEUGWAHL
- Bei Unklarheit pbp_capabilities() — kuratierte Übersicht nach
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

    #: Aufrufe, die in die Zeitüberschreitung liefen: (Werkzeug, Argumente) ->
    #: Zeitpunkt. Der Arbeits-Thread eines synchronen Werkzeugs lässt sich nicht
    #: abbrechen und rechnet weiter (#1148); eine sofortige Wiederholung mit
    #: denselben Argumenten startete dieselbe Rechnung ein zweites Mal.
    _abgelaufen: dict = {}

    @staticmethod
    def _schluessel(context, tool_name):
        try:
            args = json.dumps(getattr(context.message, "arguments", None) or {},
                              sort_keys=True, default=str, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            args = ""
        return (tool_name, args)

    async def on_call_tool(self, context, call_next):
        import asyncio
        from fastmcp.exceptions import ToolError
        tool_name = context.message.name if context.message else "unknown"
        logger.info("Tool aufgerufen: %s", tool_name)
        write_heartbeat(tool_name)

        # #1148 Punkt 9: typisierte Kennungen ("APP-42061e46", "JOB-…") nimmt jedes Werkzeug an.
        # PBP gibt sie aus, aber nur einzelne Werkzeuge verstanden sie wieder; das Praefix faellt
        # deshalb hier weg, bevor ein Werkzeug die Argumente sieht.
        from .services.typed_ids import FalscheKennung, normalisiere_argumente
        try:
            neue_argumente = normalisiere_argumente(getattr(context.message, "arguments", None))
        except FalscheKennung as exc:
            raise ToolError(json.dumps({
                "error": "falsche_kennung",
                "tool": tool_name,
                "message": str(exc),
            }, ensure_ascii=False))
        if neue_argumente is not None and hasattr(context.message, "model_copy"):
            context = context.copy(
                message=context.message.model_copy(update={"arguments": neue_argumente}))

        timeout = self.LONG_TIMEOUT if tool_name in self.LONG_RUNNING_TOOLS else self.DEFAULT_TIMEOUT

        # #1148: lief derselbe Aufruf eben in die Zeitüberschreitung und rechnet
        # noch, nicht ein zweites Mal starten.
        schluessel = self._schluessel(context, tool_name)
        if schluessel in self._abgelaufen:
            from .tools import laufende_aufrufe
            if laufende_aufrufe(tool_name) > 0:
                raise ToolError(json.dumps({
                    "error": "laeuft_noch",
                    "tool": tool_name,
                    "message": (
                        f"'{tool_name}' rechnet mit diesen Angaben noch, nachdem die "
                        "Zeit überschritten war. Warte einen Moment und frage dann noch "
                        "einmal — eine Wiederholung jetzt würde dieselbe Rechnung ein "
                        "zweites Mal starten."),
                }, ensure_ascii=False))
            self._abgelaufen.pop(schluessel, None)

        try:
            result = await asyncio.wait_for(call_next(context), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error("Tool %s Timeout nach %ds", tool_name, timeout)
            self._abgelaufen[schluessel] = True
            if len(self._abgelaufen) > 50:  # Altlasten nicht anhaeufen
                self._abgelaufen.pop(next(iter(self._abgelaufen)), None)
            # Strukturierter Fehler statt Silence (#303). #1148: als Fehler
            # MELDEN statt als Ergebnis ohne strukturierten Inhalt zu bauen —
            # jedes Werkzeug deklariert ein Ausgabeschema, und die Pruefung
            # ersetzte die deutsche Meldung durch "Output validation error:
            # outputSchema defined but no structured output returned".
            raise ToolError(json.dumps({
                "error": "timeout",
                "tool": tool_name,
                "timeout_seconds": timeout,
                "message": (
                    f"Tool '{tool_name}' hat nach {timeout} Sekunden nicht geantwortet. "
                    f"Mögliche Ursache: DB-Lock oder externer Service nicht erreichbar. "
                    f"Die Rechnung kann im Hintergrund noch laufen — warte einen "
                    f"Moment, bevor du es erneut versuchst."
                ),
            }, ensure_ascii=False))
        except Exception as e:
            logger.error("Tool %s Fehler: %s", tool_name, e, exc_info=True)
            raise
        finally:
            # #708: Bricht wait_for ein Tool mitten in einem Write ab (oder
            # leakt ein Fehlerpfad eine Transaktion), bliebe der Write-Lock
            # sonst dauerhaft offen — jeder weitere Write (auch der des
            # Dashboard-Threads) scheitert dann bis zum Neustart.
            # #1144: das wirkt nur auf die Connection DIESES Threads, also
            # des Event-Loops (asynchrone Werkzeuge). Synchrone Werkzeuge
            # laufen in Worker-Threads mit eigener Connection; dort raeumt
            # `tools/__init__._mit_aufraeumen` im Worker selbst auf.
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

def dashboard_im_hintergrund_starten(datenbank, port: int | None = None):
    """Startet das Dashboard als Thread dieses Prozesses — und mit ihm den Planer.

    v1.7.146 (#1138): Der Planer (tägliche Sicherung, geplante Suche, Lernen)
    wurde bisher nur in `dashboard.start_dashboard` gestartet, also nur im
    eigenständigen Dashboard. Der Weg, den Claude Desktop nimmt (dieser hier),
    startete ihn nie: die Karte versprach "PBP sichert einmal am Tag von
    selbst", und es geschah nichts. Wer das Dashboard hostet, hostet auch den
    Planer — an EINER Stelle, damit kein Weg ihn wieder vergisst.

    Gibt den uvicorn-Server zurück (zum sauberen Beenden) oder None, wenn der
    Port belegt ist: dort läuft eine andere Instanz, die das Dashboard und
    damit den Planer hat (kein Doppellauf). Wird sie geschlossen, übernimmt
    dieser Prozess später (`dashboard_nachholen_starten`, #1155).
    """
    from .dashboard import app as dashboard_app
    import uvicorn
    from . import dashboard as _dashboard_module
    from .services import dashboard_halter
    _dashboard_module._db = datenbank  # Set shared database reference

    dash_port = port or int(os.environ.get("BA_DASHBOARD_PORT", "8200"))

    # Port-Konflikt pruefen (#293)
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", dash_port)) == 0:
            # #1149: nicht jeder belegte Port gehoert einem PBP.
            if dashboard_halter.ist_pbp(dash_port):
                logger.warning(
                    "Port %d ist bereits belegt — dort laeuft eine andere PBP-Instanz. "
                    "Dashboard wird nicht erneut gestartet, MCP-Server laeuft trotzdem.",
                    dash_port,
                )
                dashboard_halter.setzen(dashboard_halter.ANDERER, port=dash_port)
            else:
                logger.warning(
                    "Port %d wird von einem anderen Programm benutzt (kein PBP). "
                    "Dashboard und Planer starten hier nicht; der MCP-Server laeuft trotzdem.",
                    dash_port,
                )
                dashboard_halter.setzen(dashboard_halter.FREMDES, port=dash_port)
            return None

    config = uvicorn.Config(
        dashboard_app, host="127.0.0.1", port=dash_port, log_level="warning",
    )
    dashboard_server = uvicorn.Server(config)
    dashboard_thread = threading.Thread(target=dashboard_server.run, daemon=True)
    dashboard_thread.start()
    logger.info("Web Dashboard gestartet auf http://localhost:%d", dash_port)
    dashboard_halter.setzen(dashboard_halter.EIGENER, port=dash_port, server=dashboard_server)

    try:
        from .services.automatik_scheduler import start_automatik_scheduler
        start_automatik_scheduler(datenbank)
    except Exception as exc:  # der Planer darf den Serverstart nie verhindern
        logger.warning("Automatik-Scheduler konnte nicht starten: %s", exc)
    return dashboard_server


#: Wie oft ein Prozess, der den Dashboard-Port nicht bekam, nachsieht, ob er
#: inzwischen frei ist (#1155). Selten genug, um nicht aufzufallen; oft genug,
#: dass niemand lange ohne Sicherung dasteht.
DASHBOARD_NACHHOLEN_S = 300


def dashboard_nachholen_starten(datenbank, port: int | None = None,
                                intervall_s: float | None = None):
    """Übernimmt Dashboard und Planer, sobald der Port frei wird (#1155).

    Bis v1.7.147 prüfte der Prozess den Port nur beim Start. Lief dort das
    eigenständige Dashboard (Desktop-Verknüpfung) und wurde später
    geschlossen, gab es bis zum Neustart von Claude Desktop weder Dashboard
    noch tägliche Sicherung noch geplante Suche — und die Karte
    "Sicherungen" versprach weiter "PBP sichert einmal am Tag von selbst".

    Ein Daemon-Thread sieht alle `intervall_s` Sekunden nach; ist der Port
    frei, startet er denselben Weg wie beim Start (Dashboard UND Planer, an
    einer Stelle) und endet. Solange der Port belegt bleibt, passiert nichts.
    Gibt den Thread zurück; `thread.stoppen()` beendet ihn (für Tests).
    """
    import socket
    from .services import dashboard_halter

    dash_port = port or int(os.environ.get("BA_DASHBOARD_PORT", "8200"))
    pause = DASHBOARD_NACHHOLEN_S if intervall_s is None else intervall_s
    stopp = threading.Event()
    dashboard_halter.pruefintervall_merken(pause)

    def _port_belegt() -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                return s.connect_ex(("127.0.0.1", dash_port)) == 0
        except OSError:
            return True  # im Zweifel nicht anfassen

    def _schleife():
        while not stopp.wait(pause):
            if dashboard_halter.lesen()["halter"] == dashboard_halter.EIGENER:
                return
            dashboard_halter.versuch_zaehlen()
            if _port_belegt():
                continue
            logger.info(
                "Port %d ist frei geworden — Dashboard und Planer starten jetzt "
                "in diesem Prozess (#1155).", dash_port)
            try:
                if dashboard_im_hintergrund_starten(datenbank, dash_port) is not None:
                    return
            except Exception as exc:  # noqa: BLE001 — beim naechsten Mal wieder
                logger.warning("Dashboard-Nachstart fehlgeschlagen: %s", exc)

    thread = threading.Thread(target=_schleife, daemon=True, name="dashboard-nachholen")
    thread.stoppen = stopp.set
    thread.start()
    logger.info("Dashboard-Port %d ist belegt — dieser Prozess sieht alle %d s nach, "
                "ob er das Dashboard übernehmen kann.", dash_port, int(pause))
    return thread


def run_server():
    """Start the MCP server with optional web dashboard."""
    import atexit
    import signal

    from .services import dashboard_halter

    _dashboard_server = None

    # Start web dashboard in background thread (with managed uvicorn.Server for clean shutdown)
    try:
        _dashboard_server = dashboard_im_hintergrund_starten(db)
    except Exception as e:
        logger.warning("Dashboard konnte nicht gestartet werden: %s", e)
        dashboard_halter.setzen(dashboard_halter.KEINER, fehler=str(e))

    # #1155: hat dieser Prozess das Dashboard nicht bekommen (Port belegt),
    # sieht er spaeter nach, ob er es uebernehmen kann.
    if _dashboard_server is None:
        try:
            dashboard_nachholen_starten(db)
        except Exception as e:
            logger.warning("Dashboard-Nachholen nicht gestartet: %s", e)

    # Clean shutdown handler — stops dashboard + closes DB
    def _cleanup():
        logger.info("Bewerbungs-Assistent wird beendet...")
        # Auch ein SPAETER uebernommenes Dashboard (#1155) muss gestoppt werden.
        _laufend = dashboard_halter.server() or _dashboard_server
        if _laufend:
            try:
                _laufend.should_exit = True
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
