"""Tests fuer v1.7.58 — #1001: Ollama mit PBP starten.

Nutzerwunsch vom 09.09.2026:

    "Ich moechte die Option haben, dass ich Ollama automatisch mit PBP
    starte."

Der Knopf gab es seit #637; was fehlte, war der Weg OHNE Knopfdruck.
Nach einem Neustart des Rechners stand die lokale KI auf "nicht
erreichbar", bis jemand das Dashboard oeffnet — waehrend die
Hintergrund-Aufgaben (Auto-Aussortierung, Lernlauf) laengst liefen.

Was diese Datei absichert, in der Reihenfolge der Akzeptanzkriterien:

* Die **Vorgabe ist AUS**. Einen fremden Prozess ungefragt zu starten
  ist eine Nebenwirkung, die niemand bestellt hat.
* Die Einstellung liegt **am Profil**, nicht im Browser — PBP startet
  haeufig ueber Claude Desktop, wo niemand das Dashboard sieht.
* **Eine Start-Logik, drei Aufrufer.** Der Guard zaehlt die Fundstellen
  nicht ab, er prueft, dass der Endpunkt keine EIGENE Fassung mehr
  haelt und dass beide Startwege dieselbe Funktion rufen. Eine zweite
  Fassung waere das Muster aus #963/#991/#992 zum achten Mal.
* **Der Startpfad von PBP darf nie warten und nie brechen** — ein
  fehlendes Ollama ist kein Grund, PBP nicht hochzufahren.
* **Fuenf Ausgaenge statt zwei.** `abgeschaltet`, `lokale_ki_aus`,
  `lief_bereits`, `gestartet`, `nicht_installiert` verlangen
  verschiedene naechste Schritte; sie zu einer Absage zu verschmelzen
  waere der Fehler aus #989.
"""
import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import ollama_start  # noqa: E402


def ohne_kommentare(text: str) -> str:
    """Kommentare und Docstrings raus.

    Ohne das prueft ein Quelltext-Guard die Erklaerung mit, warum etwas
    nicht mehr dasteht — und schlaegt an ihr an. Dieselbe Lehre wie bei
    #993, #998 und v1.7.31 MERKE (6).
    """
    ohne_docstrings = re.sub(r'"""[\s\S]*?"""', "", text)
    return "\n".join(z for z in ohne_docstrings.split("\n")
                     if not z.strip().startswith("#"))


@pytest.fixture
def db():
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_ollama_autostart_")
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = tmpdir
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Muster Person"})
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt
        shutil.rmtree(tmpdir, ignore_errors=True)


# -- AK 1: Vorgabe AUS ------------------------------------------------

def test_1001_vorgabe_ist_aus(db):
    """Ein frisches Profil startet nichts.

    Das ist die wichtigste Zusicherung der ganzen Aenderung: wer nichts
    einstellt, bemerkt sie nicht.
    """
    assert ollama_start.VORGABE is False
    assert ollama_start.autostart_gewuenscht(db) is False
    assert ollama_start.beim_start(db)["status"] == "abgeschaltet"


def test_1001_ein_kaputter_wert_faellt_auf_die_vorgabe(db):
    """Ein unlesbarer Wert darf nicht als "an" durchgehen — die sichere
    Richtung ist hier eindeutig."""
    db.set_profile_setting(ollama_start.AUTOSTART_SCHLUESSEL, "vielleicht")
    assert ollama_start.autostart_gewuenscht(db) is False


# -- AK 2: am Profil, nicht im Browser --------------------------------

def test_1001_einstellung_liegt_in_den_profil_einstellungen(db):
    """Sie muss auch gelten, wenn PBP ueber Claude Desktop startet und
    niemand das Dashboard oeffnet."""
    ollama_start.autostart_setzen(db, True)
    assert db.get_profile_setting(ollama_start.AUTOSTART_SCHLUESSEL) == "true"
    ollama_start.autostart_setzen(db, False)
    assert db.get_profile_setting(ollama_start.AUTOSTART_SCHLUESSEL) == "false"


def test_1001_schluessel_gehoert_zur_familie_der_lokalen_ki(db):
    """`llm_local_state`, `llm_local_model`, `llm_local_autostart` — wer
    die lokale KI sucht, findet alle drei nebeneinander."""
    assert ollama_start.AUTOSTART_SCHLUESSEL.startswith("llm_local_")


# -- AK 5/6: die Torfrage, benannt statt verschmolzen -----------------

@pytest.mark.parametrize("autostart,zustand,erwartet", [
    (False, "active", "abgeschaltet"),
    (False, "off", "abgeschaltet"),
    (True, "off", "lokale_ki_aus"),
    (True, "paused", "lokale_ki_aus"),
    (True, "active", "bereit"),
])
def test_1001_torfrage_unterscheidet_die_faelle(autostart, zustand, erwartet):
    """Drei Sachverhalte, drei Namen.

    "Autostart aus" und "lokale KI aus" fuehren beide dazu, dass nichts
    startet — sie bedeuten aber Verschiedenes und verlangen verschiedene
    naechste Schritte. Ein gemeinsames "nein" waere #989.
    """
    ja, status, begruendung = ollama_start.darf_starten(autostart, zustand)
    assert status == erwartet
    assert ja is (erwartet == "bereit")
    assert begruendung.strip()


def test_1001_die_torfrage_braucht_weder_datenbank_noch_netz():
    """Sie ist eine reine Funktion — deshalb ist sie ueberhaupt
    vollstaendig pruefbar."""
    import inspect
    parameter = list(inspect.signature(ollama_start.darf_starten).parameters)
    assert parameter == ["autostart", "zustand"]


def test_1001_wirkungslose_einstellung_wird_benannt(db):
    """Wer den Autostart bei abgeschalteter lokaler KI setzt, bekommt das
    gesagt.

    Eine Einstellung, die stillschweigend nichts tut, ist der Fehler aus
    #988 — dort glaubte der Nutzer an eine Schwelle von 35, die bei 0 lag.
    """
    db.set_profile_setting("llm_local_state", "paused")
    antwort = ollama_start.autostart_setzen(db, True)
    assert antwort["autostart"] is True
    assert antwort["wirkung"] == "lokale_ki_aus"
    assert "paused" in antwort["hinweis"]


def test_1001_lesen_und_setzen_antworten_in_derselben_form(db):
    """Sonst muss jeder Aufrufer zwei Formen kennen."""
    gesetzt = ollama_start.autostart_setzen(db, True)
    gelesen = ollama_start.autostart_lesen(db)
    assert set(gelesen) <= set(gesetzt)
    assert gelesen["autostart"] == gesetzt["autostart"]
    assert gelesen["wirkung"] == gesetzt["wirkung"]


# -- AK 3: EINE Start-Logik, drei Aufrufer ----------------------------

def test_1001_der_endpunkt_haelt_keine_eigene_startfassung_mehr():
    """Der Kern des Akzeptanzkriteriums.

    Vor #1001 stand die Spawn-Logik inline in `api_llm_start`. Waere sie
    dort geblieben, haetten Autostart und Knopf zwei Fassungen von
    Binary-Suche und Detach-Flags — und die laufen mit Sicherheit
    auseinander (#963/#991/#992).
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent"
              / "dashboard.py").read_text(encoding="utf-8-sig")
    start = quelle.index('@app.post("/api/llm/start")')
    rumpf = ohne_kommentare(quelle[start:quelle.index("@app.", start + 10)])
    assert "ollama_start.ollama_starten" in rumpf
    assert "subprocess.Popen" not in rumpf
    assert '"serve"' not in rumpf


def test_1001_beide_startwege_rufen_dieselbe_stelle():
    """Der MCP-Weg (server.py) und der Dashboard-Weg
    (dashboard.start_dashboard) muessen BEIDE anstossen.

    Wer PBP ueber Claude Desktop startet, oeffnet das Dashboard oft nie —
    genau dann soll der Autostart wirken. Dieselbe Zusicherung wie bei
    der Score-Verteilung in #986: eine Rechnung, festgehaltene Aufrufer.
    """
    basis = _repo() / "src" / "bewerbungs_assistent"
    server = ohne_kommentare(
        (basis / "server.py").read_text(encoding="utf-8-sig"))
    assert "ollama_start.beim_start(db)" in server

    dashboard = (basis / "dashboard.py").read_text(encoding="utf-8-sig")
    rumpf = ohne_kommentare(dashboard[dashboard.index("def start_dashboard("):])
    assert "ollama_start.beim_start(" in rumpf


# -- AK 4: der Startpfad wartet nicht und bricht nicht ----------------

def test_1001_beim_start_bricht_nicht_an_einer_kaputten_datenbank():
    """Ein fehlendes Ollama oder eine stolpernde Einstellung darf PBP
    nicht am Hochfahren hindern."""
    class _KaputteDB:
        def get_profile_setting(self, *a, **kw):
            raise RuntimeError("DB kaputt")

    assert ollama_start.beim_start(_KaputteDB())["status"] == "abgeschaltet"


def test_1001_beim_start_startet_im_hintergrund(db, monkeypatch):
    """Der Aufruf kehrt zurueck, ohne auf Ollama zu warten — der
    Statuscheck ist eine Netzabfrage und haette im Startpfad nichts zu
    suchen."""
    db.set_profile_setting("llm_local_state", "active")
    ollama_start.autostart_setzen(db, True)
    monkeypatch.setattr(ollama_start, "_autostart_thread", None)

    gestartet = {}

    def _falscher_start(_db):
        gestartet["ja"] = True
        return {"status": "gestartet", "pid": 4711}

    monkeypatch.setattr(ollama_start, "ollama_starten", _falscher_start)
    antwort = ollama_start.beim_start(db)
    assert antwort["status"] == "wird_versucht"
    ollama_start._autostart_thread.join(timeout=5)
    assert gestartet.get("ja") is True


# -- Die Start-Logik selbst -------------------------------------------

def test_1001_lief_bereits_ist_kein_fehler(db, monkeypatch):
    """Ollama laeuft schon — nichts zu tun, und das ist ein eigener
    Ausgang."""
    class _Stand:
        ollama_available = True
        ollama_endpoint = "http://localhost:11434"

    class _Dienst:
        def get_status(self, force_refresh=False):
            return _Stand()

    monkeypatch.setattr(
        "bewerbungs_assistent.services.llm_service.get_llm_service",
        lambda _db: _Dienst())
    ergebnis = ollama_start.ollama_starten(db)
    assert ergebnis["status"] == "lief_bereits"


def _ollama_aus(monkeypatch):
    class _Stand:
        ollama_available = False
        ollama_endpoint = "http://localhost:11434"

    class _Dienst:
        def get_status(self, force_refresh=False):
            return _Stand()

    monkeypatch.setattr(
        "bewerbungs_assistent.services.llm_service.get_llm_service",
        lambda _db: _Dienst())


def test_1001_ohne_binary_kommt_nicht_installiert(db, monkeypatch):
    """"Nicht gefunden" wird benannt und traegt den Weg zur Loesung."""
    _ollama_aus(monkeypatch)
    monkeypatch.setattr(ollama_start, "binary_finden", lambda: None)
    ergebnis = ollama_start.ollama_starten(db)
    assert ergebnis["status"] == "nicht_installiert"
    assert "ollama.com/download" in ergebnis["hilfe_url"]


def test_1001_start_ist_losgeloest(db, monkeypatch):
    """Endet PBP, laeuft Ollama weiter.

    Andersherum verschwaende ein Modell mitten in einem Lauf — und der
    Nutzer haette einen Dienst, der mit dem Schliessen eines Fensters
    verschwindet.
    """
    _ollama_aus(monkeypatch)
    monkeypatch.setattr(ollama_start, "binary_finden", lambda: "/pfad/ollama")
    aufruf = {}

    class _Prozess:
        pid = 1234

    def _popen(befehl, **kwargs):
        aufruf["befehl"] = befehl
        aufruf["kwargs"] = kwargs
        return _Prozess()

    monkeypatch.setattr(subprocess, "Popen", _popen)
    ergebnis = ollama_start.ollama_starten(db)

    assert ergebnis["status"] == "gestartet"
    assert ergebnis["pid"] == 1234
    assert aufruf["befehl"] == ["/pfad/ollama", "serve"]
    if sys.platform == "win32":
        # DETACHED_PROCESS muss gesetzt sein
        assert aufruf["kwargs"]["creationflags"] & 0x00000008
    else:
        assert aufruf["kwargs"]["start_new_session"] is True


def test_1001_ein_spawn_fehler_wird_gemeldet_statt_geworfen(db, monkeypatch):
    """Ein Fehler beim Start ist eine Antwort, kein Absturz."""
    _ollama_aus(monkeypatch)
    monkeypatch.setattr(ollama_start, "binary_finden", lambda: "/pfad/ollama")

    def _popen(befehl, **kwargs):
        raise OSError("kein Speicher")

    monkeypatch.setattr(subprocess, "Popen", _popen)
    ergebnis = ollama_start.ollama_starten(db)
    assert ergebnis["status"] == "fehler"
    assert "kein Speicher" in ergebnis["fehler"]


def test_1001_binary_wird_auch_ausserhalb_des_pfads_gefunden(monkeypatch):
    """Der PATH allein genuegt nicht.

    Startet PBP als MCP-Server, erbt es die Umgebung von Claude Desktop —
    und die ist nicht die der Anmelde-Shell. Ein `which`-Fehlschlag
    duerfte dort nicht als "nicht installiert" durchgehen; das waere
    dieselbe Verwechslung wie in #989.
    """
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(ollama_start, "_bekannte_orte",
                        lambda: [str(_repo() / "README.md")])
    assert ollama_start.binary_finden() == str(_repo() / "README.md")


def test_1001_kein_binary_heisst_none(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(ollama_start, "_bekannte_orte",
                        lambda: ["/gibt/es/nicht/ollama"])
    assert ollama_start.binary_finden() is None


# -- AK 8: ueber Claude bedienbar -------------------------------------

def _tool_holen(db, name):
    import logging
    from bewerbungs_assistent.tools import analyse as analyse_tools

    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    analyse_tools.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt[name]


def test_1001_mcp_tool_liest_und_setzt(db):
    """Ueber Claude bedienbar, nicht nur ueber das Dashboard."""
    werkzeug = _tool_holen(db, "ollama_autostart")

    assert werkzeug()["autostart"] is False
    assert werkzeug("an")["autostart"] is True
    assert ollama_start.autostart_gewuenscht(db) is True
    assert werkzeug("aus")["autostart"] is False
    assert ollama_start.autostart_gewuenscht(db) is False


def test_1001_mcp_tool_weist_unbekannte_aktion_ab(db):
    """Eine unbekannte Aktion darf nicht still als "aus" gelten."""
    werkzeug = _tool_holen(db, "ollama_autostart")
    ollama_start.autostart_setzen(db, True)
    antwort = werkzeug("vielleicht")
    assert "fehler" in antwort
    assert ollama_start.autostart_gewuenscht(db) is True


# -- Das Dashboard zeigt den Schalter ---------------------------------

def test_1001_schalter_steht_im_einstellungen_tab():
    """Er gehoert vor allem in die Ansicht "nicht erreichbar" — dort
    braucht man ihn, denn dort steht man nach jedem Neustart."""
    quelle = (_repo() / "frontend" / "src" / "pages"
              / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert "function OllamaAutostartBlock" in quelle
    assert quelle.count("<OllamaAutostartBlock") >= 2
    nicht_erreichbar = quelle[quelle.index("Variante A"):
                              quelle.index("Variante B")]
    assert "<OllamaAutostartBlock" in nicht_erreichbar

# -- Der Weg ueber das Dashboard, tatsaechlich aufgerufen --------------

@pytest.fixture
def rest(tmp_path):
    """TestClient auf isolierter DB.

    Ein Endpunkt, der nur im Quelltext geprueft wird, ist nicht geprueft
    (DoD 8c). Hier wird er wirklich gerufen.
    """
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


def test_1001_rest_liest_und_setzt(rest):
    klient, datenbank = rest
    assert klient.get("/api/llm/autostart").json()["autostart"] is False

    antwort = klient.put("/api/llm/autostart", json={"an": True}).json()
    assert antwort["autostart"] is True
    assert ollama_start.autostart_gewuenscht(datenbank) is True

    antwort = klient.put("/api/llm/autostart", json={"an": False}).json()
    assert antwort["autostart"] is False


def test_1001_rest_weist_unsinn_ab(rest):
    """Ein Wert, der weder wahr noch falsch ist, darf nicht still als
    "aus" gespeichert werden."""
    klient, _ = rest
    antwort = klient.put("/api/llm/autostart", json={"an": "vielleicht schon"})
    assert antwort.status_code == 400
