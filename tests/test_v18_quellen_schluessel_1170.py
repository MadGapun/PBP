"""#1170 U3 — eine Quelle, die einen Zugangsschlüssel braucht, sagt es.

Befund (04.10.2026, Rundgang durch eine leere Installation): Wer Adzuna anhakt, sieht die Quelle auf „Aktiv“, ohne eine
Meldung und ohne einen Hinweis, wo der kostenlose Zugangsschlüssel einzutragen ist. Sie liefert dann nichts und sieht
trotzdem aus wie ein Erfolg (das Muster aus #989).

`/api/sources` meldet jetzt je Quelle `schluessel_noetig` und `schluessel_fehlt`; die Oberfläche macht daraus ein Etikett
und eine Meldung (Node-Test `quellenBadges.test.mjs`).
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def client(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database, get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash

    db = Database()
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    monkeypatch.setattr(dash, "_db", db)
    yield TestClient(dash.app), db
    os.environ.pop("BA_DATA_DIR", None)


def _zeilen(tc):
    antwort = tc.get("/api/sources")
    assert antwort.status_code == 200
    return {z["key"]: z for z in antwort.json()}


def test_1170_adzuna_ohne_schluessel_meldet_dass_er_fehlt(client):
    tc, _ = client
    adzuna = _zeilen(tc)["adzuna"]
    assert adzuna["schluessel_noetig"] is True
    assert adzuna["schluessel_fehlt"] is True


def test_1170_mit_beiden_feldern_fehlt_nichts_mehr(client):
    tc, db = client
    db.set_setting("adzuna_app_id", "abc")
    db.set_setting("adzuna_app_key", "def")
    adzuna = _zeilen(tc)["adzuna"]
    assert adzuna["schluessel_noetig"] is True
    assert adzuna["schluessel_fehlt"] is False


@pytest.mark.parametrize("gesetzt", [("abc", ""), ("", "def")])
def test_1170_ein_halber_schluessel_zaehlt_als_fehlend(client, gesetzt):
    """Adzuna braucht beide Felder; mit nur einem liefert die Quelle nichts."""
    tc, db = client
    db.set_setting("adzuna_app_id", gesetzt[0])
    db.set_setting("adzuna_app_key", gesetzt[1])
    assert _zeilen(tc)["adzuna"]["schluessel_fehlt"] is True


def test_1170_quellen_ohne_schluessel_pflicht_bleiben_unberuehrt(client):
    tc, _ = client
    zeilen = _zeilen(tc)
    ohne = [z for k, z in zeilen.items() if k != "adzuna"]
    assert ohne, "es gibt weitere Quellen"
    assert all(z["schluessel_noetig"] is False and z["schluessel_fehlt"] is False for z in ohne)


def test_1170_die_angabe_gilt_auch_fuer_aktive_quellen(client):
    """Anhaken ändert die Schlüssel-Auskunft nicht: aktiv UND ohne Schlüssel ist genau der gemeldete Zustand."""
    tc, _ = client
    tc.post("/api/sources", json={"active_sources": ["adzuna"]})
    adzuna = _zeilen(tc)["adzuna"]
    assert adzuna["active"] is True and adzuna["schluessel_fehlt"] is True


def test_1170_die_oberflaeche_benutzt_die_auskunft_an_beiden_stellen():
    """Der Schutz zählt erst, wenn er aufgerufen wird (DoD 8c): Einstellungen und Einstieg zeigen die Meldung."""
    einstellungen = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    einstieg = (ROOT / "frontend" / "src" / "components" / "ProfileOnboarding.jsx").read_text(encoding="utf-8-sig")
    assert "schluesselHinweis(source)" in einstellungen and 'setSettingsTab("erweiterungen")' in einstellungen
    assert "schluesselHinweis(source)" in einstieg
