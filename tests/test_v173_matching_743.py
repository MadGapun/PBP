"""Tests fuer v1.7.3 — #743: Auto-Matching haerten (E17).

User-Fund 2026-07-02: Vermittler-Mails (gleiche Absender-Domain, anderer
Berater/Endkunde/Titel) wurden mit Konfidenz 70% an inhaltlich fremde,
laengst abgeschlossene Bewerbungen gehaengt. Zwei Matcher beteiligt:

1. ``database.auto_assign_document`` (#177): Dateiname-Matcher, Auto-Link
   ab 0.7, kein Status-Filter → jetzt 0.9-Schwelle + Archiv-Sperre.
2. ``email_service.match_email_to_application`` (#523): Domain-Signal 0.9
   nicht diskriminierend bei Agenturen → jetzt Archiv-Sperre (ausser
   exakter kontakt_email), Ambiguitaets-Check + Vermittler-Domain-Liste.

Leitprinzip bleibt #523: „Im Zweifel unverknuepft."
"""
import asyncio
import os
import tempfile

import pytest

from bewerbungs_assistent.services.email_service import (
    match_email_to_application,
    _is_recruiter_domain,
)


# =====================================================================
# E-Mail-Matcher (pure function, keine DB)
# =====================================================================

def _hays_app(status="abgelehnt", **overrides):
    app = {
        "id": "APP-ALT",
        "company": "Hays",
        "title": "Interim Projektleiter ERP CloudSuite",
        "kontakt_email": "maria.beraterin@hays.de",
        "ansprechpartner": "Maria Beraterin",
        "url": "",
        "status": status,
        "created_at": "2026-03-01T10:00:00",
    }
    app.update(overrides)
    return app


class TestArchivSperre:
    def test_agentur_mail_neuer_berater_archivierte_bewerbung_unverknuepft(self):
        """Kern-Fall aus #743: neue Hays-Mail (anderer Berater, anderes Thema)
        darf NICHT an der abgelehnten Hays-Bewerbung landen."""
        apps = [_hays_app(status="abgelehnt")]
        parsed = {
            "sender": "Hendrik Anders <hendrik.anders@hays.de>",
            "subject": "Technischer Zeichner (m/w/d) - Referenz 882117",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id is None, "Archiv-Bewerbung darf nicht per Domain-Signal matchen"
        assert score == 0.0

    def test_zurueckgezogene_bewerbung_ebenfalls_gesperrt(self):
        apps = [_hays_app(status="zurueckgezogen")]
        parsed = {
            "sender": "someone.else@hays.de",
            "subject": "Business Solutions Manager ERP-Umfeld",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id is None

    def test_exakte_kontakt_email_matcht_auch_archivierte_bewerbung(self):
        """Antwort der bekannten Beraterin zur alten Bewerbung gehoert dorthin."""
        apps = [_hays_app(status="abgelehnt")]
        parsed = {
            "sender": "Maria Beraterin <maria.beraterin@hays.de>",
            "subject": "RE: Ihre Bewerbung",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id == "APP-ALT"
        assert score >= 0.95

    def test_aktive_bewerbung_gewinnt_vor_archivierter_gleicher_domain(self):
        """Alte abgelehnte + neue aktive Bewerbung derselben Agentur:
        die aktive bekommt die Mail (Titel-Signal loest die Ambiguitaet)."""
        apps = [
            _hays_app(status="abgelehnt"),
            _hays_app(
                id="APP-NEU", status="beworben",
                title="Projektmanager PLM Migration",
                kontakt_email="neuer.berater@hays.de",
                ansprechpartner="Neuer Berater",
                created_at="2026-06-20T10:00:00",
            ),
        ]
        parsed = {
            "sender": "noreply@hays.de",
            "subject": "Ihre Bewerbung als Projektmanager PLM Migration",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id == "APP-NEU"


class TestAmbiguitaet:
    def test_zwei_aktive_gleiche_domain_ohne_inhalt_unverknuepft(self):
        """Zwei aktive Bewerbungen ueber dieselbe Agentur, Mail ohne
        inhaltliches Signal → Domain ist nicht diskriminierend → unverknuepft."""
        apps = [
            _hays_app(id="APP-1", status="beworben", title="Konstrukteur Anlagenbau"),
            _hays_app(
                id="APP-2", status="beworben",
                title="Projektmanager PLM Migration",
                kontakt_email="anders.berater@hays.de",
                ansprechpartner="Anders Berater",
            ),
        ]
        parsed = {
            "sender": "dritte.person@hays.de",
            "subject": "Neue Position im Angebot",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id is None
        assert score == 0.0

    def test_titel_signal_loest_ambiguitaet_auf(self):
        apps = [
            _hays_app(id="APP-1", status="beworben", title="Konstrukteur Anlagenbau"),
            _hays_app(
                id="APP-2", status="beworben",
                title="Projektmanager PLM Migration",
                kontakt_email="anders.berater@hays.de",
            ),
        ]
        parsed = {
            "sender": "dritte.person@hays.de",
            "subject": "Update zu Ihrer Bewerbung: Projektmanager PLM Migration",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id == "APP-2"

    def test_ansprechpartner_signal_loest_ambiguitaet_auf(self):
        apps = [
            _hays_app(id="APP-1", status="beworben", title="Konstrukteur Anlagenbau"),
            _hays_app(
                id="APP-2", status="beworben",
                title="Projektmanager PLM",
                kontakt_email="anders.berater@hays.de",
                ansprechpartner="Anders Berater",
            ),
        ]
        parsed = {
            "sender": "Anders Berater <anders.berater2@hays.de>",
            "subject": "Rueckmeldung",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id == "APP-2"


class TestRecruiterDomains:
    def test_is_recruiter_domain(self):
        assert _is_recruiter_domain("hays.de")
        assert _is_recruiter_domain("mail.sthree.com")
        assert not _is_recruiter_domain("siemens.com")
        assert not _is_recruiter_domain("")

    def test_recruiter_domain_ohne_inhalt_kein_match_trotz_aktiver_bewerbung(self):
        """Auch bei nur EINER aktiven Agentur-Bewerbung: Domain-Signal allein
        reicht bei Vermittlern nicht — jede Hays-Mail kommt von hays.de."""
        apps = [_hays_app(status="beworben")]
        parsed = {
            "sender": "unbekannt@hays.de",
            "subject": "Neue Vakanz fuer Sie",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id is None
        assert score == 0.0

    def test_recruiter_domain_mit_titel_signal_matcht(self):
        """Absage/Update der Agentur MIT Stellenbezug matcht weiterhin —
        Regression-Schutz fuer den Absage-Workflow."""
        apps = [_hays_app(status="beworben")]
        parsed = {
            "sender": "noreply@hays.de",
            "subject": "Absage: Interim Projektleiter ERP CloudSuite",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id == "APP-ALT"
        assert score >= 0.90


class TestRegressionNormaleFirmen:
    def test_aktive_plus_archivierte_gleiche_firma_matcht_aktive(self):
        """Review-Fund v1.7.3: eine alte abgelehnte Bewerbung derselben
        Firma darf den einzigen aktiven Kandidaten NICHT als 'ambig'
        blocken — HR-Mail der Firma gehoert zur aktiven Bewerbung."""
        apps = [
            {
                "id": "APP-ALT", "company": "Siemens",
                "kontakt_email": "hr@siemens.com", "ansprechpartner": "",
                "title": "PLM Architect", "url": "", "status": "abgelehnt",
                "created_at": "2025-11-01T10:00:00",
            },
            {
                "id": "APP-NEU", "company": "Siemens",
                "kontakt_email": "", "ansprechpartner": "",
                "title": "Solution Architect", "url": "", "status": "beworben",
                "created_at": "2026-06-01T10:00:00",
            },
        ]
        parsed = {
            "sender": "recruiting@siemens.com",
            "subject": "Ihre Unterlagen",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id == "APP-NEU", \
            "Archivierte Bewerbung darf den aktiven Einzelkandidaten nicht blocken"
        assert score >= 0.90

    def test_einzelne_firma_domain_match_bleibt_erhalten(self):
        """#523-Verhalten fuer normale Firmen unveraendert: HR-Mail von der
        Firmen-Domain matcht die einzige Bewerbung dort — auch ohne
        inhaltliches Signal."""
        apps = [{
            "id": "APP-1", "company": "Siemens",
            "kontakt_email": "", "ansprechpartner": "",
            "title": "PLM Architect", "url": "", "status": "beworben",
        }]
        parsed = {
            "sender": "recruiting@siemens.com",
            "subject": "Bewerbung",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id == "APP-1"
        assert score >= 0.90

    def test_absage_an_aktive_bewerbung_matcht_weiter(self):
        """Absage-Mails kommen zu AKTIVEN Bewerbungen — muessen matchen,
        sonst bricht das Status-Routing (#643)."""
        apps = [{
            "id": "APP-1", "company": "Acme Industries",
            "kontakt_email": "hr@acme-industries.de",
            "ansprechpartner": "", "title": "Senior Engineer",
            "url": "", "status": "interview",
        }]
        parsed = {
            "sender": "no-reply@acme-industries.de",
            "subject": "Absage zu Ihrer Bewerbung als Senior Engineer",
            "_direction": "eingang",
        }
        app_id, score = match_email_to_application(parsed, apps)
        assert app_id == "APP-1"
        assert score >= 0.90


# =====================================================================
# Dateiname-Matcher auto_assign_document (DB, isoliert via tmp_path)
# =====================================================================

@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    # Harte Isolations-Pruefung (QA-Regel seit 2026-06-10)
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


def _doc_link(db, doc_id):
    conn = db.connect()
    row = conn.execute(
        "SELECT linked_application_id FROM documents WHERE id=?", (doc_id,)
    ).fetchone()
    return row["linked_application_id"] if row else None


class TestAutoAssignDocument:
    def test_firma_archiviert_kein_autolink(self, tmp_db):
        """Kern-Fall #743: 'AW Hays....msg' darf nicht an der abgelehnten
        Hays-Bewerbung landen — nur Vorschlag mit Warnhinweis."""
        app_id = tmp_db.add_application(
            {"title": "Projektleiter", "company": "Hays", "status": "abgelehnt"})
        doc_id = tmp_db.add_document({
            "filename": "AW Hays - 882117_1 Technischer Zeichner.msg",
            "filepath": "/fake/mail.msg", "doc_type": "email",
        })
        assert _doc_link(tmp_db, doc_id) is None, \
            "Archiv-Bewerbung darf nicht auto-verknuepft werden"
        # Vorschlags-Mechanik liefert den Warnhinweis
        result = tmp_db.auto_assign_document(doc_id, "AW Hays - Anfrage.msg")
        assert result["auto_verknuepft"] is False
        assert "abgeschlossen" in result.get("hinweis", "")
        assert result["match"]["bewerbung_id_voll"] == app_id

    def test_firma_und_doctyp_archiviert_kein_autolink(self, tmp_db):
        """Auch der 0.95-Zweig (Firma+Doku-Typ) respektiert die Archiv-Sperre."""
        tmp_db.add_application(
            {"title": "Projektleiter", "company": "Hays", "status": "zurueckgezogen"})
        doc_id = tmp_db.add_document({
            "filename": "Lebenslauf_Hays.pdf",
            "filepath": "/fake/cv.pdf", "doc_type": "lebenslauf",
        })
        assert _doc_link(tmp_db, doc_id) is None

    def test_nur_firma_im_dateinamen_aktiv_nur_noch_vorschlag(self, tmp_db):
        """E17.2: der 0.7-Zweig verknuepft nicht mehr automatisch (war die
        gemeldete 70%-Konfidenz), sondern liefert einen Vorschlag."""
        app_id = tmp_db.add_application(
            {"title": "Engineer", "company": "Siemens", "status": "beworben"})
        doc_id = tmp_db.add_document({
            "filename": "Siemens_Unterlagen.pdf",
            "filepath": "/fake/u.pdf", "doc_type": "sonstiges",
        })
        assert _doc_link(tmp_db, doc_id) is None
        result = tmp_db.auto_assign_document(doc_id, "Siemens_Unterlagen.pdf")
        assert result["confidence"] == 0.7
        assert result["auto_verknuepft"] is False
        assert app_id[:8] in result.get("hinweis", "")

    def test_firma_und_doctyp_aktiv_autolink_bleibt(self, tmp_db):
        """Regression: der 0.95-Zweig (Firma + Doku-Typ) verknuepft aktive
        Bewerbungen weiterhin automatisch, inkl. Timeline-Event."""
        app_id = tmp_db.add_application(
            {"title": "Engineer", "company": "Siemens", "status": "beworben"})
        doc_id = tmp_db.add_document({
            "filename": "Anschreiben_Siemens.pdf",
            "filepath": "/fake/a.pdf", "doc_type": "anschreiben",
        })
        assert _doc_link(tmp_db, doc_id) == app_id
        conn = tmp_db.connect()
        events = conn.execute(
            "SELECT notes FROM application_events WHERE application_id=?",
            (app_id,)
        ).fetchall()
        assert any("automatisch verknuepft" in (e["notes"] or "") for e in events)

    def test_gleiche_konfidenz_aktive_gewinnt(self, tmp_db):
        """Tie-Break: bei gleicher Konfidenz gewinnt die aktive Bewerbung."""
        tmp_db.add_application(
            {"title": "Alt", "company": "Siemens", "status": "abgelehnt"})
        app_aktiv = tmp_db.add_application(
            {"title": "Neu", "company": "Siemens", "status": "beworben"})
        doc_id = tmp_db.add_document({
            "filename": "Anschreiben_Siemens.pdf",
            "filepath": "/fake/a2.pdf", "doc_type": "anschreiben",
        })
        assert _doc_link(tmp_db, doc_id) == app_aktiv


# =====================================================================
# E17.4: Warnhinweis im Analyse-Plan (#686)
# =====================================================================

@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v173_743_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    assert tmpdir in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _make_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import dokumente
    import logging
    mcp = FastMCP("test")
    dokumente.register(mcp, db, logging.getLogger("test"))
    return mcp


def test_743_analyse_plan_warnt_bei_abgeschlossener_bewerbung(setup_env):
    db = setup_env
    db.add_application(
        {"title": "Projektleiter", "company": "Musterfirma GmbH", "status": "abgelehnt"})
    db.add_document({
        "filename": "Mail_neu.eml", "filepath": "/fake/mail_neu.eml",
        "doc_type": "email",
        "extracted_text": "Musterfirma GmbH hat eine neue Position fuer Sie.",
    })
    mcp = _make_mcp(db)
    result = _call(mcp, "analyse_plan_erstellen", {})
    z = result["bewerbungs_zuordnungen"]
    assert z, "Zuordnungsvorschlag erwartet"
    eintrag = next(e for e in z if e["dateiname"] == "Mail_neu.eml")
    assert "achtung" in eintrag
    assert "abgeschlossen" in eintrag["achtung"]


def test_743_analyse_plan_keine_warnung_bei_aktiver_bewerbung(setup_env):
    db = setup_env
    db.add_application(
        {"title": "Projektleiter", "company": "Musterfirma GmbH", "status": "beworben"})
    db.add_document({
        "filename": "Mail_neu.eml", "filepath": "/fake/mail_neu.eml",
        "doc_type": "email",
        "extracted_text": "Musterfirma GmbH bestaetigt den Eingang.",
    })
    mcp = _make_mcp(db)
    result = _call(mcp, "analyse_plan_erstellen", {})
    z = result["bewerbungs_zuordnungen"]
    assert z, "Zuordnungsvorschlag erwartet"
    eintrag = next(e for e in z if e["dateiname"] == "Mail_neu.eml")
    assert "achtung" not in eintrag
