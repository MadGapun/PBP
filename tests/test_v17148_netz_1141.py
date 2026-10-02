"""v1.7.148 — Ohne Netz meldet die Jobsuche nicht mehr „alle Quellen ok“ (#1141).

Befund (01.10.2026): Bei Verbindungsfehlern gaben alle 24 getesteten Quellen
eine leere Liste zurück. Die Suche meldete „8 von 8 Quellen ok“ und „Fertig —
keine neuen Stellen“; fünf solche Läufe in Folge pausierten alle Quellen für
mindestens einen Tag. Wer kurz offline war, bekam den Rat, die Suchbegriffe zu
lockern.

Hier: eine Netzprüfung vor dem Start und nach einem Lauf ohne einen einzigen
Rohtreffer; offline heißt „Keine Verbindung“, ohne dass an den Quellen etwas
gezählt oder verändert wird. Außerdem: eine übersprungene Quelle bekommt
keinen Fehler mehr gebucht und heißt nicht mehr pauschal „deprecated“.

Jeder Test hat eine Gegenprobe (scratchpad/n144/gegenprobe_1141.py).
"""
import asyncio
import logging
import os
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Suche"})
    d.set_search_criteria("keywords_muss", ["einkauf"])
    d.set_profile_setting("active_sources", ["bundesagentur", "arbeitnow"])
    import bewerbungs_assistent.dashboard as dash
    vorher = dash._db
    dash._db = d
    from bewerbungs_assistent.services import auto_aussortierung, text_nachzug
    monkeypatch.setattr(auto_aussortierung, "nach_suche", lambda _db, job_id: None)
    monkeypatch.setattr(text_nachzug, "nach_suche", lambda _db, job_id: None)
    yield d
    for t in threading.enumerate():
        if t.name.startswith("pbp-jobsuche"):
            t.join(timeout=10)
    dash._db = vorher
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def netz(monkeypatch):
    """Die Netzpruefung mit ihrem echten Verhalten, aber ohne fremde Server."""
    monkeypatch.delenv("PBP_NETZ_PRUEFUNG", raising=False)
    from bewerbungs_assistent.services import netz_pruefung
    netz_pruefung.vergessen()
    yield netz_pruefung
    netz_pruefung.vergessen()


def _offline(monkeypatch):
    from bewerbungs_assistent.services import netz_pruefung
    monkeypatch.setattr(netz_pruefung, "erreichbar", lambda *a, **k: False)


def _online(monkeypatch):
    from bewerbungs_assistent.services import netz_pruefung
    monkeypatch.setattr(netz_pruefung, "erreichbar", lambda *a, **k: True)


# ══ Die Pruefung selbst ════════════════════════════════════════════

def test_ein_antwortendes_ziel_genuegt_und_man_wartet_nicht_auf_die_anderen(netz, monkeypatch):
    def antwort(url, timeout):
        if "google" in url:
            return True
        time.sleep(1.5)
        return False
    monkeypatch.setattr(netz, "_anfragen", antwort)
    t0 = time.perf_counter()
    assert netz.erreichbar() is True
    assert time.perf_counter() - t0 < 1.0


def test_antwortet_kein_ziel_ist_pbp_offline_und_das_wird_nicht_gemerkt(netz, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(netz, "_anfragen", lambda url, timeout: aufrufe.append(url) or False)
    assert netz.erreichbar() is False
    assert len(aufrufe) == len(netz.ZIELE)
    # wer das WLAN eben wieder verbunden hat, wartet nicht auf einen Zwischenspeicher
    assert netz.erreichbar() is False
    assert len(aufrufe) == 2 * len(netz.ZIELE)


def test_eine_bejahung_wird_kurz_gemerkt(netz, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(netz, "_anfragen", lambda url, timeout: aufrufe.append(url) or True)
    assert netz.erreichbar() is True
    gezaehlt = len(aufrufe)
    assert netz.erreichbar() is True
    assert len(aufrufe) == gezaehlt, "die zweite Frage hat wieder ins Netz gefragt"


def test_die_pruefung_ist_abschaltbar(netz, monkeypatch):
    monkeypatch.setenv("PBP_NETZ_PRUEFUNG", "0")
    monkeypatch.setattr(netz, "_anfragen", lambda *a: pytest.fail("es wurde gefragt"))
    assert netz.erreichbar() is True


def test_jede_http_antwort_zaehlt_ein_verbindungsfehler_nicht(netz, monkeypatch):
    import httpx

    class Antwort:
        status_code = 503
    monkeypatch.setattr(httpx, "head", lambda *a, **k: Antwort())
    assert netz._anfragen("https://beispiel.invalid", 1.0) is True
    for fehler in (httpx.ConnectError("x"), httpx.ConnectTimeout("x"), httpx.ProxyError("x")):
        def werfen(*a, _f=fehler, **k):
            raise _f
        monkeypatch.setattr(httpx, "head", werfen)
        assert netz._anfragen("https://beispiel.invalid", 1.0) is False, type(fehler)


# ══ Der Start ═════════════════════════════════════════════════════

def _jobsuche_jobs(db):
    return db.connect().execute(
        "SELECT COUNT(*) FROM background_jobs WHERE job_type='jobsuche'").fetchone()[0]


def test_offline_startet_keine_suche_und_aendert_nichts(db, monkeypatch):
    _offline(monkeypatch)
    from bewerbungs_assistent.services import jobsuche_start
    gesundheit_vorher = db.get_scraper_health()
    erg = jobsuche_start.starten(db, quellen=["bundesagentur"], keywords=["einkauf"],
                                 herkunft="claude")
    assert erg["status"] == "kein_netz", erg
    assert "Keine Verbindung" in erg["nachricht"]
    assert "netz_pruefung" in erg["schritte"]
    assert _jobsuche_jobs(db) == 0
    assert db.get_scraper_health() == gesundheit_vorher


def test_online_startet_wie_bisher(db, monkeypatch):
    _online(monkeypatch)
    import bewerbungs_assistent.job_scraper as js
    monkeypatch.setattr(js, "run_search", lambda _db, job_id, params: _db.update_background_job(
        job_id, "fertig", progress=100, result={"total": 0}))
    from bewerbungs_assistent.services import jobsuche_start
    erg = jobsuche_start.starten(db, quellen=["bundesagentur"], keywords=["einkauf"],
                                 herkunft="claude")
    assert erg["status"] == "gestartet", erg


def _werkzeug(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1141")
    register_all(mcp, db, logging.getLogger("test.1141"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def test_claude_hoert_kein_netz_und_keinen_rat_zu_den_suchbegriffen(db, monkeypatch):
    _offline(monkeypatch)
    erg = _werkzeug(db, "jobsuche_starten", {"keywords": ["einkauf"]})
    assert erg["status"] == "kein_netz", erg
    assert "Verbindung prüfen" in erg["naechster_schritt"]
    assert "Suchbegriffe" not in erg["nachricht"].replace("Suchbegriffen", "")  # kein Rat dazu
    assert _jobsuche_jobs(db) == 0


def test_das_dashboard_antwortet_503_mit_der_meldung(db, monkeypatch):
    _offline(monkeypatch)
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    r = TestClient(dash.app).post("/api/jobsuche/start", json={"keywords": ["einkauf"]})
    assert r.status_code == 503, r.text
    assert r.json()["status"] == "kein_netz"
    assert "Keine Verbindung" in r.json()["nachricht"]


def test_die_oberflaeche_zeigt_die_meldung_ohne_umbau():
    """Die Seite liest bei einem Fehlerstatus `nachricht` (frontend/src/api.js)."""
    js = (ROOT / "frontend" / "src" / "api.js").read_text(encoding="utf-8-sig")
    assert "data.nachricht" in js


def test_die_automatik_vermerkt_einen_ausgefallenen_lauf_nicht_als_gelaufen(db, monkeypatch):
    _offline(monkeypatch)
    from bewerbungs_assistent.services import automatik_scheduler as sched
    monkeypatch.setattr("bewerbungs_assistent.services.sicherung.taeglich", lambda _db: None)
    db.set_automatik_settings(jobsuche_intervall_tage=1)
    assert sched.run_jobsuche_now(db) == {"status": "kein_netz"}
    sched._tick(db)
    assert not db.get_automatik_settings()["jobsuche_last_at"], (
        "der Takt hat die Suche als gelaufen vermerkt - sie liefe erst morgen wieder")
    # mit Netz wird sie vermerkt
    _online(monkeypatch)
    import bewerbungs_assistent.job_scraper as js
    monkeypatch.setattr(js, "run_search", lambda _db, job_id, params: _db.update_background_job(
        job_id, "fertig", progress=100, result={"total": 0}))
    sched._tick(db)
    assert db.get_automatik_settings()["jobsuche_last_at"]


# ══ Der Lauf ══════════════════════════════════════════════════════

def _quellen_leer(monkeypatch):
    """Alle Adapter schlucken den Verbindungsfehler und geben [] zurueck."""
    from bewerbungs_assistent.job_scraper import arbeitnow, bundesagentur
    monkeypatch.setattr(bundesagentur, "search_bundesagentur", lambda p: [])
    monkeypatch.setattr(arbeitnow, "search_arbeitnow", lambda p: [])


def _suchen(db):
    from bewerbungs_assistent.job_scraper import run_search
    job_id = db.create_background_job("jobsuche", {})
    run_search(db, job_id, {"quellen": ["bundesagentur", "arbeitnow"], "keywords": ["einkauf"]})
    return db.get_background_job(job_id)


def _gesundheit(db, name):
    return next((h for h in db.get_scraper_health() if h["scraper_name"] == name), None)


def test_ein_lauf_ohne_netz_endet_als_fehler_und_zaehlt_keine_quelle(db, monkeypatch):
    _quellen_leer(monkeypatch)
    _offline(monkeypatch)
    job = _suchen(db)
    assert job["status"] == "fehler", job
    assert "Keine Verbindung" in (job.get("message") or "")
    assert "8 von 8" not in (job.get("message") or "") and "ok" not in (job.get("message") or "").split()
    ergebnis = job["result"] if isinstance(job["result"], dict) else {}
    assert ergebnis.get("kein_netz") is True
    # keine Quelle bekam einen stillen Lauf gebucht
    for q in ("bundesagentur", "arbeitnow"):
        h = _gesundheit(db, q)
        assert h is None or (h["consecutive_silent"] == 0 and h["total_runs"] == 0), (q, h)
    # und die Zeit der letzten Suche bleibt, wie sie war
    assert not db.get_profile_setting("last_search_at", None)


def test_fuenf_laeufe_ohne_netz_pausieren_keine_quelle(db, monkeypatch):
    _quellen_leer(monkeypatch)
    _offline(monkeypatch)
    for _ in range(6):
        _suchen(db)
    for q in ("bundesagentur", "arbeitnow"):
        h = _gesundheit(db, q)
        assert h is None or h["is_active"], f"{q} wurde pausiert: {h}"
    from bewerbungs_assistent.job_scraper import quellen_einteilen
    uebersprungen, _defekt, _probe = quellen_einteilen(db)
    assert not uebersprungen


def test_mit_netz_und_ohne_treffer_bleibt_es_ein_stiller_lauf(db, monkeypatch):
    """Die Gegenrichtung: ein Lauf OHNE Verbindungsproblem, der nichts findet,
    wird weiter ehrlich als stiller Lauf gefuehrt."""
    _quellen_leer(monkeypatch)
    _online(monkeypatch)
    job = _suchen(db)
    assert job["status"] == "fertig", job
    h = _gesundheit(db, "bundesagentur")
    assert h is not None and h["consecutive_silent"] == 1, h


def test_eine_uebersprungene_quelle_bekommt_keinen_fehler_gebucht(db, monkeypatch):
    _quellen_leer(monkeypatch)
    _online(monkeypatch)
    # arbeitnow ist pausiert (wie nach fuenf stillen Laeufen)
    db.update_scraper_health("arbeitnow", "ok", 0, 1.0)
    db.toggle_scraper("arbeitnow", False)
    vorher = _gesundheit(db, "arbeitnow")
    job = _suchen(db)
    status = (job["result"] or {}).get("quellen_status") or {}
    assert status["arbeitnow"]["status"] == "skipped"
    assert status["arbeitnow"]["detail"].startswith("pausiert"), status["arbeitnow"]
    assert "deprecated" not in status["arbeitnow"]["detail"]
    nachher = _gesundheit(db, "arbeitnow")
    assert nachher["consecutive_failures"] == vorher["consecutive_failures"] == 0, nachher
    assert nachher["total_runs"] == vorher["total_runs"]


def test_abgekuendigte_quellen_heissen_weiter_deprecated(db, monkeypatch):
    _quellen_leer(monkeypatch)
    _online(monkeypatch)
    from bewerbungs_assistent.job_scraper import run_search
    job_id = db.create_background_job("jobsuche", {})
    run_search(db, job_id, {"quellen": ["bundesagentur", "xing"], "keywords": ["einkauf"]})
    status = (db.get_background_job(job_id)["result"] or {}).get("quellen_status") or {}
    assert status["xing"]["detail"] == "deprecated"


def test_wer_rohtreffer_geliefert_hat_war_nicht_offline(db, monkeypatch):
    """Die Pruefung greift nur, wenn keine gelaufene Quelle auch nur einen
    Rohtreffer meldete: eine Quelle, die liefert und deren Treffer alle am
    Filter scheitern, ist die falsche Quelle - aber nicht offline."""
    from bewerbungs_assistent.job_scraper import arbeitnow, bundesagentur, rohtreffer

    def liefert_aber_nichts_passt(p):
        rohtreffer.melde("bundesagentur", 5)
        return []
    monkeypatch.setattr(bundesagentur, "search_bundesagentur", liefert_aber_nichts_passt)
    monkeypatch.setattr(arbeitnow, "search_arbeitnow", lambda p: [])
    _offline(monkeypatch)       # waere die Pruefung aktiv, wuerde sie den Lauf kippen
    job = _suchen(db)
    assert job["status"] == "fertig", job
    h = _gesundheit(db, "bundesagentur")
    assert h is not None and h["consecutive_silent"] == 0, h   # geliefert: nicht still


def test_auch_ein_adapter_der_den_fehler_wirft_wird_offline_nicht_gezaehlt(db, monkeypatch):
    """Nicht jede Quelle schluckt den Verbindungsfehler: eine, die ihn wirft,
    bekaeme sonst offline eine Fehlerserie gebucht und waere nach fuenf
    Laeufen pausiert."""
    from bewerbungs_assistent.job_scraper import arbeitnow, bundesagentur
    import httpx

    def wirft(p):
        raise httpx.ConnectError("Name or service not known")
    monkeypatch.setattr(bundesagentur, "search_bundesagentur", wirft)
    monkeypatch.setattr(arbeitnow, "search_arbeitnow", lambda p: [])
    _offline(monkeypatch)
    job = _suchen(db)
    assert job["status"] == "fehler" and "Keine Verbindung" in job["message"], job
    h = _gesundheit(db, "bundesagentur")
    assert h is None or h["consecutive_failures"] == 0, h
    # dasselbe mit Netz: dann ist der Fehler der Quelle ein Fehler der Quelle
    _online(monkeypatch)
    job = _suchen(db)
    assert job["status"] == "fertig", job
    assert _gesundheit(db, "bundesagentur")["consecutive_failures"] == 1
