"""SQLite Database Layer for Bewerbungs-Assistent.

Handles all data persistence: profiles, jobs, applications, documents.
Synchronous SQLite with WAL mode and check_same_thread=False for
cross-thread access (MCP thread + Dashboard thread).
"""

import sqlite3
import json
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger("bewerbungs_assistent.database")

SCHEMA_VERSION = 9


def _gen_id() -> str:
    """Generate a short unique ID (8 hex chars)."""
    return str(uuid.uuid4())[:8]


def get_data_dir() -> Path:
    """Get the data directory, create if needed.

    Priority: BA_DATA_DIR env var > platform default.
    Windows default: %LOCALAPPDATA%/BewerbungsAssistent
    Linux default:   ~/.bewerbungs-assistent
    """
    env_dir = os.environ.get("BA_DATA_DIR")
    if env_dir:
        data_dir = Path(env_dir)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        data_dir = base / "BewerbungsAssistent"
    else:
        data_dir = Path.home() / ".bewerbungs-assistent"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "dokumente").mkdir(exist_ok=True)
    (data_dir / "export").mkdir(exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """Get the SQLite database file path."""
    return get_data_dir() / "pbp.db"


class Database:
    """Synchronous SQLite database manager."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def initialize(self):
        """Create all tables if they don't exist."""
        conn = self.connect()
        conn.executescript(SCHEMA_SQL)
        # Check schema version
        cur = conn.execute("SELECT value FROM settings WHERE key='schema_version'")
        row = cur.fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),)
            )
            conn.commit()
        else:
            current = int(row["value"])
            if current < SCHEMA_VERSION:
                self._migrate(current, SCHEMA_VERSION)
        logger.info("Database initialized at %s", self.db_path)

    def _migrate(self, from_ver: int, to_ver: int):
        """Run schema migrations."""
        logger.info("Migrating schema from v%d to v%d", from_ver, to_ver)
        conn = self.connect()

        if from_ver < 2:
            # v2: Extended application fields
            for col, default in [
                ("bewerbungsart", "'mit_dokumenten'"),
                ("lebenslauf_variante", "'standard'"),
                ("ansprechpartner", "''"),
                ("kontakt_email", "''"),
                ("portal_name", "''"),
            ]:
                try:
                    conn.execute(
                        f"ALTER TABLE applications ADD COLUMN {col} TEXT DEFAULT {default}"
                    )
                except Exception as e:
                    logger.debug("Spalte existiert bereits oder Fehler: %s", e)
            logger.info("Migration v1->v2: applications erweitert")

        if from_ver < 3:
            # v3: Multi-Profil + Erfassungsfortschritt + Auto-Extraktion
            migrations_v3 = [
                ("profile", "is_active", "INTEGER DEFAULT 1"),
                ("profile", "erfassung_fortschritt", "TEXT DEFAULT '{}'"),
                ("positions", "profile_id", "TEXT"),
                ("education", "profile_id", "TEXT"),
                ("skills", "profile_id", "TEXT"),
                ("documents", "profile_id", "TEXT"),
            ]
            for table, col, coltype in migrations_v3:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                except Exception as e:
                    logger.debug("Spalte existiert bereits: %s", e)
            # Link existing data to first profile
            cur = conn.execute("SELECT id FROM profile LIMIT 1")
            row = cur.fetchone()
            if row:
                pid = row["id"]
                for table in ["positions", "education", "skills", "documents"]:
                    conn.execute(f"UPDATE {table} SET profile_id=? WHERE profile_id IS NULL", (pid,))
            # Create index for profile_id lookups
            for table in ["positions", "education", "skills", "documents"]:
                try:
                    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_profile ON {table}(profile_id)")
                except Exception:
                    pass
            logger.info("Migration v2->v3: Multi-Profil + Erfassung")

        if from_ver < 4:
            # v4: Erweiterte KI-Features (Gehalt, Follow-ups)
            migrations_v4 = [
                ("jobs", "salary_min", "REAL"),
                ("jobs", "salary_max", "REAL"),
                ("jobs", "salary_type", "TEXT"),
            ]
            for table, col, coltype in migrations_v4:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                except Exception as e:
                    logger.debug("Spalte existiert bereits: %s", e)
            # Create follow_ups table
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS follow_ups (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    scheduled_date TEXT NOT NULL,
                    follow_up_type TEXT DEFAULT 'nachfass',
                    template TEXT,
                    status TEXT DEFAULT 'geplant',
                    created_at TEXT,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_followups_app ON follow_ups(application_id);
                CREATE INDEX IF NOT EXISTS idx_followups_date ON follow_ups(scheduled_date, status);
            """)
            logger.info("Migration v3->v4: Gehalt-Spalten + Follow-ups Tabelle")

        if from_ver < 5:
            # v5: Smart Auto-Extraction + Profile Backup
            migrations_v5 = [
                ("documents", "extraction_status", "TEXT DEFAULT 'nicht_extrahiert'"),
                ("documents", "last_extraction_at", "TEXT"),
            ]
            for table, col, coltype in migrations_v5:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                except Exception as e:
                    logger.debug("Spalte existiert bereits: %s", e)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS extraction_history (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    profile_id TEXT NOT NULL,
                    extraction_type TEXT DEFAULT 'auto',
                    extracted_fields TEXT DEFAULT '{}',
                    conflicts TEXT DEFAULT '[]',
                    applied_fields TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'ausstehend',
                    created_at TEXT,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_extraction_doc ON extraction_history(document_id);
                CREATE INDEX IF NOT EXISTS idx_extraction_profile ON extraction_history(profile_id);
            """)
            logger.info("Migration v4->v5: Smart Auto-Extraction + Profile Backup")

        if from_ver < 6:
            # v6: FK fix (applications.job_hash ON DELETE SET NULL), rejection tracking
            # Recreate applications table with proper FK constraint
            try:
                conn.execute("PRAGMA foreign_keys=OFF")
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS applications_new (
                        id TEXT PRIMARY KEY,
                        job_hash TEXT REFERENCES jobs(hash) ON DELETE SET NULL,
                        title TEXT NOT NULL,
                        company TEXT NOT NULL,
                        url TEXT,
                        status TEXT DEFAULT 'beworben',
                        applied_at TEXT,
                        cover_letter_path TEXT,
                        cv_path TEXT,
                        project_list_path TEXT,
                        notes TEXT,
                        bewerbungsart TEXT DEFAULT 'mit_dokumenten',
                        lebenslauf_variante TEXT DEFAULT 'standard',
                        ansprechpartner TEXT DEFAULT '',
                        kontakt_email TEXT DEFAULT '',
                        portal_name TEXT DEFAULT '',
                        rejection_reason TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    );
                    INSERT OR IGNORE INTO applications_new
                        SELECT id, job_hash, title, company, url, status,
                               applied_at, cover_letter_path, cv_path, project_list_path,
                               notes, bewerbungsart, lebenslauf_variante,
                               ansprechpartner, kontakt_email, portal_name,
                               NULL, created_at, updated_at
                        FROM applications;
                    DROP TABLE IF EXISTS applications;
                    ALTER TABLE applications_new RENAME TO applications;
                    CREATE INDEX IF NOT EXISTS idx_apps_status ON applications(status);
                """)
                conn.execute("PRAGMA foreign_keys=ON")
            except Exception as e:
                logger.warning("Migration v5->v6 applications: %s", e)
                conn.execute("PRAGMA foreign_keys=ON")
            logger.info("Migration v5->v6: FK fix + rejection_reason Spalte")

        if from_ver < 7:
            # v7: Salary estimation flag + user preferences table
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN salary_min REAL")
            except Exception:
                pass  # Already exists from v4
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN salary_max REAL")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN salary_type TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN salary_estimated INTEGER DEFAULT 0")
            except Exception as e:
                logger.debug("salary_estimated already exists: %s", e)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                );
            """)
            try:
                conn.execute(
                    "ALTER TABLE documents ADD COLUMN linked_application_id INTEGER "
                    "REFERENCES applications(id) ON DELETE SET NULL"
                )
            except Exception:
                pass  # Already exists
            logger.info("Migration v6->v7: salary_estimated + user_preferences + doc-app link")

        if from_ver < 8:
            # v8: Profile isolation — add profile_id to applications and jobs
            for col_add in [
                ("applications", "profile_id TEXT"),
                ("jobs", "profile_id TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE {col_add[0]} ADD COLUMN {col_add[1]}")
                except Exception:
                    pass  # Already exists
            # Backfill: assign existing data to active profile
            active = conn.execute("SELECT id FROM profile WHERE is_active=1 LIMIT 1").fetchone()
            if active:
                pid = active["id"]
                conn.execute("UPDATE applications SET profile_id=? WHERE profile_id IS NULL", (pid,))
                conn.execute("UPDATE jobs SET profile_id=? WHERE profile_id IS NULL", (pid,))
            logger.info("Migration v7->v8: profile_id on applications + jobs, data backfilled")

        if from_ver < 9:
            # v9: Skill recency + suggested job titles
            try:
                conn.execute("ALTER TABLE skills ADD COLUMN last_used_year INTEGER")
            except Exception:
                pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS suggested_job_titles (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT DEFAULT 'auto',
                    confidence REAL DEFAULT 0.0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT
                )
            """)
            logger.info("Migration v8->v9: last_used_year on skills + suggested_job_titles table")

        conn.execute(
            "UPDATE settings SET value=? WHERE key='schema_version'",
            (str(to_ver),)
        )
        conn.commit()

    # === Profile ===

    def get_active_profile_id(self) -> Optional[str]:
        """Get the ID of the currently active profile."""
        conn = self.connect()
        cur = conn.execute("SELECT id FROM profile WHERE is_active=1 LIMIT 1")
        row = cur.fetchone()
        return row["id"] if row else None

    def get_profile(self) -> Optional[dict]:
        """Get the currently active profile with all related data."""
        conn = self.connect()
        cur = conn.execute("SELECT * FROM profile WHERE is_active=1 LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return None
        profile = dict(row)
        profile["preferences"] = json.loads(profile["preferences"] or "{}")
        profile["erfassung_fortschritt"] = json.loads(profile.get("erfassung_fortschritt") or "{}")
        pid = profile["id"]
        profile["positions"] = self._get_positions(pid)
        profile["education"] = self._get_education(pid)
        profile["skills"] = self._get_skills(pid)
        profile["documents"] = self._get_documents(pid)
        profile["suggested_job_titles"] = self.get_suggested_job_titles(pid)
        return profile

    def get_profiles(self) -> list:
        """List all profiles (for profile switching)."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT id, name, email, is_active, created_at, updated_at FROM profile ORDER BY is_active DESC, updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def switch_profile(self, profile_id: str) -> bool:
        """Activate a specific profile, deactivate all others."""
        conn = self.connect()
        conn.execute("UPDATE profile SET is_active=0")
        result = conn.execute("UPDATE profile SET is_active=1 WHERE id=?", (profile_id,))
        conn.commit()
        return result.rowcount > 0

    def delete_profile(self, profile_id: str, delete_files: bool = True):
        """Delete a profile and ALL its related data (CASCADE)."""
        conn = self.connect()

        # Delete document files from disk
        if delete_files:
            docs = conn.execute(
                "SELECT filepath FROM documents WHERE profile_id=?", (profile_id,)
            ).fetchall()
            for d in docs:
                if d["filepath"]:
                    try:
                        Path(d["filepath"]).unlink(missing_ok=True)
                    except Exception as e:
                        logger.warning("Could not delete file %s: %s", d["filepath"], e)

        # Disable FK constraints during bulk delete to avoid issues with
        # invalid references (e.g. job_hash="" from previous bug)
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            # Fix corrupt job_hash="" entries first
            conn.execute(
                "UPDATE applications SET job_hash=NULL WHERE profile_id=? AND job_hash=''",
                (profile_id,))

            # Delete extraction history for this profile's documents
            conn.execute("""
                DELETE FROM extraction_history WHERE profile_id=?
            """, (profile_id,))

            # Delete application events for this profile's applications
            conn.execute("""
                DELETE FROM application_events WHERE application_id IN
                (SELECT id FROM applications WHERE profile_id=?)
            """, (profile_id,))

            # Delete projects for positions of this profile
            conn.execute("""
                DELETE FROM projects WHERE position_id IN
                (SELECT id FROM positions WHERE profile_id=?)
            """, (profile_id,))

            # Delete all profile-linked data
            for table in ["positions", "education", "skills", "documents",
                           "applications", "jobs", "suggested_job_titles"]:
                conn.execute(f"DELETE FROM {table} WHERE profile_id=?", (profile_id,))

            # Delete the profile itself
            conn.execute("DELETE FROM profile WHERE id=?", (profile_id,))
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys=ON")
        logger.info("Profile %s and all related data deleted", profile_id)

    def reset_all_data(self):
        """Delete ALL data — factory reset for testing."""
        conn = self.connect()
        # Delete document files
        docs = conn.execute("SELECT filepath FROM documents WHERE filepath IS NOT NULL").fetchall()
        for d in docs:
            try:
                Path(d["filepath"]).unlink(missing_ok=True)
            except Exception:
                pass
        # Disable FK constraints during factory reset
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            # Fix corrupt job_hash="" entries first
            conn.execute("UPDATE applications SET job_hash=NULL WHERE job_hash=''")
            # Clear all data tables
            for table in ["extraction_history", "application_events", "projects",
                           "positions", "education", "skills", "documents",
                           "applications", "jobs", "blacklist", "background_jobs",
                           "user_preferences", "suggested_job_titles", "profile"]:
                try:
                    conn.execute(f"DELETE FROM {table}")
                except Exception:
                    pass
            # Keep settings but reset search-related ones
            conn.execute("DELETE FROM settings WHERE key != 'schema_version'")
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys=ON")
        logger.info("Factory reset: all data deleted")

    def save_profile(self, data: dict) -> str:
        conn = self.connect()
        now = _now()
        cur = conn.execute("SELECT id FROM profile WHERE is_active=1 LIMIT 1")
        existing = cur.fetchone()
        prefs = json.dumps(data.get("preferences", {}), ensure_ascii=False)
        if existing:
            conn.execute("""
                UPDATE profile SET
                    name=?, email=?, phone=?, address=?, city=?, plz=?,
                    country=?, birthday=?, nationality=?,
                    summary=?, informal_notes=?, preferences=?,
                    updated_at=?
                WHERE id=?
            """, (
                data.get("name"), data.get("email"), data.get("phone"),
                data.get("address"), data.get("city"), data.get("plz"),
                data.get("country", "Deutschland"), data.get("birthday"),
                data.get("nationality"),
                data.get("summary"), data.get("informal_notes"), prefs,
                now, existing["id"]
            ))
            conn.commit()
            return existing["id"]
        else:
            pid = _gen_id()
            # Deactivate other profiles, activate new one
            conn.execute("UPDATE profile SET is_active=0")
            conn.execute("""
                INSERT INTO profile (id, name, email, phone, address, city, plz,
                    country, birthday, nationality, summary, informal_notes,
                    preferences, is_active, erfassung_fortschritt,
                    created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '{}', ?, ?)
            """, (
                pid, data.get("name"), data.get("email"), data.get("phone"),
                data.get("address"), data.get("city"), data.get("plz"),
                data.get("country", "Deutschland"), data.get("birthday"),
                data.get("nationality"),
                data.get("summary"), data.get("informal_notes"), prefs,
                now, now
            ))
            # Adopt orphaned documents (uploaded before any profile existed)
            adopted = conn.execute(
                "UPDATE documents SET profile_id=? WHERE profile_id IS NULL", (pid,)
            ).rowcount
            if adopted:
                logger.info("Adopted %d orphaned document(s) for new profile %s", adopted, pid)
            conn.commit()
            return pid

    def create_profile(self, name: str, email: str = "") -> str:
        """Create a new, empty profile and activate it. Deactivates previous profile."""
        conn = self.connect()
        now = _now()
        pid = _gen_id()
        conn.execute("UPDATE profile SET is_active=0")
        conn.execute("""
            INSERT INTO profile (id, name, email, phone, address, city, plz,
                country, birthday, nationality, summary, informal_notes,
                preferences, is_active, erfassung_fortschritt,
                created_at, updated_at)
            VALUES (?, ?, ?, NULL, NULL, NULL, NULL,
                'Deutschland', NULL, NULL, NULL, NULL,
                '{}', 1, '{}', ?, ?)
        """, (pid, name, email, now, now))
        conn.commit()
        return pid

    # === Erfassungsfortschritt (PBP-026) ===

    def get_erfassung_fortschritt(self) -> dict:
        """Get progress of the profile creation conversation."""
        conn = self.connect()
        cur = conn.execute("SELECT erfassung_fortschritt FROM profile WHERE is_active=1 LIMIT 1")
        row = cur.fetchone()
        if row and row["erfassung_fortschritt"]:
            return json.loads(row["erfassung_fortschritt"])
        return {}

    def set_erfassung_fortschritt(self, fortschritt: dict):
        """Update the profile creation progress."""
        conn = self.connect()
        conn.execute(
            "UPDATE profile SET erfassung_fortschritt=?, updated_at=? WHERE is_active=1",
            (json.dumps(fortschritt, ensure_ascii=False), _now())
        )
        conn.commit()

    # === Positions (Berufserfahrung) ===

    def _get_positions(self, profile_id: str = None) -> list:
        conn = self.connect()
        if profile_id:
            rows = conn.execute(
                "SELECT * FROM positions WHERE profile_id=? ORDER BY start_date DESC",
                (profile_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM positions ORDER BY start_date DESC"
            ).fetchall()
        positions = []
        for row in rows:
            pos = dict(row)
            pos["projects"] = [
                dict(p) for p in conn.execute(
                    "SELECT * FROM projects WHERE position_id=? ORDER BY sort_order",
                    (row["id"],)
                ).fetchall()
            ]
            positions.append(pos)
        return positions

    def add_position(self, data: dict) -> str:
        conn = self.connect()
        pid = _gen_id()
        now = _now()
        profile_id = data.get("profile_id") or self.get_active_profile_id()
        conn.execute("""
            INSERT INTO positions (id, company, title, location, start_date, end_date,
                is_current, employment_type, industry, description,
                tasks, achievements, technologies, profile_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid, data.get("company"), data.get("title"), data.get("location"),
            data.get("start_date"), data.get("end_date"),
            data.get("is_current", False), data.get("employment_type", "festanstellung"),
            data.get("industry"), data.get("description"),
            data.get("tasks"), data.get("achievements"), data.get("technologies"),
            profile_id, now
        ))
        conn.commit()
        return pid

    def add_project(self, position_id: str, data: dict) -> str:
        conn = self.connect()
        pid = _gen_id()
        conn.execute("""
            INSERT INTO projects (id, position_id, name, description,
                role, situation, task, action, result,
                technologies, duration, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid, position_id, data.get("name"), data.get("description"),
            data.get("role"), data.get("situation"), data.get("task"),
            data.get("action"), data.get("result"),
            data.get("technologies"), data.get("duration"),
            data.get("sort_order", 0)
        ))
        conn.commit()
        return pid

    def update_position(self, position_id: str, data: dict):
        conn = self.connect()
        fields = ["company", "title", "location", "start_date", "end_date",
                  "is_current", "employment_type", "industry", "description",
                  "tasks", "achievements", "technologies"]
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if sets:
            vals.append(position_id)
            conn.execute(f"UPDATE positions SET {','.join(sets)} WHERE id=?", vals)
            conn.commit()

    def update_education(self, education_id: str, data: dict):
        conn = self.connect()
        fields = ["institution", "degree", "field_of_study", "start_date",
                  "end_date", "grade", "description"]
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if sets:
            vals.append(education_id)
            conn.execute(f"UPDATE education SET {','.join(sets)} WHERE id=?", vals)
            conn.commit()

    def update_skill(self, skill_id: str, data: dict):
        conn = self.connect()
        fields = ["name", "category", "level", "years_experience", "last_used_year"]
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if sets:
            vals.append(skill_id)
            conn.execute(f"UPDATE skills SET {','.join(sets)} WHERE id=?", vals)
            conn.commit()

    def delete_position(self, position_id: str):
        conn = self.connect()
        # Projects are deleted automatically via ON DELETE CASCADE
        conn.execute("DELETE FROM positions WHERE id = ?", (position_id,))
        conn.commit()

    # === Education ===

    def _get_education(self, profile_id: str = None) -> list:
        conn = self.connect()
        if profile_id:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM education WHERE profile_id=? ORDER BY end_date DESC",
                (profile_id,)
            ).fetchall()]
        return [dict(r) for r in conn.execute(
            "SELECT * FROM education ORDER BY end_date DESC"
        ).fetchall()]

    def add_education(self, data: dict) -> str:
        conn = self.connect()
        eid = _gen_id()
        profile_id = data.get("profile_id") or self.get_active_profile_id()
        conn.execute("""
            INSERT INTO education (id, institution, degree, field_of_study,
                start_date, end_date, grade, description, profile_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eid, data.get("institution"), data.get("degree"),
            data.get("field_of_study"), data.get("start_date"),
            data.get("end_date"), data.get("grade"), data.get("description"),
            profile_id
        ))
        conn.commit()
        return eid

    def delete_education(self, education_id: str):
        conn = self.connect()
        conn.execute("DELETE FROM education WHERE id = ?", (education_id,))
        conn.commit()

    # === Skills ===

    def _get_skills(self, profile_id: str = None) -> list:
        conn = self.connect()
        if profile_id:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM skills WHERE profile_id=? ORDER BY category, level DESC",
                (profile_id,)
            ).fetchall()]
        return [dict(r) for r in conn.execute(
            "SELECT * FROM skills ORDER BY category, level DESC"
        ).fetchall()]

    def add_skill(self, data: dict) -> str:
        conn = self.connect()
        sid = _gen_id()
        profile_id = data.get("profile_id") or self.get_active_profile_id()
        conn.execute("""
            INSERT INTO skills (id, name, category, level, years_experience, last_used_year, profile_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            sid, data.get("name"), data.get("category", "fachlich"),
            data.get("level", 3), data.get("years_experience"),
            data.get("last_used_year"), profile_id
        ))
        conn.commit()
        return sid

    def delete_skill(self, skill_id: str):
        conn = self.connect()
        conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        conn.commit()

    # === Suggested Job Titles ===

    def get_suggested_job_titles(self, profile_id: str = None) -> list:
        conn = self.connect()
        pid = profile_id or self.get_active_profile_id()
        if not pid:
            return []
        return [dict(r) for r in conn.execute(
            "SELECT * FROM suggested_job_titles WHERE profile_id=? ORDER BY confidence DESC",
            (pid,)
        ).fetchall()]

    def add_job_title(self, title: str, source: str = "auto",
                      confidence: float = 0.0, profile_id: str = None) -> str:
        conn = self.connect()
        pid = profile_id or self.get_active_profile_id()
        tid = _gen_id()
        conn.execute("""
            INSERT INTO suggested_job_titles (id, profile_id, title, source, confidence, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (tid, pid, title, source, confidence, _now()))
        conn.commit()
        return tid

    def update_job_title(self, title_id: str, data: dict):
        conn = self.connect()
        fields = ["title", "is_active", "confidence"]
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if sets:
            vals.append(title_id)
            conn.execute(f"UPDATE suggested_job_titles SET {','.join(sets)} WHERE id=?", vals)
            conn.commit()

    def delete_job_title(self, title_id: str):
        conn = self.connect()
        conn.execute("DELETE FROM suggested_job_titles WHERE id=?", (title_id,))
        conn.commit()

    # === Documents ===

    def _get_documents(self, profile_id: str = None) -> list:
        conn = self.connect()
        if profile_id:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM documents WHERE profile_id=? ORDER BY created_at DESC",
                (profile_id,)
            ).fetchall()]
        return [dict(r) for r in conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ).fetchall()]

    def add_document(self, data: dict) -> str:
        conn = self.connect()
        did = _gen_id()
        profile_id = data.get("profile_id") or self.get_active_profile_id()
        conn.execute("""
            INSERT INTO documents (id, filename, filepath, doc_type,
                extracted_text, linked_position_id, profile_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            did, data.get("filename"), data.get("filepath"),
            data.get("doc_type", "sonstiges"), data.get("extracted_text"),
            data.get("linked_position_id"), profile_id, _now()
        ))
        conn.commit()
        return did

    def delete_document(self, doc_id: str):
        conn = self.connect()
        # Get filepath to delete file from disk
        row = conn.execute("SELECT filepath FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if row and row["filepath"]:
            try:
                Path(row["filepath"]).unlink(missing_ok=True)
            except Exception as e:
                logger.warning("Dokument-Datei konnte nicht geloescht werden: %s", e)
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()

    def link_document_to_application(self, doc_id, application_id: int):
        """Link a document to an application."""
        conn = self.connect()
        conn.execute(
            "UPDATE documents SET linked_application_id=? WHERE id=?",
            (application_id, str(doc_id)),
        )
        conn.commit()

    # === Jobs ===

    def save_jobs(self, jobs: list):
        conn = self.connect()
        now = _now()
        pid = self.get_active_profile_id()
        for job in jobs:
            conn.execute("""
                INSERT OR REPLACE INTO jobs (hash, title, company, location, url,
                    source, description, score, remote_level, distance_km,
                    salary_info, salary_min, salary_max, salary_type, salary_estimated,
                    employment_type, profile_id, found_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                job["hash"], job.get("title"), job.get("company"),
                job.get("location"), job.get("url"), job.get("source"),
                job.get("description"), job.get("score", 0),
                job.get("remote_level", "unbekannt"),
                job.get("distance_km"), job.get("salary_info"),
                job.get("salary_min"), job.get("salary_max"),
                job.get("salary_type"), job.get("salary_estimated", 0),
                job.get("employment_type", "festanstellung"), pid,
                job.get("found_at", now), now
            ))
        conn.commit()

    def get_active_jobs(self, filters: Optional[dict] = None) -> list:
        conn = self.connect()
        pid = self.get_active_profile_id()
        query = "SELECT * FROM jobs WHERE is_active=1 AND (profile_id=? OR profile_id IS NULL)"
        params = [pid]
        if filters:
            if filters.get("source"):
                query += " AND source=?"
                params.append(filters["source"])
            if filters.get("employment_type"):
                query += " AND employment_type=?"
                params.append(filters["employment_type"])
            if filters.get("min_score"):
                query += " AND score>=?"
                params.append(filters["min_score"])
        query += " ORDER BY score DESC, found_at DESC"
        return [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_dismissed_jobs(self) -> list:
        conn = self.connect()
        pid = self.get_active_profile_id()
        return [dict(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) ORDER BY updated_at DESC",
            (pid,)
        ).fetchall()]

    def dismiss_job(self, job_hash: str, reason: str):
        conn = self.connect()
        conn.execute(
            "UPDATE jobs SET is_active=0, dismiss_reason=?, updated_at=? WHERE hash=?",
            (reason, _now(), job_hash)
        )
        conn.commit()

    def restore_job(self, job_hash: str):
        conn = self.connect()
        conn.execute(
            "UPDATE jobs SET is_active=1, dismiss_reason=NULL, updated_at=? WHERE hash=?",
            (_now(), job_hash)
        )
        conn.commit()

    # === Applications ===

    def get_applications(self, status: Optional[str] = None) -> list:
        conn = self.connect()
        pid = self.get_active_profile_id()
        if status:
            rows = conn.execute(
                "SELECT * FROM applications WHERE status=? AND (profile_id=? OR profile_id IS NULL) ORDER BY applied_at DESC",
                (status, pid)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM applications WHERE (profile_id=? OR profile_id IS NULL) ORDER BY applied_at DESC",
                (pid,)
            ).fetchall()
        apps = []
        for row in rows:
            app = dict(row)
            app["events"] = [dict(e) for e in conn.execute(
                "SELECT * FROM application_events WHERE application_id=? ORDER BY event_date",
                (row["id"],)
            ).fetchall()]
            apps.append(app)
        return apps

    def add_application(self, data: dict) -> str:
        conn = self.connect()
        aid = _gen_id()
        now = _now()
        pid = self.get_active_profile_id()
        conn.execute("""
            INSERT INTO applications (id, job_hash, profile_id, title, company, url, status,
                applied_at, cover_letter_path, cv_path, notes, created_at,
                bewerbungsart, lebenslauf_variante, ansprechpartner,
                kontakt_email, portal_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            aid, data.get("job_hash") or None, pid, data.get("title"), data.get("company"),
            data.get("url"), data.get("status", "beworben"),
            data.get("applied_at", now), data.get("cover_letter_path"),
            data.get("cv_path"), data.get("notes"), now,
            data.get("bewerbungsart", "mit_dokumenten"),
            data.get("lebenslauf_variante", "standard"),
            data.get("ansprechpartner", ""),
            data.get("kontakt_email", ""),
            data.get("portal_name", ""),
        ))
        # Add initial event
        conn.execute("""
            INSERT INTO application_events (application_id, status, event_date, notes)
            VALUES (?, ?, ?, ?)
        """, (aid, data.get("status", "beworben"), now, "Bewerbung erstellt"))
        conn.commit()
        return aid

    def update_application_status(self, app_id: str, new_status: str,
                                   notes: str = "", rejection_reason: str = ""):
        conn = self.connect()
        now = _now()
        if rejection_reason and new_status == "abgelehnt":
            conn.execute(
                "UPDATE applications SET status=?, rejection_reason=?, updated_at=? WHERE id=?",
                (new_status, rejection_reason, now, app_id)
            )
        else:
            conn.execute(
                "UPDATE applications SET status=?, updated_at=? WHERE id=?",
                (new_status, now, app_id)
            )
        conn.execute("""
            INSERT INTO application_events (application_id, status, event_date, notes)
            VALUES (?, ?, ?, ?)
        """, (app_id, new_status, now, notes))
        conn.commit()

    # === Search Criteria ===

    def get_search_criteria(self) -> dict:
        conn = self.connect()
        cur = conn.execute("SELECT * FROM search_criteria")
        rows = cur.fetchall()
        criteria = {}
        for row in rows:
            criteria[row["key"]] = json.loads(row["value"])
        return criteria

    def set_search_criteria(self, key: str, value):
        conn = self.connect()
        conn.execute("""
            INSERT OR REPLACE INTO search_criteria (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, json.dumps(value, ensure_ascii=False), _now()))
        conn.commit()

    # === Blacklist ===

    def add_to_blacklist(self, entry_type: str, value: str, reason: str = ""):
        conn = self.connect()
        conn.execute("""
            INSERT OR IGNORE INTO blacklist (type, value, reason, created_at)
            VALUES (?, ?, ?, ?)
        """, (entry_type, value, reason, _now()))
        conn.commit()

    def get_blacklist(self) -> list:
        conn = self.connect()
        return [dict(r) for r in conn.execute(
            "SELECT * FROM blacklist ORDER BY type, value"
        ).fetchall()]

    # === Background Jobs ===

    def create_background_job(self, job_type: str, params: dict = None) -> str:
        conn = self.connect()
        jid = _gen_id()
        conn.execute("""
            INSERT INTO background_jobs (id, job_type, params, status, created_at)
            VALUES (?, ?, ?, 'running', ?)
        """, (jid, job_type, json.dumps(params or {}), _now()))
        conn.commit()
        return jid

    def update_background_job(self, job_id: str, status: str,
                               progress: int = 0, message: str = "",
                               result: dict = None):
        conn = self.connect()
        conn.execute("""
            UPDATE background_jobs SET status=?, progress=?, message=?,
                result=?, updated_at=?
            WHERE id=?
        """, (
            status, progress, message,
            json.dumps(result) if result else None,
            _now(), job_id
        ))
        conn.commit()

    def get_background_job(self, job_id: str) -> Optional[dict]:
        conn = self.connect()
        cur = conn.execute("SELECT * FROM background_jobs WHERE id=?", (job_id,))
        row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["params"] = json.loads(d["params"] or "{}")
        d["result"] = json.loads(d["result"] or "null")
        return d

    # === Statistics ===

    def get_statistics(self) -> dict:
        conn = self.connect()
        stats = {}
        # Applications by status
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        ).fetchall()
        stats["applications_by_status"] = {r["status"]: r["cnt"] for r in rows}
        stats["total_applications"] = sum(r["cnt"] for r in rows)
        # Jobs
        stats["active_jobs"] = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_active=1"
        ).fetchone()[0]
        stats["dismissed_jobs"] = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_active=0"
        ).fetchone()[0]
        # Conversion rate
        total = stats["total_applications"]
        if total > 0:
            interviews = stats["applications_by_status"].get("interview", 0)
            offers = stats["applications_by_status"].get("angebot", 0)
            stats["interview_rate"] = round(interviews / total * 100, 1)
            stats["offer_rate"] = round(offers / total * 100, 1)
        return stats

    # === Salary Data (PBP-014) ===

    def save_salary_data(self, job_hash: str, salary_min: float, salary_max: float, salary_type: str):
        """Save extracted salary data for a job."""
        conn = self.connect()
        conn.execute(
            "UPDATE jobs SET salary_min=?, salary_max=?, salary_type=?, updated_at=? WHERE hash=?",
            (salary_min, salary_max, salary_type, _now(), job_hash)
        )
        conn.commit()

    def get_salary_statistics(self) -> dict:
        """Get aggregated salary statistics across all jobs with salary data."""
        conn = self.connect()
        rows = conn.execute("""
            SELECT salary_min, salary_max, salary_type, employment_type, source, location
            FROM jobs WHERE salary_min IS NOT NULL AND is_active=1
        """).fetchall()
        if not rows:
            return {"anzahl": 0, "nachricht": "Keine Gehaltsdaten vorhanden"}
        data = [dict(r) for r in rows]
        annual = [d for d in data if d["salary_type"] == "jaehrlich"]
        daily = [d for d in data if d["salary_type"] == "taeglich"]
        result = {"anzahl": len(data)}
        if annual:
            mins = [d["salary_min"] for d in annual]
            maxs = [d["salary_max"] for d in annual]
            result["festanstellung"] = {
                "anzahl": len(annual),
                "gehalt_min": min(mins),
                "gehalt_max": max(maxs),
                "durchschnitt_min": round(sum(mins) / len(mins)),
                "durchschnitt_max": round(sum(maxs) / len(maxs)),
                "median_min": sorted(mins)[len(mins) // 2],
            }
        if daily:
            mins = [d["salary_min"] for d in daily]
            maxs = [d["salary_max"] for d in daily]
            result["freelance"] = {
                "anzahl": len(daily),
                "tagessatz_min": min(mins),
                "tagessatz_max": max(maxs),
                "durchschnitt_min": round(sum(mins) / len(mins)),
                "durchschnitt_max": round(sum(maxs) / len(maxs)),
            }
        return result

    def get_company_jobs(self, company: str) -> list:
        """Get all jobs from a specific company."""
        conn = self.connect()
        return [dict(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE company LIKE ? ORDER BY score DESC",
            (f"%{company}%",)
        ).fetchall()]

    def get_skill_frequency(self) -> list:
        """Analyze skill keywords frequency in active job descriptions."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT description FROM jobs WHERE is_active=1 AND description IS NOT NULL"
        ).fetchall()
        return [r["description"] for r in rows]

    # === Follow-ups (PBP-014) ===

    def add_follow_up(self, application_id: str, scheduled_date: str,
                      follow_up_type: str = "nachfass", template: str = "") -> str:
        """Schedule a follow-up for an application."""
        conn = self.connect()
        fid = _gen_id()
        conn.execute("""
            INSERT INTO follow_ups (id, application_id, scheduled_date,
                follow_up_type, template, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'geplant', ?)
        """, (fid, application_id, scheduled_date, follow_up_type, template, _now()))
        conn.commit()
        return fid

    def get_pending_follow_ups(self) -> list:
        """Get all pending follow-ups with application details."""
        conn = self.connect()
        return [dict(r) for r in conn.execute("""
            SELECT f.*, a.title, a.company, a.status as app_status, a.applied_at
            FROM follow_ups f
            JOIN applications a ON f.application_id = a.id
            WHERE f.status = 'geplant'
            ORDER BY f.scheduled_date ASC
        """).fetchall()]

    def complete_follow_up(self, follow_up_id: str, status: str = "gesendet"):
        """Mark a follow-up as completed or skipped."""
        conn = self.connect()
        conn.execute(
            "UPDATE follow_ups SET status=?, completed_at=? WHERE id=?",
            (status, _now(), follow_up_id)
        )
        conn.commit()

    # === Settings ===

    def get_setting(self, key: str, default=None):
        conn = self.connect()
        cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return json.loads(row["value"]) if row else default

    def set_setting(self, key: str, value):
        conn = self.connect()
        conn.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        """, (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()

    # === User Preferences (PBP v0.10.0) ===

    def get_user_preference(self, key: str, default=None):
        """Get a user preference value."""
        conn = self.connect()
        cur = conn.execute("SELECT value FROM user_preferences WHERE key=?", (key,))
        row = cur.fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]

    def set_user_preference(self, key: str, value):
        """Set a user preference value."""
        conn = self.connect()
        conn.execute("""
            INSERT OR REPLACE INTO user_preferences (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, json.dumps(value, ensure_ascii=False), _now()))
        conn.commit()

    # === Rejection Analysis (PBP v0.9.0) ===

    def get_rejection_patterns(self) -> dict:
        """Analyze rejection patterns across all applications."""
        conn = self.connect()
        apps = conn.execute("""
            SELECT a.*, ae.notes as event_notes, ae.event_date
            FROM applications a
            LEFT JOIN application_events ae ON a.id = ae.application_id AND ae.status = 'abgelehnt'
            WHERE a.status = 'abgelehnt'
            ORDER BY a.updated_at DESC
        """).fetchall()
        if not apps:
            return {"anzahl": 0, "muster": [], "nachricht": "Keine Ablehnungen vorhanden."}

        rejections = [dict(a) for a in apps]
        # Group by company
        by_company = {}
        for r in rejections:
            co = r.get("company", "Unbekannt")
            by_company.setdefault(co, []).append(r)

        # Aggregate reasons
        reasons = {}
        for r in rejections:
            reason = r.get("rejection_reason") or r.get("event_notes") or "Kein Grund angegeben"
            reasons.setdefault(reason, 0)
            reasons[reason] += 1

        return {
            "anzahl": len(rejections),
            "nach_firma": {k: len(v) for k, v in by_company.items()},
            "nach_grund": dict(sorted(reasons.items(), key=lambda x: -x[1])),
            "ablehnungen": [{
                "firma": r.get("company"),
                "stelle": r.get("title"),
                "beworben_am": r.get("applied_at"),
                "grund": r.get("rejection_reason") or r.get("event_notes") or "",
            } for r in rejections[:20]],
        }

    def get_next_steps(self) -> list:
        """Get personalized next steps based on profile completeness and activity.

        Returns list of dicts with keys:
          aktion, beschreibung, prioritaet (hoch/mittel/info),
          prompt (optional), action_type (dashboard/prompt),
          action_target (JS function for dashboard), action_label (button text)
        """
        steps = []
        profile = self.get_profile()
        conn = self.connect()
        profile_id = self.get_active_profile_id()

        if not profile:
            steps.append({"aktion": "Profil erstellen", "prioritaet": "hoch",
                          "beschreibung": "Erstelle dein Bewerberprofil — per Gespraech, Dokument-Upload oder manuell.",
                          "action_type": "dashboard", "action_target": "wizardDocUpload()",
                          "action_label": "Lebenslauf hochladen",
                          "prompt": "/ersterfassung"})
            return steps

        # Check completeness — profile building
        if not profile.get("summary"):
            steps.append({"aktion": "Zusammenfassung ergaenzen", "prioritaet": "hoch",
                          "beschreibung": "Dein Profil braucht eine Zusammenfassung fuer Anschreiben und CV.",
                          "action_type": "dashboard", "action_target": "showProfileForm()",
                          "action_label": "Profil bearbeiten", "prompt": "/profil_ueberpruefen"})
        if not profile.get("positions"):
            steps.append({"aktion": "Berufserfahrung hinzufuegen", "prioritaet": "hoch",
                          "beschreibung": "Berufserfahrung ist fuer Bewerbungen essentiell.",
                          "action_type": "dashboard", "action_target": "showPage('profil'); setTimeout(showPositionForm, 200)",
                          "action_label": "+ Position", "prompt": "/ersterfassung"})
        if not profile.get("skills"):
            steps.append({"aktion": "Skills hinzufuegen", "prioritaet": "mittel",
                          "beschreibung": "Skills helfen beim Job-Matching und Fit-Score.",
                          "action_type": "dashboard", "action_target": "showPage('profil'); setTimeout(showSkillForm, 200)",
                          "action_label": "+ Skill"})
        if not profile.get("education"):
            steps.append({"aktion": "Ausbildung ergaenzen", "prioritaet": "mittel",
                          "beschreibung": "Fuer ein vollstaendiges Bewerberprofil.",
                          "action_type": "dashboard", "action_target": "showPage('profil'); setTimeout(showEducationForm, 200)",
                          "action_label": "+ Ausbildung"})

        # Check documents for extraction
        docs = profile.get("documents", [])
        unextracted = [d for d in docs if d.get("extraction_status") == "nicht_extrahiert"
                       and d.get("extracted_text")]
        if unextracted:
            steps.append({"aktion": f"{len(unextracted)} Dokument(e) analysieren",
                          "prioritaet": "hoch",
                          "beschreibung": "Hochgeladene Dokumente wurden noch nicht ausgewertet — Claude kann die Daten extrahieren.",
                          "action_type": "prompt", "prompt": "/profil_erweiterung"})
        elif not docs:
            # No documents at all — suggest upload
            steps.append({"aktion": "Dokumente hochladen", "prioritaet": "mittel",
                          "beschreibung": "Lade Lebenslauf oder Zeugnisse hoch fuer automatische Profil-Erweiterung.",
                          "action_type": "dashboard", "action_target": "wizardDocUpload()",
                          "action_label": "Dokument hochladen"})

        # Check follow-ups
        due_followups = conn.execute("""
            SELECT COUNT(*) FROM follow_ups
            WHERE status = 'geplant' AND scheduled_date <= date('now')
        """).fetchone()[0]
        if due_followups:
            steps.append({"aktion": f"{due_followups} faellige(s) Follow-up(s)",
                          "prioritaet": "hoch",
                          "beschreibung": "Nachfass-Aktionen sind faellig — nicht vergessen!",
                          "action_type": "dashboard",
                          "action_target": "showPage('bewerbungen')",
                          "action_label": "Bewerbungen ansehen"})

        # Check sources
        active_sources = self.get_setting("active_sources", [])
        if not active_sources:
            steps.append({"aktion": "Jobquellen aktivieren", "prioritaet": "hoch",
                          "beschreibung": "Ohne aktive Quellen kann keine Jobsuche gestartet werden.",
                          "action_type": "dashboard",
                          "action_target": "showPage('einstellungen')",
                          "action_label": "Einstellungen"})

        # Check job search recency
        last_search = self.get_setting("last_search_at")
        if last_search:
            try:
                from datetime import datetime
                days = (datetime.now() - datetime.fromisoformat(last_search)).days
                if days >= 7:
                    steps.append({"aktion": "Neue Jobsuche starten",
                                  "prioritaet": "hoch" if days > 14 else "mittel",
                                  "beschreibung": f"Letzte Suche war vor {days} Tagen. Neue Stellen warten!",
                                  "action_type": "prompt", "prompt": "/jobsuche_workflow"})
            except (ValueError, TypeError):
                pass

        # Check active jobs without applications
        where_profile = "AND profile_id = ?" if profile_id else ""
        params_profile = (profile_id,) if profile_id else ()
        active_jobs = conn.execute(
            f"SELECT COUNT(*) FROM jobs WHERE is_active=1 {where_profile}",
            params_profile
        ).fetchone()[0]
        high_score_jobs = conn.execute(
            f"SELECT COUNT(*) FROM jobs WHERE is_active=1 AND score >= 8 {where_profile}",
            params_profile
        ).fetchone()[0]
        apps_count = conn.execute(
            f"SELECT COUNT(*) FROM applications {('WHERE profile_id = ?' if profile_id else '')}",
            params_profile
        ).fetchone()[0]

        if high_score_jobs > 0 and apps_count == 0:
            steps.append({"aktion": "Erste Bewerbung schreiben", "prioritaet": "hoch",
                          "beschreibung": f"{high_score_jobs} gut passende Stelle(n) warten auf deine Bewerbung!",
                          "action_type": "dashboard",
                          "action_target": "showPage('stellen')",
                          "action_label": "Stellen ansehen"})
        elif active_jobs == 0 and not last_search and active_sources:
            steps.append({"aktion": "Erste Jobsuche starten", "prioritaet": "mittel",
                          "beschreibung": "Quellen sind aktiv — starte jetzt deine erste Suche.",
                          "action_type": "prompt", "prompt": "/jobsuche_workflow"})

        # Check rejections — suggest pattern analysis
        rejections = conn.execute(
            f"SELECT COUNT(*) FROM applications WHERE status='abgelehnt' {where_profile}",
            params_profile
        ).fetchone()[0]
        if rejections >= 3:
            steps.append({"aktion": "Ablehnungen analysieren", "prioritaet": "mittel",
                          "beschreibung": f"{rejections} Absagen erhalten — analysiere die Muster fuer bessere Chancen.",
                          "action_type": "prompt", "prompt": "/profil_analyse"})

        # Suggest interview prep when interviews scheduled
        interviews = conn.execute(
            f"SELECT COUNT(*) FROM applications WHERE status IN ('interview','zweitgespraech') {where_profile}",
            params_profile
        ).fetchone()[0]
        if interviews > 0:
            steps.append({"aktion": "Interview vorbereiten", "prioritaet": "hoch",
                          "beschreibung": f"{interviews} Interview(s) stehen an — bereite dich vor!",
                          "action_type": "prompt", "prompt": "/interview_vorbereitung"})

        if not steps:
            steps.append({"aktion": "Alles auf dem neuesten Stand", "prioritaet": "info",
                          "beschreibung": "Weiter so! Pruefe regelmaessig deine Bewerbungen und starte neue Suchen.",
                          "prompt": ""})
        return steps

    # === Extraction History (PBP v0.8.0) ===

    def add_extraction_history(self, data: dict) -> str:
        """Record an extraction operation."""
        conn = self.connect()
        eid = _gen_id()
        conn.execute("""
            INSERT INTO extraction_history (id, document_id, profile_id, extraction_type,
                extracted_fields, conflicts, applied_fields, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eid, data["document_id"], data["profile_id"],
            data.get("extraction_type", "auto"),
            json.dumps(data.get("extracted_fields", {}), ensure_ascii=False),
            json.dumps(data.get("conflicts", []), ensure_ascii=False),
            json.dumps(data.get("applied_fields", {}), ensure_ascii=False),
            data.get("status", "ausstehend"), _now()
        ))
        conn.commit()
        return eid

    def update_extraction_history(self, extraction_id: str, status: str,
                                   applied_fields: dict = None):
        """Update extraction status and applied fields."""
        conn = self.connect()
        if applied_fields:
            conn.execute("""
                UPDATE extraction_history SET status=?, applied_fields=?, completed_at=?
                WHERE id=?
            """, (status, json.dumps(applied_fields, ensure_ascii=False),
                  _now(), extraction_id))
        else:
            conn.execute(
                "UPDATE extraction_history SET status=?, completed_at=? WHERE id=?",
                (status, _now(), extraction_id)
            )
        conn.commit()

    def get_extraction_history(self, profile_id: str = None,
                                document_id: str = None) -> list:
        """Get extraction history for a profile or document."""
        conn = self.connect()
        query = "SELECT * FROM extraction_history"
        params = []
        conditions = []
        if profile_id:
            conditions.append("profile_id=?")
            params.append(profile_id)
        if document_id:
            conditions.append("document_id=?")
            params.append(document_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        return [dict(r) for r in conn.execute(query, params).fetchall()]

    def update_document_extraction_status(self, doc_id: str, status: str):
        """Update extraction status of a document."""
        conn = self.connect()
        conn.execute(
            "UPDATE documents SET extraction_status=?, last_extraction_at=? WHERE id=?",
            (status, _now(), doc_id)
        )
        conn.commit()

    # === Profile Export/Import (PBP v0.8.0) ===

    def export_profile_json(self, profile_id: str = None) -> Optional[dict]:
        """Export a complete profile as JSON for backup."""
        if not profile_id:
            profile_id = self.get_active_profile_id()
        if not profile_id:
            return None

        conn = self.connect()
        row = conn.execute("SELECT * FROM profile WHERE id=?", (profile_id,)).fetchone()
        if not row:
            return None

        profile = dict(row)
        profile["preferences"] = json.loads(profile.get("preferences") or "{}")
        profile["erfassung_fortschritt"] = json.loads(
            profile.get("erfassung_fortschritt") or "{}")
        profile["positions"] = self._get_positions(profile_id)
        profile["education"] = self._get_education(profile_id)
        profile["skills"] = self._get_skills(profile_id)
        # Documents: metadata only (no extracted_text to keep file small)
        docs = self._get_documents(profile_id)
        for d in docs:
            d.pop("extracted_text", None)
        profile["documents"] = docs

        profile["_export_meta"] = {
            "version": "0.8.0",
            "schema_version": SCHEMA_VERSION,
            "exported_at": _now(),
            "export_type": "full_profile_backup",
        }
        return profile

    def import_profile_json(self, data: dict) -> str:
        """Import a profile from JSON backup. Creates a new profile."""
        # Validate required fields
        required = ["name"]
        for field in required:
            if not data.get(field):
                raise ValueError(f"Pflichtfeld fehlt im Import: {field}")
        # Validate nested data types
        for key in ["positions", "education", "skills", "documents"]:
            val = data.get(key)
            if val is not None and not isinstance(val, list):
                raise ValueError(f"Ungueltiges Format fuer '{key}': Liste erwartet")
        if data.get("preferences") is not None and not isinstance(data.get("preferences"), (dict, str)):
            raise ValueError("Ungueltiges Format fuer 'preferences': Dict erwartet")
        # Ensure preferences is a dict (could be JSON string from export)
        if isinstance(data.get("preferences"), str):
            data["preferences"] = json.loads(data["preferences"])

        # Strip export metadata and nested data
        data.pop("_export_meta", None)
        positions = data.pop("positions", [])
        education = data.pop("education", [])
        skills = data.pop("skills", [])
        documents = data.pop("documents", [])

        # Strip internal IDs (will be regenerated)
        data.pop("id", None)
        data.pop("created_at", None)
        data.pop("updated_at", None)
        data.pop("is_active", None)

        # Deactivate all existing profiles so save_profile creates new one
        conn = self.connect()
        conn.execute("UPDATE profile SET is_active=0")
        conn.commit()

        # Save new profile (no active profile → creates new)
        pid = self.save_profile(data)

        # Import positions with projects
        for pos in positions:
            projects = pos.pop("projects", [])
            pos.pop("id", None)
            pos.pop("created_at", None)
            pos["profile_id"] = pid
            pos_id = self.add_position(pos)
            for proj in projects:
                proj.pop("id", None)
                self.add_project(pos_id, proj)

        # Import education
        for edu in education:
            edu.pop("id", None)
            edu["profile_id"] = pid
            self.add_education(edu)

        # Import skills
        for skill in skills:
            skill.pop("id", None)
            skill["profile_id"] = pid
            self.add_skill(skill)

        # Import document metadata (not files themselves)
        for doc in documents:
            doc.pop("id", None)
            doc["profile_id"] = pid
            doc.pop("extraction_status", None)
            doc.pop("last_extraction_at", None)
            self.add_document(doc)

        return pid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS profile (
    id TEXT PRIMARY KEY,
    name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    city TEXT,
    plz TEXT,
    country TEXT DEFAULT 'Deutschland',
    birthday TEXT,
    nationality TEXT,
    photo_path TEXT,
    summary TEXT,
    informal_notes TEXT,
    preferences TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    erfassung_fortschritt TEXT DEFAULT '{}',
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    start_date TEXT,
    end_date TEXT,
    is_current INTEGER DEFAULT 0,
    employment_type TEXT DEFAULT 'festanstellung',
    industry TEXT,
    description TEXT,
    tasks TEXT,
    achievements TEXT,
    technologies TEXT,
    profile_id TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    position_id TEXT NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    role TEXT,
    situation TEXT,
    task TEXT,
    action TEXT,
    result TEXT,
    technologies TEXT,
    duration TEXT,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS education (
    id TEXT PRIMARY KEY,
    institution TEXT NOT NULL,
    degree TEXT,
    field_of_study TEXT,
    start_date TEXT,
    end_date TEXT,
    grade TEXT,
    description TEXT,
    profile_id TEXT
);

CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'fachlich',
    level INTEGER DEFAULT 3,
    years_experience INTEGER,
    last_used_year INTEGER,
    profile_id TEXT
);

CREATE TABLE IF NOT EXISTS suggested_job_titles (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT DEFAULT 'auto',
    confidence REAL DEFAULT 0.0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT,
    doc_type TEXT DEFAULT 'sonstiges',
    extracted_text TEXT,
    linked_position_id TEXT REFERENCES positions(id) ON DELETE SET NULL,
    linked_application_id INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    profile_id TEXT,
    extraction_status TEXT DEFAULT 'nicht_extrahiert',
    last_extraction_at TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    hash TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    location TEXT,
    url TEXT,
    source TEXT,
    description TEXT,
    score INTEGER DEFAULT 0,
    remote_level TEXT DEFAULT 'unbekannt',
    distance_km REAL,
    salary_info TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_type TEXT,
    salary_estimated INTEGER DEFAULT 0,
    employment_type TEXT DEFAULT 'festanstellung',
    dismiss_reason TEXT,
    is_active INTEGER DEFAULT 1,
    profile_id TEXT,
    found_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    job_hash TEXT REFERENCES jobs(hash) ON DELETE SET NULL,
    profile_id TEXT,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    url TEXT,
    status TEXT DEFAULT 'beworben',
    applied_at TEXT,
    cover_letter_path TEXT,
    cv_path TEXT,
    project_list_path TEXT,
    notes TEXT,
    bewerbungsart TEXT DEFAULT 'mit_dokumenten',
    lebenslauf_variante TEXT DEFAULT 'standard',
    ansprechpartner TEXT DEFAULT '',
    kontakt_email TEXT DEFAULT '',
    portal_name TEXT DEFAULT '',
    rejection_reason TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS application_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    event_date TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS search_criteria (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    reason TEXT,
    created_at TEXT,
    UNIQUE(type, value)
);

CREATE TABLE IF NOT EXISTS background_jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    params TEXT DEFAULT '{}',
    status TEXT DEFAULT 'running',
    progress INTEGER DEFAULT 0,
    message TEXT DEFAULT '',
    result TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS follow_ups (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    scheduled_date TEXT NOT NULL,
    follow_up_type TEXT DEFAULT 'nachfass',
    template TEXT,
    status TEXT DEFAULT 'geplant',
    created_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active, score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_apps_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_app_events ON application_events(application_id);
CREATE INDEX IF NOT EXISTS idx_followups_app ON follow_ups(application_id);
CREATE INDEX IF NOT EXISTS idx_followups_date ON follow_ups(scheduled_date, status);

CREATE TABLE IF NOT EXISTS extraction_history (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL,
    extraction_type TEXT DEFAULT 'auto',
    extracted_fields TEXT DEFAULT '{}',
    conflicts TEXT DEFAULT '[]',
    applied_fields TEXT DEFAULT '{}',
    status TEXT DEFAULT 'ausstehend',
    created_at TEXT,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_extraction_doc ON extraction_history(document_id);
CREATE INDEX IF NOT EXISTS idx_extraction_profile ON extraction_history(profile_id);

CREATE TABLE IF NOT EXISTS user_preferences (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);
"""
