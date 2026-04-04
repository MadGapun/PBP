"""Konfiguriert Claude Desktop fuer den Bewerbungs-Assistenten.

Plattformunabhaengig: Windows, macOS und Linux.
Verwendet feste Installationspfade, damit Versions-Updates
die MCP-Konfiguration nicht kaputtmachen.
"""
import json, os, sys


def get_claude_config_path():
    """Gibt den Claude Desktop Config-Pfad fuer die aktuelle Plattform zurueck."""
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude_desktop_config.json")
    elif sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Claude", "claude_desktop_config.json")
    else:
        return os.path.join(os.path.expanduser("~"), ".config", "Claude", "claude_desktop_config.json")


def get_data_dir():
    """Gibt das Datenverzeichnis fuer die aktuelle Plattform zurueck."""
    if sys.platform == "win32":
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "BewerbungsAssistent")
    else:
        return os.path.join(os.path.expanduser("~"), ".bewerbungs-assistent")


def get_python_exe(data_dir):
    """Gibt den Python-Pfad im Installationsverzeichnis zurueck."""
    if sys.platform == "win32":
        return os.path.join(data_dir, "python", "Scripts", "python.exe")
    else:
        return os.path.join(data_dir, "venv", "bin", "python")


config_path = get_claude_config_path()
data_dir = get_data_dir()
python_exe = get_python_exe(data_dir)
src_dir = os.path.join(data_dir, "src")

print(f"[CLAUDE] Plattform: {sys.platform}")
print(f"[CLAUDE] Config: {config_path}")
print(f"[CLAUDE] Python: {python_exe}")
print(f"[CLAUDE] Source: {src_dir}")
print(f"[CLAUDE] Daten:  {data_dir}")

# Bestehende Config laden oder neue erstellen
config = {"mcpServers": {}}
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        if "mcpServers" not in config:
            config["mcpServers"] = {}
        existing = list(config["mcpServers"].keys())
        print(f"[CLAUDE] Bestehende MCP-Server: {existing}")
    except Exception as e:
        print(f"[CLAUDE] Config-Fehler (wird neu erstellt): {e}")
else:
    print("[CLAUDE] Keine bestehende Config gefunden, erstelle neue")

# MCP Server eintragen
config["mcpServers"]["bewerbungs-assistent"] = {
    "command": python_exe,
    "args": ["-m", "bewerbungs_assistent"],
    "env": {
        "BA_DATA_DIR": data_dir,
        "PYTHONPATH": src_dir
    }
}

# Config-Verzeichnis erstellen falls noetig
os.makedirs(os.path.dirname(config_path), exist_ok=True)

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("[CLAUDE] Config geschrieben")
print("OK")
