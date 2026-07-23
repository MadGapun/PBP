"""Regression #763: URL-Qualitaet im Bestand heilen + Such-URL-Erkennung.

Hintergrund: Der Scraper-Fix aus #645 wirkte nur auf NEUE Laeufe; das
Akzeptanzkriterium AK5 (Bestands-Heilung) wurde nie umgesetzt. Zusaetzlich
erkannte `is_search_result_url` pfadbasierte Such-URLs ohne Query-Parameter
nicht — darunter ausgerechnet die Form, die PBP in handoff.py selbst baut
(`stepstone.de/jobs/{keyword_pfad}`).

WICHTIG (ehrliche Grenze): Echte Detail-URLs sind aus dem Bestand NICHT
rekonstruierbar — die Portal-IDs werden nie persistiert. Die Heilung kann
nur korrekt klassifizieren und eine gezielte SUCH-URL nachtragen.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v179_763_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
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


# ---------------------------------------------------------------- Erkennung

@pytest.mark.parametrize("url", [
    "https://www.stepstone.de/jobs/plm-manager/in-hamburg",  # PBP baut das selbst
    "https://www.stepstone.de/stellenangebote/plm",
    "https://de.indeed.com/jobs",
    "https://www.arbeitsagentur.de/jobsuche/suche",
    "https://www.xing.com/jobs",
    "https://www.stepstone.de/jobs?what=plm",
])
def test_763_pfadbasierte_such_urls_werden_erkannt(url):
    from bewerbungs_assistent.job_scraper import is_search_result_url
    assert is_search_result_url(url) is True, f"Such-URL nicht erkannt: {url}"


@pytest.mark.parametrize("url", [
    "https://www.xing.com/jobs/hamburg-plm-manager-123456",   # XING-Detail!
    "https://www.arbeitsagentur.de/jobsuche/jobdetail/12345",
    "https://www.stepstone.de/stellenangebote--PLM-Hamburg--123456-inline.html",
    "https://www.linkedin.com/jobs/view/4012345678",
    "https://de.indeed.com/viewjob?jk=abc123",
    "https://careers.nordwind-pharma.example/job/Beispielstadt-IT-Partner/12345",
])
def test_763_detail_urls_bleiben_detail(url):
    """False-Positive waere eine Regression: blockiert stellenbeschreibung_nachladen."""
    from bewerbungs_assistent.job_scraper import is_search_result_url
    assert is_search_result_url(url) is False, f"Detail-URL faelschlich als Suche: {url}"


# ---------------------------------------------------------------- Heilung

def _job(db, hash_, title, source, url, is_search_url=0, location="Hamburg"):
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, title, company, location, url, source, "
        "is_search_url, is_active, profile_id, found_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,1,?,'2026-07-01','2026-07-01')",
        (hash_, title, "Beispiel AG", location, url, source, is_search_url,
         db.get_active_profile_id()),
    )
    conn.commit()


def _flag(db, hash_):
    row = db.connect().execute(
        "SELECT url, is_search_url FROM jobs WHERE hash=?", (hash_,)).fetchone()
    return dict(row)


def test_763_reklassifiziert_unmarkierte_such_url(setup_env):
    """Altbestand: Such-URL mit is_search_url=0 wird korrekt markiert."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _job(db, "h1", "PLM Manager", "stepstone",
         "https://www.stepstone.de/jobs/plm-manager/in-hamburg", is_search_url=0)
    res = _result(_call(mcp, "stellen_urls_heilen", {"dry_run": False}))
    assert res["status"] == "ausgefuehrt"
    assert _flag(db, "h1")["is_search_url"] == 1


def test_763_gibt_nachgepflegte_detail_url_wieder_frei(setup_env):
    """Gegenrichtung: save_jobs-Guard setzte defensiv 1, jetzt ist eine echte
    Detail-URL da -> Flag zurueck auf 0, damit Nachladen wieder geht."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _job(db, "h2", "IT Business Partner", "stepstone",
         "https://careers.nordwind-pharma.example/job/Beispielstadt-IT-Partner/12345",
         is_search_url=1)
    _call(mcp, "stellen_urls_heilen", {"dry_run": False})
    assert _flag(db, "h2")["is_search_url"] == 0


def test_763_leere_url_bekommt_such_url_und_flag(setup_env):
    """Leere URL + Handoff-Template -> Such-URL, IMMER als Such-URL markiert."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _job(db, "h3", "PLM Projektleiter", "xing", "", is_search_url=0)
    _call(mcp, "stellen_urls_heilen", {"dry_run": False})
    nach = _flag(db, "h3")
    assert nach["url"], "Such-URL haette nachgetragen werden muessen"
    assert nach["is_search_url"] == 1, "muss ehrlich als Such-URL markiert sein"


def test_763_ohne_template_nicht_heilbar_statt_stillem_leerfeld(setup_env):
    """Quelle ohne Handoff-Template wird transparent als nicht heilbar gemeldet."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _job(db, "h4", "Consultant", "bundesagentur", "", is_search_url=0)
    res = _result(_call(mcp, "stellen_urls_heilen", {"dry_run": True}))
    assert res["count_nicht_heilbar"] >= 1
    assert any(e["hash"] == "h4" for e in res["nicht_heilbar"])


def test_763_dry_run_schreibt_nicht(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _job(db, "h5", "PLM Manager", "stepstone",
         "https://www.stepstone.de/jobs/plm-manager/in-hamburg", is_search_url=0)
    res = _result(_call(mcp, "stellen_urls_heilen", {}))  # Default dry_run=True
    assert res["status"] == "vorschau"
    assert res["count_applied"] == 0
    assert _flag(db, "h5")["is_search_url"] == 0, "dry_run darf nicht schreiben"


def test_763_idempotent(setup_env):
    """Zweiter Lauf findet nichts mehr — Kernforderung des Issues."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _job(db, "h6", "PLM Manager", "stepstone",
         "https://www.stepstone.de/jobs/plm-manager/in-hamburg", is_search_url=0)
    _job(db, "h7", "PLM Architekt", "xing", "", is_search_url=0)
    erst = _result(_call(mcp, "stellen_urls_heilen", {"dry_run": False}))
    assert erst["count_applied"] >= 2
    zweit = _result(_call(mcp, "stellen_urls_heilen", {"dry_run": False}))
    assert zweit["count_changed"] == 0, f"nicht idempotent: {zweit}"


def test_763_akzeptanz_nie_beides_leer_und_unmarkiert(setup_env):
    """AK aus #763: nach der Heilung nie 'URL leer UND is_search_url=0',
    sofern die Quelle ueberhaupt heilbar ist."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    for i, src in enumerate(["stepstone", "xing", "linkedin", "indeed"]):
        _job(db, f"ak{i}", "PLM Manager", src, "", is_search_url=0)
    _call(mcp, "stellen_urls_heilen", {"dry_run": False})
    rows = db.connect().execute(
        "SELECT hash, url, is_search_url FROM jobs WHERE hash LIKE 'ak%'").fetchall()
    for r in rows:
        assert (r["url"] or "") or r["is_search_url"], (
            f"{r['hash']}: URL leer UND nicht als Such-URL markiert"
        )
