"""Tests fuer v1.7.7 — #750-T1 (E18: dokument_text_setzen) und #753 (H18: firma_kontext).

#750: OCR-Text nachtragen ging bisher nur per Direkt-SQL (Anti-DB-Bypass-
Verstoss). #753: Firmen-Status wurde aus dem Gedaechtnis behauptet —
firma_kontext liefert den dokumentierten Stand in einem Call.
"""
import asyncio
import logging

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _mcp_mit(db, modul):
    from fastmcp import FastMCP
    mcp = FastMCP("test")
    modul.register(mcp, db, logging.getLogger("test"))
    return mcp


# =====================================================================
# #750-T1: dokument_text_setzen
# =====================================================================

class TestDokumentTextSetzen:
    def test_ocr_text_mit_provenienz(self, tmp_db):
        from bewerbungs_assistent.tools import dokumente
        doc_id = tmp_db.add_document({
            "filename": "Techniker-Abschluss.pdf", "filepath": "/fake/t.pdf",
            "doc_type": "zeugnis", "extracted_text": "x",  # 1-Zeichen-Scan
        })
        mcp = _mcp_mit(tmp_db, dokumente)
        out = _call(mcp, "dokument_text_setzen", {
            "dokument_id": doc_id,
            "text": "Staatlich gepruefter Techniker, Fachrichtung Maschinentechnik.",
            "quelle": "OCR via Tesseract 5.4.0, deu+eng, OSD-Rotationskorrektur",
        })
        assert out["status"] == "gesetzt"
        assert out["zeichen_vorher"] == 1
        doc = tmp_db.get_document(doc_id)
        assert doc["extracted_text"].startswith("[OCR via Tesseract 5.4.0")
        assert "nachgetragen" in doc["extracted_text"]
        assert "Maschinentechnik" in doc["extracted_text"]
        assert doc["last_extraction_at"]

    def test_quelle_ist_pflicht(self, tmp_db):
        from bewerbungs_assistent.tools import dokumente
        doc_id = tmp_db.add_document({
            "filename": "scan.pdf", "filepath": "/fake/s.pdf",
            "doc_type": "zeugnis",
        })
        mcp = _mcp_mit(tmp_db, dokumente)
        out = _call(mcp, "dokument_text_setzen",
                    {"dokument_id": doc_id, "text": "Inhalt", "quelle": "  "})
        assert "fehler" in out and "Provenienz" in out["fehler"]
        # Nichts geschrieben
        assert (tmp_db.get_document(doc_id).get("extracted_text") or "") in ("", None)

    def test_leerer_text_abgelehnt(self, tmp_db):
        from bewerbungs_assistent.tools import dokumente
        doc_id = tmp_db.add_document({
            "filename": "scan.pdf", "filepath": "/fake/s2.pdf",
            "doc_type": "zeugnis",
        })
        mcp = _mcp_mit(tmp_db, dokumente)
        out = _call(mcp, "dokument_text_setzen",
                    {"dokument_id": doc_id, "text": "", "quelle": "OCR"})
        assert "fehler" in out

    def test_unbekanntes_dokument(self, tmp_db):
        from bewerbungs_assistent.tools import dokumente
        mcp = _mcp_mit(tmp_db, dokumente)
        out = _call(mcp, "dokument_text_setzen",
                    {"dokument_id": "gibtsnicht", "text": "x", "quelle": "OCR"})
        assert "fehler" in out


# =====================================================================
# #753: firma_kontext
# =====================================================================

class TestFirmaKontext:
    def _befuellen(self, db):
        db.add_application({
            "title": "Interim Projektleiter ERP", "company": "Werftbau Nord GmbH",
            "status": "abgelehnt", "applied_at": "2026-06-04",
        })
        db.add_application({
            "title": "Programm-Manager", "company": "Musterfirma AG",
            "status": "interview",
        })
        conn = db.connect()
        pid = db.get_active_profile_id()
        conn.execute(
            "INSERT INTO jobs (hash, title, company, is_active, profile_id, score) "
            "VALUES (?, ?, ?, 1, ?, 25)",
            (f"{pid}:aktiv1", "Project Manager", "Halbleiterwerk Nord GmbH", pid))
        conn.execute(
            "INSERT INTO jobs (hash, title, company, is_active, profile_id, "
            "dismiss_reason, score) VALUES (?, ?, ?, 0, ?, 'falsches_fachgebiet', 5)",
            (f"{pid}:tot1", "Quality Engineer", "Halbleiterwerk Nord GmbH", pid))
        conn.execute(
            "INSERT INTO jobs (hash, title, company, is_active, profile_id, "
            "dismiss_reason, score) VALUES (?, ?, ?, 0, ?, 'falsches_fachgebiet', 3)",
            (f"{pid}:tot2", "Reliability Manager", "Halbleiterwerk Nord GmbH", pid))
        conn.commit()

    def test_teilstring_findet_firma(self, tmp_db):
        from bewerbungs_assistent.tools import bewerbungen
        self._befuellen(tmp_db)
        mcp = _mcp_mit(tmp_db, bewerbungen)
        out = _call(mcp, "firma_kontext", {"firmenname": "Halbleiterwerk"})
        assert out["gefunden"] is True
        assert len(out["aktive_stellen"]) == 1
        assert out["aussortiert_anzahl"] == 2
        assert out["aussortiert_gruende"] == {"falsches_fachgebiet": 2}
        # #757-Hinweis: Gruende gelten je Stelle, nicht firmenweit
        assert "je STELLE" in out["hinweis"]

    def test_bewerbungen_mit_status_und_terminen(self, tmp_db):
        from bewerbungs_assistent.tools import bewerbungen
        self._befuellen(tmp_db)
        app_id = tmp_db.get_applications()[0]["id"]
        tmp_db.add_meeting({
            "application_id": app_id, "title": "Zweitgespraech vor Ort",
            "meeting_date": "2026-07-01T10:00:00", "meeting_type": "interview",
        }) if hasattr(tmp_db, "add_meeting") else None
        mcp = _mcp_mit(tmp_db, bewerbungen)
        out = _call(mcp, "firma_kontext", {"firmenname": "Werftbau"})
        assert out["gefunden"] is True
        assert len(out["bewerbungen"]) == 1
        b = out["bewerbungen"][0]
        assert b["status"] == "abgelehnt"
        assert b["beworben_am"] == "2026-06-04"

    def test_unbekannte_firma_ehrliche_antwort(self, tmp_db):
        from bewerbungs_assistent.tools import bewerbungen
        self._befuellen(tmp_db)
        mcp = _mcp_mit(tmp_db, bewerbungen)
        out = _call(mcp, "firma_kontext", {"firmenname": "Voellig Unbekannt AG"})
        assert out["gefunden"] is False
        assert "NICHT aus PBP" in out["hinweis"]

    def test_normalisierung_rechtsformen(self):
        from bewerbungs_assistent.tools.bewerbungen import (
            _firma_matcht, _firma_normalisieren)
        assert _firma_normalisieren("Halbleiterwerk Nord GmbH") == "halbleiterwerk nord"
        assert _firma_matcht("Halbleiterwerk Nord GmbH",
                             _firma_normalisieren("Halbleiterwerk"))
        assert not _firma_matcht("Siemens AG",
                                 _firma_normalisieren("Halbleiterwerk"))

    def test_regel_in_server_instructions_und_willkommen(self, tmp_db):
        from bewerbungs_assistent.server import PBP_INSTRUCTIONS
        assert "firma_kontext" in PBP_INSTRUCTIONS
        from bewerbungs_assistent.tools.workflows import _prompt_registry
        text = _prompt_registry(tmp_db)["willkommen"]()
        assert "firma_kontext" in text
