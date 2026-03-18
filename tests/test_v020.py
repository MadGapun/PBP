"""Tests for v0.20.0 features: is_pinned, abgelaufen status, pagination, report export."""

import pytest
from bewerbungs_assistent.database import Database, SCHEMA_VERSION


class TestIsPinned:
    def test_is_pinned_column_exists(self, tmp_db):
        """jobs table should have is_pinned column."""
        cols = tmp_db.connect().execute("PRAGMA table_info(jobs)").fetchall()
        col_names = [c["name"] for c in cols]
        assert "is_pinned" in col_names

    def test_save_pinned_job(self, tmp_db, sample_jobs):
        """Pinned jobs should store is_pinned=1."""
        job = sample_jobs[0].copy()
        job["is_pinned"] = True
        job["score"] = 0
        tmp_db.save_jobs([job])
        row = tmp_db.connect().execute(
            "SELECT is_pinned, score FROM jobs WHERE hash=?", (job["hash"],)
        ).fetchone()
        assert row["is_pinned"] == 1
        assert row["score"] == 0

    def test_pinned_sort_order(self, tmp_db, sample_jobs):
        """Pinned jobs should appear before high-score unpinned jobs."""
        # Regular high-score job
        regular = sample_jobs[0].copy()
        regular["score"] = 15
        regular["is_pinned"] = False
        # Pinned low-score job
        pinned = sample_jobs[1].copy()
        pinned["score"] = 0
        pinned["is_pinned"] = True
        tmp_db.save_jobs([regular, pinned])
        jobs = tmp_db.get_active_jobs()
        assert jobs[0]["hash"] == pinned["hash"], "Pinned job should be first"
        assert jobs[1]["hash"] == regular["hash"]

    def test_toggle_pin(self, tmp_db, sample_jobs):
        """toggle_job_pin should flip the pin state."""
        tmp_db.save_jobs(sample_jobs[:1])
        # Initially not pinned
        row = tmp_db.connect().execute(
            "SELECT is_pinned FROM jobs WHERE hash=?", (sample_jobs[0]["hash"],)
        ).fetchone()
        assert row["is_pinned"] == 0
        # Toggle on
        result = tmp_db.toggle_job_pin(sample_jobs[0]["hash"])
        assert result is True
        # Toggle off
        result = tmp_db.toggle_job_pin(sample_jobs[0]["hash"])
        assert result is False

    def test_update_job_score(self, tmp_db, sample_jobs):
        """update_job_score should change the score."""
        tmp_db.save_jobs(sample_jobs[:1])
        tmp_db.update_job_score(sample_jobs[0]["hash"], 42)
        row = tmp_db.connect().execute(
            "SELECT score FROM jobs WHERE hash=?", (sample_jobs[0]["hash"],)
        ).fetchone()
        assert row["score"] == 42


class TestAbgelaufenStatus:
    def test_abgelaufen_status_works(self, tmp_db, sample_profile, sample_jobs):
        """Applications with abgelaufen status should be saved and retrieved."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs(sample_jobs[:1])
        aid = tmp_db.add_application({
            "title": "Test Job", "company": "TestCo",
            "job_hash": sample_jobs[0]["hash"], "status": "beworben",
        })
        tmp_db.update_application_status(aid, "abgelaufen", "Keine Rueckmeldung seit 3 Monaten")
        app = tmp_db.get_application(aid)
        assert app["status"] == "abgelaufen"

    def test_archive_statuses(self, tmp_db, sample_profile, sample_jobs):
        """Archive statuses should be filterable."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs(sample_jobs)
        # Create one active and one archived application
        aid1 = tmp_db.add_application({
            "title": "Active Job", "company": "ActiveCo",
            "job_hash": sample_jobs[0]["hash"], "status": "beworben",
        })
        aid2 = tmp_db.add_application({
            "title": "Old Job", "company": "OldCo",
            "job_hash": sample_jobs[1]["hash"], "status": "beworben",
        })
        tmp_db.update_application_status(aid2, "abgelaufen")

        # Exclude archived
        active_apps = tmp_db.get_applications(include_archived=False)
        assert len(active_apps) == 1
        assert active_apps[0]["id"] == aid1

        # Include archived
        all_apps = tmp_db.get_applications(include_archived=True)
        assert len(all_apps) == 2

    def test_count_archived(self, tmp_db, sample_profile, sample_jobs):
        """count_archived_applications should count correct statuses."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs(sample_jobs)
        aid1 = tmp_db.add_application({
            "title": "J1", "company": "C1",
            "job_hash": sample_jobs[0]["hash"], "status": "beworben",
        })
        aid2 = tmp_db.add_application({
            "title": "J2", "company": "C2",
            "job_hash": sample_jobs[1]["hash"], "status": "beworben",
        })
        tmp_db.update_application_status(aid1, "abgelehnt")
        tmp_db.update_application_status(aid2, "abgelaufen")
        assert tmp_db.count_archived_applications() == 2


class TestPagination:
    def test_limit_offset(self, tmp_db, sample_profile, sample_jobs):
        """Pagination with limit/offset should work."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs(sample_jobs)
        for i in range(5):
            tmp_db.add_application({
                "title": f"Job {i}", "company": f"Company {i}",
                "job_hash": sample_jobs[0]["hash"], "status": "beworben",
            })
        page1 = tmp_db.get_applications(limit=2, offset=0)
        assert len(page1) == 2
        page2 = tmp_db.get_applications(limit=2, offset=2)
        assert len(page2) == 2
        # No overlap
        ids1 = {a["id"] for a in page1}
        ids2 = {a["id"] for a in page2}
        assert ids1.isdisjoint(ids2)


class TestStatistics:
    def test_pinned_excluded_from_avg_score(self, tmp_db, sample_profile):
        """Pinned jobs should not affect avg_score in statistics."""
        tmp_db.create_profile("Test User", "test@example.com")
        # Regular job with score 10
        tmp_db.save_jobs([{
            "hash": "regular1", "title": "Regular", "company": "Co",
            "score": 10, "source": "stepstone",
        }])
        # Pinned job (manual, score 0)
        tmp_db.save_jobs([{
            "hash": "pinned1", "title": "Pinned", "company": "Co",
            "score": 0, "is_pinned": True, "source": "manuell",
        }])
        stats = tmp_db.get_statistics()
        assert stats["avg_score"] == 10.0, "Pinned job score=0 should not lower avg"
        assert stats["pinned_jobs"] == 1

    def test_jobs_by_source(self, tmp_db, sample_profile, sample_jobs):
        """Statistics should include jobs_by_source breakdown."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs(sample_jobs)
        stats = tmp_db.get_statistics()
        assert "jobs_by_source" in stats
        assert stats["jobs_by_source"].get("stepstone") == 1
        assert stats["jobs_by_source"].get("indeed") == 1


class TestReportData:
    def test_report_data_structure(self, tmp_db, sample_profile, sample_jobs):
        """get_report_data should return complete report structure."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs(sample_jobs)
        tmp_db.add_application({
            "title": "Test Job", "company": "TestCo",
            "job_hash": sample_jobs[0]["hash"], "status": "beworben",
        })
        report = tmp_db.get_report_data()
        assert "applications" in report
        assert "score_distribution" in report
        assert "unapplied_high_score" in report
        assert "date_range" in report
        assert "statistics" in report
        assert len(report["applications"]) == 1


class TestTimelineStats:
    def test_timeline_returns_structure(self, tmp_db, sample_jobs):
        """get_timeline_stats should return proper structure."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs(sample_jobs[:1])
        tmp_db.add_application({
            "title": "Job 1", "company": "Co",
            "job_hash": sample_jobs[0]["hash"], "status": "beworben",
            "applied_at": "2026-03-10",
        })
        result = tmp_db.get_timeline_stats("month")
        assert "periods" in result
        assert "applications" in result
        assert "jobs_found" in result
        assert result["interval"] == "month"

    def test_timeline_intervals(self, tmp_db, sample_jobs):
        """All interval types should work."""
        tmp_db.create_profile("Test User", "test@example.com")
        for interval in ["week", "month", "quarter", "year"]:
            result = tmp_db.get_timeline_stats(interval)
            assert result["interval"] == interval

    def test_score_stats_structure(self, tmp_db, sample_jobs):
        """get_score_stats should return score distribution and sources."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs(sample_jobs)
        result = tmp_db.get_score_stats()
        assert "score_distribution" in result
        assert "sources" in result
        assert len(result["sources"]) == 2  # stepstone + indeed

    def test_score_stats_excludes_pinned(self, tmp_db):
        """Score distribution should exclude pinned jobs."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs([
            {"hash": "r1", "title": "A", "company": "C", "score": 5, "source": "test"},
            {"hash": "p1", "title": "B", "company": "C", "score": 0,
             "is_pinned": True, "source": "manuell"},
        ])
        result = tmp_db.get_score_stats()
        # Only the score=5 job should appear, not the pinned score=0
        assert "5" in result["score_distribution"]
        assert "0" not in result["score_distribution"]


class TestExportReport:
    def test_pdf_generation(self, tmp_db, sample_profile, sample_jobs, tmp_path):
        """PDF report should be generated without errors."""
        tmp_db.create_profile("Test User", "test@example.com")
        tmp_db.save_jobs(sample_jobs)
        tmp_db.add_application({
            "title": "PLM Consultant", "company": "Siemens",
            "job_hash": sample_jobs[0]["hash"], "status": "beworben",
        })
        report = tmp_db.get_report_data()
        profile = tmp_db.get_profile()

        from bewerbungs_assistent.export_report import generate_application_report
        output = tmp_path / "test_report.pdf"
        result = generate_application_report(report, profile, output)
        assert result.exists()
        assert result.stat().st_size > 1000  # should be substantial


class TestMigrationV10:
    def test_migration_from_v9(self, tmp_path):
        """Migration from v9 should add is_pinned and migrate score=99 entries."""
        import os, sqlite3
        os.environ["BA_DATA_DIR"] = str(tmp_path)
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        # Create v9-era jobs table WITHOUT is_pinned
        conn.executescript("""
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO settings VALUES ('schema_version', '9');
            CREATE TABLE jobs (hash TEXT PRIMARY KEY, title TEXT, company TEXT,
                location TEXT, url TEXT, source TEXT, description TEXT,
                score INTEGER DEFAULT 0, remote_level TEXT, distance_km REAL,
                salary_info TEXT, salary_min REAL, salary_max REAL,
                salary_type TEXT, salary_estimated INTEGER DEFAULT 0,
                employment_type TEXT DEFAULT 'festanstellung',
                dismiss_reason TEXT, is_active INTEGER DEFAULT 1,
                profile_id TEXT, found_at TEXT, updated_at TEXT);
            INSERT INTO jobs (hash, title, company, source, score, is_active)
                VALUES ('manual1', 'Manual Job', 'ManCo', 'manuell', 99, 1);
            INSERT INTO jobs (hash, title, company, source, score, is_active)
                VALUES ('regular1', 'Regular Job', 'RegCo', 'stepstone', 8, 1);
            CREATE TABLE profile (id TEXT PRIMARY KEY, name TEXT, is_active INTEGER DEFAULT 0,
                created_at TEXT, updated_at TEXT);
            CREATE TABLE search_criteria (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
            CREATE TABLE blacklist (id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL, value TEXT NOT NULL, reason TEXT,
                created_at TEXT, UNIQUE(type, value));
        """)
        conn.commit()
        conn.close()

        # Trigger migration by running _migrate directly
        db = Database(db_path=db_path)
        conn = db.connect()
        conn.execute("PRAGMA foreign_keys=ON")
        db._migrate(9, 11)

        # Check migration results
        ver = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
        assert ver["value"] == "11"

        manual = conn.execute("SELECT is_pinned, score FROM jobs WHERE hash='manual1'").fetchone()
        assert manual["is_pinned"] == 1
        assert manual["score"] == 0

        regular = conn.execute("SELECT is_pinned, score FROM jobs WHERE hash='regular1'").fetchone()
        assert regular["is_pinned"] == 0
        assert regular["score"] == 8

        db.close()
        del os.environ["BA_DATA_DIR"]
