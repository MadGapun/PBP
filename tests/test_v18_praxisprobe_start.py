"""Praxisprobe 1.8 (05.10.2026), Teil Start: zwei Funde auf einem frischen Windows 11, auf dem Claude Desktop lief.

PP1  Das Dashboard-Fenster stellte „Claude jetzt neu starten? [j/N]“ VOR dem Start des Servers. Das Fenster liegt hinter anderen;
     solange niemand antwortet, läuft kein Server. Der Installer wartet 60 Sekunden und öffnet im Browser eine Seite „Verbindung
     verweigert“ — der erste Eindruck bei jedem, der Claude Desktop beim Installieren offen hat.
PP3  Der Installer meldete am Ende „Claude Desktop nicht gefunden — bitte manuell starten“, obwohl es installiert war und lief
     (Store-Fassung, schon am Konfigurationsordner erkannt, dadurch wurde die Paket-Abfrage übersprungen). Dazu stand ein
     Gedankenstrich in der Ausgabe, den die Konsole als „ÖÇö“ zeigte.
PP14 (Gegenprobe) Die Frage läuft im Hintergrund, und Protokollzeilen des Servers schoben sich in dieselbe Zeile. Dazu zeigte der erste
     Start Dutzende Zeilen „Safety-Net … nachgezogen“. Das Dashboard-Fenster zeigt jetzt nur Warnungen und Fehler; die Log-Datei
     bekommt weiter alles.
PP15 (Gegenprobe) `start_dashboard.py` öffnete Chrome, BEVOR der Server lauschte: auf einem frischen Rechner „Verbindung verweigert“
     bis zum Neuladen. Dazu öffnete der Installer danach den Standardbrowser noch einmal. Jetzt öffnet das Dashboard erst, wenn es
     antwortet, und der Installer unterdrückt das Öffnen im von ihm gestarteten Fenster (er öffnet selbst, nach seiner Prüfung).
PP18 (zweite Gegenprobe) Am Ende JEDER gelungenen Installation stand „Die Syntax für den Dateinamen, Verzeichnisnamen oder die
     Datenträgerbezeichnung ist falsch.“, und die Einstellung zum Aufräumen (nie/immer) wurde nie gelesen: `for /f "usebackq"` führt den
     Befehl über `cmd /c` aus, und `cmd` schneidet bei mehr als zwei Anführungszeichen das erste und das letzte ab.
"""
import http.server
import json
import logging
import os
import socket
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from bewerbungs_assistent.services import browser_oeffnen, claude_neustart

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


def test_pp3_zwei_kleinigkeiten_der_ausgabe():
    """Unter EnableDelayedExpansion verschluckt ein einzelnes `!` den Satzanfang („Willkommen Dieses Setup …“), und in einer
    Zeichenkette in Anführungszeichen sind `^(` und `^)` keine Fluchtzeichen, sondern erscheinen so auf dem Bildschirm."""
    text = (ROOT / "INSTALLIEREN.bat").read_text(encoding="utf-8")
    assert "Willkommen^^! Dieses Setup" in text
    zeile = next(z for z in text.splitlines() if z.strip().startswith('set /p FORCE_INSTALL="'))
    assert "^(" not in zeile and "(j/n)" in zeile


# ── PP14: die Console zeigt nur Warnungen ──────────────────────────────────────────────────────

def _logging_lauf(tmp_path, console_level=None, env_stufe=None):
    """Ein frischer Interpreter (`setup_logging` merkt sich seinen Zustand im Modul): INFO und WARNING schreiben, dann Console (stderr)
    und Log-Datei lesen. Die Datenordner liegen im Temp-Ordner des Tests."""
    code = (
        "import sys, logging, time\n"
        f"sys.path.insert(0, {str(ROOT / 'src')!r})\n"
        "from bewerbungs_assistent import logging_config as lc\n"
        f"lc.setup_logging(console=True, console_level={console_level!r})\n"
        "lg = logging.getLogger('bewerbungs_assistent')\n"
        "lg.info('INFO-ZEILE-eins')\n"
        "lg.warning('WARN-ZEILE-zwei')\n"
        "time.sleep(0.5)\n"                       # der QueueListener schreibt auf einem eigenen Thread
        "lc._queue_listener.stop()\n"
    )
    env = dict(os.environ, BA_DATA_DIR=str(tmp_path / "daten"))
    assert str(tmp_path) in env["BA_DATA_DIR"], "QA-Isolation"
    env.pop("BA_CONSOLE_LEVEL", None)
    env.pop("BA_LOG_LEVEL", None)
    if env_stufe:
        env["BA_CONSOLE_LEVEL"] = env_stufe
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stderr, (tmp_path / "daten" / "logs" / "pbp.log").read_text(encoding="utf-8")


def test_pp14_ohne_angabe_bleibt_es_wie_vorher_alles_auf_der_console(tmp_path):
    konsole, datei = _logging_lauf(tmp_path)
    assert "INFO-ZEILE-eins" in konsole and "WARN-ZEILE-zwei" in konsole
    assert "INFO-ZEILE-eins" in datei and "WARN-ZEILE-zwei" in datei


def test_pp14_mit_warning_zeigt_die_console_nur_warnungen_die_datei_alles(tmp_path):
    konsole, datei = _logging_lauf(tmp_path, console_level="WARNING")
    assert "INFO-ZEILE-eins" not in konsole and "WARN-ZEILE-zwei" in konsole
    assert "INFO-ZEILE-eins" in datei and "WARN-ZEILE-zwei" in datei, "die Datei behält alles"


def test_pp14_die_umgebungsvariable_stellt_die_console_ein(tmp_path):
    konsole, datei = _logging_lauf(tmp_path, env_stufe="ERROR")
    assert "INFO-ZEILE-eins" not in konsole and "WARN-ZEILE-zwei" not in konsole
    assert "WARN-ZEILE-zwei" in datei


def test_pp14_ein_unbekannter_name_macht_die_console_nie_stiller_als_die_datei(tmp_path):
    konsole, _ = _logging_lauf(tmp_path, console_level="LAUT")
    assert "INFO-ZEILE-eins" in konsole


def test_pp14_das_dashboard_fenster_nimmt_warning_als_vorgabe():
    quelle = (ROOT / "start_dashboard.py").read_text(encoding="utf-8")
    assert 'setup_logging(console=True, console_level=os.environ.get("BA_CONSOLE_LEVEL", "WARNING"))' in quelle


def test_pp14_der_mcp_server_behaelt_seine_console():
    """Der MCP-Prozess hängt am stderr von Claude Desktop (#760); seine Stufe bleibt, wie sie war."""
    quelle = (ROOT / "src" / "bewerbungs_assistent" / "server.py").read_text(encoding="utf-8")
    assert "setup_logging(console=True)" in quelle


# ── PP15: der Browser öffnet sich erst, wenn das Dashboard antwortet ───────────────────────────

class _Uhr:
    """Eine Uhr, die nur beim Warten vorrückt: kein echtes Schlafen im Test."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def pause(self, sekunden):
        self.t += sekunden
        # Ein Warten, das nie endet, soll als Fehler auffallen und nicht als Hänger der ganzen Suite
        assert self.t < 1000, "das Warten endet nie"


def test_pp15_das_warten_endet_mit_der_ersten_antwort():
    uhr, antworten, proben = _Uhr(), iter([False, False, True]), []

    def probe(port):
        proben.append(port)
        return next(antworten)

    assert browser_oeffnen.warte_bis_bereit(8200, frist=60, takt=0.3, probe=probe, uhr=uhr, pause=uhr.pause) is True
    assert proben == [8200, 8200, 8200]
    assert uhr.t == pytest.approx(0.6)


def test_pp15_ohne_antwort_gibt_das_warten_nach_der_frist_auf():
    uhr = _Uhr()
    assert browser_oeffnen.warte_bis_bereit(8200, frist=2.0, takt=0.5, probe=lambda p: False, uhr=uhr, pause=uhr.pause) is False
    assert 2.0 <= uhr.t < 3.0


def test_pp15_eine_fehlgeschlagene_probe_heisst_nur_noch_nicht():
    uhr, lage = _Uhr(), {"n": 0}

    def probe(port):
        lage["n"] += 1
        if lage["n"] < 3:
            raise OSError("noch nichts da")
        return True

    assert browser_oeffnen.warte_bis_bereit(8200, frist=60, probe=probe, uhr=uhr, pause=uhr.pause) is True


def test_pp15_geoeffnet_wird_erst_nach_der_antwort():
    bereit, geoeffnet = threading.Event(), []
    faden = browser_oeffnen.oeffnen_sobald_bereit("http://x", 1, geoeffnet.append, probe=lambda p: bereit.is_set(), takt=0.01)
    try:
        assert faden.daemon, "ein Daemon: der Thread hält das Beenden des Dashboards nie auf"
        time.sleep(0.3)
        assert geoeffnet == [], "das Dashboard antwortet noch nicht"
    finally:
        bereit.set()
    faden.join(timeout=10)
    assert geoeffnet == ["http://x"] and not faden.is_alive()


def test_pp15_nach_der_frist_wird_trotzdem_geoeffnet_und_gewarnt(caplog):
    geoeffnet = []
    with caplog.at_level(logging.WARNING):
        faden = browser_oeffnen.oeffnen_sobald_bereit("http://x", 1, geoeffnet.append, frist=0.05, takt=0.01, probe=lambda p: False)
        faden.join(timeout=10)
    assert geoeffnet == ["http://x"]
    assert "noch nicht" in caplog.text


def test_pp15_ein_fehler_beim_oeffnen_stoert_nichts(caplog):
    def kaputt(url):
        raise RuntimeError("kein Browser da")

    with caplog.at_level(logging.WARNING):
        faden = browser_oeffnen.oeffnen_sobald_bereit("http://x", 1, kaputt, probe=lambda p: True)
        faden.join(timeout=10)
    assert not faden.is_alive()
    assert "kein Browser da" in caplog.text


def test_pp15_mit_einem_echten_server_der_erst_spaeter_lauscht():
    """Die Praxis: erst ist nichts da (Windows lehnt die Verbindung ab), dann antwortet ein Server auf /api/health."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    class Gesundheit(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            koerper = json.dumps({"pbp_version": "test"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(koerper)))
            self.end_headers()
            self.wfile.write(koerper)

        def log_message(self, *a):
            pass

    geoeffnet = []
    url = f"http://localhost:{port}"
    faden = browser_oeffnen.oeffnen_sobald_bereit(url, port, geoeffnet.append, takt=0.05)
    time.sleep(0.8)
    assert geoeffnet == [], "noch lauscht niemand"
    server = http.server.HTTPServer(("127.0.0.1", port), Gesundheit)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        faden.join(timeout=20)
        assert geoeffnet == [url]
    finally:
        server.shutdown()
        server.server_close()


def test_pp15_der_starter_oeffnet_den_browser_erst_nach_der_antwort():
    quelle = (ROOT / "start_dashboard.py").read_text(encoding="utf-8")
    haupt = quelle[quelle.index("db = Database()"):]
    assert "oeffnen_sobald_bereit(f\"http://localhost:{port}\", port, _open_in_chrome)" in haupt
    assert haupt.index("oeffnen_sobald_bereit(") < haupt.index("start_dashboard(db, port=port)")
    # Direkt aufgerufen wird nur noch im Zweig „PBP läuft bereits“ (der Server steht dort schon)
    assert quelle.count('_open_in_chrome(f"http://localhost:{port}")') == 1
    assert quelle.index('_open_in_chrome(f"http://localhost:{port}")') < quelle.index("db = Database()")


def test_pp15_der_installer_unterdrueckt_den_browser_des_dashboards_und_oeffnet_selbst():
    z = (ROOT / "INSTALLIEREN.bat").read_text(encoding="utf-8").splitlines()
    setzen = next(i for i, s in enumerate(z) if s.strip() == 'set "PBP_KEIN_BROWSER=1"')
    start = next(i for i, s in enumerate(z) if s.startswith('start "PBP-Dashboard" /MIN'))
    loeschen = next(i for i, s in enumerate(z) if s.strip() == 'set "PBP_KEIN_BROWSER="')
    assert setzen < start < loeschen, "gesetzt, dann gestartet, dann wieder gelöscht"
    assert 'start "" "http://localhost:8200/"' in "\n".join(z[loeschen:]), "geöffnet wird weiter vom Installer, nach seiner Prüfung"


# ── PP18: die Abfrage zum Aufräumen am Ende der Installation ───────────────────────────────────

def _aufraeumen_zeile() -> str:
    text = (ROOT / "INSTALLIEREN.bat").read_text(encoding="utf-8")
    return next(z for z in text.splitlines()
                if z.startswith("for /f") and "_installer_aufraeumen.py" in z and "einstellung" in z)


def test_pp18_der_ganze_befehl_steht_in_einem_zusaetzlichen_anfuehrungszeichenpaar():
    """`cmd /c` schneidet bei einem Befehl, der mit einem Anführungszeichen beginnt und mehr als zwei hat, das erste und das letzte ab."""
    zeile = _aufraeumen_zeile()
    befehl = zeile[zeile.index("(`") + 2:zeile.index("`)")]
    assert befehl.startswith('""') and befehl.endswith('""'), befehl


@pytest.mark.skipif(os.name != "nt", reason="braucht cmd.exe")
def test_pp18_die_abfrage_laeuft_und_ihre_antwort_kommt_an(tmp_path):
    """Die ECHTE Zeile aus dem Installer mit einer Kopie des Basis-Python als Laufzeit und einem Skript, das „nie“ meldet. Alles im
    Temp-Ordner. Vorher blieb das Ergebnis „fragen“, und cmd schrieb die Syntax-Meldung auf den Bildschirm."""
    basis_python = Path(sys.base_exec_prefix) / "python.exe"
    if not basis_python.is_file():
        pytest.skip("kein eigenständiges Basis-Python gefunden")
    app, install, daten = tmp_path / "app", tmp_path / "install", tmp_path / "data"
    (app / "python").mkdir(parents=True)
    install.mkdir()
    shutil.copy2(basis_python, app / "python" / "python.exe")
    (install / "_installer_aufraeumen.py").write_text("print('nie')\n", encoding="utf-8")
    bat = tmp_path / "probe.bat"
    bat.write_bytes(("@echo off\r\nsetlocal EnableDelayedExpansion\r\n"
                     f'set "APP_DIR={app}"\r\nset "BASEDIR={install}"\r\nset "DATA_DIR={daten}"\r\n'
                     'set "AUFRAEUMEN=fragen"\r\n' + _aufraeumen_zeile() + "\r\necho ERGEBNIS=!AUFRAEUMEN!\r\n").encode("cp850"))
    env = dict(os.environ, PATH=str(Path(sys.base_exec_prefix)) + os.pathsep + os.environ.get("PATH", ""))
    r = subprocess.run(["cmd.exe", "/c", str(bat)], capture_output=True, env=env, timeout=60, creationflags=0x08000000)
    ausgabe = (r.stdout + r.stderr).decode("cp850", errors="replace")
    assert "Syntax" not in ausgabe, ausgabe
    assert "ERGEBNIS=nie" in ausgabe, ausgabe
