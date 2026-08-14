# Claude Code Handoff

Nutze diesen Prompt fuer Claude Code, um den aktuellen Codex-Arbeitsstand
sauber zu uebernehmen, zu pruefen und final auf GitHub weiterzufuehren.

```text
Bitte uebernimm den aktuellen Stand im PBP-Repo auf Basis des Branches
`codex/dashboard-smoke-tests`.

Wichtiger Kontext:
- PBP ist ein lokal-first Produkt fuer Claude Desktop, deutschsprachig und fuer
  Markus als Endnutzer gebaut.
- Der letzte veroeffentlichte Release ist `v0.14.0`.
- Codex hat danach zwei Folgearbeiten vorbereitet:
  1. eine Release-Review zu `v0.14.0`
  2. echte Dashboard-Browser-Smoke-Tests plus Doku-Sync
- Die Release-Review wurde in diesen Branch bereits uebernommen.
- Es existiert zusaetzlich noch ein aelterer, separater Docs-Branch
  `codex/release-review-v0140` mit PR #36. Wenn dieser Branch hier alles
  enthaelt, kann die alte PR als redundant geschlossen oder entsprechend
  ersetzt werden.

Lies zuerst in dieser Reihenfolge:
1. AGENTS.md
2. README.md
3. ZUSTAND.md
4. DOKUMENTATION.md
5. CHANGELOG.md
6. docs/VERBESSERUNGSPLAN.md
7. docs/architecture.md
8. docs/codex_context.md
9. docs/RELEASE_REVIEW_v0.14.0.md
10. tests/test_dashboard_browser.py
11. tests/test_dashboard.py
12. src/bewerbungs_assistent/templates/dashboard.html

Was Codex in diesem Branch bereits umgesetzt hat:
- neue Browser-Smoke-Tests in `tests/test_dashboard_browser.py`
  - Erststart mit Wizard und Welcome-Screen
  - Tab-Navigation plus Dokument-Sprung
  - Workspace-Guidance bei ueberfaelligen Follow-ups
  - Mobile-Layout ohne Horizontal-Overflow
- Doku-Sync fuer den aktuellen Repo-Stand mit 190 Tests
- Release-Review-Datei `docs/RELEASE_REVIEW_v0.14.0.md`
- voller Testlauf lokal gruen: `190 passed`

Deine Aufgabe:
1. Pruefe den gesamten Branch sorgfaeltig.
2. Verifiziere besonders die Browser-Smoke-Tests auf Stabilitaet und Sinn.
3. Vergleiche Doku und echten Stand:
   - Tests: 190
   - Browser-Smokes vorhanden
   - voller Test-Setup mit `.[all,dev]` + `playwright install chromium`
4. Fuehre die komplette Testsuite aus.
5. Wenn noetig, nimm letzte saubere Korrekturen vor.
6. Erstelle danach einen sauberen GitHub-Abschluss:
   - Commit(s) falls noch noetig
   - Push des Branches
   - PR gegen `main`
7. Entscheide bewusst, ob PR #36 noch gebraucht wird:
   - wenn redundant: schliessen
   - wenn nicht redundant: sauber begruenden

Abnahmekriterien:
- komplette Testsuite bleibt gruen
- Browser-Smokes laufen stabil und pruefen echte Nutzerpfade
- Doku ist konsistent zum aktuellen Repo-Stand
- `v0.14.0` selbst wird nicht umgeschrieben
- der aktuelle Branch ist klar als Nacharbeit nach `v0.14.0` erkennbar

Worauf du besonders achten sollst:
- keine erneute Doku-Drift
- keine fragilen Browser-Tests, die nur zufaellig lokal laufen
- klare Trennung zwischen historischem Release `v0.14.0` und nachgelagerter Repo-Arbeit
- ob die README-Testsektion fuer Entwickler wirklich klar genug ist

Wenn alles sauber ist:
- pushe `codex/dashboard-smoke-tests`
- lege oder aktualisiere den PR
- schliesse den redundanten Docs-only-PR, falls dieser Branch ihn ersetzt
- gib danach eine knappe Rueckmeldung, was veroeffentlicht oder vorbereitet wurde
```
