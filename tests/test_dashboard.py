"""Dashboard API Tests — FastAPI TestClient-basierte Tests.

Testet die wichtigsten Dashboard-API-Endpoints mit einer temporaeren
Datenbank. Deckt Status, Profil-CRUD, Validierung, Multi-Profil,
Stellen, Bewerbungen, Paginierung und Factory Reset ab.
"""

import os
import sys
import json
import pytest
from pathlib import Path

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
