"""#1077 — `stelle_mergen` ueberstimmte eine ausdrueckliche Master-Strategie.

Gemeldet am 23.09.2026: beim Master war die Entfernung BEWUSST leer (der
Antritt am Wohnort ist moeglich, die Anzeige nennt formal einen Ort rund
390 km entfernt). `feld_strategie={"distance_km": "master", ...}` wurde
ignoriert, die Stelle stand danach mit 386 km im Bestand — und liess sich
ueber kein Werkzeug mehr korrigieren.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest

MASTER = {
    "hash": "m1077master0001",
    "title": "Functional Consultant Engineering und PLM",
    "company": "Musterfertigung GmbH",
    "location": "Antritt am Konzernstandort am Wohnort moeglich",
    "url": "https://example.com/stelle/1",
    "source": "manuell",
    "description": "Master-Beschreibung der Vakanz.",
    "score": 8,
}
DUPLIKAT = {
    "hash": "d1077duplikat01",
    "title": "Business Application Manager PLM und Engineering",
    "company": "Musterfertigung GmbH",
    "location": "Musterstadt Sued",
    "url": "https://example.com/stelle/2",
    "source": "jobspy_linkedin",
    "description": "Duplikat-Beschreibung der Vakanz.",
    "score": 9,
    "distance_km": 386.3,
    "lat": 48.1,
    "lon": 11.5,
}


@pytest.fixture
def zwei(tmp_db):
    db = tmp_db
    db.save_profile({"name": "Test"})
    db.save_jobs([dict(MASTER), dict(DUPLIKAT)])
    return db


def _job(db, h):
    return db.get_job(db.resolve_job_hash(h))


def test_1077_der_gemeldete_aufruf_laesst_die_entfernung_leer(zwei):
    db = zwei
    plan = db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"], field_strategy={
        "description": "merge", "distance_km": "master",
        "lat": "master", "lon": "master"}, dry_run=False)
    assert plan["status"] == "ok", plan
    m = _job(db, MASTER["hash"])
    assert m["distance_km"] is None
    assert m["lat"] is None and m["lon"] is None


def test_1077_ausdrueckliches_master_gewinnt_auch_ohne_ortsbezug(zwei):
    """Die Strategie allein genuegt, auch wenn der Ort nicht abweicht."""
    db = zwei
    db.update_job(MASTER["hash"], {"location": DUPLIKAT["location"]})
    plan = db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"],
                         field_strategy={"distance_km": "master"})
    assert plan["feld_entscheidungen"]["distance_km"]["quelle"] == "master"
    assert "distance_km" not in plan["neue_werte"]


def test_1077_ohne_strategie_folgt_die_entfernung_dem_ort(zwei):
    """Kommt `location` vom Master, kommen distance/lat/lon nicht vom Duplikat."""
    db = zwei
    plan = db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"])
    for f in ("distance_km", "lat", "lon"):
        assert plan["feld_entscheidungen"][f]["quelle"] == "master_ort", f
        assert f not in plan["neue_werte"]


def test_1077_gleicher_ort_uebernimmt_die_entfernung_weiter(zwei):
    """Die Gegenrichtung: ohne Ortsabweichung bleibt das alte Verhalten."""
    db = zwei
    db.update_job(MASTER["hash"], {"location": DUPLIKAT["location"]})
    plan = db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"])
    assert plan["neue_werte"]["distance_km"] == 386.3
    assert plan["feld_entscheidungen"]["distance_km"]["quelle"] == "duplikat_auto"


def test_1077_ort_vom_duplikat_nimmt_die_entfernung_mit(zwei):
    db = zwei
    plan = db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"],
                         field_strategy={"location": "duplikat"})
    assert plan["neue_werte"]["location"] == DUPLIKAT["location"]
    assert plan["neue_werte"]["distance_km"] == 386.3


def test_1077_null_km_ist_ein_wert(zwei):
    """0 km heisst "am Wohnort" und darf nicht als Leerfeld gelten."""
    db = zwei
    db.update_job(MASTER["hash"], {"location": DUPLIKAT["location"]})
    db.set_job_entfernung(MASTER["hash"], 0)
    plan = db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"])
    assert plan["feld_entscheidungen"]["distance_km"]["nachher"] == 0


def test_1077_vorschau_nennt_die_automatisch_uebernommenen_felder(zwei):
    db = zwei
    db.update_job(MASTER["hash"], {"location": DUPLIKAT["location"]})
    plan = db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"])
    block = plan["ohne_rueckfrage_uebernommen"]
    assert "distance_km" in block["felder"]
    assert "'master'" in block["hinweis"]


def test_1077_verknuepfungen_und_fundstellen_gehen_mit(zwei):
    """`application_jobs` (#764) und `job_sources` (#951) zeigten danach
    auf eine geloeschte Stelle."""
    db = zwei
    app_id = db.add_application({"title": "x", "company": "y",
                                 "status": "beworben"})
    db.link_application_to_job(app_id, DUPLIKAT["hash"], is_primary=True)
    dup_st = db.resolve_job_hash(DUPLIKAT["hash"])
    master_st = db.resolve_job_hash(MASTER["hash"])
    conn = db.connect()
    vorher = conn.execute("SELECT COUNT(*) FROM job_sources WHERE job_hash=?",
                          (dup_st,)).fetchone()[0]
    assert vorher >= 1
    plan = db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"], dry_run=False)
    assert plan["umgehaengte_bezuege"].get("application_jobs") == 1
    for tab in ("application_jobs", "job_sources"):
        rest = conn.execute(f"SELECT COUNT(*) FROM {tab} WHERE job_hash=?",
                            (dup_st,)).fetchone()[0]
        assert rest == 0, tab
    zeile = conn.execute(
        "SELECT is_primary FROM application_jobs WHERE application_id=? "
        "AND job_hash=?", (app_id, master_st)).fetchone()
    assert zeile and zeile["is_primary"] == 1
    assert db.get_application(app_id)["job_hash"] in (master_st,
                                                      MASTER["hash"])


def test_1077_primaer_bleibt_primaer_wenn_beide_verknuepft_sind(zwei):
    """Haengt die Bewerbung an beiden Stellen, faellt die Zeile zum
    Duplikat als Doppelung weg — ihre Primaer-Markierung darf nicht mit."""
    db = zwei
    app_id = db.add_application({"title": "x", "company": "y",
                                 "status": "beworben"})
    db.link_application_to_job(app_id, MASTER["hash"], is_primary=False)
    db.link_application_to_job(app_id, DUPLIKAT["hash"], is_primary=True)
    db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"], dry_run=False)
    zeilen = db.connect().execute(
        "SELECT job_hash, is_primary FROM application_jobs "
        "WHERE application_id=?", (app_id,)).fetchall()
    assert [(z["job_hash"], z["is_primary"]) for z in zeilen] == [
        (db.resolve_job_hash(MASTER["hash"]), 1)]


def test_1077_handentfernung_ueberlebt_den_naechsten_suchlauf(zwei):
    db = zwei
    db.set_job_entfernung(MASTER["hash"], 0)
    wieder = dict(MASTER, distance_km=390.0, lat=48.0, lon=11.0)
    db.save_jobs([wieder])
    m = _job(db, MASTER["hash"])
    assert m["distance_km"] == 0
    assert m["entfernung_quelle"] == "mensch"


def test_1077_zuruecksetzen_gibt_die_entfernung_frei(zwei):
    db = zwei
    db.set_job_entfernung(MASTER["hash"], 5)
    db.set_job_entfernung(MASTER["hash"], None)
    db.save_jobs([dict(MASTER, distance_km=42.0)])
    m = _job(db, MASTER["hash"])
    assert m["distance_km"] == 42.0
    assert not m.get("entfernung_quelle")


# ===== Werkzeug ==========================================================

@pytest.fixture
def mcp_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17126_1077_")
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
    db.save_jobs([dict(DUPLIKAT)])
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


def test_1077_entfernung_ist_ueber_mcp_setzbar(mcp_env):
    db, mcp = mcp_env
    res = _call(mcp, "stelle_bearbeiten", {
        "job_hash": DUPLIKAT["hash"], "entfernung_km": 0})
    assert res["status"] == "aktualisiert", res
    assert res["entfernung"]["quelle"] == "mensch"
    assert _job(db, DUPLIKAT["hash"])["distance_km"] == 0
    res = _call(mcp, "stelle_bearbeiten", {
        "job_hash": DUPLIKAT["hash"], "entfernung_zuruecksetzen": True})
    assert _job(db, DUPLIKAT["hash"])["distance_km"] is None


def test_1077_negative_entfernung_wird_abgewiesen(mcp_env):
    db, mcp = mcp_env
    res = _call(mcp, "stelle_bearbeiten", {
        "job_hash": DUPLIKAT["hash"], "entfernung_km": -1})
    assert "fehler" in res
    assert _job(db, DUPLIKAT["hash"])["distance_km"] == 386.3


def test_1077_ortswechsel_nennt_die_alte_entfernung(mcp_env):
    db, mcp = mcp_env
    res = _call(mcp, "stelle_bearbeiten", {
        "job_hash": DUPLIKAT["hash"], "ort": "Anderswo"})
    assert "386.3" in res["entfernung_hinweis"]


def test_1077_kontaktverweise_wandern_zum_master(zwei):
    """`contact_links` ist polymorph und hat keine `job_hash`-Spalte."""
    db = zwei
    cid = db.add_contact({"full_name": "Person Muster",
                          "company": "Musterfertigung GmbH"})
    db.link_contact(cid, "job", db.resolve_job_hash(DUPLIKAT["hash"]))
    db.merge_jobs(MASTER["hash"], DUPLIKAT["hash"], dry_run=False)
    ziel = db.connect().execute(
        "SELECT target_id FROM contact_links WHERE contact_id=? "
        "AND target_kind='job'", (cid,)).fetchall()
    assert [r["target_id"] for r in ziel] == [db.resolve_job_hash(MASTER["hash"])]
