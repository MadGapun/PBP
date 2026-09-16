"""Tests fuer #1035: ein Score hat eine Nachkommastelle, und die Teile ergeben ihn.

Gemeldet mit einer Stelle, deren Score im Dashboard als
`6.199999999999999` stand. Dahinter lagen vier Befunde: die Summe der
Regler blieb ungerundet, die Neuberechnung schnitt Zehntel ab (1.156 von
1.174 Scores ganzzahlig), Fach- und Rahmenwert wurden einzeln gerundet und
die Summe aus ungerundeten Werten gebildet, und bei Untergrenze oder
Handwert stand die alte Aufteilung unkommentiert neben dem Score.
"""
import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

TEXT = "Ausfuehrliche Stellenbeschreibung mit genug Inhalt. " * 3


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "rundung.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.switch_profile(datenbank.create_profile("Rundung"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _nachkommastellen(wert) -> int:
    text = repr(float(wert))
    return 0 if "." not in text else len(text.split(".")[1].rstrip("0"))


def _stelle(nr=1, **extra):
    job = {
        "hash": f"r1035{nr:03d}", "title": f"Rolle {nr}",
        "company": f"Firma {nr}", "url": f"https://example.com/1035/{nr}",
        "source": "manuell", "_manual_entry": True, "description": TEXT,
        "score": 10.0,
    }
    job.update(extra)
    return job


def _mcp(db, modul):
    from fastmcp import FastMCP

    register = importlib.import_module(
        f"bewerbungs_assistent.tools.{modul}").register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    return mcp


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def _gespeichert(db, nr=1):
    return dict(db.connect().execute(
        "SELECT hash, score, fachscore, rahmenscore FROM jobs WHERE hash LIKE ?",
        (f"%r1035{nr:03d}",)).fetchone())


# ============================================== Befund 1: der Regler


def test_ak1_die_summe_der_regler_hat_hoechstens_eine_nachkommastelle(db):
    """Woertlich der Meldefall: 11,2 mit einem Abzug von 2."""
    from bewerbungs_assistent.services.scoring_service import (
        apply_scoring_adjustments)

    job = {"score": 11.2, "remote_level": "vor_ort"}
    abzug = apply_scoring_adjustments(dict(job), 11.2, db)["adjustment_total"]
    assert abzug != 0, \
        "ohne Abzug prueft der Fall nichts — Regler-Vorgabe nachsehen"
    # Eine Basis suchen, bei der die ungerundete Summe WIRKLICH einen
    # Rechenrest traegt. Die erste Fassung nahm 11,2 fest — mit dem hier
    # geltenden Abzug ergab das zufaellig eine glatte Zahl, und die
    # Gegenprobe blieb ohne Rundung gruen.
    basen = [round(0.1 * i, 1) for i in range(1, 400)]
    basis = next(b for b in basen
                 if b + abzug > 0 and _nachkommastellen(b + abzug) > 1)
    ergebnis = apply_scoring_adjustments(dict(job, score=basis), basis, db)
    assert _nachkommastellen(ergebnis["final_score"]) <= 1, (
        basis, abzug, ergebnis["final_score"])


# ======================================== Befund 2: die Neuberechnung


def _feste_bewertung(monkeypatch, score, fach, rahmen):
    from bewerbungs_assistent import job_scraper

    def _bewerten(job, criteria):
        job["_fachscore"], job["_rahmenscore"] = fach, rahmen
        return score

    monkeypatch.setattr(job_scraper, "calculate_score", _bewerten)


def test_ak2_die_neuberechnung_speichert_zehntel(db, monkeypatch):
    db.save_jobs([_stelle()])
    _feste_bewertung(monkeypatch, 18.7, 12.5, 6.2)
    _call(_mcp(db, "jobs"), "scores_neu_berechnen", {})
    assert _gespeichert(db)["score"] == 18.7


def test_ak3_eine_geaenderte_nachkommastelle_wird_geschrieben(db, monkeypatch):
    db.save_jobs([_stelle(score=3.8)])
    _feste_bewertung(monkeypatch, 3.0, 2.0, 1.0)
    antwort = _call(_mcp(db, "jobs"), "scores_neu_berechnen", {})
    assert _gespeichert(db)["score"] == 3.0, \
        "3,8 und 3,0 galten abgeschnitten als gleich — der Score blieb 3,8"
    assert antwort["geaendert"] == 1


def test_fit_analyse_uebernimmt_den_score_nicht_abgeschnitten():
    """Dieselbe Bauform wie in scores_neu_berechnen (#1035)."""
    import inspect

    from bewerbungs_assistent.tools import jobs

    code = inspect.getsource(jobs)
    werkzeug = code[code.index("def fit_analyse(job_hash"):]
    werkzeug = werkzeug[:werkzeug.index("@mcp.tool()")]
    assert "int(new_score)" not in werkzeug
    assert '{"score": round(float(new_score), 1)}' in werkzeug


def test_der_backtest_rechnet_mit_zehnteln(monkeypatch):
    from bewerbungs_assistent import job_scraper
    from bewerbungs_assistent.services import kalibrierung

    monkeypatch.setattr(job_scraper, "calculate_score", lambda job, c: 18.7)
    assert kalibrierung.schatten_score({"title": "x"}, {}) == 18.7


def test_stelle_bearbeiten_schreibt_die_teile_mit(db, monkeypatch):
    db.save_jobs([_stelle()])
    hash_ = _gespeichert(db)["hash"]
    db.update_job(hash_, {"fachscore": 1.0, "rahmenscore": 1.0})
    _feste_bewertung(monkeypatch, 12.3, 8.0, 4.3)
    _call(_mcp(db, "jobs"), "stelle_bearbeiten",
          {"job_hash": "r1035001", "beschreibung": TEXT + " neu"})
    zeile = _gespeichert(db)
    assert zeile["score"] == 12.3
    assert (zeile["fachscore"], zeile["rahmenscore"]) == (8.0, 4.3)


def test_das_frontend_gibt_keinen_score_roh_aus():
    """Sechs Stellen gaben `job.score` roh aus — eine davon zeigte den
    Rechenrest. Jede Ausgabe geht durch lib/score.js."""
    import re

    roh = re.compile(r"\{\s*[\w.?]*\.score\s*(\|\|\s*0\s*)?\}")
    funde = []
    for datei in (_repo() / "frontend" / "src").rglob("*.jsx"):
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if roh.search(zeile):
                funde.append(f"{datei.name}:{nr}: {zeile.strip()[:80]}")
    assert not funde, "\n".join(funde)


# ======================================== Befund 3: Teile und Summe


@pytest.mark.parametrize("gewichte", [
    {"python": 1.25, "sql": 0.35},
    {"python": 0.45, "sql": 0.45, "cloud": 0.45},
])
def test_ak4_fach_und_rahmen_ergeben_den_score(gewichte):
    from bewerbungs_assistent.job_scraper import calculate_score

    kriterien = {"keywords_muss": list(gewichte), "keyword_gewichte": gewichte,
                 "keywords_plus": ["remote"]}
    job = {"title": "Python SQL Cloud Entwicklung",
           "description": TEXT + " python sql cloud remote",
           "remote_level": "hybrid", "employment_type": "festanstellung"}
    score = calculate_score(job, kriterien)
    assert score > 0, "ohne Treffer prueft der Fall nichts"
    # v1.7.117 (#1052): die Zusicherung aus #1035 ist AUFGEHOBEN, und
    # zwar absichtlich. Sie lautete "die Teile ergeben die Summe" und war
    # richtig, solange es eine Summe gab. Genau die gibt es nicht mehr:
    # Fachwert und Rahmenwert stehen nebeneinander und werden nirgends
    # addiert (Akzeptanzkriterium 1 von #1052).
    #
    # Was von #1035 GILT, ist die Rundungsregel dahinter: erst die Teile
    # runden, dann rechnen. Sonst steht neben "fachlich 7,5" ein Score
    # mit einem Rechenrest, und eine Erklaerung, die nicht aufgeht, ist
    # schlimmer als keine.
    assert job["_fachscore"] == round(job["_fachscore"], 1)
    assert job["_rahmenscore"] == round(job["_rahmenscore"], 1)
    assert score == round(score, 1)
    # Und die Probe darauf, dass wirklich nicht mehr addiert wird: der
    # Rahmen dieser Anzeige ist von null verschieden, die Summe waere
    # also eine andere Zahl.
    assert job["_rahmenscore"] != 0
    assert round(job["_fachscore"] + job["_rahmenscore"], 1) != score


# ====================================== Befund 4: Ausnahmen erkennbar


def test_ak4_die_untergrenze_steht_in_der_herkunft(db):
    db.save_jobs([_stelle(score=0)])
    db.update_job(_gespeichert(db)["hash"], {"fachscore": 2.0,
                                             "rahmenscore": -3.0})
    antwort = _call(_mcp(db, "analyse"), "scoring_vorschau",
                    {"job_hash": "r1035001"})
    assert "Untergrenze" in (antwort.get("score_herkunft") or "")


def test_ak4_ein_handwert_verwirft_die_alte_aufteilung(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    db.save_jobs([_stelle(score=10.0)])
    hash_ = _gespeichert(db)["hash"]
    db.update_job(hash_, {"fachscore": 7.5, "rahmenscore": 2.5})
    vorher = dash._db
    dash._db = db
    try:
        antwort = TestClient(dash.app).put(
            f"/api/jobs/{hash_}/score", json={"score": 12.34})
    finally:
        dash._db = vorher
    assert antwort.status_code == 200
    zeile = _gespeichert(db)
    assert zeile["score"] == 12.3
    assert zeile["fachscore"] is None and zeile["rahmenscore"] is None
