"""#1092: Nach der Suche sortiert die lokale KI nur mit Schalter aus —
über denselben Weg wie das Werkzeug, ohne Stellen ohne Anzeigentext und
ohne erfundenen Score.

Die lokale KI ist ein Testdoppel; der Weg läuft trotzdem bis zur
Aussortierung durch. Diese Schleife war zweimal stumm kaputt (beta.63),
ein Test, der nur den Aufruf prüft, hätte das nicht gesehen.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"


class _KI:
    """Testdoppel: PASST_NICHT für Titel mit "fremd", sonst PASST."""

    def __init__(self):
        self.gefragt = []

    def get_status(self, force_refresh=False):
        return SimpleNamespace(ollama_available=True, available_models=["m"],
                               user_state="active", selected_model="m")

    def warmup(self):
        return {"status": "warm", "duration_sec": 0}

    def run(self, kind, payload):
        self.gefragt.append(payload["job_title"])
        urteil = "PASST_NICHT" if "fremd" in payload["job_title"] else "PASST"
        return SimpleNamespace(success=True, fallback_message="",
                               payload={"decision": urteil, "reason": "Testurteil"})


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "KI-Test"})
    ki = _KI()
    from bewerbungs_assistent.services import llm_service
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db=None: ki)
    d.ki = ki
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung, titel, text, score=3):
    db.save_jobs([{"hash": kennung, "title": titel, "company": "Musterbetrieb GmbH",
                   "url": f"https://example.com/{kennung}", "source": "manuell",
                   "description": text, "score": score}])
    return db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE ?",
                                (f"%{kennung}",)).fetchone()[0]


def _zeile(db, voll):
    return dict(db.connect().execute("SELECT * FROM jobs WHERE hash=?", (voll,)).fetchone())


LANG = "Ein ausführlicher Anzeigentext mit Aufgaben und Anforderungen. " * 3


# ── AK 2 und 3: kein Urteil ohne Text, kein erfundener Score ─────────

def test_ohne_anzeigentext_kein_urteil(db):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    ohne = _stelle(db, "a1092", "Stelle fremd ohne Text", "kurz")
    erg = aa.aussortieren(db, max_stellen=30)
    assert "Stelle fremd ohne Text" not in db.ki.gefragt
    assert _zeile(db, ohne)["is_active"] == 1
    assert erg["uebersprungen_ohne_beschreibung"] == 1


def test_passt_setzt_keinen_score(db):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    voll = _stelle(db, "b1092", "Passende Stelle", LANG, score=2)
    vorher = _zeile(db, voll)["score"]
    aa.aussortieren(db, max_stellen=30)
    assert "Passende Stelle" in db.ki.gefragt
    assert _zeile(db, voll)["score"] == vorher, "Score wurde verändert"


def test_passt_nicht_wird_als_automatik_aussortiert(db):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    voll = _stelle(db, "c1092", "Stelle fremd", LANG)
    erg = aa.aussortieren(db, max_stellen=30)
    z = _zeile(db, voll)
    assert z["is_active"] == 0
    assert z["dismissed_by"] == "automatik", "Urteil der KI stand als 'ich' da"
    assert erg["passt_nicht"] == 1


# ── AK 4: Schalter, Vorgabe aus ─────────────────────────────────────

def _suchjob(db):
    jid = db.create_background_job("jobsuche", {})
    db.update_background_job(jid, "fertig", progress=100, message="ok",
                             result={"total": 1})
    return jid


def test_nach_der_suche_ohne_schalter_nichts(db):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    voll = _stelle(db, "d1092", "Stelle fremd", LANG)
    assert aa.nach_suche(db, _suchjob(db)) is None
    assert db.ki.gefragt == []
    assert _zeile(db, voll)["is_active"] == 1


def test_nach_der_suche_mit_schalter_und_ergebnis_im_lauf(db):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    voll = _stelle(db, "e1092", "Stelle fremd", LANG)
    db.set_profile_setting(aa.SCHALTER, "true")
    jid = _suchjob(db)
    aa.nach_suche(db, jid)
    assert _zeile(db, voll)["is_active"] == 0
    assert db.get_background_job(jid)["result"]["auto_aussortiert"]["aussortiert"] == 1


def test_alte_schleife_ruft_denselben_dienst(db):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    from bewerbungs_assistent.tools import jobs as tj
    voll = _stelle(db, "f1092", "Stelle fremd", LANG)
    db.set_profile_setting(aa.SCHALTER, "true")
    tj._maybe_auto_dismiss_after_search(db, _suchjob(db))
    assert _zeile(db, voll)["is_active"] == 0


def test_hinweis_nur_bei_stiller_alter_vorgabe(db):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    from bewerbungs_assistent.services.onboarding_hints import _condition_auto_aussortieren_aus
    assert _condition_auto_aussortieren_aus(db) is False, "ohne aktive KI kein Hinweis"
    db.set_profile_setting("llm_local_state", "active")
    assert _condition_auto_aussortieren_aus(db) is True
    db.set_profile_setting(aa.SCHALTER, "false")
    assert _condition_auto_aussortieren_aus(db) is False, "selbst gesetzt: kein Hinweis"


def test_schalter_im_dashboard(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    tc = TestClient(dash.app)
    assert tc.get("/api/settings/auto-aussortieren").json() == {"an": False}
    assert tc.put("/api/settings/auto-aussortieren", json={"an": True}).status_code == 200
    assert tc.get("/api/settings/auto-aussortieren").json() == {"an": True}
    assert tc.put("/api/settings/auto-aussortieren", json={"an": "ja"}).status_code == 400


def test_schalter_ueber_claude(db):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    from bewerbungs_assistent.services import auto_aussortierung as aa
    mcp = FastMCP("PBP #1092")
    register_all(mcp, db, logging.getLogger("test.1092"))

    async def lauf():
        t = await mcp.get_tool("automatik_setzen")
        return (await t.run({"nach_suche_aussortieren": True})).structured_content
    assert asyncio.run(lauf())["nach_suche_aussortieren"] is True
    assert aa.schalter_an(db)


# ── AK 1 und 5: ein Weg, beide Startwege ─────────────────────────────

def test_ki_abfrage_steht_nur_an_einer_stelle():
    funde = []
    for p in SRC.rglob("*.py"):
        if p.name == "llm_service.py":
            continue
        if "MATCH_JOB_TO_SKILLS" in p.read_text(encoding="utf-8-sig"):
            funde.append(p.name)
    assert funde == ["auto_aussortierung.py"], funde


def test_kein_fester_score_mehr():
    for p in (SRC / "tools").rglob("*.py"):
        assert '{"score": 35}' not in p.read_text(encoding="utf-8"), p.name


def _ruft(datei: Path, funktion: str, ziel: str) -> bool:
    baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
    for f in ast.walk(baum):
        if isinstance(f, ast.FunctionDef) and f.name == funktion:
            return any(isinstance(c, ast.Call) and getattr(c.func, "attr",
                       getattr(c.func, "id", "")) == ziel for c in ast.walk(f))
    return False


def test_beide_startwege_rufen_den_schritt():
    assert _ruft(SRC / "dashboard.py", "_run_search", "nach_suche"), "Dashboard-Knopf"
    assert _ruft(SRC / "tools" / "jobs.py", "_run_search",
                 "_maybe_auto_dismiss_after_search"), "jobsuche_starten"
    assert _ruft(SRC / "tools" / "jobs.py", "_maybe_auto_dismiss_after_search",
                 "nach_suche")
