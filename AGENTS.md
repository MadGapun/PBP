# AGENTS.md — PBP (Persönliches Bewerbungs-Portal)

> **Version:** 0.13.0 (Stand: 2026-03-08)
> **Detaillierte Doku:** `ZUSTAND.md` (aktueller Systemzustand), `README.md`, `DOKUMENTATION.md`
> **Codex-Analyse:** `docs/CODEX_ANALYSE.md` | **Verbesserungsplan:** `docs/VERBESSERUNGSPLAN.md`

## Projektübersicht

PBP ist ein MCP-Server für Claude Desktop, der bei der gesamten Jobsuche und Bewerbung
unterstützt — vom Profil-Aufbau über die Stellensuche bis zum Bewerbungstracking.

**Sprache:** Deutsch
**Tech-Stack:** Python 3.11+, FastMCP, SQLite (WAL Mode), FastAPI, Playwright
**Eigentümer:** Markus (kein Programmierer, nutzt PBP über Claude Desktop)
**Tests:** 159 Tests, alle grün

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
    │   ├── profil.py       — Profilverwaltung, Positionen, Skills, Ausbildung
    │   ├── dokumente.py    — Dokumenten-Upload, Extraktion, Analyse
    │   ├── jobs.py         — Stellensuche, Bewertung, Suchkriterien
    │   ├── bewerbungen.py  — Bewerbungstracking, Status, Timeline
    │   ├── analyse.py      — Fit-Analyse, Skill-Gap, Statistiken, Trends
    │   ├── export_tools.py — Lebenslauf/Anschreiben als PDF/DOCX
    │   └── suche.py        — Jobsuche starten/Status prüfen
    │
    ├── prompts.py          ◄── 12 MCP-Prompts
    ├── resources.py        ◄── 6 MCP-Resources
    │
    ├── database.py         ◄── 15 Tabellen, WAL, Schema v8, Profil-Isolation
    │
    ├── dashboard.py        ◄── FastAPI :8200, 47+ API-Endpoints
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

## Deployment

### Lokal (Windows — Hauptnutzung)
- Installiert via `INSTALLIEREN.bat` (Zero-Knowledge Installer)
- Läuft als MCP-Server in Claude Desktop
- SQLite-Datenbank lokal unter `~/.pbp/`

### Server (ELWOSA — sekundär)
- Server-Pfad: `/home/chatgpt/pbp/bewerbungs-assistent/`
- Git-Repo: `/home/claude/PBP/`
- PBP nutzt ELWOSA nur als Hosting-Plattform — KEINE Code-Abhängigkeit

## Setup & Tests

```bash
# Windows: Doppelklick
INSTALLIEREN.bat

# Manuell
pip install -e ".[dev]"

# Tests (159 Tests)
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
