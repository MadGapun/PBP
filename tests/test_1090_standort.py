"""#1090: Der Wohnort aus dem Profil gilt als Standort, ein eigener Ort
gewinnt, und die Entfernungen des Bestands ziehen nach.

Der Geocoder ist ein Testdoppel (kein Netz); gezaehlt wird, wie oft er
gefragt wird — je VERSCHIEDENEM Ort einmal (#1057).
"""
from __future__ import annotations

import ast
import os
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"

ORTE = {
    "20095 Hamburg": (53.55, 10.0),
    "Hamburg": (53.55, 10.0),
    "21073 Hamburg": (53.46, 9.98),
    "Bremen": (53.08, 8.8),
    "Lübeck": (53.87, 10.69),
}


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.services import geocoding_service as gs
    gefragt = []

    def geo(ort):
        gefragt.append(ort)
        return ORTE.get((ort or "").strip())
    monkeypatch.setattr(gs, "geocode_location", geo)
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.gefragt = gefragt
    yield d
    for t in threading.enumerate():
        if t.name.startswith("pbp-"):
            t.join(timeout=10)
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _warten():
    for t in threading.enumerate():
        if t.name.startswith("pbp-entfernungen"):
            t.join(timeout=10)


def _profil(db, daten):
    """Profil speichern und die Neuberechnung abwarten, die ein neuer
    Wohnort im Hintergrund startet — sonst laeuft sie gegen den Test."""
    db.save_profile(daten)
    _warten()


def _stelle(db, kennung, ort, **mehr):
    db.save_jobs([{"hash": kennung, "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                   "url": f"https://example.com/{kennung}", "source": "manuell",
                   "location": ort, "description": "x" * 80, "score": 3, **mehr}])
    return db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE ?",
                                (f"%{kennung}",)).fetchone()[0]


def _zeile(db, voll):
    return dict(db.connect().execute("SELECT * FROM jobs WHERE hash=?", (voll,)).fetchone())


# ── AK 1: der Wohnort zählt ─────────────────────────────────────────

def test_wohnort_aus_dem_profil_wird_standort(db):
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test", "plz": "20095", "city": "Hamburg"})
    b = es.befund(db)
    assert b["quelle"] == es.PROFIL and b["aufgeloest"] and b["ort"] == "20095 Hamburg"
    k = db.get_search_criteria()
    assert (k["standort_lat"], k["standort_lon"]) == ORTE["20095 Hamburg"]


def test_nicht_aufgeloester_wohnort_schreibt_nichts_und_wird_benannt(db):
    from bewerbungs_assistent.services import eigener_standort as es
    from bewerbungs_assistent.services.onboarding_hints import _condition_standort_fehlt
    _profil(db, {"name": "Test", "city": "Nirgendwo"})
    b = es.befund(db)
    assert b["quelle"] == es.PROFIL and not b["aufgeloest"]
    assert "standort_ort" not in (db.get_search_criteria() or {}), "leere Kriterien blieben nicht leer"
    assert _condition_standort_fehlt(db) is False, "ohne Stellen noch kein Hinweis"
    _stelle(db, "hinweis1090", "Bremen")
    assert _condition_standort_fehlt(db) is True


def test_ohne_profil_kein_hinweis(db):
    from bewerbungs_assistent.services.onboarding_hints import _condition_standort_fehlt
    assert _condition_standort_fehlt(db) is False


# ── AK 2: ein eigener Ort gewinnt ───────────────────────────────────

def test_eigener_ort_gewinnt_gegen_spaeteres_profil_speichern(db):
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test", "city": "Hamburg"})
    assert es.eigenen_setzen(db, "Bremen", neu_rechnen=False)["status"] == "gesetzt"
    _profil(db, {"name": "Test", "city": "Lübeck"})
    b = es.befund(db)
    assert b["quelle"] == es.EIGENE and b["ort"] == "Bremen"


def test_suchlauf_ueberschreibt_eigenen_ort_nicht(db):
    """Der Suchlauf ruft `aus_profil_uebernehmen` direkt, ohne die
    Vorpruefung aus `save_profile`."""
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test", "city": "Hamburg"})
    es.eigenen_setzen(db, "Bremen", neu_rechnen=False)
    assert es.aus_profil_uebernehmen(db, neu_rechnen=False)["geaendert"] is False
    assert es.befund(db)["ort"] == "Bremen"


def test_nicht_aufloesbarer_eigener_ort_wird_nicht_gespeichert(db):
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test", "city": "Hamburg"})
    erg = es.eigenen_setzen(db, "Atlantis", neu_rechnen=False)
    assert erg["status"] == "nicht_aufgeloest"
    assert es.befund(db)["quelle"] == es.PROFIL


def test_leer_heisst_zurueck_zum_wohnort(db):
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test", "city": "Hamburg"})
    es.eigenen_setzen(db, "Bremen", neu_rechnen=False)
    es.eigenen_setzen(db, "", neu_rechnen=False)
    b = es.befund(db)
    assert b["quelle"] == es.PROFIL and b["ort"] == "Hamburg" and b["aufgeloest"]


# ── AK 3/4: Bestand zieht nach, je Ort eine Anfrage ─────────────────

def test_neuer_standort_rechnet_bestand_neu(db):
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test", "city": "Hamburg"})
    a = _stelle(db, "a1090", "Bremen")
    b = _stelle(db, "b1090", "Bremen")
    c = _stelle(db, "c1090", "Lübeck")
    db.connect().execute("UPDATE jobs SET fahrstrecke_km=99, route_quelle='ors' WHERE hash=?", (a,))
    db.connect().commit()
    db.gefragt.clear()
    erg = es.entfernungen_nachziehen(db, alle=True, max_orte=None)
    assert erg["stellen"] == 3 and erg["orte"] == 2
    assert sorted(db.gefragt) == ["Bremen", "Lübeck"], "je Ort genau eine Anfrage"
    assert 80 < _zeile(db, a)["distance_km"] < 110
    assert _zeile(db, a)["fahrstrecke_km"] is None, "Fahrstrecke zum alten Ort blieb stehen"
    assert _zeile(db, b)["distance_km"] == _zeile(db, a)["distance_km"]
    assert _zeile(db, c)["distance_km"] is not None


def test_von_hand_gesetzte_entfernung_bleibt(db):
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test", "city": "Hamburg"})
    a = _stelle(db, "d1090", "Bremen")
    db.connect().execute("UPDATE jobs SET distance_km=7, entfernung_quelle='mensch' WHERE hash=?", (a,))
    db.connect().commit()
    es.entfernungen_nachziehen(db, alle=True, max_orte=None)
    assert _zeile(db, a)["distance_km"] == 7


def test_nachholen_nur_fehlende_und_begrenzt(db):
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test", "city": "Hamburg"})
    fertig = _stelle(db, "e1090", "Bremen")
    db.connect().execute("UPDATE jobs SET distance_km=1 WHERE hash=?", (fertig,))
    offen = _stelle(db, "f1090", "Lübeck")
    db.connect().commit()
    erg = es.entfernungen_nachziehen(db, alle=False, max_orte=1)
    assert _zeile(db, fertig)["distance_km"] == 1
    assert _zeile(db, offen)["distance_km"] is not None
    assert erg["orte"] == 1


def test_standortwechsel_startet_neuberechnung_im_hintergrund(db):
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test", "city": "Hamburg"})
    a = _stelle(db, "g1090", "Lübeck")
    es.eigenen_setzen(db, "Bremen")
    _warten()
    jobs = db.connect().execute(
        "SELECT id FROM background_jobs WHERE job_type='entfernungen' ORDER BY rowid DESC").fetchall()
    assert jobs, "kein Hintergrund-Eintrag"
    job = db.get_background_job(jobs[0][0])
    assert job["status"] == "fertig", job
    assert "Nähe-Punkte" in job["message"]
    assert _zeile(db, a)["distance_km"] > 150


def test_ohne_standort_nichts_zu_rechnen(db):
    from bewerbungs_assistent.services import eigener_standort as es
    _profil(db, {"name": "Test"})
    _stelle(db, "h1090", "Bremen")
    assert es.entfernungen_nachziehen(db)["status"] == "kein_standort"


# ── AK 5: dauerhafter Speicher ──────────────────────────────────────

def test_geocoding_ergebnis_ueberlebt_den_speicher_im_prozess(db, monkeypatch):
    from bewerbungs_assistent.services import geocoding_service as gs
    monkeypatch.undo()  # echter geocode_location, aber ohne Netz (PBP_GEOCODING=0)
    gs.speicher_setzen(db)
    gs._in_speicher("musterstadt", (50.0, 9.0))
    gs._in_speicher("unbekanntdorf", None)
    with gs._cache_lock:
        gs._geo_cache.pop("musterstadt", None)
        gs._geo_cache.pop("unbekanntdorf", None)
    assert gs.geocode_location("Musterstadt") == (50.0, 9.0)
    assert gs._aus_speicher("unbekanntdorf") == (True, None), "Nicht-Befund nicht gemerkt"


def test_ohne_netz_wird_nichts_gemerkt(db, monkeypatch):
    from bewerbungs_assistent.services import geocoding_service as gs
    monkeypatch.undo()
    gs.speicher_setzen(db)
    assert gs.geocode_location("Nie-Gefragt-Stadt") is None
    assert gs._aus_speicher("nie-gefragt-stadt")[0] is False, "Ausfall als Befund gespeichert"


# ── Oberflaeche und Claude ──────────────────────────────────────────

def test_dashboard_standort(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    tc = TestClient(dash.app)
    assert tc.get("/api/standort").json()["quelle"] is None
    _profil(db, {"name": "Test", "city": "Hamburg"})
    assert tc.get("/api/standort").json()["aufgeloest"] is True
    r = tc.put("/api/standort", json={"ort": "Atlantis"})
    assert r.status_code == 422
    r = tc.put("/api/standort", json={"ort": "Bremen"})
    assert r.status_code == 200 and r.json()["befund"]["quelle"] == "eigene"
    _warten()
    assert tc.put("/api/standort", json={"ort": 5}).status_code == 400


def test_ersterfassung_fragt_nach_dem_wohnort():
    from bewerbungs_assistent.services import ersterfassung_phasen as ep
    text = " ".join(v for v in vars(ep).values() if isinstance(v, str))
    assert "profil_erstellen(plz=" in text and "standort=" in text


def _ruft(datei: Path, funktion: str, ziel: str) -> bool:
    baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
    for f in ast.walk(baum):
        if isinstance(f, ast.FunctionDef) and f.name == funktion:
            return any(isinstance(c, ast.Call) and getattr(c.func, "attr",
                       getattr(c.func, "id", "")) == ziel for c in ast.walk(f))
    return False


def test_suchlauf_uebernimmt_wohnort_und_holt_nach():
    datei = SRC / "job_scraper" / "__init__.py"
    assert _ruft(datei, "run_search", "aus_profil_uebernehmen")
    assert _ruft(datei, "run_search", "nachholen")


def test_profil_speichern_ist_das_nadeloehr():
    assert _ruft(SRC / "database.py", "save_profile", "nach_profil_speichern")
