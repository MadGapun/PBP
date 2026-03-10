# PBP Verbesserungsplan

Stand: 2026-03-09

Dieses Dokument beschreibt nicht mehr den alten Aufraeumbedarf aus v0.11.x,
sondern den sinnvollen naechsten Schritt nach Modularisierung, FK-Bugfixes,
Auto-Analyse und Dashboard-Tests.

## Bereits umgesetzt

- Dokumentationskonsolidierung auf den Stand nach der Codex-Analyse
- Modularisierung von `server.py` in 7 Tool-Module plus `prompts.py` und `resources.py`
- Dashboard-API-Tests
- FK-sichere Behandlung von `job_hash`
- Auto-Analyse fuer importierte Dokumente
- Ordner-Browser fuer Dokument-Import

## In diesem Arbeitsblock ergaenzt

- MCP-Registry-Smoke-Tests fuer Tools, Prompts und Resources
- erste Scraper-Fixture-Tests fuer Hays, freelance.de und Freelancermap
- erster kleiner Service-Layer mit `services/profile_service.py`
- ausgebauter Service-Layer mit `services/search_service.py` und `services/workspace_service.py`
- zusaetzliche Dashboard-Tests fuer Quellen- und Suchstatus-Endpunkte
- neue Service- und Dashboard-Regressionstests fuer Profilstatus, Praeferenzen und Vollstaendigkeit
- kleinere Dashboard-UX-Verbesserung: sichtbarer Schnellzugriff mit Quellen- und Suchstatus
- Workspace-Summary-API plus klarere Navigation, Workspace-Kopf und seitenbezogene Orientierung
- Doku-Sweep fuer verbleibende Architektur- und Zaehldifferenzen

## Offene Prioritaeten

### Prio 1: Testnetz um externe und oeffentliche Kanten schliessen

Noch offen sind die zwei fragilsten Bereiche:

1. Scraper-Fixture-Tests auf weitere Quellen und Fallbacks ausweiten
2. MCP-Tool-Tests mit etwas mehr Verhaltenstiefe als reine Registrierung

Empfehlung:

- fuer weitere Quellen stabile HTML/JSON-Fixtures anlegen
- typische Extraktionsfaelle und Fallbacks absichern
- fuer kritische MCP-Tools die wichtigsten Erfolgs- und Fehlerszenarien testen

### Prio 2: Service-Layer gezielt weiter ausbauen

Die Modularisierung hat `server.py` entschlackt. Mit `services/profile_service.py`,
`services/search_service.py` und `services/workspace_service.py` gibt es jetzt
bereits einen soliden gemeinsamen Unterbau fuer Dashboard und MCP-Tools.
Weitere Bereiche sprechen aber weiterhin recht direkt mit `database.py`.

Sinnvoller naechster Schritt:

- `services/application_service.py`
- danach bei Bedarf weitere Domain-Services fuer Export oder Analyse

Ziel:

- Domaenenlogik aus UI- und MCP-Schicht herausziehen
- Refactorings billiger machen
- Testbarkeit weiter verbessern

### Prio 3: Dashboard-Usability weiter schaerfen

Der grobe UX-Rahmen ist inzwischen gut. Der Mehrwert liegt jetzt in kleinen,
handlungsorientierten Verbesserungen:

- Status noch klarer in Aktionen uebersetzen
- bessere Kontextinfos bei leerer Jobsuche
- Such- und Quellenbereitschaft sichtbarer machen
- Bewerbungsnaechste Schritte noch direkter hervorheben

## Nicht empfohlen

- Cloud- oder Multi-User-Umbau
- Framework-Wechsel
- grosse Featurepakete vor weiterer Konsolidierung

## Empfohlene Reihenfolge

1. Scraper-Fixture-Tests auf weitere Quellen ausbauen
2. MCP-Tool-Verhaltenstests erweitern
3. Service-Layer in Anwendungen oder Suche weiterziehen
4. danach weitere UX-Politur
