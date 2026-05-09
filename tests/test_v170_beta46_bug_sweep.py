"""Tests fuer v1.7.0-beta.46 — Bug-Sweep (#604, #618, #602, #619, #610, #603, #615)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta46_")
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


# ============= #604: 'intern' Synonym entfernt ===============

def test_604_intern_no_longer_in_praktikum_synonym():
    from bewerbungs_assistent.job_scraper import _SYNONYM_MAP
    assert "intern" not in _SYNONYM_MAP["praktikum"]
    assert "intern" not in _SYNONYM_MAP["praktikant"]
    # internship bleibt — englischer eindeutiger Begriff
    assert "internship" in _SYNONYM_MAP["praktikum"]


def test_604_internationalen_kunden_no_false_positive():
    """Stellen mit 'internationalen Kunden' duerfen nicht als
    Praktikum aussortiert werden."""
    from bewerbungs_assistent.job_scraper import calculate_score
    job = {
        "title": "Senior PLM Solution Architect",
        "description": "Sie arbeiten mit internationalen Kunden in einer "
                       "internationalen Umgebung. PLM-Erfahrung mit Aras "
                       "und Teamcenter erforderlich. " * 3,
    }
    criteria = {
        "keywords_muss": ["plm"],
        "keywords_ausschluss": ["praktikum"],
        "gewichtung": {"muss": 2},
    }
    score = calculate_score(job, criteria)
    assert score > 0, "Score wurde durch falschen 'intern'-Match auf 0 gesetzt"


# ============= #618: stelle_bearbeiten kurzer Hash ===============

def test_618_stelle_bearbeiten_with_short_hash(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    full_hash = f"{pid}:1ee365357e6f"
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, is_active, source) "
        "VALUES (?,?,?,?,?,?)",
        (full_hash, pid, "Test", "ACME", 1, "manuell")
    )
    conn.commit()

    # Kurz-Hash (8 Zeichen) sollte funktionieren
    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run(args):
        tool = await mcp.get_tool("stelle_bearbeiten")
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run({"job_hash": "1ee36535", "firma": "Neue Firma"}))
    # Nicht 'fehler', sondern erfolgreiche Aktualisierung
    assert "fehler" not in out, f"Kurz-Hash wurde nicht akzeptiert: {out}"


# ============= #602: applied_at Default ===============

def test_602_applied_at_default_to_today(setup_env):
    """Inbound-Recruiter-Anfrage ohne explizites applied_at -> heute."""
    from datetime import datetime
    db = setup_env
    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.bewerbungen import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("bewerbung_erstellen")
        res = await tool.run({
            "title": "Senior PLM",
            "company": "ACME",
            "url": "https://example.com",
            "status": "beworben",
            # KEIN applied_at uebergeben
        })
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run())
    today = datetime.now().isoformat()[:10]
    # Bewerbung sollte applied_at=heute haben
    apps = db.get_applications()
    assert len(apps) >= 1
    assert apps[0]["applied_at"] == today, (
        f"applied_at nicht gesetzt — Inbound-Bug. Got: {apps[0].get('applied_at')!r}"
    )


# ============= #619: PDF Unicode-Fallback ===============

def test_619_pdf_safe_replaces_arrows():
    """safe()-Helper im PDF-Generator ersetzt Unicode-Pfeile."""
    # Wir ruefen die safe()-Logik indirekt: das Modul muss geladen werden
    # koennen + die Helvetica-Replacement-Map enthaelt die Pfeile.
    from bewerbungs_assistent import export
    src = (PROJECT_ROOT / "src" / "bewerbungs_assistent" / "export.py").read_text(encoding="utf-8")
    # Pruefe dass die Replace-Map den Pfeil enthaelt
    assert '"\\u2192"' in src or '"→"' in src, "Pfeil-Replacement fehlt"
    assert '"->"' in src, "ASCII-Fallback '->' fehlt"


def test_619_safe_strips_unknown_unicode():
    """Letzter Fallback: latin-1 errors='replace' fuer alles unbekannte."""
    src = (PROJECT_ROOT / "src" / "bewerbungs_assistent" / "export.py").read_text(encoding="utf-8")
    assert 'errors="replace"' in src, "latin-1-replace-Fallback fehlt"


# ============= #610: stellen_auto_aussortieren uniformes Schema ===============

def test_610_uniform_output_schema_on_error(setup_env):
    """Auch im Fehler-Fall (Ollama nicht da) muss ein uniformes Schema kommen."""
    db = setup_env
    import asyncio, logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("stellen_auto_aussortieren")
        res = await tool.run({"max_stellen": 1, "dry_run": True})
        return res.structured_content if hasattr(res, "structured_content") else res

    # Ollama ist im Test nicht aktiv — sollte 'fehler'-Status zurueckgeben,
    # aber mit allen Schema-Feldern.
    out = asyncio.run(_run())
    # Pflicht-Felder die das Schema verlangen
    for key in ("status", "geprueft", "passt_nicht", "unsicher", "passt",
                "errors_count", "passt_nicht_details", "modell"):
        assert key in out, f"Schema-Feld {key!r} fehlt im Output: {out}"


# ============= #603: PBP-Notizen-Trenner im Score ===============

def test_603_strip_pbp_notes_separator():
    from bewerbungs_assistent.job_scraper import _strip_pbp_notes
    text = (
        "Original-Stellentext mit PLM und Teamcenter.\n\n"
        "---\n"
        "PBP-Notiz: Hands-on-Implementierer/Konfigurator als Architekt"
    )
    cleaned = _strip_pbp_notes(text)
    assert "Hands-on" not in cleaned
    assert "PLM" in cleaned


def test_603_strip_pbp_notes_with_auffaelliges_marker():
    from bewerbungs_assistent.job_scraper import _strip_pbp_notes
    text = (
        "Senior PLM Solution Architect Position.\n"
        "## Auffaelliges:\n"
        "- Hands-on statt Strategy"
    )
    cleaned = _strip_pbp_notes(text)
    assert "Hands-on" not in cleaned


def test_603_score_ignores_pbp_notes_with_ausschluss_keyword():
    from bewerbungs_assistent.job_scraper import calculate_score
    job = {
        "title": "Senior PLM Solution Architect",
        "description": (
            "PLM-Architekt mit Teamcenter-Erfahrung gesucht. "
            "Strategische Verantwortung fuer Tooling-Auswahl. " * 5 +
            "\n\n---\n"
            "PBP-Notiz: Rolle ist eher Hands-on-Implementierer"
        ),
    }
    criteria = {
        "keywords_muss": ["plm"],
        "keywords_ausschluss": ["hands-on"],
        "gewichtung": {"muss": 2},
    }
    score = calculate_score(job, criteria)
    assert score > 0, "PBP-Notiz nach Trenner sabotiert immer noch das Scoring"


# ============= #615: kontakt_verknuepfen FK-Lookup ===============

def test_615_link_contact_clear_error_when_contact_missing(setup_env):
    db = setup_env
    with pytest.raises(ValueError, match="Kontakt nicht gefunden"):
        db.link_contact("does-not-exist", "application", "any-target")


def test_615_link_contact_clear_error_when_application_missing(setup_env):
    db = setup_env
    cid = db.add_contact({"full_name": "Test Recruiter"})
    with pytest.raises(ValueError, match="Bewerbung nicht gefunden"):
        db.link_contact(cid, "application", "does-not-exist")


def test_615_link_contact_clear_error_when_job_missing(setup_env):
    db = setup_env
    cid = db.add_contact({"full_name": "Test Recruiter"})
    with pytest.raises(ValueError, match="orphaned FK|Stelle nicht gefunden"):
        db.link_contact(cid, "job", "phantom-hash")


def test_615_link_contact_works_when_both_exist(setup_env):
    db = setup_env
    cid = db.add_contact({"full_name": "Test Recruiter"})
    pid = db.get_active_profile_id()
    aid = db.add_application({"title": "X", "company": "Y", "status": "beworben",
                              "applied_at": "2026-05-10"})
    lid = db.link_contact(cid, "application", aid, role="hiring_manager")
    assert lid is not None
