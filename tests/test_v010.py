"""Tests for v0.10.x features: Schema v8, salary extraction, user preferences, profile isolation."""

import pytest
from bewerbungs_assistent.database import Database, SCHEMA_VERSION
from bewerbungs_assistent.job_scraper import extract_salary_from_text, estimate_salary


# === Schema v8 ===

class TestSchemaV8:
    def test_schema_version_is_8(self, tmp_db):
        """Schema version should be 8."""
        assert SCHEMA_VERSION == 8

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
