# CODEX Analyse: PBP

Stand: 2026-03-07
Branch: `codex/pbp-analyse`

## Kurzfazit

PBP ist kein Prototyp mehr, sondern ein bereits deutlich ausgearbeitetes Produkt mit realer Architektur, persistenter Datenhaltung, lokalem Dashboard, Export-Funktionen und einem vergleichsweise breiten MCP-Interface. Die Grundidee ist technisch schluessig: Claude Desktop ist die sprachliche Oberflaeche, `server.py` kapselt die MCP-Interaktion, `database.py` haelt den Zustand lokal und `dashboard.py` bietet eine zweite Bedienoberflaeche.

Mit dem neuen Kontext aus `AGENTS.md` wird auch die Entstehung nachvollziehbar: Markus ist Produktverantwortlicher und Endnutzer, waehrend der Grossteil der technischen Umsetzung von PAPA/Claude getragen wurde. Genau das sieht man dem Repo an: hohe Feature-Dichte, viele pragmatische Erweiterungen, aber auch einige Inkonsistenzen zwischen Dokumentation, Versionierung und tatsaechlichem Implementierungsstand.

## Teamkontext aus AGENTS.md

- PBP ist ein Endnutzerprodukt fuer Markus und kein generisches Framework.
- PAPA/Claude hat den Hauptteil der technischen Implementierung uebernommen.
- MAMA/ChatGPT wird fuer strategische Planung genannt.
- TANTE/Codex ist fuer Code-Vorlagen, UI und GitHub-Arbeit vorgesehen.

Dieser Kontext ist wichtig, weil er mehrere Architekturentscheidungen erklaert:

- Starke lokale Ausrichtung statt Cloud-zentrierter Architektur
- Fokus auf Zero-Knowledge-Installation fuer Windows
- Viele direkt nutzbare Features in einem monolithischen Python-Paket
- Hohe Bedeutung von Dokumentation und gefuehrten Workflows fuer einen nicht-programmierenden Nutzer

## Reale Ist-Architektur

Der tatsaechliche Code bestaetigt die in `AGENTS.md` beschriebene Richtung weitgehend.

### 1. MCP-Server als Kern

`src/bewerbungs_assistent/server.py` initialisiert `FastMCP`, die Datenbank und registriert Tools, Resources und Prompts. Ueber `rg` sind im aktuellen Stand sichtbar:

- 44 `@mcp.tool()`
- 6 `@mcp.resource(...)`
- 12 `@mcp.prompt()`

Das passt zu `AGENTS.md` und `docs/architecture.md`, aber nicht mehr zu `ZUSTAND.md`, das noch einen aelteren Stand mit 21 Tools und 8 Prompts beschreibt.

### 2. SQLite als zentrales Rueckgrat

`src/bewerbungs_assistent/database.py` ist fuer dieses Projekt ein tragender Bestandteil und sauberer, als man es in einem KI-getriebenen Repo oft sieht:

- `SCHEMA_VERSION = 8`
- WAL-Modus
- `foreign_keys=ON`
- Migrationslogik von alten Stufen auf den aktuellen Stand
- separate Datenablage ueber `BA_DATA_DIR` oder plattformspezifische Defaults

Im Code sind 15 fachliche Tabellen erkennbar:

- `settings`
- `profile`
- `positions`
- `projects`
- `education`
- `skills`
- `documents`
- `jobs`
- `applications`
- `application_events`
- `search_criteria`
- `blacklist`
- `background_jobs`
- `follow_ups`
- `extraction_history`
- plus `user_preferences` als spaeter ergaenzte System-/Preference-Tabelle

Die Migrationen zeigen, dass das Projekt nicht nur erweitert, sondern rueckwaertskompatibel weiterentwickelt wurde. Das ist ein gutes Zeichen fuer reale Nutzung.

### 3. Dashboard als zweite Produktflaeche

`src/bewerbungs_assistent/dashboard.py` implementiert eine lokale FastAPI-Oberflaeche auf Port 8200. Die API ist pragmatisch gehalten, direkt an der DB ausgerichtet und deckt Profilverwaltung, Dokumente, Jobs, Bewerbungen und Profile-Switching ab.

Wichtig: Das Dashboard ist kein separates Frontend-Projekt, sondern bewusst eng an die Python-Anwendung gekoppelt. Das reduziert Komplexitaet, erkauft aber engere Kopplung zwischen UI, API und Persistenz.

### 4. Job-Scraper als modularer Block

`src/bewerbungs_assistent/job_scraper/__init__.py` zeigt eine sinnvolle Struktur:

- zentrales `SOURCE_REGISTRY`
- dynamische Keyword-Erzeugung aus den Suchkriterien
- Dispatcher fuer die einzelnen Quellen
- Deduplizierung
- Score-Berechnung
- Gehaltsextraktion und Gehaltsschaetzung

Die Scraper selbst sind bewusst heterogen, je nach Quelle mit REST, HTML-Scraping oder Playwright. Das ist technisch pragmatisch und fuer Jobportale realistisch.

## Technische Staerken

### 1. Produktfokus statt Technikdemo

PBP ist klar fuer einen konkreten Nutzer und einen konkreten Workflow gebaut. Viele Entscheidungen sind deshalb richtig einfach:

- lokale Datenhaltung statt unnoetiger Serverkomplexitaet
- stdio/MCP als natuerliche Claude-Integration
- Dashboard fuer visuelle Kontrolle
- Installer fuer Windows als echte Nutzbarmachung

### 2. Gute Persistenz-Basis

Die Datenbankschicht ist fuer den Scope solide:

- Migrationen statt Wegwerf-Schema
- Foreign Keys und WAL
- Profil-Isolation als zentrales Designprinzip
- Background Jobs fuer laenger laufende Prozesse

Gerade fuer ein Solo-/KI-Projekt ist das ueberdurchschnittlich robust.

### 3. Saubere Domaenenaufteilung

Die grobe Modulaufteilung ist nachvollziehbar:

- `server.py`: Sprachschnittstelle und Orchestrierung
- `database.py`: Persistenz
- `dashboard.py`: HTTP/UI-Zugriff
- `export.py`: Dokumentgenerierung
- `job_scraper/`: Quellenintegration und Scoring

Das ist kein perfekter Hexagonal-Ansatz, aber fuer das Produkt sinnvoll und wartbar genug.

### 4. Tests fuer Kernbereiche vorhanden

Das Repo enthaelt echte Tests fuer:

- Datenbank-CRUD und Migrationen
- Scoring/Fit-Logik
- Export-Funktionen

Das bedeutet: Die risikoreichsten Kernbereiche sind nicht voellig ungesichert.

## Auffaellige Schwaechen und Risiken

### 1. Dokumentation und Code laufen auseinander

Das ist aktuell das groesste Organisationsproblem des Repos.

Beispiele:

- `pyproject.toml` meldet Version `0.11.0`
- `ZUSTAND.md` nennt `1.0.0`
- `database.py` arbeitet mit Schema `v8`
- `ZUSTAND.md` beschreibt noch Schema `v2`
- `ZUSTAND.md` spricht von 21 Tools, waehrend `server.py` aktuell 44 Tools registriert
- `docs/architecture.md` und `AGENTS.md` sind naeher am Code als `ZUSTAND.md`

Risiko:

- Neue Arbeit basiert leicht auf veralteten Annahmen.
- KI-Agenten koennen aus widerspruechlichen Dokumenten falsche Schluesse ziehen.
- Release-Kommunikation wirkt weniger vertrauenswuerdig als der eigentliche Code.

### 2. `server.py` ist funktional stark, aber zu gross

`server.py` ist der zentrale Erfolgsfaktor und zugleich ein Wartungsrisiko. Das Modul enthaelt Tool-Definitionen, Prompt-Definitionen, Logging-Wrapping, Initialisierung und vermutlich Teile der Business-Logik in direkter Form.

Problem:

- hohe Kopplung
- schwerer gezielt zu testen
- neue Features landen fast automatisch in derselben Datei
- Konfliktpotenzial bei paralleler Arbeit durch Mensch und mehrere KI-Rollen

Empfehlung:

- Tools thematisch in Teilmodule zerlegen, z. B. `tools_profile.py`, `tools_jobs.py`, `tools_applications.py`, `prompts.py`
- `server.py` nur noch als Composition Root nutzen

### 3. DB-Schicht uebernimmt zu viele Rollen

`database.py` ist nicht nur Persistence Layer, sondern auch teilweise Domaenenlogik, Migrationssystem und Infrastrukturzugang. Das ist in kleinen Projekten normal, wird aber ab diesem Umfang spuerbar.

Folge:

- Fachlogik wird schwer isolierbar
- HTTP/MCP/API-Layer greifen sehr direkt auf DB-nahe Methoden zu
- spaetere Refactorings werden teurer

Empfehlung:

- mittelfristig Service-Layer einfuehren, z. B. `profile_service.py`, `job_service.py`, `application_service.py`
- DB-Klasse auf CRUD, Queries, Migrationen und technische Hilfsfunktionen begrenzen

### 4. Monolithische lokale Architektur ist absichtlich einfach, aber fragil bei Wachstum

Aktuell ist die enge Kopplung vermutlich die richtige Entscheidung. Wenn PBP aber weiter waechst, treten typische Folgen auf:

- Dashboard und MCP greifen auf dieselben Daten und dieselbe Logik zu
- Playwright/Scraper, HTTP-API und MCP-Tools leben im selben Prozessmodell
- Fehler in einer Domaene koennen den Gesamteindruck des Produkts beeintraechtigen

Das ist noch kein unmittelbarer Architekturfehler, aber ein klares Wachstumslimit.

### 5. Uneinheitliche Benennung und Historie erschweren Orientierung

Schon in der Doku gibt es mehrere parallele Erzaehlungen:

- "Bewerbungs-Assistent"
- "PBP"
- "Persoenliches Bewerbungs-Portal"
- unterschiedliche Zaehlungen fuer Tabellen, Tools und Endpoints

Das ist nicht nur kosmetisch. Es erschwert:

- Onboarding
- Fehlersuche
- Release Notes
- Zusammenarbeit zwischen mehreren KI-Rollen

## Konkrete Verbesserungsvorschlaege

### Prioritaet 1: Dokumentations- und Versionsdisziplin herstellen

1. Eine einzige Datei als technische Wahrheit definieren, am besten `docs/architecture.md` plus `README.md`.
2. `ZUSTAND.md` auf aktuellen Stand bringen oder klar als historisch markieren.
3. Versionierung synchronisieren:
   - `pyproject.toml`
   - `CHANGELOG.md`
   - `ZUSTAND.md`
   - Release-Tags
4. In der Doku explizit zwischen historischem und aktuellem Stand unterscheiden.

### Prioritaet 2: `server.py` modularisieren

Empfohlene Zielstruktur:

- `src/bewerbungs_assistent/server.py`
- `src/bewerbungs_assistent/tools/profile.py`
- `src/bewerbungs_assistent/tools/jobs.py`
- `src/bewerbungs_assistent/tools/applications.py`
- `src/bewerbungs_assistent/tools/documents.py`
- `src/bewerbungs_assistent/prompts.py`

Nutzen:

- bessere Testbarkeit
- weniger Merge-Konflikte
- klarere Verantwortlichkeiten
- einfacher fuer Claude, Codex und Menschen gemeinsam zu bearbeiten

### Prioritaet 3: Service-Schicht einfuehren

Ein leichter Zwischenschritt reicht schon:

- `services/profile_service.py`
- `services/search_service.py`
- `services/application_service.py`

Diese Schicht sollte Validierung, Orchestrierung und domaenenspezifische Entscheidungen kapseln. Der MCP-Layer und das Dashboard sprechen dann nicht mehr direkt mit einer allwissenden DB-Klasse.

### Prioritaet 4: Teststrategie erweitern

Der aktuelle Testfokus ist sinnvoll, aber lueckenhaft in genau den Bereichen, die mit wachsender Nutzung teurer werden:

- MCP-Tool-Integrationstests
- Dashboard-API-Tests
- Multi-Profil-Regressionstests
- Migrations-Tests ueber mehrere historische DB-Staende
- Scraper-Fallback-Tests mit stabilen Fixtures

### Prioritaet 5: Architekturgrenzen explizit dokumentieren

PBP ist lokal, monolithisch und workflow-orientiert. Das sollte als bewusste Produktentscheidung dokumentiert werden. Dann wird auch klar, was PBP nicht sein will:

- kein Cloud-SaaS
- kein Multi-User-Webservice
- kein generisches Bewerbungs-Framework

Das wuerde viele spaetere Architekturdebatten verkuerzen.

## Einordnung des Projekts

Aus Codex-Sicht ist PBP ein bemerkenswert produktnahes KI-Co-Engineering-Projekt. Die interessanteste Eigenschaft ist nicht ein einzelnes Feature, sondern dass hier bereits ein nutzbares Gesamtsystem entstanden ist:

- installierbar
- lokal betreibbar
- deutschsprachig
- mit persistenter Datenhaltung
- mit mehreren Bedienkanaelen
- mit echter Prozessabdeckung von Profil bis Bewerbung

Das groesste Defizit liegt derzeit nicht primaer in fehlenden Features, sondern in Konsistenz und Strukturpflege. Anders gesagt: Die Produktidee ist tragfaehig, die technische Basis ist brauchbar, aber der naechste Reifeschritt ist Konsolidierung statt weiterer Feature-Ausdehnung.

## Empfohlene naechste Schritte

1. `ZUSTAND.md` auf den realen Stand bringen oder archivieren.
2. Aktuelle Versionsnummer und Release-Story vereinheitlichen.
3. `server.py` in fachliche Module zerlegen.
4. Service-Schicht zwischen MCP/Dashboard und DB einziehen.
5. API- und Integrations-Tests ergaenzen.

## Gesamturteil

PBP ist technisch sinnvoll aufgebaut und fuer seinen Einsatzzweck bereits weit. Die Architektur ist pragmatisch, lokal-first und nutzerorientiert. Die groesste Gefahr ist aktuell nicht ein falsches Tech-Stack-Fundament, sondern dass die Codebasis schneller gewachsen ist als ihre innere Ordnung und Dokumentationskonsistenz.

Wenn ihr jetzt konsolidiert, kann PBP ein stabiles, gut wartbares Spezialprodukt werden. Wenn ihr dagegen hauptsaechlich weiter Features stapelt, steigt die Wahrscheinlichkeit, dass Mensch und KI auf veraltete oder widerspruechliche Projektbilder reagieren.
