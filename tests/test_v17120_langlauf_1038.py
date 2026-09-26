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
            # Wie der echte Adapter (#1061): Begriff fuer Begriff, das
            # Gefundene liegt sofort im Zwischenstand, und nach einem
            # Anhalte-Signal endet der Lauf nach dem aktuellen Begriff.
            zw = p.get("_zwischenstand") or {"jobs": [], "fertig": 0,
                                               "stopp": __import__("threading").Event()}
            begriffe = 3
            zw["abfragen"] = begriffe
            for i in range(begriffe):
                if zw["stopp"].is_set():
                    break
                time.sleep(linkedin_dauer / begriffe)
                zw["jobs"].append(_stelle(i, "jobspy_linkedin"))
                zw["fertig"] += 1
            return zw["jobs"]

        monkeypatch.setattr(jobspy_source, "search_jobspy_linkedin", _langsam)
        monkeypatch.setattr(jobspy_source, "linkedin_langlauf_budget",
                            lambda params, mindestens, gemessen=None: linkedin_budget)
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
    # #1061: was bis zum Abbruch gefunden war, ist uebernommen.
    assert "teilweise" in (h.get("last_status_detail") or "")
    assert "jobspy_linkedin" in {j.get("source") for j in db.get_active_jobs()}
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


# ══ #1061: die Ernte wird angenommen, nicht verworfen ═══════════════
#
# Folgebefund zu #1038 (Nachmessung des Melders, 18.09.2026): das eigene
# Budget (576 s) reichte um 39 s nicht, und die 1.075 Stellen, die danach
# vorlagen, sammelte niemand mehr ein. Neun Laeufe seit dem 09.09., rund
# 9.600 gefundene Stellen, null gespeicherte.

def test_1061_teilergebnis_wird_uebernommen(lauf):
    db, starten = lauf
    job, _ = starten(linkedin_dauer=6.0, linkedin_budget=1)
    h = _health(db, "jobspy_linkedin")
    assert h["last_count"] >= 1, "was bis zum Abbruch gefunden war, ging verloren"
    assert "von 3 Suchbegriffen" in h["last_status_detail"]
    assert "ins Höchstbudget passen etwa" in h["last_status_detail"]
    assert "jobspy_linkedin" in {j.get("source") for j in db.get_active_jobs()}


def test_1061_im_nachlauf_vollstaendig_heisst_ok(lauf):
    """Wird der Lauf nach dem Anhalte-Signal doch noch fertig, ist er ein
    Erfolg und kein Teilergebnis."""
    db, starten = lauf
    # Ein Begriff dauert 1,5 s, das Budget 4 s: das Signal kommt waehrend
    # des dritten und letzten Begriffs.
    starten(linkedin_dauer=4.5, linkedin_budget=4)
    h = _health(db, "jobspy_linkedin")
    assert h["last_count"] == 3
    assert h["consecutive_failures"] == 0
    assert "teilweise" not in (h.get("last_status_detail") or "")


def test_1061_dauer_je_begriff_wird_gemessen_und_abgelegt(lauf):
    from bewerbungs_assistent.job_scraper.jobspy_source import LINKEDIN_MESSWERT_SCHLUESSEL
    db, starten = lauf
    starten(linkedin_dauer=1.5, linkedin_budget=30)
    wert = db.get_setting(LINKEDIN_MESSWERT_SCHLUESSEL)
    assert wert is not None and 0.3 <= wert <= 1.5, wert


def test_1061_budget_rechnet_mit_dem_messwert():
    from bewerbungs_assistent.job_scraper import jobspy_source as js
    params = {"keywords": [f"Begriff {i}" for i in range(44)]}
    n = js.linkedin_abfragen(params)
    ohne = js.linkedin_langlauf_budget(params, 60)
    mit = js.linkedin_langlauf_budget(params, 60, gemessen=14)
    assert ohne == int(n * 12 * js.LINKEDIN_ZUSCHLAG) + 60
    assert mit == int(n * 14 * js.LINKEDIN_ZUSCHLAG) + 60
    # Der gemeldete Fall: 44 Begriffe brauchten rund 615 s.
    if n == 44:
        assert mit > 615
    # Ein Messwert unter der Untergrenze senkt das Budget nicht.
    assert js.linkedin_langlauf_budget(params, 60, gemessen=3) == ohne
    # Die Obergrenze gilt weiter.
    assert js.linkedin_langlauf_budget({"keywords": ["x"] * 500}, 60, gemessen=30) \
        == js.LINKEDIN_BUDGET_MAX
    # Wunsch 4: wie viele Begriffe passen hinein.
    assert js.begriffe_im_budget(14) == int((js.LINKEDIN_BUDGET_MAX - 60) / (14 * js.LINKEDIN_ZUSCHLAG))


def test_1061_der_adapter_haelt_nach_dem_signal_an(monkeypatch):
    """Der echte Adapter, nicht die Attrappe: das Gefundene liegt schon
    waehrend des Laufs im Zwischenstand, und nach dem Signal kommt kein
    weiterer Begriff dazu."""
    import threading
    from bewerbungs_assistent.job_scraper import jobspy_source as js

    class _Df:
        empty = False

        def __init__(self, kw):
            self.kw = kw

        def iterrows(self):
            yield 0, {"kw": self.kw}

    zw = {"jobs": [], "fertig": 0, "abfragen": 0, "stopp": threading.Event()}
    gefragt = []

    def _scrape(**kw):
        gefragt.append(kw["search_term"])
        if len(gefragt) == 2:
            zw["stopp"].set()
        return _Df(kw["search_term"])

    monkeypatch.setattr(js, "_ensure_jobspy", lambda: _scrape)
    monkeypatch.setattr(js, "_map_row", lambda row, site: {"title": row["kw"]})
    monkeypatch.setattr(js, "_expand_keywords_for_linkedin", lambda k: list(k))
    ergebnis = js.search_jobspy_linkedin(
        {"keywords": ["a", "b", "c", "d"], "_zwischenstand": zw})
    assert gefragt == ["a", "b"]
    assert zw["fertig"] == 2 and zw["abfragen"] == 4
    assert ergebnis is zw["jobs"] and len(ergebnis) == 2
