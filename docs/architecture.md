# PBP Architektur

Stand: 2026-03-21
Referenz: Release-Linie v0.30.0

## Systemüberblick

PBP (Persönliches Bewerbungs-Portal) ist ein lokal-first MCP-Server für Claude Desktop.
Er deckt den Bewerbungsprozess von der Profilerstellung über Jobsuche und Dokument-Analyse
bis zum Bewerbungstracking ab.

```text
Claude Desktop (Windows / Linux)
    │
    │ stdio (MCP Protocol)
    ▼
server.py (FastMCP, ~140 Zeilen)
    │
    ├── tools/              66 MCP-Tools in 8 Modulen
    ├── prompts.py          14 MCP-Prompts
    ├── resources.py        6 MCP-Resources
    ├── services/           4 Services (Profil, Suche, Workspace, E-Mail)
    ├── database.py         SQLite, Schema v15, 21 Tabellen
    ├── dashboard.py        FastAPI :8200 + React 19 SPA
    ├── export.py           PDF/DOCX Export
    └── job_scraper/        17 Jobquellen
```

## Komponenten

### server.py

`src/bewerbungs_assistent/server.py` ist seit v0.12.0 nur noch Composition Root.
Die Datei initialisiert Logging, Datenbank und FastMCP, registriert Tools, Prompts
und Resources und startet optional das Dashboard in einem Hintergrund-Thread.

### tools/

Die 66 Tools sind fachlich in 8 Module getrennt:

- `profil.py` — Profilverwaltung, Multi-Profil, Erfassungsfortschritt
- `dokumente.py` — Dokument-Analyse, Extraktion, Profil-Im/Export
- `jobs.py` — Jobsuche, Stellenverwaltung, Fit-Analyse
- `bewerbungen.py` — Bewerbungstracking, Status, Statistiken, Edit
- `analyse.py` — Gehalt, Trends, Skill-Gap, Follow-ups, E-Mail
- `export_tools.py` — Lebenslauf- und Anschreiben-Export
- `suche.py` — Suchkriterien und Blacklist
- `workflows.py` — Geführte Workflows (12 Workflow-Typen)

Diese Aufteilung ist der zentrale Strukturgewinn gegenüber dem alten monolithischen
`server.py` (vor v0.12.0).

### prompts.py und resources.py

- `prompts.py` kapselt die 14 MCP-Prompts (inkl. email_analyse, quick_check seit v0.29.0).
- `resources.py` kapselt die 6 MCP-Resources.

### services/

`src/bewerbungs_assistent/services/` kapselt gemeinsam genutzte Domänenlogik
zwischen Dashboard und MCP-Tools:

- `profile_service.py` — Profilstatus, Präferenzen, Vollständigkeit
- `search_service.py` — Suchstatus, Quellen, Source-Listen
- `workspace_service.py` — Übergreifende Guidance, Navigation
- `email_service.py` — E-Mail-Parsing (.eml/.msg), Matching (6 Strategien), Meeting-Extraktion

### database.py

`src/bewerbungs_assistent/database.py` ist die persistente Basis des Systems.
Aktuell existieren 21 Tabellen.

Wichtige Eigenschaften:

- Schema-Version `v15` (Migrationskette v1→v15, voll abwärtskompatibel)
- SQLite WAL Mode
- `foreign_keys=ON` mit CASCADE
- Automatische Migrationen beim Start
- Profil-Isolation über `profile_id`
- Content-Hashing (SHA256) für Dokument-Deduplizierung

### dashboard.py

`src/bewerbungs_assistent/dashboard.py` stellt das lokale Web-Dashboard bereit
auf Port **8200**. Das Frontend ist eine React 19 SPA (Vite + Tailwind), die als
statische Assets ausgeliefert wird.

7 Bereiche: Dashboard, Profil, Stellen, Bewerbungen, Statistiken, Einstellungen, Onboarding.

Features: Drag & Drop, Live-Update-Polling, Toast-Notifications, Responsive Layout,
Meeting-Widget, E-Mail-Import, Lazy Loading mit Pagination.

### export.py

`src/bewerbungs_assistent/export.py` erzeugt Lebenslauf und Anschreiben als PDF oder DOCX.
Technologie: fpdf2 (reines Python, keine System-Dependencies) + python-docx.

### job_scraper/

`src/bewerbungs_assistent/job_scraper/` enthält den Dispatcher und 17 Quellen:

**Festanstellung (11):** Bundesagentur, StepStone, Hays, Monster, Indeed,
ingenieur.de, Heise Jobs, Stellenanzeigen.de, Jobware, FERCHAU, Kimeta

**Freelance (4):** Freelancermap, Freelance.de, GULP, SOLCOM

**Netzwerk (2, Login):** LinkedIn, XING

Die Quellen sind bewusst heterogen umgesetzt: REST, HTML-Scraping, JSON-LD oder Playwright,
je nachdem was für die jeweilige Plattform robust genug ist.

## Datenfluss

```text
1. Nutzer interagiert in Claude Desktop oder im Dashboard
2. MCP-Tools bzw. Dashboard-API rufen dieselbe Domänenlogik auf
3. database.py liest und schreibt den lokalen Zustand
4. export.py und job_scraper/ ergänzen Dokumente und Stellenmarktdaten
5. email_service.py verarbeitet importierte E-Mails (Matching, Meetings)
```

## Datenspeicherung

- Windows: `%LOCALAPPDATA%/BewerbungsAssistent/pbp.db`
- Linux: `~/.bewerbungs-assistent/pbp.db`
- alternativ explizit über `BA_DATA_DIR`

Zusatzverzeichnisse im Datenordner: `dokumente/`, `export/`, `logs/`

## Qualitätsstand

- 317 Tests (13 Testdateien + conftest), alle grün
- Modulare MCP-Struktur mit klarer Trennung
- Browser-Smoke-Tests für Dashboard
- E-Mail-Service mit 46 dedizierten Tests
- Regressionstests für alle Major-Versionen
