# Changelog

Alle wichtigen Aenderungen am Bewerbungs-Assistent werden hier dokumentiert.

## [0.11.1] — 2026-03-07

### Konsolidierung
- **ZUSTAND.md** komplett auf realen Stand gebracht (war v1.0.0, jetzt v0.11.0 mit 44 Tools, Schema v8, 108 Tests)
- **README.md** korrigiert: 9 Jobquellen (statt 8), 108 Tests (statt 100/85), freelance_de.py im Architekturdiagramm ergaenzt, Changelog auf letzte 3 Versionen gekuerzt
- **AGENTS.md** korrigiert: 9 Quellen (statt 8), freelance_de.py in Architektur ergaenzt
- **docs/architecture.md** synchronisiert: 9 Scraper, 108 Tests
- **docs/codex_context.md** synchronisiert: 9 Portale, 108 Tests
- **docs/VERBESSERUNGSPLAN.md** NEU: Priorisierter Verbesserungsplan (Prio 1-3) auf Basis der Codex-Analyse

## [0.11.0] — 2026-03-06

### Neue Features
- **Form-Validierung** (OPT-004): Pflichtfeld-Pruefung in allen Formularen (Client + Server). Visuelle Hervorhebung mit rotem Rand und Fehlermeldung. E-Mail- und Datums-Validierung.
- **Ladeanimationen** (OPT-009): Spinner beim Laden aller Seiten (Dashboard, Profil, Stellen, Bewerbungen). Loading-Zustand auf Submit-Buttons verhindert Doppelklicks.
- **Paginierung Bewerbungen** (OPT-010): Bewerbungs-Tab laed 20 Eintraege pro Seite. "Mehr laden" Button mit Zaehler. API unterstuetzt `limit`/`offset` Parameter.
- **Auto-Apply Extraktion**: `extraktion_anwenden(auto_apply=True)` ist Standard. Daten werden ohne Rueckfragen uebernommen, nur echte Konflikte werden uebersprungen.
- **Standalone-Projekte**: Extrahierte Projekte (STAR-Format) werden automatisch der passenden Position zugeordnet.

### Bugfixes
- **KRITISCH**: Felder (email, phone, address, summary) waren nach Extraktion leer — `summary` fehlte in der persoenliche_daten-Feldliste, und aktualisierte Profile wurden nicht zwischen Schritten neu gelesen.
- Profilname blieb "Mein Profil" statt automatisch auf extrahierten Namen zu wechseln — Default-Name wird jetzt als leer behandelt.
- Projekte bei doppelten Positionen wurden komplett uebersprungen — neue Projekte werden jetzt trotzdem hinzugefuegt.
- Praeferenzen konnten beim Multi-Step-Update ueberschrieben werden — Profil wird nach jedem Schritt neu gelesen.

### Optimierungen abgeschlossen
- OPT-003: Error-Handling (bereits seit v0.10.0)
- OPT-004: Form-Validierung ✓ NEU
- OPT-008: Scraper-Keywords konfigurierbar (bereits seit v0.10.0)
- OPT-009: Ladeanimationen ✓ NEU
- OPT-010: Paginierung ✓ NEU
- OPT-011: Test-Suite (bereits seit v0.10.0, 108 Tests)

## [0.10.5] — 2026-03-06

### Bugfixes
- Markdown-Dateien (.md, .csv, .json, .xml, .rtf) werden als Plain-Text extrahiert

## [0.10.4] — 2026-03-06

### Neue Features
- Feldnamen-Aliase (adresse→address, kurzprofil→summary, etc.)
- Bulk-Import fuer Skills, Positionen, Projekte, Ausbildung
- Feld-Validierung mit Feedback bei unbekannten Feldnamen

### Bugfixes
- Vollstaendigkeits-Check erkennt jetzt address und summary Aliase

## [0.10.3] — 2026-03-06

### Bugfixes
- Dokument-Upload ohne Profil: Auto-Profil wird erstellt
- Verwaiste Dokumente werden automatisch adoptiert

## [0.10.2] — 2026-03-06

### Neue Features
- Smart Next-Steps (kontextabhaengige Empfehlungen)
- Onboarding Dokument-Upload als 3. Wizard-Option
- Actionable Empty States mit direkten Aktionsbuttons
- Clean Shutdown mit atexit/signal-Handlern

## [0.10.1] — 2026-03-06

### Neue Features
- Factory Reset
- Runtime-Log Viewer
- Extraktions-Historie leeren

### Bugfixes
- Profil loeschen repariert (automatischer Wechsel)
- Daten-Isolation zwischen Profilen (profile_id auf jobs/applications)
- Schema v7 → v8

## [0.10.0] — 2026-03-05

### Neue Features
- Onboarding-Wizard (4 Schritte)
- Bewerbungs-Wizard (5 Schritte)
- Gehalts-Schaetzungs-Engine
- Quellen-Banner und Such-Reminder
- Hint-System (per-Hint dismissbar + Expertenmodus)
- Gehaltsfilter und Tooltips

### Scraper-Reparatur
- StepStone, Indeed, Monster: Komplett auf Playwright umgestellt
- XING: Selektoren repariert
- Freelancermap: Playwright-Fallback

## [0.9.0] — 2026-03-04

- Multi-Profil Support
- KI-Features (Interview-Simulation, Gehaltsverhandlung, Netzwerk-Strategie)
- 12 MCP-Prompts
- 44 MCP-Tools

## [0.8.0] — 2026-03-03

- Profil Import/Export (JSON-Backup)
- Dashboard mit 5 Tabs
- 8 Job-Scraper

## [0.7.0] — 2026-03-02

- KI-Features (Fit-Analyse, Profil-Analyse)
- Scoring-Engine

## [0.6.0] — 2026-03-01

- Multi-Profil Unterstuetzung

## [0.5.0] — 2026-02-28

- Dashboard, Bewerbungs-Tracking
- Scraper (Bundesagentur, Hays)

## [0.4.0] — 2026-02-27

- MCP Server Grundstruktur
- SQLite Database
- Profil-Management

## [1.0.0] — 2026-02-26

- Initial Release
