"""PBP Dashboard Launcher - startet das Web-Dashboard auf Port 8200."""
import os, shutil, subprocess, sys

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


def _find_chrome() -> str | None:
    """Find Chrome executable. Supports Windows, macOS and Linux."""
    if sys.platform == "darwin":
        mac_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.isfile(mac_chrome):
            return mac_chrome
        return shutil.which("google-chrome") or shutil.which("chromium-browser")

    if sys.platform != "win32":
        return shutil.which("google-chrome") or shutil.which("chromium-browser")

    # Typische Chrome-Installationspfade auf Windows
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _open_in_chrome(url: str) -> None:
    """Open URL in Chrome if available, otherwise fall back to system default."""
    chrome = _find_chrome()
    if chrome:
        logger.info("Oeffne Dashboard in Chrome: %s", chrome)
        try:
            subprocess.Popen([chrome, url], start_new_session=True)
            return
        except Exception as e:
            logger.warning("Chrome-Start fehlgeschlagen: %s — nutze Fallback", e)

    # Fallback: System-Standard-Browser
    logger.info("Chrome nicht gefunden — oeffne im Standard-Browser")
    if sys.platform == "win32":
        os.startfile(url)
    else:
        import webbrowser
        webbrowser.open(url)


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
            _open_in_chrome(f"http://localhost:{port}")
            input("  Druecke Enter zum Schliessen...")
            sys.exit(0)

    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.dashboard import start_dashboard

    db = Database()
    db.initialize()
    logger.info("Datenbank initialisiert")

    # Claude Desktop Neustart anbieten (damit MCP-Server sauber geladen wird)
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Claude.exe", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000,
            )
            if "Claude.exe" in result.stdout:
                print()
                print("  !! Claude Desktop laeuft bereits.")
                print("  Damit PBP als MCP-Server erkannt wird, muss Claude")
                print("  neu gestartet werden.")
                print()
                answer = input("  Claude jetzt neu starten? [J/n]: ").strip().lower()
                if answer in ("", "j", "ja", "y", "yes"):
                    logger.info("Claude Desktop wird neu gestartet...")
                    subprocess.run(
                        ["taskkill", "/IM", "Claude.exe", "/F"],
                        capture_output=True, timeout=5,
                        creationflags=0x08000000,
                    )
                    import time
                    time.sleep(2)
                    for cp in [
                        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Claude", "Claude.exe"),
                        os.path.join(os.environ.get("PROGRAMFILES", ""), "Claude", "Claude.exe"),
                    ]:
                        if cp and os.path.isfile(cp):
                            subprocess.Popen([cp], start_new_session=True, creationflags=0x00000008)
                            print("  Claude Desktop wird gestartet...")
                            time.sleep(3)
                            break
        except Exception as e:
            logger.warning("Claude-Check fehlgeschlagen: %s", e)
    elif sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["pgrep", "-x", "Claude"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                print()
                print("  !! Claude Desktop laeuft bereits.")
                print("  Damit PBP als MCP-Server erkannt wird, muss Claude")
                print("  neu gestartet werden.")
                print()
                answer = input("  Claude jetzt neu starten? [J/n]: ").strip().lower()
                if answer in ("", "j", "ja", "y", "yes"):
                    logger.info("Claude Desktop wird neu gestartet...")
                    subprocess.run(["pkill", "-x", "Claude"], capture_output=True, timeout=5)
                    import time
                    time.sleep(2)
                    claude_app = "/Applications/Claude.app"
                    if os.path.isdir(claude_app):
                        subprocess.Popen(["open", claude_app], start_new_session=True)
                        print("  Claude Desktop wird gestartet...")
                        time.sleep(3)
        except Exception as e:
            logger.warning("Claude-Check fehlgeschlagen: %s", e)

    print()
    print(f"  Dashboard: http://localhost:{port}")
    print(f"  Daten:     {data_dir}")
    print(f"  Log:       {log_path}")
    quit_hint = "Strg+C" if sys.platform != "darwin" else "Ctrl+C oder Cmd+Q"
    print(f"  Beenden:   Dieses Fenster schliessen oder {quit_hint}")
    print()

    _open_in_chrome(f"http://localhost:{port}")

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
