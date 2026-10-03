"""Konfiguriert Claude Desktop fuer den Bewerbungs-Assistenten.

Plattformunabhaengig: Windows, macOS und Linux.
Erkennt automatisch ob aus Repo (.venv) oder offiziellem Installationspfad
gestartet wird und setzt die Pfade entsprechend.
"""
import json, os, shutil, sys, time


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


def lese_config(pfad):
    """Liest die Claude-Konfiguration: (config, problem).

    ``config`` ist None, wenn die Datei nicht lesbar ist. BOM-fest
    (``utf-8-sig``): Windows PowerShell 5.1 schreibt UTF-8 mit BOM, der
    Deinstaller tat das bis v1.7.144. Mit ``utf-8`` galt so eine Datei als
    defekt und wurde samt allen anderen MCP-Servern ueberschrieben.
    """
    try:
        with open(pfad, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
    except Exception as e:  # noqa: BLE001 - jeder Lesefehler zaehlt gleich
        return None, str(e)
    if not isinstance(config, dict):
        return None, "oberste Ebene ist kein JSON-Objekt"
    if not isinstance(config.get("mcpServers", {}), dict):
        return None, "mcpServers ist kein JSON-Objekt"
    return config, ""


def sichere_kopie(pfad):
    """Legt neben die Datei eine Kopie ab; gibt deren Pfad zurueck, sonst None."""
    ziel = f"{pfad}.pbp-defekt-{time.strftime('%Y%m%d-%H%M%S')}"
    try:
        shutil.copy2(pfad, ziel)
        return ziel
    except OSError:
        return None


def eintrag_bauen(python_exe, src_dir, data_dir, alter_eintrag=None):
    """Der PBP-Eintrag fuer ``mcpServers``.

    v1.7.145: Eigene Einstellungen des bisherigen Eintrags bleiben erhalten
    (``BA_DATA_DIR`` fuer einen verlegten Datenordner, ``BA_DASHBOARD_PORT``,
    weitere). Vorher baute jeder Installerlauf den Eintrag neu, und wer seine
    Daten wie im Wiki beschrieben verlegt hatte, startete nach dem Update mit
    leerem Profil. Nur ``PYTHONPATH`` folgt immer der Installation.
    """
    env = {}
    if isinstance(alter_eintrag, dict) and isinstance(alter_eintrag.get("env"), dict):
        env.update(alter_eintrag["env"])
    env.setdefault("BA_DATA_DIR", data_dir)
    env["PYTHONPATH"] = src_dir
    return {"command": python_exe, "args": ["-m", "bewerbungs_assistent"], "env": env}


def config_schreiben(cp, python_exe, src_dir, data_dir):
    """Traegt PBP in EINE Claude-Konfiguration ein. True = geschrieben.

    Ist die vorhandene Datei nicht lesbar, wird sie NIE einfach ueberschrieben:
    erst eine Kopie daneben, und gelingt die nicht, bleibt die Datei unberuehrt.
    """
    config = {"mcpServers": {}}
    if os.path.exists(cp):
        gelesen, problem = lese_config(cp)
        if gelesen is None:
            kopie = sichere_kopie(cp)
            if kopie is None:
                print(f"[CLAUDE] {cp}: Config nicht lesbar ({problem}) und keine Kopie moeglich - nichts geschrieben")
                return False
            print(f"[CLAUDE] {cp}: Config nicht lesbar ({problem}); Kopie gesichert: {kopie}")
        else:
            config = gelesen
            config.setdefault("mcpServers", {})
            print(f"[CLAUDE] {cp}: Bestehende MCP-Server: {list(config['mcpServers'].keys())}")
    else:
        print(f"[CLAUDE] {cp}: Keine bestehende Config, erstelle neue")

    alter = config["mcpServers"].get("bewerbungs-assistent")
    eintrag = eintrag_bauen(python_exe, src_dir, data_dir, alter)
    if isinstance(alter, dict) and isinstance(alter.get("env"), dict):
        geerbt = sorted(k for k in alter["env"] if k != "PYTHONPATH")
        if geerbt:
            print(f"[CLAUDE] {cp}: Eigene Einstellungen bleiben erhalten: {', '.join(geerbt)}")
        if eintrag["env"].get("BA_DATA_DIR") != data_dir:
            print(f"[CLAUDE] {cp}: Datenordner bleibt: {eintrag['env']['BA_DATA_DIR']}")
    config["mcpServers"]["bewerbungs-assistent"] = eintrag

    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp, "w", encoding="utf-8") as f:  # ohne BOM
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"[CLAUDE] Config geschrieben: {cp}")
    return True


def _ausgabe_absichern():
    """Die Ausgabe nennt Pfade, und die tragen den Benutzernamen. Geht sie in eine Datei (Installer-Protokoll), gilt die Zeichentabelle
    des Rechners; ein Zeichen ausserhalb davon (ł, ş, griechisch) darf das Drucken nicht zum Absturz bringen (L44)."""
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(errors="backslashreplace")
        except Exception:
            pass


def main():
    _ausgabe_absichern()
    # Projektverzeichnis = wo dieses Script liegt
    project_dir = os.path.dirname(os.path.abspath(__file__))
    config_paths = get_claude_config_paths()
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
            print("[CLAUDE] Tipp: Fuehre zuerst den Installer aus oder nutze den Dev-Modus (.venv)")

    # #361: Config in alle erkannten Pfade schreiben (Standard + ggf. Windows Store)
    written = 0
    for cp in config_paths:
        if config_schreiben(cp, python_exe, src_dir, data_dir):
            written += 1

    print(f"[CLAUDE] {written} Config-Datei(en) geschrieben ({mode}-Modus)")
    if written == 0:
        print("[CLAUDE] FEHLER: Keine Konfiguration geschrieben - Claude Desktop kennt PBP noch nicht.")
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
