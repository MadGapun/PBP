"""#1111: Dashboard und Claude bauen denselben Bewerbungsbericht."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Bericht"})
    d.set_profile_setting("report_taetigkeitsbericht_mode", True)
    d.set_profile_setting("report_ba_aktenzeichen", "AZ-1")
    from bewerbungs_assistent import export_report
    d.aufrufe = []

    def fang(art):
        def _f(report_data, profile, path, **kw):
            d.aufrufe.append((art, sorted(report_data), kw))
            Path(path).write_text("x", encoding="utf-8")
        return _f
    monkeypatch.setattr(export_report, "generate_application_report", fang("pdf"))
    monkeypatch.setattr(export_report, "generate_excel_report", fang("excel"))
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _claude(db, fmt):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1111")
    register_all(mcp, db, logging.getLogger("test.1111"))

    async def lauf():
        t = await mcp.get_tool("bewerbungsbericht_exportieren")
        return (await t.run({"format": fmt})).structured_content
    return asyncio.run(lauf())


def _dashboard(db, fmt):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    return TestClient(dash.app).get("/api/applications/export", params={"format": fmt})


@pytest.mark.parametrize("claude_fmt, dash_fmt", [("pdf", "pdf"), ("excel", "xlsx")])
def test_beide_wege_gleiche_eingaben(db, claude_fmt, dash_fmt):
    _claude(db, claude_fmt)
    assert _dashboard(db, dash_fmt).status_code == 200
    (a1, daten1, kw1), (a2, daten2, kw2) = db.aufrufe
    assert a1 == a2
    assert kw1 == kw2, (kw1, kw2)
    assert daten1 == daten2
    assert kw1["report_settings"]["taetigkeitsbericht_mode"] is True
    # #781: die Prozess-Kennzahlen kamen bisher nur ueber Claude an.
    assert "prozess_kennzahlen" in daten1
    if a1 == "pdf":
        assert "pbp_first_active_at" in kw1


def test_einstellungs_endpunkt_liest_dieselbe_liste(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.services import bericht
    dash._db = db
    assert TestClient(dash.app).get("/api/settings/report").json() == bericht.einstellungen(db)


def test_einstellungen_nur_an_einer_stelle():
    funde = []
    for p in SRC.rglob("*.py"):
        if p.name == "bericht.py":
            continue
        text = p.read_text(encoding="utf-8-sig")
        if '"report_taetigkeitsbericht_mode", False' in text and "report_settings" in text:
            funde.append(p.name)
    assert not funde, funde
