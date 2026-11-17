"""#1396 Schicht 2 - Beispiele nach Aehnlichkeit statt nach Datum.

Regeln: nur Entscheidungen von Mensch und Claude, nie automatische (#1239,
#1395); aehnlichste zuerst, gemischt passt/passt nicht; Claude mit Begruendung
vor Mensch mit Grund vor Mensch ohne Grund; bekannte Fehler der KI zuerst;
Kurzform; ganze Woerter. Alle Datenbanken sind isoliert (BA_DATA_DIR).
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

ANFORDERUNGEN = ("Ihr Profil:\n- Studium Maschinenbau oder vergleichbar\n"
                 "- mehrjaehrige Erfahrung in der Konstruktion\n"
                 "- sicherer Umgang mit CAD-Systemen\n- Reisebereitschaft\n")


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test 1396b"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung, titel, text="Wir suchen Verstaerkung fuer unser Team in Hamburg. " * 3):
    db.save_jobs([{
        "hash": kennung, "title": titel, "company": "Musterwerk Nord GmbH",
        "location": "Hamburg", "url": f"https://example.com/1396b/{kennung}",
        "source": "stepstone", "description": text, "score": 20,
    }])
    return db.resolve_job_hash(kennung)


def _mensch_nein(db, kennung, titel, grund="falsches_fachgebiet", notiz="", text=None):
    voll = _stelle(db, kennung, titel, **({"text": text} if text else {}))
    assert db.dismiss_job(voll, grund, herkunft="ich", notiz=notiz)
    return voll


def _pool(db):
    from bewerbungs_assistent.services import ki_beispiele
    return ki_beispiele.pool_laden(db)


def _titel(beispiele):
    return [b["titel"] for b in beispiele]


def test_aehnlichste_stellen_kommen_zuerst_nicht_die_neuesten(db):
    from bewerbungs_assistent.services import ki_beispiele
    _mensch_nein(db, "a1", "Leiter Konstruktion Maschinenbau")
    _mensch_nein(db, "a2", "Sachbearbeiter Einkauf")
    for i in range(12):  # viele neuere, aber fachfremde Entscheidungen
        _mensch_nein(db, f"z{i}", f"Erzieher Kita Nord {i}")
    job = {"hash": "neu", "title": "Konstruktionsleiter Maschinenbau",
           "description": "Konstruktion von Maschinen"}
    bsp = ki_beispiele.waehlen(_pool(db), job, limit=4)
    assert bsp and bsp[0]["titel"] == "Leiter Konstruktion Maschinenbau"
    assert not any("Kita" in t for t in _titel(bsp))


def test_ganze_woerter_ki_steckt_nicht_in_kita(db):
    from bewerbungs_assistent.services import ki_beispiele
    _mensch_nein(db, "w1", "Kita Leitung")
    pool = _pool(db)
    t_job = ki_beispiele.stamm_menge("KI Entwickler")
    assert not (t_job & pool[0]["_titel"])
    assert ki_beispiele.aehnlichkeit(t_job, set(), pool[0]["_titel"], set()) == 0


def test_automatische_entscheidungen_sind_nie_ein_beispiel(db):
    from bewerbungs_assistent.services import ki_beispiele
    v = _stelle(db, "x1", "Leiter Konstruktion Maschinenbau")
    db.dismiss_job(v, "profil_match_negativ", herkunft="automatik",
                   notiz="[Auto-Aussortierung] Falsche Branche.",
                   entschieden_von="ollama")
    v2 = _stelle(db, "x2", "Konstruktion Leiter Anlagenbau")
    db.dismiss_job(v2, "duplikat", herkunft="automatik")
    v3 = _stelle(db, "x3", "Leiter Konstruktion Fahrzeuge")
    conn = db.connect()
    conn.execute("UPDATE jobs SET is_active=0, dismiss_reason='zu_junior', "
                 "dismissed_by=NULL, entschieden_von='unbekannt' WHERE hash=?", (v3,))
    conn.commit()
    assert _pool(db) == [], "Automatik und Unbekanntes sind kein Beleg."
    job = {"hash": "n", "title": "Leiter Konstruktion", "description": ""}
    assert ki_beispiele.waehlen(_pool(db), job) == []


def test_gemischt_passt_und_passt_nicht(db):
    from bewerbungs_assistent.services import ki_beispiele
    for i in range(5):
        _mensch_nein(db, f"n{i}", f"Projektleiter Maschinenbau Variante {i}")
    for i in range(3):
        v = _stelle(db, f"p{i}", f"Projektleiter Maschinenbau Erfolg {i}")
        db.set_job_analysis(v, "EMPFOHLEN", "Passt, weil die Erfahrung es abdeckt.")
    job = {"hash": "n", "title": "Projektleiter Maschinenbau", "description": ""}
    bsp = ki_beispiele.waehlen(_pool(db), job, limit=6)
    klassen = [b["klasse"] for b in bsp]
    assert "passt" in klassen and "passt_nicht" in klassen
    assert klassen.count("passt") >= 2


def test_gewichtung_claude_vor_mensch_mit_grund_vor_mensch_ohne(db):
    from bewerbungs_assistent.services import ki_beispiele
    titel = "Konstruktion Projektleiter Hydraulik"
    _mensch_nein(db, "g1", titel, grund="sonstiges")
    _mensch_nein(db, "g2", titel, grund="falsche_branche", notiz="Branche passt nicht.")
    v = _stelle(db, "g3", titel)
    db.dismiss_job(v, "zu_junior", herkunft="claude")
    db.set_job_analysis(v, "NICHT_EMPFOHLEN", "Zu junge Rolle fuer dieses Profil.")
    bsp = ki_beispiele.waehlen(_pool(db), {"hash": "n", "title": titel, "description": ""},
                               limit=3)
    assert [b["von"] for b in bsp] == ["claude", "mensch", "mensch"]
    assert bsp[1]["begruendung"] and not bsp[2]["begruendung"]


def test_bekannte_fehler_der_ki_stehen_zuerst(db):
    from bewerbungs_assistent.services import ki_beispiele
    titel = "Konstruktion Projektleiter Hydraulik"
    _mensch_nein(db, "f1", titel, grund="falsche_branche", notiz="Branche passt nicht.")
    b = _mensch_nein(db, "f2", titel)
    conn = db.connect()
    conn.execute("UPDATE jobs SET ollama_urteil='PASST', ollama_lag_richtig=0 "
                 "WHERE hash=?", (b,))
    conn.commit()
    bsp = ki_beispiele.waehlen(_pool(db), {"hash": "n", "title": titel, "description": ""},
                               limit=2)
    assert bsp[0]["gegenbeispiel"] is True
    assert "lag hier früher falsch" in ki_beispiele.als_zeile(bsp[0])


def test_die_stelle_ist_nie_ihr_eigenes_beispiel(db):
    from bewerbungs_assistent.services import ki_beispiele
    v = _mensch_nein(db, "s1", "Leiter Konstruktion Maschinenbau")
    _mensch_nein(db, "s2", "Leiter Konstruktion Anlagenbau")
    job = {"hash": "s1", "title": "Leiter Konstruktion Maschinenbau", "description": ""}
    assert "Leiter Konstruktion Maschinenbau" not in _titel(
        ki_beispiele.waehlen(_pool(db), job))
    job2 = dict(job, hash=v)  # auch mit dem gespeicherten Profil-Praefix
    assert "Leiter Konstruktion Maschinenbau" not in _titel(
        ki_beispiele.waehlen(_pool(db), job2))


def test_abgeschalteter_grund_ist_kein_muster(db):
    _mensch_nein(db, "ab1", "Leiter Konstruktion Maschinenbau", grund="zu_junior")
    conn = db.connect()
    conn.execute("UPDATE dismiss_reasons SET is_active=0 WHERE label='zu_junior'")
    conn.commit()
    assert all(p["grund"] != "zu_junior" for p in _pool(db))


def test_kurzform_mit_kern_grund_und_satz(db):
    from bewerbungs_assistent.services import ki_beispiele
    _mensch_nein(db, "k1", "Konstrukteur Maschinenbau (m/w/d)", grund="zu_junior",
                 notiz="Verantwortung zu klein. Weitere Worte folgen hier.",
                 text=ANFORDERUNGEN + "x" * 100)
    bsp = ki_beispiele.waehlen(
        _pool(db), {"hash": "n", "title": "Konstrukteur Maschinenbau", "description": ""})
    zeile = ki_beispiele.als_zeile(bsp[0])
    assert "PASST_NICHT" in zeile and "zu_junior" in zeile
    assert "Kern: Studium Maschinenbau" in zeile
    assert "Begründung: Verantwortung zu klein." in zeile
    assert len(zeile) <= ki_beispiele.ZEILE_MAX
    assert len(bsp[0]["kern"]) <= 3


def test_prompt_nutzt_die_neuen_beispiele_und_nicht_die_alte_liste():
    from bewerbungs_assistent.services.llm_service import _build_match_job_to_skills_prompt
    alt_liste = [{"title": "ALTE LISTE", "company": "F", "dismiss_reason": "x"}]
    payload = {"job_title": "X", "recent_dismissals": alt_liste, "lern_beispiele": [
        {"titel": "Leiter Konstruktion", "klasse": "passt_nicht", "von": "mensch",
         "grund": "zu_junior", "begruendung": "", "kern": [], "gegenbeispiel": False}]}
    prompt = _build_match_job_to_skills_prompt(payload)
    assert "Leiter Konstruktion" in prompt and "ALTE LISTE" not in prompt
    leer = _build_match_job_to_skills_prompt(dict(payload, lern_beispiele=[]))
    assert "ALTE LISTE" not in leer
    # ohne den neuen Schluessel bleibt das alte Verhalten
    alt = _build_match_job_to_skills_prompt({"job_title": "X", "recent_dismissals": alt_liste})
    assert "ALTE LISTE" in alt


# -- Der Weg der Auto-Aussortierung -----------------------------------------

class _KI:
    def __init__(self, decision="PASST_NICHT", grund="Falsche Branche."):
        self.decision, self.grund, self.payloads = decision, grund, []

    def get_status(self, force_refresh=False):
        return SimpleNamespace(ollama_available=True, available_models=["m"],
                               user_state="active", selected_model="m")

    def warmup(self):
        return {"status": "warm", "duration_sec": 0}

    def run(self, kind, payload):
        self.payloads.append(payload)
        return SimpleNamespace(success=True, fallback_message="",
                               payload={"decision": self.decision, "reason": self.grund,
                                        "sicherheit": "klar"})


def _zeile(db, voll):
    return dict(db.connect().execute("SELECT * FROM jobs WHERE hash=?", (voll,)).fetchone())


def test_auto_aussortierung_zeigt_aehnliche_beispiele_und_vermerkt_das_urteil(db, monkeypatch):
    from bewerbungs_assistent.services import auto_aussortierung as aa, llm_service
    _mensch_nein(db, "e1", "Leiter Konstruktion Maschinenbau")
    voll = _stelle(db, "e2", "Konstruktionsleiter Maschinenbau (m/w/d)",
                   text="Konstruktion von Maschinen und Anlagen im Team. " * 3)
    ki = _KI()
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db=None: ki)
    aa.aussortieren(db, max_stellen=5, dry_run=True)
    assert ki.payloads and "lern_beispiele" in ki.payloads[0]
    assert [b["titel"] for b in ki.payloads[0]["lern_beispiele"]] == [
        "Leiter Konstruktion Maschinenbau"]
    assert _zeile(db, voll)["ollama_urteil"] is None, "Ein Probelauf hinterlaesst keine Marker."
    aa.aussortieren(db, max_stellen=5, dry_run=False)
    z = _zeile(db, voll)
    assert z["ollama_urteil"] == "PASST_NICHT" and z["ollama_gesehen_am"]
    assert z["ollama_grund"] == "Falsche Branche." and z["ollama_sicherheit"] == "klar"
    assert z["entschieden_von"] == "ollama" and not z["is_active"]


def test_dublettenbehauptung_gilt_als_unsicher_im_marker(db, monkeypatch):
    from bewerbungs_assistent.services import auto_aussortierung as aa, llm_service
    voll = _stelle(db, "d1", "Sachbearbeiter Einkauf",
                   text="Pflege der Stammdaten und Abstimmung mit Fachbereichen im Einkauf. " * 2)
    ki = _KI(grund="Dublikat einer anderen Anzeige")
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db=None: ki)
    aa.aussortieren(db, max_stellen=5)
    z = _zeile(db, voll)
    assert z["ollama_urteil"] == "UNSICHER" and z["is_active"]


def test_fehler_der_ki_stehen_auch_dann_zuerst_wenn_sie_weniger_aehnlich_sind(db):
    from bewerbungs_assistent.services import ki_beispiele
    titel = "Konstruktion Projektleiter Hydraulik"
    _mensch_nein(db, "h1", titel, grund="falsche_branche", notiz="Branche passt nicht.")
    b = _mensch_nein(db, "h2", "Projektleiter Vertrieb Hydraulik Service")
    conn = db.connect()
    conn.execute("UPDATE jobs SET ollama_urteil='PASST', ollama_lag_richtig=0 "
                 "WHERE hash=?", (b,))
    conn.commit()
    bsp = ki_beispiele.waehlen(_pool(db), {"hash": "n", "title": titel, "description": ""},
                               limit=2)
    assert [x["gegenbeispiel"] for x in bsp] == [True, False]
