"""Schnelltest: Kann der Bewerbungs-Assistent importiert werden?"""
import sys, os, tempfile, shutil, threading
import faulthandler  # VOR dem Waechter: ein Import im Waechter wartet auf die Import-Sperre, die ein Haenger im Import haelt

# Die Ausgabe nennt den Programmpfad. Enthaelt der ein Zeichen, das die Zeichentabelle des Rechners nicht kennt (Benutzername
# mit »ł«, »ş«, griechischen oder kyrillischen Buchstaben), darf das Drucken den Test nicht zum Absturz bringen.
for _strom in (sys.stdout, sys.stderr):
    try:
        _strom.reconfigure(errors="backslashreplace")
    except Exception:
        pass

# #1281: der Selbsttest muss von selbst enden. Beim Update von 1.8.0-rc.4 auf 1.8.0 lief er auf einem Rechner in die Zeitgrenze des
# Aufrufers (240 s), obwohl er allein in 4 s fertig war; die Ausgabe ging dabei verloren. Dieser Waechter bricht nach 200 s selbst ab,
# schreibt die Staende ALLER Threads auf die Fehlerausgabe (sie landet im Protokoll des Aufrufers) und beendet den Prozess hart.
# Der Waechter importiert nichts: haengt der Test IM Import, haelt er die Import-Sperre (gemessen: ein Import im Waechter kam erst nach dem Haenger).
SELBSTGRENZE_S = int(os.environ.get("PBP_SELBSTTEST_GRENZE_S") or 200)  # die Variable nur fuer Tests; unter der Zeitgrenze des Aufrufers (240 s), sonst haette sie keine Wirkung


def _selbst_abbrechen():
    try:
        print("[TEST] FEHLER: der Selbsttest endet nicht innerhalb von %d s. Laufende Threads:" % SELBSTGRENZE_S, file=sys.stderr, flush=True)
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(3)


_waechter = threading.Timer(SELBSTGRENZE_S, _selbst_abbrechen)
_waechter.daemon = True
_waechter.start()

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

_code = 0
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
    _code = 1

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
            # Der Helfer erbt sonst den Arbeitsordner des Selbsttests, und das ist der entpackte Ordner der neuen Version: die
            # Installation benennt ihn gleich danach um, und Windows verweigert das, solange ein Prozess dort seinen
            # Arbeitsordner hat (WinError 32). Gemessen: der erste Versuch scheiterte immer.
            subprocess.Popen([sys.executable, "-c", code, d], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True, cwd=tempfile.gettempdir(),
                             creationflags=(0x00000008 | 0x08000000) if sys.platform == "win32" else 0,
                             start_new_session=(sys.platform != "win32"))
        except Exception:
            pass

# #1281: hart beenden. Ein Hintergrund-Thread oder ein atexit-Haken eines importierten Pakets (Update-Pruefung, Planer) darf das Ende nicht
# aufhalten: das Ergebnis steht fest, und der Aufrufer wartet darauf. Vorher die Ausgabe leeren, sonst fehlt das "OK" am Ende.
_waechter.cancel()
try:
    sys.stdout.flush()
    sys.stderr.flush()
except Exception:
    pass
os._exit(_code)
