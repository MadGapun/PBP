# PBP — Roadmap

> Stand: 2026-05-07 (v1.7.0-beta.36, 1026 Tests gruen)

Diese Datei haelt den Strategie-Stand fest, was als naechstes ansteht
und welche Issues warum zurueckgestellt werden.

## Aktueller Release-Stand

- **v1.6.9** ist aktuell als „Latest" markiert (Stable)
- **v1.7.0-beta.36** ist der juengste Pre-Release
- v1.7.0 wechselt erst nach erfolgreichem User-Test auf "Latest"

## Offene Issues nach Strategie

### 🟢 Quick Wins — kann jederzeit kommen

| # | Titel | Aufwand | Hinweis |
|---|---|---|---|
| #464 | Post-Interview-Reflexion | klein | Strukturierter Fragebogen nach `interview_abgeschlossen`. Schliesst Lifecycle-Luecke. |
| #425 | Granulare KI-Steuerung in Einstellungen | klein-mittel | Pro LLM-Task einstellbar (Local/Claude/Manual). Heute Default-Routing in `ROUTING_TABLE`, User kann das nicht ueberschreiben. |
| #513 | Community-Tagesimpulse | klein | User koennen Sprueche via GitHub-Issue beisteuern. „Spielerei", aber macht aus Solo-Tool ein bisschen Community. |

### 🟡 Mittlerer Aufwand — wenn Zeit + Mehrwert

| # | Titel | Aufwand | Hinweis |
|---|---|---|---|
| #452 | Interview-Training-Arc | gross | Eigener PBP-Bereich fuer Interview-Vorbereitung. Strukturierte Frageliste, Coaching, Vorbereitungs-Checkliste. |
| #429 | PyPI-Paket + MCP Registry | mittel | Verbreitet PBP an mehr User. Unabhaengig vom Lern-System. |
| #590-C.4 | Quellen-Rotation (gestaffelter Pull) | mittel | Aus #590 herausgehalten — betrifft job_runner-Orchestrator. Reduziert Bot-Detection bei aggressiven Portalen. |

### 🟠 Erstmal nicht — strategisch zurueckgestellt

| # | Titel | Warum zurueckgestellt |
|---|---|---|
| #504 | Plugin-Plattform v1.7 | **User-Vorgabe:** wird vermutlich erst v1.8. Architektur-Brocken, mehrere Tage Arbeit, sollte sauber durchdacht werden. |
| #478 | Thunderbird-Add-On „An PBP senden" | **Soll als Plug-In kommen** — braucht #504 als Voraussetzung. |
| #480 | Outlook-Integration (Office-Add-In) | **Soll als Plug-In kommen** — braucht #504. |
| #481 | Termine an Thunderbird/Outlook-Kalender senden | **Soll als Plug-In kommen** — braucht #504. |
| #524 | Spam-Ordner-Lifeline | Setzt Mail-Integration voraus → braucht #504. |
| #525 | Stellenboersen-Newsletter automatisch ingestieren | Setzt Mail-Integration voraus → braucht #504. **Plus User-Hinweis:** „nur fuer mich, weniger Allgemein-Wert". |

## Strategie

### Vor v1.7.0-Stable

1. **User-Test der beta.36** — sind alle 10 neuen Quellen-Adapter,
   Profile-Detection, AdaptiveHintBanner und Telemetrie-Sharing real
   nutzbar? Live-Healthcheck der Quellen empfehlenswert (welche liefern
   wirklich Stellen).
2. **Falls neue Findings auftauchen** → wie bei beta.31 als
   „User-Test-Findings"-Bundle releasen.
3. **Bei stabiler Lage** → v1.7.0-Final als „Latest" releasen.

### Fuer v1.8.0

- **#504 Plugin-Plattform** als Architektur-Grundlage
- Darauf aufbauend: #478/#480/#481/#524 Mail-/Kalender-Plug-Ins
- #525 Newsletter-Ingest als optionales Plug-In

### Spielereien (jederzeit moeglich)

- **„Marvin"-Statusanzeige** wenn lokale AI arbeitet — humorvolle
  Live-Kommentare im Stil von Douglas Adams' depressivem Roboter.
  Eigenes Issue, sehr begrenzter Aufwand.
- **#513 Community-Tagesimpulse** in der gleichen Kategorie.

## Nicht-Code-Themen

- **CHANGELOG-Entry** je Beta enthaelt vollstaendige Installations-
  Anleitung (Pflicht ab v1.6.4)
- **README-Badges** werden mit jeder Beta aktualisiert (Tests, Tools)
- **`gh release create`** IMMER mit `unset GITHUB_TOKEN` aufrufen
  (Token-Falle — Keyring-Token hat Repo-Scope, ENV-Token nicht)
