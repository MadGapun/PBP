"""Tests fuer v1.7.12 — #825 (D32): Vollstaendigkeits-Check Interview.

Belegter Fall: Verfahren mit zwei Interviews und sieben Dokumenten,
verknuepfter Kontakt: EINER — der Vermittler. Die Endkundenseite stand
nirgends. Der Check meldet solche Luecken; er behebt nichts automatisch,
und jeder Befund ist einzeln dauerhaft abweisbar.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_825_")
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


def _pruefe(db):
    from bewerbungs_assistent.services.interview_vollstaendigkeit import (
        pruefe_interview_vollstaendigkeit)
    return pruefe_interview_vollstaendigkeit(db)


def _kontakt(db, name, firma, role=""):
    return db.add_contact({"full_name": name, "company": firma,
                           "tags": [role] if role else []})


def test_825_kein_kontakt_jenseits_beworben(setup_env):
    db, _ = setup_env
    aid = db.add_application({"company": "Werft Nord", "title": "Lead",
                              "status": "interview"})
    arten = {b["art"]: b for b in _pruefe(db) if b["bewerbung_id"] == aid}
    assert "kein_kontakt" in arten
    assert arten["kein_kontakt"]["deeplink"] == f"pbp://bewerbung/{aid}"


def test_825_nur_vermittler_wird_erkannt(setup_env):
    """Der belegte Fall: einziger Kontakt ist der Vermittler."""
    db, _ = setup_env
    aid = db.add_application({"company": "Werft Nord", "title": "Lead",
                              "status": "interview"})
    kid = _kontakt(db, "Vermittelnde Person",
                   "Ingenieurvermittlung Mitte GmbH", role="recruiter")
    db.link_contact(kid, "application", aid, role="recruiter")
    arten = {b["art"] for b in _pruefe(db) if b["bewerbung_id"] == aid}
    assert "nur_vermittler" in arten
    assert "kein_kontakt" not in arten


def test_825_direktbewerbung_ist_kein_befund(setup_env):
    """Guard: Kontakt in der Bewerbungsfirma -> normale Direktbewerbung."""
    db, _ = setup_env
    aid = db.add_application({"company": "Werft Nord GmbH", "title": "Lead",
                              "status": "interview"})
    kid = _kontakt(db, "Fachliche Leitung", "Werft Nord GmbH")
    db.link_contact(kid, "application", aid)
    arten = {b["art"] for b in _pruefe(db) if b["bewerbung_id"] == aid}
    assert "nur_vermittler" not in arten
    assert "kein_kontakt" not in arten


def test_825_beworben_ohne_kontakt_ist_kein_befund(setup_env):
    """Pruefung 4 greift erst JENSEITS von 'beworben'."""
    db, _ = setup_env
    aid = db.add_application({"company": "Firma X", "title": "Y",
                              "status": "beworben"})
    assert all(b["bewerbung_id"] != aid for b in _pruefe(db))


def test_825_vergangener_termin_ohne_teilnehmer_und_reflexion(setup_env):
    db, _ = setup_env
    aid = db.add_application({"company": "Werft Nord", "title": "Lead",
                              "status": "interview"})
    kid = _kontakt(db, "Fachliche Leitung", "Werft Nord")
    db.link_contact(kid, "application", aid)
    mid = db.add_meeting({"application_id": aid,
                          "meeting_date": "2026-08-05T16:00:00",
                          "title": "Interview Runde 1",
                          "meeting_type": "interview"})
    arten = {b["art"]: b for b in _pruefe(db) if b["bewerbung_id"] == aid}
    assert "termin_ohne_teilnehmer" in arten
    assert arten["termin_ohne_teilnehmer"]["termin_id"] == str(mid)
    assert "termin_ohne_reflexion" in arten

    # Teilnehmer nachgetragen -> Befund weg
    db.link_contact(kid, "meeting", str(mid), role="Entscheider")
    arten2 = {b["art"] for b in _pruefe(db) if b["bewerbung_id"] == aid}
    assert "termin_ohne_teilnehmer" not in arten2

    # Reflexion nachgetragen -> Befund weg
    db.add_interview_reflection(aid, {"was_lief_gut": "ok"},
                                meeting_id=str(mid))
    arten3 = {b["art"] for b in _pruefe(db) if b["bewerbung_id"] == aid}
    assert "termin_ohne_reflexion" not in arten3


def test_825_zukuenftiger_termin_ist_kein_befund(setup_env):
    """Karenz: nicht schon waehrend/vor dem Gespraech melden."""
    db, _ = setup_env
    aid = db.add_application({"company": "Werft Nord", "title": "Lead",
                              "status": "interview"})
    kid = _kontakt(db, "Leitung", "Werft Nord")
    db.link_contact(kid, "application", aid)
    db.add_meeting({"application_id": aid,
                    "meeting_date": "2027-01-01T16:00:00",
                    "title": "Interview", "meeting_type": "interview"})
    arten = {b["art"] for b in _pruefe(db) if b["bewerbung_id"] == aid}
    assert "termin_ohne_teilnehmer" not in arten
    assert "termin_ohne_reflexion" not in arten


def test_825_gespraech_nur_in_notizen(setup_env):
    db, _ = setup_env
    aid = db.add_application({
        "company": "Werft Nord", "title": "Lead", "status": "interview",
        "notes": "Telefonat am 05.08.2026 mit der Fachabteilung, "
                 "sehr positiv."})
    kid = _kontakt(db, "Leitung", "Werft Nord")
    db.link_contact(kid, "application", aid)
    arten = {b["art"] for b in _pruefe(db) if b["bewerbung_id"] == aid}
    assert "gespraech_nur_notiz" in arten


def test_825_befund_dauerhaft_abweisbar(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = db.add_application({"company": "Werft Nord", "title": "Lead",
                              "status": "interview"})
    befunde = [b for b in _pruefe(db) if b["bewerbung_id"] == aid]
    assert befunde
    bid = befunde[0]["id"]

    def _call(name, args):
        async def _run():
            tool = await mcp.get_tool(name)
            res = await tool.run(args)
            return res.structured_content if hasattr(
                res, "structured_content") else res
        return asyncio.run(_run())

    res = _call("diagnose_befund_abweisen", {"befund_id": bid})
    raw = res
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    assert raw["status"] == "abgewiesen"
    assert all(b["id"] != bid for b in _pruefe(db)), \
        "abgewiesener Befund darf NIE wiederkommen"


def test_825_leerer_bestand_keine_befunde(setup_env):
    db, _ = setup_env
    assert _pruefe(db) == []


def test_825_pbp_diagnose_enthaelt_sektion(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.add_application({"company": "Werft Nord", "title": "Lead",
                        "status": "interview"})

    async def _run():
        tool = await mcp.get_tool("pbp_diagnose")
        res = await tool.run({"auto_fix": False})
        return res.structured_content if hasattr(
            res, "structured_content") else res
    raw = asyncio.run(_run())
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    assert "interview_vollstaendigkeit" in raw, list(raw.keys())
    assert any(b["art"] == "kein_kontakt"
               for b in raw["interview_vollstaendigkeit"])
