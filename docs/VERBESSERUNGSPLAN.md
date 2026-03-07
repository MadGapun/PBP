# PBP Verbesserungsplan

Erstellt auf Basis der Codex-Analyse (docs/CODEX_ANALYSE.md) und eigenem Code-Review.
Fokus: Konsolidierung, nicht neue Features.

Stand: 2026-03-07

---

## Akute Probleme (Prio 1 — sofort beheben)

### 1.1 ZUSTAND.md ist komplett veraltet

**Problem:** ZUSTAND.md beschreibt den Stand v1.0.0 (2026-02-26). Das Projekt ist
inzwischen bei v0.11.0 mit 23 zusaetzlichen Tools, 6 Schema-Versionen mehr und
43 neuen Tests. Jeder KI-Agent oder Mensch, der ZUSTAND.md als Referenz nimmt,
arbeitet mit falschen Annahmen.

| Aspekt | ZUSTAND.md | Tatsaechlich |
|--------|-----------|-------------|
| Version | 1.0.0 | 0.11.0 |
| Tools | 21 | 44 |
| Prompts | 8 | 12 |
| Schema | v2 | v8 |
| Tabellen | 13 | 15+ |
| API-Endpoints | 28 | ~47 |
| Tests | 65 | 108 |
| Jobquellen | 8 | 9 |

**Massnahme:** ZUSTAND.md komplett auf den realen Stand aktualisieren.

### 1.2 Inkonsistente Zahlen in README.md

**Problem:** README.md ist groesstenteils aktuell, enthaelt aber Widersprueche:
- Highlights: "8 Jobportale" → tatsaechlich 9 (freelance_de fehlt)
- Architektur-Diagramm: 8 Scraper-Dateien → freelance_de.py fehlt
- Tests-Badge: "100 passing", Struktur-Sektion: "85 Tests", Test-Sektion: "100 Tests" → tatsaechlich 108
- Scoring-Test-Count: "19" im Tests-Block, tatsaechlich 24

**Massnahme:** Zahlen auf den tatsaechlichen Stand (108 Tests, 9 Quellen) bringen.

### 1.3 AGENTS.md Inkonsistenz

**Problem:** AGENTS.md sagt "8 Quellen" bei den Job-Scrapern.

**Massnahme:** Auf 9 Quellen korrigieren, freelance_de erwaehnen.

---

## Kurzfristige Verbesserungen (Prio 2 — in dieser Session)

### 2.1 Versionierung vereinheitlichen

**Problem:** ZUSTAND.md nennt "1.0.0", pyproject.toml hat "0.11.0". Die
Versionsnummer in pyproject.toml ist die einzige maschinenlesbare Wahrheit.

**Massnahme:** pyproject.toml als Single Source of Truth definieren.
Alle Dokumente auf 0.11.0 bringen.

### 2.2 Redundante Dokumentation reduzieren

**Problem:** 6 Markdown-Dateien mit ueberlappenden Inhalten:
- README.md (Hauptdoku, 524 Zeilen — am aktuellsten)
- ZUSTAND.md (Projektzustand — stark veraltet)
- DOKUMENTATION.md (Technische Details)
- OPTIMIERUNGEN.md (Optimierungs-Tracking)
- TESTVERSION.md (Testanleitung)
- CHANGELOG.md (Aenderungshistorie)

Das Changelog in README.md dupliziert CHANGELOG.md. ZUSTAND.md dupliziert
teilweise README.md und AGENTS.md.

**Massnahme:**
- ZUSTAND.md auf den realen Stand bringen und klarer als Status-Snapshot definieren
- README.md-Changelog auf "Letzte 3 Versionen + Link auf CHANGELOG.md" kuerzen
- OPTIMIERUNGEN.md: Pruefen ob noch relevant (v0.11.0 hat "alle Optimierungen abgeschlossen")

### 2.3 docs/architecture.md und docs/codex_context.md auf Stand bringen

**Problem:** Diese Dateien wurden erst kuerzlich erstellt und sind naeher am
realen Stand, aber noch nicht ganz exakt (9 vs. 8 Quellen).

**Massnahme:** Zahlen synchronisieren.

---

## Mittelfristige Verbesserungen (Prio 3 — naechste Sessions)

### 3.1 server.py modularisieren

**Problem:** server.py hat 3.261 Zeilen und enthaelt 44 Tool-Definitionen,
12 Prompt-Definitionen, Logging-Wrapper und Initialisierungslogik. Neue
Features landen automatisch hier. Das erschwert Wartung, Testing und
parallele Arbeit.

**Empfohlene Zielstruktur:**
```
src/bewerbungs_assistent/
    server.py                    # Composition Root (~200 Zeilen)
    tools/
        __init__.py
        profile.py               # 14 Tools (Profil, Multi-Profil, Erfassung)
        documents.py             # 6 Tools (Extraktion, Import/Export)
        jobs.py                  # 5 Tools (Suche, Bewertung, Fit)
        applications.py          # 5 Tools (Bewerbung, Status, Statistiken)
        search.py                # 2 Tools (Suchkriterien, Blacklist)
        export.py                # 2 Tools (Lebenslauf, Anschreiben)
        analytics.py             # 9 Tools (Gehalt, Firmen, Trends, etc.)
        system.py                # 1 Tool (Factory Reset o.ae.)
    prompts.py                   # 12 Prompt-Definitionen
```

**Nutzen:**
- Bessere Testbarkeit (einzelne Module isoliert testbar)
- Klarere Verantwortlichkeiten
- Weniger Merge-Konflikte
- Einfacher fuer mehrere KI-Agenten und Menschen

**Risiken:**
- FastMCP Tool-Registrierung muss sauber funktionieren (pruefen!)
- Bestehende Tests duerfen nicht brechen
- Import-Pfade aendern sich

**Aufwand:** 2-4 Stunden, mittleres Risiko

### 3.2 Service-Layer einfuehren

**Problem:** dashboard.py und server.py greifen beide direkt auf database.py
zu. Business-Logik (z.B. Scoring, Fit-Analyse, Follow-up-Berechnung) ist
teils in server.py, teils in database.py, teils in job_scraper/__init__.py.

**Empfehlung:** Leichtgewichtiger Service-Layer als Zwischenschicht.
Nicht sofort noetig, aber empfohlen wenn neue Features hinzukommen.

**Aufwand:** 4-8 Stunden, niedriges Risiko

### 3.3 Teststrategie erweitern

**Aktueller Stand:** 108 Tests fuer database.py, scoring und export.
Nicht getestet: server.py (44 Tools), dashboard.py (47 Endpoints),
Scraper, Integration.

**Empfohlene Erweiterungen (nach Nutzen sortiert):**
1. Dashboard-API-Tests (FastAPI TestClient) — schnell, hoher Wert
2. MCP-Tool-Smoke-Tests (Tool aufrufen, pruefen ob kein Crash) — mittel
3. Multi-Profil-Regressionstests (Profil-Isolation) — wichtig
4. Scraper-Fixture-Tests (gespeicherte HTML/JSON-Responses) — stabil

**Aufwand:** Je Kategorie 2-4 Stunden

---

## Nicht empfohlen (explizit ausgeklammert)

### Cloud-Deployment / Multi-User
PBP ist ein lokales Endnutzerprodukt. Cloud-Architektur wuerde die
Kernidee (Privatsphaere, Einfachheit) untergraben.

### Framework-Wechsel
FastMCP, SQLite und FastAPI sind die richtige Wahl fuer dieses Produkt.
Kein Grund fuer Aenderungen.

### Neue Features
Das Projekt ist bei v0.11.0 mit "alle Optimierungen abgeschlossen".
Konsolidierung hat Vorrang vor Feature-Wachstum.

---

## Umsetzungsreihenfolge fuer diese Session

| # | Aufgabe | Risiko | Aufwand |
|---|---------|--------|---------|
| 1 | ZUSTAND.md auf realen Stand bringen | Kein | 20 min |
| 2 | README.md Zahlen korrigieren (9 Quellen, 108 Tests) | Kein | 10 min |
| 3 | AGENTS.md korrigieren (9 Quellen) | Kein | 5 min |
| 4 | docs/architecture.md + codex_context.md synchronisieren | Kein | 10 min |
| 5 | OPTIMIERUNGEN.md pruefen und ggf. als abgeschlossen markieren | Kein | 5 min |
| 6 | Redundantes Changelog in README.md kuerzen | Niedrig | 10 min |

**Nicht in dieser Session:** server.py Modularisierung (zu gross fuer
einen ersten Konsolidierungs-Commit, sollte eigenstaendig geplant werden).

---

*Erstellt von Claude Code, 2026-03-07*
