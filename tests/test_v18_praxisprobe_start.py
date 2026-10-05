"""Praxisprobe 1.8 (05.10.2026), Teil Start: zwei Funde auf einem frischen Windows 11, auf dem Claude Desktop lief.

PP1  Das Dashboard-Fenster stellte „Claude jetzt neu starten? [j/N]“ VOR dem Start des Servers. Das Fenster liegt hinter anderen;
     solange niemand antwortet, läuft kein Server. Der Installer wartet 60 Sekunden und öffnet im Browser eine Seite „Verbindung
     verweigert“ — der erste Eindruck bei jedem, der Claude Desktop beim Installieren offen hat.
PP3  Der Installer meldete am Ende „Claude Desktop nicht gefunden — bitte manuell starten“, obwohl es installiert war und lief
     (Store-Fassung, schon am Konfigurationsordner erkannt, dadurch wurde die Paket-Abfrage übersprungen). Dazu stand ein
     Gedankenstrich in der Ausgabe, den die Konsole als „ÖÇö“ zeigte.
"""
import threading
import time
from pathlib import Path

from bewerbungs_assistent.services import claude_neustart

ROOT = Path(__file__).resolve().parents[1]


def _tasklist_mit_claude(cmd, **kw):
    class R:
        stdout = "Claude.exe    1234 Console   1   100.000 K"
        returncode = 0
    return R()


# ── PP1: die Frage hält den Start nicht auf ────────────────────────────────────────────────────

def test_pp1_die_frage_blockiert_den_start_nicht():
    wartet = threading.Event()
    gefragt = threading.Event()

    def frage(text):
        gefragt.set()
        wartet.wait(timeout=30)           # niemand antwortet — wie im Praxisfall
        return "n"

    t0 = time.monotonic()
    faden = claude_neustart.neustart_im_hintergrund(
        warte=0, ist_konsole=lambda: True, plattform="win32", frage=frage, ausgabe=lambda *a: None,
        run=_tasklist_mit_claude, pause=lambda s: None)
    zurueck_nach = time.monotonic() - t0
    try:
        assert faden is not None and faden.daemon, "ein Daemon-Thread: er hält das Beenden des Dashboards nie auf"
        assert zurueck_nach < 2, "die Funktion muss sofort zurückkehren, sonst wartet der Server weiter"
        assert gefragt.wait(timeout=10), "gefragt wird trotzdem — nur eben nicht vor dem Start"
        assert faden.is_alive(), "der Thread wartet auf die Antwort"
    finally:
        wartet.set()
        faden.join(timeout=10)
    assert not faden.is_alive()


def test_pp1_ohne_konsole_wird_gar_nicht_gefragt():
    fragen = []
    faden = claude_neustart.neustart_im_hintergrund(
        warte=0, ist_konsole=lambda: False, plattform="win32", frage=lambda t: fragen.append(t) or "n",
        ausgabe=lambda *a: None, run=_tasklist_mit_claude, pause=lambda s: None)
    assert faden is None and fragen == []


def test_pp1_eine_ausnahme_im_thread_stoert_den_server_nicht():
    def kaputt(cmd, **kw):
        raise OSError("tasklist nicht da")

    faden = claude_neustart.neustart_im_hintergrund(
        warte=0, ist_konsole=lambda: True, plattform="win32", frage=lambda t: "n",
        ausgabe=lambda *a: None, run=kaputt, pause=lambda s: None)
    faden.join(timeout=10)
    assert not faden.is_alive()


def test_pp1_ein_nein_laesst_claude_offen(monkeypatch):
    """Die Vorgabe bleibt NEIN: nichts wird beendet, wenn niemand ausdrücklich Ja sagt."""
    aufrufe = []

    def run(cmd, **kw):
        aufrufe.append(cmd)
        return _tasklist_mit_claude(cmd, **kw)

    faden = claude_neustart.neustart_im_hintergrund(
        warte=0, ist_konsole=lambda: True, plattform="win32", frage=lambda t: "", ausgabe=lambda *a: None,
        run=run, pause=lambda s: None)
    faden.join(timeout=10)
    assert not any("taskkill" in str(c) for c in aufrufe)


def test_pp1_der_starter_fragt_erst_im_hintergrund_und_nach_dem_banner():
    quelle = (ROOT / "start_dashboard.py").read_text(encoding="utf-8-sig")
    assert "neustart_anbieten(" not in quelle, "der blockierende Aufruf darf nicht zurückkehren"
    aufruf = quelle.index("neustart_im_hintergrund()")
    assert quelle.index('print(f"  Dashboard: http://localhost:{port}")') < aufruf, "erst das Banner mit der Adresse"
    assert aufruf < quelle.index("start_dashboard(db, port=port)"), "die Frage ist unterwegs, bevor der Server blockiert"


# ── PP3: der Installer startet auch die Store-Fassung ──────────────────────────────────────────

def _installer() -> list:
    return (ROOT / "INSTALLIEREN.bat").read_text(encoding="utf-8").splitlines()


def test_pp3_die_paketabfrage_laeuft_auch_wenn_der_konfigurationsordner_schon_gereicht_hat():
    z = _installer()
    exe = max(i for i, s in enumerate(z) if s.startswith('if exist "%USERPROFILE%\\AppData\\Local\\Programs\\Claude\\Claude.exe" set "CLAUDE_EXE='))
    block = next(i for i, s in enumerate(z) if s.startswith("if not defined CLAUDE_EXE if not defined CLAUDE_APPX ("))
    claude_dir = next(i for i, s in enumerate(z) if s.startswith('set "CLAUDE_DIR=%APPDATA%\\Claude"'))
    assert exe < block < claude_dir
    assert "Get-AppxPackage" in z[block + 1] and 'set "CLAUDE_APPX=' in z[block + 1]
    # und der Abschluss startet die Store-Fassung, wenn kein Programmpfad bekannt ist
    ende = "\n".join(z[claude_dir:])
    assert "else if defined CLAUDE_APPX (" in ende and "call :start_claude_appx" in ende


def test_pp3_die_ausgabe_der_bat_dateien_ist_reines_ascii():
    """cmd gibt die UTF-8-Datei in der OEM-Codeseite aus: aus einem Gedankenstrich wird „ÖÇö“. Kommentare sind frei."""
    for name in ("INSTALLIEREN.bat", "DEINSTALLIEREN.bat"):
        for nr, zeile in enumerate((ROOT / name).read_text(encoding="utf-8").splitlines(), 1):
            if zeile.strip().lower().startswith(("::", "rem ")):
                continue
            fremd = [c for c in zeile if ord(c) > 127]
            assert not fremd, f"{name}:{nr} enthält {fremd!r}: {zeile.strip()[:80]}"
