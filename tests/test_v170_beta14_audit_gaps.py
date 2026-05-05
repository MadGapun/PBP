"""Tests fuer die in beta.14 geschlossenen Audit-Luecken.

Hintergrund: rc.1 wurde verfrueht released ohne dass die Akzeptanzkriterien
der „schon implementiert"-Issues sauber gegen die Realitaet abgeglichen
wurden. Diese Datei deckt die Luecken-Schluss-Aenderungen aus beta.14:

- #571 Stufe 1 — Skill-Filter im Profil ist Frontend-only und wird
  nicht hier getestet (statisch in ProfilePage.jsx ueber Snapshot-Pruefung
  des Quellcodes).
- #573 — google_jobs_url liefert jetzt extraction_js + ergaenzten Hinweis.
- #583 — App.jsx Modal-Hinweistext wurde aktualisiert (von „kommt in
  naechster Beta" auf „in Einstellungen → Lokale KI").
- #505 — README enthaelt Typed-IDs-Sektion.
"""
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ============= #573 google_jobs_url ===============

def test_573_google_jobs_url_returns_extraction_js():
    from bewerbungs_assistent.tools.jobs import register as register_job_tools
    # Tool-Funktion direkt aufrufen ueber den FastMCP-Decorator-Trick:
    # register_job_tools registriert auf einer FastMCP-Instanz; wir
    # fischen die nackte Funktion aus dem Module-namespace.
    import bewerbungs_assistent.tools.jobs as jobs_mod
    src = Path(jobs_mod.__file__).read_text(encoding="utf-8")
    # Pruefen dass extraction_js drin ist und einen sinnvollen Selektor enthaelt
    assert 'extraction_js' in src
    assert 'querySelectorAll' in src
    assert 'data-ved' in src or 'role="listitem"' in src
    # Hinweis-Text reflektiert die DOM-Strategie
    assert 'javascript_tool' in src
    assert 'Rohtext' in src or 'rohtext' in src.lower()


def test_573_google_jobs_url_e2e_via_fastmcp():
    """End-to-end: Tool registrieren, aufrufen, Result-Shape pruefen."""
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.jobs import register as register_job_tools
    # Minimaler db-Stub
    class _DBStub:
        def get_search_criteria(self): return {}
        def get_active_jobs(self): return []
        def get_active_profile_id(self): return "p1"
    import logging
    mcp = FastMCP("test")
    register_job_tools(mcp, _DBStub(), logging.getLogger("test"))
    import asyncio
    async def _run():
        tool = await mcp.get_tool("google_jobs_url")
        res = await tool.run({"keyword": "PLM Manager", "ort": "Hamburg"})
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    out = asyncio.run(_run())
    # FastMCP umschlaegt manchmal in {"result": ...}
    payload = out.get("result", out) if isinstance(out, dict) else out
    assert "url" in payload
    assert "extraction_js" in payload
    assert payload["extraction_js"].lstrip().startswith("(()")
    assert "google.com" in payload["url"]


# ============= #583 App.jsx Modal-Text aktualisiert ===============

def test_583_modal_hint_no_longer_promises_future_beta():
    app_jsx = (PROJECT_ROOT / "frontend" / "src" / "App.jsx").read_text(
        encoding="utf-8"
    )
    # Der alte Text war irrefuehrend — er sollte weg sein
    assert "Einrichtung der lokalen KI kommt" not in app_jsx, (
        "Veralteter Modal-Hinweistext findet sich noch in App.jsx"
    )
    assert "in der naechsten Beta-Version" not in app_jsx
    # Neuer Hinweis verweist auf den existierenden Setup-Wizard
    assert "Einstellungen" in app_jsx
    assert "Lokale KI" in app_jsx


# ============= #505 README enthaelt ID-Doku ===============

def test_505_readme_documents_typed_ids():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    # Sektion vorhanden
    assert "Typed IDs" in readme or "Typisierte IDs" in readme
    # Alle 5 Praefixe dokumentiert
    for prefix in ("APP-", "JOB-", "DOC-", "MTG-", "CON-"):
        assert prefix in readme, f"Praefix {prefix} fehlt in README"
    # Nicht-breaking-Hinweis (nackte IDs gehen auch noch)
    assert "Nicht-breaking" in readme or "nicht-breaking" in readme.lower()


# ============= #571 Stufe 1 Skill-Filter im Profil ===============

def test_571_stage1_skill_filter_present_in_profile_page():
    profile_jsx = (
        PROJECT_ROOT / "frontend" / "src" / "pages" / "ProfilePage.jsx"
    ).read_text(encoding="utf-8")
    # State + Input + Filter-Logik vorhanden
    assert "skillFilter" in profile_jsx
    assert "setSkillFilter" in profile_jsx
    assert 'placeholder="Skill suchen' in profile_jsx
    # Filter wirkt auf profile.skills
    assert "filteredSkills" in profile_jsx
