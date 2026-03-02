# PBP — Persoenliches Bewerbungs-Portal
## Zustandsbericht | 2026-02-26 | V1.0 Release

---

## 1. Projektueberblick

| Eigenschaft | Wert |
|------------|------|
| **Name** | Bewerbungs-Assistent |
| **Version** | 1.0.0 |
| **Architektur** | MCP Server + Web Dashboard |
| **Sprache** | Python 3.11+ |
| **Codezeilen** | 6.162 (16 Quelldateien) + 886 Tests + 1.076 Installer/Tools |
| **Datenbank** | SQLite (13 Tabellen, WAL, CASCADE, Schema v2) |
| **Transport** | stdio (MCP) + HTTP localhost:8200 (Dashboard) |
| **Zielplattform** | Windows 10/11 (Claude Desktop) + Linux (Entwicklung) |
| **Jobquellen** | 8 (Bundesagentur, StepStone, Hays, Freelancermap, LinkedIn, Indeed, XING, Monster) |
| **Testabdeckung** | 65 Tests (Database, Scoring, Export) — alle gruen |

---

## 2. Architektur

```
Claude Desktop (Windows)
    |
    | stdio (MCP Protocol)
    v
server.py (FastMCP)  <-- 21 Tools, 6 Resources, 8 Prompts
    |
    v
database.py (SQLite)  <-- 13 Tabellen, WAL Mode, CASCADE, Schema v2
    |
    +---> dashboard.py (FastAPI :8200)  <-- 28 API Endpoints
    |         |
    |         v
    |     dashboard.html (SPA)  <-- 5 Tabs, Vanilla JS, Toast-System
    |
    +---> export.py  <-- CV + Anschreiben als PDF/DOCX
    |
    +---> job_scraper/ (8 Quellen)
              |
              +-- bundesagentur.py  (REST API, 83 Z.)
              +-- stepstone.py      (BeautifulSoup, 86 Z.)
              +-- hays.py           (Sitemap+JSON-LD, 89 Z.)
              +-- freelancermap.py  (JS State, 90 Z.)
              +-- linkedin.py       (Playwright, 292 Z.)
              +-- indeed.py         (BeautifulSoup, 140 Z.)
              +-- xing.py           (Playwright, 236 Z.)
              +-- monster.py        (BeautifulSoup, 121 Z.)
```

---

## 3. Implementierungsstatus — V1.0 KOMPLETT

### 3.1 V1.0 Arbeitspakete (8/8 = 100%)

| WP | Titel | Status |
|----|-------|--------|
| WP1 | Dialog-Profil (zwangloses Interview + Review) | ✓ done |
| WP2 | Dynamische Scraper-Keywords | ✓ done |
| WP3A | Quellenverwaltung UI + Infrastruktur | ✓ done |
| WP3B | Neue Scraper (Indeed, XING, Monster) | ✓ done |
| WP4A | Erweitertes Bewerbungsformular | ✓ done |
| WP4B | PDF/DOCX Export-Modul | ✓ done |
| WP5 | Frontend-Qualitaet (Toast, Validierung, Spinner) | ✓ done |
| WP6 | Automatische Tests (65 Tests) | ✓ done |

### 3.2 Feature-Matrix

| Feature | Backend | Frontend | MCP Tool | Getestet |
|---------|---------|----------|----------|----------|
| Profil erstellen/bearbeiten | ja | ja | ja | ja |
| Dialog-basierte Ersterfassung | ja | — | Prompt | ja |
| Profil-Review + Korrektur | ja | — | 2 Tools | ja |
| Positionen + STAR-Projekte | ja | ja | ja | ja |
| Ausbildung CRUD | ja | ja | ja | ja |
| Skills CRUD | ja | ja | ja | ja |
| Dokument-Upload (max 50MB) | ja | ja | nein | ja |
| Ordner-Scanner (Path-sicher) | ja | ja | nein | ja |
| Jobsuche (8 Quellen) | ja | ja | ja | teilw. |
| Quellenverwaltung (an/aus) | ja | ja | ja | ja |
| Dynamische Keywords | ja | — | ja | ja |
| Fit-Analyse + Scoring | ja | ja | nein | ja |
| Bewerbung erstellen (3 Arten) | ja | ja | ja | ja |
| Status-Tracking + Timeline | ja | ja | ja | ja |
| CV-Generator (Text) | ja | ja | nein | ja |
| CV-Export PDF/DOCX | ja | ja | ja | ja |
| Anschreiben-Export PDF/DOCX | ja | ja | ja | ja |
| Interview-Vorbereitung | nein | nein | Prompt | nein |
| Suchkriterien verwalten | ja | ja | ja | ja |
| Blacklist verwalten | ja | ja | ja | ja |
| Statistiken | ja | ja | ja | ja |
| Toast-Benachrichtigungen | — | ja | — | ja |
| Form-Validierung | — | ja | — | ja |
| Ladeanimationen (Spinner) | — | ja | — | ja |

---

## 4. Dateiinventar

### 4.1 Python-Module (16 Dateien, 5.632 Zeilen)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| __init__.py | 9 | Entry Point |
| __main__.py | 4 | CLI Runner |
| server.py | 1.490 | MCP Server (21 Tools, 6 Resources, 8 Prompts) |
| database.py | 746 | SQLite-Persistenz (Schema v2, 28 Methoden) |
| dashboard.py | 597 | FastAPI Web-API (28 Endpoints) |
| export.py | 363 | PDF/DOCX-Export (fpdf2 + python-docx) |
| job_scraper/__init__.py | 362 | Orchestrator, Scoring, Fit-Analyse, SOURCE_REGISTRY |
| job_scraper/linkedin.py | 292 | LinkedIn (Playwright) |
| job_scraper/xing.py | 236 | XING (Playwright) |
| job_scraper/indeed.py | 140 | Indeed (httpx + BS4) |
| job_scraper/monster.py | 121 | Monster (httpx + BS4) |
| job_scraper/freelancermap.py | 90 | Freelancermap (JS State) |
| job_scraper/hays.py | 89 | Hays (Sitemap + JSON-LD) |
| job_scraper/stepstone.py | 86 | StepStone (BS4) |
| job_scraper/bundesagentur.py | 83 | Bundesagentur (REST API) |
| templates/dashboard.html | 1.454 | SPA (5 Tabs, Toast, Spinner, Onboarding, Naechste-Schritte) |

### 4.2 Tests (4 Dateien, 886 Zeilen)

| Datei | Zeilen | Tests | Zweck |
|-------|--------|-------|-------|
| conftest.py | 117 | — | 5 Fixtures (tmp_db, sample_*) |
| test_database.py | 378 | 34 | CRUD alle Entities, CASCADE, Migration, Stats |
| test_scoring.py | 244 | 19 | Score, Fit-Analyse, Remote, Hash, Keywords |
| test_export.py | 147 | 8 | CV + Anschreiben in PDF + DOCX, Validierung |
| **Gesamt** | **886** | **65** | **Alle gruen** |

### 4.3 Installer + Tools (5 Dateien, 1.076 Zeilen)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| INSTALLIEREN.bat | ~250 | Windows Zero-Knowledge Installer (winget + Fallback) |
| installer/install.sh | 123 | Linux-Installer |
| installer/install.ps1 | 340 | PowerShell-Installer (Detail) |
| pyproject.toml | 48 | Build-Config (hatchling) |
| test_demo.py | 196 | Demo-Launcher mit Beispieldaten |

---

## 5. Datenbank-Schema (v2, 13 Tabellen)

| Tabelle | Spalten | Zweck | FK / Cascade |
|---------|---------|-------|-------------|
| settings | 2 | Globale Konfig (JSON) | — |
| profile | 16 | Benutzerprofil + Praeferenzen | — |
| positions | 15 | Berufserfahrung | — |
| projects | 12 | STAR-Projekte | positions(id) CASCADE |
| education | 8 | Ausbildung | — |
| skills | 5 | Kompetenzen | — |
| documents | 7 | Dokumente | positions(id) SET NULL |
| jobs | 16 | Stellenangebote | — |
| applications | 17 | Bewerbungen (v2: +5 Spalten) | jobs(hash) |
| application_events | 5 | Timeline | applications(id) CASCADE |
| search_criteria | 3 | Suchfilter (JSON) | — |
| blacklist | 5 | Ausschlussliste | — |
| background_jobs | 9 | Async Tasks | — |

**Indexes**: 4 (jobs_active, jobs_source, apps_status, app_events)
**Schema v2 Erweiterungen**: bewerbungsart, lebenslauf_variante, ansprechpartner, kontakt_email, portal_name

---

## 6. API-Endpoints (28 total)

| Method | Pfad | Zweck |
|--------|------|-------|
| GET | / | Dashboard HTML |
| GET | /api/status | Server-Status |
| GET/POST | /api/profile | Profil lesen/speichern |
| POST | /api/position | Position hinzufuegen |
| POST | /api/project | Projekt hinzufuegen |
| POST | /api/education | Ausbildung hinzufuegen |
| POST | /api/skill | Skill hinzufuegen |
| DELETE | /api/position/{id} | Position loeschen (CASCADE) |
| DELETE | /api/education/{id} | Ausbildung loeschen |
| DELETE | /api/skill/{id} | Skill loeschen |
| DELETE | /api/document/{id} | Dokument loeschen |
| POST | /api/documents/upload | Dokument hochladen (max 50MB) |
| POST | /api/documents/import-folder | Ordner scannen (Path-sicher) |
| GET | /api/cv/generate | Lebenslauf als Text |
| GET | /api/cv/export/{fmt} | CV als PDF/DOCX FileResponse |
| POST | /api/cover-letter/export/{fmt} | Anschreiben als PDF/DOCX |
| GET | /api/application/{id}/timeline | Bewerbungs-Timeline |
| GET | /api/jobs | Stellen auflisten |
| POST | /api/jobs/dismiss | Stelle aussortieren |
| POST | /api/jobs/restore | Stelle wiederherstellen |
| GET | /api/jobs/{hash}/fit-analyse | Fit-Analyse |
| GET/POST | /api/applications | Bewerbungen |
| PUT | /api/applications/{id}/status | Status aendern |
| GET | /api/statistics | Statistiken |
| GET/POST | /api/search-criteria | Suchkriterien |
| GET/POST | /api/blacklist | Blacklist |
| GET/POST | /api/sources | Quellenverwaltung |
| GET | /api/background-jobs/{id} | Hintergrund-Job |

### MCP Interface

| Typ | Anzahl | Elemente |
|-----|--------|----------|
| **Tools** | 21 | profil_status, profil_zusammenfassung, profil_bearbeiten, profil_erstellen, position_hinzufuegen, projekt_hinzufuegen, ausbildung_hinzufuegen, skill_hinzufuegen, jobsuche_starten, jobsuche_status, stelle_bewerten, **lebenslauf_exportieren**, **anschreiben_exportieren**, **stellen_anzeigen**, **fit_analyse**, **bewerbungen_anzeigen**, bewerbung_erstellen, bewerbung_status_aendern, statistiken_abrufen, suchkriterien_setzen, blacklist_verwalten |
| **Resources** | 6 | profil://aktuell, jobs://aktiv, jobs://aussortiert, bewerbungen://alle, bewerbungen://statistik, config://suchkriterien |
| **Prompts** | 8 | ersterfassung, bewerbung_schreiben, interview_vorbereitung, profil_ueberpruefen, profil_analyse, **willkommen**, **jobsuche_workflow**, **bewerbungs_uebersicht** |

Neue Tools (V1.0 Feinschliff):
- `lebenslauf_exportieren()` — CV als PDF/DOCX direkt aus Claude heraus
- `anschreiben_exportieren()` — Anschreiben als PDF/DOCX
- `stellen_anzeigen()` — Stellenangebote in Claude anzeigen (mit Filter)
- `fit_analyse()` — Detaillierte Passungsanalyse einer Stelle
- `bewerbungen_anzeigen()` — Bewerbungen mit Statistik in Claude

Neue Prompts (V1.0 Feinschliff):
- `willkommen` — Willkommensbildschirm mit Status-Uebersicht
- `jobsuche_workflow` — Gefuehrter Workflow: Kriterien → Quellen → Suche → Bewerbung
- `bewerbungs_uebersicht` — Komplette Uebersicht aller Daten + naechste Schritte

---

## 7. Abhaengigkeiten

### Core
| Paket | Version | Zweck |
|-------|---------|-------|
| fastmcp | >=2.0 | MCP Server Framework |
| uvicorn | >=0.30 | ASGI Server |
| fastapi | >=0.115 | Web Framework |
| python-multipart | >=0.0.9 | Form-Parsing |
| httpx | >=0.27 | HTTP Client |

### Optional: Scraper
| Paket | Version | Zweck |
|-------|---------|-------|
| playwright | >=1.40 | LinkedIn/XING Browser-Scraping |
| beautifulsoup4 | >=4.12 | HTML Parsing (StepStone, Indeed, Monster) |
| lxml | >=5.0 | XML Parser |

### Optional: Dokumente
| Paket | Version | Zweck |
|-------|---------|-------|
| python-docx | >=1.1 | Word-Dokumente lesen/schreiben |
| pypdf | >=4.0 | PDF-Text extrahieren |
| fpdf2 | >=2.7 | PDF-Generierung (reines Python, kein System-Deps) |

### Dev
| Paket | Version | Zweck |
|-------|---------|-------|
| pytest | >=8.0 | Test-Framework |
| pytest-asyncio | >=0.23 | Async-Test-Support |

---

## 8. Qualitaetsanalyse

### Staerken
- Saubere Architektur (Server / DB / Scraper / Export getrennt)
- SQL-Injection-sicher (parametrisierte Queries)
- STAR-Methode fuer Projekte (Best Practice)
- Multi-Source Job-Suche mit 8 Quellen + Deduplizierung
- Konfigurierbares Scoring-System (Gewichtungen einstellbar)
- Dynamische Scraper-Keywords aus DB
- Bewerbungs-Timeline mit Event-Log
- Cascading Deletes (Datenintegritaet)
- Upload-Limit (50MB) + Path-Traversal-Schutz
- Cross-Platform (Windows + Linux)
- Toast-Benachrichtigungen + Form-Validierung + Spinner
- PDF/DOCX-Export mit fpdf2 (keine System-Dependencies)
- Dialog-basierte Profilerstellung (4-Phasen Interview)
- Unterstuetzung fuer diverse Lebenslaeufe (Studenten, Wiedereinsteiger, Freelancer, etc.)
- 65 automatische Tests (100% gruen)
- Zero-Knowledge Windows-Installer (winget + manuelle Fallbacks)
- Quellenverwaltung (Jobquellen an/aus im Dashboard)
- Schema-Migration (v1→v2 abwaertskompatibel)
- **Willkommens-Prompt** mit Status-Uebersicht fuer wiederkehrende Nutzer
- **Gefuehrter Jobsuche-Workflow** (Kriterien → Quellen → Suche → Bewerbung)
- **Export direkt aus Claude** (kein Umweg uebers Dashboard noetig)
- **Naechste-Schritte-Karte** im Dashboard (proaktive Handlungsempfehlungen)
- **Claude-Prompt-Hinweise** in allen leeren Zustaenden des Dashboards

### Offene Optimierungen (Post-V1.0)

| Nr | Problem | Prioritaet |
|----|---------|------------|
| OPT-010 | Keine Paginierung bei Bewerbungen/Jobs | NIEDRIG |
| OPT-014 | Profil im Dashboard nur hinzufuegen, nicht bearbeiten | MITTEL |
| OPT-015 | Keine Backup-Funktion | MITTEL |
| OPT-016 | SQLite unverschluesselt | NIEDRIG |
| OPT-017 | Kein Dark Mode | NIEDRIG |

---

## 9. Testbericht (2026-02-26, V1.0)

### Automatische Tests: 65/65 bestanden

| Datei | Tests | Ergebnis |
|-------|-------|----------|
| test_database.py | 34 | ✓ PASSED |
| test_scoring.py | 19 | ✓ PASSED |
| test_export.py | 8 | ✓ PASSED |
| **Gesamt** | **65** | **✓ ALL PASSED (1.96s)** |

### Test-Kategorien
- **Database**: Profil CRUD, Positions+Projects CASCADE, Education, Skills, Jobs (Filter, Upsert, Dismiss/Restore), Applications (v2-Felder), Search Criteria, Blacklist, Settings, Background Jobs, Schema-Migration v1→v2, Statistiken
- **Scoring**: MUSS/PLUS/AUSSCHLUSS Keywords, Remote-Bonus, Hybrid-Bonus, Entfernungs-Bonus/-Malus, Custom Weights, Case-Insensitive, fit_analyse, detect_remote_level, stelle_hash, build_search_keywords
- **Export**: CV als DOCX + PDF, Anschreiben als DOCX + PDF, Datei-Integritaet (PDF-Header), Content-Verifikation, Minimal-Profil, Leer-Text

---

## 10. Changelog V1.0

| WP | Feature | Dateien |
|----|---------|---------|
| WP1 | Dialog-Profil: 4-Phasen Interview, profil_zusammenfassung(), profil_bearbeiten(), profil_ueberpruefen() | server.py |
| WP2 | Dynamische Keywords: build_search_keywords(), alle Scraper auf DB-Keywords umgestellt | job_scraper/*.py |
| WP3A | Quellenverwaltung: SOURCE_REGISTRY, /api/sources, Dashboard-UI mit Checkboxen | job_scraper/__init__.py, dashboard.py, dashboard.html |
| WP3B | 3 neue Scraper: Indeed (httpx+BS4), XING (Playwright), Monster (httpx+BS4) | indeed.py, xing.py, monster.py |
| WP4A | Bewerbungsformular: 3 Bewerbungsarten, dynamische Felder, Schema v2 (+5 Spalten) | database.py, server.py, dashboard.html |
| WP4B | Export-Modul: CV + Anschreiben als PDF (fpdf2) und DOCX (python-docx) | export.py, dashboard.py, pyproject.toml |
| WP5 | Frontend: Toast-System, Form-Validierung, Spinner, alle alert() ersetzt | dashboard.html |
| WP6 | Tests: 65 Tests in 3 Dateien, fpdf2 v2.8 API-Migration | tests/*, export.py |
