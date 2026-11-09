"""#1317: Startet PBP Ollama, oeffnen dessen Hilfsprozesse keine sichtbaren Konsolenfenster.

Ursache war `DETACHED_PROCESS`: Ollama hatte gar keine Konsole, und Windows gab jedem Konsolenprogramm, das Ollama
startete (Grafikkarten-Erkennung, Modell-Runner), ein neues, sichtbares Fenster. Mit `CREATE_NO_WINDOW` bekommt Ollama
eine versteckte Konsole, die seine Kinder erben.

Gegenprobe von Hand am 08.11.2026 (nicht in der Suite, weil sie ein Fenster aufblitzen laesst): mit
DETACHED_PROCESS meldet das Kind `IsWindowVisible = True`, mit den neuen Schaltern kein Fenster.

Die Windows-Proben bauen das mit Python nach (ein Elternprozess mit den Schaltern von PBP startet ein Konsolen-Kind ohne
besondere Schalter, wie Ollama es tut) und fassen Ollama selbst nie an.
"""
from __future__ import annotations

import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from bewerbungs_assistent.services import ollama_start

SRC = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200

nur_windows = pytest.mark.skipif(sys.platform != "win32", reason="Konsolenfenster gibt es nur unter Windows")


def test_die_schalter_geben_ollama_eine_versteckte_konsole():
    flags = ollama_start._WIN_LOSGELOEST
    assert flags & CREATE_NO_WINDOW
    assert flags & CREATE_NEW_PROCESS_GROUP
    # Beide schliessen sich aus: mit DETACHED_PROCESS wird CREATE_NO_WINDOW ignoriert.
    assert not flags & DETACHED_PROCESS


def _skripte(tmp_path: Path) -> tuple[Path, Path]:
    kind = tmp_path / "kind.py"
    kind.write_bytes(textwrap.dedent("""
        import ctypes, sys
        k = ctypes.windll.kernel32; u = ctypes.windll.user32
        h = k.GetConsoleWindow()
        open(sys.argv[1], "w").write("sichtbar" if (h and u.IsWindowVisible(h)) else "unsichtbar")
    """).encode())
    eltern = tmp_path / "eltern.py"
    # Wie `ollama serve`: startet ein Konsolenprogramm ohne eigene Schalter (Go exec ohne HideWindow).
    eltern.write_bytes(b"import subprocess, sys\nsubprocess.run([sys.executable, sys.argv[1], sys.argv[2]])\n")
    return kind, eltern


def _python() -> str:
    return sys.executable.replace("pythonw.exe", "python.exe")


@nur_windows
def test_ein_hilfsprozess_von_ollama_bekommt_kein_sichtbares_fenster(tmp_path):
    kind, eltern = _skripte(tmp_path)
    aus = tmp_path / "ergebnis.txt"
    p = subprocess.Popen([_python(), str(eltern), str(kind), str(aus)], creationflags=ollama_start._WIN_LOSGELOEST,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert p.wait(60) == 0
    assert aus.read_text() == "unsichtbar"


@nur_windows
def test_ollama_laeuft_weiter_wenn_der_startende_prozess_endet(tmp_path):
    """Endet PBP, bleibt Ollama: ein so gestarteter Prozess ueberlebt seinen Starter."""
    pid_datei = tmp_path / "pid.txt"
    starter = tmp_path / "starter.py"
    starter.write_bytes(textwrap.dedent(f"""
        import subprocess, sys
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                             creationflags={ollama_start._WIN_LOSGELOEST},
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        open(sys.argv[1], "w").write(str(p.pid))
    """).encode())
    s = subprocess.Popen([_python(), str(starter), str(pid_datei)], creationflags=CREATE_NO_WINDOW,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert s.wait(60) == 0
    pid = int(pid_datei.read_text())
    try:
        time.sleep(1)
        liste = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True,
                               creationflags=CREATE_NO_WINDOW, timeout=15).stdout.decode("ascii", "replace")
        assert str(pid) in liste, "der Prozess ist mit seinem Starter verschwunden"
    finally:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, creationflags=CREATE_NO_WINDOW,
                       timeout=15)


# Wo DETACHED_PROCESS bewusst bleibt: Claude Desktop ist ein Fensterprogramm (keine Konsolen-Kinder), und das
# Fenster des Deinstallers SOLL sichtbar sein.
_AUSNAHMEN = {"services/claude_neustart.py", "services/deinstallation.py"}


def test_waechter_kein_detached_process_ausserhalb_der_ausnahmen():
    funde = []
    for datei in SRC.rglob("*.py"):
        rel = datei.relative_to(SRC).as_posix()
        text = datei.read_text(encoding="utf-8")
        if re.search(r"DETACHED_PROCESS\s*=|0x0{0,7}8\s*\|", text) and rel not in _AUSNAHMEN:
            funde.append(rel)
    assert not funde, f"DETACHED_PROCESS laesst Konsolen-Kinder sichtbare Fenster oeffnen (#1317): {funde}"


def test_waechter_kennt_seine_ausnahmen_noch():
    for rel in _AUSNAHMEN:
        assert (SRC / rel).is_file(), rel
