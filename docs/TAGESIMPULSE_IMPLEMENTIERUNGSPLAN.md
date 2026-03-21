# PBP Tagesimpulse — Implementierungsplan

Stand: 2026-03-21

## Ziel

PBP soll optional einen kleinen, taeglichen Impuls im Dashboard anzeigen.

Der Impuls soll:
- motivieren, ohne kitschig zu wirken
- die Rueckkehr ins PBP positiv bestaerken
- je nach Situation leicht anders klingen
- abschaltbar sein
- bei mehrfachem Oeffnen am selben Tag stabil bleiben

Das Feature ist bewusst **kein** grosses Gamification-System.
Es ist ein kleines, menschliches Zusatzsignal.

## Produktidee in einem Satz

PBP zeigt beim Oeffnen des Dashboards einen kurzen, passenden Tagesimpuls, der zur aktuellen Bewerbungsphase, zum Wochentag und zum Arbeitsstand passt.

## Empfohlener Name

Nicht:
- Motivationsspruch
- Quote des Tages

Besser:
- Tagesimpuls
- Heute fuer dich
- Kleiner Kompass

Im Plan wird der neutrale Arbeitsname `Tagesimpuls` verwendet.

## Scope fuer die erste Version

### Enthalten

- kleine Impuls-Karte im Dashboard
- taegliche Auswahl aus kuratierter Sammlung
- gleiche Anzeige fuer den ganzen Kalendertag
- einfache Kontextlogik
- Einstellung an/aus
- spaeter leicht erweiterbar

### Nicht enthalten

- KI-generierte Live-Sprueche
- komplexe Personalisierung pro Nutzerstil
- eigene Historienseite fuer alle bisherigen Impulse
- Belohnungssystem, Punkte, Streaks, Badges

## Warum das in PBP passt

- Jobsuche ist nicht nur Organisation, sondern auch Ausdauer und Selbstregulation.
- PBP ist bereits Begleiter, nicht nur Datenverwaltung.
- Das Feature kann die Rueckkehr ins Tool weicher machen, ohne vom Kernprodukt abzulenken.

## Produkt-Risiken

### 1. Kitsch-Risiko

Wenn der Ton zu kalenderhaft wird, verliert das Feature sofort an Wert.

### 2. Nerven-Risiko

Wenn der Impuls zu gross, zu bunt oder zu dominant ist, wird er schnell weggeschaltet.

### 3. Ton-Risiko

Humor und leichter Sarkasmus koennen gut sein, duerfen aber in Rueckschlag-Momenten nicht zynisch kippen.

### 4. Wartungs-Risiko

Der eigentliche Aufwand ist eher Content-Pflege als Code.

## Empfohlene UX

### Platzierung

Dashboard-Seite, im oberen Bereich, aber unterhalb der wichtigsten Arbeits-Guidance.

Empfehlung:
- unter Workspace-Guidance
- oberhalb der Metriken oder zwischen Header und Metriken

### Darstellung

- kleine Karte
- 1 kurzer Titel, z. B. `Heute fuer dich`
- 1 Spruch/Impuls
- optional 1 kleines Kontextlabel wie `Ruhig`, `Dranbleiben`, `Heute reicht ein Schritt`

### Verhalten

- pro Kalendertag stabil
- kein automatisches Rotieren im laufenden Tag
- unaufdringlich

### Interaktionen

Fuer V1:
- nur anzeigen
- in Einstellungen abschaltbar

Optional spaeter:
- `Heute ausblenden`
- `Anderen Impuls anzeigen`
- `Mehr Humor / Mehr Ruhe / Mehr Ernst`

## Datenmodell

Empfehlung fuer V1:

Datei im Repo, z. B.
- `src/bewerbungs_assistent/content/tagesimpulse.json`

Beispielstruktur:

```json
[
  {
    "id": "impuls_001",
    "text": "Heute musst du nicht alles loesen. Du musst nur wieder anfangen.",
    "tags": ["ermutigend", "alltag"],
    "tones": ["warm"],
    "contexts": ["default", "onboarding", "profile_building"],
    "weekend_ok": true,
    "holiday_ok": true,
    "weight": 1
  }
]
```

## Erste Kontextlogik

PBP muss nicht erraten, was los ist. Vieles ist schon im System vorhanden.

### Bereits nutzbare Signale

Aus `workspace_service.py` / Dashboard-Status:
- kein Profil vorhanden
- Profil unvollstaendig
- keine Quellen aktiv
- Jobsuche nie/veraltet/dringend
- Jobs vorhanden, aber noch keine Bewerbungen
- Follow-up ueberfaellig

Aus Datum:
- Wochenende
- spaeter Feiertag

Aus Bewerbungslage, optional fuer V2:
- juengste Bewerbung wurde abgelehnt
- Interview bald

### Empfohlene Kontexte fuer V1

- `default`
- `onboarding`
- `profile_building`
- `sources_missing`
- `search_refresh`
- `jobs_ready`
- `follow_up_due`
- `weekend`
- `holiday`

### Kontext-Prioritaet

Wenn mehrere Kontexte gleichzeitig gelten:

1. `holiday`
2. `weekend`
3. `follow_up_due`
4. `jobs_ready`
5. `search_refresh`
6. `sources_missing`
7. `profile_building`
8. `onboarding`
9. `default`

## Technischer Aufbau

### Backend

Neue Datei:
- `src/bewerbungs_assistent/services/daily_impulse_service.py`

Aufgaben:
- Impuls-Daten laden
- Kontext aus Workspace/Zeit bestimmen
- tagesstabile Auswahl treffen
- deaktivierte Anzeige respektieren

Empfohlene API:
- `get_daily_impulse(profile, workspace_summary, today=None) -> dict | None`

Rueckgabe:

```python
{
    "id": "impuls_042",
    "title": "Heute fuer dich",
    "text": "Heute reicht auch: Quellen checken, Suche anstossen, weitersehen.",
    "tags": ["jobsuche", "alltag"],
    "context": "search_refresh",
}
```

### Dashboard-API

Option A:
- in `/api/workspace-summary` integrieren

Option B, empfohlen:
- neuer Endpoint `/api/daily-impulse`

Warum Option B:
- sauber getrennt
- leichter testbar
- spaeter leichter ausbaubar

### Settings

Neue User-Preference:
- `daily_impulse_enabled`

Optional spaeter:
- `daily_impulse_tone`

V1:
- default `true`

### Frontend

Dashboard:
- neue kleine `DailyImpulseCard`

Settings:
- einfacher Toggle:
  - `Tagesimpuls im Dashboard anzeigen`

## Auswahl-Logik

### Wichtig

Nicht einfach `today.day_of_year % len(list)`.

Besser:
- erst passende Kandidaten nach Kontext filtern
- dann aus diesen stabil fuer den Tag auswaehlen

Beispiel:
- Seed aus `YYYY-MM-DD + context`
- daraus Index in Kandidatenliste

Vorteile:
- pro Tag stabil
- je Kontext anders
- Sammlung spaeter erweiterbar

## Feiertage

### V1 Empfehlung

Feiertage noch nicht perfekt loesen, sondern vorbereitet bauen:

Optionen:
1. nur Wochenende in V1
2. deutsche Feiertage spaeter ueber kleine Hilfsfunktion oder Bibliothek wie `holidays`

Empfehlung:
- V1: Wochenende sofort
- Feiertage V1.1 oder V2

Grund:
- Feiertagslogik ist nett, aber nicht noetig fuer den ersten nutzbaren Wert

## Content-Strategie

Vorhanden:
- `docs/TAGESIMPULSE_SEED.md` mit 140 kuratierten Originaltexten

Empfehlung fuer Implementierung:
- beim Einbau in maschinenlesbares JSON ueberfuehren
- Tags aus der Seed-Datei uebernehmen
- spaeter Content separat erweitern

## Testplan

### Backend-Tests

Neue Datei:
- `tests/test_daily_impulse_service.py`

Testfaelle:
- liefert `None`, wenn deaktiviert
- liefert fuer denselben Tag denselben Impuls
- liefert fuer verschiedene Kontexte unterschiedliche Kandidatenbereiche
- priorisiert Wochenende/Follow-up/etc. korrekt
- faellt auf `default` zurueck

### API-Tests

Erweiterung in:
- `tests/test_dashboard.py`

Testfaelle:
- `/api/daily-impulse` liefert gueltige Struktur
- deaktivierter Impuls liefert `enabled=false` oder `impulse=null`

### Browser-Tests

Erweiterung in:
- `tests/test_dashboard_browser.py`

Testfaelle:
- Karte sichtbar im Dashboard
- Toggle in Einstellungen deaktiviert Anzeige

## Konfliktarme Umsetzung

Damit Claude parallel zu anderer GitHub-Arbeit wenig Konflikte hat, sollte die Einfuehrung so geschnitten werden:

### Niedrige Konfliktwahrscheinlichkeit

- neue Content-Datei
- neuer Service `daily_impulse_service.py`
- neuer API-Endpoint
- kleine Card-Komponente
- kleiner Settings-Toggle

### Hoehere Konfliktwahrscheinlichkeit

- grosse Umbauten in `DashboardPage.jsx`
- breite Refactors im Settings-Bereich

### Empfehlung

Den Einbau in 3 kleine Schritte schneiden:

1. Content + Service + API
2. kleine Dashboard-Karte
3. Settings-Toggle + Tests

## Empfohlene Reihenfolge fuer Claude

1. Seed-Datei in JSON-Struktur ueberfuehren
2. `daily_impulse_service.py` bauen
3. `/api/daily-impulse` einfuehren
4. Dashboard-Karte einbauen
5. Toggle in Einstellungen
6. Tests ergaenzen
7. Ton/Spacing im UI feinziehen

## Ehrliche Priorisierung

Das Feature ist sinnvoll, aber nicht kritisch fuer die Kernfunktion von PBP.

Es lohnt sich, wenn:
- die Umsetzung klein bleibt
- die Texte hochwertig bleiben
- das Feature optional und unaufdringlich ist

Es lohnt sich nicht, wenn:
- es in grossen UI-Umbauten endet
- die Sammlung lieblos oder austauschbar wirkt
- es mit zu viel Logik ueberladen wird

## Fazit

Die Idee ist produktseitig gut.

Der richtige Einstieg ist:
- kleine, saubere V1
- kuratierter Content
- einfache Kontextlogik
- keine Ueberautomatisierung

So bleibt das Feature charmant und kippt nicht in Gimmick oder Kitsch.
