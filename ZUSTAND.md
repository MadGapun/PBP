# PBP — Persoenliches Bewerbungs-Portal
## Zustandsbericht | 2026-03-07 | v0.12.0

---

## 1. Projektueberblick

| Eigenschaft | Wert |
|------------|------|
| **Name** | PBP (Persoenliches Bewerbungs-Portal) |
| **Version** | 0.12.0 (pyproject.toml) |
| **Architektur** | MCP Server + Web Dashboard |
| **Sprache** | Python 3.11+ |
| **Datenbank** | SQLite (15 Tabellen, WAL, CASCADE, Schema v8, Profil-Isolation) |
| **Transport** | stdio (MCP) + HTTP localhost:8200 (Dashboard) |
| **Zielplattform** | Windows 10/11 (Claude Desktop) + Linux (Entwicklung) |
| **Jobquellen** | 9 (Bundesagentur, StepStone, Hays, Freelancermap, Freelance.de, LinkedIn, Indeed, XING, Monster) |
| **Tests** | 145 Tests (Database, Scoring, Export, v0.10.x, Dashboard) — alle gruen |

---

## 2. Architektur

```
Claude Desktop (Windows)
    |
    | stdio (MCP Protocol)
    v
server.py (FastMCP)  <-- 44 Tools, 6 Resources, 12 Prompts
    |
    v
database.py (SQLite)  <-- 15 Tabellen, WAL Mode, Schema v8, Profil-Isolation
    |
    +---> dashboard.py (FastAPI :8200)  <-- ~47 API Endpoints
    |         |
    |         v
    |     dashboard.html (SPA)  <-- 5 Tabs, Vanilla JS
    |
    +---> export.py  <-- CV + Anschreiben als PDF/DOCX
    |
    +---> job_scraper/ (9 Quellen)
              |
              +-- bundesagentur.py   (REST API)
              +-- stepstone.py       (Playwright)
              +-- hays.py            (Sitemap + JSON-LD)
              +-- freelancermap.py   (httpx + Playwright Fallback)
              +-- freelance_de.py    (HTML Scraping)
              +-- linkedin.py        (Playwright)
              +-- indeed.py          (Playwright)
              +-- xing.py            (Playwright)
              +-- monster.py         (Playwright)
```

---

## 3. MCP Interface

| Typ | Anzahl |
|-----|--------|
| **Tools** | 44 |
| **Resources** | 6 |
| **Prompts** | 12 |

### Tools nach Kategorie

**Profil-Grundlagen (8):**
profil_status, profil_zusammenfassung, profil_bearbeiten, profil_erstellen,
position_hinzufuegen, projekt_hinzufuegen, ausbildung_hinzufuegen, skill_hinzufuegen

**Multi-Profil (4):**
profile_auflisten, profil_wechseln, neues_profil_erstellen, profil_loeschen

**Erfassungsfortschritt (2):**
erfassung_fortschritt_lesen, erfassung_fortschritt_speichern

**Dokument-Analyse (6):**
dokument_profil_extrahieren, dokumente_zur_analyse, extraktion_starten,
extraktion_ergebnis_speichern, extraktion_anwenden, extraktions_verlauf

**Profil Export/Import (2):**
profil_exportieren, profil_importieren

**Jobsuche (3):**
jobsuche_starten, jobsuche_status, stelle_bewerten

**Stellen & Bewerbungen (3):**
stellen_anzeigen, fit_analyse, bewerbungen_anzeigen

**Bewerbungs-Management (3):**
bewerbung_erstellen, bewerbung_status_aendern, statistiken_abrufen

**Suchkriterien (2):**
suchkriterien_setzen, blacklist_verwalten

**Export (2):**
lebenslauf_exportieren, anschreiben_exportieren

**Erweiterte KI-Features (9):**
gehalt_extrahieren, gehalt_marktanalyse, firmen_recherche, branchen_trends,
skill_gap_analyse, ablehnungs_muster, nachfass_planen, nachfass_anzeigen,
bewerbung_stil_tracken

### Resources (6)

profil://aktuell, jobs://aktiv, jobs://aussortiert,
bewerbungen://alle, bewerbungen://statistik, config://suchkriterien

### Prompts (12)

ersterfassung, bewerbung_schreiben, interview_vorbereitung, profil_ueberpruefen,
profil_analyse, willkommen, jobsuche_workflow, bewerbungs_uebersicht,
interview_simulation, gehaltsverhandlung, netzwerk_strategie, profil_erweiterung

---

## 4. Datenbank-Schema (v8, 15 Tabellen)

| Tabelle | Zweck | Seit |
|---------|-------|------|
| settings | Globale Konfiguration | v1 |
| profile | Benutzerprofil (Multi-Profil, is_active, Fortschritt) | v1, erweitert v3 |
| positions | Berufserfahrung (profile_id FK) | v1, erweitert v3 |
| projects | STAR-Projekte (positions CASCADE) | v1 |
| education | Ausbildung (profile_id FK) | v1, erweitert v3 |
| skills | Kompetenzen (profile_id FK) | v1, erweitert v3 |
| documents | Dokumente (profile_id, extraction_status) | v1, erweitert v3/v5 |
| jobs | Stellenangebote (salary_*, profile_id) | v1, erweitert v4/v7/v8 |
| applications | Bewerbungen (rejection_reason, profile_id) | v1, erweitert v2/v6/v8 |
| application_events | Bewerbungs-Timeline (CASCADE) | v1 |
| search_criteria | Suchfilter (JSON) | v1 |
| blacklist | Ausschlussliste | v1 |
| background_jobs | Async Tasks | v1 |
| follow_ups | Nachfass-Erinnerungen | v4 |
| extraction_history | Extraktions-Verlauf | v5 |
| user_preferences | Benutzereinstellungen (Wizard, Hints) | v7 |

Migrationskette: v1 -> v2 -> v3 -> v4 -> v5 -> v6 -> v7 -> v8

---

## 5. Quelldateien

### Python-Module

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| server.py | ~140 | Composition Root (Init + Dashboard + Shutdown) |
| tools/*.py | ~2.485 | 7 Module: 44 Tools |
| prompts.py | ~765 | 12 MCP Prompts |
| resources.py | ~45 | 6 MCP Resources |
| database.py | 1.635 | SQLite-Persistenz (Schema v8, Migrationen) |
| dashboard.py | 1.030 | FastAPI Web-Dashboard (~47 Endpoints) |
| export.py | 366 | PDF/DOCX-Export (fpdf2 + python-docx) |
| job_scraper/__init__.py | 601 | Orchestrator, Scoring, Gehaltsextraktion |
| job_scraper/linkedin.py | ~290 | LinkedIn (Playwright) |
| job_scraper/xing.py | ~240 | XING (Playwright) |
| job_scraper/indeed.py | ~160 | Indeed (Playwright) |
| job_scraper/monster.py | ~140 | Monster (Playwright) |
| job_scraper/freelancermap.py | ~180 | Freelancermap (httpx + Playwright) |
| job_scraper/freelance_de.py | ~230 | Freelance.de (HTML Scraping) |
| job_scraper/hays.py | ~90 | Hays (Sitemap + JSON-LD) |
| job_scraper/stepstone.py | ~130 | StepStone (Playwright) |
| job_scraper/bundesagentur.py | ~80 | Bundesagentur (REST API) |
| logging_config.py | ~50 | Zentrales Logging |
| __init__.py / __main__.py | ~15 | Entry Points |

### Tests (4 Dateien, 1.428 Zeilen)

| Datei | Tests | Zweck |
|-------|-------|-------|
| conftest.py | — | Fixtures (tmp_db, sample_*) |
| test_database.py | 33 | CRUD, CASCADE, Migration, Stats |
| test_scoring.py | 24 | Score, Fit, Remote, Hash, Keywords |
| test_export.py | 8 | CV + Anschreiben in PDF + DOCX |
| test_v010.py | 43 | Schema v8, Salary, UserPrefs, Profil-Isolation |
| test_dashboard.py | 37 | Dashboard-API (Status, CRUD, Validierung, Multi-Profil) |
| **Gesamt** | **145** | **Alle gruen** |

---

## 6. Qualitaetsanalyse

### Staerken
- Saubere Architektur (Server / DB / Dashboard / Scraper / Export getrennt)
- Multi-Profil-System mit Profil-Isolation
- Automatische Dokument-Extraktion (Smart Auto-Extraction)
- 9-Quellen Job-Suche mit Scoring und Deduplizierung
- Gehaltsextraktion (7 Regex-Patterns + Schaetzungstabellen)
- Vollstaendige Schema-Migrationen (v1 bis v8, abwaertskompatibel)
- 108 automatische Tests
- Zero-Knowledge Windows-Installer
- Onboarding-Wizard und Bewerbungs-Wizard
- Factory Reset fuer saubere Neuinstallation

### Bekannte Einschraenkungen
- ~~server.py ist monolithisch~~ — modularisiert in v0.12.0 (tools/, resources.py, prompts.py)
- Keine Tests fuer MCP-Tools, Dashboard-API oder Scraper
- Kein Multi-User-System (lokale SQLite-DB)
- Scraper abhaengig von Portal-Struktur (kann brechen)

---

## 7. Versionsverlauf (Auswahl)

| Version | Datum | Highlights |
|---------|-------|-----------|
| 0.12.0 | 2026-03-07 | server.py Modularisierung, Dashboard-Tests, Doku-Korrekturen |
| 0.11.0 | 2026-03-06 | Validierung, Ladeanimationen, Paginierung, Extraktions-Fixes |
| 0.10.5 | 2026-03-06 | Markdown & Textdateien Support |
| 0.10.0 | 2026-03-05 | UX & Scraper Overhaul, Onboarding-Wizard, Gehalts-Engine |
| 0.9.0 | 2026-03-02 | Skill-Gap-Analyse, Follow-ups, Ablehnungs-Tracking |
| 0.8.0 | 2026-03-02 | Smart Auto-Extraction, Profil-Export/Import |
| 0.7.0 | 2026-03-02 | Interview-Simulation, Gehaltsverhandlung, 9 neue Tools |
| 0.6.0 | 2026-03-02 | Multi-Profil, Fortfuehrbare Ersterfassung |
| 0.1.0 | 2026-03-02 | Erster Release (21 Tools, 65 Tests) |

Vollstaendiges Changelog: siehe CHANGELOG.md und README.md

---

*Aktualisiert: 2026-03-07 von Claude Code (v0.12.0 Modularisierung)*
*Vorheriger Stand: 2026-03-07 (v0.11.1)*
