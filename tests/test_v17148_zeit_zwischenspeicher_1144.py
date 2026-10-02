"""#1144 — Zeit und Zwischenspeicher: vier Funde, jeder mit eigenem Test.

Durchsicht vom 01.10.2026. Jeder Fund wurde nachgestellt, bevor er behoben
wurde (die Zahlen stehen an den Tests):

1. Die Seite zeigte "Claude Desktop: verbunden", auch wenn PBP beendet war.
3. Die "Neu"-Marker im Block "Offen" verschwanden beim ersten Neuladen.
4. Zwei Stellen merkten einen Fehlschlag als "leer": die Hinweise (eine
   Stunde) und die Kontakt-Kategorien (die ganze Sitzung).
5. Das Sicherheitsnetz gegen offene Transaktionen wirkte im falschen Thread.

(Punkt 2 betrifft nur die Beta-Linie.)
"""
import os
import sys
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _quelle(*teile):
    return ROOT.joinpath(*teile).read_text(encoding="utf-8-sig")


# ══ Punkt 3: "Neu"-Marker und Rueckschau messen gegen denselben Besuch ═══

def _stelle_ein(db, *, letzter_zugriff, aufgabe_vor):
    """Ein Profil, eine Bewerbung, eine offene Aufgabe von heute — der letzte
    Zugriff und das Alter der Aufgabe sind vorgegeben (Stunden)."""
    from bewerbungs_assistent.services import besuch

    db.create_profile("Nutzerin", "n@example.com")
    aid = db.add_application({"title": "Fachkraft", "company": "Musterbetrieb GmbH",
                              "status": "beworben"})
    jetzt = datetime.now(timezone.utc)
    if letzter_zugriff is not None:
        db.set_profile_setting(besuch.BESUCH_EINSTELLUNG,
                               (jetzt - timedelta(hours=letzter_zugriff)).isoformat())
    tid = db.add_task({"application_id": aid, "titel": "Frisch",
                       "faellig_am": date.today().isoformat()})
    alt = (jetzt - timedelta(hours=aufgabe_vor)).isoformat()
    db.connect().execute("UPDATE tasks SET created_at=? WHERE id=?", (alt, tid))
    db.connect().commit()
    return aid, tid


def test_1144_neu_marker_ueberleben_das_neuladen_nach_langer_pause(tmp_db):
    """Gemessen: letzter Besuch vor 15 h, Aufgabe vor 10 h angelegt. Vorher:
    erster Aufruf neu_anzahl=1, zweiter (F5 nach einer Minute) neu_anzahl=0."""
    from bewerbungs_assistent.services import aufgaben_sicht

    _stelle_ein(tmp_db, letzter_zugriff=15, aufgabe_vor=10)
    erst = aufgaben_sicht.dashboard_block(tmp_db)["neu_anzahl"]
    zweit = aufgaben_sicht.dashboard_block(tmp_db)["neu_anzahl"]
    dritt = aufgaben_sicht.dashboard_block(tmp_db)["neu_anzahl"]
    assert erst == 1
    assert zweit == 1, "die Marke darf das erste Neuladen nicht ueberleben muessen"
    assert dritt == 1


def test_1144_der_naechste_besuch_beginnt_nach_einer_pause(tmp_db):
    """Nach einer Pause von mehr als vier Stunden ist neu, was seit dem
    letzten Zugriff dazukam — und die Aufgabe von gestern ist es nicht mehr."""
    from bewerbungs_assistent.services import aufgaben_sicht, besuch

    _stelle_ein(tmp_db, letzter_zugriff=15, aufgabe_vor=10)
    assert aufgaben_sicht.dashboard_block(tmp_db)["neu_anzahl"] == 1
    zugriff = datetime.now(timezone.utc)
    # Dreissig Stunden spaeter, ohne dass jemand dazwischen hinsah.
    spaeter = zugriff + timedelta(hours=30)
    basis = besuch.neu_seit(tmp_db, jetzt=spaeter)
    assert abs((basis - zugriff).total_seconds()) < 5, "neu ist, was nach dem letzten Zugriff kam"
    zeile = {"erstellt_am": (zugriff - timedelta(hours=10)).isoformat()}
    assert aufgaben_sicht._markiere_neu({"heute": [zeile]}, basis.isoformat()) == 0
    assert zeile["neu"] is False


def test_1144_jeder_zugriff_rueckt_die_besuchszeit_vor_nicht_die_basis(tmp_db):
    """Besuchszeit (letzter Zugriff) und "neu seit"-Basis sind getrennt."""
    from bewerbungs_assistent.services import besuch

    _stelle_ein(tmp_db, letzter_zugriff=15, aufgabe_vor=10)
    vorher = datetime.now(timezone.utc) - timedelta(hours=15)
    basis1 = besuch.neu_seit(tmp_db)
    zugriff1 = tmp_db.get_profile_setting(besuch.BESUCH_EINSTELLUNG)
    basis2 = besuch.neu_seit(tmp_db)
    zugriff2 = tmp_db.get_profile_setting(besuch.BESUCH_EINSTELLUNG)

    assert abs((basis1 - vorher).total_seconds()) < 5, "Basis = der Zugriff davor"
    assert basis1 == basis2, "innerhalb des Besuchs aendert sich die Basis nicht"
    assert zugriff2 >= zugriff1
    assert datetime.fromisoformat(zugriff1) > basis1, "der Zugriff ist neuer als die Basis"


def test_1144_erster_zugriff_ueberhaupt_schaut_72_stunden_zurueck(tmp_db):
    from bewerbungs_assistent.services import besuch

    tmp_db.create_profile("Nutzerin", "n@example.com")
    jetzt = datetime.now(timezone.utc)
    basis = besuch.neu_seit(tmp_db, jetzt=jetzt)
    assert abs((jetzt - basis).total_seconds() - 72 * 3600) < 5
    # Das zweite Lesen ein paar Minuten spaeter aendert daran nichts.
    spaeter = besuch.neu_seit(tmp_db, jetzt=jetzt + timedelta(minutes=5))
    assert spaeter == basis


def test_1144_werte_aus_der_zeit_vor_der_trennung_bleiben_brauchbar(tmp_db):
    """Installationen kennen nur `last_login_at`. Dessen Wert gilt dann als
    Beginn des Besuchs — nichts bricht, und nichts springt 72 h zurueck."""
    from bewerbungs_assistent.services import besuch

    tmp_db.create_profile("Nutzerin", "n@example.com")
    jetzt = datetime.now(timezone.utc)
    zwei_h = jetzt - timedelta(hours=2)
    tmp_db.set_profile_setting(besuch.BESUCH_EINSTELLUNG, zwei_h.isoformat())
    assert tmp_db.get_profile_setting(besuch.BASIS_EINSTELLUNG, None) is None
    basis = besuch.neu_seit(tmp_db, jetzt=jetzt)
    assert abs((basis - zwei_h).total_seconds()) < 1


def test_1144_unlesbare_werte_werfen_nicht(tmp_db):
    from bewerbungs_assistent.services import besuch

    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.set_profile_setting(besuch.BESUCH_EINSTELLUNG, "kein Datum")
    tmp_db.set_profile_setting(besuch.BASIS_EINSTELLUNG, "auch keins")
    basis = besuch.neu_seit(tmp_db)
    assert isinstance(basis, datetime)


@pytest.fixture
def dash_client(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database, get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    monkeypatch.setattr(dash, "_db", db)
    yield TestClient(dash.app), db
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def test_1144_die_rueckschau_zeigt_beim_zweiten_aufruf_dasselbe_fenster(dash_client):
    """`/api/recap` schrieb den letzten Zugriff bei JEDEM Aufruf fort: nach
    einer Pause zeigte der erste Aufruf die Rueckschau, der zweite eine leere."""
    from bewerbungs_assistent.services import besuch

    tc, db = dash_client
    db.create_profile("Nutzerin", "n@example.com")
    db.set_profile_setting(besuch.BESUCH_EINSTELLUNG,
                           (datetime.now(timezone.utc) - timedelta(hours=15)).isoformat())
    erst = tc.get("/api/recap").json()
    zweit = tc.get("/api/recap").json()
    assert erst["since"] == zweit["since"]


def test_1144_marken_und_rueckschau_messen_gegen_denselben_zeitpunkt(dash_client):
    """Vorher kam es darauf an, wer zuerst las."""
    from bewerbungs_assistent.services import aufgaben_sicht, besuch

    tc, db = dash_client
    _stelle_ein(db, letzter_zugriff=15, aufgabe_vor=10)
    recap = tc.get("/api/recap").json()
    aufgaben_sicht.dashboard_block(db)  # liest dazwischen
    recap2 = tc.get("/api/recap").json()
    assert recap["since"] == recap2["since"]
    assert datetime.fromisoformat(recap["since"]) == besuch.neu_seit(db)


def test_1144_die_aufruferseite_hat_keinen_eigenen_zeitstempel_mehr():
    """Beide Wege gehen durch `services/besuch.py`."""
    dash = _quelle("src", "bewerbungs_assistent", "dashboard.py")
    sicht = _quelle("src", "bewerbungs_assistent", "services", "aufgaben_sicht.py")
    assert 'set_profile_setting("last_login_at"' not in dash
    assert "from .services.besuch import neu_seit" in dash
    assert "from .besuch import neu_seit" in sicht
    assert "set_profile_setting(BESUCH_EINSTELLUNG" not in sicht


# ══ Punkt 4: Fehlschlaege nicht als "leer" merken ═════════════════════

class _Resp:
    def __init__(self, status=200, daten=None):
        self.status_code = status
        self._daten = daten if daten is not None else {}

    def json(self):
        return self._daten


class _Netz:
    """Ein Netz, das sich umschalten laesst: "aus" (Verbindungsfehler),
    "fehler" (HTTP 503) oder "an" (zwei Hinweise)."""

    def __init__(self):
        self.modus = "aus"
        self.aufrufe = 0

    def klasse(self):
        netz = self

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, *a, **k):
                netz.aufrufe += 1
                if netz.modus == "aus":
                    raise ConnectionError("Netz weg")
                if netz.modus == "fehler":
                    return _Resp(503, {})
                return _Resp(200, {"hints": [
                    {"id": "a", "titel": "Hinweis A"}, {"id": "b", "titel": "Hinweis B"}]})

        return _Client


@pytest.fixture
def hinweise(dash_client, monkeypatch):
    tc, db = dash_client
    import bewerbungs_assistent.dashboard as dash
    if hasattr(dash.api_public_hints, "_cache"):
        delattr(dash.api_public_hints, "_cache")
    monkeypatch.setenv("PBP_HINTS_URL", "https://example.invalid/hints.json")
    netz = _Netz()
    monkeypatch.setattr("httpx.AsyncClient", netz.klasse())
    yield tc, dash, netz
    if hasattr(dash.api_public_hints, "_cache"):
        delattr(dash.api_public_hints, "_cache")


def _frist_abgelaufen(dash, sekunden):
    """Die gemerkte Antwort ist `sekunden` Sekunden aelter geworden."""
    dash.api_public_hints._cache["ts"] -= sekunden


def test_1144_ein_netzfehler_gilt_nicht_eine_stunde_als_keine_hinweise(hinweise):
    """Gemessen: zweiter Abruf bei wieder erreichbarem Netz lieferte ohne
    neuen Netzaufruf [] — eine Stunde lang."""
    tc, dash, netz = hinweise
    assert tc.get("/api/public/hints").json()["hints"] == []        # Netz weg
    netz.modus = "an"
    _frist_abgelaufen(dash, dash._HINWEISE_FEHLSCHLAG_S + 1)        # nur die kurze Frist
    res = tc.get("/api/public/hints").json()
    assert [h["id"] for h in res["hints"]] == ["a", "b"]


def test_1144_ein_fehlschlag_wird_nur_kurz_gemerkt(hinweise):
    """Ein Schwall von Seitenaufrufen darf nicht jedes Mal auf den Abruf warten."""
    tc, dash, netz = hinweise
    tc.get("/api/public/hints")
    vorher = netz.aufrufe
    tc.get("/api/public/hints")
    tc.get("/api/public/hints")
    assert netz.aufrufe == vorher, "innerhalb der kurzen Frist kein neuer Netzaufruf"
    assert dash._HINWEISE_FEHLSCHLAG_S <= 60 < dash._HINWEISE_ERFOLG_S


def test_1144_eine_fehlerantwort_ist_keine_auskunft(hinweise):
    """HTTP 503 (Sperre, Ausfall) zaehlt wie ein Netzfehler."""
    tc, dash, netz = hinweise
    netz.modus = "fehler"
    assert tc.get("/api/public/hints").json()["hints"] == []
    netz.modus = "an"
    _frist_abgelaufen(dash, dash._HINWEISE_FEHLSCHLAG_S + 1)
    assert len(tc.get("/api/public/hints").json()["hints"]) == 2


def test_1144_ein_erfolg_wird_weiter_eine_stunde_gemerkt(hinweise):
    tc, dash, netz = hinweise
    netz.modus = "an"
    assert len(tc.get("/api/public/hints").json()["hints"]) == 2
    aufrufe = netz.aufrufe
    _frist_abgelaufen(dash, 3000)                       # fast eine Stunde
    assert len(tc.get("/api/public/hints").json()["hints"]) == 2
    assert netz.aufrufe == aufrufe
    _frist_abgelaufen(dash, 700)                        # jetzt ueber einer Stunde
    tc.get("/api/public/hints")
    assert netz.aufrufe == aufrufe + 1


def test_1144_die_kontakt_kategorien_merken_nur_einen_erfolg():
    seite = _quelle("frontend", "src", "pages", "ContactsPage.jsx")
    assert 'from "@/lib/nurErfolge"' in seite
    assert "nurErfolgeMerken(" in seite
    # Die alte Bauform — ein Fehlschlag wird zur leeren Liste und bleibt es — darf nicht zurueckkehren.
    assert "_categoriesCache = []" not in seite
    assert "catch {\n    _categoriesCache" not in seite


# ══ Punkt 5: das Rollback-Netz laeuft im Worker ═════════════════════════

@pytest.fixture
def werkzeug_server(tmp_path):
    """Ein echter FastMCP-Server mit der Registrierung, die auch der Server
    benutzt (`mit_katalog`), und einer eigenen, isolierten Datenbank."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database, get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import mit_katalog

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    mcp = FastMCP("test")
    yield mit_katalog(mcp, db), mcp, db, tmp_path
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def _aufrufen(mcp, name, args=None):
    import asyncio

    async def _run():
        tool = await mcp.get_tool(name)
        return await tool.run(args or {})

    return asyncio.run(_run())


def _anderer_schreiber_kommt_durch(pfad) -> bool:
    """Ein zweiter Prozess-Ersatz: eigene Connection, kurze Wartezeit. Wer den
    Schreib-Lock nicht bekommt, scheitert mit "database is locked"."""
    import sqlite3
    conn = sqlite3.connect(str(pfad), timeout=0.3)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.rollback()
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def test_1144_ein_werkzeug_das_vor_dem_commit_abbricht_haelt_den_lock_nicht(werkzeug_server):
    """Gemessen: ein Worker schreibt und wirft vor dem Commit; die Middleware
    (Event-Loop-Thread) kam an dessen Connection nicht heran, und ein anderer
    Schreiber scheiterte mit 'database is locked'."""
    mit_katalog, mcp, db, tmp_path = werkzeug_server

    @mit_katalog.tool()
    def pbp_test_bricht_ab() -> dict:
        """Schreibt und bricht vor dem Commit ab."""
        conn = db.connect()
        conn.execute("INSERT INTO settings (key, value) VALUES ('leck_test', 'halb')")
        raise RuntimeError("vor dem Commit")

    with pytest.raises(Exception):
        _aufrufen(mcp, "pbp_test_bricht_ab")
    assert _anderer_schreiber_kommt_durch(db.db_path), \
        "der Worker hat seine offene Transaktion liegen lassen"


def test_1144_die_halbe_arbeit_wird_nicht_vom_naechsten_commit_festgeschrieben(werkzeug_server):
    mit_katalog, mcp, db, tmp_path = werkzeug_server

    @mit_katalog.tool()
    def pbp_test_leck() -> dict:
        """Schreibt und bricht vor dem Commit ab."""
        db.connect().execute("INSERT INTO settings (key, value) VALUES ('halb', '1')")
        raise RuntimeError("vor dem Commit")

    @mit_katalog.tool()
    def pbp_test_commit() -> dict:
        """Ein ganz anderer Aufruf, der ordentlich festschreibt."""
        conn = db.connect()
        conn.execute("INSERT INTO settings (key, value) VALUES ('ganz', '1')")
        conn.commit()
        return {"ok": True}

    with pytest.raises(Exception):
        _aufrufen(mcp, "pbp_test_leck")
    _aufrufen(mcp, "pbp_test_commit")
    import sqlite3
    pruef = sqlite3.connect(str(db.db_path))
    try:
        schluessel = {r[0] for r in pruef.execute("SELECT key FROM settings")}
    finally:
        pruef.close()
    assert "ganz" in schluessel
    assert "halb" not in schluessel, "ein fremder Commit hat die halbe Arbeit festgeschrieben"


def test_1144_ein_werkzeug_das_ordentlich_festschreibt_bleibt_unberuehrt(werkzeug_server):
    mit_katalog, mcp, db, tmp_path = werkzeug_server

    @mit_katalog.tool()
    def pbp_test_ordentlich() -> dict:
        """Schreibt und schreibt fest."""
        conn = db.connect()
        conn.execute("INSERT INTO settings (key, value) VALUES ('fest', '1')")
        conn.commit()
        return {"ok": True}

    res = _aufrufen(mcp, "pbp_test_ordentlich")
    assert (getattr(res, "structured_content", None) or {}).get("ok") is True
    import sqlite3
    pruef = sqlite3.connect(str(db.db_path))
    try:
        assert pruef.execute("SELECT value FROM settings WHERE key='fest'").fetchone()
    finally:
        pruef.close()


def test_1144_eine_schon_offene_transaktion_gehoert_dem_aufrufer(werkzeug_server):
    """Wer eine Transaktion offen hat und ein Werkzeug als Funktion aufruft,
    behaelt sie: zurueckgenommen wird nur, was der Aufruf selbst offen liess."""
    mit_katalog, mcp, db, tmp_path = werkzeug_server

    @mit_katalog.tool()
    def pbp_test_harmlos() -> dict:
        """Tut nichts."""
        return {"ok": True}

    conn = db.connect()
    conn.execute("INSERT INTO settings (key, value) VALUES ('aufrufer', '1')")
    assert conn.in_transaction
    pbp_test_harmlos()  # als Funktion, im selben Thread
    assert conn.in_transaction, "die Transaktion des Aufrufers wurde zurueckgenommen"
    assert conn.execute("SELECT 1 FROM settings WHERE key='aufrufer'").fetchone()
    conn.rollback()


def test_1144_ein_werkzeug_im_werkzeug_nimmt_nicht_vorzeitig_zurueck(werkzeug_server):
    """Nur der AEUSSERSTE Aufruf raeumt auf. Ruft ein Werkzeug ein anderes als
    Funktion auf, ist dessen Ende nicht das Ende der Arbeit."""
    mit_katalog, mcp, db, tmp_path = werkzeug_server

    @mit_katalog.tool()
    def pbp_test_innen() -> dict:
        """Schreibt, ohne festzuschreiben (der aeussere tut es)."""
        db.connect().execute("INSERT INTO settings (key, value) VALUES ('innen', '1')")
        return {"ok": True}

    @mit_katalog.tool()
    def pbp_test_aussen() -> dict:
        """Ruft das innere als Funktion auf und schreibt dann fest."""
        pbp_test_innen()
        conn = db.connect()
        assert conn.execute("SELECT 1 FROM settings WHERE key='innen'").fetchone(), \
            "das innere Werkzeug hat vorzeitig zurueckgenommen"
        conn.commit()
        return {"ok": True}

    _aufrufen(mcp, "pbp_test_aussen")
    import sqlite3
    pruef = sqlite3.connect(str(db.db_path))
    try:
        assert pruef.execute("SELECT 1 FROM settings WHERE key='innen'").fetchone()
    finally:
        pruef.close()


def test_1144_die_aufrufstiefe_ist_nach_einem_fehler_wieder_null(werkzeug_server):
    """Sonst raeumte dieser Thread nie wieder auf."""
    mit_katalog, mcp, db, tmp_path = werkzeug_server
    from bewerbungs_assistent.tools import _AUFRUF

    @mit_katalog.tool()
    def pbp_test_wirft() -> dict:
        """Wirft sofort."""
        raise ValueError("nein")

    for _ in range(3):
        with pytest.raises(Exception):
            _aufrufen(mcp, "pbp_test_wirft")
    assert getattr(_AUFRUF, "tiefe", 0) == 0


def test_1144_asynchrone_werkzeuge_bleiben_unveraendert(werkzeug_server):
    """Sie laufen im Event-Loop-Thread; dort deckt die Middleware sie ab."""
    mit_katalog, mcp, db, tmp_path = werkzeug_server

    async def pbp_test_asynchron() -> dict:
        """Asynchron."""
        return {"ok": True}

    registriert = mit_katalog.tool()(pbp_test_asynchron)
    import inspect
    assert inspect.iscoroutinefunction(registriert)


def test_1144_auch_ein_auftrag_im_budget_pool_laesst_keine_transaktion_liegen(werkzeug_server):
    """Vier Werkzeuge laufen im Budget-Pool (todo_anlegen, meeting_hinzufuegen, ...).
    Dort sitzt die Connection im Pool-Worker, nicht im Thread des MCP-Aufrufs —
    die Huelle um das Werkzeug erreicht sie nicht, der Pool raeumt selbst auf."""
    mit_katalog, mcp, db, tmp_path = werkzeug_server
    from bewerbungs_assistent.services import tool_budget
    tool_budget.aufraeumen_fuer(db)

    @tool_budget.mit_budget("pbp_test_pool_leck", lese_tool="x")
    def leck():
        db.connect().execute("INSERT INTO settings (key, value) VALUES ('pool_leck', '1')")
        raise RuntimeError("vor dem Commit")

    with pytest.raises(RuntimeError):
        leck()
    assert tool_budget.warte_auf_leerlauf(10)
    assert _anderer_schreiber_kommt_durch(db.db_path),         "der Pool-Worker hat seine offene Transaktion liegen lassen"


def test_1144_der_pool_raeumt_nicht_weg_was_dem_aufrufer_gehoert(werkzeug_server):
    """Hat die Connection des Workers beim Eintritt schon eine Transaktion offen,
    gehoert sie dem Aufrufer."""
    mit_katalog, mcp, db, tmp_path = werkzeug_server
    from bewerbungs_assistent.services import tool_budget
    tool_budget.aufraeumen_fuer(db)
    ergebnis = {}

    @tool_budget.mit_budget("pbp_test_pool_fremd", lese_tool="x")
    def fremd():
        conn = db.connect()
        conn.execute("INSERT INTO settings (key, value) VALUES ('pool_eins', '1')")
        # innen: noch ein Aufruf, bei dem schon eine Transaktion offen ist
        ergebnis["offen_davor"] = tool_budget._offen_vorher()
        return {"ok": True}

    try:
        fremd()
    finally:
        tool_budget.warte_auf_leerlauf(10)
    assert ergebnis["offen_davor"] is True


def test_1144_die_registrierung_gibt_dem_pool_die_datenbank(werkzeug_server):
    """Setzer und Leser: ohne diese Zeile wuerde der Pool nie aufraeumen."""
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.services import tool_budget
    from bewerbungs_assistent.tools import register_all
    mit_katalog, mcp, db, tmp_path = werkzeug_server
    tool_budget.aufraeumen_fuer(None)
    register_all(FastMCP("x"), db, logging.getLogger("x"))
    assert tool_budget._DB is db


def test_1144_alle_registrierten_werkzeuge_tragen_die_huelle():
    """Die Huelle sitzt an der EINEN Stelle, durch die jede Registrierung geht."""
    quelle = _quelle("src", "bewerbungs_assistent", "tools", "__init__.py")
    assert "fn = _mit_aufraeumen(fn, name, self._db)" in quelle
    assert "def _mit_aufraeumen(" in quelle


# ══ Punkt 1: die Oberflaeche merkt, wenn PBP nicht mehr antwortet ═════════

def test_1144_die_oberflaeche_wertet_ausbleibende_antworten_aus():
    app = _quelle("frontend", "src", "App.jsx")
    assert 'from "@/lib/verbindung"' in app
    assert "naechsterStand(stand, antwortKam)" in app
    assert "naechsteAbfrageMs(stand)" in app
    # Die alte Bauform — Antwort null, nichts passiert — darf nicht zurueckkehren.
    assert "window.setInterval(pollConnection" not in app
    assert "clearTimeout(timer)" in app
    # Die Anzeige und die Hilfe kennen den Zustand.
    assert "anzeigeStand(serverErreichbar" in app
    assert 'data-mcp-hilfe={st}' in app
    leiste = _quelle("frontend", "src", "components", "Sidebar.jsx")
    assert "server_weg" in leiste
    assert "PBP antwortet nicht" in leiste
    assert "data-verbindung={brand.connectionStatus}" in leiste


def test_1144_die_node_tests_laufen_in_der_ci():
    ci = _quelle(".github", "workflows", "tests.yml")
    assert "node frontend/src/lib/verbindung.test.mjs" in ci
    assert "node frontend/src/lib/nurErfolge.test.mjs" in ci


# ══ Im Browser: der Weg, den ein Mensch sieht ═════════════════════════

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None
    PlaywrightError = Exception


@pytest.fixture(scope="module")
def browser():
    if sync_playwright is None:
        pytest.skip("Playwright nicht installiert")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


class _Dashboard:
    """Ein echter Dashboard-Server, der sich anhalten und wieder starten laesst
    (auf demselben Port, wie ein beendetes und neu gestartetes PBP)."""

    def __init__(self, dash):
        import socket
        self.dash = dash
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._srv = None
        self._thread = None

    def start(self):
        import time
        import urllib.request

        import uvicorn
        self._srv = uvicorn.Server(uvicorn.Config(
            self.dash.app, host="127.0.0.1", port=self.port, log_level="warning"))
        self._srv.install_signal_handlers = lambda: None
        self._thread = threading.Thread(target=self._srv.run, daemon=True)
        self._thread.start()
        for _ in range(100):
            try:
                urllib.request.urlopen(f"{self.url}/api/status", timeout=1)
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("Dashboard startet nicht")

    def stop(self):
        if self._srv is not None:
            self._srv.should_exit = True
            self._thread.join(timeout=10)
            self._srv = None


@pytest.fixture
def live(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database, get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    monkeypatch.setattr(dash, "_db", db)
    monkeypatch.setenv("PBP_HINTS_URL", "off")  # kein Netzaufruf im Browsertest
    # Ein lebender MCP-Server: die Zeile zeigt "Claude Desktop: verbunden" —
    # genau der Zustand, der vorher stehen blieb.
    from bewerbungs_assistent import heartbeat
    heartbeat._write_heartbeat_file("alive_ping", is_alive=True)
    assert (tmp_path / "mcp_heartbeat.json").exists(), "Heartbeat nicht isoliert geschrieben"
    server = _Dashboard(dash)
    server.start()
    yield server
    server.stop()
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def _zeile(page):
    return page.locator("button[data-verbindung]")


def _vorspulen(page, ms, bis, versuche=14):
    """Die Uhr der Seite vorstellen, bis `bis()` wahr ist. Die Antwort auf eine
    Abfrage kommt in Echtzeit; die naechste Frist ist erst danach geplant — darum
    in Schritten."""
    for _ in range(versuche):
        if bis():
            return True
        page.clock.fast_forward(ms)
        page.wait_for_timeout(350)
    return bis()


def test_1144_nach_dem_ende_von_pbp_steht_dort_nicht_mehr_verbunden(browser, live):
    """Gemessen: Seite geladen, Server gestoppt, nach mehr als 70 s steht die
    Anzeige noch auf 'verbunden'."""
    page = browser.new_page()
    try:
        page.clock.install()
        page.goto(live.url, wait_until="networkidle", timeout=30000)
        _zeile(page).wait_for(timeout=15000)
        assert _zeile(page).get_attribute("data-verbindung") == "connected"
        assert _zeile(page).inner_text().strip() == "Claude Desktop: verbunden"
        live.stop()
        weg = _vorspulen(
            page, 31000,
            lambda: _zeile(page).get_attribute("data-verbindung") == "server_weg")
        assert weg, "die Anzeige merkt nicht, dass PBP nicht mehr antwortet"
        assert _zeile(page).inner_text().strip() == "PBP antwortet nicht"
        # Die Lokale-KI-Zeile behauptet dann auch nichts mehr.
        assert "Stand unbekannt" in page.locator("aside.app-sidebar").inner_text()
    finally:
        page.close()


def test_1144_ein_klick_auf_die_zeile_erklaert_was_zu_tun_ist(browser, live):
    """Vorher oeffnete ein Klick auf das gruene 'verbunden' Claude Desktop —
    obwohl PBP gar nicht mehr antwortete."""
    page = browser.new_page()
    try:
        page.clock.install()
        page.goto(live.url, wait_until="networkidle", timeout=30000)
        _zeile(page).wait_for(timeout=15000)
        assert _zeile(page).get_attribute("data-verbindung") == "connected"
        live.stop()
        assert _vorspulen(
            page, 31000,
            lambda: _zeile(page).get_attribute("data-verbindung") == "server_weg")
        _zeile(page).click()
        hilfe = page.locator('[data-mcp-hilfe="server_weg"]')
        hilfe.wait_for(timeout=10000)
        text = hilfe.inner_text()
        assert "PBP antwortet nicht" in text
        assert "PBP-Fenster" in text
    finally:
        page.close()


def test_1144_ein_einzelner_ausfall_ist_noch_keiner(browser, live):
    """Ein Ruckler (Ruhezustand, Neustart des Servers) schlaegt nicht sofort
    in einen roten Zustand um — erst der zweite Fehlschlag in Folge."""
    page = browser.new_page()
    try:
        page.clock.install()
        page.goto(live.url, wait_until="networkidle", timeout=30000)
        _zeile(page).wait_for(timeout=15000)
        live.stop()
        page.clock.fast_forward(31000)       # die erste Abfrage schlaegt fehl
        page.wait_for_timeout(1200)
        assert _zeile(page).get_attribute("data-verbindung") != "server_weg"
        live.start()                         # und der Server ist wieder da
        page.clock.fast_forward(9000)
        page.wait_for_timeout(1200)
        page.clock.fast_forward(9000)
        page.wait_for_timeout(600)
        assert _zeile(page).get_attribute("data-verbindung") != "server_weg"
    finally:
        page.close()


def test_1144_antwortet_pbp_wieder_nimmt_die_anzeige_es_zurueck(browser, live):
    page = browser.new_page()
    try:
        page.clock.install()
        page.goto(live.url, wait_until="networkidle", timeout=30000)
        _zeile(page).wait_for(timeout=15000)
        live.stop()
        assert _vorspulen(
            page, 31000,
            lambda: _zeile(page).get_attribute("data-verbindung") == "server_weg")
        live.start()
        zurueck = _vorspulen(
            page, 9000,
            lambda: _zeile(page).get_attribute("data-verbindung") != "server_weg")
        assert zurueck, "die Anzeige bleibt auf 'antwortet nicht', obwohl PBP wieder da ist"
        assert "Stand unbekannt" not in page.locator("aside.app-sidebar").inner_text()
    finally:
        page.close()
