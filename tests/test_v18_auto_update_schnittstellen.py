"""Auto-Update (#1093): die Schnittstellen — REST im Dashboard, Werkzeuge im Chat, Schema-Schutz.

Dashboard und Chat sind dieselbe Funktion (PBP soll auch ohne Claude nutzbar sein): beide rufen `lauf` und
`zustand`. Hier wird geprueft, dass beide dieselben Regeln durchsetzen — besonders die Zusage an den
Menschen: eine Stufe, bei der PBP von selbst installiert, und jede Installation brauchen seine Zustimmung.
"""
import json
import logging
import os

import pytest
from _au_hilfen import FakeOeffner, eintrag, fassung_anlegen, liste, programmordner

from bewerbungs_assistent.services import schema_schutz
from bewerbungs_assistent.services.auto_update import lauf, layout, quelle, zustand


@pytest.fixture(autouse=True)
def _sauber(monkeypatch):
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    lauf._JOB.update(id=None, status=None, phase="", anteil=0.0, text="", version=None, ausloeser="")
    schema_schutz.zuruecksetzen()
    yield
    schema_schutz.zuruecksetzen()


@pytest.fixture
def client_db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    yield TestClient(dash.app), db
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    app = programmordner(tmp_path / "pc", fassungen=("1.8.0",))
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    return app


@pytest.fixture
def netz(monkeypatch):
    """Die Liste der Veroeffentlichungen kommt aus dem Testdoppel; ein Aufruf des echten Netzes schlaegt fehl."""
    state = {"o": liste(eintrag("v1.8.1"))}
    monkeypatch.setattr(quelle, "standard_oeffner", lambda: state["o"])
    return state


# ══ REST ═════════════════════════════════════════════════════════════════════════════════

def test_get_ohne_installer_layout_nennt_den_grund_statt_zu_scheitern(client_db):
    c, _ = client_db
    r = c.get("/api/auto-update")
    assert r.status_code == 200
    j = r.json()
    assert j["verfuegbar"] is False and ("Installer" in j["grund"] or "Windows" in j["grund"])
    assert j["stufe"] == "aus" and j["vorgaenger_behalten"] == 3 and j["installer_aufraeumen"] == "fragen"


def test_get_mit_layout_nennt_laufende_und_vorgemerkte_fassung(client_db, umgebung):
    c, _ = client_db
    fassung_anlegen(umgebung, "1.8.1")
    (umgebung / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    j = c.get("/api/auto-update").json()
    assert j["verfuegbar"] is True and (j["laufend"], j["aktuell"], j["neustart_noetig"]) == ("1.8.0", "1.8.1", True)


def test_einstellungen_setzen_und_lesen(client_db, umgebung):
    c, db = client_db
    r = c.post("/api/auto-update/einstellungen", json={"stufe": "hinweis", "vorgaenger_behalten": 5, "installer_aufraeumen": "immer"})
    assert r.status_code == 200
    j = r.json()
    assert (j["stufe"], j["vorgaenger_behalten"], j["installer_aufraeumen"]) == ("hinweis", 5, "immer")
    assert zustand.stufe(db) == "hinweis" and zustand.gefragt(db)["antwort"] == "ja"


def test_wer_die_stufe_selbst_waehlt_hat_die_rueckfrage_beantwortet(client_db, umgebung):
    c, db = client_db
    c.post("/api/auto-update/einstellungen", json={"stufe": "aus"})
    assert zustand.gefragt(db)["antwort"] == "nein"
    c.post("/api/auto-update/einstellungen", json={"stufe": "auto_still"})
    assert zustand.gefragt(db)["antwort"] == "ja"


@pytest.mark.parametrize("body", [{}, {"stufe": "immer"}, {"vorgaenger_behalten": 0}, {"vorgaenger_behalten": "x"},
                                  {"installer_aufraeumen": "vielleicht"}, {"unbekannt": 1}])
def test_ungueltige_einstellungen_geben_400_und_aendern_nichts(client_db, umgebung, body):
    c, db = client_db
    r = c.post("/api/auto-update/einstellungen", json=body)
    assert r.status_code == 400 and r.json()["error"]
    assert zustand.stufe(db) == "aus" and zustand.vorgaenger_behalten(db) == 3


def test_die_quelle_laesst_sich_ueber_keinen_aufruf_aendern(client_db, umgebung):
    """Akzeptanzkriterium 6: weder die Einstellung `update_quellen` noch ein Aufruf lenkt die INSTALLATION um."""
    c, db = client_db
    db.set_setting("update_quellen", [{"name": "evil", "url": "https://evil.example/releases", "art": "github"}])
    r = c.post("/api/auto-update/einstellungen", json={"stufe": "auto_still", "quelle": "https://evil.example"})
    assert r.status_code == 200
    assert quelle.API_FREIGABEN.startswith("https://api.github.com/repos/MadGapun/PBP/")
    assert "evil" not in json.dumps(r.json())
    # und die feste Quelle steht nicht im Zustand, der aus der Datenbank kommt
    assert db.get_setting("auto_update_quelle", None) is None


@pytest.mark.parametrize("antwort,stufe,gefragt", [("automatisch", "auto_meldung", "ja"), ("klick", "hinweis", "ja"),
                                                   ("nein", "aus", "nein")])
def test_die_rueckfrage_setzt_stufe_und_merkt_die_antwort(client_db, umgebung, antwort, stufe, gefragt):
    c, db = client_db
    r = c.post("/api/auto-update/antwort", json={"antwort": antwort, "bei_version": "1.8.1"})
    assert r.status_code == 200
    assert zustand.stufe(db) == stufe and zustand.gefragt(db)["antwort"] == gefragt


def test_spaeter_laesst_die_stufe_aus_und_fragt_erst_beim_naechsten_update_wieder(client_db, umgebung):
    c, db = client_db
    c.post("/api/auto-update/antwort", json={"antwort": "spaeter", "bei_version": "1.8.1"})
    assert zustand.stufe(db) == "aus"
    assert zustand.frage_faellig(db, "1.8.1") is False and zustand.frage_faellig(db, "1.8.2") is True


def test_eine_unbekannte_antwort_wird_abgewiesen(client_db, umgebung):
    c, db = client_db
    assert c.post("/api/auto-update/antwort", json={"antwort": "immer"}).status_code == 400
    assert zustand.stufe(db) == "aus" and zustand.gefragt(db)["antwort"] is None


def test_jetzt_pruefen_fragt_die_feste_quelle_und_nennt_die_neue_version(client_db, umgebung, netz):
    c, _ = client_db
    j = c.post("/api/auto-update/pruefen").json()
    assert j["neu"]["version"] == "1.8.1" and j["neu"]["frage_faellig"] is True and j["pruefung"]["status"] == "neu"


def test_installieren_ohne_neue_version_ist_ein_fehler(client_db, umgebung):
    c, _ = client_db
    r = c.post("/api/auto-update/installieren", json={})
    assert r.status_code == 400 and "keine neue Version" in r.json()["error"]


def test_installieren_startet_den_lauf_fuer_die_gefundene_version(client_db, umgebung, netz, monkeypatch):
    c, db = client_db
    c.post("/api/auto-update/pruefen")
    aufrufe = []
    monkeypatch.setattr(lauf, "starte_installation",
                        lambda db_, version, **kw: aufrufe.append((version, kw)) or {"status": "gestartet", "job_id": "x"})
    r = c.post("/api/auto-update/installieren", json={})
    assert r.status_code == 200 and r.json()["status"] == "gestartet"
    assert aufrufe == [("1.8.1", {"ausloeser": "klick"})]


@pytest.mark.parametrize("status,code", [("laeuft_bereits", 409), ("nicht_verfuegbar", 409), ("abgelehnt", 400)])
def test_installieren_gibt_den_grund_als_statuscode_weiter(client_db, umgebung, monkeypatch, status, code):
    c, _ = client_db
    monkeypatch.setattr(lauf, "starte_installation", lambda *a, **k: {"status": status, "text": "t"})
    assert c.post("/api/auto-update/installieren", json={"version": "1.8.1"}).status_code == code


def test_zurueckschalten_schaltet_um_und_merkt_die_neueren_als_zurueckgenommen(client_db, umgebung):
    c, db = client_db
    fassung_anlegen(umgebung, "1.8.1")
    (umgebung / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    r = c.post("/api/auto-update/zurueck", json={"version": "1.8.0"})
    assert r.status_code == 200 and r.json()["nach"] == "1.8.0"
    assert (umgebung / "aktuell.txt").read_text().strip() == "1.8.0"
    assert lauf.abgelehnt(db) == ["1.8.1"]
    assert zustand.verlauf(db)[-1]["ergebnis"] == "zurueckgeschaltet"


def test_zurueckschalten_auf_etwas_nicht_installiertes_geht_nicht(client_db, umgebung):
    c, _ = client_db
    r = c.post("/api/auto-update/zurueck", json={"version": "1.7.0"})
    assert r.status_code == 409 and r.json()["status"] == "nicht_moeglich"


def test_eine_zurueckgenommene_fassung_wird_nie_von_selbst_wieder_eingeschaltet(client_db, umgebung, netz):
    c, db = client_db
    fassung_anlegen(umgebung, "1.8.1")
    (umgebung / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    c.post("/api/auto-update/zurueck", json={"version": "1.8.0"})
    zustand.stufe_setzen(db, "auto_still")
    aufrufe = []
    r = lauf.automatik_schritt(db, installieren=lambda v, **kw: aufrufe.append(v), synchron=True)
    assert r["status"] == "zurueckgenommen" and aufrufe == []
    j = c.post("/api/auto-update/pruefen").json()
    assert j["neu"]["zurueckgenommen"] is True


def test_der_rueckgang_wird_gemeldet_und_als_gesehen_vermerkt(client_db, umgebung):
    c, _ = client_db
    (umgebung / "update_status.json").write_text(json.dumps(
        {"rueckgang": {"von": "1.8.1", "nach": "1.8.0", "grund": "ImportError", "gemeldet": False}}), encoding="utf-8")
    assert c.get("/api/auto-update").json()["rueckgang"]["von"] == "1.8.1"
    assert c.post("/api/auto-update/rueckgang-gesehen").json()["rueckgang"] is None


# ══ Schema-Schutz ═════════════════════════════════════════════════════════════════════════

def _schema_hochsetzen(db):
    from bewerbungs_assistent.database import SCHEMA_VERSION
    db.connect().execute("UPDATE settings SET value=? WHERE key='schema_version'", (str(SCHEMA_VERSION + 1),))
    db.connect().commit()
    schema_schutz.zuruecksetzen()
    return SCHEMA_VERSION


def test_eine_neuere_datenbank_wird_erkannt(client_db):
    _, db = client_db
    assert schema_schutz.zu_neu(db) is None
    stand = _schema_hochsetzen(db)
    t = schema_schutz.zu_neu(db)
    assert t["datenbank"] == stand + 1 and t["programm"] == stand
    assert "Claude Desktop" in t["text"] and "starte beides neu" in t["text"]


def test_gleiche_oder_aeltere_datenbank_ist_kein_fall(client_db):
    _, db = client_db
    from bewerbungs_assistent.database import SCHEMA_VERSION
    for n in (SCHEMA_VERSION, SCHEMA_VERSION - 1, 1):
        db.connect().execute("UPDATE settings SET value=? WHERE key='schema_version'", (str(n),))
        db.connect().commit()
        schema_schutz.zuruecksetzen()
        assert schema_schutz.zu_neu(db) is None


def test_ein_kaputter_schemawert_gilt_nie_als_zu_neu(client_db):
    _, db = client_db
    for kaputt in ("abc", "", "9" * 3 + "x"):
        db.connect().execute("UPDATE settings SET value=? WHERE key='schema_version'", (kaputt,))
        db.connect().commit()
        schema_schutz.zuruecksetzen()
        assert schema_schutz.zu_neu(db) is None
    db.connect().execute("DELETE FROM settings WHERE key='schema_version'")
    db.connect().commit()
    schema_schutz.zuruecksetzen()
    assert schema_schutz.zu_neu(db) is None


def test_bei_zu_neuer_datenbank_schreibt_das_dashboard_nicht_mehr_lesen_aber_geht(client_db):
    c, db = client_db
    _schema_hochsetzen(db)
    assert c.get("/api/profile").status_code == 200
    r = c.post("/api/profile", json={"name": "Neu"})
    assert r.status_code == 503
    j = r.json()
    assert j["error"] == "datenbank_zu_neu" and "starte beides neu" in j["message"]
    assert db.get_profile()["name"] == "Test", "der schreibende Aufruf darf nichts veraendert haben"


def test_bei_zu_neuer_datenbank_bleiben_die_wege_zur_loesung_offen(client_db, umgebung, netz):
    c, db = client_db
    _schema_hochsetzen(db)
    assert c.post("/api/auto-update/einstellungen", json={"stufe": "hinweis"}).status_code == 200
    assert c.post("/api/auto-update/pruefen").status_code == 200
    assert c.post("/api/sicherungen/wiederherstellen", json={}).status_code != 503
    zu_neu = c.get("/api/health").json()["datenbank_zu_neu"]
    assert zu_neu["datenbank"] > zu_neu["programm"]


def test_bei_normaler_datenbank_schreibt_das_dashboard_wie_immer(client_db):
    c, db = client_db
    assert c.post("/api/profile", json={"name": "Neu"}).status_code == 200
    assert c.get("/api/health").json()["datenbank_zu_neu"] is None


def test_die_gesundheitsantwort_nennt_laufende_fassung_und_die_des_mcp_servers(client_db, umgebung, monkeypatch):
    c, _ = client_db
    from bewerbungs_assistent import heartbeat
    heartbeat._write_heartbeat_file("test", is_alive=True)
    j = c.get("/api/health").json()
    from bewerbungs_assistent import __version__
    assert j["fassung_laufend"] == "1.8.0"
    assert j["mcp_connection"]["version"] == __version__


# ══ Werkzeuge im Chat ════════════════════════════════════════════════════════════════════

class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **_kw):
        def deko(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return deko


@pytest.fixture
def werkzeuge(client_db):
    from bewerbungs_assistent.tools import update
    _, db = client_db
    mcp = FakeMCP()
    update.register(mcp, db, logging.getLogger("test"))
    return mcp.tools, db


def test_update_status_zeigt_dieselbe_uebersicht_wie_das_dashboard(werkzeuge, client_db, umgebung):
    tools, _ = werkzeuge
    c, _ = client_db
    a, b = tools["update_status"](), c.get("/api/auto-update").json()
    assert {k: a[k] for k in ("stufe", "laufend", "aktuell", "installiert", "verfuegbar")} == \
        {k: b[k] for k in ("stufe", "laufend", "aktuell", "installiert", "verfuegbar")}


@pytest.mark.parametrize("stufe", ["auto_meldung", "auto_still"])
def test_eine_automatische_stufe_braucht_die_zustimmung_des_menschen(werkzeuge, umgebung, stufe):
    tools, db = werkzeuge
    r = tools["update_einstellungen_setzen"](stufe=stufe)
    assert r["status"] == "bestaetigung_noetig" and zustand.stufe(db) == "aus"
    r = tools["update_einstellungen_setzen"](stufe=stufe, bestaetigt=True)
    assert r["status"] == "gesetzt" and zustand.stufe(db) == stufe and "stufe" in r["geaendert"]


def test_aus_und_hinweis_brauchen_keine_zustimmung(werkzeuge, umgebung):
    tools, db = werkzeuge
    assert tools["update_einstellungen_setzen"](stufe="hinweis")["status"] == "gesetzt"
    assert tools["update_einstellungen_setzen"](stufe="aus")["status"] == "gesetzt"
    assert zustand.gefragt(db)["antwort"] == "nein"


def test_die_anderen_einstellungen_und_ihre_grenzen(werkzeuge, umgebung):
    tools, db = werkzeuge
    r = tools["update_einstellungen_setzen"](vorgaenger_behalten=2, installer_aufraeumen="nie")
    assert r["status"] == "gesetzt" and set(r["geaendert"]) == {"vorgaenger_behalten", "installer_aufraeumen"}
    assert tools["update_einstellungen_setzen"](vorgaenger_behalten=99)["fehler"]
    assert tools["update_einstellungen_setzen"](installer_aufraeumen="egal")["fehler"]
    assert tools["update_einstellungen_setzen"]()["status"] == "nichts_geaendert"
    assert zustand.vorgaenger_behalten(db) == 2


def test_unbekannte_stufe_im_werkzeug_ist_ein_fehler_ohne_aenderung(werkzeuge, umgebung):
    tools, db = werkzeuge
    assert "fehler" in tools["update_einstellungen_setzen"](stufe="immer", bestaetigt=True)
    assert zustand.stufe(db) == "aus"


def test_jetzt_installieren_verlangt_zustimmung_und_startet_dann_den_lauf(werkzeuge, umgebung, netz, monkeypatch):
    tools, db = werkzeuge
    aufrufe = []
    monkeypatch.setattr(lauf, "starte_installation",
                        lambda db_, version, **kw: aufrufe.append((version, kw)) or {"status": "gestartet", "job_id": "j"})
    r = tools["update_jetzt_installieren"]()
    assert r["status"] == "bestaetigung_noetig" and aufrufe == []
    r = tools["update_jetzt_installieren"](bestaetigt=True)
    assert r["status"] == "gestartet" and r["version"] == "1.8.1" and aufrufe == [("1.8.1", {"ausloeser": "mcp"})]


def test_jetzt_installieren_ohne_neue_version_sagt_das(werkzeuge, umgebung, monkeypatch):
    tools, db = werkzeuge
    monkeypatch.setattr(quelle, "standard_oeffner", lambda: liste(eintrag("v1.8.0")))
    assert tools["update_jetzt_installieren"](bestaetigt=True)["status"] == "keine_neue_version"


def test_zurueckschalten_im_werkzeug(werkzeuge, umgebung):
    tools, _ = werkzeuge
    fassung_anlegen(umgebung, "1.8.1")
    (umgebung / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    assert tools["update_zurueckschalten"]("1.8.0")["status"] == "ok"
    assert tools["update_zurueckschalten"]("1.8.0")["status"] == "nichts_zu_tun"
    assert tools["update_zurueckschalten"]("0.0.1")["status"] == "nicht_moeglich"


def test_die_werkzeuge_sind_als_einstellung_eingeordnet_und_status_ist_nur_lesend():
    from bewerbungs_assistent.services import werkzeug_katalog, werkzeug_schutz
    for name in ("update_status", "update_einstellungen_setzen", "update_jetzt_installieren", "update_zurueckschalten"):
        assert werkzeug_katalog.tag(name) == "einstellung", name
    assert werkzeug_schutz.annotations_fuer("update_status") == {"readOnlyHint": True}
    assert not werkzeug_schutz.annotations_fuer("update_jetzt_installieren").get("readOnlyHint")


def test_bei_zu_neuer_datenbank_weist_die_middleware_werkzeuge_ab_ausser_diagnose(client_db):
    _, db = client_db
    _schema_hochsetzen(db)
    abgewiesen = schema_schutz.werkzeug_abweisen(db, "stellen_bulk_bewerten")
    assert abgewiesen and json.loads(abgewiesen)["error"] == "datenbank_zu_neu"
    for erlaubt in schema_schutz.ERLAUBTE_WERKZEUGE:
        assert schema_schutz.werkzeug_abweisen(db, erlaubt) is None
    schema_schutz.zuruecksetzen()


def test_die_erlaubten_werkzeuge_im_schema_schutz_gibt_es_wirklich(tmp_path):
    """Ein Tippfehler in der Liste haette zur Folge, dass ein Diagnosewerkzeug genau dann gesperrt waere, wenn man es braucht."""
    import asyncio
    import logging as lg
    from fastmcp import FastMCP
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.tools import register_all
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    try:
        db = Database(db_path=tmp_path / "t.db")
        db.initialize()
        mcp = FastMCP("t")
        register_all(mcp, db, lg.getLogger("t"))
        namen = {t.name for t in asyncio.run(mcp.list_tools())}
        db.close()
    finally:
        os.environ.pop("BA_DATA_DIR", None)
    assert schema_schutz.ERLAUBTE_WERKZEUGE <= namen, sorted(schema_schutz.ERLAUBTE_WERKZEUGE - namen)
