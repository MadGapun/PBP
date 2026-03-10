# Release Review v0.14.0

Stand: 2026-03-10

Diese Review bewertet den GitHub-Release `v0.14.0` von PBP auf Basis des
veroeffentlichten Releases, des Diffs zu `v0.13.0`, des getaggten Changelogs
und des aktuellen Remote-Stands auf GitHub.

- Release: [v0.14.0](https://github.com/MadGapun/PBP/releases/tag/v0.14.0)
- Compare: [v0.13.0...v0.14.0](https://github.com/MadGapun/PBP/compare/v0.13.0...v0.14.0)

## Kurzfazit

`v0.14.0` ist ein starkes Konsolidierungs-Release. Es fuehrt PBP nicht durch
neue Endnutzer-Features weiter, sondern verbessert genau die Bereiche, die fuer
ein reales Produkt in dieser Phase wichtig sind: Struktur, Guidance, Tests und
Dokumentation.

Gesamtbewertung aus Codex-Sicht: **8.5/10**

## Was der Release konkret liefert

Zwischen `v0.13.0` und `v0.14.0` liegen 4 Commits, 28 geaenderte Dateien,
2.258 Einfuegungen und 608 Loeschungen. Der Schwerpunkt liegt klar auf
Konsolidierung:

- gemeinsamer Service-Layer mit `profile_service.py`, `search_service.py`,
  `workspace_service.py`
- neue Workspace-Guidance mit Readiness-Stufen und Handlungsempfehlungen
- neuer Endpoint `/api/workspace-summary`
- ueberarbeitetes Dashboard mit besserer Navigation, Statussicht und
  Schnellzugriffen
- 28 neue Tests, insgesamt 187 gruene Tests
- Scraper-Fixtures fuer reproduzierbare Parser-Tests
- Doku-Sweep ueber Changelog, README, Architektur- und Kontextdokumente

## Staerken

### 1. Gute strategische Priorisierung

Der Release setzt auf die richtige Art von Fortschritt. Statt neue Features auf
eine bereits komplexe Codebasis zu stapeln, reduziert `v0.14.0` strukturelle
Reibung und macht PBP wartbarer.

### 2. Produkt wird gefuehrter

Die Workspace-Guidance ist der groesste Produktgewinn in diesem Release.
PBP wirkt dadurch weniger wie eine Sammlung einzelner Tools und mehr wie ein
Assistent mit erkennbarem naechstem Schritt. Das passt gut zum Nutzerbild aus
`AGENTS.md`: Markus ist Endnutzer, nicht Entwickler.

### 3. Architektur gewinnt an Klarheit

Mit dem Service-Layer ist ein frueherer Hauptkritikpunkt sinnvoll adressiert:
Dashboard und MCP-Tools koennen gemeinsame fachliche Logik nutzen, statt
Parallellogik zu pflegen.

### 4. Teststrategie wird deutlich belastbarer

Die Testerweiterung ist inhaltlich gut, nicht nur numerisch:

- Service-Tests sichern zentrale Domain-Regeln ab
- MCP-Registry-Smoke-Tests sichern die modulare Server-Schnittstelle
- Scraper-Fixtures reduzieren Parser-Risiken ohne Netzabhaengigkeit
- Dashboard-Tests decken neue Guidance- und API-Pfade ab

### 5. Release-Hygiene im Tag ist gut

Im getaggten `v0.14.0` sind Version, Changelog und Release-Text konsistent.
Das ist fuer PBP besonders wichtig, weil das Projekt historisch mehrfach unter
Doku-Drift gelitten hat.

## Risiken und offene Punkte

### 1. Frontend-Regressionsrisiko bleibt der groesste Restpunkt

Der groesste Risikobereich ist weiter das Dashboard-Frontend. Die
`dashboard.html` wurde stark erweitert, was produktseitig sinnvoll ist, aber
ohne echte Browser-Smoke- oder visuelle E2E-Tests bleibt dort die meiste
Restunsicherheit.

### 2. Service-Layer ist erst der Anfang

`profile`, `search` und `workspace` sind jetzt sauberer organisiert. Die
Bewerbungs- und Job-Workflows sind aber noch nicht im selben Mass durch einen
eigenen Application- oder Domain-Service entkoppelt.

### 3. Scraper-Abdeckung ist besser, aber noch selektiv

Fixtures fuer Hays, Freelance.de und Freelancermap sind ein guter Anfang.
Die riskanteren oder haeufig wechselnden Pfade sind damit aber noch nicht
vollstaendig abgesichert. Sinnvoll waeren als naechstes mindestens
`bundesagentur` und ein Playwright-/Fallback-Pfad.

### 4. Lokale Checkouts koennen hinter dem Release zurueckbleiben

Zum Zeitpunkt dieser Review lag der lokale Arbeitsbranch noch vor dem finalen
Release-Merge. Das ist kein Fehler im Release selbst, aber ein reales
Arbeitsrisiko fuer Folgearbeit: Vor neuen Aenderungen sollte immer zuerst auf
den getaggten oder aktuellen Remote-Stand synchronisiert werden.

## Abgleich mit dem frueheren Verbesserungsplan

Die wichtigsten frueheren Empfehlungen sind in `v0.14.0` weitgehend umgesetzt:

- **umgesetzt**: Service-Layer begonnen
- **umgesetzt**: MCP-Smoke-Tests aufgebaut
- **umgesetzt**: Scraper-Fixture-Tests eingefuehrt
- **umgesetzt**: Dashboard-Guidance und Benutzerfuehrung verbessert
- **umgesetzt**: Doku-Zahlen und Release-Hygiene konsolidiert
- **noch offen**: Service-Layer auf Bewerbungen und Job-Flows ausweiten
- **noch offen**: echte Browser-Smoke-Tests fuer das Dashboard

## Empfehlung fuer die naechsten Schritte

### Prioritaet 1: Browser-Smoke-Tests

Mindestens 2 bis 3 reale UI-Smoke-Tests fuer:

- Dashboard laden
- Navigation zwischen Tabs
- Profil/Workspace-Zustand sichtbar
- Dokument-Import bzw. Wizard-Sprung

### Prioritaet 2: Service-Layer weiterziehen

Ein kleiner `application_service.py` oder getrennte Services fuer Bewerbungen
und Job-Workflows waeren der naechste logische Schritt. Ziel ist, dass mehr
fachliche Regeln ausserhalb von Dashboard- und Tool-Endpunkten liegen.

### Prioritaet 3: Scraper-Haertung ausbauen

Weitere Fixture- oder isolierte Parser-Tests fuer:

- `bundesagentur`
- mindestens einen Playwright-dominierten Quellpfad
- einen Fallback- oder Fehlerpfad

### Prioritaet 4: Release- und Branch-Disziplin

Vor neuer Entwicklungsarbeit sollte lokal zuerst auf den aktuellen
Release-/Remote-Stand gewechselt oder rebased werden, damit Doku und
Arbeitsstand nicht erneut auseinanderlaufen.

## Schlussbewertung

`v0.14.0` ist ein sinnvoller, technisch reifer Release. Er verbessert PBP an den
richtigen Stellen und reduziert zentrale Risiken der vorherigen Versionen.
Er ist nicht "fertig" im Sinn eines abgeschlossenen Produkts, aber er ist ein
guter Release, weil er die Basis fuer die naechsten Schritte stabiler macht,
statt nur neue Komplexitaet aufzubauen.
