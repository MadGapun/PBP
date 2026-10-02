"""Auto-Update (#1093): Ende-zu-Ende mit ECHTEN Prozessen und dem echten Programm.

Der Installer-Helfer richtet aus dem Quellbaum dieses Repositorys einen Programmordner ein; das Dashboard startet
ueber den Starter im Programmordner und den Startbaustein — genau der Weg der Desktop-Verknuepfung. Drei Zusagen:

* die Fassung laeuft aus `versions/<fassung>` und weiss es (`/api/health`, `/api/auto-update`),
* der Start wird bestaetigt (`update_status.json`),
* eine Fassung, die beim Start einen Importfehler wirft, fuehrt zum Rueckfall auf die vorige — im selben Prozess,
  das Dashboard antwortet trotzdem, und es sagt, was passiert ist (Akzeptanzkriterium 5).

Isolation (QA-Regel): jeder Prozess bekommt `BA_DATA_DIR` und `PBP_APP_DIR`-freie Umgebung unter `tmp_path`; der
Starter oeffnet keinen Browser (`PBP_KEIN_BROWSER`), stdin ist zu (kein Rueckfrage-Dialog zu Claude Desktop).
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "src"))

import _programm_einrichten as einrichten  # noqa: E402

PYTHON = sys.executable


def quellbaum_kopieren(ziel: Path, version: str) -> Path:
    shutil.copytree(WURZEL / "src", ziel / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("start_dashboard.py", "_selftest.py"):
        shutil.copy2(WURZEL / name, ziel / name)
    (ziel / "installer" / "boot").mkdir(parents=True)
    shutil.copy2(WURZEL / "installer" / "boot" / "start_dashboard_launcher.py", ziel / "installer" / "boot")
    init = ziel / "src" / "bewerbungs_assistent" / "__init__.py"
    init.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{version}"', init.read_text(encoding="utf-8")),
                    encoding="utf-8")
    return ziel


@pytest.fixture(scope="module")
def quellen(tmp_path_factory):
    """Zwei Fassungen des echten Programms: 1.8.0 und 1.8.1 — nur die Versionsnummer unterscheidet sie."""
    wurzel = tmp_path_factory.mktemp("quellen")
    return {v: quellbaum_kopieren(wurzel / v, v) for v in ("1.8.0", "1.8.1")}


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http_json(port: int, pfad: str, timeout=5):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{pfad}", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class Dashboard:
    """Das Dashboard als echter Prozess ueber den Starter im Programmordner."""

    def __init__(self, app: Path, daten: Path, basis: Path):
        norm = lambda p: os.path.normcase(os.path.abspath(str(p)))   # noqa: E731
        assert norm(app).startswith(norm(basis)) and norm(daten).startswith(norm(basis)), "Programm- oder Datenordner nicht isoliert"
        self.app, self.daten, self.port = app, daten, freier_port()
        self.log = daten.parent / f"dashboard-{self.port}.log"
        env = {k: v for k, v in os.environ.items() if k not in ("PBP_APP_DIR", "PBP_FASSUNG", "PYTHONPATH", "BA_DATA_DIR")}
        env.update(BA_DATA_DIR=str(daten), BA_DASHBOARD_PORT=str(self.port), PBP_KEIN_BROWSER="1",
                   PBP_BESTAETIGUNG_NACH_S="1", PBP_GEOCODING="0", PBP_BERUFE_LOOKUP="0", PBP_NETZ_PRUEFUNG="0",
                   PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        self._logdatei = open(self.log, "wb")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen([PYTHON, str(app / "start_dashboard.py")], env=env, stdin=subprocess.DEVNULL,
                                     stdout=self._logdatei, stderr=subprocess.STDOUT, cwd=str(app.parent), creationflags=flags)

    def warten(self, sekunden=120):
        ende = time.time() + sekunden
        while time.time() < ende:
            if self.proc.poll() is not None:
                raise AssertionError(f"Dashboard beendet ({self.proc.returncode}):\n{self.log_text()}")
            try:
                return http_json(self.port, "/api/health", timeout=2)
            except Exception:
                time.sleep(0.5)
        raise AssertionError(f"Dashboard antwortet nicht:\n{self.log_text()}")

    def log_text(self):
        self._logdatei.flush()
        return self.log.read_text(encoding="utf-8", errors="replace")[-3000:]

    def beenden(self):
        if self.proc.poll() is None:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True)
            else:
                self.proc.terminate()
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self._logdatei.close()


@pytest.fixture
def dashboard(tmp_path):
    gestartet = []

    def start(app: Path):
        d = Dashboard(app, tmp_path / "daten", tmp_path)
        gestartet.append(d)
        return d

    yield start
    for d in gestartet:
        d.beenden()


def programmordner(tmp_path: Path, quellen, *versionen) -> Path:
    app = tmp_path / "app"
    for v in versionen:
        assert einrichten.einrichten(quellen[v], app)["version"] == v
    return app


def status(app: Path) -> dict:
    return json.loads((app / "update_status.json").read_text(encoding="utf-8"))


# ══ Normaler Start ═══════════════════════════════════════════════════════════════════════

def test_das_dashboard_laeuft_aus_dem_versionsordner_und_bestaetigt_seinen_start(tmp_path, quellen, dashboard):
    app = programmordner(tmp_path, quellen, "1.8.0")
    d = dashboard(app)
    gesund = d.warten()
    assert gesund["pbp_version"] == "1.8.0" and gesund["fassung_laufend"] == "1.8.0"
    assert gesund["datenbank_zu_neu"] is None
    if sys.platform == "win32":
        au = http_json(d.port, "/api/auto-update")
        assert au["verfuegbar"] is True and au["laufend"] == "1.8.0" and au["aktuell"] == "1.8.0"
        assert au["installiert"] == ["1.8.0"] and au["stufe"] == "aus"
        for _ in range(40):                                  # PBP_BESTAETIGUNG_NACH_S=1
            if status(app).get("start", {}).get("bestaetigt"):
                break
            time.sleep(0.5)
        s = status(app)
        assert s["start"]["bestaetigt"] is True and s["bestaetigt"] == "1.8.0"


def test_ein_belegungseintrag_zeigt_dass_die_fassung_benutzt_wird_und_verschwindet_beim_beenden(tmp_path, quellen, dashboard):
    app = programmordner(tmp_path, quellen, "1.8.0")
    d = dashboard(app)
    d.warten()
    from bewerbungs_assistent.services.auto_update import aufraeumen
    marken = list((app / "versions" / "1.8.0" / ".in_benutzung").glob("*.json"))
    assert len(marken) == 1
    pid = json.loads(marken[0].read_text())["pid"]         # unter Windows startet der venv-Starter den eigentlichen Interpreter
    assert aufraeumen.prozess_lebt(pid) and aufraeumen.belegungen(app, "1.8.0", aufraeumen=False)
    d.beenden()
    # bei hartem Beenden (taskkill /F) bleibt die Marke liegen; die Aufraeum-Logik erkennt den toten Prozess daran
    for _ in range(20):
        if not aufraeumen.prozess_lebt(pid):
            break
        time.sleep(0.5)
    assert aufraeumen.belegungen(app, "1.8.0") == []


def test_zwei_fassungen_aktuell_txt_entscheidet(tmp_path, quellen, dashboard):
    app = programmordner(tmp_path, quellen, "1.8.0", "1.8.1")
    d = dashboard(app)
    assert d.warten()["pbp_version"] == "1.8.1"
    d.beenden()
    (app / "aktuell.txt").write_text("1.8.0\n", encoding="utf-8")
    d2 = dashboard(app)
    assert d2.warten()["pbp_version"] == "1.8.0"


# ══ Rueckfall ════════════════════════════════════════════════════════════════════════════

def fassung_kaputt_machen(app: Path, version: str, datei="dashboard.py"):
    ziel = app / "versions" / version / "src" / "bewerbungs_assistent" / datei
    text = ziel.read_text(encoding="utf-8-sig")
    ziel.write_text('raise ImportError("Testdefekt: ein Paket fehlt")\n' + text, encoding="utf-8")


def test_eine_fassung_mit_importfehler_fuehrt_im_selben_prozess_zurueck_auf_die_vorige(tmp_path, quellen, dashboard):
    app = programmordner(tmp_path, quellen, "1.8.0", "1.8.1")
    fassung_kaputt_machen(app, "1.8.1")
    assert (app / "aktuell.txt").read_text().strip() == "1.8.1" and status(app)["vorherige"] == "1.8.0"
    d = dashboard(app)
    gesund = d.warten()
    assert gesund["pbp_version"] == "1.8.0", "das Dashboard laeuft wieder mit der vorigen Fassung"
    assert (app / "aktuell.txt").read_text().strip() == "1.8.0"
    s = status(app)
    assert s["gescheitert"] == ["1.8.1"]
    assert s["rueckgang"]["von"] == "1.8.1" and s["rueckgang"]["nach"] == "1.8.0"
    assert "ImportError" in s["rueckgang"]["grund"] and "Testdefekt" in s["rueckgang"]["grund"]
    if sys.platform == "win32":
        au = http_json(d.port, "/api/auto-update")
        assert au["rueckgang"]["von"] == "1.8.1" and au["laufend"] == "1.8.0"
        # und die gescheiterte Fassung wird nicht noch einmal angeboten
        from bewerbungs_assistent.services.auto_update import zustand
        assert "1.8.1" in zustand.gescheiterte_fassungen(app)


def test_ohne_vorige_fassung_gibt_es_keinen_rueckfall_und_der_fehler_bleibt_sichtbar(tmp_path, quellen, dashboard):
    app = programmordner(tmp_path, quellen, "1.8.1")
    fassung_kaputt_machen(app, "1.8.1")
    d = dashboard(app)
    ende = time.time() + 60
    while time.time() < ende and d.proc.poll() is None:
        time.sleep(0.5)
    assert d.proc.poll() is not None, "ohne Rueckfall beendet sich das Dashboard"
    assert "Testdefekt" in d.log_text()
    assert (app / "aktuell.txt").read_text().strip() == "1.8.1"
    assert "ImportError" in status(app)["start"]["fehler"]


# ══ Der MCP-Server ueber den Startbaustein ═══════════════════════════════════════════════

def test_der_mcp_server_antwortet_ueber_den_startbaustein_und_stoert_die_standardausgabe_nicht(tmp_path, quellen):
    """Claude Desktop startet `python -m bewerbungs_assistent_boot` und spricht JSON-RPC ueber stdin/stdout. Schreibt der
    Startbaustein irgendetwas anderes auf die Standardausgabe, ist das Gespraech kaputt: jede Zeile dort muss JSON sein.

    Die Fehlerausgabe wird mitgelesen: der Anonym-Puffer unter Windows fasst nur 4 KB, und eine frische Datenbank
    schreibt beim Anlegen etwa 6 KB Protokoll (gilt genauso fuer den Server OHNE Startbaustein). Alles liest ueber
    Threads mit hartem Zeitlimit, damit ein Haenger den Testlauf nie blockiert."""
    import queue
    import threading

    app = programmordner(tmp_path, quellen, "1.8.0")
    daten = tmp_path / "daten"
    assert str(tmp_path) in str(daten)
    env = {k: v for k, v in os.environ.items() if k not in ("PBP_APP_DIR", "PBP_FASSUNG", "BA_DATA_DIR", "PYTHONPATH")}
    env.update(BA_DATA_DIR=str(daten), BA_DASHBOARD_PORT=str(freier_port()), PYTHONPATH=str(app / "boot"),
               PBP_BESTAETIGUNG_NACH_S="1", PBP_GEOCODING="0", PBP_BERUFE_LOOKUP="0", PBP_NETZ_PRUEFUNG="0",
               PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    p = subprocess.Popen([PYTHON, "-m", "bewerbungs_assistent_boot"], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, cwd=str(tmp_path), creationflags=flags)
    aus, fehlerzeilen = queue.Queue(), []

    def leser(strom, ablage):
        for zeile in iter(strom.readline, b""):
            ablage(zeile)
        ablage(None)

    threading.Thread(target=leser, args=(p.stdout, aus.put), daemon=True).start()
    threading.Thread(target=leser, args=(p.stderr, lambda z: fehlerzeilen.append(z) if z else None), daemon=True).start()

    def senden(nachricht):
        p.stdin.write((json.dumps(nachricht) + "\n").encode("utf-8"))
        p.stdin.flush()

    def antwort(nr, sekunden=120):
        ende = time.time() + sekunden
        while time.time() < ende:
            try:
                zeile = aus.get(timeout=1)
            except queue.Empty:
                continue
            assert zeile is not None, "der Server hat die Standardausgabe geschlossen"
            try:
                d = json.loads(zeile.decode("utf-8"))
            except ValueError:
                raise AssertionError(f"Zeile auf der Standardausgabe ist kein JSON: {zeile[:200]!r}")
            if d.get("id") == nr:
                return d
        raise AssertionError(f"keine Antwort auf Anfrage {nr} nach {sekunden} s;\nFehlerausgabe:\n"
                             + b"".join(fehlerzeilen[-20:]).decode("utf-8", "replace"))

    try:
        senden({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}})
        assert antwort(1)["result"]["serverInfo"]["name"] == "Bewerbungs-Assistent"
        senden({"jsonrpc": "2.0", "method": "notifications/initialized"})
        senden({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        namen = {t["name"] for t in antwort(2)["result"]["tools"]}
        assert {"profil_status", "update_status", "update_einstellungen_setzen"} <= namen
        assert len(namen) > 200
        # und die Fassung steht im Programmordner, nicht irgendwo im Quellbaum: ein echtes Werkzeug fragen
        senden({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "update_status", "arguments": {}}})
        ergebnis = antwort(3)["result"]
        text = json.dumps(ergebnis, ensure_ascii=False)
        assert '"laufend"' in text and "1.8.0" in text, text[:600]
    finally:
        try:
            p.stdin.close()
        except OSError:
            pass
        try:
            p.wait(30)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            else:
                p.kill()
    fehler = b"".join(fehlerzeilen).decode("utf-8", "replace")
    assert "Traceback" not in fehler, fehler[-1500:]
