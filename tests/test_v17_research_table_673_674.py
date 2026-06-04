"""beta.98 — research_notes-Tabelle (#674) + Anzeige (#673).

- dedizierte Tabelle research_notes (Schema v46)
- Ein-Schritt-Persistenz aus den Analyse-Tools
- bewerbung_details + Timeline zeigen die Recherchen
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


def _reg(modul, tmp_db):
    mcp = FakeMCP()
    modul.register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _make_job(tmp_db, hash_="job-x", company="Firma X"):
    tmp_db.save_jobs([{
        "hash": hash_, "title": "PLM Consultant", "company": company,
        "source": "stepstone", "score": 7, "location": "Muenchen",
        "salary_min": 65000, "salary_max": 80000,
    }])
    return hash_


# ── Schema v46 / Tabelle vorhanden ──────────────────────────────────────


def test_schema_version_46_und_tabelle(tmp_db):
    from bewerbungs_assistent.database import SCHEMA_VERSION
    assert SCHEMA_VERSION >= 46
    conn = tmp_db.connect()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='research_notes'"
    ).fetchone()
    assert row is not None


# ── DB-Helper ───────────────────────────────────────────────────────────


def test_add_und_get_research_notes_neueste_zuerst(tmp_db):
    tmp_db.create_profile("T", "t@example.com")
    h = _make_job(tmp_db)
    app_id = tmp_db.add_application({"title": "PLM", "company": "Firma X", "job_hash": h})
    tmp_db.add_research_note("gehalt", "erst", bewerbung_id=app_id)
    tmp_db.add_research_note("markt", "zuletzt", bewerbung_id=app_id)
    rows = tmp_db.get_research_notes(bewerbung_id=app_id)
    assert [r["text"] for r in rows] == ["zuletzt", "erst"]


def test_get_research_notes_ohne_filter_leer(tmp_db):
    tmp_db.create_profile("T", "t@example.com")
    assert tmp_db.get_research_notes() == []


# ── Ein-Schritt-Persistenz (#674) ───────────────────────────────────────


def test_firmen_recherche_one_step_persistiert(tmp_db):
    import bewerbungs_assistent.tools.analyse as analyse
    tmp_db.create_profile("T", "t@example.com")
    h = _make_job(tmp_db, company="Firma X")
    app_id = tmp_db.add_application({"title": "PLM", "company": "Firma X", "job_hash": h})
    mcp = _reg(analyse, tmp_db)
    res = mcp.tools["firmen_recherche"]("Firma X", bewerbung_id=app_id)
    assert res.get("status") == "ok", res
    assert "gespeichert_als" in res, res
    rows = tmp_db.get_research_notes(bewerbung_id=app_id)
    assert any(r["kategorie"] == "firmenrecherche" for r in rows), rows
    assert any("Firmen-Recherche Firma X" in r["text"] for r in rows)


def test_firmen_recherche_ohne_id_persistiert_nicht(tmp_db):
    import bewerbungs_assistent.tools.analyse as analyse
    tmp_db.create_profile("T", "t@example.com")
    _make_job(tmp_db, company="Firma X")
    mcp = _reg(analyse, tmp_db)
    res = mcp.tools["firmen_recherche"]("Firma X")
    assert res.get("status") == "ok"
    assert "gespeichert_als" not in res


# ── Anzeige in bewerbung_details (#673) ─────────────────────────────────


def test_bewerbung_details_zeigt_recherchen(tmp_db):
    import bewerbungs_assistent.tools.bewerbungen as bewerbungen
    import bewerbungs_assistent.tools.analyse as analyse
    tmp_db.create_profile("T", "t@example.com")
    h = _make_job(tmp_db)
    app_id = tmp_db.add_application({"title": "PLM", "company": "Firma X", "job_hash": h})
    analyse_mcp = _reg(analyse, tmp_db)
    analyse_mcp.tools["recherche_speichern"](
        text="Gehalt 65-75k laut Kununu", bewerbung_id=app_id, kategorie="gehalt")
    bew_mcp = _reg(bewerbungen, tmp_db)
    details = bew_mcp.tools["bewerbung_details"](app_id)
    assert "recherchen" in details, details
    assert any(r["kategorie"] == "gehalt" and "65-75k" in r["text"]
               for r in details["recherchen"])
    assert all("datum" in r and "id" in r for r in details["recherchen"])


def test_bewerbung_details_ohne_recherchen_kein_feld(tmp_db):
    import bewerbungs_assistent.tools.bewerbungen as bewerbungen
    tmp_db.create_profile("T", "t@example.com")
    h = _make_job(tmp_db)
    app_id = tmp_db.add_application({"title": "PLM", "company": "Firma X", "job_hash": h})
    bew_mcp = _reg(bewerbungen, tmp_db)
    details = bew_mcp.tools["bewerbung_details"](app_id)
    assert "recherchen" not in details
