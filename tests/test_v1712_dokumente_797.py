"""Tests fuer v1.7.12 — #797 (E20): lose/kaputte Dokument-Verknuepfungen.

Belegt 25.07.: 48 von 223 Dokumenten lose (9 gehoerten nachweislich zu
einer Bewerbung), drei FALSCH verknuepft — und die Antwort war nur per
Direkt-SQL zu bekommen. Eine falsche Zuordnung ist unsichtbarer als
eine fehlende: sie wird nie gesucht, weil sie scheinbar richtig liegt.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_797_")
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


def _doc(db, did, filename, doc_type="sonstiges", linked=None):
    conn = db.connect()
    conn.execute("PRAGMA foreign_keys=OFF") if linked == "__kaputt__" else None
    conn.execute(
        "INSERT INTO documents (id, filename, doc_type, "
        "linked_application_id, profile_id, created_at) "
        "VALUES (?,?,?,?,?,'2026-08-01')",
        (did, filename, doc_type,
         "app_gibt_es_nicht" if linked == "__kaputt__" else linked,
         db.get_active_profile_id()))
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")


def test_797_vorgangstyp_lose_ist_verdaechtig(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.dokument_zuordnung import (
        finde_lose_dokumente)
    _doc(db, "d1", "scan_0815.pdf", doc_type="absage")
    res = finde_lose_dokumente(db)
    assert res["verdaechtige"] == 1
    assert any("Vorgang" in g for g in res["treffer"][0]["verdacht"])


def test_797_firmenname_im_dateinamen_liefert_vorschlag(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.dokument_zuordnung import (
        finde_lose_dokumente)
    aid = db.add_application({"company": "Halbleiterwerk Nord GmbH",
                              "title": "PLM Lead", "status": "beworben"})
    _doc(db, "d2", "Halbleiterwerk_Nord_Rueckmeldung.pdf")
    res = finde_lose_dokumente(db)
    t = next(x for x in res["treffer"] if x["dokument_id"] == "d2")
    assert t["zuordnungs_vorschlag"]["bewerbung_id"] == aid
    assert t["zuordnungs_vorschlag"]["konfidenz"] == "mittel"


def test_797_thread_geschwister_ist_staerkstes_signal(setup_env):
    """Genau so wurden fuenf der neun realen Faelle gefunden."""
    db, _ = setup_env
    from bewerbungs_assistent.services.dokument_zuordnung import (
        finde_lose_dokumente)
    aid = db.add_application({"company": "Werft Nord", "title": "Lead",
                              "status": "interview"})
    _doc(db, "d3", "Ihre Bewerbung Vorgang 4711.eml", linked=aid)
    _doc(db, "d4", "AW_ Ihre Bewerbung Vorgang 4711.eml")
    res = finde_lose_dokumente(db)
    t = next(x for x in res["treffer"] if x["dokument_id"] == "d4")
    assert t["zuordnungs_vorschlag"]["bewerbung_id"] == aid
    assert t["zuordnungs_vorschlag"]["konfidenz"] == "hoch"
    assert "Thread" in t["verdacht"][0] or any(
        "Thread" in g for g in t["verdacht"])
    # Hoch-Konfidenz steht VORN
    assert res["treffer"][0]["dokument_id"] == "d4"


def test_797_unverdaechtige_nur_auf_wunsch(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.dokument_zuordnung import (
        finde_lose_dokumente)
    _doc(db, "d5", "allgemeiner_lebenslauf.pdf", doc_type="lebenslauf")
    res = finde_lose_dokumente(db, nur_verdaechtige=True)
    assert all(t["dokument_id"] != "d5" for t in res["treffer"]), \
        "allgemeine Dokumente sind zu Recht lose"
    res2 = finde_lose_dokumente(db, nur_verdaechtige=False)
    assert any(t["dokument_id"] == "d5" for t in res2["treffer"])


def test_797_kaputte_verknuepfung_wird_gemeldet(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.dokument_zuordnung import (
        pruefe_verknuepfungs_integritaet)
    _doc(db, "d6", "haengt_im_leeren.pdf", linked="__kaputt__")
    kaputt = pruefe_verknuepfungs_integritaet(db)
    assert len(kaputt) == 1
    assert kaputt[0]["dokument_id"] == "d6"


def test_797_tool_liefert_alles_zusammen(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _doc(db, "d7", "angebot_scan.pdf", doc_type="angebot")

    async def _run():
        tool = await mcp.get_tool("dokumente_ohne_bewerbung")
        res = await tool.run({})
        return res.structured_content if hasattr(
            res, "structured_content") else res
    raw = asyncio.run(_run())
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    assert raw["verdaechtige"] >= 1
    assert "hinweis" in raw
