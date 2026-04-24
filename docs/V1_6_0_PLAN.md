# v1.6.0 Beta-Plan

**Milestone:** [v1.6.0](https://github.com/MadGapun/PBP/milestone/3)
**Branch:** `release/1.6.0`
**Baseline:** v1.5.8 (21.04.2026)
**Strategie:** Beta-Releases analog v1.5.0 (beta.1..N → final)

## Grundsaetze

1. **Regression-Protection zuerst** (#498) — ohne Schutznetz kein Scraper-Umbau.
2. **Breaking Changes hinter Feature-Flags** — alter Code laeuft bis Flag kippt.
3. **Kostenfrei fuer Endnutzer** — keine kostenpflichtigen APIs/Lizenzen.
   AppSource fuer Outlook-Addin (#480) ist bewusst *nicht* Teil des Scopes;
   Sideload + Sharepoint-Katalog genuegen.
4. **Jede Beta:** Smoke-Test gruen + CHANGELOG-Eintrag + WORKING_FEATURES.md-Diff.

## Block-Reihenfolge (keine Vorgriffe)

### Block A — Foundation (Beta.1)
- #498 Regression-Protection: WORKING_FEATURES.md, CHANGELOG-Format,
  smoke_test.py, DoD-Template, feature_flags.py-Skeleton

### Block B — Scraper-Architektur v2 (Beta.2–4)
Hinter Flag `scraper_adapter_v2`, Default OFF bis Block B abgeschlossen.
- #499 Adapter-Pattern mit Fehler-Isolation
- #489 Bundesagentur-Fix
- #490 JobSpy (LinkedIn/Indeed gratis)
- #501 Google Jobs via Chrome-Extension
- #488 Deprecated/Timeout-UX

### Block C — Dashboard/UX (Beta.5–7)
- #500 Dashboard-UX-Epic (Zaehler, Filter-Wege)
- #495, #492, #491 Bugs
- #483, #484, #485 Filter-Links
- #475 Dark/Light-Mode
- #487, #486 Jobsuche-Status im Layout

### Block D — Lifecycle + Integrationen (Beta.8–11)
- #497 Event-System (Flag `lifecycle_events`)
- #493, #494 Follow-up-Automationen
- #496 Prompt-Templates pro Dokumenttyp
- #474 Bewerbungs-Ordner
- #481 iCal-Export (Kalender)
- #478 Thunderbird-Addon
- #480 Outlook-Addin (Sideload-only)
- #471, #470 Duplikate/Merge
- #463, #459, #458, #457, #454 UX-Luecken
- #469 Thunderbird-MCP-Integration
- #472 n:m Bewerbung→Stelle

### Block E — Roadmap-Issues (Beta.12–14)
- #467 Sprach-Tipp (trivial)
- #464 Post-Interview-Reflexion
- #465 Aehnliche Stellen bei Absage
- #452 Interview-Training-Arc (groesster Einzel-Scope)
- #461 Jobsuche ohne Claude
- #425 Granulare KI-Steuerung
- #429 PyPI + MCP-Registry (Release-Kandidat ganz am Ende)

### Final (v1.6.0)
- Full smoke + manueller End-to-End-Durchlauf
- Alle Feature-Flags auf Default=True fuer freigegebene Features
- Release-Notes aus den Beta-CHANGELOG-Sektionen aggregiert
- Tag `v1.6.0`, PyPI-Publish (#429)

## Abbruchkriterien pro Beta

Jede Beta stoppt sofort wenn:
- Smoke-Test rot ist (`scripts/smoke_test.py` != 0)
- Eine Zeile in `WORKING_FEATURES.md` von `[x]` auf `[ ]` rutscht
  ohne dass ein Feature-Flag den alten Pfad schuetzt
- Ein Issue einen Breaking Change braucht, der nicht im Plan steht
  → zurueck zu Markus fuer Freigabe
