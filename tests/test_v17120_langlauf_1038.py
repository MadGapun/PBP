"""#1038 — LinkedIn liefert, nur langsam, und wurde als Ausfall gefuehrt.

Aus dem Bericht (Log des Melders): LinkedIn ueber JobSpy fand 1.030 bis
1.100 Stellen — sieben Minuten, nachdem PBP die Quelle nach dem
Phasen-Budget (195 s) als `server_weg` verbucht und ihre Ergebnisse
verworfen hatte. Nach fuenf solchen Laeufen war sie pausiert.

Beim Umbau gefunden: jede Fehlerklasse, die NICHT temporaer ist, fuehrt
nach fuenf Laeufen zur HARTEN Deaktivierung. Ein naiver neuer Befund
"zu langsam" als Fehlerklasse haette LinkedIn schlimmer getroffen als
vorher.
"""
import importlib
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def lauf(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17120_1038_")
    monkeypatch.setenv("BA_DATA_DIR", tmpdir)
    monkeypatch.delenv("PBP_FEATURES", raising=False)
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    db.set_search_criteria("keywords_muss", ["Stammdaten"])

    from bewerbungs_assistent.job_scraper import bundesagentur, jobspy_source

    def _stelle(nr, quelle):
        return {"hash": f"{quelle}{nr}", "title": f"Stammdaten Spezialist {nr}",
                "company": f"Musterfirma {quelle} {nr} GmbH", "location": "Musterstadt",
                "url": f"https://example.com/{quelle}/{nr}", "source": quelle,
                "description": "Stammdaten Pflege und Governance. " * 10}

    def starten(linkedin_dauer: float, linkedin_budget: int):
        monkeypatch.setattr(bundesagentur, "search_bundesagentur",
                            lambda p: [_stelle(1, "bundesagentur")])

        def _langsam(p):
            time.sleep(linkedin_dauer)
            return [_stelle(i, "jobspy_linkedin") for i in range(3)]

        monkeypatch.setattr(jobspy_source, "search_jobspy_linkedin", _langsam)
        monkeypatch.setattr(jobspy_source, "linkedin_langlauf_budget",
                            lambda params, mindestens: linkedin_budget)
        from bewerbungs_assistent.job_scraper import run_search
        job_id = db.create_background_job("jobsuche", {})
        t0 = time.time()
        run_search(db, job_id, {"quellen": ["bundesagentur", "jobspy_linkedin"],
                                "keywords": ["Stammdaten"]})
        return db.get_background_job(job_id), time.time() - t0

    yield db, starten
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _status(job):
    ergebnis = job["result"] if isinstance(job["result"], dict) else {}
    return ergebnis.get("quellen_status") or ergebnis.get("source_status") or {}


def _health(db, name):
    return next((h for h in db.get_scraper_health() if h["scraper_name"] == name), None)


def test_ein_spaetes_ergebnis_wird_gespeichert_statt_verworfen(lauf):
    """Der Kern des Berichts: LinkedIn liefert nach dem Budget der
    schnellen Quellen — die Treffer landen trotzdem im Bestand."""
    db, starten = lauf
    job, _ = starten(linkedin_dauer=2.0, linkedin_budget=30)
    quellen = {j.get("source") for j in db.get_active_jobs()}
    assert "jobspy_linkedin" in quellen, quellen
    h = _health(db, "jobspy_linkedin")
    assert h["consecutive_failures"] == 0
    assert "server_weg" not in str(h.get("last_error") or "")


def test_zu_langsam_ist_kein_ausfall_und_pausiert_nicht(lauf):
    """Reisst auch das eigene Budget, heisst der Befund `zu_langsam` —
    ohne Fehlerserie, ohne Pause, ohne harte Abschaltung. Fuenf Laeufe
    hintereinander, genau die Schwelle, an der vorher pausiert wurde."""
    db, starten = lauf
    for _ in range(5):
        job, dauer = starten(linkedin_dauer=6.0, linkedin_budget=1)
        assert dauer < 5.5, f"der Lauf hat auf die langsame Quelle gewartet: {dauer:.1f}s"
    h = _health(db, "jobspy_linkedin")
    assert h["consecutive_failures"] == 0
    assert h["is_active"], "nach fuenf zu langsamen Laeufen darf nichts pausiert sein"
    assert not h.get("error_class")
    assert "zu langsam" in (h.get("last_status_detail") or "")
    # Die schnelle Quelle ist davon unberuehrt und gespeichert.
    assert "bundesagentur" in {j.get("source") for j in db.get_active_jobs()}


def test_die_schnellen_quellen_warten_nicht_auf_das_phasen_budget(lauf):
    """Stufe 1 endet, sobald keine schnelle Quelle mehr aussteht. Vorher
    haette der Lauf bis zum Phasen-Budget (hier 105 s) gewartet."""
    db, starten = lauf
    _, dauer = starten(linkedin_dauer=3.0, linkedin_budget=60)
    assert dauer < 30, f"{dauer:.1f}s — Stufe 1 hat das ganze Phasen-Budget abgewartet"


def test_ein_echter_fehler_bleibt_ein_fehler(db_leer=None):
    """Die Gegenrichtung (#966): `zu_langsam` ist ein eigener Zustand,
    kein Freibrief. Ein Timeout einer SCHNELLEN Quelle zaehlt weiter."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17120_1038_fehler_")
    os.environ["BA_DATA_DIR"] = tmpdir
    try:
        import bewerbungs_assistent.database as _db_mod
        importlib.reload(_db_mod)
        db = _db_mod.Database()
        db.initialize()
        assert str(tmpdir) in str(db.db_path)
        db.update_scraper_health("hays", "timeout", 0, 105, None, error_class="server_weg")
        db.update_scraper_health("hays", "timeout", 0, 105, None, error_class="server_weg")
        assert _health(db, "hays")["consecutive_failures"] == 2
        db.update_scraper_health("hays", "zu_langsam", 0, 600, "zu langsam: 600s")
        h = _health(db, "hays")
        assert h["consecutive_failures"] == 2, "zu_langsam setzt die Serie nicht zurueck"
        assert h["total_successes"] == 0, "zu_langsam ist kein Erfolg"
        db.close()
    finally:
        os.environ.pop("BA_DATA_DIR", None)
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_das_budget_waechst_mit_den_suchbegriffen():
    from bewerbungs_assistent.job_scraper import jobspy_source as js
    wenig = js.linkedin_langlauf_budget({"keywords": ["A", "B"]}, 120)
    viel = js.linkedin_langlauf_budget({"keywords": [f"Begriff{i}" for i in range(44)]}, 120)
    assert wenig == 120, "unter dem Mindestwert gilt der Mindestwert"
    # 44 Begriffe: gemessen rund acht Minuten, das Budget muss darueber liegen.
    assert viel >= 8 * 60, viel
    riesig = js.linkedin_langlauf_budget({"keywords": [f"B{i}" for i in range(500)]}, 120)
    assert riesig == js.LINKEDIN_BUDGET_MAX
    # Gezaehlt wird mit derselben Liste, die die Abfrage schickt (#490).
    assert js.linkedin_abfragen({"keywords": ["A", "B"]}) >= 2


def test_die_werkzeugbeschreibung_behauptet_keinen_ausfall_mehr():
    """Punkt 5 aus #1038."""
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "tools" / "jobs.py").read_text(encoding="utf-8")
    assert "die jobspy-Variante ist deprecated" not in quelle
    assert "#1038" in quelle
