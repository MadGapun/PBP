#!/usr/bin/env python3
"""Generiert Dashboard-Screenshots mit Demo-Daten für die GitHub-Dokumentation.

Verwendung:
    python docs/screenshots/generate_screenshots.py

Voraussetzungen:
    pip install playwright
    playwright install chromium
"""

import os
import sys
import time
import threading
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from bewerbungs_assistent.database import Database


SCREENSHOT_DIR = Path(__file__).resolve().parent
PORT = 8299  # Separate port to avoid conflicts


def _create_demo_data(db: Database):
    """Erstellt realistische Demo-Daten für Screenshots."""

    # Profil
    db.save_profile({
        "name": "Max Mustermann",
        "email": "max.mustermann@example.com",
        "phone": "+49 40 12345678",
        "address": "Musterweg 42",
        "city": "Hamburg",
        "postal_code": "20099",
        "summary": (
            "Erfahrener IT-Projektmanager mit 15+ Jahren Expertise in Software-Architektur, "
            "Cloud-Migration und agiler Transformation. Schwerpunkte: Microservices, DevOps, "
            "Enterprise-Integration und Change Management."
        ),
        "preferences": {
            "stellentyp": "festanstellung",
            "arbeitsmodell": "hybrid",
            "min_gehalt": 75000,
            "ziel_gehalt": 90000,
            "regionen": ["Hamburg", "Remote"],
        },
    })

    # Positionen
    db.add_position({
        "company": "ACME Engineering GmbH",
        "title": "Senior Software Architect",
        "start_date": "2019-04",
        "end_date": None,
        "description": "Leitung von Cloud-Migrationsprojekten und Architekturberatung.",
    })
    db.add_position({
        "company": "TechVision AG",
        "title": "IT-Projektmanager",
        "start_date": "2014-01",
        "end_date": "2019-03",
        "description": "Enterprise-Integration und Prozessautomatisierung.",
    })
    db.add_position({
        "company": "DataSoft Solutions",
        "title": "Software Engineer",
        "start_date": "2009-06",
        "end_date": "2013-12",
        "description": "Backend-Entwicklung und API-Design.",
    })

    # Skills mit Level und Kategorie
    for skill_name, cat, level in [
        ("Python", "programmiersprache", 5), ("TypeScript", "programmiersprache", 4),
        ("Java", "programmiersprache", 4), ("SQL", "programmiersprache", 4),
        ("Go", "programmiersprache", 2),
        ("Docker", "tool", 5), ("Kubernetes", "tool", 4), ("Terraform", "tool", 3),
        ("AWS", "tool", 4), ("PostgreSQL", "tool", 4),
        ("Projektmanagement", "methodik", 5), ("Agile/Scrum", "methodik", 4),
        ("CI/CD", "methodik", 4), ("ITIL", "methodik", 3),
        ("Change Management", "soft_skill", 5),
        ("Stakeholder-Kommunikation", "soft_skill", 4),
        ("Englisch C1", "sprache", 4), ("Deutsch Muttersprache", "sprache", 5),
    ]:
        db.add_skill({"name": skill_name, "category": cat, "level": level})

    # Ausbildung
    db.add_education({
        "institution": "TU Hamburg",
        "degree": "Diplom-Informatiker",
        "field": "Wirtschaftsinformatik",
        "start_date": "2003",
        "end_date": "2008",
    })

    # Suchkriterien
    db.set_setting("search_criteria", {
        "keywords_muss": ["Software Architect", "Projektmanager", "DevOps"],
        "keywords_plus": ["Python", "Cloud", "Agile", "Remote"],
        "keywords_ausschluss": ["Junior", "Praktikum", "Werkstudent"],
        "regionen": ["Hamburg", "Remote"],
        "umkreis_km": 50,
    })

    # Aktive Quellen
    db.set_setting("active_sources", ["bundesagentur", "stepstone", "hays"])
    db.set_setting("last_search_at", datetime.now().isoformat())

    # Jobs — Mix aus Festanstellung und Freelance für Split-View
    now = datetime.now()
    jobs = [
        {
            "title": "Senior Software Architect (Cloud)",
            "company": "TechCorp GmbH",
            "location": "Hamburg (Hybrid)",
            "url": "https://example.com/job/1",
            "source": "stepstone",
            "description": "Wir suchen einen erfahrenen Software Architect mit Cloud-Expertise für unsere Microservices-Plattform. Erfahrung mit AWS und Kubernetes von Vorteil.",
            "salary_min": 80000, "salary_max": 95000, "salary_type": "yearly",
            "employment_type": "festanstellung", "remote_level": "hybrid",
            "score": 92, "found_at": (now - timedelta(days=1)).isoformat(),
        },
        {
            "title": "IT-Projektmanager Digitalisierung",
            "company": "NovaTech Industries AG",
            "location": "Hamburg-Altona",
            "url": "https://example.com/job/2",
            "source": "bundesagentur",
            "description": "Leitung von Digitalisierungsprojekten im Enterprise-Umfeld. Erfahrung mit agilen Methoden und Change Management erforderlich.",
            "salary_min": 85000, "salary_max": 100000, "salary_type": "yearly",
            "employment_type": "festanstellung", "remote_level": "onsite",
            "score": 88, "found_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "title": "Platform Engineer (Kubernetes)",
            "company": "CloudWorks GmbH",
            "location": "Remote / Berlin",
            "url": "https://example.com/job/3",
            "source": "hays",
            "description": "Aufbau und Betrieb einer Container-Plattform. Python-Kenntnisse für Automatisierung erwünscht.",
            "salary_min": 75000, "salary_max": 90000, "salary_type": "yearly",
            "employment_type": "festanstellung", "remote_level": "remote",
            "score": 85, "found_at": (now - timedelta(days=3)).isoformat(),
        },
        {
            "title": "DevOps Engineer",
            "company": "DataStream Solutions",
            "location": "Hamburg",
            "url": "https://example.com/job/4",
            "source": "stepstone",
            "description": "CI/CD-Pipelines und Infrastructure-as-Code mit Terraform und AWS.",
            "salary_min": 60000, "salary_max": 72000, "salary_type": "yearly",
            "employment_type": "festanstellung", "remote_level": "onsite",
            "score": 65, "found_at": (now - timedelta(days=5)).isoformat(),
        },
        # Freelance-Stellen für Split-View
        {
            "title": "Cloud Migration Architect",
            "company": "InnoConsult AG",
            "location": "Remote",
            "url": "https://example.com/job/5",
            "source": "freelancermap",
            "description": "6-Monats-Projekt: Migration von On-Premise auf AWS. Erfahrung mit Multi-Account-Architektur erforderlich.",
            "salary_min": 850, "salary_max": 950, "salary_type": "taeglich",
            "employment_type": "freelance", "remote_level": "remote",
            "score": 90, "found_at": (now - timedelta(days=1)).isoformat(),
        },
        {
            "title": "Backend-Entwickler Python/FastAPI",
            "company": "CodeForge GmbH",
            "location": "Stuttgart (Hybrid)",
            "url": "https://example.com/job/6",
            "source": "freelance_de",
            "description": "API-Entwicklung für Fintech-Startup. 3 Monate, Verlängerung möglich.",
            "salary_min": 800, "salary_max": 900, "salary_type": "taeglich",
            "employment_type": "freelance", "remote_level": "hybrid",
            "score": 78, "found_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "title": "Projektleiter Digitaler Zwilling",
            "company": "EngSmart Consulting",
            "location": "München",
            "url": "https://example.com/job/7",
            "source": "freelancermap",
            "description": "Aufbau Digital-Twin-Strategie für Industrie-Konzern. Cloud-Erfahrung zwingend.",
            "salary_min": 900, "salary_max": 1050, "salary_type": "taeglich",
            "employment_type": "freelance", "remote_level": "onsite",
            "score": 72, "found_at": (now - timedelta(days=4)).isoformat(),
        },
    ]
    # save_jobs erwartet eine Liste mit hash-Feld
    import hashlib
    for job in jobs:
        job["hash"] = hashlib.md5(job["url"].encode()).hexdigest()[:12]
    db.save_jobs(jobs)

    # Bewerbungen (add_application erstellt automatisch ein erstes Event)
    app1_id = db.add_application({
        "title": "Senior Software Architect (Cloud)",
        "company": "TechCorp GmbH",
        "status": "beworben",
        "applied_at": (now - timedelta(days=10)).date().isoformat(),
        "notes": "Bewerbung über StepStone, Anschreiben personalisiert.",
    })
    db.update_application_status(app1_id, "eingeladen", "Einladung zum Erstgespräch am 20.03.")

    app2_id = db.add_application({
        "title": "IT-Projektmanager Digitalisierung",
        "company": "NovaTech Industries AG",
        "status": "beworben",
        "applied_at": (now - timedelta(days=5)).date().isoformat(),
    })

    app3_id = db.add_application({
        "title": "Full-Stack Developer",
        "company": "WebScale AG",
        "status": "beworben",
        "applied_at": (now - timedelta(days=30)).date().isoformat(),
    })
    db.update_application_status(app3_id, "abgelehnt", "Absage erhalten", "Stelle intern besetzt")

    app4_id = db.add_application({
        "title": "Platform Engineer (Kubernetes)",
        "company": "CloudWorks GmbH",
        "status": "beworben",
        "applied_at": (now - timedelta(days=3)).date().isoformat(),
        "notes": "Initiativbewerbung nach Empfehlung von Ex-Kollege.",
    })

    app5_id = db.add_application({
        "title": "Cloud Migration Architect",
        "company": "InnoConsult AG",
        "status": "beworben",
        "applied_at": (now - timedelta(days=20)).date().isoformat(),
    })
    db.update_application_status(app5_id, "eingeladen", "Technisches Interview am 18.03.")
    db.update_application_status(app5_id, "verhandlung", "Angebot: 900 EUR/Tag, 6 Monate")

    # Follow-ups
    db.add_follow_up(app2_id, (now + timedelta(days=3)).date().isoformat())
    db.add_follow_up(app4_id, (now + timedelta(days=7)).date().isoformat())

    # Meetings fuer Kalender-Tab
    db.add_meeting({
        "application_id": app1_id,
        "title": "Erstgespraech TechCorp",
        "meeting_date": (now + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00"),
        "meeting_url": "https://teams.microsoft.com/l/meetup-join/demo",
        "platform": "teams",
        "duration_minutes": 60,
    })
    db.add_meeting({
        "application_id": app5_id,
        "title": "Technisches Interview InnoConsult",
        "meeting_date": (now + timedelta(days=5)).strftime("%Y-%m-%dT14:00:00"),
        "meeting_url": "https://zoom.us/j/demo",
        "platform": "zoom",
        "duration_minutes": 90,
    })
    db.add_meeting({
        "application_id": None,
        "title": "Netzwerk-Treffen IT Hamburg",
        "meeting_date": (now + timedelta(days=10)).strftime("%Y-%m-%dT18:00:00"),
        "is_private": True,
        "duration_minutes": 120,
    })

    # Demo-Dokument
    db.add_document({
        "filename": "Lebenslauf_Max_Mustermann.pdf",
        "filepath": "/tmp/demo_cv.pdf",
        "doc_type": "lebenslauf",
        "extracted_text": "Senior Software Architect mit 15 Jahren Erfahrung...",
        "extraction_status": "analysiert",
    })


def _start_dashboard(db_path: str, port: int):
    """Startet das Dashboard als Hintergrund-Thread."""
    import uvicorn
    os.environ["BA_DATA_DIR"] = str(Path(db_path).parent)
    os.environ["BA_DASHBOARD_PORT"] = str(port)

    from bewerbungs_assistent.dashboard import app, start_dashboard
    start_dashboard(Database(db_path=db_path))

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def _dismiss_toasts(page):
    """Entfernt Toast-Benachrichtigungen vor dem Screenshot."""
    for _ in range(5):
        try:
            close_btns = page.locator("[class*='toast'] button, [class*='Toast'] button, [role='alert'] button")
            if close_btns.count() > 0:
                for i in range(close_btns.count()):
                    close_btns.nth(i).click(timeout=500)
                time.sleep(0.3)
        except Exception:
            pass
    page.evaluate("""
        document.querySelectorAll('[class*="toast"], [class*="Toast"], [role="alert"], [role="status"]')
            .forEach(el => el.remove());
    """)
    time.sleep(0.3)


def _screenshot(page, url, output_path, desc):
    """Navigiert zu URL und macht einen Screenshot."""
    page.goto(url)
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    _dismiss_toasts(page)
    page.screenshot(path=str(output_path), full_page=False)
    print(f"  Screenshot: {output_path.name} ({desc})")


def _take_screenshots(port: int, output_dir: Path):
    """Nimmt Screenshots aller Dashboard-Tabs."""
    from playwright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{port}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        tabs = [
            ("dashboard", "01_dashboard.png", "Dashboard-\u00dcbersicht"),
            ("profil", "02_profil.png", "Profil-Tab"),
            ("stellen", "03_stellen.png", "Stellen-Tab"),
            ("bewerbungen", "04_bewerbungen.png", "Bewerbungen-Tab"),
            ("dokumente", "05_dokumente.png", "Dokumente-Tab"),
            ("kalender", "06_kalender.png", "Kalender-Tab"),
            ("statistiken", "07_statistiken.png", "Statistiken-Tab"),
            ("einstellungen", "08_einstellungen.png", "Einstellungen-Tab"),
        ]

        for hash_id, filename, desc in tabs:
            _screenshot(page, f"{base}#{hash_id}", output_dir / filename, desc)

        browser.close()


def _take_onboarding_screenshots(port: int, output_dir: Path, db_path: str):
    """Nimmt Screenshots fuer verschiedene Onboarding-Zustaende."""
    from playwright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{port}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # --- Phase 1: Leere DB = Willkommensbildschirm ---
        print("\n  Phase 1: Neuer User (kein Profil)")
        _screenshot(page, f"{base}#dashboard",
                    output_dir / "00_willkommen.png",
                    "Willkommen — erster Start")

        # --- Phase 2: Profil unvollstaendig (nur Name, keine Skills/Positionen) ---
        print("  Phase 2: Profil unvollstaendig")
        db = Database(db_path=db_path)
        db.initialize()
        db.save_profile({
            "name": "Heike Mustermann",
            "email": "heike@example.com",
            "summary": "",
        })
        db.close()
        time.sleep(0.5)

        _screenshot(page, f"{base}#dashboard",
                    output_dir / "00b_profil_unvollstaendig.png",
                    "Dashboard — Profil unvollst\u00e4ndig")

        # --- Phase 3: Profil vollstaendig, mit Stellen + Bewerbungen ---
        print("  Phase 3: Profil vollstaendig (Demo-Daten)")
        db = Database(db_path=db_path)
        db.initialize()
        # Loesche das minimale Profil und lade die vollen Demo-Daten
        conn = db.connect()
        for tbl in ["positions", "skills", "education", "documents", "profile"]:
            try:
                conn.execute(f"DELETE FROM {tbl}")
            except Exception:
                pass
        conn.commit()
        _create_demo_data(db)
        db.close()
        time.sleep(0.5)

        _screenshot(page, f"{base}#dashboard",
                    output_dir / "00c_dashboard_vollstaendig.png",
                    "Dashboard — Profil vollst\u00e4ndig, aktive Bewerbungen")

        browser.close()


def main():
    print("PBP Screenshot-Generator")
    print("=" * 40)

    # Temp-DB — startet LEER fuer Onboarding-Screenshots
    tmp_dir = tempfile.mkdtemp(prefix="pbp_screenshots_")
    db_path = os.path.join(tmp_dir, "pbp.db")

    print(f"1. Erstelle leere Datenbank: {db_path}")
    db = Database(db_path=db_path)
    db.initialize()
    db.close()

    # Dashboard starten
    print(f"2. Starte Dashboard auf Port {PORT}...")
    server_thread = threading.Thread(
        target=_start_dashboard,
        args=(db_path, PORT),
        daemon=True,
    )
    server_thread.start()
    time.sleep(3)  # Wait for server startup

    # Onboarding-Screenshots (leer -> unvollstaendig -> vollstaendig)
    print("3. Erstelle Onboarding-Screenshots (3 Zustaende)...")
    _take_onboarding_screenshots(PORT, SCREENSHOT_DIR, db_path)

    # Vollstaendige Tab-Screenshots (DB hat jetzt Demo-Daten)
    print("4. Erstelle Tab-Screenshots...")
    _take_screenshots(PORT, SCREENSHOT_DIR)

    print(f"\nFertig! Screenshots in: {SCREENSHOT_DIR}")
    print("Dateien:")
    for f in sorted(SCREENSHOT_DIR.glob("*.png")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
