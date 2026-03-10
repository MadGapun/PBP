# PBP Architektur

Stand: 2026-03-09
Referenz: Release-Linie v0.13.0 plus laufende Konsolidierung

## Systemueberblick

PBP (Persoenliches Bewerbungs-Portal) ist ein lokal-first MCP-Server fuer Claude Desktop.
Er deckt den Bewerbungsprozess von der Profilerstellung ueber Jobsuche und Dokument-Analyse
bis zum Bewerbungstracking ab.

```text
Claude Desktop (Windows)
    |
    | stdio (MCP Protocol)
    v
server.py (FastMCP, 138 Zeilen)
    |
    +-- tools/              44 MCP-Tools in 7 Modulen
    +-- prompts.py          12 MCP-Prompts
    +-- resources.py        6 MCP-Resources
    +-- services/          gemeinsamer Service-Layer
    +-- database.py         SQLite, Schema v8
    +-- dashboard.py        FastAPI :8200
    +-- export.py           PDF/DOCX Export
    +-- job_scraper/        9 Jobquellen
```

## Komponenten

### server.py

`src/bewerbungs_assistent/server.py` ist seit v0.12.0 nur noch Composition Root.
Die Datei initialisiert Logging, Datenbank und FastMCP, registriert Tools, Prompts
und Resources und startet optional das Dashboard in einem Hintergrund-Thread.

### tools/

Die 44 Tools sind fachlich getrennt:

- `profil.py` - Profilverwaltung, Multi-Profil, Erfassungsfortschritt
- `dokumente.py` - Dokument-Analyse, Extraktion, Profil-Im/Export
- `jobs.py` - Jobsuche, Stellenverwaltung, Fit-Analyse
- `bewerbungen.py` - Bewerbungstracking, Status, Statistiken
- `analyse.py` - Gehalt, Trends, Skill-Gap, Follow-ups
- `export_tools.py` - Lebenslauf- und Anschreiben-Export
- `suche.py` - Suchkriterien und Blacklist

Diese Aufteilung ist der zentrale Strukturgewinn gegenueber dem alten monolithischen
`server.py`.

### prompts.py und resources.py

- `prompts.py` kapselt die 12 MCP-Prompts.
- `resources.py` kapselt die 6 MCP-Resources.

Damit ist die oeffentliche MCP-Schnittstelle in drei klaren Schichten organisiert:
Tools, Prompts und Resources.

### database.py

`src/bewerbungs_assistent/database.py` ist die persistente Basis des Systems.
Aktuell existieren 15 Kern-Tabellen plus `user_preferences` als systemnahe Tabelle.

Wichtige Eigenschaften:

- Schema-Version `v8`
- SQLite WAL Mode
- `foreign_keys=ON`
- automatische Migrationen von aelteren Stufen
- Profil-Isolation ueber `profile_id`

### services/

`src/bewerbungs_assistent/services/` kapselt gemeinsam genutzte Domaenenlogik
zwischen Dashboard und MCP-Tools. Aktuell liegen dort
`profile_service.py`, `search_service.py` und `workspace_service.py`
fuer Profilstatus, Suchstatus/Quellen und die uebergreifende Guidance.

### dashboard.py

`src/bewerbungs_assistent/dashboard.py` stellt das lokale Web-Dashboard bereit.
Der aktuelle Stand umfasst 55 API-Endpoints plus die HTML-Startseite.

Das Dashboard ist bewusst eng an dieselbe lokale Datenbank gekoppelt wie der MCP-Server.
Es ist kein separates SPA-Build-System, sondern ein pragmatisches, leicht deploybares
Frontend fuer den Endnutzer. Neu dazugekommen sind eine verdichtete
`/api/workspace-summary`-Sicht fuer Navigation und Benutzerfuehrung sowie
ein klarerer Workspace-Kopf im Dashboard.

### export.py

`src/bewerbungs_assistent/export.py` erzeugt Lebenslauf und Anschreiben als PDF oder DOCX.
Die Export-Tools im MCP-Layer und die Dashboard-Endpunkte greifen auf dieses Modul zu.

### job_scraper/

`src/bewerbungs_assistent/job_scraper/` enthaelt den Dispatcher und 9 Quellen:

- Bundesagentur
- StepStone
- Hays
- Freelancermap
- Freelance.de
- LinkedIn
- Indeed
- XING
- Monster

Die Quellen sind absichtlich heterogen umgesetzt: REST, HTML-Scraping oder Playwright,
je nachdem was fuer die jeweilige Plattform robust genug ist.

## Datenfluss

```text
1. Nutzer interagiert in Claude Desktop oder im Dashboard
2. MCP-Tools bzw. Dashboard-API rufen dieselbe Domaenenlogik auf
3. database.py liest und schreibt den lokalen Zustand
4. export.py und job_scraper/ ergaenzen Dokumente und Stellenmarktdaten
```

## Datenspeicherung

Die Datenablage folgt direkt dem Code in `database.py`:

- Windows: `%LOCALAPPDATA%/BewerbungsAssistent/pbp.db`
- Linux: `~/.bewerbungs-assistent/pbp.db`
- alternativ explizit ueber `BA_DATA_DIR`

Zusatzverzeichnisse im Datenordner:

- `dokumente/`
- `export/`
- `logs/`

## Qualitaetsstand

Der aktuelle Repo-Stand ist deutlich konsolidierter als in der fruehen Analyse:

- modulare MCP-Struktur statt monolithischem `server.py`
- 187 Tests im Repo
- Dashboard-API-Tests vorhanden
- Regressionstests fuer v0.13.0-Bugfixes vorhanden

Offen bleiben vor allem:

- MCP-Tool-Smoke-Tests weiter ausbauen
- Scraper-Fixture-Tests auf weitere Quellen und Fallbacks ausweiten
- Service-Layer nach Profil/Suche/Workspace auf Bewerbungen weiterziehen
