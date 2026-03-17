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
        dash._db.set_setting("last_search_at", datetime.now().isoformat())

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
        dash._db.set_setting("last_search_at", (datetime.now() - timedelta(days=8)).isoformat())

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



