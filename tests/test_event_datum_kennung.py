"""bewerbung_event_datum_setzen: die ID steht in der Timeline, und fremde
Profile sind tabu (#994-Klasse, #1106-Klasse)."""
from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database
    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "ev.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Erstes"))
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _call(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.bewerbungen import register
    mcp = FastMCP("t")
    register(mcp, db, logging.getLogger("t"))

    async def lauf():
        res = await (await mcp.get_tool(name)).run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(lauf())


def test_timeline_nennt_die_event_id_und_sie_wirkt(db):
    app = db.add_application({"title": "Einkauf", "company": "Musterfirma", "status": "beworben"})
    details = _call(db, "bewerbung_details", {"bewerbung_id": app})
    eintrag = details["timeline"][0]
    assert isinstance(eintrag["event_id"], int)
    erg = _call(db, "bewerbung_event_datum_setzen",
                {"event_id": eintrag["event_id"], "neues_datum": "2026-09-01"})
    assert erg["status"] == "ok" and erg["new_date"].startswith("2026-09-01")


def test_event_eines_anderen_profils_ist_nicht_erreichbar(db):
    app = db.add_application({"title": "Einkauf", "company": "Musterfirma", "status": "beworben"})
    eid = db.get_application(app)["events"][0]["id"]
    db.switch_profile(db.create_profile("Zweites"))
    erg = _call(db, "bewerbung_event_datum_setzen", {"event_id": eid, "neues_datum": "2026-09-01"})
    assert erg.get("fehler") == "Event nicht gefunden."
