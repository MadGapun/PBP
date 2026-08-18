"""Tests fuer v1.7.17 — #915: Wall-Clock-Budget gegen stille MCP-Haenger.

Belegter Vorfall 17.08.: todo_anlegen/meeting_hinzufuegen blieben je
4 Minuten OHNE Antwort, ohne Wirkung, ohne Fehlermeldung; pbp_mcp_diagnose
war im Ereignisfall selbst nicht erreichbar (sein einziger DB-Zugriff
hing mit). busy_timeout (30 s) haette einen SQLite-Lock als
'database is locked' gemeldet — es kam NICHTS: die Blockade sass auf
Python-Ebene, dagegen hilft nur eine Wall-Clock-Grenze im Tool-Pfad.
"""
import asyncio
import importlib
import os
import shutil
import tempfile
import threading
import time

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1717_915_")
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
    os.environ.pop("PBP_TOOL_BUDGET_SEK", None)
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp_obj, name, args):
    async def _run():
        tool = await mcp_obj.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(
            res, "structured_content") else res
    raw = asyncio.run(_run())
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw


# ------------------------------------------------------ Budget-Helper

def test_915_mit_budget_reicht_ergebnis_durch():
    from bewerbungs_assistent.services.tool_budget import mit_budget

    @mit_budget("demo", lese_tool="demo_anzeigen")
    def schnell(x):
        return {"status": "ok", "x": x}

    assert schnell(7) == {"status": "ok", "x": 7}


def test_915_mit_budget_exception_propagiert():
    from bewerbungs_assistent.services.tool_budget import mit_budget

    @mit_budget("demo", lese_tool="demo_anzeigen")
    def kaputt():
        raise ValueError("kaputt")

    with pytest.raises(ValueError):
        kaputt()


def test_915_mit_budget_timeout_liefert_statuswert():
    """Kern-AK: Blockade -> schemakonformes Ergebnis statt Stille."""
    from bewerbungs_assistent.services import tool_budget
    os.environ["PBP_TOOL_BUDGET_SEK"] = "0.3"
    frei = threading.Event()
    try:
        @tool_budget.mit_budget("demo", lese_tool="demo_anzeigen")
        def haengt():
            frei.wait(timeout=10)
            return {"status": "ok"}

        t0 = time.time()
        res = haengt()
        dauer = time.time() - t0
        assert res["status"] == "timeout", res
        assert dauer < 5, "muss nach dem Budget antworten, nicht ewig warten"
        assert "fehler" in res and "hinweis" in res
        assert "erst" in res["hinweis"] and "demo_anzeigen" in res["hinweis"], \
            "der Idempotenz-Hinweis (erst lesen, dann wiederholen) fehlt"
        assert "hintergrund_tasks" in res
    finally:
        frei.set()
        os.environ.pop("PBP_TOOL_BUDGET_SEK", None)


def test_915_hintergrund_register_wird_im_timeout_benannt():
    from bewerbungs_assistent.services import tool_budget
    from bewerbungs_assistent.services.hintergrund_status import (
        laufender_task, aktuelle_tasks)
    os.environ["PBP_TOOL_BUDGET_SEK"] = "0.3"
    frei = threading.Event()
    gestartet = threading.Event()

    def _hintergrund():
        with laufender_task("auto_engine:auto_refetch_descriptions"):
            gestartet.set()
            frei.wait(timeout=10)

    t = threading.Thread(target=_hintergrund, daemon=True,
                         name="pbp-test-hintergrund")
    t.start()
    try:
        assert gestartet.wait(timeout=5)

        @tool_budget.mit_budget("demo", lese_tool="demo_anzeigen")
        def haengt():
            frei.wait(timeout=10)
            return {}

        res = haengt()
        tasks = [e["task"] for e in res["hintergrund_tasks"]]
        assert "auto_engine:auto_refetch_descriptions" in tasks, res
    finally:
        frei.set()
        t.join(timeout=5)
        os.environ.pop("PBP_TOOL_BUDGET_SEK", None)
    assert aktuelle_tasks() == [] or all(
        not e["task"].startswith("auto_engine:") for e in aktuelle_tasks())


# --------------------------------------------- Tool-Pfad (Regression-AK)

def test_915_meeting_hinzufuegen_laeuft_in_sein_budget(setup_env, monkeypatch):
    """AK: bei kuenstlich gehaltener Blockade liefert meeting_hinzufuegen
    einen Statuswert statt den Client-Timeout zu reissen — und der
    Aufruf wirkt SPAETER genau einmal (kein halber Datensatz, keine
    Dublette durch den einen Aufruf)."""
    db, _ = setup_env
    # WICHTIG: die Tools nutzen das Database-Objekt des SERVER-Moduls
    # (gleiche Datei, anderes Objekt) — der Patch muss dort ansetzen.
    from bewerbungs_assistent import server as srv
    mcp = srv.mcp
    aid = db.add_application({"company": "PLM-Haus Sued AG",
                              "title": "Lead", "status": "interview"})

    frei = threading.Event()
    original_add = srv.db.add_meeting

    def _blockiert(daten):
        frei.wait(timeout=15)  # simulierte Python-Ebene-Blockade
        return original_add(daten)

    monkeypatch.setattr(srv.db, "add_meeting", _blockiert)
    os.environ["PBP_TOOL_BUDGET_SEK"] = "0.5"
    try:
        res = _call(mcp, "meeting_hinzufuegen", {
            "bewerbung_id": aid, "datum": "2026-08-25T10:00",
            "titel": "Zweitgespraech"})
        assert res.get("status") == "timeout", res
        assert "meetings_anzeigen" in res.get("hinweis", "")
        # noch nichts geschrieben — kein halber Datensatz
        assert db.get_meetings_for_application(aid) in ([], None)
    finally:
        frei.set()
        os.environ.pop("PBP_TOOL_BUDGET_SEK", None)
    # der Hintergrund-Write laeuft zu Ende — deshalb der Lese-Hinweis
    for _ in range(50):
        if db.get_meetings_for_application(aid):
            break
        time.sleep(0.1)
    meetings = db.get_meetings_for_application(aid)
    assert len(meetings) == 1, \
        "der eine Aufruf wirkt genau einmal (Idempotenz-Nachweis)"


def test_915_meeting_hinzufuegen_normal_unveraendert(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = db.add_application({"company": "F", "title": "T",
                              "status": "interview"})
    res = _call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-25T10:00",
        "titel": "Erstgespraech"})
    assert res.get("status") != "timeout"
    assert len(db.get_meetings_for_application(aid)) == 1


def test_915_todo_anlegen_hat_budget(setup_env, monkeypatch):
    db, _ = setup_env
    from bewerbungs_assistent import server as srv
    mcp = srv.mcp
    frei = threading.Event()

    def _blockiert(*a, **k):
        frei.wait(timeout=15)
        return "t1"

    monkeypatch.setattr(srv.db, "add_task", _blockiert)
    os.environ["PBP_TOOL_BUDGET_SEK"] = "0.5"
    try:
        res = _call(mcp, "todo_anlegen", {"titel": "Referenzen"})
        assert res.get("status") == "timeout", res
        assert "todos_anzeigen" in res.get("hinweis", "")
    finally:
        frei.set()
        os.environ.pop("PBP_TOOL_BUDGET_SEK", None)


# --------------------------------------------------- Diagnose gehaertet

def test_915_diagnose_antwortet_trotz_db_blockade(setup_env, monkeypatch):
    """Der eigentliche Schmerzpunkt: die Telemetrie war genau dann blind,
    wenn man sie brauchte. Jetzt: Ringpuffer liefert, DB-Teil wird mit
    eigenem Kurzbudget uebersprungen."""
    db, _ = setup_env
    from bewerbungs_assistent import server as srv
    mcp = srv.mcp
    frei = threading.Event()

    def _blockiert():
        frei.wait(timeout=15)
        return {}

    monkeypatch.setattr(srv.db, "get_ollama_accuracy_stats", _blockiert)
    try:
        t0 = time.time()
        res = _call(mcp, "pbp_mcp_diagnose", {"limit": 10})
        dauer = time.time() - t0
        assert res["status"] == "ok", res
        assert dauer < 10, "Diagnose darf nicht am DB-Teil haengen"
        assert res["ollama_genauigkeit"].get("status") == "uebersprungen"
        assert "hintergrund_tasks" in res
    finally:
        frei.set()
