"""Dashboard API Tests — FastAPI TestClient-basierte Tests.

Testet die wichtigsten Dashboard-API-Endpoints mit einer temporaeren
Datenbank. Deckt Status, Profil-CRUD, Validierung, Multi-Profil,
Stellen, Bewerbungen, Paginierung und Factory Reset ab.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

import pytest

from bewerbungs_assistent import __version__

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
# Dashboard Index
# ============================================================

class TestDashboardIndex:
    def test_index_serves_built_frontend(self, client, monkeypatch, tmp_path):
        """Root route serves the built dashboard frontend when available."""
        import bewerbungs_assistent.dashboard as dash

        built_html = tmp_path / "dashboard" / "index.html"
        built_html.parent.mkdir(parents=True, exist_ok=True)
        built_html.write_text("<!doctype html><html><body>NEUE-UI</body></html>", encoding="utf-8")
        monkeypatch.setattr(dash, "DASHBOARD_BUILD_HTML", built_html)

        r = client.get("/")
        assert r.status_code == 200
        assert "NEUE-UI" in r.text
        assert "Dashboard-Fehler" not in r.text

    def test_index_shows_error_page_when_build_missing(self, client, monkeypatch, tmp_path):
        """Missing frontend build no longer falls back to legacy template."""
        import bewerbungs_assistent.dashboard as dash

        missing_html = tmp_path / "does-not-exist" / "index.html"
        monkeypatch.setattr(dash, "DASHBOARD_BUILD_HTML", missing_html)

        r = client.get("/")
        assert r.status_code == 500
        assert "Dashboard-Fehler" in r.text
        assert "nicht gefunden" in r.text
        assert str(missing_html) in r.text
        assert "Bitte Templates installieren" not in r.text

    def test_index_shows_error_page_when_build_unreadable(self, client, monkeypatch):
        """Read failures render a dedicated error page instead of old UI."""
        import bewerbungs_assistent.dashboard as dash

        class BrokenBuild:
            def exists(self):
                return True

            def read_text(self, encoding="utf-8"):
                raise OSError("kaputt")

            def __str__(self):
                return "BROKEN/index.html"

        monkeypatch.setattr(dash, "DASHBOARD_BUILD_HTML", BrokenBuild())

        r = client.get("/")
        assert r.status_code == 500
        assert "Dashboard-Fehler" in r.text
        assert "konnte nicht geladen werden" in r.text
        assert "kaputt" in r.text


# ============================================================
# Status
# ============================================================

class TestStatus:
    def test_status_empty(self, client):
        """Status ohne Profil zeigt has_profile=False."""
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert data["version"] == __version__
        assert data["has_profile"] is False
        assert data["profile_name"] is None
        assert data["active_jobs"] == 0
        assert data["applications"] == 0

    def test_status_with_profile(self, client):
        """Status mit Profil zeigt has_profile=True und Namen."""
        client.post("/api/profile", json={"name": "Tester"})
        r = client.get("/api/status")
        data = r.json()
        assert data["version"] == __version__
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
        dash._db.set_profile_setting("active_sources", ["bundesagentur", "stepstone"])
        dash._db.set_profile_setting("last_search_at", datetime.now().isoformat())
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

    def test_live_update_token_endpoint(self, client):
        """Live-Update-Token steht fuer Frontend-Polling bereit."""
        before = client.get("/api/live-update-token")
        assert before.status_code == 200
        before_body = before.json()
        assert isinstance(before_body.get("token"), str)

        client.post("/api/profile", json={"name": "Live Token"})

        after = client.get("/api/live-update-token")
        assert after.status_code == 200
        after_body = after.json()
        assert isinstance(after_body.get("token"), str)
        assert before_body["token"] != after_body["token"]


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

    def test_switch_nonexistent_profile_keeps_active_profile(self, client):
        """Ungültiger Wechsel darf das aktive Profil nicht verlieren."""
        client.post("/api/profile", json={"name": "Profil A"})
        active_before = client.get("/api/profile").json()["id"]
        r = client.post("/api/profiles/switch", json={"profile_id": "nonexistent"})
        assert r.status_code == 404
        active_after = client.get("/api/profile")
        assert active_after.status_code == 200
        assert active_after.json()["id"] == active_before

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

    def test_delete_nonexistent_profile_returns_404(self, client):
        """Löschen eines unbekannten Profils liefert 404 und behält aktives Profil."""
        client.post("/api/profile", json={"name": "Profil A"})
        active_before = client.get("/api/profile").json()["id"]

        r = client.delete("/api/profiles/nonexistent")
        assert r.status_code == 404
        assert "nicht gefunden" in r.json()["error"]

        active_after = client.get("/api/profile")
        assert active_after.status_code == 200
        assert active_after.json()["id"] == active_before

    def test_new_profile_without_name(self, client):
        """Neues Profil ohne Name → 400."""
        r = client.post("/api/profiles/new", json={})
        assert r.status_code == 400


# ============================================================
# Stellen (Jobs)
# ============================================================

class TestProfileIsolation:
    def test_profile_specific_sources_criteria_blacklist_and_search_status(self, client):
        """Profilbezogene Einstellungen bleiben beim Wechsel sauber getrennt."""
        import bewerbungs_assistent.dashboard as dash
        from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY

        client.post("/api/profile", json={"name": "Profil A"})
        client.post("/api/sources", json={"active_sources": ["bundesagentur"]})
        client.post("/api/search-criteria", json={"keywords": "PLM"})
        client.post("/api/blacklist", json={"type": "firma", "value": "BadCorp"})
        dash._db.set_profile_setting("last_search_at", datetime.now().isoformat())

        r_new = client.post("/api/profiles/new", json={"name": "Profil B"})
        profile_b = r_new.json()["id"]

        active_defaults_b = {
            source["key"] for source in client.get("/api/sources").json() if source["active"]
        }
        expected_defaults = {
            key for key, source in SOURCE_REGISTRY.items() if not source.get("login_erforderlich")
        }
        assert active_defaults_b == expected_defaults
        assert client.get("/api/search-criteria").json() == {}
        assert client.get("/api/blacklist").json() == []
        assert client.get("/api/search-status").json()["status"] == "nie"

        client.post("/api/sources", json={"active_sources": ["stepstone"]})
        client.post("/api/search-criteria", json={"keywords": "React"})
        client.post("/api/blacklist", json={"type": "firma", "value": "NopeCorp"})
        dash._db.set_profile_setting("last_search_at", (datetime.now() - timedelta(days=8)).isoformat())

        profiles = client.get("/api/profiles").json()["profiles"]
        profile_a = next(profile["id"] for profile in profiles if profile["name"] == "Profil A")

        client.post("/api/profiles/switch", json={"profile_id": profile_a})
        active_a = {source["key"] for source in client.get("/api/sources").json() if source["active"]}
        assert active_a == {"bundesagentur"}
        assert client.get("/api/search-criteria").json()["keywords"] == "PLM"
        assert [entry["value"] for entry in client.get("/api/blacklist").json()] == ["BadCorp"]
        assert client.get("/api/search-status").json()["status"] == "aktuell"

        client.post("/api/profiles/switch", json={"profile_id": profile_b})
        active_b = {source["key"] for source in client.get("/api/sources").json() if source["active"]}
        assert active_b == {"stepstone"}
        assert client.get("/api/search-criteria").json()["keywords"] == "React"
        assert [entry["value"] for entry in client.get("/api/blacklist").json()] == ["NopeCorp"]
        assert client.get("/api/search-status").json()["status"] == "dringend"

    def test_blacklist_entries_can_be_deleted_and_are_profile_scoped(self, client):
        """DELETE /api/blacklist/{id} loescht nur Eintraege des aktiven Profils."""
        client.post("/api/profile", json={"name": "Profil A"})
        client.post("/api/blacklist", json={"type": "firma", "value": "BadCorp"})
        entry_a = client.get("/api/blacklist").json()[0]

        r_new = client.post("/api/profiles/new", json={"name": "Profil B"})
        profile_b = r_new.json()["id"]
        client.post("/api/blacklist", json={"type": "firma", "value": "NopeCorp"})
        entry_b = client.get("/api/blacklist").json()[0]

        # Active profile is B: deleting A's entry must fail.
        r_forbidden_scope = client.delete(f"/api/blacklist/{entry_a['id']}")
        assert r_forbidden_scope.status_code == 404
        assert [entry["value"] for entry in client.get("/api/blacklist").json()] == ["NopeCorp"]

        # Deleting own entry works.
        r_delete_b = client.delete(f"/api/blacklist/{entry_b['id']}")
        assert r_delete_b.status_code == 200
        assert client.get("/api/blacklist").json() == []

        profiles = client.get("/api/profiles").json()["profiles"]
        profile_a = next(profile["id"] for profile in profiles if profile["name"] == "Profil A")
        client.post("/api/profiles/switch", json={"profile_id": profile_a})
        assert [entry["value"] for entry in client.get("/api/blacklist").json()] == ["BadCorp"]

        r_delete_a = client.delete(f"/api/blacklist/{entry_a['id']}")
        assert r_delete_a.status_code == 200
        assert client.get("/api/blacklist").json() == []

        client.post("/api/profiles/switch", json={"profile_id": profile_b})
        assert client.get("/api/blacklist").json() == []

    def test_profile_specific_jobs_and_applications_are_isolated(self, client):
        """Job- und Bewerbungslisten folgen dem aktiven Profil."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Profil A"})
        dash._db.save_jobs([{
            "hash": "job-a",
            "title": "PLM Consultant",
            "company": "Firma A",
            "source": "stepstone",
            "score": 8,
        }])
        client.post("/api/applications", json={"title": "Job A", "company": "Firma A"})

        r_new = client.post("/api/profiles/new", json={"name": "Profil B"})
        profile_b = r_new.json()["id"]
        dash._db.save_jobs([{
            "hash": "job-b",
            "title": "React Developer",
            "company": "Firma B",
            "source": "indeed",
            "score": 7,
        }])
        client.post("/api/applications", json={"title": "Job B", "company": "Firma B"})

        jobs_b = client.get("/api/jobs").json()
        apps_b = client.get("/api/applications").json()
        assert [job["hash"] for job in jobs_b] == ["job-b"]
        assert [app["title"] for app in apps_b["applications"]] == ["Job B"]

        profiles = client.get("/api/profiles").json()["profiles"]
        profile_a = next(profile["id"] for profile in profiles if profile["name"] == "Profil A")
        client.post("/api/profiles/switch", json={"profile_id": profile_a})

        jobs_a = client.get("/api/jobs").json()
        apps_a = client.get("/api/applications").json()
        assert [job["hash"] for job in jobs_a] == ["job-a"]
        assert [app["title"] for app in apps_a["applications"]] == ["Job A"]

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

    def test_archived_applications_are_hidden_by_default_but_counted(self, client):
        """Archivierte Bewerbungen bleiben standardmäßig verborgen, sind aber als Metadaten sichtbar."""
        client.post("/api/applications", json={"title": "Aktiv", "company": "Firma A", "status": "beworben"})
        client.post("/api/applications", json={"title": "Archiv", "company": "Firma B", "status": "abgelehnt"})

        hidden = client.get("/api/applications")
        hidden_data = hidden.json()
        assert hidden.status_code == 200
        assert hidden_data["archived_count"] == 1
        assert [app["title"] for app in hidden_data["applications"]] == ["Aktiv"]

        visible = client.get("/api/applications?include_archived=true")
        visible_data = visible.json()
        assert visible.status_code == 200
        assert visible_data["archived_count"] == 1
        assert {app["title"] for app in visible_data["applications"]} == {"Aktiv", "Archiv"}


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

    def test_document_endpoints_reject_cross_profile_access(self, client, tmp_path):
        """Dokument-Endpunkte duerfen keine fremden Profile lesen, aendern oder loeschen."""
        import bewerbungs_assistent.dashboard as dash

        pid_a = dash._db.create_profile("Profil A", "a@example.com")
        app_a = dash._db.add_application({"title": "Job A", "company": "Firma A"})
        doc_a_path = tmp_path / "profil-a.pdf"
        doc_a_path.write_text("A", encoding="utf-8")
        doc_a = dash._db.add_document({
            "filename": "profil-a.pdf",
            "filepath": str(doc_a_path),
            "doc_type": "lebenslauf",
        })

        pid_b = dash._db.create_profile("Profil B", "b@example.com")
        dash._db.switch_profile(pid_b)
        app_b = dash._db.add_application({"title": "Job B", "company": "Firma B"})
        doc_b_path = tmp_path / "profil-b.pdf"
        doc_b_path.write_text("B", encoding="utf-8")
        doc_b = dash._db.add_document({
            "filename": "profil-b.pdf",
            "filepath": str(doc_b_path),
            "doc_type": "lebenslauf",
        })

        dash._db.switch_profile(pid_a)

        relink = client.put(f"/api/document/{doc_a}/link", json={"application_id": app_b})
        assert relink.status_code == 404
        assert dash._db.get_document(doc_a, profile_id=pid_a)["linked_application_id"] is None

        update_type = client.put(f"/api/document/{doc_b}/doc-type", json={"doc_type": "zeugnis"})
        assert update_type.status_code == 404
        assert dash._db.get_document(doc_b, profile_id=pid_b)["doc_type"] == "lebenslauf"

        download = client.get(f"/api/documents/{doc_b}/download")
        assert download.status_code == 404

        delete = client.delete(f"/api/document/{doc_b}")
        assert delete.status_code == 404
        assert dash._db.get_document(doc_b, profile_id=pid_b) is not None

        link_to_foreign_app = client.post(
            f"/api/applications/{app_b}/link-document",
            json={"document_id": doc_a},
        )
        assert link_to_foreign_app.status_code == 404
        assert dash._db.get_document(doc_a, profile_id=pid_a)["linked_application_id"] is None

        # Sanity check: same-profile link still works.
        link_same_profile = client.post(
            f"/api/applications/{app_a}/link-document",
            json={"document_id": doc_a},
        )
        assert link_same_profile.status_code == 200
        assert dash._db.get_document(doc_a, profile_id=pid_a)["linked_application_id"] == app_a

    def test_meeting_endpoints_reject_cross_profile_access(self, client):
        """Meeting-Endpunkte duerfen keine fremden Profile lesen oder veraendern."""
        import bewerbungs_assistent.dashboard as dash

        pid_a = dash._db.create_profile("Profil A", "a@example.com")
        app_a = dash._db.add_application({"title": "Job A", "company": "Firma A"})

        pid_b = dash._db.create_profile("Profil B", "b@example.com")
        dash._db.switch_profile(pid_b)
        app_b = dash._db.add_application({"title": "Job B", "company": "Firma B"})
        meeting_b = dash._db.add_meeting({
            "application_id": app_b,
            "title": "B Termin",
            "meeting_date": (datetime.now() + timedelta(days=3)).isoformat(),
        })

        dash._db.switch_profile(pid_a)

        get_meeting = client.get(f"/api/meetings/{meeting_b}")
        assert get_meeting.status_code == 404

        update_meeting = client.put(f"/api/meetings/{meeting_b}", json={"title": "Manipuliert"})
        assert update_meeting.status_code == 404
        foreign_meeting = dash._db.get_meetings_for_application(app_b, profile_id=pid_b)[0]
        assert foreign_meeting["title"] == "B Termin"

        delete_meeting = client.delete(f"/api/meetings/{meeting_b}")
        assert delete_meeting.status_code == 404
        assert len(dash._db.get_meetings_for_application(app_b, profile_id=pid_b)) == 1

        meeting_ics = client.get(f"/api/meetings/{meeting_b}/ics")
        assert meeting_ics.status_code == 404

        app_meetings = client.get(f"/api/applications/{app_b}/meetings")
        assert app_meetings.status_code == 404

        create_foreign = client.post(
            "/api/meetings",
            json={
                "application_id": app_b,
                "title": "Fremdtermin",
                "meeting_date": (datetime.now() + timedelta(days=7)).isoformat(),
            },
        )
        assert create_foreign.status_code == 404

        create_same = client.post(
            "/api/meetings",
            json={
                "application_id": app_a,
                "title": "Eigenes Meeting",
                "meeting_date": (datetime.now() + timedelta(days=2)).isoformat(),
            },
        )
        assert create_same.status_code == 200

    def test_application_and_email_endpoints_reject_cross_profile_access(self, client):
        """Bewerbungs- und E-Mail-Endpunkte duerfen keine fremden Profile lesen oder veraendern."""
        import bewerbungs_assistent.dashboard as dash

        pid_a = dash._db.create_profile("Profil A", "a@example.com")
        app_a = dash._db.add_application({"title": "Job A", "company": "Firma A", "status": "offen"})

        pid_b = dash._db.create_profile("Profil B", "b@example.com")
        dash._db.switch_profile(pid_b)
        app_b = dash._db.add_application({"title": "Job B", "company": "Firma B", "status": "offen"})
        dash._db.add_application_note(app_b, "Geheime Notiz B")
        conn = dash._db.connect()
        note_event_id = conn.execute(
            "SELECT id FROM application_events WHERE application_id=? AND status='notiz' ORDER BY id DESC LIMIT 1",
            (app_b,),
        ).fetchone()[0]
        email_path = Path(os.environ["BA_DATA_DIR"]) / "profil-b-mail.eml"
        email_path.write_text("Subject: Vertraulich", encoding="utf-8")
        email_b = dash._db.add_email({
            "application_id": app_b,
            "filename": "profil-b-mail.eml",
            "filepath": str(email_path),
            "subject": "Interview nur fuer Profil B",
            "sender": "hr@firma-b.de",
            "recipients": "b@example.com",
            "sent_date": "2026-04-10T10:00:00",
            "body_text": "Vertraulicher Inhalt Profil B",
        })

        dash._db.switch_profile(pid_a)

        assert client.get(f"/api/application/{app_b}/timeline").status_code == 404
        assert client.get(f"/api/application/{app_b}/timeline/print").status_code == 404
        assert client.put(
            f"/api/applications/{app_b}/status",
            json={"status": "zusage", "notes": "Profil A aendert Profil B"},
        ).status_code == 404
        assert dash._db.get_application(app_b)["status"] == "offen"

        assert client.put(
            f"/api/applications/{app_b}",
            json={"company": "Manipulierte Firma"},
        ).status_code == 404
        assert dash._db.get_application(app_b)["company"] == "Firma B"

        assert client.post(
            f"/api/applications/{app_b}/notes",
            json={"text": "Fremde Notiz"},
        ).status_code == 404
        assert client.put(
            f"/api/applications/{app_b}/notes/{note_event_id}",
            json={"text": "Ueberschrieben"},
        ).status_code == 404
        assert client.delete(f"/api/applications/{app_b}/notes/{note_event_id}").status_code == 404
        note_row = dash._db.connect().execute(
            "SELECT notes FROM application_events WHERE id=?",
            (note_event_id,),
        ).fetchone()
        assert note_row["notes"] == "Geheime Notiz B"

        assert client.post(
            f"/api/applications/{app_b}/snapshot",
            json={"url": "data:text/html,<html><body>Geheim</body></html>"},
        ).status_code == 404
        assert not dash._db.get_application(app_b).get("description_snapshot")

        assert client.post(
            f"/api/applications/{app_b}/fit-analyse",
            json={"score": 13, "summary": "Manipuliert"},
        ).status_code == 404
        assert dash._db.get_application(app_b).get("fit_analyse") is None

        assert client.get(f"/api/emails/{email_b}").status_code == 404
        assert client.get(f"/api/applications/{app_b}/emails").status_code == 404
        assert client.delete(f"/api/emails/{email_b}").status_code == 404
        assert dash._db.get_email(email_b) is not None

        assert client.post(
            f"/api/emails/{email_b}/confirm-match",
            json={"application_id": app_a},
        ).status_code == 404
        assert dash._db.get_email(email_b)["application_id"] == app_b

        assert client.post(
            f"/api/emails/{email_b}/apply-status",
            json={"status": "abgelehnt"},
        ).status_code == 404
        assert dash._db.get_application(app_a)["status"] == "offen"
        assert dash._db.get_application(app_b)["status"] == "offen"

    def test_application_update_and_email_actions_work_same_profile(self, client):
        """Same-Profile-Bearbeitung, E-Mail-Linking und Statusuebernahme bleiben funktionsfaehig."""
        import bewerbungs_assistent.dashboard as dash

        client.post("/api/profile", json={"name": "Tester"})
        app_id = dash._db.add_application({"title": "Job", "company": "Firma Alt", "status": "offen"})
        email_path = Path(os.environ["BA_DATA_DIR"]) / "profil-a-mail.eml"
        email_path.write_text("Subject: Hallo", encoding="utf-8")
        email_id = dash._db.add_email({
            "filename": "profil-a-mail.eml",
            "filepath": str(email_path),
            "subject": "Intervieweinladung",
            "sender": "hr@firma.de",
            "recipients": "tester@example.com",
            "sent_date": "2026-04-10T10:00:00",
            "body_text": "Wir laden Sie zum Interview ein.",
        })

        get_email = client.get(f"/api/emails/{email_id}")
        assert get_email.status_code == 200
        assert get_email.json()["subject"] == "Intervieweinladung"

        confirm_match = client.post(
            f"/api/emails/{email_id}/confirm-match",
            json={"application_id": app_id},
        )
        assert confirm_match.status_code == 200
        assert dash._db.get_email(email_id)["application_id"] == app_id

        list_emails = client.get(f"/api/applications/{app_id}/emails")
        assert list_emails.status_code == 200
        assert list_emails.json()["count"] == 1

        apply_status = client.post(
            f"/api/emails/{email_id}/apply-status",
            json={"status": "interview"},
        )
        assert apply_status.status_code == 200
        assert dash._db.get_application(app_id)["status"] == "interview"

        update_application = client.put(
            f"/api/applications/{app_id}",
            json={"company": "Firma Neu"},
        )
        assert update_application.status_code == 200
        assert update_application.json()["changes"] == 1
        assert dash._db.get_application(app_id)["company"] == "Firma Neu"

        save_fit = client.post(
            f"/api/applications/{app_id}/fit-analyse",
            json={"score": 42, "summary": "Passt gut"},
        )
        assert save_fit.status_code == 200
        assert dash._db.get_application(app_id)["fit_analyse"]["score"] == 42

        timeline = client.get(f"/api/application/{app_id}/timeline")
        assert timeline.status_code == 200
        assert any(event["status"] == "bearbeitet" for event in timeline.json()["events"])

        printable = client.get(f"/api/application/{app_id}/timeline/print")
        assert printable.status_code == 200
        assert "Firma Neu" in printable.text

        delete_email = client.delete(f"/api/emails/{email_id}")
        assert delete_email.status_code == 200
        assert dash._db.get_email(email_id) is None

    def test_cv_data_endpoints_reject_cross_profile_access(self, client):
        """Positions, Education, Skills, Job-Titles und Projects duerfen keine fremden Profile aendern."""
        import bewerbungs_assistent.dashboard as dash

        pid_a = dash._db.create_profile("Profil A", "a@example.com")
        conn = dash._db.connect()

        pid_b = dash._db.create_profile("Profil B", "b@example.com")
        dash._db.switch_profile(pid_b)
        conn.execute(
            "INSERT INTO positions (id, profile_id, company, title, start_date) VALUES (?,?,?,?,?)",
            ("pos_b", pid_b, "Firma B", "Dev B", "2021-01-01"),
        )
        conn.execute(
            "INSERT INTO education (id, profile_id, institution, degree, field_of_study, start_date) VALUES (?,?,?,?,?,?)",
            ("edu_b", pid_b, "Uni B", "BSc", "Mathe", "2016-01-01"),
        )
        conn.execute(
            "INSERT INTO skills (id, profile_id, name, level) VALUES (?,?,?,?)",
            ("skill_b", pid_b, "Java", "advanced"),
        )
        conn.execute(
            "INSERT INTO suggested_job_titles (id, profile_id, title, source, confidence) VALUES (?,?,?,?,?)",
            ("jt_b", pid_b, "Manager", "manual", 1.0),
        )
        conn.execute(
            "INSERT INTO projects (id, position_id, name, description) VALUES (?,?,?,?)",
            ("proj_b", "pos_b", "Geheimprojekt", "Vertraulich"),
        )
        conn.commit()

        dash._db.switch_profile(pid_a)

        # Position: PUT und DELETE
        assert client.put("/api/position/pos_b", json={"title": "HACKED"}).status_code == 404
        assert conn.execute("SELECT title FROM positions WHERE id='pos_b'").fetchone()[0] == "Dev B"
        assert client.delete("/api/position/pos_b").status_code == 404
        assert conn.execute("SELECT id FROM positions WHERE id='pos_b'").fetchone() is not None

        # Education: PUT und DELETE
        assert client.put("/api/education/edu_b", json={"institution": "HACKED"}).status_code == 404
        assert conn.execute("SELECT institution FROM education WHERE id='edu_b'").fetchone()[0] == "Uni B"
        assert client.delete("/api/education/edu_b").status_code == 404
        assert conn.execute("SELECT id FROM education WHERE id='edu_b'").fetchone() is not None

        # Skill: PUT und DELETE
        assert client.put("/api/skill/skill_b", json={"name": "HACKED"}).status_code == 404
        assert conn.execute("SELECT name FROM skills WHERE id='skill_b'").fetchone()[0] == "Java"
        assert client.delete("/api/skill/skill_b").status_code == 404
        assert conn.execute("SELECT id FROM skills WHERE id='skill_b'").fetchone() is not None

        # Job-Title: PUT und DELETE
        assert client.put("/api/job-title/jt_b", json={"title": "HACKED"}).status_code == 404
        assert conn.execute("SELECT title FROM suggested_job_titles WHERE id='jt_b'").fetchone()[0] == "Manager"
        assert client.delete("/api/job-title/jt_b").status_code == 404
        assert conn.execute("SELECT id FROM suggested_job_titles WHERE id='jt_b'").fetchone() is not None

        # Project: PUT und DELETE
        assert client.put("/api/project/proj_b", json={"name": "HACKED"}).status_code == 404
        assert conn.execute("SELECT name FROM projects WHERE id='proj_b'").fetchone()[0] == "Geheimprojekt"
        assert client.delete("/api/project/proj_b").status_code == 404
        assert conn.execute("SELECT id FROM projects WHERE id='proj_b'").fetchone() is not None

    def test_status_update_requires_status_field(self, client):
        """PUT /api/applications/{app_id}/status muss 400 liefern wenn status fehlt."""
        import bewerbungs_assistent.dashboard as dash

        dash._db.create_profile("Tester", "t@example.com")
        app_id = dash._db.add_application({"title": "Job", "company": "Firma", "status": "offen"})

        r = client.put(f"/api/applications/{app_id}/status", json={})
        assert r.status_code == 400
        assert "status" in r.json()["error"].lower()

        r = client.put(f"/api/applications/{app_id}/status", json={"notes": "nur notiz"})
        assert r.status_code == 400


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

    def test_jobsuche_running_false_without_running_job(self, client):
        """Jobsuche-Status liefert running=False ohne laufenden Hintergrundjob."""
        r = client.get("/api/jobsuche/running")
        assert r.status_code == 200
        assert r.json()["running"] is False

    def test_jobsuche_running_true_with_running_job(self, client):
        """Jobsuche-Status zeigt Fortschritt eines laufenden Jobsuche-Jobs."""
        import bewerbungs_assistent.dashboard as dash

        job_id = dash._db.create_background_job("jobsuche", {"quellen": ["stepstone"]})
        dash._db.update_background_job(
            job_id,
            "running",
            progress=42,
            message="Durchsuche stepstone... (1/1)",
        )

        r = client.get("/api/jobsuche/running")
        assert r.status_code == 200
        body = r.json()
        assert body["running"] is True
        assert body["job_id"] == job_id
        assert body["status"] == "running"
        assert body["progress"] == 42

    def test_sources_default_all_inactive(self, client):
        """Quellen-API liefert standardmaessig alle Quellen als inaktiv."""
        r = client.get("/api/sources")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert all(source["active"] is False for source in data)

    def test_sources_default_with_profile_excludes_login_required(self, client):
        """Frisches Profil aktiviert alle Quellen ausser LinkedIn/XING."""
        from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY

        client.post("/api/profile", json={"name": "Tester"})
        r = client.get("/api/sources")
        assert r.status_code == 200

        active = {source["key"] for source in r.json() if source["active"]}
        expected = {
            key for key, source in SOURCE_REGISTRY.items() if not source.get("login_erforderlich")
        }
        assert active == expected

    def test_sources_can_be_updated(self, client):
        """Aktive Quellen koennen gespeichert und erneut geladen werden."""
        r = client.post("/api/sources", json={"active_sources": ["bundesagentur", "stepstone"]})
        assert r.status_code == 200

        r2 = client.get("/api/sources")
        active_sources = {source["key"] for source in r2.json() if source["active"]}
        assert active_sources == {"bundesagentur", "stepstone"}

    def test_source_login_rejects_non_login_source(self, client):
        """Login-Endpunkt weist Quellen ohne Login-Anforderung ab."""
        r = client.post("/api/sources/stepstone/login")
        assert r.status_code == 400
        assert "kein Login erforderlich" in r.json()["error"]

    def test_source_login_starts_background_job_for_linkedin(self, client, monkeypatch):
        """LinkedIn-Login startet Job und markiert ihn bei Erfolg als fertig."""
        import bewerbungs_assistent.dashboard as dash
        import bewerbungs_assistent.job_scraper.linkedin as linkedin

        class ImmediateThread:
            def __init__(self, target=None, daemon=None):
                self._target = target

            def start(self):
                if self._target:
                    self._target()

        monkeypatch.setattr(dash.threading, "Thread", ImmediateThread)
        monkeypatch.setattr(linkedin, "ensure_linkedin_session", lambda progress_callback=None: True)

        r = client.post("/api/sources/linkedin/login")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "gestartet"

        r_job = client.get(f"/api/background-jobs/{body['job_id']}")
        assert r_job.status_code == 200
        job = r_job.json()
        assert job["status"] == "fertig"
        assert job["result"]["source"] == "linkedin"
        assert job["result"]["session_ready"] is True

    def test_upload_document_sanitizes_nested_path_filename(self, client):
        """Upload with relative folder path stores file under /dokumente without source subfolders."""
        client.post("/api/profile", json={"name": "Uploader"})
        r = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("Tomra/Bewerbung Vollzeit.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert r.status_code == 200

        profile = client.get("/api/profile").json()
        docs = profile["documents"]
        assert len(docs) == 1
        assert docs[0]["filename"] == "Bewerbung Vollzeit.pdf"

        stored_path = Path(docs[0]["filepath"])
        assert stored_path.exists()
        assert "dokumente" in [part.lower() for part in stored_path.parts]
        assert stored_path.parent.name != "Tomra"

    def test_upload_document_sanitizes_windows_separator_filename(self, client):
        """Upload with backslashes should not fail and should keep only the basename."""
        client.post("/api/profile", json={"name": "Uploader"})
        r = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("Tomra\\Lebenslauf Vollzeit.pdf", b"dummy", "application/pdf")},
        )
        assert r.status_code == 200
        profile = client.get("/api/profile").json()
        names = [document["filename"] for document in profile["documents"]]
        assert "Lebenslauf Vollzeit.pdf" in names

    def test_upload_same_filename_in_new_profile_keeps_original_name(self, client):
        """Same filename in a different profile should not be renamed to _1."""
        client.post("/api/profile", json={"name": "Profil A"})
        first_upload = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("Bewerbung.pdf", b"dummy-a", "application/pdf")},
        )
        assert first_upload.status_code == 200

        first_profile = client.get("/api/profile").json()
        first_profile_id = first_profile["id"]
        assert [doc["filename"] for doc in first_profile["documents"]] == ["Bewerbung.pdf"]

        create_second = client.post("/api/profiles/new", json={"name": "Profil B"})
        assert create_second.status_code == 200

        second_upload = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("Bewerbung.pdf", b"dummy-b", "application/pdf")},
        )
        assert second_upload.status_code == 200

        second_profile = client.get("/api/profile").json()
        assert second_profile["id"] != first_profile_id
        assert [doc["filename"] for doc in second_profile["documents"]] == ["Bewerbung.pdf"]

        first_path = Path(first_profile["documents"][0]["filepath"])
        second_path = Path(second_profile["documents"][0]["filepath"])
        assert first_path.parent != second_path.parent

    def test_upload_email_document_extracts_mail_content(self, client):
        """Uploading an .eml through the documents endpoint stores readable text for later analysis."""
        client.post("/api/profile", json={"name": "Uploader"})

        message = MIMEText("Vielen Dank fuer Ihre Bewerbung. Wir melden uns zeitnah.")
        message["Subject"] = "Recruiter-Update"
        message["From"] = "hr@example.com"
        message["To"] = "markus@example.com"

        response = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("recruiter-update.eml", message.as_bytes(), "message/rfc822")},
        )

        assert response.status_code == 200
        assert response.json()["extracted_length"] > 0

        profile = client.get("/api/profile").json()
        document = profile["documents"][0]
        assert "Recruiter-Update" in document["extracted_text"]
        assert "Vielen Dank fuer Ihre Bewerbung" in document["extracted_text"]

    def test_upload_email_document_auto_links_matching_application(self, client):
        """Document uploads should reuse email matching helpers when a mail clearly belongs to one application."""
        client.post("/api/profile", json={"name": "Uploader", "email": "markus@example.com"})
        app_response = client.post(
            "/api/applications",
            json={
                "title": "Senior Consultant",
                "company": "ACME GmbH",
                "status": "beworben",
                "kontakt_email": "hr@example.com",
            },
        )
        assert app_response.status_code == 200
        app_id = app_response.json()["id"]

        message = MIMEText("Wir laden Sie gern zu einem Interview ein.")
        message["Subject"] = "Interview bei ACME"
        message["From"] = "hr@example.com"
        message["To"] = "markus@example.com"

        response = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("einladung.eml", message.as_bytes(), "message/rfc822")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["linked_application"] == app_id
        assert payload["email_context"]["matched_application"]["id"] == app_id
        assert payload["email_context"]["detected_status"] == "interview"

        profile = client.get("/api/profile").json()
        document = profile["documents"][0]
        assert document["linked_application_id"] == app_id
        assert document["extraction_status"] == "basis_analysiert"

    def test_upload_email_document_creates_timeline_event(self, client):
        """Email upload via documents endpoint should add a timeline event to the matched application."""
        client.post("/api/profile", json={"name": "Uploader", "email": "markus@example.com"})
        app_response = client.post(
            "/api/applications",
            json={
                "title": "Tester",
                "company": "Timeline Corp",
                "status": "beworben",
                "kontakt_email": "hr@timeline.com",
            },
        )
        app_id = app_response.json()["id"]

        body = "Vielen Dank fuer Ihre Bewerbung. Wir haben diese erhalten."
        message = MIMEText(body)
        message["Subject"] = "Eingangsbestaetigung"
        message["From"] = "hr@timeline.com"
        message["To"] = "markus@example.com"

        response = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("bestaetigung.eml", message.as_bytes(), "message/rfc822")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["linked_application"] == app_id

        # Check timeline event via DB (application_events table)
        import bewerbungs_assistent.dashboard as dash
        conn = dash._db.connect()
        events = conn.execute(
            "SELECT * FROM application_events WHERE application_id=? AND status LIKE 'email_%'",
            (app_id,),
        ).fetchall()
        assert len(events) >= 1, "Timeline event for email should have been created"
        assert "Eingangsbestaetigung" in events[0]["notes"]

    def test_upload_email_document_extracts_meeting(self, client):
        """Email with Teams link and date should create a meeting when uploaded via documents."""
        client.post("/api/profile", json={"name": "Uploader", "email": "markus@example.com"})
        app_response = client.post(
            "/api/applications",
            json={
                "title": "Dev",
                "company": "MeetCo",
                "status": "beworben",
                "kontakt_email": "hr@meetco.com",
            },
        )
        app_id = app_response.json()["id"]

        body = (
            "Wir moechten Sie gerne zu einem Vorstellungsgespraech einladen.\n"
            "Termin: am 28.03.2026 um 10:00 Uhr\n"
            "Link: https://teams.microsoft.com/l/meetup-join/19%3Ameeting_test123\n"
        )
        message = MIMEText(body)
        message["Subject"] = "Einladung Interview"
        message["From"] = "hr@meetco.com"
        message["To"] = "markus@example.com"

        response = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("interview.eml", message.as_bytes(), "message/rfc822")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["linked_application"] == app_id
        assert len(payload.get("meetings", [])) >= 1, "Meeting should have been extracted"
        assert "teams" in (payload["meetings"][0].get("meeting_url") or "")

    def test_upload_msg_document_returns_clear_error_when_parser_missing(self, client, monkeypatch):
        """Missing extract-msg must surface as a user-facing error instead of a silent empty document."""
        client.post("/api/profile", json={"name": "Uploader"})

        import bewerbungs_assistent.dashboard as dash

        def fail_extract(filepath):
            if str(filepath).lower().endswith(".msg"):
                raise ImportError(
                    "extract-msg ist nicht installiert. "
                    "Bitte PBP neu installieren (INSTALLIEREN.bat). "
                    "Falls das nicht hilft: Mail in Outlook als .eml oder PDF speichern und erneut hochladen."
                )
            return "", None

        monkeypatch.setattr(dash, "_extract_document_text", fail_extract)

        response = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("outlook.msg", b"dummy", "application/vnd.ms-outlook")},
        )

        assert response.status_code == 501
        body = response.json()
        assert "extract-msg" in body["error"]
        assert "PDF" in body["hinweis"]
        assert "Outlook" in body["hinweis"]

        profile = client.get("/api/profile").json()
        assert profile["documents"] == []

    def test_import_folder_supports_eml_documents(self, client, tmp_path):
        """Folder import should parse .eml files and keep them usable for profile analysis."""
        client.post("/api/profile", json={"name": "Importer"})
        folder = tmp_path / "import"
        folder.mkdir()

        message = MIMEText("Bitte senden Sie uns Ihre Unterlagen.")
        message["Subject"] = "Stellenbeschreibung"
        message["From"] = "jobs@example.com"
        message["To"] = "markus@example.com"
        (folder / "angebot.eml").write_bytes(message.as_bytes())

        response = client.post(
            "/api/documents/import-folder",
            json={"folder_path": str(folder), "import_documents": True, "import_applications": False},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["documents_imported"] == 1
        assert payload["warning_count"] == 0

        profile = client.get("/api/profile").json()
        document = profile["documents"][0]
        assert document["filename"] == "angebot.eml"
        assert "Stellenbeschreibung" in document["extracted_text"]
        assert document["extraction_status"] == "basis_analysiert"

    def test_import_folder_reports_missing_msg_parser_as_warning(self, client, tmp_path, monkeypatch):
        """Folder import should report .msg parser problems clearly instead of silently importing empty docs."""
        client.post("/api/profile", json={"name": "Importer"})
        folder = tmp_path / "import"
        folder.mkdir()
        (folder / "outlook.msg").write_bytes(b"dummy")

        import bewerbungs_assistent.dashboard as dash

        def fail_extract(filepath):
            if str(filepath).lower().endswith(".msg"):
                raise ImportError(
                    "extract-msg ist nicht installiert. "
                    "Bitte PBP neu installieren (INSTALLIEREN.bat). "
                    "Falls das nicht hilft: Mail in Outlook als .eml oder PDF speichern und erneut hochladen."
                )
            return "", None

        monkeypatch.setattr(dash, "_extract_document_text", fail_extract)

        response = client.post(
            "/api/documents/import-folder",
            json={"folder_path": str(folder), "import_documents": True, "import_applications": False},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["documents_imported"] == 0
        assert payload["skipped_files"] == 1
        assert payload["warning_count"] == 1
        assert "extract-msg" in payload["warnings"][0]
        assert "PDF" in payload["warnings"][0]

    def test_analyze_documents_keeps_non_empty_text_as_basis_analysiert(self, client):
        """Readable documents without structured profile fields should not fall back to 'Ohne Inhalt'."""
        client.post("/api/profile", json={"name": "Uploader"})

        upload = client.post(
            "/api/documents/upload",
            data={"doc_type": "sonstiges"},
            files={"file": ("notiz.txt", b"Bitte denke an das Nachfassen am Freitag.", "text/plain")},
        )
        assert upload.status_code == 200

        analysis = client.post("/api/dokumente-analysieren", json={"force": True})
        assert analysis.status_code == 200
        payload = analysis.json()
        assert payload["status"] == "keine_daten"
        assert payload["basis_analysiert"] == 1
        assert payload["analysiert_leer"] == 0

        profile = client.get("/api/profile").json()
        assert profile["documents"][0]["extraction_status"] == "basis_analysiert"

    def test_document_analysis_prompt_targets_single_document(self, client):
        """The prompt endpoint should generate a Claude-ready command for one concrete document."""
        client.post("/api/profile", json={"name": "Prompt Tester"})

        upload = client.post(
            "/api/documents/upload",
            data={"doc_type": "lebenslauf"},
            files={"file": ("profil.txt", b"Python, PLM, Projektleitung", "text/plain")},
        )
        assert upload.status_code == 200

        profile = client.get("/api/profile").json()
        document = profile["documents"][0]

        response = client.get(f"/api/document/{document['id']}/analysis-prompt")
        assert response.status_code == 200

        payload = response.json()
        assert payload["document"]["id"] == document["id"]
        assert payload["document"]["filename"] == "profil.txt"
        assert document["id"] in payload["prompt"]
        assert "extraktion_starten(document_ids=[" in payload["prompt"]
        assert "extraktion_ergebnis_speichern" in payload["prompt"]
        assert "extraktion_anwenden" in payload["prompt"]

    def test_workflow_prompt_resolves_profile_extension_instructions(self, client):
        """UI slash commands should resolve to a usable workflow prompt for Claude."""
        client.post("/api/profile", json={"name": "Workflow Tester"})

        response = client.get("/api/workflow-prompt/profil_erweiterung")
        assert response.status_code == 200

        payload = response.json()
        assert payload["workflow"] == "profil_erweiterung"
        assert "Analysiere hochgeladene Dokumente" in payload["prompt"]
        assert "extraktion_starten()" in payload["prompt"]


# ============================================================
# Email Download (#422)
# ============================================================

class TestEmailDownload:
    def test_download_email_returns_file(self, client, tmp_path):
        """Email download endpoint returns the original .eml file."""
        client.post("/api/profile", json={"name": "Downloader", "email": "test@example.com"})
        app_resp = client.post("/api/applications", json={
            "title": "Dev", "company": "TestCo", "status": "beworben",
        })
        app_id = app_resp.json()["id"]

        eml_file = tmp_path / "test_mail.eml"
        eml_file.write_text("Subject: Hallo\nFrom: hr@testco.com\n\nWir freuen uns.")

        import bewerbungs_assistent.dashboard as dash
        email_id = dash._db.add_email({
            "application_id": app_id,
            "filename": "test_mail.eml",
            "filepath": str(eml_file),
            "subject": "Hallo",
            "sender": "hr@testco.com",
            "direction": "eingang",
        })

        resp = client.get(f"/api/emails/{email_id}/download")
        assert resp.status_code == 200
        assert b"Wir freuen uns" in resp.content

    def test_download_email_not_found(self, client):
        """Non-existent email ID returns 404."""
        client.post("/api/profile", json={"name": "Tester"})
        resp = client.get("/api/emails/nonexistent/download")
        assert resp.status_code == 404

    def test_download_email_missing_file(self, client):
        """Email exists in DB but file is missing on disk."""
        client.post("/api/profile", json={"name": "Tester", "email": "t@t.com"})
        app_resp = client.post("/api/applications", json={
            "title": "Job", "company": "Co", "status": "beworben",
        })
        app_id = app_resp.json()["id"]

        import bewerbungs_assistent.dashboard as dash
        email_id = dash._db.add_email({
            "application_id": app_id,
            "filename": "gone.eml",
            "filepath": "/tmp/nonexistent_email_file.eml",
            "subject": "Test",
            "sender": "a@b.com",
            "direction": "eingang",
        })

        resp = client.get(f"/api/emails/{email_id}/download")
        assert resp.status_code == 404
        assert "Dateisystem" in resp.json()["error"]


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


# ============================================================
# v0.24.1 — SafeJSONResponse / inf-Sanitization
# ============================================================

class TestSafeJSONResponse:
    """Regression tests for inf/nan float values in API responses."""

    def test_profile_with_inf_confidence_does_not_crash(self, client):
        """Profile with inf confidence in suggested_job_titles must not crash (#91)."""
        import math
        client.post("/api/profile", json={"name": "Inf-Test"})
        # Directly inject inf into suggested_job_titles via DB
        from bewerbungs_assistent import dashboard
        db = dashboard._db
        conn = db.connect()
        pid = db.get_active_profile_id()
        conn.execute(
            "INSERT INTO suggested_job_titles (id, profile_id, title, source, confidence, is_active, created_at) "
            "VALUES ('inf-test', ?, 'Developer', 'test', ?, 1, '2026-01-01')",
            (pid, float('inf'))
        )
        conn.commit()
        r = client.get("/api/profile")
        assert r.status_code == 200
        data = r.json()
        # inf should be sanitized to None
        inf_title = [t for t in data["suggested_job_titles"] if t["id"] == "inf-test"]
        assert len(inf_title) == 1
        assert inf_title[0]["confidence"] is None

    def test_sanitize_for_json_handles_nested_inf(self):
        """_sanitize_for_json must handle deeply nested inf/nan."""
        import math
        from bewerbungs_assistent.dashboard import _sanitize_for_json
        data = {
            "a": float('inf'),
            "b": [1, float('-inf'), {"c": float('nan')}],
            "d": "normal",
            "e": 42,
        }
        result = _sanitize_for_json(data)
        assert result["a"] is None
        assert result["b"][0] == 1
        assert result["b"][1] is None
        assert result["b"][2]["c"] is None
        assert result["d"] == "normal"
        assert result["e"] == 42


# ============================================================
# Daily Impulse API (#163)
# ============================================================

class TestDailyImpulseAPI:
    def test_daily_impulse_returns_valid_structure(self, client):
        """GET /api/daily-impulse returns enabled, context, datum, impulse."""
        r = client.get("/api/daily-impulse")
        assert r.status_code == 200
        data = r.json()
        assert "enabled" in data
        assert "context" in data
        assert "datum" in data
        # Context depends on day-of-week and workspace state
        assert data["context"] in (
            "onboarding", "weekend", "default", "profile_building",
            "sources_missing", "search_refresh", "jobs_ready", "follow_up_due",
        )

    def test_daily_impulse_has_impulse_object(self, client):
        """When enabled the response should contain an impulse dict."""
        r = client.get("/api/daily-impulse")
        data = r.json()
        assert data["enabled"] is True
        impulse = data["impulse"]
        assert impulse is not None
        assert "id" in impulse
        assert "title" in impulse
        assert "text" in impulse
        assert "tags" in impulse
        assert impulse["id"].startswith("impuls_")

    def test_daily_impulse_stable_within_same_request(self, client):
        """Two calls on the same day return the same impulse."""
        r1 = client.get("/api/daily-impulse")
        r2 = client.get("/api/daily-impulse")
        assert r1.json()["impulse"]["id"] == r2.json()["impulse"]["id"]

    def test_daily_impulse_toggle(self, client):
        """POST /api/daily-impulse/toggle flips the enabled state."""
        r = client.get("/api/daily-impulse")
        initial = r.json()["enabled"]

        t = client.post("/api/daily-impulse/toggle")
        assert t.status_code == 200
        assert t.json()["enabled"] is not initial

        r2 = client.get("/api/daily-impulse")
        assert r2.json()["enabled"] is not initial

    def test_daily_impulse_disabled_returns_null(self, client):
        """When disabled, impulse should be None."""
        # Disable
        client.post("/api/daily-impulse/toggle")
        r = client.get("/api/daily-impulse")
        data = r.json()
        assert data["enabled"] is False
        assert data["impulse"] is None


