"""v1.7.146 — Die Hintergrund-Automatik startet auch im Weg über Claude Desktop (#1138).

Befund (01.10.2026, Prüfung "Zeit und Zwischenspeicher"): `run_server`, der
Weg, den Claude Desktop nimmt, startete das Dashboard in einem Thread und
keinen Planer. `start_automatik_scheduler` hatte genau einen Aufrufer,
`dashboard.start_dashboard`, also nur das eigenständige Dashboard. Die Karte
"Sicherungen" versprach "PBP sichert einmal am Tag von selbst", und es
geschah nichts; eine eingestellte Automatik-Jobsuche oder ein eingestelltes
Lernen liefen nie.

Hier: der Startweg ruft den Planer (und nur wenn er das Dashboard wirklich
hostet), ein Fehler des Planers verhindert den Serverstart nicht, und jeder
Weg, der das Dashboard startet, startet auch den Planer (Setzer und Leser).
"""
import importlib
import inspect
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def server(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="pbp_planer1138_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv
    importlib.reload(_srv)
    assert str(tmpdir) in str(_srv.db.db_path), f"DB nicht isoliert: {_srv.db.db_path}"

    import uvicorn

    class FalscherServer:
        """Startet nichts: der Test prueft den Startweg, nicht uvicorn."""

        def __init__(self, config):
            self.config = config
            self.should_exit = False
            self.gelaufen = False

        def run(self):
            self.gelaufen = True

    monkeypatch.setattr(uvicorn, "Server", FalscherServer)
    import bewerbungs_assistent.dashboard as dash
    alt = dash._db
    yield _srv
    dash._db = alt
    _srv.db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _freier_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def planer_aufrufe(monkeypatch):
    aufrufe = []
    from bewerbungs_assistent.services import automatik_scheduler
    monkeypatch.setattr(automatik_scheduler, "start_automatik_scheduler",
                        lambda db: aufrufe.append(db))
    return aufrufe


def test_der_startweg_von_claude_desktop_startet_den_planer(server, planer_aufrufe):
    dashboard = server.dashboard_im_hintergrund_starten(server.db, port=_freier_port())
    assert dashboard is not None
    assert planer_aufrufe == [server.db], "der Planer wurde nicht (genau einmal) gestartet"


def test_bei_belegtem_port_startet_kein_zweiter_planer(server, planer_aufrufe):
    """Dort läuft eine andere Instanz mit dem Dashboard, und die hat den Planer."""
    with socket.socket() as belegt:
        belegt.bind(("127.0.0.1", 0))
        belegt.listen(1)
        port = belegt.getsockname()[1]
        assert server.dashboard_im_hintergrund_starten(server.db, port=port) is None
    assert planer_aufrufe == []


def test_ein_fehler_des_planers_verhindert_den_serverstart_nicht(server, monkeypatch):
    from bewerbungs_assistent.services import automatik_scheduler

    def kaputt(db):
        raise RuntimeError("Planer kaputt")

    monkeypatch.setattr(automatik_scheduler, "start_automatik_scheduler", kaputt)
    assert server.dashboard_im_hintergrund_starten(server.db, port=_freier_port()) is not None


def test_run_server_nimmt_diesen_startweg(server):
    """Setzer und Leser: der Weg, den Claude Desktop nimmt, ruft die Funktion auf."""
    quelle = inspect.getsource(server.run_server)
    assert "dashboard_im_hintergrund_starten(" in quelle


def test_jeder_weg_der_das_dashboard_startet_startet_den_planer(server):
    """Es gibt genau zwei Startwege (uvicorn.run/Server); beide starten den Planer."""
    import bewerbungs_assistent.dashboard as dash
    # der AUFRUF zaehlt, nicht der Import: "start_automatik_scheduler(" mit Klammer
    assert "start_automatik_scheduler(" in inspect.getsource(dash.start_dashboard)
    assert "start_automatik_scheduler(" in inspect.getsource(server.dashboard_im_hintergrund_starten)
    paket = ROOT / "src" / "bewerbungs_assistent"
    startwege = sorted(
        p.relative_to(paket).as_posix() for p in paket.rglob("*.py")
        if "uvicorn.run(" in p.read_text(encoding="utf-8-sig")
        or "uvicorn.Server(" in p.read_text(encoding="utf-8-sig"))
    assert startwege == ["dashboard.py", "server.py"], (
        "Ein neuer Weg startet ein uvicorn: er muss auch den Planer starten "
        f"(und hier eingetragen werden): {startwege}")
