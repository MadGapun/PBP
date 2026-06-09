# AGENTS.md — PBP (Persönliches Bewerbungs-Portal)

> **Version:** 1.7.0-beta.100 (Stand: 2026-06-09)
> **Detaillierte Doku:** `README.md`, `CHANGELOG.md`, [Wiki Master-Plan](https://github.com/MadGapun/PBP/wiki/Master-Plan)

## Projektübersicht

PBP ist ein MCP-Server für Claude Desktop, der bei der gesamten Jobsuche und Bewerbung
unterstützt — vom Profil-Aufbau über die Stellensuche bis zum Bewerbungstracking.

**Sprache:** Deutsch
**Tech-Stack:** Python 3.11+, FastMCP 3.x, SQLite (WAL Mode), FastAPI, React 19, Playwright
**Tests:** 1683 Tests (1 bewusst geskippt)

## Architektur

```
Claude Desktop
    │ stdio (MCP Protocol)
    ▼
server.py (FastMCP, ~140 Zeilen)  ◄── Composition Root, registriert Module
    │
    ├── tools/              ◄── 177 MCP-Tools in 11 Modulen
    │   ├── profil.py       — Profilverwaltung, Multi-Profil, Erfassungsfortschritt
    │   ├── dokumente.py    — Dokumenten-Analyse, Extraktion, Profil-Im/Export
    │   ├── jobs.py         — Jobsuche, Stellenverwaltung, Fit-Analyse
    │   ├── bewerbungen.py  — Bewerbungstracking, Status, Statistiken
    │   ├── analyse.py      — Gehalt, Trends, Skill-Gap, Follow-ups
    │   ├── export_tools.py — Lebenslauf/Anschreiben als PDF/DOCX
    │   ├── suche.py        — Suchkriterien und Blacklist
    │   └── workflows.py    — Geführte Workflows
    │
    ├── prompts.py          ◄── 24 MCP-Prompts
    ├── resources.py        ◄── 6 MCP-Resources
    │
    ├── services/           ◄── Service-Layer (profile/search/workspace/email/daily_impulse)
    ├── database.py         ◄── Schema v46, WAL, CASCADE
    │
    ├── dashboard.py        ◄── FastAPI, React-SPA, REST-API
    │
    ├── export.py           ◄── Lebenslauf + Anschreiben (PDF/DOCX)
    │
    └── job_scraper/        ◄── 34 Quellen (6 produktiv, Rest defekt/zurueckgestellt)
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

- `main` — Stabiler Hauptbranch, geschützt
- Feature-Branches für neue Funktionen, PR gegen `main`

## Dokumentation

1. **`README.md`** — Projektbeschreibung, Installation, Nutzung, vollständige Tool-Referenz
2. **`CHANGELOG.md`** — Änderungsprotokoll aller Versionen
3. **`CONTRIBUTING.md`** — Beitragsrichtlinien
4. **`SECURITY.md`** — Sicherheitsrichtlinie
