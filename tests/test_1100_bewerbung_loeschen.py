"""#1100: Eine gelöschte Bewerbung hinterlässt keine Verweise.

Der Kern-Test prüft NICHT gegen die Liste, nach der gelöscht wird —
eine Kontrolle mit derselben Annahme prüft nichts. Er sucht die ID der
Bewerbung in JEDER Spalte JEDER Tabelle.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import pytest


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Loeschtest"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, hash_="st1100"):
    db.save_jobs([{"hash": hash_, "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/stelle/1100", "source": "manuell",
                   "description": "x" * 80, "score": 5}])
    return db.connect().execute(
        "SELECT hash FROM jobs WHERE hash LIKE ?", (f"%{hash_}",)).fetchone()[0]


def _bewerbung_mit_allem(db):
    stelle = _stelle(db)
    app = db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                              "status": "beworben", "job_hash": stelle})
    db.link_application_to_job(app, stelle)
    db.add_follow_up(app, "2030-01-01")
    db.add_task({"titel": "Unterlagen nachreichen", "application_id": app})
    meeting = db.add_meeting({"application_id": app, "title": "Gespräch",
                              "meeting_date": "2030-01-02T10:00"})
    kontakt = db.add_contact({"full_name": "Erika Beispiel",
                              "company": "Musterbetrieb GmbH"})
    db.link_contact(kontakt, "application", app)
    db.link_contact(kontakt, "meeting", meeting)
    db.add_interview_reflection(app, {"was_lief_gut": "vieles"}, meeting_id=meeting)
    db.add_application_cost({"application_id": app, "kind": "reise",
                             "amount": 42.0, "description": "Fahrt"})
    db.add_research_note("firma", "Mittelständler", bewerbung_id=app)
    db.add_document_version({"kind": "cover_letter", "content": "Anschreiben",
                             "application_id": app})
    db.add_contact_reference(kontakt, "vorgesetzter", application_id=app)
    doc = db.add_document({"filename": "a.pdf", "filepath": "",
                           "linked_application_id": app})
    db.add_email({"application_id": app, "filename": "a.eml", "subject": "Einladung"})
    return {"app": app, "stelle": stelle, "meeting": meeting, "kontakt": kontakt,
            "doc": doc}


def _verweise_auf(db, wert) -> dict:
    """Jede Spalte jeder Tabelle, in der `wert` noch steht."""
    con = db.connect()
    funde = {}
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                            "AND name NOT LIKE 'sqlite_%'").fetchall():
        for spalte in [r[1] for r in con.execute(f"PRAGMA table_info({t})")]:
            n = con.execute(f"SELECT COUNT(*) FROM {t} WHERE {spalte}=?",
                            (wert,)).fetchone()[0]
            if n:
                funde[f"{t}.{spalte}"] = n
    return funde


# ── AK 1 ─────────────────────────────────────────────────────────────

def test_nach_dem_loeschen_zeigt_nichts_mehr_auf_die_bewerbung(db):
    b = _bewerbung_mit_allem(db)
    vorher = _verweise_auf(db, b["app"])
    assert len(vorher) >= 10, f"Testaufbau zu dünn: {vorher}"
    db.delete_application(b["app"])
    assert _verweise_auf(db, b["app"]) == {}


def test_auch_der_mitgeloeschte_termin_hinterlaesst_nichts(db):
    b = _bewerbung_mit_allem(db)
    db.delete_application(b["app"])
    assert _verweise_auf(db, b["meeting"]) == {}


# ── AK 2 und 3 ───────────────────────────────────────────────────────

def test_stelle_gilt_nicht_mehr_als_beworben(db):
    b = _bewerbung_mit_allem(db)
    n = lambda: db.connect().execute(  # noqa: E731
        "SELECT COUNT(*) FROM application_jobs WHERE job_hash=? OR job_hash LIKE ?",
        (b["stelle"], "%st1100")).fetchone()[0]
    assert n() == 1
    db.delete_application(b["app"])
    assert n() == 0
    aktiv = {j["hash"] for j in db.get_active_jobs(exclude_applied=True)}
    assert any(h.endswith("st1100") for h in aktiv), "Stelle gilt weiter als beworben"


def test_kosten_zaehlen_nicht_mehr_im_aufwand(db):
    b = _bewerbung_mit_allem(db)
    summe = lambda: db.connect().execute(  # noqa: E731
        "SELECT COALESCE(SUM(amount),0) FROM application_costs").fetchone()[0]
    assert summe() == 42.0
    db.delete_application(b["app"])
    assert summe() == 0


# ── Dokumente, Mails, Referenzen bleiben ─────────────────────────────

def test_dokumente_mails_und_referenzen_bleiben_erhalten(db):
    b = _bewerbung_mit_allem(db)
    con = db.connect()
    db.delete_application(b["app"])
    assert con.execute("SELECT COUNT(*) FROM documents WHERE id=?", (b["doc"],)).fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM application_emails").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM contact_references").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM interview_reflections").fetchone()[0] == 0, \
        "die Reflexion gehört zur Bewerbung und geht mit"
    assert con.execute("SELECT COUNT(*) FROM contacts WHERE id=?", (b["kontakt"],)).fetchone()[0] == 1


# ── AK 4: Vorschau und Antwort nennen dieselben Zahlen ───────────────

def test_vorschau_gleich_ausfuehrung(db):
    b = _bewerbung_mit_allem(db)
    vorher = db.delete_application(b["app"], dry_run=True)
    assert db.get_application(b["app"]) is not None, "Vorschau hat gelöscht"
    nachher = db.delete_application(b["app"])
    assert vorher == nachher
    assert nachher["geloest"]["documents"] == 1
    assert nachher["geloescht"]["application_costs"] == 1
    assert nachher["geloescht"]["contact_links"] == 2
    assert "interview_reflections" not in nachher["geloest"], "doppelt gezählt"


def _werkzeug(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1100 Test")
    register_all(mcp, db, logging.getLogger("test.1100"))

    async def lauf():
        tool = await mcp.get_tool(name)
        return (await tool.run(args)).structured_content
    return asyncio.run(lauf())


def test_werkzeug_nennt_folgen_vorher_und_nachher(db):
    b = _bewerbung_mit_allem(db)
    frage = _werkzeug(db, "bewerbung_loeschen", {"bewerbung_id": b["app"]})
    assert frage["status"] == "bestaetigung_erforderlich"
    assert "Kosten" in frage["folgen"] and "Dokumente" in frage["folgen"]
    assert "löst" in frage["folgen"]
    antwort = _werkzeug(db, "bewerbung_loeschen",
                        {"bewerbung_id": b["app"], "bestaetigung": True})
    assert antwort["geloescht"] == frage["geloescht"]
    assert antwort["geloest"] == frage["geloest"]
    assert "Gelöscht:" in antwort["folgen"]


# ── Termin löschen ───────────────────────────────────────────────────

def test_termin_loeschen_raeumt_kontakt_verknuepfung_ab(db):
    b = _bewerbung_mit_allem(db)
    assert db.delete_meeting(b["meeting"]) is True
    assert _verweise_auf(db, b["meeting"]) == {}
    # Die Reflexion bleibt — sie gehört zur Bewerbung, nicht zum Termin.
    assert db.connect().execute(
        "SELECT COUNT(*) FROM interview_reflections").fetchone()[0] == 1
    assert db.get_application(b["app"]) is not None


def test_termin_eines_fremden_profils_wird_nicht_geloescht(db):
    b = _bewerbung_mit_allem(db)
    assert db.delete_meeting(b["meeting"], profile_id="anderes-profil") is False
    assert _verweise_auf(db, b["meeting"])
