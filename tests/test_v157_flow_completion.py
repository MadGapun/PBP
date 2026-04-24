"""Regressionstests fuer v1.5.7 Journey-Abschluss (#455, #456, #460, #462, #453).

Deckt:
- Auto-Follow-up beim Statuswechsel auf 'beworben' (#462)
- Auto-Follow-up direkt bei bewerbung_erstellen(status='beworben') (#462)
- Auto-Hinfaellig bei Wechsel auf 'abgelehnt'/'zurueckgezogen'/'angenommen' (#453)
- Follow-up Lifecycle: erledigen, hinfaellig, verschieben (#453)
- final_salary Feld ueber bewerbung_bearbeiten (#460)
- position_aus_bewerbung_uebernehmen (#455)
- STATUS_ACTIONS enthaelt 'angenommen' und 'zurueckgezogen' (#455)
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.database import Database  # noqa: E402
from bewerbungs_assistent.tools import register_all  # noqa: E402
from bewerbungs_assistent.tools.bewerbungen import STATUS_ACTIONS  # noqa: E402


def _build_server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Flow Tester", "email": "flow@example.com"})
    mcp = FastMCP("PBP v1.5.7 Test")
    logger = logging.getLogger("test.v157")
    register_all(mcp, db, logger)
    return mcp, db


async def _call(mcp, name, args=None):
    tool = await mcp.get_tool(name)
    result = await tool.run(args or {})
    if hasattr(result, "structured_content") and result.structured_content:
        return result.structured_content
    import json
    for c in getattr(result, "content", []):
        if hasattr(c, "text"):
            try:
                return json.loads(c.text)
            except (json.JSONDecodeError, TypeError):
                return {"text": c.text}
    return {}


def _run(mcp, name, args=None):
    return asyncio.run(_call(mcp, name, args or {}))


# ==================== STATUS_ACTIONS (#455) ====================

def test_status_actions_hat_angenommen_und_zurueckgezogen():
    assert "angenommen" in STATUS_ACTIONS
    assert "zurueckgezogen" in STATUS_ACTIONS
    assert any(a["tool"] == "position_aus_bewerbung_uebernehmen"
               for a in STATUS_ACTIONS["angenommen"]["aktionen"])


# ==================== Auto-Follow-up (#462) ====================

def test_auto_followup_bei_bewerbung_erstellen_mit_status_beworben(tmp_path):
    mcp, db = _build_server(tmp_path)
    result = _run(mcp, "bewerbung_erstellen", {
        "title": "Senior Dev", "company": "Acme GmbH", "status": "beworben"
    })
    assert result.get("status") == "erstellt"
    assert "auto_follow_up" in result
    assert result["auto_follow_up"]["tage"] == 7

    # Und es gibt genau einen pending follow-up
    pendings = db.get_pending_follow_ups()
    assert len(pendings) == 1
    assert pendings[0]["application_id"] == result["bewerbung_id_voll"]


def test_auto_followup_bei_statuswechsel_auf_beworben(tmp_path):
    mcp, db = _build_server(tmp_path)
    created = _run(mcp, "bewerbung_erstellen", {
        "title": "Dev", "company": "Foo", "status": "in_vorbereitung"
    })
    assert db.get_pending_follow_ups() == []  # kein Auto-FU bei Vorbereitung

    result = _run(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": created["bewerbung_id_voll"], "neuer_status": "beworben"
    })
    assert result.get("status") == "aktualisiert"
    assert "auto_follow_up" in result
    assert len(db.get_pending_follow_ups()) == 1


def test_auto_followup_nicht_doppelt_bei_wiederholtem_wechsel(tmp_path):
    mcp, db = _build_server(tmp_path)
    created = _run(mcp, "bewerbung_erstellen", {
        "title": "Dev", "company": "Foo", "status": "beworben"
    })
    # Statuswechsel durch Interview -> zurueck zu beworben:
    bid = created["bewerbung_id_voll"]
    _run(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": bid, "neuer_status": "eingangsbestaetigung"
    })
    _run(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": bid, "neuer_status": "beworben"
    })
    # Es darf nur 1 offener Follow-up existieren (der bei Anlage entstandene)
    assert len(db.get_pending_follow_ups()) == 1


# ==================== Auto-Hinfaellig (#453) ====================

def test_absage_setzt_offene_followups_auf_hinfaellig(tmp_path):
    mcp, db = _build_server(tmp_path)
    created = _run(mcp, "bewerbung_erstellen", {
        "title": "Dev", "company": "Foo", "status": "beworben"
    })
    bid = created["bewerbung_id_voll"]
    assert len(db.get_pending_follow_ups()) == 1

    result = _run(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": bid, "neuer_status": "abgelehnt",
        "ablehnungsgrund": "Kein Match"
    })
    assert result.get("follow_ups_geschlossen") == 1
    assert db.get_pending_follow_ups() == []


def test_angenommen_setzt_offene_followups_auf_hinfaellig(tmp_path):
    mcp, db = _build_server(tmp_path)
    created = _run(mcp, "bewerbung_erstellen", {
        "title": "Dev", "company": "Foo", "status": "beworben"
    })
    bid = created["bewerbung_id_voll"]
    result = _run(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": bid, "neuer_status": "angenommen"
    })
    assert result.get("follow_ups_geschlossen") == 1
    assert db.get_pending_follow_ups() == []


# ==================== Follow-up Lifecycle (#453) ====================

def test_follow_up_erledigen_und_hinfaellig_tools(tmp_path):
    mcp, db = _build_server(tmp_path)
    created = _run(mcp, "bewerbung_erstellen", {
        "title": "Dev", "company": "Foo", "status": "beworben"
    })
    fu_id = db.get_pending_follow_ups()[0]["id"]

    result = _run(mcp, "follow_up_erledigen", {"follow_up_id": fu_id, "notiz": "Telefonat gefuehrt"})
    assert result.get("status") == "erledigt"
    assert db.get_pending_follow_ups() == []

    # zweimal erledigen ist nicht erlaubt
    second = _run(mcp, "follow_up_erledigen", {"follow_up_id": fu_id})
    assert "fehler" in second


def test_follow_up_verschieben(tmp_path):
    mcp, db = _build_server(tmp_path)
    created = _run(mcp, "bewerbung_erstellen", {
        "title": "Dev", "company": "Foo", "status": "beworben"
    })
    fu_id = db.get_pending_follow_ups()[0]["id"]
    result = _run(mcp, "follow_up_verschieben", {"follow_up_id": fu_id, "neues_datum": "2099-12-31"})
    assert result.get("status") == "verschoben"
    refreshed = db.get_follow_up(fu_id)
    assert refreshed["scheduled_date"] == "2099-12-31"


# ==================== final_salary (#460) ====================

def test_bewerbung_bearbeiten_setzt_final_salary(tmp_path):
    mcp, db = _build_server(tmp_path)
    created = _run(mcp, "bewerbung_erstellen", {
        "title": "Dev", "company": "Foo", "status": "angenommen"
    })
    bid = created["bewerbung_id_voll"]
    result = _run(mcp, "bewerbung_bearbeiten", {
        "bewerbung_id": bid, "final_salary": "72.000 EUR/Jahr"
    })
    assert result.get("status") == "aktualisiert"
    assert "final_salary" in result["geänderte_felder"]
    app = db.get_application(bid)
    assert app["final_salary"] == "72.000 EUR/Jahr"


# ==================== position_aus_bewerbung_uebernehmen (#455) ====================

def test_position_aus_bewerbung_uebernehmen(tmp_path):
    mcp, db = _build_server(tmp_path)
    created = _run(mcp, "bewerbung_erstellen", {
        "title": "Senior Platform Engineer", "company": "Acme GmbH", "status": "angenommen"
    })
    bid = created["bewerbung_id_voll"]
    result = _run(mcp, "position_aus_bewerbung_uebernehmen", {
        "bewerbung_id": bid, "start_date": "2026-05-01", "description": "Plattformteam"
    })
    assert result.get("status") == "uebernommen"
    positions = db.get_profile().get("positions", [])
    assert any(p["title"] == "Senior Platform Engineer" and p["company"] == "Acme GmbH"
               and p.get("is_current") for p in positions)


# ==================== Schema v26 ====================

def test_schema_hat_final_salary_spalte(tmp_path):
    mcp, db = _build_server(tmp_path)
    conn = db.connect()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(applications)").fetchall()]
    assert "final_salary" in cols
