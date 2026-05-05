"""Tests fuer v1.6.9 — Hash- & Datum-Hygiene.

Issues gefixt:
- #565 datetime offset-naive vs aware
- #567 Duplikat-Filter zu strikt + datetime-TypeError
- #574 Hash-Format-Inkonsistenz + dismiss_reason-Formatmix
- #570 Direkt-Upload Duplikate
- #547 Auto-Quarantaene silent_timeout
- #548 Quellen-Counter mathematisch korrekt
- #551 Fortschritts-Phase explizit
- #569 Dokumenten-Sortierung Workflow-rank
- #554 scores_neu_berechnen Tool
"""
import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v169_test_")
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


# ============= #565, #567 datetime tz-aware ===============
def test_565_find_duplicate_with_aware_found_at(setup_env):
    """find_duplicate_job crasht nicht mit tz-aware found_at."""
    from bewerbungs_assistent.duplicate_detection import find_duplicate_job
    candidates = [{
        "company": "TestCorp",
        "title": "Old Job",
        "found_at": "2026-04-01T10:00:00+00:00",  # tz-aware
        "url": "",
    }]
    # Sollte nicht crashen
    result = find_duplicate_job("TestCorp", "Old Job", "", candidates)
    assert result is not None  # Match auf Firma + Titel-Aehnlichkeit
    assert result["job"]["company"] == "TestCorp"


def test_565_find_duplicate_with_naive_found_at(setup_env):
    """find_duplicate_job tolerant gegenueber naive found_at (Legacy)."""
    from bewerbungs_assistent.duplicate_detection import find_duplicate_job
    candidates = [{
        "company": "TestCorp",
        "title": "Old Job",
        "found_at": "2026-04-01T10:00:00",  # naive
        "url": "",
    }]
    result = find_duplicate_job("TestCorp", "Old Job", "", candidates)
    assert result is not None


# ============= #574 Hash-Format Migration ===============
def test_574_hash_migration_unifies_format(setup_env):
    """Migration v31 wandelt Format-A-Eintraege auf Format-B um."""
    db, _ = setup_env
    conn = db.connect()
    pid = db.get_active_profile_id()
    # Format-A einfuegen (nackter Hash) — simuliert Legacy-Eintrag
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO jobs (hash, title, company, profile_id, is_active) "
        "VALUES (?, ?, ?, ?, 0)",
        ("legacy_nackt_hash", "Old", "OldCorp", pid),
    )
    conn.commit()
    # Vorher: 1 Format-A da
    nackt_before = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE hash NOT LIKE '%:%'"
    ).fetchone()[0]
    assert nackt_before == 1

    # Migration manuell triggern: schema_version zurueck + initialize
    conn.execute("UPDATE settings SET value='30' WHERE key='schema_version'")
    conn.commit()
    db.initialize()  # triggert Migration v30 → v31

    # Nachher: kein Format-A mehr
    nackt_after = db.connect().execute(
        "SELECT COUNT(*) FROM jobs WHERE hash NOT LIKE '%:%'"
    ).fetchone()[0]
    assert nackt_after == 0


def test_574_dismiss_reason_normalisierung(setup_env):
    """_serialize_job_row liefert dismiss_reasons IMMER als Liste."""
    db, _ = setup_env
    # Plain-String und JSON-Array beide einfuegen
    conn = db.connect()
    pid = db.get_active_profile_id()
    conn.execute(
        "INSERT INTO jobs (hash, title, company, profile_id, is_active, dismiss_reason) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (f"{pid}:plain01", "T", "C", pid, "falsches_fachgebiet"),
    )
    conn.execute(
        "INSERT INTO jobs (hash, title, company, profile_id, is_active, dismiss_reason) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (f"{pid}:array01", "T", "C", pid, json.dumps(["zu_weit", "duplikat"])),
    )
    conn.commit()
    plain = db.get_job("plain01")
    arr = db.get_job("array01")
    assert plain["dismiss_reasons"] == ["falsches_fachgebiet"]
    assert plain["dismiss_reason"] == "falsches_fachgebiet"
    assert arr["dismiss_reasons"] == ["zu_weit", "duplikat"]
    assert arr["dismiss_reason"] == "zu_weit"  # erstes Element


# ============= #567 Duplikat-Filter zweistufig ===============
def test_567_dismissed_does_not_block_new_application(setup_env):
    """Eine ALTE aussortierte Stelle bei der gleichen Firma blockt nicht."""
    db, _ = setup_env
    pid = db.get_active_profile_id()
    # Aussortierte alte Stelle anlegen
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, title, company, profile_id, is_active, "
        "dismiss_reason, found_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
        (f"{pid}:old01", "Old Position", "TestCorp",
         pid, "falsches_fachgebiet",
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    # Neue Stelle bei gleicher Firma soll durchgehen
    from bewerbungs_assistent.server import mcp
    async def call():
        tool = await mcp.get_tool("stelle_manuell_anlegen")
        res = await tool.run({
            "titel": "Brand New Position",
            "firma": "TestCorp",
            "url": "https://example.com/new",
        })
        return res.structured_content if hasattr(res, "structured_content") else res
    result = asyncio.run(call())
    # Sollte nicht „warnung" zurueckgeben
    assert "warnung" not in result, f"Aussortierte Stelle blockte faelschlich: {result}"


def test_567_running_application_blocks_new(setup_env):
    """Eine LAUFENDE Bewerbung bei der gleichen Firma + aehnlichem Titel blockt."""
    db, _ = setup_env
    db.add_application({
        "title": "PLM Manager",
        "company": "TestCorp",
        "status": "beworben",  # laeuft noch
    })
    from bewerbungs_assistent.server import mcp
    async def call():
        tool = await mcp.get_tool("stelle_manuell_anlegen")
        res = await tool.run({
            "titel": "PLM Manager Senior",
            "firma": "TestCorp",
            "url": "https://example.com/x",
        })
        return res.structured_content if hasattr(res, "structured_content") else res
    result = asyncio.run(call())
    assert result.get("warnung") == "duplikat_bewerbung"


def test_567_terminal_application_does_not_block(setup_env):
    """Eine ABGELEHNTE Bewerbung blockt nicht — User darf sich neu bewerben."""
    db, _ = setup_env
    db.add_application({
        "title": "PLM Manager",
        "company": "TestCorp",
        "status": "abgelehnt",
    })
    from bewerbungs_assistent.server import mcp
    async def call():
        tool = await mcp.get_tool("stelle_manuell_anlegen")
        res = await tool.run({
            "titel": "PLM Manager (neue Stelle)",
            "firma": "TestCorp",
            "url": "https://example.com/x",
        })
        return res.structured_content if hasattr(res, "structured_content") else res
    result = asyncio.run(call())
    assert "warnung" not in result, f"Terminale Bewerbung blockte faelschlich: {result}"


# ============= #570 Direkt-Upload Idempotenz ===============
def test_570_uploadDocumentFile_signature_accepts_options():
    """Frontend-Helper akzeptiert options.applicationId."""
    src = Path("frontend/src/document-upload.js").read_text(encoding="utf-8")
    assert "options.applicationId" in src
    assert "link_application_id" in src


# ============= #547 Auto-Quarantaene silent_timeout ===============
def test_547_silent_timeout_detected(setup_env):
    """Status=ok+count=0+time>60s wird als silent_timeout markiert."""
    db, _ = setup_env
    db.update_scraper_health("jobware_test", "ok", count=0, time_s=237.0)
    health = db.get_scraper_health()
    entry = next((h for h in health if h["scraper_name"] == "jobware_test"), None)
    assert entry is not None
    # Status-Detail sollte "silent_timeout" sein (nicht nur "silent")
    assert "silent_timeout" in (entry.get("last_status_detail") or "")


# ============= #554 scores_neu_berechnen Tool ===============
def test_554_scores_neu_berechnen_existiert(setup_env):
    """Neues MCP-Tool ist registriert."""
    from bewerbungs_assistent.server import mcp
    async def get():
        tool = await mcp.get_tool("scores_neu_berechnen")
        return tool
    tool = asyncio.run(get())
    assert tool is not None
    assert tool.name == "scores_neu_berechnen"


def test_554_scores_neu_berechnen_runs_on_empty_db(setup_env):
    """Tool laeuft ohne Crash auf leerer DB."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    async def call():
        tool = await mcp.get_tool("scores_neu_berechnen")
        res = await tool.run({"nur_aktive": True})
        return res.structured_content if hasattr(res, "structured_content") else res
    result = asyncio.run(call())
    assert result.get("status") == "fertig"
    assert result.get("verarbeitet") == 0


# ============= Smoke: Migration auf realer Bestand ===============
def test_migration_idempotent(setup_env):
    """Migration v31 zweimal hintereinander ist idempotent."""
    db, _ = setup_env
    conn = db.connect()
    # Erste Migration ist beim setup_env schon gelaufen
    # Zweite Migration triggern
    conn.execute("UPDATE settings SET value='30' WHERE key='schema_version'")
    conn.commit()
    db.initialize()
    # Sollte ohne Crash laufen, schema_version zurueck auf 31
    sv = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0]
    assert sv == "31"
