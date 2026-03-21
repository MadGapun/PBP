# PBP — Persönliches Bewerbungs-Portal
## Zustandsbericht | 2026-03-21 | v0.30.0

---

## 1. Projektüberblick

| Eigenschaft | Wert |
|------------|------|
| **Name** | PBP (Persönliches Bewerbungs-Portal) |
| **Version** | 0.30.0 (pyproject.toml + \_\_init\_\_.py) |
| **Architektur** | MCP Server + React-Dashboard (SPA) |
| **Sprache** | Python 3.11+ / React 19 + Vite + Tailwind |
| **Datenbank** | SQLite (21 Tabellen, WAL, CASCADE, Schema v15, Profil-Isolation) |
| **Transport** | stdio (MCP) + HTTP localhost:8200 (Dashboard) |
| **Zielplattform** | Windows 10/11 (Claude Desktop) + Linux (Entwicklung) |
| **Jobquellen** | 17 (11 Festanstellung + 4 Freelance + 2 Netzwerk) |
| **Tests** | 317 Tests (alle grün, 4 übersprungen) |

---

## 2. Architektur

```
Claude Desktop (Windows / Linux)
    │
    │ stdio (MCP Protocol)
    ▼
server.py (FastMCP, ~140 Zeilen)  ◄── Composition Root
    │
    ├── tools/ (8 Module, 66 Tools)
    │     ├── profil.py         — Profilverwaltung, Multi-Profil, Fortschritt
    │     ├── dokumente.py      — Analyse, Extraktion, Im/Export
    │     ├── jobs.py           — Jobsuche, Stellenverwaltung, Fit-Analyse
    │     ├── bewerbungen.py    — Tracking, Status, Statistiken
    │     ├── analyse.py        — Gehalt, Trends, Skill-Gap, Follow-ups
    │     ├── export_tools.py   — Lebenslauf/Anschreiben (PDF/DOCX)
    │     ├── suche.py          — Suchkriterien und Blacklist
    │     └── workflows.py      — Geführte Workflows
    │
    ├── prompts.py       ◄── 14 MCP-Prompts
    ├── resources.py     ◄── 6 MCP-Resources
    │
    ├── services/        ◄── Service-Layer
    │     ├── profile_service.py    — Profilstatus, Präferenzen
    │     ├── search_service.py     — Suchstatus, Quellen
    │     ├── workspace_service.py  — Guidance, Navigation
    │     └── email_service.py      — E-Mail-Parsing, Matching, Meetings
    │
    ├── database.py      ◄── Schema v15, WAL, CASCADE, Migrationen v1→v15
    │
    ├── dashboard.py     ◄── FastAPI :8200, React-SPA, REST-API
    │
    ├── export.py        ◄── PDF/DOCX (fpdf2 + python-docx)
    │
    └── job_scraper/     ◄── 17 Quellen
          ├── __init__.py       — Dispatcher, Scoring, Deduplizierung
          ├── bundesagentur.py  — REST API
          ├── stepstone.py      — Playwright
          ├── hays.py           — Sitemap + JSON-LD
          ├── linkedin.py       — Playwright (Login)
          ├── xing.py           — Playwright (Login)
          ├── indeed.py         — Playwright
          ├── monster.py        — Playwright
          ├── freelancermap.py  — httpx + Playwright Fallback
          ├── freelance_de.py   — HTML Scraping
          ├── gulp.py           — HTML + JSON-LD
          ├── solcom.py         — HTML + JSON-LD
          ├── ingenieur_de.py   — HTML Scraping (VDI)
          ├── heise_jobs.py     — HTML + JSON-LD
          ├── stellenanzeigen_de.py — HTML + JSON-LD
          ├── jobware.py        — HTML + JSON-LD
          ├── ferchau.py        — HTML + JSON-LD
          └── kimeta.py         — HTML Scraping (Aggregator)
```

---

## 3. MCP Interface

| Typ | Anzahl |
|-----|--------|
| **Tools** | 66 |
| **Resources** | 6 |
| **Prompts** | 14 |

### Tools nach Kategorie (66)

**Profil-Grundlagen (8):**
profil_status, profil_zusammenfassung, profil_bearbeiten, profil_erstellen,
position_hinzufuegen, projekt_hinzufuegen, ausbildung_hinzufuegen, skill_hinzufuegen

**Multi-Profil (4):**
profile_auflisten, profil_wechseln, neues_profil_erstellen, profil_loeschen

**Erfassungsfortschritt (2):**
erfassung_fortschritt_lesen, erfassung_fortschritt_speichern

**Dokument-Analyse (10):**
dokument_profil_extrahieren, dokumente_zur_analyse, extraktion_starten,
extraktion_ergebnis_speichern, extraktion_anwenden, extraktions_verlauf,
analyse_plan_erstellen, dokumente_batch_analysieren, dokumente_bulk_markieren,
bewerbungs_dokumente_erkennen

**Profil Export/Import (2):**
profil_exportieren, profil_importieren

**Jobsuche (3):**
jobsuche_starten, jobsuche_status, stelle_bewerten

**Stellen & Bewerbungen (5):**
stellen_anzeigen, fit_analyse, bewerbungen_anzeigen,
bewerbung_erstellen, bewerbung_status_aendern

**Statistiken & Analyse (10):**
statistiken_abrufen, gehalt_extrahieren, gehalt_marktanalyse,
firmen_recherche, branchen_trends, skill_gap_analyse,
ablehnungs_muster, nachfass_planen, nachfass_anzeigen,
bewerbung_stil_tracken

**Suchkriterien (2):**
suchkriterien_setzen, blacklist_verwalten

**Export (2):**
lebenslauf_exportieren, anschreiben_exportieren

**Jobtitel (2):**
jobtitel_vorschlagen, jobtitel_verwalten

**Workflows (3):**
workflow_starten, jobsuche_workflow_starten, ersterfassung_starten

**E-Mail (5):**
email_importieren, email_zuordnung_bestätigen, email_meetings_anzeigen,
email_meeting_erstellen, emails_einer_bewerbung

**Bewerbungs-Edit (6):**
bewerbung_bearbeiten, bewerbung_loeschen, bewerbung_notiz,
stelle_snapshot_aktualisieren, dismiss_reason_verwalten, statistik_tagesbericht

### Resources (6)

profil://aktuell, jobs://aktiv, jobs://aussortiert,
bewerbungen://alle, bewerbungen://statistik, config://suchkriterien

### Prompts (14)

ersterfassung, willkommen, profil_ueberpruefen, profil_analyse,
profil_erweiterung, bewerbung_schreiben, interview_vorbereitung,
interview_simulation, gehaltsverhandlung, netzwerk_strategie,
bewerbungs_uebersicht, jobsuche_workflow, email_analyse, quick_check

---

## 4. Datenbank-Schema (v15, 21 Tabellen)

| Tabelle | Zweck | Seit |
|---------|-------|------|
| settings | Globale Konfiguration | v1 |
| profile | Benutzerprofil (Multi-Profil, Fortschritt) | v1, v3 |
| positions | Berufserfahrung | v1, v3 |
| projects | STAR-Projekte | v1 |
| education | Ausbildung | v1, v3 |
| skills | Kompetenzen mit Kategorie + Level | v1, v3 |
| documents | Dokumente (extraction_status, content_hash) | v1, v3, v5, v15 |
| jobs | Stellenangebote (salary_*, description_snapshot) | v1, v4, v7, v8, v14 |
| applications | Bewerbungen (vermittler, endkunde, editierbar) | v1, v2, v6, v8, v14 |
| application_events | Bewerbungs-Timeline (CASCADE) | v1 |
| application_emails | E-Mail-Zuordnung (matched_by, status_detected) | v15 |
| application_meetings | Termine (meeting_url, platform) | v15 |
| search_criteria | Suchfilter (JSON) | v1 |
| blacklist | Ausschlussliste | v1 |
| background_jobs | Async Tasks | v1 |
| follow_ups | Nachfass-Erinnerungen | v4 |
| extraction_history | Extraktions-Verlauf | v5 |
| user_preferences | Benutzereinstellungen (Wizard, Hints) | v7 |
| suggested_job_titles | Jobtitel (auto + manuell) | v9 |
| dismiss_reasons | Ablehnungsgründe (benutzerdefiniert) | v13 |
| document_templates | Vorlagen-Kennzeichnung | v14 |

Migrationskette: v1 → v2 → v3 → v4 → v5 → v6 → v7 → v8 → v9 → v10 → v11 → v12 → v13 → v14 → v15

---

## 5. Quelldateien

### Python-Module

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| server.py | ~140 | Composition Root |
| tools/*.py | ~4.500 | 8 Module: 66 Tools |
| prompts.py | ~1.100 | 14 MCP Prompts |
| resources.py | ~45 | 6 MCP Resources |
| services/*.py | ~800 | 4 Services (Profil, Suche, Workspace, E-Mail) |
| database.py | ~2.200 | SQLite-Persistenz (Schema v15, 15 Migrationen) |
| dashboard.py | ~1.800 | FastAPI Dashboard (REST-API + React-SPA) |
| export.py | ~400 | PDF/DOCX-Export |
| export_report.py | ~300 | Profil-Report |
| job_scraper/*.py | ~3.000 | Dispatcher + 17 Quellen |

### Frontend (React 19)

| Datei | Zweck |
|-------|-------|
| frontend/src/App.jsx | Haupt-SPA (~7.500 Zeilen) |
| frontend/src/pages/*.jsx | 6 Seiten (Dashboard, Profil, Bewerbungen, Stellen, Statistiken, Einstellungen) |
| frontend/src/utils.js | Hilfsfunktionen (statusLabel, normalizeMonthDate) |
| frontend/src/styles.css | Tailwind + Custom CSS |

### Tests (13 Testdateien, 317 Tests)

| Datei | Tests | Zweck |
|-------|-------|-------|
| test_database.py | 33 | CRUD, CASCADE, Migration, Stats |
| test_scoring.py | 24 | Score, Fit, Remote, Hash, Keywords |
| test_export.py | 8 | CV + Anschreiben in PDF + DOCX |
| test_v010.py | 43 | Schema v8, Salary, UserPrefs, Profil-Isolation |
| test_dashboard.py | 44 | Dashboard-API, CRUD, Multi-Profil, Version-Check |
| test_v013.py | 14 | FK-Bugfixes, Ordner-Browser, Auto-Analyse |
| test_v020.py | 80 | v0.20+ Features, Export-Report, E-Mail |
| test_email_service.py | 46 | E-Mail-Parsing, Matching, Meetings |
| test_mcp_registry.py | 3 | MCP-Registry, Public Interface |
| test_scrapers.py | 3 | Fixture-basierte Parser-Tests |
| test_profile_service.py | 5 | Service-Layer Profil |
| test_search_service.py | 5 | Suchstatus, Quellen |
| test_workspace_service.py | 5 | Workspace-Guidance |
| test_dashboard_browser.py | 3 | Browser-Smokes |
| **Gesamt** | **317** | **Alle grün** |

---

## 6. Dashboard (React 19 SPA)

Port: **8200** (localhost)

**7 Bereiche:**

| Bereich | Inhalt |
|---------|--------|
| **Dashboard** | Statistik-Kacheln, Meetings-Widget, Follow-up-Alerts, Guidance-TODOs |
| **Profil** | Persönliche Daten, Positionen, Ausbildung, Skills, Dokumente |
| **Stellen** | Job-Karten mit Score, Lazy Loading, Pagination, Fit-Analyse |
| **Bewerbungen** | Timeline, Status-Tracking, E-Mail-Zuordnung, Meetings |
| **Statistiken** | Charts (Recharts), Trends, Tagesbericht, Status-Verteilung |
| **Einstellungen** | Keywords, Regionen, Gewichtungen, Quellen, Blacklist |
| **Onboarding** | Wizard für Ersteinrichtung (Profil, Kriterien, Quellen) |

**Features:** Drag & Drop (E-Mail + Dokumente), Toast-Notifications, Live-Update-Polling,
Responsive Layout, Profil-Sidebar, Hilfe-Dialog, Credits-Dialog

---

## 7. Qualitätsanalyse

### Stärken
- Modulare MCP-Architektur (server.py nur Composition Root)
- Multi-Profil mit vollständiger Daten-Isolation
- 17-Quellen-Jobsuche mit konfigurierbarem Scoring
- E-Mail-Integration (.eml + .msg) mit automatischem Matching
- Schema-Migrationen v1→v15, voll abwärtskompatibel
- 317 automatische Tests inkl. Browser-Smokes
- React 19 SPA mit professionellem UI
- Zero-Knowledge Windows-Installer
- Deutsche Nutzerführung durchgängig

### Bekannte Einschränkungen
- Frontend-Bundle ~832 kB (vor gzip) — funktional, Optimierung möglich
- fpdf2 Deprecation-Warnungen (ln→new_x/new_y)
- Kein Multi-User-System (bewusst: lokale SQLite-DB)
- Scraper abhängig von Portal-Struktur (kann brechen)
- LinkedIn/XING erfordern eigenen Account

---

## 8. Versionsverlauf (Auswahl)

| Version | Datum | Highlights |
|---------|-------|-----------|
| 0.30.0 | 2026-03-20 | UX-Fixes (9 Issues, Koala280), Lazy Loading, ~300 Umlaut-Korrekturen |
| 0.29.0 | 2026-03-20 | E-Mail-Integration, Schema v15, 17 API-Endpoints, Meeting-Widget |
| 0.28.0 | 2026-03-20 | Editierbare Bewerbungen, Snapshot, Schema v14 |
| 0.27.0 | 2026-03-20 | Datenqualität, Skill-Normalisierung, Zombie-Erkennung |
| 0.26.0 | 2026-03-20 | Filtering, Scoring, UX, 66 Tools, Schema v13 |
| 0.25.2 | 2026-03-20 | Frontend-Recovery (Codex + Claude) |
| 0.25.0 | 2026-03-17 | Datenqualität, Installer, Profil-Report |
| 0.24.0 | 2026-03-16 | Dashboard-Erweiterungen, Fit-Analyse, Help-Menü |
| 0.23.0 | 2026-03-16 | Koala280 React-Frontend (7.877 Zeilen) |
| 0.17.0 | 2026-03-14 | React 19 + Vite + Tailwind (Koala280-Basis) |
| 0.16.0 | 2026-03-12 | Skill-Aktualität, Jobtitel, Schema v9, 53 Tools |
| 0.14.0 | 2026-03-10 | Service-Layer, Workspace-Guidance |
| 0.10.0 | 2026-03-05 | UX-Overhaul, Onboarding-Wizard |
| 0.1.0 | 2026-03-02 | Erster Release (21 Tools, 65 Tests) |

Vollständiges Changelog: siehe CHANGELOG.md

---

*Aktualisiert: 2026-03-21 von Claude Code (v0.30.0 Release-Vorbereitung für v1.0.0)*
*Vorheriger Stand: 2026-03-12 (v0.16.0)*
