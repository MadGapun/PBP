"""Tests fuer v1.7.17 — #906: Quellen-Aktivierung ohne Wahrheit.

Befund 17.08.: 'deprecated' verdeckte erreichbare APIs (personio,
himalayas, ferchau antworteten HTTP 200, standen aber als tot da — ein
sich selbst bestaetigender Zustand, weil deaktivierte Quellen nie wieder
laufen); die Freelance-Schiene war komplett aus, ohne dass es jemand
sagte; Chrome-Quellen sagten nicht, dass ein Konto noetig ist.
"""
import importlib
import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1717_906_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


# ------------------------------------------------------- Zugriffsart

def test_906_chrome_quellen_sind_browser_login():
    from bewerbungs_assistent.job_scraper import zugriffsart_von
    for q in ("linkedin", "xing", "stepstone", "indeed", "monster",
              "google_jobs"):
        assert zugriffsart_von(q) == "browser_login", q


def test_906_api_quellen_bleiben_api():
    from bewerbungs_assistent.job_scraper import zugriffsart_von
    for q in ("bundesagentur", "hays", "arbeitnow", "remotive"):
        assert zugriffsart_von(q) == "api", q


def test_906_browser_login_hat_konto_url_und_hinweis():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    for q in ("linkedin", "xing", "google_jobs"):
        meta = SOURCE_REGISTRY[q]
        assert meta.get("konto_url"), q
        assert meta.get("login_hinweis"), q


def test_906_source_rows_tragen_zugriffsart():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services.search_service import build_source_rows
    rows = {r["key"]: r for r in build_source_rows(SOURCE_REGISTRY, ["xing"])}
    assert rows["xing"]["zugriffsart"] == "browser_login"
    assert rows["xing"]["konto_url"]
    assert rows["bundesagentur"]["zugriffsart"] == "api"


# ------------------------------------- Deaktivierung nachvollziehbar

def test_906_auto_deaktivierung_setzt_grund_und_datum(setup_env):
    db, _ = setup_env
    res = None
    for _ in range(db.SILENT_AUTO_DEACTIVATE_THRESHOLD):
        res = db.update_scraper_health("demoquelle", "ok", count=0,
                                       time_s=5.0)
    assert res["auto_deactivated"] is True
    row = db.connect().execute(
        "SELECT * FROM scraper_health WHERE scraper_name='demoquelle'"
    ).fetchone()
    assert row["is_active"] == 0
    assert row["deaktiviert_am"], "Zeitpunkt muss persistiert sein (#906)"
    assert "stille Laeufe" in (row["deaktiviert_grund"] or "")


def test_906_erfolg_loescht_deaktivierungs_metadaten(setup_env):
    db, _ = setup_env
    for _ in range(db.SILENT_AUTO_DEACTIVATE_THRESHOLD):
        db.update_scraper_health("demoquelle2", "ok", count=0, time_s=5.0)
    db.update_scraper_health("demoquelle2", "ok", count=7, time_s=5.0)
    row = db.connect().execute(
        "SELECT * FROM scraper_health WHERE scraper_name='demoquelle2'"
    ).fetchone()
    assert row["is_active"] == 1
    assert row["deaktiviert_am"] is None
    assert row["deaktiviert_grund"] is None


# --------------------------------------------- Probe bricht den Zirkel

def test_906_probe_meldet_erreichbare_deaktivierte_als_pruefen(setup_env,
                                                              monkeypatch):
    """AK 7: eine als tot markierte, aber per Probe erreichbare Quelle
    wird als 'pruefen' gemeldet — nicht als tot."""
    db, _ = setup_env
    import bewerbungs_assistent.server as srv
    importlib.reload(srv)
    from bewerbungs_assistent import server as srv2
    for _ in range(db.SILENT_AUTO_DEACTIVATE_THRESHOLD):
        srv2.db.update_scraper_health("personio", "ok", count=0, time_s=5.0)

    import bewerbungs_assistent.job_scraper.health as health_mod
    monkeypatch.setattr(
        health_mod, "check_source",
        lambda s: {"source": s, "reachable": True, "http_status": 200,
                   "latency_ms": 42})

    import asyncio

    def _call(name, args):
        async def _run():
            tool = await srv2.mcp.get_tool(name)
            res = await tool.run(args)
            return res.structured_content if hasattr(
                res, "structured_content") else res
        raw = asyncio.run(_run())
        if isinstance(raw, tuple):
            raw = raw[1] if len(raw) > 1 else raw[0]
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        return raw

    res = _call("quellen_health_check", {"quellen": ["personio"],
                                         "parallel": False})
    wieder = res.get("wieder_erreichbar") or []
    assert any(w["quelle"] == "personio" for w in wieder), res
    row = srv2.db.connect().execute(
        "SELECT * FROM scraper_health WHERE scraper_name='personio'"
    ).fetchone()
    assert "pruefen" in (row["last_status_detail"] or ""), \
        dict(row)
    assert row["letzte_probe_am"]
    assert row["letzte_probe_status"] == "HTTP 200"


# ----------------------------------------------- totes Suchkriterium

def test_906_stellentyp_quellen_mapping():
    from bewerbungs_assistent.job_scraper import STELLENTYP_QUELLEN
    assert "freelance" in STELLENTYP_QUELLEN
    assert {"freelance_de", "freelancermap", "gulp",
            "solcom"} <= STELLENTYP_QUELLEN["freelance"]


# ------------------------------------------------- Frontend-Invarianten

def test_906_frontend_dialog_und_badges():
    src = (Path(__file__).resolve().parents[1] / "frontend" / "src" /
           "components" / "SourceSelectionList.jsx").read_text(
        encoding="utf-8")
    assert 'source.zugriffsart === "browser_login"' in src, \
        "browser_login braucht den Bestaetigungs-Dialog (#906 AK 2)"
    assert "window.confirm" in src
    assert "Wartet auf dich" in src, \
        "aktive Browser-Quellen duerfen nicht wie Auto-Quellen aussehen"
    assert "konto_url" in src
