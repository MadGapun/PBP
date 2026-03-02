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

SCHEMA_VERSION = 4


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

    def delete_profile(self, profile_id: str):
        """Delete a profile and all its related data."""
        conn = self.connect()
        # Delete related data
        for table in ["positions", "education", "skills", "documents"]:
            conn.execute(f"DELETE FROM {table} WHERE profile_id=?", (profile_id,))
        # Delete projects for positions of this profile
        conn.execute("""
            DELETE FROM projects WHERE position_id IN
            (SELECT id FROM positions WHERE profile_id=?)
        """, (profile_id,))
        conn.execute("DELETE FROM profile WHERE id=?", (profile_id,))
        conn.commit()

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
            INSERT INTO skills (id, name, category, level, years_experience, profile_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sid, data.get("name"), data.get("category", "fachlich"),
            data.get("level", 3), data.get("years_experience"), profile_id
        ))
        conn.commit()
        return sid

    def delete_skill(self, skill_id: str):
        conn = self.connect()
        conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
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

    # === Jobs ===

    def save_jobs(self, jobs: list):
        conn = self.connect()
        now = _now()
        for job in jobs:
            conn.execute("""
                INSERT OR REPLACE INTO jobs (hash, title, company, location, url,
                    source, description, score, remote_level, distance_km,
                    salary_info, employment_type, found_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                job["hash"], job.get("title"), job.get("company"),
                job.get("location"), job.get("url"), job.get("source"),
                job.get("description"), job.get("score", 0),
                job.get("remote_level", "unbekannt"),
                job.get("distance_km"), job.get("salary_info"),
                job.get("employment_type", "festanstellung"),
                job.get("found_at", now), now
            ))
        conn.commit()

    def get_active_jobs(self, filters: Optional[dict] = None) -> list:
        conn = self.connect()
        query = "SELECT * FROM jobs WHERE is_active=1"
        params = []
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
        return [dict(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE is_active=0 ORDER BY updated_at DESC"
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
        if status:
            rows = conn.execute(
                "SELECT * FROM applications WHERE status=? ORDER BY applied_at DESC",
                (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY applied_at DESC"
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
        conn.execute("""
            INSERT INTO applications (id, job_hash, title, company, url, status,
                applied_at, cover_letter_path, cv_path, notes, created_at,
                bewerbungsart, lebenslauf_variante, ansprechpartner,
                kontakt_email, portal_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            aid, data.get("job_hash"), data.get("title"), data.get("company"),
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

    def update_application_status(self, app_id: str, new_status: str, notes: str = ""):
        conn = self.connect()
        now = _now()
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
    profile_id TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT,
    doc_type TEXT DEFAULT 'sonstiges',
    extracted_text TEXT,
    linked_position_id TEXT REFERENCES positions(id) ON DELETE SET NULL,
    profile_id TEXT,
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
    employment_type TEXT DEFAULT 'festanstellung',
    dismiss_reason TEXT,
    is_active INTEGER DEFAULT 1,
    found_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    job_hash TEXT REFERENCES jobs(hash),
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
"""
