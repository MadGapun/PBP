# AGENTS.md — PBP (Persönliches Bewerbungs-Portal)

> **Detaillierte Doku:** `README.md` (500+ Zeilen), `DOKUMENTATION.md`, `ZUSTAND.md`

## Projektübersicht

PBP ist ein MCP-Server für Claude Desktop, der bei der gesamten Jobsuche und Bewerbung
unterstützt — vom Profil-Aufbau über die Stellensuche bis zum Bewerbungstracking.

**Sprache:** Deutsch
**Tech-Stack:** Python 3.11+, FastMCP, SQLite (WAL Mode), FastAPI, Playwright
**Eigentümer:** Markus (kein Programmierer, nutzt PBP über Claude Desktop)

## Team & KI-Rollen

- **PAPA (Claude/Anthropic)** — Hat PBP technisch implementiert und deployed
- **MAMA (ChatGPT/OpenAI)** — Strategische Planung
- **TANTE (Codex/OpenAI)** — Code-Vorlagen, UI, GitHub-Arbeit
- **Markus** — Produktverantwortlicher, Endbenutzer

## Architektur

```
Claude Desktop (Windows)
    │ stdio (MCP Protocol)
    ▼
server.py (FastMCP)  ◄── 44 Tools, 6 Resources, 12 Prompts
    │
    ▼
database.py (SQLite)  ◄── 15 Tabellen, WAL Mode, Schema v8, Profil-Isolation
    │
    ├── dashboard.py (FastAPI :8200)  ◄── 43+ API Endpoints
    │         └── dashboard.html (SPA, Vanilla JS, 5 Tabs)
    │
    ├── export.py  ◄── Lebenslauf + Anschreiben (PDF/DOCX)
    │
    └── job_scraper/ (8 Quellen)
          ├── bundesagentur.py (REST API)
          ├── stepstone.py (Playwright)
          ├── hays.py, freelancermap.py, linkedin.py
          ├── indeed.py, xing.py, monster.py
          └── (alle nutzen Playwright für Headless-Scraping)
```

## Deployment

PBP läuft auf zwei Plattformen:

### 1. Lokal (Windows — Hauptnutzung)
- Installiert via `INSTALLIEREN.bat` (Zero-Knowledge Installer)
- Läuft als MCP-Server in Claude Desktop
- SQLite-Datenbank lokal unter `~/.pbp/`

### 2. Server (ELWOSA — sekundär)
- Server-Pfad: `/home/chatgpt/pbp/bewerbungs-assistent/`
- PBP nutzt ELWOSA nur als Hosting-Plattform — KEINE Code-Abhängigkeit
- Release-ZIPs werden über den Voice-Backend-Static-Server ausgeliefert

## Setup & Tests

```bash
# Windows (empfohlen): Doppelklick
INSTALLIEREN.bat

# Manuell
pip install -e ".[dev]"

# Tests
python -m pytest tests/ -v

# Dashboard starten
python start_dashboard.py
# Oder: Doppelklick "Dashboard starten.bat" → http://localhost:8200
```

## Wichtige Konventionen

- **Profil-Isolation** — Jedes Profil hat eigene Daten, Multi-Profil-Support
- **STAR-Methode** — Projekte im STAR-Format (Situation, Task, Action, Result)
- **Deutsche UI** — Alle Texte, Logs und Oberflächen auf Deutsch
- **Keine API-Keys im Code** — Umgebungsvariablen oder .env
- **Playwright für Scraping** — Headless Browser für Jobportale
- **SQLite WAL Mode** — Concurrent Reads, Schema-Migrationen automatisch

## Branches

- `main` — Stabiler Hauptbranch
- Feature-Branches für neue Funktionen erstellen

## Dokumentation (nach Wichtigkeit)

1. **`README.md`** — Vollständige Doku (Architektur, Installation, Nutzung, 500+ Zeilen)
2. **`ZUSTAND.md`** — Aktueller Projektstatus und offene Punkte
3. **`DOKUMENTATION.md`** — Technische Details
4. **`CHANGELOG.md`** — Änderungsprotokoll
5. **`OPTIMIERUNGEN.md`** — Geplante Verbesserungen
6. **`TESTVERSION.md`** — Test-Anleitung

## Verwandtes Projekt: ELWOSA

ELWOSA ist das Hauptprojekt (KI-Sprachassistent):
- **GitHub:** https://github.com/MadGapun/ELWOSA
- PBP und ELWOSA teilen denselben Server, sind aber unabhängig
