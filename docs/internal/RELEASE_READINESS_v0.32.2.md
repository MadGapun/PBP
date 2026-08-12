# Release Readiness v0.32.2

Stand: 2026-03-23
Branch: `codex/pbp-stabilisierung-v0321`

## Kurzfazit

`v0.32.2` ist aus meiner Sicht ein sinnvoller Patch-Release-Kandidat.

- voller Testlauf: `349 passed, 4 skipped`
- Web-Build: gruen
- wichtigste React-Hauptpfade: verifiziert
- Fokus dieses Patches: Nutzerfuehrung, Sichtbarkeit von Zustaenden, saubere Archiv-/Score-UX

## Was fuer den Release neu dazu kam

### 1. Bewerbungsfluss ist jetzt vollstaendiger

- Archivierte Bewerbungen koennen in der React-Oberflaeche wieder eingeblendet werden
- die Seite zeigt jetzt einen klaren naechsten sinnvollen Schritt
- Entwuerfe, Follow-ups, Interview-Phase und Archiv werden sichtbar eingeordnet

### 2. Stellenfluss ist ehrlicher

- Stellen mit fehlender oder sehr kurzer Beschreibung werden als `Score unsicher` markiert
- es gibt einen gezielten Filter `Nur ohne Beschreibung`
- die Stellenansicht sagt jetzt klarer, ob gerade Suche, Filter oder Datenqualitaet das eigentliche Problem sind

### 3. Dashboard fuehrt aktiver

- Workspace-Readiness wird als eigene Karte sichtbar
- vorhandene Workspace-Signale werden nicht nur intern berechnet, sondern als direkte Handlungshinweise gezeigt

### 4. Release-Hygiene wurde nachgezogen

- Versionsdrift zwischen `pyproject.toml` und `src/bewerbungs_assistent/__init__.py` ist bereinigt
- `CHANGELOG.md`, `README.md` und `AGENTS.md` sind auf `v0.32.2` angehoben

## Restpunkte vor einer spaeteren "fast fertig"-Version

Nicht blockierend fuer `v0.32.2`, aber sichtbar:

- `Issue #187`: restliche ASCII-/Umlaut-Konsolidierung in UI-Hilfe und Doku
- Build-Warnung wegen grossem Frontend-Bundle
- DeprecationWarnings im PDF-Report-Export (`fpdf2` `ln=` API)

## Empfehlung

Wenn wir jetzt einen Patch-Release wollen, ist `v0.32.2` gerechtfertigt.

Wenn wir stattdessen auf einen groesseren Release-Kandidaten hinarbeiten, dann ist der naechste sinnvolle Block:

1. restliche Text-/Umlaut-Konsolidierung
2. PDF-Export-Warnungen abbauen
3. optional Bundle-Optimierung
4. danach erst wieder groessere Feature-Pakete
