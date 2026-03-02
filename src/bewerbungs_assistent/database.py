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

SCHEMA_VERSION = 2


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

        conn.execute(
            "UPDATE settings SET value=? WHERE key='schema_version'",
            (str(to_ver),)
        )
        conn.commit()

    # === Profile ===

    def get_profile(self) -> Optional[dict]:
        conn = self.connect()
        cur = conn.execute("SELECT * FROM profile LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return None
        profile = dict(row)
        profile["preferences"] = json.loads(profile["preferences"] or "{}")
        # Load positions
        profile["positions"] = self._get_positions()
        profile["education"] = self._get_education()
        profile["skills"] = self._get_skills()
        profile["documents"] = self._get_documents()
        return profile

    def save_profile(self, data: dict) -> str:
        conn = self.connect()
        now = _now()
        cur = conn.execute("SELECT id FROM profile LIMIT 1")
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
            conn.execute("""
                INSERT INTO profile (id, name, email, phone, address, city, plz,
                    country, birthday, nationality, summary, informal_notes,
                    preferences, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    # === Positions (Berufserfahrung) ===

    def _get_positions(self) -> list:
        conn = self.connect()
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
        conn.execute("""
            INSERT INTO positions (id, company, title, location, start_date, end_date,
                is_current, employment_type, industry, description,
                tasks, achievements, technologies, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid, data.get("company"), data.get("title"), data.get("location"),
            data.get("start_date"), data.get("end_date"),
            data.get("is_current", False), data.get("employment_type", "festanstellung"),
            data.get("industry"), data.get("description"),
            data.get("tasks"), data.get("achievements"), data.get("technologies"),
            now
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

    def _get_education(self) -> list:
        conn = self.connect()
        return [dict(r) for r in conn.execute(
            "SELECT * FROM education ORDER BY end_date DESC"
        ).fetchall()]

    def add_education(self, data: dict) -> str:
        conn = self.connect()
        eid = _gen_id()
        conn.execute("""
            INSERT INTO education (id, institution, degree, field_of_study,
                start_date, end_date, grade, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eid, data.get("institution"), data.get("degree"),
            data.get("field_of_study"), data.get("start_date"),
            data.get("end_date"), data.get("grade"), data.get("description")
        ))
        conn.commit()
        return eid

    def delete_education(self, education_id: str):
        conn = self.connect()
        conn.execute("DELETE FROM education WHERE id = ?", (education_id,))
        conn.commit()

    # === Skills ===

    def _get_skills(self) -> list:
        conn = self.connect()
        return [dict(r) for r in conn.execute(
            "SELECT * FROM skills ORDER BY category, level DESC"
        ).fetchall()]

    def add_skill(self, data: dict) -> str:
        conn = self.connect()
        sid = _gen_id()
        conn.execute("""
            INSERT INTO skills (id, name, category, level, years_experience)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sid, data.get("name"), data.get("category", "fachlich"),
            data.get("level", 3), data.get("years_experience")
        ))
        conn.commit()
        return sid

    def delete_skill(self, skill_id: str):
        conn = self.connect()
        conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        conn.commit()

    # === Documents ===

    def _get_documents(self) -> list:
        conn = self.connect()
        return [dict(r) for r in conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ).fetchall()]

    def add_document(self, data: dict) -> str:
        conn = self.connect()
        did = _gen_id()
        conn.execute("""
            INSERT INTO documents (id, filename, filepath, doc_type,
                extracted_text, linked_position_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            did, data.get("filename"), data.get("filepath"),
            data.get("doc_type", "sonstiges"), data.get("extracted_text"),
            data.get("linked_position_id"), _now()
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
    description TEXT
);

CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'fachlich',
    level INTEGER DEFAULT 3,
    years_experience INTEGER
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT,
    doc_type TEXT DEFAULT 'sonstiges',
    extracted_text TEXT,
    linked_position_id TEXT REFERENCES positions(id) ON DELETE SET NULL,
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

CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active, score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_apps_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_app_events ON application_events(application_id);
"""
