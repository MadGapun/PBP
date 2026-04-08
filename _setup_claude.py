"""Konfiguriert Claude Desktop fuer den Bewerbungs-Assistenten.

Plattformunabhaengig: Windows, macOS und Linux.
Erkennt automatisch ob aus Repo (.venv) oder offiziellem Installationspfad
gestartet wird und setzt die Pfade entsprechend.
"""
import json, os, sys


def get_claude_config_paths():
    """Gibt alle Claude Desktop Config-Pfade fuer die aktuelle Plattform zurueck.

    #361: Windows Store installiert Claude in einem Packages-Unterordner.
    Wir geben alle gefundenen Pfade zurueck, damit beide Varianten bedient werden.
    """
    paths = []
    if sys.platform == "win32":
        # Standard-Pfad (Direktdownload von claude.ai)
        std_path = os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude_desktop_config.json")
        paths.append(std_path)
        # Windows Store Pfad (#361)
        local_app = os.environ.get("LOCALAPPDATA", "")
        packages_dir = os.path.join(local_app, "Packages")
        if os.path.isdir(packages_dir):
            import glob
            for pkg in glob.glob(os.path.join(packages_dir, "Claude_*")):
                store_path = os.path.join(pkg, "LocalCache", "Roaming", "Claude", "claude_desktop_config.json")
                store_dir = os.path.dirname(store_path)
                # Nur hinzufuegen wenn das Verzeichnis existiert (Store-Version installiert)
                if os.path.isdir(store_dir) or os.path.exists(store_path):
                    paths.append(store_path)
    elif sys.platform == "darwin":
        paths.append(os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Claude", "claude_desktop_config.json"))
    else:
        paths.append(os.path.join(os.path.expanduser("~"), ".config", "Claude", "claude_desktop_config.json"))
    return paths


def get_claude_config_path():
    """Gibt den primaeren Claude Desktop Config-Pfad zurueck (Kompatibilitaet)."""
    return get_claude_config_paths()[0]


def get_data_dir():
    """Gibt das Datenverzeichnis fuer die aktuelle Plattform zurueck.

    v1.5.0: Klare Trennung — App-Code in app/, Benutzerdaten in data/ (#297).
    """
    if sys.platform == "win32":
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "BewerbungsAssistent", "data")
    else:
        return os.path.join(os.path.expanduser("~"), ".bewerbungs-assistent")


def get_app_dir():
    """Gibt das App-Verzeichnis (python + src) fuer die aktuelle Plattform zurueck (#297)."""
    if sys.platform == "win32":
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "BewerbungsAssistent", "app")
    else:
        return os.path.join(os.path.expanduser("~"), ".bewerbungs-assistent")


def detect_mode(project_dir):
    """Erkennt den Installations-Modus und findet den richtigen Python-Pfad.

    Prueft in dieser Reihenfolge:
    1. .venv im Projektordner (Dev-Modus, macOS/Linux/Windows mit venv)
    2. AppData app/ Verzeichnis (Official v1.5+, #297 — bevorzugt)
    3. AppData flach (Official v1.4.x Legacy — Rueckwaertskompatibilitaet)
    4. python/ im Projektordner (Fallback, z.B. aus Downloads)

    Returns (mode, python_exe, src_dir, data_dir)
    """
    data_dir = get_data_dir()
    app_dir = get_app_dir()
    src_dir_local = os.path.join(project_dir, "src")

    # 1. Dev-Modus: .venv existiert im Projektordner
    if sys.platform == "win32":
        venv_python = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(project_dir, ".venv", "bin", "python")

    if os.path.exists(venv_python):
        return "dev", venv_python, src_dir_local, data_dir

    # 2. Official v1.5+ Modus: Python in app/ Unterverzeichnis (#297)
    if sys.platform == "win32":
        for appdata_python in [
            os.path.join(app_dir, "python", "Scripts", "python.exe"),
            os.path.join(app_dir, "python", "python.exe"),
        ]:
            if os.path.exists(appdata_python):
                src_dir_appdata = os.path.join(app_dir, "src")
                return "official", appdata_python, src_dir_appdata, data_dir
    else:
        official_python = os.path.join(app_dir, "venv", "bin", "python")
        if os.path.exists(official_python):
            src_dir_appdata = os.path.join(app_dir, "src")
            return "official", official_python, src_dir_appdata, data_dir

    # 3. Legacy v1.4.x Modus: Python flach in BewerbungsAssistent/ (Rueckwaertskompatibel)
    legacy_base = os.path.dirname(data_dir) if sys.platform == "win32" else data_dir
    if sys.platform == "win32":
        for legacy_python in [
            os.path.join(legacy_base, "python", "Scripts", "python.exe"),
            os.path.join(legacy_base, "python", "python.exe"),
        ]:
            if os.path.exists(legacy_python):
                src_dir_legacy = os.path.join(legacy_base, "src")
                # Legacy data_dir = legacy_base (flache Struktur)
                return "legacy", legacy_python, src_dir_legacy, legacy_base

    # 4. Fallback: Python im Projektordner (Windows Embeddable aus Downloads)
    if sys.platform == "win32":
        for local_python in [
            os.path.join(project_dir, "python", "Scripts", "python.exe"),
            os.path.join(project_dir, "python", "python.exe"),
        ]:
            if os.path.exists(local_python):
                return "local", local_python, src_dir_local, data_dir

    # 5. Nichts gefunden — Official-Pfad als Platzhalter (wird Warnung auslösen)
    if sys.platform == "win32":
        fallback_python = os.path.join(app_dir, "python", "python.exe")
    else:
        fallback_python = os.path.join(app_dir, "venv", "bin", "python")
    src_dir_fallback = os.path.join(app_dir, "src")
    return "official", fallback_python, src_dir_fallback, data_dir


# Projektverzeichnis = wo dieses Script liegt
project_dir = os.path.dirname(os.path.abspath(__file__))
config_paths = get_claude_config_paths()
config_path = config_paths[0]  # Primaerer Pfad
mode, python_exe, src_dir, data_dir = detect_mode(project_dir)

print(f"[CLAUDE] Plattform: {sys.platform}")
print(f"[CLAUDE] Modus:   {mode}")
print(f"[CLAUDE] Projekt: {project_dir}")
print(f"[CLAUDE] Config:  {config_paths}")
print(f"[CLAUDE] Python:  {python_exe}")
print(f"[CLAUDE] Source:  {src_dir}")
print(f"[CLAUDE] Daten:   {data_dir}")

if not os.path.exists(python_exe):
    print(f"[CLAUDE] WARNUNG: Python nicht gefunden unter {python_exe}")
    if mode == "official":
        print(f"[CLAUDE] Tipp: Fuehre zuerst den Installer aus oder nutze den Dev-Modus (.venv)")

# MCP Server eintragen
mcp_entry = {
    "command": python_exe,
    "args": ["-m", "bewerbungs_assistent"],
    "env": {
        "BA_DATA_DIR": data_dir,
    }
}

# PYTHONPATH immer setzen — stellt sicher dass bewerbungs_assistent gefunden wird
mcp_entry["env"]["PYTHONPATH"] = src_dir

# #361: Config in alle erkannten Pfade schreiben (Standard + ggf. Windows Store)
written = 0
for cp in config_paths:
    config = {"mcpServers": {}}
    if os.path.exists(cp):
        try:
            with open(cp, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "mcpServers" not in config:
                config["mcpServers"] = {}
            existing = list(config["mcpServers"].keys())
            print(f"[CLAUDE] {cp}: Bestehende MCP-Server: {existing}")
        except Exception as e:
            print(f"[CLAUDE] {cp}: Config-Fehler (wird neu erstellt): {e}")
    else:
        print(f"[CLAUDE] {cp}: Keine bestehende Config, erstelle neue")

    config["mcpServers"]["bewerbungs-assistent"] = mcp_entry

    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"[CLAUDE] Config geschrieben: {cp}")
    written += 1

print(f"[CLAUDE] {written} Config-Datei(en) geschrieben ({mode}-Modus)")
print("OK")
