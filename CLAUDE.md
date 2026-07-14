# PBP — Claude-Code-Memory

Persoenliches Bewerbungs-Portal (PBP). MCP-Server (Python/FastMCP 3.x) +
React-Frontend + SQLite. **v1.7.7** ist Stable (`--latest`) — v1.7.0 wurde am
2026-06-18 aus beta.108 promotet (User-Wort); v1.7.1 #737-Hotfix, v1.7.2
Windows-Deinstaller (#739), v1.7.3 Matching-Haertung + `projekte_anzeigen`
+ Schema-Parity (#743/#741/#738), v1.7.4 die **Einsteiger-Welle** (G17
gefuehrte Kette #744, F24 Ollama-Vorschlaege #745, H17 Melde-Hilfe #746
inkl. Mail-Weg PBP-Service@Elwosa.de, B13-Teil-1 #747), v1.7.5
(2026-07-03) **Fuehrung & Pflege**: G11 Onboarding-Hints im Frontend
(#652), Probes adapter-konsistent (#748), Umlaut-Restaurierung
`profil_umlaute_reparieren` (A20/#742), v1.7.6 (2026-07-03)
**Alltags-Fuehrung** (#706/#707/#689/#749), v1.7.7 (2026-07-14)
**Scoring-Fairness & Praxis-Funde** vom 13.07. (#750/#752-#757).
**Leitlinie des Users: Benutzerfuehrung ist oberste Prioritaet** — jeder
Flow fuehrt zum naechsten logischen Schritt; Melde-Kultur gehoert zur
DNA. v1.6.10 bleibt als aelterer Release verfuegbar. **v1.8-Beta-Linie
eroeffnet (Planungswelle 2026-07-14, User-Wort):** Architektur-Entwurf
D1–D5 (Plugins = EXTERNE Prozesse gegen versionierte Ingest-API, kein
Code-Loading; Komponenten ≠ Plugins; Pairing statt Discovery) + Beta-
Fahrplan in Plan-Roadmap-v18; Beta-Exit-Kriterium v1.8 im Master-Plan.
**beta.0 = I10 Komponenten-Framework (#751) + E19 Auto-OCR (#750-T2,
Schema v49)**, beta.1 = J1 Ingest-API v1 (#504), beta.2 = J2 Thunderbird
+ J4.1 ics, beta.3 = J5 Newsletter. Betas sind GitHub-Prereleases,
`--latest` bleibt v1.7.7; Hotfix-Pfad: Branch vom Tag v1.7.7. Weitere
v1.8-Themen: Branchen-Radar #718/#735 (Kern-Welle), Referenzen #740/D24,
PII-Altbestand A21/#758.

## Stand 2026-07-14 (v1.7.7) — Scoring-Fairness & Praxis-Funde

**Schema:** v48 (unveraendert). **Tests:** 1952 passed, 1 skipped.
**MCP-Tools:** 181 (+`firma_kontext` #753, +`dokument_text_setzen` #750),
**Prompts:** 25.

Sechs Funde aus einem realen Bewerbungs-Nachmittag (13.07.): (1)
**C25/#755** — MINUS-Keywords matchen strikt (`_strict_keyword_match`:
Wortgrenzen + zusammenhaengende Phrase, keine Synonym-Expansion; betrifft
`calculate_score` UND `fit_analyse`). (2) **F25/#754+#757** —
Wiedergaenger rollen-sensitiv: Fach-Domaene traegt allein (#671-Semantik
bleibt), ohne Fach-Signal zaehlt nur dieselbe Rollen-Familie
(`_role_families` in `services/wiedergaenger.py`); NEU
`firmen_historie()` als neutrale Einordnung (Gruende gelten je STELLE).
(3) **F26/#756** — Beschreibung-zuerst: `stellen_auto_aussortieren`
ueberspringt beschreibungslose Stellen (< 50 Zeichen) statt die LLM auf
Titel-Basis raten zu lassen (`uebersprungen_ohne_beschreibung`);
`stellen_anzeigen` liefert `score_status='unbewertet'` + Summenzeile;
Frontend-Badge „Unbewertet" auch bei Score 0 (JobsPage). (4) **F27/#752**
— Elwosa: `{monat}`-Platzhalter, Guard gegen Linien die mit falschem
Monat BEGINNEN, `paused_until` nur bei aktiver Pause. (5) **H18/#753** —
`firma_kontext(firmenname)` + PFLICHT-Regel (Server-Instructions,
willkommen, CLAUDE.md-Sektion unten). (6) **E18/#750-T1** —
`dokument_text_setzen` mit Provenienz-Pflicht (E19 Auto-OCR bleibt v1.8,
braucht I10/#751).

## Stand 2026-07-03 (v1.7.6) — Alltags-Fuehrung

**Schema:** v48 (unveraendert). **Tests:** 1911 passed, 1 skipped.
**MCP-Tools:** 179, **Prompts:** 25.

Kernpunkte: (1) **G16/#706** — Interview-Vorbereitung-Button in
Bewerbungs-Uebersicht + Timeline (Status interview/zweitgespraech):
kopiert vorbefuellte Anleitung (Stelle+Firma) in die Zwischenablage;
`/api/workflow-prompt/{name}` nimmt jetzt signatur-geprueft Query-Args.
(2) **H15/#707** — Notizen-Pflege: Hint `g11_notizen_pflegen` (Profil-Tab),
Feld-Hilfetext, Prompt-Guidance in ersterfassung (Regel 6b) + willkommen.
(3) **F21/#689 komplett** — Lernprotokoll stummschalten je Eintrag +
`POST /api/learning/insights/reset` (harter Reset). (4) **G18/#749** —
Verbindungsstatus-Streifen auf dem Welcome-Screen (gruen/amber mit
3-Schritte-Anleitung; User-Leitlinie: ab Installation alles einfach).
(5) Plan-Hygiene: C24/#698 war seit beta.107 fertig.

## Stand 2026-07-03 (v1.7.5) — Fuehrung & Pflege

**Schema:** v48 (unveraendert). **Tests:** 1901 passed, 1 skipped. **MCP-Tools:** 179
(+`profil_umlaute_reparieren`, #742), **Prompts:** 25.

Kernpunkte: (1) **G11/#652** — Onboarding-Hints endlich sichtbar: REST
`GET /api/onboarding/hints?tab=` + `DELETE .../{id}`,
`OnboardingHintBanner.jsx` auf 4 Tabs, neuer Hint
`g11_erste_suche_starten` (Profil ohne Suchbegriffe → naechster Schritt).
(2) **B13.4/#748** — Prinzip Probe==Adapter: `_PROBE_EXTRA_HEADERS`
(bundesagentur X-API-Key+UA), workable v1-Widget-API, personio
Adapter-Firma. (3) **A20/#742** — `profil_umlaute_reparieren`
(kuratierte ~150-Wort-Positivliste in `tools/profil.py`, Dry-Run-Default,
Backup-Pflicht, ss→ß nie, technologies nie; ungemappte Woerter als
Kuratierungs-Kandidaten).

## Stand 2026-07-03 (v1.7.4) — Einsteiger-Welle

**Schema:** v48 (unveraendert). **Tests:** 1871 passed, 1 skipped.
**MCP-Tools:** 178, **Prompts:** 25 (+`problem_melden`).

Kernpunkte: (1) **G17/#744** — Ersterfassungs-Wizard hat Phase 5
(keyword_vorschlaege → suchkriterien_setzen → Smart-Default-Quellen
`bundesagentur/arbeitnow/jobspy_indeed` → jobsuche_starten →
Treffer-Vorschau); `keyword_vorschlaege` liefert bei leerem Bestand
Profil-Vorschlaege statt Sackgasse; `jobsuche_starten` uebernimmt beim
ersten expliziten Lauf die Quellen als aktiv; `zero_treffer_diagnose`
erklaert 0-Treffer-Ergebnisse; Welcome-Screen: CV-Upload prominent.
(2) **F24/#745** — TaskKinds EXTRACT_KEYWORDS/SUGGEST_JOB_TITLES,
`jobtitel_vorschlagen()` ohne Argumente generiert via Ollama
(`build_profil_kurztext` in llm_service, ohne PII). (3) **H17/#746** —
Prompt `problem_melden`: erst Sofortloesung, dann PII-gescrubbter Report;
GitHub ODER Mail an PBP-Service@Elwosa.de. Frontend: Defekt-Badges und
Ollama-Download-Hinweis existierten schon (SourceSelectionList,
SettingsPage) — vor Frontend-Arbeit immer erst pruefen, was da ist.

## Stand 2026-07-02 (v1.7.3) — Hotfix-Session

**Schema:** v48 (unveraendert, kein Bump — Safety-Net statt Migration).
**Tests:** 1837 passed, 1 skipped.
**MCP-Tools:** 178 (+`projekte_anzeigen`, #741), **Prompts:** 24.

Kernpunkte: (1) **E17/#743** — beide Auto-Matcher gehaertet: Archiv-Status
(abgelehnt/zurueckgezogen/abgelaufen) wird nie mehr auto-verknuepft,
`auto_assign_document`-Schwelle 0.7→0.9, Ambiguitaets-Check + Vermittler-
Domain-Liste (`RECRUITER_DOMAIN_KEYWORDS` in `email_service.py`),
`achtung`-Warnung im Analyse-Plan. (2) **A19/#738** — Schema-Parity-Tests
(`tests/test_schema_parity_738.py`, Doppel-Migrations-Trick + v31-Vergleich);
der Test fand sofort die #737-RESTLUECKE: v1.6.x-SCHEMA_SQL hatte kein
`is_imported`, Fresh-Install-Upgrader crashten weiter im Statistik-Tab →
idempotentes Safety-Net in `initialize()`. Die #705-Fixture ist jetzt
originalgetreu zum echten v1.6.10-Schema (aus Git-Historie verifiziert).
(3) **H16/#741** — `projekte_anzeigen(position_id='')` liefert STAR-Volltext
+ Projekt-IDs, `is_confidential` maskiert; Prompts rufen es vor dem
Formulieren auf.

## ⛔ QA-Isolations-Regel (HART, seit dem DB-Vorfall 2026-06-10)

Der Daten-Isolations-Env-Var heisst **`BA_DATA_DIR`** (NICHT PBP_DATA_DIR
— ein falscher Name faellt STILL auf die echte AppData-DB zurueck!).
Jedes QA-/Test-Skript und jede Test-Fixture MUSS nach dem DB-Oeffnen hart
asserten, dass `db.db_path` im Temp-Verzeichnis liegt:

```python
os.environ["BA_DATA_DIR"] = tmpdir
# ... importlib.reload(database); db = Database(); db.initialize()
assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
```

Hintergrund: Am 2026-06-10 traf ein QA-Lauf mit falschem Env-Var-Namen die
echte User-DB (Profil ueberschrieben — aus Backup wiederhergestellt, alle
Aenderungen inventarisiert und zurueckgebaut). NIEMALS MCP-Tools des
laufenden bewerbungs-assistent-Servers fuer Tests nutzen — die treffen
immer die echte DB. Subagenten bekommen diese Regel woertlich in den
Auftrag geschrieben.

## ⛔⛔ ZUERST LESEN: Master-Plan (Single Source of Truth)

**Der Master-Plan ist das verbindliche Steuerungsdokument fuer PBP. Er
liegt im GitHub-Wiki, NICHT im Code-Repo:**

> **https://github.com/MadGapun/PBP/wiki/Master-Plan**

Begleitseiten:
- Risiken / Trade-offs / Reihenfolge: https://github.com/MadGapun/PBP/wiki/Master-Plan-Optimierung
- 9 Sub-Plaene auf Issue-Ebene: `Plan-{Cluster}` (A–J) im selben Wiki

**Pflicht vor JEDER Aenderung (Code, Schema, Tools, Doku, Issues):**
1. Den Master-Plan oeffnen und lesen — er ist ein lebendiges Dokument und
   aendert sich staendig. NIE aus dem Gedaechtnis arbeiten.
2. Pruefen, ob das Vorhaben dort schon als Position gefuehrt wird
   (Cluster A–J). Wenn ja: Status und Abhaengigkeiten beachten.
3. Wenn nein: erst einen Plan-Eintrag (⬜ Stub) ergaenzen, dann weiter
   nach dem Master-Plan-First-Workflow unten.

**Das Wiki ist ein eigenes Git-Repo** (`PBP.wiki.git`). Edits laufen
NICHT ueber die Contents-API des Code-Repos, sondern per lokalem Clone +
Push (Desktop Commander). Der Master-Plan darf nur bewusst und
nachvollziehbar geaendert werden — vor einem Wiki-Edit den aktuellen
Stand frisch ziehen (Pull), nicht auf eine Cache-Version verlassen.

**⛔ Wiki-Clone-Regeln (HART, seit dem Vorfall 2026-07-14):** Der Clone
liegt in `D:\MAD\Documents\Entwicklung\PBP.wiki` — NIEMALS in Temp-/
Scratchpad-Verzeichnissen (die werden zwischen Sessions teilweise
aufgeraeumt; ein `git add -A` committet die fehlenden Dateien dann als
LOESCHUNGEN — am 2026-07-14 wurden so 34 Wiki-Seiten gepusht-geloescht
und per Revert wiederhergestellt). Vor JEDEM Wiki-Commit den
Vollstaendigkeits-Guard laufen lassen:
`test $(ls *.md | wc -l) -ge 39 && git add -A ...` (Zahl bei neuen
Seiten nachziehen). Ausserdem: `git pull --rebase` und Commit-Kette nie
so verketten, dass der Commit auch bei fehlgeschlagenem Pull/Edit laeuft.

## ⛔ Session-Abschluss-Checkliste (Definition of Done) — Dauer-Issue #675

**Am Ende JEDER Arbeitssession diese Punkte durchgehen.** Die maszgebliche,
immer offene Version steht in **Issue #675** (nicht schliessen). Diese
Kopie hier ist die schnell-praesente Fassung — bei Aenderungen beide
synchron halten.

**Selbst-erweiternd:** Diese Checkliste ist lebendig. Taucht eine neue
wiederkehrende Abschluss-Pflicht auf, wird sie als Punkt aufgenommen, nicht
nur einmal abgehakt. **Pruefung und Erweiterung macht Claude Code** (tieferes
Repo-/Code-Verstaendnis). Die MCP-Chat-Instanz arbeitet die Liste ab und
meldet Erweiterungs-Kandidaten, schreibt die Liste aber nicht selbst fort,
sondern reicht sie an Claude Code weiter. Liste und Issue #675 synchron halten.

1. **Master-Plan pruefen, lesen, ggf. aktualisieren** —
   https://github.com/MadGapun/PBP/wiki/Master-Plan. Neue/geaenderte
   Themen als Position aufnehmen (⬜) oder Status nachziehen (🟨/✅).
2. **Wiki aktualisieren** — betroffene Seiten nachziehen (`Plan-{Cluster}`,
   Tab-Seiten, MCP-Tools, FAQ). Clone + Push, vorher Pull.
3. **README aktualisieren** — Repo-Root-README pruefen (Tool-Count,
   Feature-Liste, Version) und bei Bedarf nachziehen.
4. **Issues dokumentieren / abschliessen** — adressierte Issues mit
   Ergebnis + Versionsbezug kommentieren und schliessen; neue Erkenntnisse
   als neue Issues anlegen (PII-Scrub).
5. **GitHub-MCP nutzen** — Issue-Operationen laufen ueber den GitHub-MCP.
   Umlaut-Regel: nach `create` immer `update` mit korrekten Umlauten.
6. **PBP-MCP-Luecken als Issue dokumentieren** — alles, was ueber den
   PBP-MCP funktionieren MUESSTE aber nicht funktioniert (fehlende/kaputte
   Tools, Felder die ins Leere schreiben, Tools die per tool_search nicht
   ladbar sind, jeder Direkt-SQL-Workaround), wird als Issue erfasst. Ziel:
   MCP-Layer bleibt langfristig die einzige Schnittstelle (Anti-DB-Bypass,
   #514).
7. **PII-Sweep ueber neue Artefakte** (seit 2026-07-14) — der Issue-Scrub
   gilt sinngemaess fuer ALLES Oeffentliche: vor Commit/Wiki-Push neue
   Tests, Docstrings, CHANGELOG-Eintraege und Plan-Seiten auf reale
   Firmen aus der Bewerbungshistorie und Personen-Namen pruefen
   (`grep -rni`; Namensmuster in `scripts/scrub_pii.py`). Reale Faelle
   als „Praxis-Fall [Datum]" mit fiktiver Firma dokumentieren.
   Hintergrund: 2026-07-14 standen reale Firmennamen in neuen
   v1.7.7-Tests/Wiki-Stubs und der User-Vorname im Wiki-Altbestand —
   vor dem Release bereinigt.
8. **Checkliste selbst pruefen (Claude Code)** — ist eine neue wiederkehrende
   Abschluss-Pflicht entstanden? Dann diese Liste (hier + #675) erweitern.

## Stand 2026-06-02 (beta.90) — QA-Selbsttest + Doku-Sync

**Schema:** v45 (v44 `documents.lifecycle`; v45 `tasks` +
`dismiss_reasons.is_active` + `search_criteria.keywords_minus`).
**Tests:** 1611 passed, 1 skipped (1612 collected).
**MCP-Tools:** 171 (historischer Stand beta.90 — aktuell 178, siehe oben),
**Prompts:** 24.
**Quellen:** 34 (~6 produktiv).

Selbsttest dieser Session (autonomer 8h-Lauf): volle Suite gruen +
saubere Migration v43->v45 auf einer **Kopie** der Real-DB
(`C:\Temp\claude\qa`, Original unter AppData NIE angefasst); 10/10
REST-Endpoints der beta.78-90-Welle via FastAPI-TestClient OK
(`tools/qa_rest_smoke.py`). Befunde + Drift-Tabelle:
`docs/QA-Audit-beta90.md`. Das Wiki war auf beta.74 eingefroren (152
Tools / 23 Prompts / Schema v42) und wurde Wiki-weit nachgezogen, inkl.
neuer User-Doku fuer Lifecycle (#657/#658), Routing (#643), Tasks
(#666), Ablehnungsgruende-Editor (#663), Minus-Keywords (#667),
Wiedergaenger (#671), `stelle_reaktivieren` (#664).

**Tool-Module (Code-Wahrheit, 11 Module = 171):** bewerbungen 30,
analyse 27, jobs 26, dokumente 22, profil 20, kontakte 14, suche 12,
export_tools 7, elwosa 6, tasks 4, workflows 3. `pbp_*`-Diagnose-Tools
liegen im `analyse`-Modul.

## ⛔ Master-Plan-First (HART, seit 2026-06-01)

**Vor JEDEM Code-Change MUSS ein Master-Plan-Eintrag existieren** —
mindestens als ⬜ Stub mit Issue-Verweis. Sonst keine Implementierung.
Die Master-Plan-Adresse und die Pflicht zum Vorab-Lesen stehen oben im
Abschnitt "ZUERST LESEN".

- **Wiki:** [Master-Plan](https://github.com/MadGapun/PBP/wiki/Master-Plan)
  (Cluster-Ebene A–J) + [Master-Plan-Optimierung](https://github.com/MadGapun/PBP/wiki/Master-Plan-Optimierung)
  (Risiken/Trade-offs) + 9 Sub-Plaene `Plan-{Cluster}.md` mit Issue-Detail
- **Reihenfolge:** (1) Plan-Eintrag aufnehmen → (2) Issue erstellen (mit
  PII-Scrub) → (3) Code → (4) Tests → (5) Wiki-Eintrag → (6) Plan auf ✅
  setzen → (7) Release
- **Akzeptanzkriterium:** ✅ nur wenn **alle drei** zutreffen: Code im
  Repo + Tests gruen + Wiki-Eintrag vorhanden. Sonst bleibt 🟨 oder ⬜.
- **Ausnahmen:** keine. Auch nicht fuer "schnelle Hotfixes" — die kommen
  als ⬜-Eintrag in den Plan, werden umgesetzt, und derselbe Commit
  setzt sie auf ✅ und schiebt den Wiki-Stub nach.

Beispiel-Workflow fuer ein neues Feature:

```
1. Master-Plan-Eintrag: "B17 — Neue Quelle XYZ scrapen (#999)"  ⬜
2. Issue #999 anlegen (mit PII-Scrub)
3. Code in src/bewerbungs_assistent/job_scraper/xyz.py
4. Tests in tests/test_xyz.py — gruen
5. Wiki-Eintrag (Jobportale ergaenzen, ggf. eigene Seite)
6. Master-Plan: B17 auf ✅, Plan-Jobsuche.md auf Issue-Level erweitern
7. Release-Workflow (Version-Bump, CHANGELOG, Commit, Tag, GH-Release)
```

**Bei Verstoss:** der Code-Change ist nicht abgeschlossen. Im naechsten
Commit nachholen.

## Stand 2026-05-09 (User-Test-Findings beta.41)

**Schema:** v42 (zuletzt `contact_categories` aus #607 in beta.39).
**Tests:** 1147 grün (+28 neue für #614 + #612).
**MCP-Tools:** 138, **Prompts:** 23.
**Quellen:** 33+.

### beta.41 — #614 + #612 (User-Test-Findings vom 8. Mai)

- **#614 Elwosa-Varianz** — Welt-Trigger-Pools auf 4-8 Linien ausgebaut
  (vorher 1-3); Markup-Support `**bold**` und `[link:pause:N|label]`;
  `pick_line()` mit Same-Day-Anti-Repeat (zwei Filter-Schichten:
  not-7-days, dann not-today; Repeat erst wenn Pool fuer den Tag durch).
- **#612 Settings-Verdrahtung** — `tonfall_modus` jetzt funktional in
  `can_post_class()`: `aus`→alles blockt, `sachlich`→idle/world/tip/easter
  blockt, `minimal`→Hard-Cap 1/Tag. Neuer Endpoint
  `POST /api/elwosa/user-action` + `speak_settings_reflection()` Helper
  + `SETTINGS_REFLECTION_LINES` Pool. Frontend feuert Hook auf jede
  Settings-Aenderung (1 Reflektion pro Patch via `pickReflectionTarget`).

### Stand 2026-05-07 (Sprint-Tag mit 12 Releases)

**Schema:** v41 — `elwosa_messages` + `elwosa_pending_lines` (#599).
**Tests:** 1057 grün.
**MCP-Tools:** 133, **Prompts:** 23.
**Quellen:** 33+ (10 neue heute aus #590).

### Heute geschlossene Issues

- **#594** Lern-System (5 Stufen) — beta.26-30:
  Foundation, Aggregation, LLM-Pattern-Analyse + Korrektur-Loop,
  Adaptive UI, Telemetrie-Sharing (opt-in, wochenweise)
- **#595** Stellen-Detail-Bug bei is_active=0 — beta.31
- **#596** Keyword-Analyse 3 Bugs (Eigenname, ???-Zeile, PDM) — beta.31
- **#597** Dokumente pro Bewerbung im Bericht — beta.31
- **#598** Quellen-Aktivität Volumen (statt nur letzte Treffer) — beta.31
- **#588** Stellenbeschreibung sauber von Notizen trennen — beta.32
- **#564** Portal-spezifische Such-Profile (LinkedIn-Lessons) — beta.32
- **#590** Quellen-Strategie (gross) — beta.33-36:
  Auto-Reactivate, 10 neue Quellen-Adapter, Profile-Detection,
  9 Cluster, Recommendations-UI
- **#599** Elwosa — beta.37:
  Live-Statusanzeige der lokalen AI in der linken Sidebar mit eigener
  Persoenlichkeit (geschlechtsfrei, britisch ironisch). 6 MCP-Tools
  als Bridge fuer Claude, 5 Bridge-Prompts, ~140 Linien kuratiert,
  Sprach-DNA-Validator, Settings-Section im Lokale-KI-Tab.

### Aktuelle Architektur-Highlights

- **`services/profile_classifier.py`** — heuristische Profil-Erkennung
  in 9 Cluster (student/service/trade/tech_junior/tech_senior/
  engineering_senior/freelance/executive/mixed) + Quellen-Empfehlung
  pro Cluster
- **`services/llm_service.py`** — TaskKind-Routing-Table (Local/Claude/Manual)
  mit den Tasks: classify_document, extract_skills, match_job_to_skills,
  classify_email, analyze_user_patterns, generate_cover_letter, ...
- **`scraper_health` mit Auto-Reactivate** — Backoff 24h/48h/72h/168h
  bei silent failures, automatische Reaktivierung bei OK-Run
- **Activity-Tracking + LLM-Insights** — `user_activity_events` +
  `learning_insights` Tabellen, AdaptiveHintBanner pro Page (#594)

### Nicht im Sprint, aber wichtig zu wissen

- **Plugin-Plattform** (#504) ist explizit User-Vorgabe fuer v1.8 —
  Mail-Integrationen (#481/#480/#478) und Newsletter-Ingest (#525)
  sollen als Plug-Ins kommen, nicht als Kern-Code.
- **Quellen-Rotation (#590-C.4)** wurde aus #590 herausgehalten —
  betrifft den job_runner-Orchestrator, eigenes Issue empfohlen.

### Elwosa (#599) — shipped in beta.37

Live-Statusanzeige der lokalen AI in der linken Sidebar. Eigene Persoenlichkeit
(geschlechtsfrei, britisch ironisch, lakonisch). Kommentiert was die lokale AI
gerade tut, gibt Tipps zu Claude-Workflows und PBP-Features.

**Wichtige Files:**
- `docs/elwosa-character.md` — Charakter-Briefing + Linien-Pool (~140 Linien)
- `src/bewerbungs_assistent/services/elwosa_lines.py` — Linien-Pool im Code
- `src/bewerbungs_assistent/services/elwosa.py` — Trigger-Engine + Validator
- `src/bewerbungs_assistent/tools/elwosa.py` — 6 MCP-Tools (Bridge fuer Claude)

**Pflege-Regel bei neuen Linien:**
- Beide Files synchron halten (Doku + `elwosa_lines.py`)
- Sprach-DNA: keine Ausrufezeichen, keine Emojis, kein `Ihre/Ihnen`
- `Sie` als 3.-Person-Pronomen (Firma/Recruiter) ist erlaubt — siehe
  Sektion 3 in `docs/elwosa-character.md`
- Lakonische Untertreibung, max 280 Zeichen pro Linie
- Tonfall-Waechter-Test (`test_all_pool_lines_pass_validator`) bei
  jeder Aenderung gruen halten

**Frequenz-Logik:**
- **Status-Trigger UNBEGRENZT** (mail_received, auto_dismiss_ran,
  status_change, ...) — Elwosa schweigt nicht wenn die AI arbeitet
- Idle/Welt/Tipp werden nach Frequenz-Slider gedrosselt
  (ruhig=2 idle/Tag, standard=4, aktiv=6)
- Cooldown: 90s zwischen zwei beliebigen Nachrichten

**MCP-Bridge:** User kommunizieren NICHT direkt mit Elwosa — Claude
ist der Uebersetzer. 6 Tools: `elwosa_lesen`, `elwosa_schreiben` (Tonfall
validiert!), `elwosa_pause`, `elwosa_tonfall`, `elwosa_linie_vorschlagen`,
`elwosa_status`. Plus 5 Bridge-Prompts in `prompts.py`.

## Issue-Erstellung — DSGVO-Pflicht (kritisch)

**KEIN Issue darf Personen-Namen, Firmen-Namen oder Kontaktdaten enthalten.**
Issues sind oeffentlich einsehbar, ein Verstoss ist DSGVO-relevant fuer
den User UND die Dritten. Auch in Reproduktions-Beispielen, Bug-
Beschreibungen, Test-Daten.

**Vor jedem `gh issue create` IMMER durch den Anonymisierer laufen lassen:**

```bash
python scripts/scrub_pii.py --check < /tmp/issue_body.md
# exit 0 → sauber, kann raus
# exit 1 → Treffer aufgelistet, vorher anonymisieren
```

Oder programmatisch:

```python
from scripts.scrub_pii import scrub_text, find_pii
hits = find_pii(body)
if hits:
    body = scrub_text(body)  # wendet Replace-Mapping an
```

**Replace-Konvention:**
- Personen-Namen → `<USER>` (User selbst) oder `<PERSON>` (Dritte)
- Konkrete Firmen → `<FIRMA>` (alle gleich, nicht durchnummeriert)
- E-Mail-Adressen (echt) → `<email-anonymisiert>`
- Telefonnummern (echt) → `<telefon>`
- Konkrete Stellen-IDs / Hashes → bleiben erlaubt (interne IDs ohne externe Bedeutung)

**Was bleibt erlaubt im Issue:**
- GitHub-Username `MadGapun` (oeffentlicher Repo-Owner)
- Generische Branchen ("Maschinenbau", "Tech-Senior")
- Test-Mails wie `bewerbung@firma.de`, `test@example.com`
- DAX/Branchenindizes ohne konkrete Firma

**Das gilt sowohl fuer Code-getriebene Issue-Creation (via `gh` CLI im
Code) als auch fuer Claude-Chat-getriebene Issue-Creation.**

Background: am 2026-05-10 wurden in 3 Sweep-Passes ~155 historische
Issue-Bodies + 9 Comments nachtraeglich anonymisiert. Das darf nicht
nochmal passieren — siehe `scripts/scrub_pii.py` Header.

**WICHTIG zur Edit-History:** GitHub zeigt fuer Issue-Bodies eine
`edited`-Markierung mit Zugriff auf die Vorgaenger-Versionen — auch
fuer non-Admins in oeffentlichen Repos. Anonymisierung der CURRENT
Version macht die Original-PII NICHT ungeschehen. Fuer wirklich
sensible Faelle ist Issue-LOESCHUNG (via GraphQL `deleteIssue`)
notwendig, was aber:
- Issue-Nummer unwiederbringlich verbrennt (#602 → wird nie wieder vergeben)
- alle Comments mit-loescht
- Cross-References im CHANGELOG / Code zu Dead-Links macht

Bei Zweifel: Issue-Loeschung ist die einzige sichere Option.

**Praeventiv:** vor JEDEM `gh issue create` (sowohl in Code als auch
Claude-Chat) den Scrubber laufen lassen. So entsteht das Problem
gar nicht erst.

## Release-Workflow (Pflicht-Checkliste)

Bevor ein neuer Release gebaut wird:

1. **Versionen bumpen** an drei Stellen:
   - `pyproject.toml`
   - `src/bewerbungs_assistent/__init__.py`
   - `frontend/package.json`
2. **Schema-Migration** ALTER-only (keine Daten-Migrationen). `SCHEMA_VERSION` in
   `database.py` hochziehen, neue Spalten in `_migrate` UND in `SCHEMA_SQL`
   (CREATE TABLE) ergaenzen.
3. **Tests gruen:** mindestens
   `pytest tests/test_v16*_*.py tests/test_database.py tests/test_mcp_registry.py`.
4. **Frontend rebuild:** `cd frontend && pnpm exec vite build`. Built-Assets unter
   `src/bewerbungs_assistent/static/dashboard/assets/` mit committen, alte
   Hash-Dateien `git rm`-en.
5. **CHANGELOG.md** erweitern: neuer Eintrag GANZ OBEN (vor v1.6.4),
   Sektionen Added/Changed/Fixed nach Keep-a-Changelog. Am ENDE des Eintrags
   IMMER die volle Installationsanleitung (siehe Pflicht-Block unten).
6. **Pre-Release-Pause:** vor `git commit` einmal kurz reflektieren (Risiko-
   Tabelle pro Issue, was kann brechen, was ist nur additiv) und nochmal
   testen. User hat das explizit eingefordert.
7. **⛔ Pre-Release-Issue-Check (HART, seit beta.82):** UNMITTELBAR
   bevor `gh release create` laeuft, IMMER die aktuelle Liste offener
   Issues auf GitHub abrufen (`gh issue list --state open --json
   number,title,createdAt,labels --limit 30`) und mit den in der Session
   adressierten Issues abgleichen. Wenn ein neues Issue dazwischen
   gekommen ist, das in diesen Release gehoert haette (Bug oder
   prompt-relevant), den Release zurueckhalten und das Issue noch
   mitnehmen. **Lieber 5 Minuten warten als einen Release nachschieben.**
   Hintergrund: am 2026-06-02 wurde beta.81 zu frueh veroeffentlicht;
   waehrend Tests + CHANGELOG liefen, kam #664 rein und musste in eine
   hektische beta.82 nachgezogen werden.
8. **Erst nach OK** committen, taggen, pushen, GH-Release erstellen.

## GitHub-Release-Notes — Pflicht-Block

**Jeder GitHub-Release MUSS die volle Installationsanleitung in den
Release-Notes selbst enthalten — NICHT nur als Link aufs CHANGELOG.**

Hintergrund: Viele Anwender klicken auf den Release, sehen "Source code
(zip/tar.gz)" und wissen nicht, was sie damit anfangen sollen. Die
Anleitung muss dort stehen, wo der User landet.

Template (am Ende der Release-Notes einfuegen, Versionsnummer ersetzen):

```markdown
---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein (siehe unten), **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-X.Y.Z.zip](https://github.com/MadGapun/PBP/archive/refs/tags/vX.Y.Z.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste → *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei → *„Oeffnen"* → nochmal *„Oeffnen"*

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
\`\`\`

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)
```

Derselbe Block gehoert auch ans Ende des CHANGELOG-Eintrags (Pflicht ab v1.6.4).

## GitHub CLI — Token-Falle

`gh` nutzt sonst den `GITHUB_TOKEN` aus dem Env mit eingeschraenkten Scopes.
Vor `gh`-Aufrufen IMMER `unset GITHUB_TOKEN` setzen, damit der Keyring-
Token mit Repo-Scope greift:

```bash
unset GITHUB_TOKEN; gh release create vX.Y.Z --title "..." --notes-file ... --latest
unset GITHUB_TOKEN; gh issue close 123 --comment "..."
```

## Tag-Lock-Falle (immutable releases)

GitHub Releases sind tag-gelocked: ein Release zu einem existierenden Tag
laesst sich NICHT mehr neu erstellen, nur editieren. v1.6.0/v1.6.1 wurden
durch das verbrannt. Konsequenzen:

- Vor `git tag` SICHER sein, dass alles drin ist (Frontend gebaut, Tests
  gruen, CHANGELOG aktuell).
- Bei kaputtem Release: NICHT taglock loesen — neue Patch-Version (vX.Y.Z+1)
  veroeffentlichen.
- **NIE `git push --tags`** (Fund v1.7.3-Release): das schiebt auch lokale
  Alt-Tags mit (v1.0.0, das verbrannte v1.6.0) und scheitert an den
  Repo-Rules. Immer gezielt pushen: `git push origin main vX.Y.Z`.

## Bericht-Designprinzip (v1.6.8)

**Kennzahlen, deren Datenbasis nicht zuverlaessig ist, kommen nicht in den
Bewerbungsbericht.** Lieber eine Sektion weglassen als eine irrefuehrende
Zahl drucken. Konkrete Faelle aus v1.6.8:

- „Aktive Filter-Arbeit" suggerierte „nur 1 wuerdig" — vergass dass viele
  Bewerbungen ueber Direct-Add aus dem Chat kommen, nicht ueber
  `stelle_bewerten('passt')`. Raus.
- „Geschaetzter Zeitaufwand" mit 30min/Bewerbung war Groessenordnungen
  unter Realwert (Stunden bis Tage pro Stelle inkl. Anschreiben-Iteration,
  Format-/Umlaut-Korrekturen, Interview-Vorbereitung). Raus.
- „Bewerbungs-Trichter" stufte aussortiert+beworben in sich
  widerspruechlich, weil Bewerbungen auch von ausserhalb des gesichteten
  Pools kommen. Raus.

Bevor eine neue Kennzahl in den Bericht eingebaut wird: pruefen, ob die
Datenbasis ALLE Pfade abdeckt, die zu dem Wert beitragen. Wenn nein:
weglassen.

## Anti-DB-Bypass-Pattern (#514)

Claude darf NICHT direkt in die SQLite schreiben. Alle Mutationen laufen
ueber MCP-Tools (`stelle_bewerten`, `stellen_bulk_bewerten`, `bewerbung_*`)
damit Lifecycle (Audit, dismiss_counts, Lerneffekt, Statistik) konsistent
durchlaeuft.

Server-Instructions in `server.py` machen das transparent. `pbp_capabilities`
und `pbp_grenze_melden` decken Edge-Cases ab.

## STRENG: Firmen-Status NIE aus dem Gedaechtnis (#753, seit v1.7.7)

Sobald ein Firmenname mit einer WERTUNG faellt — "kenne ich", "war
abgesagt", "laeuft noch", "da war ein Interview", auch beilaeufig in
einem Fallback-Vorschlag — ZUERST `firma_kontext(firmenname)` aufrufen
und NUR auf dessen Ergebnis antworten. Der Trigger ist der bewertete
Firmenname, nicht erst die explizite Statusfrage. Hintergrund (13.07.):
Claude behauptete aus dem Gedaechtnis einen falschen Firmen-Stand ("nur
eine Bewerbung, kein Interview") — tatsaechlich lief ein kompletter
Prozess bis ins Finale. PBP haelt die dokumentierte Wahrheit.

## STRENG: keine eigenen Ablehnungsgruende erfinden (#663 Teil 2)

Bei `stelle_bewerten(bewertung='passt_nicht')` und `stellen_bulk_bewerten`
NUR die vordefinierten Whitelist-Werte nutzen. Auch nicht "intelligent"
neu kombinieren, eindeutschen, kuerzen oder anders schreiben.

**Erlaubt — und sonst NICHTS:**

```
zu_weit_entfernt          gehalt_zu_niedrig         falsches_fachgebiet
zu_junior                 zu_senior                 unpassendes_arbeitsmodell
firma_uninteressant       zeitarbeit                befristet
bereits_beworben          duplikat                  kein_hochschulabschluss
sonstiges
```

**Verboten — frei erfunden, fuehrt zu Statistik-/Lerneffekt-Schaden:**

```
abgelaufen        war_nur_anfrage      windchill_fehlt
duplikat_bewerbung   teamcenter_fehlt      kein_passendes_projekt
```

Bei Unsicherheit: `sonstiges` waehlen oder den User fragen. `stelle_bewerten`
normalisiert nicht-vordefinierte Gruende zwar still auf `sonstiges`, aber
das verfaelscht die Statistik und den Lerneffekt (Outcome-Pattern in
fit_analyse, #648).

**Ausnahme:** ein User kann eigene Gruende in den PBP-Einstellungen anlegen
(Issue #663 Teil 1, geplant). Sobald das Feature live ist, gilt die dort
hinterlegte erweiterte Whitelist — Claude muss die aktuelle Liste aus
`stelle_bewerten`'s `verfuegbare_gruende`-Response uebernehmen.

## Fit-Analyse-Verdict scharf zitieren (#662)

`fit_analyse` liefert ein strukturiertes `empfehlung`-Feld mit drei
Kategorien: **EMPFOHLEN / BEDINGT / NICHT_EMPFOHLEN** plus `begruendung`
und `kurz`. Claude zitiert den Verdict direkt — keine eigenen Weichspueler
wie "Trefferchance nicht hoch, aber realistisch vorhanden".

- **EMPFOHLEN**: Profil passt, Bewerbung sinnvoll. Klare Ansage geben.
- **BEDINGT**: Methodenluecke, aber ueberbrueckbar. Im Anschreiben
  transparent adressieren (nicht versteckt!) — sonst wird das im Interview
  ein Problem.
- **NICHT_EMPFOHLEN**: k.o.-Kriterium oder fachlicher Gap zu gross. Klar
  sagen, NICHT mit "vielleicht doch versuchen" weichspuelen. Wenn der User
  trotzdem will, kann er entscheiden — aber die Empfehlung steht.

Konkrete Sprache:
- Statt "die Trefferchance ist nicht sehr hoch": **"Ohne [Skill X] wird
  diese Stelle nicht antreten."**
- Statt "denkbar mit Anpassung des Anschreibens": **"BEDINGT — Methoden
  uebertragbar, aber [Fachbegriff Y] muss im Anschreiben offen erwaehnt
  werden."**
- Statt "lohnt sich nur bedingt": **"NICHT EMPFOHLEN — [konkretes
  k.o.-Kriterium]. Bewerbung nur bei Kontakt im Unternehmen."**

## Kritische DB-Helfer

- `db.dismiss_job(hash, reason)` — nutzt `resolve_job_hash` intern, scoped Hash
  korrekt. NICHT roh `UPDATE jobs SET is_active=0 WHERE hash=?` ausfuehren —
  Hash ist mit `{profile_id}:` praefixed, das matcht sonst nicht.
- `db.update_job(hash, fields)` — Whitelist-Filter im Inneren. Wenn ein neues
  Feld nicht durchkommt, `_ALLOWED_UPDATE_FIELDS` erweitern.

## Mojibake-Repair

Doppelt-kodiertes UTF-8 als Latin-1 reparieren:
`s.encode('latin-1').decode('utf-8')`. Trat in `dashboard.py` an 47 Stellen
auf (v1.6.4-Fix).

## Test-Helper fuer FastMCP 2.12+

`mcp.call_tool` existiert in 2.12 nicht mehr. Stattdessen:

```python
def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())
```

(In `tests/test_v164_bugfixes.py`, `tests/test_v165_drift_fixes.py`,
`tests/test_v165_quickfixes.py` jeweils dupliziert — bei Bedarf zentralisieren.)
