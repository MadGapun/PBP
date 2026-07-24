"""Tests fuer v1.7.10 — #783 (B28): Suchperformance aus Bestandsdaten.

Kern-These des Issues: Die Kennzahl ist die Bewerbungsquote pro Quelle,
nicht die Trefferzahl. Eine Quelle mit 7 Treffern und 2 Bewerbungen ist
besser als eine mit 100 Treffern und 0.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1710_783_")
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


def _lage(db):
    conn = db.connect()
    pid = db.get_active_profile_id()
    # Quelle 'masse': 12 Funde, alle aussortiert, 0 Bewerbungen
    for i in range(12):
        conn.execute(
            "INSERT INTO jobs (hash, title, company, location, url, source, "
            "description, is_active, dismiss_reason, profile_id, found_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,0,'falsches_fachgebiet',?,'2026-06-01','2026-06-01')",
            (f"m{i}", f"Rolle {i}", "MasseCo", "HH", f"https://x.example/{i}",
             "masse", "Text. " * 20, pid))
    # Quelle 'klasse': 3 Funde, 2 fuehrten zu Bewerbungen, 1 Interview
    for i in range(3):
        conn.execute(
            "INSERT INTO jobs (hash, title, company, location, url, source, "
            "description, is_active, profile_id, found_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,1,?,'2026-06-01','2026-06-01')",
            (f"k{i}", f"PLM Rolle {i}", f"KlasseCo {i}", "HH",
             f"https://y.example/{i}", "klasse", "PLM. " * 20, pid))
    conn.commit()
    a1 = db.add_application({"company": "KlasseCo 0", "title": "PLM Rolle 0",
                             "job_hash": db.resolve_job_hash("k0"),
                             "status": "beworben", "applied_at": "2026-06-10"})
    a2 = db.add_application({"company": "KlasseCo 1", "title": "PLM Rolle 1",
                             "job_hash": db.resolve_job_hash("k1"),
                             "status": "interview", "applied_at": "2026-06-12"})
    conn.execute("UPDATE applications SET has_reached_interview=1 WHERE id=?", (a2,))
    conn.commit()
    return a1, a2


def test_783_bewerbungsquote_schlaegt_trefferzahl(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _lage(db)
    res = _result(_call(mcp, "suchperformance_auswerten", {}))
    q = res["quellen"]
    assert q["masse"]["gefunden"] == 12
    assert q["masse"]["beworben"] == 0
    assert q["klasse"]["gefunden"] == 3
    assert q["klasse"]["beworben"] == 2
    assert q["klasse"]["interviews"] == 1
    assert res["ranking_nach_bewerbungsquote"][0] == "klasse"
    assert "masse" in res["quellen_ohne_einzige_bewerbung"]
    assert q["masse"]["top_aussortier_gruende"].get("falsches_fachgebiet") == 12


def test_783_bewerbung_ohne_stelle_faellt_auf_source_zurueck(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _lage(db)
    aid = db.add_application({"company": "Netzwerk AG", "title": "Direkt",
                              "status": "beworben", "applied_at": "2026-06-15"})
    db.update_application(aid, {"source": "netzwerk"})
    res = _result(_call(mcp, "suchperformance_auswerten", {}))
    assert res["quellen"]["netzwerk"]["beworben"] == 1


def test_783_grenze_ist_benannt(setup_env):
    """Ehrlichkeit: Query-Ebene ist v1.8 — steht im Result."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "suchperformance_auswerten", {}))
    assert "Quellen-Ebene" in res["grenze"]
