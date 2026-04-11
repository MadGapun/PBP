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
    """Erstellt realistische Demo-Daten fuer Screenshots — Medienkauffrau-Profil."""

    now = datetime.now()
    import hashlib

    # ── Profil: Lisa Berger, Medienkauffrau ──
    db.save_profile({
        "name": "Lisa Berger",
        "email": "lisa.berger@example.com",
        "phone": "+49 221 9876543",
        "address": "Lindenallee 8",
        "city": "Koeln",
        "postal_code": "50667",
        "summary": (
            "Medienkauffrau Digital & Print mit 8 Jahren Erfahrung in Verlagen und Agenturen. "
            "Schwerpunkte: Mediaplanung, Kampagnensteuerung, Anzeigenverkauf und "
            "Social-Media-Marketing. Erfahrung mit Programmatic Advertising und Datenanalyse."
        ),
        "preferences": {
            "stellentyp": "festanstellung",
            "arbeitsmodell": "hybrid",
            "min_gehalt": 42000,
            "ziel_gehalt": 52000,
            "regionen": ["Koeln", "Duesseldorf", "Remote"],
        },
    })

    # ── Positionen ──
    db.add_position({
        "company": "Rheinland Medien GmbH",
        "title": "Senior Media Plannerin",
        "start_date": "2021-03",
        "end_date": None,
        "description": "Strategische Mediaplanung fuer Großkunden. Budgetverantwortung 2 Mio EUR/Jahr. Einfuehrung von Programmatic Advertising.",
    })
    db.add_position({
        "company": "Stadtanzeiger Verlag",
        "title": "Medienkauffrau Digital & Print",
        "start_date": "2018-01",
        "end_date": "2021-02",
        "description": "Anzeigenverkauf, Kundenpflege und Cross-Media-Kampagnen fuer regionale und ueberregionale Kunden.",
    })
    db.add_position({
        "company": "Kreativfunke Agentur",
        "title": "Junior Account Managerin",
        "start_date": "2016-08",
        "end_date": "2017-12",
        "description": "Kampagnenkoordination, Briefing-Erstellung und Social-Media-Betreuung fuer mittelstaendische Kunden.",
    })
    db.add_position({
        "company": "Stadtanzeiger Verlag",
        "title": "Auszubildende Medienkauffrau",
        "start_date": "2013-09",
        "end_date": "2016-07",
        "description": "Duale Ausbildung: Anzeigendisposition, Medienrecht, Kalkulation, Kundenberatung.",
    })

    # ── Skills ──
    for skill_name, cat, level in [
        ("Mediaplanung", "methodik", 5), ("Kampagnensteuerung", "methodik", 5),
        ("Programmatic Advertising", "methodik", 4), ("SEO/SEA", "methodik", 4),
        ("Social Media Marketing", "methodik", 4), ("Content-Strategie", "methodik", 3),
        ("Google Ads", "tool", 5), ("Meta Business Suite", "tool", 4),
        ("SAP Media", "tool", 4), ("Adobe Creative Suite", "tool", 3),
        ("Google Analytics", "tool", 4), ("Salesforce", "tool", 3),
        ("HubSpot", "tool", 3), ("Canva", "tool", 4),
        ("Anzeigenverkauf", "soft_skill", 5), ("Kundenberatung", "soft_skill", 5),
        ("Budgetplanung", "soft_skill", 4), ("Praesentation", "soft_skill", 4),
        ("Teamfuehrung", "soft_skill", 3),
        ("Deutsch Muttersprache", "sprache", 5), ("Englisch B2", "sprache", 3),
        ("Franzoesisch A2", "sprache", 2),
    ]:
        db.add_skill({"name": skill_name, "category": cat, "level": level})

    # ── Ausbildung ──
    db.add_education({
        "institution": "Stadtanzeiger Verlag / IHK Koeln",
        "degree": "Medienkauffrau Digital & Print",
        "field": "Medien und Kommunikation",
        "start_date": "2013",
        "end_date": "2016",
    })
    db.add_education({
        "institution": "IHK Koeln",
        "degree": "Fachwirtin fuer Medien",
        "field": "Medienmanagement",
        "start_date": "2019",
        "end_date": "2020",
    })

    # ── Suchkriterien ──
    db.set_setting("search_criteria", {
        "keywords_muss": ["Mediaplanung", "Marketing Manager", "Kampagnenmanagement"],
        "keywords_plus": ["Social Media", "Programmatic", "Remote", "Hybrid"],
        "keywords_ausschluss": ["Praktikum", "Werkstudent", "Volontariat"],
        "regionen": ["Koeln", "Duesseldorf", "Remote"],
        "umkreis_km": 50,
    })

    # ── Aktive Quellen ──
    db.set_setting("active_sources", [
        "bundesagentur", "stepstone", "hays", "indeed", "kimeta",
        "stellenanzeigen_de", "jobware",
    ])
    db.set_setting("last_search_at", now.isoformat())

    # ── 15 Jobs fuer volle Stellenliste ──
    jobs = [
        {"title": "Senior Media Plannerin (m/w/d)", "company": "WPP GroupM", "location": "Duesseldorf (Hybrid)",
         "source": "stepstone", "salary_min": 50000, "salary_max": 60000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "hybrid", "score": 94,
         "description": "Strategische Mediaplanung fuer FMCG-Kunden. Erfahrung mit TV, Digital und OOH.",
         "found_at": (now - timedelta(days=1)).isoformat()},
        {"title": "Marketing Managerin Digital", "company": "Koelner Stadtanzeiger", "location": "Koeln",
         "source": "bundesagentur", "salary_min": 45000, "salary_max": 52000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "onsite", "score": 91,
         "description": "Digitales Marketing fuer Verlagsprodukte. Social Media, Newsletter, Kampagnen.",
         "found_at": (now - timedelta(days=1)).isoformat()},
        {"title": "Kampagnenmanagerin Programmatic", "company": "adesso SE", "location": "Koeln (Hybrid)",
         "source": "hays", "salary_min": 48000, "salary_max": 58000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "hybrid", "score": 88,
         "description": "Steuerung programmatischer Werbekampagnen. DV360, Google Ads, Meta.",
         "found_at": (now - timedelta(days=2)).isoformat()},
        {"title": "Social Media Managerin", "company": "REWE Digital", "location": "Koeln",
         "source": "indeed", "salary_min": 40000, "salary_max": 48000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "hybrid", "score": 85,
         "description": "Content-Erstellung und Community Management fuer REWE Social-Media-Kanaele.",
         "found_at": (now - timedelta(days=2)).isoformat()},
        {"title": "Account Managerin Media", "company": "Publicis Media", "location": "Duesseldorf",
         "source": "stepstone", "salary_min": 42000, "salary_max": 50000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "onsite", "score": 82,
         "description": "Kundenbetreuung und Kampagnenkoordination fuer Automobilbranche.",
         "found_at": (now - timedelta(days=3)).isoformat()},
        {"title": "Online Marketing Spezialistin", "company": "trivago N.V.", "location": "Duesseldorf (Remote moeglich)",
         "source": "kimeta", "salary_min": 46000, "salary_max": 55000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "remote", "score": 80,
         "description": "SEA-Kampagnen, Performance Marketing und Budgetoptimierung.",
         "found_at": (now - timedelta(days=3)).isoformat()},
        {"title": "Content & Campaign Managerin", "company": "Henkel AG", "location": "Duesseldorf",
         "source": "bundesagentur", "salary_min": 48000, "salary_max": 56000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "hybrid", "score": 78,
         "description": "Content-Strategie und Kampagnenplanung fuer Beauty-Marken.",
         "found_at": (now - timedelta(days=4)).isoformat()},
        {"title": "Mediaberaterin Crossmedia", "company": "Funke Mediengruppe", "location": "Essen",
         "source": "jobware", "salary_min": 38000, "salary_max": 45000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "onsite", "score": 72,
         "description": "Verkauf von crossmedialen Werbeloesungen. Print, Digital, Events.",
         "found_at": (now - timedelta(days=5)).isoformat()},
        {"title": "Marketing Assistentin", "company": "Zurich Versicherung", "location": "Koeln",
         "source": "stellenanzeigen_de", "salary_min": 36000, "salary_max": 42000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "onsite", "score": 65,
         "description": "Unterstuetzung der Marketingabteilung bei Kampagnen und Events.",
         "found_at": (now - timedelta(days=6)).isoformat()},
        {"title": "Digital Strategist", "company": "Mindshare", "location": "Duesseldorf (Hybrid)",
         "source": "hays", "salary_min": 52000, "salary_max": 62000, "salary_type": "yearly",
         "employment_type": "festanstellung", "remote_level": "hybrid", "score": 76,
         "description": "Entwicklung digitaler Mediastrategien fuer internationale Kunden.",
         "found_at": (now - timedelta(days=4)).isoformat()},
        # Freelance
        {"title": "Freelance Social Media Beratung", "company": "StartupHub Koeln", "location": "Remote",
         "source": "freelancermap", "salary_min": 450, "salary_max": 550, "salary_type": "taeglich",
         "employment_type": "freelance", "remote_level": "remote", "score": 87,
         "description": "Social-Media-Strategie und Umsetzung fuer 3 Startups. 3 Monate.",
         "found_at": (now - timedelta(days=1)).isoformat()},
        {"title": "Kampagnenberatung E-Commerce", "company": "ShopTech AG", "location": "Remote",
         "source": "freelance_de", "salary_min": 500, "salary_max": 600, "salary_type": "taeglich",
         "employment_type": "freelance", "remote_level": "remote", "score": 74,
         "description": "Google Ads + Meta Ads Optimierung fuer Online-Shop. 2 Monate.",
         "found_at": (now - timedelta(days=3)).isoformat()},
    ]
    for i, job in enumerate(jobs):
        job["url"] = f"https://example.com/job/{i+1}"
        job["hash"] = hashlib.md5(job["url"].encode()).hexdigest()[:12]
    db.save_jobs(jobs)

    # ── 12 Bewerbungen fuer volle Pipeline und Statistiken ──
    apps = []

    a = db.add_application({"title": "Senior Media Plannerin", "company": "WPP GroupM",
        "status": "beworben", "applied_at": (now - timedelta(days=45)).date().isoformat()})
    db.update_application_status(a, "eingeladen", "Telefoninterview am 15.03.")
    db.update_application_status(a, "interview", "Zweitgespraech vor Ort am 22.03.")
    db.update_application_status(a, "verhandlung", "Angebot: 55.000 EUR, 30 Tage Urlaub")
    apps.append(a)

    a = db.add_application({"title": "Marketing Managerin Digital", "company": "Koelner Stadtanzeiger",
        "status": "beworben", "applied_at": (now - timedelta(days=30)).date().isoformat()})
    db.update_application_status(a, "eingeladen", "Einladung zum Vorstellungsgespraech")
    apps.append(a)

    a = db.add_application({"title": "Kampagnenmanagerin Programmatic", "company": "adesso SE",
        "status": "beworben", "applied_at": (now - timedelta(days=25)).date().isoformat()})
    db.update_application_status(a, "eingeladen", "Online-Assessment erhalten")
    db.update_application_status(a, "interview", "Interview mit Teamleitung am 28.03.")
    apps.append(a)

    a = db.add_application({"title": "Social Media Managerin", "company": "REWE Digital",
        "status": "beworben", "applied_at": (now - timedelta(days=20)).date().isoformat()})
    apps.append(a)

    a = db.add_application({"title": "Account Managerin Media", "company": "Publicis Media",
        "status": "beworben", "applied_at": (now - timedelta(days=18)).date().isoformat()})
    db.update_application_status(a, "abgelehnt", "Absage — Stelle intern besetzt")
    apps.append(a)

    a = db.add_application({"title": "Content & Campaign Managerin", "company": "Henkel AG",
        "status": "beworben", "applied_at": (now - timedelta(days=15)).date().isoformat()})
    db.update_application_status(a, "eingeladen", "Video-Interview naechste Woche")
    apps.append(a)

    a = db.add_application({"title": "Online Marketing Spezialistin", "company": "trivago N.V.",
        "status": "beworben", "applied_at": (now - timedelta(days=12)).date().isoformat()})
    apps.append(a)

    a = db.add_application({"title": "Digital Strategist", "company": "Mindshare",
        "status": "beworben", "applied_at": (now - timedelta(days=40)).date().isoformat()})
    db.update_application_status(a, "abgelehnt", "Absage nach Erstgespraech")
    apps.append(a)

    a = db.add_application({"title": "Mediaberaterin Print", "company": "Axel Springer",
        "status": "beworben", "applied_at": (now - timedelta(days=55)).date().isoformat()})
    db.update_application_status(a, "eingeladen", "Einladung Probearbeiten")
    db.update_application_status(a, "interview", "Probearbeitstag absolviert")
    db.update_application_status(a, "angebot", "Angebot: 47.000 EUR — abgelehnt, zu weit")
    db.update_application_status(a, "zurueckgezogen", "Entfernung nicht praktikabel")
    apps.append(a)

    a = db.add_application({"title": "PR & Communications Managerin", "company": "Deutsche Telekom",
        "status": "beworben", "applied_at": (now - timedelta(days=8)).date().isoformat()})
    apps.append(a)

    a = db.add_application({"title": "Freelance Social Media Beratung", "company": "StartupHub Koeln",
        "status": "beworben", "applied_at": (now - timedelta(days=5)).date().isoformat()})
    db.update_application_status(a, "eingeladen", "Kennenlerngespraech Donnerstag")
    apps.append(a)

    a = db.add_application({"title": "Mediaplanerin Junior", "company": "OMD Germany",
        "status": "beworben", "applied_at": (now - timedelta(days=60)).date().isoformat()})
    db.update_application_status(a, "abgelehnt", "Ueberqualifiziert fuer Junior-Rolle")
    apps.append(a)

    # ── Follow-ups ──
    db.add_follow_up(apps[3], (now + timedelta(days=2)).date().isoformat())   # REWE nachfassen
    db.add_follow_up(apps[6], (now + timedelta(days=5)).date().isoformat())   # trivago nachfassen
    db.add_follow_up(apps[9], (now + timedelta(days=3)).date().isoformat())   # Telekom nachfassen

    # ── Meetings fuer Kalender ──
    db.add_meeting({
        "application_id": apps[0], "title": "Gehaltsverhandlung WPP GroupM",
        "meeting_date": (now + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00"),
        "meeting_url": "https://teams.microsoft.com/l/meetup-join/demo1",
        "platform": "teams", "duration_minutes": 45,
    })
    db.add_meeting({
        "application_id": apps[1], "title": "Vorstellungsgespraech Stadtanzeiger",
        "meeting_date": (now + timedelta(days=4)).strftime("%Y-%m-%dT14:00:00"),
        "platform": "onsite", "duration_minutes": 60,
    })
    db.add_meeting({
        "application_id": apps[2], "title": "Interview adesso — Teamleitung",
        "meeting_date": (now + timedelta(days=6)).strftime("%Y-%m-%dT11:00:00"),
        "meeting_url": "https://zoom.us/j/demo2",
        "platform": "zoom", "duration_minutes": 90,
    })
    db.add_meeting({
        "application_id": apps[5], "title": "Video-Interview Henkel",
        "meeting_date": (now + timedelta(days=8)).strftime("%Y-%m-%dT15:00:00"),
        "meeting_url": "https://meet.google.com/demo3",
        "platform": "google_meet", "duration_minutes": 60,
    })
    db.add_meeting({
        "application_id": apps[10], "title": "Kennenlerngespraech StartupHub",
        "meeting_date": (now + timedelta(days=1)).strftime("%Y-%m-%dT16:00:00"),
        "platform": "onsite", "duration_minutes": 30,
    })
    db.add_meeting({
        "application_id": None, "title": "Marketing-Stammtisch Koeln",
        "meeting_date": (now + timedelta(days=12)).strftime("%Y-%m-%dT19:00:00"),
        "is_private": True, "duration_minutes": 120,
    })
    db.add_meeting({
        "application_id": None, "title": "LinkedIn-Workshop (Webinar)",
        "meeting_date": (now + timedelta(days=15)).strftime("%Y-%m-%dT10:00:00"),
        "meeting_url": "https://zoom.us/j/webinar", "platform": "zoom",
        "duration_minutes": 90,
    })

    # ── Dokumente ──
    for fname, dtype, text in [
        ("Lebenslauf_Lisa_Berger_2026.pdf", "lebenslauf",
         "Medienkauffrau Digital & Print mit 8 Jahren Erfahrung. Mediaplanung, Kampagnensteuerung, Social Media."),
        ("Anschreiben_WPP_GroupM.pdf", "anschreiben",
         "Bewerbung als Senior Media Plannerin bei WPP GroupM."),
        ("Arbeitszeugnis_Rheinland_Medien.pdf", "zeugnis",
         "Frau Berger war als Senior Media Plannerin in unserem Haus beschaeftigt..."),
        ("Zertifikat_Google_Ads.pdf", "zertifikat",
         "Google Ads Zertifizierung — Search, Display, Video. Bestanden 2024."),
        ("Zertifikat_Fachwirtin_Medien.pdf", "zertifikat",
         "IHK Pruefungszeugnis Fachwirtin fuer Medien."),
        ("Portfolio_Kampagnen_2023.pdf", "sonstiges",
         "Kampagnen-Portfolio: REWE Sommer-Kampagne, Telekom Herbst-Aktion, Henkel Produktlaunch."),
    ]:
        db.add_document({
            "filename": fname, "filepath": f"/tmp/{fname}",
            "doc_type": dtype, "extracted_text": text,
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
    # Sicherstellen, dass alle Spalten existieren (Migration laeuft nicht immer vollstaendig)
    conn = db.connect()
    for stmt in [
        "ALTER TABLE applications ADD COLUMN is_imported INTEGER DEFAULT 0",
        "ALTER TABLE application_meetings ADD COLUMN is_private INTEGER DEFAULT 0",
        "ALTER TABLE application_meetings ADD COLUMN duration_minutes INTEGER",
        "ALTER TABLE application_meetings ADD COLUMN category_id TEXT",
    ]:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # Spalte existiert bereits
    conn.commit()
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
