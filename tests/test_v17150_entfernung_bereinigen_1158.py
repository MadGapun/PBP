"""#1158 Punkt 8: gespeicherte Entfernungen, die mit einem Zusatz im Ortstext gerechnet wurden, werden geheilt.

Bis v1.7.149 ging der Rohtext an den Ortsdienst: "Hamburg (hybrid), remote möglich" lag bei Mainz (410 statt 20 km)
und blieb so gespeichert. Die Korrektur des Dienstes heilt nur NEUE Rechnungen; die Stellen im Bestand behielten die
falsche Zahl. `eigener_standort.entfernungen_bereinigen` läuft nach jedem Suchlauf (`nachholen`), begrenzt und ohne
von Hand gesetzte Werte anzufassen.

Der Ortsdienst ist ein Testdouble (kein Netz). Alle Orte, Firmen und Texte sind Platzhalter.
"""
from __future__ import annotations

import importlib
import os
import threading

import pytest

HEIM = (53.08, 8.8)          # "Bremen"
KOORD = {
    "Hamburg": (53.55, 10.0),
    "Hamburg, Hamburg": (53.55, 10.0),
    "Lübeck": (53.87, 10.69),
    "Bremen": HEIM,
}


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.services import eigener_standort as es
    from bewerbungs_assistent.services import geocoding_service as gs
    gefragt: list = []

    def geo(ort):
        gefragt.append(ort)
        return KOORD.get(gs.ort_fuer_abfrage(ort))

    monkeypatch.setattr(gs, "geocode_location", geo)
    es._BEREINIGT_VERSUCHT.clear()
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.set_search_criteria("standort_lat", HEIM[0])
    d.set_search_criteria("standort_lon", HEIM[1])
    d.gefragt = gefragt
    yield d
    for t in threading.enumerate():
        if t.name.startswith("pbp-"):
            t.join(timeout=10)
    d.close()
    es._BEREINIGT_VERSUCHT.clear()
    os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung, ort, km, quelle=None, route=False):
    db.save_jobs([{"hash": kennung, "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                   "url": f"https://example.com/{kennung}", "source": "manuell",
                   "location": ort, "description": "x" * 80, "score": 3}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE ?", (f"%{kennung}",)).fetchone()[0]
    db.connect().execute(
        "UPDATE jobs SET distance_km=?, entfernung_quelle=?, fahrstrecke_km=?, fahrzeit_min=?, route_quelle=? "
        "WHERE hash=?",
        (km, quelle, 450.0 if route else None, 300 if route else None, "test" if route else None, voll))
    db.connect().commit()
    return voll


def _zeile(db, voll):
    return dict(db.connect().execute("SELECT * FROM jobs WHERE hash=?", (voll,)).fetchone())


def _km(ziel):
    from bewerbungs_assistent.services.geocoding_service import calculate_distance_km
    return calculate_distance_km(HEIM, ziel)


def _bereinigen(db, **kw):
    from bewerbungs_assistent.services import eigener_standort as es
    return es.entfernungen_bereinigen(db, **kw)


# ── die Heilung ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_eine_entfernung_mit_ortszusatz_wird_neu_gerechnet(db):
    voll = _stelle(db, "a1", "Hamburg (hybrid), remote möglich", 410.0, route=True)
    erg = _bereinigen(db)
    assert erg["stellen"] == 1 and erg["geleert"] == 0
    z = _zeile(db, voll)
    assert z["distance_km"] == _km(KOORD["Hamburg"]) and z["distance_km"] < 150
    assert (z["lat"], z["lon"]) == KOORD["Hamburg"]
    assert z["entfernung_am"]
    assert z["fahrstrecke_km"] is None and z["fahrzeit_min"] is None and z["route_quelle"] is None, \
        "eine Fahrstrecke zum falschen Ort ist danach falsch"


def test_saubere_orte_bleiben_unberuehrt_und_werden_nicht_gefragt(db):
    voll = _stelle(db, "a2", "Lübeck", 999.0)
    assert _bereinigen(db)["stellen"] == 0
    assert _zeile(db, voll)["distance_km"] == 999.0
    assert db.gefragt == []


def test_ein_angehaengtes_land_ist_kein_anlass(db):
    """'Hamburg, Hamburg, Germany' (die übliche Form aus JobSpy) fragt nach #1158 dasselbe wie vorher."""
    voll = _stelle(db, "a3", "Hamburg, Hamburg, Germany", 77.0, route=True)
    assert _bereinigen(db)["stellen"] == 0
    z = _zeile(db, voll)
    assert z["distance_km"] == 77.0 and z["fahrstrecke_km"] == 450.0
    assert db.gefragt == []


def test_von_hand_gesetzte_entfernungen_bleiben(db):
    voll = _stelle(db, "a4", "Hamburg (hybrid), remote möglich", 410.0, quelle="mensch")
    assert _bereinigen(db)["stellen"] == 0
    assert _zeile(db, voll)["distance_km"] == 410.0
    assert db.gefragt == []


@pytest.mark.parametrize("text", ["Remote möglich", "Homeoffice möglich", "Bundesweit (Homeoffice)", "Germany",
                                  "Deutschland", "hybrid"])
def test_ein_text_ohne_ort_hat_keine_entfernung(db, text):
    voll = _stelle(db, "a5", text, 300.0, route=True)
    erg = _bereinigen(db)
    assert erg["geleert"] == 1 and erg["stellen"] == 0
    z = _zeile(db, voll)
    assert z["distance_km"] is None and z["lat"] is None and z["lon"] is None
    assert z["fahrstrecke_km"] is None and z["route_quelle"] is None
    assert db.gefragt == [], "dafür braucht es kein Netz"


def test_findet_der_dienst_den_ort_nicht_bleibt_die_gespeicherte_zahl(db):
    """Ein Ausfall oder ein unbekannter Ort ist kein Befund über die Stelle - nichts wird gelöscht."""
    voll = _stelle(db, "a6", "Nirgendwo (hybrid)", 123.0, route=True)
    erg = _bereinigen(db)
    assert erg["stellen"] == 0 and erg["geleert"] == 0
    z = _zeile(db, voll)
    assert z["distance_km"] == 123.0 and z["fahrstrecke_km"] == 450.0
    assert db.gefragt == ["Nirgendwo (hybrid)"]


def test_eine_abweichung_unter_einem_kilometer_ersetzt_nichts(db):
    soll = _km(KOORD["Hamburg"])
    voll = _stelle(db, "a7", "Hamburg (hybrid)", soll + 0.5, route=True)
    assert _bereinigen(db)["stellen"] == 0
    z = _zeile(db, voll)
    assert z["distance_km"] == soll + 0.5 and z["fahrstrecke_km"] == 450.0


def test_die_heilung_laeuft_nur_einmal_ueber_dieselbe_stelle(db):
    voll = _stelle(db, "a8", "Hamburg (hybrid), remote möglich", 410.0)
    assert _bereinigen(db)["stellen"] == 1
    gerechnet = _zeile(db, voll)["distance_km"]
    from bewerbungs_assistent.services import eigener_standort as es
    es._BEREINIGT_VERSUCHT.clear()           # sogar mit neuem Prozess: die Zahl stimmt jetzt, nichts ändert sich
    assert _bereinigen(db)["stellen"] == 0
    assert _zeile(db, voll)["distance_km"] == gerechnet


def test_ein_ort_wird_je_prozess_nur_einmal_gefragt(db):
    """Sonst fragte jeder Suchlauf dieselben unauflösbaren Orte neu - mit Zeitgrenze je Anfrage, solange das Netz fehlt."""
    _stelle(db, "a9", "Nirgendwo (hybrid)", 123.0)
    _bereinigen(db)
    _bereinigen(db)
    assert db.gefragt == ["Nirgendwo (hybrid)"]


def test_je_lauf_werden_hoechstens_max_orte_gefragt_der_rest_folgt(db):
    for i in range(5):
        _stelle(db, f"b{i}", f"Ort{i} (hybrid)", 123.0)
    _bereinigen(db, max_orte=2)
    assert len(db.gefragt) == 2
    _bereinigen(db, max_orte=2)
    assert len(db.gefragt) == 4 and len(set(db.gefragt)) == 4, "der zweite Lauf nimmt die nächsten, nicht dieselben"
    _bereinigen(db, max_orte=2)
    assert len(set(db.gefragt)) == 5


def test_ohne_standort_wird_nichts_gerechnet(db):
    _stelle(db, "c1", "Hamburg (hybrid)", 410.0)
    db.set_search_criteria("standort_lat", None)
    db.set_search_criteria("standort_lon", None)
    assert _bereinigen(db)["status"] == "kein_standort"
    assert db.gefragt == []


# ── im Ablauf nach einem Suchlauf ─────────────────────────────────────────────────────────────────────────────────

def test_nachholen_heilt_und_rechnet_die_punkte_neu(db, monkeypatch):
    from bewerbungs_assistent.services import eigener_standort as es
    voll = _stelle(db, "d1", "Hamburg (hybrid), remote möglich", 410.0)
    aufrufe: list = []
    monkeypatch.setattr(es, "_punkte_neu", lambda d: aufrufe.append(1) or {"geaendert": 1})
    erg = es.nachholen(db)
    assert erg["bereinigt"] == 1
    assert len(aufrufe) == 1, "die Nähe-Punkte der geheilten Stelle müssen neu gerechnet werden"
    assert _zeile(db, voll)["distance_km"] < 150


def test_nachholen_ohne_etwas_zu_heilen_laesst_die_punkte_in_ruhe(db, monkeypatch):
    from bewerbungs_assistent.services import eigener_standort as es
    _stelle(db, "d2", "Lübeck", 80.0)
    aufrufe: list = []
    monkeypatch.setattr(es, "_punkte_neu", lambda d: aufrufe.append(1) or {})
    erg = es.nachholen(db)
    assert erg["bereinigt"] == 0 and aufrufe == []


def test_eine_fehlgeschlagene_heilung_stoppt_das_nachholen_nicht(db, monkeypatch):
    from bewerbungs_assistent.services import eigener_standort as es

    def kaputt(*a, **k):
        raise RuntimeError("Netz weg")

    monkeypatch.setattr(es, "entfernungen_bereinigen", kaputt)
    erg = es.nachholen(db)
    assert erg["bereinigt"] == 0 and erg["status"] == "fertig"
