"""PBP Bewerbungs-Assistent — Testversion Launcher.

Startet den Dashboard-Server auf Port 5173 mit Demo-Daten.
Funktioniert auf Windows und Linux.
"""
import os, sys, shutil, tempfile
from pathlib import Path

# Auto-detect project directory (where this script lives)
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR / "src"

# Use temp directory for test data
TEST_DIR = os.path.join(tempfile.gettempdir(), "pbp_testversion")
os.environ["BA_DATA_DIR"] = TEST_DIR

# Add src to path if not already installed as package
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))

# Zentrales Logging aktivieren
from bewerbungs_assistent.logging_config import setup_logging
setup_logging(console=True)

if os.path.exists(TEST_DIR):
    try:
        shutil.rmtree(TEST_DIR)
    except PermissionError:
        # Old test data may have locked files (WAL journal)
        print(f"[HINWEIS] Alte Testdaten konnten nicht geloescht werden: {TEST_DIR}")
        print("          Verwende vorhandene Datenbank weiter.")

from bewerbungs_assistent.database import Database
from bewerbungs_assistent.dashboard import start_dashboard

db = Database()
db.initialize()
print("[OK] Datenbank initialisiert")

# === Demo-Profil ===
db.save_profile({
    "name": "Max Mustermann",
    "email": "max@example.de",
    "phone": "+49 170 0000000",
    "city": "Hamburg",
    "plz": "20095",
    "country": "Deutschland",
    "summary": "Erfahrener IT-Fachmann mit Schwerpunkt Systemadministration, Projektmanagement und KI-Integration.",
})
print("[OK] Profil erstellt")

# Positionen
p1 = db.add_position({
    "company": "TechCorp GmbH",
    "title": "System Administrator & Entwickler",
    "start_date": "2024-01",
    "is_current": True,
    "description": "Administration von Linux-Servern mit KI-Integration",
    "technologies": "Python, FastAPI, PostgreSQL, Docker, Linux",
})
db.add_project(p1, {
    "name": "KI-Sprachassistent",
    "role": "Architekt & Entwickler",
    "duration": "12 Monate",
    "situation": "Bedarf an sprachgesteuertem Assistenten fuer das Unternehmen",
    "task": "Komplettsystem entwickeln: STT, LLM, TTS, Smart Client",
    "action": "Modulare Architektur mit FastAPI Backend und Raspberry Pi Client",
    "result": "Funktionsfaehiger Sprachassistent mit 10+ Modulen und Wake Word",
    "technologies": "Python, FastAPI, OpenAI, Whisper",
})

p2 = db.add_position({
    "company": "Beispiel AG",
    "title": "IT-Projektleiter",
    "start_date": "2020-06",
    "end_date": "2023-12",
    "description": "Leitung von IT-Infrastrukturprojekten",
    "technologies": "Linux, Docker, CI/CD, Jira",
})
print("[OK] Positionen erstellt")

# Ausbildung
db.add_education({
    "institution": "Technische Universitaet",
    "degree": "B.Sc.",
    "field_of_study": "Informatik",
    "start_date": "2015",
    "end_date": "2019",
})
db.add_education({
    "institution": "Online Academy",
    "degree": "Zertifikat",
    "field_of_study": "Cloud Architecture (AWS)",
})
print("[OK] Ausbildung erstellt")

# Skills
for name, cat, lvl in [
    ("Python", "Programmiersprache", 9),
    ("Linux Administration", "System", 8),
    ("FastAPI", "Framework", 8),
    ("PostgreSQL", "Datenbank", 7),
    ("Docker", "DevOps", 7),
    ("Git", "Tool", 8),
    ("Projektmanagement", "Methodik", 7),
    ("Deutsch", "Sprache", 10),
    ("Englisch", "Sprache", 8),
    ("Russisch", "Sprache", 6),
]:
    db.add_skill({"name": name, "category": cat, "level": lvl})
print("[OK] Skills erstellt")

# Demo-Jobs
from bewerbungs_assistent.job_scraper import stelle_hash
demo_jobs = [
    {
        "hash": stelle_hash("example.de", "Python Backend Developer"),
        "title": "Python Backend Developer (m/w/d)",
        "company": "TechStart GmbH",
        "location": "Hamburg",
        "url": "https://example.de/job/python-dev",
        "source": "demo",
        "description": "Wir suchen einen Python-Entwickler mit FastAPI-Erfahrung. Remote moeglich. Linux-Kenntnisse erwuenscht.",
        "remote_level": "hybrid",
        "distance_km": 15,
        "employment_type": "festanstellung",
        "salary_info": "60.000 - 80.000 EUR",
        "is_active": True,
        "found_at": "2026-02-25",
    },
    {
        "hash": stelle_hash("example.de", "DevOps Engineer"),
        "title": "DevOps Engineer — Kubernetes & CI/CD",
        "company": "CloudCorp AG",
        "location": "Berlin",
        "url": "https://example.de/job/devops",
        "source": "demo",
        "description": "DevOps mit Docker, Kubernetes, CI/CD Pipelines. Python oder Go.",
        "remote_level": "remote",
        "distance_km": 290,
        "employment_type": "festanstellung",
        "is_active": True,
        "found_at": "2026-02-24",
    },
    {
        "hash": stelle_hash("example.de", "IT-Projektleiter"),
        "title": "IT-Projektleiter (m/w/d) — Digitalisierung",
        "company": "MittelstandTech GmbH",
        "location": "Luebeck",
        "url": "https://example.de/job/pm",
        "source": "demo",
        "description": "Projektmanagement in der IT. Jira, agile Methoden, Linux-Infrastruktur.",
        "remote_level": "hybrid",
        "distance_km": 60,
        "employment_type": "festanstellung",
        "salary_info": "70.000 - 90.000 EUR",
        "is_active": True,
        "found_at": "2026-02-23",
    },
]
db.save_jobs(demo_jobs)
print(f"[OK] {len(demo_jobs)} Demo-Stellen erstellt")

# Suchkriterien setzen
db.set_search_criteria("keywords_muss", ["python", "linux"])
db.set_search_criteria("keywords_plus", ["fastapi", "docker", "projektmanagement", "devops"])
db.set_search_criteria("keywords_ausschluss", ["java", "c#", "sap"])
db.set_search_criteria("gewichtung", {"muss": 2, "plus": 1, "remote": 2, "naehe": 2, "fern_malus": 3})
print("[OK] Suchkriterien gesetzt")

# Scores berechnen
from bewerbungs_assistent.job_scraper import calculate_score
conn = db.connect()
criteria = db.get_search_criteria()
for job_row in conn.execute("SELECT * FROM jobs WHERE is_active = 1").fetchall():
    job = dict(job_row)
    score = calculate_score(job, criteria)
    conn.execute("UPDATE jobs SET score = ? WHERE hash = ?", (score, job["hash"]))
conn.commit()
print("[OK] Scores berechnet")

# Demo-Bewerbung
aid = db.add_application({
    "company": "TechStart GmbH",
    "title": "Python Backend Developer",
    "url": "https://example.de/job/python-dev",
    "status": "beworben",
    "job_hash": demo_jobs[0]["hash"],
})
db.update_application_status(aid, "interview", "Telefoninterview am 03.03.")
print(f"[OK] Demo-Bewerbung: {aid}")

print(f"\n{'='*60}")
print(f"  PBP Testversion bereit!")
print(f"  Daten: {TEST_DIR}")
print(f"  Dashboard: http://localhost:5173")
print(f"{'='*60}\n")

# Start dashboard
start_dashboard(db)
