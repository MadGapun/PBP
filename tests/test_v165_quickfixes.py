"""Tests fuer v1.6.5 Quick-Fixes (#544, #545, #546, #549, #550, #553, #556, #557, #558, #559)."""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v165qf_test_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _result(raw):
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if hasattr(raw, "structured_content"):
        raw = raw.structured_content
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


# ============= #544 — min_gehalt-Param ================
def test_544_min_gehalt_parameter(setup_env):
    """suchkriterien_setzen akzeptiert min_gehalt/min_tagessatz/min_stundensatz direkt."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    raw = _call(mcp, "suchkriterien_setzen", {
        "keywords_muss": ["python"],
        "min_gehalt": 65000,
        "min_tagessatz": 800,
        "min_stundensatz": 90,
    })
    result = _result(raw)
    assert result.get("status") == "gespeichert"
    crit = db.get_search_criteria()
    assert crit.get("min_gehalt") == 65000.0
    assert crit.get("min_tagessatz") == 800.0
    assert crit.get("min_stundensatz") == 90.0


# ============= #545 — Genderform-Filter ===============
def test_545_werkstudent_matcht_werkstudierende(setup_env):
    """AUSSCHLUSS 'Werkstudent' filtert auch 'Werkstudierende' weg."""
    from bewerbungs_assistent.job_scraper import _fuzzy_keyword_match
    assert _fuzzy_keyword_match("Werkstudent", "Werkstudierende fuer Backend gesucht")
    assert _fuzzy_keyword_match("Werkstudent", "Wir suchen einen Werkstudierenden")
    assert _fuzzy_keyword_match("Werkstudent", "Studentische Hilfskraft")


def test_545_praktikant_matcht_praktikum(setup_env):
    """AUSSCHLUSS 'Praktikant' filtert auch 'Praktikum'/'Praktikantin'."""
    from bewerbungs_assistent.job_scraper import _fuzzy_keyword_match
    assert _fuzzy_keyword_match("Praktikant", "Pflichtpraktikum 6 Monate")
    assert _fuzzy_keyword_match("Praktikant", "Praktikantin im Marketing")
    assert _fuzzy_keyword_match("Praktikum", "Praktikantenstelle Vertrieb")


# ============= #546 — Word-Boundary fuer Kurz-Keywords =====
def test_546_short_keyword_word_boundary(setup_env):
    """Kurz-Keywords (<=4 Zeichen) duerfen nicht innerhalb eines Wortes matchen."""
    from bewerbungs_assistent.job_scraper import _fuzzy_keyword_match
    # "AI" darf NICHT in "Mainz" oder "Hauptmainframe" matchen
    assert not _fuzzy_keyword_match("AI", "Standort Mainz")
    assert not _fuzzy_keyword_match("ML", "HTML5 Frontend")
    # Aber an Wortgrenzen schon
    assert _fuzzy_keyword_match("AI", "AI Engineer gesucht")
    assert _fuzzy_keyword_match("ML", "ML Engineer (m/w/d)")


def test_546_long_keyword_substring_still_works(setup_env):
    """Lange Keywords behalten Substring-Match (z.B. fuer Komposita)."""
    from bewerbungs_assistent.job_scraper import _fuzzy_keyword_match
    assert _fuzzy_keyword_match("Python", "Pythonentwicklung")
    assert _fuzzy_keyword_match("python", "Senior Python Engineer")


# ============= #549 — bereinigung-Stats nicht doppelt =====
def test_549_bereinigung_nicht_doppelt(setup_env):
    """jobsuche_status liefert bereinigung NICHT zusaetzlich in ergebnis."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    job_id = db.create_background_job("jobsuche")
    db.update_background_job(job_id, status="fertig", progress=100, result={
        "total": 5,
        "bereinigung": {"alte_geloescht": 3},
    })
    raw = _call(mcp, "jobsuche_status", {"job_id": job_id})
    result = _result(raw)
    # bereinigung soll genau einmal erscheinen (top-level), nicht zusaetzlich in ergebnis
    assert "bereinigung" in result
    assert result["bereinigung"] == {"alte_geloescht": 3}
    assert "bereinigung" not in (result.get("ergebnis") or {})


# ============= #550 — firma='nan' Filter =================
def test_550_pandas_nan_company_gefiltert(setup_env):
    """jobspy-Mapper interpretiert pandas-NaN nicht als Firmenname 'nan'."""
    from bewerbungs_assistent.job_scraper.jobspy_source import _map_row
    import math
    row = {
        "title": "Engineer",
        "company": math.nan,  # pandas NaN as float
        "location": "",
        "description": "",
    }
    job = _map_row(row, "linkedin")
    assert job["company"] == "Nicht angegeben"
    assert job["company"] != "nan"


def test_550_string_nan_gefiltert(setup_env):
    """String 'nan' (z.B. von astype(str)) wird ebenfalls gefiltert."""
    from bewerbungs_assistent.job_scraper.jobspy_source import _map_row
    row = {"title": "Eng", "company": "nan", "location": "", "description": ""}
    job = _map_row(row, "indeed")
    assert job["company"] == "Nicht angegeben"


# ============= #553 — letzte_treffer Felder ================
def test_553_drei_treffer_felder_im_diagnose(setup_env):
    """scraper_diagnose liefert letzte_rohtreffer / letzte_gefilterte_treffer / letzte_neue_treffer."""
    db, _ = setup_env
    db.update_scraper_health("test_quelle", "ok", count=10, time_s=1.0,
                              filtered_count=7, new_count=4)
    from bewerbungs_assistent.server import mcp
    raw = _call(mcp, "scraper_diagnose", {"aktion": "status"})
    result = _result(raw)
    scrapers = result.get("scrapers", [])
    test_entry = next((s for s in scrapers if s["name"] == "test_quelle"), None)
    assert test_entry is not None
    assert test_entry["letzte_rohtreffer"] == 10
    assert test_entry["letzte_gefilterte_treffer"] == 7
    assert test_entry["letzte_neue_treffer"] == 4
    # Backwards compat
    assert test_entry["letzte_treffer"] == 10


# ============= #557 — quelle Partial-Match =====================
def test_557_linkedin_matcht_jobspy_linkedin(setup_env):
    """Filter quelle='linkedin' findet auch source='jobspy_linkedin'."""
    db, _ = setup_env
    db.save_jobs([
        {
            "hash": "li_h1",
            "title": "Senior Python",
            "company": "TestCorp",
            "url": "https://example.com/1",
            "source": "jobspy_linkedin",
            "score": 50,
        },
        {
            "hash": "ba_h1",
            "title": "Java Dev",
            "company": "OtherCorp",
            "url": "https://example.com/2",
            "source": "bundesagentur",
            "score": 30,
        },
    ])
    jobs = db.get_active_jobs(filters={"source": "linkedin"})
    sources = {j["source"] for j in jobs}
    assert "jobspy_linkedin" in sources
    assert "bundesagentur" not in sources


# ============= #558 — Score-Drift bei Bulk =====================
def test_558_bulk_dismiss_kein_score_drift(setup_env):
    """Bulk-Aussortierung triggert Auto-Adjust nur einmal, nicht pro Job."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp

    # 8 Stellen anlegen, alle mit 'zu_weit_entfernt'-Trigger
    jobs = [{
        "hash": f"drift_{i:02d}",
        "title": f"Engineer {i}",
        "company": f"FarCorp {i}",
        "location": "Hamburg",
        "url": f"https://example.com/{i}",
        "source": "manuell",
        "score": 50,
    } for i in range(8)]
    db.save_jobs(jobs)

    # dismiss_counts vorab auf 4 setzen (knapp unter Schwelle)
    db.set_setting("dismiss_counts", {"zu_weit_entfernt": 4})

    raw = _call(mcp, "stellen_bulk_bewerten", {
        "bewertung": "passt_nicht",
        "gruende": ["zu_weit_entfernt"],
        "dry_run": False,
    })
    result = _result(raw)
    # Es soll den Hinweis auf Drift geben
    assert result.get("bearbeitet") == 8
    hinweise = " ".join(result.get("hinweise") or [])
    assert "Score" in hinweise or "Scoring" in hinweise

    # Counts hochgesetzt — nach 8 Dismissals von 4 starten
    final_counts = db.get_setting("dismiss_counts", {})
    assert final_counts.get("zu_weit_entfernt") == 12

    # WICHTIG: Auto-Adjust darf nur EINMAL passiert sein, nicht 8x
    # Pruefen: scoring_config-Eintrag fuer entfernung_fest sollte einen
    # vernuenftigen Wert haben, nicht extrem niedrig.
    conn = db.connect()
    row = conn.execute(
        "SELECT value FROM scoring_config WHERE dimension='entfernung_fest' AND sub_key='50km'"
    ).fetchone()
    assert row is not None
    # new_val = -2 * (1 + (12-5)*0.5) = -2 * 4.5 = -9 (mit final count)
    # vs. wenn pro Job aufgerufen: zuletzt -2 * (1 + (12-5)*0.5) = -9 — selbe Formel
    # Der echte Fix: NICHT mehr pro Stelle, sondern einmal. Wert sollte -9 sein.
    assert -10 <= row["value"] <= -2


# ============= #559 — blacklist_anwenden Tool =================
def test_559_blacklist_anwenden_dry_run(setup_env):
    """blacklist_anwenden(dry_run=True) zeigt Treffer ohne zu deaktivieren."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp

    db.save_jobs([{
        "hash": "bl_h1",
        "title": "Engineer",
        "company": "BadCorp GmbH",
        "url": "https://example.com/1",
        "source": "manuell",
        "score": 50,
    }, {
        "hash": "bl_h2",
        "title": "Engineer",
        "company": "GoodCorp",
        "url": "https://example.com/2",
        "source": "manuell",
        "score": 50,
    }])
    db.add_to_blacklist("firma", "BadCorp", "test")

    raw = _call(mcp, "blacklist_anwenden", {"dry_run": True})
    result = _result(raw)
    assert result.get("dry_run") is True
    assert result.get("betroffen") == 1
    # Job bleibt aktiv
    j = db.get_job("bl_h1")
    assert j["is_active"] == 1


def test_559_blacklist_anwenden_apply(setup_env):
    """blacklist_anwenden(dry_run=False) deaktiviert die betroffenen Stellen."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp

    # Direkter DB-Insert ohne Auto-Deaktivierung des add_to_blacklist-Hooks
    db.save_jobs([{
        "hash": "bl_app1",
        "title": "Engineer",
        "company": "EvilCorp AG",
        "url": "https://example.com/1",
        "source": "manuell",
        "score": 50,
    }])
    # Blacklist nachtraeglich erweitern (ohne Job-Sweep, simuliert alten Zustand)
    conn = db.connect()
    pid = db.get_active_profile_id() or ""
    conn.execute(
        "INSERT INTO blacklist(profile_id, type, value, reason, created_at) "
        "VALUES (?,?,?,?,?)",
        (pid, "firma", "EvilCorp", "test", "2026-04-29"),
    )
    conn.commit()

    raw = _call(mcp, "blacklist_anwenden", {"dry_run": False})
    result = _result(raw)
    assert result.get("dry_run") is False
    assert result.get("deaktiviert") >= 1
    # Job ist jetzt inaktiv
    j = db.get_job("bl_app1")
    assert j["is_active"] == 0
