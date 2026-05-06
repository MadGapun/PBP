"""Tests fuer v1.7.0-beta.20 — Recruiter-Anfragen sauber + Auto-Engine.

A) Recruiter-Anfragen
   - bewerbung_erstellen blockt bereits_beworben=False + status=zurueckgezogen/abgelehnt
   - recruiter_anfrage_ablehnen legt Stelle an + dismisst, KEIN applications-Eintrag
   - bewerbung_zu_anfrage_konvertieren loescht Bewerbung, dismisst Stelle

B) Status-Whitelist
   - bewerbung_status_aendern lehnt 'warte_auf_rueckmeldung' ab (mit Mapping-Hinweis)
   - bewerbung_status_aendern akzeptiert offizielle Werte

C) Schema v37 Migration
   - warte_auf_rueckmeldung -> eingangsbestaetigung
   - abgesagt -> abgelaufen

D) Auto-Engine
   - Auto-Expire setzt Bewerbungen ohne Aktivitaet > N Tage auf abgelaufen
   - Auto-FU-Reconciler legt fehlende FUs an
   - Settings-Endpoint validiert Bereiche
"""
import asyncio
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta20_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db, _srv_mod
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    """FastMCP 2.12+ Tool-Call-Helper (siehe CLAUDE.md)."""
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _result(raw):
    """Unwrap FastMCP-Result-Container."""
    if isinstance(raw, dict) and set(raw.keys()) == {"result"}:
        return raw["result"]
    return raw


# ============= A) Recruiter-Anfragen ===============

def test_bewerbung_erstellen_blocks_inbound_pattern(setup_env):
    db, srv = setup_env
    raw = _call(srv.mcp, "bewerbung_erstellen", {
        "title": "X", "company": "ACME",
        "bereits_beworben": False,
        "status": "zurueckgezogen",
    })
    r = _result(raw)
    assert "fehler" in r
    assert "recruiter_anfrage_ablehnen" in r.get("vorschlag_tool", "")
    # KEIN Eintrag in applications
    assert len(db.get_applications()) == 0


def test_bewerbung_erstellen_blocks_inbound_abgelehnt(setup_env):
    """Auch status='abgelehnt' bei bereits_beworben=False soll blockiert werden."""
    db, srv = setup_env
    raw = _call(srv.mcp, "bewerbung_erstellen", {
        "title": "Y", "company": "BCorp",
        "bereits_beworben": False,
        "status": "abgelehnt",
    })
    r = _result(raw)
    assert "fehler" in r
    assert len(db.get_applications()) == 0


def test_recruiter_anfrage_ablehnen_creates_dismissed_job(setup_env):
    db, srv = setup_env
    raw = _call(srv.mcp, "recruiter_anfrage_ablehnen", {
        "firma": "BadFit GmbH",
        "titel": "PHP-Entwickler",
        "grund": "falsches_fachgebiet",
        "notizen": "PHP ist nicht meine Welt.",
    })
    r = _result(raw)
    assert r["status"] == "abgelehnt"

    # Stelle ist im Bestand mit is_active=0
    pid = db.get_active_profile_id()
    conn = db.connect()
    job = conn.execute(
        "SELECT * FROM jobs WHERE company=? AND (profile_id=? OR profile_id IS NULL)",
        ("BadFit GmbH", pid)
    ).fetchone()
    assert job is not None
    assert job["is_active"] == 0
    assert job["dismiss_reason"] == "falsches_fachgebiet"
    assert job["source"] == "recruiter_inbound"

    # KEIN Bewerbungs-Eintrag
    assert len(db.get_applications()) == 0


def test_recruiter_anfrage_ablehnen_validiert_pflichtfelder(setup_env):
    db, srv = setup_env
    raw = _call(srv.mcp, "recruiter_anfrage_ablehnen", {
        "firma": "X", "titel": "Y", "grund": "",
    })
    r = _result(raw)
    assert "fehler" in r


def test_konvertieren_leert_applications_dismisst_stelle(setup_env):
    db, srv = setup_env
    # Faelschlich angelegte "zurueckgezogen"-Bewerbung ohne Stelle
    aid = db.add_application({
        "title": "PLM Manager", "company": "Leuchtmehr",
        "status": "zurueckgezogen",
        "notes": "Headhunter, Standort passt nicht.",
    })
    raw = _call(srv.mcp, "bewerbung_zu_anfrage_konvertieren", {
        "bewerbung_id": aid, "grund": "standort",
    })
    r = _result(raw)
    assert r["status"] == "konvertiert"
    # Bewerbung weg
    assert db.get_application(aid) is None
    # Stelle existiert + ist dismissed
    pid = db.get_active_profile_id()
    conn = db.connect()
    job = conn.execute(
        "SELECT * FROM jobs WHERE company='Leuchtmehr' AND (profile_id=? OR profile_id IS NULL)",
        (pid,)
    ).fetchone()
    assert job is not None
    assert job["is_active"] == 0
    assert job["dismiss_reason"] == "standort"


def test_konvertieren_lehnt_aktive_bewerbungen_ab(setup_env):
    db, srv = setup_env
    aid = db.add_application({
        "title": "X", "company": "ACME", "status": "beworben",
    })
    raw = _call(srv.mcp, "bewerbung_zu_anfrage_konvertieren", {
        "bewerbung_id": aid,
    })
    r = _result(raw)
    assert "fehler" in r


# ============= B) Status-Whitelist ===============

def test_status_whitelist_blocks_undefined(setup_env):
    db, srv = setup_env
    aid = db.add_application({"title": "X", "company": "Y", "status": "beworben"})
    raw = _call(srv.mcp, "bewerbung_status_aendern", {
        "bewerbung_id": aid,
        "neuer_status": "warte_auf_rueckmeldung",
    })
    r = _result(raw)
    assert "fehler" in r
    assert r.get("vorschlag_status") == "eingangsbestaetigung"


def test_status_whitelist_blocks_unknown(setup_env):
    db, srv = setup_env
    aid = db.add_application({"title": "X", "company": "Y", "status": "beworben"})
    raw = _call(srv.mcp, "bewerbung_status_aendern", {
        "bewerbung_id": aid,
        "neuer_status": "schmuh",
    })
    r = _result(raw)
    assert "fehler" in r
    assert "Unbekannter" in r["fehler"]


def test_status_whitelist_accepts_official(setup_env):
    db, srv = setup_env
    aid = db.add_application({"title": "X", "company": "Y", "status": "beworben"})
    raw = _call(srv.mcp, "bewerbung_status_aendern", {
        "bewerbung_id": aid,
        "neuer_status": "interview",
    })
    r = _result(raw)
    assert "fehler" not in r
    assert db.get_application(aid)["status"] == "interview"


# ============= C) Schema v37 Migration ===============

def test_v37_migration_warte_auf_rueckmeldung_to_eingang(setup_env):
    """Direkter Test mit DB-Manipulation: alte Status-Werte werden migriert."""
    db, _ = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    # Direkt unter dem Schutzgitter eingefuegt — als waers ein altes Bestand-Datum
    conn.execute(
        "INSERT INTO applications (id, profile_id, title, company, status, applied_at, created_at) "
        "VALUES ('alt1', ?, 'X', 'Y', 'warte_auf_rueckmeldung', '2026-01-01', '2026-01-01T10:00:00')",
        (pid,)
    )
    conn.execute(
        "INSERT INTO applications (id, profile_id, title, company, status, applied_at, created_at) "
        "VALUES ('alt2', ?, 'A', 'B', 'abgesagt', '2026-01-02', '2026-01-02T10:00:00')",
        (pid,)
    )
    conn.commit()
    # Migration manuell triggern
    db._migrate(36, 37)
    # Pruefen: beide Bestand-Eintraege sind umgemappt
    r1 = conn.execute("SELECT status FROM applications WHERE id='alt1'").fetchone()
    r2 = conn.execute("SELECT status FROM applications WHERE id='alt2'").fetchone()
    assert r1["status"] == "eingangsbestaetigung"
    assert r2["status"] == "abgelaufen"
    # Audit-Events wurden geschrieben
    e1 = conn.execute(
        "SELECT notes FROM application_events WHERE application_id='alt1' "
        "AND status='eingangsbestaetigung' AND notes LIKE 'Auto-Migration v37%'"
    ).fetchone()
    assert e1 is not None


# ============= D) Auto-Engine ===============

def _backdate_application(db, aid, date_str):
    """Setzt applied_at + event_date auf einen alten Wert.

    add_application schreibt automatisch ein Event mit jetzt-Timestamp;
    fuer realistische Tests muessen wir das auch zuruecksetzen.
    """
    conn = db.connect()
    conn.execute("UPDATE applications SET applied_at=? WHERE id=?",
                 (date_str + "T10:00:00", aid))
    conn.execute("UPDATE application_events SET event_date=? WHERE application_id=?",
                 (date_str + "T10:00:00", aid))
    conn.commit()


def test_auto_expire_setzt_alte_bewerbungen(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # Eine 90 Tage alte beworbene Bewerbung (sollte abgelaufen werden — default 60d)
    old_date = (datetime.now() - timedelta(days=90)).date().isoformat()
    aid = db.add_application({
        "title": "Alt", "company": "Lange Stille", "status": "beworben",
    })
    _backdate_application(db, aid, old_date)
    # Eine 5 Tage alte (soll bleiben)
    new_date = (datetime.now() - timedelta(days=5)).date().isoformat()
    aid_new = db.add_application({
        "title": "Frisch", "company": "Frisch", "status": "beworben",
    })
    _backdate_application(db, aid_new, new_date)

    r = client.post("/api/auto-actions/run")
    j = r.json()
    assert j["expire"]["expired_count"] == 1
    assert any(e["id"] == aid for e in j["expire"]["expired"])
    assert db.get_application(aid)["status"] == "abgelaufen"
    assert db.get_application(aid_new)["status"] == "beworben"


def test_auto_expire_eingangsbestaetigung_kuerzeres_threshold(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # 40 Tage alt — fuer 'beworben' (60d) noch ok, fuer 'eingangsbestaetigung' (30d) abgelaufen
    old_date = (datetime.now() - timedelta(days=40)).date().isoformat()
    aid_eb = db.add_application({
        "title": "EB", "company": "EB-Co", "status": "eingangsbestaetigung",
    })
    _backdate_application(db, aid_eb, old_date)
    r = client.post("/api/auto-actions/run")
    j = r.json()
    assert any(e["id"] == aid_eb for e in j["expire"]["expired"])


def test_auto_followup_reconciler_legt_fehlende_an(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # Bewerbung ohne FU
    base_date = (datetime.now() - timedelta(days=10)).date().isoformat()
    aid = db.add_application({
        "title": "FU-Test", "company": "Co",
        "status": "beworben",
        "applied_at": base_date + "T10:00:00",
    })
    # Sicherstellen dass es keinen offenen FU gibt
    fus_before = db.get_pending_follow_ups()
    assert all(f["application_id"] != aid for f in fus_before)

    r = client.post("/api/auto-actions/run")
    j = r.json()
    assert j["followup_reconciler"]["created_count"] >= 1
    fus_after = db.get_pending_follow_ups()
    assert any(f["application_id"] == aid for f in fus_after)


def test_auto_actions_settings_validieren(setup_env):
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    # Out-of-range
    r = client.put("/api/auto-actions/settings", json={"expire_default_days": 9999})
    assert r.status_code == 400
    # Valid
    r2 = client.put("/api/auto-actions/settings", json={"expire_default_days": 45})
    assert r2.status_code == 200
    # Status-Endpoint sieht den neuen Wert
    s = client.get("/api/auto-actions/status").json()
    assert s["settings"]["expire_default_days"] == 45


def test_auto_actions_idempotent_zweiter_lauf(setup_env):
    """Zweiter Lauf am gleichen Tag erzeugt keine Duplikate."""
    db, _ = setup_env
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    base_date = (datetime.now() - timedelta(days=10)).date().isoformat()
    db.add_application({
        "title": "Dup-Test", "company": "Co",
        "status": "beworben",
        "applied_at": base_date + "T10:00:00",
    })
    # 1. Lauf
    j1 = client.post("/api/auto-actions/run").json()
    n1 = j1["followup_reconciler"]["created_count"]
    # 2. Lauf
    j2 = client.post("/api/auto-actions/run").json()
    # Beim 2. Lauf sollten keine FUs erneut erzeugt werden
    assert j2["followup_reconciler"]["created_count"] == 0
    assert n1 >= 1
