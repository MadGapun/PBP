# PBP — Persönliches Bewerbungs-Portal

> Dein KI-gestützter Bewerbungsassistent für Claude Desktop

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Claude_Desktop-orange.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-159%20passing-brightgreen.svg)](#tests)

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
server.py (FastMCP)  ◄── 44 Tools, 6 Resources, 12 Prompts
    │
    ▼
database.py (SQLite)  ◄── 15 Tabellen, WAL Mode, Schema v8, Profil-Isolation
    │
    ├──► dashboard.py (FastAPI :8200)  ◄── 43+ API Endpoints
    │         │
    │         ▼
    │     dashboard.html (SPA)  ◄── 5 Tabs, Vanilla JS
    │
    ├──► export.py  ◄── Lebenslauf + Anschreiben (PDF/DOCX)
    │
    └──► job_scraper/ (9 Quellen)
              │
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

SQLite mit WAL-Mode, 15 Tabellen, Schema v8 (Profil-Isolation + Factory-Reset):

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
│   ├── server.py                 # MCP Server (44 Tools, 6 Resources, 12 Prompts)
│   ├── database.py               # SQLite Layer (15 Tabellen, Schema v8)
│   ├── dashboard.py              # FastAPI Dashboard (43+ Endpoints)
│   ├── export.py                 # PDF/DOCX Export
│   ├── logging_config.py         # Zentrales Logging
│   ├── templates/
│   │   └── dashboard.html        # SPA Frontend (5 Tabs)
│   └── job_scraper/
│       ├── __init__.py           # Orchestrator + Scoring
│       ├── bundesagentur.py      # Bundesagentur für Arbeit (REST)
│       ├── stepstone.py          # StepStone (Playwright)
│       ├── hays.py               # Hays (Sitemap)
│       ├── freelancermap.py      # Freelancermap (httpx + Playwright)
│       ├── freelance_de.py       # Freelance.de
│       ├── linkedin.py           # LinkedIn (Playwright)
│       ├── indeed.py             # Indeed (Playwright)
│       ├── xing.py               # XING (Playwright)
│       └── monster.py            # Monster (Playwright)
│
├── tests/                        # 159 Tests (pytest)
│   ├── test_database.py
│   ├── test_scoring.py
│   ├── test_dashboard.py
│   ├── test_v010.py
│   ├── test_v013.py
│   └── test_export.py
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

# 159 Tests, ~7 Sekunden
# ✓ 33 Datenbank-Tests
# ✓ 24 Scoring-Tests
# ✓ 37 Dashboard-API-Tests
# ✓ 43 v0.10.x Tests (Schema, Profil-Isolation, Next-Steps, Doc-Adoption, Completeness, Bulk)
# ✓ 14 v0.13.0 Tests (FK-Fix, Ordner-Browser, Auto-Analyse, Recursive-Import)
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

## Geplante Features

- **Screenshots für README** — Automatisierte Dashboard-Screenshots via Playwright
- **Erweiterte Scraper** — Zusätzliche Jobportale und verbesserte Datenextraktion

---

## Changelog (letzte 3 Versionen)

> Vollständiges Changelog: [CHANGELOG.md](CHANGELOG.md)

### v0.13.0 — FK-Bugfixes, Auto-Analyse, Ordner-Browser (2026-03-08)
- Fix: **job_hash FK-Constraint** — Leerer String → None, kein FK-Fehler mehr
- Fix: **Reset/Loeschen blockiert** — FK-safe mit PRAGMA + Datenbereinigung
- Feature: **Auto-Analyse** — Dokumente automatisch per Regex ins Profil einpflegen
- Feature: **Ordner-Browser** — Klickbarer Verzeichnis-Browser statt nur Pfad-Eingabe
- Feature: **Unterordner-Option** — Rekursiver Import mit Warnhinweis
- 159 Tests bestanden

### v0.12.0 — Architektur: Modularisierung (2026-03-07)
- server.py (3.261 Zeilen) aufgeteilt in 8 fachliche Module
- 37 neue Dashboard-API-Tests
- 145 Tests bestanden

### v0.11.0 — Validierung, Ladeanimationen, Paginierung (2026-03-06)
- Feature: **Form-Validierung** — Pflichtfeld-Prüfung (Client + Server)
- Feature: **Ladeanimationen** — Spinner + Loading-Buttons
- Feature: **Paginierung Bewerbungen** — 20er Seiten + "Mehr laden"

### v0.10.5 — Markdown & Textdateien Support (2026-03-06)
- Fix: Markdown-Dateien (.md) werden jetzt als Text extrahiert
- Feature: Zusätzliche Formate (.md, .csv, .json, .xml, .rtf)

### v0.10.0 — UX & Scraper Overhaul (2026-03-05)
- Feature: Onboarding-Wizard (4 Schritte) + Bewerbungs-Wizard (5 Schritte)
- Feature: Gehalts-Engine (7 Regex-Patterns + Schätzung)
- Feature: Hint-System, Gehaltsfilter, Quellen-Banner
- Scraper: StepStone, Indeed, Monster auf Playwright; XING, Freelancermap repariert
- Schema v6→v7, 44 Tools, 12 Prompts, 15 Tabellen

---

## Lizenz

[MIT License](LICENSE) — Markus Birzite

---

## Autor

**Markus Birzite** — PLM/PDM Systemarchitekt
