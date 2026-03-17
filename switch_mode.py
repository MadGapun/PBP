"""Umschalten zwischen Dev- und Offizieller Version in Claude Desktop.

Aendert die MCP-Konfiguration in claude_desktop_config.json:
  - Dev:       Quellcode aus dem Projektordner, .venv-Python
  - Offiziell: Installierte Version in AppData, embedded Python

Nutzung:
  python switch_mode.py          # Zeigt aktuellen Modus
  python switch_mode.py dev      # Wechselt auf Dev-Version
  python switch_mode.py official # Wechselt auf offizielle Version
"""

import json
import os
import sys

# ── Pfade ──────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.environ["APPDATA"], "Claude", "claude_desktop_config.json")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

MODES = {
    "dev": {
        "python": os.path.join(PROJECT_DIR, ".venv", "Scripts", "python.exe"),
        "src": os.path.join(PROJECT_DIR, "src"),
        "data_dir": os.path.join(os.environ["LOCALAPPDATA"], "BewerbungsAssistent"),
        "label": "Dev",
    },
    "official": {
        "python": os.path.join(os.environ["LOCALAPPDATA"], "BewerbungsAssistent", "python", "python.exe"),
        "src": os.path.join(os.environ["LOCALAPPDATA"], "BewerbungsAssistent", "src"),
        "data_dir": os.path.join(os.environ["LOCALAPPDATA"], "BewerbungsAssistent"),
        "label": "Offiziell",
    },
}

MCP_KEY = "bewerbungs-assistent"


# ── Hilfsfunktionen ───────────────────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"mcpServers": {}}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def detect_current_mode(config):
    """Erkennt den aktuellen Modus anhand des PYTHONPATH."""
    entry = config.get("mcpServers", {}).get(MCP_KEY, {})
    pythonpath = entry.get("env", {}).get("PYTHONPATH", "")

    if os.path.normcase(pythonpath) == os.path.normcase(MODES["dev"]["src"]):
        return "dev"
    elif os.path.normcase(pythonpath) == os.path.normcase(MODES["official"]["src"]):
        return "official"
    return None


def get_version(src_dir):
    """Liest __version__ aus dem Quellcode."""
    init = os.path.join(src_dir, "bewerbungs_assistent", "__init__.py")
    if not os.path.exists(init):
        return "?"
    with open(init, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "?"


def switch_to(mode_name):
    mode = MODES[mode_name]

    # Pruefen ob Python existiert
    if not os.path.exists(mode["python"]):
        print(f"FEHLER: Python nicht gefunden: {mode['python']}")
        sys.exit(1)

    # Pruefen ob Quellcode existiert
    pkg_dir = os.path.join(mode["src"], "bewerbungs_assistent")
    if not os.path.isdir(pkg_dir):
        print(f"FEHLER: Quellcode nicht gefunden: {pkg_dir}")
        sys.exit(1)

    config = load_config()

    config.setdefault("mcpServers", {})[MCP_KEY] = {
        "command": mode["python"],
        "args": ["-m", "bewerbungs_assistent"],
        "env": {
            "BA_DATA_DIR": mode["data_dir"],
            "PYTHONPATH": mode["src"],
        },
    }

    save_config(config)

    version = get_version(mode["src"])
    print(f"Umgeschaltet auf: {mode['label']} (v{version})")
    print(f"  Python:    {mode['python']}")
    print(f"  Quellcode: {mode['src']}")
    print(f"  Daten:     {mode['data_dir']}")
    print()
    print("Claude Desktop muss neu gestartet werden, damit die Aenderung wirkt.")


def show_status():
    config = load_config()
    current = detect_current_mode(config)

    print("=== Bewerbungs-Assistent: Modus-Status ===\n")

    if current:
        mode = MODES[current]
        version = get_version(mode["src"])
        print(f"  Aktiver Modus: {mode['label']} (v{version})")
    else:
        entry = config.get("mcpServers", {}).get(MCP_KEY, {})
        pythonpath = entry.get("env", {}).get("PYTHONPATH", "(nicht konfiguriert)")
        print(f"  Aktiver Modus: Unbekannt")
        print(f"  PYTHONPATH:    {pythonpath}")

    print()
    for name, mode in MODES.items():
        version = get_version(mode["src"])
        exists = os.path.exists(mode["python"]) and os.path.isdir(
            os.path.join(mode["src"], "bewerbungs_assistent")
        )
        marker = " <-- aktiv" if name == current else ""
        status = "OK" if exists else "FEHLT"
        print(f"  [{name:9s}] v{version:8s}  ({status}){marker}")
        print(f"              Python: {mode['python']}")
        print(f"              Source: {mode['src']}")
        print()

    print("Nutzung: python switch_mode.py [dev|official]")


# ── Main ───────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_status()
    elif sys.argv[1] in ("dev", "official"):
        switch_to(sys.argv[1])
    else:
        print(f"Unbekannter Modus: {sys.argv[1]}")
        print("Nutzung: python switch_mode.py [dev|official]")
        sys.exit(1)
