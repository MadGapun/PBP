# PBP — Claude-Code-Memory

Persoenliches Bewerbungs-Portal (PBP). MCP-Server (Python/FastMCP) +
React-Frontend + SQLite. **v1.6.10** ist Stable auf GitHub. v1.7.0 laeuft
in der Beta-Reihe (zuletzt **beta.74**) — wird `--latest` erst nach
abgeschlossenem User-Test (User-Wort).

## ⛔ Master-Plan-First (HART, seit 2026-06-01)

**Vor JEDEM Code-Change MUSS ein Master-Plan-Eintrag existieren** —
mindestens als ⬜ Stub mit Issue-Verweis. Sonst keine Implementierung.

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
7. **Erst nach OK** committen, taggen, pushen, GH-Release erstellen.

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

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-X.Y.Z.zip](https://github.com/MadGapun/PBP/archive/refs/tags/vX.Y.Z.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

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
