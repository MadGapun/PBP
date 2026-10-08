"""Konsolenausgaben werden nie mit der falschen Kodierung gelesen (#1182, I26).

Fund (08.10.2026, Bildschirmfoto des Nutzers): Im Fenster „PBP Bewerbungs-Portal“ stand beim Start nach den Zeilen „Dashboard / Daten / Log /
Beenden“ ein Python-Fehler: `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 74` im Lese-Thread von `subprocess`.

Ursache: `claude_neustart.claude_laeuft` las die Ausgabe von `tasklist` im Textmodus (cp1252). Läuft Claude Desktop nicht, antwortet Windows
deutsch „… Kriterien ausgeführt.“; das „ü“ schreibt die Konsole als OEM-Byte 0x81 (cp850), das in cp1252 nicht definiert ist. Der Lese-Thread bricht
ab, `stdout` ist `None`, und die Prüfung stimmt nur zufällig. Dieselbe Klasse steckt in den PowerShell-Aufrufen (`ollama_start`).

Die Tests nehmen KEIN echtes `tasklist`: ein Kindprozess schreibt genau die Bytes, die Windows schreibt, und läuft mit den Optionen, die der
Aufrufer wählt. So schlägt der Test vorher auf jedem Betriebssystem an (unter Windows im Lese-Thread, sonst als Ausnahme im Aufruf) und ist von
der Sprache des Rechners unabhängig. Alle Namen und Pfade sind erfunden.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import claude_neustart as cn  # noqa: E402
from bewerbungs_assistent.services import konsole  # noqa: E402

# So meldet tasklist auf einem deutschen Windows „kein Claude“: das ü steht als OEM-Byte 0x81 (cp850), nicht als cp1252 oder UTF-8 (Stelle 74).
KEIN_CLAUDE = b"INFORMATION: Es werden keine Aufgaben mit den angegebenen Kriterien ausgef\x81hrt.\r\n"
MIT_CLAUDE = (b"Claude.exe                    1234 Console                    1    204.812 K\r\n"
              b"Claude.exe                    5678 Console                    1     51.200 K\r\n")


def _kind(ausgabe: bytes):
    """Ein `run`, das statt `tasklist` einen echten Kindprozess startet, der genau diese Bytes schreibt, mit den Optionen des Aufrufers."""
    code = "import sys; sys.stdout.buffer.write(%r); sys.stdout.buffer.flush()" % (ausgabe,)

    def run(befehl, **kw):
        kw.pop("creationflags", None)       # CREATE_NO_WINDOW gibt es nur unter Windows
        return subprocess.run([sys.executable, "-c", code], **kw)
    return run


@pytest.fixture
def lese_thread_fehler(monkeypatch):
    """Sammelt Ausnahmen aus Hintergrund-Threads — so druckt Python den Traceback ins Fenster des Nutzers."""
    gesammelt: list = []
    monkeypatch.setattr(threading, "excepthook", lambda args: gesammelt.append(args.exc_value))
    return gesammelt


# ── der Fall des Nutzers ────────────────────────────────────────────────────────────────────────────────────

def test_1182_ohne_laufendes_claude_kein_abbruch_und_kein_fehler_im_fenster(lese_thread_fehler):
    assert cn.claude_laeuft("win32", run=_kind(KEIN_CLAUDE)) is False
    assert lese_thread_fehler == [], f"der Lese-Thread brach ab (so entsteht der Traceback im Fenster): {lese_thread_fehler}"


def test_1182_der_ganze_start_ohne_claude_bleibt_still(lese_thread_fehler):
    """Die Frage „Claude neu starten?“ kommt nicht, nichts wird beendet, nichts steht im Fenster."""
    fragen, ausgaben, starts = [], [], []
    ergebnis = cn.neustart_anbieten(
        "win32", frage=lambda t: fragen.append(t) or "", ausgabe=lambda *t: ausgaben.append(t), run=_kind(KEIN_CLAUDE),
        start=lambda *a, **k: starts.append(a), pause=lambda s: None, umgebung={}, ist_datei=lambda p: False, ist_ordner=lambda p: False)
    assert ergebnis == "laeuft_nicht"
    assert fragen == [] and ausgaben == [] and starts == []
    assert lese_thread_fehler == []


def test_1182_laeuft_claude_wird_es_auch_mit_nicht_ascii_in_der_ausgabe_erkannt(lese_thread_fehler):
    ausgabe = MIT_CLAUDE + b"Sp\x81ter.exe                    99 Console                    1     10 K\r\n"
    assert cn.claude_laeuft("win32", run=_kind(ausgabe)) is True
    assert lese_thread_fehler == []


@pytest.mark.parametrize("zeile", [b"claude.exe 1234 Console", b"CLAUDE.EXE 1234 Console", b"Claude.exe 1234 Console"])
def test_1182_gross_und_kleinschreibung_des_prozessnamens_zaehlt_weiter_nicht(zeile):
    assert cn.claude_laeuft("win32", run=_kind(zeile + b"\r\n")) is True


def test_1182_ein_run_mit_text_ausgabe_oder_ohne_ausgabe_geht_weiter():
    """Die Tests des Starters reichen Text herein, ein gescheiterter Aufruf liefert `None`: beides bleibt gültig."""
    assert cn.claude_laeuft("win32", run=lambda b, **kw: SimpleNamespace(stdout="Claude.exe 1 Console", returncode=0)) is True
    assert cn.claude_laeuft("win32", run=lambda b, **kw: SimpleNamespace(stdout=None, returncode=0)) is False
    assert cn.claude_laeuft("win32", run=lambda b, **kw: SimpleNamespace(stdout=b"", returncode=0)) is False


def test_1182_der_store_start_liest_bytes_und_meldet_ok(lese_thread_fehler):
    """PowerShell schreibt ebenfalls in der Kodierung der Konsole; „ok“ wird auch erkannt, wenn die Ausgabe sonst nicht ASCII ist."""
    ausgabe = b"ok\r\nVerkn\x81pfung gestartet\r\n"
    fragen, ausgaben = [], []
    ergebnis = cn.neustart_anbieten(
        "win32", frage=lambda t: fragen.append(t) or "j", ausgabe=lambda *t: ausgaben.append(t),
        run=lambda befehl, **kw: (SimpleNamespace(stdout=MIT_CLAUDE, returncode=0) if befehl[0] == "tasklist"
                                  else _kind(ausgabe)(befehl, **kw) if befehl[0] == "powershell"
                                  else SimpleNamespace(stdout=b"", returncode=0)),
        start=lambda *a, **k: None, pause=lambda s: None, umgebung={}, ist_datei=lambda p: False, ist_ordner=lambda p: False)
    assert ergebnis == "beendet_und_gestartet"
    assert lese_thread_fehler == []


# ── der Helfer ────────────────────────────────────────────────────────────────────────────────────────────────

def test_1182_text_lesen_verwandelt_bytes_nie_mit_abbruch():
    assert konsole.text_lesen(None) == ""
    assert konsole.text_lesen("schon Text") == "schon Text"
    assert isinstance(konsole.text_lesen(b"\xff\xfe\x81\x8d\x8f\x90\x9d"), str), "auch Bytes, die in keiner Kodierung stimmen, brechen nichts ab"
    # UTF-8 kennt 0xFF nicht: ohne Ersatzzeichen bräche das Lesen ab (die OEM-Tabellen unter Windows definieren alle 256 Bytes)
    assert konsole.text_lesen(b"M\xffller", kodierung="utf-8") == "M\ufffdller"


@pytest.mark.skipif(sys.platform != "win32", reason="die OEM-Kodierung der Konsole gibt es nur unter Windows")
def test_1182_unter_windows_ist_die_kodierung_der_konsole_oem():
    assert konsole.konsole_kodierung() == "oem"
    assert konsole.text_lesen(b"M\x81ller") == "Müller"          # in cp850 und cp437 ist 0x81 das ü


@pytest.mark.skipif(sys.platform == "win32", reason="nur ausserhalb von Windows")
def test_1182_sonst_ist_es_utf8():
    assert konsole.konsole_kodierung() == "utf-8"
    assert konsole.text_lesen("Müller".encode("utf-8")) == "Müller"


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell-Pfade gibt es nur unter Windows")
def test_1182_ein_desktop_pfad_mit_umlaut_wird_richtig_gelesen(monkeypatch):
    """`[Environment]::GetFolderPath('Desktop')` schreibt den Pfad in der Kodierung der Konsole; ein Benutzername wie „Müller“ brach den Lese-Thread ab."""
    from bewerbungs_assistent.services import ollama_start
    ausgabe = "C:\\Users\\Müller\\Desktop\r\n".encode(konsole.konsole_kodierung())
    code = "import sys; sys.stdout.buffer.write(%r)" % (ausgabe,)
    echtes_run = subprocess.run
    monkeypatch.setattr(ollama_start.subprocess, "run", lambda befehl, **kw: echtes_run([sys.executable, "-c", code], **kw))
    assert str(ollama_start._desktop_ordner()) == "C:\\Users\\Müller\\Desktop"


# ── der Wächter ───────────────────────────────────────────────────────────────────────────────────────────────

#: Bestand, der den Textmodus ohne Kodierung benutzen darf (Datei:Zeile). Leer: keiner.
BESTAND: set = set()


def _quelldateien():
    for ordner in ("src", "installer"):
        yield from (ROOT / ordner).rglob("*.py")
    for name in ("start_dashboard.py", "_selftest.py", "_programm_einrichten.py"):
        if (ROOT / name).exists():
            yield ROOT / name


def _text_modus_ohne_kodierung():
    funde = set()
    for pfad in _quelldateien():
        try:
            baum = ast.parse(pfad.read_text(encoding="utf-8-sig"))
        except SyntaxError:      # pragma: no cover
            continue
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            kw = {k.arg: k.value for k in knoten.keywords if k.arg}
            text = kw.get("text") or kw.get("universal_newlines")
            if isinstance(text, ast.Constant) and text.value is True and "encoding" not in kw and "errors" not in kw:
                funde.add(f"{pfad.relative_to(ROOT).as_posix()}:{knoten.lineno}")
    return funde


def test_1182_waechter_kein_textmodus_mit_der_standardkodierung():
    """Jeder Aufruf mit `text=True` (oder `universal_newlines=True`) nennt `encoding=` oder `errors=`.

    Ohne das liest Python die Ausgabe eines Konsolenprogramms mit der Kodierung des Systems (cp1252), das Programm schreibt aber in der der
    Konsole (cp850): beim ersten „ü“ bricht der Lese-Thread ab. Die Regeln und der Helfer stehen in `services/konsole.py`.
    """
    neu = _text_modus_ohne_kodierung() - BESTAND
    assert not neu, "Textmodus ohne Kodierung (siehe services/konsole.py): " + ", ".join(sorted(neu))
    veraltet = BESTAND - _text_modus_ohne_kodierung()
    assert not veraltet, f"der Bestand ist nicht mehr nötig: {sorted(veraltet)}"


def test_1182_der_waechter_erkennt_den_fehler_wirklich(tmp_path):
    """Der Wächter prüft sich selbst: ein Aufruf wie der des Fundes wird gefunden, einer mit Kodierung nicht."""
    quelle = ("import subprocess\n"
              "subprocess.run(['x'], capture_output=True, text=True)\n"                                  # Zeile 2: Fund
              "subprocess.run(['x'], capture_output=True, text=True, errors='replace')\n"
              "subprocess.run(['x'], capture_output=True, encoding='utf-8')\n"
              "subprocess.Popen(['x'], stdout=subprocess.PIPE, universal_newlines=True)\n"                # Zeile 5: Fund
              "subprocess.run(['x'], capture_output=True)\n")
    baum = ast.parse(quelle)
    zeilen = []
    for k in ast.walk(baum):
        if isinstance(k, ast.Call):
            kw = {x.arg: x.value for x in k.keywords if x.arg}
            t = kw.get("text") or kw.get("universal_newlines")
            if isinstance(t, ast.Constant) and t.value is True and "encoding" not in kw and "errors" not in kw:
                zeilen.append(k.lineno)
    assert sorted(zeilen) == [2, 5]
