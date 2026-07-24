"""Tests fuer v1.7.10 — #779 (D27): applied_at-Nachtrag + arbeitgeber_ausgefallen.

Praxis-Fall 24.07.2026: Der intensivste Bewerbungsvorgang des Jahres
(drei Gespraeche, Angebot, Insolvenz des Arbeitgebers) fehlte KOMPLETT in
der Statistik, weil `applied_at` leer war — der Status 'beworben' wurde
bei einem Netzwerk-Kontakt nie durchlaufen. Zusaetzlich stand der Vorgang
als 'zurueckgezogen', obwohl der Bewerber nichts zurueckgezogen hat.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1710_779_")
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


def _netzwerk_bewerbung(db):
    """Der Praxis-Fall: in_vorbereitung angelegt, nie 'beworben'.

    applied_at explizit leer — so sah der Bestand aus (das Tool
    bewerbung_erstellen setzt bei in_vorbereitung kein Datum)."""
    return db.add_application({
        "company": "Firma K", "title": "Projektleiter Digitalisierung",
        "status": "in_vorbereitung", "applied_at": "",
    })


def test_779_statuswechsel_traegt_applied_at_nach(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = _netzwerk_bewerbung(db)
    assert not (db.get_application(aid).get("applied_at") or "")

    res = _result(_call(mcp, "bewerbung_status_aendern",
                        {"bewerbung_id": aid, "neuer_status": "interview"}))
    assert res["status"] == "aktualisiert"
    assert "applied_at_nachgetragen" in res, res
    app = db.get_application(aid)
    assert (app.get("applied_at") or "").strip(), "applied_at muss gesetzt sein"


def test_779_beworben_pfad_unveraendert(setup_env):
    """Der normale Weg ueber 'beworben' setzt applied_at wie bisher."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = _netzwerk_bewerbung(db)
    _call(mcp, "bewerbung_status_aendern",
          {"bewerbung_id": aid, "neuer_status": "beworben"})
    assert (db.get_application(aid).get("applied_at") or "").strip()


def test_779_neuer_status_arbeitgeber_ausgefallen(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = _netzwerk_bewerbung(db)
    res = _result(_call(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": aid, "neuer_status": "arbeitgeber_ausgefallen",
        "notizen": "Insolvenz des Arbeitgebers"}))
    assert res["status"] == "aktualisiert"
    assert db.get_application(aid)["status"] == "arbeitgeber_ausgefallen"
    assert "hinweis" in res


def test_779_ausgefallen_zaehlt_nicht_als_rueckzug_aber_angebot_bleibt(setup_env):
    """Kern der Statistik-Ehrlichkeit: withdrawal_rate 0, offer_rate > 0."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = _netzwerk_bewerbung(db)
    for status in ("interview", "angebot", "arbeitgeber_ausgefallen"):
        _call(mcp, "bewerbung_status_aendern",
              {"bewerbung_id": aid, "neuer_status": status})

    stats = db.get_statistics()
    q = stats["quoten"]["gesamt"]
    assert q.get("zurueckgezogen", 0) == 0, "Ausfall ist kein Rueckzug"
    assert q.get("arbeitgeber_ausgefallen") == 1
    assert q.get("angebot") == 1, (
        "Das vor dem Ausfall vorliegende Angebot muss in der offer_rate bleiben")
    assert q["offer_rate"] > 0


def test_779_statistik_weist_ausgeschlossene_aus(setup_env):
    db, _ = setup_env
    conn = db.connect()
    aid = _netzwerk_bewerbung(db)
    # Kuenstlich den Alt-Zustand herstellen: fortgeschrittener Status,
    # applied_at leer (direkt, ohne Tool — genau so sah der Bestand aus)
    conn.execute("UPDATE applications SET status='zurueckgezogen', "
                 "applied_at='' WHERE id=?", (aid,))
    conn.commit()
    stats = db.get_statistics()
    assert "ausgeschlossen" in stats, "leises Verschlucken ist der Bug"
    assert stats["ausgeschlossen"]["anzahl"] == 1
    assert stats["ausgeschlossen"]["bewerbungen"][0]["firma"] == "Firma K"


def test_779_diagnose_findet_und_fixt(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    conn = db.connect()
    aid = _netzwerk_bewerbung(db)
    conn.execute("UPDATE applications SET status='abgelehnt', applied_at='' "
                 "WHERE id=?", (aid,))
    conn.execute(
        "INSERT INTO application_events (application_id, status, event_date, notes) "
        "VALUES (?, 'beworben', '2026-06-15T10:00:00', 'test')", (aid,))
    conn.commit()

    diag = _result(_call(mcp, "pbp_diagnose", {}))
    treffer = [w for w in diag.get("warnungen", [])
               if "applied_at" in str(w.get("problem", ""))]
    assert treffer, "Diagnose muss die Luecke melden"

    diag_fix = _result(_call(mcp, "pbp_diagnose", {"auto_fix": True}))
    assert any("applied_at" in f
               for f in diag_fix.get("automatisch_behoben", [])), diag_fix
    assert db.get_application(aid)["applied_at"] == "2026-06-15", (
        "auto_fix muss den aeltesten Event nehmen")

    # Idempotenz: zweiter Lauf findet nichts mehr
    diag2 = _result(_call(mcp, "pbp_diagnose", {"auto_fix": True}))
    assert not any("applied_at" in f
                   for f in diag2.get("automatisch_behoben", []))


def test_779_rueckfrage_bei_absage_ohne_grund(setup_env):
    """#782-Anteil: Absage ohne Grund -> Rueckfrage im Result, kein Zwang."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = _netzwerk_bewerbung(db)
    res = _result(_call(mcp, "bewerbung_status_aendern",
                        {"bewerbung_id": aid, "neuer_status": "abgelehnt"}))
    assert res["status"] == "aktualisiert", "kein Zwang — Wechsel geht durch"
    assert "rueckfrage_ablehnungsgrund" in res

    aid2 = db.add_application({"company": "Firma L", "title": "X",
                               "status": "in_vorbereitung"})
    res2 = _result(_call(mcp, "bewerbung_status_aendern", {
        "bewerbung_id": aid2, "neuer_status": "abgelehnt",
        "ablehnungsgrund": "interne Besetzung"}))
    assert "rueckfrage_ablehnungsgrund" not in res2


def test_779_bewerbungen_anzeigen_archiviert_ausgefallene(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = _netzwerk_bewerbung(db)
    _call(mcp, "bewerbung_status_aendern",
          {"bewerbung_id": aid, "neuer_status": "arbeitgeber_ausgefallen"})
    ohne = _result(_call(mcp, "bewerbungen_anzeigen", {}))
    mit = _result(_call(mcp, "bewerbungen_anzeigen", {"archiv": True}))
    ids_ohne = [b.get("id") for b in (ohne.get("bewerbungen") or [])]
    ids_mit = [b.get("id") for b in (mit.get("bewerbungen") or [])]
    assert aid[:8] not in ids_ohne, "Endstatus gehoert ins Archiv"
    assert aid[:8] in ids_mit
