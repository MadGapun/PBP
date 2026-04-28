"""Tests fuer v1.6.4-Hotfixes (#532, #528, #522, #529, #530, #531, #535, #536)."""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v164_test_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    import shutil
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
    """v1.6.5: FastMCP 2.12 entfernte mcp.call_tool — wir nutzen tool.run()."""
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


# ============= #528 — Umlaut bei suchkriterien_bearbeiten ========
def test_528_suchkriterien_umlaut(setup_env):
    """suchkriterien_bearbeiten akzeptiert sowohl 'hinzufuegen' als auch 'hinzufügen'."""
    from bewerbungs_assistent.server import mcp
    raw = _call(mcp, "suchkriterien_bearbeiten", {
        "kategorie": "muss",
        "aktion": "hinzufügen",
        "werte": ["Python"],
    })
    result = _result(raw)
    assert result.get("status") == "hinzugefuegt", f"Expected success, got: {result}"

    raw2 = _call(mcp, "suchkriterien_bearbeiten", {
        "kategorie": "muss",
        "aktion": "hinzufuegen",
        "werte": ["FastAPI"],
    })
    result2 = _result(raw2)
    assert result2.get("status") == "hinzugefuegt"


# ============= #529 — applied_at Parameter ========================
def test_529_bewerbung_bearbeiten_applied_at(setup_env):
    """bewerbung_bearbeiten kann applied_at nachtraeglich setzen/korrigieren."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp

    # Bewerbung anlegen — applied_at wird auto-gesetzt
    bid = db.add_application({"title": "Test Job", "company": "TestCorp"})
    before = db.get_application(bid).get("applied_at")
    assert before, "applied_at sollte initial gesetzt sein (auto)"

    # Korrektur via DD.MM.YYYY
    raw = _call(mcp, "bewerbung_bearbeiten", {
        "bewerbung_id": bid,
        "applied_at": "24.03.2026",
    })
    result = _result(raw)
    assert result.get("status") == "aktualisiert"
    assert "applied_at" in result.get("geänderte_felder", [])
    after = db.get_application(bid).get("applied_at")
    assert after == "2026-03-24", f"Erwartet 2026-03-24 nach Korrektur, bekommen: {after}"


def test_529_bewerbung_bearbeiten_applied_at_invalid(setup_env):
    """Ungueltiges Datum gibt Fehler statt zu speichern."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    bid = db.add_application({"title": "Test", "company": "TestCorp"})
    raw = _call(mcp, "bewerbung_bearbeiten", {
        "bewerbung_id": bid,
        "applied_at": "kein-datum",
    })
    result = _result(raw)
    assert "fehler" in result


# ============= #530 — has_reached_interview Flag =====================
def test_530_interview_flag_persists(setup_env):
    """has_reached_interview bleibt TRUE auch nach Wechsel auf abgelehnt."""
    db, _ = setup_env
    bid = db.add_application({"title": "Test", "company": "TestCorp", "status": "beworben"})

    # Interview erreicht
    db.update_application_status(bid, "interview")
    app = db.get_application(bid)
    assert app.get("has_reached_interview") == 1

    # Spaeter abgelehnt
    db.update_application_status(bid, "abgelehnt")
    app = db.get_application(bid)
    assert app.get("has_reached_interview") == 1, "Flag muss nach Ablehnung TRUE bleiben"
    assert app.get("status") == "abgelehnt"


def test_530_statistik_zaehlt_historische_interviews(setup_env):
    """statistiken_abrufen zaehlt has_reached_interview, nicht nur aktuellen Status."""
    db, _ = setup_env
    # 3 Bewerbungen anlegen, alle Interview erreicht
    for i in range(3):
        bid = db.add_application({"title": f"Job {i}", "company": f"Corp{i}", "status": "beworben"})
        db.update_application_status(bid, "interview")
    # 2 davon spaeter abgelehnt
    apps = db.get_applications()
    db.update_application_status(apps[0]["id"], "abgelehnt")
    db.update_application_status(apps[1]["id"], "abgelaufen")

    stats = db.get_statistics()
    assert stats.get("interview_count_total", 0) == 3, (
        f"Erwartet 3 historische Interviews, bekommen: {stats.get('interview_count_total')}"
    )


# ============= #531 — Duplikat-Erkennung (Vermittler/Endkunde) =======
def test_531_duplikat_vermittler_endkunde(setup_env):
    """bewerbung_erstellen erkennt Vermittler/Endkunde-Duplikate."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    # Erste Bewerbung: Vermittler-Sicht
    raw = _call(mcp, "bewerbung_erstellen", {
        "title": "Senior PLM Functional Expert (m/w/d)",
        "company": "IQ Intelligentes Ingenieur Management (Endkunde: Siemens Energy)",
    })
    result = _result(raw)
    assert result.get("status") in ("erstellt", "angelegt")  # Erste = OK

    # Zweite mit Endkunden-Sicht — sollte als Duplikat erkannt werden
    raw2 = _call(mcp, "bewerbung_erstellen", {
        "title": "Senior PLM Functional Expert (Internal) (m/w/d) — Mülheim",
        "company": "Siemens Energy (via IQ Intelligentes Ingenieur Management GmbH)",
    })
    result2 = _result(raw2)
    assert result2.get("status") == "duplikat", f"Erwartet Duplikat-Status, bekommen: {result2}"
    assert result2.get("match_typ") in ("fuzzy_firma_titel", "email_oder_ansprechpartner")


def test_531_kein_duplikat_bei_unterschiedlicher_firma(setup_env):
    """Verschiedene Firmen sind KEIN Duplikat (kein false positive)."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _call(mcp, "bewerbung_erstellen", {
        "title": "Python Developer", "company": "Bechtle AG",
    })
    raw = _call(mcp, "bewerbung_erstellen", {
        "title": "Python Developer", "company": "Adesso SE",
    })
    result = _result(raw)
    assert result.get("status") != "duplikat"


# ============= #535 — Score-Recompute nach stelle_bearbeiten =========
def test_535_score_recompute_after_description_update(setup_env):
    """stelle_bearbeiten mit neuer description triggert Score-Recompute."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    # Job anlegen mit knapper Beschreibung
    db.save_jobs([{
        "hash": "testhash01",
        "title": "Python Developer",
        "company": "TestCorp",
        "description": "kurz",
        "score": 5,
        "url": "https://example.com/1",
        "found_at": "2026-04-28T00:00:00",
        "source": "manuell",
    }])
    db.set_search_criteria("keywords_muss", ["python"])
    db.set_search_criteria("keywords_plus", ["fastapi", "postgres"])

    # Beschreibung mit Plus-Keywords erweitern -> Score sollte steigen
    raw = _call(mcp, "stelle_bearbeiten", {
        "job_hash": "testhash01",
        "beschreibung": "Python FastAPI Postgres Senior Backend Developer",
    })
    result = _result(raw)
    assert result.get("status") == "aktualisiert"
    # Score-Recompute sollte stattgefunden haben
    assert "score_neu_berechnet" in result, f"Erwartet Score-Recompute-Info, bekommen: {result}"


# ============= #536 — Quereinsteiger-Heuristik =======================
def test_536_career_changers_welcome_no_warning():
    """Quereinsteiger-Klausel hebt Hochschulabschluss-Warnung auf."""
    from bewerbungs_assistent.job_scraper import _detect_degree_required
    text_with = (
        "Degree in Engineering, Business Informatics or comparable field. "
        "Career changers are welcome, provided they bring strong project management skills."
    )
    text_without = "Abgeschlossenes Studium der Informatik erforderlich."
    text_quereinsteiger_de = (
        "Hochschulabschluss erforderlich. Quereinsteiger sind willkommen."
    )
    assert _detect_degree_required(text_with) is False, "Career changers welcome muss Warnung aufheben"
    assert _detect_degree_required(text_without) is True, "Eindeutige Anforderung muss True bleiben"
    assert _detect_degree_required(text_quereinsteiger_de) is False, "Deutsche Quereinsteiger-Klausel muss greifen"
