# Claude Code — PBP Kickstart Prompt

<!-- Markus: Dieses Prompt an Claude Code schicken wenn eine neue Session beginnt. -->
<!-- Ersetzt nicht AGENTS.md — ergaenzt es mit aktuellem Stand und Kontext. -->

---

Du arbeitest an **PBP (Persoenliches Bewerbungs-Portal)**, einem Open-Source-Tool
fuer KI-gestuetzte Bewerbungsverwaltung. GitHub: https://github.com/MadGapun/PBP

## Dein Arbeitsbereich

- **Du laeuft auf:** ELWOSA (Linux, Heimserver von Markus)
- **Repo:** das ausgecheckte PBP-Repository in deinem Arbeitsverzeichnis
- **Aktueller Stand:** Lese zuerst `AGENTS.md` + `CHANGELOG.md` fuer den genauen Versionsstand

## Wichtigste Architektur-Fakten

```
Python Backend:   src/bewerbungs_assistent/
  server.py       MCP-Server (FastMCP, Composition Root)
  dashboard.py    FastAPI REST-API + Auslieferung des React-SPA
  database.py     SQLite (WAL, Schema-Migrationen v1->aktuell)
  tools/          MCP-Tools (profil, jobs, bewerbungen, dokumente, ...)
  services/       Service-Layer
  static/         Kompiliertes React-Bundle (NICHT manuell editieren)

React Frontend:   frontend/src/
  App.jsx         Hauptapp, Routing, Topbar, globales Layout
  pages/          Eine Datei pro Tab (DashboardPage, ProfilePage, ...)
  components/     Wiederverwendbare UI-Komponenten (ui.jsx = Basis)
  styles.css      Tailwind + Custom CSS (CSS-Variablen fuer Theming)
```

## Pflichtschritte vor jeder Aenderung

```bash
git pull                          # Aktuellen Stand holen
python -m pytest tests/ -q        # Baseline: alle Tests gruen?
grep version pyproject.toml       # Welche Version ist aktiv?
```

## Pflichtschritte nach jeder Aenderung

```bash
python -m pytest tests/ -q        # Keine Regressionen
# Bei Frontend-Aenderungen:
cd frontend && pnpm run build      # Bundle neu bauen
# Build-Output geht automatisch nach src/bewerbungs_assistent/static/dashboard/
```

**Wichtig:** Kein Frontend-Build = Nutzer sieht beim naechsten Install nichts.
Das Bundle MUSS committed werden.

## Arbeitsstil

- **Issues sind deine Aufgabenliste** — lese das Issue vollstaendig bevor du anfaengst
- **Ursachenanalyse im Issue = Hypothese**, nicht Fakt — verifiziere im Code
- **Scope halten** — nur was im Issue steht, kein opportunistisches Refactoring
- **Tests schreiben** wenn neue Logik entsteht — das Projekt hat 360+ Tests
- **Keine AGENTS.md-Updates** ohne expliziten Auftrag von Markus
- **Deutsche UI-Texte** — alle sichtbaren Strings auf Deutsch, Umlaute korrekt

## Zusammenarbeit mit Claude Chat

Markus hat zwei Claude-Instanzen:
- **Claude Chat (claude.ai):** analysiert lokal, schreibt Issues, Sparring-Partner
- **Du (Claude Code):** implementierst, testest, commitest

Issues von Chat erkennst du daran, dass sie Dateinamen + Zeilennummern enthalten
und eine "Ursachenanalyse"-Sektion haben. Die Hypothesen darin sind gut recherchiert
aber nicht verifiziert — du machst die Verifikation.

Wenn du etwas findest das nicht im Issue steht aber eindeutig falsch ist:
Kommentar im Issue, **nicht** still mitfixen.

## Haeufige Fallen

- `pnpm run build` vergessen nach JSX-Aenderungen
- `profile_id`-Filter vergessen bei neuen SQL-Queries (Multi-Profil!)
- Schema-Migration fehlt bei neuen Datenbankfeldern (Migrationskette in database.py)
- `__version__` in `__init__.py` und `pyproject.toml` muessen synchron sein
- Playwright-Scraper: nur sync, kein async (haengt im PBP-Server-Kontext, Issue #238)

## Wenn du nicht weiterkommst

Schreib einen Kommentar im GitHub Issue mit:
- Was du probiert hast
- Wo es haengt
- Was du fuer den naechsten Schritt brauchst

Markus schaut regelmaessig rein und eskaliert ggf. zu Claude Chat fuer weitere Analyse.
