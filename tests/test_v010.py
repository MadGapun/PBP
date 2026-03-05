"""Tests for v0.10.0 features: Schema v7, salary extraction, user preferences."""

import pytest
from bewerbungs_assistent.database import Database, SCHEMA_VERSION
from bewerbungs_assistent.job_scraper import extract_salary_from_text, estimate_salary


# === Schema v7 ===

class TestSchemaV7:
    def test_schema_version_is_7(self, tmp_db):
        """Schema version should be 7."""
        assert SCHEMA_VERSION == 7

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
