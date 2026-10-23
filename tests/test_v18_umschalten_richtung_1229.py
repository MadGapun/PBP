"""#1229 (dritter Lauf, Block E5): „Beim nächsten Start nutzen“ kennt zwei Richtungen.

Die Oberflaeche bietet fuer JEDE installierte, nicht vorgemerkte Fassung „Beim naechsten Start nutzen“ an. Nach dem Rueckweg von
1.9.0-rc.2 auf rc.1 und dem Wunsch „wieder rc.2“ stand im Verlauf „Zurueckgeschaltet · Auf Wunsch zurueck von 1.9.0-rc.1 auf
1.9.0-rc.2.“ -- ein Schritt nach vorn. Hier: der Verlauf nennt die Richtung, die ausdrueckliche Wahl hebt die Zuruecknahme des Ziels
auf, der Rueckweg bleibt, wie er war.
"""
from __future__ import annotations

from _au_hilfen import FakeDb, programmordner

from bewerbungs_assistent.services.auto_update import lauf, zustand


def _letzter(db):
    return zustand.verlauf(db)[-1]


def test_ein_schritt_nach_vorn_heisst_umgeschaltet(tmp_path):
    app = programmordner(tmp_path / "pc", fassungen=("1.9.0-rc.1", "1.9.0-rc.2"), aktuell="1.9.0-rc.1")
    db = FakeDb()
    erg = lauf.zurueckschalten(db, "1.9.0-rc.2", app=app)
    assert erg["status"] == "ok" and erg["nach"] == "1.9.0-rc.2"
    assert (app / "aktuell.txt").read_text(encoding="utf-8").strip() == "1.9.0-rc.2"
    e = _letzter(db)
    assert e["ergebnis"] == "umgeschaltet" and e["version"] == "1.9.0-rc.2"
    assert "umgeschaltet" in e["grund"] and "zurück" not in e["grund"], e["grund"]
    assert "1.9.0-rc.1" in e["grund"] and "1.9.0-rc.2" in e["grund"]


def test_der_rueckweg_bleibt_ein_rueckweg(tmp_path):
    app = programmordner(tmp_path / "pc", fassungen=("1.9.0-rc.1", "1.9.0-rc.2"), aktuell="1.9.0-rc.2")
    db = FakeDb()
    erg = lauf.zurueckschalten(db, "1.9.0-rc.1", app=app)
    assert erg["status"] == "ok"
    e = _letzter(db)
    assert e["ergebnis"] == "zurueckgeschaltet"
    assert e["grund"] == "Auf Wunsch zurück von 1.9.0-rc.2 auf 1.9.0-rc.1."
    assert lauf.abgelehnt(db) == ["1.9.0-rc.2"], "die neuere Fassung gilt als zurueckgenommen"


def test_die_ausdrueckliche_wahl_hebt_die_zuruecknahme_des_ziels_auf(tmp_path):
    """Rueckweg von rc.2 auf rc.1 nimmt rc.2 zurueck; wer danach rc.2 ausdruecklich waehlt, will sie wieder."""
    app = programmordner(tmp_path / "pc", fassungen=("1.9.0-rc.1", "1.9.0-rc.2"), aktuell="1.9.0-rc.2")
    db = FakeDb()
    lauf.zurueckschalten(db, "1.9.0-rc.1", app=app)
    assert lauf.abgelehnt(db) == ["1.9.0-rc.2"]
    lauf.zurueckschalten(db, "1.9.0-rc.2", app=app)
    assert lauf.abgelehnt(db) == [], "rc.2 ist nicht mehr zurueckgenommen"
    assert _letzter(db)["ergebnis"] == "umgeschaltet"


def test_eine_noch_neuere_fassung_bleibt_zurueckgenommen(tmp_path):
    app = programmordner(tmp_path / "pc", fassungen=("1.9.0-rc.1", "1.9.0-rc.2", "1.9.0-rc.3"), aktuell="1.9.0-rc.1")
    db = FakeDb()
    lauf.zurueckschalten(db, "1.9.0-rc.2", app=app)
    assert lauf.abgelehnt(db) == ["1.9.0-rc.3"], "wer rc.2 will, hat rc.3 nicht gewollt"
    assert _letzter(db)["ergebnis"] == "umgeschaltet"


def test_ohne_zeiger_gilt_der_rueckweg_text(tmp_path):
    """Ohne `aktuell.txt` gibt es kein Vorher: der bisherige Wortlaut bleibt (kein Absturz, keine erfundene Richtung)."""
    app = programmordner(tmp_path / "pc", fassungen=("1.9.0-rc.1", "1.9.0-rc.2"), aktuell=None)
    (app / "aktuell.txt").unlink(missing_ok=True)
    db = FakeDb()
    erg = lauf.zurueckschalten(db, "1.9.0-rc.1", app=app)
    assert erg["status"] == "ok"
    assert _letzter(db)["ergebnis"] == "zurueckgeschaltet"
