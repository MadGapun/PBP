"""beta.94 (#677/#678): Hintergrund-Automatik — Scheduler-Logik + Settings + MCP.

Getestet wird die Steuer-Logik (Intervalle, Faelligkeit, Status) und die
MCP-/DB-Schicht. Die eigentlichen Laeufe (Ollama-Analyse, Scraper) werden
NICHT angestossen — die self-gaten ohnehin und brauchen externe Dienste.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register_analyse(tmp_db):
    from bewerbungs_assistent.tools.analyse import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


# ── DB-Settings ──────────────────────────────────────────────────────────


def test_automatik_settings_default_aus(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    s = tmp_db.get_automatik_settings()
    assert s["jobsuche_intervall_tage"] == 0
    assert s["lernen_intervall_tage"] == 0
    assert s["jobsuche_last_at"] == ""


def test_automatik_settings_setzen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    out = tmp_db.set_automatik_settings(jobsuche_intervall_tage=3, lernen_intervall_tage=7)
    assert out["jobsuche_intervall_tage"] == 3
    assert out["lernen_intervall_tage"] == 7


def test_automatik_settings_ungueltig(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    import pytest
    with pytest.raises(ValueError):
        tmp_db.set_automatik_settings(jobsuche_intervall_tage=5)  # 5 nicht erlaubt


def test_mark_automatik_run(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    ts = tmp_db.mark_automatik_run("jobsuche")
    assert ts
    assert tmp_db.get_automatik_settings()["jobsuche_last_at"] == ts
    import pytest
    with pytest.raises(ValueError):
        tmp_db.mark_automatik_run("quatsch")


# ── Faelligkeits-Logik ───────────────────────────────────────────────────


def test_is_due_logic():
    from bewerbungs_assistent.services.automatik_scheduler import _is_due
    now = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)
    # aus
    assert _is_due(0, "", now) is False
    # nie gelaufen -> faellig
    assert _is_due(7, "", now) is True
    # gerade gelaufen -> nicht faellig
    recent = (now - timedelta(days=1)).isoformat()
    assert _is_due(7, recent, now) is False
    # lange her -> faellig
    old = (now - timedelta(days=8)).isoformat()
    assert _is_due(7, old, now) is True


def test_compute_status_shape(tmp_db):
    from bewerbungs_assistent.services.automatik_scheduler import compute_status
    tmp_db.create_profile("Test", "test@example.com")
    tmp_db.set_automatik_settings(jobsuche_intervall_tage=1)
    st = compute_status(tmp_db)
    assert st["jobsuche"]["intervall_tage"] == 1
    assert st["jobsuche"]["naechster_lauf"] == "faellig"  # noch nie gelaufen
    assert st["lernen"]["intervall_tage"] == 0
    assert "hinweis" in st


# ── MCP-Tools ────────────────────────────────────────────────────────────


def test_mcp_automatik_status_und_setzen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_analyse(tmp_db)
    status = mcp.tools["automatik_status"]
    setzen = mcp.tools["automatik_setzen"]

    r = setzen(jobsuche_intervall_tage=3, lernen_intervall_tage=7)
    assert r["status"] == "gespeichert"
    assert r["jobsuche"]["intervall_tage"] == 3

    st = status()
    assert st["jobsuche"]["intervall_tage"] == 3
    assert st["lernen"]["intervall_tage"] == 7


def test_mcp_automatik_setzen_ungueltig(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_analyse(tmp_db)
    r = mcp.tools["automatik_setzen"](jobsuche_intervall_tage=99)
    assert "fehler" in r


def test_mcp_automatik_setzen_leer(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_analyse(tmp_db)
    r = mcp.tools["automatik_setzen"]()
    assert "fehler" in r
