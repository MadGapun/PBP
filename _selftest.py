"""Schnelltest: Kann der Bewerbungs-Assistent importiert werden?"""
import sys, os, tempfile, shutil

# Die Ausgabe nennt den Programmpfad. Enthaelt der ein Zeichen, das die Zeichentabelle des Rechners nicht kennt (Benutzername
# mit »ł«, »ş«, griechischen oder kyrillischen Buchstaben), darf das Drucken den Test nicht zum Absturz bringen.
for _strom in (sys.stdout, sys.stderr):
    try:
        _strom.reconfigure(errors="backslashreplace")
    except Exception:
        pass

# src-Verzeichnis hinzufuegen
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Zusaetzliche Pakete einer Fassung (Auto-Update, #1093) liegen in `site`; sie kommen NACH dem Programm in den Pfad
SITE_DIR = os.path.join(SCRIPT_DIR, "site")
if os.path.isdir(SITE_DIR):
    sys.path.insert(0, SITE_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, "src"))

# Temporaeres Datenverzeichnis
d = tempfile.mkdtemp()
os.environ["BA_DATA_DIR"] = d

try:
    print(f"[TEST] Python: {sys.version}")
    print(f"[TEST] Pfad: {SCRIPT_DIR}")

    from bewerbungs_assistent.database import Database
    print("[TEST] Import Database: OK")

    from bewerbungs_assistent.dashboard import start_dashboard
    print("[TEST] Import Dashboard: OK")

    from bewerbungs_assistent.server import mcp
    print("[TEST] Import MCP Server: OK")

    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    assert db.get_profile()["name"] == "Test"
    print("[TEST] Datenbank lesen/schreiben: OK")

    db.close()
    print("[TEST] Alle Tests bestanden")
    print("OK")

except Exception as e:
    print(f"[TEST] FEHLER: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

finally:
    shutil.rmtree(d, ignore_errors=True)
    if os.path.isdir(d):
        # PP23 (#1170): das Datenverzeichnis des Selbsttests blieb in %TEMP% liegen (je Lauf rund 0,6 MB): der importierte Server haelt die
        # Datenbank und die Protokolldatei offen, und Windows loescht keine geoeffnete Datei. Ein abgetrennter Helfer raeumt nach.
        try:
            import subprocess
            code = ("import shutil,sys,time\n"
                    "for _ in range(30):\n"
                    "    shutil.rmtree(sys.argv[1], ignore_errors=True)\n"
                    "    import os\n"
                    "    if not os.path.isdir(sys.argv[1]): break\n"
                    "    time.sleep(1)\n")
            subprocess.Popen([sys.executable, "-c", code, d], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True,
                             creationflags=(0x00000008 | 0x08000000) if sys.platform == "win32" else 0,
                             start_new_session=(sys.platform != "win32"))
        except Exception:
            pass
