"""Tests fuer Issue #664 — stelle_reaktivieren.

Bisher gab es kein MCP-Tool, um eine irrtuemlich aussortierte Stelle
wieder zu reaktivieren (`is_active=0` -> `is_active=1`). User musste
in den DB-Bypass (Verletzung von #514, H9).
"""
from __future__ import annotations

import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register_jobs(tmp_db):
    from bewerbungs_assistent.tools.jobs import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _make_dismissed_job(tmp_db, hash_short="abc12345", title="Lead Architect"):
    """Helper: legt eine aussortierte Stelle an."""
    pid = tmp_db.get_active_profile_id() or ""
    full_hash = f"{pid}:{hash_short}"
    tmp_db.save_jobs([{
        "hash": full_hash,
        "title": title,
        "company": "Beispiel GmbH",
        "location": "Bremen",
        "url": "https://example.com/job",
        "source": "manuell",
        "score": 50,
        "description": "Test-Beschreibung",
    }])
    tmp_db.dismiss_job(full_hash, "firma_uninteressant")
    return full_hash


def test_stelle_reaktivieren_setzt_is_active_und_loescht_grund(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    full_hash = _make_dismissed_job(tmp_db)

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_reaktivieren"]

    result = fn(job_hash=full_hash, grund="Irrtum — Firma nicht auf Blacklist")
    assert result["status"] == "reaktiviert"
    assert result["vorheriger_dismiss_reason"] == "firma_uninteressant"
    assert result["grund"] == "Irrtum — Firma nicht auf Blacklist"

    # DB-Stand pruefen
    job = tmp_db.get_job(full_hash)
    assert job["is_active"] == 1
    assert not job.get("dismiss_reason")


def test_stelle_reaktivieren_mit_kurzhash(tmp_db):
    """Kurzhash (8 Zeichen) muss auch aufgeloest werden."""
    tmp_db.create_profile("Test", "test@example.com")
    full_hash = _make_dismissed_job(tmp_db, hash_short="abcd1234")

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_reaktivieren"]

    result = fn(job_hash="abcd1234")
    assert result["status"] == "reaktiviert"


def test_stelle_reaktivieren_idempotent_bei_aktiver_stelle(tmp_db):
    """Wenn die Stelle bereits aktiv ist: bereits_aktiv, kein Fehler."""
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id() or ""
    full_hash = f"{pid}:xyz98765"
    tmp_db.save_jobs([{
        "hash": full_hash, "title": "Job", "company": "Firma",
        "location": "", "url": "", "source": "manuell", "score": 50,
        "description": "x",
    }])

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_reaktivieren"]

    result = fn(job_hash=full_hash)
    assert result["status"] == "bereits_aktiv"


def test_stelle_reaktivieren_fehler_bei_unbekanntem_hash(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_reaktivieren"]

    result = fn(job_hash="ffffffffffff")
    assert "fehler" in result


def test_stelle_reaktivieren_erscheint_wieder_in_stellen_anzeigen(tmp_db):
    """Reaktivierte Stelle taucht wieder in der aktiven Liste auf."""
    tmp_db.create_profile("Test", "test@example.com")
    full_hash = _make_dismissed_job(tmp_db, hash_short="d99d99d9")
    short_hash = "d99d99d9"

    mcp = _register_jobs(tmp_db)
    reaktivieren = mcp.tools["stelle_reaktivieren"]
    anzeigen = mcp.tools["stellen_anzeigen"]

    # Vor Reaktivierung: nicht aktiv -> nicht in Default-Liste
    aktiv_vor = anzeigen()
    if isinstance(aktiv_vor, dict):
        hashes_vor = [
            (j.get("hash") or "").split(":")[-1]
            for j in aktiv_vor.get("stellen", []) if isinstance(j, dict)
        ]
        assert short_hash not in hashes_vor

    reaktivieren(job_hash=full_hash)

    # Nach Reaktivierung: in Default-Liste (Kurzhash matchen, da
    # stellen_anzeigen den profile-Prefix abschneidet)
    aktiv_nach = anzeigen()
    if isinstance(aktiv_nach, dict):
        hashes_nach = [
            (j.get("hash") or "").split(":")[-1]
            for j in aktiv_nach.get("stellen", []) if isinstance(j, dict)
        ]
        assert short_hash in hashes_nach
