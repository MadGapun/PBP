# PBP Architektur

## Systemueberblick

PBP (Persoenliches Bewerbungs-Portal) ist ein MCP-Server fuer Claude Desktop,
der den gesamten Bewerbungsprozess unterstuetzt — von der Profilerstellung bis
zum Bewerbungs-Tracking.

```
Claude Desktop (Windows/Mac)
    |
    | stdio (MCP Protocol)
    v
server.py (FastMCP)         <-- 44 Tools, 6 Resources, 12 Prompts
    |
    v
database.py (SQLite)        <-- 15 Tabellen, WAL Mode, Schema v8
    |
    +-- dashboard.py (FastAPI, Port 8200)  <-- Web-Dashboard
    +-- export.py                          <-- PDF/DOCX Export
    +-- job_scraper/                       <-- 8 Jobportal-Scraper
```

## Komponenten

### server.py (3261 Zeilen)
MCP-Server mit FastMCP-Framework. Definiert alle Tools, Resources und Prompts.
Startet den Dashboard-Server in einem Background-Thread.

**Tool-Kategorien (44 Tools):**
- Profil-Management: Erstellung, Bearbeitung, Import/Export
- Jobsuche: Multi-Quellen-Scraping, Favoriten, Bewertung
- Bewerbungen: Tracking, Status-Updates, Timeline
- Dokumente: Upload, Extraktion, Anschreiben-Generierung
- Dashboard: Statistiken, Analyse-Tools
- System: Factory-Reset, Daten-Bereinigung

**Resources (6 Stueck):**
- Profile, Jobs, Bewerbungen, Dokumente, Statistiken, System-Status

**Prompts (12 Stueck):**
- Profil-Interview, Job-Analyse, Anschreiben, Bewerbungsstrategie, etc.

### database.py (1635 Zeilen)
SQLite-Datenbankschicht mit WAL-Modus und Thread-Safety.

**15 Tabellen (Schema v8):**
- `profiles` — Benutzerprofile mit Skills, Erfahrung
- `profile_projects` — STAR-Methode Projekte
- `profile_languages` — Sprachkenntnisse
- `profile_certifications` — Zertifikate
- `jobs` — Gefundene Stellenangebote
- `job_scoring` — Bewertungs-Keywords (MUSS/PLUS/AUSSCHLUSS)
- `applications` — Bewerbungs-Tracking
- `application_events` — Timeline-Events
- `documents` — Hochgeladene Dokumente (Lebenslaeufe, Zeugnisse)
- `scraper_configs` — Scraper-Konfigurationen
- `extraction_cache` — Cache fuer Dokument-Extraktionen
- `favorites` — Favorisierte Stellen
- Plus System- und Meta-Tabellen

### dashboard.py (1029 Zeilen)
FastAPI Web-Dashboard auf `localhost:8200`. Bietet visuelle Uebersicht
ueber Profile, Jobs und Bewerbungen.

### export.py (365 Zeilen)
PDF/DOCX-Export mit fpdf2 und python-docx. Erzeugt professionelle
Lebenslaeufe und Anschreiben.

### job_scraper/ (8 Scraper, 600 Zeilen __init__.py)
Modularer Scraper fuer 8 Jobportale:
- Bundesagentur fuer Arbeit
- StepStone
- Indeed
- LinkedIn
- XING
- Hays
- Monster
- Freelancermap
- Freelance.de

---

## Datenfluss

```
1. Benutzer chattet mit Claude
   |
   v
2. Claude ruft MCP-Tools auf (server.py)
   |
   v
3. server.py fuehrt DB-Operationen aus (database.py)
   |
   v
4. Ergebnis geht zurueck an Claude -> Benutzer

Parallel:
- Dashboard zeigt Daten auf localhost:8200
- Scraper holen Jobs von 8 Portalen
- Export erzeugt PDF/DOCX Dokumente
```

## Technische Details

| Aspekt | Detail |
|--------|--------|
| Python | >= 3.11 |
| MCP Framework | FastMCP >= 2.0 |
| Datenbank | SQLite (WAL, check_same_thread=False) |
| Web Framework | FastAPI + uvicorn |
| PDF | fpdf2 |
| DOCX | python-docx |
| Scraping | Playwright + BeautifulSoup4 |
| Tests | pytest (100 Tests) |
| Package | pyproject.toml (hatchling) |

## Datenspeicherung

SQLite-Datenbank liegt unter:
- Windows: `%APPDATA%/BewerbungsAssistent/data.db`
- Linux: `~/.local/share/BewerbungsAssistent/data.db`

Profil-Isolation: Jedes Profil hat eine eigene `profile_id`,
alle Daten sind daran gebunden.

---

*Stand: 06.03.2026*
