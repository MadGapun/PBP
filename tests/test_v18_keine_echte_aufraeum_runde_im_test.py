"""Ein gewöhnlicher Test, der den Planer-Takt ruft, startet keine echte Aufräum-Runde (#1139; CI am 16.10.2026).

Die Runde ist täglich und ohne letzten Lauf sofort fällig. Sie lief als echter Thread mit `run_auto_actions` (Netz, lokale KI, Schreiben)
gegen die Datenbank des Tests und überlebte den Abbau: db.close() unter einem laufenden Thread stürzt auf C-Ebene ab (Exit 139). Die
autouse-Fixture in `conftest.py` ersetzt das Starten; dieser Test hält fest, dass sie wirkt (Gegenprobe `ar72`).
"""
from __future__ import annotations

import threading

import pytest

from bewerbungs_assistent.services import automatik_scheduler


@pytest.fixture
def db(tmp_path):
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "takt.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    yield d
    d.close()


def test_der_takt_startet_in_einem_gewoehnlichen_test_keine_echte_runde(db, monkeypatch):
    from bewerbungs_assistent.services import sicherung
    monkeypatch.setattr(sicherung, "taeglich", lambda *a, **k: None)   # die Sicherung ist hier nicht der Gegenstand
    assert db.get_automatik_settings()["aufraeumen_last_at"] == "", "Voraussetzung: die Runde ist sofort fällig"
    automatik_scheduler._tick(db)
    assert db.get_automatik_settings()["aufraeumen_last_at"], "der Takt hat die Runde gar nicht angestoßen: der Test prüft nichts"
    assert not [t.name for t in threading.enumerate() if "aufraeum" in t.name], "ein Thread der Runde läuft"
    angelegt = db.connect().execute("SELECT COUNT(*) FROM background_jobs WHERE job_type='aufraeumen'").fetchone()[0]
    assert angelegt == 0, "die echte Runde hat einen Job angelegt"
