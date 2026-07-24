"""Tests fuer v1.7.10 — #780 (D28): Recruiter-/Vermittler-Historie.

Praxis-Befund 24.07.2026: Recruiter melden sich wiederholt und beziehen
sich auf fruehere Prozesse — aber es gab keine Personensuche. Der
Ansprechpartner steht als Freitext in `applications`, die Kontakt-Tabelle
blieb leer. Beide Tools muessen deshalb auch den ALTBESTAND (Freitext)
finden, ohne Migration.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1710_780_")
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


def _bestand(db):
    """Nachgebauter Altbestand: Vermittler B mit 3 Vorgaengen, Freitext-
    Ansprechpartner, teils mehrere Personen in einem Feld."""
    a1 = db.add_application({
        "company": "Vermittler B GmbH", "title": "PLM Consultant P-1",
        "status": "abgelehnt", "applied_at": "2025-11-10",
        "ansprechpartner": "Sabine Beispiel (Sales Consultant)",
        "kontakt_email": "s.beispiel@vermittler-b.example",
        "endkunde": "Endkunde X",
    })
    a2 = db.add_application({
        "company": "Vermittler B GmbH", "title": "MDM Projekt",
        "status": "abgelaufen", "applied_at": "2026-02-01",
        "ansprechpartner": "Sabine Beispiel, Lena Muster (Werkstudentin)",
        "endkunde": "Endkunde Y",
    })
    a3 = db.add_application({
        "company": "Anderer Arbeitgeber AG", "title": "Inhouse PLM",
        "status": "interview", "applied_at": "2026-06-01",
        "ansprechpartner": "Peter Anders",
    })
    return a1, a2, a3


def test_780_personensuche_findet_freitext(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    res = _result(_call(mcp, "kontakt_historie", {"suchbegriff": "Sabine Beispiel"}))
    assert res["status"] == "ok"
    assert res["anzahl_vorgaenge"] == 2
    assert res["letzter_kontakt"] == "2026-02-01"
    firmen = {v["firma"] for v in res["vorgaenge"]}
    assert firmen == {"Vermittler B GmbH"}


def test_780_teilname_genuegt(setup_env):
    """Fuzzy-Anspruch aus dem Issue: der Nachname reicht."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    res = _result(_call(mcp, "kontakt_historie", {"suchbegriff": "Beispiel"}))
    assert res["anzahl_vorgaenge"] == 2
    res2 = _result(_call(mcp, "kontakt_historie",
                         {"suchbegriff": "s.beispiel@vermittler-b.example"}))
    assert res2["anzahl_vorgaenge"] >= 1


def test_780_suche_findet_auch_kontaktdatenbank(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    cid = db.add_contact({"full_name": "Karla Kontakt",
                          "email": "karla@example.com",
                          "company": "Vermittler C"})
    res = _result(_call(mcp, "kontakt_historie", {"suchbegriff": "Karla"}))
    assert res["status"] == "ok"
    assert res["kontakte"][0]["name"] == "Karla Kontakt"


def test_780_nichts_gefunden_ist_ehrlich(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    res = _result(_call(mcp, "kontakt_historie", {"suchbegriff": "Unbekannter"}))
    assert res["status"] == "nichts_gefunden"


def test_780_vermittler_historie_aggregiert(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    res = _result(_call(mcp, "vermittler_historie", {"firma": "Vermittler B"}))
    assert res["status"] == "ok"
    assert res["anfragen_gesamt"] == 2
    assert set(res["endkunden"]) == {"Endkunde X", "Endkunde Y"}
    # Mehrere Personen in einem Freitextfeld werden getrennt
    assert any("Lena Muster" in a for a in res["ansprechpartner"])
    assert any("Sabine Beispiel" in a for a in res["ansprechpartner"])
    assert res["zeitraum"]["erster_kontakt"] == "2025-11-10"
    assert res["zeitraum"]["letzter_kontakt"] == "2026-02-01"
    assert res["interviews"] == 0
    assert "Noch kein Vorgang" in res["hinweis"]


def test_780_vermittler_historie_zaehlt_interviews(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    conn = db.connect()
    conn.execute("UPDATE applications SET has_reached_interview=1 "
                 "WHERE company='Vermittler B GmbH' AND title='PLM Consultant P-1'")
    conn.commit()
    res = _result(_call(mcp, "vermittler_historie", {"firma": "vermittler b"}))
    assert res["interviews"] == 1
    assert res["interview_quote"] == 50.0
