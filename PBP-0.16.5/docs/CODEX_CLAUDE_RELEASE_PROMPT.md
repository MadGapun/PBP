# Claude Release Prompt

Nutze diesen Prompt fuer Claude Code oder Claude Desktop, um den aktuellen
Codex-Arbeitsstand im PBP-Repo zu pruefen, sauber abzuschliessen und auf GitHub
zu veroeffentlichen.

```text
Bitte uebernimm den aktuellen Repo-Stand im PBP-Projekt und bereite ihn fuer
Commit, PR und Veroeffentlichung auf GitHub vor.

Arbeitsgrundlage:
- Nutze den aktuellen Working Tree auf Branch `codex/konsolidierung-sprint1`.
- Behandle den Stand als ernst gemeinte Integrationsarbeit, nicht als
  Experiment.
- Markus ist Endnutzer. PBP ist ein lokal-first Produkt fuer Claude Desktop,
  deutschsprachig und produktorientiert.

Lies zuerst in genau dieser Reihenfolge:
1. AGENTS.md
2. ZUSTAND.md
3. README.md
4. docs/architecture.md
5. docs/VERBESSERUNGSPLAN.md
6. docs/CODEX_ANALYSE.md
7. docs/CODEX_CLAUDE_RELEASE_PROMPT.md
8. src/bewerbungs_assistent/services/profile_service.py
9. src/bewerbungs_assistent/services/search_service.py
10. src/bewerbungs_assistent/services/workspace_service.py
11. src/bewerbungs_assistent/dashboard.py
12. src/bewerbungs_assistent/templates/dashboard.html
13. src/bewerbungs_assistent/tools/profil.py
14. tests/test_dashboard.py
15. tests/test_profile_service.py
16. tests/test_search_service.py
17. tests/test_workspace_service.py
18. tests/test_mcp_registry.py
19. tests/test_scrapers.py

Kontext zum aktuellen Codex-Stand:
- Service-Layer ausgebaut:
  - profile_service.py
  - search_service.py
  - workspace_service.py
- Neues Dashboard-API-Objekt: `/api/workspace-summary`
- Dashboard-UX deutlich ueberarbeitet:
  - klarerer Topbar- und Menueaufbau
  - Workspace-Kopf mit aktuellem Arbeitsstand
  - seitenbezogene Orientierung und Summary-Karten
  - bessere Profil-Schnellzugriffe
  - Jobs- und Bewerbungs-Summaries
  - Hash-Navigation und mehrere Bedienungsfixes
- Bugfixes:
  - Wizard speichert Quellen korrekt mit `active_sources`
  - Sprung zum Dokument- und Import-Bereich korrigiert
  - Runtime-Log-CSS-Fallback bereinigt
  - Quellenfilter in der Stellenansicht wird sauber neu aufgebaut
- Doku wurde auf den aktuellen Branch-Stand synchronisiert
- Teststand zum Codex-Abschluss: `187 passed`

Deine Aufgabe:
1. Pruefe den gesamten Working Tree sorgfaeltig.
2. Vergleiche Doku, Architektur und realen Code.
3. Suche nach letzten Inkonsistenzen, kleinen Regressionen oder Doku-Luecken.
4. Fuehre die komplette Testsuite aus.
5. Wenn noetig, nimm die letzten sauberen Korrekturen vor.
6. Erstelle danach:
   - eine knappe Change-Zusammenfassung
   - sinnvolle Commit(s)
   - einen passenden PR-Text
7. Veroeffentliche den Stand auf GitHub.

Abnahmekriterien:
- Tests bleiben komplett gruen.
- Doku und Ist-Stand sprechen dieselbe Sprache.
- Keine offensichtlichen UI- oder UX-Regressionsstellen bleiben offen.
- Die neuen Service-Module und die Workspace-Guidance sind klar nachvollziehbar.
- Markus bekommt ein gefuehrteres Dashboard statt einer reinen Rohdatenflaeche.

Worauf du besonders achten sollst:
- Sind `dashboard.py` und die neuen Service-Module sauber getrennt?
- Ist die Workspace-Priorisierung produktseitig sinnvoll?
- Sind Navigation, Menue und Seitenwechsel im Dashboard konsistent?
- Gibt es noch Stellen, an denen vor dem Veroeffentlichen Kontext manuell
  rekonstruiert werden muss?
- Fehlt irgendwo noch eine kleine Release-Politur, die den GitHub-Stand
  nachvollziehbarer macht?

Wenn alles sauber ist:
- committe den Stand
- pushe den passenden Branch
- erstelle oder aktualisiere den GitHub-PR
- gib danach eine kurze Rueckmeldung, was veroeffentlicht wurde und ob vor dem
  Merge noch etwas offen ist
```
