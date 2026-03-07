# Auftrag: PBP Konsolidierung auf Basis der Codex-Analyse

## Kontext

PBP (Persoenliches Bewerbungs-Portal) ist ein MCP-Server fuer Claude Desktop.
Das Repo liegt hier auf dem Server unter: /home/claude/PBP/
Die produktive Deployment-Instanz laeuft unter: /home/chatgpt/pbp/bewerbungs-assistent/

OpenAI Codex hat eine umfassende Analyse des Projekts durchgefuehrt.
Die Ergebnisse liegen in docs/CODEX_ANALYSE.md.

### Team-Rollen
- Markus (OPA): Produktverantwortlicher, Endnutzer, kein Programmierer
- PAPA (Claude Desktop/Anthropic): Hat den Grossteil der technischen Implementierung gemacht
- MAMA (ChatGPT): Strategische Planung und Koordination
- TANTE (Codex): Code-Vorlagen, UI, GitHub-Arbeit, hat diese Analyse erstellt
- Du (Claude Code): Technische Weiterarbeit, Konsolidierung, Code-Verbesserung

### Wichtige Konventionen
- Deutsche UI-Texte und Logs
- Keine API-Keys im Code (immer .env oder Umgebungsvariablen)
- SQLite WAL Mode, Profil-Isolation
- STAR-Methode fuer Projekte
- Playwright fuer Job-Scraping
- Aenderungen als Feature-Branch, nie direkt auf main

## Deine Aufgabe

Lies die Dateien in dieser Reihenfolge:
1. AGENTS.md
2. docs/CODEX_ANALYSE.md
3. README.md
4. ZUSTAND.md
5. pyproject.toml
6. src/bewerbungs_assistent/server.py
7. src/bewerbungs_assistent/database.py
8. src/bewerbungs_assistent/dashboard.py
9. src/bewerbungs_assistent/job_scraper/__init__.py
10. tests/

Dann:

### Phase 1: Analyse und Plan
- Vergleiche Codex-Analyse, Dokumentation und realen Code
- Identifiziere die wichtigsten Diskrepanzen zwischen Doku und Implementierung
- Erstelle einen umsetzbaren Verbesserungsplan

### Phase 2: Priorisierte Umsetzung
Priorisiere in dieser Reihenfolge:
1. Fehler und Inkonsistenzen (v.a. ZUSTAND.md vs. realer Stand)
2. Wartbarkeit/Struktur (server.py Modularisierung)
3. Usability (Dashboard, Nutzerfluss)
4. Produkt-Erweiterungen (nur wenn sie Markus realen Nutzen bringen)

### Phase 3: Dokumentation
- Bringe README.md, ZUSTAND.md und den tatsaechlichen Systemstand in Einklang
- Aktualisiere Versionsnummern konsistent

## Einschraenkungen
- Schlage keine rein theoretischen Architekturideen vor
- PBP ist ein lokales Endnutzerprodukt, kein Cloud-SaaS
- Die naechste sinnvolle Phase ist Konsolidierung, nicht Feature-Wachstum
- Aenderungen immer auf einem Feature-Branch (z.B. claude-code/konsolidierung)
- Bewerte PBP auch als Produkt: Nutzerfluss, gefuehrte Entscheidungen, Dashboard-Verstaendlichkeit

## Erwartetes Ergebnis
- docs/VERBESSERUNGSPLAN.md mit:
  - Akuten Problemen
  - Kurzfristigen Verbesserungen
  - Mittelfristigen Erweiterungen
  - Konkreten Umsetzungsschritten
- Erste konkrete Code-Aenderungen auf dem Feature-Branch
- Aktualisierte Dokumentation
