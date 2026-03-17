"""PBP Dashboard Launcher - startet das Web-Dashboard auf Port 5173."""
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
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.dashboard import start_dashboard

    db = Database()
    db.initialize()
    logger.info("Datenbank initialisiert")

    print()
    print(f"  Dashboard: http://localhost:5173")
    print(f"  Daten:     {data_dir}")
    print(f"  Log:       {log_path}")
    print(f"  Beenden:   Dieses Fenster schliessen oder Strg+C")
    print()

    start_dashboard(db)

except Exception as e:
    logger.exception("Dashboard-Fehler: %s", e)
    print()
    print(f"  FEHLER: {e}")
    print(f"  Details in: {log_path}")
    print()
    input("  Druecke Enter zum Schliessen...")
