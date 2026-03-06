# AGENTS.md — PBP (Persönliches Bewerbungs-Portal)

## Projektübersicht

PBP ist ein MCP-Server für Claude Desktop, der bei der gesamten Jobsuche und Bewerbung
unterstützt — vom Profil-Aufbau über die Stellensuche bis zum Bewerbungstracking.

**Sprache:** Deutsch
**Tech-Stack:** Python 3.11+, FastMCP, SQLite (WAL Mode), FastAPI, Playwright

## Architektur

- **MCP Server** (`src/bewerbungs_assistent/server.py`) — 44 Tools, 6 Resources, 12 Prompts
- **Datenbank** (`src/bewerbungs_assistent/database.py`) — SQLite, 15 Tabellen, Schema v8
- **Dashboard** (`src/bewerbungs_assistent/dashboard.py`) — FastAPI auf Port 8200, 43+ Endpoints
- **Export** (`src/bewerbungs_assistent/export.py`) — Lebenslauf + Anschreiben als PDF/DOCX
- **Job Scraper** (`src/bewerbungs_assistent/job_scraper/`) — 8 Quellen (Bundesagentur, StepStone, etc.)

## Setup & Tests

```bash
# Installation (Windows)
Doppelklick auf INSTALLIEREN.bat

# Manuell
pip install -e ".[dev]"

# Tests ausführen
python -m pytest tests/ -v
```

## Wichtige Konventionen

- **Profil-Isolation** — Jedes Profil hat eigene Daten, Multi-Profil-Support
- **STAR-Methode** — Projekte werden im STAR-Format erfasst (Situation, Task, Action, Result)
- **Deutsche UI** — Alle Texte, Logs und Oberflächen auf Deutsch
- **Keine API-Keys im Code** — Umgebungsvariablen oder .env verwenden
- **Playwright für Scraping** — Headless Browser für Jobportale

## Branches

- `main` — Stabiler Hauptbranch

## Dokumentation

- `README.md` — Vollständige Projektdokumentation
- `DOKUMENTATION.md` — Technische Details
- `CHANGELOG.md` — Änderungsprotokoll
- `ZUSTAND.md` — Aktueller Projektstatus
- `OPTIMIERUNGEN.md` — Geplante Verbesserungen
- `docs/` — Weitere Dokumentation

## Dashboard starten

```bash
python start_dashboard.py
# Oder: Doppelklick auf "Dashboard starten.bat"
# Öffnet http://localhost:8200
```
