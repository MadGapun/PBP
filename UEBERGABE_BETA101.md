# ÜBERGABE: beta.101-Fertigstellung (Session-Limit-Unterbrechung 10.06.2026)

> **Für Claude Code beim Neustart:** Dies ist der vollständige Arbeitsstand.
> Auftrag des Users: Beta auf freigabefähigen Stand bringen (Stabilität für
> Neulinge, Nutzerführung, Wiki aktuell, Master-Plan-Disziplin). Nach
> Abschluss: Bestandsaufnahme. Diese Datei nach erfolgreichem Release löschen.

## Wo wir stehen

**Branch `beta-stabilisierung`** (auf GitHub, PR #693 offen, CI grün bis Commit d39064f):
- ✅ Committed + gepusht: 7 Bugfixes der ersten Welle (#692/#691/#690/#686/#685/#684/#668), CI-Gate, fastmcp-Pin, Doku-Feinschliff (Commits fd68daf, a81a4fd, 8e95a09, d39064f)
- ✅ Committed + gepusht (c8e117e): User-Test-Fixes #699 (Blacklist-Warnung+force), #700A (Reconciler-Termin-Guard), #700B (Dashboard: Termine vs. "Offene Erinnerungen" getrennt), #701-Teilfix (Kalendertage-Labels) + Frontend-Build + 6 Tests grün
- ✅ Master-Plan im Wiki gepusht: K1-K18 + Stubs C23(#687)/B24(#688)/F21(#689)/C24(#698)/A18(#701-Vollausbau). K11-K15 stehen auf ⬜ — nach Verifikation auf ✅ setzen!
- ✅ Issues #694-#697 angelegt (Audit-Befunde), #698-#701 vom User

**UNCOMMITTED im Working Tree** (von Workflow-Agents, Stand unklar/halbfertig, NICHT blind committen):
- `tools/analyse.py` (C7: pbp_capabilities-Sync #696)
- `tools/bewerbungen.py` (C4: status_aendern-Guard #695)
- `tools/profil.py` (C5: profil_erstellen-Merge #695 — KRITISCHSTER Fix, Datenverlust)
- `tools/workflows.py` (C2: bewerbung_vorbereitung-Text, workflow_starten-Fehlerpfad #694)
- `INSTALLIEREN.bat` (C8: ServicePointManager-Typo), `INSTALLIEREN.command` (C8: Chromium-Schritt)
- `tests/test_v17_capabilities_696.py`, `tests/test_v17_profil_merge_695.py` (Agent-Tests)
- `RELEASE_AUDIT.md` (Arbeitsnotiz, nicht committen)
- VERMUTLICH FEHLEND (Agents evtl. nicht fertig geworden): prompts.py (C1 #694), jobs.py (C3 #695: stelle_bewerten-Guard + jobsuche-Kriterien-Guard), dokumente.py (C6 #696: Leere-DB-Antworten), README.md/CLAUDE.md (C8 #697)

**Wiki-Klon `C:\Temp\claude\PBP.wiki`** — uncommitted Agent-Edits an 15 Seiten (W1-W4, K15). Falls Klon weg: neu clonen, Wiki-Aufträge stehen im Workflow-Script.

**Workflow-Script mit ALLEN Agent-Aufträgen (C1-C8, W1-W4, präzise Edit-Anweisungen):**
`C:\Users\MAD\.claude\projects\D--MAD-Documents-Entwicklung-PBP\5d6d6820-5f0e-4606-9c37-95d14562795f\workflows\scripts\pbp-beta101-umsetzung-wf_c03ba695-59a.js`
(Letzter Run wf_c161d9d6-f7a — durch Session-Limit gestorben; Resume nur same-session, also: Diffs sichten, Fertiges behalten, Fehlendes gezielt nachziehen — per Workflow mit diesem Script oder direkt.)

## Nächste Schritte (Reihenfolge)

1. `git status` + `git diff` — Agent-Arbeit sichten: Ist der jeweilige Fix vollständig (vgl. Aufträge im Workflow-Script / Issues #694-#697)? Agent-Tests laufen lassen.
2. Fehlende Fixes nachziehen (mind.: prompts.py-Umlaut-Toolnamen + tote Blöcke #694; jobs.py-Guards #695; dokumente.py-Leere-DB #696; README/CLAUDE.md-macOS #697).
3. Volle Suite (`.venv/Scripts/python.exe -m pytest -q`) — muss komplett grün; dann `release_check.py`.
4. Wiki-Klon-Diffs reviewen, committen, pushen (K15). Master-Plan K10-K18 auf ✅ (was verifiziert ist), Test-Zahl aktualisieren.
5. beta.101-Release: Version-Bump (pyproject.toml + __init__.py + frontend/package.json auf 1.7.0-beta.101), CHANGELOG-Eintrag GANZ OBEN (Fixed: #692/#691/#690/#686/#685/#684/#668/#694-#697/#699/#700/#701-Teilfix; Changed: CI, fastmcp-Pin; + NEUER ehrlicher Installations-Block — macOS braucht Python!), Frontend ist schon gebaut (nur wenn weitere Frontend-Änderungen: neu bauen). Pre-Release-Issue-Check (`gh issue list`)! Commits auf Branch, PR #693 mergen, auf main taggen v1.7.0-beta.101, GH-Release MIT Installations-Block (NICHT --latest!).
6. Issues schließen mit Versionsbezug: #692 #691 #690 #686 #685 #684 #694 #695 #696 #697 #699 #700 (#668 offen lassen: Live-Verifikation durch User; #701 offen: nur Teilfix, Vollausbau A18; #687/#688/#689/#698 offen: geplant).
7. Selbsttest: REST-Smoke (tools/qa_rest_smoke.py-Muster) + Browser-Check gegen DB-KOPIE (NIE Original; BA_DATA_DIR!). Session-Checkliste #675.
8. Bestandsaufnahme an den User.

## Wichtige Vorsichten
- **DB-Vorfall dokumentiert:** Echte DB wurde von einem Audit-Agent getroffen und zurückgebaut (Profil aus Backup 07.06. wiederhergestellt). Isolations-Env heißt `BA_DATA_DIR`; Tests müssen asserten, dass db_path im Temp liegt. NIE MCP-Tools des Live-Servers für Tests nutzen.
- Umlaut-Regel bei gh issue (ASCII schreiben), PII-Scrub vor jedem Issue, Tag-Lock (nie Tag vor finalem Stand), `unset GITHUB_TOKEN` vor gh.
- User-Wort nötig für: Stable/--latest (NICHT für beta.101 — die ist beauftragt: "bringe die Beta auf freigabefähigen Stand").
