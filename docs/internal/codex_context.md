# PBP Codex Context

Kurzkontext für KI-Assistenten, die im Repo arbeiten.

Stand: 2026-03-21 | v0.30.0

## Was ist PBP?

PBP (Persönliches Bewerbungs-Portal) ist ein MCP-Server für Claude Desktop.
Das Produkt ist lokal-first, deutschsprachig und für einen Endnutzerworkflow gebaut:
Profil aufbauen, Jobs suchen, Dokumente exportieren, Bewerbungen verfolgen,
E-Mails importieren und Termine verwalten.

## Technischer Kern

- Python 3.11+
- FastMCP für die Claude-Desktop-Integration
- FastAPI für das lokale Dashboard auf Port 8200
- React 19 + Vite + Tailwind für das Frontend
- SQLite mit WAL, Schema v15, 21 Tabellen
- Playwright/HTML-Scraping für 17 Jobportale
- E-Mail-Parsing (.eml + .msg) mit automatischem Matching

## Struktur

- `src/bewerbungs_assistent/server.py`
  Composition Root, registriert Module und startet das Dashboard.
- `src/bewerbungs_assistent/tools/`
  66 MCP-Tools in 8 Modulen (profil, dokumente, jobs, bewerbungen, analyse, export_tools, suche, workflows).
- `src/bewerbungs_assistent/prompts.py`
  14 MCP-Prompts (inkl. email_analyse, quick_check).
- `src/bewerbungs_assistent/resources.py`
  6 MCP-Resources.
- `src/bewerbungs_assistent/services/`
  4 Services: profile_service, search_service, workspace_service, email_service.
- `src/bewerbungs_assistent/database.py`
  SQLite-Schicht mit Schema v15, 21 Tabellen, Migrationskette v1→v15.
- `src/bewerbungs_assistent/dashboard.py`
  REST-API + React-SPA-Auslieferung auf Port 8200.
- `src/bewerbungs_assistent/export.py`
  PDF/DOCX-Erzeugung (fpdf2 + python-docx).
- `src/bewerbungs_assistent/job_scraper/`
  Dispatcher plus 17 Quellen (11 Festanstellung + 4 Freelance + 2 Netzwerk).

## Datenbank

21 Tabellen, wichtige Merkmale:

- Profil-Isolation über profile_id
- WAL Mode + Foreign Keys mit CASCADE
- Migrationskette v1→v15 (voll abwärtskompatibel)
- Content-Hashing (SHA256) für Deduplizierung
- E-Mail-Tabellen: application_emails, application_meetings (seit v15)

## Datenpfade

- Windows: `%LOCALAPPDATA%/BewerbungsAssistent/pbp.db`
- Linux: `~/.bewerbungs-assistent/pbp.db`
- überschreibbar über `BA_DATA_DIR`

## Teststand

317 Tests in 13 Testdateien + conftest, alle grün:

- test_database.py (33), test_scoring.py (24), test_export.py (8)
- test_v010.py (43), test_dashboard.py (44), test_v013.py (14)
- test_v020.py (80), test_email_service.py (46)
- test_mcp_registry.py (3), test_scrapers.py (3)
- test_profile_service.py (5), test_search_service.py (5), test_workspace_service.py (5)
- test_dashboard_browser.py (3)

## Wichtige Doku

- `README.md` — Maßgebliche öffentliche Dokumentation (Nutzen, Installation, Features, FAQ)
- `CHANGELOG.md` — Vollständiges Änderungsprotokoll aller Versionen
- `AGENTS.md` — Kurzreferenz für KI-Agenten (Architektur, Konventionen)
- `DOKUMENTATION.md` — Ausführliche Feature-Dokumentation
- `ZUSTAND.md` — Aktueller Systemzustand (Stand v0.30.0)

## Credits

- **Markus Birzite** — Konzept, Architektur, Projektleitung
- **Claude (Anthropic)** — Hauptentwickler seit v0.1.0
- **Codex (OpenAI)** — Code-Analyse, Recovery, Bugfixes
- **Toms (@Koala280)** — React 19 Frontend (v0.23.0), UX-Issues
- **ELWOSA** — Projektrahmen und Infrastruktur
