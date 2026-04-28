"""SQLite Database Layer for Bewerbungs-Assistent.

Handles all data persistence: profiles, jobs, applications, documents.
Synchronous SQLite with WAL mode and check_same_thread=False for
cross-thread access (MCP thread + Dashboard thread).
"""

import sqlite3
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

logger = logging.getLogger("bewerbungs_assistent.database")

SCHEMA_VERSION = 29


def _gen_id() -> str:
    """Generate a short unique ID (8 hex chars)."""
    return str(uuid.uuid4())[:8]


def _iso_week_key(date_str: str) -> str | None:
    """Konvertiert YYYY-MM-DD oder YYYY-MM-DD HH:MM:SS in ISO-Wochenschluessel
    'YYYY-Www' (#User-Feedback nach beta.32 — SQLite kann kein %V).

    Beispiel: '2026-04-26' -> '2026-W17' (statt '%W' = 16).
    """
    if not date_str:
        return None
    try:
        from datetime import datetime as _dt
        d = _dt.fromisoformat(date_str.replace(" ", "T")[:19])
        iso = d.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    except Exception:
        try:
            from datetime import datetime as _dt
            d = _dt.fromisoformat(date_str[:10])
            iso = d.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        except Exception:
            return None


def _group_by_iso_week(rows) -> list[dict]:
    """Gruppiert sqlite3.Row-Liste {dt, status} nach ISO-Woche.
    Liefert das Format das die get_timeline_stats-Aggregation erwartet:
    [{'period': 'YYYY-Www', 'count': N, 'status': str}, ...].
    """
    grouped = {}
    for r in rows:
        period = _iso_week_key(r["dt"])
        if not period:
            continue
        status = r["status"]
        key = (period, status)
        grouped[key] = grouped.get(key, 0) + 1
    return [
        {"period": p, "count": c, "status": s}
        for (p, s), c in sorted(grouped.items())
    ]


def _group_by_iso_week_count(rows) -> list[dict]:
    """Gruppiert sqlite3.Row-Liste {dt} nach ISO-Woche, mit Count.
    Liefert: [{'period': 'YYYY-Www', 'count': N}, ...].
    """
    counts = {}
    for r in rows:
        period = _iso_week_key(r["dt"])
        if not period:
            continue
        counts[period] = counts.get(period, 0) + 1
    return [{"period": p, "count": c} for p, c in sorted(counts.items())]


def get_data_dir() -> Path:
    """Get the data directory, create if needed.

    Priority: BA_DATA_DIR env var > platform default.
    Windows default: %LOCALAPPDATA%/BewerbungsAssistent/data  (v1.5.0+)
    Linux default:   ~/.bewerbungs-assistent

    v1.5.0 migration: if pbp.db exists in the old flat layout
    (%LOCALAPPDATA%/BewerbungsAssistent/pbp.db) it is moved into the
    new ``data/`` subdirectory automatically.
    """
    env_dir = os.environ.get("BA_DATA_DIR")
    if env_dir:
        data_dir = Path(env_dir)
        # Warn if BA_DATA_DIR points to parent instead of data/ subdirectory (#380)
        if not (data_dir / "pbp.db").exists() and (data_dir / "data" / "pbp.db").exists():
            logger.warning(
                "BA_DATA_DIR zeigt auf '%s', aber pbp.db liegt in data/ Unterordner. "
                "Korrigiere auf '%s/data'.", data_dir, data_dir
            )
            data_dir = data_dir / "data"
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        base_install = base / "BewerbungsAssistent"
        data_dir = base_install / "data"
        # v1.4.x → v1.5.0 migration: move DB from flat layout into data/
        _migrate_flat_layout(base_install, data_dir)
    else:
        data_dir = Path.home() / ".bewerbungs-assistent"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "dokumente").mkdir(exist_ok=True)
    (data_dir / "export").mkdir(exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    return data_dir


def _migrate_flat_layout(base_install: Path, data_dir: Path) -> None:
    """Move v1.4.x flat-layout files into the v1.5.0 data/ subdirectory.

    Creates an automatic backup before moving anything.
    """
    old_db = base_install / "pbp.db"
    new_db = data_dir / "pbp.db"
    if not old_db.exists() or new_db.exists():
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    # Create backup before migration
    create_backup(old_db, data_dir / "backups")
    logger.info("v1.4.x Migration: verschiebe pbp.db nach data/")
    shutil.move(str(old_db), str(new_db))
    # Move WAL/SHM files if present
    for suffix in ("-wal", "-shm"):
        wal = base_install / f"pbp.db{suffix}"
        if wal.exists():
            shutil.move(str(wal), str(data_dir / f"pbp.db{suffix}"))
    # Move subdirectories
    for subdir in ("dokumente", "export", "logs"):
        old_sub = base_install / subdir
        new_sub = data_dir / subdir
        if old_sub.exists() and not new_sub.exists():
            shutil.move(str(old_sub), str(new_sub))
    logger.info("v1.4.x Migration abgeschlossen")


def create_backup(db_path: Path, backup_dir: Path, max_backups: int = 5) -> Optional[Path]:
    """Create a timestamped backup of the database.

    Returns the backup path on success, None if the source DB doesn't exist.
    Rotates old backups to keep at most *max_backups*.
    """
    if not db_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = backup_dir / f"pbp-backup-{timestamp}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    try:
        src.execute("PRAGMA busy_timeout=5000")
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    logger.info("Backup erstellt: %s", backup_path)
    # Rotate: keep only the newest max_backups
    backups = sorted(backup_dir.glob("pbp-backup-*.db"), key=lambda p: p.stat().st_mtime)
    while len(backups) > max_backups:
        oldest = backups.pop(0)
        oldest.unlink()
        logger.info("Altes Backup entfernt: %s", oldest)
    return backup_path


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
            # Pre-populate standard dismiss reasons for fresh databases (#108)
            _standard_reasons = [
                "zu_weit_entfernt", "gehalt_zu_niedrig", "falsches_fachgebiet",
                "zu_junior", "zu_senior", "unpassendes_arbeitsmodell",
                "firma_uninteressant", "zeitarbeit", "befristet", "sonstiges",
            ]
            for label in _standard_reasons:
                try:
                    conn.execute(
                        "INSERT INTO dismiss_reasons (label, is_custom, profile_id, created_at) VALUES (?, 0, '', ?)",
                        (label, _now())
                    )
                except Exception:
                    pass
            # Pre-populate scoring defaults for fresh databases (#169)
            _scoring_defaults = [
                ("stellentyp", "freelance", 3, 0),
                ("stellentyp", "festanstellung", 0, 0),
                ("stellentyp", "zeitarbeit", -5, 0),
                ("stellentyp", "befristet", -2, 0),
                ("stellentyp", "praktikum", -8, 1),
                ("stellentyp", "werkstudent", -8, 1),
                ("remote", "remote", 2, 0),
                ("remote", "hybrid", 1, 0),
                ("remote", "vor_ort", -2, 0),
                ("remote", "unbekannt", 0, 0),
                ("entfernung_fest", "30", 0, 0),
                ("entfernung_fest", "50", -2, 0),
                ("entfernung_fest", "80", -5, 0),
                ("entfernung_fest", "999", -8, 0),
                ("entfernung_freelance", "100", 0, 0),
                ("entfernung_freelance", "200", 0, 0),
                ("entfernung_freelance", "999", -1, 0),
                ("gehalt", "pro_10_prozent", 1, 0),
                ("schwellenwert", "auto_ignore", 0, 0),
            ]
            for dim, sub, val, ign in _scoring_defaults:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO scoring_config "
                        "(profile_id, dimension, sub_key, value, ignore_flag, created_at) "
                        "VALUES ('', ?, ?, ?, ?, ?)",
                        (dim, sub, val, ign, _now())
                    )
                except Exception:
                    pass
            conn.commit()
        else:
            current = int(row["value"])
            if current < SCHEMA_VERSION:
                # Backup before schema migration
                backup_dir = self.db_path.parent / "backups"
                create_backup(self.db_path, backup_dir)
                self._migrate(current, SCHEMA_VERSION)
        # Safety net: ensure is_pinned column exists (may be missing if a prior
        # v10 migration only added profile-scoped tables but not this column).
        try:
            conn.execute("SELECT is_pinned FROM jobs LIMIT 1")
        except Exception:
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN is_pinned INTEGER DEFAULT 0")
                conn.execute(
                    "UPDATE jobs SET is_pinned=1, score=0 WHERE source='manuell' AND score=99"
                )
                conn.commit()
            except Exception:
                pass
        # Safety net: if active_sources / last_search_at were migrated to
        # profile_settings by a prior profile-scoped migration, copy them back
        # to settings so the current code can read them.
        for _key in ("active_sources", "last_search_at"):
            try:
                cur2 = conn.execute("SELECT value FROM settings WHERE key=?", (_key,))
                if cur2.fetchone() is None:
                    ps_row = conn.execute(
                        "SELECT value FROM profile_settings WHERE key=? LIMIT 1",
                        (_key,)
                    ).fetchone()
                    if ps_row:
                        conn.execute(
                            "INSERT INTO settings (key, value) VALUES (?, ?)",
                            (_key, ps_row["value"])
                        )
                        conn.commit()
            except Exception:
                pass  # profile_settings table may not exist
        # Create indexes that depend on migrated columns (safe after migration)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_pinned ON jobs(is_pinned DESC, score DESC)"
        )
        conn.commit()
        # Safety net: if profiles exist but none is active, auto-activate the newest
        active_check = conn.execute("SELECT id FROM profile WHERE is_active=1 LIMIT 1").fetchone()
        if active_check is None:
            orphan = conn.execute(
                "SELECT id FROM profile ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            if orphan:
                conn.execute("UPDATE profile SET is_active=1 WHERE id=?", (orphan["id"],))
                conn.commit()
                logger.warning("Kein aktives Profil gefunden — %s automatisch aktiviert", orphan["id"])
        # #503: Dokument-Pfad-Reparatur nach Verzeichnisstruktur-Aenderungen.
        # Wenn beim Update von v1.4.x → v1.5.x oder durch manuelle Eingriffe
        # absolute Pfade in der DB veraltet sind, suchen wir die Dateien im
        # aktuellen data_dir wieder und aktualisieren die Pfade still im
        # Hintergrund. Vorher musste der User das per Hand SQL-skripten.
        try:
            self._repair_document_paths()
        except Exception as e:
            logger.debug("Pfad-Reparatur uebersprungen: %s", e)
        logger.info("Database initialized at %s", self.db_path)

    def _repair_document_paths(self) -> int:
        """Validiert alle `documents.filepath`-Eintraege und repariert
        veraltete absolute Pfade nach Verzeichnisstruktur-Aenderungen
        (#503).

        Strategie:
            1. Pruefe jeden filepath; wenn die Datei existiert: alles ok.
            2. Wenn nicht: probiere bekannte Fallback-Stellen im aktuellen
               data_dir (data/dokumente/<basename>, dokumente/<basename>,
               data/dokumente/<profile_id>/<basename>).
            3. Bei Treffer: Pfad in der DB still aktualisieren.

        Returns: Anzahl reparierter Pfade.
        """
        conn = self.connect()
        try:
            cur = conn.execute(
                "SELECT id, filepath, profile_id FROM documents "
                "WHERE filepath IS NOT NULL AND filepath != ''"
            )
            rows = cur.fetchall()
        except Exception:
            return 0

        if not rows:
            return 0

        data_dir = self.db_path.parent
        repaired = 0
        broken = 0

        for r in rows:
            doc_id = r["id"]
            old_path = r["filepath"]
            profile_id = r["profile_id"]
            if Path(old_path).exists():
                continue
            broken += 1
            basename = Path(old_path).name
            candidates = [
                data_dir / "dokumente" / basename,
                data_dir / "dokumente" / (profile_id or "") / basename,
                data_dir.parent / "dokumente" / basename,
            ]
            # Auch: wenn der alte Pfad ein .../BewerbungsAssistent/dokumente/...
            # Format hat, dann das data/-Vorhaengen probieren.
            if "BewerbungsAssistent" in old_path and "data" not in old_path:
                fixed = old_path.replace(
                    "BewerbungsAssistent" + os.sep + "dokumente",
                    "BewerbungsAssistent" + os.sep + "data" + os.sep + "dokumente"
                )
                candidates.insert(0, Path(fixed))

            for cand in candidates:
                if cand and cand.exists():
                    conn.execute(
                        "UPDATE documents SET filepath=? WHERE id=?",
                        (str(cand), doc_id)
                    )
                    repaired += 1
                    break

        if repaired:
            conn.commit()
            logger.warning(
                "Dokument-Pfade repariert: %d von %d kaputten Eintraegen "
                "automatisch korrigiert (#503).", repaired, broken
            )
        elif broken:
            logger.info(
                "Dokument-Pfade: %d Eintraege koennen nicht aufgeloest werden "
                "(Datei wurde geloescht oder verschoben).", broken
            )
        return repaired

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

        if from_ver < 10:
            # v10: is_pinned flag on jobs (replaces score=99 hack) + abgelaufen status support
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN is_pinned INTEGER DEFAULT 0")
            except Exception:
                pass  # Already exists
            # Migrate existing score=99 manual entries: set is_pinned=1, recalculate score to 0
            conn.execute(
                "UPDATE jobs SET is_pinned=1, score=0 WHERE source='manuell' AND score=99"
            )
            # Add index for pinned+score sorting
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_pinned ON jobs(is_pinned DESC, score DESC)"
            )
            logger.info("Migration v9->v10: is_pinned on jobs + abgelaufen status")

        if from_ver < 11:
            # v11: profile_id on search_criteria and blacklist for profile isolation
            for col_add in [
                ("search_criteria", "profile_id TEXT NOT NULL DEFAULT ''"),
                ("blacklist", "profile_id TEXT NOT NULL DEFAULT ''"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE {col_add[0]} ADD COLUMN {col_add[1]}")
                except Exception:
                    pass  # Already exists
            # Backfill: assign existing data to active profile
            active = conn.execute("SELECT id FROM profile WHERE is_active=1 LIMIT 1").fetchone()
            if active:
                pid = active["id"]
                conn.execute("UPDATE search_criteria SET profile_id=? WHERE profile_id=''", (pid,))
                conn.execute("UPDATE blacklist SET profile_id=? WHERE profile_id=''", (pid,))
            logger.info("Migration v10->v11: profile_id on search_criteria + blacklist")

        if from_ver < 12:
            # v12: fit_analyse on applications, parent_event_id for threaded notes
            for col_add in [
                ("applications", "fit_analyse TEXT"),
                ("application_events", "parent_event_id INTEGER"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE {col_add[0]} ADD COLUMN {col_add[1]}")
                except Exception:
                    pass  # Already exists
            logger.info("Migration v11->v12: fit_analyse + threaded notes")

        if from_ver < 13:
            # v13: dismiss_reasons table for multi-select + custom reasons (#108, #120)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS dismiss_reasons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    is_custom INTEGER DEFAULT 0,
                    usage_count INTEGER DEFAULT 0,
                    profile_id TEXT,
                    created_at TEXT
                );
            """)
            # Pre-populate with standard reasons
            from datetime import datetime as _dt
            _now_str = _dt.now().isoformat()
            _standard = [
                "zu_weit_entfernt", "gehalt_zu_niedrig", "falsches_fachgebiet",
                "zu_junior", "zu_senior", "unpassendes_arbeitsmodell",
                "firma_uninteressant", "zeitarbeit", "befristet", "sonstiges",
            ]
            for label in _standard:
                try:
                    conn.execute(
                        "INSERT INTO dismiss_reasons (label, is_custom, profile_id, created_at) VALUES (?, 0, '', ?)",
                        (label, _now_str)
                    )
                except Exception:
                    pass
            logger.info("Migration v12->v13: dismiss_reasons table")

        if from_ver < 14:
            # v14: description_snapshot (#124), vermittler/endkunde (#134), activity tracking (#135)
            migrations_v14 = [
                ("applications", "description_snapshot", "TEXT"),
                ("applications", "snapshot_date", "TEXT"),
                ("applications", "vermittler", "TEXT DEFAULT ''"),
                ("applications", "endkunde", "TEXT DEFAULT ''"),
            ]
            for table, col, coltype in migrations_v14:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                except Exception as e:
                    logger.debug("Spalte existiert bereits: %s", e)
            logger.info("Migration v13->v14: description_snapshot, vermittler/endkunde")

        if from_ver < 15:
            # v15: E-Mail-Integration — application_emails, application_meetings, content_hash
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS application_emails (
                    id TEXT PRIMARY KEY,
                    application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
                    profile_id TEXT,
                    filename TEXT NOT NULL,
                    filepath TEXT,
                    subject TEXT,
                    sender TEXT,
                    recipients TEXT,
                    sent_date TEXT,
                    direction TEXT DEFAULT 'eingang',
                    body_text TEXT,
                    body_html TEXT,
                    detected_status TEXT,
                    detected_status_confidence REAL DEFAULT 0.0,
                    match_confidence REAL DEFAULT 0.0,
                    attachments_json TEXT DEFAULT '[]',
                    meeting_extracted INTEGER DEFAULT 0,
                    is_processed INTEGER DEFAULT 0,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS application_meetings (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    email_id TEXT REFERENCES application_emails(id) ON DELETE SET NULL,
                    profile_id TEXT,
                    title TEXT NOT NULL,
                    meeting_date TEXT NOT NULL,
                    meeting_end TEXT,
                    location TEXT,
                    meeting_url TEXT,
                    meeting_type TEXT DEFAULT 'interview',
                    platform TEXT,
                    ics_data TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'geplant',
                    created_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_emails_app ON application_emails(application_id);
                CREATE INDEX IF NOT EXISTS idx_emails_profile ON application_emails(profile_id);
                CREATE INDEX IF NOT EXISTS idx_meetings_app ON application_meetings(application_id);
                CREATE INDEX IF NOT EXISTS idx_meetings_date ON application_meetings(meeting_date, status);
            """)
            # Add content_hash to documents for duplicate detection
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT")
            except Exception:
                pass
            logger.info("Migration v14->v15: application_emails, application_meetings, content_hash")

        if from_ver < 16:
            # v16: employment_type in applications für manuelle Stellenart-Zuordnung (#151)
            try:
                conn.execute("ALTER TABLE applications ADD COLUMN employment_type TEXT")
            except Exception:
                pass
            logger.info("Migration v15->v16: applications.employment_type")

        if from_ver < 17:
            # v17: Geocoding (#167), Scoring-Config (#169), Bewerbungs-Workflow (#170),
            #      Quellenfeld bei Bewerbungen (#173)

            # 1. Geocoding: lat/lon auf jobs Tabelle (#167)
            for col_add in [
                ("jobs", "lat REAL"),
                ("jobs", "lon REAL"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE {col_add[0]} ADD COLUMN {col_add[1]}")
                except Exception:
                    pass

            # 2. Scoring-Config Tabelle (#169)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scoring_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT NOT NULL DEFAULT '',
                    dimension TEXT NOT NULL,
                    sub_key TEXT NOT NULL,
                    value REAL DEFAULT 0,
                    ignore_flag INTEGER DEFAULT 0,
                    created_at TEXT,
                    UNIQUE(profile_id, dimension, sub_key)
                );
                CREATE INDEX IF NOT EXISTS idx_scoring_profile
                    ON scoring_config(profile_id, dimension);
            """)

            # Pre-populate scoring defaults
            _scoring_defaults = [
                # Stellentyp
                ("stellentyp", "freelance", 3, 0),
                ("stellentyp", "festanstellung", 0, 0),
                ("stellentyp", "zeitarbeit", -5, 0),
                ("stellentyp", "befristet", -2, 0),
                ("stellentyp", "praktikum", -8, 1),
                ("stellentyp", "werkstudent", -8, 1),
                # Remote
                ("remote", "remote", 2, 0),
                ("remote", "hybrid", 1, 0),
                ("remote", "vor_ort", -2, 0),
                ("remote", "unbekannt", 0, 0),
                # Entfernung Festanstellung (km-Stufen)
                ("entfernung_fest", "30", 0, 0),
                ("entfernung_fest", "50", -2, 0),
                ("entfernung_fest", "80", -5, 0),
                ("entfernung_fest", "999", -8, 0),
                # Entfernung Freelance (km-Stufen)
                ("entfernung_freelance", "100", 0, 0),
                ("entfernung_freelance", "200", 0, 0),
                ("entfernung_freelance", "999", -1, 0),
                # Gehalt (pro 10% Abweichung)
                ("gehalt", "pro_10_prozent", 1, 0),
                # Schwellenwert
                ("schwellenwert", "auto_ignore", 0, 0),
            ]
            for dim, sub, val, ign in _scoring_defaults:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO scoring_config "
                        "(profile_id, dimension, sub_key, value, ignore_flag, created_at) "
                        "VALUES ('', ?, ?, ?, ?, ?)",
                        (dim, sub, val, ign, _now())
                    )
                except Exception:
                    pass

            # 3. Quellen-Feld bei Bewerbungen (#173)
            for col_add in [
                ("applications", "source TEXT DEFAULT ''"),
                ("applications", "source_secondary TEXT DEFAULT ''"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE {col_add[0]} ADD COLUMN {col_add[1]}")
                except Exception:
                    pass

            # 4. Blacklist bereinigen (#168): dismiss_pattern Einträge migrieren
            # Konvertiere generische dismiss_patterns zu keywords oder lösche sie
            try:
                _generic_patterns = {
                    "zu_junior", "zu_senior", "zu_weit_entfernt", "gehalt_zu_niedrig",
                    "falsches_fachgebiet", "unpassendes_arbeitsmodell", "firma_uninteressant",
                    "zeitarbeit", "befristet", "bereits_beworben", "sonstiges",
                    "duplikat",
                }
                dp_rows = conn.execute(
                    "SELECT id, value FROM blacklist WHERE type='dismiss_pattern'"
                ).fetchall()
                for dp in dp_rows:
                    val = dp["value"].lower().strip()
                    if val in _generic_patterns:
                        # Generic reason — just delete, these belong in dismiss_reasons
                        conn.execute("DELETE FROM blacklist WHERE id=?", (dp["id"],))
                    elif len(val) > 40:
                        # Long free-text entry (e.g. duplicate descriptions) — delete
                        conn.execute("DELETE FROM blacklist WHERE id=?", (dp["id"],))
                    else:
                        # Short custom pattern — convert to keyword
                        conn.execute(
                            "UPDATE blacklist SET type='keyword' WHERE id=?", (dp["id"],)
                        )
            except Exception as e:
                logger.warning("Blacklist migration (dismiss_pattern): %s", e)

            logger.info("Migration v16->v17: Geocoding, Scoring-Config, Quellen, Blacklist-Bereinigung")

        if from_ver < 18:
            # v18: Gehaltsvorstellung pro Bewerbung (#203)
            try:
                conn.execute("ALTER TABLE applications ADD COLUMN gehaltsvorstellung TEXT DEFAULT ''")
            except Exception:
                pass
            logger.info("Migration v17->v18: applications.gehaltsvorstellung (#203)")

        if from_ver < 19:
            # v19: documents.linked_application_id INTEGER→TEXT (#242)
            # SQLite kann keine Spaltentypen aendern → Tabelle neu erstellen
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS documents_new (
                        id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        filepath TEXT,
                        doc_type TEXT DEFAULT 'sonstiges',
                        extracted_text TEXT,
                        linked_position_id TEXT REFERENCES positions(id) ON DELETE SET NULL,
                        linked_application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
                        profile_id TEXT,
                        extraction_status TEXT DEFAULT 'nicht_extrahiert',
                        last_extraction_at TEXT,
                        content_hash TEXT,
                        created_at TEXT
                    )
                """)
                conn.execute("""
                    INSERT OR IGNORE INTO documents_new
                    SELECT id, filename, filepath, doc_type, extracted_text,
                           linked_position_id, CAST(linked_application_id AS TEXT),
                           profile_id, extraction_status, last_extraction_at,
                           content_hash, created_at
                    FROM documents
                """)
                conn.execute("DROP TABLE documents")
                conn.execute("ALTER TABLE documents_new RENAME TO documents")
            except Exception as e:
                logger.warning("Migration v18->v19 documents: %s", e)
            logger.info("Migration v18->v19: documents.linked_application_id TEXT (#242)")

        if from_ver < 20:
            # v20: projects.customer_name + is_confidential (#246)
            try:
                conn.execute("ALTER TABLE projects ADD COLUMN customer_name TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE projects ADD COLUMN is_confidential INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN research_notes TEXT")
            except Exception:
                pass
            logger.info("Migration v19->v20: projects.customer_name, is_confidential (#246); jobs.research_notes (#240)")

        if from_ver < 21:
            # v21: Fix is_active for jobs with existing applications (#382, closes #375)
            try:
                fixed = conn.execute(
                    """UPDATE jobs SET is_active = 0, dismiss_reason = 'bewerbung_erstellt'
                    WHERE hash IN (SELECT job_hash FROM applications WHERE job_hash IS NOT NULL)
                    AND is_active = 1"""
                ).rowcount
                if fixed:
                    logger.info("Migration v20->v21: %d Jobs mit bestehenden Bewerbungen auf is_active=0 gesetzt (#382)", fixed)
            except Exception as e:
                logger.warning("Migration v20->v21: %s", e)
            logger.info("Migration v20->v21: is_active cleanup (#382)")

        if from_ver < 22:
            # v22: Add is_imported flag for distinguishing native vs imported applications (#368)
            try:
                conn.execute("ALTER TABLE applications ADD COLUMN is_imported INTEGER DEFAULT 0")
                logger.info("Migration v21->v22: is_imported Spalte hinzugefuegt (#368)")
            except Exception:
                pass  # Already exists

        if from_ver < 23:
            # v23: Calendar enhancements — nullable application_id, categories,
            # private entries, duration (#394, #417, #418, #419)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS application_meetings_new (
                        id TEXT PRIMARY KEY,
                        application_id TEXT REFERENCES applications(id) ON DELETE CASCADE,
                        email_id TEXT REFERENCES application_emails(id) ON DELETE SET NULL,
                        profile_id TEXT,
                        title TEXT NOT NULL,
                        meeting_date TEXT NOT NULL,
                        meeting_end TEXT,
                        location TEXT,
                        meeting_url TEXT,
                        meeting_type TEXT DEFAULT 'interview',
                        platform TEXT,
                        ics_data TEXT,
                        notes TEXT,
                        status TEXT DEFAULT 'geplant',
                        is_private INTEGER DEFAULT 0,
                        duration_minutes INTEGER,
                        category_id TEXT,
                        created_at TEXT
                    );

                    INSERT OR IGNORE INTO application_meetings_new
                        (id, application_id, email_id, profile_id, title, meeting_date,
                         meeting_end, location, meeting_url, meeting_type, platform,
                         ics_data, notes, status, is_private, duration_minutes,
                         category_id, created_at)
                    SELECT id, application_id, email_id, profile_id, title, meeting_date,
                           meeting_end, location, meeting_url, meeting_type, platform,
                           ics_data, notes, status, 0, NULL, NULL, created_at
                    FROM application_meetings;

                    DROP TABLE IF EXISTS application_meetings;
                    ALTER TABLE application_meetings_new RENAME TO application_meetings;

                    CREATE INDEX IF NOT EXISTS idx_meetings_app ON application_meetings(application_id);
                    CREATE INDEX IF NOT EXISTS idx_meetings_date ON application_meetings(meeting_date, status);

                    CREATE TABLE IF NOT EXISTS meeting_categories (
                        id TEXT PRIMARY KEY,
                        profile_id TEXT,
                        name TEXT NOT NULL,
                        color TEXT DEFAULT '#3b82f6',
                        show_in_stats INTEGER DEFAULT 1,
                        is_system INTEGER DEFAULT 0,
                        created_at TEXT
                    );
                """)
                logger.info("Migration v22->v23: calendar enhancements (#394, #417, #418)")
            except Exception as exc:
                logger.warning("Migration v22->v23 partial: %s", exc)

        if from_ver < 24:
            # v24: Veröffentlichungsdatum für Stellen (#434)
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN veroeffentlicht_am TEXT")
                logger.info("Migration v23->v24: veroeffentlicht_am Spalte hinzugefuegt (#434)")
            except Exception:
                pass  # Already exists

        if from_ver < 25:
            # v25: Projekt-Zeitraeume (#442), Scraper-URL-Flag (#436), Health-Tracking (#432)
            for col, table in [
                ("start_date TEXT", "projects"),
                ("end_date TEXT", "projects"),
                ("is_search_url INTEGER DEFAULT 0", "jobs"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col}")
                except Exception:
                    pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scraper_health (
                    scraper_name TEXT PRIMARY KEY,
                    last_run TEXT,
                    last_success TEXT,
                    last_error TEXT,
                    consecutive_failures INTEGER DEFAULT 0,
                    total_runs INTEGER DEFAULT 0,
                    total_successes INTEGER DEFAULT 0,
                    avg_time_s REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            """)
            logger.info("Migration v24->v25: projects.start_date/end_date (#442), "
                        "jobs.is_search_url (#436), scraper_health (#432)")

        if from_ver < 26:
            # v26: final_salary fuer abgeschlossene Bewerbungen (#460 / v1.5.7)
            try:
                conn.execute("ALTER TABLE applications ADD COLUMN final_salary TEXT DEFAULT ''")
            except Exception:
                pass
            logger.info("Migration v25->v26: applications.final_salary (#460)")

        if from_ver < 27:
            # v27: scraper_health-Wahrheit (#499 / v1.6.0-beta.14):
            # ok+0-Treffer wird als "silent" getrackt, damit stumme Quellen
            # (Indeed, XING & Co. die status=ok mit count=0 melden) erkannt
            # und nach mehreren Stille-Laeufen automatisch deaktiviert werden.
            for col in (
                "last_count INTEGER DEFAULT 0",
                "last_status_detail TEXT",
                "consecutive_silent INTEGER DEFAULT 0",
            ):
                try:
                    conn.execute(f"ALTER TABLE scraper_health ADD COLUMN {col}")
                except Exception:
                    pass
            logger.info("Migration v26->v27: scraper_health.last_count/"
                        "last_status_detail/consecutive_silent (#499)")

        if from_ver < 28:
            # v28: Skill-Datenmodell-Erweiterung (#511 / v1.6.0-beta.22):
            # - start_year/end_year statt nur "seit". end_year=NULL = laeuft noch.
            # - level_current zusaetzlich zu level (= peak). NULL = identisch
            #   mit peak (durchgehend genutzt). Wenn end_year gesetzt,
            #   typischerweise level_current < peak.
            for col in (
                "start_year INTEGER",
                "end_year INTEGER",
                "level_current INTEGER",
            ):
                try:
                    conn.execute(f"ALTER TABLE skills ADD COLUMN {col}")
                except Exception:
                    pass
            # Bestehende Daten migrieren: start_year aus last_used_year-years_experience
            # ableiten (wenn beide vorhanden), sonst keine Aenderung.
            try:
                conn.execute("""
                    UPDATE skills
                    SET start_year = last_used_year - years_experience
                    WHERE start_year IS NULL
                      AND last_used_year IS NOT NULL
                      AND years_experience IS NOT NULL
                      AND years_experience > 0
                """)
            except Exception:
                pass
            logger.info("Migration v27->v28: skills.start_year/end_year/"
                        "level_current (#511)")

        if from_ver < 29:
            # v29 / #530 v1.6.4: applications.has_reached_interview Flag.
            # Vorher zaehlte die Statistik nur den AKTUELLEN Status — Interviews
            # die in 'abgelehnt' oder 'abgelaufen' rutschten verschwanden aus
            # den Zahlen. Das verzerrte Track-Record-Statistiken (User-Issue:
            # statt 7 Interviews wurden nur 1 angezeigt).
            try:
                conn.execute(
                    "ALTER TABLE applications ADD COLUMN has_reached_interview INTEGER DEFAULT 0"
                )
            except Exception:
                pass
            # Backfill aus application_events: alle Bewerbungen die jemals
            # einen 'interview*'-Status hatten kriegen das Flag.
            try:
                conn.execute("""
                    UPDATE applications
                    SET has_reached_interview = 1
                    WHERE id IN (
                        SELECT DISTINCT application_id
                        FROM application_events
                        WHERE status LIKE 'interview%'
                           OR status = 'zweitgespraech'
                           OR status = 'angebot'
                           OR status = 'angenommen'
                    )
                """)
                # Plus: aktueller Status ist Interview-Stufe oder darueber
                conn.execute("""
                    UPDATE applications
                    SET has_reached_interview = 1
                    WHERE status IN ('interview', 'zweitgespraech',
                                     'interview_abgeschlossen',
                                     'angebot', 'angenommen')
                """)
            except Exception as exc:
                logger.warning("Backfill has_reached_interview teilweise fehlgeschlagen: %s", exc)
            logger.info("Migration v28->v29: applications.has_reached_interview (#530)")

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
        exists = conn.execute("SELECT 1 FROM profile WHERE id=?", (profile_id,)).fetchone()
        if not exists:
            return False
        conn.execute("UPDATE profile SET is_active=0")
        conn.execute("UPDATE profile SET is_active=1 WHERE id=?", (profile_id,))
        conn.commit()
        return True

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

            # Delete emails and meetings for this profile
            conn.execute("DELETE FROM application_meetings WHERE profile_id=?", (profile_id,))
            conn.execute("DELETE FROM application_emails WHERE profile_id=?", (profile_id,))

            # Delete all profile-linked data
            for table in ["positions", "education", "skills", "documents",
                           "applications", "jobs", "suggested_job_titles"]:
                conn.execute(f"DELETE FROM {table} WHERE profile_id=?", (profile_id,))

            # Delete search_criteria and blacklist for this profile
            conn.execute("DELETE FROM search_criteria WHERE profile_id=?", (profile_id,))
            conn.execute("DELETE FROM blacklist WHERE profile_id=?", (profile_id,))

            # Delete the profile itself
            cur = conn.execute("DELETE FROM profile WHERE id=?", (profile_id,))
            deleted = cur.rowcount > 0
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys=ON")
        logger.info("Profile %s and all related data deleted", profile_id)
        return deleted

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
            for table in ["application_meetings", "application_emails",
                           "extraction_history", "application_events", "projects",
                           "positions", "education", "skills", "documents",
                           "applications", "jobs", "blacklist", "background_jobs",
                           "user_preferences", "suggested_job_titles",
                           "search_criteria", "follow_ups", "profile"]:
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

    def _scope_job_hash(self, job_hash: Optional[str], profile_id: Optional[str] = None) -> Optional[str]:
        """Return the internal storage hash for one profile."""
        if not job_hash:
            return job_hash
        pid = profile_id or self.get_active_profile_id()
        if not pid:
            return job_hash
        prefix = f"{pid}:"
        if job_hash.startswith(prefix):
            return job_hash
        return f"{prefix}{job_hash}"

    def _public_job_hash(self, job_hash: Optional[str], profile_id: Optional[str] = None) -> Optional[str]:
        """Convert an internal storage hash back to the stable public hash."""
        if not job_hash:
            return job_hash
        pid = profile_id or self.get_active_profile_id()
        if not pid:
            return job_hash
        prefix = f"{pid}:"
        if job_hash.startswith(prefix):
            return job_hash[len(prefix):]
        return job_hash

    def _job_hash_candidates(self, job_hash: Optional[str], profile_id: Optional[str] = None) -> list[str]:
        """Return compatible hashes for scoped and legacy rows."""
        if not job_hash:
            return []
        pid = profile_id or self.get_active_profile_id()
        candidates: list[str] = []
        for candidate in (
            job_hash,
            self._scope_job_hash(job_hash, pid),
            self._public_job_hash(job_hash, pid),
        ):
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        return candidates

    def _find_job_row(self, job_hash: str, profile_id: Optional[str] = None) -> Optional[sqlite3.Row]:
        """Find a job for the requested profile, including legacy unscoped rows."""
        conn = self.connect()
        pid = profile_id or self.get_active_profile_id()
        for candidate in self._job_hash_candidates(job_hash, pid):
            if pid:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE hash=? AND (profile_id=? OR profile_id IS NULL)",
                    (candidate, pid),
                ).fetchone()
            else:
                row = conn.execute("SELECT * FROM jobs WHERE hash=?", (candidate,)).fetchone()
            if row is not None:
                return row
        return None

    def _serialize_job_row(self, row: sqlite3.Row | dict | None) -> Optional[dict]:
        """Return one job row in the public API shape."""
        if row is None:
            return None
        job = dict(row)
        job["hash"] = self._public_job_hash(job.get("hash"), job.get("profile_id"))
        return job

    def _serialize_application_row(self, row: sqlite3.Row | dict | None) -> Optional[dict]:
        """Return one application row in the public API shape."""
        if row is None:
            return None
        app = dict(row)
        app["job_hash"] = self._public_job_hash(app.get("job_hash"), app.get("profile_id"))
        if app.get("fit_analyse"):
            try:
                app["fit_analyse"] = json.loads(app["fit_analyse"])
            except (json.JSONDecodeError, TypeError):
                pass
        return app

    def _preferred_application_source(self, app_source: Optional[str], job_source: Optional[str]) -> str:
        """Return the most accurate source for an application/report row."""
        app_val = (app_source or "").strip()
        job_val = (job_source or "").strip()
        if app_val and app_val.lower() != "manuell":
            return app_val
        if job_val:
            return job_val
        return app_val

    def resolve_job_hash(self, job_hash: str, profile_id: Optional[str] = None) -> Optional[str]:
        """Resolve a public job hash to the stored value for one profile."""
        if not job_hash:
            return None
        row = self._find_job_row(job_hash, profile_id)
        if row is not None:
            return row["hash"]
        return self._scope_job_hash(job_hash, profile_id)

    def get_job(self, job_hash: str, profile_id: Optional[str] = None) -> Optional[dict]:
        """Return one job by public or stored hash for the selected profile."""
        return self._serialize_job_row(self._find_job_row(job_hash, profile_id))

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
                technologies, duration, customer_name, is_confidential,
                sort_order, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid, position_id, data.get("name"), data.get("description"),
            data.get("role"), data.get("situation"), data.get("task"),
            data.get("action"), data.get("result"),
            data.get("technologies"), data.get("duration"),
            data.get("customer_name"), data.get("is_confidential", 0),
            data.get("sort_order", 0),
            data.get("start_date"), data.get("end_date")
        ))
        conn.commit()
        return pid

    def update_project(self, project_id: str, data: dict, profile_id: str = None) -> bool:
        conn = self.connect()
        fields = ["name", "description", "role", "situation", "task",
                  "action", "result", "technologies", "duration",
                  "customer_name", "is_confidential",
                  "start_date", "end_date"]
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if not sets:
            return False
        query = "UPDATE projects SET {sets} WHERE id=?".format(sets=','.join(sets))
        vals.append(project_id)
        if profile_id is not None:
            query += " AND position_id IN (SELECT id FROM positions WHERE profile_id=? OR profile_id IS NULL)"
            vals.append(profile_id)
        cur = conn.execute(query, vals)
        conn.commit()
        return cur.rowcount > 0

    def delete_project(self, project_id: str, profile_id: str = None) -> bool:
        conn = self.connect()
        query = "DELETE FROM projects WHERE id = ?"
        params: list[str] = [project_id]
        if profile_id is not None:
            query += " AND position_id IN (SELECT id FROM positions WHERE profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

    def update_position(self, position_id: str, data: dict, profile_id: str = None) -> bool:
        conn = self.connect()
        fields = ["company", "title", "location", "start_date", "end_date",
                  "is_current", "employment_type", "industry", "description",
                  "tasks", "achievements", "technologies"]
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if not sets:
            return False
        query = f"UPDATE positions SET {','.join(sets)} WHERE id=?"
        vals.append(position_id)
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            vals.append(profile_id)
        cur = conn.execute(query, vals)
        conn.commit()
        return cur.rowcount > 0

    def update_education(self, education_id: str, data: dict, profile_id: str = None) -> bool:
        conn = self.connect()
        fields = ["institution", "degree", "field_of_study", "start_date",
                  "end_date", "grade", "description"]
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if not sets:
            return False
        query = f"UPDATE education SET {','.join(sets)} WHERE id=?"
        vals.append(education_id)
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            vals.append(profile_id)
        cur = conn.execute(query, vals)
        conn.commit()
        return cur.rowcount > 0

    def update_skill(self, skill_id: str, data: dict, profile_id: str = None) -> bool:
        conn = self.connect()
        # #511: start_year, end_year, level_current dazu
        fields = ["name", "category", "level", "years_experience", "last_used_year",
                  "start_year", "end_year", "level_current"]
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if not sets:
            return False
        query = f"UPDATE skills SET {','.join(sets)} WHERE id=?"
        vals.append(skill_id)
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            vals.append(profile_id)
        cur = conn.execute(query, vals)
        conn.commit()
        return cur.rowcount > 0

    def delete_position(self, position_id: str, profile_id: str = None) -> bool:
        conn = self.connect()
        # Projects are deleted automatically via ON DELETE CASCADE
        query = "DELETE FROM positions WHERE id = ?"
        params: list[str] = [position_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

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

    def delete_education(self, education_id: str, profile_id: str = None) -> bool:
        conn = self.connect()
        query = "DELETE FROM education WHERE id = ?"
        params: list[str] = [education_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

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

    @staticmethod
    def _is_garbage_skill(name: str) -> bool:
        """Check if a skill name is garbage from extraction artifacts (#129)."""
        import re
        if not name or len(name) < 2 or len(name) > 100:
            return True
        # Reject obvious markdown/formatting artifacts
        _GARBAGE_PATTERNS = ["---", "===", "***", "|||", "```", "<!--", "-->",
                             "##", "**", "__", "- -", "...", "~~~"]
        if any(p in name for p in _GARBAGE_PATTERNS):
            return True
        # Reject if name is mostly special characters
        alpha_count = sum(1 for c in name if c.isalnum() or c == ' ')
        if alpha_count < len(name) * 0.5:
            return True
        # Reject numbered list items: "1. Something", "2) Something"
        if re.match(r'^\d+[\.\)]\s', name):
            return True
        # Reject strings starting with parentheses: "(DETAILLIERT)", "(optional)"
        if name.startswith("("):
            return True
        # Reject URLs and email addresses
        if "://" in name or "@" in name:
            return True
        # Reject strings with colons (header fragments): "Programmsteuerung: Program Management"
        if ": " in name and len(name) > 30:
            return True
        # Reject sentence fragments: too many spaces = likely a sentence, not a skill
        if name.count(" ") > 5:
            return True
        # Reject ALL-CAPS fragments over 20 chars (header artifacts)
        if name.isupper() and len(name) > 20:
            return True
        # Reject common non-skill words/fragments
        _STOPWORDS = {"enabling", "efficient", "power", "detailliert", "sonstige",
                       "diverse", "verschiedene", "übersicht", "zusammenfassung",
                       "verantwortlich", "zustaendig", "erfahrung"}
        if name.lower().strip() in _STOPWORDS:
            return True
        # Reject names that are just a single digit/number
        if name.strip().isdigit():
            return True
        return False

    @staticmethod
    def _normalize_skill_category(raw: str) -> str:
        """Normalize skill category against a whitelist (#128)."""
        if not raw:
            return "fachlich"
        _CATEGORY_MAP = {
            "fachlich": "fachlich", "fachkenntnisse": "fachlich", "fachkenntnis": "fachlich",
            "fachkompetenz": "fachlich", "engineering": "fachlich",
            "tool": "tool", "tools": "tool", "software": "tool", "systeme": "tool",
            "system": "tool", "anwendungen": "tool",
            "sprache": "sprache", "sprachen": "sprache", "language": "sprache",
            "soft_skill": "soft_skill", "softskill": "soft_skill", "softskills": "soft_skill",
            "soft skill": "soft_skill", "soft skills": "soft_skill", "sozial": "soft_skill",
            "methodisch": "methodisch", "methoden": "methodisch", "methodik": "methodisch",
            "methodenkompetenz": "methodisch",
            "zertifizierung": "zertifizierung", "zertifikat": "zertifizierung",
            "zertifikate": "zertifizierung", "certification": "zertifizierung",
            "fuehrung": "fuehrung", "management": "fuehrung", "leadership": "fuehrung",
        }
        normalized = raw.strip().lower().replace("-", "_")
        return _CATEGORY_MAP.get(normalized, "fachlich")

    def add_skill(self, data: dict) -> str:
        conn = self.connect()
        name = (data.get("name") or "").strip()
        # Strip leading bullet markers from extraction
        import re
        name = re.sub(r'^[\-\*\+•]\s+', '', name).strip()
        # Validate: reject garbage skills (#43, #129)
        if self._is_garbage_skill(name):
            return ""
        sid = _gen_id()
        profile_id = data.get("profile_id") or self.get_active_profile_id()
        # Normalize category (#128)
        category = self._normalize_skill_category(data.get("category", "fachlich"))
        # Deduplicate: skip if same name already exists for this profile
        existing = conn.execute(
            "SELECT id FROM skills WHERE profile_id=? AND LOWER(name)=LOWER(?)",
            (profile_id, name)
        ).fetchone()
        if existing:
            return existing["id"]
        # #511: Neue Felder. Backward-compat: wenn start_year nicht gegeben,
        # aber last_used_year + years_experience da sind, ableiten.
        start_year = data.get("start_year")
        end_year = data.get("end_year")
        level_current = data.get("level_current")
        last_used_year = data.get("last_used_year")
        years_experience = data.get("years_experience")
        if start_year is None and last_used_year and years_experience:
            try:
                start_year = int(last_used_year) - int(years_experience)
            except (TypeError, ValueError):
                start_year = None
        # Wenn end_year nicht gesetzt aber last_used_year, nutzen wir
        # last_used_year als end_year-Hinweis (vorhandene Daten).
        if end_year is None and last_used_year:
            # nur als Hinweis — bleibt offen, wenn Skill aktiv ist
            pass
        conn.execute("""
            INSERT INTO skills (id, name, category, level, years_experience,
                                last_used_year, profile_id,
                                start_year, end_year, level_current)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sid, name, category,
            data.get("level", 3), years_experience,
            last_used_year, profile_id,
            start_year, end_year, level_current
        ))
        conn.commit()
        return sid

    def delete_skill(self, skill_id: str, profile_id: str = None) -> bool:
        conn = self.connect()
        query = "DELETE FROM skills WHERE id = ?"
        params: list[str] = [skill_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

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

    def update_job_title(self, title_id: str, data: dict, profile_id: str = None) -> bool:
        conn = self.connect()
        fields = ["title", "is_active", "confidence"]
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if not sets:
            return False
        query = f"UPDATE suggested_job_titles SET {','.join(sets)} WHERE id=?"
        vals.append(title_id)
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            vals.append(profile_id)
        cur = conn.execute(query, vals)
        conn.commit()
        return cur.rowcount > 0

    def delete_job_title(self, title_id: str, profile_id: str = None) -> bool:
        conn = self.connect()
        query = "DELETE FROM suggested_job_titles WHERE id=?"
        params: list[str] = [title_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

    # === Documents ===

    def _get_documents(self, profile_id: str = None) -> list:
        conn = self.connect()
        if profile_id:
            return [dict(r) for r in conn.execute(
                """SELECT d.*, a.company as app_company, a.title as app_title, a.status as app_status
                   FROM documents d
                   LEFT JOIN applications a ON d.linked_application_id = a.id
                   WHERE d.profile_id=? ORDER BY d.created_at DESC""",
                (profile_id,)
            ).fetchall()]
        return [dict(r) for r in conn.execute(
            """SELECT d.*, a.company as app_company, a.title as app_title, a.status as app_status
               FROM documents d
               LEFT JOIN applications a ON d.linked_application_id = a.id
               ORDER BY d.created_at DESC"""
        ).fetchall()]

    def get_document(self, doc_id: str, profile_id: str = None) -> dict | None:
        """Get a single document, optionally scoped to a profile."""
        conn = self.connect()
        query = "SELECT * FROM documents WHERE id=?"
        params: list[str] = [str(doc_id)]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None

    def add_document(self, data: dict) -> str:
        conn = self.connect()
        did = _gen_id()
        profile_id = data.get("profile_id") or self.get_active_profile_id()
        conn.execute("""
            INSERT INTO documents (id, filename, filepath, doc_type,
                extracted_text, linked_position_id, linked_application_id,
                profile_id, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            did, data.get("filename"), data.get("filepath"),
            data.get("doc_type", "sonstiges"), data.get("extracted_text"),
            data.get("linked_position_id"), data.get("linked_application_id"),
            profile_id,
            data.get("content_hash"), _now()
        ))
        conn.commit()

        # #177: Auto-assign document to matching application
        try:
            filename = data.get("filename", "")
            if filename and not data.get("linked_application_id"):
                self.auto_assign_document(did, filename)
        except Exception as e:
            logger.debug("Auto-assign document failed (non-critical): %s", e)

        return did

    def update_document_type(self, doc_id: str, doc_type: str, profile_id: str = None) -> bool:
        """Update a document type, optionally scoped to a profile."""
        conn = self.connect()
        query = "UPDATE documents SET doc_type=? WHERE id=?"
        params: list[str] = [doc_type, str(doc_id)]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

    def relink_document(self, doc_id: str, application_id: str | None, profile_id: str = None) -> bool:
        """Relink or unlink a document, optionally scoped to a profile."""
        conn = self.connect()
        if not self.get_document(doc_id, profile_id=profile_id):
            return False
        if application_id is not None:
            query = "SELECT 1 FROM applications WHERE id=?"
            params: list[str] = [str(application_id)]
            if profile_id is not None:
                query += " AND (profile_id=? OR profile_id IS NULL)"
                params.append(profile_id)
            if not conn.execute(query, params).fetchone():
                return False
        query = "UPDATE documents SET linked_application_id=? WHERE id=?"
        params = [application_id, str(doc_id)]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

    def delete_document(self, doc_id: str, profile_id: str = None) -> bool:
        conn = self.connect()
        row = self.get_document(doc_id, profile_id=profile_id)
        if not row:
            return False
        if row["filepath"]:
            try:
                Path(row["filepath"]).unlink(missing_ok=True)
            except Exception as e:
                logger.warning("Dokument-Datei konnte nicht gelöscht werden: %s", e)
        query = "DELETE FROM documents WHERE id = ?"
        params: list[str] = [str(doc_id)]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

    def _auto_link_documents(self, application_id: str, company: str):
        """Auto-link unlinked documents whose filename contains the company name."""
        if not company or len(company) < 2:
            return
        conn = self.connect()
        pid = self.get_active_profile_id()
        company_lower = company.lower()
        unlinked = conn.execute(
            "SELECT id, filename FROM documents "
            "WHERE (profile_id=? OR profile_id IS NULL) "
            "AND linked_application_id IS NULL",
            (pid,)
        ).fetchall()
        linked = 0
        for doc in unlinked:
            if company_lower in (doc["filename"] or "").lower():
                conn.execute(
                    "UPDATE documents SET linked_application_id=? WHERE id=?",
                    (application_id, doc["id"]),
                )
                linked += 1
        if linked:
            conn.commit()
            logger.info("Auto-linked %d document(s) to application %s (company: %s)",
                        linked, application_id, company)

    @staticmethod
    def _normalize_umlauts(text: str) -> str:
        """Normalize umlauts for fuzzy matching (#177).

        Handles both directions: ü→ue and ue→ü, ö→oe, ä→ae, ß→ss.
        """
        t = text.lower()
        # Expand umlauts to ASCII
        for uml, repl in [("ü", "ue"), ("ö", "oe"), ("ä", "ae"), ("ß", "ss"),
                          ("Ü", "ue"), ("Ö", "oe"), ("Ä", "ae")]:
            t = t.replace(uml, repl)
        return t

    def auto_assign_document(self, doc_id: str, filename: str) -> dict:
        """Smart auto-assignment of uploaded document to matching application (#177).

        Matching criteria (in order of confidence):
        1. Company name in filename + document type → high confidence
        2. Company name in filename only → medium confidence
        3. Recently created application (within 24h) → low confidence

        Returns dict with match info or None if no match.
        """
        conn = self.connect()
        pid = self.get_active_profile_id()
        if not pid:
            return {"match": None, "confidence": 0}

        fname_lower = (filename or "").lower()
        fname_normalized = self._normalize_umlauts(fname_lower)  # #177

        # Detect document type from filename
        doc_type = "sonstiges"
        type_keywords = {
            "lebenslauf": "lebenslauf", "cv": "lebenslauf", "resume": "lebenslauf",
            "anschreiben": "anschreiben", "cover": "anschreiben", "motivationsschreiben": "anschreiben",
            "projektliste": "projektliste", "referenz": "referenz", "zeugnis": "zeugnis",
        }
        for keyword, dtype in type_keywords.items():
            if keyword in fname_lower:
                doc_type = dtype
                break

        # Get all applications
        apps = conn.execute(
            "SELECT id, title, company, status, created_at FROM applications "
            "WHERE (profile_id=? OR profile_id IS NULL) "
            "ORDER BY created_at DESC",
            (pid,)
        ).fetchall()

        best_match = None
        best_confidence = 0

        for app in apps:
            company = (app["company"] or "").lower()
            if not company or len(company) < 2:
                continue

            # Check company name match in filename (#177: with umlaut normalization)
            # Try full company name and significant parts
            company_parts = [company]
            company_normalized = self._normalize_umlauts(company)
            company_parts_normalized = [company_normalized]
            # Also try individual words > 3 chars (e.g. "Luerssen" from "Luerssen Werft")
            for part in company.split():
                if len(part) > 3:
                    company_parts.append(part.lower())
                    company_parts_normalized.append(self._normalize_umlauts(part.lower()))

            # Match against both original and normalized filenames
            company_match = (
                any(cp in fname_lower for cp in company_parts) or
                any(cp in fname_normalized for cp in company_parts_normalized)
            )

            if company_match and doc_type != "sonstiges":
                # High confidence: company + document type
                confidence = 0.95
            elif company_match:
                # Medium confidence: company only
                confidence = 0.7
            else:
                # Check time proximity (within 24h)
                from datetime import datetime, timedelta
                try:
                    created = datetime.fromisoformat(app["created_at"].replace("Z", "+00:00"))
                    if datetime.now(created.tzinfo or None) - created < timedelta(hours=24):
                        confidence = 0.3
                    else:
                        confidence = 0
                except Exception:
                    confidence = 0

            if confidence > best_confidence:
                best_confidence = confidence
                best_match = dict(app)

        if not best_match:
            return {"match": None, "confidence": 0}

        result = {
            "match": {
                "bewerbung_id": best_match["id"][:8],
                "bewerbung_id_voll": best_match["id"],
                "firma": best_match["company"],
                "titel": best_match["title"],
                "status": best_match["status"],
            },
            "confidence": best_confidence,
            "doc_type": doc_type,
        }

        # Auto-link if confidence is high enough (#219: auch extraction_status setzen)
        if best_confidence >= 0.7:
            conn.execute(
                "UPDATE documents SET linked_application_id=?, "
                "extraction_status='angewendet', last_extraction_at=? WHERE id=?",
                (best_match["id"], _now(), doc_id)
            )
            # Add timeline event
            self.add_application_event(
                best_match["id"], "dokument",
                f"Dokument '{filename}' automatisch verknuepft (Konfidenz: {best_confidence:.0%})"
            )
            conn.commit()
            result["auto_verknuepft"] = True
        else:
            result["auto_verknuepft"] = False
            result["hinweis"] = (
                f"Moeglicher Match mit '{best_match['company']}' "
                f"(Konfidenz: {best_confidence:.0%}). "
                f"Nutze dokument_verknuepfen('{doc_id}', '{best_match['id'][:8]}') "
                "um manuell zu verknuepfen."
            )

        return result

    def link_document_to_application(self, doc_id, application_id: int, profile_id: str = None) -> bool:
        """Link a document to an application and create timeline entry (#176, #219)."""
        conn = self.connect()
        doc_row = self.get_document(str(doc_id), profile_id=profile_id)
        if not doc_row:
            return False
        app_query = "SELECT 1 FROM applications WHERE id=?"
        app_params: list[str] = [str(application_id)]
        if profile_id is not None:
            app_query += " AND (profile_id=? OR profile_id IS NULL)"
            app_params.append(profile_id)
        if not conn.execute(app_query, app_params).fetchone():
            return False
        update_query = (
            "UPDATE documents SET linked_application_id=?, "
            "extraction_status='angewendet', last_extraction_at=? WHERE id=?"
        )
        update_params: list[str] = [application_id, _now(), str(doc_id)]
        if profile_id is not None:
            update_query += " AND (profile_id=? OR profile_id IS NULL)"
            update_params.append(profile_id)
        cur = conn.execute(update_query, update_params)
        if cur.rowcount == 0:
            return False
        # Get filename for timeline entry (#176)
        filename = doc_row["filename"] if doc_row else "Dokument"
        conn.execute("""
            INSERT INTO application_events (application_id, status, event_date, notes)
            VALUES (?, 'dokument', ?, ?)
        """, (str(application_id), _now(), f"Dokument verknuepft: {filename}"))
        conn.commit()
        return True

    def get_documents_for_application(self, application_id: str, profile_id: str = None) -> list:
        """Return all documents linked to an application."""
        conn = self.connect()
        query = (
            "SELECT id, filename, filepath, doc_type, created_at, extraction_status "
            "FROM documents WHERE linked_application_id=?"
        )
        params: list[str] = [application_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        query += " ORDER BY created_at DESC"
        return [dict(r) for r in conn.execute(query, params).fetchall()]

    # === Jobs ===

    def save_jobs(self, jobs: list):
        conn = self.connect()
        now = _now()
        active_pid = self.get_active_profile_id()
        for job in jobs:
            job_pid = job.get("profile_id") or active_pid
            stored_hash = self.resolve_job_hash(job["hash"], job_pid)
            # Preserve existing score/pin state for pinned or manually scored jobs
            new_score = job.get("score", 0)
            new_pinned = 1 if job.get("is_pinned") else 0
            existing = conn.execute(
                "SELECT score, is_pinned FROM jobs WHERE hash=?", (stored_hash,)
            ).fetchone()
            if existing:
                if existing["is_pinned"]:
                    new_pinned = 1
                if existing["score"] and existing["score"] > new_score:
                    new_score = existing["score"]
            conn.execute("""
                INSERT OR REPLACE INTO jobs (hash, title, company, location, url,
                    source, description, score, remote_level, distance_km,
                    salary_info, salary_min, salary_max, salary_type, salary_estimated,
                    employment_type, is_pinned, lat, lon, veroeffentlicht_am,
                    is_search_url, profile_id, found_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                stored_hash, job.get("title"), job.get("company"),
                job.get("location"), job.get("url"), job.get("source"),
                job.get("description"), new_score,
                job.get("remote_level", "unbekannt"),
                job.get("distance_km"), job.get("salary_info"),
                job.get("salary_min"), job.get("salary_max"),
                job.get("salary_type"), job.get("salary_estimated", 0),
                job.get("employment_type", "festanstellung"),
                new_pinned, job.get("lat"), job.get("lon"),
                job.get("veroeffentlicht_am"),
                1 if job.get("is_search_url") else 0,
                job_pid, job.get("found_at", now), now
            ))
        conn.commit()

    def get_active_jobs(self, filters: Optional[dict] = None,
                        exclude_blacklisted: bool = False,
                        exclude_applied: bool = False) -> list:
        """Get active jobs with optional filtering (#118, #121).

        Args:
            filters: dict with source, employment_type, min_score
            exclude_blacklisted: exclude jobs from blacklisted companies
            exclude_applied: exclude jobs that already have an application
        """
        conn = self.connect()
        pid = self.get_active_profile_id()
        query = "SELECT * FROM jobs WHERE is_active=1 AND (profile_id=? OR profile_id IS NULL)"
        params: list = [pid]
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
        query += " ORDER BY is_pinned DESC, score DESC, found_at DESC"
        jobs = [self._serialize_job_row(r) for r in conn.execute(query, params).fetchall()]

        # Blacklist filter (#121): exclude jobs from blacklisted companies
        if exclude_blacklisted:
            bl_entries = self.get_blacklist()
            bl_firms = {e["value"].lower() for e in bl_entries if e.get("type") == "firma"}
            bl_keywords = {e["value"].lower() for e in bl_entries if e.get("type") == "keyword"}
            if bl_firms or bl_keywords:
                filtered = []
                for j in jobs:
                    company = (j.get("company") or "").lower()
                    title = (j.get("title") or "").lower()
                    if company in bl_firms:
                        continue
                    if any(kw in title or kw in company for kw in bl_keywords):
                        continue
                    filtered.append(j)
                jobs = filtered

        # Applied filter (#118): exclude jobs already applied to
        if exclude_applied:
            applied_hashes = {
                r["job_hash"] for r in self.get_applications()
                if r.get("job_hash") and r.get("status") not in ("abgelehnt", "zurueckgezogen", "abgelaufen")
            }
            if applied_hashes:
                jobs = [j for j in jobs if j["hash"] not in applied_hashes]

        return jobs

    def get_dismissed_jobs(self) -> list:
        conn = self.connect()
        pid = self.get_active_profile_id()
        return [self._serialize_job_row(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) ORDER BY updated_at DESC",
            (pid,)
        ).fetchall()]

    def dismiss_job(self, job_hash: str, reason: str):
        conn = self.connect()
        target_hash = self.resolve_job_hash(job_hash)
        if not target_hash:
            return
        conn.execute(
            "UPDATE jobs SET is_active=0, dismiss_reason=?, updated_at=? WHERE hash=?",
            (reason, _now(), target_hash)
        )
        conn.commit()

    def restore_job(self, job_hash: str):
        conn = self.connect()
        target_hash = self.resolve_job_hash(job_hash)
        if not target_hash:
            return
        conn.execute(
            "UPDATE jobs SET is_active=1, dismiss_reason=NULL, updated_at=? WHERE hash=?",
            (_now(), target_hash)
        )
        conn.commit()

    def update_job_score(self, job_hash: str, score: int):
        """Manually update a job's score."""
        conn = self.connect()
        target_hash = self.resolve_job_hash(job_hash)
        if not target_hash:
            return
        conn.execute(
            "UPDATE jobs SET score=?, updated_at=? WHERE hash=?",
            (score, _now(), target_hash)
        )
        conn.commit()

    def toggle_job_pin(self, job_hash: str) -> bool:
        """Toggle is_pinned flag. Returns new pin state."""
        conn = self.connect()
        target_hash = self.resolve_job_hash(job_hash)
        if not target_hash:
            return False
        row = conn.execute("SELECT is_pinned FROM jobs WHERE hash=?", (target_hash,)).fetchone()
        if not row:
            return False
        new_val = 0 if row["is_pinned"] else 1
        conn.execute(
            "UPDATE jobs SET is_pinned=?, updated_at=? WHERE hash=?",
            (new_val, _now(), target_hash)
        )
        conn.commit()
        return bool(new_val)

    # === Applications ===

    # Statuses considered archived (inactive)
    ARCHIVE_STATUSES = ("abgelehnt", "zurueckgezogen", "abgelaufen")

    def get_applications(self, status: Optional[str] = None,
                         include_archived: bool = True,
                         limit: int = 0, offset: int = 0,
                         from_date: Optional[str] = None,
                         to_date: Optional[str] = None,
                         search: Optional[str] = None,
                         sort_by: str = "applied_at",
                         sort_order: str = "desc") -> list:
        conn = self.connect()
        pid = self.get_active_profile_id()
        query = "SELECT * FROM applications WHERE (profile_id=? OR profile_id IS NULL)"
        params: list = [pid]
        if status:
            query += " AND status=?"
            params.append(status)
        elif not include_archived:
            placeholders = ",".join("?" for _ in self.ARCHIVE_STATUSES)
            query += f" AND status NOT IN ({placeholders})"
            params.extend(self.ARCHIVE_STATUSES)
        if from_date:
            query += " AND applied_at >= ?"
            params.append(from_date)
        if to_date:
            query += " AND applied_at <= ?"
            params.append(to_date + " 23:59:59" if len(to_date) == 10 else to_date)
        if search:
            query += " AND (title LIKE ? OR company LIKE ? OR notes LIKE ?)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        # Whitelist allowed sort columns
        allowed_sort = {"applied_at", "title", "company", "status", "created_at", "updated_at"}
        col = sort_by if sort_by in allowed_sort else "applied_at"
        order = "ASC" if sort_order.lower() == "asc" else "DESC"
        query += f" ORDER BY {col} {order}"
        if limit > 0:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        apps = []
        for row in rows:
            app = dict(row)
            app["events"] = [dict(e) for e in conn.execute(
                "SELECT * FROM application_events WHERE application_id=? ORDER BY event_date",
                (row["id"],)
            ).fetchall()]
            # Last note excerpt for list display (#88)
            last_note_row = conn.execute(
                "SELECT notes FROM application_events "
                "WHERE application_id=? AND status='notiz' ORDER BY event_date DESC LIMIT 1",
                (row["id"],)
            ).fetchone()
            app["last_note"] = last_note_row["notes"] if last_note_row else None
            # Document count for list display (#77)
            doc_count_row = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE linked_application_id=?",
                (row["id"],)
            ).fetchone()
            app["document_count"] = doc_count_row[0] if doc_count_row else 0
            # Job metadata for list display (employment_type, source, url fallback)
            if row["job_hash"]:
                job_row = conn.execute(
                    "SELECT employment_type, source, url FROM jobs WHERE hash=? LIMIT 1",
                    (row["job_hash"],)
                ).fetchone()
                if job_row:
                    # Manuell gesetzter Typ hat Vorrang (#151)
                    app["job_employment_type"] = app.get("employment_type") or job_row["employment_type"]
                    app["job_source"] = self._preferred_application_source(
                        app.get("source"), job_row["source"]
                    )
                    if not app.get("url"):
                        app["url"] = job_row["url"]
            else:
                # Manuell angelegte Bewerbung ohne Job-Verknüpfung
                if app.get("employment_type"):
                    app["job_employment_type"] = app["employment_type"]
                if app.get("source"):
                    app["job_source"] = app["source"]
            apps.append(self._serialize_application_row(app))
        return apps

    def count_applications(self, status: Optional[str] = None,
                           include_archived: bool = True,
                           from_date: Optional[str] = None,
                           to_date: Optional[str] = None,
                           search: Optional[str] = None) -> int:
        """Count applications without loading full data."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        query = "SELECT COUNT(*) FROM applications WHERE (profile_id=? OR profile_id IS NULL)"
        params: list = [pid]
        if status:
            query += " AND status=?"
            params.append(status)
        elif not include_archived:
            placeholders = ",".join("?" for _ in self.ARCHIVE_STATUSES)
            query += f" AND status NOT IN ({placeholders})"
            params.extend(self.ARCHIVE_STATUSES)
        if from_date:
            query += " AND applied_at >= ?"
            params.append(from_date)
        if to_date:
            query += " AND applied_at <= ?"
            params.append(to_date + " 23:59:59" if len(to_date) == 10 else to_date)
        if search:
            query += " AND (title LIKE ? OR company LIKE ? OR notes LIKE ?)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        return conn.execute(query, params).fetchone()[0]

    def count_archived_applications(self) -> int:
        """Count archived (abgelehnt/zurückgezogen/abgelaufen) applications."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        placeholders = ",".join("?" for _ in self.ARCHIVE_STATUSES)
        return conn.execute(
            f"SELECT COUNT(*) FROM applications WHERE status IN ({placeholders}) "
            "AND (profile_id=? OR profile_id IS NULL)",
            (*self.ARCHIVE_STATUSES, pid)
        ).fetchone()[0]

    def add_application(self, data: dict) -> str:
        conn = self.connect()
        aid = _gen_id()
        now = _now()
        pid = self.get_active_profile_id()
        stored_job_hash = self.resolve_job_hash(data.get("job_hash"), pid) if data.get("job_hash") else None
        source = data.get("source", "")
        if stored_job_hash and not str(source or "").strip():
            linked_job = self.get_job(stored_job_hash, pid)
            if linked_job:
                source = linked_job.get("source", "") or ""
        conn.execute("""
            INSERT INTO applications (id, job_hash, profile_id, title, company, url, status,
                applied_at, cover_letter_path, cv_path, notes, created_at,
                bewerbungsart, lebenslauf_variante, ansprechpartner,
                kontakt_email, portal_name, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            aid, stored_job_hash, pid, data.get("title"), data.get("company"),
            data.get("url"), data.get("status", "beworben"),
            data.get("applied_at", now), data.get("cover_letter_path"),
            data.get("cv_path"), data.get("notes"), now,
            data.get("bewerbungsart", "mit_dokumenten"),
            data.get("lebenslauf_variante", "standard"),
            data.get("ansprechpartner", ""),
            data.get("kontakt_email", ""),
            data.get("portal_name", ""),
            source,
        ))
        # Add initial event
        conn.execute("""
            INSERT INTO application_events (application_id, status, event_date, notes)
            VALUES (?, ?, ?, ?)
        """, (aid, data.get("status", "beworben"), now, "Bewerbung erstellt"))
        # #530 v1.6.4: has_reached_interview-Flag setzen, falls die Bewerbung
        # bereits mit Interview-Stufen-Status angelegt wird (z.B. via Import).
        initial_status = data.get("status", "beworben")
        if initial_status in ("interview", "zweitgespraech", "interview_abgeschlossen",
                               "angebot", "angenommen"):
            conn.execute(
                "UPDATE applications SET has_reached_interview=1 WHERE id=?",
                (aid,)
            )
        conn.commit()
        # Auto-link documents by company name match
        self._auto_link_documents(aid, data.get("company", ""))
        return aid

    # Terminal-Status: hier werden offene Follow-ups automatisch hinfaellig (#493)
    TERMINAL_STATUSES = ("abgelehnt", "zurueckgezogen", "angenommen", "abgelaufen", "abgesagt")

    def update_application_status(
        self,
        app_id: str,
        new_status: str,
        notes: str = "",
        rejection_reason: str = "",
        profile_id: str = None,
    ) -> bool:
        """Aktualisiert den Status. Seiteneffekte siehe _apply_status_lifecycle()."""
        conn = self.connect()
        now = _now()
        params: list[str] = [new_status]
        if rejection_reason and new_status == "abgelehnt":
            query = "UPDATE applications SET status=?, rejection_reason=?, updated_at=? WHERE id=?"
            params.extend([rejection_reason, now, app_id])
        else:
            query = "UPDATE applications SET status=?, updated_at=? WHERE id=?"
            params.extend([now, app_id])
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        if cur.rowcount == 0:
            conn.commit()
            return False
        conn.execute("""
            INSERT INTO application_events (application_id, status, event_date, notes)
            VALUES (?, ?, ?, ?)
        """, (app_id, new_status, now, notes))
        conn.commit()
        # Lifecycle-Hooks (Event-System, minimal — #497): Follow-ups, Auto-Nachfrage
        self._apply_status_lifecycle(app_id, new_status)
        return True

    def _apply_status_lifecycle(self, app_id: str, new_status: str) -> dict:
        """Zentrale Lifecycle-Hooks nach Statuswechsel (#493, #494, #497).

        Returns dict mit keys:
            dismissed_followups (int), new_followup_id (str|None), new_followup_date (str|None)
        """
        result = {"dismissed_followups": 0, "new_followup_id": None, "new_followup_date": None}
        # #530 v1.6.4: has_reached_interview-Flag setzen sobald die Bewerbung
        # eine Interview-Stufe durchlaufen hat. Bleibt TRUE auch wenn der
        # Status spaeter auf abgelehnt/abgelaufen wechselt — sonst zaehlt die
        # Statistik nur das AKTUELLE Status und verliert historische Interviews.
        if new_status in ("interview", "zweitgespraech", "interview_abgeschlossen",
                           "angebot", "angenommen"):
            try:
                conn = self.connect()
                conn.execute(
                    "UPDATE applications SET has_reached_interview=1 WHERE id=?",
                    (app_id,)
                )
                conn.commit()
            except Exception:
                pass
        # #493: Offene Follow-ups schliessen bei terminalen Status
        if new_status in self.TERMINAL_STATUSES:
            try:
                result["dismissed_followups"] = self.dismiss_open_followups_for_application(
                    app_id, reason=f"Bewerbung auf {new_status} gesetzt"
                )
            except Exception:
                pass
        # #494: Nach Interview alte Follow-ups schliessen + Nachfrage-FU anlegen
        elif new_status == "interview_abgeschlossen":
            try:
                result["dismissed_followups"] = self.dismiss_open_followups_for_application(
                    app_id, reason="Interview abgeschlossen"
                )
            except Exception:
                pass
            raw = self.get_setting("followup_interview_delay_days", 14)
            try:
                delay_days = int(raw) if raw is not None else 14
            except (TypeError, ValueError):
                delay_days = 14
            if delay_days > 0:
                from datetime import datetime, timedelta
                when = (datetime.now() + timedelta(days=delay_days)).date().isoformat()
                try:
                    fid = self.add_follow_up(
                        app_id, when, follow_up_type="nachfass",
                        template=f"Nachfrage nach Interview-Ergebnis (automatisch {delay_days} Tage nach Abschluss)",
                    )
                    result["new_followup_id"] = fid
                    result["new_followup_date"] = when
                except Exception:
                    pass
        return result

    def delete_application(self, app_id: str):
        """Delete an application and all its events."""
        conn = self.connect()
        conn.execute("DELETE FROM application_events WHERE application_id=?", (app_id,))
        conn.execute("DELETE FROM follow_ups WHERE application_id=?", (app_id,))
        conn.execute("DELETE FROM applications WHERE id=?", (app_id,))
        conn.commit()

    def update_application(self, app_id: str, data: dict):
        """Update application fields (#181: employment_type/source/vermittler/endkunde, #448: cover_letter_path/cv_path, #460: final_salary)."""
        conn = self.connect()
        now = _now()
        fields = []
        values = []
        allowed_keys = ("title", "company", "url", "notes", "ansprechpartner",
                        "kontakt_email", "portal_name", "bewerbungsart",
                        "employment_type", "source", "source_secondary",
                        "vermittler", "endkunde", "applied_at",
                        "cover_letter_path", "cv_path",
                        "gehaltsvorstellung", "final_salary")
        for key in allowed_keys:
            if key in data:
                fields.append(f"{key}=?")
                values.append(data[key])
        if not fields:
            return
        fields.append("updated_at=?")
        values.append(now)
        values.append(app_id)
        conn.execute(f"UPDATE applications SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()

    def add_application_note(self, app_id: str, note: str, parent_event_id: int = None):
        """Add a timestamped note to the application timeline."""
        conn = self.connect()
        now = _now()
        conn.execute("""
            INSERT INTO application_events (application_id, status, event_date, notes, parent_event_id)
            VALUES (?, 'notiz', ?, ?, ?)
        """, (app_id, now, note, parent_event_id))
        conn.commit()

    def add_application_event(self, app_id: str, status: str, notes: str = ""):
        """Add a generic event to the application timeline (#136)."""
        conn = self.connect()
        now = _now()
        conn.execute("""
            INSERT INTO application_events (application_id, status, event_date, notes)
            VALUES (?, ?, ?, ?)
        """, (app_id, status, now, notes))
        conn.commit()

    def update_application_event(self, event_id: int, app_id: str, text: str):
        """Update the notes text of an existing event."""
        conn = self.connect()
        conn.execute(
            "UPDATE application_events SET notes=? WHERE id=? AND application_id=?",
            (text, event_id, app_id)
        )
        conn.commit()

    def delete_application_event(self, event_id: int, app_id: str):
        """Delete a single event (only 'notiz' type should be deletable)."""
        conn = self.connect()
        conn.execute(
            "DELETE FROM application_events WHERE id=? AND application_id=? AND status='notiz'",
            (event_id, app_id)
        )
        conn.commit()

    def get_application(self, app_id: str, profile_id: str = None) -> dict | None:
        """Get a single application with events."""
        conn = self.connect()
        query = "SELECT * FROM applications WHERE id=?"
        params: list[str] = [app_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        app = dict(row)
        app["events"] = [dict(e) for e in conn.execute(
            "SELECT * FROM application_events WHERE application_id=? ORDER BY event_date",
            (app_id,)
        ).fetchall()]
        # Also load linked job description if available
        if app.get("job_hash"):
            job = conn.execute("SELECT description, url FROM jobs WHERE hash=?",
                               (app["job_hash"],)).fetchone()
            if job:
                app["stellenbeschreibung"] = dict(job).get("description", "")
                if not app.get("url"):
                    app["url"] = dict(job).get("url", "")
        return self._serialize_application_row(app)

    # === Search Criteria ===

    def get_search_criteria(self) -> dict:
        pid = self.get_active_profile_id()
        conn = self.connect()
        if pid:
            cur = conn.execute("SELECT * FROM search_criteria WHERE profile_id=?", (pid,))
        else:
            cur = conn.execute("SELECT * FROM search_criteria")
        rows = cur.fetchall()
        criteria = {}
        for row in rows:
            criteria[row["key"]] = json.loads(row["value"])
        return criteria

    def set_search_criteria(self, key: str, value):
        pid = self.get_active_profile_id() or ""
        conn = self.connect()
        conn.execute("""
            INSERT OR REPLACE INTO search_criteria (profile_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
        """, (pid, key, json.dumps(value, ensure_ascii=False), _now()))
        conn.commit()

    # === Blacklist ===

    def add_to_blacklist(self, entry_type: str, value: str, reason: str = ""):
        # #168: Nur noch firma und keyword erlaubt
        if entry_type not in ("firma", "keyword"):
            raise ValueError(f"Ungültiger Blacklist-Typ '{entry_type}'. Nur 'firma' oder 'keyword' erlaubt.")
        pid = self.get_active_profile_id() or ""
        conn = self.connect()
        conn.execute("""
            INSERT OR IGNORE INTO blacklist (profile_id, type, value, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (pid, entry_type, value, reason, _now()))
        conn.commit()

    # --- Scraper Health (#432) ---

    # Schwelle, ab der eine stumme Quelle (status=ok+count=0) automatisch
    # deaktiviert wird (#499 / v1.6.0-beta.14).
    SILENT_AUTO_DEACTIVATE_THRESHOLD = 5

    def update_scraper_health(self, name: str, status: str, count: int = 0,
                              time_s: float = 0, detail: str = None) -> dict:
        """Persist per-scraper health after each search run.

        Returns a dict mit Status-Klassifikation (#499):
        - state: "ok" | "silent" | "fail"
        - auto_deactivated: True wenn consecutive_silent die Schwelle erreicht
          und die Quelle deshalb deaktiviert wurde
        """
        # status=ok mit count=0 => "stumme" Quelle (z.B. Indeed/XING melden
        # ok ohne Treffer). Wir tracken das als eigenen Zustand, damit die
        # Quelle nicht ewig faelschlich als "gesund" gilt.
        if status == "ok" and count <= 0:
            state = "silent"
        elif status == "ok":
            state = "ok"
        else:
            state = "fail"

        # Heuristik: ok + sehr kurze Laufzeit ist verdaechtig (Quelle hat
        # vermutlich gar nicht angefragt, sondern ist sofort durchgefallen).
        status_detail = detail
        if state == "silent":
            if time_s > 0 and time_s < 2:
                status_detail = status_detail or "verdaechtig schnell"
            else:
                status_detail = status_detail or "silent"

        conn = self.connect()
        now = _now()
        existing = conn.execute(
            "SELECT * FROM scraper_health WHERE scraper_name=?", (name,)
        ).fetchone()
        auto_deactivated = False
        if existing:
            total_runs = existing["total_runs"] + 1
            total_successes = existing["total_successes"] + (1 if state == "ok" else 0)
            avg_time = (existing["avg_time_s"] * existing["total_runs"] + time_s) / total_runs
            prev_silent = existing["consecutive_silent"] if "consecutive_silent" in existing.keys() else 0
            if state == "ok":
                conn.execute("""
                    UPDATE scraper_health SET last_run=?, last_success=?,
                        consecutive_failures=0, total_runs=?, total_successes=?,
                        avg_time_s=?, last_count=?, last_status_detail=?,
                        consecutive_silent=0 WHERE scraper_name=?
                """, (now, now, total_runs, total_successes, avg_time,
                      count, None, name))
            elif state == "silent":
                consec_silent = prev_silent + 1
                conn.execute("""
                    UPDATE scraper_health SET last_run=?,
                        consecutive_failures=0, total_runs=?, total_successes=?,
                        avg_time_s=?, last_count=?, last_status_detail=?,
                        consecutive_silent=? WHERE scraper_name=?
                """, (now, total_runs, total_successes, avg_time,
                      count, status_detail, consec_silent, name))
                if consec_silent >= self.SILENT_AUTO_DEACTIVATE_THRESHOLD \
                        and existing["is_active"]:
                    conn.execute(
                        "UPDATE scraper_health SET is_active=0 WHERE scraper_name=?",
                        (name,)
                    )
                    auto_deactivated = True
                    logger.warning(
                        "Scraper %s nach %d stillen Laeufen automatisch deaktiviert (#499)",
                        name, consec_silent
                    )
            else:
                consec = existing["consecutive_failures"] + 1
                conn.execute("""
                    UPDATE scraper_health SET last_run=?, last_error=?,
                        consecutive_failures=?, total_runs=?, total_successes=?,
                        avg_time_s=?, last_count=?, last_status_detail=?
                        WHERE scraper_name=?
                """, (now, status_detail or status, consec, total_runs,
                      total_successes, avg_time, count, status_detail, name))
        else:
            conn.execute("""
                INSERT INTO scraper_health (scraper_name, last_run, last_success,
                    last_error, consecutive_failures, total_runs, total_successes,
                    avg_time_s, is_active, last_count, last_status_detail,
                    consecutive_silent)
                VALUES (?, ?, ?, ?, ?, 1, ?, 0, 1, ?, ?, ?)
            """, (name, now,
                  now if state == "ok" else None,
                  None if state != "fail" else (status_detail or status),
                  0 if state != "fail" else 1,
                  1 if state == "ok" else 0,
                  count,
                  status_detail,
                  1 if state == "silent" else 0))
        conn.commit()
        return {
            "state": state,
            "auto_deactivated": auto_deactivated,
            "detail": status_detail,
        }

    def get_scraper_health(self) -> list:
        conn = self.connect()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM scraper_health ORDER BY scraper_name"
            ).fetchall()]
        except Exception:
            return []

    def toggle_scraper(self, name: str, active: bool):
        conn = self.connect()
        conn.execute(
            "UPDATE scraper_health SET is_active=?, consecutive_failures=0, "
            "consecutive_silent=0 WHERE scraper_name=?",
            (1 if active else 0, name)
        )
        conn.commit()

    def get_blacklist(self) -> list:
        pid = self.get_active_profile_id()
        conn = self.connect()
        if pid:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM blacklist WHERE profile_id=? ORDER BY type, value", (pid,)
            ).fetchall()]
        return [dict(r) for r in conn.execute(
            "SELECT * FROM blacklist ORDER BY type, value"
        ).fetchall()]

    def remove_blacklist_entry(self, entry_id: int) -> bool:
        pid = self.get_active_profile_id()
        conn = self.connect()
        if pid:
            cur = conn.execute(
                "DELETE FROM blacklist WHERE id=? AND profile_id=?", (entry_id, pid)
            )
        else:
            cur = conn.execute("DELETE FROM blacklist WHERE id=?", (entry_id,))
        conn.commit()
        return cur.rowcount > 0

    # === Dismiss Reasons (#108, #120) ===

    def get_dismiss_reasons(self) -> list:
        """Get all dismiss reasons (standard + custom)."""
        conn = self.connect()
        pid = self.get_active_profile_id() or ""
        return [dict(r) for r in conn.execute(
            "SELECT * FROM dismiss_reasons WHERE profile_id='' OR profile_id=? ORDER BY usage_count DESC, label",
            (pid,)
        ).fetchall()]

    def add_dismiss_reason(self, label: str) -> int:
        """Add a custom dismiss reason. Returns the new id."""
        pid = self.get_active_profile_id() or ""
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO dismiss_reasons (label, is_custom, profile_id, created_at) VALUES (?, 1, ?, ?)",
            (label, pid, _now())
        )
        conn.commit()
        return cur.lastrowid

    def increment_dismiss_reason_usage(self, labels: list):
        """Increment usage_count for the given reason labels.

        If a label doesn't exist yet (custom reason from free-text input),
        auto-create it so it appears as a selectable option next time (#126).
        """
        conn = self.connect()
        pid = self.get_active_profile_id() or ""
        for label in labels:
            cur = conn.execute(
                "UPDATE dismiss_reasons SET usage_count = usage_count + 1 WHERE label=?",
                (label,)
            )
            if cur.rowcount == 0:
                # New custom reason — insert so it's available next time
                try:
                    conn.execute(
                        "INSERT INTO dismiss_reasons (label, is_custom, profile_id, usage_count, created_at) "
                        "VALUES (?, 1, ?, 1, ?)",
                        (label, pid, _now())
                    )
                except Exception:
                    pass  # Duplicate or constraint violation — ignore
        conn.commit()

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

    def get_last_finished_background_job(self, job_type: str) -> Optional[dict]:
        """Return the most recently finished background job of the given type (#487)."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM background_jobs WHERE job_type=? AND status IN ('fertig','fehler') "
            "ORDER BY updated_at DESC LIMIT 1",
            (job_type,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["params"] = json.loads(d["params"] or "{}")
        d["result"] = json.loads(d["result"] or "null")
        return d

    def get_running_background_job(self, job_type: Optional[str] = None) -> Optional[dict]:
        """Return the most recent running/pending background job of the given type."""
        conn = self.connect()
        if job_type:
            row = conn.execute(
                "SELECT * FROM background_jobs WHERE job_type=? AND status IN ('running','pending') "
                "ORDER BY created_at DESC LIMIT 1",
                (job_type,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM background_jobs WHERE status IN ('running','pending') "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["params"] = json.loads(d["params"] or "{}")
        d["result"] = json.loads(d["result"] or "null")
        return d

    # === Statistics ===

    def get_statistics(self) -> dict:
        conn = self.connect()
        pid = self.get_active_profile_id()
        stats = {}
        # Applications by status (profile-filtered)
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM applications "
            "WHERE (profile_id=? OR profile_id IS NULL) GROUP BY status",
            (pid,)
        ).fetchall()
        stats["applications_by_status"] = {r["status"]: r["cnt"] for r in rows}
        stats["total_applications"] = sum(r["cnt"] for r in rows)
        # Jobs
        stats["active_jobs"] = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_active=1 AND (profile_id=? OR profile_id IS NULL)",
            (pid,)
        ).fetchone()[0]
        stats["dismissed_jobs"] = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL)",
            (pid,)
        ).fetchone()[0]
        stats["pinned_jobs"] = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_pinned=1 AND is_active=1 AND (profile_id=? OR profile_id IS NULL)",
            (pid,)
        ).fetchone()[0]
        # Score statistics (excluding pinned/manual to avoid skew) —
        # #471 follow-up: auch dismissed Jobs zaehlen, sonst weicht der
        # "Spitzen-Score" von der Unapplied-Liste ab, die dismissed inkludiert.
        score_row = conn.execute(
            "SELECT AVG(score) as avg_score, MAX(score) as max_score, COUNT(*) as cnt "
            "FROM jobs WHERE is_pinned=0 AND score>0 "
            "AND (profile_id=? OR profile_id IS NULL)",
            (pid,)
        ).fetchone()
        if score_row and score_row["cnt"]:
            stats["avg_score"] = _safe_float(score_row["avg_score"], 0)
            if stats["avg_score"]:
                stats["avg_score"] = round(stats["avg_score"], 1)
            stats["max_score"] = _safe_float(score_row["max_score"], 0)
            stats["scored_jobs"] = score_row["cnt"]
        # Conversion rate — exclude in_vorbereitung from basis (#198)
        in_vorb = stats["applications_by_status"].get("in_vorbereitung", 0)
        submitted = stats["total_applications"] - in_vorb
        if submitted > 0:
            # #530 v1.6.4: has_reached_interview-Flag bevorzugen — zaehlt
            # Bewerbungen die JEMALS eine Interview-Stufe hatten, auch wenn
            # sie spaeter auf abgelehnt/abgelaufen rutschten. Vorher zaehlten
            # nur aktuelle Status, was Track-Record-Statistik verzerrte.
            interviews_total_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM applications "
                "WHERE has_reached_interview=1 AND status != 'in_vorbereitung' "
                "AND (profile_id=? OR profile_id IS NULL)",
                (pid,)
            ).fetchone()
            interviews = interviews_total_row["cnt"] if interviews_total_row else 0
            stats["interview_count_total"] = interviews
            stats["interview_count_current"] = (
                stats["applications_by_status"].get("interview", 0)
                + stats["applications_by_status"].get("zweitgespraech", 0)
                + stats["applications_by_status"].get("interview_abgeschlossen", 0)
            )
            offers = (stats["applications_by_status"].get("angebot", 0)
                      + stats["applications_by_status"].get("angenommen", 0))
            stats["interview_rate"] = round(interviews / submitted * 100, 1)
            stats["offer_rate"] = round(offers / submitted * 100, 1)
        # Sources breakdown — count ALL jobs (active + dismissed) for historical accuracy (#125)
        source_rows = conn.execute(
            "SELECT source, COUNT(*) as cnt, "
            "SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active_cnt "
            "FROM jobs WHERE (profile_id=? OR profile_id IS NULL) "
            "GROUP BY source ORDER BY cnt DESC",
            (pid,)
        ).fetchall()
        stats["jobs_by_source"] = {r["source"]: r["cnt"] for r in source_rows}
        stats["active_jobs_by_source"] = {r["source"]: r["active_cnt"] for r in source_rows}
        return stats

    def get_timeline_stats(self, interval: str = "month", time_range: str = "") -> dict:
        """Get application counts grouped by time interval for charts (#125).

        ``interval`` controls the grouping: day / week / month / quarter / year.
        ``time_range`` optionally overrides the default time window:
            30d, 90d, 6m, 12m, or empty for defaults.
        """
        conn = self.connect()
        pid = self.get_active_profile_id()

        original_interval = interval
        # "all" shows everything grouped monthly
        if interval == "all":
            interval = "month"
        # #308: "day" für Tagesansicht, %W → konsistente ISO-Woche
        fmt_map = {"day": "%Y-%m-%d", "week": "%Y-W%W", "month": "%Y-%m", "year": "%Y"}
        fmt = fmt_map.get(interval, "%Y-%m")

        # Time window limits (#125) — only for non-"all" views
        # Note: SQLite does NOT support 'weeks' modifier — use days instead
        _default_limits = {
            "day": "date('now', '-30 days')",
            "week": "date('now', '-84 days')",
            "month": "date('now', '-12 months')",
            "quarter": "date('now', '-24 months')",
        }
        # Parse optional time_range override
        _range_map = {
            "30d": "date('now', '-30 days')",
            "90d": "date('now', '-90 days')",
            "6m": "date('now', '-6 months')",
            "12m": "date('now', '-12 months')",
        }
        _time_limits = _default_limits.copy()
        if time_range and time_range in _range_map:
            # Override the limit for the current interval
            _time_limits[interval] = _range_map[time_range]
        # #357: Use COALESCE(applied_at, created_at) so imported applications
        # (which may lack applied_at) still appear in the timeline.
        _effective_date = "COALESCE(NULLIF(applied_at, ''), created_at)"
        time_filter = ""
        if original_interval != "all" and interval in _time_limits:
            time_filter = f"AND {_effective_date} >= {_time_limits[interval]}"
        time_filter_jobs = time_filter.replace(_effective_date, "found_at")

        # Normalize date: strip timezone suffix and skip empty strings (#197)
        _date_col = f"substr(replace({_effective_date}, 'T', ' '), 1, 19)"
        _date_filter = f"AND {_effective_date} IS NOT NULL"

        if interval == "quarter":
            rows = conn.execute(f"""
                SELECT
                    CAST(strftime('%Y', {_date_col}) AS TEXT) || '-Q' ||
                    CAST((CAST(strftime('%m', {_date_col}) AS INTEGER) - 1) / 3 + 1 AS TEXT)
                    as period,
                    COUNT(*) as count, status
                FROM applications
                WHERE (profile_id=? OR profile_id IS NULL)
                {_date_filter} {time_filter}
                GROUP BY period, status ORDER BY period
            """, (pid,)).fetchall()
        elif interval == "week":
            # beta.33: ISO-Wochengruppierung in Python (SQLite kennt kein %V).
            raw = conn.execute(f"""
                SELECT {_date_col} as dt, status
                FROM applications
                WHERE (profile_id=? OR profile_id IS NULL)
                {_date_filter} {time_filter}
            """, (pid,)).fetchall()
            rows = _group_by_iso_week(raw)
        else:
            rows = conn.execute(f"""
                SELECT strftime('{fmt}', {_date_col}) as period,
                       COUNT(*) as count, status
                FROM applications
                WHERE (profile_id=? OR profile_id IS NULL)
                {_date_filter} {time_filter}
                GROUP BY period, status ORDER BY period
            """, (pid,)).fetchall()

        periods = {}
        for r in rows:
            p = r["period"]
            if not p:  # skip NULL periods from empty dates (#197)
                continue
            if p not in periods:
                periods[p] = {"total": 0, "by_status": {}}
            periods[p]["total"] += r["count"]
            periods[p]["by_status"][r["status"]] = r["count"]

        # Jobs found — count ALL jobs (active + dismissed) for historical accuracy (#125)
        if interval == "quarter":
            job_rows = conn.execute(f"""
                SELECT
                    CAST(strftime('%Y', found_at) AS TEXT) || '-Q' ||
                    CAST((CAST(strftime('%m', found_at) AS INTEGER) - 1) / 3 + 1 AS TEXT)
                    as period, COUNT(*) as count
                FROM jobs WHERE found_at IS NOT NULL
                AND (profile_id=? OR profile_id IS NULL)
                {time_filter_jobs}
                GROUP BY period ORDER BY period
            """, (pid,)).fetchall()
        elif interval == "week":
            # beta.33: ISO-Wochengruppierung in Python
            raw_jobs = conn.execute(f"""
                SELECT found_at as dt
                FROM jobs WHERE found_at IS NOT NULL
                AND (profile_id=? OR profile_id IS NULL)
                {time_filter_jobs}
            """, (pid,)).fetchall()
            job_rows = _group_by_iso_week_count(raw_jobs)
        else:
            job_rows = conn.execute(f"""
                SELECT strftime('{fmt}', found_at) as period, COUNT(*) as count
                FROM jobs WHERE found_at IS NOT NULL
                AND (profile_id=? OR profile_id IS NULL)
                {time_filter_jobs}
                GROUP BY period ORDER BY period
            """, (pid,)).fetchall()

        # #308: Fill gaps for week/day intervals so charts don't skip empty periods
        all_periods = set(periods.keys()) | {r["period"] for r in job_rows if r["period"]}
        if interval in ("week", "day") and all_periods:
            from datetime import datetime as _dt, timedelta
            sorted_p = sorted(all_periods)
            if interval == "day":
                try:
                    start = _dt.strptime(sorted_p[0], "%Y-%m-%d")
                    end = _dt.strptime(sorted_p[-1], "%Y-%m-%d")
                    d = start
                    while d <= end:
                        key = d.strftime("%Y-%m-%d")
                        if key not in periods:
                            periods[key] = {"total": 0, "by_status": {}}
                        d += timedelta(days=1)
                except ValueError:
                    pass
            elif interval == "week":
                try:
                    # beta.33: ISO-Woche fuer Gap-Fill
                    def _iso_week_to_date(w):
                        y, wn = w.split("-W")
                        return _dt.strptime(f"{y}-W{wn}-1", "%G-W%V-%u")
                    start = _iso_week_to_date(sorted_p[0])
                    end_period = sorted_p[-1]
                    # Auch die laufende ISO-Woche aufnehmen (User-Wunsch:
                    # nicht filtern, sichtbar lassen).
                    # Beta.34: lokales _dt nutzen (Module-Level _now()
                    # liefert String, nicht datetime).
                    iso_now = _dt.now().isocalendar()
                    cur_key = f"{iso_now.year}-W{iso_now.week:02d}"
                    if cur_key > end_period:
                        end_period = cur_key
                    end = _iso_week_to_date(end_period)
                    d = start
                    while d <= end:
                        iso = d.isocalendar()
                        key = f"{iso.year}-W{iso.week:02d}"
                        if key not in periods:
                            periods[key] = {"total": 0, "by_status": {}}
                        d += timedelta(weeks=1)
                except (ValueError, AttributeError):
                    pass

        # #358: Determine current (incomplete) period so frontend can mark it
        from datetime import datetime as _dt
        _now = _dt.now()
        if interval == "quarter":
            current_period = f"{_now.year}-Q{(_now.month - 1) // 3 + 1}"
        elif interval == "day":
            current_period = _now.strftime("%Y-%m-%d")
        elif interval == "week":
            # beta.33 / User-Feedback: ISO-Kalenderwoche statt %W,
            # damit die Anzeige mit der Woche im User-Kalender uebereinstimmt
            # (Beispiel 26.04.2026: %W = 16, ISO = 17 — User sieht Letzteres).
            iso = _now.isocalendar()
            current_period = f"{iso.year}-W{iso.week:02d}"
        elif interval == "year":
            current_period = _now.strftime("%Y")
        else:
            current_period = _now.strftime("%Y-%m")

        return {
            "interval": interval,
            "periods": sorted(periods.keys()),
            "applications": {p: d["total"] for p, d in sorted(periods.items())},
            "by_status": {p: d["by_status"] for p, d in sorted(periods.items())},
            "jobs_found": {r["period"]: r["count"] for r in job_rows if r["period"]},
            "current_period": current_period,
        }

    def get_score_stats(self) -> dict:
        """Get score distribution and source comparison data for charts (#125)."""
        conn = self.connect()
        pid = self.get_active_profile_id()

        # Score distribution using brackets — ALL jobs (active + dismissed) for full picture (#178)
        dist_rows = conn.execute("""
            SELECT
                CASE
                    WHEN score = 0 THEN '0'
                    WHEN score BETWEEN 1 AND 3 THEN '1-3'
                    WHEN score BETWEEN 4 AND 6 THEN '4-6'
                    WHEN score BETWEEN 7 AND 9 THEN '7-9'
                    ELSE '10+'
                END as bracket, COUNT(*) as cnt
            FROM jobs WHERE is_pinned=0
            AND (profile_id=? OR profile_id IS NULL)
            GROUP BY bracket ORDER BY bracket
        """, (pid,)).fetchall()

        # Separate: nur aktive Jobs für die "aktive Score-Verteilung"
        active_dist_rows = conn.execute("""
            SELECT
                CASE
                    WHEN score = 0 THEN '0'
                    WHEN score BETWEEN 1 AND 3 THEN '1-3'
                    WHEN score BETWEEN 4 AND 6 THEN '4-6'
                    WHEN score BETWEEN 7 AND 9 THEN '7-9'
                    ELSE '10+'
                END as bracket, COUNT(*) as cnt
            FROM jobs WHERE is_pinned=0 AND is_active=1
            AND (profile_id=? OR profile_id IS NULL)
            GROUP BY bracket ORDER BY bracket
        """, (pid,)).fetchall()

        # Source stats — ALL jobs (active + dismissed) for historical view (#125)
        source_rows = conn.execute("""
            SELECT source, COUNT(*) as cnt,
                   ROUND(AVG(CASE WHEN is_pinned=0 AND score>0 THEN score END), 1) as avg_score,
                   MAX(CASE WHEN is_pinned=0 THEN score END) as max_score
            FROM jobs WHERE (profile_id=? OR profile_id IS NULL)
            GROUP BY source ORDER BY cnt DESC
        """, (pid,)).fetchall()

        # Application sources (#87, #185) – prefer applications.source over jobs.source
        app_sources = {}
        for app in self.get_applications(include_archived=True):
            source = self._preferred_application_source(
                app.get("source"), app.get("job_source")
            ) or "import"
            app_sources[source] = app_sources.get(source, 0) + 1

        return {
            "score_distribution": {r["bracket"]: r["cnt"] for r in dist_rows},
            "score_distribution_aktiv": {r["bracket"]: r["cnt"] for r in active_dist_rows},
            "sources": [
                {"name": r["source"] or "unbekannt", "count": r["cnt"],
                 "avg_score": _safe_float(r["avg_score"]),
                 "max_score": _safe_float(r["max_score"])}
                for r in source_rows
            ],
            "application_sources": [
                {"name": name, "count": count}
                for name, count in sorted(app_sources.items(), key=lambda item: (-item[1], item[0]))
            ],
        }

    def get_zombie_applications(self, days_threshold: int = 60) -> list:
        """Detect zombie applications — stuck in early status with no recent activity (#130).

        Returns applications where:
        - Status is 'offen', 'beworben', or 'eingangsbestaetigung'
        - Last update was more than `days_threshold` days ago
        - No pending follow-up scheduled
        """
        conn = self.connect()
        pid = self.get_active_profile_id()
        rows = conn.execute(f"""
            SELECT a.id, a.title, a.company, a.status, a.applied_at, a.updated_at,
                   j.score, j.source as job_source,
                   CAST(julianday('now') - julianday(COALESCE(a.updated_at, a.applied_at, a.created_at))
                        AS INTEGER) as days_inactive
            FROM applications a
            LEFT JOIN jobs j ON a.job_hash = j.hash
            LEFT JOIN follow_ups f ON a.id = f.application_id AND f.status = 'offen'
            WHERE a.status IN ('offen', 'beworben', 'eingangsbestaetigung')
            AND (a.profile_id=? OR a.profile_id IS NULL)
            AND f.id IS NULL
            AND julianday('now') - julianday(COALESCE(a.updated_at, a.applied_at, a.created_at)) > ?
            ORDER BY days_inactive DESC
        """, (pid, days_threshold)).fetchall()
        return [dict(r) for r in rows]

    def get_extended_stats(self) -> dict:
        """Get extended statistics for the enhanced stats page (#135).

        Returns: daily activity, response times, dismiss reasons breakdown,
        import vs new applications, overall totals since start.
        """
        conn = self.connect()
        pid = self.get_active_profile_id()

        # --- Today's activity ---
        today_jobs_found = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE date(found_at) = date('now') "
            "AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]
        today_dismissed = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE date(updated_at) = date('now') AND is_active=0 "
            "AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]
        today_applied = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE date(applied_at) = date('now') "
            "AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]

        # --- This week ---
        week_jobs = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE found_at >= date('now', '-7 days') "
            "AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]
        week_dismissed = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE updated_at >= date('now', '-7 days') AND is_active=0 "
            "AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]
        week_applied = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE applied_at >= date('now', '-7 days') "
            "AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]

        # --- Overall totals (#308: Beworben vs. Aussortiert unterscheiden) ---
        total_jobs_ever = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]
        # Jobs mit Bewerbung (haben Eintrag in applications)
        total_applied = conn.execute(
            "SELECT COUNT(DISTINCT j.hash) FROM jobs j "
            "JOIN applications a ON a.job_hash = j.hash "
            "WHERE (j.profile_id=? OR j.profile_id IS NULL)", (pid,)
        ).fetchone()[0]
        # Aussortiert = inaktiv OHNE Bewerbung
        total_dismissed = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_active=0 "
            "AND hash NOT IN (SELECT DISTINCT job_hash FROM applications WHERE job_hash IS NOT NULL) "
            "AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]
        total_active = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_active=1 AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]
        total_pinned = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_pinned=1 AND is_active=1 AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()[0]

        # --- Import vs. new applications ---
        # Applications before first job found_at are considered "imported"
        first_job = conn.execute(
            "SELECT MIN(found_at) as first FROM jobs WHERE found_at IS NOT NULL "
            "AND (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()
        first_job_date = first_job["first"] if first_job else None

        if first_job_date:
            imported = conn.execute(
                "SELECT COUNT(*) FROM applications WHERE applied_at < ? "
                "AND (profile_id=? OR profile_id IS NULL)", (first_job_date, pid)
            ).fetchone()[0]
            new_apps = conn.execute(
                "SELECT COUNT(*) FROM applications WHERE applied_at >= ? "
                "AND (profile_id=? OR profile_id IS NULL)", (first_job_date, pid)
            ).fetchone()[0]
        else:
            imported = 0
            new_apps = conn.execute(
                "SELECT COUNT(*) FROM applications WHERE (profile_id=? OR profile_id IS NULL)", (pid,)
            ).fetchone()[0]

        # --- Response times (days from applied_at to first status change beyond 'beworben') ---
        # #396: Exclude imported applications — their events were created at import time,
        # not when the actual response arrived, leading to wildly inflated values (e.g. 643d)
        response_rows = conn.execute("""
            SELECT a.id,
                   CAST(julianday(MIN(e.event_date)) - julianday(a.applied_at) AS INTEGER) as days
            FROM applications a
            JOIN application_events e ON a.id = e.application_id
            WHERE e.status IN ('abgelehnt', 'interview', 'zweitgespraech', 'angebot', 'abgelaufen')
            AND a.applied_at IS NOT NULL
            AND COALESCE(a.is_imported, 0) = 0
            AND (a.profile_id=? OR a.profile_id IS NULL)
            GROUP BY a.id
            HAVING days >= 0 AND days <= 365
        """, (pid,)).fetchall()
        response_days = [r["days"] for r in response_rows]
        avg_response = round(sum(response_days) / len(response_days), 1) if response_days else None
        min_response = min(response_days) if response_days else None
        max_response = max(response_days) if response_days else None

        # --- Dismiss reasons breakdown ---
        dismiss_rows = conn.execute("""
            SELECT dismiss_reason, COUNT(*) as cnt
            FROM jobs WHERE is_active=0 AND dismiss_reason IS NOT NULL AND dismiss_reason != ''
            AND (profile_id=? OR profile_id IS NULL)
            GROUP BY dismiss_reason ORDER BY cnt DESC
        """, (pid,)).fetchall()
        # Normalize: some are JSON arrays, some strings
        reason_counter = {}
        for r in dismiss_rows:
            raw = r["dismiss_reason"]
            count = r["cnt"]
            # Try JSON array
            try:
                reasons = json.loads(raw)
                if isinstance(reasons, list):
                    for reason in reasons:
                        reason_counter[reason] = reason_counter.get(reason, 0) + count
                    continue
            except (json.JSONDecodeError, TypeError):
                pass
            # Plain string — skip duplicates
            if raw.startswith("Duplikat:"):
                reason_counter["duplikat"] = reason_counter.get("duplikat", 0) + count
            else:
                reason_counter[raw] = reason_counter.get(raw, 0) + count

        dismiss_reasons = sorted(reason_counter.items(), key=lambda x: -x[1])

        # --- Recent activity (last 10 events) ---
        recent = conn.execute("""
            SELECT e.event_date, e.status, e.notes,
                   a.title, a.company
            FROM application_events e
            JOIN applications a ON e.application_id = a.id
            WHERE (a.profile_id=? OR a.profile_id IS NULL)
            ORDER BY e.event_date DESC LIMIT 10
        """, (pid,)).fetchall()
        recent_activity = [dict(r) for r in recent]

        # --- Start date ---
        start_date = conn.execute(
            "SELECT MIN(created_at) FROM profile WHERE is_active=1"
        ).fetchone()[0]

        return {
            "today": {
                "jobs_found": today_jobs_found,
                "dismissed": today_dismissed,
                "applied": today_applied,
            },
            "this_week": {
                "jobs_found": week_jobs,
                "dismissed": week_dismissed,
                "applied": week_applied,
            },
            "totals": {
                "jobs_ever": total_jobs_ever,
                "jobs_active": total_active,
                "jobs_dismissed": total_dismissed,
                "jobs_applied": total_applied,
                "jobs_pinned": total_pinned,
                "dismiss_rate": round(total_dismissed / total_jobs_ever * 100, 1) if total_jobs_ever else 0,
                "hit_rate": round(total_applied / total_jobs_ever * 100, 1) if total_jobs_ever else 0,
            },
            "applications": {
                "imported": imported,
                "new": new_apps,
                "total": imported + new_apps,
            },
            "response_times": {
                "average_days": avg_response,
                "fastest_days": min_response,
                "slowest_days": max_response,
                "sample_size": len(response_days),
            },
            "dismiss_reasons": dismiss_reasons,
            "recent_activity": recent_activity,
            "start_date": start_date,
        }

    def get_report_data(self) -> dict:
        """Get comprehensive data for the PDF/Excel Bewerbungsbericht.

        Returns everything needed: applications list, score stats,
        source breakdown, keyword analysis, unapplied high-score jobs.
        """
        conn = self.connect()
        pid = self.get_active_profile_id()

        # All applications with their linked job data
        apps = conn.execute("""
            SELECT a.*, j.score, j.source as job_source, j.is_pinned,
                   j.description as job_description, j.found_at as job_found_at
            FROM applications a
            LEFT JOIN jobs j ON a.job_hash = j.hash
            WHERE (a.profile_id=? OR a.profile_id IS NULL)
            ORDER BY a.applied_at DESC
        """, (pid,)).fetchall()

        # Score distribution (non-pinned only) – all jobs for historical accuracy (#178)
        score_dist = conn.execute("""
            SELECT
                CASE
                    WHEN score = 0 THEN '0'
                    WHEN score BETWEEN 1 AND 3 THEN '1-3'
                    WHEN score BETWEEN 4 AND 6 THEN '4-6'
                    WHEN score BETWEEN 7 AND 9 THEN '7-9'
                    ELSE '10+'
                END as bracket, COUNT(*) as cnt
            FROM jobs WHERE is_pinned=0
            AND (profile_id=? OR profile_id IS NULL)
            GROUP BY bracket ORDER BY bracket
        """, (pid,)).fetchall()

        # High-score jobs NOT applied to — NUR aktive (#532, v1.6.4):
        # Vorher waren auch dismissed-Stellen drin; das suggerierte verschwendete
        # Chancen, obwohl der User die Stellen aktiv ausgemustert hatte. Jetzt:
        # is_active=1 erzwingen + auch Stellen ausschliessen, deren Firma bereits
        # eine Bewerbung hat (Vermittler/Endkunde-Beziehung).
        unapplied_high = conn.execute("""
            SELECT j.hash, j.title, j.company, j.score, j.source,
                   j.dismiss_reason, j.is_active, j.found_at
            FROM jobs j
            LEFT JOIN applications a ON j.hash = a.job_hash
            WHERE a.id IS NULL
              AND j.score >= 5
              AND j.is_pinned = 0
              AND j.is_active = 1
              AND (j.profile_id=? OR j.profile_id IS NULL)
              AND NOT EXISTS (
                  SELECT 1 FROM applications a2
                  WHERE a2.profile_id IS j.profile_id
                    AND LOWER(TRIM(a2.company)) = LOWER(TRIM(j.company))
              )
            ORDER BY j.score DESC LIMIT 30
        """, (pid,)).fetchall()

        # Date range
        date_range = conn.execute("""
            SELECT MIN(applied_at) as first, MAX(applied_at) as last
            FROM applications WHERE (profile_id=? OR profile_id IS NULL)
        """, (pid,)).fetchone()

        serialized_apps = [
            self._serialize_application_row(
                {
                    **dict(r),
                    "job_source": self._preferred_application_source(
                        dict(r).get("source"), dict(r).get("job_source")
                    ),
                }
            )
            for r in apps
        ]

        # Bewerbungsart-Verteilung (#496 follow-up)
        bewerbungsart = {}
        for a in serialized_apps:
            art = (a.get("bewerbungsart") or "unbekannt").strip() or "unbekannt"
            bewerbungsart[art] = bewerbungsart.get(art, 0) + 1

        # Follow-up-Uebersicht (#496 follow-up)
        follow_ups = self.get_pending_follow_ups() or []
        today_iso = datetime.now().date().isoformat()
        overdue = [fu for fu in follow_ups if (fu.get("scheduled_date") or "") < today_iso]
        follow_up_summary = {
            "pending": len(follow_ups),
            "overdue": len(overdue),
            "items": [
                {
                    "firma": fu.get("company") or fu.get("application_company"),
                    "stelle": fu.get("position") or fu.get("application_title"),
                    "scheduled_date": fu.get("scheduled_date"),
                    "follow_up_type": fu.get("follow_up_type"),
                    "template": fu.get("template"),
                }
                for fu in follow_ups[:20]
            ],
        }

        return {
            "applications": serialized_apps,
            "score_distribution": {r["bracket"]: r["cnt"] for r in score_dist},
            "unapplied_high_score": [self._serialize_job_row(r) for r in unapplied_high],
            "date_range": {
                "first": date_range["first"] if date_range else None,
                "last": date_range["last"] if date_range else None,
            },
            "statistics": self.get_statistics(),
            "rejection_patterns": self.get_rejection_patterns(),
            "follow_ups": follow_up_summary,
            "bewerbungsart": bewerbungsart,
        }

    # === Salary Data (PBP-014) ===

    def save_salary_data(self, job_hash: str, salary_min: float, salary_max: float, salary_type: str):
        """Save extracted salary data for a job."""
        conn = self.connect()
        target_hash = self.resolve_job_hash(job_hash)
        if not target_hash:
            return
        conn.execute(
            "UPDATE jobs SET salary_min=?, salary_max=?, salary_type=?, updated_at=? WHERE hash=?",
            (salary_min, salary_max, salary_type, _now(), target_hash)
        )
        conn.commit()

    def get_salary_statistics(self) -> dict:
        """Get aggregated salary statistics across all jobs with salary data."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        rows = conn.execute("""
            SELECT salary_min, salary_max, salary_type, employment_type, source, location
            FROM jobs
            WHERE salary_min IS NOT NULL AND is_active=1
              AND (? IS NULL OR profile_id=? OR profile_id IS NULL)
        """, (pid, pid)).fetchall()
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

    def save_fit_analyse(self, app_id: str, fit_data: dict, profile_id: str = None) -> bool:
        """Save fit analysis result to an application (#84)."""
        conn = self.connect()
        query = "UPDATE applications SET fit_analyse=?, updated_at=? WHERE id=?"
        params: list[str] = [json.dumps(fit_data, ensure_ascii=False), _now(), app_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

    def update_job(self, job_hash: str, data: dict):
        """Update editable fields of a job (#90)."""
        conn = self.connect()
        target_hash = self.resolve_job_hash(job_hash)
        if not target_hash:
            return
        allowed = ("title", "company", "location", "description", "research_notes")
        sets, vals = [], []
        for f in allowed:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if sets:
            sets.append("updated_at=?")
            vals.append(_now())
            vals.append(target_hash)
            conn.execute(f"UPDATE jobs SET {','.join(sets)} WHERE hash=?", vals)
            conn.commit()

    def merge_jobs(
        self,
        master_hash: str,
        duplicate_hash: str,
        field_strategy: Optional[dict] = None,
        dry_run: bool = True,
    ) -> dict:
        """Merge zwei Stellen-Datensaetze (#470).

        Verhalten:
        - ``field_strategy``: dict pro Feld, Wert ``'master'`` (default),
          ``'duplikat'`` oder ``'merge'`` (nur fuer description — konkateniert).
        - Felder, die im Master leer/None sind und im Duplikat gefuellt, werden
          automatisch uebernommen (egal welche Strategie, weil es keinen
          Konflikt gibt).
        - Referenzen aus ``applications.job_hash`` werden auf ``master_hash``
          umgehaengt.
        - Duplikat-Job wird geloescht.
        - Alles in einer Transaktion. Bei ``dry_run=True`` wird nur der Plan
          zurueckgegeben, nichts geschrieben.

        Returns:
            dict mit Schluesseln:
              - ``status``: 'vorschau' bei dry_run, sonst 'ok'
              - ``master``: {hash, title, company} des Masters
              - ``duplikat``: dito
              - ``feld_entscheidungen``: {feld: {vorher, nachher, quelle}}
              - ``konflikte``: Liste von Feldern mit abweichenden Werten
              - ``umgehaengte_bewerbungen``: Liste von application-IDs
              - ``fehler``: Optional — Problemen wie 'nicht_gefunden'
        """
        conn = self.connect()
        if master_hash == duplicate_hash:
            return {"fehler": "master und duplikat sind identisch"}

        master = self._find_job_row(master_hash)
        duplicate = self._find_job_row(duplicate_hash)
        if not master:
            return {"fehler": "master_nicht_gefunden", "hash": master_hash}
        if not duplicate:
            return {"fehler": "duplikat_nicht_gefunden", "hash": duplicate_hash}

        master_d = dict(master)
        duplicate_d = dict(duplicate)
        strategy = field_strategy or {}

        # Merge-Plan aufbauen
        mergeable_fields = (
            "title", "company", "location", "url", "description", "score",
            "remote_level", "distance_km", "salary_info", "salary_min",
            "salary_max", "salary_type", "employment_type", "research_notes",
            "veroeffentlicht_am", "lat", "lon",
        )
        feld_entscheidungen: dict = {}
        konflikte: list[str] = []
        new_values: dict = {}
        for f in mergeable_fields:
            mv = master_d.get(f)
            dv = duplicate_d.get(f)
            mv_filled = mv not in (None, "", 0)
            dv_filled = dv not in (None, "", 0)
            if mv == dv:
                continue  # nichts zu tun
            if not mv_filled and dv_filled:
                # Master leer, Duplikat gefuellt -> automatisch
                new_values[f] = dv
                feld_entscheidungen[f] = {
                    "vorher": mv, "nachher": dv, "quelle": "duplikat_auto",
                }
                continue
            if mv_filled and not dv_filled:
                feld_entscheidungen[f] = {
                    "vorher": mv, "nachher": mv, "quelle": "master_auto",
                }
                continue
            # Beide unterschiedlich gefuellt -> Konflikt
            konflikte.append(f)
            mode = strategy.get(f, "master")
            if mode == "duplikat":
                new_values[f] = dv
                feld_entscheidungen[f] = {
                    "vorher": mv, "nachher": dv, "quelle": "duplikat",
                }
            elif mode == "merge" and f == "description":
                merged = f"{mv}\n\n--- aus Duplikat {duplicate_hash[:8]} ---\n{dv}"
                new_values[f] = merged
                feld_entscheidungen[f] = {
                    "vorher": mv, "nachher": merged, "quelle": "merge",
                }
            else:
                feld_entscheidungen[f] = {
                    "vorher": mv, "nachher": mv, "quelle": "master",
                }

        # Referenzen suchen
        pid = self.get_active_profile_id()
        apps_to_move = conn.execute(
            "SELECT id FROM applications WHERE job_hash=? "
            "AND (profile_id=? OR profile_id IS NULL)",
            (duplicate_d["hash"], pid),
        ).fetchall()
        umgehaengte = [r["id"] for r in apps_to_move]

        plan = {
            "status": "vorschau" if dry_run else "ok",
            "master": {
                "hash": master_d["hash"],
                "title": master_d.get("title"),
                "company": master_d.get("company"),
            },
            "duplikat": {
                "hash": duplicate_d["hash"],
                "title": duplicate_d.get("title"),
                "company": duplicate_d.get("company"),
            },
            "feld_entscheidungen": feld_entscheidungen,
            "konflikte": konflikte,
            "umgehaengte_bewerbungen": umgehaengte,
            "neue_werte": new_values,
        }

        if dry_run:
            return plan

        # --- Ausfuehrung ---
        try:
            with conn:
                # 1) Applications umhaengen
                if umgehaengte:
                    conn.execute(
                        "UPDATE applications SET job_hash=?, updated_at=? "
                        "WHERE job_hash=? AND (profile_id=? OR profile_id IS NULL)",
                        (master_d["hash"], _now(), duplicate_d["hash"], pid),
                    )
                # 2) Master updaten mit neuen Werten
                if new_values:
                    sets = ", ".join(f"{k}=?" for k in new_values)
                    vals = list(new_values.values()) + [_now(), master_d["hash"]]
                    conn.execute(
                        f"UPDATE jobs SET {sets}, updated_at=? WHERE hash=?",
                        vals,
                    )
                # 3) Duplikat-Job loeschen
                conn.execute("DELETE FROM jobs WHERE hash=?", (duplicate_d["hash"],))
            plan["status"] = "ok"
            return plan
        except Exception as exc:
            return {"fehler": "transaktion_fehlgeschlagen", "detail": str(exc)}

    def get_company_jobs(self, company: str) -> list:
        """Get all jobs from a specific company."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        return [self._serialize_job_row(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE company LIKE ? "
            "AND (? IS NULL OR profile_id=? OR profile_id IS NULL) "
            "ORDER BY score DESC",
            (f"%{company}%", pid, pid)
        ).fetchall()]

    def get_skill_frequency(self) -> list:
        """Analyze skill keywords frequency in active job descriptions."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        rows = conn.execute(
            "SELECT description FROM jobs WHERE is_active=1 AND description IS NOT NULL "
            "AND (? IS NULL OR profile_id=? OR profile_id IS NULL)",
            (pid, pid)
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
        pid = self.get_active_profile_id()
        return [dict(r) for r in conn.execute("""
            SELECT f.*, a.title, a.company, a.status as app_status, a.applied_at
            FROM follow_ups f
            JOIN applications a ON f.application_id = a.id
            WHERE f.status = 'geplant'
              AND (? IS NULL OR a.profile_id=? OR a.profile_id IS NULL)
            ORDER BY f.scheduled_date ASC
        """, (pid, pid)).fetchall()]

    def complete_follow_up(self, follow_up_id: str, status: str = "gesendet"):
        """Mark a follow-up as completed or skipped."""
        conn = self.connect()
        conn.execute(
            "UPDATE follow_ups SET status=?, completed_at=? WHERE id=?",
            (status, _now(), follow_up_id)
        )
        conn.commit()

    def get_follow_up(self, follow_up_id: str) -> Optional[dict]:
        """Get a single follow-up by ID (#453)."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM follow_ups WHERE id=?", (follow_up_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_follow_up(self, follow_up_id: str, data: dict):
        """Update follow-up fields (scheduled_date, template). #453"""
        conn = self.connect()
        fields = []
        values = []
        for key in ("scheduled_date", "template", "follow_up_type"):
            if key in data:
                fields.append(f"{key}=?")
                values.append(data[key])
        if not fields:
            return
        values.append(follow_up_id)
        conn.execute(f"UPDATE follow_ups SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()

    def dismiss_open_followups_for_application(self, application_id: str, reason: str = "") -> int:
        """Setze alle offenen Follow-ups einer Bewerbung auf 'hinfaellig' (z.B. bei Absage). #453"""
        conn = self.connect()
        cur = conn.execute(
            "UPDATE follow_ups SET status='hinfaellig', completed_at=? "
            "WHERE application_id=? AND status='geplant'",
            (_now(), application_id)
        )
        conn.commit()
        return cur.rowcount or 0

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

    def get_profile_setting(self, key: str, default=None):
        """Get a setting scoped to the active profile.

        Stored in settings as '{profile_id}:{key}'.  Falls back to *default*
        when no entry exists for the current profile (even if a global entry
        with the bare *key* exists from a previous schema).
        """
        pid = self.get_active_profile_id()
        if not pid:
            return self.get_setting(key, default)
        return self.get_setting(f"{pid}:{key}", default)

    def set_profile_setting(self, key: str, value):
        """Store a setting scoped to the active profile."""
        pid = self.get_active_profile_id() or ""
        self.set_setting(f"{pid}:{key}" if pid else key, value)

    # === Scoring Config (#169) ===

    def get_scoring_config(self, dimension: str = None) -> list:
        """Get scoring configuration entries, optionally filtered by dimension."""
        pid = self.get_active_profile_id() or ""
        conn = self.connect()
        if dimension:
            rows = conn.execute(
                "SELECT * FROM scoring_config WHERE (profile_id=? OR profile_id='') "
                "AND dimension=? ORDER BY sub_key",
                (pid, dimension)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM scoring_config WHERE profile_id=? OR profile_id='' "
                "ORDER BY dimension, sub_key",
                (pid,)
            ).fetchall()
        return [dict(r) for r in rows]

    def set_scoring_config(self, dimension: str, sub_key: str,
                           value: float = 0, ignore_flag: bool = False):
        """Set or update a scoring config entry."""
        pid = self.get_active_profile_id() or ""
        conn = self.connect()
        conn.execute("""
            INSERT OR REPLACE INTO scoring_config
                (profile_id, dimension, sub_key, value, ignore_flag, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pid, dimension, sub_key, value, 1 if ignore_flag else 0, _now()))
        conn.commit()

    def get_scoring_threshold(self) -> float:
        """Get the auto-ignore threshold for fit scores."""
        pid = self.get_active_profile_id() or ""
        conn = self.connect()
        row = conn.execute(
            "SELECT value FROM scoring_config "
            "WHERE (profile_id=? OR profile_id='') "
            "AND dimension='schwellenwert' AND sub_key='auto_ignore' "
            "ORDER BY profile_id DESC LIMIT 1",
            (pid,)
        ).fetchone()
        return float(row["value"]) if row else 0

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
        pid = self.get_active_profile_id()
        apps = conn.execute("""
            SELECT a.*, ae.notes as event_notes, ae.event_date
            FROM applications a
            LEFT JOIN application_events ae ON a.id = ae.application_id AND ae.status = 'abgelehnt'
            WHERE a.status = 'abgelehnt'
              AND (? IS NULL OR a.profile_id=? OR a.profile_id IS NULL)
            ORDER BY a.updated_at DESC
        """, (pid, pid)).fetchall()
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
            steps.append({"aktion": "Zusammenfassung ergänzen", "prioritaet": "hoch",
                          "beschreibung": "Dein Profil braucht eine Zusammenfassung für Anschreiben und CV.",
                          "action_type": "dashboard", "action_target": "showProfileForm()",
                          "action_label": "Profil bearbeiten", "prompt": "/profil_überprüfen"})
        if not profile.get("positions"):
            steps.append({"aktion": "Berufserfahrung hinzufügen", "prioritaet": "hoch",
                          "beschreibung": "Berufserfahrung ist für Bewerbungen essentiell.",
                          "action_type": "dashboard", "action_target": "showPage('profil'); setTimeout(showPositionForm, 200)",
                          "action_label": "+ Position", "prompt": "/ersterfassung"})
        if not profile.get("skills"):
            steps.append({"aktion": "Skills hinzufügen", "prioritaet": "mittel",
                          "beschreibung": "Skills helfen beim Job-Matching und Fit-Score.",
                          "action_type": "dashboard", "action_target": "showPage('profil'); setTimeout(showSkillForm, 200)",
                          "action_label": "+ Skill"})
        if not profile.get("education"):
            steps.append({"aktion": "Ausbildung ergänzen", "prioritaet": "mittel",
                          "beschreibung": "Für ein vollständiges Bewerberprofil.",
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
                          "beschreibung": "Lade Lebenslauf oder Zeugnisse hoch für automatische Profil-Erweiterung.",
                          "action_type": "dashboard", "action_target": "wizardDocUpload()",
                          "action_label": "Dokument hochladen"})

        # Check follow-ups
        due_followups = conn.execute("""
            SELECT COUNT(*)
            FROM follow_ups f
            JOIN applications a ON a.id = f.application_id
            WHERE f.status = 'geplant'
              AND f.scheduled_date <= date('now')
              AND (? IS NULL OR a.profile_id=? OR a.profile_id IS NULL)
        """, (profile_id, profile_id)).fetchone()[0]
        if due_followups:
            steps.append({"aktion": f"{due_followups} faellige(s) Follow-up(s)",
                          "prioritaet": "hoch",
                          "beschreibung": "Nachfass-Aktionen sind faellig — nicht vergessen!",
                          "action_type": "dashboard",
                          "action_target": "showPage('bewerbungen')",
                          "action_label": "Bewerbungen ansehen"})

        # Check sources
        active_sources = self.get_profile_setting("active_sources", [])
        if not active_sources:
            steps.append({"aktion": "Jobquellen aktivieren", "prioritaet": "hoch",
                          "beschreibung": "Ohne aktive Quellen kann keine Jobsuche gestartet werden.",
                          "action_type": "dashboard",
                          "action_target": "showPage('einstellungen')",
                          "action_label": "Einstellungen"})

        # Check job search recency
        last_search = self.get_profile_setting("last_search_at")
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
        where_profile = "AND (profile_id = ? OR profile_id IS NULL)" if profile_id else ""
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
            f"SELECT COUNT(*) FROM applications {('WHERE (profile_id = ? OR profile_id IS NULL)' if profile_id else '')}",
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
                          "beschreibung": f"{rejections} Absagen erhalten — analysiere die Muster für bessere Chancen.",
                          "action_type": "prompt", "prompt": "/profil_analyse"})

        # Suggest interview prep when interviews scheduled
        interviews = conn.execute(
            f"SELECT COUNT(*) FROM applications WHERE status IN ('interview','zweitgespraech','interview_abgeschlossen') {where_profile}",
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
                raise ValueError(f"Ungueltiges Format für '{key}': Liste erwartet")
        if data.get("preferences") is not None and not isinstance(data.get("preferences"), (dict, str)):
            raise ValueError("Ungueltiges Format für 'preferences': Dict erwartet")
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

    # === E-Mail Integration ===

    def add_email(self, data: dict) -> str:
        """Store a parsed email in the database."""
        conn = self.connect()
        eid = _gen_id()
        pid = self.get_active_profile_id()
        conn.execute(
            """INSERT INTO application_emails
               (id, application_id, profile_id, filename, filepath, subject, sender,
                recipients, sent_date, direction, body_text, body_html,
                detected_status, detected_status_confidence, match_confidence,
                attachments_json, meeting_extracted, is_processed, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                eid,
                data.get("application_id"),
                pid,
                data.get("filename", ""),
                data.get("filepath", ""),
                data.get("subject", ""),
                data.get("sender", ""),
                data.get("recipients", ""),
                data.get("sent_date"),
                data.get("direction", "eingang"),
                data.get("body_text", ""),
                data.get("body_html", ""),
                data.get("detected_status"),
                data.get("detected_status_confidence", 0.0),
                data.get("match_confidence", 0.0),
                json.dumps(data.get("attachments_meta", []), ensure_ascii=False),
                1 if data.get("meeting_extracted") else 0,
                1 if data.get("is_processed") else 0,
                _now(),
            ),
        )
        conn.commit()
        return eid

    def find_recent_duplicate_email(
        self,
        sender: str,
        subject: str,
        sent_date: Optional[str],
        window_minutes: int = 5,
    ) -> Optional[dict]:
        """Finde eine bereits importierte Mail mit gleichem sender/subject/sent_date
        die innerhalb der letzten ``window_minutes`` Minuten angelegt wurde.

        Schuetzt vor dem Drag-and-Drop-Zweit-Import aus Thunderbird, wenn der Import-
        Toast fuer den User nicht schnell genug erscheint und er die Mail erneut
        hineinzieht (#476). Identisches sent_date verhindert False-Positives bei
        Mails mit identischem Betreff von demselben Absender an unterschiedlichen
        Tagen.
        """
        conn = self.connect()
        pid = self.get_active_profile_id()
        row = conn.execute(
            """SELECT id, subject, sender, sent_date, created_at
               FROM application_emails
               WHERE (profile_id=? OR profile_id IS NULL)
                 AND sender=? AND subject=?
                 AND (sent_date IS ? OR sent_date=?)
                 AND created_at >= datetime('now', ?)
               ORDER BY created_at DESC
               LIMIT 1""",
            (pid, sender, subject, sent_date, sent_date, f"-{int(window_minutes)} minutes"),
        ).fetchone()
        return dict(row) if row else None

    def get_email(self, email_id: str, profile_id: str = None) -> Optional[dict]:
        """Get a single email by ID."""
        conn = self.connect()
        query = "SELECT * FROM application_emails WHERE id=?"
        params: list[str] = [email_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        d = dict(row)
        d["attachments_meta"] = json.loads(d.get("attachments_json") or "[]")
        return d

    def get_emails_for_application(self, application_id: str, profile_id: str = None) -> list:
        """List all emails linked to an application."""
        conn = self.connect()
        query = "SELECT * FROM application_emails WHERE application_id=?"
        params: list[str] = [application_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        query += " ORDER BY sent_date DESC"
        rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["attachments_meta"] = json.loads(d.get("attachments_json") or "[]")
            # Don't send full body in list view
            d.pop("body_html", None)
            result.append(d)
        return result

    def get_unmatched_emails(self) -> list:
        """Get emails not yet linked to an application."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        rows = conn.execute(
            """SELECT * FROM application_emails
               WHERE application_id IS NULL AND (profile_id=? OR profile_id IS NULL)
               ORDER BY created_at DESC""",
            (pid,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_email(self, email_id: str, data: dict, profile_id: str = None) -> bool:
        """Update email fields (e.g., assign to application)."""
        conn = self.connect()
        allowed = {"application_id", "is_processed", "detected_status",
                    "detected_status_confidence", "match_confidence"}
        sets = []
        vals = []
        for k, v in data.items():
            if k in allowed:
                sets.append(f"{k}=?")
                vals.append(v)
        if not sets:
            return False
        query = f"UPDATE application_emails SET {', '.join(sets)} WHERE id=?"
        vals.append(email_id)
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            vals.append(profile_id)
        cur = conn.execute(query, vals)
        conn.commit()
        return cur.rowcount > 0

    def delete_email(self, email_id: str, profile_id: str = None) -> bool:
        """Delete an email record."""
        conn = self.connect()
        query = "DELETE FROM application_emails WHERE id=?"
        params: list[str] = [email_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

    def get_all_emails(self) -> list:
        """Get all emails for the active profile."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        rows = conn.execute(
            """SELECT id, application_id, filename, subject, sender, recipients,
                      sent_date, direction, detected_status, detected_status_confidence,
                      match_confidence, is_processed, created_at
               FROM application_emails
               WHERE profile_id=? OR profile_id IS NULL
               ORDER BY sent_date DESC""",
            (pid,),
        ).fetchall()
        return [dict(r) for r in rows]

    # === Meetings ===

    def add_meeting(self, data: dict) -> str:
        """Store a meeting/appointment."""
        conn = self.connect()
        mid = _gen_id()
        pid = self.get_active_profile_id()
        conn.execute(
            """INSERT INTO application_meetings
               (id, application_id, email_id, profile_id, title, meeting_date,
                meeting_end, location, meeting_url, meeting_type, platform,
                ics_data, notes, status, is_private, duration_minutes,
                category_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                mid,
                data.get("application_id"),
                data.get("email_id"),
                pid,
                data.get("title", "Termin"),
                data["meeting_date"],
                data.get("meeting_end"),
                data.get("location", ""),
                data.get("meeting_url"),
                data.get("meeting_type", "interview"),
                data.get("platform"),
                data.get("ics_data"),
                data.get("notes"),
                data.get("status", "geplant"),
                1 if data.get("is_private") else 0,
                data.get("duration_minutes"),
                data.get("category_id"),
                _now(),
            ),
        )
        conn.commit()
        return mid

    def get_upcoming_meetings(self, days: int = 30) -> list:
        """Get upcoming meetings for the active profile within N days."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        now = datetime.now().isoformat()
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()
        rows = conn.execute(
            """SELECT m.*, a.title as app_title, a.company as app_company
               FROM application_meetings m
               LEFT JOIN applications a ON m.application_id = a.id
               WHERE m.status != 'abgesagt'
                 AND m.meeting_date >= ?
                 AND m.meeting_date <= ?
                 AND (m.profile_id=? OR m.profile_id IS NULL)
               ORDER BY m.meeting_date ASC""",
            (now, cutoff, pid),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_meetings_for_application(self, application_id: str, profile_id: str = None) -> list:
        """Get all meetings for a specific application."""
        conn = self.connect()
        query = "SELECT * FROM application_meetings WHERE application_id=?"
        params: list[str] = [application_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        query += " ORDER BY meeting_date ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def update_meeting(self, meeting_id: str, data: dict, profile_id: str = None) -> bool:
        """Update meeting fields."""
        conn = self.connect()
        allowed = {"title", "meeting_date", "meeting_end", "location",
                    "meeting_url", "meeting_type", "platform", "notes", "status",
                    "is_private", "duration_minutes", "category_id", "application_id"}
        sets = []
        vals = []
        for k, v in data.items():
            if k in allowed:
                sets.append(f"{k}=?")
                vals.append(v)
        if not sets:
            return False
        query = f"UPDATE application_meetings SET {', '.join(sets)} WHERE id=?"
        vals.append(meeting_id)
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            vals.append(profile_id)
        cur = conn.execute(query, vals)
        conn.commit()
        return cur.rowcount > 0

    def delete_meeting(self, meeting_id: str, profile_id: str = None) -> bool:
        """Delete a meeting."""
        conn = self.connect()
        query = "DELETE FROM application_meetings WHERE id=?"
        params: list[str] = [meeting_id]
        if profile_id is not None:
            query += " AND (profile_id=? OR profile_id IS NULL)"
            params.append(profile_id)
        cur = conn.execute(query, params)
        conn.commit()
        return cur.rowcount > 0

    # === Meeting Categories (#417) ===

    def get_meeting_categories(self, profile_id: str = None) -> list:
        """Get all meeting categories for a profile, including system categories."""
        conn = self.connect()
        pid = profile_id or self.get_active_profile_id()
        rows = conn.execute(
            """SELECT * FROM meeting_categories
               WHERE profile_id=? OR profile_id IS NULL
               ORDER BY is_system DESC, name ASC""",
            (pid,),
        ).fetchall()
        return [dict(r) for r in rows]

    def ensure_system_categories(self, profile_id: str = None) -> None:
        """Create default system categories if they don't exist for a profile."""
        conn = self.connect()
        pid = profile_id or self.get_active_profile_id()
        if not pid:
            return
        existing = conn.execute(
            "SELECT name FROM meeting_categories WHERE profile_id=? AND is_system=1",
            (pid,),
        ).fetchall()
        existing_names = {r["name"] for r in existing}
        defaults = [
            ("Bewerbung", "#0ea5e9", 1),
            ("Interview", "#f59e0b", 1),
            ("Privat", "#6b7280", 0),
        ]
        for name, color, show_stats in defaults:
            if name not in existing_names:
                conn.execute(
                    """INSERT INTO meeting_categories
                       (id, profile_id, name, color, show_in_stats, is_system, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (_gen_id(), pid, name, color, show_stats, _now()),
                )
        conn.commit()

    def add_meeting_category(self, data: dict) -> str:
        """Create a custom meeting category."""
        conn = self.connect()
        cid = _gen_id()
        pid = self.get_active_profile_id()
        conn.execute(
            """INSERT INTO meeting_categories
               (id, profile_id, name, color, show_in_stats, is_system, created_at)
               VALUES (?, ?, ?, ?, ?, 0, ?)""",
            (cid, pid, data["name"], data.get("color", "#3b82f6"),
             1 if data.get("show_in_stats", True) else 0, _now()),
        )
        conn.commit()
        return cid

    def update_meeting_category(self, category_id: str, data: dict) -> bool:
        """Update a custom meeting category (not system categories)."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        sets, vals = [], []
        for k in ("name", "color", "show_in_stats"):
            if k in data:
                sets.append(f"{k}=?")
                vals.append(data[k])
        if not sets:
            return False
        vals.extend([category_id, pid])
        cur = conn.execute(
            f"UPDATE meeting_categories SET {', '.join(sets)} WHERE id=? AND profile_id=?",
            vals,
        )
        conn.commit()
        return cur.rowcount > 0

    def delete_meeting_category(self, category_id: str, reassign_to: str = None) -> bool:
        """Delete a custom category. Optionally reassign meetings to another category."""
        conn = self.connect()
        pid = self.get_active_profile_id()
        # Prevent deleting system categories
        row = conn.execute(
            "SELECT is_system FROM meeting_categories WHERE id=? AND profile_id=?",
            (category_id, pid),
        ).fetchone()
        if not row or row["is_system"]:
            return False
        if reassign_to:
            conn.execute(
                "UPDATE application_meetings SET category_id=? WHERE category_id=? AND profile_id=?",
                (reassign_to, category_id, pid),
            )
        else:
            conn.execute(
                "UPDATE application_meetings SET category_id=NULL WHERE category_id=? AND profile_id=?",
                (category_id, pid),
            )
        conn.execute(
            "DELETE FROM meeting_categories WHERE id=? AND profile_id=? AND is_system=0",
            (category_id, pid),
        )
        conn.commit()
        return True


def _safe_float(val, default=None):
    """Sanitize float values for JSON serialization (inf/nan -> default)."""
    import math
    if val is None:
        return default
    try:
        f = float(val)
        if math.isinf(f) or math.isnan(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


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
    customer_name TEXT,
    is_confidential INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    start_date TEXT,
    end_date TEXT
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
    level INTEGER DEFAULT 3,           -- = level_peak (hoechstes erreichtes Niveau)
    years_experience INTEGER,           -- legacy, abgeleitet aus start_year/end_year
    last_used_year INTEGER,             -- legacy, redundant zu end_year
    profile_id TEXT,
    start_year INTEGER,                 -- v28 (#511): Anfang der Skill-Nutzung
    end_year INTEGER,                   -- v28: Ende; NULL = laeuft noch
    level_current INTEGER               -- v28: aktuelles Niveau (NULL = wie peak)
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
    linked_application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
    profile_id TEXT,
    extraction_status TEXT DEFAULT 'nicht_extrahiert',
    last_extraction_at TEXT,
    content_hash TEXT,
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
    is_pinned INTEGER DEFAULT 0,
    lat REAL,
    lon REAL,
    research_notes TEXT,
    veroeffentlicht_am TEXT,
    is_search_url INTEGER DEFAULT 0,
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
    fit_analyse TEXT,
    employment_type TEXT,
    source TEXT DEFAULT '',
    source_secondary TEXT DEFAULT '',
    vermittler TEXT DEFAULT '',
    endkunde TEXT DEFAULT '',
    description_snapshot TEXT,
    snapshot_date TEXT,
    gehaltsvorstellung TEXT DEFAULT '',
    final_salary TEXT DEFAULT '',
    has_reached_interview INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS application_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    event_date TEXT NOT NULL,
    notes TEXT,
    parent_event_id INTEGER REFERENCES application_events(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS search_criteria (
    profile_id TEXT NOT NULL DEFAULT '',
    key TEXT NOT NULL,
    value TEXT,
    updated_at TEXT,
    PRIMARY KEY (profile_id, key)
);

CREATE TABLE IF NOT EXISTS blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    reason TEXT,
    created_at TEXT,
    UNIQUE(profile_id, type, value)
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

CREATE TABLE IF NOT EXISTS dismiss_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    is_custom INTEGER DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    profile_id TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS application_emails (
    id TEXT PRIMARY KEY,
    application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
    profile_id TEXT,
    filename TEXT NOT NULL,
    filepath TEXT,
    subject TEXT,
    sender TEXT,
    recipients TEXT,
    sent_date TEXT,
    direction TEXT DEFAULT 'eingang',
    body_text TEXT,
    body_html TEXT,
    detected_status TEXT,
    detected_status_confidence REAL DEFAULT 0.0,
    match_confidence REAL DEFAULT 0.0,
    attachments_json TEXT DEFAULT '[]',
    meeting_extracted INTEGER DEFAULT 0,
    is_processed INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS application_meetings (
    id TEXT PRIMARY KEY,
    application_id TEXT REFERENCES applications(id) ON DELETE CASCADE,
    email_id TEXT REFERENCES application_emails(id) ON DELETE SET NULL,
    profile_id TEXT,
    title TEXT NOT NULL,
    meeting_date TEXT NOT NULL,
    meeting_end TEXT,
    location TEXT,
    meeting_url TEXT,
    meeting_type TEXT DEFAULT 'interview',
    platform TEXT,
    ics_data TEXT,
    notes TEXT,
    status TEXT DEFAULT 'geplant',
    is_private INTEGER DEFAULT 0,
    duration_minutes INTEGER,
    category_id TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS meeting_categories (
    id TEXT PRIMARY KEY,
    profile_id TEXT,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#3b82f6',
    show_in_stats INTEGER DEFAULT 1,
    is_system INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_emails_app ON application_emails(application_id);
CREATE INDEX IF NOT EXISTS idx_emails_profile ON application_emails(profile_id);
CREATE INDEX IF NOT EXISTS idx_meetings_app ON application_meetings(application_id);
CREATE INDEX IF NOT EXISTS idx_meetings_date ON application_meetings(meeting_date, status);

CREATE TABLE IF NOT EXISTS scoring_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT '',
    dimension TEXT NOT NULL,
    sub_key TEXT NOT NULL,
    value REAL DEFAULT 0,
    ignore_flag INTEGER DEFAULT 0,
    created_at TEXT,
    UNIQUE(profile_id, dimension, sub_key)
);
CREATE INDEX IF NOT EXISTS idx_scoring_profile ON scoring_config(profile_id, dimension);

CREATE TABLE IF NOT EXISTS scraper_health (
    scraper_name TEXT PRIMARY KEY,
    last_run TEXT,
    last_success TEXT,
    last_error TEXT,
    consecutive_failures INTEGER DEFAULT 0,
    total_runs INTEGER DEFAULT 0,
    total_successes INTEGER DEFAULT 0,
    avg_time_s REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    last_count INTEGER DEFAULT 0,
    last_status_detail TEXT,
    consecutive_silent INTEGER DEFAULT 0
);
"""
