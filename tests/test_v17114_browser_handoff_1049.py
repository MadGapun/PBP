"""Tests fuer #1049 — der Weg von der Jobsuche zu den Browser-Quellen.

Nutzerbericht vom 15.09.2026: der Knopf "Jobsuche starten" startet nur den
internen Lauf. Sechs aktive Quellen, die ein eingeloggtes Konto im Browser
brauchen, trugen seit fuenf Monaten nichts bei, drei defekte liefern nur im
Browser — und kein Weg fuehrte im Dashboard zum Lauf ueber Claude.
"""
import asyncio
import importlib
import json
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import browser_handoff as bh  # noqa: E402

BROWSER_LOGIN = {"stepstone", "indeed", "monster", "linkedin", "xing", "google_jobs"}
DEFEKT_BROWSER = {"heise_jobs", "meinestadt", "workday_dax"}


@pytest.fixture
def umgebung(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.switch_profile(db.create_profile("Muster"))
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    try:
        yield db, TestClient(dash.app)
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


# ------------------------------------------------ welche Quellen


def test_die_neun_quellen_aus_dem_bericht(umgebung):
    db, _ = umgebung
    eintraege = bh.browser_quellen(db, auswahl=sorted(BROWSER_LOGIN) + ["bundesagentur"])
    arten = {e["key"]: e["art"] for e in eintraege}
    assert {k for k, a in arten.items() if a == bh.UEBERSPRUNGEN} == BROWSER_LOGIN
    assert {k for k, a in arten.items() if a == bh.DEFEKT_NUR_BROWSER} == DEFEKT_BROWSER
    assert "bundesagentur" not in arten


def test_nicht_gewaehlte_browser_quellen_gelten_nicht_als_uebersprungen(umgebung):
    db, _ = umgebung
    eintraege = bh.browser_quellen(db, auswahl=["linkedin"])
    assert [e["key"] for e in eintraege if e["art"] == bh.UEBERSPRUNGEN] == ["linkedin"]


def test_workday_nennt_den_browser_nur_im_grund():
    """Die Regel prueft Grund UND Ersatzweg — sonst fehlte eine der drei."""
    assert bh._nur_im_browser({"defekt_grund": "liefert nur im Browser", "manueller_fallback": ""})
    assert not bh._nur_im_browser({"defekt_grund": "HTTP 500", "manueller_fallback": "spaeter"})


# ------------------------------------------------ Suchbegriffe


def test_begriffe_aus_beiden_eintragsformen_ohne_gesperrte():
    profil = {
        "primaere_suchen": [{"keywords": "Datenpflege", "notiz": "x"}, "Stammdaten"],
        "sekundaere_suchen": [{"keywords": "Datenpflege"}, {"keywords": "Controlling"}],
        "nicht_verwenden": [{"wert": "Controlling", "grund": "0 Treffer"}],
    }
    assert bh.suchbegriffe(profil) == ["Datenpflege", "Stammdaten"]
    assert bh.suchbegriffe(None) == []


def test_ohne_suchprofil_steht_ein_hinweis_statt_erfundener_begriffe(umgebung):
    db, _ = umgebung
    eintraege = bh.browser_quellen(db, auswahl=["xing"])
    xing = next(e for e in eintraege if e["key"] == "xing")
    assert xing["suchbegriffe"] == [] and xing["suchprofil_vorhanden"] is False
    text = bh.prompt(eintraege)
    assert "suchprofil_lesen('xing')" in text
    assert "statt welche zu erfinden" in text


def test_lesen_legt_kein_suchprofil_an(umgebung):
    """`get_portal_search_profile` legt beim ersten Lesen eines an — hier nicht."""
    db, _ = umgebung
    bh.browser_quellen(db, auswahl=sorted(BROWSER_LOGIN))
    anzahl = db.connect().execute(
        "SELECT COUNT(*) FROM portal_search_profiles").fetchone()[0]
    assert anzahl == 0


def test_gepflegte_begriffe_landen_im_prompt(umgebung):
    db, _ = umgebung
    db.update_portal_search_profile("stepstone", primaere_suchen=["Datenpflege"],
                                    nicht_verwenden=["Praktikum"])
    text = bh.prompt(bh.browser_quellen(db, auswahl=["stepstone"]))
    assert "erprobte Suchbegriffe: Datenpflege" in text
    assert "google_jobs_url()" in text


# ------------------------------------------------ der Prompt


def test_der_prompt_verlangt_volltext_und_rueckmeldung(umgebung):
    db, _ = umgebung
    text = bh.prompt(bh.browser_quellen(db, auswahl=sorted(BROWSER_LOGIN)))
    assert "VOLLTEXT" in text and "Titel allein reicht nicht" in text
    assert "Rohtreffer, uebernommen, und verworfen mit Grund" in text
    assert "linkedin_lauf_plan()" in text
    assert "Optional" in text and "Heise Jobs" in text


def test_ohne_browser_quellen_gibt_es_keinen_prompt():
    assert bh.prompt([]) == ""


def test_jedes_genannte_werkzeug_ist_registriert(umgebung):
    """Ein Prompt, der auf ein Werkzeug zeigt, das es nicht gibt, fuehrt ins Leere (#1000)."""
    db, _ = umgebung
    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test 1049")
    register_all(mcp, db, logging.getLogger("test.1049"))
    async def _werkzeuge():
        # Dieselbe Form wie test_mcp_registry: je nach FastMCP-Fassung.
        if hasattr(mcp, "list_tools"):
            return await mcp.list_tools()
        return list((await mcp.get_tools()).values())

    namen = {w.name for w in asyncio.run(_werkzeuge())}
    text = bh.prompt(bh.browser_quellen(db, auswahl=sorted(BROWSER_LOGIN)))
    for werkzeug in ("suchprofil_lesen", "linkedin_lauf_plan", "google_jobs_url",
                     "stelle_manuell_anlegen", "linkedin_treffer_uebernehmen"):
        assert werkzeug in text, werkzeug
        assert werkzeug in namen, f"{werkzeug} ist nicht registriert"


# ------------------------------------------------ Endpunkte


def test_der_endpunkt_liefert_liste_und_prompt(umgebung):
    db, tc = umgebung
    db.set_profile_setting("active_sources", ["bundesagentur", "linkedin", "xing"])
    daten = tc.get("/api/jobsuche/browser-quellen").json()
    keys = {q["key"] for q in daten["quellen"] if q["art"] == bh.UEBERSPRUNGEN}
    assert keys == {"linkedin", "xing"}
    assert daten["prompt"].startswith("Suche fuer mich")


def test_der_start_haelt_die_uebersprungenen_quellen_fest(umgebung, monkeypatch):
    db, tc = umgebung
    db.set_search_criteria("keywords_muss", ["Datenpflege"])
    import bewerbungs_assistent.job_scraper as js
    monkeypatch.setattr(js, "run_search", lambda *_a, **_k: None)
    antwort = tc.post("/api/jobsuche/start",
                      json={"quellen": ["bundesagentur", "linkedin"]}).json()
    assert antwort["status"] == "gestartet", antwort
    job = db.get_background_job(antwort["job_id"])
    assert job["params"]["browser_quellen"] == ["linkedin"]


def test_last_nennt_die_uebersprungenen_browser_quellen(umgebung):
    db, tc = umgebung
    job_id = db.create_background_job(
        "jobsuche", {"quellen": ["bundesagentur"], "browser_quellen": ["linkedin", "xing"]})
    db.update_background_job(job_id, "fertig", message="ok",
                             result={"total": 3, "quellen_status": {"bundesagentur": {"status": "ok"}}})
    daten = tc.get("/api/jobsuche/last").json()
    assert daten["quellen"]["nur_browser"] == 2


def test_der_mcp_start_haelt_die_uebersprungenen_quellen_fest(umgebung, monkeypatch):
    """Derselbe Vermerk auf dem Weg, den Claude nimmt."""
    db, _ = umgebung
    db.set_search_criteria("keywords_muss", ["Datenpflege"])
    import bewerbungs_assistent.job_scraper as js
    monkeypatch.setattr(js, "run_search", lambda *_a, **_k: None)
    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test 1049 Start")
    register_all(mcp, db, logging.getLogger("test.1049.start"))

    async def _lauf():
        werkzeug = await mcp.get_tool("jobsuche_starten")
        res = await werkzeug.run({"quellen": ["bundesagentur", "linkedin"]})
        return getattr(res, "structured_content", res)

    antwort = asyncio.run(_lauf())
    assert antwort["status"] == "gestartet", antwort
    job = db.get_background_job(antwort["job_id"])
    assert job["params"]["browser_quellen"] == ["linkedin"]
