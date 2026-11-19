"""#1396 Schicht 4 - der Nachlernlauf "KI lernt nach".

Im Leerlauf, in Portionen, begrenzt, BLIND, nur bei eingeschalteter KI. Alle
Datenbanken sind isoliert (BA_DATA_DIR); die echte lokale KI (Ollama, Port 11434)
wird nie erreicht: ein Testdoppel ersetzt den Dienst.
"""
from __future__ import annotations

import os
import threading
import time
from types import SimpleNamespace

import pytest

TEXT = ("Aufgaben: Konstruktion von Maschinen und Anlagen im Team. "
        "Anforderungen: mehrjaehrige Erfahrung und sicheres Deutsch. ") * 2


class _KI:
    """Testdoppel: antwortet nach Titelwort; haelt jede Nutzlast fest."""

    def __init__(self, antworten=None, fehler=False):
        self.antworten = antworten or {}
        self.fehler = fehler
        self.payloads = []
        self.aufrufe = 0

    def get_status(self, force_refresh=False):
        return SimpleNamespace(ollama_available=True, available_models=["m"],
                               user_state="active", selected_model="m")

    def warmup(self):
        return {"status": "warm", "duration_sec": 0}

    def run(self, kind, payload):
        self.aufrufe += 1
        self.payloads.append(payload)
        if self.fehler:
            return SimpleNamespace(success=False, fallback_message="aus", payload=None)
        for wort, urteil in self.antworten.items():
            if wort in payload["job_title"]:
                return SimpleNamespace(success=True, fallback_message="", payload={
                    "decision": urteil, "reason": "Falsche Branche.", "sicherheit": "klar"})
        return SimpleNamespace(success=True, fallback_message="", payload={
            "decision": "PASST", "reason": "Passt.", "sicherheit": "klar"})


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test 1396d"})
    yield d
    for t in threading.enumerate():
        if t.name == "pbp-ki-nachlernen":
            t.join(15)
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _an(db):
    db.set_profile_setting("llm_local_state", "active")


def _entschieden(db, kennung, titel, *, wer="mensch", grund="falsche_branche", notiz=""):
    db.save_jobs([{
        "hash": kennung, "title": titel, "company": "Musterwerk Nord GmbH",
        "location": "Hamburg", "url": f"https://example.com/1396d/{kennung}",
        "source": "stepstone", "description": TEXT, "score": 20,
    }])
    voll = db.resolve_job_hash(kennung)
    if wer == "mensch":
        assert db.dismiss_job(voll, grund, herkunft="ich", notiz=notiz)
    else:
        db.set_job_analysis(voll, "EMPFOHLEN", "Passt nach dem Lesen gut zu den Aufgaben.")
    return voll


def _z(db, voll):
    return dict(db.connect().execute("SELECT * FROM jobs WHERE hash=?", (voll,)).fetchone())


def test_ki_aus_keine_laeufe_keine_wartezeit_marker_trotzdem(db, monkeypatch):
    from bewerbungs_assistent.services import ki_nachlernen, llm_service
    ki = _KI()
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db=None: ki)
    voll = _entschieden(db, "a1", "Konstrukteur Maschinenbau")
    t0 = time.perf_counter()
    assert ki_nachlernen.tick(db) == {"status": "ki_aus"}
    assert ki_nachlernen.portion(db)["status"] == "ki_aus"
    assert time.perf_counter() - t0 < 0.5, "Bei ausgeschalteter KI gibt es keine Wartezeit."
    assert ki.aufrufe == 0
    assert not [t for t in threading.enumerate() if t.name == "pbp-ki-nachlernen"]
    assert _z(db, voll)["entschieden_von"] == "mensch", "Marker werden trotzdem gefuehrt."
    # "pausiert" ist nicht eingeschaltet
    db.set_profile_setting("llm_local_state", "paused")
    assert ki_nachlernen.tick(db)["status"] == "ki_aus"


def test_portion_vergleicht_blind_und_speichert_die_gegenprobe(db):
    from bewerbungs_assistent.services import ki_nachlernen
    _an(db)
    richtig = _entschieden(db, "r1", "Konstrukteur Maschinenbau")      # Mensch: passt nicht
    falsch = _entschieden(db, "r2", "Konstrukteur Anlagenbau")         # KI sagt PASST -> falsch
    ja = _entschieden(db, "r3", "Konstrukteur Fahrzeugbau", wer="claude")  # Claude: passt
    ki = _KI({"Maschinenbau": "PASST_NICHT", "Fahrzeugbau": "PASST"})
    erg = ki_nachlernen.portion(db, svc=ki)
    assert (erg["geprueft"], erg["richtig"], erg["falsch"]) == (3, 2, 1)
    assert _z(db, richtig)["ollama_lag_richtig"] == 1
    assert _z(db, falsch)["ollama_lag_richtig"] == 0
    assert _z(db, ja)["ollama_lag_richtig"] == 1
    z = _z(db, richtig)
    assert z["ollama_urteil"] == "PASST_NICHT" and z["ollama_gesehen_am"]
    assert z["ollama_sicherheit"] == "klar" and z["is_active"] == 0
    assert z["entschieden_von"] == "mensch", "Das Nachlernen aendert nie die Entscheidung."
    # BLIND: die eigene Stelle steht nie unter den Beispielen, ihre Entscheidung nie im Prompt
    for payload in ki.payloads:
        assert payload["job_title"] not in [b["titel"] for b in payload["lern_beispiele"]]
        assert "dismiss_reason" not in payload and "entscheidung" not in payload
    # Die Abweichung ist ab jetzt ein Gegenbeispiel und steht zuerst
    from bewerbungs_assistent.services import ki_beispiele
    bsp = ki_beispiele.waehlen(
        ki_beispiele.pool_laden(db), {"hash": "n", "title": "Konstrukteur Anlagenbau", "description": ""})
    assert bsp[0]["gegenbeispiel"] is True


def test_dieselbe_stelle_wird_nicht_zweimal_gelernt(db):
    from bewerbungs_assistent.services import ki_nachlernen
    _an(db)
    _entschieden(db, "z1", "Konstrukteur Maschinenbau")
    ki = _KI()
    assert ki_nachlernen.portion(db, svc=ki)["geprueft"] == 1
    assert ki_nachlernen.portion(db, svc=ki)["status"] == "nichts_zu_tun"
    assert ki.aufrufe == 1


def test_automatische_entscheidungen_sind_kein_lernstoff(db):
    from bewerbungs_assistent.services import ki_nachlernen
    _an(db)
    db.save_jobs([{"hash": "au1", "title": "Konstrukteur", "company": "Musterwerk Nord GmbH",
                   "url": "https://example.com/au1", "source": "stepstone",
                   "description": TEXT, "score": 5}])
    voll = db.resolve_job_hash("au1")
    db.dismiss_job(voll, "profil_match_negativ", herkunft="automatik",
                   notiz="[Auto-Aussortierung] x", entschieden_von="ollama")
    assert ki_nachlernen.kandidaten(db) == []


def test_portion_ist_begrenzt_in_menge_zeit_und_woche(db, monkeypatch):
    from bewerbungs_assistent.services import ki_nachlernen
    _an(db)
    for i in range(10):
        _entschieden(db, f"b{i}", f"Konstrukteur Variante {i}")
    ki = _KI()
    assert ki_nachlernen.portion(db, svc=ki, max_stellen=3)["geprueft"] == 3
    # Wochenbudget: noch zwei uebrig
    erg = ki_nachlernen.portion(db, svc=ki, max_stellen=6, wochenbudget=5)
    assert erg["geprueft"] == 2
    assert ki_nachlernen.portion(db, svc=ki, wochenbudget=5)["status"] == "wochenbudget"
    # Zeit: die Uhr springt nach dem ersten Aufruf ueber die Grenze
    uhr = iter([0.0, 0.0, 500.0, 500.0, 500.0, 500.0, 500.0])
    monkeypatch.setattr(ki_nachlernen.time, "monotonic", lambda: next(uhr, 500.0))
    teil = ki_nachlernen.portion(db, svc=ki, max_stellen=6, max_dauer_sek=100)
    assert teil["status"] == "teilweise" and teil["geprueft"] == 1


def test_zwei_fehler_in_folge_beenden_die_portion(db):
    from bewerbungs_assistent.services import ki_nachlernen
    _an(db)
    for i in range(4):
        _entschieden(db, f"f{i}", f"Konstrukteur Variante {i}")
    ki = _KI(fehler=True)
    erg = ki_nachlernen.portion(db, svc=ki)
    assert erg["status"] == "abgebrochen" and ki.aufrufe == 2 and erg["geprueft"] == 0


def test_bevorzugt_stellen_mit_begruendung(db):
    from bewerbungs_assistent.services import ki_nachlernen
    _entschieden(db, "p1", "Konstrukteur Variante eins")
    mit = _entschieden(db, "p2", "Konstrukteur Variante zwei", notiz="Branche passt nicht zu mir.")
    erste = ki_nachlernen.kandidaten(db, limit=1)
    assert erste[0]["hash"] == mit


def test_tick_startet_nur_im_leerlauf(db, monkeypatch):
    from bewerbungs_assistent.services import ki_nachlernen, llm_service
    _an(db)
    _entschieden(db, "t1", "Konstrukteur Maschinenbau")
    ki = _KI()
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db=None: ki)
    stop = threading.Event()
    fremd = threading.Thread(target=stop.wait, name="pbp-jobsuche-test", daemon=True)
    fremd.start()
    try:
        erg = ki_nachlernen.tick(db)
        assert erg["status"] == "beschaeftigt" and "pbp-jobsuche-test" in erg["arbeit"]
        assert ki.aufrufe == 0
    finally:
        stop.set()
        fremd.join(5)
    assert ki_nachlernen.tick(db)["status"] == "gestartet"
    for t in threading.enumerate():
        if t.name == "pbp-ki-nachlernen":
            t.join(15)
    assert ki.aufrufe == 1
    jobs = db.connect().execute(
        "SELECT status FROM background_jobs WHERE job_type='ki_nachlernen'").fetchall()
    assert [j[0] for j in jobs] == ["fertig"]


def test_tick_ist_im_scheduler_angeschlossen(db, monkeypatch):
    """Ein Schutz zaehlt erst, wenn er aufgerufen wird (8c): der Takt ruft den Lauf."""
    from bewerbungs_assistent.services import automatik_scheduler, ki_nachlernen
    gerufen = []
    monkeypatch.setattr(ki_nachlernen, "tick", lambda d, *a, **k: gerufen.append(d) or {})
    monkeypatch.setattr("bewerbungs_assistent.services.sicherung.taeglich", lambda d: None)
    automatik_scheduler._tick(db)
    assert gerufen == [db]


def test_ein_fehler_im_lauf_stoppt_den_takt_nicht(db, monkeypatch):
    from bewerbungs_assistent.services import automatik_scheduler, ki_nachlernen
    def kaputt(d, *a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(ki_nachlernen, "tick", kaputt)
    monkeypatch.setattr("bewerbungs_assistent.services.sicherung.taeglich", lambda d: None)
    automatik_scheduler._tick(db)  # wirft nicht
