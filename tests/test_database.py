"""Tests for the Database layer.

Covers CRUD for all entities, CASCADE deletes, schema migration,
settings, search criteria, blacklist, and background jobs.
"""

import json
import pytest
from bewerbungs_assistent.database import Database, SCHEMA_VERSION


# === Profile CRUD ===

class TestProfile:
    def test_save_and_get_profile(self, tmp_db, sample_profile):
        """Save a profile and retrieve it."""
        pid = tmp_db.save_profile(sample_profile)
        assert pid is not None
        profile = tmp_db.get_profile()
        assert profile is not None
        assert profile["name"] == "Max Mustermann"
        assert profile["email"] == "max@example.com"
        assert profile["city"] == "Hamburg"
        assert profile["preferences"]["arbeitsmodell"] == "hybrid"

    def test_update_profile(self, tmp_db, sample_profile):
        """Updating an existing profile should not create a new one."""
        pid1 = tmp_db.save_profile(sample_profile)
        sample_profile["name"] = "Maximiliane Muster"
        sample_profile["city"] = "Berlin"
        pid2 = tmp_db.save_profile(sample_profile)
        assert pid1 == pid2  # Same ID — update, not insert
        profile = tmp_db.get_profile()
        assert profile["name"] == "Maximiliane Muster"
        assert profile["city"] == "Berlin"

    def test_empty_profile(self, tmp_db):
        """No profile saved yet returns None."""
        assert tmp_db.get_profile() is None


# === Positions & Projects ===

class TestPositions:
    def test_add_position(self, tmp_db, sample_position):
        """Add a position and verify it appears in profile."""
        tmp_db.save_profile({"name": "Test"})
        pos_id = tmp_db.add_position(sample_position)
        assert pos_id is not None
        profile = tmp_db.get_profile()
        assert len(profile["positions"]) == 1
        assert profile["positions"][0]["company"] == "Tech GmbH"
        assert profile["positions"][0]["title"] == "Senior PLM Consultant"

    def test_add_multiple_positions(self, tmp_db, sample_position):
        """Multiple positions are stored and ordered by start_date DESC."""
        tmp_db.save_profile({"name": "Test"})
        tmp_db.add_position(sample_position)
        older = dict(sample_position, company="Alt GmbH", title="Junior Dev", start_date="2015-01")
        tmp_db.add_position(older)
        profile = tmp_db.get_profile()
        assert len(profile["positions"]) == 2
        # 2018-01 should come first (DESC)
        assert profile["positions"][0]["start_date"] == "2018-01"

    def test_delete_position(self, tmp_db, sample_position):
        """Deleting a position removes it from the DB."""
        tmp_db.save_profile({"name": "Test"})
        pos_id = tmp_db.add_position(sample_position)
        tmp_db.delete_position(pos_id)
        profile = tmp_db.get_profile()
        assert len(profile["positions"]) == 0

    def test_add_project_to_position(self, tmp_db, sample_position, sample_project):
        """A project linked to a position appears in the position's projects."""
        tmp_db.save_profile({"name": "Test"})
        pos_id = tmp_db.add_position(sample_position)
        proj_id = tmp_db.add_project(pos_id, sample_project)
        assert proj_id is not None
        profile = tmp_db.get_profile()
        pos = profile["positions"][0]
        assert len(pos["projects"]) == 1
        assert pos["projects"][0]["name"] == "PLM-Migration Automotive"
        assert pos["projects"][0]["role"] == "Projektleiter"

    def test_cascade_delete_projects(self, tmp_db, sample_position, sample_project):
        """Deleting a position also deletes its projects (CASCADE)."""
        tmp_db.save_profile({"name": "Test"})
        pos_id = tmp_db.add_position(sample_position)
        tmp_db.add_project(pos_id, sample_project)
        tmp_db.delete_position(pos_id)
        # Verify project is gone
        conn = tmp_db.connect()
        count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        assert count == 0


# === Education ===

class TestEducation:
    def test_add_education(self, tmp_db):
        """Add education entry and verify it's retrievable."""
        tmp_db.save_profile({"name": "Test"})
        edu_id = tmp_db.add_education({
            "institution": "TU Hamburg",
            "degree": "Master",
            "field_of_study": "Maschinenbau",
            "start_date": "2010",
            "end_date": "2013",
            "grade": "1.5",
        })
        assert edu_id is not None
        profile = tmp_db.get_profile()
        assert len(profile["education"]) == 1
        assert profile["education"][0]["institution"] == "TU Hamburg"
        assert profile["education"][0]["grade"] == "1.5"

    def test_delete_education(self, tmp_db):
        """Deleting an education entry removes it."""
        tmp_db.save_profile({"name": "Test"})
        edu_id = tmp_db.add_education({"institution": "FH Wedel", "degree": "B.Sc."})
        tmp_db.delete_education(edu_id)
        profile = tmp_db.get_profile()
        assert len(profile["education"]) == 0


# === Skills ===

class TestSkills:
    def test_add_skill(self, tmp_db):
        """Add a skill and verify it."""
        tmp_db.save_profile({"name": "Test"})
        sid = tmp_db.add_skill({
            "name": "Python",
            "category": "tool",
            "level": 5,
            "years_experience": 10,
        })
        assert sid is not None
        profile = tmp_db.get_profile()
        assert len(profile["skills"]) == 1
        assert profile["skills"][0]["name"] == "Python"
        assert profile["skills"][0]["level"] == 5

    def test_delete_skill(self, tmp_db):
        """Deleting a skill removes it."""
        tmp_db.save_profile({"name": "Test"})
        sid = tmp_db.add_skill({"name": "Java", "category": "tool"})
        tmp_db.delete_skill(sid)
        profile = tmp_db.get_profile()
        assert len(profile["skills"]) == 0


# === Jobs ===

class TestJobs:
    def test_save_and_get_jobs(self, tmp_db, sample_jobs):
        """Save jobs and retrieve active ones."""
        tmp_db.save_profile({"name": "Test"})
        tmp_db.save_jobs(sample_jobs)
        active = tmp_db.get_active_jobs()
        assert len(active) == 2
        # Should be ordered by score DESC
        assert active[0]["score"] >= active[1]["score"]

    def test_dismiss_and_restore_job(self, tmp_db, sample_jobs):
        """Dismiss a job, verify it's inactive, then restore it."""
        tmp_db.save_profile({"name": "Test"})
        tmp_db.save_jobs(sample_jobs)
        tmp_db.dismiss_job("abc123456789", "nicht relevant")
        active = tmp_db.get_active_jobs()
        assert len(active) == 1
        dismissed = tmp_db.get_dismissed_jobs()
        assert len(dismissed) == 1
        assert dismissed[0]["dismiss_reason"] == "nicht relevant"
        # Restore
        tmp_db.restore_job("abc123456789")
        active = tmp_db.get_active_jobs()
        assert len(active) == 2

    def test_filter_jobs_by_source(self, tmp_db, sample_jobs):
        """Filter active jobs by source."""
        tmp_db.save_profile({"name": "Test"})
        tmp_db.save_jobs(sample_jobs)
        stepstone = tmp_db.get_active_jobs({"source": "stepstone"})
        assert len(stepstone) == 1
        assert stepstone[0]["source"] == "stepstone"

    def test_filter_jobs_by_min_score(self, tmp_db, sample_jobs):
        """Filter active jobs by minimum score."""
        tmp_db.save_profile({"name": "Test"})
        tmp_db.save_jobs(sample_jobs)
        high = tmp_db.get_active_jobs({"min_score": 5})
        assert len(high) == 1
        assert high[0]["score"] == 8

    def test_upsert_jobs(self, tmp_db, sample_jobs):
        """INSERT OR REPLACE should update existing jobs."""
        tmp_db.save_profile({"name": "Test"})
        tmp_db.save_jobs(sample_jobs)
        # Update score of existing job
        updated = [dict(sample_jobs[0], score=10)]
        tmp_db.save_jobs(updated)
        active = tmp_db.get_active_jobs()
        job = [j for j in active if j["hash"] == "abc123456789"][0]
        assert job["score"] == 10


# === Applications ===

class TestApplications:
    def test_add_application(self, tmp_db):
        """Add an application and retrieve it."""
        tmp_db.save_profile({"name": "Test"})
        aid = tmp_db.add_application({
            "title": "PLM Consultant",
            "company": "Siemens",
            "status": "beworben",
            "bewerbungsart": "elektronisch",
        })
        assert aid is not None
        apps = tmp_db.get_applications()
        assert len(apps) == 1
        assert apps[0]["title"] == "PLM Consultant"
        assert apps[0]["bewerbungsart"] == "elektronisch"
        # Should have initial event
        assert len(apps[0]["events"]) == 1
        assert apps[0]["events"][0]["status"] == "beworben"

    def test_update_application_status(self, tmp_db):
        """Updating status creates a new event."""
        tmp_db.save_profile({"name": "Test"})
        aid = tmp_db.add_application({
            "title": "Dev", "company": "Startup",
        })
        tmp_db.update_application_status(aid, "interview", "Telefon-Interview am Montag")
        apps = tmp_db.get_applications()
        assert apps[0]["status"] == "interview"
        assert len(apps[0]["events"]) == 2
        assert apps[0]["events"][1]["status"] == "interview"
        assert "Telefon-Interview" in apps[0]["events"][1]["notes"]

    def test_filter_applications_by_status(self, tmp_db):
        """Filter applications by status."""
        tmp_db.save_profile({"name": "Test"})
        tmp_db.add_application({"title": "A", "company": "X", "status": "beworben"})
        tmp_db.add_application({"title": "B", "company": "Y", "status": "interview"})
        beworben = tmp_db.get_applications(status="beworben")
        assert len(beworben) == 1
        assert beworben[0]["title"] == "A"

    def test_application_v2_fields(self, tmp_db):
        """v2 fields: bewerbungsart, lebenslauf_variante, ansprechpartner, kontakt_email, portal_name."""
        tmp_db.save_profile({"name": "Test"})
        aid = tmp_db.add_application({
            "title": "Manager", "company": "Firma",
            "bewerbungsart": "ueber_portal",
            "lebenslauf_variante": "angepasst",
            "ansprechpartner": "Frau Mueller",
            "kontakt_email": "mueller@firma.de",
            "portal_name": "Workday",
        })
        apps = tmp_db.get_applications()
        app = apps[0]
        assert app["bewerbungsart"] == "ueber_portal"
        assert app["lebenslauf_variante"] == "angepasst"
        assert app["ansprechpartner"] == "Frau Mueller"
        assert app["kontakt_email"] == "mueller@firma.de"
        assert app["portal_name"] == "Workday"


# === Search Criteria ===

class TestSearchCriteria:
    def test_set_and_get_criteria(self, tmp_db):
        """Set and retrieve search criteria."""
        tmp_db.set_search_criteria("keywords_muss", ["PLM", "Windchill"])
        tmp_db.set_search_criteria("keywords_plus", ["Python", "Agile"])
        criteria = tmp_db.get_search_criteria()
        assert criteria["keywords_muss"] == ["PLM", "Windchill"]
        assert criteria["keywords_plus"] == ["Python", "Agile"]

    def test_overwrite_criteria(self, tmp_db):
        """Overwriting criteria replaces the old value."""
        tmp_db.set_search_criteria("keywords_muss", ["PLM"])
        tmp_db.set_search_criteria("keywords_muss", ["SAP", "ERP"])
        criteria = tmp_db.get_search_criteria()
        assert criteria["keywords_muss"] == ["SAP", "ERP"]


# === Blacklist ===

class TestBlacklist:
    def test_add_and_get_blacklist(self, tmp_db):
        """Add blacklist entries and retrieve them."""
        tmp_db.add_to_blacklist("firma", "BadCorp", "Schlechte Bewertungen")
        tmp_db.add_to_blacklist("keyword", "Zeitarbeit", "Nicht gewuenscht")
        bl = tmp_db.get_blacklist()
        assert len(bl) == 2

    def test_blacklist_unique(self, tmp_db):
        """Duplicate entries are ignored (INSERT OR IGNORE)."""
        tmp_db.add_to_blacklist("firma", "BadCorp", "Grund 1")
        tmp_db.add_to_blacklist("firma", "BadCorp", "Grund 2")
        bl = tmp_db.get_blacklist()
        assert len(bl) == 1


# === Settings ===

class TestSettings:
    def test_set_and_get_setting(self, tmp_db):
        """Settings are stored as JSON and retrieved correctly."""
        tmp_db.set_setting("active_sources", ["stepstone", "indeed"])
        result = tmp_db.get_setting("active_sources")
        assert result == ["stepstone", "indeed"]

    def test_setting_default(self, tmp_db):
        """Missing setting returns default value."""
        result = tmp_db.get_setting("nonexistent", "fallback")
        assert result == "fallback"


# === Background Jobs ===

class TestBackgroundJobs:
    def test_create_and_get_job(self, tmp_db):
        """Create a background job and retrieve it."""
        jid = tmp_db.create_background_job("search", {"quellen": ["stepstone"]})
        job = tmp_db.get_background_job(jid)
        assert job is not None
        assert job["status"] == "running"
        assert job["params"]["quellen"] == ["stepstone"]

    def test_update_background_job(self, tmp_db):
        """Update background job status and progress."""
        jid = tmp_db.create_background_job("search")
        tmp_db.update_background_job(jid, "fertig", progress=100,
                                      message="Done", result={"total": 42})
        job = tmp_db.get_background_job(jid)
        assert job["status"] == "fertig"
        assert job["progress"] == 100
        assert job["result"]["total"] == 42


# === Schema Migration ===

class TestMigration:
    def test_schema_version(self, tmp_db):
        """Database should have current schema version after init."""
        version = tmp_db.get_setting("schema_version")
        # schema_version is stored as string in settings
        conn = tmp_db.connect()
        row = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
        assert int(row["value"]) == SCHEMA_VERSION

    def test_v2_columns_exist(self, tmp_db):
        """v2 migration columns should exist in applications table."""
        conn = tmp_db.connect()
        # Check column names via PRAGMA
        cols = conn.execute("PRAGMA table_info(applications)").fetchall()
        col_names = [c["name"] for c in cols]
        for expected in ["bewerbungsart", "lebenslauf_variante", "ansprechpartner",
                         "kontakt_email", "portal_name"]:
            assert expected in col_names, f"Column {expected} missing from applications"


# === Statistics ===

class TestStatistics:
    def test_statistics_empty(self, tmp_db):
        """Statistics with no data should return zeros."""
        stats = tmp_db.get_statistics()
        assert stats["total_applications"] == 0
        assert stats["active_jobs"] == 0

    def test_statistics_with_data(self, tmp_db, sample_jobs):
        """Statistics reflect actual data."""
        tmp_db.save_profile({"name": "Test"})
        tmp_db.save_jobs(sample_jobs)
        tmp_db.add_application({"title": "A", "company": "X", "status": "beworben"})
        tmp_db.add_application({"title": "B", "company": "Y", "status": "interview"})
        stats = tmp_db.get_statistics()
        assert stats["total_applications"] == 2
        assert stats["active_jobs"] == 2
        assert stats["applications_by_status"]["beworben"] == 1
        assert stats["applications_by_status"]["interview"] == 1
        assert stats["interview_rate"] == 50.0

    def test_statistics_are_scoped_to_active_profile(self, tmp_db):
        """Statistics should not include jobs/applications from another profile."""
        tmp_db.save_profile({"name": "Alice"})
        tmp_db.save_jobs([{
            "hash": "alice_job", "title": "Alice Job",
            "company": "A-Corp", "url": "https://a.com", "source": "test",
        }])
        tmp_db.add_application({"title": "App A", "company": "Corp A", "status": "beworben"})

        conn = tmp_db.connect()
        conn.execute("UPDATE profile SET is_active=0")
        conn.execute(
            "INSERT INTO profile (id, name, is_active, created_at, updated_at) VALUES (?,?,1,?,?)",
            ("bob12345", "Bob", "2025-01-01", "2025-01-01")
        )
        conn.commit()

        tmp_db.save_jobs([{
            "hash": "bob_job", "title": "Bob Job",
            "company": "B-Corp", "url": "https://b.com", "source": "test",
        }])
        tmp_db.add_application({"title": "App B", "company": "Corp B", "status": "interview"})

        stats = tmp_db.get_statistics()
        assert stats["total_applications"] == 1
        assert stats["active_jobs"] == 1
        assert set(stats["applications_by_status"]) == {"interview"}
