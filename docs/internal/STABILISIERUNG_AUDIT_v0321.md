# Stabilisierungs-Audit v0.32.1

Stand: 2026-03-22
Branch: `codex/pbp-stabilisierung-v0321`
Basis: `origin/main` auf Tag `v0.32.1`

## Kurzfazit

PBP ist auf dem aktuellen Stand grundsaetzlich lauffaehig.

- Voller Testlauf: `345 passed, 4 skipped`
- Web-Build: gruen
- React-Frontend, Dashboard und MCP-/Backend-Grundfunktionen laufen

Der User-Eindruck "Issues werden geschlossen, aber nicht komplett erledigt" war trotzdem berechtigt.
Die Hauptursache ist nicht ein instabiles Gesamtsystem, sondern eine Reihe von Themen, die
zwischen 2026-03-21 und 2026-03-22 sehr schnell implementiert und geschlossen wurden.
Dabei sind mehrere Punkte nur teilweise oder nur in einem Teilpfad angekommen.

## Was ich konkret nachgezogen habe

### 1. Quellenlogik fuer Bewerbungen/Berichte/Statistiken repariert

Betroffene Probleme:

- `applications.source` wurde nicht zentral aus der verknuepften Stelle uebernommen
- Statistik/Report bevorzugten haeufig `jobs.source` statt `applications.source`
- manuell angelegte Bridge-Jobs (`jobs.source = manuell`) haben dadurch echte Quellen
  wie `freelance_de` oder `linkedin` im Bericht ueberschrieben

Behobene Stellen:

- `src/bewerbungs_assistent/database.py`
- `src/bewerbungs_assistent/tools/export_tools.py`

Wirkung:

- neue Bewerbungen ueber verknuepfte Jobs uebernehmen ihre Quelle jetzt zentral
- `get_score_stats()` zaehlt Bewerbungsquellen jetzt fachlich korrekt
- Export/Bewerbungsbericht bevorzugt jetzt die echte Bewerbungsquelle

GitHub-Bezug:

- Offenes Bug-Issue `#185` wurde auf Branch-Ebene adressiert und kommentiert

### 2. Bewerbungsbericht/Report nutzt wieder die historische Score-Verteilung

Das war einer der Kernpunkte aus `#178`: die Score-Verteilung fuer Bericht/Analyse darf nicht
nur aktive Jobs betrachten. Der Branch nutzt jetzt wieder die historisch vollstaendige
Verteilung fuer nicht angepinnte Jobs.

### 3. Sichtbarer Tagesimpuls-Titel mit Umlaut korrigiert

Der user-facing Titel des Tagesimpulses wurde von der ASCII-Schreibweise auf die
korrekte Umlaut-Variante zurueckgezogen.

Hinweis:

Die groessere Text-/Umlaut-Konsolidierung im UI ist damit noch nicht komplett erledigt.
Dafuer wurde ein Folge-Issue angelegt.

## Bewertung der Issues seit 2026-03-21

### Sauber oder weitgehend sauber umgesetzt

- `#151` Freelance-Erkennung / Stellenart editierbar
- `#153` Post-Search Cleanup
- `#154` Abgleich Jobsuche gegen bestehende Bewerbungen
- `#155` stale Jobsuche-Status
- `#156` / `#171` ID-Anzeige
- `#159` / `#160` / `#161` LinkedIn/XING/Bridge-Doku
- `#162` Badge-/Metrik-Inkonsistenz
- `#163` Tagesimpulse V1
- `#167` Geocoding / Distanz
- `#168` Blacklist-Bereinigung
- `#169` Scoring-Regler-System
- `#170` gefuehrter Bewerbungs-Workflow
- `#172` auto-save Stellenbeschreibung
- `#174` ATS-CV
- `#175` FAQ / Erste-Schritte
- `#176` Dokument-Upload in Timeline
- `#177` Auto-Zuordnung von Dokumenten
- `#181` employment_type / Bewerbungsbearbeitung / ID-Anzeige
- `#183` Fuzzy-/Synonym-Matching im Keyword-Scoring
- `#184` proaktive Keyword-Vorschlaege

### Teilweise umgesetzt / zu frueh geschlossen

- `#173`
  - Bewerbungsbericht wurde deutlich ausgebaut
  - ein Teil der Quellen-/Score-Logik war aber noch nicht ueberall konsistent
  - spaetere Folgeprobleme liefen in `#178` und `#185`

- `#178`
  - Score-Brackets und Bewerben-Bonus wurden umgesetzt
  - die Quellenlogik war aber noch nicht komplett durchgezogen
  - dieser Rest ist auf diesem Branch nachgezogen

- `#179`
  - der konkrete Spruchtext war korrigiert
  - aber die breitere ASCII-/Umlaut-Konsolidierung im UI war nicht abgeschlossen
  - Folge-Issue: `#187`

- `#180`
  - es gibt jetzt sinnvolle Mitigation:
    - fehlende Beschreibung wird markiert
    - Score wird als unsicher behandelt
    - Fit-Analyse warnt
  - die eigentliche Wurzel bleibt aber: Beschreibungen muessen weiterhin so oft wie moeglich
    sauber extrahiert werden

- `#182`
  - archivierte Bewerbungen sind standardmaessig aus der API-/Standardansicht raus
  - aber der sichtbare UX-Schritt zum Wiedereinblenden fehlt noch
  - Folge-Issue: `#186`

## Neu angelegte Folge-Issues

- `#186` Review: `#182` ist nur teilweise abgeschlossen, Archiv-Toggle fehlt
- `#187` Review: Restliche ASCII-/Umlaut-Texte in UI-Hilfe und Doku konsolidieren

## Release-/Versionsbewertung

### Kann man daraus eine lauffaehige, downloadbare Version machen?

Ja.

Mit dem aktuellen Branch-Stand wuerde ich PBP als lauffaehig und downloadbar einstufen.
Es gibt keine Hinweise auf einen funktionalen Blocker im Kernsystem.

### Was ist noch nicht "perfekt", aber kein Blocker?

- UI-Texte/ASCII-Reste sind noch nicht vollstaendig vereinheitlicht
- Bewerbungsarchiv hat noch keinen klaren Toggle in der React-Oberflaeche
- Export-Report/Statistik war ein Hotspot und sollte bei den naechsten Aenderungen
  weiter mit Regressionstests abgesichert bleiben

### Welche naechste Version ist sinnvoll?

Wenn nur die Stabilisierung dieses Branches veroeffentlicht wird:

- Empfehlung: `v0.32.2`

Begruendung:

- reiner Bugfix-/Stabilisierungsschnitt
- keine neue Produktphase
- keine Architekturverschiebung

## Empfehlung fuer Claude / naechsten Integrationsschritt

1. Diesen Branch gegen `main` reviewen und mergen
2. `#185` nach Merge schliessen
3. `#186` und `#187` bewusst offen lassen
4. Falls ein Release gemacht werden soll:
   - `CHANGELOG.md` um den Stabilisierungsschnitt ergaenzen
   - `v0.32.2` statt Minor/Feature-Sprung
5. Beim Merge die erzeugten `static/dashboard` Build-Artefakte mitnehmen, damit der
   downloadbare Stand wirklich zum aktuellen Frontend-Code passt

## Verifikation

Ausgefuehrt auf diesem Branch:

- `python -m pytest tests -q`
- Ergebnis: `345 passed, 4 skipped`

- `pnpm run build:web`
- Ergebnis: gruen
