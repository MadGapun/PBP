"""Tests fuer v1.7.10 — #782 (C30): Repost-Erkennung.

Praxis-Fall 24.07.2026: Eine aktive Stelle entsprach exakt einer Bewerbung
von vor 10 Monaten (abgelehnt) — erkennbar nur durch manuellen
firma_kontext-Aufruf. Bei 220 Stellen im Bestand geht das zwangslaeufig
unter. Kern: WARNUNG in stellen_anzeigen/fit_analyse/firma_kontext,
NIE automatische Aussortierung.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1710_782_")
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


def _repost_lage(db):
    """Alte Bewerbung (abgelehnt, ohne Grund) + neue aktive Stelle derselben
    Firma mit fast gleichem Titel und NEUER URL."""
    db.add_application({
        "company": "Firma L GmbH", "title": "Team Lead Master Data Management",
        "status": "abgelehnt", "applied_at": "2025-09-30",
    })
    db.save_jobs([{
        "hash": "repost1", "title": "Team Lead Master Data Management (m/w/d)",
        "company": "Firma L GmbH", "location": "Hamburg",
        "url": "https://karriere.firma-l.example/jobs/9999",
        "source": "stepstone",
        "description": "MDM Team Lead Rolle mit PLM-Bezug. " * 20,
        "employment_type": "festanstellung",
    }])


def test_782_stellen_anzeigen_warnt(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _repost_lage(db)
    res = _result(_call(mcp, "stellen_anzeigen", {}))
    stelle = next(s for s in res["stellen"] if s["id"] == "repost1"[:8])
    assert "repost_warnung" in stelle, stelle
    assert "2025-09-30" in stelle["repost_warnung"]
    assert stelle["repost_details"]["ablehnungsgrund_dokumentiert"] is False


def test_782_keine_automatische_aussortierung(setup_env):
    """Die Warnung darf die Stelle NICHT deaktivieren."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _repost_lage(db)
    _call(mcp, "stellen_anzeigen", {})
    job = db.get_job("repost1")
    assert job["is_active"] == 1, "Repost-Warnung darf nie aussortieren"


def test_782_fit_analyse_warnt(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _repost_lage(db)
    res = _result(_call(mcp, "fit_analyse", {"job_hash": "repost1"}))
    assert "repost_warnung" in res, list(res.keys())


def test_782_firma_kontext_zeigt_repost(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _repost_lage(db)
    res = _result(_call(mcp, "firma_kontext", {"firmenname": "Firma L"}))
    assert res["gefunden"] is True
    stellen = res["aktive_stellen"]
    assert stellen and "repost_warnung" in stellen[0], stellen


def test_782_andere_firma_ist_kein_repost(setup_env):
    """Gleicher Titel bei ANDERER Firma darf nicht warnen."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.add_application({
        "company": "Firma L GmbH", "title": "Team Lead MDM",
        "status": "abgelehnt", "applied_at": "2025-09-30"})
    db.save_jobs([{
        "hash": "andere1", "title": "Team Lead MDM",
        "company": "Voellig Andere AG", "location": "Hamburg",
        "url": "https://example.com/x", "source": "stepstone",
        "description": "MDM Rolle. " * 20,
        "employment_type": "festanstellung"}])
    res = _result(_call(mcp, "stellen_anzeigen", {}))
    stelle = next(s for s in res["stellen"] if s["id"] == "andere1"[:8])
    assert "repost_warnung" not in stelle


def test_782_bereits_beworben_ist_kein_repost(setup_env):
    """Die per Hash verknuepfte Bewerbung ist 'bereits_beworben', kein Repost."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.save_jobs([{
        "hash": "gleich1", "title": "PLM Manager",
        "company": "Firma M", "location": "HH",
        "url": "https://example.com/g", "source": "stepstone",
        "description": "PLM. " * 30, "employment_type": "festanstellung"}])
    voll = db.resolve_job_hash("gleich1")
    db.add_application({"company": "Firma M", "title": "PLM Manager",
                        "job_hash": voll, "status": "beworben",
                        "applied_at": "2026-06-01"})
    res = _result(_call(mcp, "stellen_anzeigen", {}))
    stelle = next(s for s in res["stellen"] if s["id"] == "gleich1"[:8])
    assert stelle.get("bereits_beworben") is True
    assert "repost_warnung" not in stelle


def test_782_rekonstruiert_kennzeichen(setup_env):
    """applied_at deutlich vor created_at -> abgeleitetes Kennzeichen."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = db.add_application({
        "company": "Alt AG", "title": "PLM Rolle",
        "status": "abgelehnt", "applied_at": "2025-09-30"})
    res = _result(_call(mcp, "bewerbung_details", {"bewerbung_id": aid}))
    assert res.get("datenqualitaet") == "rekonstruiert", res.get("datenqualitaet")

    aid2 = db.add_application({
        "company": "Frisch GmbH", "title": "X", "status": "beworben",
        "applied_at": "2026-07-24"})
    res2 = _result(_call(mcp, "bewerbung_details", {"bewerbung_id": aid2}))
    assert res2.get("datenqualitaet") != "rekonstruiert"
