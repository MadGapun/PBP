"""#1281: der Funktionstest des Auto-Updates endet von selbst, und eine Zeitgrenze verliert die Ausgabe nicht mehr.

Beim Update von rc.4 auf 1.8.0 lief der Test auf einem Rechner in die Zeitgrenze von 240 s, obwohl er allein in 4 s fertig war. Die Ursache
ist nicht gefunden (er haengt nur, wenn ihn das laufende Dashboard startet). Gebaut ist, was dann hilft: der Test beendet sich hart, hat einen
eigenen Waechter mit Thread-Staenden, der Aufrufer wartet nicht auf Pipes und protokolliert das Teilstueck der Ausgabe.
"""
import subprocess
import sys
import time
from pathlib import Path

import pytest

from bewerbungs_assistent.services.auto_update import installation
from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler, TEXTE

WURZEL = Path(__file__).resolve().parent.parent
KEIN_FENSTER = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _skript(ordner: Path, code: str) -> None:
    (ordner / "_selftest.py").write_text(code, encoding="utf-8")


# ----------------------------------------------------------- der Aufrufer

def test_der_aufrufer_liefert_die_ausgabe_wie_subprocess_run(tmp_path):
    _skript(tmp_path, "import sys\nprint('hallo')\nprint('OK')\nsys.stderr.write('log\\n')\n")
    r = installation._selbsttest_lauf([sys.executable, str(tmp_path / "_selftest.py")], timeout=30,
                                      env=None, cwd=str(tmp_path), creationflags=KEIN_FENSTER)
    assert r.returncode == 0
    assert r.stdout.strip().splitlines()[-1] == "OK"
    assert "log" in r.stderr


def test_die_zeitgrenze_nennt_die_ausgabe_bis_dahin(tmp_path, monkeypatch):
    _skript(tmp_path, "import sys, time\nprint('bis-hierher', flush=True)\nsys.stderr.write('thread-stand\\n')\nsys.stderr.flush()\ntime.sleep(60)\n")
    monkeypatch.setattr(installation, "SELBSTTEST_TIMEOUT_S", 3)
    with pytest.raises(UpdateFehler) as e:
        installation.selbsttest_starten(tmp_path)
    assert e.value.code == "selbsttest"
    assert e.value.detail.startswith("Zeitgrenze")
    assert "bis-hierher" in e.value.detail and "thread-stand" in e.value.detail


def test_ein_enkelprozess_haelt_den_aufrufer_nicht_fest(tmp_path):
    """Gegenprobe zur Pipe-Eigenschaft: ein Prozess, der ein Ausgabe-Ende erbt und weiterlaeuft, hielt `subprocess.run(capture_output=True)`
    bis zu seinem Ende fest. Ohne Pipes kehrt der Aufrufer sofort zurueck, sobald der Selbsttest selbst fertig ist."""
    pid_datei = tmp_path / "enkel.pid"
    _skript(tmp_path, (
        "import subprocess, sys\n"
        "kind = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(25)'], creationflags=%d, close_fds=False)\n"
        "open(r'%s', 'w').write(str(kind.pid))\n"
        "print('OK')\n" % (KEIN_FENSTER, pid_datei)))
    t0 = time.monotonic()
    try:
        installation.selbsttest_starten(tmp_path)  # der echte Weg: wirft, wenn der Test nicht mit "OK" endet
        dauer = time.monotonic() - t0
    finally:
        if pid_datei.exists():
            _beenden(int(pid_datei.read_text()))
    assert dauer < 15, f"der Aufrufer wartete {dauer:.0f} s auf den Enkelprozess"


def _beenden(pid: int) -> None:
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=KEIN_FENSTER)
        else:
            import os
            import signal
            os.kill(pid, signal.SIGKILL)
    except Exception:
        pass


# ----------------------------------------------------------- das Skript selbst

def _selbsttest_mit(tmp_path, sitecustomize: str, **umgebung):
    import os
    (tmp_path / "sitecustomize.py").write_text(sitecustomize, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("BA_DATA_DIR", "PBP_APP_DIR", "PBP_FASSUNG", "PYTHONPATH")}
    env.update({"PYTHONPATH": str(tmp_path), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    env.update(umgebung)
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, str(WURZEL / "_selftest.py")], capture_output=True, encoding="utf-8", errors="replace",
                       timeout=120, env=env, cwd=str(WURZEL), creationflags=KEIN_FENSTER)
    return r, time.monotonic() - t0


def test_ein_hintergrund_thread_haelt_das_ende_nicht_auf(tmp_path):
    """Ein nicht-daemon Thread eines importierten Pakets liess den Prozess vor dem Ende warten; jetzt beendet sich der Selbsttest hart."""
    r, dauer = _selbsttest_mit(tmp_path, "import threading, time\nthreading.Thread(target=lambda: time.sleep(90)).start()\n")
    assert r.returncode == 0, r.stderr[-600:]
    assert r.stdout.strip().splitlines()[-1] == "OK"
    assert dauer < 75, f"der Selbsttest endete erst nach {dauer:.0f} s"


def test_der_waechter_bricht_ab_und_nennt_die_threads(tmp_path):
    hang = ("import sys, time\n"
            "class _Haenger:\n"
            "    def find_spec(self, name, pfad=None, ziel=None):\n"
            "        if name == 'bewerbungs_assistent.database':\n"
            "            time.sleep(90)\n"
            "sys.meta_path.insert(0, _Haenger())\n")
    r, dauer = _selbsttest_mit(tmp_path, hang, PBP_SELBSTTEST_GRENZE_S="3")
    assert r.returncode == 3, (r.returncode, r.stderr[-600:])
    assert "endet nicht innerhalb von 3 s" in r.stderr
    assert "Thread" in r.stderr and "_selftest.py" in r.stderr  # Thread-Staende mit dem Ort des Haengers
    assert dauer < 60


def test_ein_echter_fehler_bleibt_ein_fehlschlag(tmp_path):
    kaputt = ("import sys\n"
              "class _Kaputt:\n"
              "    def find_spec(self, name, pfad=None, ziel=None):\n"
              "        if name == 'bewerbungs_assistent.database':\n"
              "            raise ImportError('Absicht')\n"
              "sys.meta_path.insert(0, _Kaputt())\n")
    r, _ = _selbsttest_mit(tmp_path, kaputt)
    assert r.returncode == 1
    assert "OK" not in r.stdout.strip().splitlines()[-1:]
    assert "Absicht" in r.stdout + r.stderr


# ----------------------------------------------------------- der Text fuer Menschen

def test_die_meldung_nennt_den_weg_von_hand():
    text = TEXTE["selbsttest"]
    assert "Es wurde nichts installiert" in text
    assert "INSTALLIEREN" in text and "Daten bleiben erhalten" in text
