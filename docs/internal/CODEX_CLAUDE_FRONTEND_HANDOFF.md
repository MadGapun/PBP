# Claude-Code Handoff: Frontend Recovery ab v0.22.0

Bitte uebernimm den Release-/Merge-Abschluss fuer die Frontend-Recovery auf Basis von `codex/v22-v23-frontend-recovery`.

## Zuerst lesen

1. `docs/FRONTEND_RECOVERY_v022_to_v025.md`
2. `CHANGELOG.md`
3. `frontend/src/App.jsx`
4. `frontend/src/pages/ApplicationsPage.jsx`
5. `tests/test_dashboard_browser.py`
6. `package.json`
7. `frontend/package.json`

## Was dieser Branch bereits erledigt

### Fixes

- `#99` Hilfe-Button repariert
  - Ursache: `Modal` ohne `open={helpOpen}`
  - Datei: `frontend/src/App.jsx`

- `#100` Timeline-Notiz repariert
  - Ursache: `onClick={addNote}` uebergab Click-Event als erstes Argument
  - Datei: `frontend/src/pages/ApplicationsPage.jsx`

- `#102` Statuswechsel direkt in der Timeline ergaenzt
  - Datei: `frontend/src/pages/ApplicationsPage.jsx`

- Build-Workflow robust gemacht
  - Dateien: `package.json`, `frontend/package.json`

### Tests

- Browser-Regressionen fuer Hilfe, Notiz und Timeline-Status
  - Datei: `tests/test_dashboard_browser.py`

## Was du lokal pruefen und dann mergen sollst

### Pflicht-Checks

```bash
pnpm install
pnpm --dir frontend build
python -m pytest tests -q
```

### Erwarteter Stand

- alle Python-Tests gruen
- Frontend-Build erfolgreich
- statische Assets unter `src/bewerbungs_assistent/static/dashboard/` aktualisiert

## Inhaltlich erwartete GitHub-Aktionen

### Nach dem Merge schliessen

- `#99`
- `#100`
- `#102`

### Vor dem Schliessen kurz manuell pruefen

- `#101`

Hinweis:
- Im aktuellen React-Frontend gibt es bereits eine Job-Bearbeitung im Detail-Dialog.
- Bitte kurz entscheiden, ob das den Issue-Intent bereits ausreichend abdeckt oder ob fuer manuelle Stellen noch ein direkterer Bearbeitungspfad noetig ist.

## Release-Empfehlung

### Wenn nur dieser Branch in die naechste Version geht

- `v0.25.2`

### Wenn du zusaetzlich weitere offene UI-/Produktpunkte mitnimmst

- `v0.26.0`

## Changelog-Vorschlag

```text
### Frontend-Recovery: Hilfe, Timeline und Build-Workflow

- Hilfe-Button im React-Dashboard repariert (Modal wurde korrekt verdrahtet)
- Bewerbungs-Timeline: Notizen koennen wieder zuverlaessig hinzugefuegt werden
- Bewerbungsstatus jetzt direkt in der Timeline aenderbar
- Browser-Regressionstests fuer Hilfe-Modal und Timeline-Flows hinzugefuegt
- Frontend-Build-Skripte auf stabilen Vite-Aufruf via pnpm exec umgestellt
```

## Technische Kernstellen

### 1. Hilfe-Fix

```jsx
<Modal open={helpOpen} title="Hilfe & Support" onClose={() => setHelpOpen(false)}>
```

### 2. Notiz-Fix

```jsx
<Button onClick={() => addNote()}>
```

Nicht wieder auf `onClick={addNote}` zurueckdrehen. Das fuehrt den Bug erneut ein.

### 3. Timeline-Status

Die Statusaenderung in der Timeline nutzt bewusst den vorhandenen Backend-Pfad:

```text
PUT /api/applications/{app_id}/status
```

und laedt danach die Timeline neu, damit der Ereignisverlauf sofort sichtbar bleibt.

## Was ich danach als naechste Phase sehe

### Hohe Prioritaet

- `#101` final entscheiden
- `README.md` Encoding bereinigen
- Frontend-Chunks spaeter aufsplitten, weil `index-*.js` gross ist

### Danach

- `#103` Dokumente proaktiv in `/profil_erweiterung`
- `#104` bis `#112` als neue Produktphase, nicht mehr als React-Recovery behandeln

