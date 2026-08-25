"""Migrations-Smoke-Test v1.6.9 (Schema v31) -> v1.7.0-beta.18 (Schema v36).

Hintergrund: v1.6.9 ist der Stable-Release den Endnutzer aktuell laufen
haben. Beim Drueber-Install der v1.7-Beta laeuft beim ersten Start die
Schema-Migration v31 -> v32 -> v33 -> v34 -> v35 -> v36 sequenziell durch.

Dieser Test simuliert das Szenario:
1. Lege eine v1.6.9-DB an (Schema-Version 31, mit realistischen Daten)
2. Starte Database() darueber — fuehrt initialize() + Migration durch
3. Verifiziere dass alle Daten noch da sind und neue Strukturen existieren
4. Verifiziere dass das automatische Backup angelegt wurde
5. Verifiziere dass die #526 BA-URL-Migration durchgelaufen ist

Schlaegt der Test fehl, wuerde ein User beim Drueber-Install Daten oder
Funktionalitaet verlieren — Release-Blocker.
"""
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest


# === Test-Helfer: realistische v1.6.9-DB anlegen ===

def _create_v169_database(db_path: Path) -> dict:
    """Legt eine SQLite-DB an die so aussieht wie eine echte v1.6.9-DB.

    Returns: dict mit IDs der angelegten Daten zur spaeteren Verifikation.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=OFF")  # Migration-Pfad-aehnlich
    cur = conn.cursor()

    # === Minimal-Schema v31 (so wie v1.6.9 es hatte) ===
    cur.executescript("""
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE profile (
            id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT,
            address TEXT, city TEXT, plz TEXT,
            country TEXT DEFAULT 'Deutschland', birthday TEXT,
            nationality TEXT, photo_path TEXT, summary TEXT,
            informal_notes TEXT, preferences TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            erfassung_fortschritt TEXT DEFAULT '{}',
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE positions (
            id TEXT PRIMARY KEY, company TEXT NOT NULL, title TEXT NOT NULL,
            location TEXT, start_date TEXT, end_date TEXT,
            is_current INTEGER DEFAULT 0,
            employment_type TEXT DEFAULT 'festanstellung',
            industry TEXT, description TEXT, tasks TEXT, achievements TEXT,
            technologies TEXT, profile_id TEXT,
            sort_order INTEGER DEFAULT 0, created_at TEXT
        );
        CREATE TABLE skills (
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            category TEXT DEFAULT 'fachlich', level INTEGER DEFAULT 3,
            years_experience INTEGER, last_used_year INTEGER,
            profile_id TEXT, start_year INTEGER, end_year INTEGER,
            level_current INTEGER
        );
        CREATE TABLE jobs (
            hash TEXT PRIMARY KEY, title TEXT, company TEXT, location TEXT,
            url TEXT, source TEXT, description TEXT,
            score INTEGER DEFAULT 0,
            remote_level TEXT DEFAULT 'unbekannt',
            distance_km REAL, salary_info TEXT,
            salary_min REAL, salary_max REAL, salary_type TEXT,
            salary_estimated INTEGER DEFAULT 0,
            employment_type TEXT DEFAULT 'festanstellung',
            dismiss_reason TEXT, is_active INTEGER DEFAULT 1,
            is_pinned INTEGER DEFAULT 0, lat REAL, lon REAL,
            research_notes TEXT, veroeffentlicht_am TEXT,
            is_search_url INTEGER DEFAULT 0, profile_id TEXT,
            found_at TEXT, updated_at TEXT
        );
        CREATE TABLE applications (
            id TEXT PRIMARY KEY,
            job_hash TEXT REFERENCES jobs(hash) ON DELETE SET NULL,
            profile_id TEXT, title TEXT NOT NULL, company TEXT NOT NULL,
            url TEXT, status TEXT DEFAULT 'beworben',
            applied_at TEXT, cover_letter_path TEXT, cv_path TEXT,
            project_list_path TEXT, notes TEXT,
            bewerbungsart TEXT DEFAULT 'mit_dokumenten',
            lebenslauf_variante TEXT DEFAULT 'standard',
            ansprechpartner TEXT DEFAULT '',
            kontakt_email TEXT DEFAULT '',
            portal_name TEXT DEFAULT '',
            rejection_reason TEXT, fit_analyse TEXT,
            employment_type TEXT, source TEXT DEFAULT '',
            source_secondary TEXT DEFAULT '',
            vermittler TEXT DEFAULT '', endkunde TEXT DEFAULT '',
            description_snapshot TEXT, snapshot_date TEXT,
            gehaltsvorstellung TEXT DEFAULT '',
            final_salary TEXT DEFAULT '',
            has_reached_interview INTEGER DEFAULT 0,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE documents (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, filepath TEXT,
            doc_type TEXT DEFAULT 'sonstiges', extracted_text TEXT,
            linked_position_id TEXT REFERENCES positions(id) ON DELETE SET NULL,
            linked_application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
            profile_id TEXT,
            extraction_status TEXT DEFAULT 'nicht_extrahiert',
            last_extraction_at TEXT, content_hash TEXT, created_at TEXT
        );
        CREATE TABLE application_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            status TEXT NOT NULL, event_date TEXT NOT NULL,
            notes TEXT,
            parent_event_id INTEGER REFERENCES application_events(id) ON DELETE SET NULL
        );
        CREATE TABLE search_criteria (
            profile_id TEXT NOT NULL DEFAULT '',
            key TEXT NOT NULL, value TEXT, updated_at TEXT,
            PRIMARY KEY (profile_id, key)
        );
        CREATE TABLE blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL DEFAULT '',
            type TEXT NOT NULL, value TEXT NOT NULL,
            created_at TEXT
        );
        CREATE TABLE follow_ups (
            id TEXT PRIMARY KEY,
            application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            scheduled_date TEXT NOT NULL,
            follow_up_type TEXT DEFAULT 'nachfass',
            template TEXT, status TEXT DEFAULT 'geplant',
            created_at TEXT, completed_at TEXT
        );
        CREATE TABLE application_meetings (
            id TEXT PRIMARY KEY,
            application_id TEXT REFERENCES applications(id) ON DELETE CASCADE,
            title TEXT NOT NULL, meeting_date TEXT NOT NULL,
            meeting_type TEXT, location TEXT, status TEXT DEFAULT 'geplant',
            notes TEXT, created_at TEXT
        );
        CREATE TABLE profile_settings (
            profile_id TEXT, key TEXT NOT NULL, value TEXT,
            PRIMARY KEY (profile_id, key)
        );
        CREATE TABLE dismiss_reasons (
            label TEXT, is_custom INTEGER DEFAULT 0,
            profile_id TEXT, created_at TEXT
        );
        CREATE TABLE scoring_config (
            profile_id TEXT, dimension TEXT, sub_key TEXT,
            value INTEGER, ignore_flag INTEGER DEFAULT 0,
            created_at TEXT,
            PRIMARY KEY (profile_id, dimension, sub_key)
        );
    """)

    # Schema-Version auf v31 setzen (v1.6.9)
    cur.execute("INSERT INTO settings VALUES ('schema_version', '31')")

    # === Realistische Daten (so wie ein User auf v1.6.9 sie haette) ===
    pid = "prof-test-pid"
    cur.execute(
        "INSERT INTO profile (id, name, email, is_active, created_at) "
        "VALUES (?, 'Markus Mustermann', 'markus@example.com', 1, '2024-12-01T10:00:00')",
        (pid,)
    )
    cur.execute(
        "INSERT INTO positions (id, company, title, profile_id, start_date, created_at) "
        "VALUES ('pos-1', 'Musterfirma Software GmbH', 'PLM Consultant', ?, '2018-01-01', '2024-12-01T10:00:00')",
        (pid,)
    )
    cur.execute(
        "INSERT INTO skills (id, name, category, level, profile_id, start_year, end_year) "
        "VALUES ('sk-py', 'Python', 'fachlich', 5, ?, 2008, NULL)",
        (pid,)
    )
    # Stelle mit alter BA-URL (#526)
    cur.execute(
        "INSERT INTO jobs (hash, title, company, source, url, profile_id, found_at) "
        "VALUES ('h-ba-old', 'PLM Manager', 'ACME', 'bundesagentur', "
        "'https://www.arbeitsagentur.de/jobsuche/suche?id=12634-BB-640183-7878-S', ?, "
        "'2025-01-15T08:00:00')",
        (pid,)
    )
    # Stelle mit korrekter URL (sollte unangetastet bleiben)
    cur.execute(
        "INSERT INTO jobs (hash, title, company, source, url, profile_id, found_at) "
        "VALUES ('h-ok', 'Engineer', 'CO', 'indeed', 'https://indeed.com/viewjob?jk=abc', ?, "
        "'2025-02-01T08:00:00')",
        (pid,)
    )
    # Bewerbung
    cur.execute(
        "INSERT INTO applications (id, profile_id, title, company, status, applied_at, "
        "created_at, has_reached_interview) VALUES "
        "('app-1', ?, 'PLM Manager', 'ACME', 'beworben', '2025-01-20T09:00:00', "
        "'2025-01-20T09:00:00', 0)",
        (pid,)
    )
    # Dokument
    cur.execute(
        "INSERT INTO documents (id, filename, doc_type, profile_id, "
        "linked_application_id, created_at) VALUES "
        "('doc-1', 'lebenslauf-markus.pdf', 'lebenslauf', ?, 'app-1', "
        "'2025-01-20T09:00:00')",
        (pid,)
    )
    # Follow-up
    cur.execute(
        "INSERT INTO follow_ups (id, application_id, scheduled_date, "
        "follow_up_type, template, status, created_at) VALUES "
        "('fu-1', 'app-1', '2025-02-05', 'nachfass', "
        "'Hallo, gibt es Neuigkeiten?', 'geplant', '2025-01-20T09:00:00')"
    )

    conn.commit()
    conn.close()
    return {
        "pid": pid,
        "position_id": "pos-1",
        "skill_id": "sk-py",
        "ba_old_hash": "h-ba-old",
        "ok_hash": "h-ok",
        "app_id": "app-1",
        "doc_id": "doc-1",
        "followup_id": "fu-1",
    }


# === Tests ===

@pytest.fixture
def v169_data_dir():
    """Erzeugt eine isolierte Daten-Umgebung mit fertiger v1.6.9-DB."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_v169_to_beta18_")
    data_dir = Path(tmpdir) / "data"
    data_dir.mkdir()
    db_path = data_dir / "pbp.db"
    ids = _create_v169_database(db_path)
    os.environ["BA_DATA_DIR"] = str(data_dir)
    # Force reimport
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    yield data_dir, ids
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_migration_runs_to_v36(v169_data_dir):
    """Migration v31 -> aktuelle SCHEMA_VERSION laeuft komplett durch ohne Fehler.

    (Test-Name ist historisch — laeuft in beta.20+ bis v37.)
    """
    data_dir, _ = v169_data_dir
    from bewerbungs_assistent.database import Database, SCHEMA_VERSION

    assert SCHEMA_VERSION >= 36, f"SCHEMA_VERSION muss >= 36 sein, ist {SCHEMA_VERSION}"

    db = Database()
    db.initialize()  # Sollte v31 -> aktuelles Schema migrieren
    conn = db.connect()
    row = conn.execute(
        "SELECT value FROM settings WHERE key='schema_version'"
    ).fetchone()
    assert row["value"] == str(SCHEMA_VERSION), (
        f"Schema-Version nach Migration: {row['value']}, erwartet {SCHEMA_VERSION}"
    )
    db.close()


def test_backup_created_before_migration(v169_data_dir):
    """Vor der Migration wird automatisch ein Backup angelegt."""
    data_dir, _ = v169_data_dir
    from bewerbungs_assistent.database import Database

    db = Database()
    db.initialize()
    db.close()

    backups = list((data_dir / "backups").glob("pbp-backup-*.db"))
    assert len(backups) >= 1, "Mindestens ein Backup haette angelegt werden sollen"
    # Das Backup ist eine valide v1.6.9-DB (Schema v31)
    bconn = sqlite3.connect(str(backups[0]))
    row = bconn.execute(
        "SELECT value FROM settings WHERE key='schema_version'"
    ).fetchone()
    bconn.close()
    assert row[0] == "31", f"Backup-Schema-Version: {row[0]}"


def test_v169_data_preserved(v169_data_dir):
    """Alle v1.6.9-Daten sind nach der Migration noch da."""
    data_dir, ids = v169_data_dir
    from bewerbungs_assistent.database import Database

    db = Database()
    db.initialize()
    conn = db.connect()

    # Profil
    p = conn.execute("SELECT * FROM profile WHERE id=?", (ids["pid"],)).fetchone()
    assert p is not None
    assert p["name"] == "Markus Mustermann"

    # Position
    pos = conn.execute(
        "SELECT * FROM positions WHERE id=?", (ids["position_id"],)
    ).fetchone()
    assert pos is not None
    assert pos["company"] == "Musterfirma Software GmbH"

    # Skill
    sk = conn.execute(
        "SELECT * FROM skills WHERE id=?", (ids["skill_id"],)
    ).fetchone()
    assert sk is not None
    assert sk["name"] == "Python"
    assert sk["start_year"] == 2008

    # Bewerbung
    app = conn.execute(
        "SELECT * FROM applications WHERE id=?", (ids["app_id"],)
    ).fetchone()
    assert app is not None
    assert app["company"] == "ACME"

    # Dokument
    doc = conn.execute(
        "SELECT * FROM documents WHERE id=?", (ids["doc_id"],)
    ).fetchone()
    assert doc is not None
    assert doc["filename"] == "lebenslauf-markus.pdf"

    # Follow-up
    fu = conn.execute(
        "SELECT * FROM follow_ups WHERE id=?", (ids["followup_id"],)
    ).fetchone()
    assert fu is not None
    assert fu["follow_up_type"] == "nachfass"

    db.close()


def test_v36_ba_url_migration_applied(v169_data_dir):
    """Die alte Bundesagentur-URL wurde von v36-Migration auf jobdetail/ umgestellt (#526)."""
    data_dir, ids = v169_data_dir
    from bewerbungs_assistent.database import Database

    db = Database()
    db.initialize()
    conn = db.connect()

    # Alte URL muss umgestellt sein
    old = conn.execute("SELECT url FROM jobs WHERE hash LIKE ?",
                       (f"%{ids['ba_old_hash']}%",)).fetchone()
    assert old is not None, "Bestand-Stelle ist verschwunden"
    assert "jobsuche/jobdetail/" in old["url"], (
        f"BA-URL wurde NICHT migriert: {old['url']}"
    )
    assert "jobsuche/suche?id=" not in old["url"]

    # Andere URLs (Indeed) bleiben unangetastet
    ok = conn.execute("SELECT url FROM jobs WHERE hash LIKE ?",
                      (f"%{ids['ok_hash']}%",)).fetchone()
    assert "indeed.com/viewjob?jk=abc" in ok["url"]
    db.close()


def test_v34_new_tables_exist_after_migration(v169_data_dir):
    """Neue Tabellen aus v32-v36 wurden angelegt — der User kann v1.7-Features nutzen."""
    data_dir, _ = v169_data_dir
    from bewerbungs_assistent.database import Database

    db = Database()
    db.initialize()
    conn = db.connect()

    expected_tables = [
        "contacts",            # v34 (#563)
        "contact_links",       # v34 (#563)
        "application_jobs",    # v34 (#472, n:m)
        "skill_periods",       # v34 (#572)
        "application_costs",   # v35 (#568)
        "document_versions",   # v33 (#577 stilarchiv)
    ]
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    actual = {r["name"] for r in cur}
    for tbl in expected_tables:
        assert tbl in actual, f"Tabelle '{tbl}' fehlt nach Migration"
    db.close()


def test_can_use_new_v17_features_after_migration(v169_data_dir):
    """Smoke-Test: Nach Migration koennen die neuen v1.7-Features genutzt werden."""
    data_dir, ids = v169_data_dir
    from bewerbungs_assistent.database import Database

    db = Database()
    db.initialize()

    # #572: Skill-Zeitraum hinzufuegen
    period_id = db.add_skill_period(
        ids["skill_id"], start_year=2018, end_year=2024,
        level=4, notes="Hauptsprache"
    )
    assert period_id

    # #563: Kontakt anlegen
    cid = db.add_contact({
        "full_name": "Anna Recruiter",
        "email": "anna@acme.com",
        "company": "ACME",
        "tags": ["recruiter"],
    })
    assert cid.startswith("CON-") or cid

    # #472: Bewerbung mit Stelle verknuepfen (n:m) — nur Smoke-Test
    pid = ids["pid"]
    full_hash = f"{pid}:{ids['ba_old_hash']}"
    conn = db.connect()
    conn.execute("UPDATE jobs SET hash=? WHERE hash=?", (full_hash, ids["ba_old_hash"]))
    conn.commit()
    db.link_application_to_job(ids["app_id"], full_hash)
    # Junction-Tabelle hat einen Eintrag fuer diese Bewerbung
    cnt = conn.execute(
        "SELECT COUNT(*) AS n FROM application_jobs WHERE application_id=?",
        (ids["app_id"],)
    ).fetchone()["n"]
    assert cnt >= 1, "n:m-Verknuepfung wurde nicht angelegt"

    db.close()
