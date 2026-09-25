"""Tests fuer v1.7.129 — #1086: Ollama beenden.

Nutzerwunsch vom 25.09.2026: Ollama belegt Arbeitsspeicher, auch wenn
PBP stundenlang nicht mehr benutzt wird. Drei Wege: Knopf, Desktop-
Verknuepfung, Einstellung "beim Beenden von PBP". Beendet wird hier nie
ein echter Prozess — `subprocess.run` ist ersetzt.
"""
import importlib
import logging
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import ollama_start  # noqa: E402


@pytest.fixture
def db(tmp_path):
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = str(tmp_path / "daten")
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Muster Person"})
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt


class _Ergebnis:
    def __init__(self, code=0, stdout=""):
        self.returncode = code
        self.stdout = stdout
        self.stderr = ""


@pytest.fixture
def aufrufe(monkeypatch):
    """Ersetzt subprocess.run; die Rueckgabe steuert `codes` je Name."""
    liste = []
    codes = {}

    def _run(befehl, **kw):
        liste.append(list(befehl))
        name = befehl[-1]
        return _Ergebnis(codes.get(name, 0))

    monkeypatch.setattr(ollama_start.subprocess, "run", _run)
    monkeypatch.setattr(ollama_start, "_systemdienst_aktiv", lambda: False)
    monkeypatch.setattr(ollama_start, "_von_pbp_gestartet", None)
    monkeypatch.setattr(ollama_start, "_beim_beenden_gelaufen", False)
    return liste, codes


# --- Einstellung -----------------------------------------------------------

def test_vorgabe_ist_aus_und_beenden_tut_nichts(db, aufrufe):
    liste, _ = aufrufe
    assert ollama_start.autostop_lesen(db)["beim_beenden"] == "aus"
    assert ollama_start.beim_beenden(db)["status"] == "abgeschaltet"
    assert liste == []


def test_immer_nur_mit_bestaetigung(db):
    antwort = ollama_start.autostop_setzen(db, "immer")
    assert antwort["status"] == "rueckfrage"
    assert ollama_start.autostop_lesen(db)["beim_beenden"] == "aus"
    antwort = ollama_start.autostop_setzen(db, "immer", bestaetigt=True)
    assert antwort["beim_beenden"] == "immer"


def test_unbekannter_wert_wird_abgewiesen(db):
    assert "fehler" in ollama_start.autostop_setzen(db, "manchmal")
    db.set_profile_setting(ollama_start.AUTOSTOP_SCHLUESSEL, "manchmal")
    assert ollama_start.autostop_lesen(db)["beim_beenden"] == "aus"


def test_gestartet_laesst_fremdes_ollama_stehen(db, aufrufe):
    liste, _ = aufrufe
    ollama_start.autostop_setzen(db, "gestartet")
    assert ollama_start.beim_beenden(db)["status"] == "nicht_von_pbp"
    assert liste == []


def test_gestartet_beendet_das_von_pbp_gestartete(db, aufrufe, monkeypatch):
    liste, _ = aufrufe

    class _Prozess:
        pid = 4711

    class _Stand:
        ollama_available = False
        ollama_endpoint = "http://localhost:11434"

    class _Dienst:
        def get_status(self, force_refresh=False):
            return _Stand()

    from bewerbungs_assistent.services import llm_service
    monkeypatch.setattr(llm_service, "get_llm_service", lambda db: _Dienst())
    monkeypatch.setattr(ollama_start, "binary_finden", lambda: "ollama")
    monkeypatch.setattr(ollama_start.subprocess, "Popen", lambda *a, **k: _Prozess())
    assert ollama_start.ollama_starten(db)["status"] == "gestartet"

    ollama_start.autostop_setzen(db, "gestartet")
    assert ollama_start.beim_beenden(db)["status"] == "beendet"
    assert liste
    assert ollama_start._von_pbp_gestartet is None


def test_beim_beenden_laeuft_nur_einmal(db, aufrufe):
    liste, _ = aufrufe
    ollama_start.autostop_setzen(db, "immer", bestaetigt=True)
    ollama_start.beim_beenden(db)
    anzahl = len(liste)
    assert ollama_start.beim_beenden(db)["status"] == "schon_gelaufen"
    assert len(liste) == anzahl


# --- Beenden selbst --------------------------------------------------------

def test_windows_beendet_erst_die_tray_app(aufrufe, monkeypatch):
    liste, _ = aufrufe
    monkeypatch.setattr(ollama_start.sys, "platform", "win32")
    ergebnis = ollama_start.ollama_beenden()
    assert ergebnis["status"] == "beendet"
    namen = [b[-1] for b in liste]
    assert namen == ["ollama app.exe", "ollama.exe"]
    assert all(b[0] == "taskkill" for b in liste)


def test_lief_nicht_wird_benannt(aufrufe, monkeypatch):
    liste, codes = aufrufe
    monkeypatch.setattr(ollama_start.sys, "platform", "win32")
    codes.update({"ollama app.exe": 128, "ollama.exe": 128})
    assert ollama_start.ollama_beenden()["status"] == "lief_nicht"


def test_systemdienst_wird_benannt_statt_still_nicht_beendet(aufrufe, monkeypatch):
    liste, _ = aufrufe
    monkeypatch.setattr(ollama_start, "_systemdienst_aktiv", lambda: True)
    ergebnis = ollama_start.ollama_beenden()
    assert ergebnis["status"] == "systemdienst"
    assert "systemctl" in ergebnis["hinweis"]
    assert liste == []


# --- Desktop-Verknuepfung --------------------------------------------------

def test_windows_skript_fragt_und_hat_keine_klammerbloecke():
    skript = ollama_start.WINDOWS_SKRIPT
    skript.encode("ascii")                      # Konsolen-Codepage
    assert "\r\n" in skript
    assert "choice /C JN" in skript
    assert skript.index("ollama app.exe") < skript.index('"ollama.exe"')
    # #990: eine Klammer in einem Block beendet ihn — hier gibt es keinen.
    assert not re.search(r"\)\s*$|^\s*\(|\s\($", skript, re.M)


def test_verknuepfung_unter_unix(tmp_path, monkeypatch):
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path / "daten"))
    monkeypatch.setattr(ollama_start.sys, "platform", "linux")
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    ergebnis = ollama_start.verknuepfung_anlegen(desktop)
    assert ergebnis["status"] == "angelegt"
    inhalt = Path(ergebnis["verknuepfung"]).read_text(encoding="utf-8")
    assert "read antwort" in inhalt and "pkill" in inhalt


def test_verknuepfung_unter_windows(tmp_path, monkeypatch):
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path / "daten"))
    monkeypatch.setattr(ollama_start.sys, "platform", "win32")
    monkeypatch.setattr(ollama_start, "binary_finden", lambda: None)
    desktop = tmp_path / "Desktop"
    desktop.mkdir()

    def _run(befehl, **kw):
        Path(kw["env"]["PBP_LNK"]).write_bytes(b"lnk")
        assert kw["env"]["PBP_ZIEL"].endswith("ollama_beenden.bat")
        return _Ergebnis(0)

    monkeypatch.setattr(ollama_start.subprocess, "run", _run)
    ergebnis = ollama_start.verknuepfung_anlegen(desktop)
    assert ergebnis["status"] == "angelegt"
    assert Path(ergebnis["skript"]).read_bytes() == ollama_start.WINDOWS_SKRIPT.encode("ascii")
    assert str(tmp_path / "daten") in ergebnis["skript"]


# --- MCP und REST ----------------------------------------------------------

def _werkzeuge(db):
    from bewerbungs_assistent.tools import analyse as modul
    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

        def prompt(self, *a, **kw):
            return self.tool()

    modul.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt


def test_werkzeug_jetzt_nur_mit_bestaetigung(db, aufrufe):
    liste, _ = aufrufe
    werkzeug = _werkzeuge(db)["ollama_beenden"]
    assert werkzeug(aktion="jetzt")["status"] == "rueckfrage"
    assert liste == []
    assert werkzeug(aktion="beim_pbp_ende", wert="immer")["status"] == "rueckfrage"
    assert werkzeug(aktion="beim_pbp_ende", wert="gestartet")["beim_beenden"] == "gestartet"


@pytest.fixture
def rest(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    datenbank = Database(db_path=tmp_path / "test.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path)
    import bewerbungs_assistent.dashboard as dash
    dash._db = datenbank
    from fastapi.testclient import TestClient
    with TestClient(dash.app) as klient:
        yield klient, datenbank
    os.environ.pop("BA_DATA_DIR", None)


def test_rest_stop_verlangt_bestaetigung(rest, aufrufe):
    klient, _ = rest
    liste, _ = aufrufe
    assert klient.post("/api/llm/stop", json={}).status_code == 400
    assert liste == []
    antwort = klient.post("/api/llm/stop", json={"bestaetigt": True}).json()
    assert antwort["status"] == "beendet"


def test_rest_autostop(rest):
    klient, datenbank = rest
    assert klient.get("/api/llm/autostop").json()["beim_beenden"] == "aus"
    assert klient.put("/api/llm/autostop", json={"wert": "immer"}).json()["status"] == "rueckfrage"
    assert klient.put("/api/llm/autostop",
                      json={"wert": "immer", "bestaetigt": True}).json()["beim_beenden"] == "immer"
    assert klient.put("/api/llm/autostop", json={"wert": "x"}).status_code == 400


# --- Beide Startwege rufen beim Beenden ------------------------------------

def test_mcp_weg_beendet_vor_dem_schliessen_der_datenbank():
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "server.py").read_text(encoding="utf-8")
    rumpf = quelle[quelle.index("def _cleanup():"):quelle.index("atexit.register(_cleanup)")]
    assert "ollama_start.beim_beenden(db)" in rumpf
    # der Aufruf, nicht der Kommentar, der ihn erklaert
    assert rumpf.index("ollama_start.beim_beenden(db)") < rumpf.index("\n            db.close()")


def test_dashboard_weg_beendet_nach_uvicorn():
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "dashboard.py").read_text(encoding="utf-8-sig")
    rumpf = quelle[quelle.index("def start_dashboard("):]
    rumpf = rumpf[:rumpf.index("\ndef ")]
    assert "atexit.register(_ollama_start.beim_beenden" in rumpf
    assert rumpf.index("uvicorn.run(") < rumpf.rindex("_ollama_start.beim_beenden(db_instance)")


def test_oberflaeche_hat_knopf_auswahl_und_verknuepfung():
    quelle = (_repo() / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    block = quelle[quelle.index("function OllamaBeendenBlock"):quelle.index("function LocalAITab")]
    assert '"/api/llm/stop"' in block and "bestaetigt: true" in block
    # Jede Rueckfrage in IHRER Funktion und vor dem Aufruf — "confirm"
    # steht zweimal im Block, ein Wort-Guard saehe eine fehlende nicht.
    jetzt = block[block.index("async function jetztBeenden"):block.index("async function verknuepfung")]
    # G67 (#1087 H5): der eigene Dialog statt window.confirm.
    assert jetzt.index("if (!(await bestaetigen(") < jetzt.index('postJson("/api/llm/stop"')
    setzen = block[block.index("async function setzen"):block.index("async function jetztBeenden")]
    assert setzen.index("if (!(await bestaetigen(") < setzen.index('putJson("/api/llm/autostop"')
    assert '"/api/llm/stop-verknuepfung"' in block
    for wert in ("aus", "gestartet", "immer"):
        assert f'value="{wert}"' in block
    assert quelle.count("<OllamaBeendenBlock pushToast={pushToast} />") == 2
