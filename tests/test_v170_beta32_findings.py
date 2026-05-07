"""Tests fuer v1.7.0-beta.32 — #588 Stellenbeschreibung-Trennung +
#564 Portal-spezifische Such-Profile."""
import os
import asyncio
import logging
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta32_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


# ============= #588 Stellenbeschreibung-Trennung ===============

def test_bewerbung_erstellen_speichert_description_snapshot(setup_env):
    db = setup_env
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.bewerbungen import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    out = _call(mcp, "bewerbung_erstellen", {
        "title": "PLM-Architekt",
        "company": "ACME",
        "stellenbeschreibung": "Originaltext der Stellenanzeige.",
        "notes": "Recherche-Notizen mit Vermittler-Kontext",
    })
    assert "id" in out or out.get("status")  # Anlage erfolgreich
    aid = out.get("id") or out.get("bewerbung_id")
    if not aid:
        # Fallback: alle Bewerbungen holen
        apps = db.get_applications()
        assert len(apps) == 1
        aid = apps[0]["id"]
    app = db.get_application(aid)
    # description_snapshot soll genau den Originaltext halten
    assert app.get("description_snapshot") == "Originaltext der Stellenanzeige."
    # notes bleibt separat
    assert app.get("notes") == "Recherche-Notizen mit Vermittler-Kontext"


def test_bewerbung_erstellen_keine_notes_in_jobs_description(setup_env):
    """Vorher landete `notes` als Fallback in jobs.description. Das ist
    der Wurzelfehler aus #588 — verschmutzt downstream alle Tools."""
    db = setup_env
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.bewerbungen import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    out = _call(mcp, "bewerbung_erstellen", {
        "title": "PLM",
        "company": "Phoenix Contact",
        "notes": "Vermittler PBCN, Endkunde-Kandidaten Benteler/CLAAS",
        # KEIN stellenbeschreibung-Parameter
    })
    apps = db.get_applications()
    aid = apps[0]["id"]
    app = db.get_application(aid)
    job_hash = app.get("job_hash")
    assert job_hash
    job = db.get_job(job_hash)
    # description darf NICHT die Notizen enthalten
    assert "Vermittler" not in (job.get("description") or "")
    assert "Endkunde" not in (job.get("description") or "")
    assert (job.get("description") or "") == ""


def test_bewerbung_bearbeiten_stellenbeschreibung_original(setup_env):
    db = setup_env
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.bewerbungen import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    _call(mcp, "bewerbung_erstellen", {
        "title": "X", "company": "Y",
    })
    apps = db.get_applications()
    aid = apps[0]["id"]
    res = _call(mcp, "bewerbung_bearbeiten", {
        "bewerbung_id": aid,
        "stellenbeschreibung_original": "Wir suchen einen Senior PLM-Architekten...",
    })
    assert "geänderte_felder" in res or res.get("status") == "aktualisiert"
    app = db.get_application(aid)
    assert "Senior PLM-Architekten" in (app.get("description_snapshot") or "")
    assert app.get("snapshot_date")


def test_get_application_uses_snapshot_first(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    # Bewerbung mit description_snapshot = Snapshot
    # + verlinktem Job mit eigener description (sollte NICHT verwendet werden)
    conn.execute("INSERT INTO jobs (hash, profile_id, title, company, "
                 "description, is_active, found_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (f"{pid}:j1", pid, "T", "C",
                  "MUELL-DESCRIPTION-DIE-NICHT-VERWENDET-WERDEN-DARF", 1,
                  "2026-05-01"))
    conn.execute("INSERT INTO applications (id, profile_id, title, company, "
                 "job_hash, status, applied_at, created_at, updated_at, "
                 "description_snapshot, snapshot_date) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 ("app1", pid, "T", "C", f"{pid}:j1", "beworben",
                  "2026-05-02", "2026-05-02", "2026-05-02",
                  "ORIGINAL-WORTLAUT-DER-STELLENANZEIGE", "2026-05-02"))
    conn.commit()
    app = db.get_application("app1")
    assert app["stellenbeschreibung"] == "ORIGINAL-WORTLAUT-DER-STELLENANZEIGE"
    assert app["stellenbeschreibung_quelle"] == "snapshot"


def test_get_application_falls_back_to_job_description(setup_env):
    """Alte Bewerbungen (vor v1.7.0-beta.32) haben kein
    description_snapshot. Fallback auf jobs.description muss greifen."""
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute("INSERT INTO jobs (hash, profile_id, title, company, "
                 "description, is_active, found_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (f"{pid}:j2", pid, "T", "C", "Alte job-Beschreibung", 1,
                  "2026-05-01"))
    conn.execute("INSERT INTO applications (id, profile_id, title, company, "
                 "job_hash, status, applied_at, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 ("app2", pid, "T", "C", f"{pid}:j2", "beworben",
                  "2026-05-02", "2026-05-02", "2026-05-02"))
    conn.commit()
    app = db.get_application("app2")
    assert app["stellenbeschreibung"] == "Alte job-Beschreibung"
    assert "fallback" in (app.get("stellenbeschreibung_quelle") or "").lower()


# ============= #564 Portal-Such-Profile ===============

def test_portal_search_profile_default_linkedin(setup_env):
    """Beim ersten Lesen wird das LinkedIn-Profil mit den #564-Lessons
    initialisiert."""
    db = setup_env
    p = db.get_portal_search_profile("linkedin")
    assert p["portal"] == "linkedin"
    primaer_keywords = [s["keywords"] for s in p["primaere_suchen"]]
    assert "PDM" in primaer_keywords
    assert "PLM Berater" in primaer_keywords
    assert "Product Lifecycle Management" in primaer_keywords
    nicht_werte = [n["wert"] for n in p["nicht_verwenden"]]
    assert "PLM Architect" in nicht_werte
    assert "PRO.FILE" in nicht_werte


def test_portal_search_profile_default_other_portal_empty(setup_env):
    db = setup_env
    p = db.get_portal_search_profile("xing")
    assert p["portal"] == "xing"
    assert p["primaere_suchen"] == []


def test_portal_search_profile_update(setup_env):
    db = setup_env
    db.get_portal_search_profile("stepstone")  # init
    out = db.update_portal_search_profile(
        "stepstone",
        primaere_suchen=[{"keywords": "PLM Berater"}],
        notizen="Erstes Test-Profil",
    )
    assert out["primaere_suchen"][0]["keywords"] == "PLM Berater"
    assert out["notizen"] == "Erstes Test-Profil"


def test_mcp_tool_suchprofil_lesen(setup_env):
    db = setup_env
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.suche import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    out = _call(mcp, "suchprofil_lesen", {"portal": "linkedin"})
    assert out["portal"] == "linkedin"
    assert any(s["keywords"] == "PDM" for s in out["primaere_suchen"])


def test_mcp_tool_suchprofil_aktualisieren(setup_env):
    db = setup_env
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.suche import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    out = _call(mcp, "suchprofil_aktualisieren", {
        "portal": "xing",
        "primaere_suchen": [{"keywords": "PLM Manager"}],
        "notizen": "XING-Lessons folgen.",
    })
    assert out["notizen"] == "XING-Lessons folgen."


def test_mcp_tool_suchprofile_auflisten(setup_env):
    db = setup_env
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.suche import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    db.get_portal_search_profile("linkedin")
    db.get_portal_search_profile("xing")
    out = _call(mcp, "suchprofile_auflisten", {})
    assert out["anzahl"] == 2
    portals = {p["portal"] for p in out["profile"]}
    assert "linkedin" in portals
    assert "xing" in portals


# ============= Schema-Migration ===============

def test_schema_v39_table_exists(setup_env):
    db = setup_env
    conn = db.connect()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "portal_search_profiles" in tables
