# AGENTS.md â€” PBP (PersÃ¶nliches Bewerbungs-Portal)

> **Version:** 0.32.5 (Stand: 2026-03-24)
> **Detaillierte Doku:** `README.md`, `CHANGELOG.md`

## ProjektÃ¼bersicht

PBP ist ein MCP-Server fÃ¼r Claude Desktop, der bei der gesamten Jobsuche und Bewerbung
unterstÃ¼tzt â€” vom Profil-Aufbau Ã¼ber die Stellensuche bis zum Bewerbungstracking.

**Sprache:** Deutsch
**Tech-Stack:** Python 3.11+, FastMCP, SQLite (WAL Mode), FastAPI, React 19, Playwright
**Tests:** 360 Tests, 4 bewusst geskippt

## Architektur

```
Claude Desktop
    â”‚ stdio (MCP Protocol)
    â–¼
server.py (FastMCP, ~140 Zeilen)  â—„â”€â”€ Composition Root, registriert Module
    â”‚
    â”œâ”€â”€ tools/              â—„â”€â”€ 66 MCP-Tools in 8 Modulen
    â”‚   â”œâ”€â”€ profil.py       â€” Profilverwaltung, Multi-Profil, Erfassungsfortschritt
    â”‚   â”œâ”€â”€ dokumente.py    â€” Dokumenten-Analyse, Extraktion, Profil-Im/Export
    â”‚   â”œâ”€â”€ jobs.py         â€” Jobsuche, Stellenverwaltung, Fit-Analyse
    â”‚   â”œâ”€â”€ bewerbungen.py  â€” Bewerbungstracking, Status, Statistiken
    â”‚   â”œâ”€â”€ analyse.py      â€” Gehalt, Trends, Skill-Gap, Follow-ups
    â”‚   â”œâ”€â”€ export_tools.py â€” Lebenslauf/Anschreiben als PDF/DOCX
    â”‚   â”œâ”€â”€ suche.py        â€” Suchkriterien und Blacklist
    â”‚   â””â”€â”€ workflows.py    â€” GefÃ¼hrte Workflows
    â”‚
    â”œâ”€â”€ prompts.py          â—„â”€â”€ 14 MCP-Prompts
    â”œâ”€â”€ resources.py        â—„â”€â”€ 6 MCP-Resources
    â”‚
    â”œâ”€â”€ services/           â—„â”€â”€ Service-Layer (profile/search/workspace/email)
    â”œâ”€â”€ database.py         â—„â”€â”€ Schema v15, WAL, CASCADE
    â”‚
    â”œâ”€â”€ dashboard.py        â—„â”€â”€ FastAPI, React-SPA, REST-API
    â”‚
    â”œâ”€â”€ export.py           â—„â”€â”€ Lebenslauf + Anschreiben (PDF/DOCX)
    â”‚
    â””â”€â”€ job_scraper/        â—„â”€â”€ 17 Quellen
        â”œâ”€â”€ __init__.py     â€” Dispatcher, Scoring, Deduplizierung
        â””â”€â”€ *.py            â€” Bundesagentur, StepStone, LinkedIn, XING, etc.
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
python start_dashboard.py  # â†’ http://localhost:8200
```

## Wichtige Konventionen

- **Profil-Isolation** â€” Jedes Profil hat eigene Daten, Multi-Profil-Support
- **STAR-Methode** â€” Projekte im STAR-Format (Situation, Task, Action, Result)
- **Deutsche UI** â€” Alle Texte, Logs und OberflÃ¤chen auf Deutsch
- **Keine API-Keys im Code** â€” Umgebungsvariablen oder .env
- **Playwright fÃ¼r Scraping** â€” Headless Browser fÃ¼r Jobportale
- **SQLite WAL + CASCADE** â€” Foreign Keys mit ON DELETE CASCADE
- **Modular** â€” Tools in fachliche Module aufteilen, server.py bleibt schlank

## Branches

- `main` â€” Stabiler Hauptbranch
- Feature-Branches fÃ¼r neue Funktionen

## Dokumentation

1. **`README.md`** â€” Projektbeschreibung, Installation, Nutzung, vollstÃ¤ndige Tool-Referenz
2. **`CHANGELOG.md`** â€” Ã„nderungsprotokoll aller Versionen



---

## Chat<>Code Arbeitsteilung

Dieses Projekt wird von zwei Claude-Instanzen gemeinsam entwickelt:

| Rolle | Tool | Arbeitsbereich | Aufgabe |
|---|---|---|---|
| **Claude Chat** | claude.ai (Browser) | Windows, lokale Analyse | Analyse, Issues schreiben, Sparring mit Markus, lokale DB/Datei-Checks |
| **Claude Code** | Claude Code (CLI) | ELWOSA (Linux), Repo | Implementierung, Tests, Commits, PRs |

### Fuer Claude Code: Wie Issues von Chat strukturiert sind

Issues mit Label `bug` oder `enhancement` von Chat enthalten:
1. **Betrifft** - Datei(en) + Zeilennummern
2. **Ursachenanalyse** - Hypothesen (verifizieren bevor aendern!)
3. **Betroffene Dateien** - Tabelle mit was zu pruefen/aendern ist
4. **Akzeptanzkriterien** - verbindliche Checklist fuer "fertig"

### Pflichtschritte (Code)

```bash
# Vor und nach jeder Aenderung
python -m pytest tests/ -q

# Bei JSX-Aenderungen: Bundle MUSS committed werden
cd frontend && pnpm run build
```

### Scope halten

- Nur was im Issue steht, kein opportunistisches Refactoring
- Bei Unklarheiten: Kommentar im Issue, nicht raten
- `profile_id`-Filter nie vergessen (Multi-Profil!)
- Schema-Migrationen bei neuen DB-Feldern nicht vergessen
- Playwright nur sync, kein async (Issue #238)
