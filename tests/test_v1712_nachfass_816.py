"""Tests fuer v1.7.12 — #816 (D34): Offene Aktionen sagen, WAS zu tun ist.

Belegte Befunde: 8 von 9 Nachfassungen hatten ein leeres template (kein
Aufrufweg befuellte es); die naechste_aktionen einer 55 Tage stillen
Bewerbung OHNE je ein Interview empfahlen Interview-Vorbereitung mit
Prio 1, boten 'zurueckgezogen' fuer Funkstille an und trugen doppelte
Prioritaeten.
"""
import asyncio
import importlib
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_816_")
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


def test_816_auto_followup_hat_inhalt(setup_env):
    """Der Kern-Befund: Auto-Nachfassungen entstanden als leerer Reminder."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = db.add_application({
        "company": "Anlagenbau Sued GmbH",
        "title": "Consultant SAP ECTR",
        "status": "in_vorbereitung",
        "ansprechpartner": "Erik Mustermann",
        "kontakt_email": "bewerbung@firma.de",
    })
    res = _result(_call(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": aid, "neuer_status": "beworben"}))
    assert "fehler" not in res, res
    fus = db.get_pending_follow_ups()
    assert fus, "Auto-Follow-up muss existieren"
    tpl = fus[0].get("template") or ""
    assert tpl, "NIE mehr als leerer Reminder"
    assert "Anlagenbau Sued" in tpl
    assert "Consultant SAP ECTR" in tpl
    assert "Erik Mustermann" in tpl, "Ansprechpartner gehoert in die Anweisung"


def test_816_follow_up_bearbeiten(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = db.add_application({"company": "F", "title": "T",
                              "status": "beworben"})
    fid = db.add_follow_up(aid, "2026-09-01", "nachfass")
    res = _result(_call(mcp, "follow_up_bearbeiten", {
        "follow_up_id": fid,
        "text": "Bei der Fachabteilung telefonisch nachfragen, "
                "Bezug: Arbeitsprobe vom 05.08."}))
    assert res["status"] == "aktualisiert"
    fu = db.get_follow_up(fid)
    assert "telefonisch" in (fu.get("template") or "")

    leer = _result(_call(mcp, "follow_up_bearbeiten", {
        "follow_up_id": fid, "text": "  "}))
    assert "fehler" in leer, "leerer Text ist genau das Problem"


def _stale_app(db, mcp_unused, status="beworben", tage=55):
    aid = db.add_application({
        "company": "Anlagenbau Sued GmbH", "title": "Consultant",
        "status": status, "ansprechpartner": "Erik Mustermann",
        "kontakt_email": "bewerbung@firma.de"})
    alt = (datetime.now(timezone.utc) - timedelta(days=tage)).isoformat()
    conn = db.connect()
    conn.execute("UPDATE application_events SET event_date=? "
                 "WHERE application_id=?", (alt, aid))
    conn.commit()
    return aid


def test_816_funkstille_ohne_interview_fallbezogen(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = _stale_app(db, mcp)
    res = _result(_call(mcp, "bewerbung_details", {"bewerbung_id": aid}))
    akt = res.get("nächste_aktionen") or res.get("naechste_aktionen")
    assert akt and akt.get("staleness_tage", 0) >= 14, akt
    aktionen = akt["aktionen"]
    labels = [a["label"] for a in aktionen]

    # Kein Interview-Workflow ohne je ein Interview
    assert not any(a.get("workflow") in ("interview_vorbereitung",
                                          "interview_simulation")
                   for a in aktionen), labels
    # Nachfassen ist Prio 1 und nennt Ansprechpartner + Mail
    assert aktionen[0]["prioritaet"] == 1
    assert "Erik Mustermann" in aktionen[0]["label"]
    assert "bewerbung@firma.de" in aktionen[0]["label"]
    # Funkstille -> abgelaufen, NICHT zurueckgezogen
    assert any(a.get("status") == "abgelaufen" for a in aktionen), labels
    assert not any(a.get("status") == "zurueckgezogen" for a in aktionen)
    # Deterministische Rangfolge: 1..n ohne Dubletten
    prios = [a["prioritaet"] for a in aktionen]
    assert prios == list(range(1, len(prios) + 1)), prios


def test_816_nach_interview_bleiben_interview_aktionen(setup_env):
    """Wer im Interview-Stadium ist, behaelt die Interview-Werkzeuge."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = _stale_app(db, mcp, status="interview", tage=20)
    res = _result(_call(mcp, "bewerbung_details", {"bewerbung_id": aid}))
    akt = res.get("nächste_aktionen") or res.get("naechste_aktionen")
    aktionen = akt["aktionen"]
    prios = [a["prioritaet"] for a in aktionen]
    assert prios == list(range(1, len(prios) + 1)), prios
