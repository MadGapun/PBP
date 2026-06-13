"""Generalprobe Migration (#705) — Pflicht-Gate vor dem v1.7.0-Stable-Tag.

End-to-End-Beweis, dass das Update einer voll befuellten 1.6.x-DB (Schema v31,
wie es v1.6.9/v1.6.10-Endnutzer laufen haben) auf das aktuelle 1.7-Schema
KEINEN bestehenden Wert verliert:

  1. Eine realistische v1.6.x-DB anlegen: Profil mit ALLEN Feldern inkl.
     informal_notes/summary/phone/address, mehrere Bewerbungen mit Events,
     Meetings, Follow-ups, Dokumenten, Skills, Positionen, Projekt, Ausbildung.
  2. Vorher-Zustand erfassen: Zaehler pro Tabelle + voller Profil-Felder-Dump.
  3. Migration auf dieser (Wegwerf-)Kopie ausfuehren (BA_DATA_DIR-isoliert,
     NIE die echte User-DB).
  4. Nachher gegen Vorher pruefen: kein vorher-befuelltes Profilfeld ist leer,
     informal_notes intakt, alle Tabellen-Zaehler >= vorher, keine Waisen.

Plus: Pre-Migration-Backup ist garantiert (und ist die UNmigrierte v31-DB),
und ein fehlschlagendes Backup bricht die Migration HART ab (#705).

HARTE ISOLATIONS-REGEL (DB-Vorfall 2026-06-10): Jeder Test asserted, dass
db.db_path im Temp-Verzeichnis liegt. BA_DATA_DIR (NICHT PBP_DATA_DIR).
"""
import importlib
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest


# Tabellen, deren Datenbestand die Migration nie verkleinern darf.
_USER_TABLES = [
    "profile", "positions", "education", "projects", "skills", "jobs",
    "applications", "application_events", "application_meetings",
    "follow_ups", "documents",
]

# Profilfelder, die nach der Migration unveraendert befuellt sein muessen.
_PROFILE_FIELDS = [
    "name", "email", "phone", "address", "city", "plz", "country",
    "birthday", "nationality", "summary", "informal_notes",
]


def _create_full_v16x_db(db_path: Path) -> dict:
    """Legt eine voll befuellte v1.6.x-DB (Schema v31) an.

    Returns: erwartete Profil-Feldwerte + Tabellen-Zaehler fuer den Abgleich.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()
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
        CREATE TABLE education (
            id TEXT PRIMARY KEY, institution TEXT NOT NULL, degree TEXT,
            field_of_study TEXT, start_date TEXT, end_date TEXT,
            grade TEXT, description TEXT, profile_id TEXT
        );
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            position_id TEXT NOT NULL,
            name TEXT NOT NULL, description TEXT, role TEXT,
            situation TEXT, task TEXT, action TEXT, result TEXT,
            technologies TEXT, duration TEXT, customer_name TEXT,
            is_confidential INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
            start_date TEXT, end_date TEXT
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
            url TEXT, source TEXT, description TEXT, score INTEGER DEFAULT 0,
            remote_level TEXT DEFAULT 'unbekannt', distance_km REAL,
            salary_info TEXT, salary_min REAL, salary_max REAL, salary_type TEXT,
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
            ansprechpartner TEXT DEFAULT '', kontakt_email TEXT DEFAULT '',
            portal_name TEXT DEFAULT '', rejection_reason TEXT, fit_analyse TEXT,
            employment_type TEXT, source TEXT DEFAULT '',
            source_secondary TEXT DEFAULT '', vermittler TEXT DEFAULT '',
            endkunde TEXT DEFAULT '', description_snapshot TEXT,
            snapshot_date TEXT, gehaltsvorstellung TEXT DEFAULT '',
            final_salary TEXT DEFAULT '', has_reached_interview INTEGER DEFAULT 0,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE documents (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, filepath TEXT,
            doc_type TEXT DEFAULT 'sonstiges', extracted_text TEXT,
            linked_position_id TEXT, linked_application_id TEXT,
            profile_id TEXT, extraction_status TEXT DEFAULT 'nicht_extrahiert',
            last_extraction_at TEXT, content_hash TEXT, created_at TEXT
        );
        CREATE TABLE application_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT NOT NULL, status TEXT NOT NULL,
            event_date TEXT NOT NULL, notes TEXT,
            parent_event_id INTEGER
        );
        CREATE TABLE application_meetings (
            id TEXT PRIMARY KEY, application_id TEXT,
            title TEXT NOT NULL, meeting_date TEXT NOT NULL,
            meeting_type TEXT, location TEXT, status TEXT DEFAULT 'geplant',
            notes TEXT, created_at TEXT
        );
        CREATE TABLE follow_ups (
            id TEXT PRIMARY KEY, application_id TEXT NOT NULL,
            scheduled_date TEXT NOT NULL, follow_up_type TEXT DEFAULT 'nachfass',
            template TEXT, status TEXT DEFAULT 'geplant',
            created_at TEXT, completed_at TEXT
        );
        CREATE TABLE search_criteria (
            profile_id TEXT NOT NULL DEFAULT '', key TEXT NOT NULL,
            value TEXT, updated_at TEXT, PRIMARY KEY (profile_id, key)
        );
        CREATE TABLE blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL DEFAULT '', type TEXT NOT NULL,
            value TEXT NOT NULL, created_at TEXT
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
            value INTEGER, ignore_flag INTEGER DEFAULT 0, created_at TEXT,
            PRIMARY KEY (profile_id, dimension, sub_key)
        );
    """)
    cur.execute("INSERT INTO settings VALUES ('schema_version', '31')")

    pid = "prof-gp"
    profile = {
        "name": "Dr. Renate Vollprofil",
        "email": "renate@example.com",
        "phone": "+49 170 1234567",
        "address": "Beispielallee 42",
        "city": "Musterstadt",
        "plz": "54321",
        "country": "Oesterreich",          # bewusst NICHT der Default 'Deutschland'
        "birthday": "1975-07-09",
        "nationality": "deutsch",
        "summary": "Senior PLM-Beraterin mit 15 Jahren Erfahrung.",
        "informal_notes": (
            "Sucht Remote-Rolle, max 2 Tage Buero. Pferd, daher Land bevorzugt. "
            "Keine Zeitarbeit. Mag CONTACT/Windchill-Umfeld."
        ),
    }
    cur.execute(
        "INSERT INTO profile (id, name, email, phone, address, city, plz, "
        "country, birthday, nationality, summary, informal_notes, is_active, "
        "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,'2024-10-01T08:00:00')",
        (pid, profile["name"], profile["email"], profile["phone"],
         profile["address"], profile["city"], profile["plz"], profile["country"],
         profile["birthday"], profile["nationality"], profile["summary"],
         profile["informal_notes"]),
    )
    # 2 Positionen
    cur.executemany(
        "INSERT INTO positions (id, company, title, profile_id, start_date, created_at) "
        "VALUES (?,?,?,?,?, '2024-10-01T08:00:00')",
        [("pos-1", "CONTACT Software GmbH", "PLM Consultant", pid, "2015-01-01"),
         ("pos-2", "Maschinenbau AG", "CAx-Administrator", pid, "2009-01-01")],
    )
    # 1 Projekt (an Position gehaengt)
    cur.execute(
        "INSERT INTO projects (id, position_id, name, description, role, technologies) "
        "VALUES ('prj-1', 'pos-1', 'Windchill-Migration', 'PLM-Rollout', 'Lead', 'Windchill,Java')"
    )
    # 1 Ausbildung
    cur.execute(
        "INSERT INTO education (id, institution, degree, field_of_study, profile_id) "
        "VALUES ('edu-1', 'TU Musterstadt', 'Diplom', 'Maschinenbau', ?)", (pid,)
    )
    # 3 Skills
    cur.executemany(
        "INSERT INTO skills (id, name, category, level, profile_id, start_year) "
        "VALUES (?,?,?,?,?,?)",
        [("sk-1", "Windchill", "fachlich", 5, pid, 2010),
         ("sk-2", "Python", "fachlich", 4, pid, 2012),
         ("sk-3", "Projektleitung", "methodisch", 5, pid, 2014)],
    )
    # 2 Jobs
    cur.executemany(
        "INSERT INTO jobs (hash, title, company, source, url, profile_id, found_at) "
        "VALUES (?,?,?,?,?,?, '2025-03-01T08:00:00')",
        [("job-a", "PLM Manager", "ACME", "indeed", "https://indeed.com/viewjob?jk=a", pid),
         ("job-b", "CAx Lead", "Beta GmbH", "bundesagentur",
          "https://www.arbeitsagentur.de/jobsuche/suche?id=12634-BB-1-S", pid)],
    )
    # 2 Bewerbungen (verschiedene Status, eine abgelehnt)
    cur.executemany(
        "INSERT INTO applications (id, profile_id, title, company, status, "
        "notes, applied_at, created_at, has_reached_interview) VALUES "
        "(?,?,?,?,?,?, '2025-03-05T09:00:00', '2025-03-05T09:00:00', ?)",
        [("app-1", pid, "PLM Manager", "ACME", "interview",
          "Telefoninterview lief gut", 1),
         ("app-2", pid, "CAx Lead", "Beta GmbH", "abgelehnt",
          "Absage per Mail erhalten", 0)],
    )
    # Events
    cur.executemany(
        "INSERT INTO application_events (application_id, status, event_date, notes) "
        "VALUES (?,?,?,?)",
        [("app-1", "beworben", "2025-03-05", "Online beworben"),
         ("app-1", "interview", "2025-03-12", "Erstgespraech"),
         ("app-2", "beworben", "2025-03-06", None),
         ("app-2", "abgelehnt", "2025-03-20", "Standardabsage")],
    )
    # Meetings
    cur.executemany(
        "INSERT INTO application_meetings (id, application_id, title, meeting_date, "
        "meeting_type, notes, created_at) VALUES (?,?,?,?,?,?, '2025-03-10T10:00:00')",
        [("mtg-1", "app-1", "Erstgespraech", "2025-03-12T14:00:00", "interview",
          "Mit Teamleitung"),
         ("mtg-2", "app-1", "Zweitgespraech", "2025-03-19T10:00:00", "interview", "Fachteil")],
    )
    # Follow-ups
    cur.executemany(
        "INSERT INTO follow_ups (id, application_id, scheduled_date, follow_up_type, "
        "template, status, created_at) VALUES (?,?,?,?,?,?, '2025-03-05T09:00:00')",
        [("fu-1", "app-1", "2025-03-26", "nachfass", "Nachfrage Stand?", "geplant"),
         ("fu-2", "app-2", "2025-03-13", "nachfass", "Erinnerung", "erledigt")],
    )
    # Dokumente
    cur.executemany(
        "INSERT INTO documents (id, filename, doc_type, profile_id, "
        "linked_application_id, created_at) VALUES (?,?,?,?,?, '2025-03-05T09:00:00')",
        [("doc-1", "Lebenslauf_Renate.pdf", "lebenslauf", pid, "app-1"),
         ("doc-2", "Anschreiben_ACME.pdf", "anschreiben", pid, "app-1")],
    )

    conn.commit()
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in _USER_TABLES}
    conn.close()
    return {"pid": pid, "profile": profile, "counts": counts}


@pytest.fixture
def full_v16x_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_gp_705_")
    data_dir = Path(tmpdir) / "data"
    data_dir.mkdir()
    db_path = data_dir / "pbp.db"
    expected = _create_full_v16x_db(db_path)
    os.environ["BA_DATA_DIR"] = str(data_dir)
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    yield data_dir, db_path, expected, _db_mod
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_generalprobe_kein_datenverlust(full_v16x_env):
    """Volle 1.6.x-DB -> aktuelles Schema: kein Profilfeld leer, alle Zaehler >= vorher."""
    data_dir, db_path, expected, _db_mod = full_v16x_env
    from bewerbungs_assistent.database import Database, SCHEMA_VERSION

    db = Database()
    # Isolations-Wachhund
    assert str(data_dir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"

    db.initialize()  # fuehrt Migration v31 -> SCHEMA_VERSION durch
    conn = db.connect()

    # Schema hochgezogen
    sv = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
    assert sv["value"] == str(SCHEMA_VERSION)

    # --- Profilfelder: jedes vorher befuellte Feld ist nachher identisch ---
    p = conn.execute("SELECT * FROM profile WHERE id=?", (expected["pid"],)).fetchone()
    assert p is not None, "Profil verschwunden"
    for field in _PROFILE_FIELDS:
        before = expected["profile"][field]
        after = p[field]
        assert after == before, (
            f"Profilfeld '{field}' veraendert: vorher {before!r}, nachher {after!r}"
        )
    # informal_notes besonders hart pruefen
    assert "Pferd" in p["informal_notes"]
    assert p["country"] == "Oesterreich"  # nicht-Default-Land erhalten

    # --- Tabellen-Zaehler: nachher >= vorher fuer jede User-Tabelle ---
    for table, before in expected["counts"].items():
        after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert after >= before, (
            f"Tabelle '{table}' hat Daten verloren: vorher {before}, nachher {after}"
        )

    # --- keine Waisen: jedes Event/Meeting/Follow-up/Doc zeigt auf eine Bewerbung ---
    orphan_events = conn.execute(
        "SELECT COUNT(*) FROM application_events e "
        "WHERE e.application_id NOT IN (SELECT id FROM applications)"
    ).fetchone()[0]
    assert orphan_events == 0, "verwaiste application_events nach Migration"
    orphan_mtg = conn.execute(
        "SELECT COUNT(*) FROM application_meetings m "
        "WHERE m.application_id NOT IN (SELECT id FROM applications)"
    ).fetchone()[0]
    assert orphan_mtg == 0, "verwaiste application_meetings nach Migration"

    db.close()


def test_generalprobe_backup_ist_unmigrierte_v31(full_v16x_env):
    """Das Pre-Migration-Backup existiert und ist die UNveraenderte v31-DB."""
    data_dir, db_path, expected, _db_mod = full_v16x_env
    from bewerbungs_assistent.database import Database

    db = Database()
    db.initialize()
    db.close()

    backups = list((data_dir / "backups").glob("pbp-backup-*.db"))
    assert backups, "kein Pre-Migration-Backup angelegt"
    bconn = sqlite3.connect(str(backups[0]))
    sv = bconn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0]
    # voller Profil-Bestand auch im Backup
    notes = bconn.execute(
        "SELECT informal_notes FROM profile WHERE id=?", (expected["pid"],)
    ).fetchone()[0]
    bconn.close()
    assert sv == "31", f"Backup ist nicht die v31-Vorlage (schema_version={sv})"
    assert "Pferd" in notes, "informal_notes fehlt im Backup"


def test_705_backup_fehlschlag_bricht_migration_hart_ab(full_v16x_env, monkeypatch):
    """Schlaegt das Pre-Migration-Backup fehl, wird HART abgebrochen statt
    ohne Sicherheitsnetz zu migrieren — und die DB bleibt auf v31."""
    data_dir, db_path, expected, _db_mod = full_v16x_env
    from bewerbungs_assistent.database import Database

    def _boom(*a, **k):
        raise OSError("Kein Speicherplatz (simuliert)")

    monkeypatch.setattr(_db_mod, "create_backup", _boom)

    db = Database()
    with pytest.raises(RuntimeError, match="Backup fehlgeschlagen"):
        db.initialize()
    db.close()

    # DB darf NICHT migriert sein — schema_version unveraendert v31
    raw = sqlite3.connect(str(db_path))
    sv = raw.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0]
    notes = raw.execute(
        "SELECT informal_notes FROM profile WHERE id=?", (expected["pid"],)
    ).fetchone()[0]
    raw.close()
    assert sv == "31", f"Migration lief trotz Backup-Fehler (schema_version={sv})"
    assert "Pferd" in notes, "Daten beschaedigt trotz Abbruch"


def test_705_export_import_roundtrip_inkl_informal_notes(full_v16x_env):
    """profil_exportieren -> importieren bewahrt ALLE Profilfelder inkl.
    informal_notes (Sicherheitsnetz fuer Wiederherstellung)."""
    data_dir, db_path, expected, _db_mod = full_v16x_env
    from bewerbungs_assistent.database import Database

    db = Database()
    db.initialize()

    exported = db.export_profile_json()
    assert exported is not None
    # Export enthaelt alle kritischen Felder
    for field in _PROFILE_FIELDS:
        assert exported.get(field) == expected["profile"][field], (
            f"Export-Feld '{field}' weicht ab"
        )
    assert exported["positions"], "Positionen fehlen im Export"
    assert exported["skills"], "Skills fehlen im Export"

    # Re-Import legt ein neues Profil an, das alle Felder traegt
    new_pid = db.import_profile_json(dict(exported))
    assert new_pid
    reimported = db.export_profile_json(new_pid)
    for field in _PROFILE_FIELDS:
        assert reimported.get(field) == expected["profile"][field], (
            f"Re-Import-Feld '{field}' verloren"
        )
    assert "Pferd" in reimported["informal_notes"]
    db.close()
