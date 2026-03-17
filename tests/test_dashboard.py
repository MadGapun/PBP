"""Dashboard API Tests — FastAPI TestClient-basierte Tests.

Testet die wichtigsten Dashboard-API-Endpoints mit einer temporaeren
Datenbank. Deckt Status, Profil-CRUD, Validierung, Multi-Profil,
Stellen, Bewerbungen, Paginierung und Factory Reset ab.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def client(tmp_path):
    """FastAPI TestClient mit temporaerer DB."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()

    import bewerbungs_assistent.dashboard as dash
    dash._db = db

    from fastapi.testclient import TestClient
    tc = TestClient(dash.app)
    yield tc

    db.close()
    if "BA_DATA_DIR" in os.environ:
        del os.environ["BA_DATA_DIR"]


# ============================================================
# Status
# ============================================================

class TestStatus:
    def test_status_empty(self, client):
        """Status ohne Profil zeigt has_profile=False."""
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert data["has_profile"] is False
        assert data["profile_name"] is None
        assert data["active_jobs"] == 0
        assert data["applications"] == 0

    def test_status_with_profile(self, client):
        """Status mit Profil zeigt has_profile=True und Namen."""
        client.post("/api/profile", json={"name": "Tester"})
        r = client.get("/api/status")
        data = r.json()
        assert data["has_profile"] is True
        assert data["profile_name"] == "Tester"

    def test_workspace_summary_empty(self, client):
        """Workspace Summary zeigt Onboarding-Zustand ohne Profil."""
        r = client.get("/api/workspace-summary")
        assert r.status_code == 200
        data = r.json()
        assert data["has_profile"] is False
        assert data["readiness"]["stage"] == "onboarding"
        assert data["sources"]["active"] == 0
        assert data["jobs"]["active"] == 0
        assert data["applications"]["total"] == 0

    def test_workspace_summary_profile_needs_building(self, client):
        """Minimales Profil priorisiert den Profil-Ausbau."""
        client.post("/api/profile", json={"name": "Tester"})
        r = client.get("/api/workspace-summary")
        data = r.json()
        assert data["has_profile"] is True
        assert data["readiness"]["stage"] == "profil_aufbauen"
        assert data["profile"]["completeness"] < 60
        assert "Adresse" in data["profile"]["missing_areas"]
        assert data["navigation"]["profile_badge"] is not None

    def test_workspace_summary_counts_sources_search_and_followups(self, client):
        """Workspace Summary verdichtet Quellen, Suche und Follow-ups fuer die Navigation."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={
            "name": "Tester",
            "email": "test@example.com",
            "phone": "+49 40 123456",
            "address": "Musterweg 1",
            "summary": "Erfahrener Berater",
            "preferences": {"stellentyp": "festanstellung"},
        })
        dash._db.add_position({"company": "ACME", "title": "Consultant", "start_date": "2022-01"})
        dash._db.add_education({"institution": "FH Hamburg", "degree": "Bachelor"})
        dash._db.add_skill({"name": "Python", "category": "tool"})
        dash._db.set_setting("active_sources", ["bundesagentur", "stepstone"])
        dash._db.set_setting("last_search_at", datetime.now().isoformat())
        app_id = dash._db.add_application({
            "title": "PLM Consultant",
            "company": "ACME",
            "status": "beworben",
            "applied_at": datetime.now().date().isoformat(),
        })
        due_date = (datetime.now() - timedelta(days=1)).date().isoformat()
        dash._db.add_follow_up(app_id, due_date)

        r = client.get("/api/workspace-summary")
        data = r.json()
        assert data["sources"]["active"] == 2
        assert data["search"]["status"] == "aktuell"
        assert data["applications"]["total"] == 1
        assert data["applications"]["follow_ups_due"] == 1
        assert data["readiness"]["stage"] == "nachfassen"
        assert data["navigation"]["applications_badge"] == "1"


# ============================================================
# Profil CRUD
# ============================================================

class TestProfile:
    def test_get_profile_empty(self, client):
        """GET /api/profile ohne Profil → 404."""
        r = client.get("/api/profile")
        assert r.status_code == 404

    def test_create_profile(self, client):
        """POST /api/profile erstellt Profil."""
        r = client.post("/api/profile", json={
            "name": "Max Mustermann",
            "email": "max@example.com",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        # Verify
        r2 = client.get("/api/profile")
        assert r2.status_code == 200
        assert r2.json()["name"] == "Max Mustermann"
        assert r2.json()["email"] == "max@example.com"

    def test_update_profile(self, client):
        """POST /api/profile aktualisiert bestehendes Profil."""
        client.post("/api/profile", json={"name": "Original"})
        client.post("/api/profile", json={"name": "Updated", "email": "new@test.de"})
        r = client.get("/api/profile")
        assert r.json()["name"] == "Updated"
        assert r.json()["email"] == "new@test.de"


# ============================================================
# Validierung
# ============================================================

class TestValidation:
    def test_profile_name_required(self, client):
        """Profil ohne Name → 400."""
        r = client.post("/api/profile", json={"email": "test@test.de"})
        assert r.status_code == 400
        assert "Name" in r.json()["error"]

    def test_profile_empty_name(self, client):
        """Profil mit leerem Name → 400."""
        r = client.post("/api/profile", json={"name": "   "})
        assert r.status_code == 400

    def test_position_company_required(self, client):
        """Position ohne Firma → 400."""
        client.post("/api/profile", json={"name": "Test"})
        r = client.post("/api/position", json={"title": "Developer"})
        assert r.status_code == 400
        assert "Firma" in r.json()["error"]

    def test_position_title_required(self, client):
        """Position ohne Titel → 400."""
        client.post("/api/profile", json={"name": "Test"})
        r = client.post("/api/position", json={"company": "Firma GmbH"})
        assert r.status_code == 400
        assert "Titel" in r.json()["error"]

    def test_education_institution_required(self, client):
        """Ausbildung ohne Einrichtung → 400."""
        client.post("/api/profile", json={"name": "Test"})
        r = client.post("/api/education", json={"degree": "MSc"})
        assert r.status_code == 400
        assert "Einrichtung" in r.json()["error"]

    def test_skill_name_required(self, client):
        """Skill ohne Name → 400."""
        client.post("/api/profile", json={"name": "Test"})
        r = client.post("/api/skill", json={"category": "fachlich"})
        assert r.status_code == 400
        assert "Name" in r.json()["error"]

    def test_application_title_required(self, client):
        """Bewerbung ohne Stelle → 400."""
        r = client.post("/api/applications", json={"company": "Firma"})
        assert r.status_code == 400
        assert "Stelle" in r.json()["error"]

    def test_application_company_required(self, client):
        """Bewerbung ohne Firma → 400."""
        r = client.post("/api/applications", json={"title": "Job"})
        assert r.status_code == 400
        assert "Firma" in r.json()["error"]


# ============================================================
# Multi-Profil
# ============================================================

class TestMultiProfile:
    def test_list_profiles(self, client):
        """Profil-Liste enthaelt erstelltes Profil."""
        client.post("/api/profile", json={"name": "Profil A"})
        r = client.get("/api/profiles")
        assert r.status_code == 200
        profiles = r.json()["profiles"]
        assert len(profiles) >= 1
        assert any(p["name"] == "Profil A" for p in profiles)

    def test_create_and_switch_profile(self, client):
        """Neues Profil erstellen und wechseln."""
        # Create first profile
        client.post("/api/profile", json={"name": "Profil A"})
        # Create second profile
        r = client.post("/api/profiles/new", json={"name": "Profil B"})
        assert r.status_code == 200
        new_id = r.json()["id"]
        profiles = client.get("/api/profiles").json()["profiles"]
        assert len(profiles) == 2
        assert {p["name"] for p in profiles} == {"Profil A", "Profil B"}

        # Switch to new profile
        r2 = client.post("/api/profiles/switch", json={"profile_id": new_id})
        assert r2.status_code == 200

        # Verify active profile changed
        r3 = client.get("/api/profile")
        assert r3.json()["name"] == "Profil B"

    def test_switch_nonexistent_profile(self, client):
        """Wechsel zu nicht existierendem Profil → 404."""
        r = client.post("/api/profiles/switch", json={"profile_id": "nonexistent"})
        assert r.status_code == 404

    def test_delete_profile(self, client):
        """Profil loeschen."""
        client.post("/api/profile", json={"name": "Profil A"})
        r1 = client.post("/api/profiles/new", json={"name": "Profil B"})
        new_id = r1.json()["id"]

        r2 = client.delete(f"/api/profiles/{new_id}")
        assert r2.status_code == 200

        # Verify deleted
        profiles = client.get("/api/profiles").json()["profiles"]
        assert not any(p.get("id") == new_id for p in profiles)

    def test_new_profile_without_name(self, client):
        """Neues Profil ohne Name → 400."""
        r = client.post("/api/profiles/new", json={})
        assert r.status_code == 400


# ============================================================
# Stellen (Jobs)
# ============================================================

class TestJobs:
    def test_jobs_empty(self, client):
        """Keine Stellen → leere Liste."""
        r = client.get("/api/jobs")
        assert r.status_code == 200
        assert r.json() == []

    def test_jobs_dismissed_empty(self, client):
        """Keine aussortierten Stellen → leere Liste."""
        r = client.get("/api/jobs?active=false")
        assert r.status_code == 200
        assert r.json() == []


# ============================================================
# Bewerbungen
# ============================================================

class TestApplications:
    def test_applications_empty(self, client):
        """Keine Bewerbungen → leere Liste."""
        r = client.get("/api/applications")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["applications"] == []

    def test_create_application(self, client):
        """Bewerbung erstellen."""
        r = client.post("/api/applications", json={
            "title": "PLM Consultant",
            "company": "Siemens",
            "status": "beworben",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        # Verify
        r2 = client.get("/api/applications")
        assert r2.json()["total"] == 1
        assert r2.json()["applications"][0]["company"] == "Siemens"

    def test_pagination(self, client):
        """Paginierung mit limit und offset."""
        # Create 5 applications
        for i in range(5):
            client.post("/api/applications", json={
                "title": f"Job {i}",
                "company": f"Firma {i}",
            })

        # Full list
        r1 = client.get("/api/applications")
        assert r1.json()["total"] == 5

        # Page 1 (2 items)
        r2 = client.get("/api/applications?limit=2&offset=0")
        assert len(r2.json()["applications"]) == 2
        assert r2.json()["total"] == 5

        # Page 2
        r3 = client.get("/api/applications?limit=2&offset=2")
        assert len(r3.json()["applications"]) == 2

        # Page 3 (last item)
        r4 = client.get("/api/applications?limit=2&offset=4")
        assert len(r4.json()["applications"]) == 1


# ============================================================
# Follow-ups
# ============================================================

class TestFollowUps:
    def test_follow_ups_endpoint_respects_active_profile(self, client):
        """API liefert nur Follow-ups des aktiven Profils."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Profil A"})
        app_a = dash._db.add_application({"title": "App A", "company": "Corp A"})
        dash._db.add_follow_up(app_a, (datetime.now() - timedelta(days=1)).date().isoformat())

        r_new = client.post("/api/profiles/new", json={"name": "Profil B"})
        profile_b = r_new.json()["id"]
        client.post("/api/profiles/switch", json={"profile_id": profile_b})
        app_b = dash._db.add_application({"title": "App B", "company": "Corp B"})
        dash._db.add_follow_up(app_b, datetime.now().date().isoformat())

        data_b = client.get("/api/follow-ups").json()
        assert [item["title"] for item in data_b["follow_ups"]] == ["App B"]

        profiles = client.get("/api/profiles").json()["profiles"]
        profile_a = next(p["id"] for p in profiles if p["name"] == "Profil A")
        client.post("/api/profiles/switch", json={"profile_id": profile_a})

        data_a = client.get("/api/follow-ups").json()
        assert [item["title"] for item in data_a["follow_ups"]] == ["App A"]


# ============================================================
# Application Detail (Timeline + Job + Documents)
# ============================================================

class TestApplicationDetail:
    def test_timeline_includes_job_and_documents(self, client):
        """Timeline-Endpoint liefert Job-Details und Dokumente."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        # Create a job first
        dash._db.save_jobs([{
            "hash": "test_job_001", "title": "Engineer",
            "company": "Nordex", "url": "https://nordex.com/job",
            "source": "stepstone", "description": "Wind energy engineer",
            "score": 82,
        }])
        # Create application linked to job
        app_id = dash._db.add_application({
            "title": "Engineer", "company": "Nordex",
            "job_hash": "test_job_001", "status": "beworben",
        })
        # Create and link a document
        doc_id = dash._db.add_document({
            "filename": "anschreiben_nordex.pdf",
            "doc_type": "anschreiben",
        })
        dash._db.link_document_to_application(doc_id, app_id)

        # Fetch detail
        r = client.get(f"/api/application/{app_id}/timeline")
        assert r.status_code == 200
        data = r.json()
        assert data["application"]["title"] == "Engineer"
        # Job details present
        assert data["job"] is not None
        assert data["job"]["company"] == "Nordex"
        assert data["job"]["score"] == 82
        assert data["job"]["source"] == "stepstone"
        assert data["job"]["description"] == "Wind energy engineer"
        # Documents present
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "anschreiben_nordex.pdf"

    def test_timeline_without_job(self, client):
        """Timeline funktioniert auch ohne verknuepften Job."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        app_id = dash._db.add_application({
            "title": "Manuell", "company": "TestFirma",
        })
        r = client.get(f"/api/application/{app_id}/timeline")
        assert r.status_code == 200
        data = r.json()
        assert data["job"] is None
        assert data["documents"] == []

    def test_link_document_to_application(self, client):
        """Dokument via API mit Bewerbung verknuepfen."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        app_id = dash._db.add_application({
            "title": "Job X", "company": "Firma X",
        })
        doc_id = dash._db.add_document({
            "filename": "cv.pdf", "doc_type": "lebenslauf",
        })
        r = client.post(f"/api/applications/{app_id}/link-document",
                        json={"document_id": doc_id})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        # Verify linkage
        docs = dash._db.get_documents_for_application(app_id)
        assert len(docs) == 1
        assert docs[0]["filename"] == "cv.pdf"

    def test_documents_list_endpoint(self, client):
        """Dokumente-Liste-Endpoint liefert alle Dokumente."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        dash._db.add_document({"filename": "cv.pdf", "doc_type": "lebenslauf"})
        dash._db.add_document({"filename": "brief.pdf", "doc_type": "anschreiben"})

        r = client.get("/api/documents")
        assert r.status_code == 200
        assert len(r.json()["documents"]) == 2


# ============================================================
# Gespraechsnotizen
# ============================================================

class TestApplicationNotes:
    def test_add_note(self, client):
        """Notiz zu Bewerbung hinzufuegen."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        app_id = dash._db.add_application({"title": "Job", "company": "Firma"})
        r = client.post(f"/api/applications/{app_id}/notes",
                        json={"text": "Telefonat mit HR, positives Feedback"})
        assert r.status_code == 200
        # Verify in timeline
        r2 = client.get(f"/api/application/{app_id}/timeline")
        notes = [e for e in r2.json()["events"] if e["status"] == "notiz"]
        assert len(notes) == 1
        assert "Telefonat" in notes[0]["notes"]

    def test_add_note_empty_rejected(self, client):
        """Leere Notiz wird abgelehnt."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        app_id = dash._db.add_application({"title": "Job", "company": "Firma"})
        r = client.post(f"/api/applications/{app_id}/notes", json={"text": ""})
        assert r.status_code == 400

    def test_edit_note(self, client):
        """Notiz bearbeiten."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        app_id = dash._db.add_application({"title": "Job", "company": "Firma"})
        dash._db.add_application_note(app_id, "Erste Version")
        # Get the event id
        r = client.get(f"/api/application/{app_id}/timeline")
        note_event = [e for e in r.json()["events"] if e["status"] == "notiz"][0]
        # Update
        r2 = client.put(f"/api/applications/{app_id}/notes/{note_event['id']}",
                        json={"text": "Korrigierte Version"})
        assert r2.status_code == 200
        # Verify
        r3 = client.get(f"/api/application/{app_id}/timeline")
        updated = [e for e in r3.json()["events"] if e["status"] == "notiz"][0]
        assert updated["notes"] == "Korrigierte Version"

    def test_delete_note(self, client):
        """Notiz loeschen (nur Typ 'notiz', nicht Statusaenderungen)."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        app_id = dash._db.add_application({"title": "Job", "company": "Firma"})
        dash._db.add_application_note(app_id, "Wird geloescht")
        r = client.get(f"/api/application/{app_id}/timeline")
        events = r.json()["events"]
        note_event = [e for e in events if e["status"] == "notiz"][0]
        status_event = [e for e in events if e["status"] == "beworben"][0]
        # Delete note
        r2 = client.delete(f"/api/applications/{app_id}/notes/{note_event['id']}")
        assert r2.status_code == 200
        # Try deleting status event (should NOT work)
        r3 = client.delete(f"/api/applications/{app_id}/notes/{status_event['id']}")
        assert r3.status_code == 200  # No error, but nothing deleted
        # Verify: notiz gone, status still there
        r4 = client.get(f"/api/application/{app_id}/timeline")
        remaining = r4.json()["events"]
        assert not any(e["status"] == "notiz" for e in remaining)
        assert any(e["status"] == "beworben" for e in remaining)

    def test_multiple_notes_chronological(self, client):
        """Mehrere Notizen werden chronologisch gespeichert."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        app_id = dash._db.add_application({"title": "Nordex", "company": "Nordex"})
        dash._db.add_application_note(app_id, "Bewerbung abgeschickt")
        dash._db.add_application_note(app_id, "Einladung zum Interview erhalten")
        dash._db.add_application_note(app_id, "Interview war gut, Feedback in 1 Woche")
        r = client.get(f"/api/application/{app_id}/timeline")
        notes = [e for e in r.json()["events"] if e["status"] == "notiz"]
        assert len(notes) == 3


# ============================================================
# Profil-Elemente (Position, Skill, Ausbildung)
# ============================================================

class TestProfileElements:
    def test_add_position(self, client):
        """Position hinzufuegen."""
        client.post("/api/profile", json={"name": "Test"})
        r = client.post("/api/position", json={
            "company": "Tech GmbH",
            "title": "Consultant",
            "start_date": "2020-01",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        # Verify in profile
        profile = client.get("/api/profile").json()
        assert len(profile["positions"]) == 1
        assert profile["positions"][0]["company"] == "Tech GmbH"

    def test_add_skill(self, client):
        """Skill hinzufuegen."""
        client.post("/api/profile", json={"name": "Test"})
        r = client.post("/api/skill", json={
            "name": "Python",
            "category": "tool",
            "level": "experte",
        })
        assert r.status_code == 200

        profile = client.get("/api/profile").json()
        assert len(profile["skills"]) == 1
        assert profile["skills"][0]["name"] == "Python"

    def test_add_education(self, client):
        """Ausbildung hinzufuegen."""
        client.post("/api/profile", json={"name": "Test"})
        r = client.post("/api/education", json={
            "institution": "TU Hamburg",
            "degree": "Master",
            "field_of_study": "Informatik",
        })
        assert r.status_code == 200

        profile = client.get("/api/profile").json()
        assert len(profile["education"]) == 1
        assert profile["education"][0]["institution"] == "TU Hamburg"

    def test_delete_position(self, client):
        """Position loeschen."""
        client.post("/api/profile", json={"name": "Test"})
        r = client.post("/api/position", json={
            "company": "Firma",
            "title": "Dev",
        })
        pos_id = r.json()["id"]
        r2 = client.delete(f"/api/position/{pos_id}")
        assert r2.status_code == 200

        profile = client.get("/api/profile").json()
        assert len(profile["positions"]) == 0


# ============================================================
# CV-Generierung
# ============================================================

class TestCVGeneration:
    def test_cv_no_profile(self, client):
        """CV ohne Profil → 404."""
        r = client.get("/api/cv/generate")
        assert r.status_code == 404

    def test_cv_with_profile(self, client):
        """CV mit Profil enthält Name."""
        client.post("/api/profile", json={
            "name": "Max Mustermann",
            "email": "max@test.de",
        })
        r = client.get("/api/cv/generate")
        assert r.status_code == 200
        data = r.json()
        assert "Max Mustermann" in data["cv_text"]
        assert data["line_count"] > 0


# ============================================================
# Statistiken & Hilfsfunktionen
# ============================================================

class TestStatistics:
    def test_statistics(self, client):
        """Statistiken abrufbar (auch ohne Daten)."""
        r = client.get("/api/statistics")
        assert r.status_code == 200

    def test_search_criteria(self, client):
        """Suchkriterien lesen und setzen."""
        r1 = client.get("/api/search-criteria")
        assert r1.status_code == 200

        r2 = client.post("/api/search-criteria", json={
            "keywords": "PLM, Consultant",
            "location": "Hamburg",
        })
        assert r2.status_code == 200

    def test_profile_completeness_empty(self, client):
        """Vollstaendigkeit ohne Profil = 0%."""
        r = client.get("/api/profile/completeness")
        assert r.status_code == 200
        assert r.json()["completeness"] == 0

    def test_profile_completeness_partial(self, client):
        """Vollstaendigkeit mit teilweisem Profil."""
        client.post("/api/profile", json={
            "name": "Test",
            "email": "test@test.de",
            "city": "Hamburg",
            "summary": "Ein kurzes Summary.",
        })
        r = client.get("/api/profile/completeness")
        data = r.json()
        assert data["completeness"] > 0
        assert data["checks"]["name"] is True
        assert data["checks"]["kontakt"] is True
        assert data["checks"]["adresse"] is True
        assert data["checks"]["zusammenfassung"] is True

    def test_profile_completeness_address_without_city(self, client):
        """Adresse allein zaehlt auch im Dashboard als gueltige Anschrift."""
        client.post("/api/profile", json={
            "name": "Test",
            "email": "test@test.de",
            "address": "Musterweg 1",
        })
        r = client.get("/api/profile/completeness")
        data = r.json()
        assert data["checks"]["adresse"] is True

    def test_next_steps(self, client):
        """Next Steps abrufbar."""
        r = client.get("/api/next-steps")
        assert r.status_code == 200
        assert "steps" in r.json()

    def test_search_status(self, client):
        """Such-Status zeigt 'nie' wenn keine Suche lief."""
        r = client.get("/api/search-status")
        assert r.status_code == 200
        assert r.json()["status"] == "nie"

    def test_search_status_recent(self, client):
        """Aktuelle Suche wird als 'aktuell' markiert."""
        import bewerbungs_assistent.dashboard as dash

        dash._db.set_setting("last_search_at", datetime.now().isoformat())
        r = client.get("/api/search-status")
        assert r.status_code == 200
        assert r.json()["status"] == "aktuell"

    def test_sources_default_all_inactive(self, client):
        """Quellen-API liefert standardmaessig alle Quellen als inaktiv."""
        r = client.get("/api/sources")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert all(source["active"] is False for source in data)

    def test_sources_can_be_updated(self, client):
        """Aktive Quellen koennen gespeichert und erneut geladen werden."""
        r = client.post("/api/sources", json={"active_sources": ["bundesagentur", "stepstone"]})
        assert r.status_code == 200

        r2 = client.get("/api/sources")
        active_sources = {source["key"] for source in r2.json() if source["active"]}
        assert active_sources == {"bundesagentur", "stepstone"}


# ============================================================
# Factory Reset
# ============================================================

class TestFactoryReset:
    def test_reset_without_confirmation(self, client):
        """Reset ohne Bestaetigung → 400."""
        r = client.post("/api/reset", json={})
        assert r.status_code == 400

    def test_reset_clears_data(self, client):
        """Reset loescht alle Daten."""
        client.post("/api/profile", json={"name": "Wird geloescht"})
        r = client.post("/api/reset", json={"confirm": "RESET"})
        assert r.status_code == 200

        # Profile should be gone
        r2 = client.get("/api/status")
        assert r2.json()["has_profile"] is False
