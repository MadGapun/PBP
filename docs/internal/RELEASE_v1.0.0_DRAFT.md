# PBP v1.0.0 — Persönliches Bewerbungs-Portal

Der erste offizielle Public Release. PBP verwaltet deine Bewerbungen, durchsucht
diverse Stellenportale und gibt dir ehrliches Feedback zu deinen Unterlagen — mit
konkreten Vorschlägen, wie es besser geht. Läuft lokal, kostet nichts, deine Daten
bleiben bei dir.

## Was steckt drin

- **72 MCP-Tools** in 8 Modulen (Profil, Dokumente, Jobs, Bewerbungen, Analyse, Export, Suche, Workflows)
- **16 MCP-Prompts** — von Ersterfassung über Interview-Simulation bis Gehaltsverhandlung
- **18 Jobquellen** — Bundesagentur, StepStone, LinkedIn, XING, Indeed, Monster, Hays und 11 weitere
- **E-Mail-Integration** — .eml/.msg Import, automatisches Matching, Meeting-Extraktion mit Kalender-Widget
- **React 19 Dashboard** — 7 Bereiche mit Drag & Drop, Live-Updates, Statistik-Charts (Recharts)
- **PDF/DOCX-Export** — Lebenslauf und Anschreiben in professionellem Layout (ATS-konform)
- **Multi-Profil** — Mehrere Profile mit vollständiger Daten-Isolation
- **Scoring-Regler** — 6 konfigurierbare Dimensionen für persönliche Gewichtung
- **Geocoding** — Automatische Entfernungsberechnung zu Stellenorten
- **Geführter Bewerbungs-Workflow** — Kontextabhängige nächste Schritte pro Status
- **362 Tests** — alle grün, 4 bewusst geskippt
- **Schema v18** — SQLite WAL Mode mit CASCADE
- **Zero-Knowledge Installer** — `INSTALLIEREN.bat` doppelklicken und loslegen

## Schnellstart

```bat
:: Windows — Doppelklick auf:
INSTALLIEREN.bat

:: Oder manuell:
pip install -e ".[all]"
playwright install chromium
```

Danach in Claude Desktop: **"Ersterfassung starten"**

## Voraussetzungen

- **Python 3.11+** (Windows: wird vom Installer mitgebracht)
- **Claude Desktop** (Free, Pro oder Max)
- **~500 MB Festplatte** (Python + Dependencies + Playwright)

## Versionshistorie

PBP wurde seit Februar 2026 in 65+ inkrementellen Releases entwickelt (v0.1.0 → v0.33.9).
Ein früherer `v1.0.0`-Tag vom 2. März 2026 wurde entfernt — er zeigte auf einen frühen
Prototyp-Stand (21 Tools) und entsprach nicht dem Reifegrad eines 1.0-Produkts.

Dieser Release basiert auf v0.33.9 und enthält zusätzlich:
- Community-Dateien (CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md)
- GitHub Issue-/PR-Templates
- Aktualisierte Dokumentation und Badges

## Credits

- **Markus Birzite** — Konzept, Architektur, Projektleitung
- **Claude** (Anthropic) — Hauptentwickler seit v0.1.0
- **ChatGPT** (OpenAI) — Bewertung, Analyse & Qualitätssicherung
- **Codex** (OpenAI) — Code-Analyse, Recovery, Bugfixes
- **Toms (@Koala280)** — React 19 Frontend, UX-Issues
- **ELWOSA** — Projektrahmen und Infrastruktur
