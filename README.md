# PBP — Persönliches Bewerbungs-Portal

> Dein KI-gestützter Bewerbungsassistent für Claude Desktop

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Claude_Desktop-orange.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-65%20passing-brightgreen.svg)](#tests)

---

## Was ist PBP?

PBP ist ein **MCP-Server für Claude Desktop**, der dich bei der gesamten Jobsuche und Bewerbung unterstützt — vom Profil-Aufbau über die Stellensuche bis zum Bewerbungstracking. Alles gesteuert durch natürliche Sprache in Claude.

**Kein Formular-Ausfüllen.** Du unterhältst dich einfach mit Claude, und PBP kümmert sich um den Rest.

### Highlights

- 🗣️ **Gesprächsbasierte Profilerstellung** — Claude führt ein lockeres Interview und baut dein Profil auf (STAR-Methode für Projekte)
- 🔍 **Multi-Quellen Jobsuche** — 8 Jobportale gleichzeitig durchsuchen (Bundesagentur, StepStone, Hays, LinkedIn, u.v.m.)
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
server.py (FastMCP)  ◄── 29 Tools, 6 Resources, 8 Prompts
    │
    ▼
database.py (SQLite)  ◄── 13 Tabellen, WAL Mode, Schema v3, Multi-Profil
    │
    ├──► dashboard.py (FastAPI :8200)  ◄── 32 API Endpoints
    │         │
    │         ▼
    │     dashboard.html (SPA)  ◄── 5 Tabs, Vanilla JS
    │
    ├──► export.py  ◄── Lebenslauf + Anschreiben (PDF/DOCX)
    │
    └──► job_scraper/ (8 Quellen)
              │
              ├── bundesagentur.py   (REST API)
              ├── stepstone.py       (BeautifulSoup)
              ├── hays.py            (Sitemap + JSON-LD)
              ├── freelancermap.py   (JS State Extraction)
              ├── linkedin.py        (Playwright)
              ├── indeed.py          (httpx + BS4)
              ├── xing.py            (Playwright)
              └── monster.py         (httpx + BS4)
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

PBP durchsucht bis zu 8 Portale gleichzeitig und bewertet die Ergebnisse automatisch.

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

### 29 Tools

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
| `profil_loeschen` | Profil löschen (nicht das aktive) |
| `erfassung_fortschritt_lesen` | Ersterfassungs-Fortschritt abrufen |
| `erfassung_fortschritt_speichern` | Fortschritt pro Bereich speichern |
| `dokument_profil_extrahieren` | Profildaten aus Dokument extrahieren |
| `dokumente_zur_analyse` | Dokumente mit extrahierbarem Text auflisten |
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

### 6 Resources

| URI | Beschreibung |
|-----|-------------|
| `profil://aktuell` | Vollständiges Bewerberprofil |
| `jobs://aktiv` | Aktive Stellenangebote (nach Score sortiert) |
| `jobs://aussortiert` | Aussortierte Jobs mit Begründung |
| `bewerbungen://alle` | Alle Bewerbungen mit Status |
| `bewerbungen://statistik` | Bewerbungsstatistiken |
| `config://suchkriterien` | Aktuelle Sucheinstellungen |

### 8 Prompts

| Prompt | Beschreibung |
|--------|-------------|
| `ersterfassung` | Gesprächsbasierte Profilerstellung (4 Phasen) |
| `bewerbung_schreiben` | Stellenspezifisches Anschreiben |
| `interview_vorbereitung` | Interview-Prep mit STAR-Antworten |
| `profil_ueberpruefen` | Profil prüfen und korrigieren |
| `profil_analyse` | Stärken, Potenziale, Marktposition |
| `willkommen` | Begrüßung und Statusübersicht |
| `jobsuche_workflow` | Geführter 5-Schritte Suchprozess |
| `bewerbungs_uebersicht` | Komplettübersicht aller Aktivitäten |

---

## Datenbank

SQLite mit WAL-Mode, 13 Tabellen, Schema v3 (Multi-Profil):

| Tabelle | Beschreibung |
|---------|-------------|
| `profile` | Bewerberprofil + Präferenzen (Multi-Profil, Fortschritt) |
| `positions` | Berufserfahrung |
| `projects` | STAR-Projekte (→ positions) |
| `education` | Ausbildung |
| `skills` | Kompetenzen (5 Kategorien) |
| `documents` | Hochgeladene Dokumente |
| `jobs` | Stellenangebote (8 Quellen) |
| `applications` | Bewerbungen (6 Status-Stufen) |
| `application_events` | Bewerbungs-Timeline |
| `search_criteria` | Suchfilter |
| `blacklist` | Ausschlussliste |
| `background_jobs` | Async-Tasks |
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
│   ├── server.py                 # MCP Server (29 Tools, 6 Resources, 8 Prompts)
│   ├── database.py               # SQLite Layer (13 Tabellen)
│   ├── dashboard.py              # FastAPI Dashboard (32 Endpoints)
│   ├── export.py                 # PDF/DOCX Export
│   ├── logging_config.py         # Zentrales Logging
│   ├── templates/
│   │   └── dashboard.html        # SPA Frontend (5 Tabs)
│   └── job_scraper/
│       ├── __init__.py           # Orchestrator + Scoring
│       ├── bundesagentur.py      # Bundesagentur für Arbeit (REST)
│       ├── stepstone.py          # StepStone (BS4)
│       ├── hays.py               # Hays (Sitemap)
│       ├── freelancermap.py      # Freelancermap (JS)
│       ├── freelance_de.py       # Freelance.de
│       ├── linkedin.py           # LinkedIn (Playwright)
│       ├── indeed.py             # Indeed (BS4)
│       ├── xing.py               # XING (Playwright)
│       └── monster.py            # Monster (BS4)
│
├── tests/                        # 65 Tests (pytest)
│   ├── test_database.py
│   ├── test_scoring.py
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

# 65 Tests, ~2 Sekunden
# ✓ 34 Datenbank-Tests
# ✓ 19 Scoring-Tests
# ✓  8 Export-Tests (+ 4 Edge-Cases)
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

- **Erweiterte KI-Features** (PBP-014) — Weiterführende KI-gestützte Bewerbungsoptimierung
- **Screenshots für README** — Automatisierte Dashboard-Screenshots via Playwright

---

## Changelog

### v0.6.0 — Multi-Profil, Fortführbare Ersterfassung & UX (2026-03-02)
- Feature: **Multi-Profil-Support** (PBP-025) — Mehrere Profile pro PC, Profil-Wechsel im Dashboard und via MCP-Tools
- Feature: **Fortführbare Ersterfassung** (PBP-026) — Profil-Gespräch pausieren und später nahtlos fortsetzen
- Feature: **UX-Verbesserungen** (PBP-027) — Tooltips, Copy-Buttons für `/ersterfassung`, Claude Desktop Restart-Hinweis
- Feature: **Dokument-Profil-Extraktion** (PBP-028) — Hochgeladene Dokumente werden automatisch für Profildaten analysiert
- Schema: Datenbank-Migration v2→v3 (is_active, erfassung_fortschritt, profile_id FKs)
- Dashboard: Profil-Switcher in der Navigationsleiste
- Dashboard: Verbesserte Willkommensseite mit Ersterfassungs-Anleitung
- Tools: 8 neue MCP-Tools (21→29 gesamt)
- API: 4 neue Dashboard-Endpoints (28→32 gesamt)

### v0.5.1 — Abbrechen-Button Fix (2026-03-02)
- Fix: Abbrechen-Buttons in Modal-Dialogen funktionieren jetzt korrekt
- Feature: Escape-Taste schließt Modal-Dialoge

### v0.5.0 — Installer-Fix Delayed Expansion (2026-03-02)
- Fix: `!variable!`-Syntax für CMD.exe Delayed Expansion wiederhergestellt
- Fix: PowerShell-Variablen in Expand-Archive korrekt escaped
- Feature: Vollständiger Installationsdurchlauf (Python + pip + Pakete + Claude Desktop Config)
- Getestet und funktionsfähig auf Windows 10/11

### v0.4.0 — Installer GOTO-Refactoring (2026-03-02)
- Fix: GOTO-basierte Fehlerbehandlung im Windows-Installer
- Fix: PowerShell Expand-Archive statt tar für ZIP-Entpackung
- Fix: Debug-Logging zwischen allen Installationsschritten

### v0.3.0 — Installer Update (2026-03-02)
- Umstellung auf curl.exe für Downloads (Windows 10+ built-in)
- Nur ASCII-Zeichen im Installer

### v0.2.0 — Installer Bugfix (2026-03-02)
- Fix: PowerShell exit-Bug der BAT-Prozess beendete
- Fix: ExecutionPolicy Bypass hinzugefügt

### v0.1.0 — Erster Release (2026-03-02)
- Vollständiger MCP-Server mit 21 Tools, 6 Resources, 8 Prompts
- Web-Dashboard mit 5 Tabs
- 8 Job-Scraper (Bundesagentur, StepStone, Hays, Freelancermap, LinkedIn, Indeed, XING, Monster)
- Intelligentes Scoring-System
- PDF/DOCX Export für Lebenslauf und Anschreiben
- Bewerbungs-Tracking mit Timeline
- Windows Zero-Knowledge Installer
- 65 Tests bestanden

---

## Lizenz

[MIT License](LICENSE) — Markus Birzite

---

## Autor

**Markus Birzite** — PLM/PDM Systemarchitekt
