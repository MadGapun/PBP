# Claude Handoff — Tagesimpulse

Bitte uebernimm die spaetere technische Integration des Tagesimpuls-Features fuer PBP.

## Zuerst lesen

1. `AGENTS.md`
2. `docs/TAGESIMPULSE_SEED.md`
3. `docs/TAGESIMPULSE_IMPLEMENTIERUNGSPLAN.md`
4. `src/bewerbungs_assistent/services/workspace_service.py`
5. `src/bewerbungs_assistent/dashboard.py`
6. `frontend/src/pages/DashboardPage.jsx`
7. `frontend/src/pages/SettingsPage.jsx`

## Ziel

PBP soll optional einen kleinen, taeglichen Impuls im Dashboard anzeigen.

Das Feature soll:
- motivieren, ohne kitschig zu werden
- zur Jobsuche passen
- taeglich stabil sein
- in den Einstellungen deaktivierbar sein
- spaeter leicht erweitert werden koennen

## Bereits vorbereitet

- Seed-Sammlung mit 140 Originaltexten:
  - `docs/TAGESIMPULSE_SEED.md`
- technischer und produktseitiger Plan:
  - `docs/TAGESIMPULSE_IMPLEMENTIERUNGSPLAN.md`

## Empfohlener technischer Schnitt

### 1. Content-Datei

Lege eine maschinenlesbare Datei an, z. B.:
- `src/bewerbungs_assistent/content/tagesimpulse.json`

Uebernimm die Seed-Texte aus `docs/TAGESIMPULSE_SEED.md` mit:
- `id`
- `text`
- `tags`
- `contexts`
- optional `tones`

### 2. Service

Neue Datei:
- `src/bewerbungs_assistent/services/daily_impulse_service.py`

Der Service soll:
- Kontext bestimmen
- passende Impulse filtern
- taeglich stabile Auswahl treffen
- deaktivierte Anzeige respektieren

### 3. API

Bevorzugt neuer Endpoint:
- `GET /api/daily-impulse`

Rueckgabeform:

```json
{
  "enabled": true,
  "context": "search_refresh",
  "impulse": {
    "id": "impuls_052",
    "title": "Heute fuer dich",
    "text": "Heute musst du nicht den perfekten Job finden. Nur den naechsten guten Treffer.",
    "tags": ["jobsuche", "alltag"]
  }
}
```

### 4. Settings

Neue User-Preference:
- `daily_impulse_enabled`

Default:
- `true`

UI:
- kleiner Toggle in `SettingsPage.jsx`
- Text: `Tagesimpuls im Dashboard anzeigen`

### 5. Dashboard

In `DashboardPage.jsx`:
- kleine Card oder Banner
- unaufdringlich
- idealerweise zwischen Header/Workspace und Metriken

## Kontextlogik fuer V1

Verwende nur einfache, bereits vorhandene Signale:

- `onboarding`
- `profile_building`
- `sources_missing`
- `search_refresh`
- `jobs_ready`
- `follow_up_due`
- `weekend`
- `default`

Wochenende:
- Samstag/Sonntag direkt ueber Datum

Feiertage:
- optional spaeter, nicht noetig fuer den ersten Einbau

## Prioritaet bei mehreren Kontexten

1. `weekend`
2. `follow_up_due`
3. `jobs_ready`
4. `search_refresh`
5. `sources_missing`
6. `profile_building`
7. `onboarding`
8. `default`

## Wichtige Produktregeln

- Kein grosses Gamification-System
- Keine KI-Livegenerierung fuer V1
- Nicht zu gross und nicht zu laut im Dashboard
- Keine zufaellige Rotation bei jedem Refresh
- Pro Tag stabil

## Tests

Bitte mindestens ergaenzen:

- `tests/test_daily_impulse_service.py`
- API-Test in `tests/test_dashboard.py`
- Browser-Smoke fuer Sichtbarkeit/Toggle in `tests/test_dashboard_browser.py`

## Akzeptanzkriterien

- Dashboard zeigt einen Tagesimpuls
- derselbe Tag zeigt denselben Impuls
- Toggle blendet das Feature sauber aus
- keine Beeintraechtigung der bestehenden Workspace-Guidance
- Tests laufen gruen

## Nicht tun

- Keine riesige Refactor-Welle im Dashboard
- Nicht 365 Texte erzwingen
- Keine aggressive Animation
- Kein Pop-up, kein Modal, kein Alert

## Zielbild

Am Ende soll es sich anfuehlen wie:
- kleine menschliche Begleitung
- passend zu PBP
- nicht kitschig
- nicht stoerend
