# AGENTS.md — PBP (Persönliches Bewerbungs-Portal)

> **Version:** 0.14.0 (Stand: 2026-03-10)
> **Detaillierte Doku:** `ZUSTAND.md` (aktueller Systemzustand), `README.md`, `DOKUMENTATION.md`
> **Codex-Analyse:** `docs/CODEX_ANALYSE.md` | **Verbesserungsplan:** `docs/VERBESSERUNGSPLAN.md`

## Projektübersicht

PBP ist ein MCP-Server für Claude Desktop, der bei der gesamten Jobsuche und Bewerbung
unterstützt — vom Profil-Aufbau über die Stellensuche bis zum Bewerbungstracking.

**Sprache:** Deutsch
**Tech-Stack:** Python 3.11+, FastMCP, SQLite (WAL Mode), FastAPI, Playwright
**Eigentümer:** Markus (kein Programmierer, nutzt PBP über Claude Desktop)
**Tests:** 190 Tests, alle gruen (aktueller Repo-Stand)

## Team & KI-Rollen

- **PAPA (Claude Desktop/Anthropic)** — Hat PBP technisch implementiert (v0.1–v0.11)
- **Claude Code** — Modularisierung und Konsolidierung (v0.11.1–v0.13.0)
- **MAMA (ChatGPT/OpenAI)** — Strategische Planung und Koordination
- **TANTE (Codex/OpenAI)** — Analyse, Code-Vorlagen, UI, GitHub-Arbeit
- **Markus (OPA)** — Produktverantwortlicher, Endbenutzer

## Architektur (ab v0.12.0 — modularisiert)

```
Claude Desktop (Windows)
    │ stdio (MCP Protocol)
    ▼
server.py (FastMCP, ~140 Zeilen)  ◄── Composition Root, registriert Module
    │
    ├── tools/              ◄── 44 MCP-Tools in 7 Modulen
    │   ├── profil.py       — Profilverwaltung, Multi-Profil, Erfassungsfortschritt
    │   ├── dokumente.py    — Dokumenten-Analyse, Extraktion, Profil-Im/Export
    │   ├── jobs.py         — Jobsuche, Stellenverwaltung, Fit-Analyse
    │   ├── bewerbungen.py  — Bewerbungstracking, Status, Statistiken
    │   ├── analyse.py      — Gehalt, Trends, Skill-Gap, Follow-ups
    │   ├── export_tools.py — Lebenslauf/Anschreiben als PDF/DOCX
    │   └── suche.py        — Suchkriterien und Blacklist
    │
    ├── prompts.py          ◄── 12 MCP-Prompts
    ├── resources.py        ◄── 6 MCP-Resources
    │
    ├── services/          ◄── gemeinsamer Service-Layer (profile/search/workspace)
    ├── database.py         ◄── 15 Kern-Tabellen + user_preferences, WAL, Schema v8
    │
    ├── dashboard.py        ◄── FastAPI :5173, 56 API-Endpoints + Dashboard-Root
    │   └── templates/dashboard.html (SPA, Vanilla JS, 5 Tabs)
    │
    ├── export.py           ◄── Lebenslauf + Anschreiben (PDF/DOCX)
    │
    └── job_scraper/        ◄── 9 Quellen
        ├── __init__.py     — Dispatcher, Scoring, Deduplizierung
        ├── bundesagentur.py (REST API)
        ├── stepstone.py, hays.py, freelancermap.py, freelance_de.py
        └── linkedin.py, indeed.py, xing.py, monster.py
```

### Wichtig: Modularisierung (v0.12.0)

In v0.12.0 wurde `server.py` von ~3200 Zeilen auf ~140 Zeilen reduziert:
- Tools wurden in `tools/` aufgeteilt (7 fachliche Module)
- Prompts nach `prompts.py` extrahiert
- Resources nach `resources.py` extrahiert
- `server.py` ist jetzt nur noch Composition Root

## Versionshistorie (Kurzfassung)

| Version | Wer | Was |
|---------|-----|-----|
| v0.1–v0.10 | PAPA (Claude Desktop) | Kernentwicklung: MCP-Server, DB, Dashboard, Scraper |
| v0.11.0 | PAPA | Validierung, Paginierung, Extraktions-Fixes |
| v0.11.1 | Claude Code | Doku-Konsolidierung (Codex-Analyse integriert) |
| v0.12.0 | Claude Code | Modularisierung (server.py aufgeteilt, 37 Dashboard-Tests) |
| v0.13.0 | Claude Code | FK-Bugfixes, Auto-Analyse, Ordner-Browser, 159 Tests |
| v0.14.0 | Codex + Claude Code | Service-Layer, Dashboard-UX, Workspace-Guidance, 187 Tests |
| nach v0.14.0 | Codex | Dashboard-Browser-Smoke-Tests, 190 Tests im Repo-Stand |

## Deployment

### Lokal (Windows — Hauptnutzung)
- Installiert via `INSTALLIEREN.bat` (Zero-Knowledge Installer)
- Läuft als MCP-Server in Claude Desktop
- SQLite-Datenbank lokal unter `%LOCALAPPDATA%/BewerbungsAssistent\pbp.db`

### Server (ELWOSA — sekundär)
- Server-Pfad: `/home/chatgpt/pbp/bewerbungs-assistent/`
- Git-Repo: `/home/claude/PBP/`
- PBP nutzt ELWOSA nur als Hosting-Plattform — KEINE Code-Abhängigkeit

## Setup & Tests

```bash
# Windows: Doppelklick
INSTALLIEREN.bat

# Fuer den vollen Dev-/Test-Stand
pip install -e ".[all,dev]"
playwright install chromium

# Tests (190 Tests)
python -m pytest tests/ -v

# Dashboard
python start_dashboard.py  # → http://localhost:5173
```

## Wichtige Konventionen

- **Profil-Isolation** — Jedes Profil hat eigene Daten, Multi-Profil-Support
- **STAR-Methode** — Projekte im STAR-Format (Situation, Task, Action, Result)
- **Deutsche UI** — Alle Texte, Logs und Oberflächen auf Deutsch
- **Keine API-Keys im Code** — Umgebungsvariablen oder .env
- **Playwright für Scraping** — Headless Browser für Jobportale
- **SQLite WAL + CASCADE** — Foreign Keys mit ON DELETE CASCADE (ab v0.13.0)
- **Modular** — Tools in fachliche Module aufteilen, server.py bleibt schlank

## Branches

- `main` — Stabiler Hauptbranch
- Feature-Branches für neue Funktionen (z.B. `claude-code/konsolidierung`)

## Dokumentation (nach Wichtigkeit)

1. **`ZUSTAND.md`** — AKTUELL: Kompletter Systemzustand, Architektur, offene Punkte
2. **`README.md`** — Projektbeschreibung, Installation, Nutzung
3. **`docs/CODEX_ANALYSE.md`** — Tiefenanalyse von Codex (Stärken, Risiken, Vorschläge)
4. **`docs/VERBESSERUNGSPLAN.md`** — Priorisierter Umsetzungsplan
5. **`CHANGELOG.md`** — Änderungsprotokoll aller Versionen
6. **`DOKUMENTATION.md`** — Technische Details
7. **`OPTIMIERUNGEN.md`** — Geplante Verbesserungen

## Verwandtes Projekt: ELWOSA

ELWOSA ist das Hauptprojekt (KI-Sprachassistent):
- **GitHub:** https://github.com/MadGapun/ELWOSA
- PBP und ELWOSA teilen denselben Server, sind aber unabhängig
