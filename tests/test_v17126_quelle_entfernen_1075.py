"""#1075 — Stellen abgewaehlter Quellen liessen sich nicht entfernen.

Es gab nur Aussortieren (die Zeile bleibt und zaehlt weiter in Statistik
und Schwellen-Stufen) oder `daten_bereiche_leeren(['stellen'])` (der ganze
Bestand). Beim Melder: 2.600 Stellen samt Historie, um 62 loszuwerden.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17126_1075_")
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
    db.set_profile_setting("active_sources", ["bundesagentur"])
    db.save_jobs([
        {"hash": f"h1075{i}", "title": f"Projekt {i}", "company": "Vermittler",
         "location": "Remote", "url": f"https://example.com/h{i}",
         "source": "hays", "description": "Text"} for i in range(4)
    ] + [{"hash": "b1075", "title": "Sachbearbeitung", "company": "Amt",
          "location": "Hamburg", "url": "https://example.com/b",
          "source": "bundesagentur", "description": "Text"}])
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _anzahl(db, quelle):
    return db.connect().execute(
        "SELECT COUNT(*) FROM jobs WHERE source=?", (quelle,)).fetchone()[0]


def test_1075_vorschau_loescht_nichts(env):
    db, mcp = env
    db.dismiss_job("h10750", "falsches_fachgebiet")
    res = _call(mcp, "stellen_entfernen_nach_quelle", {"quelle": "hays"})
    assert res["status"] == "vorschau"
    assert res["zu_entfernen"] == 4
    assert res["davon_aussortiert"] == 1 and res["davon_aktiv"] == 3
    assert _anzahl(db, "hays") == 4


def test_1075_entfernt_nur_die_quelle_und_ihre_fundstellen(env):
    db, mcp = env
    hashes = [db.resolve_job_hash(f"h1075{i}") for i in range(4)]
    res = _call(mcp, "stellen_entfernen_nach_quelle",
                {"quelle": "hays", "dry_run": False})
    assert res["status"] == "entfernt" and res["zu_entfernen"] == 4
    assert _anzahl(db, "hays") == 0
    assert _anzahl(db, "bundesagentur") == 1
    platz = ",".join("?" * len(hashes))
    rest = db.connect().execute(
        f"SELECT COUNT(*) FROM job_sources WHERE job_hash IN ({platz})",
        hashes).fetchone()[0]
    assert rest == 0, "Fundstellen muessen mitgehen"
    assert res["geloeschte_bezuege"].get("job_sources") == 4


def test_1075_stelle_mit_bewerbung_bleibt(env):
    db, mcp = env
    app_id = db.add_application({"title": "Projekt 1", "company": "Vermittler",
                                 "status": "beworben"})
    db.link_application_to_job(app_id, "h10751", is_primary=True)
    res = _call(mcp, "stellen_entfernen_nach_quelle",
                {"quelle": "hays", "dry_run": False})
    assert res["bleiben_gruende"]["bewerbung"] == 1
    assert db.get_job(db.resolve_job_hash("h10751")) is not None
    assert _anzahl(db, "hays") == 1


def test_1075_stelle_einer_gewaehlten_quelle_bleibt(env):
    db, mcp = env
    conn = db.connect()
    conn.execute(
        "INSERT INTO job_sources (job_hash, source, url, gefunden_am) "
        "VALUES (?, 'bundesagentur', 'https://example.com/x', '2026-09-23')",
        (db.resolve_job_hash("h10752"),))
    conn.commit()
    res = _call(mcp, "stellen_entfernen_nach_quelle", {"quelle": "hays"})
    assert res["bleiben_gruende"]["weitere_fundstelle"] == 1
    assert res["zu_entfernen"] == 3


def test_1075_fundstelle_einer_abgewaehlten_quelle_schuetzt_nicht(env):
    db, mcp = env
    conn = db.connect()
    conn.execute(
        "INSERT INTO job_sources (job_hash, source, url, gefunden_am) "
        "VALUES (?, 'gulp', 'https://example.com/g', '2026-09-23')",
        (db.resolve_job_hash("h10752"),))
    conn.commit()
    res = _call(mcp, "stellen_entfernen_nach_quelle", {"quelle": "hays"})
    assert res["zu_entfernen"] == 4


def test_1075_kontaktverweise_gehen_mit_der_kontakt_bleibt(env):
    db, mcp = env
    cid = db.add_contact({"full_name": "Person Muster", "company": "Vermittler"})
    db.link_contact(cid, "job", db.resolve_job_hash("h10753"))
    _call(mcp, "stellen_entfernen_nach_quelle", {"quelle": "hays", "dry_run": False})
    links = db.connect().execute(
        "SELECT COUNT(*) FROM contact_links WHERE target_kind='job'").fetchone()[0]
    assert links == 0
    assert db.connect().execute(
        "SELECT COUNT(*) FROM contacts WHERE id=?", (cid,)).fetchone()[0] == 1


def test_1075_gewaehlte_quelle_bekommt_eine_warnung(env):
    db, mcp = env
    res = _call(mcp, "stellen_entfernen_nach_quelle", {"quelle": "bundesagentur"})
    assert "noch ausgewaehlt" in res["warnung"]


def test_1075_rest_weg(env):
    db, _ = env
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    alt = dash._db
    dash._db = db
    try:
        c = TestClient(dash.app)
        v = c.get("/api/sources/hays/stellen").json()
        assert v["zu_entfernen"] == 4 and _anzahl(db, "hays") == 4
        r = c.post("/api/sources/hays/stellen-entfernen", json={}).json()
        assert r["status"] == "entfernt" and _anzahl(db, "hays") == 0
    finally:
        dash._db = alt


def test_1075_das_dashboard_bietet_es_beim_abwaehlen_an():
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "frontend" / "src" /
              "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert "if (!checked) await offerRemoveSourceJobs(source);" in quelle
    assert "/stellen-entfernen" in quelle
