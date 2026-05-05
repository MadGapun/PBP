"""Tests fuer v1.7.0-beta.6 — Bewerbungsaufwand (#568)."""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta6_")
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


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


# ============= Schema ===============

def test_568_application_costs_table_exists(setup_env):
    db, _ = setup_env
    conn = db.connect()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='application_costs'"
    ).fetchone()
    assert row is not None


def test_568_meetings_have_aufwand_columns(setup_env):
    db, _ = setup_env
    conn = db.connect()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(application_meetings)").fetchall()]
    for needed in ("runde_nr", "vorbereitungszeit_min", "reise_modus",
                   "reisekosten_brutto", "reisekosten_erstattet"):
        assert needed in cols


# ============= add_application_cost ===============

def test_568_add_cost_basic(setup_env):
    db, _ = setup_env
    cid = db.add_application_cost({
        "kind": "tool",
        "amount": 9.99,
        "description": "LinkedIn Premium",
    })
    assert cid
    items = db.list_application_costs()
    assert len(items) == 1
    assert items[0]["amount"] == 9.99
    assert items[0]["kind"] == "tool"


def test_568_add_cost_negative_amount_rejected(setup_env):
    db, _ = setup_env
    with pytest.raises(ValueError):
        db.add_application_cost({"kind": "tool", "amount": -5})


def test_568_filter_costs_by_kind(setup_env):
    db, _ = setup_env
    db.add_application_cost({"kind": "tool", "amount": 10})
    db.add_application_cost({"kind": "reise", "amount": 50})
    db.add_application_cost({"kind": "tool", "amount": 20})
    tools = db.list_application_costs(kind="tool")
    assert len(tools) == 2
    reisen = db.list_application_costs(kind="reise")
    assert len(reisen) == 1


def test_568_delete_cost(setup_env):
    db, _ = setup_env
    cid = db.add_application_cost({"kind": "tool", "amount": 5})
    ok = db.delete_application_cost(cid)
    assert ok
    assert len(db.list_application_costs()) == 0


# ============= update_meeting_aufwand ===============

def test_568_update_meeting_aufwand(setup_env):
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    mid = db.add_meeting({
        "application_id": bid,
        "title": "Interview Round 1",
        "meeting_date": "2026-05-10T10:00:00",
        "duration_minutes": 60,
    })
    ok = db.update_meeting_aufwand(
        mid, runde_nr=1, vorbereitungszeit_min=120,
        reise_modus="video", reisekosten_brutto=0
    )
    assert ok
    # Read back
    conn = db.connect()
    row = conn.execute("SELECT * FROM application_meetings WHERE id=?", (mid,)).fetchone()
    assert row["runde_nr"] == 1
    assert row["vorbereitungszeit_min"] == 120
    assert row["reise_modus"] == "video"


# ============= get_aufwand_summary ===============

def test_568_aufwand_summary_total(setup_env):
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    mid = db.add_meeting({
        "application_id": bid,
        "title": "Interview",
        "meeting_date": "2026-05-10T10:00:00",
        "duration_minutes": 90,
    })
    db.update_meeting_aufwand(
        mid, vorbereitungszeit_min=60,
        reisekosten_brutto=80, reisekosten_erstattet=20
    )
    db.add_application_cost({"kind": "tool", "amount": 15, "application_id": bid})
    s = db.get_aufwand_summary(application_id=bid)
    assert s["kosten_summe_eur"] == 15.0
    assert s["reisekosten_brutto_eur"] == 80.0
    assert s["reisekosten_erstattet_eur"] == 20.0
    assert s["reisekosten_netto_eur"] == 60.0
    assert s["vorbereitungszeit_min_summe"] == 60
    assert s["termine_dauer_min_summe"] == 90
    assert s["termine_anzahl"] == 1


# ============= MCP-Tools ===============

def test_568_kosten_erfassen_tool(setup_env):
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "kosten_erfassen", {
        "kategorie": "tool",
        "betrag_eur": 49.99,
        "beschreibung": "Notion 1 Jahr",
    })
    assert result["status"] == "gespeichert"


def test_568_kosten_validates_kategorie(setup_env):
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "kosten_erfassen", {
        "kategorie": "ungueltig",
        "betrag_eur": 10,
    })
    assert "fehler" in result


def test_568_kosten_validates_negative(setup_env):
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "kosten_erfassen", {
        "kategorie": "tool",
        "betrag_eur": -10,
    })
    assert "fehler" in result


def test_568_kosten_anzeigen_summe(setup_env):
    db, _ = setup_env
    db.add_application_cost({"kind": "tool", "amount": 10})
    db.add_application_cost({"kind": "tool", "amount": 25})
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "kosten_anzeigen", {})
    assert result["anzahl"] == 2
    assert result["summe_eur"] == 35.0


def test_568_aufwand_uebersicht_tool(setup_env):
    db, _ = setup_env
    db.add_application_cost({"kind": "tool", "amount": 50})
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "aufwand_uebersicht", {})
    assert result["kosten_summe_eur"] == 50.0


def test_568_meeting_aufwand_setzen_tool(setup_env):
    db, _ = setup_env
    bid = db.add_application({"title": "T", "company": "C"})
    mid = db.add_meeting({
        "application_id": bid,
        "title": "Interview",
        "meeting_date": "2026-05-10T10:00:00",
        "duration_minutes": 45,
    })
    from bewerbungs_assistent.server import mcp
    result = _call(mcp, "meeting_aufwand_setzen", {
        "meeting_id": mid,
        "runde": 2,
        "vorbereitung_minuten": 90,
        "reise_modus": "vor_ort",
        "reisekosten_brutto": 75.50,
    })
    assert result["status"] == "aktualisiert"
