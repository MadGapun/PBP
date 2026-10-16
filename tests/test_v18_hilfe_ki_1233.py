"""#1233 (F51) - die KI-Schicht der interaktiven Hilfe und die Endpunkte.

Die lokale KI formuliert hoechstens eine Kurzantwort UEBER den Karten. Sie darf nur umformulieren, was in den drei besten Abschnitten steht:
die Antwort wird geprueft (Quelle genannt, nichts erfunden), sonst bleibt die Karte. Die Suite braucht kein Ollama: das Modell ist ein Testdouble
(`erzeuger`), der Zustand der lokalen KI ein Stand-in. Frage und Antwort werden nicht gespeichert.
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "src"))

from bewerbungs_assistent.services import hilfe_ki, hilfe_suche  # noqa: E402

ABSCHNITTE = [
    {"id": "faq:wie_aktualisiere_ich_pbp", "titel": "Wie aktualisiere ich PBP?",
     "text": "Einstellungen › Erweitert › Updates: PBP sagt Bescheid, wenn es eine neue Version gibt, und installiert sie auf Wunsch mit einem Klick. "
             "Danach PBP und Claude Desktop neu starten. Der Befehl `python scripts/start_dashboard.py` startet das Dashboard."},
    {"id": "hilfe:einstellungen:updates", "titel": "Updates",
     "text": "Unter Erweitert › Updates wählst du, wie neue Versionen auf den Rechner kommen. Mehr unter https://github.com/MadGapun/PBP/wiki/Updates."},
    {"id": "wiki:Updates:die_vier_stufen", "titel": "Die vier Stufen", "text": "Nur Hinweis, mit einem Klick, automatisch mit Meldung, automatisch still."},
]


# ── die Pruefung ────────────────────────────────────────────────────────────────────────────

def test_eine_antwort_mit_quelle_besteht():
    r = hilfe_ki.pruefen("Du findest es unter Erweitert › Updates [1]. Dort wählst du die Stufe [3].", ABSCHNITTE)
    assert r["ok"]
    assert r["quellen"] == ["faq:wie_aktualisiere_ich_pbp", "wiki:Updates:die_vier_stufen"]
    assert "[" not in r["text"] and "  " not in r["text"]
    assert r["text"] == "Du findest es unter Erweitert › Updates. Dort wählst du die Stufe."


@pytest.mark.parametrize("text, grund", [
    ("", "leer"),
    ("   \n", "leer"),
    ("KEINE ANTWORT", "keine_antwort"),
    ("Keine Antwort", "keine_antwort"),
    ("Das steht in den Einstellungen.", "ohne_quelle"),
    ("Das steht in den Einstellungen [4].", "fremde_quelle"),
    ("Das steht in den Einstellungen [0].", "fremde_quelle"),
    ("Sieh nach [1]. " * 80, "zu_lang"),
    ("Mehr dazu auf https://boese.example/anmelden [1].", "erfundene_adresse"),
    ("Starte mit `pbp erfunden --jetzt` [1].", "erfundener_befehl"),
    ("Das findest du unter Einstellungen › Erfundener Reiter [1].", "erfundener_pfad"),
])
def test_eine_unbrauchbare_antwort_wird_verworfen(text, grund):
    r = hilfe_ki.pruefen(text, ABSCHNITTE)
    assert not r["ok"] and r["grund"] == grund, r


def test_was_in_den_abschnitten_steht_darf_vorkommen():
    """Adresse, Befehl und Pfad sind nicht verboten, sondern nur, wenn sie erfunden sind."""
    ok = hilfe_ki.pruefen("Mehr dazu auf https://github.com/MadGapun/PBP/wiki/Updates [2].", ABSCHNITTE)
    assert ok["ok"], ok
    ok = hilfe_ki.pruefen("Das Dashboard startet mit `python scripts/start_dashboard.py` [1].", ABSCHNITTE)
    assert ok["ok"], ok
    ok = hilfe_ki.pruefen("Du findest es unter Erweitert › Updates [1].", ABSCHNITTE)
    assert ok["ok"], ok


def test_der_prompt_nennt_frage_abschnitte_und_regeln():
    p = hilfe_ki.prompt_bauen("Wie aktualisiere ich PBP?", ABSCHNITTE)
    assert "FRAGE: Wie aktualisiere ich PBP?" in p
    assert "ABSCHNITT [1] Wie aktualisiere ich PBP?:" in p and "ABSCHNITT [3] Die vier Stufen:" in p
    assert "KEINE ANTWORT" in p and "Erfinde nichts" in p and p.rstrip().endswith("ANTWORT:")


def test_ein_langer_abschnitt_wird_im_prompt_gekuerzt():
    lang = [{"id": "x", "titel": "T", "text": "wort " * 1000}]
    p = hilfe_ki.prompt_bauen("f", lang)
    assert len(p) < len(hilfe_ki.ANWEISUNG) + 200 + hilfe_ki.MAX_ABSCHNITT_ZEICHEN + 50


def test_die_anweisung_an_das_modell_steht_in_umschrift():
    """Prompts an die lokale KI bleiben in Umschrift (CLAUDE.md, Umlaut-Regel)."""
    assert all(c not in hilfe_ki.ANWEISUNG for c in "äöüÄÖÜß")


# ── der Schalter und der Zustand ────────────────────────────────────────────────────────────

def test_die_kurzantwort_ist_vorgabe_aus_und_wird_vom_menschen_gesetzt(tmp_db):
    """Nutzerentscheidung 16.10.2026: reicht die Messung nicht, bleibt die KI-Antwort als Beta aus."""
    assert hilfe_ki.VORGABE_AN is False
    tmp_db.create_profile("Test", "test@example.com")
    assert hilfe_ki.einstellung(tmp_db) is False
    assert hilfe_ki.einstellung_setzen(tmp_db, True) == {"formulieren": True}
    assert hilfe_ki.einstellung(tmp_db) is True
    assert hilfe_ki.einstellung_setzen(tmp_db, False) == {"formulieren": False}
    assert hilfe_ki.einstellung(tmp_db) is False


def _llm(monkeypatch, **status):
    stand = dict(ollama_available=True, user_state="active", selected_model="qwen3:8b")
    stand.update(status)
    svc = SimpleNamespace(get_status=lambda: SimpleNamespace(**stand))
    from bewerbungs_assistent.services import llm_service
    monkeypatch.setattr(llm_service, "get_llm_service", lambda db=None: svc)


@pytest.mark.parametrize("status, grund", [
    ({}, ""),
    ({"ollama_available": False}, "ollama_nicht_erreichbar"),
    ({"user_state": "off"}, "ki_off"),
    ({"user_state": "paused"}, "ki_paused"),
    ({"selected_model": None}, "kein_modell"),
])
def test_zustand_der_lokalen_ki(monkeypatch, tmp_db, status, grund):
    _llm(monkeypatch, **status)
    z = hilfe_ki.zustand(tmp_db)
    assert z["aktiv"] == (grund == "")
    assert z["grund"] == grund
    assert z["modell"] == ("qwen3:8b" if grund == "" else None)


def test_ein_fehler_beim_zustand_ist_kein_absturz(monkeypatch, tmp_db):
    from bewerbungs_assistent.services import llm_service

    def kaputt(db=None):
        raise RuntimeError("kein Dienst")
    monkeypatch.setattr(llm_service, "get_llm_service", kaputt)
    assert hilfe_ki.zustand(tmp_db) == {"aktiv": False, "grund": "unbekannt", "modell": None}


# ── anstossen: wann entsteht eine Kurzantwort ───────────────────────────────────────────────

@pytest.fixture
def wissen():
    return hilfe_suche.laden()


@pytest.fixture
def sicher(wissen):
    a = hilfe_suche.antwort("Wie aktualisiere ich PBP?", wissen=wissen)
    assert a["status"] == "gefunden"
    return a


def _bereit(monkeypatch, tmp_db, an=True):
    tmp_db.create_profile("Test", "test@example.com")
    _llm(monkeypatch)
    hilfe_ki.einstellung_setzen(tmp_db, an)


def test_ohne_anfrage_keine_kurzantwort(tmp_db, sicher, wissen, monkeypatch):
    _bereit(monkeypatch, tmp_db)
    assert hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=False) == {"status": "aus", "grund": "nicht_angefragt"}


def test_bei_einem_unsicheren_treffer_wird_nicht_formuliert(tmp_db, wissen, monkeypatch):
    _bereit(monkeypatch, tmp_db)
    a = dict(hilfe_suche.antwort("Wie aktualisiere ich PBP?", wissen=wissen), status="unsicher")
    assert hilfe_ki.anstossen(tmp_db, a, wissen, mit_ki=True)["grund"] == "keine_sichere_antwort"
    a["status"] = "nichts_gefunden"
    assert hilfe_ki.anstossen(tmp_db, a, wissen, mit_ki=True)["grund"] == "keine_sichere_antwort"


def test_der_schalter_aus_verhindert_die_kurzantwort(tmp_db, sicher, wissen, monkeypatch):
    _bereit(monkeypatch, tmp_db, an=False)
    assert hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True) == {"status": "aus", "grund": "schalter_aus"}


def test_eine_nicht_bereite_ki_nennt_den_grund(tmp_db, sicher, wissen, monkeypatch):
    _bereit(monkeypatch, tmp_db)
    _llm(monkeypatch, user_state="paused")
    assert hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True) == {"status": "aus", "grund": "ki_paused"}


def test_eine_kurzantwort_entsteht_und_wird_gelesen(tmp_db, sicher, wissen, monkeypatch):
    _bereit(monkeypatch, tmp_db)
    prompts = []

    def modell(prompt):
        prompts.append(prompt)
        return "Du findest es unter Erweitert › Updates [1]."
    start = hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True, erzeuger=modell, synchron=True)
    assert start["status"] == "laeuft" and start["job"]
    stand = hilfe_ki.lesen(start["job"])
    assert stand["status"] == "fertig" and "Updates" in stand["text"] and stand["quellen"]
    assert len(prompts) == 1 and "Wie aktualisiere ich PBP?" in prompts[0]


def test_eine_verworfene_antwort_laesst_die_karte_stehen(tmp_db, sicher, wissen, monkeypatch):
    _bereit(monkeypatch, tmp_db)
    start = hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True, erzeuger=lambda p: "Einfach den Knopf drücken.", synchron=True)
    stand = hilfe_ki.lesen(start["job"])
    assert stand["status"] == "verworfen" and stand["grund"] == "ohne_quelle" and stand["text"] == ""


def test_ein_fehler_des_modells_wird_ein_grund_kein_absturz(tmp_db, sicher, wissen, monkeypatch):
    _bereit(monkeypatch, tmp_db)

    def kaputt(prompt):
        raise TimeoutError("zu langsam")
    stand = hilfe_ki.lesen(hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True, erzeuger=kaputt, synchron=True)["job"])
    assert stand["status"] == "fehler" and stand["grund"] == "fehler"

    class KontextZuKlein(Exception):
        pass

    def zu_gross(prompt):
        raise KontextZuKlein("passt nicht")
    stand = hilfe_ki.lesen(hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True, erzeuger=zu_gross, synchron=True)["job"])
    assert stand["grund"] == "kontext"


def test_ein_unbekannter_auftrag_ist_unbekannt():
    assert hilfe_ki.lesen("gibt-es-nicht") == {"status": "unbekannt"}
    assert hilfe_ki.lesen("") == {"status": "unbekannt"}
    assert hilfe_ki.lesen(None) == {"status": "unbekannt"}


def test_im_hintergrund_laeuft_die_antwort_nach(tmp_db, sicher, wissen, monkeypatch):
    _bereit(monkeypatch, tmp_db)
    freigabe = threading.Event()

    def langsam(prompt):
        freigabe.wait(5)
        return "Unter Erweitert › Updates [1]."
    start = hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True, erzeuger=langsam)
    assert hilfe_ki.lesen(start["job"])["status"] == "laeuft"
    freigabe.set()
    for _ in range(100):
        if hilfe_ki.lesen(start["job"])["status"] != "laeuft":
            break
        time.sleep(0.05)
    assert hilfe_ki.lesen(start["job"])["status"] == "fertig"
    for t in threading.enumerate():
        if t.name.startswith("pbp-hilfe-ki"):
            t.join(timeout=5)


def test_viele_fragen_hintereinander_stapeln_keine_auftraege(tmp_db, sicher, wissen, monkeypatch):
    """Die lokale KI antwortet eine nach der anderen: ab MAX_OFFENE_AUFTRAEGE offenen Auftraegen gibt es zur naechsten Frage nur die Karten."""
    _bereit(monkeypatch, tmp_db)
    with hilfe_ki._LOCK:
        hilfe_ki._JOBS.clear()
    freigabe = threading.Event()

    def langsam(prompt):
        freigabe.wait(5)
        return "Unter Erweitert › Updates [1]."
    try:
        starts = [hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True, erzeuger=langsam) for _ in range(hilfe_ki.MAX_OFFENE_AUFTRAEGE)]
        assert all(s["status"] == "laeuft" for s in starts)
        assert hilfe_ki.offene_auftraege() == hilfe_ki.MAX_OFFENE_AUFTRAEGE
        assert hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True, erzeuger=langsam) == {"status": "aus", "grund": "beschaeftigt"}
    finally:
        freigabe.set()
        for t in threading.enumerate():
            if t.name.startswith("pbp-hilfe-ki"):
                t.join(timeout=5)
    # danach ist wieder Platz
    assert hilfe_ki.offene_auftraege() == 0
    nochmal = hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True, erzeuger=lambda p: "Bei Updates [1].", synchron=True)
    assert nochmal["status"] == "laeuft"


def test_auftraege_verschwinden_nach_der_lebensdauer(tmp_db, sicher, wissen, monkeypatch):
    _bereit(monkeypatch, tmp_db)
    job = hilfe_ki.anstossen(tmp_db, sicher, wissen, mit_ki=True, erzeuger=lambda p: "Bei Updates [1].", synchron=True)["job"]
    assert hilfe_ki.lesen(job)["status"] == "fertig"
    assert hilfe_ki.aufraeumen(time.monotonic() + hilfe_ki.JOB_LEBENSDAUER_SEK + 1) >= 1
    assert hilfe_ki.lesen(job) == {"status": "unbekannt"}


# ── Datenschutz: nichts bleibt liegen ───────────────────────────────────────────────────────

def test_frage_und_antwort_bleiben_nirgends_liegen(tmp_db, wissen, monkeypatch, caplog):
    _bereit(monkeypatch, tmp_db)
    caplog.set_level(logging.DEBUG)
    geheim = "Zebrastreifen Quartz 7731"
    a = dict(hilfe_suche.antwort("Wie aktualisiere ich PBP?", wissen=wissen), frage=f"Wie aktualisiere ich PBP? {geheim}")
    vor = {t: tmp_db.connect().execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
           for t in ("elwosa_messages", "background_jobs", "user_activity_events")}
    job = hilfe_ki.anstossen(tmp_db, a, wissen, mit_ki=True, erzeuger=lambda p: "Bei Updates [1].", synchron=True)["job"]
    stand = hilfe_ki.lesen(job)
    assert geheim not in str(stand), "der Auftrag traegt die Frage"
    assert all(geheim not in str(v) for v in hilfe_ki._JOBS.values())
    assert not [r for r in caplog.records if "Zebrastreifen" in r.getMessage()]
    nach = {t: tmp_db.connect().execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in vor}
    assert nach == vor, "die Hilfe hat in die Datenbank geschrieben"


# ── Endpunkte ───────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_db, monkeypatch):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    tmp_db.create_profile("Test", "test@example.com")
    monkeypatch.setattr(dash, "_db", tmp_db)
    _llm(monkeypatch)
    return TestClient(dash.app)


def test_die_frage_liefert_karten(client):
    r = client.post("/api/hilfe/frage", json={"frage": "Wie aktualisiere ich PBP?"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "gefunden" and d["karten"] and d["frage"] == "Wie aktualisiere ich PBP?"
    assert d["ki"] == {"status": "aus", "grund": "nicht_angefragt"}
    assert d["karten"][0]["quelle"]


def test_eine_frage_ausserhalb_bekommt_den_satz_fuer_claude(client):
    d = client.post("/api/hilfe/frage", json={"frage": "Wie wird das Wetter morgen?"}).json()
    assert d["status"] == "ausserhalb" and d["karten"] == [] and "Wetter" in d["claude"]["satz"]


def test_falsche_eingaben_werden_abgewiesen(client):
    assert client.post("/api/hilfe/frage", json={"frage": 5}).status_code == 400
    assert client.post("/api/hilfe/frage", json=[1, 2]).status_code == 400
    assert client.post("/api/hilfe/frage", content=b"kein json", headers={"Content-Type": "application/json"}).status_code == 400
    assert client.post("/api/hilfe/frage", json={}).json()["status"] == "leer"
    # eine Nachfrage, die nicht als Text ankommt, ist keine Nachfrage
    assert client.post("/api/hilfe/frage", json={"frage": "Wie aktualisiere ich PBP?", "vorherige": 7}).status_code == 200


def test_fehlen_die_daten_ist_es_ein_503(client, monkeypatch):
    monkeypatch.setattr(hilfe_suche, "verfuegbar", lambda: False)
    r = client.post("/api/hilfe/frage", json={"frage": "Wie aktualisiere ich PBP?"})
    assert r.status_code == 503 and "fehlen" in r.json()["error"]


def test_mit_ki_und_schalter_entsteht_ein_auftrag(client, tmp_db, monkeypatch):
    hilfe_ki.einstellung_setzen(tmp_db, True)
    monkeypatch.setattr(hilfe_ki, "_erzeugen", lambda db, modell: (lambda prompt: "Unter Erweitert › Updates [1]."))
    d = client.post("/api/hilfe/frage", json={"frage": "Wie aktualisiere ich PBP?", "mit_ki": True}).json()
    assert d["ki"]["status"] == "laeuft"
    for _ in range(100):
        stand = client.get(f"/api/hilfe/ki/{d['ki']['job']}").json()
        if stand["status"] != "laeuft":
            break
        time.sleep(0.05)
    assert stand["status"] == "fertig" and "Updates" in stand["text"]
    for t in threading.enumerate():
        if t.name.startswith("pbp-hilfe-ki"):
            t.join(timeout=5)


def test_mit_ki_aber_schalter_aus_bleibt_es_bei_den_karten(client):
    d = client.post("/api/hilfe/frage", json={"frage": "Wie aktualisiere ich PBP?", "mit_ki": True}).json()
    assert d["ki"] == {"status": "aus", "grund": "schalter_aus"} and d["karten"]


def test_ein_unbekannter_auftrag_ist_unbekannt_am_endpunkt(client):
    assert client.get("/api/hilfe/ki/gibt-es-nicht").json() == {"status": "unbekannt"}


def test_der_schalter_laesst_sich_lesen_und_setzen(client):
    d = client.get("/api/hilfe/ki").json()
    assert d["formulieren"] is False and d["zustand"]["aktiv"] is True
    assert client.put("/api/hilfe/ki", json={"formulieren": True}).json() == {"formulieren": True}
    assert client.get("/api/hilfe/ki").json()["formulieren"] is True
    assert client.put("/api/hilfe/ki", json={"formulieren": "ja"}).status_code == 400
    assert client.put("/api/hilfe/ki", json={}).status_code == 400
    assert client.put("/api/hilfe/ki", json={"formulieren": False}).json() == {"formulieren": False}


def test_die_endpunkte_schreiben_die_frage_nicht_ins_protokoll(client, caplog):
    caplog.set_level(logging.DEBUG)
    client.post("/api/hilfe/frage", json={"frage": "Zebrastreifen Quartz 7731 PBP aktualisieren?"})
    assert not [r for r in caplog.records if "Zebrastreifen" in r.getMessage()]


def test_bei_zu_neuer_datenbank_antwortet_die_hilfe_weiter_nur_der_schalter_bleibt_gesperrt(client, tmp_db):
    """Schema-Schutz: eine zu neue Datenbank sperrt schreibende Aufrufe. Die Frage ist ein POST (damit sie nie in einer Adresse steht), schreibt
    aber nichts - gerade dann, nach einem Rueckschritt auf eine aeltere Fassung, wird die Hilfe gebraucht."""
    from bewerbungs_assistent.database import SCHEMA_VERSION
    from bewerbungs_assistent.services import schema_schutz
    tmp_db.connect().execute("UPDATE settings SET value=? WHERE key='schema_version'", (str(SCHEMA_VERSION + 1),))
    tmp_db.connect().commit()
    schema_schutz.zuruecksetzen()
    try:
        assert schema_schutz.zu_neu(tmp_db) is not None, "Voraussetzung: die Datenbank gilt als zu neu"
        r = client.post("/api/hilfe/frage", json={"frage": "Wie aktualisiere ich PBP?"})
        assert r.status_code == 200 and r.json()["status"] == "gefunden"
        assert client.get("/api/hilfe/ki").status_code == 200
        gesperrt = client.put("/api/hilfe/ki", json={"formulieren": True})
        assert gesperrt.status_code == 503 and gesperrt.json()["error"] == "datenbank_zu_neu", "der Schalter schreibt und muss gesperrt bleiben"
    finally:
        schema_schutz.zuruecksetzen()
