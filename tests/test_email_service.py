"""Tests for email service — parsing, matching, status detection, meeting extraction (#136)."""

import json
import os
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bewerbungs_assistent.database import Database, SCHEMA_VERSION
from bewerbungs_assistent.services.email_service import (
    detect_direction,
    detect_email_status,
    extract_meeting_links,
    extract_sender_domain,
    extract_sender_email,
    match_email_to_application,
    extract_meetings_from_email,
    extract_rejection_feedback,
    parse_eml,
    save_attachments,
    find_duplicate_document,
)


@pytest.fixture
def tmp_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


@pytest.fixture
def sample_eml(tmp_path):
    """Create a simple .eml file for testing."""
    msg = MIMEText("Vielen Dank für Ihre Bewerbung. Wir haben diese erhalten.")
    msg["Subject"] = "Eingangsbestätigung - PLM Architect"
    msg["From"] = "hr@siemens.com"
    msg["To"] = "markus@example.com"
    msg["Date"] = "Fri, 20 Mar 2026 10:00:00 +0100"
    path = tmp_path / "test_mail.eml"
    path.write_bytes(msg.as_bytes())
    return str(path)


@pytest.fixture
def interview_eml(tmp_path):
    """Create an interview invitation .eml file."""
    body = """Sehr geehrter Herr Mustermann,

wir möchten Sie gerne zu einem Vorstellungsgespräch einladen.

Termin: am 27.03.2026 um 14:00 Uhr

Bitte nutzen Sie folgenden Link:
https://teams.microsoft.com/l/meetup-join/19%3Ameeting_abc123

Mit freundlichen Grüßen,
HR Team"""
    msg = MIMEText(body)
    msg["Subject"] = "Einladung zum Vorstellungsgespräch - PLM Architect"
    msg["From"] = "recruiter@firma-xy.de"
    msg["To"] = "markus@example.com"
    msg["Date"] = "Sat, 21 Mar 2026 09:00:00 +0100"
    path = tmp_path / "interview_invite.eml"
    path.write_bytes(msg.as_bytes())
    return str(path)


@pytest.fixture
def rejection_eml(tmp_path):
    """Create a rejection email."""
    body = """Sehr geehrter Herr Mustermann,

vielen Dank für Ihr Interesse und Ihre Bewerbung.
Leider müssen wir Ihnen mitteilen, dass wir uns für andere Kandidaten entschieden haben.
Ihr Profil passt nicht zu den aktuellen Anforderungen im Bereich Embedded Systems.

Wir wünschen Ihnen alles Gute.

Mit freundlichen Grüßen"""
    msg = MIMEText(body)
    msg["Subject"] = "Ihre Bewerbung - Absage"
    msg["From"] = "hr@bosch.com"
    msg["To"] = "markus@example.com"
    path = tmp_path / "rejection.eml"
    path.write_bytes(msg.as_bytes())
    return str(path)


@pytest.fixture
def eml_with_attachment(tmp_path):
    """Create an .eml file with a PDF attachment."""
    msg = MIMEMultipart()
    msg["Subject"] = "Vertragsunterlagen - PLM Projekt"
    msg["From"] = "hr@siemens.com"
    msg["To"] = "markus@example.com"
    msg["Date"] = "Mon, 23 Mar 2026 15:00:00 +0100"
    msg.attach(MIMEText("Anbei die Vertragsunterlagen."))
    # Add a fake PDF attachment
    att = MIMEBase("application", "pdf")
    att.set_payload(b"FAKE_PDF_CONTENT_" * 10)
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", "attachment", filename="Rahmenvertrag.pdf")
    msg.attach(att)
    path = tmp_path / "contract.eml"
    path.write_bytes(msg.as_bytes())
    return str(path)


class TestSchemaV16:
    def test_schema_version_is_19(self, tmp_db):
        assert SCHEMA_VERSION == 26

    def test_application_emails_table_exists(self, tmp_db):
        conn = tmp_db.connect()
        cols = conn.execute("PRAGMA table_info(application_emails)").fetchall()
        col_names = {c["name"] for c in cols}
        assert "id" in col_names
        assert "application_id" in col_names
        assert "subject" in col_names
        assert "sender" in col_names
        assert "direction" in col_names
        assert "detected_status" in col_names

    def test_application_meetings_table_exists(self, tmp_db):
        conn = tmp_db.connect()
        cols = conn.execute("PRAGMA table_info(application_meetings)").fetchall()
        col_names = {c["name"] for c in cols}
        assert "id" in col_names
        assert "application_id" in col_names
        assert "meeting_date" in col_names
        assert "meeting_url" in col_names
        assert "platform" in col_names

    def test_documents_has_content_hash(self, tmp_db):
        conn = tmp_db.connect()
        cols = conn.execute("PRAGMA table_info(documents)").fetchall()
        col_names = {c["name"] for c in cols}
        assert "content_hash" in col_names


class TestEmailParsing:
    def test_parse_eml_basic(self, sample_eml):
        result = parse_eml(sample_eml)
        assert "Eingangsbestätigung" in result["subject"]
        assert "siemens.com" in result["sender"]
        assert "markus@example.com" in result["recipients"]
        assert "Bewerbung" in result["body_text"]
        assert result["source_format"] == "eml"

    def test_parse_eml_with_attachment(self, eml_with_attachment):
        result = parse_eml(eml_with_attachment)
        assert "Vertragsunterlagen" in result["subject"]
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["filename"] == "Rahmenvertrag.pdf"

    def test_parse_eml_date(self, sample_eml):
        result = parse_eml(sample_eml)
        assert result["sent_date"] is not None
        assert "2026-03-20" in result["sent_date"]


class TestDirectionDetection:
    def test_incoming_email(self):
        assert detect_direction("hr@siemens.com", "markus@example.com") == "eingang"

    def test_outgoing_email(self):
        assert detect_direction("markus@example.com", "markus@example.com") == "ausgang"

    def test_outgoing_with_name(self):
        assert detect_direction("Markus <markus@example.com>", "markus@example.com") == "ausgang"

    def test_no_profile_email(self):
        assert detect_direction("anyone@anywhere.com", "") == "eingang"


class TestSenderExtraction:
    def test_extract_email_simple(self):
        assert extract_sender_email("hr@siemens.com") == "hr@siemens.com"

    def test_extract_email_with_name(self):
        assert extract_sender_email("Hans Mueller <hr@siemens.com>") == "hr@siemens.com"

    def test_extract_domain(self):
        assert extract_sender_domain("HR <hr@siemens.com>") == "siemens.com"

    def test_extract_domain_no_email(self):
        assert extract_sender_domain("no-email-here") == ""


class TestApplicationMatching:
    def test_match_by_kontakt_email(self):
        apps = [
            {"id": "a1", "company": "Siemens", "kontakt_email": "hr@siemens.com",
             "ansprechpartner": "", "title": "PLM Architect", "url": ""},
        ]
        app_id, confidence = match_email_to_application(
            {"sender": "hr@siemens.com", "subject": "Test", "recipients": ""},
            apps,
        )
        assert app_id == "a1"
        assert confidence >= 0.9

    def test_match_by_domain(self):
        apps = [
            {"id": "a1", "company": "Siemens", "kontakt_email": "other@siemens.com",
             "ansprechpartner": "", "title": "PLM Architect", "url": ""},
        ]
        app_id, confidence = match_email_to_application(
            {"sender": "recruiter@siemens.com", "subject": "Update", "recipients": ""},
            apps,
        )
        assert app_id == "a1"
        assert confidence >= 0.7

    def test_match_by_company_in_sender(self):
        apps = [
            {"id": "a2", "company": "Nordex", "kontakt_email": "",
             "ansprechpartner": "", "title": "PM Wind Energy", "url": ""},
        ]
        app_id, confidence = match_email_to_application(
            {"sender": "jobs@nordex.com", "subject": "Einladung", "recipients": ""},
            apps,
        )
        assert app_id == "a2"
        assert confidence >= 0.5

    def test_no_match_below_threshold(self):
        apps = [
            {"id": "a1", "company": "Siemens", "kontakt_email": "",
             "ansprechpartner": "", "title": "Engineer", "url": ""},
        ]
        app_id, confidence = match_email_to_application(
            {"sender": "random@gmail.com", "subject": "Newsletter", "recipients": ""},
            apps,
        )
        assert app_id is None
        assert confidence == 0.0

    def test_match_empty_applications(self):
        app_id, confidence = match_email_to_application(
            {"sender": "hr@test.com", "subject": "Test", "recipients": ""},
            [],
        )
        assert app_id is None


class TestStatusDetection:
    def test_detect_confirmation(self):
        status, conf = detect_email_status(
            "Eingangsbestätigung",
            "Vielen Dank für Ihre Bewerbung. Wir haben diese erhalten.",
        )
        assert status == "beworben"
        assert conf > 0.5

    def test_detect_interview(self):
        status, conf = detect_email_status(
            "Einladung zum Vorstellungsgespräch",
            "Wir möchten Sie gerne zu einem Interview einladen.",
        )
        assert status == "interview"
        assert conf > 0.5

    def test_detect_rejection(self):
        status, conf = detect_email_status(
            "Ihre Bewerbung",
            "Leider müssen wir Ihnen mitteilen, dass wir uns für andere Kandidaten entschieden haben.",
        )
        assert status == "abgelehnt"
        assert conf > 0.5

    def test_detect_offer(self):
        status, conf = detect_email_status(
            "Vertragsangebot",
            "Wir freuen uns Ihnen ein Vertragsangebot zu unterbreiten. Anbei die Vertragsunterlagen.",
        )
        assert status == "angebot"
        assert conf > 0.5

    def test_no_status_detected(self):
        status, conf = detect_email_status(
            "Mittagessen am Freitag?",
            "Hast du Lust auf Sushi?",
        )
        assert status is None
        assert conf == 0.0

    def test_english_rejection(self):
        status, conf = detect_email_status(
            "Your Application",
            "We regret to inform you that the position has been filled.",
        )
        assert status == "abgelehnt"
        assert conf > 0.5


class TestMeetingExtraction:
    def test_extract_teams_link(self):
        text = "Join here: https://teams.microsoft.com/l/meetup-join/19%3Ameeting_abc123 for the call."
        links = extract_meeting_links(text)
        assert len(links) == 1
        assert links[0]["platform"] == "teams"
        assert "teams.microsoft.com" in links[0]["url"]

    def test_extract_zoom_link(self):
        text = "Meeting: https://us02web.zoom.us/j/1234567890"
        links = extract_meeting_links(text)
        assert len(links) == 1
        assert links[0]["platform"] == "zoom"

    def test_extract_google_meet_link(self):
        text = "Join at https://meet.google.com/abc-defg-hij"
        links = extract_meeting_links(text)
        assert len(links) == 1
        assert links[0]["platform"] == "google_meet"

    def test_no_links(self):
        links = extract_meeting_links("This is a plain email without meeting links.")
        assert len(links) == 0

    def test_meeting_from_email_with_date_and_link(self):
        parsed = {
            "subject": "Vorstellungsgespräch",
            "body_text": "Termin am 27.03.2026 um 14:00 Uhr\nhttps://teams.microsoft.com/l/meetup-join/abc",
            "body_html": "",
            "attachments": [],
        }
        meetings = extract_meetings_from_email(parsed)
        assert len(meetings) >= 1
        assert meetings[0]["start"] is not None
        assert "teams" in (meetings[0].get("meeting_url") or "")

    def test_meeting_link_only(self):
        parsed = {
            "subject": "Teams Meeting",
            "body_text": "Here is the link: https://teams.microsoft.com/l/meetup-join/xyz",
            "body_html": "",
            "attachments": [],
        }
        meetings = extract_meetings_from_email(parsed)
        assert len(meetings) >= 1
        assert meetings[0]["meeting_url"] is not None


class TestRejectionFeedback:
    def test_extract_feedback(self):
        body = """Sehr geehrter Herr Mustermann,

leider müssen wir Ihnen absagen.

Ihr Profil passt nicht zu unseren aktuellen Anforderungen im Bereich Cloud Engineering.
Wir suchen jemanden mit mehr Erfahrung in AWS und Kubernetes.

Wir wünschen Ihnen alles Gute."""
        feedback = extract_rejection_feedback(body)
        assert feedback is not None
        assert "Profil passt nicht" in feedback

    def test_no_feedback_in_generic_rejection(self):
        body = "Leider müssen wir absagen. Vielen Dank."
        feedback = extract_rejection_feedback(body)
        assert feedback is None


class TestAttachmentSaving:
    def test_save_attachments(self, tmp_path):
        parsed = {
            "attachments": [
                {"filename": "CV.pdf", "payload": b"FAKE_PDF" * 20, "content_type": "application/pdf"},
                {"filename": "meeting.ics", "payload": b"BEGIN:VCALENDAR", "content_type": "text/calendar"},
            ],
        }
        saved = save_attachments(parsed, str(tmp_path / "docs"))
        # .ics should be skipped
        assert len(saved) == 1
        assert saved[0]["filename"] == "CV.pdf"
        assert saved[0]["content_hash"]
        assert Path(saved[0]["filepath"]).exists()

    def test_skip_tiny_files(self, tmp_path):
        parsed = {"attachments": [{"filename": "tiny.txt", "payload": b"hi", "content_type": "text/plain"}]}
        saved = save_attachments(parsed, str(tmp_path / "docs"))
        assert len(saved) == 0

    def test_duplicate_filenames(self, tmp_path):
        target = tmp_path / "docs"
        target.mkdir()
        (target / "file.pdf").write_bytes(b"existing")
        parsed = {"attachments": [{"filename": "file.pdf", "payload": b"NEWCONTENT" * 20, "content_type": ""}]}
        saved = save_attachments(parsed, str(target))
        assert len(saved) == 1
        assert saved[0]["filename"] != "file.pdf"  # Should be renamed


class TestDuplicateDetection:
    def test_find_duplicate(self):
        docs = [
            {"id": "d1", "content_hash": "abc123"},
            {"id": "d2", "content_hash": "def456"},
        ]
        assert find_duplicate_document("abc123", docs) == "d1"
        assert find_duplicate_document("xyz789", docs) is None


class TestDatabaseEmailMethods:
    def test_add_and_get_email(self, tmp_db):
        # Create a profile first
        tmp_db.save_profile({"name": "Test User", "email": "test@example.com"})
        # Create an application
        app_id = tmp_db.add_application({
            "title": "Test Job",
            "company": "Test Corp",
            "status": "beworben",
        })
        email_id = tmp_db.add_email({
            "application_id": app_id,
            "filename": "test.eml",
            "subject": "Eingangsbestätigung",
            "sender": "hr@testcorp.com",
            "recipients": "test@example.com",
            "direction": "eingang",
            "body_text": "Danke für Ihre Bewerbung.",
            "detected_status": "beworben",
            "detected_status_confidence": 0.8,
        })
        assert email_id

        em = tmp_db.get_email(email_id)
        assert em is not None
        assert em["subject"] == "Eingangsbestätigung"
        assert em["sender"] == "hr@testcorp.com"
        assert em["direction"] == "eingang"

    def test_get_emails_for_application(self, tmp_db):
        tmp_db.save_profile({"name": "Test", "email": "t@t.com"})
        app_id = tmp_db.add_application({"title": "Job", "company": "Corp", "status": "beworben"})
        tmp_db.add_email({"application_id": app_id, "filename": "a.eml", "subject": "Mail 1", "sender": "a@b.com"})
        tmp_db.add_email({"application_id": app_id, "filename": "b.eml", "subject": "Mail 2", "sender": "c@d.com"})
        emails = tmp_db.get_emails_for_application(app_id)
        assert len(emails) == 2

    def test_unmatched_emails(self, tmp_db):
        tmp_db.save_profile({"name": "Test", "email": "t@t.com"})
        tmp_db.add_email({"application_id": None, "filename": "unmatched.eml", "subject": "Unknown", "sender": "x@y.com"})
        unmatched = tmp_db.get_unmatched_emails()
        assert len(unmatched) == 1

    def test_add_and_get_meeting(self, tmp_db):
        tmp_db.save_profile({"name": "Test", "email": "t@t.com"})
        app_id = tmp_db.add_application({"title": "Job", "company": "Corp", "status": "interview"})
        future = (datetime.now() + timedelta(days=5)).isoformat()
        mid = tmp_db.add_meeting({
            "application_id": app_id,
            "title": "Interview",
            "meeting_date": future,
            "meeting_url": "https://teams.microsoft.com/l/meetup-join/abc",
            "platform": "teams",
        })
        assert mid

        meetings = tmp_db.get_upcoming_meetings(days=30)
        assert len(meetings) >= 1
        assert meetings[0]["title"] == "Interview"
        assert meetings[0]["app_company"] == "Corp"

    def test_get_meetings_for_application(self, tmp_db):
        tmp_db.save_profile({"name": "Test", "email": "t@t.com"})
        app_id = tmp_db.add_application({"title": "Job", "company": "Corp", "status": "interview"})
        future = (datetime.now() + timedelta(days=3)).isoformat()
        tmp_db.add_meeting({"application_id": app_id, "title": "Call 1", "meeting_date": future})
        tmp_db.add_meeting({"application_id": app_id, "title": "Call 2", "meeting_date": future})
        meetings = tmp_db.get_meetings_for_application(app_id)
        assert len(meetings) == 2

    def test_update_meeting(self, tmp_db):
        tmp_db.save_profile({"name": "Test", "email": "t@t.com"})
        app_id = tmp_db.add_application({"title": "Job", "company": "Corp", "status": "interview"})
        future = (datetime.now() + timedelta(days=7)).isoformat()
        mid = tmp_db.add_meeting({"application_id": app_id, "title": "Old Title", "meeting_date": future})
        tmp_db.update_meeting(mid, {"title": "New Title", "notes": "Bring laptop"})
        meetings = tmp_db.get_meetings_for_application(app_id)
        assert meetings[0]["title"] == "New Title"
        assert meetings[0]["notes"] == "Bring laptop"

    def test_delete_meeting(self, tmp_db):
        tmp_db.save_profile({"name": "Test", "email": "t@t.com"})
        app_id = tmp_db.add_application({"title": "Job", "company": "Corp", "status": "interview"})
        future = (datetime.now() + timedelta(days=7)).isoformat()
        mid = tmp_db.add_meeting({"application_id": app_id, "title": "To Delete", "meeting_date": future})
        tmp_db.delete_meeting(mid)
        meetings = tmp_db.get_meetings_for_application(app_id)
        assert len(meetings) == 0

    def test_add_application_event(self, tmp_db):
        tmp_db.save_profile({"name": "Test", "email": "t@t.com"})
        app_id = tmp_db.add_application({"title": "Job", "company": "Corp", "status": "beworben"})
        tmp_db.add_application_event(app_id, "email_eingang", "E-Mail: Eingangsbestätigung")
        conn = tmp_db.connect()
        events = conn.execute(
            "SELECT * FROM application_events WHERE application_id=? AND status='email_eingang'",
            (app_id,),
        ).fetchall()
        assert len(events) == 1
        assert "Eingangsbestätigung" in events[0]["notes"]
