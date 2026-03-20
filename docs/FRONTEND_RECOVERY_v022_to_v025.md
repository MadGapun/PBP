# Frontend Recovery: v0.22.0 bis v0.25.1

## Kurzfazit

`v0.22.0` war die letzte eindeutig funktionale UI-Basis vor dem grossen Frontend-Wechsel. Mit `v0.23.0` wurde Koalas React/Vite/Tailwind-Frontend integriert, aber dieses Frontend basierte laut Projektkontext auf dem Stand `v0.17.0`. Genau dort entstand der Kern des Problems:

- das neue Frontend war visuell stark,
- die Backend-/Produktrealitaet war aber bereits weiter,
- dadurch mussten Features aus `v0.18.0` bis `v0.22.0` nachtraeglich wieder angeflanscht werden.

Die GitHub-Issues `#75` bis `#98` bestaetigen genau dieses Muster: Nach `v0.23.0` begann keine normale Feature-Phase, sondern eine hektische Re-Integrationsphase, in der verlorene oder halb angeschlossene Dashboard-Flows nachgezogen wurden.

## Was in v0.22.0 funktionierte

`v0.22.0` war produktseitig bereits deutlich weiter als die Koala-Basis:

- Bewerbungs-Detailansicht mit Stelleninfos, Kontaktdaten, Dokumenten
- Gespraechsnotizen mit Zeitstempeln
- Dokument-Verknuepfung direkt an Bewerbungen
- gereifte Dashboard-/API-Kopplung
- 237 Tests laut Release

Wichtig: `v0.22.0` war keine moderne React-SPA, aber die Oberflaeche und die API waren funktional enger miteinander verdrahtet.

## Was mit v0.23.0 passierte

Mit `v0.23.0` kamen laut Release:

- komplettes React/Vite/Tailwind-Frontend
- neue SPA-Architektur
- neue Build-Kette
- neue statische Dashboard-Auslieferung

Das Frontend war visuell ein grosser Sprung, aber technisch entstand ein Mismatch:

1. Koalas UI-Basis stammte aus `v0.17.0`.
2. Zwischen `v0.17.0` und `v0.22.0` waren bereits mehrere produktrelevante Flows dazugekommen.
3. Diese Flows waren im React-Frontend teilweise noch nicht oder nur unvollstaendig angekommen.

Das sieht man sehr klar an den nachfolgenden Issues:

- `#89` aktives Profil nicht erkannt
- `#90` Stellen-Detailansicht / Bearbeiten
- `#95` Hilfe-Button ohne Funktion
- `#96` Stellen-Klick ohne Wirkung
- `#97` Bewerbungs-Detailansicht unvollstaendig
- `#98` Top-Stellen zeigen bereits beworbene Jobs
- `#99` Hilfe weiterhin kaputt
- `#100` Notiz hinzufuegen in Timeline kaputt
- `#101` manuelle Stellenbeschreibung editierbar machen
- `#102` Status direkt in Timeline aendern

## Was bis v0.25.1 bereits nachgezogen wurde

`v0.23.1` bis `v0.25.1` waren im Wesentlichen Stabilisierung und Feature-Nachzug fuer das neue React-Frontend:

- Schema-/Profil-Isolation repariert
- Hilfe-Menue und Dashboard-Funktionen erweitert
- Stellen-Detailansicht, Bewerbungs-Detailansicht und Dokument-Links nachgezogen
- Top-Stellen, Filter, Auto-Linking, Notiz-Antworten, Statistik und Suche verbessert
- Installer- und Build-Themen bereinigt

Das ist eine klare Re-Integrationsphase, keine reine Feature-Phase.

## Befund auf diesem Codex-Branch

Auf `codex/v22-v23-frontend-recovery` habe ich die GitHub-Linie `v0.22.0 -> v0.25.1` mit Code und Issues abgeglichen und die heute noch relevanten Frontend-Punkte ueberprueft.

### Verifiziert/fixiert

#### 1. Hilfe-Button war tatsaechlich weiterhin kaputt (`#99`)

Ursache in `frontend/src/App.jsx`:

```jsx
{helpOpen && (
  <Modal onClose={() => setHelpOpen(false)}>
```

Der `Modal`-Component erwartet `open={...}`. Ohne dieses Prop wurde der Dialog trotz `helpOpen` nie angezeigt.

Fix:

```jsx
{helpOpen && (
  <Modal open={helpOpen} title="Hilfe & Support" onClose={() => setHelpOpen(false)}>
```

#### 2. Notiz-hinzufuegen in der Timeline war wirklich kaputt (`#100`)

Ursache in `frontend/src/pages/ApplicationsPage.jsx`:

```jsx
<Button onClick={addNote}>
```

`addNote(parentEventId = null)` bekam dadurch beim Klick das React-Event als erstes Argument. Die Funktion landete irrtuemlich im Antwort-Pfad und verwarf den eigentlichen Text aus `newNoteText`.

Fix:

```jsx
<Button onClick={() => addNote()}>
```

Das ist ein echter UI-Regression-Bug, nicht nur ein Bedienfehler.

#### 3. Status direkt in der Timeline wurde ergaenzt (`#102`)

Die Timeline war bereits der richtige Ort fuer Kontext und Historie, aber der Status liess sich dort noch nicht aendern. Das ist jetzt direkt im Timeline-Header moeglich und nutzt die bestehende API `PUT /api/applications/{id}/status`.

#### 4. Browser-Regressionen abgesichert

Neu in `tests/test_dashboard_browser.py`:

- Hilfe-Modal oeffnet und enthaelt GitHub-Aktionen
- Timeline kann Notizen anlegen
- Timeline kann Status direkt aendern

Damit sind `#99`, `#100` und `#102` nicht mehr nur Behauptungen oder Einzelfallberichte, sondern testseitig sichtbar.

#### 5. Build-Workflow repariert

Der bisherige Wrapper war lokal nicht verlaesslich:

- `pnpm run build:web` / `pnpm --dir frontend build` waren auf dieser Maschine gebrochen

Die Skripte wurden auf einen robusteren Vite-Aufruf mit `pnpm exec vite ...` umgestellt.

## Offene Punkte nach heutigem Stand

### Praktisch offen

- `#101` Manuelle Stellenbeschreibung editierbar machen
  - Im aktuellen React-Frontend gibt es bereits eine Bearbeitungsfunktion in der Stellen-Detailansicht.
  - Offene Frage fuer Claude-Code: reicht das UX-seitig fuer den Issue-Intent oder soll die Bearbeitung gezielt an `source == "manuell"` noch prominenter/schneller werden?

- `#103` bis `#112`
  - Das sind keine reinen React-Integrationsregressionen mehr.
  - Das sind neue Produkt-/Workflow-Themen fuer die naechste Ausbaustufe.

### Technische Restpunkte

- Das gebaute Dashboard-JS ist mit knapp 800 kB weiterhin gross.
- `README.md` hat sichtbare Encoding-Schaeden und sollte separat bereinigt werden.
- Browser-Tests setzen einen gebauten Frontend-Stand voraus. Das ist okay, aber fuer Release/CI sollte `pnpm --dir frontend build` vor UI-Tests fest eingeplant werden.

## Empfehlung fuer die naechste Version

Wenn Claude-Code nur diesen Recovery-Block merged und sauber released:

- Empfehlung: `v0.25.2`

Wenn Claude-Code zusaetzlich `#101` und weitere groessere Frontend-/Produktpunkte mitnimmt:

- Empfehlung: `v0.26.0`

## Empfohlene Release-Reihenfolge

1. Diesen Branch mergen
2. `#99` schliessen
3. `#100` schliessen
4. `#102` schliessen
5. `#101` gegen UI pruefen und dann entscheiden: schliessen oder konkretisieren
6. Danach erst `#103+` als naechste Produktphase priorisieren

## Verifikation auf diesem Branch

- `python -m pytest tests -q` -> `264 passed, 4 skipped`
- `python -m pytest tests/test_dashboard_browser.py -q` -> `4 passed, 4 skipped`
- `pnpm --dir frontend build` -> erfolgreich

