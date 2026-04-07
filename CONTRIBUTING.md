# Beitragen zu PBP

Danke, dass du PBP verbessern möchtest! Hier findest du alles, was du dafür wissen musst.

## Schnellstart

```bash
# Repository klonen
git clone https://github.com/MadGapun/PBP.git
cd PBP

# Python-Umgebung einrichten
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[all,dev]"
playwright install chromium

# Tests ausführen
python -m pytest tests/ -q

# Dashboard starten
python start_dashboard.py   # → http://localhost:8200

# Frontend entwickeln (Hot Reload)
cd frontend
pnpm install
pnpm run dev                # → http://localhost:5173
```

## Wie du beitragen kannst

### Bugs melden

Nutze das [Bug-Template](https://github.com/MadGapun/PBP/issues/new?template=bug_report.yml). Je mehr Details (Version, Betriebssystem, Schritte zum Reproduzieren), desto schneller können wir helfen.

### Features vorschlagen

Nutze das [Feature-Template](https://github.com/MadGapun/PBP/issues/new?template=feature_request.yml). Beschreibe das Problem, das du lösen möchtest — nicht nur die gewünschte Lösung.

### Code beitragen

1. **Fork** das Repository
2. Erstelle einen **Feature-Branch** von `develop`: `git checkout develop && git checkout -b feature/mein-feature`
3. Entwickle und teste lokal
4. Stelle sicher, dass alle Tests grün sind: `python -m pytest tests/ -q`
5. Erstelle einen **Pull Request** gegen `develop` (nicht gegen `main`!)

### Branch-Strategie

```
main       → Nur stabile, produktionsreife Releases (= "Latest" auf GitHub)
develop    → Laufende Entwicklung, Beta-Versionen (= Pre-release auf GitHub)
feature/*  → Einzelne Features/Bugfixes, werden in develop gemergt
```

- **Stabile Releases** (z.B. `v1.4.3`) werden auf `main` getaggt → GitHub "Latest Release"
- **Beta-Releases** (z.B. `v1.5.0-beta.1`) werden auf `develop` getaggt → GitHub "Pre-release"
- Wenn eine Beta stabil genug ist, wird `develop` in `main` gemergt und als stabiler Release veröffentlicht

### Tipp für die Zusammenarbeit mit Claude/Codex

Claude (und andere KI-Assistenten) brauchen manchmal explizite, wiederholte Anweisungen — besonders bei komplexeren Aufgaben. Wenn etwas nicht beim ersten Mal klappt: Nochmal klar sagen, was genau erwartet wird. Das ist kein Fehler, sondern Teil des Workflows.

## Konventionen

### Code-Stil

- **Python:** Keine strikten Linter-Regeln, aber sauberer, lesbarer Code
- **Deutsche UI:** Alle Texte, Tooltips und Fehlermeldungen auf Deutsch
- **Docstrings:** Für neue Tools und Services erwünscht

### Commit-Messages

```
feat: Kurze Beschreibung     # Neues Feature
fix: Kurze Beschreibung      # Bugfix
docs: Kurze Beschreibung     # Dokumentation
refactor: Kurze Beschreibung # Refactoring ohne Funktionsänderung
```

### Tests

- Neue Features sollten Tests haben
- Tests liegen in `tests/`
- Ausführen: `python -m pytest tests/ -q`
- Browser-Tests brauchen Playwright: `playwright install chromium`

### Projektstruktur

```
src/bewerbungs_assistent/
├── tools/          ← MCP-Tools (72 Tools in 8 Modulen)
├── services/       ← Service-Layer
├── job_scraper/    ← 18 Jobportal-Scraper
├── database.py     ← SQLite Schema
├── dashboard.py    ← FastAPI + REST-API
└── server.py       ← MCP-Server (Composition Root)

frontend/           ← React 19 + Vite + Tailwind
tests/              ← pytest Test-Suite
```

## Fragen?

Erstelle ein [Issue](https://github.com/MadGapun/PBP/issues) — wir antworten auf Deutsch und Englisch.

## Lizenz

Mit deinem Beitrag stimmst du zu, dass er unter der [MIT-Lizenz](LICENSE) veröffentlicht wird.
