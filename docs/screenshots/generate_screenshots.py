#!/usr/bin/env python3
"""Generiert Dashboard-Screenshots mit Demo-Daten fuer die GitHub-Dokumentation.

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
    """Erstellt realistische Demo-Daten fuer Screenshots."""

    # Profil
    db.save_profile({
        "name": "Max Mustermann",
        "email": "max.mustermann@example.com",
        "phone": "+49 40 12345678",
        "address": "Musterweg 42",
        "city": "Hamburg",
        "postal_code": "20099",
        "summary": (
            "Erfahrener IT-Projektmanager mit 15+ Jahren Expertise in PLM/PDM-Systemen, "
            "SAP-Integration und agiler Transformation. Schwerpunkte: Windchill, PRO.FILE, "
            "Multi-Site-Rollouts und Change Management."
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
        "title": "Senior PLM Consultant",
        "start_date": "2019-04",
        "end_date": None,
        "description": "Leitung von PLM-Migrationsprojekten und Architekturberatung.",
    })
    db.add_position({
        "company": "TechVision AG",
        "title": "IT-Projektmanager",
        "start_date": "2014-01",
        "end_date": "2019-03",
        "description": "SAP-ERP-Integration und Prozessautomatisierung.",
    })
    db.add_position({
        "company": "DataSoft Solutions",
        "title": "Systems Engineer",
        "start_date": "2009-06",
        "end_date": "2013-12",
        "description": "CAD/CAM-Systemadministration und Customizing.",
    })

    # Skills
    for skill_name, cat in [
        ("Windchill", "tool"), ("PRO.FILE", "tool"), ("SAP ECTR", "tool"),
        ("Python", "programmiersprache"), ("SQL", "programmiersprache"),
        ("Projektmanagement", "methodik"), ("Agile/Scrum", "methodik"),
        ("ITIL", "methodik"), ("Change Management", "soft_skill"),
        ("Stakeholder-Kommunikation", "soft_skill"),
    ]:
        db.add_skill({"name": skill_name, "category": cat})

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
        "keywords_muss": ["PLM", "PDM", "Windchill", "Projektmanager"],
        "keywords_plus": ["SAP", "Python", "Agile", "Remote"],
        "keywords_ausschluss": ["Junior", "Praktikum", "Werkstudent"],
        "regionen": ["Hamburg", "Remote"],
        "umkreis_km": 50,
    })

    # Aktive Quellen
    db.set_setting("active_sources", ["bundesagentur", "stepstone", "hays"])
    db.set_setting("last_search_at", datetime.now().isoformat())

    # Jobs
    now = datetime.now()
    jobs = [
        {
            "title": "Senior PLM Consultant (Windchill)",
            "company": "Siemens Digital Industries",
            "location": "Hamburg (Hybrid)",
            "url": "https://example.com/job/1",
            "source": "stepstone",
            "description": "Wir suchen einen erfahrenen PLM Consultant mit Windchill-Expertise fuer unsere Kunden im Maschinenbau. Erfahrung mit SAP-Integration von Vorteil.",
            "salary_min": 80000, "salary_max": 95000, "salary_type": "yearly",
            "employment_type": "festanstellung", "remote_level": "hybrid",
            "score": 92, "found_at": (now - timedelta(days=1)).isoformat(),
        },
        {
            "title": "IT-Projektmanager PLM/PDM",
            "company": "Airbus Operations GmbH",
            "location": "Hamburg-Finkenwerder",
            "url": "https://example.com/job/2",
            "source": "bundesagentur",
            "description": "Leitung von PLM-Migrationsprojekten im Bereich Flugzeugbau. Erfahrung mit agilen Methoden und Change Management erforderlich.",
            "salary_min": 85000, "salary_max": 100000, "salary_type": "yearly",
            "employment_type": "festanstellung", "remote_level": "onsite",
            "score": 88, "found_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "title": "PDM Architect PRO.FILE",
            "company": "PROCAD GmbH & Co. KG",
            "location": "Remote / Karlsruhe",
            "url": "https://example.com/job/3",
            "source": "hays",
            "description": "Architekturberatung und Implementierung von PRO.FILE PDM-Loesungen. Python-Kenntnisse fuer Automatisierung erwuenscht.",
            "salary_min": 75000, "salary_max": 90000, "salary_type": "yearly",
            "employment_type": "festanstellung", "remote_level": "remote",
            "score": 85, "found_at": (now - timedelta(days=3)).isoformat(),
        },
        {
            "title": "Systemadministrator CAD/PLM",
            "company": "MAN Energy Solutions",
            "location": "Hamburg",
            "url": "https://example.com/job/4",
            "source": "stepstone",
            "description": "Administration und Weiterentwicklung der CAD/PLM-Infrastruktur.",
            "salary_min": 60000, "salary_max": 72000, "salary_type": "yearly",
            "employment_type": "festanstellung", "remote_level": "onsite",
            "score": 65, "found_at": (now - timedelta(days=5)).isoformat(),
        },
    ]
    # save_jobs erwartet eine Liste mit hash-Feld
    import hashlib
    for job in jobs:
        job["hash"] = hashlib.md5(job["url"].encode()).hexdigest()[:12]
    db.save_jobs(jobs)

    # Bewerbungen (add_application erstellt automatisch ein erstes Event)
    app1_id = db.add_application({
        "title": "Senior PLM Consultant (Windchill)",
        "company": "Siemens Digital Industries",
        "status": "beworben",
        "applied_at": (now - timedelta(days=10)).date().isoformat(),
        "notes": "Bewerbung ueber StepStone, Anschreiben personalisiert.",
    })
    db.update_application_status(app1_id, "eingeladen", "Einladung zum Erstgespraech am 20.03.")

    app2_id = db.add_application({
        "title": "IT-Projektmanager PLM/PDM",
        "company": "Airbus Operations GmbH",
        "status": "beworben",
        "applied_at": (now - timedelta(days=5)).date().isoformat(),
    })

    app3_id = db.add_application({
        "title": "PLM Engineer",
        "company": "Daimler Truck AG",
        "status": "beworben",
        "applied_at": (now - timedelta(days=30)).date().isoformat(),
    })
    db.update_application_status(app3_id, "abgelehnt", "Absage erhalten", "Stelle intern besetzt")

    # Follow-up
    db.add_follow_up(app2_id, (now + timedelta(days=3)).date().isoformat())


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


def _take_screenshots(port: int, output_dir: Path):
    """Nimmt Screenshots aller Dashboard-Tabs."""
    from playwright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{port}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # Tab-Mapping: (tab_id, filename, description)
        tabs = [
            (None, "01_dashboard.png", "Dashboard-Uebersicht"),
            ("profil", "02_profil.png", "Profil-Tab"),
            ("stellen", "03_stellen.png", "Stellen-Tab"),
            ("bewerbungen", "04_bewerbungen.png", "Bewerbungen-Tab"),
            ("einstellungen", "05_einstellungen.png", "Einstellungen-Tab"),
        ]

        for tab_id, filename, desc in tabs:
            url = base if tab_id is None else f"{base}#{tab_id}"
            page.goto(url)
            page.wait_for_load_state("networkidle")
            time.sleep(1)  # Extra wait for JS rendering

            if tab_id:
                # Click tab to trigger JS navigation
                try:
                    page.click(f'[data-tab="{tab_id}"]', timeout=3000)
                    page.wait_for_load_state("networkidle")
                    time.sleep(0.5)
                except Exception:
                    pass

            path = output_dir / filename
            page.screenshot(path=str(path), full_page=False)
            print(f"  Screenshot: {path.name} ({desc})")

        browser.close()


def main():
    print("PBP Screenshot-Generator")
    print("=" * 40)

    # Temp-DB mit Demo-Daten
    tmp_dir = tempfile.mkdtemp(prefix="pbp_screenshots_")
    db_path = os.path.join(tmp_dir, "pbp.db")

    print(f"1. Erstelle Demo-Datenbank: {db_path}")
    db = Database(db_path=db_path)
    db.initialize()
    _create_demo_data(db)
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

    # Screenshots
    print("3. Erstelle Screenshots...")
    _take_screenshots(PORT, SCREENSHOT_DIR)

    print(f"\nFertig! Screenshots in: {SCREENSHOT_DIR}")
    print("Dateien:")
    for f in sorted(SCREENSHOT_DIR.glob("*.png")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
