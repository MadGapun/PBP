"""#1290/#1282 — ein haengender eigener Prozess haelt den Port: ehrlich melden, eigenen Prozess beenden, nie falsch zurueckfallen.

Befund (30.10.2026): ein haengender PBP-Prozess (Port offen, `/api/health` ohne Antwort) machte die Desktop-Verknuepfung
zu "ein ANDERES Programm (kein PBP)", und zwei solche Starts stuften 1.8.0 auf 1.8.0-rc.4 zurueck.

Alle Server sind Attrappen auf freien Loopback-Ports; Port 8200 und der Ollama-Port werden nie beruehrt. Beendet wird nur
der eigene Hilfsprozess jedes Tests. Der Startbaustein (`bewerbungs_assistent_boot`) bleibt unveraendert und wird hier mit
seiner echten `waehle_fassung` gegen ein Programmordner-Layout unter `tmp_path` geprueft.
"""
import functools
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import bewerbungs_assistent_boot as boot  # noqa: E402
from bewerbungs_assistent.services import dashboard_halter as halter  # noqa: E402
from bewerbungs_assistent.services import port_besitzer as pb  # noqa: E402
from bewerbungs_assistent.services import port_selbsthilfe as hilfe  # noqa: E402
from bewerbungs_assistent.services.auto_update.start_zaehler import start_ohne_schuld  # noqa: E402

OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0
PBP_JSON = json.dumps({"pbp_version": "1.8.0"})
SCHNELL = functools.partial(halter.port_auskunft, timeout=0.4, versuche=2)


# ── Attrappen ────────────────────────────────────────────────────────────────

class Haengt:
    """Haelt einen Loopback-Port, nimmt Verbindungen an (der Backlog) und antwortet nie: so sah der Fund aus."""

    def __init__(self):
        self.s = socket.socket()
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(5)
        self.port = self.s.getsockname()[1]

    def close(self):
        self.s.close()


@pytest.fixture()
def haengt():
    h = Haengt()
    yield h
    h.close()


def _handler(antworten, verzoegerung=0.0):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(verzoegerung)
            status, typ, text = antworten.get(self.path) or antworten.get("*") or (404, "text/plain", "nicht da")
            roh = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)

        def log_message(self, *args):
            pass
    return H


@pytest.fixture()
def http():
    laufende = []

    def starte(antworten, verzoegerung=0.0):
        s = ThreadingHTTPServer(("127.0.0.1", 0), _handler(antworten, verzoegerung))
        s.daemon_threads = True
        threading.Thread(target=s.serve_forever, daemon=True).start()
        laufende.append(s)
        return s.server_address[1]

    yield starte
    for s in laufende:
        s.shutdown()
        s.server_close()


def _frei():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    """Das Server-Modul auf einer ISOLIERTEN Datenbank (CLAUDE.md: QA-Isolation, `BA_DATA_DIR`), nie auf der echten."""
    import importlib
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path / "srvdaten"))
    (tmp_path / "srvdaten").mkdir()
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv
    importlib.reload(_srv)
    assert str(tmp_path) in str(_srv.db.db_path), f"DB nicht isoliert: {_srv.db.db_path}"
    yield _srv
    _srv.db.close()


@pytest.fixture(autouse=True)
def _halter_sauber():
    halter.zuruecksetzen()
    yield
    halter.zuruecksetzen()


# ── (a) keine Antwort ist nicht "kein PBP" ────────────────────────────────────

def test_a_ein_port_der_nie_antwortet_ist_keine_antwort_und_nicht_fremd(haengt):
    t0 = time.monotonic()
    assert SCHNELL(haengt.port) == halter.ANTWORT_KEINE
    assert time.monotonic() - t0 < 6


def test_a_zwei_versuche_bei_einer_zeitueberschreitung_nur_dann():
    aufrufe = []

    class Antwort:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return PBP_JSON.encode()

    def urlopen(url, timeout):
        aufrufe.append(timeout)
        if len(aufrufe) == 1:
            raise TimeoutError("timed out")
        return Antwort()

    assert halter.port_auskunft(1, timeout=3, versuche=2, urlopen=urlopen) == halter.ANTWORT_PBP
    assert aufrufe == [3, 3]
    # ein eindeutiges Ergebnis wird nicht wiederholt
    aufrufe.clear()

    def abgelehnt(url, timeout):
        aufrufe.append(1)
        raise ConnectionRefusedError()
    assert halter.port_auskunft(1, urlopen=abgelehnt) == halter.ANTWORT_FREMD
    assert len(aufrufe) == 1


def test_a_der_text_bei_keiner_antwort_sagt_nie_kein_pbp():
    for besitzer in (None, pb.unbekannt(8200),
                     {"bekannt": True, "pid": 14552, "name": "python.exe", "ist_eigener_pbp": True,
                      "seit_text": "29.10. 19:23", "unter_claude": True},
                     {"bekannt": True, "pid": 77, "name": "irgendwas.exe", "ist_eigener_pbp": False}):
        text = halter.belegt_text(8200, halter.ANTWORT_KEINE, besitzer)
        assert "kein PBP" not in text and "ANDEREN" not in text and "anderen Programm" not in text, text
        assert "antwortet" in text and "8200" in text
    eigen = halter.belegt_text(8200, halter.ANTWORT_KEINE, {"bekannt": True, "pid": 14552, "name": "python.exe",
                                                            "ist_eigener_pbp": True, "seit_text": "29.10. 19:23"})
    assert "Kennung 14552" in eigen and "seit 29.10. 19:23" in eigen and "hängt" in eigen


def test_a_der_mcp_prozess_setzt_haengt_statt_fremdes_programm(srv, haengt, monkeypatch):
    from unittest.mock import MagicMock
    monkeypatch.setattr(halter, "port_auskunft", SCHNELL)
    fake = {**pb.unbekannt(haengt.port), "bekannt": True, "pid": 4711, "name": "python.exe", "ist_eigener_pbp": True}
    monkeypatch.setattr(pb, "besitzer_von_port", lambda port, **k: fake)
    assert srv.dashboard_im_hintergrund_starten(MagicMock(), haengt.port) is None
    z = halter.lesen()
    assert z["halter"] == halter.HAENGT and z["port"] == haengt.port and z["besitzer"]["pid"] == 4711
    a = halter.beschreiben()
    assert a["art"] == "warnung" and "kein PBP" not in a["meldung"] and "Kennung 4711" in a["meldung"]
    assert "taskkill /PID 4711" in a["loesung"] or "kill 4711" in a["loesung"]


def test_a_der_nachholer_uebernimmt_wenn_der_haengende_port_frei_wird(srv, haengt, monkeypatch):
    from unittest.mock import MagicMock
    monkeypatch.setattr(halter, "port_auskunft", SCHNELL)
    monkeypatch.setattr(pb, "besitzer_von_port", lambda port, **k: pb.unbekannt(port))
    port = haengt.port
    assert srv.dashboard_im_hintergrund_starten(MagicMock(), port) is None
    assert halter.lesen()["halter"] == halter.HAENGT
    gestartet = []
    monkeypatch.setattr(srv, "dashboard_im_hintergrund_starten", lambda db, p=None: gestartet.append(p) or object())
    thread = srv.dashboard_nachholen_starten(MagicMock(), port, intervall_s=0.1)
    try:
        time.sleep(0.5)
        assert gestartet == [], "solange der Port belegt ist, startet nichts"
        haengt.close()
        thread.join(5)
        assert gestartet == [port], "ist der Port frei, uebernimmt der Prozess"
    finally:
        thread.stoppen()


def test_a_ein_fremdes_programm_bleibt_fremdes_programm(srv, http, monkeypatch):
    from unittest.mock import MagicMock
    port = http({"/api/health": (200, "application/json", json.dumps({"status": "ok"}))})
    monkeypatch.setattr(pb, "besitzer_von_port", lambda p, **k: {**pb.unbekannt(p), "bekannt": True, "pid": 9, "name": "x.exe"})
    assert srv.dashboard_im_hintergrund_starten(MagicMock(), port) is None
    z = halter.lesen()
    assert z["halter"] == halter.FREMDES
    meldung = halter.beschreiben()["meldung"]
    assert "anderen Programm" in meldung and "kein PBP" in meldung and "x.exe" in meldung and "Kennung 9" in meldung


def test_a_eine_volle_warteschlange_gilt_als_belegt_nicht_als_frei(tmp_path):
    """Ein haengender Prozess, dessen Warteschlange voll ist, laesst neue Verbindungen in die Zeitgrenze laufen."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]
    offene = []
    try:
        for _ in range(12):                                   # fuellt die Warteschlange, bis Verbindungen haengen bleiben
            c = socket.socket()
            c.settimeout(0.3)
            c.connect_ex(("127.0.0.1", port))
            offene.append(c)
        assert halter.port_belegt(port, timeout=0.5) is True
        assert hilfe.port_frei(port) is False
    finally:
        for c in offene:
            c.close()
        s.close()
    assert halter.port_belegt(_frei(), timeout=5.0) is False
    assert hilfe.port_frei(_frei()) is True


# ── (b) langsam, aber richtig ─────────────────────────────────────────────────

def test_b_eine_langsame_aber_richtige_antwort_gilt_als_pbp(http):
    port = http({"/api/health": (200, "application/json", PBP_JSON)}, verzoegerung=3.0)
    t0 = time.monotonic()
    assert halter.port_auskunft(port) == halter.ANTWORT_PBP
    assert 2.5 < time.monotonic() - t0 < 6


def test_b_die_alte_kurze_pruefung_bleibt_fuer_das_warten_kurz(http, haengt):
    t0 = time.monotonic()
    assert halter.ist_pbp(haengt.port, timeout=0.4) is False
    assert time.monotonic() - t0 < 3
    assert halter.ist_pbp(http({"/api/health": (200, "application/json", PBP_JSON)})) is True


# ── (c) fremd ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("antworten", [
    {"/api/health": (200, "application/json", json.dumps({"status": "ok"}))},       # JSON ohne pbp_version
    {"*": (404, "text/html", "<html>nicht gefunden</html>")},                         # HTTP 404 HTML
    {"*": (200, "text/html", "<html>Startseite</html>")},                             # kein JSON
    {"/api/health": (500, "application/json", json.dumps({"pbp_version": "x"}))},     # Fehlerstatus
], ids=["json_ohne_version", "404_html", "kein_json", "status_500"])
def test_c_eine_fremde_antwort_ist_fremd(http, antworten):
    assert SCHNELL(http(antworten)) == halter.ANTWORT_FREMD


def test_c_sofortiges_zurueckweisen_und_kein_http_sind_fremd():
    # abgelehnt (Windows meldet das erst nach etwa einer Sekunde: die Zeitgrenze muss grosszuegiger sein als im Hangtest)
    assert halter.port_auskunft(_frei(), timeout=5.0, versuche=1) == halter.ANTWORT_FREMD
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(5)
    stop = threading.Event()

    def annehmen():
        s.settimeout(0.2)
        while not stop.is_set():
            try:
                c, _ = s.accept()
                c.sendall(b"220 kein http hier\r\n")
                c.close()
            except OSError:
                pass
    t = threading.Thread(target=annehmen, daemon=True)
    t.start()
    try:
        assert SCHNELL(s.getsockname()[1]) == halter.ANTWORT_FREMD       # spricht etwas anderes
    finally:
        stop.set()
        t.join(2)
        s.close()


def test_c_der_text_bei_fremd_nennt_programm_und_kennung():
    text = halter.belegt_text(8200, halter.ANTWORT_FREMD, {"name": "nginx.exe", "pid": 812})
    assert "ANDEREN Programm" in text and "nginx.exe" in text and "Kennung 812" in text
    assert "Programm benutzt." in halter.belegt_text(8200, halter.ANTWORT_FREMD, None)


# ── (d) Besitzer feststellen ──────────────────────────────────────────────────

NETSTAT = """
Aktive Verbindungen

  Proto  Lokale Adresse         Remoteadresse          Status           PID
  TCP    0.0.0.0:135            0.0.0.0:0              ABHÖREN         1004
  TCP    127.0.0.1:8200         0.0.0.0:0              ABHÖREN         14552
  TCP    127.0.0.1:8200         127.0.0.1:50122        SCHLIESSEN_WARTEN  14552
  TCP    127.0.0.1:50122        127.0.0.1:8200         FIN_WAIT_2      9000
  TCP    [::]:445               [::]:0                 ABHÖREN         4
"""


def test_d_netstat_zeile_mit_uebersetztem_zustand_liefert_die_kennung():
    assert pb.parse_netstat(NETSTAT, 8200) == 14552
    assert pb.parse_netstat(NETSTAT, 445) == 4
    assert pb.parse_netstat(NETSTAT, 9999) is None
    zwei = NETSTAT + "  TCP    0.0.0.0:8200           0.0.0.0:0              LISTENING       777\n"
    assert pb.parse_netstat(zwei, 8200) is None, "zwei verschiedene Halter: nicht raten"


def test_d_lsof_und_ps_lesen():
    assert pb.parse_lsof("p1234\nf5\n") == 1234
    assert pb.parse_lsof("p1\np2\n") is None and pb.parse_lsof("") is None
    d = pb.parse_ps("  777 Thu Oct 29 19:23:27 2026 /opt/pbp/app/python/bin/python3 -m bewerbungs_assistent_boot dashboard")
    assert d["ppid"] == 777 and d["gestartet"] == "2026-10-29 19:23:27"
    assert d["kommandozeile"].endswith("bewerbungs_assistent_boot dashboard")
    assert pb.parse_ps("kaputt") is None


APP_WIN = "C:\\Users\\Łukasz Müller-Şahin\\AppData\\Local\\BewerbungsAssistent\\app"


@pytest.mark.parametrize("zeile,ordner,erwartet", [
    (f'"{APP_WIN}\\python\\python.exe" -m bewerbungs_assistent_boot', [APP_WIN], True),
    (f'{APP_WIN}\\python\\python.exe {APP_WIN}\\start_dashboard.py', [APP_WIN], True),
    (f'"{APP_WIN.upper()}\\python\\PYTHON.EXE" -m bewerbungs_assistent_boot', [APP_WIN], True),     # Gross/klein
    (f'"{APP_WIN.replace(chr(92), "/")}/python/python.exe" -m bewerbungs_assistent_boot', [APP_WIN], True),
    (f'"{APP_WIN}-fremd\\python\\python.exe" -m bewerbungs_assistent_boot', [APP_WIN], False),      # Nachbarordner
    ('C:\\Other\\python.exe -m bewerbungs_assistent_boot', [APP_WIN], False),                        # anderer Ordner
    (f'{APP_WIN}\\python\\python.exe -m http.server 8200', [APP_WIN], False),                        # kein PBP-Marker
    ('', [APP_WIN], False),
    (f'{APP_WIN}\\python\\python.exe -m bewerbungs_assistent_boot', [], False),                       # kein eigener Ordner bekannt
    (f'{APP_WIN}\\python\\python.exe -m bewerbungs_assistent_boot', [""], False),
], ids=["boot_modul", "start_dashboard", "grossschreibung", "schraegstriche", "nachbarordner", "anderer_ordner",
        "kein_marker", "leer", "kein_ordner_bekannt", "leerer_ordner"])
def test_d_eigen_oder_fremd_nach_kommandozeile_und_ordner(zeile, ordner, erwartet):
    assert pb.ist_eigene_kommandozeile(zeile, ordner, plattform="win32") is erwartet


def test_d_unix_pfade_unterscheiden_gross_und_klein():
    assert pb.ist_eigene_kommandozeile("/opt/pbp/python3 -m bewerbungs_assistent_boot", ["/opt/pbp"], "linux")
    assert not pb.ist_eigene_kommandozeile("/opt/PBP/python3 -m bewerbungs_assistent_boot", ["/opt/pbp"], "linux")
    assert not pb.ist_eigene_kommandozeile("/opt/pbp2/python3 -m bewerbungs_assistent_boot", ["/opt/pbp"], "linux")


def _fake_windows(pid_zeile, ps_json):
    """Gefaelschte Hilfsprogramme: netstat liefert `pid_zeile`, PowerShell `ps_json` (oder None)."""
    def ausfuehren(argv, timeout=0, env=None):
        if argv[0] == "netstat":
            return pid_zeile.encode("cp850", errors="replace")
        if argv[0] == "powershell":
            return None if ps_json is None else json.dumps(ps_json, ensure_ascii=False).encode("utf-8")
        return None
    return ausfuehren


def _ps(**kw):
    d = {"name": "python.exe", "cmd": f'"{APP_WIN}\\python\\python.exe" -m bewerbungs_assistent_boot', "ppid": 5000,
         "start": "2026-10-29 19:23:27", "pname": "claude.exe"}
    d.update(kw)
    return d


def test_d_besitzer_eigener_prozess_unter_claude_mit_umlauten_im_pfad():
    b = pb.besitzer_von_port(8200, ausfuehren=_fake_windows(NETSTAT, _ps()), plattform="win32", ordner=[APP_WIN])
    assert b["bekannt"] and b["pid"] == 14552 and b["ist_eigener_pbp"] is True and b["unter_claude"] is True
    assert b["ppid"] == 5000 and b["eltern_name"] == "claude.exe" and b["seit_text"] == "29.10. 19:23"


def test_d_besitzer_eigener_prozess_ohne_claude():
    b = pb.besitzer_von_port(8200, ausfuehren=_fake_windows(NETSTAT, _ps(pname="explorer.exe")), plattform="win32", ordner=[APP_WIN])
    assert b["ist_eigener_pbp"] is True and b["unter_claude"] is False


def test_d_besitzer_fremder_prozess():
    fremd = _ps(name="nginx.exe", cmd="C:\\nginx\\nginx.exe", pname="services.exe")
    b = pb.besitzer_von_port(8200, ausfuehren=_fake_windows(NETSTAT, fremd), plattform="win32", ordner=[APP_WIN])
    assert b["bekannt"] and b["name"] == "nginx.exe" and b["ist_eigener_pbp"] is False


@pytest.mark.parametrize("ausfuehren", [
    lambda *a, **k: None,                                                       # Werkzeug fehlt
    lambda *a, **k: (_ for _ in ()).throw(OSError("kein Recht")),               # wirft
    _fake_windows("nichts Brauchbares", None),                                  # kein Treffer
])
def test_d_jeder_fehler_ist_unbekannt_und_nie_eigen(ausfuehren):
    b = pb.besitzer_von_port(8200, ausfuehren=ausfuehren, plattform="win32", ordner=[APP_WIN])
    assert b["bekannt"] is False and b["ist_eigener_pbp"] is False and b["unter_claude"] is False and b["pid"] is None
    assert hilfe.darf_beenden(b)[0] is False


def test_d_kennung_ohne_details_ist_bekannt_aber_nie_eigen():
    b = pb.besitzer_von_port(8200, ausfuehren=_fake_windows(NETSTAT, None), plattform="win32", ordner=[APP_WIN])
    assert b["bekannt"] and b["pid"] == 14552 and b["ist_eigener_pbp"] is False
    assert hilfe.darf_beenden(b) == (False, "fremd")


def test_d_unix_besitzer_ueber_lsof_und_ps():
    def ausfuehren(argv, timeout=0, env=None):
        if argv[0] == "lsof":
            return b"p321\n"
        if argv[:2] == ["ps", "-o"] and argv[2] == "ppid=,lstart=,command=":
            return b"  100 Thu Oct 29 19:23:27 2026 /opt/pbp/python/bin/python3 -m bewerbungs_assistent_boot\n"
        if argv[2] == "comm=":
            return b"Claude\n"
        return None
    b = pb.besitzer_von_port(8200, ausfuehren=ausfuehren, plattform="linux", ordner=["/opt/pbp"])
    assert b["pid"] == 321 and b["ist_eigener_pbp"] and b["unter_claude"] and b["name"] == "python3"
    assert pb.besitzer_von_port(8200, ausfuehren=lambda *a, **k: None, plattform="linux")["bekannt"] is False


def test_d_eigene_ordner_ist_nie_ein_laufwerk(monkeypatch):
    monkeypatch.delenv("PBP_APP_DIR", raising=False)
    (ordner,) = pb.eigene_ordner()
    assert Path(ordner).parent != Path(ordner), "ein Laufwerk waere jeder Prozess 'eigen'"
    assert Path(ordner).name
    monkeypatch.setenv("PBP_APP_DIR", "X:\\app")
    assert pb.eigene_ordner() == ["X:\\app"]


# ── Hilfsprozess fuer die echten Pruefungen ───────────────────────────────────

HELFER = """\
import os, socket, sys, time
s = socket.socket()
s.bind(("127.0.0.1", 0))
s.listen(5)
open(sys.argv[1], "w").write("%d %d" % (s.getsockname()[1], os.getpid()))
time.sleep(120)
"""


@pytest.fixture()
def eigener_haenger(tmp_path):
    """Ein echter, unsichtbarer Prozess, der einen Port haelt und nie antwortet; seine Kommandozeile liegt im 'Programmordner'."""
    app = tmp_path / "app"
    app.mkdir()
    skript = app / "start_dashboard.py"
    skript.write_text(HELFER, encoding="utf-8")
    datei = tmp_path / "port.txt"
    proc = subprocess.Popen([sys.executable, str(skript), str(datei)], creationflags=OHNE_FENSTER,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if datei.exists() and datei.read_text().count(" "):
                break
            time.sleep(0.1)
        port, pid = (int(x) for x in datei.read_text().split())
        yield {"app": app, "port": port, "pid": pid, "proc": proc}
    finally:
        proc.kill()
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(locals().get("pid", proc.pid)), "/F"], capture_output=True,
                           creationflags=OHNE_FENSTER)
        proc.wait(10)


def _lebt(pid) -> bool:
    if sys.platform == "win32":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, creationflags=OHNE_FENSTER)
        return str(pid).encode() in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@pytest.mark.skipif(sys.platform != "win32" and not any(
    (Path(p) / "lsof").exists() for p in os.environ.get("PATH", "").split(os.pathsep)), reason="braucht netstat/lsof")
def test_d_echter_hilfsprozess_wird_als_eigener_besitzer_erkannt(eigener_haenger):
    h = eigener_haenger
    b = pb.besitzer_von_port(h["port"], ordner=[str(h["app"])])
    assert b["bekannt"] and b["pid"] == h["pid"], b
    assert b["ist_eigener_pbp"] is True and b["unter_claude"] is False
    assert "start_dashboard.py" in b["kommandozeile"] and b["eltern_name"]
    # ein anderer Programmordner: derselbe Prozess ist dann fremd
    fremd = pb.besitzer_von_port(h["port"], ordner=[str(h["app"].parent / "anderer_ordner")])
    assert fremd["pid"] == h["pid"] and fremd["ist_eigener_pbp"] is False


# ── (e) Selbsthilfe ──────────────────────────────────────────────────────────

def _eigen(**kw):
    b = {**pb.unbekannt(8200), "bekannt": True, "pid": 424242, "name": "python.exe", "kommandozeile": "x",
         "ist_eigener_pbp": True, "unter_claude": False, "ppid": 1, "eltern_name": "explorer.exe", "seit_text": "29.10. 19:23"}
    b.update(kw)
    return b


class Welt:
    """Gefaelschte Umgebung fuer `port_pruefen`: ein Port, der erst nach dem Beenden frei wird."""

    def __init__(self, besitzer, auskunft=halter.ANTWORT_KEINE, nur_hart=False, antwort="", terminal=False):
        self.besitzer, self.auskunft, self.nur_hart, self.antwort, self.terminal = besitzer, auskunft, nur_hart, antwort, terminal
        self.beendet, self.ausgabe, self.belegt, self.t, self.gefragt = [], [], True, 0.0, []

    def beende(self, pid, hart):
        self.beendet.append((pid, hart))
        if hart or not self.nur_hart:
            self.belegt = False
        return True

    def _besitzer(self):
        if isinstance(self.besitzer, list):
            return self.besitzer.pop(0) if len(self.besitzer) > 1 else self.besitzer[0]
        return self.besitzer

    def lauf(self, **k):
        def frage(text):
            self.gefragt.append(text)
            if self.antwort is None:
                raise EOFError
            return self.antwort

        def pause(s):
            self.t += s
        return hilfe.port_pruefen(8200, ausgabe=self.ausgabe.append, ist_terminal=self.terminal, frage=frage,
                                  auskunft_von=lambda p: self.auskunft, finde_besitzer=lambda p: self._besitzer(),
                                  beende=self.beende, frei=lambda p: not self.belegt, uhr=lambda: self.t, pause=pause,
                                  hoeflich_s=1.0, frei_s=2.0, **k)

    @property
    def text(self):
        return "\n".join(self.ausgabe)


def test_e_eigener_haengender_prozess_ohne_claude_wird_beendet_und_der_port_wird_frei():
    w = Welt(_eigen())
    assert w.lauf() == hilfe.FREI
    assert w.beendet == [(424242, False)], "erst hoeflich; er ging sofort"


def test_e_erst_hoeflich_dann_hart_und_nur_wenn_dieselbe_kennung_den_port_noch_haelt():
    w = Welt(_eigen(), nur_hart=True)
    assert w.lauf() == hilfe.FREI
    assert w.beendet == [(424242, False), (424242, True)]
    # eine andere Kennung haelt den Port inzwischen: nicht hart zuschlagen
    w = Welt([_eigen(), _eigen(pid=999999)], nur_hart=True)
    w.belegt = True
    w.beende = lambda pid, hart: w.beendet.append((pid, hart)) or True        # der Port bleibt belegt
    assert w.lauf() == hilfe.BELEGT
    assert w.beendet == [(424242, False)], "keine harte Beendigung einer anderen Kennung"


@pytest.mark.parametrize("besitzer,auskunft,grund", [
    (_eigen(ist_eigener_pbp=False, name="nginx.exe"), halter.ANTWORT_KEINE, "fremd, antwortet nicht"),
    (_eigen(ist_eigener_pbp=False), halter.ANTWORT_FREMD, "fremd, antwortet anders"),
    (_eigen(), halter.ANTWORT_FREMD, "eigen, aber der Port antwortet (anders)"),
    (pb.unbekannt(8200), halter.ANTWORT_KEINE, "unbekannt"),
    (_eigen(pid=os.getpid()), halter.ANTWORT_KEINE, "der eigene Prozess"),
    (_eigen(pid=os.getppid()), halter.ANTWORT_KEINE, "der Elternprozess"),
])
def test_e_nie_beendet_wird_fremdes_unbekanntes_oder_der_eigene_prozess(besitzer, auskunft, grund):
    w = Welt(besitzer, auskunft=auskunft)
    assert w.lauf() == hilfe.BELEGT, grund
    assert w.beendet == [], grund
    assert "8200" in w.text


def test_e_fremde_meldung_nennt_programm_und_kennung_und_unbekannt_sagt_unbekannt():
    w = Welt(_eigen(ist_eigener_pbp=False, name="nginx.exe", pid=812), auskunft=halter.ANTWORT_FREMD)
    w.lauf()
    assert "ANDEREN Programm" in w.text and "nginx.exe" in w.text and "Kennung 812" in w.text
    w = Welt(pb.unbekannt(8200), auskunft=halter.ANTWORT_KEINE)
    w.lauf()
    assert "antwortet aber nicht" in w.text and "kein PBP" not in w.text and "ANDEREN" not in w.text


def test_e_kind_von_claude_wird_ohne_terminal_nie_beendet_und_die_meldung_nennt_den_befehl():
    w = Welt(_eigen(unter_claude=True, eltern_name="claude.exe"), terminal=False)
    assert w.lauf() == hilfe.BELEGT
    assert w.beendet == [] and w.gefragt == []
    assert "Kennung 424242" in w.text and ("taskkill /PID 424242" in w.text or "kill 424242" in w.text)
    assert "hängt" in w.text and "verliert" in w.text


@pytest.mark.parametrize("antwort", ["", "n", "nein", "vielleicht", None])
def test_e_kind_von_claude_im_terminal_ohne_ja_wird_nicht_beendet(antwort):
    w = Welt(_eigen(unter_claude=True, eltern_name="claude.exe"), terminal=True, antwort=antwort)
    assert w.lauf() == hilfe.BELEGT
    assert w.beendet == [] and len(w.gefragt) == 1
    assert "[j/N]" in w.gefragt[0] and "verliert Claude die Verbindung" in w.text


def test_e_kind_von_claude_im_terminal_mit_ja_wird_beendet():
    w = Welt(_eigen(unter_claude=True, eltern_name="claude.exe"), terminal=True, antwort="j")
    assert w.lauf() == hilfe.FREI
    assert w.beendet and w.beendet[0] == (424242, False)


def test_e_antwortet_pbp_bleibt_alles_unberuehrt():
    w = Welt(_eigen(), auskunft=halter.ANTWORT_PBP)
    assert w.lauf() == hilfe.PBP and w.beendet == [] and w.ausgabe == []


def test_e_echter_hilfsprozess_wird_beendet_und_der_port_frei(eigener_haenger, monkeypatch):
    h = eigener_haenger
    monkeypatch.setenv("PBP_APP_DIR", str(h["app"]))
    ausgabe = []
    r = hilfe.port_pruefen(h["port"], ausgabe=ausgabe.append, ist_terminal=False, auskunft_von=SCHNELL,
                           hoeflich_s=0.5, frei_s=10.0)
    assert r == hilfe.FREI, "\n".join(ausgabe)
    assert hilfe.port_frei(h["port"])
    h["proc"].wait(10)
    for _ in range(50):
        if not _lebt(h["pid"]):
            break
        time.sleep(0.2)
    assert not _lebt(h["pid"]), "der haengende Hilfsprozess lebt noch"
    assert any("beendet ihn" in z for z in ausgabe)


def test_e_echter_hilfsprozess_aus_einem_fremden_ordner_bleibt_am_leben(eigener_haenger, monkeypatch, tmp_path):
    h = eigener_haenger
    monkeypatch.setenv("PBP_APP_DIR", str(tmp_path / "ganz_anderer_ordner"))
    ausgabe = []
    r = hilfe.port_pruefen(h["port"], ausgabe=ausgabe.append, ist_terminal=False, auskunft_von=SCHNELL,
                           hoeflich_s=0.5, frei_s=1.0)
    assert r == hilfe.BELEGT
    assert _lebt(h["pid"]) and not hilfe.port_frei(h["port"])
    assert "antwortet aber nicht" in "\n".join(ausgabe) and "kein PBP" not in "\n".join(ausgabe)


def test_e_vorfahren_sind_geschuetzt_auch_die_grosseltern():
    """Der Startprogramm-Stub des venv steht zwischen dem Start und dem Prozess, der den Port haelt (Fund der Gegenprobe:
    ein 'immer eigen'-Fehler beendete den Testlauf selbst, weil dessen Kennung ein GROSSelternteil war)."""
    kette = {100: 50, 50: 7, 7: 1}
    assert hilfe.vorfahren(100, ppid_von=kette.get) == {100, 50, 7, 1}
    assert hilfe.vorfahren(100, ppid_von=lambda p: p and 100) == {100}, "Schleifen enden"
    assert hilfe.vorfahren(100, ppid_von=lambda p: 1 / 0) == {100}, "ein Fehler ergibt die Mindestliste, keine Ausnahme"
    echt = hilfe.vorfahren()
    assert os.getpid() in echt and os.getppid() in echt and len(echt) >= 2
    grosseltern = _eigen(pid=50)
    assert hilfe.darf_beenden(grosseltern, eigene_pids={100, 50, 7}) == (False, "eigener_prozess")
    assert hilfe.darf_beenden(_eigen(pid=51), eigene_pids={100, 50, 7}) == (True, "eigener_pbp")


def test_e_beenden_verweigert_systemprozesse_und_sich_selbst():
    assert hilfe.beenden(0, True) is False and hilfe.beenden(4, True) is False
    assert hilfe.beenden(os.getpid(), True) is False


# ── (f) kein falscher Rueckfall ──────────────────────────────────────────────

@pytest.fixture()
def layout(tmp_path, monkeypatch):
    """Ein Programmordner mit 1.8.0 (aktuell) und 1.8.0-rc.4; der Startbaustein-Zaehler sieht jeden Start als 'alt'."""
    from _au_hilfen import programmordner
    app = programmordner(tmp_path, fassungen=("1.8.0-rc.4", "1.8.0"), aktuell="1.8.0")
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    monkeypatch.setattr(boot, "_alter_s", lambda iso: 1000.0)       # die Nachsicht von 90 s ist zwischen den Starts abgelaufen
    return app


def _start(app):
    """So beginnt jeder Start ueber den Startbaustein."""
    return boot.waehle_fassung(app)


def test_f_zwei_und_mehr_starts_am_belegten_port_fuehren_nicht_zum_rueckfall(layout):
    for n in range(6):
        fassung, hinweis = _start(layout)
        assert fassung == "1.8.0", f"Start {n + 1}: {hinweis}"
        assert hinweis is None
        start_ohne_schuld("port_belegt")                                # start_dashboard.py endet am Port
    assert boot.lese_aktuell(layout) == "1.8.0"
    s = boot.lese_status(layout)
    assert "rueckgang" not in s and "gescheitert" not in s
    assert s["start"]["bestaetigt"] is False, "ein Start am Port bestaetigt die Fassung nie"
    assert s["start"]["versuche"] == 1 and s["start"]["ohne_schuld"]["grund"] == "port_belegt"


def test_f_gegenprobe_ohne_die_ruecksetzung_faellt_die_fassung_zurueck(layout):
    ergebnisse = [_start(layout)[0] for _ in range(4)]                  # dieselben Starts, nur ohne start_ohne_schuld
    assert ergebnisse[:2] == ["1.8.0", "1.8.0"] and ergebnisse[2] == "1.8.0-rc.4"
    assert boot.lese_aktuell(layout) == "1.8.0-rc.4"


def test_f_echte_fehlstarts_zaehlen_weiter(layout):
    """Zwei Starts, die vor der Port-Pruefung sterben (Ausnahme), rufen start_ohne_schuld nie: der dritte faellt zurueck."""
    assert _start(layout)[0] == "1.8.0"
    assert _start(layout)[0] == "1.8.0"
    fassung, hinweis = _start(layout)
    assert fassung == "1.8.0-rc.4" and "liess sich nicht starten" in hinweis


def test_f_ein_echter_fehlstart_nach_port_starts_zaehlt_weiter(layout):
    """Der Schutz faengt nur Port-Starts ab: stirbt danach ein Start ohne Aufruf, faellt der naechste zurueck.

    Ein Start am Port laesst den Zaehler auf 1 (wie nach jedem unbestaetigten Start); der echte Fehlstart macht 2, der
    naechste Start sieht 2 und schaltet zurueck. Ohne Port-Starts waeren es zwei echte Fehlstarts (siehe test_f_echte_...).
    """
    _start(layout); start_ohne_schuld("port_belegt")
    _start(layout); start_ohne_schuld("port_belegt")
    assert _start(layout)[0] == "1.8.0"                 # echter Fehlstart: stirbt ohne Aufruf
    fassung, hinweis = _start(layout)
    assert fassung == "1.8.0-rc.4" and "liess sich nicht starten" in hinweis


def test_f_start_ohne_schuld_bestaetigt_nie_und_wirkt_nur_im_startbaustein(layout, monkeypatch):
    _start(layout); _start(layout)
    vorher = boot.lese_status(layout)
    assert start_ohne_schuld("x") is True
    nachher = boot.lese_status(layout)
    assert nachher["start"]["bestaetigt"] is False and nachher.get("bestaetigt") == vorher.get("bestaetigt")
    # eine andere Fassung im Zaehler wird nicht angefasst
    s = boot.lese_status(layout)
    s["start"]["version"] = "1.8.0-rc.4"
    s["start"]["versuche"] = 2
    boot.schreibe_status(layout, s)
    assert start_ohne_schuld("x") is False and boot.lese_status(layout)["start"]["versuche"] == 2
    # ohne Startbaustein (kein PBP_FASSUNG) passiert nichts
    monkeypatch.delenv("PBP_FASSUNG")
    s["start"]["version"] = "1.8.0"
    boot.schreibe_status(layout, s)
    assert start_ohne_schuld("x") is False and boot.lese_status(layout)["start"]["versuche"] == 2
    monkeypatch.delenv("PBP_APP_DIR")
    assert start_ohne_schuld("x") is False


# ── (g) start_dashboard.py als echter Prozess ────────────────────────────────

def _lauf_start_dashboard(tmp_path, port, app, fassung="1.8.0"):
    daten = tmp_path / "daten"
    daten.mkdir(exist_ok=True)
    env = dict(os.environ, BA_DATA_DIR=str(daten), BA_DASHBOARD_PORT=str(port), PYTHONIOENCODING="utf-8",
               PBP_KEIN_BROWSER="1", PBP_APP_DIR=str(app), PBP_FASSUNG=fassung)
    env.pop("BA_EXPERTENMODUS", None)
    r = subprocess.run([sys.executable, str(ROOT / "start_dashboard.py")], env=env, cwd=str(tmp_path),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL, creationflags=OHNE_FENSTER, timeout=180)
    return r, r.stdout + r.stderr


def _status_mit_zwei_versuchen(app):
    boot.schreibe_status(app, {"start": {"version": "1.8.0", "versuche": 2, "bestaetigt": False,
                                          "zeit": "2020-01-01T00:00:00+00:00"}})


def test_g_start_dashboard_am_haengenden_port_meldet_ehrlich_und_zaehlt_nicht(haengt, layout, tmp_path):
    _status_mit_zwei_versuchen(layout)
    r, aus = _lauf_start_dashboard(tmp_path, haengt.port, layout)
    assert r.returncode == 1, aus[-1500:]
    assert f"Port {haengt.port} ist belegt" in aus and "antwortet aber nicht" in aus, aus
    assert "kein PBP" not in aus and "ANDEREN" not in aus
    assert "Kennung" in aus, "Name oder Kennung des Halters stehen in der Meldung"
    s = boot.lese_status(layout)
    assert s["start"]["versuche"] == 1 and s["start"]["bestaetigt"] is False
    assert s["start"]["ohne_schuld"]["grund"] == "port_belegt"
    assert s["start"]["version"] == "1.8.0" and "rueckgang" not in s


def test_g_start_dashboard_bei_laufendem_pbp_endet_mit_null_und_zaehlt_nicht(http, layout, tmp_path):
    _status_mit_zwei_versuchen(layout)
    port = http({"/api/health": (200, "application/json", PBP_JSON)})
    r, aus = _lauf_start_dashboard(tmp_path, port, layout)
    assert r.returncode == 0, aus[-1500:]
    assert "PBP laeuft bereits" in aus
    assert boot.lese_status(layout)["start"]["versuche"] == 1
    assert boot.lese_status(layout)["start"]["ohne_schuld"]["grund"] == "pbp_laeuft_bereits"


def test_g_start_dashboard_am_fremden_port_zaehlt_ebenfalls_nicht(http, layout, tmp_path):
    _status_mit_zwei_versuchen(layout)
    port = http({"*": (404, "text/html", "nicht da")})
    r, aus = _lauf_start_dashboard(tmp_path, port, layout)
    assert r.returncode == 1 and "ANDEREN Programm" in aus
    assert boot.lese_status(layout)["start"]["versuche"] == 1


def test_g_start_dashboard_ruft_beide_schutzstellen_auf():
    """Ein Schutz zaehlt erst, wenn er aufgerufen wird (8c): die Quelle ruft die Pruefung und die Zaehler-Korrektur."""
    quelle = (ROOT / "start_dashboard.py").read_text(encoding="utf-8")
    assert "port_pruefen(port)" in quelle and quelle.count('_ohne_schuld("') == 2
    assert "ist_pbp" not in quelle, "die zweiwertige Frage darf den Start nicht mehr entscheiden"
