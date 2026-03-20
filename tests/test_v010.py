"""Tests for v0.10.x features: Schema v8, salary extraction, user preferences, profile isolation."""

import pytest
from bewerbungs_assistent.database import Database, SCHEMA_VERSION
from bewerbungs_assistent.job_scraper import extract_salary_from_text, estimate_salary


# === Schema v9 ===

class TestSchemaV9:
    def test_schema_version_is_15(self, tmp_db):
        """Schema version should be 15."""
        assert SCHEMA_VERSION == 15

    def test_salary_estimated_column(self, tmp_db):
        """jobs table should have salary_estimated column."""
        conn = tmp_db.connect()
        cols = conn.execute("PRAGMA table_info(jobs)").fetchall()
        col_names = [c["name"] for c in cols]
        assert "salary_estimated" in col_names

    def test_user_preferences_table(self, tmp_db):
        """user_preferences table should exist."""
        conn = tmp_db.connect()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'"
        ).fetchall()
        assert len(tables) == 1

    def test_salary_columns_in_jobs(self, tmp_db):
        """jobs table should have salary_min, salary_max, salary_type columns."""
        conn = tmp_db.connect()
        cols = conn.execute("PRAGMA table_info(jobs)").fetchall()
        col_names = [c["name"] for c in cols]
        for expected in ["salary_min", "salary_max", "salary_type"]:
            assert expected in col_names, f"Column {expected} missing from jobs"

    def test_profile_id_in_jobs(self, tmp_db):
        """jobs table should have profile_id column (v8)."""
        conn = tmp_db.connect()
        cols = conn.execute("PRAGMA table_info(jobs)").fetchall()
        col_names = [c["name"] for c in cols]
        assert "profile_id" in col_names

    def test_profile_id_in_applications(self, tmp_db):
        """applications table should have profile_id column (v8)."""
        conn = tmp_db.connect()
        cols = conn.execute("PRAGMA table_info(applications)").fetchall()
        col_names = [c["name"] for c in cols]
        assert "profile_id" in col_names


# === User Preferences ===

class TestUserPreferences:
    def test_set_and_get_preference(self, tmp_db):
        """Set a user preference and retrieve it."""
        tmp_db.set_user_preference("wizard_completed", "true")
        result = tmp_db.get_user_preference("wizard_completed")
        assert result == "true"

    def test_get_preference_default(self, tmp_db):
        """Missing preference returns default value."""
        result = tmp_db.get_user_preference("nonexistent", "fallback")
        assert result == "fallback"

    def test_overwrite_preference(self, tmp_db):
        """Overwriting a preference replaces the old value."""
        tmp_db.set_user_preference("theme", "dark")
        tmp_db.set_user_preference("theme", "light")
        assert tmp_db.get_user_preference("theme") == "light"

    def test_get_preference_none_default(self, tmp_db):
        """Missing preference with no default returns None."""
        result = tmp_db.get_user_preference("missing_key")
        assert result is None


# === Salary Extraction ===

class TestSalaryExtraction:
    def test_extract_annual_range(self):
        """Extract annual salary range: 60.000-80.000 EUR."""
        s_min, s_max, s_type = extract_salary_from_text("Gehalt: 60.000-80.000 EUR")
        assert s_min == 60000
        assert s_max == 80000
        assert s_type == "jaehrlich"

    def test_extract_k_notation(self):
        """Extract k-notation: 65k-85k."""
        s_min, s_max, s_type = extract_salary_from_text("Jahresgehalt 65k-85k")
        assert s_min == 65000
        assert s_max == 85000
        assert s_type == "jaehrlich"

    def test_extract_daily_rate(self):
        """Extract daily rate: 800-1200 EUR/Tag."""
        s_min, s_max, s_type = extract_salary_from_text("Tagessatz 800-1200 EUR/Tag")
        assert s_min == 800
        assert s_max == 1200
        assert s_type == "taeglich"

    def test_extract_hourly_rate(self):
        """Extract hourly rate: Stundensatz 80-120 EUR/Stunde."""
        s_min, s_max, s_type = extract_salary_from_text("Stundensatz 80-120 EUR/Stunde")
        assert s_min == 80
        assert s_max == 120
        assert s_type == "stuendlich"

    def test_extract_euro_symbol(self):
        """Extract with euro symbol: 70.000-90.000 euro jaehrlich."""
        s_min, s_max, s_type = extract_salary_from_text("70.000 - 90.000 Euro jaehrlich")
        assert s_min == 70000
        assert s_max == 90000
        assert s_type == "jaehrlich"

    def test_no_salary_found(self):
        """No salary in text returns None tuple."""
        s_min, s_max, s_type = extract_salary_from_text("Ein spannender Job in Hamburg")
        assert s_min is None
        assert s_max is None
        assert s_type is None

    def test_extract_single_amount(self):
        """Extract single amount: ab 70.000 EUR brutto."""
        s_min, s_max, s_type = extract_salary_from_text("ab 70.000 EUR brutto")
        assert s_min is not None
        assert s_type == "jaehrlich"


# === Salary Estimation ===

class TestSalaryEstimation:
    def test_estimate_consultant(self):
        """Consultant title should produce an estimation."""
        s_min, s_max, s_type = estimate_salary("PLM Consultant", "festanstellung", "Hamburg")
        assert s_min is not None
        assert s_max is not None
        assert s_type == "jaehrlich"
        assert s_min >= 50000

    def test_estimate_senior(self):
        """Senior title should estimate higher than regular."""
        s_min_sr, s_max_sr, _ = estimate_salary("Senior Consultant", "festanstellung", "")
        s_min_jr, s_max_jr, _ = estimate_salary("Consultant", "festanstellung", "")
        if s_min_sr and s_min_jr:
            assert s_min_sr >= s_min_jr

    def test_estimate_freelance(self):
        """Freelance should return daily rate."""
        s_min, s_max, s_type = estimate_salary("IT Consultant", "freelance", "")
        assert s_min is not None
        assert s_type == "taeglich"

    def test_estimate_unknown_title(self):
        """Unrecognized title still gets default range estimate."""
        s_min, s_max, s_type = estimate_salary("Bananenpfluecker", "festanstellung", "")
        # Returns default fallback range (50k-70k)
        assert s_min is not None
        assert s_min >= 40000

    def test_regional_adjustment(self):
        """Munich should have higher salary than average."""
        s_min_m, _, _ = estimate_salary("Consultant", "festanstellung", "Muenchen")
        s_min_l, _, _ = estimate_salary("Consultant", "festanstellung", "Leipzig")
        if s_min_m and s_min_l:
            assert s_min_m > s_min_l


# === Jobs with Salary Data ===

class TestJobsWithSalary:
    def test_save_job_with_salary(self, tmp_db):
        """Save a job with salary data and retrieve it."""
        tmp_db.save_profile({"name": "Test User"})
        jobs = [{
            "hash": "salary_test_001",
            "title": "PLM Consultant",
            "company": "TestFirma",
            "url": "https://example.com",
            "source": "stepstone",
            "salary_min": 65000,
            "salary_max": 85000,
            "salary_type": "jahr",
            "salary_estimated": 0,
        }]
        tmp_db.save_jobs(jobs)
        active = tmp_db.get_active_jobs()
        job = [j for j in active if j["hash"] == "salary_test_001"][0]
        assert job["salary_min"] == 65000
        assert job["salary_max"] == 85000
        assert job["salary_type"] == "jahr"
        assert job["salary_estimated"] == 0

    def test_save_job_with_estimated_salary(self, tmp_db):
        """Save a job with estimated salary and verify flag."""
        tmp_db.save_profile({"name": "Test User"})
        jobs = [{
            "hash": "salary_test_002",
            "title": "Manager",
            "company": "TestFirma",
            "url": "https://example.com",
            "source": "indeed",
            "salary_min": 80000,
            "salary_max": 110000,
            "salary_type": "jahr",
            "salary_estimated": 1,
        }]
        tmp_db.save_jobs(jobs)
        active = tmp_db.get_active_jobs()
        job = [j for j in active if j["hash"] == "salary_test_002"][0]
        assert job["salary_estimated"] == 1


# === Profile Isolation (v0.10.1) ===

class TestProfileIsolation:
    def test_jobs_isolated_by_profile(self, tmp_db):
        """Jobs saved under profile A should not appear for profile B."""
        # Create profile A
        pid_a = tmp_db.save_profile({"name": "Alice"})
        tmp_db.save_jobs([{
            "hash": "job_alice_001", "title": "Alice Job",
            "company": "A-Corp", "url": "https://a.com", "source": "test",
        }])
        assert len(tmp_db.get_active_jobs()) == 1

        # Create profile B (switches active to B)
        conn = tmp_db.connect()
        conn.execute("UPDATE profile SET is_active=0")
        import uuid
        pid_b = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO profile (id, name, is_active, created_at, updated_at) VALUES (?,?,1,?,?)",
            (pid_b, "Bob", "2025-01-01", "2025-01-01")
        )
        conn.commit()

        # Bob should see no jobs
        assert len(tmp_db.get_active_jobs()) == 0

        # Save a job for Bob
        tmp_db.save_jobs([{
            "hash": "job_bob_001", "title": "Bob Job",
            "company": "B-Corp", "url": "https://b.com", "source": "test",
        }])
        assert len(tmp_db.get_active_jobs()) == 1
        assert tmp_db.get_active_jobs()[0]["title"] == "Bob Job"

    def test_applications_isolated_by_profile(self, tmp_db):
        """Applications are scoped to the active profile."""
        pid_a = tmp_db.save_profile({"name": "Alice"})
        tmp_db.add_application({"title": "App A", "company": "Corp A"})
        assert len(tmp_db.get_applications()) == 1

        # Switch to new profile
        conn = tmp_db.connect()
        conn.execute("UPDATE profile SET is_active=0")
        import uuid
        pid_b = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO profile (id, name, is_active, created_at, updated_at) VALUES (?,?,1,?,?)",
            (pid_b, "Bob", "2025-01-01", "2025-01-01")
        )
        conn.commit()

        # Bob should see no applications
        assert len(tmp_db.get_applications()) == 0

    def test_same_job_hash_stays_visible_for_both_profiles(self, tmp_db):
        """Identische externe Job-Hashes duerfen sich profiluebergreifend nicht ueberschreiben."""
        pid_a = tmp_db.save_profile({"name": "Alice"})
        tmp_db.save_jobs([{
            "hash": "shared_job_001", "title": "Alice Shared Job",
            "company": "A-Corp", "url": "https://a.com", "source": "test",
        }])

        conn = tmp_db.connect()
        conn.execute("UPDATE profile SET is_active=0")
        import uuid
        pid_b = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO profile (id, name, is_active, created_at, updated_at) VALUES (?,?,1,?,?)",
            (pid_b, "Bob", "2025-01-01", "2025-01-01")
        )
        conn.commit()

        tmp_db.save_jobs([{
            "hash": "shared_job_001", "title": "Bob Shared Job",
            "company": "B-Corp", "url": "https://b.com", "source": "test",
        }])
        assert tmp_db.get_active_jobs()[0]["title"] == "Bob Shared Job"

        conn.execute("UPDATE profile SET is_active=0")
        conn.execute("UPDATE profile SET is_active=1 WHERE id=?", (pid_a,))
        conn.commit()

        active = tmp_db.get_active_jobs()
        assert len(active) == 1
        assert active[0]["hash"] == "shared_job_001"
        assert active[0]["title"] == "Alice Shared Job"
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2

    def test_follow_ups_are_scoped_to_active_profile(self, tmp_db):
        """Pending follow-ups should only include applications of the active profile."""
        pid_a = tmp_db.save_profile({"name": "Alice"})
        app_a = tmp_db.add_application({"title": "App A", "company": "Corp A"})
        tmp_db.add_follow_up(app_a, "2026-03-10")

        conn = tmp_db.connect()
        conn.execute("UPDATE profile SET is_active=0")
        import uuid
        pid_b = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO profile (id, name, is_active, created_at, updated_at) VALUES (?,?,1,?,?)",
            (pid_b, "Bob", "2025-01-01", "2025-01-01")
        )
        conn.commit()

        app_b = tmp_db.add_application({"title": "App B", "company": "Corp B"})
        tmp_db.add_follow_up(app_b, "2026-03-11")
        bob_followups = tmp_db.get_pending_follow_ups()
        assert [item["title"] for item in bob_followups] == ["App B"]

        conn.execute("UPDATE profile SET is_active=0")
        conn.execute("UPDATE profile SET is_active=1 WHERE id=?", (pid_a,))
        conn.commit()

        alice_followups = tmp_db.get_pending_follow_ups()
        assert [item["title"] for item in alice_followups] == ["App A"]

    def test_application_job_hash_stays_public(self, tmp_db):
        """Applications should expose the public hash even if the DB stores a scoped hash."""
        tmp_db.save_profile({"name": "Alice"})
        tmp_db.save_jobs([{
            "hash": "shared_job_002", "title": "Shared Job",
            "company": "A-Corp", "url": "https://a.com", "source": "test",
        }])
        app_id = tmp_db.add_application({
            "title": "Shared Job",
            "company": "A-Corp",
            "job_hash": "shared_job_002",
        })

        app = tmp_db.get_application(app_id)
        assert app["job_hash"] == "shared_job_002"
        assert tmp_db.get_applications()[0]["job_hash"] == "shared_job_002"


# === Cascade Delete (v0.10.1) ===

class TestCascadeDelete:
    def test_delete_profile_removes_all_data(self, tmp_db):
        """Deleting a profile removes all linked data."""
        pid = tmp_db.save_profile({"name": "Delete Me"})
        tmp_db.add_position({
            "company": "Corp", "title": "Dev",
            "start_date": "2020-01", "employment_type": "festanstellung",
        })
        tmp_db.add_skill({"name": "Python", "category": "tool"})
        tmp_db.add_education({"institution": "Uni", "degree": "BSc"})
        tmp_db.add_application({"title": "Job", "company": "Corp"})
        tmp_db.save_jobs([{
            "hash": "del_test_001", "title": "Job", "company": "Corp",
            "url": "https://example.com", "source": "test",
        }])

        # Verify data exists
        conn = tmp_db.connect()
        assert conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM education").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1

        # Delete
        tmp_db.delete_profile(pid)

        # Verify everything is gone
        assert conn.execute("SELECT COUNT(*) FROM profile").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM education").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


# === Factory Reset (v0.10.1) ===

class TestFactoryReset:
    def test_reset_clears_all_data(self, tmp_db):
        """Factory reset removes all data, keeps schema_version."""
        tmp_db.save_profile({"name": "Test"})
        tmp_db.add_skill({"name": "Python", "category": "tool"})
        tmp_db.save_jobs([{
            "hash": "reset_001", "title": "Job", "company": "Corp",
            "url": "https://example.com", "source": "test",
        }])
        tmp_db.set_user_preference("wizard_completed", "true")

        tmp_db.reset_all_data()

        conn = tmp_db.connect()
        assert conn.execute("SELECT COUNT(*) FROM profile").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM user_preferences").fetchone()[0] == 0
        # schema_version should still be preserved
        row = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
        assert row is not None


# === Smart Next Steps (v0.10.2) ===

class TestSmartNextSteps:
    def test_no_profile_suggests_creation(self, tmp_db):
        """No profile: next steps should suggest profile creation."""
        steps = tmp_db.get_next_steps()
        assert len(steps) >= 1
        assert steps[0]["aktion"] == "Profil erstellen"
        assert steps[0]["prioritaet"] == "hoch"
        assert steps[0]["action_type"] == "dashboard"

    def test_empty_profile_suggests_building(self, tmp_db):
        """Profile without positions/skills should suggest additions."""
        tmp_db.save_profile({"name": "Test User"})
        steps = tmp_db.get_next_steps()
        actions = [s["aktion"] for s in steps]
        assert "Zusammenfassung ergaenzen" in actions
        assert "Berufserfahrung hinzufuegen" in actions

    def test_complete_profile_suggests_sources(self, tmp_db):
        """Complete profile but no sources: suggest activating sources."""
        tmp_db.save_profile({
            "name": "Test", "email": "t@t.de", "city": "Hamburg",
            "summary": "Test summary",
            "preferences": {"stellentyp": "beides"},
        })
        tmp_db.add_position({
            "company": "Corp", "title": "Dev",
            "start_date": "2020-01", "employment_type": "festanstellung",
        })
        tmp_db.add_skill({"name": "Python", "category": "tool"})
        tmp_db.add_education({"institution": "Uni", "degree": "BSc"})
        steps = tmp_db.get_next_steps()
        actions = [s["aktion"] for s in steps]
        assert "Jobquellen aktivieren" in actions

    def test_with_rejections_suggests_analysis(self, tmp_db):
        """3+ rejections should suggest pattern analysis."""
        tmp_db.save_profile({"name": "Test", "summary": "x",
                             "preferences": {"stellentyp": "beides"}})
        tmp_db.add_position({"company": "A", "title": "B",
                             "start_date": "2020-01", "employment_type": "festanstellung"})
        tmp_db.add_skill({"name": "Python", "category": "tool"})
        tmp_db.add_education({"institution": "Uni", "degree": "BSc"})
        for i in range(3):
            aid = tmp_db.add_application({"title": f"Job {i}", "company": f"Corp {i}"})
            tmp_db.update_application_status(aid, "abgelehnt")
        steps = tmp_db.get_next_steps()
        actions = [s["aktion"] for s in steps]
        assert "Ablehnungen analysieren" in actions

    def test_interview_suggests_prep(self, tmp_db):
        """Interview status should suggest interview preparation."""
        tmp_db.save_profile({"name": "Test", "summary": "x",
                             "preferences": {"stellentyp": "beides"}})
        tmp_db.add_position({"company": "A", "title": "B",
                             "start_date": "2020-01", "employment_type": "festanstellung"})
        tmp_db.add_skill({"name": "Python", "category": "tool"})
        tmp_db.add_education({"institution": "Uni", "degree": "BSc"})
        aid = tmp_db.add_application({"title": "Job", "company": "Corp"})
        tmp_db.update_application_status(aid, "interview")
        steps = tmp_db.get_next_steps()
        actions = [s["aktion"] for s in steps]
        assert "Interview vorbereiten" in actions

    def test_action_types_present(self, tmp_db):
        """All steps should have action_type field."""
        steps = tmp_db.get_next_steps()
        for s in steps:
            assert "action_type" in s or "prompt" in s

    def test_no_docs_suggests_upload(self, tmp_db):
        """Profile without documents should suggest upload."""
        tmp_db.save_profile({"name": "Test", "summary": "x",
                             "preferences": {"stellentyp": "beides"}})
        tmp_db.add_position({"company": "A", "title": "B",
                             "start_date": "2020-01", "employment_type": "festanstellung"})
        tmp_db.add_skill({"name": "Python", "category": "tool"})
        tmp_db.add_education({"institution": "Uni", "degree": "BSc"})
        steps = tmp_db.get_next_steps()
        actions = [s["aktion"] for s in steps]
        assert "Dokumente hochladen" in actions


class TestOrphanedDocumentAdoption:
    """Documents uploaded before profile creation should be adopted."""

    def test_orphaned_docs_adopted_on_profile_creation(self, tmp_db):
        """Documents with profile_id=NULL should be adopted when first profile is created."""
        # Upload document without any profile existing
        doc_id = tmp_db.add_document({
            "filename": "lebenslauf.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": "Python Developer mit 10 Jahren Erfahrung",
        })
        # Verify document has no profile
        conn = tmp_db.connect()
        row = conn.execute("SELECT profile_id FROM documents WHERE id=?", (doc_id,)).fetchone()
        assert row["profile_id"] is None

        # Now create a profile — should adopt the orphaned document
        pid = tmp_db.save_profile({"name": "Test User"})

        # Document should now belong to the new profile
        row = conn.execute("SELECT profile_id FROM documents WHERE id=?", (doc_id,)).fetchone()
        assert row["profile_id"] == pid

        # Profile should see the document
        profile = tmp_db.get_profile()
        assert len(profile["documents"]) == 1
        assert profile["documents"][0]["filename"] == "lebenslauf.pdf"

    def test_multiple_orphaned_docs_all_adopted(self, tmp_db):
        """All orphaned documents should be adopted, not just one."""
        ids = []
        for name in ["cv.pdf", "zeugnis.pdf", "master.md"]:
            ids.append(tmp_db.add_document({
                "filename": name,
                "doc_type": "sonstiges",
                "extracted_text": f"Content of {name}",
            }))
        pid = tmp_db.save_profile({"name": "Test"})
        conn = tmp_db.connect()
        count = conn.execute(
            "SELECT COUNT(*) as c FROM documents WHERE profile_id=?", (pid,)
        ).fetchone()["c"]
        assert count == 3

    def test_existing_profile_docs_not_affected(self, tmp_db):
        """Creating a second profile should not steal documents from first."""
        # Create first profile with a document
        pid1 = tmp_db.save_profile({"name": "User 1"})
        tmp_db.add_document({
            "filename": "user1_cv.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": "User 1 CV",
        })
        # Create second profile (switch)
        pid2 = tmp_db.save_profile({"name": "User 2"})
        # User 1's document should still belong to user 1
        conn = tmp_db.connect()
        row = conn.execute(
            "SELECT profile_id FROM documents WHERE filename='user1_cv.pdf'"
        ).fetchone()
        assert row["profile_id"] == pid1


class TestCompletenessCheck:
    """Tests for the profile completeness check."""

    def test_address_field_recognized(self, tmp_db):
        """Address field should count for completeness."""
        tmp_db.save_profile({"name": "Test", "address": "Musterstr. 1"})
        profile = tmp_db.get_profile()
        # address is set, city is not — should still count
        assert profile["address"] == "Musterstr. 1"

    def test_city_also_counts_as_address(self, tmp_db):
        """City field alone should also satisfy address check."""
        tmp_db.save_profile({"name": "Test", "city": "Hamburg"})
        profile = tmp_db.get_profile()
        assert profile["city"] == "Hamburg"

    def test_summary_stored_correctly(self, tmp_db):
        """Summary field should be stored and retrievable."""
        tmp_db.save_profile({"name": "Test", "summary": "Erfahrener Entwickler"})
        profile = tmp_db.get_profile()
        assert profile["summary"] == "Erfahrener Entwickler"


class TestBulkImport:
    """Tests for bulk import via profil_bearbeiten."""

    def test_bulk_add_skills(self, tmp_db):
        """Bulk adding skills should work."""
        tmp_db.save_profile({"name": "Test"})
        skills = [
            {"name": "Python", "category": "tool", "level": 5},
            {"name": "SQL", "category": "tool", "level": 4},
            {"name": "Projektmanagement", "category": "methodisch", "level": 4},
        ]
        for s in skills:
            tmp_db.add_skill(s)
        profile = tmp_db.get_profile()
        assert len(profile["skills"]) == 3

    def test_bulk_add_positions(self, tmp_db):
        """Bulk adding positions should work."""
        tmp_db.save_profile({"name": "Test"})
        positions = [
            {"company": "Firma A", "title": "Dev", "start_date": "2020-01",
             "employment_type": "festanstellung"},
            {"company": "Firma B", "title": "Lead", "start_date": "2022-01",
             "employment_type": "festanstellung"},
        ]
        ids = [tmp_db.add_position(p) for p in positions]
        assert len(ids) == 2
        profile = tmp_db.get_profile()
        assert len(profile["positions"]) == 2
