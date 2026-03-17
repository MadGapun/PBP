"""Tests for the Database layer.

Covers CRUD for all entities, CASCADE deletes, schema migration,
settings, search criteria, blacklist, and background jobs.
"""

import json
import sqlite3
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

    def test_new_profile_default_sources_exclude_login_required(self, tmp_db):
        """Neue Profile aktivieren standardmaessig keine Login-Quellen."""
        from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY

        tmp_db.create_profile("Neues Profil")
        active_sources = tmp_db.get_setting("active_sources", [])
        expected = [
            key for key, source in SOURCE_REGISTRY.items() if not source.get("login_erforderlich")
        ]
        assert active_sources == expected
        assert "linkedin" not in active_sources
        assert "xing" not in active_sources


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

    def test_remove_blacklist_entry(self, tmp_db):
        """Blacklist entries can be removed by id."""
        tmp_db.add_to_blacklist("firma", "BadCorp", "Grund")
        tmp_db.add_to_blacklist("keyword", "Zeitarbeit", "Grund")

        entries = tmp_db.get_blacklist()
        badcorp = next(entry for entry in entries if entry["value"] == "BadCorp")

        removed = tmp_db.remove_blacklist_entry(badcorp["id"])
        assert removed is True
        assert [entry["value"] for entry in tmp_db.get_blacklist()] == ["Zeitarbeit"]

    def test_remove_blacklist_entry_is_profile_scoped(self, tmp_db):
        """An entry from profile A must not be deletable while profile B is active."""
        profile_a = tmp_db.create_profile("Profil A")
        tmp_db.add_to_blacklist("firma", "BadCorp", "A")
        entry_a = tmp_db.get_blacklist()[0]

        tmp_db.create_profile("Profil B")
        tmp_db.add_to_blacklist("firma", "NopeCorp", "B")

        assert tmp_db.remove_blacklist_entry(entry_a["id"]) is False
        assert [entry["value"] for entry in tmp_db.get_blacklist()] == ["NopeCorp"]

        tmp_db.switch_profile(profile_a)
        assert [entry["value"] for entry in tmp_db.get_blacklist()] == ["BadCorp"]
        assert tmp_db.remove_blacklist_entry(entry_a["id"]) is True
        assert tmp_db.get_blacklist() == []


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


class TestProfileScopedData:
    def test_switch_nonexistent_profile_keeps_current_active(self, tmp_db):
        """Switching to an unknown profile id must keep the current active profile."""
        profile_a = tmp_db.create_profile("Profil A")
        tmp_db.create_profile("Profil B")
        assert tmp_db.switch_profile(profile_a) is True
        active_before = tmp_db.get_active_profile_id()
        assert active_before == profile_a

        assert tmp_db.switch_profile("nonexistent") is False
        assert tmp_db.get_active_profile_id() == active_before

    def test_settings_criteria_and_blacklist_are_profile_scoped(self, tmp_db):
        """Profile-specific settings must not leak across profiles."""
        from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY

        profile_a = tmp_db.create_profile("Profil A")
        tmp_db.set_setting("active_sources", ["stepstone"])
        tmp_db.set_setting("last_search_at", "2026-03-13T10:00:00")
        tmp_db.set_search_criteria("keywords_muss", ["PLM"])
        tmp_db.add_to_blacklist("firma", "BadCorp", "Nicht passend")

        profile_b = tmp_db.create_profile("Profil B")
        expected_defaults = [
            key for key, source in SOURCE_REGISTRY.items() if not source.get("login_erforderlich")
        ]
        assert tmp_db.get_setting("active_sources", []) == expected_defaults
        assert tmp_db.get_setting("last_search_at") is None
        assert tmp_db.get_search_criteria() == {}
        assert tmp_db.get_blacklist() == []

        tmp_db.set_setting("active_sources", ["indeed"])
        tmp_db.set_search_criteria("keywords_muss", ["React"])
        tmp_db.add_to_blacklist("firma", "NopeCorp", "Anderer Markt")

        tmp_db.switch_profile(profile_a)
        assert tmp_db.get_setting("active_sources") == ["stepstone"]
        assert tmp_db.get_setting("last_search_at") == "2026-03-13T10:00:00"
        assert tmp_db.get_search_criteria()["keywords_muss"] == ["PLM"]
        assert [entry["value"] for entry in tmp_db.get_blacklist()] == ["BadCorp"]

        tmp_db.switch_profile(profile_b)
        assert tmp_db.get_setting("active_sources") == ["indeed"]
        assert tmp_db.get_search_criteria()["keywords_muss"] == ["React"]
        assert [entry["value"] for entry in tmp_db.get_blacklist()] == ["NopeCorp"]

    def test_jobs_applications_statistics_and_followups_are_profile_scoped(self, tmp_db, sample_jobs):
        """Read models should only include data from the active profile."""
        profile_a = tmp_db.create_profile("Profil A")
        tmp_db.save_jobs(sample_jobs[:1])
        app_a = tmp_db.add_application({"title": "A", "company": "Firma A", "status": "beworben"})
        tmp_db.add_follow_up(app_a, "2026-03-01")

        profile_b = tmp_db.create_profile("Profil B")
        tmp_db.save_jobs(sample_jobs[1:])
        tmp_db.add_application({"title": "B", "company": "Firma B", "status": "interview"})

        stats_b = tmp_db.get_statistics()
        assert len(tmp_db.get_active_jobs()) == 1
        assert tmp_db.get_active_jobs()[0]["hash"] == sample_jobs[1]["hash"]
        assert tmp_db.get_applications()[0]["title"] == "B"
        assert stats_b["total_applications"] == 1
        assert stats_b["applications_by_status"]["interview"] == 1
        assert stats_b["active_jobs"] == 1
        assert tmp_db.get_pending_follow_ups() == []

        tmp_db.switch_profile(profile_a)
        stats_a = tmp_db.get_statistics()
        assert len(tmp_db.get_active_jobs()) == 1
        assert tmp_db.get_active_jobs()[0]["hash"] == sample_jobs[0]["hash"]
        assert tmp_db.get_applications()[0]["title"] == "A"
        assert stats_a["total_applications"] == 1
        assert stats_a["applications_by_status"]["beworben"] == 1
        assert stats_a["active_jobs"] == 1
        assert len(tmp_db.get_pending_follow_ups()) == 1

    def test_profile_loaders_default_to_active_profile_only(self, tmp_db):
        """Internal profile loaders must never fall back to global rows."""
        profile_a = tmp_db.create_profile("Profil A")
        tmp_db.add_position({"company": "A GmbH", "title": "Consultant"})
        tmp_db.add_education({"institution": "FH A", "degree": "B.Sc."})
        tmp_db.add_skill({"name": "Python", "category": "tool"})
        tmp_db.add_document({
            "filename": "cv_a.pdf",
            "filepath": "/tmp/cv_a.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": "Profil A",
        })

        profile_b = tmp_db.create_profile("Profil B")
        assert tmp_db._get_positions() == []
        assert tmp_db._get_education() == []
        assert tmp_db._get_skills() == []
        assert tmp_db._get_documents() == []

        # Explicit profile parameter still works independent of active profile.
        assert len(tmp_db._get_positions(profile_a)) == 1
        assert len(tmp_db._get_education(profile_a)) == 1
        assert len(tmp_db._get_skills(profile_a)) == 1
        assert len(tmp_db._get_documents(profile_a)) == 1
        assert tmp_db.get_active_profile_id() == profile_b

    def test_extraction_history_defaults_to_active_profile_scope(self, tmp_db):
        """Extraction history without explicit profile_id must be profile-scoped."""
        profile_a = tmp_db.create_profile("Profil A")
        doc_a = tmp_db.add_document({
            "filename": "a.pdf",
            "filepath": "/tmp/a.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": "A",
        })
        ex_a = tmp_db.add_extraction_history({"document_id": doc_a, "profile_id": profile_a})

        profile_b = tmp_db.create_profile("Profil B")
        doc_b = tmp_db.add_document({
            "filename": "b.pdf",
            "filepath": "/tmp/b.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": "B",
        })
        ex_b = tmp_db.add_extraction_history({"document_id": doc_b, "profile_id": profile_b})

        history_b = tmp_db.get_extraction_history()
        assert [row["id"] for row in history_b] == [ex_b]

        tmp_db.switch_profile(profile_a)
        history_a = tmp_db.get_extraction_history()
        assert [row["id"] for row in history_a] == [ex_a]

    def test_active_profile_self_heals_when_multiple_profiles_are_active(self, tmp_db):
        """Legacy data with multiple active profiles is repaired on read."""
        profile_a = tmp_db.create_profile("Profil A")
        profile_b = tmp_db.create_profile("Profil B")
        conn = tmp_db.connect()
        conn.execute("UPDATE profile SET is_active=1 WHERE id IN (?, ?)", (profile_a, profile_b))
        conn.commit()

        active_id = tmp_db.get_active_profile_id()
        active_rows = conn.execute("SELECT id FROM profile WHERE is_active=1").fetchall()

        assert active_id in {profile_a, profile_b}
        assert len(active_rows) == 1
        assert active_rows[0]["id"] == active_id


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

    def test_get_running_background_job_filtered_by_type(self, tmp_db):
        """Running job lookup can be filtered by job_type."""
        tmp_db.create_background_job("search")
        jid_jobsuche = tmp_db.create_background_job("jobsuche")
        tmp_db.update_background_job(jid_jobsuche, "running", progress=55, message="scan")

        running = tmp_db.get_running_background_job("jobsuche")
        assert running is not None
        assert running["id"] == jid_jobsuche
        assert running["job_type"] == "jobsuche"
        assert running["status"] == "running"


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

    def test_initialize_repairs_legacy_blacklist_without_profile_id(self, tmp_path):
        """Init repariert Alt-DBs mit schema_version=10 aber altem blacklist-Schema."""
        db_path = tmp_path / "legacy.db"
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO settings (key, value) VALUES ('schema_version', '10');

            CREATE TABLE profile (
                id TEXT PRIMARY KEY,
                name TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            );
            INSERT INTO profile (id, name, is_active) VALUES ('p1', 'Legacy', 1);

            CREATE TABLE search_criteria (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            );
            INSERT INTO search_criteria (key, value, updated_at)
            VALUES ('keywords_muss', '["PLM"]', '2026-03-01T00:00:00');

            CREATE TABLE blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                value TEXT NOT NULL,
                reason TEXT,
                created_at TEXT,
                UNIQUE(type, value)
            );
            INSERT INTO blacklist (type, value, reason, created_at)
            VALUES ('firma', 'LegacyCorp', 'Altbestand', '2026-03-01T00:00:00');
        """)
        conn.commit()
        conn.close()

        db = Database(db_path=db_path)
        db.initialize()

        scoped_criteria = db.get_search_criteria()
        assert scoped_criteria["keywords_muss"] == ["PLM"]

        scoped_blacklist = db.get_blacklist()
        assert len(scoped_blacklist) == 1
        assert scoped_blacklist[0]["value"] == "LegacyCorp"

        columns = {
            row["name"] for row in db.connect().execute("PRAGMA table_info(blacklist)").fetchall()
        }
        assert "profile_id" in columns


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

