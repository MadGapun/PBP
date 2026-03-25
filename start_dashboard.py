"""PBP Dashboard Launcher - startet das Web-Dashboard auf Port 8200."""
import os, sys

# Finde src-Verzeichnis relativ zu diesem Script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(SCRIPT_DIR, "src")
sys.path.insert(0, SRC_DIR)

# Datenverzeichnis setzen
os.environ.setdefault(
    "BA_DATA_DIR",
    os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "BewerbungsAssistent")
)

# Zentrales Logging aktivieren (schreibt in %BA_DATA_DIR%/logs/pbp.log)
from bewerbungs_assistent.logging_config import setup_logging, get_log_path
setup_logging(console=True)

import logging
logger = logging.getLogger("bewerbungs_assistent")

data_dir = os.environ["BA_DATA_DIR"]
log_path = get_log_path()

logger.info("=== PBP Dashboard Start ===")
logger.info("Python: %s", sys.version)
logger.info("Daten: %s", data_dir)
logger.info("Log: %s", log_path)

try:
    import socket

    port = int(os.environ.get("BA_DASHBOARD_PORT", "8200"))

    # Prüfe ob der Port bereits belegt ist (z.B. durch Claude Desktop)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            print()
            print("  ====================================================")
            print(f"  PBP laeuft bereits auf http://localhost:{port}")
            print()
            print("  Das passiert, wenn Claude Desktop PBP als MCP-Server")
            print("  gestartet hat. Das Dashboard ist schon erreichbar!")
            print()
            print(f"  Oeffne einfach: http://localhost:{port}")
            print()
            print("  Falls du PBP ohne Claude starten willst:")
            print("  1. Schliesse Claude Desktop")
            print("  2. Starte PBP erneut ueber diesen Link")
            print("  ====================================================")
            print()
            # Browser trotzdem öffnen, damit der Nutzer direkt zum Dashboard kommt
            if sys.platform == "win32":
                os.startfile(f"http://localhost:{port}")
            input("  Druecke Enter zum Schliessen...")
            sys.exit(0)

    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.dashboard import start_dashboard

    db = Database()
    db.initialize()
    logger.info("Datenbank initialisiert")

    print()
    print(f"  Dashboard: http://localhost:{port}")
    print(f"  Daten:     {data_dir}")
    print(f"  Log:       {log_path}")
    print(f"  Beenden:   Dieses Fenster schliessen oder Strg+C")
    print()

    start_dashboard(db, port=port)

except Exception as e:
    logger.exception("Dashboard-Fehler: %s", e)
    print()
    print(f"  FEHLER: {e}")
    print(f"  Details in: {log_path}")
    print()
    if sys.platform == "win32":
        input("  Druecke Enter zum Schliessen...")
    sys.exit(1)
