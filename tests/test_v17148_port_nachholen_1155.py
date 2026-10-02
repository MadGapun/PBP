"""#1155 — Port 8200 beim Start belegt: der Prozess versuchte es nie wieder.

`dashboard_im_hintergrund_starten` prüft den Port nur beim Start und startet bei
Belegung weder Dashboard noch Planer (richtig, solange die andere Instanz
läuft: so gibt es keinen Doppellauf). Wurde das andere Fenster später
geschlossen (zum Beispiel das eigenständige Dashboard über die Desktop-
Verknüpfung), gab es bis zum Neustart von Claude Desktop weder Dashboard noch
tägliche Sicherung noch geplante Suche — und die Karte "Sicherungen" versprach
weiter "PBP sichert einmal am Tag von selbst".

Hier: ein Nachholer übernimmt Dashboard und Planer, sobald der Port frei wird;
er startet nichts, solange er belegt bleibt, nie doppelt, und `pbp_diagnose`
nennt, wer das Dashboard hält.
"""
import asyncio
import importlib
import inspect
import os
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def server(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="pbp_nachholen1155_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv
    importlib.reload(_srv)
    assert str(tmpdir) in str(_srv.db.db_path), f"DB nicht isoliert: {_srv.db.db_path}"

    import uvicorn
    from bewerbungs_assistent.services import dashboard_halter
    dashboard_halter.zuruecksetzen()

    class FalscherServer:
        """Startet nichts: der Test prueft den Startweg, nicht uvicorn."""
        gestartet = []

        def __init__(self, config):
            self.config = config
            self.should_exit = False

        def run(self):
            FalscherServer.gestartet.append(self.config.port)

    FalscherServer.gestartet = []
    monkeypatch.setattr(uvicorn, "Server", FalscherServer)
    import bewerbungs_assistent.dashboard as dash
    alt = dash._db
    yield _srv, FalscherServer
    dash._db = alt
    dashboard_halter.zuruecksetzen()
    _srv.db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def planer_aufrufe(monkeypatch):
    aufrufe = []
    from bewerbungs_assistent.services import automatik_scheduler
    monkeypatch.setattr(automatik_scheduler, "start_automatik_scheduler",
                        lambda db: aufrufe.append(db))
    return aufrufe


class _Belegt:
    """Etwas, das einen Port belegt: ein anderes PBP-Fenster oder ein fremdes Programm.

    v1.7.149 (#1149): der Prozess unterscheidet beides am Gesundheitstest
    `/api/health`. Ein PBP antwortet dort mit `pbp_version`, ein fremder
    Webserver nicht. Bis v1.7.148 stand hier ein blosser lauschender Socket
    "wie das andere PBP-Fenster" - der gilt jetzt als fremdes Programm.
    """

    def __init__(self, art):
        import json
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                if art == "pbp" and self.path == "/api/health":
                    roh, status = json.dumps({"pbp_version": "1.7.149"}).encode(), 200
                else:
                    roh, status = b"nicht da", 404
                self.send_response(status)
                self.send_header("Content-Length", str(len(roh)))
                self.end_headers()
                self.wfile.write(roh)

            def log_message(self, *args):
                pass

        self._s = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self._s.server_address[1]
        threading.Thread(target=self._s.serve_forever, daemon=True).start()

    def close(self):
        self._s.shutdown()
        self._s.server_close()


def _belegter_port(art="pbp"):
    """Ein Port, auf dem etwas lauscht; `art`: "pbp" (anderes Fenster) oder "fremd"."""
    belegt = _Belegt(art)
    return belegt, belegt.port


ARTEN = [("pbp", "ANDERER"), ("fremd", "FREMDES")]


def _warte(bedingung, sekunden=20.0):
    # Unter Windows braucht ein Verbindungsversuch auf einen freien Port rund
    # zwei Sekunden bis zur Absage; der Nachholer prueft zweimal (er selbst
    # und der Startweg), ein misslungener Versuch kostet also doppelt.
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        if bedingung():
            return True
        time.sleep(0.02)
    return bedingung()


@pytest.mark.parametrize("art,halter", ARTEN)
def test_1155_wird_der_port_frei_uebernimmt_der_prozess_dashboard_und_planer(server, planer_aufrufe, art, halter):
    srv, Falsch = server
    from bewerbungs_assistent.services import dashboard_halter as dh
    belegt, port = _belegter_port(art)
    try:
        assert srv.dashboard_im_hintergrund_starten(srv.db, port=port) is None
        assert dh.lesen()["halter"] == getattr(dh, halter)
        nachholer = srv.dashboard_nachholen_starten(srv.db, port=port, intervall_s=0.05)
        time.sleep(0.3)
        assert planer_aufrufe == [], "solange der Port belegt ist, startet nichts"
    finally:
        belegt.close()                       # das andere Fenster wird geschlossen
    assert _warte(lambda: planer_aufrufe), "Dashboard und Planer wurden nicht uebernommen"
    nachholer.join(timeout=5)
    assert not nachholer.is_alive(), "der Nachholer endet, sobald er uebernommen hat"
    assert planer_aufrufe == [srv.db], "der Planer startet genau einmal"
    assert Falsch.gestartet == [port]
    assert dh.lesen()["halter"] == dh.EIGENER
    assert dh.server() is not None


@pytest.mark.parametrize("art,halter", ARTEN)
def test_1155_solange_der_port_belegt_bleibt_startet_nichts(server, planer_aufrufe, art, halter):
    srv, Falsch = server
    from bewerbungs_assistent.services import dashboard_halter as dh
    belegt, port = _belegter_port(art)
    try:
        srv.dashboard_im_hintergrund_starten(srv.db, port=port)
        nachholer = srv.dashboard_nachholen_starten(srv.db, port=port, intervall_s=0.03)
        time.sleep(0.5)                       # viele Pruefungen
        assert nachholer.is_alive()
        assert planer_aufrufe == []
        assert Falsch.gestartet == []
        assert dh.lesen()["halter"] == getattr(dh, halter)
        assert dh.lesen()["nachhol_versuche"] >= 3, "der Nachholer hat nicht geprueft"
    finally:
        nachholer.stoppen()
        belegt.close()
    nachholer.join(timeout=5)


def test_1155_der_nachholer_stoppt_wenn_der_prozess_das_dashboard_selbst_hat(server, planer_aufrufe):
    srv, Falsch = server
    from bewerbungs_assistent.services import dashboard_halter as dh
    dh.setzen(dh.EIGENER, port=1234)
    nachholer = srv.dashboard_nachholen_starten(srv.db, port=1234, intervall_s=0.03)
    nachholer.join(timeout=5)
    assert not nachholer.is_alive()
    assert planer_aufrufe == [] and Falsch.gestartet == []


def test_1155_ein_misslungener_nachstart_wird_beim_naechsten_mal_wiederholt(server, planer_aufrufe, monkeypatch):
    srv, Falsch = server
    from bewerbungs_assistent.services import dashboard_halter as dh
    versuche = []
    echt = srv.dashboard_im_hintergrund_starten

    def erst_kaputt(datenbank, port=None):
        versuche.append(port)
        if len(versuche) == 1:
            raise RuntimeError("vorlaeufig kaputt")
        return echt(datenbank, port)

    monkeypatch.setattr(srv, "dashboard_im_hintergrund_starten", erst_kaputt)
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    frei = s.getsockname()[1]
    s.close()                                 # frei
    dh.setzen(dh.ANDERER, port=frei)
    nachholer = srv.dashboard_nachholen_starten(srv.db, port=frei, intervall_s=0.05)
    assert _warte(lambda: planer_aufrufe), "nach dem ersten Misserfolg wurde nicht erneut versucht"
    nachholer.join(timeout=5)
    assert len(versuche) >= 2
    assert dh.lesen()["halter"] == dh.EIGENER


def test_1155_der_serverstart_richtet_den_nachholer_bei_belegtem_port_ein():
    """Setzer und Leser: der Weg, den Claude Desktop nimmt, ruft ihn auf."""
    import bewerbungs_assistent.server as srv
    quelle = inspect.getsource(srv.run_server)
    assert "dashboard_nachholen_starten(" in quelle
    assert "if _dashboard_server is None" in quelle
    # Auch ein SPAETER uebernommenes Dashboard muss beim Beenden gestoppt werden.
    assert "dashboard_halter.server()" in quelle


def test_1155_der_nachholer_ist_ein_leerlauf_thread_ohne_pbp_praefix():
    """Die Testsuite wartet auf alle Threads mit 'pbp-' im Namen; ein Dauerlaeufer
    dieses Namens liesse jeden Test 15 Sekunden warten (siehe conftest)."""
    import bewerbungs_assistent.server as srv
    quelle = inspect.getsource(srv.dashboard_nachholen_starten)
    assert 'name="dashboard-nachholen"' in quelle


def test_1155_der_pruefabstand_ist_selten_genug_und_oft_genug():
    import bewerbungs_assistent.server as srv
    assert 60 <= srv.DASHBOARD_NACHHOLEN_S <= 900


# ══ pbp_diagnose nennt den Halter ═════════════════════════════════════

def _diagnose(srv):
    async def _run():
        tool = await srv.mcp.get_tool("pbp_diagnose")
        res = await tool.run({})
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def test_1155_pbp_diagnose_nennt_ein_anderes_fenster_als_halter(server):
    srv, _ = server
    from bewerbungs_assistent.services import dashboard_halter as dh
    dh.setzen(dh.ANDERER, port=8200)
    dh.pruefintervall_merken(300)
    antwort = _diagnose(srv)
    texte = [i["meldung"] for i in antwort.get("info", []) if i.get("bereich") == "Dashboard"]
    assert texte, antwort
    assert "anderen PBP-Fenster" in texte[0]
    assert "5 Minuten" in texte[0]


def test_1155_pbp_diagnose_nennt_den_eigenen_prozess(server):
    srv, _ = server
    from bewerbungs_assistent.services import dashboard_halter as dh
    dh.setzen(dh.EIGENER, port=8200)
    antwort = _diagnose(srv)
    texte = [i["meldung"] for i in antwort.get("info", []) if i.get("bereich") == "Dashboard"]
    assert texte and "in diesem Prozess" in texte[0]


def test_1155_pbp_diagnose_warnt_wenn_das_dashboard_nirgends_laeuft(server):
    srv, _ = server
    from bewerbungs_assistent.services import dashboard_halter as dh
    dh.setzen(dh.KEINER, fehler="Port gesperrt")
    antwort = _diagnose(srv)
    warnungen = [w for w in antwort.get("warnungen", []) if w.get("bereich") == "Dashboard"]
    assert warnungen and "Port gesperrt" in warnungen[0]["problem"]


def test_1155_pbp_diagnose_schweigt_solange_nichts_entschieden_ist(server):
    """Ohne Serverstart (Tests, andere Wege) gibt es nichts zu sagen."""
    srv, _ = server
    antwort = _diagnose(srv)
    bereiche = [i.get("bereich") for i in antwort.get("info", [])]
    assert "Dashboard" not in bereiche


def test_1155_der_stand_haelt_keinen_prozess_fest(server):
    """`lesen()` gibt das Server-Objekt nicht heraus (es ginge in JSON-Antworten)."""
    from bewerbungs_assistent.services import dashboard_halter as dh
    dh.setzen(dh.EIGENER, port=1, server=object())
    assert "server" not in dh.lesen()
    assert dh.server() is not None
