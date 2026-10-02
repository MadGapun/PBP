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
