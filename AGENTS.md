# AGENTS.md — PBP (Persönliches Bewerbungs-Portal)

> **Version:** 0.32.5 (Stand: 2026-03-24)
> **Detaillierte Doku:** `README.md`, `CHANGELOG.md`

## Projektübersicht

PBP ist ein MCP-Server für Claude Desktop, der bei der gesamten Jobsuche und Bewerbung
unterstützt — vom Profil-Aufbau über die Stellensuche bis zum Bewerbungstracking.

**Sprache:** Deutsch
**Tech-Stack:** Python 3.11+, FastMCP, SQLite (WAL Mode), FastAPI, React 19, Playwright
**Tests:** 360 Tests, 4 bewusst geskippt

## Architektur

```
Claude Desktop
    │ stdio (MCP Protocol)
    ▼
server.py (FastMCP, ~140 Zeilen)  ◄── Composition Root, registriert Module
    │
    ├── tools/              ◄── 66 MCP-Tools in 8 Modulen
    │   ├── profil.py       — Profilverwaltung, Multi-Profil, Erfassungsfortschritt
    │   ├── dokumente.py    — Dokumenten-Analyse, Extraktion, Profil-Im/Export
    │   ├── jobs.py         — Jobsuche, Stellenverwaltung, Fit-Analyse
    │   ├── bewerbungen.py  — Bewerbungstracking, Status, Statistiken
    │   ├── analyse.py      — Gehalt, Trends, Skill-Gap, Follow-ups
    │   ├── export_tools.py — Lebenslauf/Anschreiben als PDF/DOCX
    │   ├── suche.py        — Suchkriterien und Blacklist
    │   └── workflows.py    — Geführte Workflows
    │
    ├── prompts.py          ◄── 14 MCP-Prompts
    ├── resources.py        ◄── 6 MCP-Resources
    │
    ├── services/           ◄── Service-Layer (profile/search/workspace/email)
    ├── database.py         ◄── Schema v15, WAL, CASCADE
    │
    ├── dashboard.py        ◄── FastAPI, React-SPA, REST-API
    │
    ├── export.py           ◄── Lebenslauf + Anschreiben (PDF/DOCX)
    │
    └── job_scraper/        ◄── 17 Quellen
        ├── __init__.py     — Dispatcher, Scoring, Deduplizierung
        └── *.py            — Bundesagentur, StepStone, LinkedIn, XING, etc.
```

## Setup & Tests

```bash
# Windows: Doppelklick
INSTALLIEREN.bat

# Entwicklung
pip install -e ".[all,dev]"
playwright install chromium

# Tests
python -m pytest tests/ -v

# Dashboard
python start_dashboard.py  # → http://localhost:8200
```

## Wichtige Konventionen

- **Profil-Isolation** — Jedes Profil hat eigene Daten, Multi-Profil-Support
- **STAR-Methode** — Projekte im STAR-Format (Situation, Task, Action, Result)
- **Deutsche UI** — Alle Texte, Logs und Oberflächen auf Deutsch
- **Keine API-Keys im Code** — Umgebungsvariablen oder .env
- **Playwright für Scraping** — Headless Browser für Jobportale
- **SQLite WAL + CASCADE** — Foreign Keys mit ON DELETE CASCADE
- **Modular** — Tools in fachliche Module aufteilen, server.py bleibt schlank

## Branches

- `main` — Stabiler Hauptbranch
- Feature-Branches für neue Funktionen

## Dokumentation

1. **`README.md`** — Projektbeschreibung, Installation, Nutzung, vollständige Tool-Referenz
2. **`CHANGELOG.md`** — Änderungsprotokoll aller Versionen
