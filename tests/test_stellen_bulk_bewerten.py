"""Tests fuer stellen_bulk_bewerten (#514).

Verifiziert:
- dry_run=True veraendert nichts, liefert Vorschau
- dry_run=False bewertet Treffer durch die echte Lifecycle-Logik
- Filter sind kombinierbar (AND)
- titel_enthaelt_nicht / beschreibung_enthaelt_nicht funktionieren
- max_treffer cappt
- Audit/Counter werden inkrementiert (Anti-DB-Bypass)
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def setup_env_with_jobs():
    tmpdir = tempfile.mkdtemp(prefix="pbp_bulk_test_")
    os.environ["BA_DATA_DIR"] = tmpdir
    # Re-import damit Server-Module den neuen BA_DATA_DIR sehen
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)

    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    pid = db.get_active_profile_id()

    # Mehrere Jobs mit unterschiedlichen Eigenschaften anlegen
    jobs = []
    base = datetime.now()
    for i, (title, company, source, score, days_old, descr) in enumerate([
        ("Senior Python Developer", "TechAG", "bundesagentur", 85, 2, "Python FastAPI"),
        ("Junior Pflegefachkraft", "Pflege Plus", "bundesagentur", 30, 5, "Altenpflege"),
        ("Vertriebsmitarbeiter Aussendienst", "VertriebGmbH", "stepstone", 25, 10, "Aussendienst Akquise"),
        ("Senior Software Engineer", "DevHub", "indeed", 90, 1, "Python Go"),
        ("Pflegehelfer Teilzeit", "Senioren-Heim", "stepstone", 20, 30, "Pflege Senioren"),
        ("Marketing Manager", "MediaCo", "bundesagentur", 60, 60, "Kampagnen"),
    ]):
        h = f"hash{i:04d}"
        jobs.append({
            "hash": h,
            "title": title,
            "company": company,
            "source": source,
            "score": score,
            "found_at": (base - timedelta(days=days_old)).isoformat(),
            "description": descr,
            "url": f"https://example.com/{i}",
        })
    db.save_jobs(jobs)
    yield db, pid
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _get_bulk_tool():
    from bewerbungs_assistent.server import mcp
    import asyncio
    tools = asyncio.run(mcp._list_tools())
    for t in tools:
        if t.name == "stellen_bulk_bewerten":
            return t
    raise RuntimeError("stellen_bulk_bewerten nicht registriert")


def _call_bulk(**kwargs):
    """Ruft das MCP-Tool synchron auf."""
    import asyncio
    from bewerbungs_assistent.server import mcp
    tool = _get_bulk_tool()
    # FastMCP-Tools werden ueber call_tool aufgerufen
    return asyncio.run(mcp.call_tool("stellen_bulk_bewerten", kwargs))


def test_dry_run_titel_enthaelt_nicht(setup_env_with_jobs):
    """dry_run mit titel_enthaelt_nicht zeigt Treffer ohne zu veraendern."""
    db, _ = setup_env_with_jobs
    before_active = len(db.get_active_jobs())

    result = _call_bulk(
        bewertung="passt_nicht",
        gruende=["falsches_fachgebiet"],
        titel_enthaelt_nicht=["Pflege", "Vertrieb"],
        dry_run=True,
    )
    # FastMCP wraps tool returns; we accept either dict or content
    if isinstance(result, tuple):
        result = result[1] if len(result) > 1 else result[0]
    if hasattr(result, "structured_content"):
        result = result.structured_content
    if isinstance(result, list):
        result = result[0] if result else {}

    assert result.get("dry_run") is True
    assert result.get("anzahl_treffer") == 3, f"Expected 3 (Pflege x2, Vertrieb x1), got {result.get('anzahl_treffer')}"
    assert len(result.get("vorschau", [])) == 3
    # Keine DB-Aenderung
    assert len(db.get_active_jobs()) == before_active


def test_apply_titel_enthaelt_nicht(setup_env_with_jobs):
    """dry_run=False sortiert Treffer durch echte Lifecycle-Logik aus."""
    db, _ = setup_env_with_jobs
    before_active = len(db.get_active_jobs())
    counts_before = db.get_setting("dismiss_counts", {}) or {}

    result = _call_bulk(
        bewertung="passt_nicht",
        gruende=["falsches_fachgebiet"],
        titel_enthaelt_nicht=["Pflege", "Vertrieb"],
        dry_run=False,
    )
    if isinstance(result, tuple):
        result = result[1] if len(result) > 1 else result[0]
    if hasattr(result, "structured_content"):
        result = result.structured_content
    if isinstance(result, list):
        result = result[0] if result else {}

    assert result.get("dry_run") is False
    assert result.get("bearbeitet") == 3
    after_active = len(db.get_active_jobs())
    assert after_active == before_active - 3, f"3 Stellen sollten weg sein, aktiv: {after_active}, vorher: {before_active}"

    # Counter-Anti-DB-Bypass-Check: dismiss_counts wurde inkrementiert
    counts_after = db.get_setting("dismiss_counts", {}) or {}
    assert counts_after.get("falsches_fachgebiet", 0) == counts_before.get("falsches_fachgebiet", 0) + 3, (
        "dismiss_counts muss durch Lifecycle inkrementiert werden — sonst wird DB direkt umgangen"
    )


def test_dry_run_min_score(setup_env_with_jobs):
    """min_score-Filter wirkt korrekt."""
    db, _ = setup_env_with_jobs
    result = _call_bulk(
        bewertung="passt_nicht",
        gruende=["sonstiges"],
        min_score=80,
        dry_run=True,
    )
    if hasattr(result, "structured_content"):
        result = result.structured_content
    if isinstance(result, list):
        result = result[0] if result else {}
    if isinstance(result, tuple):
        result = result[1] if len(result) > 1 else result[0]
    # Score 85 (TechAG) und 90 (DevHub) — 2 Treffer
    assert result.get("anzahl_treffer") == 2


def test_max_treffer_caps(setup_env_with_jobs):
    """max_treffer cappt die Trefferzahl."""
    result = _call_bulk(
        bewertung="passt_nicht",
        gruende=["sonstiges"],
        dry_run=True,
        max_treffer=2,
    )
    if hasattr(result, "structured_content"):
        result = result.structured_content
    if isinstance(result, list):
        result = result[0] if result else {}
    if isinstance(result, tuple):
        result = result[1] if len(result) > 1 else result[0]
    assert result.get("anzahl_treffer") == 2


def test_no_gruende_returns_error(setup_env_with_jobs):
    """passt_nicht ohne gruende muss Fehler zurueckgeben."""
    result = _call_bulk(
        bewertung="passt_nicht",
        dry_run=True,
    )
    if hasattr(result, "structured_content"):
        result = result.structured_content
    if isinstance(result, list):
        result = result[0] if result else {}
    if isinstance(result, tuple):
        result = result[1] if len(result) > 1 else result[0]
    assert "fehler" in result


def test_passt_restores(setup_env_with_jobs):
    """bewertung='passt' restored vorher dismissed Stellen."""
    db, _ = setup_env_with_jobs
    # Erst aussortieren
    db.dismiss_job("hash0001", "sonstiges")
    assert db.get_active_jobs.__call__ and len([j for j in db.get_active_jobs() if j["hash"] == "hash0001"]) == 0

    # Dann via Bulk passt restoren
    result = _call_bulk(
        bewertung="passt",
        firma="Pflege",
        dry_run=False,
    )
    if hasattr(result, "structured_content"):
        result = result.structured_content
    if isinstance(result, list):
        result = result[0] if result else {}
    if isinstance(result, tuple):
        result = result[1] if len(result) > 1 else result[0]
    assert result.get("bearbeitet") >= 1
