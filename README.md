# PBP — Persönliches Bewerbungs-Portal

> Dein KI-gestützter Bewerbungsassistent für Claude Desktop

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Claude_Desktop-orange.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-187%20passing-brightgreen.svg)](#tests)

---

## Was ist PBP?

PBP ist ein **MCP-Server für Claude Desktop**, der dich bei der gesamten Jobsuche und Bewerbung unterstützt — vom Profil-Aufbau über die Stellensuche bis zum Bewerbungstracking. Alles gesteuert durch natürliche Sprache in Claude.

**Kein Formular-Ausfüllen.** Du unterhältst dich einfach mit Claude, und PBP kümmert sich um den Rest.

### Highlights

- 🗣️ **Gesprächsbasierte Profilerstellung** — Claude führt ein lockeres Interview und baut dein Profil auf (STAR-Methode für Projekte)
- 🔍 **Multi-Quellen Jobsuche** — 9 Jobportale gleichzeitig durchsuchen (Bundesagentur, StepStone, Hays, Freelance.de, LinkedIn, u.v.m.)
- 📊 **Intelligentes Scoring** — Stellen werden automatisch nach deinem Profil bewertet (MUSS/PLUS/AUSSCHLUSS Keywords)
- 📝 **Dokument-Export** — Lebenslauf und Anschreiben als PDF oder DOCX, angepasst pro Stelle
- 📈 **Bewerbungs-Tracking** — Pipeline von "offen" bis "Angebot" mit Timeline und Statistiken
- 🌐 **Web-Dashboard** — Browser-Oberfläche auf localhost:8200 für die visuelle Übersicht
- 🖥️ **Zero-Knowledge Installer** — Doppelklick auf `INSTALLIEREN.bat` und alles wird automatisch eingerichtet

---

## Architektur

```
Claude Desktop (Windows)
    │
    │ stdio (MCP Protocol)
    ▼
server.py (FastMCP, Composition Root)
    │
    ├──► tools/            ◄── 44 Tools in 7 Modulen
    ├──► prompts.py        ◄── 12 Prompts
    ├──► resources.py      ◄── 6 Resources
    │
    ├──► database.py       ◄── 15 Kern-Tabellen + user_preferences, WAL, Schema v8
    ├──► dashboard.py      ◄── FastAPI :8200, 56 API-Endpoints + Dashboard-Root
    ├──► export.py         ◄── Lebenslauf + Anschreiben (PDF/DOCX)
    └──► job_scraper/      ◄── 9 Quellen
              ├── bundesagentur.py   (REST API)
              ├── stepstone.py       (Playwright)
              ├── hays.py            (Sitemap + JSON-LD)
              ├── freelancermap.py   (httpx + Playwright Fallback)
              ├── freelance_de.py    (HTML Scraping)
              ├── linkedin.py        (Playwright)
              ├── indeed.py          (Playwright)
              ├── xing.py            (Playwright)
              └── monster.py         (Playwright)
```

---

## Installation

### Windows (Empfohlen)

1. **Lade die [neueste Version](https://github.com/MadGapun/PBP/releases/latest) herunter** (ZIP-Datei)
2. **Entpacke** das ZIP in einen Ordner deiner Wahl (z.B. `C:\PBP`)
3. **Doppelklicke `INSTALLIEREN.bat`** — der Rest passiert automatisch:
   - Python wird heruntergeladen und eingerichtet
   - Alle Pakete werden installiert
   - Claude Desktop wird konfiguriert
   - Eine Desktop-Verknüpfung wird erstellt

> **Voraussetzungen:** Windows 10/11 (64-Bit), Internetverbindung, [Claude Desktop](https://claude.ai/download)

### Linux / Manuell

```bash
# Repository klonen
git clone https://github.com/MadGapun/PBP.git
cd PBP

# Virtual Environment erstellen
python3 -m venv venv
source venv/bin/activate

# Installieren (Kern + Docs)
pip install -e ".[docs]"

# Optional: Scraper mit Playwright
pip install -e ".[all]"
playwright install chromium
```

### Claude Desktop konfigurieren

Nach der Installation muss Claude Desktop den MCP-Server kennen. Die `INSTALLIEREN.bat` macht das automatisch. Für manuelle Konfiguration, füge in `%APPDATA%\Claude\claude_desktop_config.json` hinzu:

```json
{
  "mcpServers": {
    "bewerbungs-assistent": {
      "command": "python",
      "args": ["-m", "bewerbungs_assistent"],
      "env": {
        "BA_DATA_DIR": "C:\\Users\\DEIN_NAME\\AppData\\Local\\BewerbungsAssistent"
      }
    }
  }
}
```

---

## Benutzung

### Erste Schritte

Nach der Installation einfach Claude Desktop öffnen und den Prompt `/ersterfassung` verwenden (oder eintippen: "Ersterfassung starten").

Claude führt dich durch ein lockeres Gespräch und erfasst:
1. Persönliche Daten und Kontakt
2. Berufserfahrung mit Projekten (STAR-Methode)
3. Ausbildung und Skills
4. Gehalts- und Arbeitspräferenzen

> 💡 **Tipp:** Du kannst das Gespräch jederzeit unterbrechen und später fortsetzen — der Fortschritt wird automatisch gespeichert!

### Multi-Profil

Mehrere Benutzer auf einem PC? Kein Problem:

> **"Zeige alle Profile"** — Profile auflisten
> **"Wechsle zu Profil XY"** — Aktives Profil wechseln
> **"Erstelle ein neues Profil für Anna"** — Neues Profil anlegen

Im Dashboard steht der Profil-Wechsler direkt in der Navigationsleiste.

### Jobsuche

> **"Starte eine Jobsuche nach Python Entwickler in Hamburg"**

PBP durchsucht bis zu 9 Portale gleichzeitig und bewertet die Ergebnisse automatisch.

### Bewerbung schreiben

> **"Schreibe ein Anschreiben für die Stelle bei Firma XY"**

Claude erstellt ein personalisiertes Anschreiben basierend auf deinem Profil und der Stellenbeschreibung.

### Web-Dashboard

Das Dashboard läuft auf [http://localhost:8200](http://localhost:8200) und bietet 5 Tabs:

| Tab | Funktion |
|-----|----------|
| **Dashboard** | Übersicht mit Statistiken |
| **Profil** | Profildaten, Skills, Erfahrung bearbeiten |
| **Stellen** | Gefundene Jobs mit Scoring und Fit-Analyse |
| **Bewerbungen** | Pipeline-Ansicht mit Timeline |
| **Einstellungen** | Suchkriterien, Blacklist, Quellen |

---

## MCP-Schnittstelle

### 44 Tools

| Tool | Beschreibung |
|------|-------------|
| `profil_status` | Profilstatus und Übersicht abrufen |
| `profil_zusammenfassung` | Vollständige Profilzusammenfassung |
| `profil_erstellen` | Profil anlegen oder aktualisieren |
| `profil_bearbeiten` | Einzelne Profilbereiche bearbeiten |
| `position_hinzufuegen` | Berufserfahrung hinzufügen |
| `projekt_hinzufuegen` | STAR-Projekt zu einer Position |
| `ausbildung_hinzufuegen` | Ausbildungseintrag anlegen |
| `skill_hinzufuegen` | Kompetenz hinzufügen |
| `profile_auflisten` | Alle Profile auflisten (Multi-Profil) |
| `profil_wechseln` | Aktives Profil wechseln |
| `neues_profil_erstellen` | Neues leeres Profil anlegen |
| `profil_loeschen` | Profil löschen (auch aktives, mit Auto-Switch) |
| `erfassung_fortschritt_lesen` | Ersterfassungs-Fortschritt abrufen |
| `erfassung_fortschritt_speichern` | Fortschritt pro Bereich speichern |
| `dokument_profil_extrahieren` | Profildaten aus Dokument extrahieren |
| `dokumente_zur_analyse` | Dokumente mit extrahierbarem Text auflisten |
| `extraktion_starten` | Dokument-Analyse starten und Texte laden |
| `extraktion_ergebnis_speichern` | Extraktionsergebnis zwischenspeichern |
| `extraktion_anwenden` | Extrahierte Daten auf Profil anwenden |
| `extraktions_verlauf` | Historie aller Extraktionen anzeigen |
| `profil_exportieren` | Profil als JSON-Backup exportieren |
| `profil_importieren` | Profil aus JSON-Backup importieren |
| `jobsuche_starten` | Multi-Quellen Stellensuche starten |
| `jobsuche_status` | Suchfortschritt abfragen |
| `stellen_anzeigen` | Jobs mit Filter und Scoring anzeigen |
| `stelle_bewerten` | Job als passend/unpassend markieren |
| `fit_analyse` | Detaillierte Fit-Analyse für eine Stelle |
| `bewerbung_erstellen` | Neue Bewerbung anlegen |
| `bewerbung_status_aendern` | Bewerbungsstatus aktualisieren |
| `bewerbungen_anzeigen` | Alle Bewerbungen mit Statistiken |
| `statistiken_abrufen` | Conversion Rates und Übersicht |
| `lebenslauf_exportieren` | CV als PDF/DOCX exportieren |
| `anschreiben_exportieren` | Anschreiben als PDF/DOCX |
| `suchkriterien_setzen` | Keywords und Filter konfigurieren |
| `blacklist_verwalten` | Firmen/Keywords ausschließen |
| `gehalt_extrahieren` | Gehalt/Tagessatz aus Stellenbeschreibung extrahieren |
| `gehalt_marktanalyse` | Gehaltsstatistiken über alle gesammelten Stellen |
| `firmen_recherche` | Firmendaten aus Stellenangeboten aggregieren |
| `branchen_trends` | Gefragte Skills und Technologien analysieren |
| `nachfass_planen` | Follow-up Erinnerung für Bewerbung planen |
| `nachfass_anzeigen` | Alle geplanten/fälligen Follow-ups zeigen |
| `bewerbung_stil_tracken` | Anschreiben-Stil für A/B-Tracking speichern |
| `skill_gap_analyse` | Skill-Gap zwischen Profil und Stelle analysieren |
| `ablehnungs_muster` | Ablehnungs-Muster und Empfehlungen analysieren |

### 6 Resources

| URI | Beschreibung |
|-----|-------------|
| `profil://aktuell` | Vollständiges Bewerberprofil |
| `jobs://aktiv` | Aktive Stellenangebote (nach Score sortiert) |
| `jobs://aussortiert` | Aussortierte Jobs mit Begründung |
| `bewerbungen://alle` | Alle Bewerbungen mit Status |
| `bewerbungen://statistik` | Bewerbungsstatistiken |
| `config://suchkriterien` | Aktuelle Sucheinstellungen |

### 12 Prompts

| Prompt | Beschreibung |
|--------|-------------|
| `ersterfassung` | Gesprächsbasierte Profilerstellung (4 Phasen) |
| `profil_erweiterung` | Profil aus Dokumenten erweitern (5-Schritte-Workflow) |
| `bewerbung_schreiben` | Stellenspezifisches Anschreiben |
| `interview_vorbereitung` | Interview-Prep mit STAR-Antworten |
| `profil_ueberpruefen` | Profil prüfen und korrigieren |
| `profil_analyse` | Stärken, Potenziale, Marktposition |
| `willkommen` | Begrüßung und Statusübersicht |
| `jobsuche_workflow` | Geführter 5-Schritte Suchprozess |
| `bewerbungs_uebersicht` | Komplettübersicht aller Aktivitäten |
| `interview_simulation` | Simuliertes Bewerbungsgespräch mit Claude |
| `gehaltsverhandlung` | Gehaltsverhandlung vorbereiten mit Strategie |
| `netzwerk_strategie` | Networking-Plan für eine Zielfirma |

---

## Datenbank

SQLite mit WAL-Mode, 15 Kern-Tabellen + `user_preferences`, Schema v8 (Profil-Isolation + Factory-Reset):

| Tabelle | Beschreibung |
|---------|-------------|
| `profile` | Bewerberprofil + Präferenzen (Multi-Profil, Fortschritt) |
| `positions` | Berufserfahrung |
| `projects` | STAR-Projekte (→ positions) |
| `education` | Ausbildung |
| `skills` | Kompetenzen (5 Kategorien) |
| `documents` | Hochgeladene Dokumente (+ Extraktions-Status) |
| `extraction_history` | Extraktions-Verlauf (Konflikte, angewandte Felder) |
| `jobs` | Stellenangebote (9 Quellen) |
| `applications` | Bewerbungen (6 Status-Stufen, Ablehnungs-Tracking) |
| `application_events` | Bewerbungs-Timeline |
| `search_criteria` | Suchfilter |
| `blacklist` | Ausschlussliste |
| `background_jobs` | Async-Tasks |
| `follow_ups` | Nachfass-Erinnerungen |
| `user_preferences` | Benutzereinstellungen (Wizard, Hints) |
| `settings` | Konfiguration |

**Datenspeicherung:**
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\`
- Linux: `~/.bewerbungs-assistent/`

---

## Projektstruktur

```
PBP/
├── INSTALLIEREN.bat              # Windows Zero-Knowledge Installer
├── Dashboard starten.bat         # Dashboard-Starter (Windows)
├── start_dashboard.py            # Dashboard-Starter (Python)
├── _setup_claude.py              # Claude Desktop Konfiguration
├── _selftest.py                  # Schnelltest
├── pyproject.toml                # Build-Konfiguration
│
├── src/bewerbungs_assistent/
│   ├── server.py                 # Composition Root (~140 Zeilen)
│   ├── tools/                    # 44 MCP-Tools in 7 Modulen
│   │   ├── profil.py             #   Profilverwaltung, Multi-Profil, Erfassung
│   │   ├── dokumente.py          #   Dokument-Analyse, Extraktion, Import/Export
│   │   ├── jobs.py               #   Jobsuche, Stellenverwaltung, Fit-Analyse
│   │   ├── bewerbungen.py        #   Bewerbungstracking, Status, Statistiken
│   │   ├── analyse.py            #   Gehalt, Trends, Skill-Gap, Follow-ups
│   │   ├── export_tools.py       #   Lebenslauf/Anschreiben als PDF/DOCX
│   │   └── suche.py              #   Suchkriterien und Blacklist
│   ├── prompts.py                # 12 MCP-Prompts
│   ├── resources.py              # 6 MCP-Resources
│   ├── services/                 # Gemeinsamer Service-Layer
│   │   ├── profile_service.py    #   Profilstatus, Vollstaendigkeit, Praeferenzen
│   │   ├── search_service.py     #   Suchstatus, Quellenverwaltung
│   │   └── workspace_service.py  #   Workspace-Guidance (7 Readiness-Stufen)
│   ├── database.py               # SQLite (15 Kern-Tabellen + user_preferences, Schema v8)
│   ├── dashboard.py              # FastAPI Dashboard (56 API-Endpoints + Root)
│   ├── export.py                 # PDF/DOCX Export
│   ├── logging_config.py         # Zentrales Logging
│   ├── templates/
│   │   └── dashboard.html        # SPA Frontend (5 Tabs)
│   └── job_scraper/              # 9 Quellen
│       ├── __init__.py           #   Orchestrator + Scoring
│       ├── bundesagentur.py      #   Bundesagentur fuer Arbeit (REST)
│       ├── stepstone.py          #   StepStone (Playwright)
│       ├── hays.py               #   Hays (Sitemap + JSON-LD)
│       ├── freelancermap.py      #   Freelancermap (httpx + Playwright)
│       ├── freelance_de.py       #   Freelance.de (HTML Scraping)
│       ├── linkedin.py           #   LinkedIn (Playwright)
│       ├── indeed.py             #   Indeed (Playwright)
│       ├── xing.py               #   XING (Playwright)
│       └── monster.py            #   Monster (Playwright)
│
├── tests/                        # 187 Tests (pytest)
│   ├── conftest.py               # Fixtures (tmp_db, sample_*)
│   ├── test_database.py          # 33 DB-Tests
│   ├── test_scoring.py           # 24 Scoring-Tests
│   ├── test_export.py            #  8 Export-Tests
│   ├── test_v010.py              # 43 Schema/Profil-Isolation
│   ├── test_dashboard.py         # 44 Dashboard-API-Tests
│   ├── test_v013.py              # 14 Regressionstests
│   ├── test_profile_service.py   #  5 Service-Layer
│   ├── test_search_service.py    #  5 Suchstatus
│   ├── test_workspace_service.py #  5 Workspace-Guidance
│   ├── test_mcp_registry.py      #  3 MCP-Smoke-Tests
│   ├── test_scrapers.py          #  3 Scraper-Fixture-Tests
│   └── fixtures/scrapers/        # HTML/XML-Fixtures
│
└── installer/                    # Alternative Installer
    ├── install.ps1               # PowerShell Installer
    └── install.sh                # Linux Installer
```

---

## Tests

```bash
# Alle Tests ausführen
python -m pytest tests/ -v

# 187 Tests, ~5 Sekunden
# ✓ 33 Datenbank-Tests
# ✓ 24 Scoring-Tests
# ✓ 44 Dashboard-API-Tests
# ✓ 43 v0.10.x Tests (Schema, Profil-Isolation, Next-Steps, Doc-Adoption, Completeness, Bulk)
# ✓ 14 v0.13.0 Tests (FK-Fix, Ordner-Browser, Auto-Analyse, Recursive-Import)
# ✓  5 Service-Layer-Tests (Profilstatus, Praeferenzen, Vollstaendigkeit)
# ✓  5 Search-Service-Tests
# ✓  5 Workspace-Service-Tests
# ✓  3 MCP-Registry-Tests
# ✓  3 Scraper-Fixture-Tests
# ✓  8 Export-Tests (benötigt python-docx + fpdf2)
```

---

## Technologie-Stack

| Komponente | Technologie |
|-----------|-------------|
| **MCP Framework** | [FastMCP](https://github.com/jlowin/fastmcp) ≥2.0 |
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com/) ≥0.115 |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org/) ≥0.30 |
| **Datenbank** | SQLite (WAL Mode) |
| **PDF Export** | [fpdf2](https://github.com/py-pdf/fpdf2) ≥2.7 |
| **Word Export** | [python-docx](https://python-docx.readthedocs.io/) ≥1.1 |
| **PDF Import** | [pypdf](https://github.com/py-pdf/pypdf) ≥4.0 |
| **HTTP Client** | [httpx](https://www.python-httpx.org/) ≥0.27 |
| **HTML Parsing** | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) ≥4.12 |
| **Browser Automation** | [Playwright](https://playwright.dev/python/) ≥1.40 |
| **Laufzeit** | Python ≥3.11 |

---

## Screenshots

### Dashboard — Übersicht mit Workspace-Guidance
![Dashboard](docs/screenshots/01_dashboard.png)

### Profil — Berufserfahrung, Skills, Ausbildung
![Profil](docs/screenshots/02_profil.png)

### Stellen — Scoring und Fit-Analyse
![Stellen](docs/screenshots/03_stellen.png)

### Bewerbungen — Pipeline mit Timeline
![Bewerbungen](docs/screenshots/04_bewerbungen.png)

### Einstellungen — Suchkriterien und Quellen
![Einstellungen](docs/screenshots/05_einstellungen.png)

> Screenshots werden automatisch generiert: `python docs/screenshots/generate_screenshots.py`

---

## Geplante Features

- **Erweiterte Scraper** — Zusätzliche Jobportale und verbesserte Datenextraktion

---

## Changelog (letzte 3 Versionen)

> Vollständiges Changelog: [CHANGELOG.md](CHANGELOG.md)

### v0.14.0 — Service-Layer, Dashboard-UX, Workspace-Guidance (2026-03-10)
- **Service-Layer**: `profile_service.py`, `search_service.py`, `workspace_service.py` — gemeinsame Logik fuer Dashboard und MCP-Tools
- **Dashboard-UX**: Workspace-Kopf mit Guidance, klarere Navigation, Profil-Schnellzugriffe
- **Workspace-Summary API**: `/api/workspace-summary` mit Readiness-Stufen und Handlungsempfehlung
- **MCP-Registry-Tests**: Smoke-Tests fuer alle 44 Tools, 12 Prompts, 6 Resources
- **Scraper-Fixture-Tests**: Hays, Freelance.de, Freelancermap mit stabilen HTML-Fixtures
- 187 Tests bestanden

### v0.13.0 — FK-Bugfixes, Auto-Analyse, Ordner-Browser (2026-03-08)
- Fix: **job_hash FK-Constraint** — Leerer String → None, kein FK-Fehler mehr
- Fix: **Reset/Loeschen blockiert** — FK-safe mit PRAGMA + Datenbereinigung
- Feature: **Auto-Analyse** — Dokumente automatisch per Regex ins Profil einpflegen
- Feature: **Ordner-Browser** — Klickbarer Verzeichnis-Browser statt nur Pfad-Eingabe
- 159 Tests bestanden

### v0.12.0 — Architektur: Modularisierung (2026-03-07)
- server.py (3.261 Zeilen) aufgeteilt in 8 fachliche Module
- 37 neue Dashboard-API-Tests
- 145 Tests bestanden

---

## Lizenz

[MIT License](LICENSE) — Markus Birzite

---

## Autor

**Markus Birzite** — PLM/PDM Systemarchitekt
