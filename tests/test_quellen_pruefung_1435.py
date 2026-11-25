"""#1435: HTTP-Fehler sind Fehler, abgeschaltete Quellen haben einen Rueckweg.

Datenbank isoliert, keine Netzabrufe (die Scraper werden ersetzt).
"""
from __future__ import annotations

import ast
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY, quellen_einteilen, rohtreffer
from bewerbungs_assistent.services.scraper_classifier import klasse_fuer_http_status

SCRAPER = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent" / "job_scraper"


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database

    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


class _Antwort:
    def __init__(self, code):
        self.status_code = code


# ── Register ────────────────────────────────────────────────────────

def test_nur_fehlerantworten_sind_ein_fehlschlag():
    rohtreffer.lauf_beginnen()
    for _ in range(3):
        assert rohtreffer.http_ok("probe_a", _Antwort(404)) is False
    assert rohtreffer.http_fehlschlag("probe_a") == (404, 3)


def test_eine_gute_antwort_genuegt():
    rohtreffer.lauf_beginnen()
    rohtreffer.http_ok("probe_b", _Antwort(404))
    assert rohtreffer.http_ok("probe_b", _Antwort(200)) is True
    assert rohtreffer.http_fehlschlag("probe_b") is None


def test_ohne_meldung_kein_urteil_und_neuer_lauf_vergisst():
    rohtreffer.lauf_beginnen()
    assert rohtreffer.http_fehlschlag("probe_c") is None
    rohtreffer.http_ok("probe_c", _Antwort(403))
    rohtreffer.lauf_beginnen()
    assert rohtreffer.http_befund("probe_c") is None


@pytest.mark.parametrize("code,klasse", [(404, "tot"), (410, "tot"), (403, "blockiert"),
                                         (429, "blockiert"), (503, "server_weg"), (400, "kaputt")])
def test_klasse_je_status(code, klasse):
    assert klasse_fuer_http_status(code) == klasse


def test_jeder_scraper_meldet_seine_fehlerantwort():
    """Ein Guard zaehlt erst, wenn er aufgerufen wird: kein `status_code != 200` mehr ohne Meldung."""
    ohne = []
    for datei in sorted(SCRAPER.glob("*.py")):
        if datei.name in ("health.py", "__init__.py"):
            continue
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if (isinstance(knoten, ast.Compare) and isinstance(knoten.left, ast.Attribute)
                    and knoten.left.attr == "status_code" and isinstance(knoten.ops[0], ast.NotEq)):
                ohne.append(f"{datei.name}:{knoten.lineno}")
    assert not ohne, ohne


# ── Lauf ────────────────────────────────────────────────────────────

def _lauf(db, monkeypatch, codes):
    """Bundesagentur meldet nur die gegebenen HTTP-Antworten; arbeitnow liefert (kein Offline-Fall, #1141)."""
    from bewerbungs_assistent.job_scraper import arbeitnow, bundesagentur, run_search

    def ba(_p):
        for code in codes:
            rohtreffer.http_ok("bundesagentur", _Antwort(code))
        return []

    def an(_p):
        rohtreffer.melde("arbeitnow", 5)
        return []
    monkeypatch.setattr(bundesagentur, "search_bundesagentur", ba)
    monkeypatch.setattr(arbeitnow, "search_arbeitnow", an)
    job_id = db.create_background_job("jobsuche", {})
    run_search(db, job_id, {"quellen": ["bundesagentur", "arbeitnow"], "keywords": ["einkauf"]})
    return {h["scraper_name"]: h for h in db.get_scraper_health()}["bundesagentur"]


def test_404_wird_als_fehler_mit_klasse_gebucht(db, monkeypatch):
    h = _lauf(db, monkeypatch, [404, 404])
    assert h["consecutive_failures"] == 1 and h["consecutive_silent"] == 0, h
    assert h["error_class"] == "tot" and "HTTP 404" in (h["last_error"] or ""), h


def test_eine_gute_antwort_bleibt_ein_stiller_lauf(db, monkeypatch):
    h = _lauf(db, monkeypatch, [404, 200])
    assert h["consecutive_failures"] == 0 and h["consecutive_silent"] == 1, h


def test_abgekuendigte_und_nicht_eingerichtete_quellen_werden_nicht_gezaehlt(db, monkeypatch):
    from bewerbungs_assistent.job_scraper import arbeitnow, run_search
    monkeypatch.setattr(arbeitnow, "search_arbeitnow", lambda p: (rohtreffer.melde("arbeitnow", 5), [])[1])
    job_id = db.create_background_job("jobsuche", {})
    run_search(db, job_id, {"quellen": ["arbeitnow", "solcom", "kimeta", "adzuna"], "keywords": ["einkauf"]})
    status = (db.get_background_job(job_id)["result"] or {}).get("quellen_status") or {}
    assert status["solcom"]["detail"].startswith("nur im Browser"), status["solcom"]
    assert status["kimeta"]["detail"].startswith("nur im Browser"), status["kimeta"]
    assert status["adzuna"]["detail"].startswith("nicht eingerichtet"), status["adzuna"]
    gebucht = {h["scraper_name"] for h in db.get_scraper_health()}
    assert not gebucht & {"solcom", "kimeta", "adzuna"}, gebucht


def test_abgekuendigte_quellen_laufen_nicht():
    """robots.txt (kimeta) und Bot-Schutz (solcom): nie automatisch abrufen."""
    for q in ("solcom", "kimeta"):
        assert SOURCE_REGISTRY[q].get("deprecated"), q
        assert SOURCE_REGISTRY[q].get("handoff_verfuegbar"), q


# ── Rueckweg ────────────────────────────────────────────────────────

def _quelle(db, name, *, aktiv, fehler, letzter_lauf, termin=None):
    db.update_scraper_health(name, "ok", 1, 1.0)
    db.connect().execute(
        "UPDATE scraper_health SET is_active=?, consecutive_failures=?, last_run=?, reactivate_at=? "
        "WHERE scraper_name=?", (1 if aktiv else 0, fehler, letzter_lauf, termin, name))
    db.connect().commit()


def test_automatisch_abgeschaltet_ohne_termin_bekommt_probelauf(db):
    jetzt = datetime(2026, 11, 24, 8, 0)
    _quelle(db, "gulp", aktiv=False, fehler=21, letzter_lauf="2026-10-02T08:25:37")
    weg, defekt, probe = quellen_einteilen(db, jetzt.isoformat())
    assert "gulp" in probe and "gulp" not in weg


def test_frisch_abgeschaltet_wartet_eine_woche(db):
    jetzt = datetime(2026, 11, 24, 8, 0)
    _quelle(db, "gulp", aktiv=False, fehler=6, letzter_lauf=(jetzt - timedelta(days=2)).isoformat())
    weg, _defekt, probe = quellen_einteilen(db, jetzt.isoformat())
    assert "gulp" in weg and "gulp" not in probe


def test_von_hand_abgeschaltet_bleibt_aus(db):
    _quelle(db, "gulp", aktiv=True, fehler=0, letzter_lauf="2026-10-02T08:25:37")
    db.toggle_scraper("gulp", False)
    weg, _defekt, probe = quellen_einteilen(db, "2026-11-24T08:00:00")
    assert "gulp" in weg and "gulp" not in probe


def test_aktiv_mit_fehlerserie_probt_nach_einer_woche(db):
    _quelle(db, "workable", aktiv=True, fehler=8, letzter_lauf="2026-10-02T08:25:37")
    weg, defekt, probe = quellen_einteilen(db, "2026-11-24T08:00:00")
    assert "workable" in probe and "workable" not in weg and "workable" not in defekt


# ── Keine veralteten Fehler ─────────────────────────────────────────

def test_erfolg_loescht_die_alte_fehlerklasse(db):
    db.update_scraper_health("hays", "timeout", 0, 90, error_class="server_weg")
    db.update_scraper_health("hays", "ok", 5, 3)
    h = {x["scraper_name"]: x for x in db.get_scraper_health()}["hays"]
    assert h["error_class"] is None and h["last_error"] is None


def test_stiller_lauf_loescht_den_alten_fehlertext(db):
    db.update_scraper_health("adzuna", "error", 0, 1, detail="deprecated")
    db.update_scraper_health("adzuna", "ok", 0, 1)
    h = {x["scraper_name"]: x for x in db.get_scraper_health()}["adzuna"]
    assert h["last_error"] is None and h["consecutive_silent"] == 1
