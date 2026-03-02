"""Konfiguriert Claude Desktop fuer den Bewerbungs-Assistenten."""
import json, os, sys

config_path = os.path.join(os.environ["APPDATA"], "Claude", "claude_desktop_config.json")
data_dir = os.path.join(os.environ["LOCALAPPDATA"], "BewerbungsAssistent")
python_exe = sys.executable
src_dir = os.path.join(os.path.dirname(os.path.dirname(python_exe)), "src")

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
