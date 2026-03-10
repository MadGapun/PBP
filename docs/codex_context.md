# PBP Codex Context

Kurzkontext fuer KI-Assistenten, die im Repo arbeiten.

Stand: 2026-03-10

## Was ist PBP?

PBP (Persoenliches Bewerbungs-Portal) ist ein MCP-Server fuer Claude Desktop.
Das Produkt ist lokal-first, deutschsprachig und fuer einen Endnutzerworkflow gebaut:
Profil aufbauen, Jobs suchen, Dokumente exportieren, Bewerbungen verfolgen.

## Technischer Kern

- Python 3.11+
- FastMCP fuer die Claude-Desktop-Integration
- FastAPI fuer das lokale Dashboard auf Port 8200
- SQLite mit WAL und Migrationen
- Playwright/HTML-Scraping fuer Jobportale

## Struktur

- `src/bewerbungs_assistent/server.py`
  Composition Root, registriert Module und startet das Dashboard.
- `src/bewerbungs_assistent/tools/`
  44 MCP-Tools in 7 Modulen.
- `src/bewerbungs_assistent/prompts.py`
  12 MCP-Prompts.
- `src/bewerbungs_assistent/resources.py`
  6 MCP-Resources.
- `src/bewerbungs_assistent/services/`
  Gemeinsame Profil-, Such- und Workspace-Logik fuer Dashboard und MCP-Tools.
- `src/bewerbungs_assistent/database.py`
  SQLite-Schicht mit Schema v8.
- `src/bewerbungs_assistent/dashboard.py`
  56 API-Endpoints plus Dashboard-Root.
- `src/bewerbungs_assistent/export.py`
  PDF/DOCX-Erzeugung.
- `src/bewerbungs_assistent/job_scraper/`
  Dispatcher plus 9 Quellen.

## Datenbank

Fachlich gibt es 15 Kern-Tabellen plus `user_preferences` als systemnahe Tabelle.
Wichtige Merkmale:

- Profil-Isolation
- WAL Mode
- Foreign Keys
- Migrationskette bis Schema v8

## Datenpfade

Default aus dem Code:

- Windows: `%LOCALAPPDATA%/BewerbungsAssistent/pbp.db`
- Linux: `~/.bewerbungs-assistent/pbp.db`
- ueberschreibbar ueber `BA_DATA_DIR`

## Teststand

Im Repo liegen aktuell 190 Tests:

- `tests/test_database.py`
- `tests/test_scoring.py`
- `tests/test_export.py`
- `tests/test_v010.py`
- `tests/test_dashboard.py`
- `tests/test_v013.py`
- `tests/test_mcp_registry.py`
- `tests/test_scrapers.py`
- `tests/test_profile_service.py`
- `tests/test_search_service.py`
- `tests/test_workspace_service.py`

## Wichtige Doku

- `AGENTS.md`
  Teamrollen, Architektur, Konventionen.
- `ZUSTAND.md`
  Aktueller Systemzustand.
- `docs/CODEX_ANALYSE.md`
  Urspruengliche Codex-Analyse.
- `docs/VERBESSERUNGSPLAN.md`
  Konsolidierungs- und Ausbauplan.

## Was aktuell offen ist

- Scraper-Fixture-Tests auf weitere Quellen und Fallbacks erweitern
- mehr MCP-Tool-Smoke-Tests auf Verhaltensebene
- Service-Layer nach Profil/Suche/Workspace auf Bewerbungen weiterziehen
- weitere Dashboard-Usability-Politur
