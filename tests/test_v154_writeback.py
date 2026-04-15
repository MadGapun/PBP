"""Regressionstests fuer v1.5.4 Write-Back-Tools (#443).

Deckt alle neuen MCP-Tools ab die in #444-#448 ergaenzt wurden:

- Meetings: meeting_hinzufuegen, meeting_bearbeiten, meeting_loeschen, meetings_anzeigen
- E-Mails: email_verknuepfen, email_loeschen, emails_anzeigen
- Jobs: stelle_bearbeiten
- Dokumente: dokument_entverknuepfen, dokument_loeschen, dokument_status_setzen
- Bewerbungen: bewerbung_bearbeiten um cover_letter_path/cv_path erweitert
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.database import Database  # noqa: E402
from bewerbungs_assistent.tools import register_all  # noqa: E402


def _build_server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Write-Back Tester", "email": "wb@example.com"})
    mcp = FastMCP("PBP v1.5.4 Test")
    logger = logging.getLogger("test.writeback")
    register_all(mcp, db, logger)
    return mcp, db


async def _call(mcp, name, args=None):
    result = await mcp.call_tool(name, args or {})
    if hasattr(result, "structured_content") and result.structured_content:
        return result.structured_content
    import json
    for c in getattr(result, "content", []):
        if hasattr(c, "text"):
            try:
                return json.loads(c.text)
            except (json.JSONDecodeError, TypeError):
                return {"text": c.text}
    return {}


def _run(mcp, name, args=None):
    return asyncio.run(_call(mcp, name, args or {}))


def _seed_application(db, title="Senior Dev", company="Acme GmbH") -> str:
    return db.add_application({"title": title, "company": company, "url": "https://acme.example/jobs/1"})


def _seed_job(db, title="Senior Dev", company="Acme GmbH") -> str:
    from bewerbungs_assistent.job_scraper import stelle_hash
    h = stelle_hash("manuell", f"{company} {title}")
    db.save_jobs([{
        "hash": h, "title": title, "company": company, "location": "Hamburg",
        "url": "https://acme.example/jobs/1", "description": "Alt",
        "source": "manuell", "remote": "hybrid",
    }])
    return h


def _seed_document(db, filename="lebenslauf.pdf", doc_type="lebenslauf") -> str:
    """Legt ein Dokument in der DB an ohne physische Datei."""
    return db.add_document({
        "filename": filename,
        "filepath": "",  # keine echte Datei
        "doc_type": doc_type,
    })


# ==================== Meetings (#444) ====================

def test_meeting_hinzufuegen_success(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        app_id = _seed_application(db)
        result = _run(mcp, "meeting_hinzufuegen", {
            "bewerbung_id": app_id,
            "datum": "2026-04-18T14:00",
            "typ": "interview",
            "platform": "Teams",
            "notizen": "Erstes Gespraech mit HR",
            "dauer_minuten": 60,
        })
        assert result.get("status") == "angelegt", result
        assert "meeting_id" in result
        # Persistenz pruefen
        meetings = db.get_meetings_for_application(app_id, profile_id=db.get_active_profile_id())
        assert len(meetings) == 1
        assert meetings[0]["meeting_type"] == "interview"
        assert meetings[0]["platform"] == "Teams"
        assert meetings[0]["duration_minutes"] == 60
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_meeting_hinzufuegen_invalid_bewerbung(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        result = _run(mcp, "meeting_hinzufuegen", {
            "bewerbung_id": "nicht-da",
            "datum": "2026-04-18T14:00",
        })
        assert "fehler" in result
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_meeting_hinzufuegen_invalid_typ(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        app_id = _seed_application(db)
        result = _run(mcp, "meeting_hinzufuegen", {
            "bewerbung_id": app_id,
            "datum": "2026-04-18T14:00",
            "typ": "quatsch",
        })
        assert "fehler" in result
        assert "erlaubte_typen" in result
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_meeting_bearbeiten_updates_fields(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        app_id = _seed_application(db)
        created = _run(mcp, "meeting_hinzufuegen", {
            "bewerbung_id": app_id,
            "datum": "2026-04-18T14:00",
            "typ": "telefon",
        })
        mid = created["meeting_id"]
        result = _run(mcp, "meeting_bearbeiten", {
            "meeting_id": mid,
            "status": "bestaetigt",
            "notizen": "verschoben auf 15 Uhr",
        })
        assert result.get("status") == "aktualisiert"
        assert set(result["geaenderte_felder"]) == {"status", "notes"}
        meetings = db.get_meetings_for_application(app_id, profile_id=db.get_active_profile_id())
        assert meetings[0]["status"] == "bestaetigt"
        assert meetings[0]["notes"] == "verschoben auf 15 Uhr"
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_meeting_bearbeiten_empty_update(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        app_id = _seed_application(db)
        created = _run(mcp, "meeting_hinzufuegen", {
            "bewerbung_id": app_id, "datum": "2026-04-18T14:00",
        })
        result = _run(mcp, "meeting_bearbeiten", {"meeting_id": created["meeting_id"]})
        assert "fehler" in result
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_meeting_loeschen_two_phase(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        app_id = _seed_application(db)
        created = _run(mcp, "meeting_hinzufuegen", {
            "bewerbung_id": app_id, "datum": "2026-04-18T14:00",
        })
        mid = created["meeting_id"]
        # Phase 1: ohne Bestaetigung
        r1 = _run(mcp, "meeting_loeschen", {"meeting_id": mid})
        assert r1["status"] == "bestaetigung_erforderlich"
        # Meeting muss noch da sein
        assert len(db.get_meetings_for_application(app_id, profile_id=db.get_active_profile_id())) == 1
        # Phase 2: mit Bestaetigung
        r2 = _run(mcp, "meeting_loeschen", {"meeting_id": mid, "bestaetigung": True})
        assert r2["status"] == "geloescht"
        assert db.get_meetings_for_application(app_id, profile_id=db.get_active_profile_id()) == []
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_meetings_anzeigen_filtered_and_upcoming(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        app_id = _seed_application(db)
        _run(mcp, "meeting_hinzufuegen", {
            "bewerbung_id": app_id, "datum": "2099-12-31T10:00", "typ": "interview",
        })
        # Filter nach Bewerbung
        r1 = _run(mcp, "meetings_anzeigen", {"bewerbung_id": app_id})
        assert r1["anzahl"] == 1
        # Kommende Termine global
        r2 = _run(mcp, "meetings_anzeigen", {"tage": 36500})
        assert r2["anzahl"] == 1
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


# ==================== E-Mails (#445) ====================

def test_email_verknuepfen_and_unlink(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        app_id = _seed_application(db)
        email_id = db.add_email({
            "filename": "antwort.eml",
            "subject": "Vielen Dank fuer Ihre Bewerbung",
            "sender": "hr@acme.example",
            "direction": "eingang",
        })
        # Verknuepfen
        r1 = _run(mcp, "email_verknuepfen", {"email_id": email_id, "bewerbung_id": app_id})
        assert r1["status"] == "verknuepft"
        stored = db.get_email(email_id, profile_id=db.get_active_profile_id())
        assert stored["application_id"] == app_id
        # Entkoppeln durch leere bewerbung_id
        r2 = _run(mcp, "email_verknuepfen", {"email_id": email_id, "bewerbung_id": ""})
        assert r2["status"] == "entkoppelt"
        stored = db.get_email(email_id, profile_id=db.get_active_profile_id())
        assert stored["application_id"] is None
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_email_loeschen_two_phase(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        email_id = db.add_email({"filename": "spam.eml", "subject": "Test"})
        r1 = _run(mcp, "email_loeschen", {"email_id": email_id})
        assert r1["status"] == "bestaetigung_erforderlich"
        assert db.get_email(email_id, profile_id=db.get_active_profile_id()) is not None
        r2 = _run(mcp, "email_loeschen", {"email_id": email_id, "bestaetigung": True})
        assert r2["status"] == "geloescht"
        assert db.get_email(email_id, profile_id=db.get_active_profile_id()) is None
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_emails_anzeigen_unmatched(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        db.add_email({"filename": "a.eml", "subject": "Unmatched 1"})
        db.add_email({"filename": "b.eml", "subject": "Unmatched 2"})
        app_id = _seed_application(db)
        matched_id = db.add_email({"filename": "c.eml", "subject": "Matched", "application_id": app_id})
        r = _run(mcp, "emails_anzeigen", {})
        assert r["filter"] == "unmatched"
        assert r["anzahl"] == 2
        r2 = _run(mcp, "emails_anzeigen", {"bewerbung_id": app_id})
        assert r2["anzahl"] == 1
        assert r2["emails"][0]["id"] == matched_id
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


# ==================== Jobs (#446) ====================

def test_stelle_bearbeiten_updates_fields(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        h = _seed_job(db)
        result = _run(mcp, "stelle_bearbeiten", {
            "job_hash": h,
            "titel": "Senior Dev (m/w/d) — REMOTE",
            "beschreibung": "Neue, deutlich ausfuehrlichere Beschreibung.",
        })
        assert result["status"] == "aktualisiert"
        assert set(result["geaenderte_felder"]) == {"title", "description"}
        job = db.get_job(h)
        assert job["title"] == "Senior Dev (m/w/d) — REMOTE"
        assert "ausfuehrlichere" in job["description"]
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_stelle_bearbeiten_unknown_hash(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        result = _run(mcp, "stelle_bearbeiten", {"job_hash": "nope", "titel": "X"})
        assert "fehler" in result
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_stelle_bearbeiten_empty_update(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        h = _seed_job(db)
        result = _run(mcp, "stelle_bearbeiten", {"job_hash": h})
        assert "fehler" in result
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


# ==================== Dokumente (#447) ====================

def test_dokument_entverknuepfen(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        app_id = _seed_application(db)
        doc_id = _seed_document(db)
        # Erst verknuepfen per DB-Helper, dann via Tool wieder loesen
        assert db.link_document_to_application(doc_id, app_id, profile_id=db.get_active_profile_id())
        result = _run(mcp, "dokument_entverknuepfen", {"dokument_id": doc_id})
        assert result["status"] == "entverknuepft"
        doc = db.get_document(doc_id, profile_id=db.get_active_profile_id())
        assert doc["linked_application_id"] is None
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_dokument_entverknuepfen_already_unlinked(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        doc_id = _seed_document(db)
        result = _run(mcp, "dokument_entverknuepfen", {"dokument_id": doc_id})
        assert result["status"] == "nicht_verknuepft"
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_dokument_loeschen_two_phase(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        doc_id = _seed_document(db, filename="obsolet.pdf")
        r1 = _run(mcp, "dokument_loeschen", {"dokument_id": doc_id})
        assert r1["status"] == "bestaetigung_erforderlich"
        assert db.get_document(doc_id, profile_id=db.get_active_profile_id()) is not None
        r2 = _run(mcp, "dokument_loeschen", {"dokument_id": doc_id, "bestaetigung": True})
        assert r2["status"] == "geloescht"
        assert db.get_document(doc_id, profile_id=db.get_active_profile_id()) is None
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_dokument_status_setzen(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        doc_id = _seed_document(db)
        result = _run(mcp, "dokument_status_setzen", {
            "dokument_id": doc_id, "status": "angewendet",
        })
        assert result["status"] == "aktualisiert"
        assert result["extraction_status"] == "angewendet"
        doc = db.get_document(doc_id, profile_id=db.get_active_profile_id())
        assert doc["extraction_status"] == "angewendet"
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_dokument_status_setzen_invalid(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        doc_id = _seed_document(db)
        result = _run(mcp, "dokument_status_setzen", {
            "dokument_id": doc_id, "status": "quatsch",
        })
        assert "fehler" in result
        assert "erlaubte_status" in result
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


# ==================== Bewerbungen (#448) ====================

def test_bewerbung_bearbeiten_cover_letter_and_cv(tmp_path):
    mcp, db = _build_server(tmp_path)
    try:
        app_id = _seed_application(db)
        result = _run(mcp, "bewerbung_bearbeiten", {
            "bewerbung_id": app_id,
            "cover_letter_path": "/tmp/anschreiben.pdf",
            "cv_path": "/tmp/cv.pdf",
        })
        assert result["status"] == "aktualisiert"
        assert set(result["geänderte_felder"]) == {"cover_letter_path", "cv_path"}
        app = db.get_application(app_id)
        assert app["cover_letter_path"] == "/tmp/anschreiben.pdf"
        assert app["cv_path"] == "/tmp/cv.pdf"
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)
