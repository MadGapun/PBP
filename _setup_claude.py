"""Konfiguriert Claude Desktop fuer den Bewerbungs-Assistenten.

Plattformunabhaengig: Windows, macOS und Linux.
Erkennt automatisch ob aus Repo (.venv) oder offiziellem Installationspfad
gestartet wird und setzt die Pfade entsprechend.
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


def detect_mode(project_dir):
    """Erkennt den Installations-Modus und findet den richtigen Python-Pfad.

    Prueft in dieser Reihenfolge:
    1. .venv im Projektordner (Dev-Modus, macOS/Linux/Windows mit venv)
    2. python/python.exe im Projektordner (Windows Embeddable-Modus)
    3. Official-Modus (Datenverzeichnis)

    Returns (mode, python_exe, src_dir, data_dir)
    """
    data_dir = get_data_dir()
    src_dir_local = os.path.join(project_dir, "src")

    # 1. Dev-Modus: .venv existiert im Projektordner
    if sys.platform == "win32":
        venv_python = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(project_dir, ".venv", "bin", "python")

    if os.path.exists(venv_python):
        return "dev", venv_python, src_dir_local, data_dir

    # 2. Windows Embeddable Python im Projektordner (INSTALLIEREN.bat)
    if sys.platform == "win32":
        embeddable_python = os.path.join(project_dir, "python", "python.exe")
        if os.path.exists(embeddable_python):
            # Embeddable Python nutzt Scripts/python.exe fuer pip-installierte Module
            scripts_python = os.path.join(project_dir, "python", "Scripts", "python.exe")
            if os.path.exists(scripts_python):
                return "local", scripts_python, src_dir_local, data_dir
            return "local", embeddable_python, src_dir_local, data_dir

    # 3. Official-Modus: Python im Datenverzeichnis
    if sys.platform == "win32":
        official_python = os.path.join(data_dir, "python", "Scripts", "python.exe")
    else:
        official_python = os.path.join(data_dir, "venv", "bin", "python")

    src_dir = os.path.join(data_dir, "src")
    return "official", official_python, src_dir, data_dir


# Projektverzeichnis = wo dieses Script liegt
project_dir = os.path.dirname(os.path.abspath(__file__))
config_path = get_claude_config_path()
mode, python_exe, src_dir, data_dir = detect_mode(project_dir)

print(f"[CLAUDE] Plattform: {sys.platform}")
print(f"[CLAUDE] Modus:   {mode}")
print(f"[CLAUDE] Projekt: {project_dir}")
print(f"[CLAUDE] Config:  {config_path}")
print(f"[CLAUDE] Python:  {python_exe}")
print(f"[CLAUDE] Source:  {src_dir}")
print(f"[CLAUDE] Daten:   {data_dir}")

if not os.path.exists(python_exe):
    print(f"[CLAUDE] WARNUNG: Python nicht gefunden unter {python_exe}")
    if mode == "official":
        print(f"[CLAUDE] Tipp: Fuehre zuerst den Installer aus oder nutze den Dev-Modus (.venv)")

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
mcp_entry = {
    "command": python_exe,
    "args": ["-m", "bewerbungs_assistent"],
    "env": {
        "BA_DATA_DIR": data_dir,
    }
}

# PYTHONPATH setzen wenn lokale src/ verwendet wird (dev + local Modus)
if mode in ("dev", "local"):
    mcp_entry["env"]["PYTHONPATH"] = src_dir

config["mcpServers"]["bewerbungs-assistent"] = mcp_entry

# Config-Verzeichnis erstellen falls noetig
os.makedirs(os.path.dirname(config_path), exist_ok=True)

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print(f"[CLAUDE] Config geschrieben ({mode}-Modus)")
print("OK")
