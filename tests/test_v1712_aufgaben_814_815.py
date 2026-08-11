"""Tests fuer v1.7.12 — #814/#815 (D35): Aufgaben vollwertig bedienbar.

Belegte Befunde 11.08.2026: 5 Aufgaben auf 94 Bewerbungen (Zugangs-
problem, kein Nutzungsmuster); kein Weg, ein Faelligkeitsdatum zu
aendern; Status 'hinfaellig' existierte ohne Tool, das ihn setzt;
Aufgaben ohne Bewerbungsbezug im Datenmodell unmoeglich; drei Toepfe
ohne gemeinsame Sicht.
"""
import asyncio
import importlib
import os
import shutil
import tempfile
from datetime import date, timedelta

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_814_")
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


def test_815_aufgabe_ohne_bewerbung(setup_env):
    """DER Datenmodell-Punkt: bewerbung_id ist optional."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "todo_anlegen", {
        "titel": "Lebenslauf-Variante Freelance aktualisieren"}))
    assert res["status"] == "angelegt", res
    assert res.get("bewerbungsbezug") == "keiner (freie Aufgabe)"
    task = db.get_task(res["task_id"])
    assert task["application_id"] is None
    # abhaken funktioniert genauso
    done = _result(_call(mcp, "todo_erledigen",
                         {"todo_id": res["task_id"]}))
    assert done["status"] == "erledigt"


def test_815_bestands_migration_loest_not_null(setup_env):
    """Gewachsene DBs tragen NOT NULL aus v45 — das Safety-Net loest es."""
    db, _ = setup_env
    info = {r["name"]: r["notnull"] for r in db.connect().execute(
        "PRAGMA table_info(tasks)").fetchall()}
    assert info.get("application_id") == 0, \
        "application_id muss nullable sein"


def test_814_todo_bearbeiten_faelligkeit(setup_env):
    """Es gab KEINEN Weg, ein Faelligkeitsdatum zu aendern."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "todo_anlegen", {
        "titel": "Gehalt recherchieren", "faellig_am": "2026-08-15"}))
    tid = res["task_id"]
    upd = _result(_call(mcp, "todo_bearbeiten", {
        "todo_id": tid, "faellig_am": "2026-08-22",
        "titel": "Gehaltsspanne recherchieren"}))
    assert upd["status"] == "aktualisiert"
    task = db.get_task(tid)
    assert task["faellig_am"] == "2026-08-22"
    assert task["titel"] == "Gehaltsspanne recherchieren"
    # '-' loescht die Faelligkeit
    _call(mcp, "todo_bearbeiten", {"todo_id": tid, "faellig_am": "-"})
    assert db.get_task(tid)["faellig_am"] is None


def test_814_todo_hinfaellig(setup_env):
    """Der Status existierte, das Tool nicht."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "todo_anlegen", {"titel": "Nachfassen"}))
    hin = _result(_call(mcp, "todo_hinfaellig", {
        "todo_id": res["task_id"], "grund": "Absage erhalten"}))
    assert hin["status"] == "hinfaellig"
    task = db.get_task(res["task_id"])
    assert task["status"] == "hinfaellig"
    assert task["notiz"] == "Absage erhalten"
    # reaktivieren geht weiter
    re = _result(_call(mcp, "todo_reaktivieren", {"todo_id": res["task_id"]}))
    assert re["status"] == "offen"


def test_814_todo_details_mit_kontext(setup_env):
    """Wer eine Aufgabe oeffnet, will handeln — alles in EINER Ansicht."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = db.add_application({
        "company": "Halbleiterwerk Nord GmbH", "title": "PLM Lead",
        "status": "interview", "ansprechpartner": "Erik Mustermann",
        "kontakt_email": "bewerbung@firma.de"})
    kid = db.add_contact({"full_name": "Erik Mustermann",
                          "company": "Halbleiterwerk Nord GmbH",
                          "email": "bewerbung@firma.de"})
    db.link_contact(kid, "application", aid, role="Entscheider")
    db.add_meeting({"application_id": aid,
                    "meeting_date": "2026-08-20T14:00:00",
                    "title": "Zweitgespraech", "meeting_type": "interview"})
    res = _result(_call(mcp, "todo_anlegen", {
        "titel": "Feedbackbogen senden", "bewerbung_id": aid}))
    det = _result(_call(mcp, "todo_details", {"todo_id": res["task_id"]}))
    assert det["bewerbung"]["firma"] == "Halbleiterwerk Nord GmbH"
    assert det["kontakte"][0]["email"] == "bewerbung@firma.de", \
        "Mailadresse gehoert in die Detailansicht"
    assert det["termine"][0]["titel"] == "Zweitgespraech"


def test_815_aufgaben_uebersicht_vereint_drei_toepfe(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = db.add_application({"company": "Werft Nord", "title": "Lead",
                              "status": "beworben"})
    gestern = (date.today() - timedelta(days=3)).isoformat()
    morgen = (date.today() + timedelta(days=1)).isoformat()
    _call(mcp, "todo_anlegen", {"titel": "Ueberfaellige Aufgabe",
                                "bewerbung_id": aid,
                                "faellig_am": gestern})
    db.add_follow_up(aid, morgen, "nachfass", template="Kurz nachfragen.")
    db.add_meeting({"application_id": aid,
                    "meeting_date": f"{morgen}T10:00:00",
                    "title": "Interview", "meeting_type": "interview"})
    res = _result(_call(mcp, "aufgaben_uebersicht", {}))
    assert res["anzahl"] >= 3
    herkuenfte = set()
    for gruppe in res["gruppen"].values():
        for e in gruppe:
            herkuenfte.add(e["herkunft"])
    assert {"todo", "nachfass", "termin"} <= herkuenfte, herkuenfte
    ueber = res["gruppen"]["ueberfaellig"]
    assert any(e["titel"] == "Ueberfaellige Aufgabe"
               and e["ueberfaellig_seit_tagen"] == 3 for e in ueber)
    assert res["ueberfaellig_anzahl"] >= 1


def test_815_rest_aufgaben_und_task_ops(setup_env):
    db, _ = setup_env
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)

    # Freie Aufgabe per REST
    r = client.post("/api/tasks", json={"titel": "Suchkriterien schaerfen",
                                        "faellig_am": "2026-08-20"})
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    # Verschieben per PATCH
    r2 = client.patch(f"/api/tasks/{tid}",
                      json={"faellig_am": "2026-08-25"})
    assert r2.status_code == 200
    assert r2.json()["task"]["faellig_am"] == "2026-08-25"

    # Hinfaellig
    r3 = client.post(f"/api/tasks/{tid}/hinfaellig",
                     json={"grund": "hat sich erledigt"})
    assert r3.status_code == 200
    assert db.get_task(tid)["status"] == "hinfaellig"

    # Uebersicht
    r4 = client.get("/api/aufgaben?status=alle")
    assert r4.status_code == 200
    assert "gruppen" in r4.json()
