"""Regression #764: applications.job_hash und application_jobs synchron halten.

Belegter Fall (Session 23.07.2026): Eine Bewerbung wurde von einer veralteten
StepStone-Anzeige auf den Repost umgehaengt. Danach:

    application_jobs:      [(...74d6b33b42cf, is_primary=1)]   <- korrekt
    applications.job_hash:  ...68cedc24d008                     <- unveraendert alt

Die UI liest `job_hash` und zeigte weiter die alte Version (toter Link,
Score 39 statt 45). Fuehrend ist ab v1.7.9 `application_jobs`; die
Legacy-Spalte wird synchron mitgezogen.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v179_764_")
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


def _stelle(db, hash_, titel, url):
    db.save_jobs([{
        "hash": hash_, "title": titel, "company": "Nordwind Pharma",
        "location": "Beispielstadt", "url": url, "source": "demo",
        "description": "PLM Rolle mit SAP-Bezug. " * 20,
        "employment_type": "festanstellung",
    }])


def _job_hash(db, aid):
    row = db.connect().execute(
        "SELECT job_hash FROM applications WHERE id=?", (aid,)).fetchone()
    return (row["job_hash"] or "") if row else ""


def _junction(db, aid):
    return [dict(r) for r in db.connect().execute(
        "SELECT job_hash, is_primary FROM application_jobs WHERE application_id=?",
        (aid,)).fetchall()]


def test_764_neue_bewerbung_bekommt_junction_eintrag(setup_env):
    """Ohne das lief die Junction fuer alles seit v34 strukturell leer."""
    db, _ = setup_env
    _stelle(db, "alt1", "PLM Manager", "https://example.de/alt")
    aid = db.add_application({"company": "Nordwind Pharma", "title": "PLM Manager",
                              "job_hash": "alt1"})
    links = _junction(db, aid)
    assert len(links) == 1, f"kein Junction-Eintrag angelegt: {links}"
    assert links[0]["is_primary"] == 1


def test_764_umhaengen_zieht_job_hash_mit(setup_env):
    """Der Kernfall aus dem Issue: verknuepfen(ist_primaer=True) + entknuepfen."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _stelle(db, "alt2", "PLM Manager (alt)", "https://stepstone.de/tot")
    _stelle(db, "neu2", "PLM Manager (Repost)", "https://careers.example.com/job/1")
    aid = db.add_application({"company": "Nordwind Pharma", "title": "PLM Manager",
                              "job_hash": "alt2"})

    _call(mcp, "bewerbung_stelle_verknuepfen",
          {"bewerbung_id": aid, "stellen_hash": "neu2", "ist_primaer": True})
    assert _job_hash(db, aid).endswith("neu2"), (
        f"job_hash nicht mitgezogen: {_job_hash(db, aid)}")

    _call(mcp, "bewerbung_stelle_entknuepfen",
          {"bewerbung_id": aid, "stellen_hash": "alt2"})
    assert _job_hash(db, aid).endswith("neu2")
    assert all(not l["job_hash"].endswith("alt2") for l in _junction(db, aid))


def test_764_entknuepfen_der_primaeren_laesst_keinen_waisen_zurueck(setup_env):
    """AK: nach Entknuepfen der primaeren Stelle kein verwaister Verweis."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _stelle(db, "p1", "PLM A", "https://example.de/a")
    _stelle(db, "p2", "PLM B", "https://example.de/b")
    aid = db.add_application({"company": "Nordwind Pharma", "title": "PLM A",
                              "job_hash": "p1"})
    _call(mcp, "bewerbung_stelle_verknuepfen",
          {"bewerbung_id": aid, "stellen_hash": "p2"})

    _call(mcp, "bewerbung_stelle_entknuepfen",
          {"bewerbung_id": aid, "stellen_hash": "p1"})
    jh = _job_hash(db, aid)
    assert jh.endswith("p2"), f"job_hash zeigt auf entknuepfte Stelle: {jh}"


def test_764_letzte_verknuepfung_entfernt_leert_job_hash(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _stelle(db, "solo", "PLM Solo", "https://example.de/solo")
    aid = db.add_application({"company": "Nordwind Pharma", "title": "PLM Solo",
                              "job_hash": "solo"})
    _call(mcp, "bewerbung_stelle_entknuepfen",
          {"bewerbung_id": aid, "stellen_hash": "solo"})
    assert _job_hash(db, aid) == "", "verwaister job_hash nach letzter Entknuepfung"


def test_764_heilung_traegt_fehlende_junction_nach(setup_env):
    """Fall `2dbd0571`: job_hash gesetzt, Junction leer."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _stelle(db, "h1", "PLM Manager", "https://example.de/h1")
    aid = db.add_application({"company": "Nordwind Pharma", "title": "PLM Manager",
                              "job_hash": "h1"})
    db.connect().execute("DELETE FROM application_jobs WHERE application_id=?", (aid,))
    db.connect().commit()
    assert _junction(db, aid) == []

    res = _result(_call(mcp, "bewerbungs_stellen_abgleichen", {"dry_run": False}))
    assert res["status"] == "ausgefuehrt"
    links = _junction(db, aid)
    assert len(links) == 1 and links[0]["is_primary"] == 1, res


def test_764_heilung_zieht_divergenz_auf_junction(setup_env):
    """Junction ist fuehrend: abweichender job_hash wird darauf gezogen."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _stelle(db, "d1", "PLM alt", "https://example.de/d1")
    _stelle(db, "d2", "PLM neu", "https://example.de/d2")
    aid = db.add_application({"company": "Nordwind Pharma", "title": "PLM",
                              "job_hash": "d1"})
    # Divergenz kuenstlich erzeugen (wie sie vor dem Fix entstand)
    conn = db.connect()
    conn.execute("UPDATE application_jobs SET job_hash=? WHERE application_id=?",
                 (db.resolve_job_hash("d2"), aid))
    conn.commit()

    _call(mcp, "bewerbungs_stellen_abgleichen", {"dry_run": False})
    assert _job_hash(db, aid).endswith("d2")


def test_764_heilung_ist_idempotent(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _stelle(db, "i1", "PLM", "https://example.de/i1")
    aid = db.add_application({"company": "Nordwind Pharma", "title": "PLM",
                              "job_hash": "i1"})
    db.connect().execute("DELETE FROM application_jobs WHERE application_id=?", (aid,))
    db.connect().commit()
    _call(mcp, "bewerbungs_stellen_abgleichen", {"dry_run": False})
    zweit = _result(_call(mcp, "bewerbungs_stellen_abgleichen", {"dry_run": False}))
    assert zweit["count_abweichungen"] == 0, f"nicht idempotent: {zweit}"


def test_764_dry_run_schreibt_nicht(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _stelle(db, "dr1", "PLM", "https://example.de/dr1")
    aid = db.add_application({"company": "Nordwind Pharma", "title": "PLM",
                              "job_hash": "dr1"})
    db.connect().execute("DELETE FROM application_jobs WHERE application_id=?", (aid,))
    db.connect().commit()
    res = _result(_call(mcp, "bewerbungs_stellen_abgleichen", {}))
    assert res["status"] == "vorschau"
    assert _junction(db, aid) == [], "dry_run darf nicht schreiben"


def test_764_ui_und_tool_zeigen_dieselbe_stelle(setup_env):
    """AK: nach Umhaengen liefern beide Datenpfade dieselbe Stelle."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _stelle(db, "u1", "PLM alt", "https://stepstone.de/tot")
    _stelle(db, "u2", "PLM neu", "https://careers.example.com/job/9")
    aid = db.add_application({"company": "Nordwind Pharma", "title": "PLM",
                              "job_hash": "u1"})
    _call(mcp, "bewerbung_stelle_verknuepfen",
          {"bewerbung_id": aid, "stellen_hash": "u2", "ist_primaer": True})
    _call(mcp, "bewerbung_stelle_entknuepfen",
          {"bewerbung_id": aid, "stellen_hash": "u1"})

    # Pfad 1: was die UI/Timeline liest
    ui_stelle = db.get_job(_job_hash(db, aid))
    # Pfad 2: was bewerbung_stellen_anzeigen liefert
    tool_stellen = db.get_jobs_for_application(aid)
    assert len(tool_stellen) == 1
    assert ui_stelle["url"] == tool_stellen[0]["url"], (
        "UI und Tool zeigen unterschiedliche Stellen — genau der gemeldete Bug"
    )
