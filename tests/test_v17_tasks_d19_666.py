"""Tests fuer Issue #666 (D19, beta.85) — Task-/Todo-System pro Bewerbung.

Schema v44->v45: neue tasks-Tabelle. Backend-Tools:
  todo_anlegen, todo_erledigen, todo_reaktivieren, todos_anzeigen
"""
from __future__ import annotations

import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register(tmp_db):
    from bewerbungs_assistent.tools.tasks import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _make_app(tmp_db):
    return tmp_db.add_application({
        "title": "Stelle X", "company": "Firma X",
        "url": "", "job_hash": None, "status": "beworben",
        "applied_at": "2026-05-01", "notes": "",
        "bewerbungsart": "mit_dokumenten", "lebenslauf_variante": "standard",
        "profile_id": tmp_db.get_active_profile_id(),
    })


# ── Schema ───────────────────────────────────────────────────────────────


def test_tasks_table_exists(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    conn = tmp_db.connect()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    for expected in ("id", "application_id", "titel", "status", "typ", "faellig_am"):
        assert expected in cols


# ── todo_anlegen ─────────────────────────────────────────────────────────


def test_todo_anlegen_minimal(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["todo_anlegen"]

    result = fn(bewerbung_id=aid, titel="Gehalt recherchieren")
    assert result["status"] == "angelegt"
    assert "task_id" in result
    assert result["typ"] == "custom"


def test_todo_anlegen_mit_faelligkeit(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["todo_anlegen"]

    result = fn(
        bewerbung_id=aid, titel="Interview-Vorbereitung",
        faellig_am="2026-06-10", typ="vorbereitung",
    )
    assert result["faellig_am"] == "2026-06-10"
    assert result["typ"] == "vorbereitung"


def test_todo_anlegen_fehler_ohne_titel(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["todo_anlegen"]

    result = fn(bewerbung_id=aid, titel="")
    assert "fehler" in result


def test_todo_anlegen_fehler_unbekannte_bewerbung(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register(tmp_db)
    fn = mcp.tools["todo_anlegen"]

    result = fn(bewerbung_id="nope", titel="x")
    assert "fehler" in result


def test_todo_anlegen_normalisiert_unbekannten_typ(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["todo_anlegen"]

    result = fn(bewerbung_id=aid, titel="x", typ="erfunden")
    # In DB landet 'custom' (normalisiert) — Tool gibt aber den Input zurueck
    # weil die Normalisierung in db.add_task passiert
    task = tmp_db.get_task(result["task_id"])
    assert task["typ"] == "custom"


# ── todo_erledigen ───────────────────────────────────────────────────────


def test_todo_erledigen_setzt_status(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    anlegen = mcp.tools["todo_anlegen"]
    erledigen = mcp.tools["todo_erledigen"]

    r = anlegen(bewerbung_id=aid, titel="x")
    tid = r["task_id"]

    result = erledigen(todo_id=tid, notiz="erledigt im Workshop")
    assert result["status"] == "erledigt"

    task = tmp_db.get_task(tid)
    assert task["status"] == "erledigt"
    assert task["erledigt_am"]
    assert task["notiz"] == "erledigt im Workshop"


def test_todo_erledigen_idempotent(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    anlegen = mcp.tools["todo_anlegen"]
    erledigen = mcp.tools["todo_erledigen"]

    r = anlegen(bewerbung_id=aid, titel="x")
    erledigen(todo_id=r["task_id"])
    again = erledigen(todo_id=r["task_id"])
    assert again["status"] == "bereits_erledigt"


# ── todo_reaktivieren ────────────────────────────────────────────────────


def test_todo_reaktivieren_setzt_zurueck(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    anlegen = mcp.tools["todo_anlegen"]
    erledigen = mcp.tools["todo_erledigen"]
    reaktivieren = mcp.tools["todo_reaktivieren"]

    r = anlegen(bewerbung_id=aid, titel="x")
    erledigen(todo_id=r["task_id"])
    result = reaktivieren(todo_id=r["task_id"])
    assert result["status"] == "offen"

    task = tmp_db.get_task(r["task_id"])
    assert task["status"] == "offen"
    assert task["erledigt_am"] is None


# ── todos_anzeigen ───────────────────────────────────────────────────────


def test_todos_anzeigen_all(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid1 = _make_app(tmp_db)
    aid2 = _make_app(tmp_db)
    mcp = _register(tmp_db)
    anlegen = mcp.tools["todo_anlegen"]
    anzeigen = mcp.tools["todos_anzeigen"]

    anlegen(bewerbung_id=aid1, titel="A")
    anlegen(bewerbung_id=aid2, titel="B")

    result = anzeigen()
    assert result["anzahl"] == 2


def test_todos_anzeigen_nur_offen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    anlegen = mcp.tools["todo_anlegen"]
    erledigen = mcp.tools["todo_erledigen"]
    anzeigen = mcp.tools["todos_anzeigen"]

    r1 = anlegen(bewerbung_id=aid, titel="A")
    anlegen(bewerbung_id=aid, titel="B")
    erledigen(todo_id=r1["task_id"])

    alle = anzeigen()
    assert alle["anzahl"] == 2
    offen = anzeigen(nur_offen=True)
    assert offen["anzahl"] == 1
    assert offen["todos"][0]["titel"] == "B"


def test_todos_anzeigen_filter_pro_bewerbung(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid1 = _make_app(tmp_db)
    aid2 = _make_app(tmp_db)
    mcp = _register(tmp_db)
    anlegen = mcp.tools["todo_anlegen"]
    anzeigen = mcp.tools["todos_anzeigen"]

    anlegen(bewerbung_id=aid1, titel="A")
    anlegen(bewerbung_id=aid1, titel="B")
    anlegen(bewerbung_id=aid2, titel="C")

    a1 = anzeigen(bewerbung_id=aid1)
    assert a1["anzahl"] == 2
    a2 = anzeigen(bewerbung_id=aid2)
    assert a2["anzahl"] == 1
