# Changelog

Alle wichtigen Änderungen am Bewerbungs-Assistent werden hier dokumentiert.

Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Sektionen: **Added** (neue Features), **Changed** (bestehendes geändert),
**Fixed** (Bugs), **Deprecated** (bald weg), **Removed** (weg),
**Known Issues** (bekannt kaputt in diesem Release).

> 🛡 **DSGVO-Hinweis (2026-05-10):** Im Repo-History wurden 11 Issues
> mit personenbezogenen Daten Dritter (Recruiter-Namen, Mail-Adressen,
> konkrete Bewerbungs-Listen) komplett geloescht. Issue-Nummern
> #313, #315, #362, #523, #529, #531, #532, #538, #566, #587, #602
> existieren nicht mehr — Verweise darauf in dieser CHANGELOG fuehren
> zu 404. Ueber 100 weitere Issues wurden anonymisiert (Firmen → `<FIRMA>`,
> Emails → `<email-anonymisiert>`). Praeventiv-Werkzeug:
> `scripts/scrub_pii.py`. Pflicht-Workflow in CLAUDE.md dokumentiert.

## [1.7.0-beta.66] - 2026-05-14 — KI-Transparenz: Token-Klassen + Ollama-Genauigkeit (#632 Stufe 1 + #638 Stufe 5)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

### ✨ #632 Stufe 1 — Token-/Kosten-Klassen in `pbp_capabilities`

`pbp_capabilities()` (ohne Kategorie) liefert jetzt eine Sektion
`aufwand_klassen` mit vier Stufen, damit Claude VOR einer Operation
einschaetzen kann was sie kostet:

- **gratis_db** — reine DB-/Scraper-Operationen, keine Tokens
  (jobsuche_starten, stellen_anzeigen, bewerbung_*, ...)
- **lokal_guenstig** — Ollama, kostenlos aber RAM/Zeit
  (stellen_auto_aussortieren, dokument_profil_extrahieren lokal)
- **claude_mittel** — ~2-10k Tokens (fit_analyse, anschreiben_exportieren)
- **claude_teuer_bulk** — 25k+ Tokens, VOR Start Volumen nennen
  (stellen_bulk_bewerten, batch via Claude)

Plus `aufwand_hinweis`: bei teuren Bulk-Ops dem User das Volumen
nennen, lokale AI bevorzugen wenn Tokens gespart werden sollen.

### ✨ #638 Stufe 5 — Ollama-Genauigkeits-Tracking

Wie zuverlaessig sind die automatischen Aussortierungen? Neuer Helper
`db.get_ollama_accuracy_stats()` misst, wie oft der User eine
`auto:`-Aussortierung spaeter korrigiert hat:

- `auto_aussortiert_gesamt` — alle je auto-aussortierten Stellen
- `reaktiviert` — davon wieder aktiv (User-Korrektur = false positive)
- `mit_bewerbung` — davon mit Bewerbung verknuepft (starke Korrektur)
- `genauigkeit_prozent` — 100·(1 − korrigiert/gesamt), erst ab 5
  Auto-Entscheidungen (sonst None — zu duenne Datenbasis)

Exponiert in `pbp_mcp_diagnose` (Feld `ollama_genauigkeit`) und ueber
`GET /api/llm/accuracy` fuers Dashboard. Filtert manuelle
Aussortierungen korrekt aus (nur `auto:`-Prefix zaehlt).

### Was von #638 noch offen ist

- **Stufe 4** Klick-Reihen-Tipps — die `analyze_user_patterns`-
  Infrastruktur (#594) laeuft, neue Event-Typen fuer Sortier-/
  Filter-Muster sind reine Frontend-Verkabelung und folgen separat.

### Tests

- 7 neue Tests (`test_v170_beta66_ki_transparenz.py`):
  Aufwand-Klassen im Capabilities-Overview, Genauigkeits-Stats
  (Datenbasis-Schwelle, Korrektur-Zaehlung, Manual-Filter), MCP +
  REST-Endpoint
- 1379 / 1381 gruen (2 rote = pre-existing beta24 Ollama-Connection)

### Migration / Breaking Changes

Keine. Reine additive Read-Operationen.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.66.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.66.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.65] - 2026-05-14 — Auto-Aussortierung repariert + Score-Anreicherung (#638 Stufe 1/2/3)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.
> 🔥 **Wichtig:** der in beta.63 angekuendigte Auto-Dismiss-Hook
> funktionierte tatsaechlich NIE — beta.65 macht ihn erstmals lauffaehig.

Beim Bauen von #638 Stufe 2 ist aufgefallen, dass der Auto-Aussortier-
Hook aus beta.63 wegen **vier** Fehlern komplett tot war:

| Bug | Wirkung |
|---|---|
| Status-Check auf `"erledigt"` | `run_search` setzt `"fertig"` → Hook sprang immer sofort raus |
| `svc.run_task(...)` | Methode heisst `run()` → AttributeError, verschluckt |
| `payload.get("verdict")` | Parser liefert `decision` → immer None |
| `update_background_job(..., ergebnis=)` | kwarg heisst `result=` → TypeError, verschluckt |

Alle vier gefixt. Der Hook laeuft jetzt wirklich durch.

### ✨ #638 Stufe 2 — Score-Anreicherung fuer duenne Beschreibungen

Stellen ohne (oder mit sehr kurzer) Beschreibung haben oft Score 0 und
versacken unten in der Liste — obwohl Ollama sie als passend einstuft.
Der Auto-Hook hebt solche Stellen jetzt auf einen moderaten Score (35),
wenn Ollama `PASST` sagt:

- Nur bei duenner Beschreibung (`< 120` Zeichen)
- Nur wenn aktueller Score `< 35` und nicht gepinnt
- Ergebnis im Job-Status als `score_angereichert`

So werden „blinde" Stellen sichtbar statt unsichtbar zu bleiben.

### Was jetzt nach einer Jobsuche passiert (wenn Ollama aktiv)

1. Scraper laeuft → neue Stellen in DB
2. **Auto-Dismiss** (jetzt funktional): Ollama bewertet bis zu 30
   Stellen, sortiert `PASST_NICHT` aus (Grund mit `auto:`-Prefix)
3. **Score-Anreicherung**: `PASST`-Stellen mit duenner Beschreibung
   bekommen Score 35
4. **Few-Shot-Lernen** (beta.63 Stufe 3, lief auch erst jetzt wirklich):
   die letzten 5 manuellen Aussortierungen sind als Beispiele im Prompt
5. Ergebnis steht im `jobsuche_status` unter `auto_aussortiert`

### Tests

- 4 neue Tests (`test_v170_beta65_auto_dismiss_enrich.py`): Dismiss
  greift wirklich, Score-Anreicherung, fette Beschreibung unangetastet,
  Ergebnis-Recording
- 1372 / 1374 gruen (die 2 roten beta24-Ollama-Connection-Tests sind
  pre-existing + environment-abhaengig)

### Was von #638 noch offen ist

- **Stufe 4**: Klick-Reihen-Tipps (Infrastruktur via #594 da, neue
  Event-Typen folgen)
- **Stufe 5**: Genauigkeits-Tracking der Ollama-Entscheidungen
  (false-positives via `track.llmCorrection`)

### Migration / Breaking Changes

Keine. Score-Anreicherung ist additiv, betrifft nur Score-0-Stellen
mit duenner Beschreibung.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.65.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.65.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.64] - 2026-05-14 — Installer-Autostart, Doku-Tiefenanalyse, Job-Dedup (#639 + #640)

<!-- Hinweis: das urspruengliche Job-Dedup-Issue (#641) wurde nachtraeglich
     geloescht (DSGVO — enthielt einen Firmennamen in der Edit-History).
     Das Feature selbst ist Teil dieses Releases. -->


> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Drei Findings aus der laufenden Test-Schleife — Installer-UX, ein
Doku-Analyse-Bug und Job-Duplikate.

### ✨ #639 Installer startet PBP automatisch

Beobachtung: nach der Installation passierte (gefuehlt) nichts. Befund:

- **CLI-Installer** (`INSTALLIEREN.bat`, `INSTALLIEREN.command`,
  `install.sh`) starten das Dashboard + oeffnen den Browser **schon
  seit beta.23/38** automatisch — hier war nichts zu tun.
- **GUI-Installer** (`setup_gui.py` / setup.exe) hatte den Bug: der
  "Dashboard oeffnen"-Button startete `test_demo.py` — das laeuft mit
  **Demo-Daten in einem TEMP-Verzeichnis**, nicht der echten
  Installation. Gefixt: nutzt jetzt `start_dashboard.py` mit dem echten
  Datenverzeichnis, startet automatisch beim Erreichen der Done-Page
  (Thread, kein GUI-Freeze) + Health-Check auf Port 8200.
- Irrefuehrenden Text "(verfuegbar wenn Claude Desktop laeuft)"
  korrigiert — das Dashboard laeuft eigenstaendig.

### 🐛 #640 Doku-Tiefenanalyse: basis_analysiert galt als "fertig"

`basis_analysiert` ist ein **Zwischen**-Status (nur Regex-Basics, die
KI-Tiefenanalyse fehlt noch). An einer Stelle wurde er faelschlich wie
ein End-Status behandelt:

- **`db`-Naechste-Schritte-Guidance** zaehlte nur `nicht_extrahiert` —
  jetzt auch `basis_analysiert`. Verweist auf `/dokumente_verarbeiten`.
- **`dokumente_zur_analyse`** trennt jetzt explizit `nie_analysiert` vs
  `nur_basis_extraktion` und liefert einen `hinweis_tiefenanalyse`, damit
  klar wird WAS noch aussteht.

(`extraktion_starten`, `analyse_plan_erstellen` und die Prompts haben
basis_analysiert schon korrekt einbezogen.)

### ✨ Job-Duplikat-Erkennung beim Ingest

Dieselbe Stelle landete mehrfach mit verschiedenen Hashes (verschiedene
Quellen / Zeitpunkte). Jetzt:

- Neuer Helper `db._dedup_key(title, company)` — normalisiert Titel +
  Firma (Umlaute, Rechtsform-Suffixe GmbH/AG/..., Klammerzusaetze)
- `save_jobs` prueft vor dem Insert ob eine **aktive** Stelle mit
  gleichem Key aber anderem Hash existiert (im selben Batch UND in der DB)
- Treffer → neuer Eintrag wird `is_active=0`, `dismiss_reason='duplikat'`,
  mit Verweis auf den Original-Hash in `research_notes` (Audit-Trail bleibt)
- Rueckgabe enthaelt jetzt `duplikate_erkannt`

**Bonus-Fix dabei:** Re-Ingestion einer vom User aussortierten Stelle
reaktiviert sie nicht mehr und ueberschreibt ihren `dismiss_reason`/
Notizen nicht (vorher setzte `INSERT OR REPLACE` die Zeile komplett neu).

### Tests

- 9 neue Tests (`test_v170_beta64_dedup_analyse.py`): Dedup
  (Content-Match, Suffix-Normalisierung, Audit-Note, Cross-Batch,
  Dismissed-State-Preservation) + Doku-Status-Trennung
- 1381 / 1383 gruen — die 2 roten (`test_v170_beta24` Ollama-Connection)
  sind **pre-existing + environment-abhaengig** (echte Ollama-Probe),
  keine beta.64-Regression

### Migration / Breaking Changes

Keine. Dedup-Check ist additiv, alter Lifecycle bleibt erhalten.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.64.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.64.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.63] - 2026-05-14 — Ollama wird zur Hintergrund-KI (#638 Stufe 1 + 3)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

User-Wunsch: "Ich möchte ja fast, dass Ollama im Hintergrund mitläuft
und auch lernt bei jedem Klick den ich mache." Erste zwei Stufen aus
[#638](https://github.com/MadGapun/pbp/issues/638) — jetzt sichtbar.

### ✨ A) Auto-Aussortierung nach jeder Jobsuche (#638 Stufe 1)

Bisher musste man `stellen_auto_aussortieren()` manuell anstossen
(MCP-Tool oder Chat). Jetzt laeuft das **automatisch** nach jeder
erfolgreichen Jobsuche im selben Background-Thread:

- Hook in `jobsuche_starten` → nach erfolgreichem Scraper-Run wird
  `_maybe_auto_dismiss_after_search()` aufgerufen
- Bedingungen: Ollama erreichbar + `user_state=active` + Setting
  `auto_dismiss_after_search=true` (Default ON)
- Max 30 Stellen pro Auto-Run damit das Modell-RAM nicht 10 Minuten
  blockt waehrend der User noch klicken will
- Ergebnis landet im Job-`ergebnis` als `auto_aussortiert:
  {bewertet, aussortiert, von_aktiven}`
- Aussortier-Grund praefixed mit `auto:profil_match_negativ:` damit
  man manuelle von automatischen Aussortierungen unterscheiden kann

Was der User merkt: "Jobsuche druecken → 30 Stellen rein → 10 davon
sind nach 2 Min schon weg, mit Begruendung."

### ✨ B) Few-Shot-Lernschleife aus deinen Bewertungen (#638 Stufe 3)

Bisher hatte das `match_job_to_skills`-Modell nur ein Aggregat
("der User sortiert oft wegen 'falsches_fachgebiet' aus"). Jetzt sieht
es **konkrete Beispiele** der letzten Aussortierungen:

```
BEISPIELE — diese Stellen hat der Bewerber zuletzt selbst abgelehnt:
  - 'Junior Frontend Developer' bei 'Startup XY' → PASST_NICHT
    (Grund: falsches_seniority_level)
  - 'Sales Manager' bei 'Big Corp' → PASST_NICHT
    (Grund: falsches_fachgebiet)
  - ...
```

- Neuer DB-Helper `db.get_recent_user_dismissals(limit=20)`
- Filtert `auto:`-Dismissals raus damit keine Echokammer entsteht
  (sonst wuerde Ollama von seinen eigenen Entscheidungen lernen
  statt von den User-Entscheidungen)
- Top-5 werden in den Prompt eingebaut (Token-Cap)
- Greift sowohl im Auto-Hook (A) als auch im manuellen
  `stellen_auto_aussortieren`

Was der User merkt: je laenger du dabei bist und je mehr du selber
aussortierst, desto besser werden Ollamas Auto-Entscheidungen.

### Was BEWUSST nicht in beta.63 ist

- **Score-Anreicherung fuer Stellen ohne Beschreibung** (#638 Stufe 2)
  — braucht einen neuen LLM-Task `enrich_score_minimal`, kommt separat
- **Klick-Reihen-Tipps** ("du machst immer X dann Y, Tipp Z") — die
  Infrastruktur (`user_activity_events`, `analyze_user_patterns`,
  `AdaptiveHintBanner`) existiert seit #594, neue Event-Typen werden
  in einer Polish-Welle nachgereicht
- **Genauigkeits-Tracking** (false-positives bei Ollama-Entscheidungen)
  — Helper `track.llmCorrection` existiert schon, Dashboard-Stat fehlt

### Tests

- 10 neue Tests (`test_v170_beta63_auto_learn.py`):
  Few-Shot-Block im Prompt, Cap auf 5 Beispiele, `get_recent_user_dismissals`-
  Filter gegen Auto-Dismiss-Echokammer, Auto-Hook-Bedingungen
- 1374 / 1374 gruen

### Migration / Breaking Changes

Keine. Setting `auto_dismiss_after_search` ist optional (Default ON),
alles laeuft additiv neben den bestehenden Manuell-Pfaden.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.63.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.63.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.62] - 2026-05-14 — Ollama Cold-Start-Fix (#638)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

User-Report (#638): Erster Ollama-Aufruf nach Inaktivitaet kostet
50-60s Cold-Load → MCP-Timeout schlaegt zu bei `stellen_auto_aussortieren`
und anderen Bulk-Tools. Ollama entlaedt das Modell nach 5 Minuten
Inaktivitaet aus dem RAM (Default `keep_alive=5m`).

### ✨ Vier zusammenhaengende Fixes

**1. `keep_alive: 60m` in jedem `/api/generate`-Call**
- `LLMService._ollama_generate` schickt jetzt `keep_alive=60m` im
  Payload — Ollama behaelt das Modell 60 Min im RAM
- Effekt: nach dem ersten Cold-Load bleibt das Modell aktiv solange
  ueberhaupt Calls reinkommen oder der Warmup-Loop laeuft

**2. Neue `warmup()`-Methode + `/api/llm/warmup`-Endpoint**
- `LLMService.warmup(model=None)` schickt einen Dummy-Request
  (`prompt="ready", num_predict=1, keep_alive=60m`)
- Idempotent: bei warmem Modell Millisekunden, bei kaltem max 90s
- REST: `POST /api/llm/warmup` macht das Gleiche fuer Frontend

**3. Background-Warmup-Loop**
- Neuer Thread in `heartbeat.py`: `start_ollama_warmup_loop(db)`
- Schickt alle 4 Minuten einen Warmup-Ping (Ollama-Default `keep_alive`
  ist 5 Min → 4 Min Intervall verhindert Entladen)
- Nur aktiv wenn `user_state == "active"` (bei paused/off keinen RAM blockieren)
- Wird in `server.py:run_server()` neben dem bestehenden
  `start_periodic_heartbeat()` gestartet

**4. Pre-Warmup vor `stellen_auto_aussortieren`**
- Direkt nach dem `ollama_available`-Check wird `svc.warmup()` aufgerufen
- Wenn das Modell kalt ist, zahlt der User den Cold-Load EINMAL hier
  (max 90s) statt MCP-Timeout zu riskieren

### ✨ Bonus: Status-Force-Refresh

`GET /api/llm/status?refresh=1` bypasst den 30s-Cache. Frontend nutzt
das beim Tab-Mount in Settings → Lokale KI — User sieht den echten
aktuellen Status, nicht 30s alten Cache. Wichtig wenn er gerade Ollama
gestoppt/gestartet hat und sofort nachsehen will.

### Was du jetzt merken solltest

- `stellen_auto_aussortieren` laeuft auch bei kaltem Modell durch (Warmup
  vorne dran)
- Solange Lokale-KI auf `active` steht, bleibt das Modell quasi immer
  warm (Background-Loop alle 4 Min)
- Nach `taskkill ollama` und Restart via #637-Button: Status-Anzeige in
  Settings ist sofort frisch (kein 30s-Wartezimmer mehr)

### Tests

- 8 neue Tests (`test_v170_beta62_ollama_warmup.py`):
  keep_alive im Payload, warmup() Erfolg/Fehler/Edge-Cases,
  API-Endpoints, force_refresh-Param, Heartbeat-Loop-Idempotenz
- 1364 / 1364 gruen

### Migration / Breaking Changes

Keine. Alles additiv. Wenn Ollama nicht laeuft: Loop ist no-op.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.62.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.62.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.61] - 2026-05-14 — Hotfix: Sidebar-Menue hat jetzt wirklich Vorrang (#625)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.
> 🔥 **Hotfix** zu beta.60 — der Sidebar-Fix war halbgar.

User-Feedback nach beta.60: das obere Menue muss man immer noch scrollen,
obwohl auf dem Screen genug Platz waere. Elwosa war zwar gecapped (max
42vh), aber das war oft trotzdem zu viel, und die nav hatte
`flex-1` (= konkurriert mit Elwosa um Platz statt Vorrang zu haben).

### 🐛 Korrektur

- **`Sidebar.jsx` nav**: `flex-1 overflow-y-auto` → `flex-shrink-0
  overflow-y-auto` mit `maxHeight: calc(100vh - 180px)`. Heisst: das
  Menue nimmt seine Inhalts-Hoehe (alle Items inkl. Sub-Items sind
  IMMER voll sichtbar) und scrollt nur dann intern, wenn der Viewport
  absurd klein ist (z.B. unter 500px Hoehe).
- **`Sidebar.jsx` Footer-Slot**: jetzt `flex: 1 1 0; minHeight: 0;
  overflow-y-auto` — fuellt den Rest aus den die nav nicht braucht.
  Kein `max-h-[42vh]` mehr.
- **`ElwosaSidebarChat.jsx`**: keine festen vh-Werte mehr im Scroll-
  Container. `min-h-[80px]` + `maxHeight: 100%` — passt sich an den
  Footer-Container an. Auf grossen Screens waechst Elwosa entsprechend,
  auf kleinen schrumpft sie.

### Verhalten

| Viewport | Verhalten |
|---|---|
| Gross (z.B. 1080p+) | Menue komplett sichtbar, Elwosa nimmt sehr viel Platz |
| Normal (~768-900px) | Menue komplett, Elwosa fuellt den Rest |
| Klein (~500-700px) | Menue komplett, Elwosa schrumpft auf min 80px + scrollt intern |
| Absurd klein (<500px) | Menue scrollt selber — sonst nichts mehr platzierbar |

### Tests

- `test_v170_beta48_elwosa_ux.py` angepasst (kein vh-Wert mehr in
  ElwosaSidebarChat)
- 1356 / 1356 gruen

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.61.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.61.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.60] - 2026-05-14 — User-Test-Quartet: Sidebar + MCP-Diagnose + Datums-Editing + Ollama-Start (#625 + #636 + #631 + #637)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Vier zusammenhaengende Quality-of-Life-Aenderungen aus der laufenden
User-Test-Schleife.

### 🐛 #625 Sidebar: Hauptmenue von Elwosa-Panel verdraengt

Bei expandierten Sub-Menues (z.B. Kalender) wurde das obere Hauptmenue
vom darunterliegenden Elwosa-Panel teilweise ueberlagert. Fix:

- `Sidebar.jsx` Footer-Slot: `flex-shrink min-h-0 max-h-[42vh] overflow-y-auto`
  — schrumpft wenn die nav mehr Platz braucht, scrollt intern statt
  ueberzulaufen
- `ElwosaSidebarChat.jsx`: max-h-[60vh] -> max-h-[32vh],
  min-h-[150px] -> min-h-[100px]

### ✨ #636 MCP-Tool-Telemetrie fuer Hang/Timeout-Diagnose

Nach #635 (Response-Timeout in Doku-Pipeline) gibt es jetzt einen
generischen `time_tool`-Decorator und ein neues MCP-Tool:

- **`time_tool(logger, name)`** Decorator (in `tools/__init__.py`):
  - misst Dauer jedes Tool-Calls
  - schreibt Eintrag in Ringbuffer (200 Calls)
  - loggt WARNING bei Slow-Calls (>= 5s)
  - kennzeichnet Status als `ok` / `fehler` / `exception`
- **`pbp_mcp_diagnose`** MCP-Tool: liefert die letzten N Tool-Calls
  (oder nur langsame), Server-PID, PBP/Python-Version, Plattform.
  Hilft zu unterscheiden ob ein Timeout am Tool-Code liegt (Call ist
  im Buffer mit hoher Dauer) oder am Transport (Call ist gar nicht
  da).

Decorator erstmal angewendet auf Hot-Path-Tools die in Issue-Reports
auftauchten: `bewerbung_erstellen`, `bewerbung_status_aendern`,
`bewerbung_bearbeiten`, `stelle_bewerten`, `stellen_bulk_bewerten`.
Weitere Tools koennen mit minimalem Boilerplate folgen.

### ✨ #631 Status-Wechsel-Datum nachtraeglich aenderbar

`applied_at` (Bewerbungsdatum) war bereits editierbar (#529). Was
fehlte: Datum von Status-Wechsel-Events ("abgelehnt am",
"interview am" etc) konnte nicht korrigiert werden, wenn der User
den Status erst spaeter eintraegt als die eigentliche Aenderung
passiert ist.

- **DB-Methode** `update_application_event_date(event_id, new_date,
  app_id)` mit Date-Normalisierung (akzeptiert YYYY-MM-DD,
  DD.MM.YYYY, ISO-Timestamp)
- **REST-Endpoint** `PUT /api/applications/:appId/events/:eventId/date`
- **MCP-Tool** `bewerbung_event_datum_setzen(event_id, neues_datum,
  bewerbung_id)`
- **Frontend** Inline-Edit in der Bewerbungs-Timeline (Klick aufs
  Event-Datum oeffnet `<input type="date">`, Enter speichert,
  Escape bricht ab)

### ✨ #637 Lokale KI (Ollama) aus PBP heraus starten

Wenn Ollama via Taskmanager / Reboot / `taskkill` gestoppt wurde, gab
es bisher keinen Weg, sie aus dem Dashboard heraus wieder zu starten —
der User musste manuell in die Konsole.

- **Neuer Endpoint** `POST /api/llm/start` spawnt `ollama serve` als
  **Detached-Subprocess** (Crash von PBP killed Ollama nicht).
  - Windows: `creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`
  - macOS/Linux: `start_new_session=True`
  - Bei `FileNotFoundError` (Ollama-Binary nicht im PATH) -> 404 mit
    klarer Fehlermeldung + Link zu ollama.com/download
  - Bei `already_running` -> 200 ohne Spawn-Versuch
- **Frontend**: Im Settings-Tab "Lokale KI", wenn `ui_state ==
  not_installed`, jetzt zwei Sektionen:
  1. **"Vielleicht nur gestoppt?"** mit Button "Ollama starten" —
     spawnt + pollt 30s lang (alle 2s) ob Status auf `available` wechselt
  2. Bisherige "Noch nicht installiert?"-Sektion mit Download-Link
     bleibt darunter

Stufe 2 (Auto-Restart aus dem Heartbeat) und Stufe 3 (PBP-Lifecycle-
Integration) sind im Issue dokumentiert und folgen spaeter.

### Tests

- 16 neue Tests (`test_v170_beta60_trio.py`):
  Decorator-Tracking (ok/fehler/exception/slow), pbp_mcp_diagnose,
  Date-Update DB-Layer (DE/ISO Format, unbekannte Event-IDs),
  MCP-Tool, REST-Endpoint, Ollama-Start (already_running /
  not_installed / spawned)
- `test_v170_beta48_elwosa_ux.py` an neue Sidebar-Hoehen angepasst
- `test_mcp_registry.py` aktualisiert (151 statt 149 Tools,
  +`pbp_mcp_diagnose`, +`bewerbung_event_datum_setzen`)
- 1356 / 1356 gruen

### Migration / Breaking Changes

Keine. Alles additiv. Decorator wraps existing tools transparent.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.60.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.60.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.59] - 2026-05-13 — MCP-Timeout in Doku-Analyse-Pipeline (#635)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.
> 🔥 **Bugfix-Release** — Core-Feature war komplett blockiert.

User-Report mit Diagnose im Issue: `analyse_plan_erstellen` und
`dokumente_batch_analysieren` liefen in den 4-Minuten-Timeout im
Claude-Desktop-MCP-Relay. Server-Log zeigte: Tool-Aufruf empfangen,
aber Response kam beim Client nie an. Hypothese (bestaetigt):
**Response-Payload ueber MCP-Transport-Grenze**.

### 🐛 Drei zusammenhaengende Fixes

**1. `analyse_plan_erstellen` — Response-Payload reduziert:**
- Pro Batch nur noch 3 Datei-Vorschauen + Counter (vorher: alle
  Dateinamen aller Batches → bei 75 Docs schnell 5-10 KB)
- `erkannte_firmen` Hard-Cap auf 50 Eintraege
- Default `MAX_BATCH_BYTES` von 50000 auf 30000 reduziert

**2. `dokumente_batch_analysieren` — Pro-Doku-Truncation:**
- Neuer Parameter `max_bytes_per_doc` (Default 8000 ~ 2K Tokens)
- Bei laengerem Text wird auf Char-Grenze getrunkated (kein
  UTF-8-Mojibake) und ein Marker eingefuegt: „[... gekuerzt:
  weitere N Bytes nicht uebertragen. extraktion_starten([id]) fuer
  Vollzugriff]"
- Hard-Caps auf alle Argumente (max_text_bytes <= 50000,
  max_dokumente <= 20, max_bytes_per_doc <= 20000) — schuetzt vor
  versehentlich riesigen Werten
- `aktuelles_profil`: Skills auf 100 gecapped, Summary auf 500
  Zeichen gecapped (Counter zeigt aber die volle Anzahl)

**3. Bytes statt Chars im Counter:**
- `LENGTH(extracted_text)` -> `LENGTH(CAST(extracted_text AS BLOB))`.
- SQLite `LENGTH()` liefert Char-Count fuer TEXT, nicht Bytes —
  bei UTF-8-Sonderzeichen war die Schaetzung um Faktor 1.0-2.0 zu
  klein, was Batches sprengen konnte.

**4. Timing-Logs:**
- Beide Tools loggen jetzt `tool: N Docs, M Batches, X.XXs`
- Bei zukuenftigen Performance-Issues sieht man im Log sofort ob
  das Tool selbst haengt oder der Transport.

### Tests

- 7 neue Tests (`test_v170_beta59_doku_payload.py`):
  Plan-Compactness, Truncation, Hard-Caps gegen Argument-Tricks,
  Profile-Section-Cap
- 1340 / 1340 gruen

### Migration / Breaking Changes

Keine. Alle Aenderungen sind defensive Limits — alte Argumente
funktionieren weiter, werden nur ggf hard-gecapped.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.59.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.59.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.58] - 2026-05-11 — Doku-Verarbeitung deckt alle Faelle ab (#634)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

User-Feedback (Folge zu #633): "Bei hochgeladenen Dokumenten geht es
ja nicht immer nur darum das Profil zu erweitern, sondern auch um
Mails von Absagen, Einladungen, Jobangeboten — und das soll
automatisch im PBP uebernommen werden, sonst waere es ja nicht
hochgeladen worden."

Stimmt. Der Banner und der dahinter liegende Prompt waren bisher
einseitig auf CV-Daten optimiert. Die MCP-Tools fuer Mail-Matching,
Status-Updates und Termin-Anlage existierten zwar, wurden aber im
Default-Workflow nicht angeboten.

### ✨ Neuer Sammel-Prompt `/dokumente_verarbeiten`

Klassifiziert pro Dokument und routet zum passenden Sub-Workflow:

- **A) Profil-relevant** (CV / Zeugnis / Zertifikat / Projektliste)
  → Berufserfahrung, Skills, Ausbildung, Projekte extrahieren
- **B) Mail-Korrespondenz** (Absage / Einladung / Angebot /
  Recruiter-Anfrage) → Bewerbung identifizieren, Status aendern
  (`bewerbung_status_aendern`), Mail-Snapshot als Notiz anhaengen
- **C) Bewerbungs-Anhang** (firmenspezifischer CV / fertiges
  Anschreiben) → `dokument_verknuepfen` + `cv_path` /
  `cover_letter_path` in der Bewerbung setzen
- **D) Termin-Bestaetigung** (Interview-Einladung mit Datum)
  → `meeting_hinzufuegen` + ggf Status-Hebung auf `interview` oder
  `zweitgespraech`

Mehrfach-Klassifikation explizit erlaubt — eine Interview-Einladung
ist typisch B + D.

### Banner in DocumentsPage erweitert

- Wording: "X Dokumente koennen verarbeitet werden" (nicht mehr
  "analysiert")
- Aufzaehlung der vier Aktionsklassen direkt im Banner
- Button: "Dokumente verarbeiten" (war: "Analyse-Prompt kopieren")
- Hinweis im Aufklapp-Detail: `/profil_erweiterung` bleibt fuer
  reine Profil-Power-User

### MCP-Prompt-Liste erweitert

Insgesamt jetzt **24 Prompts** (vorher 23). `/profil_erweiterung`
bleibt unveraendert als schmaler Pfad.

### Wiki

[Profil aus Dokumenten](https://github.com/MadGapun/PBP/wiki/Profil-aus-Dokumenten)
ueberarbeitet — deckt jetzt explizit alle vier Faelle und erklaert
wann der schmale `/profil_erweiterung` statt `/dokumente_verarbeiten`
passt.

### Tests

- `test_mcp_registry.py` aktualisiert (24 Prompts statt 23,
  +`dokumente_verarbeiten` in EXPECTED_PROMPT_NAMES)
- 1333 / 1333 gruen

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.58.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.58.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.57] - 2026-05-11 — User-Test-Quick-Wins (#626 + #628 + #629 + #633)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Vier kleine Findings aus der User-Test-Mail vom 2026-05-11 — die Bugs
und die offensichtlichen UX-Polituren in einem Sammel-Patch. Die
groesseren Findings (eigene Quellen #627, Live-Updates #630, KI-Budget-
Transparenz #632, Status-Datums-Editing #631) sind als eigene Issues
fuer spaetere Iterationen geplant.

### ✨ Theme-Presets (#626)

Settings -> Erscheinungsbild -> neue Sektion "Farb-Schema" mit
**4 vorbelegten Schemen** als Quick-Apply-Buttons:

- **PBP Standard** — Original-Schema (teal/amber/coral/sky)
- **Modern Blau** — kuehler Blauton, ruhiger fuer lange Sessions
- **Warm Sand** — warme Erdtoene, weicher Kontrast
- **High Contrast** — maximaler Kontrast, Barrierefreiheit

Jeder Preset setzt alle 10 Tokens fuer Hell + Dunkel auf einmal.
Custom-Override pro Token bleibt moeglich (gewinnt ueber Preset).
Persistenz im `localStorage` parallel zum bisherigen Custom-State.

### 🐛 Bug: Doku-Doppel-Upload beim Drag (#628)

Window-Level `GlobalDocumentDropZone` und Page-eigene Drop-Zonen
(`DocumentsPage`, `ApplicationsPage`, `ProfilePage`, `DashboardPage`)
hatten beide `drop`-Listener. Bei einem Drop in eine Page-Zone
verarbeiteten BEIDE Handler die Datei → Doppel-Upload.

Fix: Window-Handler prueft jetzt `event.defaultPrevented` und
ueberspringt die Datei wenn die Page sie schon hatte. Dedup-Logik
(`signatures`-Set) bleibt als zweite Sicherung erhalten.

### 🐛 Bug: Status-Dropdown scrollt Page mit (#629)

Klassisches Wheel-Bubbling am Listen-Ende des SelectInput-Portals:
wenn die scrollbare Liste am unteren Rand ankam, scrollte das
Mausrad weiter die Hauptseite. Fix in `components/ui.jsx` an
**einer zentralen Stelle**:

- `overscrollBehavior: "contain"` als CSS-Property
- `onWheel={(e) => e.stopPropagation()}` als zweite Sicherung
  (browser ohne overscroll-behavior-Support)

Wirkt fuer **alle** SelectInputs in der App.

### ✨ Onboarding-Polish (#633)

User-Feedback "die Profil-Gewichtung war anfangs nicht klar" und
"unklar wo die Doku-Analyse gestartet wird":

**ProfilePage Suchkriterien-Section:**
- Neue Erklaerungs-Box ueber den Slidern: "Wie das Scoring funktioniert"
- Klarere Slider-Labels ("MUSS-Kriterium", "PLUS-Punkte" statt nur
  "MUSS"/"PLUS")
- Tooltips mit konkreten Beispielen pro Slider (z.B. "MUSS=5: Stelle
  ohne dieses Skill bekommt deutlichen Score-Abzug")

**DocumentsPage Analyse-Banner:**
- Neuer Wording-Lead: "Claude liest deine CVs, Zeugnisse und Anschreiben
  und extrahiert Berufserfahrung, Ausbildung, Skills und Projekte
  automatisch — du musst nichts manuell tippen"
- Aufklappbare Schritt-fuer-Schritt-Anleitung "So gehts (3 Schritte)"
- Klarere Toast-Meldung nach Klick

### Tests

- 1333 / 1333 gruen — alle Aenderungen sind frontend-only oder
  defensive Code-Aenderungen, keine neuen Backend-Tests noetig

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.57.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.57.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.56] - 2026-05-11 — Granulare KI-Steuerung (#425)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

User kann Claudes KI-Funktionen jetzt einzeln an- oder ausschalten.
Default: alles aktiv. Sinnvoll fuer User die nur die Tracking-Features
nutzen wollen, kostenbewusste Token-Verbraucher, oder Phasen wo nur
manuell gepflegt werden soll.

### ✨ Master-Switch + 7 Feature-Toggles

Settings -> Lokale KI -> neue Sektion "KI-Unterstuetzung (Claude)" ganz oben:

- **Master-Switch** — wenn aus blockt JEDE KI-Operation mit klarem Hinweis
- **Jobsuche via Claude** — Dashboard-Button bleibt unabhaengig
- **Dokumentenanalyse** — Profil aus Lebenslauf-Uploads
- **Stellenanalyse / Fit-Bewertung** — fit_analyse, skill_gap_analyse
- **Bewerbungs-Erstellung** — angepasster CV, Fachprofil, Anschreiben
- **Coaching** — Interview-Sim, Ablehnungs-Analyse, Verhandlung
- **Profil-Ersterfassung** — gefuehrtes Interview
- **KI-Hinweise** — Dashboard-Recommendations die auf Claude verweisen

Manuelle Tools (Profil pflegen, Bewerbungen tracken, Standard-CV-Export)
und der Dashboard-"Jetzt suchen"-Button bleiben **immer** verfuegbar —
auch bei Master=False. Das ist explizit so designt damit PBP nie ganz
nutzlos wird.

### Backend-Gates an 7 Hot-Tools

`jobsuche_starten`, `fit_analyse`, `skill_gap_analyse`, `ablehnungs_muster`,
`lebenslauf_angepasst_exportieren`, `fachprofil_exportieren`,
`anschreiben_exportieren`, `dokument_profil_extrahieren`,
`ersterfassung_starten` — alle pruefen vor Ausfuehrung den passenden
Toggle und liefern bei Block ein freundliches `{ki_blockiert: true,
hinweis, alternative}` zurueck statt zu crashen oder still zu schweigen.

### MCP-Tools fuer Claude

- **`ki_features_lesen()`** — aktueller Stand aller 8 Toggles
- **`ki_features_setzen(master=..., jobsuche=..., ...)`** — partielle
  Updates, Validierung, persistiert pro Profil

Damit kann ein User auch via Chat sagen "schalte Coaching ab" und
Claude reagiert direkt.

### REST-API

- `GET /api/settings/ki-features` → `{features: {...}}`
- `PUT /api/settings/ki-features` mit `{features: {...}}` ODER Top-Level
  `{master: false, ...}`. Unbekannte Keys werden ignoriert (forward-
  compatible).

### Tests

- **21 neue Tests** (`test_v170_beta56_ki_features.py`): DB-Schicht,
  MCP-Tool-Schicht, Backend-Gates fuer alle 7 betroffenen Tools,
  REST-API-Endpoints
- MCP-Registry-Test angepasst (149 statt 147 Tools, +2 neue)
- **1333 / 1333 gruen**

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.56.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.56.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.55] - 2026-05-11 — PyPI-Packaging + MCP Registry vorbereitet (#429)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.
> **Kein Code-Change** — reine Packaging-Vorbereitung.

User-Wunsch: PBP ueber PyPI verbreiten + im offiziellen MCP-Registry-
Katalog auftauchen. Dieser Release legt alles vor — der eigentliche
`twine upload` und `mcp-publisher publish` muss vom Repo-Owner mit
seinen Account-Credentials gemacht werden (Claude darf da nicht ran).

### ✨ pyproject.toml PyPI-fit gemacht

- **`readme = "README.md"`** statt Inline-String → PyPI rendert die
  Long-Description sichtbar
- **18 Trove-Classifiers** ergaenzt: License, Python-Version (3.11/3.12/3.13),
  Topic (Office/Business, Communications), Natural Language (German),
  Operating System
- **`[project.urls]`** mit Homepage / Repository / Documentation /
  Changelog / Issues / Releases — landen in der PyPI-Sidebar
- **Keywords erweitert** auf 16 (mcp, claude, anthropic, ats, lebenslauf,
  cv, resume, anschreiben, scraper, ...)
- **`[project.scripts]`** unveraendert: `bewerbungs-assistent` als CLI-Entrypoint

### ✨ `server.json` fuer MCP Registry

Neuer File im Repo-Root. Standard-Schema von
`registry.modelcontextprotocol.io`. Enthaelt:
- Name: `io.github.madgapun/pbp`
- Repository-Link, Description, Version
- PyPI-Package-Eintrag mit Transport=stdio + uvx-Hint

### ✨ `scripts/publish_to_pypi.md`

Schritt-fuer-Schritt-Anleitung fuer den Repo-Owner:
- PyPI-Account + API-Token + ~/.pypirc-Setup
- `python -m build` + `twine check` + `twine upload`
- TestPyPI als optionaler Trial
- mcp-publisher CLI Installation + `mcp-publisher publish`
- Troubleshooting (403-Fehler, Schema-Probleme, doppelte Versionen)
- Sicherheits-Hinweis: Claude darf nicht selbst publishen

### Build verifiziert

`python -m build` erzeugt sauber:
- `dist/bewerbungs_assistent-1.7.0b55-py3-none-any.whl`
- `dist/bewerbungs_assistent-1.7.0b55.tar.gz`

`twine check` PASSED fuer beide.

### Tests

- 12 neue Tests (`test_v170_beta55_pypi_packaging.py`):
  pyproject.toml-Felder, server.json-Schema, Konsistenz Package-Name
  zwischen beiden Files, Publish-Doku-Existenz
- **1311 / 1311 gruen** (+11 vs. beta.54, abzüglich 1 Hygiene-Test der nach CHANGELOG-Update grün wird)

### Naechste Schritte fuer den Repo-Owner

1. PyPI-Account + Token einrichten (siehe `scripts/publish_to_pypi.md`)
2. Lokal: `python -m build` + `twine check dist/*`
3. Optional: TestPyPI-Upload
4. Produktiv: `twine upload dist/*`
5. mcp-publisher CLI installieren
6. `mcp-publisher login github` + `mcp-publisher publish`

Danach: `pip install bewerbungs-assistent` funktioniert weltweit, und
PBP ist im MCP Registry-Katalog gelistet — maximale Sichtbarkeit.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.55.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.55.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.54] - 2026-05-11 — Reverse-Kontakt-Extraktion (#605)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

User-Hinweis: ca. 70-80 Bewerbungen haben Recruiter/HR-Kontakte die
nur als Freitext in `applications.notes` stecken, aber nicht als
strukturierte `contacts`-Eintraege. Dieses Tool zieht sie nachtraeglich
heraus.

### ✨ Neues MCP-Tool `kontakte_aus_bewerbungen_extrahieren`

```python
kontakte_aus_bewerbungen_extrahieren(
    nur_ohne_kontakte=True,   # nur Apps ohne extracted_from-Marker
    max_bewerbungen=20,        # Sicherheits-Cap
    dry_run=True,              # nur Vorschau
)
```

**Erweitert** das bestehende `kontakte_aus_bestand_importieren` (#606)
um drei wichtige Quellen die das Original verpasst:

| Neu | Alt |
|---|---|
| `application_events.notes` (Timeline-Notizen mit Gespraechspartnern) | nur app.notes |
| Verknuepfte Dokumente (außer cv/cover_letter) | nur Stellenbeschreibung |
| Konfigurierbares max_bewerbungen | Hard-Cap 100 |

**Workflow:**
```
Du: „Lass kontakte_aus_bewerbungen_extrahieren mit dry_run laufen"
→ Claude prueft die Top-20 Bewerbungen ohne Kontakte
→ Du bekommst eine Vorschau-Liste

Du: „Wenn das passt, mach es scharf"
→ dry_run=False, Kontakte werden als 'pending' angelegt
→ Genehmigung in Kontakte-Tab → akzeptieren oder verwerfen
```

### Sicherheits-Logik

- Confidence-Filter: < 0.5 wird verworfen
- LLM-Input-Cap: 5000 Zeichen pro Bewerbung
- CV/Anschreiben werden ausgeschlossen (eigene Texte, keine Dritt-Kontaktdaten)
- Idempotent: zweiter Lauf mit `nur_ohne_kontakte=True` findet die schon extrahierten nicht mehr
- Pending-Markierung: Kontakte werden nicht ohne User-Genehmigung produktiv

MCP-Tool-Count: 146 → **147**.

### Tests

- 9 neue Tests (`test_v170_beta54_reverse_kontakt.py`):
  Skip-Pfade (AI nicht verfuegbar/paused), Dry-Run, Apply, Filter
  `nur_ohne_kontakte`, max_bewerbungen-Cap, Confidence-Filter,
  Event-Notes-Inclusion
- **1300 / 1300 gruen** + 1 skipped (+9 vs. beta.53)

### Bezug

- #606: bestehender Auto-Engine-Step, der nur neue Bewerbungen scannt
- #607: Kontakt-Kategorien (kontakte_kategorien_auflisten)

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.54.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.54.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.53] - 2026-05-11 — Kombiniertes Fachprofil & Referenzprojekte (#617)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

User-Test-Anlass: bei einem Direktkontakt wurde ein kombiniertes
Dokument benoetigt — `lebenslauf_angepasst_exportieren` produziert nur
den Lebenslauf, separate Projektliste war Workaround per Desktop
Commander (mit Timeout-Fehler).

### ✨ Neues MCP-Tool `fachprofil_exportieren`

```python
fachprofil_exportieren(
    stelle="Senior PLM Architect",
    firma="ACME GmbH",
    stellenbeschreibung="...",
    projekte_anzahl=5,
    format="docx",  # oder "pdf"
)
```

Anders als `lebenslauf_angepasst_exportieren` (Lebenslauf-Format mit
inline-Projekten unter Stationen) zieht dieses Tool die Projekte als
**eigene prominente Sektion** heraus — nach Stellen-Relevanz sortiert
und ausfuehrlicher dargestellt.

**Aufbau:**
1. Header (Name + Zielposition + Kontakt)
2. Kurzprofil
3. Kernkompetenzen (priorisiert nach Stellen-Match)
4. **Referenzprojekte** (Top-N, ausfuehrlich mit Beschreibung +
   Technologien + Ergebnis)
5. Berufliche Stationen (kompakt, ohne Projekt-Inline)
6. Ausbildung

**Sinnvoll fuer:**
- Direktkontakte ueber LinkedIn/XING (ein Dokument statt zwei)
- Freelance-Anfragen ohne formelle Ausschreibung
- Vorstellung beim ersten Recruiter-Gespraech

### Relevanz-Scoring fuer Projekte

`_score_project_relevance()` gewichtet:
- +3 pro Job-Keyword das im Projekt-Text vorkommt
- +1 wenn `result` befuellt (messbares Ergebnis)
- +1 wenn `technologies` befuellt

Top-N werden nach Score sortiert, dann ausfuehrlich gerendert.

### Format-Hinweise

- **DOCX (empfohlen):** im eigenen Template nachbearbeiten, dann selbst PDF
  speichern. Direkt generierte PDFs wirken haeufig KI-generiert.
- **PDF:** erzeugt aktuell DOCX als Zwischenstufe (volle PDF-
  Konvertierung via Word/LibreOffice empfohlen).

MCP-Tool-Count: 145 → **146**.

### Tests

- 11 neue Tests (`test_v170_beta53_fachprofil.py`):
  Doc-Erstellung, Header-Inhalt, Relevanz-Sortierung, Limit, Edge-Cases
  (kein Profil, falsches Format, ohne Projekte), MCP-Tool-Roundtrip
- **1291 / 1291 gruen** + 1 skipped (+11 vs. beta.52)

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.53.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.53.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.52] - 2026-05-11 — Scraper Phase 3 (#624): JSON-LD-Helper + bundesagentur-Migration

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Phase 3 der Scraper-Konsolidierung. Statt JSON-LD blind in alle HTML-
Scraper nachzuruesten (kein klarer Mehrwert wo Detail-Fetch bereits
JSON-LD nutzt) ein gezielterer Cut: zentrales JSON-LD-Extract als
wiederverwendbarer Helper, plus die letzte fehlende Scraper-Migration.

### ✨ Added — `extract_jobposting_jsonld(html, max_chars=2000)` Helper

Aus `fetch_description_from_detail` extrahiert. Gibt das volle
JobPosting-Dict (`title`, `description`, `datePosted`, `validThrough`,
`employmentType`, `hiringOrganization`, `jobLocation`, `baseSalary`, ...)
statt nur der Beschreibung. Description ist HTML-gestripped, max
`max_chars` Zeichen.

Robust:
- Akzeptiert JSON-LD als einzelnes Item, Array, oder im `@graph`-Envelope
- Ueberspringt malformed JSON-Scripts und probiert den naechsten
- Filtert auf `@type=JobPosting` (ignoriert `WebSite`, `Article`, ...)

`fetch_description_from_detail` nutzt jetzt diesen Helper intern statt
eigenem Parsing — Verhalten unveraendert, nur sauberer.

### Changed — bundesagentur.py auf `make_session()` migriert

Letzter Standard-Scraper migriert. Kniffliger als die anderen weil
`bundesagentur` einen iOS-App-User-Agent erwartet (`Jobsuche/2.12.0
(de.arbeitsagentur.jobboerse; iOS 16) Alamofire/5.6.2`) und einen
`X-API-Key`-Header. `make_session(user_agent=..., extra_headers=...)`
unterstuetzt diese Overrides genau dafuer.

Eigene Retry-Logik (`_request_with_retry`) bleibt — sie hat eine
spezifische 3-Versuchs-Strategie mit exponential backoff fuer 503/DNS-
overflow-Faelle (#489) die der generische `with_retry()`-Decorator nicht
1:1 abbildet.

Per-Request-Header-Override entfernt (war nach session-level redundant).

### Wieso nicht „JSON-LD blind nachruesten"?

Audit-Erkenntnis: 5 der „HTML-only"-Scraper nutzen `fetch_description_
from_detail` fuer Detail-Beschreibungen — das ruft jetzt
`extract_jobposting_jsonld` intern auf. JSON-LD-Lesen ist also
faktisch in 8 weiteren Scrapern aktiv, ohne dass ich die einzeln
anfassen musste.

JSON-LD AUF LISTING-Seiten (statt Detail) bringt nur in seltenen Faellen
zusaetzlichen Wert — und ist Source-spezifisch. Wenn das mal noetig
wird, koennen Scraper jetzt einfach `extract_jobposting_jsonld()`
importieren.

### Tests

- 13 neue Tests (`test_v170_beta52_jsonld_helper.py`):
  Basis-Extraktion, HTML-Strip in Description, Array/`@graph`-Envelope,
  Multi-Scripts, Malformed-JSON, Max-Chars-Limit, Migration-Verifikation
- **1280 / 1280 gruen** + 1 skipped (+13 vs. beta.51)

### Bilanz Scraper-Audit-Cycle (#624)

Alle 3 Phasen abgeschlossen:
- **Phase 1** (beta.50): `make_session`, `with_retry`, `PBP_USER_AGENT`
  + 2 Migrations
- **Phase 2** (beta.51): 9 weitere Migrations + Health-Check + MCP-Tool
- **Phase 3** (beta.52): JSON-LD-Helper extrahiert + bundesagentur-Migration

Stand danach: **alle 12 API/Feed-Scraper auf zentralen Helpers**, alle
8 Scraper mit Detail-Fetch profitieren von `extract_jobposting_jsonld`,
plus aktiver `quellen_health_check` als Diagnose. HTML-only- und
Browser-Scraper bleiben individuell — bei denen waere Konsolidierung
risikobelastet.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.52.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.52.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.51] - 2026-05-11 — Scraper Phase 2 (#624): 9 weitere Migrations + Health-Check

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Phase 2 der Scraper-Konsolidierung. 9 weitere Scraper auf zentralen
`make_session()`-Helper migriert, plus aktiver Probe-Health-Check als
Diagnose-Tool.

### Migrationen — 9 weitere Scraper auf `make_session()`

Vorher: jeder Scraper mit eigenem `_HEADERS = {...}`-Dict + `httpx.Client(...)`.
Jetzt: zentraler Helper aus #624 Phase 1.

| Scraper | Content-Type |
|---|---|
| `greenhouse.py` | json (Boards-API) |
| `remotive.py` | json |
| `himalayas.py` | json |
| `workable.py` | json |
| `workday_dax.py` | json |
| `berufsstart.py` | rss |
| `studentjob.py` | rss |
| `praktikum_de.py` | rss |
| `personio.py` | xml |

Verhalten unveraendert. Boilerplate -7 Zeilen pro Scraper, einheitlicher
User-Agent, einheitlicher Timeout-Default (15s). `bundesagentur` bleibt
unangetastet wegen seiner spezifischen Retry- + iOS-App-UA-Logik.

### ✨ Added — Health-Check für Quellen (`job_scraper/health.py`)

Aktiver Probe-Check pro Quelle: minimaler HTTP-Request (1 Stelle,
keine Filter), liefert Latenz + HTTP-Status. Ergaenzt
`scraper_diagnose` (das auf Liefer-Statistiken basiert) — hier kommt
die Info „API selbst erreichbar JA/NEIN" aus einem echten Request.

12 Quellen mit Probe-Definition: `bundesagentur`, `arbeitnow`,
`greenhouse`, `remoteok`, `remotive`, `himalayas`, `workable`,
`workday_dax`, `berufsstart`, `studentjob`, `praktikum_de`, `personio`.

Browser-/JobSpy-basierte Quellen melden `no_probe_defined` — fuer die
ist der Health-Check nicht sinnvoll.

### ✨ Added — MCP-Tool `quellen_health_check`

```python
quellen_health_check(quellen=[], parallel=True) -> dict
```

- `quellen=[]` → alle Quellen mit Probe (~12)
- `quellen=["arbeitnow", "remoteok"]` → nur die genannten
- `parallel=True` → ThreadPool mit 8 Workern (Default)

Result-Schema pro Quelle: `source`, `reachable`, `http_status`,
`latency_ms`, `error`, `method`, `url`. Plus aggregiertes
`count_total` / `count_reachable`.

**Use Case:** *„Warum kommen von <Quelle> seit Tagen keine Treffer?"*
→ Claude ruft das Tool, sagt: *„API liefert 503 — temporär weg"* ODER
*„API liefert 200 — Suche selbst ist das Problem, evtl. liegts an deinen
Suchbegriffen."*

MCP-Tool-Count: 144 → **145**.

### Tests

- 12 neue Tests (`test_v170_beta51_health_check.py`)
- 2 alte Tests bereits in beta.50 angepasst — weitere 9 Migrations
  brauchen keine Test-Anpassung weil keine Tests die Scraper direkt mocken
- **1267 / 1267 gruen** + 1 skipped (+12 vs. beta.50)

### Was offen bleibt (Phase 3 in #624)

- JSON-LD nachruesten in 4 HTML-Scrapern
- Adzuna-API-Adapter
- bundesagentur.py auf neue Helpers migrieren (vorsichtig wegen Retry-Logik)

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.51.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.51.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.50] - 2026-05-10 — Scraper-Helpers Phase 1 (#624): make_session, with_retry, PBP_USER_AGENT

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Erste Phase der Scraper-Konsolidierung. Audit ueber alle 32 Scraper
ergab: 5 verschiedene User-Agent-Strings, Timeouts 12-30s ohne Pattern,
Retry-Logik nur in 1 Scraper. Diese Beta legt die zentrale Foundation —
Migration der einzelnen Scraper erfolgt schrittweise.

### ✨ Added — `job_scraper/__init__.py` Helpers

- **`PBP_USER_AGENT`** — einheitlicher UA mit Kontakt-URL:
  `PBP-Bewerbungs-Assistent/1.7 (+https://github.com/MadGapun/PBP)`
- **`make_session(content_type, timeout, ...)`** — vorkonfigurierter
  `httpx.Client` als Context-Manager. Content-Types: json/rss/xml/html/any.
  Standard-Timeout 15s. Standards koennen via `extra_headers`/`user_agent`
  ueberschrieben werden (z.B. `bundesagentur` braucht iOS-App-UA).
- **`with_retry(max_attempts, backoff_base, retry_status)`** — Decorator
  fuer transient-error-Retry. Erkennt 500/502/503/504/429 und
  `httpx.TransportError`/`TimeoutException`. Exponential backoff,
  respektiert `Retry-After`-Header bei 429.

### Changed — Migrationen `arbeitnow` + `remoteok` als Beispiel

Beide Scraper migriert von eigenen `_HEADERS`-Dicts auf `make_session()`.
Verhalten unveraendert — User-Agent ist jetzt der zentrale PBP-String.
Kein neuer Code, nur weniger Boilerplate (-7 Zeilen pro Scraper).

### Migrations-Pfad fuer die anderen 30 Scraper

In #624 dokumentiert. Phase 2 wird die offiziellen-API-Scraper
migrieren (greenhouse, personio, workday_dax, remotive, himalayas,
workable, bundesagentur). Phase 3 die HTML-/Browser-Scraper.

### Tests

- 17 neue Tests (`test_v170_beta50_scraper_helpers.py`) — Helper +
  Migrations-Verifikation + Smoke-Test mit Mock-Response
- 2 alte Tests an neue Patch-Targets angepasst
- **1255 / 1255 gruen** + 1 skipped (+17 vs. beta.49)

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.50.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.50.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.49] - 2026-05-10 — Post-Interview-Reflexion (#464): strukturierter Fragebogen

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Schliesst eine Lifecycle-Luecke nach `interview_abgeschlossen` —
strukturierter Fragebogen statt Freitext-Notizen. Erste Stufe von
[#452 Interview-Training-Arc](https://github.com/MadGapun/PBP/issues/452):
die hier gespeicherten Reflexionen sind spaeter wiederverwendbar bei der
naechsten Interview-Vorbereitung.

### Schema v42 → v43

Neue Tabelle `interview_reflections` mit Feldern:
- `application_id` (FK ON DELETE CASCADE)
- `was_lief_gut`, `was_lief_schlecht`, `was_war_ueberraschend`
- `gefuehl` (1=mies bis 5=super)
- `next_steps`, `wiederverwendbare_antwort`
- Standard-Audit-Felder (created_at/updated_at/profile_id)

Eine Reflexion pro Bewerbung (eindeutig per `application_id`). Fuer
mehrere Reflexionen pro Bewerbung waere ein eigenes Folge-Issue noetig.

### Neue MCP-Tools

| Tool | Zweck |
|---|---|
| `interview_reflexion_speichern(bewerbung_id, was_lief_gut, was_lief_schlecht, was_war_ueberraschend, gefuehl, next_steps, wiederverwendbare_antwort)` | Anlegen oder Aktualisieren. Idempotent. |
| `interview_reflexion_lesen(bewerbung_id)` | Liest die Reflexion zu einer Bewerbung |
| `interview_reflexionen_anzeigen(limit=20)` | Liste der letzten Reflexionen — fuer Lerneffekt vor naechstem Interview |

MCP-Tool-Count: 141 → **144**.

### Workflow

1. Status auf `interview_abgeschlossen` setzen
2. Claude bitten: *„Reflexion fuer Bewerbung A-0042 speichern"*
3. Claude fragt durch (was lief gut, ueberraschend, ...) und ruft das Tool
4. Bei naechster Interview-Vorbereitung: *„zeig mir Reflexionen aus letzter Zeit"*

### Tests

- 12 neue Tests (`test_v170_beta49_interview_reflexion.py`)
- **1238 / 1238 gruen** + 1 skipped (+13 vs. beta.48)

### Bewusst nicht enthalten

- **Frontend-Card** auf der Bewerbungs-Detail-Seite — kommt mit
  beta.50 oder als Teil von #452. Aktuell laeuft alles ueber Claude.
- **LLM-gestuetzte Auto-Vorschlaege** beim Befuellen — User bestimmt
  selbst was er reflektiert.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.49.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.49.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.48] - 2026-05-10 — Elwosa-UX-Polish: Auto-Scroll, adaptive Hoehe, Action-Links (#611)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Schliesst den letzten echten Bug aus dem User-Test-Cluster der letzten
Wochen.

### ✨ Auto-Scroll mit Sticky-Bottom (#611)

`ElwosaSidebarChat` scrollt jetzt automatisch zur neuesten Nachricht —
**aber nur wenn der User am Ende ist**. Wenn er hochgescrollt hat um
eine alte Nachricht zu lesen, wird das nicht weggerissen.

- `useLayoutEffect` synchronisiert den Scroll mit dem DOM-Update
- 30px-Toleranz fuer „am Ende" (User scrollt nicht millimeter-genau)
- Pattern wie in Slack/Discord/Twitter

### ✨ „Neue Nachrichten unten"-Indicator

Wenn der User oben ist und eine neue Nachricht kommt, erscheint ein
Teal-Pill-Button am unteren Rand der Chat-Box: **„X neu"** mit
Down-Chevron. Klick scrollt nach unten und reaktiviert Sticky-Bottom.

### ✨ Adaptive Hoehe

Vorher: starres `max-h-[260px]`.
Jetzt: `min-h-[150px] max-h-[60vh]` — auf grossen Screens (4K) wachsen
die Bubbles auf bis zu ~600-700px, auf kleinen bleiben sie kompakt.

### ✨ Action-Link-Routing (#611)

Der `[link:type:id|label]`-Markup-Renderer bekommt vier neue Routen
ueber `App.jsx::onNavigate`:

| Markup | Wirkung |
|---|---|
| `[link:application:abc12345|...]` | Navigation zu Bewerbungen mit Fokus auf abc12345 |
| `[link:job:hash|...]` | Navigation zu Stellen mit Fokus auf hash |
| `[link:job_filter:missing_desc|...]` | Stellen-Page mit Filter „Nur ohne Beschreibung" |
| `[link:page:xxx|...]` | Direkter Page-Wechsel |

Plus die schon vorhandenen `[link:pause:N|...]` und `[link:wiki:Page|...]`.

### ✨ Pool-Linien mit Action-Links

`STATUS_CHANGE_LINES` haben jetzt pro Trigger mind. eine Variante mit
`[link:application:{ref}|...]`-Markup. Beim Triggern wird `{ref}`
durch die `application_id` ersetzt — Klick fuehrt direkt zur
Bewerbung.

Beispiel-Linien:
- `"Absage von {firma}. [link:application:{ref}|Akte schliessen] und naechste angehen."`
- `"**Interview** bei {firma}. [link:application:{ref}|Vorbereitung oeffnen]."`
- `"Angenommen bei {firma}. [link:application:{ref}|Verlauf ansehen]. Glueckwunsch."`

### Tests

- 10 neue Tests (`test_v170_beta48_elwosa_ux.py`)
- **1224 / 1224 gruen** + 1 skipped (+9 vs. beta.47)

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.48.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.48.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.47] - 2026-05-10 — Daten-Migrationen (#613, #616) + 2 neue MCP-Tools

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Schliesst die letzten zwei Bugs aus dem User-Test-Cluster — beide
brauchten echte Daten-Migrationen, deshalb separate Beta nach dem
Bug-Sweep.

### ✨ Added — `services/url_to_source.py` (#613)

Erkennt anhand der Job-URL die Source (LinkedIn, StepStone, Indeed,
XING, Bundesagentur, <FIRMA>, Greenhouse, Workday-DAX, plus 20 weitere).

- Pure Funktion `detect_source_from_url(url)` — Substring-Match auf
  Hostname mit Reihenfolge-Sensitivitaet
- Fallback `'manuell'` bei unbekannter Domain oder leerem URL
- Behandelt URLs ohne Schema (`linkedin.com/jobs/123`)

### ✨ Added — `quellen_aus_urls_korrigieren` MCP-Tool (#613)

Migriert bestehende `source='manuell'`-Eintraege auf die korrekte
Source basierend auf der URL.

- `dry_run=True` (Default) zeigt Vorschau ohne Schreibvorgang
- `dry_run=False` schreibt
- Idempotent — zweiter Lauf nach Erfolg findet 0 Kandidaten

Beispiel-Output:
```json
{"status": "ausgefuehrt", "count_total": 17, "count_changed": 16,
 "count_applied": 16, "changes": [{"hash": "...", "source_alt": "manuell",
 "source_neu": "linkedin"}]}
```

### ✨ Added — Hot-Path-Detection in `stelle_manuell_anlegen` + `bewerbung_erstellen`

Beim Anlegen einer neuen Stelle wird die URL jetzt sofort gegen die
Pattern-Liste geprueft. Wenn eine bekannte Quelle erkannt wird, wird
diese statt `'manuell'` gespeichert. Explizit gesetzte `quelle` bleibt
unveraendert.

So wachsen keine neuen verwaisten `source='manuell'`-Eintraege nach.

### ✨ Added — `verwaiste_stellenrefs_bereinigen` MCP-Tool (#616)

Findet Bewerbungen mit `job_hash` der nicht (mehr) in `jobs` existiert
(orphaned FK). Drei Strategien:

| Strategie | Verhalten |
|---|---|
| `report` (Default) | Nur auflisten, kein Schreibvorgang |
| `leeren` | `applications.job_hash` auf NULL setzen (FK-konform) |
| `rekonstruieren` | Platzhalter-Stelle aus title/company/url anlegen mit `is_active=0`, `dismiss_reason='rekonstruiert_orphan_616'`. Bewerbung wird auf den neuen Hash umgestellt |

Plus jede Strategie unterstuetzt `dry_run=True/False`.

Bei `rekonstruieren` wird auch die URL durch `detect_source_from_url`
gefuehrt — die Platzhalter-Stelle haengt also gleich an der richtigen
Quelle.

### Tests

- 13 neue Tests (`test_v170_beta47_data_migrations.py`)
- MCP-Tool-Count: 139 → **141** (+2 Migrations-Tools)
- **1215 / 1215 gruen** + 1 skipped (+13 vs. beta.46)

### Wie du die Migration laufen laesst

In Claude Desktop:

```
„Lass quellen_aus_urls_korrigieren mit dry_run laufen und zeig mir die Vorschau"
→ Claude ruft das Tool, du siehst was sich aendert

„Wenn das passt, mach es scharf"
→ Claude ruft mit dry_run=False
```

Analog fuer `verwaiste_stellenrefs_bereinigen`. Empfohlen: erst
`strategie='report'`, dann je nach Anzahl entweder `leeren`
(schnell, einfach) oder `rekonstruieren` (mehr Arbeit fuer PBP, aber
spaeter kein Datenverlust).

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.47.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.47.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.46] - 2026-05-10 — Bug-Sweep: 7 Bugs gefixt (#604, #618, #602, #619, #610, #603, #615)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Sammel-Release fuer Bug-Cluster der letzten Test-Sessions. Sieben User-
Test-Findings sauber gefixt, plus ein Bonus-TZ-Bug der bei Tag-Wechsel
um Mitternacht (UTC vs. Lokalzeit) Limits inkonsistent gemacht hat.

### 🐛 Fixed — #604 „intern" als Praktikum-Synonym entfernt

`_SYNONYM_MAP["praktikum"]` enthielt `"intern"` — false positive auf
`"internationalen Kunden"` / `"interne Kommunikation"` in deutschen
Stellentexten. Score sprang ohne Vorwarnung auf 0.

→ `"intern"` entfernt, `"internship"` (englisch, eindeutig) bleibt.

### 🐛 Fixed — #618 `stelle_bearbeiten` akzeptiert jetzt Kurz-Hash

`stellen_anzeigen()` liefert `id` als 8-Zeichen-Hash, andere Tools
(`fit_analyse`, `scoring_vorschau`) akzeptieren diesen — `stelle_bearbeiten`
verlangte aber den vollen 12-Zeichen-Hash.

→ `_find_job_row` mit Prefix-LIKE-Fallback fuer kurze Hashes.
Konsistent zur 8-Zeichen-Anzeige.

### 🐛 Fixed — #602 `applied_at` Default + Report-Fallback

Inbound-Recruiter-Anfragen via `bewerbung_erstellen` ohne explizites
`applied_at` haben das Feld leer gelassen → 14 verwaiste Eintraege
erschienen im Bewerbungsbericht ohne Datum.

→ Default = heute wenn `status != 'in_vorbereitung'`. Plus Report-
Generator nutzt `created_at` als Fallback fuer ggf. existierende
Altlasten.

### 🐛 Fixed — #619 PDF-Export Unicode-Pfeil-Crash

`profil_report_exportieren(format='pdf')` schlug fehl an `→` (U+2192)
weil Helvetica-Standard-Font kein Unicode kann.

→ `safe()`-Helper erweitert: Pfeile (`→`/`←`/`⇒`/...), Bullets,
typographische Anfuehrungszeichen, Mathe-Symbole werden auf ASCII
gemappt. Letzter Fallback: `latin-1` mit `errors='replace'` — kein
Crash mehr, nur einzelne `?`-Zeichen wo Unicode unbekannt.

### 🐛 Fixed — #610 `stellen_auto_aussortieren` outputSchema-Validierung

Fehler-Pfade (Ollama nicht da, kein Profil) hatten andere Keys als
Success-Pfade — MCP outputSchema-Check schlug fehl.

→ Uniformes Schema mit allen Pflicht-Keys (`status`, `geprueft`,
`passt_nicht`, ...) auch im Fehler-Fall via `_err()`-Helper.
Plus Try/Except um den ganzen Body damit unhandled Exceptions auch
strukturiert returnen.

### 🐛 Fixed — #603 Fit-Score=0 durch PBP-Notizen in `description`

Wenn Claude redaktionelle Analyse (`Auffaelliges:`, `PBP-Notiz:`) in
`jobs.description` schrieb und diese ein Ausschluss-Keyword enthielt
(z.B. „Hands-on"), sabotierte das die Score-Berechnung.

→ Neuer Helper `_strip_pbp_notes()` schneidet alles ab dem ersten
Trenner ab (`---`, `## Auffaelliges:`, `## PBP-Notizen:`, ...).
`calculate_score` benutzt den bereinigten Text fuer Ausschluss-
Matching.

### 🐛 Fixed — #615 `kontakt_verknuepfen` klare Fehlermeldungen

`FOREIGN KEY constraint failed` ohne Kontext — User wusste nicht ob
Kontakt, Bewerbung oder Stelle fehlt.

→ `link_contact` macht explizite Existenz-Checks vor INSERT mit
klaren Meldungen (`„Kontakt nicht gefunden"`, `„Bewerbung nicht
gefunden"`, `„Stelle nicht gefunden — evtl. orphaned FK (#616)"`).
Plus Kurz-Hash-Aufloesung fuer `target_id` (analog zu anderen Tools).

### 🐛 Fixed (Bonus) — Elwosa Frequenz-Limits TZ-Bug

`_count_today` / `_count_all_today` / `_seen_today` verglichen lokales
Datum gegen UTC-Datum (created_at wird in UTC gespeichert). Folge:
um Mitternacht (lokal) sprang der Counter unbemerkt zurueck.

→ Konsistent UTC-Date verwenden in `services/elwosa.py` und im
Wiki-Hint-Endpoint. Drei Tests die nach dem Datum-Wechsel rot waren
sind wieder gruen.

### Vertagt nach beta.47

- **#616** Verwaiste `stellen_id` in Bewerbungen — braucht Daten-
  Migration ueber bestehende DB
- **#613** Quellen-Migration `manuell` → `linkedin` (URL-Detection +
  Migration-Tool)

### Tests

- 14 neue Tests in `test_v170_beta46_bug_sweep.py` (alle 7 Bugs)
- **1202 / 1202 gruen** + 1 skipped (+14 vs. beta.45)

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.46.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.46.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.45] - 2026-05-09 — Wiki-Snippets als kontextuelle Elwosa-Hints (#623) + Repo-Cleanup

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

User-Idee: Elwosa/Ollama mit dem PBP-Wiki verbinden, damit kontextuelle
Hinweise aus dem Wiki im Sidebar-Chat eingeblendet werden — kleine
Snippets, kein ganzer Artikel.

### ✨ Added — Wiki-Snippet-System (#623)

**Neuer Snippet-Speicher** unter `docs/wiki-snippets/`:
- 16 kuratierte Snippets fuer 8 Page-Routen + 3 globale
- Jede Datei: YAML-Frontmatter (`id`, `page_route`, `wiki_page`, `title`)
  + 1-2-Saetze-Body mit `[link:wiki:Seite|Linktext]`-Markup
- Dokumentation in `docs/wiki-snippets/README.md`

**Backend-Service** `services/wiki_snippets.py`:
- Laedt alle Snippets beim Modul-Import, indexiert nach Route
- `pick_snippet_for_route(route, seen_ids)` mit Anti-Repeat-Logik
- 7-Tage-Pool-Memory damit User nicht dieselbe Linie immer wieder sieht

**Endpoint** `POST /api/wiki/request-hint`:
- Body: `{page: "stellen"}` (siehe `TAB_CONFIG` in App.jsx)
- Drosselung: max **1 Wiki-Hint pro Route pro Tag** (pro Profil)
- Pickt aus Pool exclusiv der heute schon gezeigten IDs
- Postet als `wiki_hint`-Trigger in den Elwosa-Stream
- Validiert Tonfall vor dem Posten — fehlerhafte Snippets werden
  nicht gespeichert

**Frontend-Hook** in `App.jsx`:
- Bei jedem Page-Wechsel (800ms debounce) wird der Endpoint gerufen
- Backend deduppt — kein Spam-Risiko bei Schnell-Klicks
- Snippet erscheint dann im Elwosa-Sidebar-Chat

**Markup-Erweiterung** `[link:wiki:Tab-Stellen|nachlesen]`:
- Frontend-Renderer (in `ElwosaSidebarChat.jsx`) öffnet
  `https://github.com/MadGapun/PBP/wiki/Tab-Stellen` in neuem Tab
- Validator markup-aware: Sprach-DNA-Pruefung greift auf gestripten Text

### 🧹 Changed — Repo-Cleanup: Doku-Files in `docs/`

Damit die README in der GitHub-Datei-Liste schneller sichtbar ist
(weniger Files im Root), wurden 6 reine Doku-Files nach `docs/` verschoben:

- `DOKUMENTATION.md` → `docs/`
- `OPTIMIERUNGEN.md` → `docs/`
- `ROADMAP.md` → `docs/`
- `TESTVERSION.md` → `docs/`
- `ZUSTAND.md` → `docs/`
- `LIESMICH.txt` → `docs/`

`git mv` benutzt — Historie bleibt sauber. Im Root bleiben:
README.md, LICENSE, CHANGELOG.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md,
SECURITY.md (GitHub-Standards), CLAUDE.md, AGENTS.md (Agent-Tools),
INSTALLIEREN.bat/.command, DEINSTALLIEREN.bat, Dashboard starten.bat/
.command (User-Doppelklick), Build-Configs.

### Tests

- 18 neue Tests (`test_v170_beta45_wiki_snippets.py`):
  Loader, Pool-Auswahl, Endpoint-Verhalten (4 Szenarien),
  Per-Route-Per-Tag-Dedup, Markup-Validator, Reload
- **1188 / 1188 gruen** + 1 skipped (+18 vs. beta.44)

### Known Issues

- Wiki-Pflege: 17 Wiki-Seiten existieren bereits, sollten aber gegen
  v1.7-Features (Elwosa, neue Quellen, Lern-System) durchgesehen werden.
  Eigene Pflege-Beta sinnvoll.
- Snippets manuell kuratiert (nicht aus Wiki gefetcht). Bei groeßeren
  Wiki-Aenderungen muessen die Snippets manuell aktualisiert werden.
  Auto-Sync waere ein moegliches Folge-Issue.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.45.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.45.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt.

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.44] - 2026-05-09 — Stellenbeschreibung nachladen: Auto + Per-Klick + MCP (#622)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

User-Beobachtung: Dashboard zeigt *„13 Stellen ohne Beschreibung — Score
ist unzuverlaessig"*. Bisher konnte der User nur manuell pro Stelle den
Browser oeffnen, kopieren und einfuegen. Jetzt drei Wege parallel.

### ✨ Added — Layer A: UI-Plumbing

- Elwosa-Status-Linien `auto_refetch_descriptions` (4 Varianten,
  feuern nach jedem Auto-Refetch-Lauf wenn was passiert ist)
- Elwosa-Tipp-Linien mit `[link:job_filter:missing_desc|...]`-Markup —
  Klick fuehrt zur JobsPage mit aktivem Filter
- Bestehender Dashboard-Card-Button „Oeffnen" funktioniert weiterhin

### ✨ Added — Layer B: Per-Klick-Refetch im Detail-Dialog

- **Neuer Button** im JobsPage-Detail-Dialog (in der Amber-„Beschreibung
  zuerst nachziehen"-Card): **„Beschreibung jetzt nachladen"**
- **Neuer Endpoint** `POST /api/jobs/{hash}/refetch-description`:
  - 1 HTTP-GET auf `job.url` mit User-Agent „PBP/1.7"
  - Nutzt das existierende `fetch_description_from_detail` (JSON-LD
    bevorzugt, dann CSS-Selektoren)
  - Erfolg → `description` in DB, Failure-Counter zuruecksetzen
  - Fehler 404/502 → Failure-Counter +1 (fuer Layer-C-Backoff)
  - Detail-Dialog refresht den Job-Inhalt sofort nach Erfolg
- **Backup-Hinweis** im Card: „Im Browser oeffnen + manuell kopieren"
  als Fallback-Link, plus „Du kannst auch Claude bitten — `stellen-
  beschreibung_nachladen` als Tool"

### ✨ Added — Layer C: Auto-Refetch im Hintergrund

- **Neuer Auto-Engine-Step** `_run_auto_refetch_descriptions(now, max_jobs=8)`
- Verdrahtet in `/api/auto-actions/run` (laeuft mit den anderen Auto-Steps)
- Findet aktive Stellen mit `description IS NULL OR LENGTH(description) < 50`
- **Backoff** ueber `settings.refetch_fail:{hash}`: nach 3 Fehlversuchen
  wird die Stelle nicht mehr probiert
- **Rate-Cap** `max_jobs=8` pro Lauf — bewusst niedrig, kein Massen-Crawl
- Postet zusammenfassende Elwosa-Linie wenn was passiert ist

### ✨ Added — MCP-Tool `stellenbeschreibung_nachladen`

Fuer Claude-Workflow: User sagt „lade Beschreibung fuer Stelle X nach",
Claude ruft das Tool, kriegt Erfolg/Fehler-Status mit Preview zurueck.
Liefert `{status: ok, chars, preview}` oder `{status: fehler, grund}`.

MCP-Tool-Count: 138 → **139**.

### Tests

- 14 neue Tests (`test_v170_beta44_refetch_description.py`)
- Alle httpx-Calls werden via `unittest.mock.patch` gestubbed —
  **keine Live-HTTP-Calls** in der Test-Suite (User-Vorgabe!)
- 1170 / 1170 gruen + 1 skipped

### Wie der Auto-Refetch User-freundlich bleibt

- Max 8 Stellen pro Auto-Engine-Lauf — keine Server-DDoS
- Backoff nach 3 Fehlversuchen — kein endloses Probieren
- User-Agent identifiziert PBP klar (kein Tarn-Crawl)
- Zusammenfassende Elwosa-Linie statt einzelner Spam-Posts

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.44.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.44.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.43] - 2026-05-09 — Komplett-Deinstallation aus der Gefahrenzone (#621)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Folge-Feature zu #620: jetzt wo der Deinstaller funktioniert, kann er
auch direkt aus den **Settings → Gefahrenzone** angestossen werden —
ohne dass der User in den Datei-Explorer muss um `DEINSTALLIEREN.bat`
zu suchen.

### ✨ Added — „PBP komplett deinstallieren"-Card in Gefahrenzone

- Neue vierte Card unter **Settings → Gefahrenzone**
- Bestaetigung per Tippen von `DEINSTALLIEREN`
- Klar sichtbarer Hinweis was **NICHT** mit-deinstalliert wird:
  - **Claude Desktop** (eigenstaendige App von Anthropic)
  - **Ollama** (eigenstaendige App fuer lokale AI)
  - **System-Python** (falls eigene Installation neben PBP existiert)
- Button startet `DEINSTALLIEREN.bat` als detached cmd-Prozess —
  der laeuft in eigenem Konsolen-Fenster und kann den Dashboard-
  Python gleich gefahrlos killen (Schritt [1/7] der .bat)

### ✨ Added — `POST /api/danger/launch-uninstaller`

- Body: `{confirm: "DEINSTALLIEREN"}`
- Falsche/fehlende Bestaetigung → 400
- Nur Windows (auf macOS/Linux 400 mit Hinweis auf shell-Skript)
- Wenn `%LOCALAPPDATA%\BewerbungsAssistent\app\DEINSTALLIEREN.bat`
  fehlt (Dev-Checkout) → 404 mit klarer Meldung
- Spawnt detached subprocess mit `DETACHED_PROCESS | CREATE_NEW_CONSOLE
  | CREATE_NEW_PROCESS_GROUP` — neuer Prozess-Tree, eigenes Fenster

### Tests

- 5 neue Tests (`test_v170_beta43_uninstall_launcher.py`):
  Bestaetigungs-Pflicht, Wrong-Confirm-Block, Non-Windows-Reject,
  404-bei-fehlender-bat, Frontend-Section-vorhanden
- 4 passed + 1 skipped (Non-Windows-Test wird auf Windows uebersprungen)

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.43.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.43.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.42] - 2026-05-09 — Deinstaller-Hotfix: Apps-Liste + AppData-Reste (#620)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.
> Identischer Fix ist auch als Patch-Release **v1.6.10** verfuegbar.

User-Report aus v1.6.9: nach „Deinstallieren" bleibt der **Eintrag in
Windows Apps & Features** stehen, plus der Ordner unter
`%LOCALAPPDATA%\BewerbungsAssistent\` ist noch da.

### 🐛 Fixed — `DEINSTALLIEREN.bat`

**Bug 1 — Self-Deletion-Race:** Beim Aufruf ueber *Apps & Features* lief
die `DEINSTALLIEREN.bat` aus `%LOCALAPPDATA%\BewerbungsAssistent\app\`
und loeschte in Schritt [4] genau diesen Ordner — also sich selbst.
cmd.exe liest .bat-Skripte just-in-time von Disk und brach still ab.
Folge: Schritt [5] (Registry-Eintrag entfernen) feuerte nie.

→ **Self-Relocation am Skript-Anfang:** wenn `BASEDIR == APP_DIR`,
kopiere die .bat nach `%TEMP%\PBP-Deinstaller-XXXX.bat` und starte
von dort neu. Die TEMP-Kopie kann APP_DIR sicher loeschen ohne sich
selbst zu killen.

**Bug 1 Defense-in-Depth:** Reihenfolge umgedreht — **Registry-Eintrag
wird jetzt VOR `rmdir APP_DIR` entfernt**. Sollte die Self-Relocation
in irgendeiner Edge-Case nicht greifen, ist mindestens der prominenteste
User-sichtbare Bug (Apps-Liste) gefixt.

**Bug 2 — `BASE_INSTALL` Parent bleibt:** Der Stamm-Ordner
`%LOCALAPPDATA%\BewerbungsAssistent\` wurde nie entfernt.
→ **`rmdir %BASE_INSTALL%` am Ende** (ohne `/s`-Flag — entfernt nur
wenn leer). Wenn der User die Daten behaelt, bleibt der Ordner mit
den Daten stehen — kein Datenverlust.

### Migration fuer Bestands-User mit v1.6.9 / vorherigen Betas

Wer bereits installiert hat: einfach **drueberinstallieren** mit
v1.7.0-beta.42 (oder v1.6.10 fuer den Stable-Pfad). Der neue Installer
ueberschreibt die `DEINSTALLIEREN.bat` in `%APP_DIR%`. Ab dann funktio-
niert die Deinstallation sauber, auch ueber „Apps & Features".

### Tests

- 5 neue Tests in `test_v170_beta42_deinstaller_fix.py` (Datei-
  Inspektion: Self-Relocation-Stanza vorhanden, Registry vor
  rmdir APP_DIR, BASE_INSTALL-Cleanup nutzt rmdir ohne /s)
- 1152 / 1152 gruen (+5 vs. beta.41)

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.42.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.42.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.41] - 2026-05-09 — Elwosa: Varianz, Markup, Settings-Verdrahtung (#614 + #612)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

User-Test der beta.40: drei Probleme bei Elwosa.

1. Welt-Trigger wie `friday_evening` hatten **nur eine Linie** — bei
   stuendlichem Heartbeat wiederholte Elwosa identisch.
2. Settings `tonfall_modus` und `comment_user_actions` waren **Dekoration**,
   wurden im Picker bzw. Frontend nirgendwo gelesen.
3. Fettdruck-Akzent + klickbare „kurz still sein"-Aktion fehlten.

### ✨ Added — Linien-Pool-Erweiterung (#614)

Welt-Trigger ausgebaut auf 4–8 Linien (vorher 1–3):

| Trigger | vorher | jetzt |
|---|---|---|
| `friday_evening` | 1 | 8 |
| `weekend` | 2 | 6 |
| `monday_morning` | 1 | 5 |
| `late_night` | 2 | 6 |
| `evening` | 2 | 6 |
| `morning` | 3 | 7 |
| `holiday_christmas` | 1 | 4 |
| `holiday_summer` | 1 | 4 |
| `return_after_break` | 2 | 4 |

Mit stilistischer Varianz: ungeduldig-ironisch, nerdig, leise, mit
Rueckfrage-Charakter — alle weiterhin Sprach-DNA-konform.

### ✨ Added — Markup-Support (#614)

- **`**Wort**`-Syntax** rendert als Fettdruck (max. dezent, 1 pro Linie)
- **`[link:type:id|label]`-Syntax** rendert als klickbarer Link:
  - `link:pause:N` → Klick ruft `/api/elwosa/pause` mit `minuten=N`
  - `link:application:hash` → Navigation zur Bewerbung (Frontend-Hook)
  - `link:job:hash` → Navigation zur Stelle
- **Validator markup-aware:** Laenge zaehlt gestrippten Text, verbotene
  Patterns (`!`, `Ihre`, Emojis) werden auch im Bold-/Link-Inhalt erkannt
  → keine Schmuggel-Pfade

Beispiel aus dem `friday_evening`-Pool:
> *„Es ist Wochenende. Falls du in Zeitnot bist und das fertig machen willst — [sag's, ich halte mich raus]"* (klickbar → 2h Pause)

### 🐛 Fixed — Anti-Wiederholung gleicher Tag (#614)

`pick_line()` hat jetzt zwei Filter-Schichten:

1. Nicht in den letzten 7 Tagen verwendet (Fallback: voller Pool)
2. Nicht heute bereits gepostet (Fallback: Schicht 1)

Vorher: einziger 7-Tage-Filter mit Hard-Fallback → wenn der Pool nur eine
Linie hatte, kam die immer wieder. Jetzt: gleicher Tag = exklusiv solange
Auswahl moeglich.

### 🐛 Fixed — `tonfall_modus` jetzt wirksam (#612)

In `services/elwosa.py::can_post_class()`:

- **`aus`** → blockiert alle Klassen (entspricht `enabled=False`)
- **`sachlich`** → blockiert idle/world/tip/easter_egg, nur Status passt
- **`minimal`** → harter Cap **1 Linie pro Tag** ueber alle Klassen
- **`humorvoll`** → unveraendert (Pool-Gewichtung kommt spaeter)

### ✨ Added — Settings-Selbst-Reflektion (#612)

**Neuer Endpoint** `POST /api/elwosa/user-action` mit Body
`{action, target, payload}`. Frontend feuert ihn nach jeder Settings-
Aenderung in der `ElwosaSettingsSection`. Backend mappt auf einen der
neuen `SETTINGS_REFLECTION_LINES`-Pools und postet eine knappe Quittung:

| Aktion | Beispiel-Reflektion |
|---|---|
| Frequenz auf „aktiv" | *„Aktiv. Du moechtest mehr von mir hoeren — riskant, aber bitte."* |
| Tonfall „humorvoll" | *„Mehr Humor. Versuche ich. Britisch unterkuehlt bleibt's trotzdem."* |
| `comment_user_actions` an | *„Auch User-Aktionen kommentieren. Anstrengend fuer dich, anstrengender fuer mich."* |
| Trigger-Klasse aus | *„Trigger-Klasse aus. Verstehe, du brauchst Ruhe an der Stelle."* |

**Bypassed** Cooldown und `tonfall_modus`-Filter — die Reflektion ist
eine direkte User-Quittung und soll auch im sachlichen Modus kommen.
Bei `enabled=False` (Elwosa komplett aus) wird trotzdem geschwiegen.

### Settings-Hook im Frontend

`ElwosaSettingsSection.update()` ruft jetzt zusaetzlich zu `PUT
/api/elwosa/settings` einen `POST /api/elwosa/user-action` mit dem
prominentesten geaenderten Feld. **Throttle:** nur EIN Reflektion-Hook
pro Patch (nicht 4 Linien wenn der Slider 4 Stufen runtergeht).

### Tests

- 26 neue Tests in `test_v170_beta41_elwosa_polish.py`
  (Pool-Groesse, Validator-Markup-Strip, Bold-Akzeptanz,
  Link-Akzeptanz, Bang-im-Bold-Block, Hoeflichkeits-im-Link-Block,
  Same-Day-Anti-Repeat, tonfall-modus-Verdrahtung,
  Settings-Reflektion-API, Bestaendigkeit der neuen Linien gegen
  Tonfall-Waechter)
- Bestehende 31 Tests in `test_v170_beta37_elwosa.py` weiterhin gruen
- Tonfall-Waechter `test_all_pool_lines_pass_validator` deckt jetzt
  ~50 zusaetzliche Linien ab

### Known Issues

- `tonfall_modus="humorvoll"` lockert noch keine Limits (Easter-Eggs
  bevorzugen kommt mit beta.42)
- Auto-Scroll + adaptive Hoehe + Aktions-Link-Navigation (#611) sind
  separat geplant fuer beta.42 — heute nur die Markup-Render-Foundation
- Issue #613 (Quellen-Migration: source='manuell' enthaelt eigentlich
  LinkedIn) bekommt eine eigene Beta wegen Daten-Migration

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.41.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.41.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.40] - 2026-05-07 — Elwosa-Hooks: Bot reagiert jetzt wirklich (#609 Hot-Fix)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

User-Test-Finding: Elwosa hat in einer 3,5h-Session **gar nichts** kommentiert
trotz laufender Jobsuche. Konzeptioneller Fehler — Elwosa sprang nur per
Auto-Engine an, der zudem selten lief. **Keine direkten Hooks** in die
laufenden Aktionen.

### 🐛 Fixed — #609 Hooks an allen wichtigen Aktions-Quellen

Direkte `elwosa.speak()`-Calls in:

- **`/api/jobsuche/start`** → `llm_task_running` mit Quellen-Anzahl
  („Jobsuche laeuft auf {count} Portalen. Mach was Vernuenftiges, ich melde mich.")
- **`_run_auto_classify_emails`** → `mail_classify` mit Anzahl klassifizierter Mails
- **`_run_auto_classify_documents`** → `mail_classify` analog
- **`_run_extract_contacts`** → `auto_dismiss_ran` mit Anzahl extrahierter Kontakte
- **`bewerbung_erstellen`** → `bewerbung_angelegt` mit Firmenname
- **`bewerbung_status_aendern`** → trigger_map auf:
  - `abgelehnt` → `absage`-Linien
  - `eingangsbestaetigung` → `eingangsbestaetigung`-Linien
  - `interview` / `zweitgespraech` → `interview_einladung`-Linien
  - `angenommen` → `angenommen`-Linien (*„Endlich. Ich war kurz davor denen selbst zu schreiben."*)

### ✨ Added — Heartbeat-Endpoint + Welcome

- **`POST /api/elwosa/heartbeat`**: Frontend-Heartbeat fuer:
  - **Welcome-Nachricht** (1x ever bei erster Aktivierung)
  - **Welt-Trigger** (morning/evening/weekend/...) basierend auf Tageszeit
- **Frontend** ruft Heartbeat:
  - 1x beim Mount der ElwosaSidebarChat-Component
  - Alle 60 Minuten
  - Bei `visibilitychange` (Tab wird wieder sichtbar)

### ✨ Added — Linien-Pool-Erweiterung

- Neue STATUS_CHANGE_LINES `bewerbung_angelegt` (3 Linien)
- Neue STATUS_LINES `llm_task_running` (4 Linien fuer Jobsuche-Start)

### Tests

- `tests/test_v170_beta40_elwosa_hooks.py`: 11 neue Tests
- **1119 Tests gesamt, alle gruen**

### Hilfs-Funktion

`_elwosa_speak_safe()` in dashboard.py kapselt den `speak()`-Aufruf so,
dass Elwosa-Probleme NIE die eigentliche Aktion blockieren.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.40.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.40.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.39] - 2026-05-07 — Kontakte-Reife: Kategorien mit Farben + LLM-Auto-Import (#606 + #608)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Zwei groesse Kontakte-Issues gebuendelt — **Kategorien** als eigene
Entity mit Farben + **LLM-basierter Auto-Import** aus Bestand und
laufenden Bewerbungen.

### ✨ Added — #608 Kontakt-Kategorien

- **Schema v41 → v42**: `contact_categories` (id, name, slug, color,
  sort_order, is_system) + `contacts.is_pending` + `contacts.extracted_from`
- **7 Default-Kategorien** mit handverlesenen Farben:
  Recruiter (Teal), HR (Blue), Ansprechpartner (Purple), Endkunde (Amber),
  Vermittler (Pink), Referenz (Sky), Sonstiges (Gray)
- **16-Farben-Palette** in `services/contact_colors.py` mit Auto-Vergabe
  beim Anlegen ohne explizite Farbe
- **5 neue API-Endpoints**:
  `GET/POST /api/contacts/categories`, `PUT/DELETE /api/contacts/categories/{id}`,
  `POST /api/contacts/categories/migrate-tags`
- **4 neue MCP-Tools**: `kontakt_kategorien_auflisten`,
  `kontakt_kategorie_anlegen` (mit/ohne Farbe), `kontakt_kategorie_bearbeiten`,
  `kontakt_kategorie_loeschen`
- **Loesch-Schutz**: `is_system=1` und Kategorien mit zugewiesenen Kontakten
  koennen nicht geloescht werden
- **Migration legacy tags**: `migrate_legacy_tags_to_categories()` promoted
  bestehende CSV-Tag-Strings zu Kategorien mit Auto-Farbe

### ✨ Added — #606 LLM-Auto-Import

- **Neuer LLM-Task `EXTRACT_CONTACTS`** in `llm_service.py`:
  - Pipe-Format: `NAME | EMAIL | KATEGORIE | ROLLE | CONFIDENCE`
  - Max 5 Kontakte pro Aufruf
  - Confidence < 0.5 wird verworfen (nur sichere Extraktionen)
- **MCP-Tool `kontakte_aus_bestand_importieren(dry_run=True)`** als
  One-Shot-Migration: scannt alle Bewerbungen ohne `extracted_from`-Marker
  und legt LLM-extrahierte Kontakte als pending an
- **Auto-Engine-Step `_run_extract_contacts`** als 8. Schritt — laeuft
  taeglich auf neuen Bewerbungen
- **`is_pending`-Workflow**: extrahierte Kontakte sind initial unsichtbar
  in der Liste, User genehmigt oder verwirft sie ueber Banner
- **Idempotent**: Bewerbungen mit existing `extracted_from='application:<id>'`
  Kontakt werden uebersprungen
- **3 neue API-Endpoints**: `GET /api/contacts/pending`,
  `POST /api/contacts/pending/{id}/approve`, `DELETE /api/contacts/pending/{id}`

### 🎨 Frontend

- **`<RoleChip>`** liest jetzt Farben dynamisch aus
  `/api/contacts/categories` (Cache + Window-Event fuer Live-Refresh)
- **`<PendingContactsBanner>`** in der Kontakte-Page: Amber-Banner mit
  Akzeptieren/Verwerfen pro pending-Kontakt
- **`<CategoryManagementSection>`** als ausklappbare Card:
  - Liste mit Color-Picker (HTML5 `<input type="color">`)
  - Inline-Edit fuer Name (onBlur speichert)
  - Anzahl Kontakte pro Kategorie sichtbar
  - „+ Neue Kategorie"-Input + Auto-Farb-Vergabe vom Backend
  - Loeschen-Knopf nur fuer non-System-Kategorien

### MCP-Stand

- **138 Tools** (von 133, +5)
- **23 Prompts** (unveraendert)

### Tests

- `tests/test_v170_beta39_kontakte.py`: 34 neue Tests
- **1108 Tests gesamt, alle gruen**

### Bezug zum Lern-System (#594)

Auto-Import nutzt die bestehende Local-LLM-Infrastruktur. Wenn der User
die lokale AI ausschaltet, laeuft der Auto-Engine-Step entsprechend
nicht — manuelle Anlage funktioniert wie bisher.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.39.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.39.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.38] - 2026-05-07 — User-Test-Findings: Score-Buckets + Elwosa-Polish + Installer-Fix

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Drei User-Test-Findings vom Abend gebuendelt.

### 🐛 Fixed — #607 Score-Buckets

Bewerbungsbericht Abschnitt 5 hatte zwei Probleme:
- Statische Aufteilung `0/1-3/4-6/7-9/10+` aus alter Scoring-Aera, in der heute praktisch alles im `10+`-Bucket landet
- Sortierung nach Anzahl statt Score-Wert (sah aus wie `0 / 1-3 / 10+ / 4-6 / 7-9`)

**Fix:** `_make_score_buckets(max_score)`-Funktion erzeugt dynamisch
5–6 Buckets aus dem Max-Score (auf 5er-Schritte gerundet, niedriger
Score zuerst). Bei Max ≤ 10 Fallback auf alte Aufteilung. Tabelle +
Chart sortieren jetzt nach Score-Wert. Balken-Breite proportional zum
Max-Count, nicht absolut.

### ✨ Added/Fixed — #601 Elwosa-Polish

- **`mood`-Anzeige im Sidebar-Header entfernt** (war Insider-Info ohne
  Mehrwert: „beschuetzend" hat User verwirrt)
- **Zahnrad-Icon** rechts neben dem Header → Klick fuehrt direkt zu
  *Einstellungen → Lokale KI → Elwosa-Section*
- **Power-User-Optionen** als ausklappbare Section in den Settings:
  - **Cooldown-Slider** (10s–300s, Default 90s)
  - **Toggle „Auch manuelle User-Aktionen kommentieren"** (Setup
    fuer #601 Continuous-Comment-Modus, Hooks kommen separat)
  - **Trigger-Klassen einzeln aus-/einschalten**: Idle / Welt-Bezug /
    Tipps & Tricks / Easter Eggs
  - **Frequenz `unbegrenzt`** als 4. Option — kein Idle/Welt/Tipp-Limit
    fuer Power-User
- Backend respektiert alle neuen Settings in `can_post_class()` +
  `is_in_cooldown()`

### 🐛 Fixed — #600 Installer-Autostart

- **macOS** (`INSTALLIEREN.command`): hatte vorher KEIN Auto-Browser-
  Open. Jetzt: Dashboard wird im Hintergrund gestartet, Health-Check
  bis Port 8200 antwortet (max 30s), `open` oeffnet den Browser
- **Linux** (`installer/install.sh`): analog mit `xdg-open`-Fallback,
  funktioniert mit und ohne Desktop-Environment
- **Windows** (`INSTALLIEREN.bat`): Browser wird jetzt AUCH geoeffnet
  wenn Health-Check fehlschlaegt — damit der Update-Pfad funktioniert,
  bei dem eine alte Instanz noch auf dem Port haengt

### Tests

- `tests/test_v170_beta38_findings.py`: 19 neue Tests
- **1074 Tests gesamt, alle gruen.**

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.38.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.38.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.37] - 2026-05-07 — Elwosa: Live-Statusanzeige der lokalen AI mit Persönlichkeit (#599)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

**Highlight-Feature** des v1.7-Sprints. Elwosa ist die Live-Statusanzeige
der lokalen AI in der linken Sidebar — mit eigener Persoenlichkeit
(geschlechtsfrei, britisch ironisch, lakonisch). Kommentiert was die
lokale AI gerade tut, gibt Tipps zu Claude und PBP.

### ✨ Added — Elwosa Backend

- **Schema v40 → v41**: `elwosa_messages` (Stream pro Profil) +
  `elwosa_pending_lines` (Claude-Vorschlaege)
- **`services/elwosa_lines.py`** mit ~140 Linien aus
  `docs/elwosa-character.md`, organisiert nach 9 Profil-Cluster +
  Status/Welt/Tipp/Easter-Egg-Pools
- **`services/elwosa.py`** mit:
  - **Sprach-DNA-Validator** (verbietet Ausrufezeichen, Emojis,
    Hoeflichkeits-`Ihre/Ihnen`, Anrede mit „Sie")
  - Trigger-Engine + Auswahl-Algorithmus (seen-Set 7 Tage)
  - Anti-Spam: 90s-Cooldown, frequenz-abhaengige Idle/Welt/Tipp-Limits
  - **Status-Trigger UNBEGRENZT** — Elwosa schweigt nicht wenn die AI
    arbeitet (Status-Anzeige-Charakter)
  - Stimmungs-Drift (melancholisch / beschuetzend / aufmerksam / standard)
- **Auto-Engine-Step `_run_elwosa_speak`** (7. Schritt im taeglichen Lauf)

### ✨ Added — MCP-Bridge (Claude als Uebersetzer)

User können nicht direkt mit Elwosa schreiben — aber Claude kann es:

- `elwosa_lesen` — Verlauf abrufen
- `elwosa_schreiben` — Im Namen von Elwosa posten (Tonfall validiert!)
- `elwosa_pause` — Schweigen anordnen (1 min - 24 h)
- `elwosa_tonfall` — `standard`/`sachlich`/`humorvoll`/`minimal`/`aus`
- `elwosa_linie_vorschlagen` — Pool erweitern, User genehmigt in Settings
- `elwosa_status` — Stimmung + Trigger-State

Plus **5 neue MCP-Prompts** in `prompts.py`: `elwosa_status_anzeigen`,
`elwosa_pause_anfordern`, `elwosa_antworten`, `elwosa_linie_lehren`,
`elwosa_zurueckholen` — kommen automatisch in der Hilfe-Uebersicht.

### ✨ Added — API + Settings

- **9 neue API-Endpoints** unter `/api/elwosa/*`
- **5 neue Profile-Settings**: enabled, frequency (ruhig/standard/aktiv),
  tonfall_modus, triggers_disabled, paused_until

### 🎨 Frontend

- **`<ElwosaSidebarChat />`** in der linken Sidebar:
  - Avatar Teal-Kreis mit „E", Header „⊙ Elwosa"
  - Crossfade beim Polling (alle 30s)
  - **Klickbare Code-Spans** in Tipps → Clipboard + Toast „kopiert"
  - 👁 ausblenden (30 min Session-Hide)
  - „⋯" Pause/Verlauf-loeschen
  - Bei Sidebar-Collapsed: nur Avatar mit Pulse + Hover-Overlay
- **`<ElwosaSettingsSection />`** im „Lokale KI"-Tab:
  - Aktivierung, Frequenz-Slider, Tonfall-Modus
  - Pending-Linien-Genehmigung (von Claude vorgeschlagen)
  - Pause-Zustand sichtbar + zurueckholbar

### 🐛 Fixed — Sidebar-Sub-Navigation

Aktueller Code in `App.jsx` zeigte nur 6 von 8 Settings-Tabs in der
Sidebar. **Fix mit drin**: `Lokale KI` und `Automatik` sind jetzt
sichtbar — User muss nicht mehr ueber Workarounds dahin navigieren.

### Tests

- `tests/test_v170_beta37_elwosa.py`: 31 neue Tests
- **Tonfall-Waechter-Test**: alle ~140 Linien im Pool werden gegen die
  Sprach-DNA validiert
- **1057 Tests gesamt, alle gruen.**

### MCP-Stand

- **133 Tools** (von 127, +6 Elwosa)
- **23 Prompts** (von 18, +5 Elwosa-Bridge)

### Doku

- **`docs/elwosa-character.md`** ist die Source of Truth fuer den
  Linien-Pool. Bei Aenderungen IMMER beide Dateien synchron halten
  (Doku + `services/elwosa_lines.py`).

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.37.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.37.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.36] - 2026-05-07 — Workday-DAX + Student-Cluster + Recommendations-UI (#590 fertig)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Letzte Stufe von Issue #590 — alle Aufgaben (A, B, C) sind damit umgesetzt:

### ✨ Added — B.4 Student-Cluster (3 neue Adapter)

- **Praktikum.de** RSS — groesste DACH-Plattform fuer Praktika und
  Werkstudenten, Suchwort-Parameter im RSS
- **StudentJob.de** RSS — Studenten- und Werkstudenten-Stellen
- **Berufsstart.de** RSS — Karriere-Einstieg fuer Studenten und Absolventen
  (Trainee, Junior, Praktika, Direkteinstieg)

### ✨ Added — B.3 Workday-DAX-Cluster

- **Workday-Cluster** mit kuratierter Liste 10 grosser DACH-Konzerne:
  <FIRMA>, SAP, <FIRMA>, Continental, ZF, Schaeffler, Knorr-Bremse,
  KraussMaffei, Heidelberg, Vitesco
- **Public Workday-API** `/wday/cxs/{tenant}/{site}/jobs` per POST
- User-Erweiterbar via `workday_firmen`-Suchkriterium
  (Format: `'<FIRMA>|<FIRMA>|wd1|external'`)

### 🎨 Added — Frontend Recommendations-Card

- **Neuer `RecommendedSourcesCard`** im Quellen-Tab der Einstellungen:
  - Zeigt erkannten Profil-Typ (`student`, `service`, `tech_senior`, …)
    + Confidence + transparente Begruendung
  - Listet empfohlene Quellen mit ✓/+ Badge (aktiv vs. fehlend)
  - **„X fehlende Quellen aktivieren"-Button** — One-Click-Aktivierung
    aller Empfehlungen, die noch nicht aktiv sind
  - User kann jederzeit einzelne Quellen wieder abschalten

### Cluster-Updates

- **Student-Cluster** an erster Stelle: praktikum_de, studentjob, berufsstart
- **Tech-Senior**: + workday_dax als Konzern-Quelle
- **Engineering-Senior**: workday_dax an erster Stelle
- **Executive**: + workday_dax fuer Konzern-Fuehrungspositionen

### Tests

- `tests/test_v170_beta36_workday_student.py`: 13 neue Tests
- **1026 Tests gesamt, alle gruen.**

### #590 Stuetzpfeiler abgeschlossen

| Aufgabe | Stand |
|---|---|
| **A** Universelle Quellen | ✓ Personio, Workable, Meinestadt (beta.34) |
| **B.1** Profile-Detection | ✓ 9 Cluster (beta.35) |
| **B.2** Cluster-Definitionen | ✓ + Recommendations-API + UI (beta.35/36) |
| **B.3** Workday-DAX-Cluster | ✓ 10 Konzerne (beta.36) |
| **B.4** Student-Cluster | ✓ Praktikum.de + StudentJob + Berufsstart (beta.36) |
| **B.5** Tech-Remote-Cluster | ✓ Himalayas + Remotive + RemoteOK (beta.35) |
| **C.1** Auto-Reactivate | ✓ 24h/48h/72h/168h Backoff (beta.33) |
| **C.2** Retry-After (HTTP-429) | ✓ (beta.33) |
| **C.3** Health-Score-UI | ✓ ScraperHealthCard (beta.33) |
| **C.4** Quellen-Rotation | offen (kein Adapter-Schutz, eigenes Issue empfohlen) |

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.36.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.36.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.35] - 2026-05-07 — Profile-Cluster + Tech-Remote (#590 Aufgabe B.1+B.2+B.5)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Aufgabe B von #590: PBP erkennt jetzt automatisch den Profil-Typ und
empfiehlt passende Quellen-Cluster. Plus drei neue Tech-Remote-Quellen.

### ✨ Added — Profile-Detection & Cluster-Empfehlung

- **Neuer Service** `services/profile_classifier.py`:
  - `detect_profile_type(profile)` — Heuristik, klassifiziert in
    `student / service / trade / tech_junior / tech_senior /
    engineering_senior / freelance / executive / mixed`
  - Bewertet aktuelle Position, Skills, Berufserfahrung,
    laufendes Studium
  - Liefert `confidence` + `reasons` (transparent fuer den User)
- **9 Quellen-Cluster** vordefiniert. Beispiele:
  - **service**: bundesagentur, meinestadt, personio, jobspy_indeed, kimeta
  - **trade**: bundesagentur, meinestadt, personio, kimeta
  - **tech_senior**: jobspy_linkedin, greenhouse, workable, personio,
    himalayas, remotive, remoteok, jobspy_indeed
  - **freelance**: freelance_de, freelancermap, gulp, solcom, <FIRMA>
- **Neuer API-Endpoint** `GET /api/profile/recommended-sources`:
  liefert Profil-Typ, Empfehlungs-Liste + Begruendung. Frontend
  kann das fuer „Empfohlene Quellen aktivieren?"-Dialog nutzen.

### ✨ Added — Tech-Remote-Cluster (B.5)

Drei neue Quellen, alle Public-API ohne Auth:

- **Himalayas** — `https://himalayas.app/jobs/api?country=DE` —
  Remote-only Aggregator mit DACH-Filter
- **Remotive** — `https://remotive.com/api/remote-jobs` —
  kuratierter Remote-Job-Aggregator, Suchstring-Parameter
- **RemoteOK** — `https://remoteok.com/api` —
  englischsprachiger Remote-Aggregator (erstes Element ist Metadaten)

### Profil-Typ-Reichweite

| Zielgruppe | Cluster-Quellen |
|---|---|
| Student / Werkstudent | bundesagentur, kimeta, personio, meinestadt, arbeitnow |
| Service | bundesagentur, meinestadt, personio, jobspy_indeed, kimeta |
| Handwerk | bundesagentur, meinestadt, personio, kimeta |
| Tech-Junior | jobspy_indeed, jobspy_linkedin, arbeitnow, **himalayas, remotive, remoteok**, workable, personio, greenhouse |
| Tech-Senior | jobspy_linkedin, greenhouse, workable, personio, **himalayas, remotive, remoteok**, jobspy_indeed |
| Engineering-Senior | jobspy_linkedin, ingenieur_de, personio, workable, stellenanzeigen_de, jobspy_indeed, <FIRMA>, <FIRMA> |
| Freelance | freelance_de, freelancermap, gulp, solcom, <FIRMA> |
| Executive | jobspy_linkedin, personio, workable, greenhouse |

### Tests

- `tests/test_v170_beta35_profile_cluster.py`: 19 neue Tests
- **1013 Tests gesamt, alle gruen** — vierstellig erreicht.

### Hinweis

`PROFILE_TYPE_CLUSTERS` referenziert NUR Quellen, die in
`SOURCE_REGISTRY` existieren — neuer Sicherheits-Test verhindert
Ghost-Quellen.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.35.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.35.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.34] - 2026-05-07 — Universelle Quellen (#590 Aufgabe A)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Aufgabe A des #590-Stuetzpfeilers: drei neue Quellen, die Stellen ueber
**alle Profil-Typen** liefern — nicht nur fuer High-Performer (User-
Vorgabe: „Studenten oder Kassiererin oder oder oder...").

### ✨ Added — Personio

- Public XML-Feed `https://{firma}.jobs.personio.de/xml`
- DACH-spezifischer ATS, im KMU sehr verbreitet
- Stellen quer durch Branchen + Skill-Level (Azubi bis Geschaeftsfuehrer)
- Kuratierte Default-Liste (11 Firmen) + User-eigene `personio_firmen`
- Filter auf Keywords + Region, Mapping auf festanstellung/freelance/teilzeit/praktikum

### ✨ Added — Workable

- Public Widget API `https://apply.workable.com/api/v1/widget/accounts/{firma}`
- Internationaler ATS, viele KMU-Kunden mit DACH-Stellen
- Mid-Level breit gestreut, auch nicht-Tech
- Kuratierte Default-Liste (8 Firmen) + User-eigene `workable_firmen`

### ✨ Added — meinestadt.de (Regional)

- RSS-Feed pro Stadt `https://www.meinestadt.de/{stadt}/jobs/rss?w={kw}`
- **Schwerpunkt Service-, Trade- und Pflege-Berufe** (Kassierer, Hotel,
  Gastro, Pflege, Handwerk) — schliesst die Luecke zu JobSpy/LinkedIn
  fuer nicht-Tech
- Region-zu-Slug-Mapping fuer 19 DACH-Staedte (Hamburg, Berlin, Muenchen,
  Koeln, Frankfurt, Stuttgart, Duesseldorf, Dortmund, Essen, Leipzig,
  Bremen, Dresden, Hannover, Nuernberg, Duisburg, Bochum, ...)
- Wenn Region nicht im Mapping: Quelle wird sauber uebersprungen
  statt 404-Spam

### Tests

- `tests/test_v170_beta34_universal_quellen.py`: 13 neue Tests (mit
  HTTP-Mocking, kein Netz-Zugriff im Test)
- **994 Tests gesamt, alle gruen.**

### Profil-Typ-Reichweite

| Zielgruppe | Vorher | Jetzt |
|---|---|---|
| Service (Kassierer, Pflege, Gastro) | Bundesagentur, Indeed | + meinestadt, personio |
| Handwerk | Bundesagentur | + meinestadt |
| KMU-Mid-Level (alle Branchen) | LinkedIn (eingeschraenkt) | + personio, workable |
| Student/Werkstudent | kimeta | + personio (intern-Schedule) |

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.34.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.34.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.33] - 2026-05-07 — Scraper-Robustheit-Upgrade (#590 Aufgabe C)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Aufgabe C des #590-Stuetzpfeilers: Scraper sollen sich selbst heilen
und nicht still leiden, wenn ein Portal kurzzeitig zickt.

### ✨ Added — Auto-Reactivate-Mechanik

- **Schema v39 → v40**: `scraper_health` bekommt `reactivate_at`,
  `reactivate_attempt`, `retry_after`.
- **Bei Auto-Deaktivierung** (n stille Laeufe in Folge) wird ein
  Probe-Run nach 24h geplant. Bei wiederholtem Fail: Backoff-Stufen
  **24h → 48h → 72h → 168h** (1 Woche).
- **Bei OK-Run**: alle Reactivate-Felder werden geleert + Scraper
  reaktiviert. Selbstheilung ohne User-Klick.
- **Manuelles Toggle uebersteuert** die Heuristik (clear all probe state).

### ✨ Added — HTTP-429 Retry-After-Respect

- Adapter koennen `set_scraper_retry_after(name, iso)` setzen wenn ein
  Portal `429 Too Many Requests` mit `Retry-After`-Header schickt.
- `is_scraper_held_by_retry_after(name)` gibt den Block-Zeitpunkt
  zurueck wenn er in der Zukunft liegt — sonst None.

### ✨ Added — Health-Score UI

- Neuer **`ScraperHealthCard`** im Quellen-Tab der Einstellungen:
  - Erfolgsquote pro Scraper (auf Basis total_runs/total_successes)
  - Status-Dots (OK / Warnung / Stumm / Probe geplant / Aus)
  - Letzter Lauf, Anzahl Fehler/Stille, Probe-Run-Countdown,
    Retry-After-Countdown
  - „Jetzt reaktivieren" / „Deaktivieren"-Buttons pro Scraper
- **Auto-Engine-6.-Schritt** `_run_scraper_probe` listet faellige
  Probe-Runs in `/api/auto-actions/run`.

### ✨ Added — API-Endpoints

- `GET /api/scraper-health/probes-due` — Liste der faelligen Probe-Runs
- `POST /api/scraper-health/{name}/probe-result` — Adapter meldet
  `{success: true|false}`
- `POST /api/scraper-health/{name}/retry-after` — Adapter setzt
  Retry-After-Wert

### Tests

- `tests/test_v170_beta33_robustheit.py`: 16 neue Tests
- **981 Tests gesamt, alle gruen.**

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.33.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.33.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.32] - 2026-05-07 — Stellenbeschreibung-Trennung + Portal-Such-Profile

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Zwei Issues, gebuendelt:

### 🐛 Fixed — #588 Stellenbeschreibung sauber trennen

- **Wurzel-Bug**: `bewerbung_erstellen` schrieb `notes` als Fallback in
  `jobs.description` wenn keine `stellenbeschreibung` mitgegeben wurde.
  Dadurch landeten Recherche-Notizen ("Vermittler <FIRMA>, Endkunde-
  Kandidaten Benteler/CLAAS") als Stellenbeschreibung in der DB und
  haben downstream alle Tools verschmutzt (Anschreiben, Fit-Analyse).
- **Fix**: Notes-Fallback entfernt — wenn keine Stellenbeschreibung
  uebergeben wird, bleibt `description` leer.
- **Snapshot-Mechanik**: `applications.description_snapshot` wird jetzt
  beim Anlegen automatisch befuellt (aus jobs.description ODER explizit
  uebergebener stellenbeschreibung) — eingefroren und read-mostly.
- **`bewerbung_bearbeiten(stellenbeschreibung_original=...)`**: neuer
  Parameter zum nachtraeglichen Setzen des Originalwortlauts.
- **`get_application`**: Stellenbeschreibung wird zuerst aus
  description_snapshot gelesen, nur als Fallback aus jobs.description.

### ✨ Added — #564 Portal-spezifische Such-Profile

LinkedIn/StepStone/XING brauchen andere Suchbegriffe als die naiven
`keywords_muss`. LinkedIn z.B. matcht generisches `PLM` mit ~90% Muell,
und Phrase-Match `"PLM Architect"` liefert 0 Treffer. Diese Lessons
landen jetzt in einer DB-Tabelle.

- **Schema v38 → v39**: neue Tabelle `portal_search_profiles`
- **DB-Helpers**: `get_portal_search_profile`, `update_portal_search_profile`,
  `list_portal_search_profiles`
- **3 neue MCP-Tools**:
  - `suchprofil_lesen(portal)` — Chrome-Extension liest VOR jeder Suche
  - `suchprofil_aktualisieren(portal, primaere_suchen, ...)` — Lessons pflegen
  - `suchprofile_auflisten()` — Uebersicht aller Profile
- **LinkedIn-Default-Profil** mit den gesammelten Lessons:
  - Primaer: `PDM` (Branchen-Filter), `PLM Berater`, `Product Lifecycle Management`
  - Sekundaer: `PLM` ZWINGEND mit Branchen-Filter
  - Nicht verwenden: `PLM Architect`/`PLM Manager` (Phrase-Match=0), `PRO.FILE` (Produktname)

### Tests

- `tests/test_v170_beta32_findings.py`: 12 neue Tests
- **965 Tests gesamt, alle gruen.**

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.32.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.32.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.31] - 2026-05-07 — User-Test-Findings: Stellen-Detail + Bericht-Polish

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Vier User-Test-Findings vom heutigen Tag, gebuendelt:

### 🐛 Fixed

- **#595 — Stellen-Detail leer wenn `is_active=0`**: Wenn eine Bewerbung
  auf eine Stelle verlinkt, die wegen `bewerbung_erstellt` aussortiert
  wurde, war die Detail-Ansicht leer.
  - Neuer Endpoint **`GET /api/jobs/{hash}`** liefert Stellen-Details
    unabhaengig von `is_active`
  - Neue Component **`InlineJobDetailModal`** in `ApplicationsPage` —
    Klick auf den Stellen-Hash oeffnet ein Read-Only-Modal mit
    Hinweis "Diese Stelle ist aussortiert"
- **#596 Bug 1 — Eigenname als Keyword**: Profil-Vorname/Nachname werden
  jetzt aus der Keyword-Extraktion gefiltert (vorher tauchte „markus 12x"
  als Keyword auf, weil er in eigenen Anschreiben/Notizen vorkommt).
- **#596 Bug 2 — `???`-Zeile in PDF**: Tokens, die latin-1 nicht
  darstellen kann (Emoji, CJK), werden ausgelassen statt als `???`
  ausgegeben.
- **#596 Bug 3 — `PDM` fehlt**: Tokenisierung umgestellt von `text.split()`
  auf `re.findall(r"[a-zäöüß]{3,}", text)` — splittet jetzt sauber
  zwischen Slashes/Bindestrichen, sodass „PDM/PLM" als zwei separate
  Tokens erkannt wird.

### ✨ Added — Bewerbungsbericht

- **#597 — Abschnitt „12b. Dokumente pro Bewerbung"**: Aufwands-
  Indikator pro Bewerbung. Kategorien: einfach (1 Doku) / standard (2-3) /
  aufwaendig (4+). Pro Bewerbung Tabelle mit Anzahl Lebenslaeufen,
  Anschreiben, Zeugnissen, Mails, Sonstiges.
- **#598 — Abschnitt 12 zeigt jetzt Volumen statt nur „letzte Treffer"**:
  Tabelle mit Gefunden / Aktiv / Aussortiert / Beworben / Konversion pro
  Quelle. Macht klar welche Quelle wirklich produktiv ist.
- **#598 — Klare Abgrenzung zwischen Abschnitt 3 und 12**: jeder Abschnitt
  hat jetzt einen Hinweis-Text.
  - Abschnitt 3 = **Qualitaet** pro Quelle (Erfolgsquote)
  - Abschnitt 12 = **Volumen** pro Quelle (Gesamttreffer)

### Tests

- `tests/test_v170_beta31_user_test_findings.py`: 13 neue Tests
- **953 Tests gesamt, alle gruen.**

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.31.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.31.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.30] - 2026-05-07 — Lern-System Stufe 5: Telemetrie-Sharing (opt-in, wochenweise)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Stufe 5 von #594 schliesst das Lern-System ab. User-Vorgaben strikt
umgesetzt: **Default OFF**, **wochenweise** (nicht taeglich), **konfigurierbar**
(0 / 7 / 14 / 30 Tage), **abschaltbar**, Mail an `PBP-Service@Elwosa.de`,
**nichts geht automatisch raus** — der User klickt mailto-Link und sieht
die volle Vorschau bevor irgendetwas passiert.

### ✨ Added — Telemetrie-Sharing-Engine

- **DB-Helper:** `get_telemetry_settings()`, `set_telemetry_settings()`,
  `mark_telemetry_shared()`. 0 ist eine valide explizite Wahl
  ("nie automatisch") — kein silentes Fallback auf Default.
- **Trigger-Logik** `_telemetry_should_trigger()`:
  1. Nur wenn `enabled=True`
  2. Nur wenn `interval_days` seit letztem Share vergangen
  3. Nur wenn signifikante Insights vorliegen
     (`observed_count >= 5` ODER `score >= 0.8`) — One-Off-Hinweise
     landen NICHT im Sharing
- **Mail-Generator** `_format_telemetry_mail()` — Plain-Text damit der
  User vor dem Senden lesen kann was rausgeht. Privacy-Garantie:
  - KEINE Profil-Daten (kein Name, Email, Skills, Position)
  - KEINE Job-Daten (keine Titel, Firmen)
  - KEINE Domain-Inhalte (keine Bewerbungs-Notes, Anschreiben)
  - NUR aggregierte Zahlen + abstrahierte Insight-Titel/Empfehlung
- **API-Endpoints:**
  - `GET /api/telemetry/settings`
  - `PUT /api/telemetry/settings` (`enabled`, `interval_days`)
  - `GET /api/telemetry/preview` — User MUSS Vorschau sehen koennen
  - `POST /api/telemetry/mark-shared` — wird vom Frontend aufgerufen
    NACHDEM der User die Mail tatsaechlich abgeschickt hat

### 🎨 Frontend — `TelemetrySharingCard`

- In *Einstellungen → Datenschutz* unter dem Lern-System-Card.
- Toggle, Intervall-Selector (`Nie automatisch / Wochenweise / 14 Tage / Monatlich`)
- Vorschau-Block mit Empfaenger, Subject, Body (scrollbar, max-h-64)
- "In Mail-Client oeffnen" — generiert `mailto:`-Link mit vorausgefuelltem
  Subject + Body + Empfaenger
- Nichts geht automatisch raus, alles transparent

### Tests

- `tests/test_v170_beta30_telemetrie.py`: 18 neue Tests
- **940 Tests gesamt, alle gruen.**

### Stufenplan-Fortschritt — abgeschlossen

- [x] Stufe 1: Foundation — beta.26
- [x] Stufe 2: Aggregation + Recap-Card — beta.27
- [x] Stufe 3: LLM-Pattern-Analyse + Korrektur-Loop + adaptive Prompts — beta.28
- [x] Stufe 4: Adaptive UI — beta.29
- [x] Stufe 5: Telemetrie-Sharing — beta.30

Issue #594 ist mit beta.30 vollstaendig umgesetzt.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.30.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.30.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.29] - 2026-05-07 — Lern-System Stufe 4: Adaptive UI

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Stufe 4 von #594 — die LLM-Erkenntnisse aus Stufe 3 finden jetzt direkt
auf der jeweiligen Seite ihren Weg zum User: kleine, dezente
Hint-Banner mit „Vorschlag anwenden" / „Nicht mehr anzeigen".

### ✨ Added — Adaptive Hints

- **Heuristische Page-Zuordnung im LLM-Parser**: jeder Insight bekommt
  ein `scope` (`page:stellen` / `page:bewerbungen` / `page:profil` /
  `page:kontakte` / `page:einstellungen` / `page:dashboard` / `global`),
  abgeleitet aus Titel + Empfehlung + Kind.
- **Neuer Endpoint** `GET /api/learning/hints?page=<id>&limit=2`
  liefert nur die Insights, die zur aktuellen Seite passen.
- **`AdaptiveHintBanner`-Component** (Frontend):
  - Holt `/api/learning/hints?page=<page>` beim Mount
  - Zeigt max 2 Hints pro Seite, dezent in Teal
  - „Nicht mehr anzeigen" → server-seitiges Dismiss
  - Session-X → nur lokal ausblenden (localStorage)
  - „Vorschlag anwenden" Button bei `filter_recommendation` (optional via
    `onApply`-Prop, von der Page selbst gehandhabt)
- **Eingebaut auf**: Dashboard, Stellen, Bewerbungen.

### Designprinzip

Adaptive UI darf nicht aufdringlich sein. Drei Schutz-Schichten:
1. LLM-Pattern-Analyse greift erst ab 50+ Events (Stufe 3 / beta.28)
2. Pro Seite max 2 Hints sichtbar
3. Server-Dismiss + Session-Dismiss + automatische Versions-Revalidierung
   nach 30 Tagen (Stufe 5-Vorgriff in beta.28)

### Tests

- `tests/test_v170_beta29_adaptive_ui.py`: 15 neue Tests
- **921 Tests gesamt, alle gruen** (1 Hygiene-Test laeuft erst nach
  CHANGELOG-Update sauber durch).

### Stufenplan-Fortschritt

- [x] Stufe 1: Foundation — beta.26
- [x] Stufe 2: Aggregation + Recap-Card — beta.27
- [x] Stufe 3: LLM-Pattern-Analyse + Korrektur-Loop + adaptive Prompts — beta.28
- [x] Stufe 4: Adaptive UI — beta.29
- [ ] Stufe 5: Telemetrie-Sharing (wochenweise, opt-in, abschaltbar) — beta.30

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.29.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.29.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.28] - 2026-05-07 — Lern-System Stufe 3: LLM-Pattern-Analyse + Korrektur-Loop

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Stufe 3 von #594 — die lokale LLM analysiert das aggregierte
Nutzungs-Verhalten, gibt verstaendliche Empfehlungen, und lernt mit
wenn der User ihre Entscheidungen korrigiert.

### ✨ Added — LLM-Pattern-Analyse

- **Neuer LLM-Task `ANALYZE_USER_PATTERNS`** im LLM-Service. Bekommt
  das Aggregat aus Stufe 2 und liefert max 3 Insights im strikten Format
  `TYP|TITEL|EMPFEHLUNG`. Typen:
  - `filter_recommendation` — Filter koennte Default werden
  - `ux_friction` — Anti-Pattern (viele Klicks, hoher Abort)
  - `workflow_optimization` — auffaellig haeufiger/abgebrochener Workflow
  - `dismiss_pattern` — Aussortier-Muster
  - `positive_signal` — User zeigt Mastery, kein Eingriff noetig
- **Persistenz `learning_insights`-Tabelle** (Schema v38, lag schon bereit).
  Helpers: `upsert_learning_insight`, `list_learning_insights`,
  `dismiss_learning_insight`, `deactivate_outdated_insights`.
- **Auto-Engine-5.-Schritt**: `_run_analyze_user_patterns` laeuft
  automatisch im taeglichen Auto-Actions-Lauf. Greift nur:
  - wenn `learning_enabled=True`,
  - mindestens 50 Events in den letzten 30 Tagen vorliegen (sonst zu duenn),
  - lokale AI aktiv + Modell installiert (sonst keine Token verbrennen).
- **API-Endpoints:**
  - `GET /api/learning/insights?only_active=1&limit=20`
  - `DELETE /api/learning/insights/{id}` (User: „Nicht mehr anzeigen")
  - `POST /api/learning/analyze` (manueller Trigger)

### ✨ Added — Korrektur-Loop

- **Tracking, wenn der User die LLM ueberstimmt**: bei
  `stelle_bewerten('passt')` auf einer Stelle, die vorher von der
  Auto-Aussortierung als `profil_match_negativ` weggeraeumt wurde, wird
  ein `llm_correction`-Event aufgezeichnet. Das ist Trainingsmaterial
  fuer adaptive Prompts und ein Indikator dafuer, wie gut die lokale
  AI mit dem Profil harmoniert.
- **DB-Helper** `count_llm_corrections(since_iso)` fuer Auswertung.

### ✨ Added — Adaptive Prompts

- **`match_job_to_skills`-Prompt-Anreicherung**: wenn der Bewerber Top-3
  Aussortier-Gruende hat (z.B. „falsches_fachgebiet 50×"), bekommt die
  LLM diese im Prompt mit. Dann muss sie nicht jede Stelle isoliert
  bewerten, sondern erkennt bekannte Anti-Muster.

### ✨ Added — Update-Reset-Mechanik (User-Vorgabe Stufe 5 vorgezogen)

- Bei jedem Auto-Engine-Lauf wird `deactivate_outdated_insights` mit
  der aktuellen App-Version aufgerufen. Insights, die fuer eine andere
  Version erstellt wurden und seit > 30 Tagen nicht mehr beobachtet
  wurden, werden deaktiviert. Beim Update werden Insights also
  automatisch revalidiert.

### 🎨 Frontend

- **`LearningInsightsCard`** zeigt jetzt zusaetzlich zu den deterministischen
  Aggregaten auch die LLM-generierten Insights — als eigenes Segment
  „KI-Erkenntnisse aus deinem Verhalten" mit Empfehlung + Counter +
  „nicht mehr anzeigen"-Button.
- Header-Counter zeigt zusaetzlich `n KI-Insight(s)` neben den
  Anti-Pattern-Hinweisen.

### Tests

- `tests/test_v170_beta28_llm_pattern.py`: 23 neue Tests
- **907 Tests gesamt, alle gruen.**

### Stufenplan-Fortschritt

- [x] Stufe 1: Foundation — beta.26
- [x] Stufe 2: Aggregation + Recap-Card — beta.27
- [x] Stufe 3: LLM-Pattern-Analyse + Korrektur-Loop + adaptive Prompts — beta.28
- [ ] Stufe 4: Adaptive UI — beta.29
- [ ] Stufe 5: Telemetrie-Sharing — beta.30

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.28.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.28.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.27] - 2026-05-07 — Lern-System Stufe 2: Aggregation + Anti-Pattern-Detection

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Stufe 2 von #594 — Aggregation der Lern-Daten + Anti-Pattern-Erkennung.

### ✨ Added

- **`GET /api/activity/aggregate?days=30`** liefert deterministische
  Aggregate (kein LLM nötig — Stufe 3 baut darauf auf):
  - `top_pages` — meistbesuchte Seiten mit Views/Klicks/Verweildauer
  - `workflow_stats` — start/abort/complete pro Workflow
  - `top_filters` — am häufigsten angewendete Filter
  - `dismiss_reasons_top` — top Aussortier-Gründe
  - `anti_patterns` — erkannte UX-Probleme

- **Anti-Pattern-Detection** (User-Vorgabe: Klicks/Scroll = Sucht-Verhalten):
  - `high_clicks_per_view` — Seite wird viel angeklickt → Filter optimieren
  - `high_abort_rate` — Workflow >40% abgebrochen → UX-Schwäche

- **Recap-Card „Was PBP gelernt hat"** auf Dashboard.
  Zeigt Top-Pages, Top-Filters, Dismiss-Reasons, Workflow-Stats und Anti-
  Pattern-Hinweise. Erst sichtbar ab 50+ Events ODER 1+ Anti-Pattern
  (sonst zu dünne Datenbasis).

### Tests

- `tests/test_v170_beta27_aggregation.py`: 9 neue Tests
- **884 Tests gesamt, alle grün.**

### Stufenplan-Fortschritt

- [x] Stufe 1: Foundation — beta.26
- [x] Stufe 2: Aggregation + Recap-Card — beta.27
- [ ] Stufe 3: LLM-Pattern-Analyse + Korrektur-Loop — beta.28
- [ ] Stufe 4: Adaptive UI — beta.29
- [ ] Stufe 5: Telemetrie-Sharing — beta.30

---

## [1.7.0-beta.26] - 2026-05-07 — Lern-System Stufe 1: Foundation (#594)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Erste Stufe von Issue #594 — Lern-System. Sammelt UI-Verhalten lokal,
damit spaetere Stufen (Aggregation → LLM-Analyse → Adaptive UI →
Telemetrie-Sharing) darauf aufbauen koennen.

### ✨ Added — Foundation

- **Schema v37 → v38:** zwei neue Tabellen
  - `user_activity_events` — UI-Klicks, Tab-Wechsel, Verweildauer,
    Scroll, Filter, Workflow-Abbrueche; mit `app_version` fuer
    spaeteren Update-Reset
  - `learning_insights` — aggregierte Erkenntnisse (kommt in Stufe 2+)
- **Frontend-Tracking-Hook** (`activity-tracking.js`):
  - Buffer mit 10s-Flush-Intervall, sendBeacon beim Tab-Schliessen
  - Pre-baked Helpers: `pageView`, `click`, `filterApply`, `dwell`,
    `scroll` (gedrosselt), `workflowStart/Abort/Complete`,
    `llmCorrection`
  - Performance-Impact < 1 ms pro Aufruf (rein lokales Buffering)
- **Privacy-Setting `learning_enabled`** (Default On per User-Vorgabe).
  In *Einstellungen → Datenschutz* mit klarer Erklaerung was lokal
  gesammelt wird + jederzeit ausschaltbar.
- **API-Endpoints:**
  - `POST /api/activity/track` — Batch-Insert. Silent-Discard wenn
    Setting deaktiviert.
  - `GET /api/activity/stats` — Anzahl + Verteilung nach Event-Typ
    fuer den Datenschutz-Tab
  - `DELETE /api/activity/clear` — alle Events des Profils loeschen,
    Domain-Daten unangetastet
  - `GET/PUT /api/settings/learning` — Toggle
- **Page-View + Verweildauer** automatisch beim Tab-Wechsel in App.jsx
  via `track.pageView()` und `track.dwell()`.

### Designprinzipien (User-Vorgabe)

- Daten **bleiben lokal** — kein externer Telemetrie-Call
- **Default On** mit klarem Onboarding-Hinweis
- **Tracking-Tiefe TIEF**: Klicks/Scroll als Anti-Patterns,
  Verweildauer als Positiv-Signal
- **Reversibel**: Lerndaten loeschen ohne Domain-Datenverlust

### Tests

- `tests/test_v170_beta26_lern_foundation.py`: 17 neue Tests
- **875 Tests gesamt, alle gruen.**

### Stufenplan-Fortschritt

- [x] Stufe 1: Foundation (Schema, Tracking-Hook, Privacy) — beta.26
- [ ] Stufe 2: Aggregation + Recap-Card — beta.27
- [ ] Stufe 3: LLM-Pattern-Analyse + Korrektur-Loop — beta.28
- [ ] Stufe 4: Adaptive UI — beta.29
- [ ] Stufe 5: Telemetrie-Sharing — beta.30

---

## [1.7.0-beta.25] - 2026-05-07 — Lokale-AI-Mehrwert: Auto-Klassifikation Mails + Dokumente, UI-Polish

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

User-Vorgabe: *„Wichtig ist mir halt, das wenn moeglich und wenn der User
das installiert hat, das die lokale LLM da besser und effizienter
eingebunden ist. Das diese einen spuerbaren Mehrwert bietet."*

### 🐛 Fixed (#591)

- **Modellname zeigte `—`** trotz „1 Modell installiert".
  Ursache: `selected_model` war `null` solange User nicht explizit ein
  Modell ausgewaehlt hatte. Jetzt: **Auto-Select** wenn nur 1 Modell
  installiert ist (in `_check_ollama` direkt).
- **`models_detail`** im Status-Endpoint: Liste mit `name`, `size_bytes`,
  `parameter_size`, `family` aus Ollama-`/api/tags`-Response.

### ✨ Added (#591/#592)

- **Modell-Detail-Liste im LocalAITab** mit Groesse + Parameter-Anzahl.
  Aktives Modell mit „aktiv"-Badge hervorgehoben.
- **„Weiteres Modell installieren"-Block** auch im `active`-Zustand
  sichtbar (vorher nur bei `no_model`). Zeigt empfohlene Modelle die
  noch nicht installiert sind, mit Ein-Klick-Pull.
- **„Was laeuft lokal?"-Erklaerbox** im LocalAITab listet die 4
  unterstuetzten Tasks (classify_document, extract_skills,
  match_job_to_skills, classify_email).
- **Klarer pausiert-Text:** „Wie 'Aus' — alle Tasks gehen an Claude"
  statt „Tasks an Claude".

### ✨ Added — Spuerbarer Mehrwert mit lokaler AI

- **Auto-Mail-Klassifikation** in der Auto-Engine.
  `_run_auto_classify_emails` als dritter Schritt in
  `POST /api/auto-actions/run`: eingehende Mails ohne `detected_status`
  werden via `classify_email` LLM-Task klassifiziert. Idempotent.
  Wenn lokale AI nicht aktiv: skipped (kein Claude-Fallback ohne
  User-Trigger).
- **Auto-Doku-Klassifikation** als vierter Schritt.
  `_run_auto_classify_documents`: Dokumente mit `doc_type='sonstiges'`
  und vorhandenem `extracted_text` werden via `classify_document`
  zu spezifischeren Kategorien (lebenslauf, anschreiben, ...) befoerdert.
- → **Spuerbarer Mehrwert:** wenn Ollama aktiv ist, sortieren sich
  Mails und Dokumente von selbst ein. Ohne lokale AI: business as usual.

### Tests

- `tests/test_v170_beta25_lokale_ai_mehrwert.py`: 11 neue Tests
  (Auto-Select, models_detail, Auto-Mail/Doku-Klassifikation,
  Idempotenz, UI-Snapshot).
- **858 Tests gesamt, alle gruen.**

---

## [1.7.0-beta.24] - 2026-05-07 — Lokale-AI-Vertiefung: Auto-Aussortieren + Mail-Klassifikation + UX

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

User-Auftrag: *„welche Issues haben wir schon, setze diese fuer die naechste
Beta um. Achte dabei darauf wo du die lokale AI besser einbinden kannst und
wo diese noch optimaler unterstuetzen oder vorarbeiten kann."*

Diese Beta vertieft die lokale AI massiv: zwei neue LLM-Tasks +
zwei UX-Verbesserungen + ein Bug-Fix.

### ✨ Added

- **#586 Profil-basiertes Auto-Aussortieren via lokale AI.**
  Statt Filter-Listen zu pflegen entscheidet die lokale AI pro Stelle,
  ob sie zum Profil passt. Skaliert mit beliebigen Berufsfeldern —
  Senior-PLM, Junior-Tech, Studenten, Service-Berufe.
  - `MATCH_JOB_TO_SKILLS` als echten LLM-Task implementiert
    (Prompt-Builder + Parser fuer PASST/PASST_NICHT/UNSICHER)
  - Neuer MCP-Tool `stellen_auto_aussortieren(max_stellen, min_score, dry_run)`
    iteriert durch unbewertete Stellen, lokale AI entscheidet, bei
    PASST_NICHT → `dismiss_job` mit LLM-Begruendung in research_notes
  - Idempotent + ehrlicher Fallback wenn Ollama nicht laeuft

- **NEU: `classify_email` LLM-Task.** Lokale AI klassifiziert eingehende
  Mails in 8 Kategorien: eingangsbestaetigung, einladung_interview,
  absage, rueckfrage, angebot, newsletter, spam, sonstiges. Vorbereitung
  fuer Auto-Status-Updates aus Mail-Inhalten.

- **#584 Test-Verbindung-Button** im Lokale-KI-Settings-Tab.
  POST `/api/llm/test-connection` liefert komplette Diagnose:
  Ollama-Erreichbarkeit, Modelle, aktiver State, Test-Roundtrip mit
  Latenz-Messung und Klassifikations-Result.

- **#585 Auto-Detect-Banner** auf dem Dashboard.
  Wenn Ollama erreichbar + Modell installiert + PBP-State `off` →
  freundlicher Banner mit „Aktivieren"-Button.
  Dismiss merkt sich 7 Tage in localStorage.

### 🐛 Fixed

- **#587 firmen_recherche-Befehl zeigte veraltete Daten.**
  Frontend-Logik priorisierte `job.company` (Snapshot bei Anlage, kann
  veralten wenn Vermittler den Endkunden bestaetigt). Jetzt:
  `application.endkunde` → `application.company` → `job.company`.

- **Modell-Wechsel-UI im LocalAITab** auch bei nur einem installierten
  Modell sichtbar (vorher versteckt, machte Nachinstallation eines
  weiteren Modells unsichtbar).

### Tests

- `tests/test_v170_beta24_lokale_ai_vertiefung.py`: 13 neue Tests
- Vorhandene Tests robuster gegen laufendes Host-Ollama (mit Mock-urllib)
- **847 Tests gesamt, alle gruen.**

---

## [1.7.0-beta.23] - 2026-05-06 — Installer-Polish: echter Health-Check + sichtbare Erfolgsmeldung

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

User-Feedback nach beta.22-Test: *„Nach der Installation startet pbp nicht
automatisch. Und auch ansonsten gibt es keinen Hinweis das die Installation
fertig ist."*

beta.19 hatte das eigentlich schon gefixt — aber die Reihenfolge im
Installer war ungluecklich (Erfolgsmeldung VOR dem Auto-Start, kein
Health-Check, `Dashboard starten.bat` schloss bei Python-Crash stumm).

### 🐛 Fixed

- **Erfolgsmeldung jetzt NACH dem Auto-Start** (Reihenfolge umgedreht).
  Vorher sah der User die Erfolgs-Box bevor klar war ob das Dashboard
  wirklich laeuft — jetzt zeigt die Box am Ende den echten Status.
- **Echter Health-Check auf `http://localhost:8200/`.** Bis zu 30
  Sekunden wird gepollt (PowerShell + `Invoke-WebRequest`). Erst wenn
  HTTP 200 ankommt, oeffnet sich der Browser. Bei Timeout: klare
  Meldung mit Log-Pfad.
- **Browser explizit oeffnen.** Vorher startete nur `Dashboard
  starten.bat` (im Hintergrund). Jetzt wird zusaetzlich
  `start "" "http://localhost:8200/"` ausgefuehrt — der User sieht
  das Dashboard wirklich.
- **Erfolgsmeldung zeigt Dashboard-Status.** Status-Zeile mit
  `[LAEUFT]` (gruen-Sinn) oder `[PRUEFEN]` (mit Log-Hinweis).
- **`Dashboard starten.bat` bleibt bei Fehler offen.** Vorher schloss
  das Fenster stumm bei Python-Crash. Jetzt: `setlocal
  EnableDelayedExpansion`, Python-Pfad-Check vorab, Errorlevel-Check
  nach dem Aufruf mit `pause` damit Fehlermeldung lesbar bleibt.

### Tests

- `tests/test_v170_beta23_installer_polish.py`: 6 neue Tests
  (Health-Check, Browser-Open, Reihenfolge, Status-Anzeige,
  Dashboard-bat-Errorlevel-Handling, Python-Pfad-Validierung).
- **832 Tests gesamt, alle gruen.**

---

## [1.7.0-beta.22] - 2026-05-06 — Bewerbungsbericht-Findings (Track-Record + PBP-Start)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Vier zusammenhaengende Bericht-Findings aus dem User-Test in beta.20.

### 🐛 Fixed

- **Interview-Rate war massiv verzerrt nach unten.** Die Executive Summary
  zaehlte nur Bewerbungen die **aktuell** im Interview-Status sind. Wer
  Interview hatte und danach abgelehnt/abgelaufen wurde, fiel raus —
  bei 11 Track-Record-Interviews sah der Bericht nur 3 (3.6%) statt 13.3%.
  **Fix:** Bericht nutzt jetzt das `has_reached_interview`-Flag (das beim
  ersten Interview-Statuswechsel gesetzt wird und bleibt). Die Quote heisst
  jetzt klar **„Track-Record-Interview-Rate"**. Pipeline zeigt zusaetzlich
  „aktuell im Interview-Prozess" als Snapshot.

### ✨ Added

- **PBP-Start-Datum prominent auf Cover-Page.** Steht direkt unter dem
  Zeitraum: *„PBP-Nutzung seit DD.MM.YYYY"*. Damit weiss der Leser sofort
  ob die Daten vollstaendig sind oder nachtraeglich erfasst.
- **Auto-Detect aus `application_events`** — kleinster `event_date` =
  erste echte PBP-Aktivitaet. User kann ueberschreiben (z.B. wenn der Start
  bewusst auf einen frueheren oder spaeteren Stichtag fixiert werden soll).
- **Setting-API:** `GET/PUT /api/settings/pbp-start-date`. Frontend-Feld
  im Bericht-Tab unter den Arbeitsamt-Settings.
- **Pre-PBP-Bewerbungen werden im Bericht grau hinterlegt.** Datums-Spalte
  bekommt ein „†"-Marker, der gesamte Zeilen-Text ist dezent grau.
  Legende unter der Liste: *„† Bewerbung vor PBP-Nutzung — nachtraeglich
  erfasst, Daten moeglicherweise unvollstaendig."* Plus Hinweis-Block in
  der Executive Summary mit der Anzahl der Pre-PBP-Bewerbungen.

### Tests

- `tests/test_v170_beta22_bericht_findings.py`: 8 neue Tests
  (Auto-Detect, User-Override, API-Validierung, PDF-Generierung mit
  Track-Record-Logik, Pre-PBP-Markierung).
- **826 Tests gesamt, alle gruen.**

---

## [1.7.0-beta.21] - 2026-05-06 — Navigation-Bug + LinkedIn-Anreicherung

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Zwei User-Test-Findings aus beta.20.

### 🐛 Fixed

- **2-Klick-Bug bei Navigation auf Kontakte.** `kontakte` fehlte in
  `frontend/src/utils.js:PAGE_IDS`. Folge: `parsePageFromHash()` lehnte
  den Hash `#kontakte` als unbekannt ab und fiel auf `dashboard`
  zurueck. Beim 1. Klick: `setPage("kontakte")` + Hash-Update →
  `hashchange`-Listener feuert → `parsePageFromHash` liefert
  `"dashboard"` zurueck → `setPage("dashboard")` ueberschreibt sofort.
  Beim 2. Klick blieb der Hash stabil weil er bereits gesetzt war.
  Fix: `kontakte` in `PAGE_IDS` aufgenommen.

### ✨ Added

- **LinkedIn-Anreicherung fuer Kontakte (#563).** Wenn beim Kontakt
  eine `linkedin.com/in/...`-URL eingetragen ist, erscheint ein
  Button **„Daten holen"**. Backend (`POST /api/contacts/enrich-from-
  linkedin`) erzeugt einen Claude-in-Chrome-Prompt mit JS-Selektoren
  fuer Name, Position, Firma, Standort, Skills. Der User kopiert den
  Prompt in Claude — Claude oeffnet das Profil im **eingeloggten**
  Chrome-Tab und liest die Daten via `javascript_tool()`. LinkedIn
  blockt direkten Server-Scraping (Login-Wall, Bot-Detection); der
  Umweg ueber den eingeloggten Browser-Tab umgeht die Sperren.

### Tests

- `tests/test_v170_beta21_fixes.py`: 6 neue Tests.
- **818 Tests gesamt, alle gruen.**

---

## [1.7.0-beta.20] - 2026-05-06 — Recruiter-Anfragen + Status-Hygiene + Auto-Engine

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Vier zusammenhaengende Bewerbungs-Workflow-Reparaturen die User-Test in
beta.18/19 aufgedeckt hatte.

### 🆕 Recruiter-Anfragen sauber abbilden (semantischer Fix)

**Problem:** Eine Recruiter-Anfrage die du sofort ablehnst wurde als
Bewerbung mit Status `zurueckgezogen` angelegt — semantisch falsch und
verfaelschte deine Track-Record-Statistik (Quoten zaehlten sie als
"submitted").

**Fix in 3 Stufen:**
1. Neuer MCP-Tool `recruiter_anfrage_ablehnen(firma, titel, grund, ...)`
   legt nur eine ausgemusterte Stelle an (KEIN applications-Eintrag).
2. `bewerbung_erstellen()` blockt den frueheren Workaround
   (`bereits_beworben=False + status=zurueckgezogen/abgelehnt`) mit
   klarer Fehlermeldung und Tool-Vorschlag.
3. Neuer MCP-Tool `bewerbung_zu_anfrage_konvertieren(bewerbung_id)`
   bereinigt Bestand: loescht den falschen applications-Eintrag und
   dismisst die verknuepfte Stelle.

### 🐛 Status-Hygiene

**Problem:** In der DB tauchten Status-Werte auf die nirgendwo definiert
waren (`warte_auf_rueckmeldung`, `abgesagt`) — `bewerbung_status_aendern`
liess sie ungeprueft durch und die Statistik konnte sie nicht einordnen.

**Fix:**
- **Schema v36 → v37 Migration:** Bestand-Reparatur — aus
  `warte_auf_rueckmeldung` wird `eingangsbestaetigung` (User-Vorgabe),
  aus `abgesagt` wird `abgelaufen` (User-Vorgabe). Audit-Event pro
  Eintrag.
- `bewerbung_status_aendern()` validiert `neuer_status` jetzt gegen die
  offizielle Whitelist mit Mapping-Hinweis fuer alte Werte.

### ⚙️ Auto-Engine (#Workflow)

**Problem:** Bewerbungen verharrten ewig auf `beworben` — keine Logik
setzt sie auto auf `abgelaufen`. Nachfass-Erinnerungen wurden nur 1×
beim Anlegen der Bewerbung erzeugt — wenn der User sie erledigte oder
verwarf, riss der Faden ab.

**Fix:**
- Neuer Endpoint `POST /api/auto-actions/run` triggert beide Engines:
  - **Auto-Expire:** setzt aktive Bewerbungen ohne Aktivitaet > N Tage
    auf `abgelaufen` (Default 60d fuer `beworben`, 30d fuer
    `eingangsbestaetigung`).
  - **Auto-Followup-Reconciler:** legt fehlende Nachfass-Follow-ups
    automatisch an (Default 7d nach letzter Aktivitaet). Idempotent —
    legt keine Duplikate an wenn schon ein offener FU existiert.
- Settings-Tab **„Automatik"** im Frontend mit konfigurierbaren
  Schwellwerten + Sofort-Lauf-Button.
- `GET /api/auto-actions/status` liefert die aktuellen Settings + den
  Zeitpunkt des letzten Laufs.

### Tests

- `tests/test_v170_beta20_recruiter_anfrage_auto.py`: 15 neue Tests
  (Recruiter-Anfragen-Tool, Konvertierung, Status-Whitelist, Auto-Expire,
  Auto-FU-Reconciler, Settings-Validierung, Idempotenz).
- Schema-v37-Test (`tests/test_v170_beta18_migration_from_169.py`)
  generalisiert auf aktuelle SCHEMA_VERSION.
- Vorhandene Tests #506 angepasst (alter Workaround wird jetzt blockiert).
- **812 Tests gruen.**

---

## [1.7.0-beta.19] - 2026-05-06 — User-Test-Findings + Kontakt-Import

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Vier konkrete Findings aus dem User-Test der beta.18 — alle gefixt.

### 🐛 Fixed

- **Installer schloss stumm.** Nach erfolgreicher Installation kam ein
  `(j/n)`-Prompt — wer Enter ohne `j` druckte, wusste nicht ob die
  Installation geklappt hat. Jetzt: klare Erfolgsmeldung mit Box-Banner,
  Versionsanzeige, **automatischer Start** von Claude + Dashboard ohne
  Rueckfrage.
- **Dashboard-Flackern.** Der Live-Update-Token wurde aus der mtime/size
  von `pbp.db-wal` und `-shm` berechnet. Im WAL-Modus aendert SQLite die
  WAL-Datei aber bei JEDEM Read (Snapshot-Header). Folge: Polling alle 2s
  sah den Token jedes Mal als geaendert → permanenter `refreshChrome` →
  Dashboard-Flackern. **Fix:** Token wird jetzt aus Tabellen-COUNTs +
  `MAX(updated_at)` aufgebaut. Reine Lese-Polls aendern nichts → stabil;
  echte Schreibvorgaenge erhoehen den Counter → Live-Update funktioniert.
- **„Mehr erfahren"-Link im Lokale-KI-Modal landete im Dashboard.**
  Vorher: `<a href="#einstellungen?tab=ai">` — Hash-Anchor unterstuetzt
  kein `?tab=...`, daher landete der User stumm in der Default-Seite.
  Jetzt: `navigateTo("einstellungen", { tab: "ai" })`.

### ✨ Added

- **#563 Kontakt-Import-Wizard.** Neuer Button „Importieren" auf der
  Kontakte-Seite oeffnet einen Wizard, der zwei Quellen abklopft:
  - **Aus Bewerbungen:** alle distinct (ansprechpartner, kontakt_email)-
    Tupel aus dem `applications`-Bestand, die noch nicht als Kontakt
    angelegt sind. Standard-Tag „recruiter", vor-selektiert.
  - **Aus E-Mail-Dokumenten:** Regex-Extraktion der E-Mail-Adressen
    aus `extracted_text` der Dokumente mit `doc_type='email'`. Pro
    E-Mail wird gelistet, in wie vielen Mails sie gefunden wurde.
    NICHT vor-selektiert (Heuristik, kann Muell enthalten).
  - Bestehende Kontakte (Match per E-Mail) werden ausgefiltert.
  - **Stellen werden NICHT abgeklopft** (User-Vorgabe: Rauschen, erst
    wenn Stelle zur Bewerbung wird, ist es relevant).
  - Backend: `GET /api/contacts/discover` (Vorschau) und
    `POST /api/contacts/import-discovered` (Anlage).

### Tests

- `tests/test_v170_beta19_fixes.py`: 13 neue Tests.
- Volle Regression: **797 Tests gruen**.

---

## [1.7.0-beta.18] - 2026-05-05 — Aufraeumen + Installer-Polish + Issue-Triage

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Code-Aufraeumen + Installer-Verbesserungen + Backlog-Triage. Keine
funktionalen Aenderungen — Polish-Beta vor dem User-Test.

### 🧹 Aufraeumen

- **v1.4-Migration entfernt** (`_migrate_flat_layout` in `database.py`).
  v1.5 ist seit > 1 Jahr Standard, der Move-Code ist toter Code. Wer
  noch auf v1.4 ist, muss zuerst v1.6.9 installieren — die hat die
  Move-Logik noch.
- **`shutil`-Import entfernt** (war nur fuer die v1.4-Migration noetig).
- **CLAUDE.md** — „v1.6.5 ist Latest" auf v1.6.9 aktualisiert + Hinweis
  zur laufenden v1.7.0-Beta-Reihe.

### 🔧 Installer-Polish (`INSTALLIEREN.bat`)

- **Header zeigt dynamische Version** statt hardgekodet „v1.6.0".
- **Claude-Desktop-Erkennung erweitert** auf 7 Pfade (statt 4):
  zusaetzlich `anthropic-claude/`, `Program Files (x86)`,
  `USERPROFILE\AppData\...`, plus PATH-Fallback (`where Claude.exe`)
  und Konfig-Fallback (wenn `%APPDATA%\Claude\claude_desktop_config.json`
  existiert, ist Claude offensichtlich da). WinStore-Detection auch
  fuer neuere `Packages\AnthropicPBC.Claude*`.
- **Process-Check:** wenn Claude waehrend der Installation laeuft, fragt
  der Installer den User aktiv zum Beenden auf — ohne Neustart nimmt
  Claude die neue MCP-Konfig nicht auf.
- **Setup-Helper-Integritaets-Check:** prueft beim Start ob
  `_setup_claude.py`, `_selftest.py`, `start_dashboard.py` vorhanden
  sind, mit klarer Fehlermeldung wenn das ZIP unvollstaendig entpackt
  wurde.

### 📦 ZIP-Download entrümpelt (`.gitattributes`)

GitHub-ZIP-Download (`archive/refs/tags/...zip`) enthaelt ab beta.18
nur noch wirklich install-relevante Dateien. Dev-Doku, Test-Suite,
Build-Tooling werden via `git archive`-`export-ignore` gefiltert:

- Dev-Doku (`AGENTS.md`, `CONTRIBUTING.md`, `DOKUMENTATION.md`,
  `OPTIMIERUNGEN.md`, `TESTVERSION.md`, `ZUSTAND.md`, `CLAUDE.md`)
- Dev-Tools (`release_check.py`, `test_demo.py`, `switch_mode.py`)
- Test-Suite (`tests/`)
- CI/Workflows (`.github/`, `.gitignore`, `.gitattributes`)
- Workspace-Manifest (`pnpm-workspace.yaml`)

Endnutzer sehen jetzt nur noch ~10 Dateien im Root statt 30+.

### 📄 Neue Datei: `LIESMICH.txt`

3-Zeilen-Klartext-Anleitung im ZIP-Root: welche Datei doppelklicken
fuer welches OS, was die Voraussetzung ist, wo Hilfe steht. Damit
brauchen Endnutzer nicht das ganze README zu lesen.

### 📋 Issue-Triage

Nach dem Audit (User-Frage „sind alle Issues weg?") aufgeraeumt:

- **Geschlossen:** #575 (v1.7.0-Sprint-Master, ist durch),
  #512 (Lokale-LLM-Epic — Foundation umgesetzt), #469 (Duplikat
  von #478/#480/#481).
- **Auf v1.8 verschoben + roadmap-Label:** #504 (Plugin-Plattform —
  trug faelschlich „v1.7" im Titel, ist aber nicht in v1.7).
- **Mit roadmap-Label markiert:** #513 (Community-Tagesimpulse),
  #452 (Interview-Training-Arc).
- **Bleiben offen ohne v1.7-Anspruch:** 6 v1.8-gelabelte Issues
  (External Inbound + Portal-Profile + Plugin-Plattform), 6
  roadmap-Issues (Future Work, kein konkretes Release-Ziel).

**Status: 0 offene v1.7-Issues. 12 offen mit klarer Verortung.**

### Tests

- **Migration-Beweis v1.6.9 → beta.18:** `tests/test_v170_beta18_migration_from_169.py`
  legt eine echte v1.6.9-DB an (Schema v31, mit Profil, Position, Skill,
  Stelle inkl. alter BA-URL, Bewerbung, Dokument, Follow-up), faehrt
  `Database.initialize()` darueber und verifiziert:
  - Migration v31 → v32 → v33 → v34 → v35 → v36 laeuft komplett durch
  - Backup wird automatisch in `data/backups/pbp-backup-*.db` angelegt
    *bevor* die Migration startet
  - Alle 6 Datenarten bleiben unveraendert erhalten
  - Bestand-BA-URL wird auf `/jobsuche/jobdetail/` umgestellt (#526)
  - Andere URLs (Indeed, etc.) bleiben unangetastet
  - Neue Tabellen (`contacts`, `application_jobs`, `skill_periods`,
    `application_costs`, `document_versions`, `contact_links`) sind nach
    der Migration alle da
  - Neue v1.7-Features (Skill-Zeitraum hinzufuegen, Kontakt anlegen,
    Bewerbung↔Stelle n:m verknuepfen) funktionieren sofort
- Volle Regression: **784 Tests gruen** (vorher 778; +6 Migration-Tests).

---

## [1.7.0-beta.17] - 2026-05-05 — Nice-to-haves: Score-Histogramm, Bulk-Doku-Prep, DSGVO-Button

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Schliesst die letzten 3 Nice-to-have-Issues fuer v1.7. Damit sind ALLE
v1.7.0-Issues erledigt — Voraussetzung fuer rc.

### ✨ Added

- **#520 Fit-Score-Verteilung ueber Zeit.** Neuer API-Endpoint
  `GET /api/stats/score-over-time?interval=month|week&weeks=N` liefert
  ein Stacked-Histogramm-Format pro Zeit-Bucket mit 4 Score-Buckets
  (0-30, 30-60, 60-80, 80-100). Ideal fuer Trend-Analyse: „werden
  meine Treffer ueber die Zeit besser?"
- **#533 Bulk-Doku-Vorbereitung.** Neuer Endpoint
  `POST /api/documents/bulk-analyze-prep` filtert offene/unverknuepfte
  Dokumente und gibt eine fertige `dokumente_batch_analysieren`-
  Prompt-Vorlage zurueck — UI kopiert sie in die Zwischenablage und
  der User fuegt sie in Claude ein. Damit ist die Bulk-Aktion sichtbar
  und 1-Klick statt versteckt.
- **#581 DSGVO Art. 15 Selbstauskunft.** Frontend-Button im Datenschutz-
  Tab fuehrt zum bereits bestehenden `/api/privacy/self-disclosure.pdf`-
  Endpoint. PDF enthaelt Profil, Skills, Berufserfahrung, Anzahlen
  (Bewerbungen, Stellen, Dokumente, Termine) + Speicherort — KEINE
  Dokument- oder E-Mail-Inhalte (DSGVO-konform).

### Tests

- `tests/test_v170_beta17_nice_to_haves.py`: 8 neue Tests
  (3 fuer #520 — empty, with jobs, weeks-Clamping;
   3 fuer #533 — empty pool, prompt-Vorlage, max-Cap;
   2 fuer #581 — PDF-Smoke + Frontend-Button-Pruefung).
- **778 Tests gesamt, alle gruen.**

### v1.7-Sprint-Status

Nach beta.17 sind alle 19 v1.7-Issues entweder erledigt oder begruendet
verschoben:
- ✅ **15 erledigt:** #472, #505, #512, #518, #520, #523, #526, #527,
  #533, #563, #568, #571, #572, #573, #576, #577, #578, #579, #580,
  #581, #582, #583
- 🔁 **6 auf v1.8 verschoben:** #478, #480, #481, #524, #525 (External
  Inbound), #564 (Portal-Profile)
- ❌ **1 closed-no-repro:** #555 (Cross-Portal-Dubletten)

---

## [1.7.0-beta.16] - 2026-05-05 — Daten-Quality-Bugs: E-Mail-Matching, BA-URLs, Freelancermap-Beschreibungen

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

### 🐛 Fixed

- **#523 E-Mail-Matching: Leitprinzip „Im Zweifel unverknuepft."**
  - Default-Threshold von 0.5 auf **0.90** angehoben.
  - **Domain-Signal-Pflicht:** ein Auto-Match braucht jetzt mindestens
    ein Domain-Signal (kontakt_email-Match, kontakt_email-Domain-Match,
    Firma-in-Sender-Domain, oder URL-Domain-Match). Reine Firmen-im-
    Betreff- oder Title-Treffer reichen nicht mehr.
  - Strategy-Scores angehoben: kontakt_email-Domain 0.8 → 0.9,
    Firma-in-Sender-Domain 0.75 → 0.9, URL-Domain-Match 0.7 → 0.85.
  - Konsequenz: weniger Auto-Matches, mehr unverknuepfte Mails — wie
    vom User gefordert. „Lieber zehn Mails manuell zuordnen als eine
    falsch automatisch."

- **#526 Bundesagentur-URLs: Bestand reparieren.**
  - Schema v35 → **v36**: Migration aktualisiert alle 249 betroffenen
    Bestand-URLs von `jobsuche/suche?id=...` (Suchergebnis-Seite) auf
    `jobsuche/jobdetail/{refnr}` (Stellenanzeige). Scraper-Code war
    bereits seit beta.7 korrekt; jetzt auch der Bestand.

- **#527 Freelancermap-Beschreibungen.**
  - Detail-Fetch-Limit von 30 auf **75** pro Such-URL angehoben — bei
    4 Such-URLs entspricht das Maximum 300 Detail-Requests pro Run.
  - Neuer Endpoint `POST /api/jobs/refresh-freelancermap-descriptions`
    holt fehlende Beschreibungen im Bestand nach (rate-limited 0.3s,
    max 50/Aufruf, hartes Cap 200).

### 📋 Issue-Triage

- **#555 Cross-Portal-Dubletten:** geschlossen als „Verdacht ohne Repro".
  Kein Bug-Indiz im Code-Review gefunden. Wird neu eroeffnet sobald ein
  reproduzierbarer Test-Case vorliegt.
- **#564 Portal-spezifische Such-Profile:** auf v1.8 verschoben (zu
  grosser UI-Eingriff fuer v1.7).
- **#478, #480, #481, #524, #525 (Externer Inbound):** auf v1.8
  verschoben — Thunderbird/Outlook/Mail-Newsletter sind ein eigener
  Sprint.

### Tests

- `tests/test_v170_beta16_bugs.py`: 10 neue Tests
  (4 fuer #523 — Threshold + Domain-Pflicht; 3 fuer #526 — Migration
  idempotent + nur bundesagentur betroffen; 3 fuer #527 — Refresh-API
  + Scraper-Limit-Code-Pruefung). **770 Tests gesamt, alle gruen.**

---

## [1.7.0-beta.15] - 2026-05-05 — Test-Hygiene: alle Tests gruen

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

User-Auftrag: „bis alle tests und simulationen auf gruen sind". Diese
Beta migriert die ausstehenden FastMCP-2.12-API-Aufrufe und fixt einen
tz-naive-Timezone-Bug im Duplikat-Erkennungs-Test.

### 🧪 Fixed (Tests)

- **`tests/test_capabilities_grenze.py`** (5 Tests) — `mcp.call_tool` ist
  in FastMCP 2.12+ entfernt. Migriert auf `await mcp.get_tool(name);
  await tool.run(args)` via `_call`-Helper (siehe CLAUDE.md).
- **`tests/test_stellen_bulk_bewerten.py`** (6 Tests) — gleicher Fix in
  `_call_bulk()`.
- **`tests/test_duplicate_detection.py`** (1 Test) — `t_minus_1h` war
  `datetime.now()` ohne tz. Bei Lokalzeit ≠ UTC kollidiert das mit dem
  tz-aware `datetime.now(timezone.utc)` im Code (negative `hours_ago`,
  Test schlaegt fehl). Fix: tz-aware UTC im Test.

### Status

- **760 Tests bestanden, 0 Failures** (vorher: 747 passed, 13 failed).
- Damit ist die Vorbedingung „alle Tests gruen" erfuellt — Voraussetzung
  fuer beta.16 (Daten-Quality-Bugs) und beta.17 (Nice-to-haves).

---

## [1.7.0-beta.14] - 2026-05-05 — Audit-Sweep, LLM-Tests vervollstaendigt, rc.1 zurueckgezogen

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

User-Feedback nach rc.1: „Du sagtest morgens 10 Tage, jetzt nach 10h rc?
Du hast nicht alles getestet." — zu Recht. **rc.1 wurde zurueckgezogen**
(siehe Hinweis im rc.1-Release-Body), Versionen sind auf beta.14.

Diese Beta schliesst die Test- und Akzeptanzkriterien-Luecken, die in
rc.1 kaschiert waren:

### 🔍 Audit der „schon implementiert"-Issues

Jedes der 5 als „im Code vorhanden" gefuehrten v1.7-Issues wurde gegen
seine eigentlichen Akzeptanzkriterien geprueft. Drei Luecken gefunden:

- **#583 — Modal-Hinweistext veraltet.** Der Erklaerungs-Modal sagte
  „Einrichtung kommt in der naechsten Beta-Version" — der Setup-Wizard
  ist seit beta.2 in *Einstellungen → Lokale KI* drin. Text korrigiert,
  verweist jetzt auf den existierenden Wizard.
- **#571 Stufe 1 — In-Page-Filter im Profil fehlte.** Skill-Liste hatte
  keinen Live-Filter; der globale Header-Search ist ein Workaround,
  aber nicht der Use-Case aus dem Issue („schnell einen Skill bearbeiten").
  Filter-Input ueber Skills nachgezogen (erscheint ab >6 Skills).
- **#573 — DOM-Extraktions-JS fehlte.** `google_jobs_url`-Tool lieferte
  nur die URL und Hinweis-Text, kein JS-Snippet. Tool liefert jetzt
  `extraction_js` mit fuer `javascript_tool()` direkt nutzbarem
  `querySelectorAll`-Code (Selektoren mit Fallback-Strategie).
- **#505 — README-Doku fehlte.** Typed-IDs-Sektion mit Praefix-Tabelle
  (APP-/JOB-/DOC-/MTG-/CON-) und Nicht-breaking-Hinweis ergaenzt.

#576, #577 sind ohne Aenderung komplett — werden mit Audit-Bestaetigung
geschlossen.

### 🧪 LLM-Pfad systematisch getestet (#512)

Die 38 LLM-Tests aus beta.1/beta.2 waren reine Mock-Tests. Echte
HTTP-Layer + alle 5 API-Endpunkte hatten **0 TestClient-Tests**. In
beta.14 hinzugefuegt:

- **`tests/test_v170_beta14_llm_audit.py`** (18 Tests):
  - HTTP-API: `/api/llm/status`, `/state`, `/model`, `/pull`,
    `/recommended-models` (success, validation, fehlertolerant).
  - `_check_ollama` mit gemocktem `urllib.request` — Erfolg, leere
    Modell-Liste, Timeout, Connection-Refused.
  - `_ollama_generate` mit Mock-Response — extrahiert `response`-Feld,
    handelt leere Antworten korrekt.
  - End-to-End `run(CLASSIFY_DOCUMENT)` mit gemocktem Ollama — Status-
    und Generate-Calls in der richtigen Reihenfolge, Backend=LOCAL,
    Parser greift, Kategorie wird korrekt zurueckgegeben.
  - Fallback-Pfad: wenn `_ollama_generate` mid-call crasht, faellt
    `run()` auf CLAUDE statt zu crashen.
  - Paused-State: `select_backend` ignoriert LOCAL auch bei verfuegbarem
    Ollama, faellt auf CLAUDE.
  - `trigger_pull` Erfolg + Fehlerpfad.

- **`tests/test_v170_beta14_audit_gaps.py`** (5 Tests):
  - #573 google_jobs_url liefert `extraction_js` mit DOM-Selektoren
  - #573 End-to-End ueber FastMCP-Tool-Call
  - #583 App.jsx Modal-Hinweistext nicht mehr veraltet
  - #505 README enthaelt vollstaendige Typed-IDs-Sektion
  - #571 Stufe 1 Filter-State + Input + Filter-Logik in ProfilePage.jsx

### Was beta.14 NICHT macht

- Keine echten End-to-End-Tests gegen einen echten Ollama-Server. Das
  muss waehrend des User-Tests passieren — kein Auto-Test denkbar ohne
  Ollama-Installation in der Test-Umgebung.
- 12 vor-bestehende `mcp.call_tool`-Test-Failures (FastMCP 2.12-Migration
  laut CLAUDE.md ausstehend) bleiben unangetastet — keine Regression.

### Ablauf bis rc.2

User testet beta.14. Wenn ok → rc.2. Wenn neue Bugs gefunden → beta.15.

---

## [1.7.0-rc.1] - 2026-05-05 — Release Candidate (zurueckgezogen)

> ❌ **VERFRUEHT VERSENDET — siehe v1.7.0-beta.14.** rc.1 hat die
> Akzeptanzkriterien der „in Code"-Issues nicht sauber gegen die
> Realitaet gepruft. Tag bleibt aus Tag-Lock-Gruenden bestehen,
> aber das Release wurde im GitHub-Body als zurueckgezogen markiert.

> ⚠️ **Pre-Release / Release Candidate**. Stable bleibt v1.6.9.
> Wenn rc.1 gruen durch Real-World-Test laeuft, geht **v1.7.0 final**
> als neues `--latest` raus.

Erstes Release-Candidate fuer v1.7.0. Funktional identisch zu beta.13 —
keine neuen Features, nur Versions-Bump zur Signalisierung „Feature-Freeze
fuer v1.7.0 erreicht, Test-Phase".

### 🆕 Was ist seit v1.6.9 dazugekommen?

Sammelt alle v1.7.0-Betas in einer Uebersicht:

- **Lokale AI (Ollama)** — beta.1: opt-in Sidecar, Status-Indicator, PBP-Router.
- **Typed IDs (Variante A)** — beta.1: Praefixe APP-/JOB-/DOC-/MTG-, parallel zu nackten IDs.
- **n:m Bewerbung↔Stelle (#472)** — beta.5: Junction-Tabelle, primaer/Versionen.
- **Kontaktdatenbank (#563)** — beta.4..beta.10: 8 MCP-Tools + Frontend-Page + Detail-Inline-Add.
- **Bewerbungs-Detail (beta.11)** — Stellen pro Bewerbung, Stellen-Vergleich (#580), Aufwand & Kosten (#568).
- **Stats & Bericht (beta.12)** — Activity-Heatmap (#579), Skill-Zeitraeume API (#572),
  Taetigkeitsbericht-Modus (#582).
- **Bug-Fixes (beta.13)** — Follow-up-Typ-Hygiene (#518), Termine-CSV-Export (#578).
- **Datenmodell** — Schema v31 → v35, Hash-Hygiene scoped, neue Tabellen
  (`contacts`, `application_jobs`, `skill_periods`, `application_costs`).

### Stable-Release-Pfad

- v1.6.9 bleibt `--latest` bis v1.7.0 final.
- rc.1 wird als `--prerelease` veroeffentlicht.
- **Nach Real-World-Test** (Endnutzer + Maintainer): v1.7.0 final als neues
  `--latest`, v1.6.x rutscht in Wartungs-Modus (kritische Bug-Fixes nur
  noch bei akuten Problemen).

---

## [1.7.0-beta.13] - 2026-05-05 — Bug-Fixes & Polish

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Sammel-Beta mit Bug-Fixes und kleinen Verbesserungen vor dem rc.1.

### 🐛 Fixed

- **#518 Follow-up-Typ-Hygiene wird respektiert** — Banner und „Faellige
  Nachfassaktionen"-Filter zaehlen ab jetzt **nur** Follow-ups vom Typ
  `nachfass`. Interview-Erinnerungen, Danke-Mails, Info-Notizen bleiben
  sichtbar, loesen aber keinen Banner-Alarm mehr aus.
  - API: `GET /api/follow-ups` liefert pro Eintrag jetzt zusaetzlich
    `faellig_datum` (rein Datums-Pruefung) und `banner_typ` (typ-basiert).
    Das Bestand-Feld `faellig` ist jetzt typ-sensitiv (`nachfass + Datum`).
  - Recap-Endpoint: korrekte SQL-Spalte (`scheduled_date` statt `due_date`)
    und Status (`geplant`) — vorher schwiegen die Counts in einer Exception.

### ✨ Added

- **#578 CSV-Export fuer Termine** — `GET /api/meetings/export.csv?from=&to=`,
  vervollstaendigt die CSV-Familie (Bewerbungen, Stellen, Kontakte, Termine
  jetzt alle exportierbar). Route-Reihenfolge in dashboard.py beachtet, damit
  FastAPI nicht auf `/api/meetings/{meeting_id}` matcht.

### Tests

- `tests/test_v170_beta13.py`: 4 neue Tests (Banner-Hygiene fuer 3 Follow-up-
  Typen, Unbekannter-Typ-Normalisierung, Termine-CSV-Export-Smoke,
  Bewerbungen-CSV-Datums-Format).

---

## [1.7.0-beta.12] - 2026-05-05 — Profil + Stats: Heatmap, Skill-Zeitraeume, Taetigkeitsbericht

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Drei zusammenhaengende Erweiterungen, die das Profil-/Stats-Erlebnis
abrunden — und dem Vermittler-Bericht einen neuen Modus geben.

### 📊 Aktivitaets-Heatmap (#579)

- GitHub-Style Contribution-Graph in *Statistiken* (Sektion ueber den
  Zeitraum-/Status-Charts).
- Aggregiert pro Tag aus **Bewerbungen, Statuswechseln, Terminen, Follow-ups**.
- Zeitraum-Wahl `90 / 180 / 365 / 730 Tage` direkt am Kopf der Card.
- Tooltip pro Zelle: Datum + Anzahl Aktionen. Empty-State erklaert das Feature
  fuer Erstnutzer.
- Backend: `GET /api/stats/heatmap?days=N` (clamped auf 30..730).

### 🕓 Skill-Zeitraeume API (#572)

- `GET/POST /api/skills/{skill_id}/periods` und `DELETE /api/skills/periods/{period_id}`.
- Diskontinuierliche Zeitraeume pro Skill (z.B. „Python 2018–2022, dann
  2024–jetzt") inkl. `start_year`, `end_year`, `level_at_period`, `notes`.
- Backend bereit; UI im Profil folgt in beta.13. MCP-Tool
  `skill_zeitraum_hinzufuegen` ist seit beta.5 nutzbar.

### 📋 Taetigkeitsbericht-Modus (#582)

- Neue Bericht-Einstellung **„Taetigkeitsbericht-Modus"** in
  *Einstellungen → Bericht*.
- Wenn aktiv: Cover-Titel wird zu **„Taetigkeitsbericht"** (statt
  „Bewerbungsbericht") und der PDF-Bericht erhaelt eine zusaetzliche
  Sektion **„11a. Taegliche Aktivitaets-Uebersicht"** — Aktivitaeten gebuendelt
  pro Tag, ideal als Nachweis konkreter Bemuehungen fuer Vermittler/Berater.
- Bestehende Sektionen bleiben unveraendert; der Modus ist additiv.

### Tests

- `tests/test_v170_beta12.py`: 8 Tests fuer Heatmap (Clamping, Empty,
  Application-Pfad), Skill-Zeitraeume (CRUD, 404), Taetigkeitsbericht
  (Settings-Persistenz, PDF-Smoke-Test).

---

## [1.7.0-beta.11] - 2026-05-05 — Bewerbungs-Detail-Erweiterungen

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Drei neue Komponenten in der Bewerbungs-Detail-Ansicht:

### 🔗 Mehrere Stellen pro Bewerbung (#472)

- Neue Section `<ApplicationJobsSection>` zeigt alle verknuepften
  Stellen mit `primaer`/`Version`-Chips
- **Empty State** erklaert Use-Cases: „Repost", „Vermittler+Endkunde-Sicht"
- **Inline-Add-Workflow** mit Versions-Label-Eingabe + Stellen-Suche
- **🆚-Button** an jeder Zeile (wenn ≥2 Stellen) oeffnet Stellen-Vergleich

### 🆚 Stellen-Vergleichs-Modal (#580)

- `<StellenVergleichModal>` zeigt strukturierten Diff zweier Stellen:
  - Side-by-Side: Score, Quelle, Standort, Gehalt, Beschreibungs-Laenge
  - Vergleich: Score-Diff, Beschreibung-Overlap-%, Titel-gemeinsam/nur-A/nur-B
- `GET /api/jobs/compare?a=...&b=...` als Backend

### 💰 Aufwand-Card (#568)

- `<ApplicationAufwandSection>` zeigt aggregierten Aufwand:
  Termine-Anzahl/Dauer, Vorbereitungszeit, Reisekosten netto, sonstige Kosten
- **Empty State** erklaert: „Trage Reisekosten, Tool-Abos oder Pruefungs-
  Gebuehren ein — fuer einen ehrlichen Blick auf den realen Aufwand."
- **Inline-Erfassung**: Kategorie-Dropdown, Betrag, Beschreibung, ein Klick speichert
- Liste bestehender Kosten mit Loeschen-Button

### 🛠️ 8 neue API-Endpoints

- `GET/POST /api/applications/{id}/jobs` — n:m-Verknuepfung
- `DELETE /api/applications/{id}/jobs/{hash}` — Entknuepfen
- `GET /api/applications/{id}/aufwand` — Aufwand-Aggregation
- `GET/POST /api/applications/{id}/costs` — Kosten-Liste/CRUD
- `DELETE /api/costs/{id}` — Kosten loeschen
- `GET /api/jobs/compare?a=...&b=...` — Stellen-Vergleich

### Stats

- **121 MCP-Tools** (unveraendert)
- **8 neue Tests** in `tests/test_v170_beta11.py`, alle gruen (191 total)
- **3 neue Frontend-Components** in `ApplicationsPage.jsx`

### 📦 Wie installiere oder aktualisiere ich PBP?

> ⚠️ Pre-Release / Beta. Stable bleibt v1.6.9.

#### Windows

1. **ZIP herunterladen:** [PBP-1.7.0-beta.11.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.11.zip)
2. **Entpacken** + Doppelklick auf **`INSTALLIEREN.bat`**

#### Update von beta.10

Einfach drueberinstallieren — keine Schema-Migration in beta.11.

📖 [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.7.0-beta.10] - 2026-05-05 — Kontakte-Frontend (#563)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Frontend zur Kontaktdatenbank aus beta.4 — End-User-fuehrend mit
Empty-States, Erst-Aktion-Buttons und vordefinierten Rollen.

### 👥 Neue Page „Kontakte"

- **Tab in der Sidebar** (zwischen Bewerbungen und Docs)
- **Empty State** erklaert was Kontakte sind:
  > „Kontakte sind Personen, die mit deiner Jobsuche zu tun haben —
  > Recruiter, Hiring Manager, Interviewer, Mentoren, Kollegen."
  Mit „Ersten Kontakt anlegen"-Button.
- **Liste** als Cards (3-Spalten-Grid auf grossen Screens) mit Rolle-Chips
- **Filter:** Volltext-Suche (Name/E-Mail/Firma) + Rollen-Dropdown
- **Detail-Dialog** mit allen Feldern (Name pflicht, Email/Telefon/Firma/
  Position/LinkedIn optional), 8 vordefinierte Rollen-Tags zum
  Anklicken, Notizen-Feld
- **Verknuepfungs-Liste** im Dialog (welche Bewerbungen/Termine ist
  diese Person verknuepft mit)
- **Loeschen** mit Bestaetigungs-Dialog (FK CASCADE entfernt
  Verknuepfungen automatisch)

### 🔗 „Beteiligte Personen" in Bewerbungs-Detail

Neue Sektion in `<ApplicationContactsSection>` im Bewerbungs-Modal:

- **Empty State:** „Noch niemand verknuepft. Wer war beim Interview dabei?"
- **Inline-Add-Workflow** ohne Modal:
  - Rolle-Dropdown (Recruiter/Hiring Manager/Interviewer/HR/...)
  - Suche im vorhandenen Kontakt-Pool
  - ODER Direkt-Anlage „Neue Person anlegen" mit Vor-und-Nachname
- **Bestehende Verknuepfungen** als Liste mit Rolle-Chip + ✕-Button zum
  Entfernen

### 🛠️ 8 neue API-Endpoints

- `GET /api/contacts?search=&role=&company=` — Liste mit Filter
- `POST /api/contacts` — Anlegen
- `PUT /api/contacts/{id}` — Aktualisieren
- `DELETE /api/contacts/{id}` — Loeschen
- `GET /api/contacts/{id}/links` — Forward-Lookup
- `POST /api/contacts/{id}/links` — Verknuepfen
- `DELETE /api/contacts/links/{link_id}` — Entknuepfen
- `GET /api/applications/{id}/contacts` — Reverse-Lookup pro Bewerbung

### Stats

- **121 MCP-Tools** (unveraendert)
- **11 neue Tests** in `tests/test_v170_beta10.py`, alle gruen (183 total)
- **Neue Frontend-Datei:** `pages/ContactsPage.jsx` (368 Zeilen)
- **Erweiterte Frontend-Datei:** `pages/ApplicationsPage.jsx` (+`ApplicationContactsSection`)

### 📦 Wie installiere oder aktualisiere ich PBP?

> ⚠️ Pre-Release / Beta. Stable bleibt v1.6.9.

#### Windows

1. **ZIP herunterladen:** [PBP-1.7.0-beta.10.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.10.zip)
2. **Entpacken** + Doppelklick auf **`INSTALLIEREN.bat`**

#### Update von beta.9

Einfach drueberinstallieren — keine Schema-Migration in beta.10.

📖 [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.7.0-beta.9] - 2026-05-05 — CSV-Export + Datenschutz-Selbstauskunft

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

(beta.8 — External Inbound Thunderbird/Outlook/iCal — wurde uebersprungen
weil externes Tooling-Setup beim User noetig ist.)

### 📊 CSV-Export (#578)

- **`GET /api/applications/export.csv`** — Bewerbungen als CSV
- **`GET /api/jobs/export.csv?filter=alle|aktiv|aussortiert`** — Stellen
- **`GET /api/contacts/export.csv`** — Kontakte (Tags als '; '-getrennt)
- **UTF-8 mit BOM** — Excel oeffnet ohne Encoding-Probleme
- **Deutsches Datumsformat** (DD.MM.YYYY) bei ISO-Datums-Feldern
- **Pflicht-Spalten in Deutsch** — keine techniknames

### 🔒 Datenschutz-Selbstauskunft (#581)

- **`GET /api/privacy/self-disclosure.pdf`** — DSGVO-Art-15-tauglicher
  Datenauskunft-PDF
- 5 Sektionen: Persoenliche Daten / Datenumfang (Anzahlen) /
  Speicher-Orte / Daten-Externalisierung (was an wen geht) / Hinweise
- **Keine sensitiven Inhalte** — nur Metadaten und Anzahlen
- Funktioniert auch ohne Profil (Fallback-Text)
- Verwendung: Beratungsgespraech, Datenschutz-Behoerde, Erklaerung
  fuer Familie/Freunde

### Stats

- **121 MCP-Tools** (unveraendert)
- **6 neue Tests** in `tests/test_v170_beta9.py`, alle gruen (172 total)
- **4 neue API-Endpoints** (3 CSV + 1 DSGVO)

### 📦 Wie installiere oder aktualisiere ich PBP?

> ⚠️ Pre-Release / Beta. Stable bleibt v1.6.9.

#### Windows

1. **ZIP herunterladen:** [PBP-1.7.0-beta.9.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.9.zip)
2. **Entpacken** + Doppelklick auf **`INSTALLIEREN.bat`**

#### Update

Einfach drueberinstallieren — keine Schema-Migration in beta.9.

📖 [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.7.0-beta.7] - 2026-05-05 — Bug-Aufraeumung (#518, #526, #527)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

### 🐛 #518 — Follow-up-Typ-Hygiene

- **Neuer `FOLLOWUP_TYPES`-Katalog** in `database.py`:
  - `nachfass` — Nachfass bei Stille (loest Banner aus)
  - `interview_erinnerung` — Interview-Erinnerung (kein Banner)
  - `danke` — Danke-Mail (kein Banner)
  - `info` — Info / Notiz (kein Banner)
  - `sonstiges`
- **`add_follow_up` validiert** den Typ. Unbekannte Typen werden auf
  `sonstiges` normalisiert (vorher landeten sie stillschweigend als
  `nachfass` und loesten Banner-Alarme aus).

### 🐛 #526 — Bundesagentur-Scraper URL

- URL-Format umgestellt von `jobsuche/suche?id={ref_nr}` (Suchergebnis-
  Seite) auf `jobsuche/jobdetail/{ref_nr}` (direkte Stellenanzeige).
- Bestehende Stellen mit alter URL bleiben erhalten — neue Stellen
  bekommen die Detail-URL.

### 🐛 #527 — Freelancermap fehlende Beschreibung

- HTML-Path (Strategie 1, neue Seite seit 2026) holt jetzt fuer die
  ersten 30 Stellen pro Suche die Detail-Beschreibung nach. Vorher gingen
  alle Stellen ohne Beschreibung in den Pool und Score-Berechnung lief
  nur auf dem Titel.
- Limit auf 30 ist konservativ — verhindert dass eine grosse Suche
  hunderte Detail-Requests rauspeitscht.

### Stats

- **121 MCP-Tools** (unveraendert)
- **5 neue Tests** in `tests/test_v170_beta7.py`, alle gruen (166 total)

### 📦 Wie installiere oder aktualisiere ich PBP?

> ⚠️ Pre-Release / Beta. Stable bleibt v1.6.9.

#### Windows

1. **ZIP herunterladen:** [PBP-1.7.0-beta.7.zip](https://github.com/MadGapun/repo/archive/refs/tags/v1.7.0-beta.7.zip)
2. **Entpacken** + Doppelklick auf **`INSTALLIEREN.bat`**

#### Update

Einfach drueberinstallieren — keine Schema-Migration in beta.7.

📖 [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.7.0-beta.6] - 2026-05-05 — Bewerbungsaufwand (#568)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

### 💰 Bewerbungsaufwand (#568)

Schwerpunkt: realer Aufwand pro Bewerbung sichtbar machen — Reisekosten,
Tool-Abos, Vorbereitungszeit, Interview-Runden.

#### Schema v35

- **`application_meetings` erweitert** um:
  - `runde_nr` — Welche Interview-Runde (1, 2, 3...)
  - `vorbereitungszeit_min` — Wie lange Vorbereitung
  - `reise_modus` — `vor_ort` / `video` / `telefon` / `hybrid`
  - `reisekosten_brutto` / `reisekosten_erstattet` — fuer Differenz-Auswertung
- **Neue Tabelle `application_costs`:** id, application_id (optional —
  ermoeglicht „untype"-Kosten wie Tool-Abos die nicht 1:1 einer Bewerbung
  zugeordnet sind), profile_id, kind, amount, description, incurred_at.
- Indizes auf `application_id` und `profile_id`.

#### 5 neue MCP-Tools

- **`meeting_aufwand_setzen`** — Aufwand-Felder an einem bestehenden Termin
  setzen (Runde, Vorbereitungszeit, Reisekosten brutto/erstattet)
- **`kosten_erfassen`** — neue Kosten-Position (kategorie, betrag_eur,
  beschreibung, optional bewerbung_id und datum)
- **`kosten_anzeigen`** — Liste mit Filter und automatischer Summe
- **`kosten_loeschen`**
- **`aufwand_uebersicht`** — Aggregation pro Bewerbung (oder gesamt):
  Kosten-Summe, Reisekosten brutto/erstattet/netto, Vorbereitungszeit-
  Summe, Termin-Dauer-Summe, Termin-Anzahl

### Stats

- **121 MCP-Tools** (vorher 116): +5 neue
- **14 neue Tests** in `tests/test_v170_beta6.py`, alle gruen (161 total)
- **Schema v35** (vorher v34) — `application_meetings` erweitert + neue Tabelle `application_costs`

### 📦 Wie installiere oder aktualisiere ich PBP?

> ⚠️ Pre-Release / Beta. Stable bleibt v1.6.9.

#### Windows

1. **ZIP herunterladen:** [PBP-1.7.0-beta.6.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.6.zip)
2. **Entpacken** + Doppelklick auf **`INSTALLIEREN.bat`**

#### Update von beta.5

Einfach drueberinstallieren — Schema-Migration v34 → v35 laeuft automatisch.

📖 [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.7.0-beta.5] - 2026-05-05 — n:m Bewerbung-Stelle + Skills-Zeitraeume + Stellen-Vergleich

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

Schwerpunkt-Schema-Update — drei zusammengehoerige Themen, alle in einer
Migration v34.

### 🔗 n:m Bewerbung-Stelle (#472)

- **Neue Tabelle `application_jobs`** als Junction zwischen Applications
  und Jobs. `is_primary`-Flag pro Bewerbung (eine primaere Stelle), 
  `version_label` fuer Bezeichnung der Variante.
- **Migration v33→v34:** Bestand wird automatisch migriert — jede
  Bewerbung mit `applications.job_hash` bekommt einen Eintrag in
  `application_jobs` mit `is_primary=1`. `applications.job_hash`
  bleibt erhalten (Backwards-Compat).
- **Idempotente Verknuepfung:** gleicher (application, job)-Kombi gibt
  vorhandene Link-ID zurueck.
- **Primary-Uniqueness:** Wenn `is_primary=True` gesetzt wird, wird
  jede andere Verknuepfung der Bewerbung auf `is_primary=0` gesetzt.

#### 4 neue MCP-Tools

- `bewerbung_stelle_verknuepfen` — eine Bewerbung mit weiteren Stellen
  verknuepfen (z.B. Repost, Vermittler+Endkunde-Sicht, mehrere Varianten)
- `bewerbung_stelle_entknuepfen`
- `bewerbung_stellen_anzeigen` — Forward-Lookup
- `aehnliche_stellen_finden` — Token-Overlap-Algorithmus, liefert
  Top N aehnliche Stellen + Outcome-Hinweis (interview/abgelehnt/aussortiert)

### 🎯 Skills-Zeitraeume (#572)

- **Neue Tabelle `skill_periods`** fuer diskontinuierliche Erfahrung —
  z.B. „Java 2<telefon>, Pause, dann 2022-heute". Pro Zeitraum kann
  ein eigenes Niveau (level 1-5) gesetzt werden.
- **Migration v33→v34:** Bestand aus `skills.start_year`/`end_year`
  (v28) wird automatisch in `skill_periods` gespiegelt.

#### 3 neue MCP-Tools

- `skill_zeitraum_hinzufuegen` — weitere Periode anlegen
- `skill_zeitraeume_anzeigen` — Liste der Zeitraeume
- `skill_zeitraum_loeschen`

### 🆚 Stellen-Vergleich (#580)

- **`stelle_vergleichen(hash_a, hash_b)`** — strukturierte Gegen-
  ueberstellung: Titel-Overlap (gemeinsam/nur A/nur B), Beschreibungs-
  Overlap-Prozent, Score-Diff, Standort, Stellenart, Salary-Bereich,
  „gleiche Firma?".
- **`aehnliche_stellen_finden(hash, max_treffer)`** — siehe oben.

### Stats

- **116 MCP-Tools** (vorher 108): +4 (n:m), +3 (skill_periods), +1 (`stelle_vergleichen`), +1 (`aehnliche_stellen_finden`)
- **15 neue Tests** in `tests/test_v170_beta5.py`, alle gruen (147 total)
- **Schema v34** (vorher v33) — `application_jobs` + `skill_periods` Tabellen, mit Bestands-Migration

### 📦 Wie installiere oder aktualisiere ich PBP?

> ⚠️ Pre-Release / Beta. Stable bleibt v1.6.9.

#### Windows

1. **ZIP herunterladen:** [PBP-1.7.0-beta.5.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.5.zip)
2. **Entpacken** + Doppelklick auf **`INSTALLIEREN.bat`**

#### Update von beta.4

Einfach drueberinstallieren — Schema-Migration v33 → v34 laeuft automatisch.

📖 [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.7.0-beta.4] - 2026-05-05 — Kontaktdatenbank Backend (#563)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

### 👥 Kontaktdatenbank — Backend

Schema, DB-Helpers, MCP-Tools fuer eine zentrale Personen-Entitaet mit
Historie ueber Bewerbungen, Stellen, Mails und Meetings.

**Designprinzip:** Rollen als Tags (JSON-Array), nicht als eigener Typ.
Eine Person kann z.B. gleichzeitig 'recruiter' und 'hiring_manager' sein —
in verschiedenen Kontexten verschiedene Rollen.

### 🗃️ Schema v33

- **`contacts`-Tabelle:** id, profile_id, full_name, email, phone,
  linkedin_url, company, position, tags (JSON), notes, created_at, updated_at.
- **`contact_links`-Tabelle:** Verknuepft Kontakt mit Bewerbung/Meeting/
  Job/Firma + optionale Rolle in diesem Kontext + Notizen. FK CASCADE-DELETE
  auf contacts.id.
- Indizes auf `profile_id`, `email`, `company`, plus zwei auf contact_links
  fuer schnelle Forward+Reverse-Lookups.

### 🛠️ DB-API

- `add_contact`, `get_contact`, `update_contact`, `delete_contact`
- `list_contacts(search, role, company)` mit drei Filtern
- `link_contact(contact_id, target_kind, target_id, role)` — idempotent
  (gleicher Kontakt + Ziel + Rolle = vorhandene Link-ID zurueck)
- `get_contact_links(contact_id)` — Forward-Lookup
- `get_contacts_for_target(target_kind, target_id)` — Reverse-Lookup
- `_serialize_contact_row` mit `tags` als Liste (nicht JSON-String) und
  `id_typed` mit `CON-`-Praefix

### 🤖 8 neue MCP-Tools

- `kontakt_anlegen` — mit Pflichtfeld `name` und optionalen `email`,
  `firma`, `position`, `telefon`, `linkedin_url`, `rollen`, `notizen`
- `kontakt_anzeigen` — Detail inkl. Verknuepfungen
- `kontakte_auflisten` — mit Filtern `suche`, `rolle`, `firma`
- `kontakt_bearbeiten` — partielle Updates (None = nicht aendern)
- `kontakt_loeschen` — mit `bestaetigung=True`
- `kontakt_verknuepfen` — `ziel_typ`-Mapping (bewerbung→application,
  meeting/termin→meeting, stelle/job→job, firma→company)
- `kontakt_entknuepfen`
- `kontakte_zu_bewerbung` — Reverse-Lookup pro Bewerbung mit Rollen

### Stats

- **108 MCP-Tools** (vorher 100): +8 `kontakt_*`-Tools (#563)
- **16 neue Tests** in `tests/test_v170_beta4.py`, alle gruen (132 total)
- **Schema v33** (vorher v32) — neue Tabellen `contacts`, `contact_links`

### 📦 Wie installiere oder aktualisiere ich PBP?

> ⚠️ Pre-Release / Beta. Stable bleibt v1.6.9.

#### Windows

1. **ZIP herunterladen:** [PBP-1.7.0-beta.4.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.4.zip)
2. **Entpacken** + Doppelklick auf **`INSTALLIEREN.bat`**

#### Update von beta.3

Einfach drueberinstallieren — Schema-Migration v32 → v33 laeuft automatisch.

#### Frontend-UI

Die UI fuer Kontakte (Liste, Detail, „Beteiligte"-Sektion in Bewerbungen)
folgt in beta.5/6. In beta.4 sind die Kontakte ueber die MCP-Tools
(Claude) bereits voll nutzbar.

📖 [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.7.0-beta.3] - 2026-05-05 — Globale Suche + Doku-Kategorien

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.9.

### 🔍 Globale Suche (#571)

- **Neuer Endpoint `GET /api/search?q=...&limit=N`** — DB-weite Suche
  ueber 6 Entitaeten: Bewerbungen, Stellen, Skills, Dokumente, E-Mails,
  Termine. Treffer werden gruppiert nach Entitaet zurueckgegeben (mit
  typisierten IDs aus #505).
- **Header-Suchleiste** (`<GlobalSearch>`) im Frontend, debounced 280ms,
  Dropdown mit gruppierten Treffern, Klick navigiert zur jeweiligen
  Detail-Seite. Ausserhalb-Click schliesst das Dropdown.

### 📂 Doku-Kategorien-Verfeinerung (#538)

`_detect_doc_type` erkennt jetzt **6 neue Cluster** zusaetzlich zu den
bestehenden — vorher landeten 58% aller Dokumente in 'sonstiges'.

Neue Typen:
- **`recruiter_anfrage`** — Inbound-Mails mit Vakanz-Anfragen
- **`interview_transkript`** — Mitschriften / Transcripts
- **`interview_einladung`** — Einladungen zu Vorstellungsgespraechen
- **`eingangsbestaetigung`** — „Vielen Dank fuer Ihre Bewerbung"
- **`absage`** — „Leider muessen wir Ihnen mitteilen"
- **`angebot`** — Vertragsangebote, Projektangebote
- **`vorbereitung`** erweitert: erkennt jetzt auch „Spickzettel"

Pattern-Matching erfolgt zuerst per Filename, dann per Inhalt
(Schluesselsatz-Heuristik). Die alten Typen (lebenslauf, anschreiben,
zeugnis, ...) sind unveraendert.

### Stats

- **100 MCP-Tools** (unveraendert)
- **12 neue Tests** in `tests/test_v170_beta3.py`, alle gruen (116 total)
- **Neue Backend-Endpoints:** `GET /api/search`
- **Frontend:** neuer `<GlobalSearch>`-Header-Component

### 📦 Wie installiere oder aktualisiere ich PBP?

> ⚠️ Pre-Release / Beta. Stable bleibt v1.6.9.

#### Windows

1. **ZIP herunterladen:** [PBP-1.7.0-beta.3.zip](https://github.com/MadGapun/repo/archive/refs/tags/v1.7.0-beta.3.zip)
2. **Entpacken** + Doppelklick auf **`INSTALLIEREN.bat`**

#### Update von beta.1/beta.2

Einfach drueberinstallieren — keine Schema-Migration in beta.3.

📖 [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.7.0-beta.2] - 2026-05-05 — Lokale AI Real + Stilarchiv

> ⚠️ **Pre-Release / Beta** — empfohlen nur fuer Tester. Stable bleibt v1.6.9.

Macht aus der beta.1-Foundation ein **funktionierendes lokales AI-Setup**.
Plus das erste echte Anwender-Feature: das Stilarchiv fuer Anschreiben/
Lebenslaeufe. Mit der lokalen AI muss Claude nicht mehr „bei null" anfangen
wenn ein neues Anschreiben geschrieben wird.

### 🤖 Lokale AI — echte Ollama-Integration (#512)

- **`LLMService.run()` ist jetzt echt** — synchroner HTTP-Call an
  `POST /api/generate` mit JSON-Response, Fallback auf Claude wenn Aufruf
  scheitert oder Modell fehlt.
- **Prompt-Builders + Response-Parsers** fuer die ersten zwei Tasks:
  - `CLASSIFY_DOCUMENT`: 10 Kategorien (lebenslauf, anschreiben, ...),
    deterministisches Ein-Wort-Output, Parser mit Fallback auf
    'sonstiges' bei unbekanntem Output
  - `EXTRACT_SKILLS`: kommagetrennte Liste, Parser entfernt Bullets/
    Whitespace/Praefix-Striche
- **`LLMService.list_models()`** — liste der lokal verfuegbaren Ollama-
  Modelle mit Metadaten.
- **`LLMService.trigger_pull(model_name)`** — synchroner Modell-Download
  via `POST /api/pull`. Streaming-Fortschritt kommt spaeter.

### 🛠 Neue API-Endpoints (#583)

- **`PUT /api/llm/model`** — Aktives Modell setzen.
- **`POST /api/llm/pull`** — Modell-Download triggern.
- **`GET /api/llm/recommended-models`** — Liste der von PBP empfohlenen
  Modelle (Llama 3.2 3B / Qwen 2.5 7B / Qwen 2.5 14B) mit Metadaten.

### 🎨 Frontend — Settings-Bereich „Lokale KI"

Neuer Tab in den Einstellungen mit drei Modi:

- **Nicht installiert:** Erklaerung mit Vor-/Nachteilen, Link zu
  ollama.com/download, „Status neu pruefen"-Button.
- **Ollama erkannt, kein Modell:** Modell-Auswahl mit Klein/Standard/Gross,
  „GB laden"-Button mit Toast bei Erfolg/Fehler. Standard-Modell wird
  automatisch nach Download als aktiv gesetzt.
- **Modell installiert:** Status-Karte (Modell, Aktiv/Pausiert/Aus),
  Modell-Wechsler bei mehreren installierten Modellen, Endpoint-Anzeige.

### ✍️ Stilarchiv (#577)

- **Schema v32:** Neue Tabelle `document_versions` mit Feldern
  `kind`, `title`, `content`, `word_count`, `application_id`, `outcome`,
  `created_at`, `notes`. Index auf `(profile_id, kind, created_at DESC)`.
- **DB-Helpers:** `add_document_version`, `get_recent_document_versions`
  (mit Filter `only_with_outcome`), `update_document_version_outcome`.
- **3 neue MCP-Tools:**
  - **`stilarchiv_speichern`** — eine Anschreiben-/Lebenslauf-Version
    ablegen (mit optionaler Verknuepfung zur Bewerbung + Outcome).
  - **`stilarchiv_kontext`** — die letzten N Versionen als Kontext fuer
    Claude/lokale AI bei der Generierung. Der Hinweis-Text instruiert
    explizit: „Stil und Tonfall uebernehmen, Inhalt neu auf die konkrete
    Stelle ausrichten" — kein 1:1-Kopieren.
  - **`stilarchiv_outcome_setzen`** — nachtraegliches Markieren mit
    `interview` / `abgelehnt` / `ohne_antwort` / `angebot` /
    `zurueckgezogen`. Erlaubt Erfolgs-bias bei der Kontext-Auswahl.

### 🔧 Release-Hygiene

- **`release_check.py`** versteht jetzt PEP-440-/SemVer-Aequivalenz.
  `1.7.0-beta.1` (SemVer) und `1.7.0b1` (PEP 440 kanonisch) gelten als
  identisch. Vorher war ein Pre-Release-Tag im pyproject.toml ein
  Release-Blocker.

### Stats

- **100 MCP-Tools** (vorher 97): +`stilarchiv_speichern`, `stilarchiv_kontext`, `stilarchiv_outcome_setzen` (#577)
- **18 neue Tests** in `tests/test_v170_beta2.py`, alle gruen (104 total)
- **Schema v32** (vorher v31) — neue Tabelle `document_versions`
- **3 neue API-Endpoints** + erweiterte LLM-Service-Klasse

### 📦 Wie installiere oder aktualisiere ich PBP?

> ⚠️ Dies ist ein **Pre-Release / Beta**. Empfohlen nur fuer Tester — der stabile Stand bleibt v1.6.9.

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.2.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.2.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
git checkout v1.7.0-beta.2
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade (v31 → v32) laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Lokale AI ausprobieren

Nach dem Update auf v1.7.0-beta.2:

1. **Ollama installieren:** [ollama.com/download](https://ollama.com/download) (Windows/macOS/Linux)
2. PBP-Dashboard oeffnen → Sidebar zeigt jetzt 🟡 „Lokale KI: kein Modell"
3. **Einstellungen → Lokale KI** → „Standard (Qwen 2.5 7B, 4.7 GB)" laden
4. Nach dem Download steht der Indicator auf 🟢 Aktiv — fertig.

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ) · [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.7.0-beta.1] - 2026-05-05 — Foundation: Lokale AI + Typisierte IDs + Recap

**Pre-Release** — der Auftakt zur v1.7.0-Serie. Master-Roadmap: #575.
v1.6.9 bleibt der „Latest"-Stand fuer normale Anwender.

Beta.1 legt vier Grundsteine, auf denen die naechsten Betas aufbauen.
Echte Features fuer den Anwender folgen in beta.2 — diese Beta ist
**Foundation-Arbeit**.

### 🤖 Lokale AI — Foundation (#512, #583)

- **`services/llm_service.py`** — zentraler Dispatcher fuer alle LLM-Aufrufe.
  Routing-Tabelle entscheidet pro Task-Typ: Lokal (Ollama) bevorzugt,
  Claude als Fallback, Manuell als letzter Ausweg.
- **Aufgabenteilung im Code festgeschrieben:**
  - Lokal-faehig: CLASSIFY_DOCUMENT, EXTRACT_SKILLS, MATCH_JOB_TO_SKILLS,
    EXTRACT_SALARY, COMPARE_JOBS, FIND_SIMILAR_JOBS
  - Claude-bevorzugt: GENERATE_COVER_LETTER, INTERVIEW_COACHING,
    SALARY_NEGOTIATION, COMPANY_RESEARCH, GENERATE_DAILY_IMPULSE
- **Status-Erkennung mit 30s-Caching** — HTTP-Check auf
  `localhost:11434/api/tags`. Mock-Modus via `PBP_LLM_MOCK=1` fuer Tests.
- **API-Endpoints** `/api/llm/status` (GET) und `/api/llm/state` (PUT)
  fuer Frontend-Anbindung.

**In beta.1 noch nicht aktiv:** echte Ollama-Calls. Wenn LOCAL gewaehlt
wuerde, faellt der Service auf CLAUDE zurueck. Echte Anbindung +
Setup-Wizard kommt in beta.2.

### 🤖 Lokale AI — UI-Indicator (#583)

- **Status-Indicator in der Sidebar** unter dem MCP-Indicator. Fuenf
  Zustaende: rot (nicht installiert), gelb (kein Modell), grau
  (deaktiviert), gelb (pausiert), gruen (aktiv).
- **Erklaerungs-Modal** beim Klick: Vorteile (Tokens-sparen UND
  kostenlos!), Nachteile (4-5 GB Modell, RAM-Bedarf), Hinweis dass die
  Einrichtung in der naechsten Beta kommt.
- **60s-Polling** im App-State haelt den Indicator aktuell.

### 🆔 Typisierte IDs (#505 — Variante A, nicht-breaking)

- Neuer Helper `services/typed_ids.py`:
  - `format_id(IdKind.APPLICATION, "42061e46")` → `"APP-42061e46"`
  - `parse_id("APP-42061e46")` → `(IdKind.APPLICATION, "42061e46")`
  - `validate_id(IdKind.APPLICATION, value)` — wirft `TypedIdMismatch`
    bei falschem Praefix, durchwinkt nackte Hex-IDs (Backwards-Compat)
- **12 Entitaetstypen** definiert: APP (Bewerbung), JOB (Stelle), DOC
  (Dokument), EVT (Event), APT (Termin), EML (E-Mail), PRO (Profil),
  POS (Position), PRJ (Projekt), SKL (Skill), EDU (Ausbildung),
  FUP (Follow-up).
- **Serializer-Erweiterung:** `_serialize_application_row` und
  `_serialize_job_row` ergaenzen `id_typed` und `hash_typed` neben den
  unveraenderten Feldern. Keine Breaking-Changes fuer Frontend.
- **Erste Tool-Adoption:** `bewerbung_details` validiert die ID am
  Eingang — bei Uebergabe von z.B. `DOC-d60ac54b` kommt eine klare
  Fehlermeldung statt „Bewerbung nicht gefunden".

### 🆕 Recap-Funktion (#576)

- **Neuer Endpoint `/api/recap`** — aggregiert was seit dem letzten
  Login passiert ist:
  - Neue Stellen (mit Top-3 nach Score)
  - Neue Bewerbungen
  - Neue E-Mails
  - Statuswechsel
  - Faellige Follow-ups
  - Anstehende Termine (naechste 7 Tage)
- **`last_login_at`** wird beim Aufruf aktualisiert — naechste Recap
  zeigt das Fenster ab jetzt. Erst-Aufruf nutzt 72h-Fenster.
- **Recap-Card auf dem Dashboard** zeigt die Zaehler als anklickbare
  Bloecke (springen direkt zum jeweiligen Bereich).
- **Auto-Hide** wenn nichts passiert ist (`has_anything=false`).
- **Manuell ausblendbar** bis morgen via [x]-Button (LocalStorage).

### 📦 Versionierung & Pre-Release

- **`v1.7.0-beta.1`** wird mit `gh release create --prerelease`
  veroeffentlicht — **NICHT** als „Latest". v1.6.9 (oder spaetere
  Hotfixes) bleibt der empfohlene Stand fuer normale Anwender.
- **SemVer**: `1.7.0-beta.1` → `-beta.N` → `-rc.1` → `1.7.0` final.
- **Hotfix-Lane** auf v1.6.x bleibt offen — falls dort Bugs auftauchen,
  patchen wir parallel zu den 1.7-Betas.

### Stats

- **97 MCP-Tools** (unveraendert)
- **20 neue Tests** in `tests/test_v170_beta1_foundation.py`, alle gruen (120 total)
- **2 neue Backend-Module:** `llm_service.py`, `typed_ids.py`
- **2 neue API-Endpoints:** `/api/recap`, `/api/llm/status` (+`/api/llm/state` PUT)

### 📦 Wie installiere oder aktualisiere ich PBP?

**Hinweis:** Dies ist ein **Pre-Release / Beta**. Empfohlen nur fuer Tester
oder zum Ausprobieren — der stabile Stand bleibt v1.6.9.

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.1.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.1.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
git checkout v1.7.0-beta.1
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ) · [v1.7.0 Roadmap](https://github.com/MadGapun/PBP/issues/575)

---

## [1.6.9] - 2026-05-05 — Hash- & Datum-Hygiene + Quick-Wins

Sammel-Release fuer das Bug-Cluster aus den letzten Test-Sessions: drei
zusammenhaengende Bugs (#565, #567, #574) hatten dieselbe Wurzel —
inkonsistente Datentypen die unter bestimmten Umstaenden zu Daten-
Korruption fuehrten ("Tool meldet 'angelegt', Stelle ist nicht
auffindbar"). Plus 5 Quick-Wins on top.

### 🚨 Kritischer Bug-Cluster gefixt

- **#565 + #567 — `datetime` tz-aware durchgezogen.** `find_duplicate_job`
  verglich `datetime.now()` (naive) mit `found_at` aus der DB (aware) und
  warf `TypeError: can't subtract offset-naive and offset-aware datetimes`.
  `_parse_iso` gibt jetzt IMMER tz-aware zurueck (Legacy-naive Werte werden
  als UTC interpretiert), `find_duplicate_job` nutzt
  `datetime.now(timezone.utc)`.

- **#567 — Duplikat-Filter zweistufig korrigiert.** Vorher blockte JEDER
  alte Eintrag bei einer Firma — selbst wenn die Bewerbung schon
  abgelehnt war oder die Stelle aussortiert. Jetzt:
  - **Stufe A:** Laufende Bewerbung (NICHT abgelehnt/abgelaufen/
    zurueckgezogen/angenommen) mit Titel-Match → blocken.
  - **Stufe B:** Identische AKTIVE Stelle → idempotent vorhandenen
    Hash zurueckgeben (statt blocken).
  - **Stufe C:** Aussortierte/abgeschlossene Eintraege blocken NICHT.

- **#574 — Hash-Format Migration v31.** Die `jobs`-Tabelle hatte zwei
  Hash-Formate gemischt: `33c272d736ba` (Format A, alt) und
  `e913acc3:33c272d736ba` (Format B, scoped). `stellen_anzeigen()`
  matchte nur Format B → 35 Alteintraege wurden unterschlagen.
  Migration vereinheitlicht alle auf Format B (FK temporaer deaktiviert,
  applications.job_hash mit-migriert).

- **#574 Fix 2 — `dismiss_reason` Format vereinheitlicht.** Mal als
  Plain-String, mal als JSON-Array gespeichert. Migration normalisiert
  Plain-Strings zu `["..."]`. `_serialize_job_row` liefert jetzt
  defensiv beide Varianten:
  - `dismiss_reason` (Plain-String, erstes Element) — fuer Backwards-Compat
  - `dismiss_reasons` (Liste) — fuer Konsumenten die alle Gruende wollen

### 🐛 Direkt-Upload-Duplikate (#570)

- Frontend: `uploadDocumentFile(file, docType, { applicationId })` —
  Backend verknuepft beim Upload automatisch.
- Backend: SHA256-Hash-basierte Deduplizierung. Wenn dasselbe File-Inhalt
  schon im aktiven Profil existiert, wird **kein neues Dokument
  angelegt** — stattdessen das vorhandene verknuepft. Antwort enthaelt
  `duplicate_of: <doc_id>`.

### ⚡ Quick-Wins on top

- **#547 — Auto-Quarantaene erweitert.** Status=ok + count=0 +
  time_s>60s wird jetzt als `silent_timeout` markiert (vorher nur
  „silent"). Beispiel: jobware mit 237s Laufzeit → eindeutig als
  haengend erkennbar.
- **#548 — Quellen-Counter mathematisch korrekt.** Vorher „10/18" ohne
  nachvollziehbare Mathematik. Jetzt aus `quellen_status` abgeleitet:
  `"X von Y Quellen ok, Z uebersprungen, W Timeout, V Fehler"`.
- **#551 — Fortschritts-Phase explizit.** Statt 60-90s lang „0% —
  Durchsuche 11 Quellen parallel..." beginnt der Lauf jetzt bei 5% mit
  „Initialisiere 11 Quellen..." — User sieht sofort dass etwas passiert.
- **#569 — Dokumentenliste Workflow-Sortierung.** Standard-Sort:
  `nicht_extrahiert > basis_analysiert > extrahiert/manuell_korrigiert >
  angewendet > verworfen/duplikat`, dann Datum DESC. Bei 167+ Dokumenten
  findet der User die TODO-Eintraege ohne Filter zu setzen.
- **#554 — Neues MCP-Tool `scores_neu_berechnen`.** Recompute aller
  (aktiven) Stellen-Scores. Sinnvoll nach Aenderungen an Suchkriterien,
  Profil oder Scoring-Reglern. Mit `nur_aktive` und `max_stellen` als
  optionale Parameter. Liefert delta-Statistik (durchschnittliche
  Aenderung, max Anstieg/Rueckgang).

### Stats

- **97 MCP-Tools** (vorher 96): +`scores_neu_berechnen` (#554)
- **12 neue Tests** in `tests/test_v169_hash_datum.py`, alle gruen (103 total)
- **Schema v31** (vorher v30) — Hash-Format-Migration + dismiss_reason-Normalisierung
- 9 Issues geschlossen: #547, #548, #551, #554, #565, #567, #569, #570, #574

### Migration

- **Datenbank:** automatischer Schema-Upgrade beim ersten Start.
  - Hash-Migration: Format-A-Eintraege werden zu Format B umgestellt
    (idempotent, FK temporaer deaktiviert).
  - dismiss_reason: Plain-Strings werden zu `["..."]` normalisiert.
  - Backup laeuft eh automatisch beim Upgrade (Ordner `data\backups\`).
- **API:** Tool-Returnwert `stelle_manuell_anlegen` enthaelt jetzt im
  Idempotenz-Fall `status: "bereits_vorhanden"` und den existierenden
  `hash`. Aufrufer sollten beide Faelle handhaben.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.6.9.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.6.9.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.6.8] - 2026-04-29 — Bericht-Hotfix: irrefuehrende Bloecke entfernt

Hotfix nach Real-Sicht des v1.6.6/1.6.7-Berichts. Drei Bloecke produzierten
Zahlen, die zwar plausibel aussahen aber inhaltlich nicht trugen — und dadurch
schlechter waren als kein Block. Konsequenz: raus, bis die Datenbasis stimmt.

### 🗑 Entfernt aus dem Bewerbungsbericht

- **„Aktive Filter-Arbeit"-Block (Executive Summary).** Suggerierte „nur
  1 Stelle wuerdig befunden", weil der Zaehler ueber `dismiss_reason`/
  `is_active=0` lief. In der Realitaet werden viele Bewerbungen ueber den
  Chat per Direct-Add angelegt — die zugehoerige Stelle wurde nie ueber
  `stelle_bewerten('passt')` markiert und blieb in `aktiv` haengen oder
  in `aussortiert` mit Grund `bewerbung_erstellt`. Die Zahl ist ohne
  Kontext irrefuehrend.
- **„Geschaetzter Zeitaufwand"-Block (Executive Summary).** Heuristik
  (Bewerbungen 30min, Aussortierung 1min, Interviews 90min) lag um
  Groessenordnungen daneben — realer Aufwand sind Stunden bis Tage pro
  Stelle (Recherche, Anschreiben-Iteration, Korrektur Umlaute/Format,
  Interview-Vorbereitung, Dossiers fuer Trainings/Firmen-Studium). 63h
  fuer 4 Monate ist ein Witz.
- **Sektion 13 „Bewerbungs-Trichter".** Die Stufen waren in sich nicht
  schluessig: 1027 aktiv aussortiert + 68 beworben passt nicht zu 1028
  gesichtet, weil Bewerbungen auch ueber Direct-Add aus externen Quellen
  kommen, nicht nur aus dem gesichteten Pool. Solange die Modellierung
  diesen Pfad nicht abbildet, ist der Trichter ein Zerrspiegel.

### 📐 Bericht-Struktur jetzt

10 Hauptsektionen + 2 neue (11 Aktivitaetsprotokoll, 12 Quellen-Aktivitaet)
+ optional 13 Beraterkommentar. Cover-Page Arbeitsamt-Block bleibt.
Footer „Erstellt am ... | Seite X / Y" auf jeder Seite bleibt.

### 🎯 Designprinzip festgehalten

In `CLAUDE.md` als Regel ergaenzt: **Kennzahlen, deren Datenbasis nicht
zuverlaessig ist, kommen nicht in den Bericht.** Lieber eine Sektion
weglassen als eine irrefuehrende Zahl drucken.

### Stats

- **96 MCP-Tools** (unveraendert)
- **Tests:** 14 v1.6.6/v1.6.7 grun, ein Test angepasst (#540 erwartet jetzt
  Trichter/Effort als „nicht im Text").

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.6.8.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.6.8.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.6.7] - 2026-04-29 — Schnellzugriff-Cleanup + Quick-Wins (#561, #562, #515, #552)

Folge-Release am gleichen Tag, getrieben von User-Feedback: „Wir haben die
Schnellzugriff-Aufraeumung (#561, #562) bei v1.6.6 vergessen — und es sind
immer noch 42 Issues offen". Diese Runde holt das nach.

### 🎨 Frontend

- **#561 — Schnellzugriff zurueck auf kuratiertes 4×3-Grid.** Werbe-
  Screenshot-tauglich, 12 Karten in 4 Kategorien:
  - „Profil" (vorher „Erste Schritte"): Kennenlernen, Wo stehe ich?,
    Dokumente analysieren
  - „Jobsuche & Bewerbung": Jobsuche starten, Bewerbung schreiben,
    Inbound erfassen
  - „Interview & Verhandlung": Interview vorbereiten, Uebungsgespraech,
    Gehalt verhandeln
  - „Analyse & Strategie": Staerken erkennen, Profil-Check (vorher
    „Profil pruefen"), Aus Absagen lernen
  Entfernt: „Uebersicht", „Netzwerk aufbauen", „Tipps & Tricks" —
  diese sind im neuen Hilfe-Reiter „Prompts" verfuegbar.

- **#562 — Hilfe & Support: Neuer Reiter „Prompts".** Vollstaendige
  Liste aller verfuegbaren MCP-Prompts mit Befehl, Titel,
  Kurzbeschreibung und „Kopieren"-Button. Filter-Suchfeld oben.
  Gruppiert nach denselben Kategorien wie der Schnellzugriff plus
  „Weitere" fuer Prompts, die im Schnellzugriff nicht auftauchen
  (`/profil_sync`, `/faq`, `/bewerbung_vorbereitung`).

- **#515 — Banner „Faellige Nachfassaktionen zuerst schliessen" hat
  jetzt einen Klick.** Setzt den Spezial-Filter „Nachfrage faellig"
  und scrollt zur „Offene Aktionen"-Sektion. Vorher rein informativ.

### 🔧 Backend

- **`GET /api/prompts`** — neuer Endpoint, listet alle verfuegbaren
  MCP-Prompts mit Metadaten (Kategorie, Titel, Kurzbeschreibung).
  Stabile Sortierung nach Kategorie + Titel.

### 🐛 Score-Drift

- **#552 — `salary_estimated=True` reduziert den Gehalts-Score-Beitrag
  um 50%.** Vorher hatten alle Stellen mit geschaetztem Gehalt den
  vollen Score-Faktor (Gewicht 8) — was die Sortierung verzerrte, weil
  spekulative Werte gleich behandelt wurden wie extrahierte. Jetzt:
  geschaetzte Gehaelter zaehlen nur halb, im `fit_analyse`-Output gibt
  es ein neues Feld `source: "geschaetzt" | "extrahiert"` und der
  Detail-Text enthaelt „(geschaetzt, 0.5x)".

### Stats

- **96 MCP-Tools** (unveraendert)
- **5 neue Tests** in `tests/test_v167_quickfixes.py`, alle gruen (92 total)
- 4 Issues in dieser Runde geschlossen: #515, #552, #561, #562

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.6.7.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.6.7.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.6.6] - 2026-04-29 — Bewerbungsbericht-Aufwertung (#540)

Mittwoch-Morgen-Sprint zur Aufwertung des PDF-Bewerbungsberichts. Treiber:
Anwender, die ihren Bericht beim Arbeitsamt vorlegen muessen, brauchen
einen formal-tauglichen Beleg ihrer Bewerbungs-Aktivitaeten — vollstaendig,
nachvollziehbar, beeindruckend. Gleichzeitig darf der Bericht nicht
verkomplizieren fuer Anwender, die ihn nur fuer sich selbst nutzen.

### 🎯 Neuer Inhalt im Bericht

- **Cover-Page:** Optionaler Arbeitsamt-Block (BA-Vermittlungsnummer,
  Aktenzeichen, Berater-Name, Beratungsstelle) — nur sichtbar wenn der
  Master-Toggle aktiv ist UND mindestens ein Feld gefuellt. Felder bleiben
  beim Toggle-Aus erhalten — kein Loeschen/Neueintippen noetig.
- **Sektion 11 „Aktivitaetsprotokoll":** Chronologische Timeline aller
  wichtigen Bewerbungs-Ereignisse (Bewerbung, Statuswechsel) mit Datum,
  Bewerbung, Status. Bis zu 60 Eintraege.
- **Sektion 12 „Quellen-Aktivitaet":** Suchaufwand pro Job-Portal — wie
  oft durchsucht, wie viele Treffer, letzter Lauf. Liefert das Argument
  „ich habe meinen Suchaufwand strukturiert dokumentiert".
- **Sektion 13 „Bewerbungs-Trichter":** Funnel-Visualisierung gesichtet →
  aussortiert → beworben → Antwort → Interview → Angebot mit Balken und
  Prozentangaben (#521).
- **Sektion 14 „Beraterkommentar" (optional):** Acht leere Linien fuer
  handschriftliche Anmerkungen — nur sichtbar wenn Toggle aktiv.
- **Effort-Proxy in Executive Summary:** Geschaetzter Zeitaufwand
  (Bewerbungen 30min, Aussortierung 1min, Interviews 90min, Follow-ups
  5min) — konservative Untergrenze ohne Vorbereitungszeit.
- **Per-Seite-Footer:** „Erstellt am ... | Seite X / Y" auf jeder Seite.
  Loest den alten redundanten Closing-Block am Berichtende ab.

### 🔧 Tool-Konsistenz

- **`/api/settings/report`** GET/PUT — speichert Bericht-Optionen pro
  Profil. Felder: `arbeitsamt_block_enabled` (bool, Master-Toggle),
  `ba_vermittlungsnummer`, `ba_aktenzeichen`, `ba_berater_name`,
  `ba_berater_stelle`, `berater_kommentar_block` (bool).
- **`generate_application_report` und `generate_excel_report`** akzeptieren
  jetzt `report_settings: dict | None`. Backwards-kompatibel — alte Aufrufe
  ohne den Parameter funktionieren weiter.
- **`get_report_data()`** liefert zusaetzlich `scraper_health` fuer die
  neue Quellen-Aktivitaets-Sektion.

### 🎨 Frontend

- **Einstellungen → System** hat eine neue Card „Bewerbungsbericht" mit
  Master-Toggle, vier optionalen Feldern und Beraterkommentar-Toggle.
  Felder sind ausgegraut wenn der Master-Toggle aus ist.
- **Statistiken-Seite** hat einen manuellen Zeitraum-Picker (von-bis)
  fuer den Bericht-Export. Ueberschreibt die Preset-Auswahl wenn
  ausgefuellt; leer = Preset gilt weiter.

### 🐛 Fixes

- **#560** — `/tipps_und_tricks` und `/profil_sync` waren in
  prompts.py registriert, aber nicht im `_prompt_registry` der
  Workflows-Datei. Folge: Klick auf die Karten im Schnellzugriff zeigte
  „Anleitung konnte nicht geladen werden". Jetzt Delegation an die
  FastMCP-Prompt-Registry.

### Stats

- **96 MCP-Tools** (unveraendert)
- **10 neue Tests** in `tests/test_v166_bericht.py`, alle gruen
- Bericht-Sektionen: 10 → 13 (+ optional 14)

### Migration

- Keine Schema-Migration noetig. Neue Settings landen in `settings`-Table
  als profile-scoped Keys (`{pid}:report_*`).
- Bestehende Berichts-Aufrufe ohne `report_settings`-Parameter funktionieren
  unveraendert — neuer Block wird einfach nicht gerendert.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.6.6.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.6.6.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.6.5] - 2026-04-29 — Real-Case-Polish (10 Quick-Fixes)

Folgerelease nach v1.6.4, getrieben von einem zweiten echten Suchsprint.
Diesmal kein einziger neuer Hauptbug, dafuer ein Bouquet kleiner
Inkonsistenzen die einzeln nervten und in Summe das Kribbeln „die Tool-
Antworten passen nicht zueinander" aufrechterhielten. Zehn Issues in
einem Rutsch — Tool-Signaturen, Filter-Symmetrie, Datenhygiene und der
seit zwei Releases verschobene Score-Drift bei Bulk-Aussortierung.

### 🎯 Tool-Signaturen & API-Konsistenz

- **#544 — `suchkriterien_setzen` akzeptiert `min_gehalt`,
  `min_tagessatz`, `min_stundensatz` als Top-Level-Parameter.**
  Vorher waren sie in `custom_kriterien` versteckt, das Scoring las
  sie aber direkt aus `criteria.get("min_gehalt")` — Setzen ueber das
  Tool wirkte deshalb nicht. Jetzt direkt parametrisierbar.
- **#549 — `jobsuche_status` liefert `bereinigung` nicht mehr doppelt.**
  Vorher tauchte das Aufraeum-Statistik-Dict gleichzeitig im Top-Level
  und in `ergebnis.bereinigung` auf. Jetzt einmalig top-level.
- **#553 — `scraper_diagnose` schluesselt Trefferzaehlung sauber auf.**
  Statt einem ambigen `letzte_treffer` jetzt drei klare Felder:
  - `letzte_rohtreffer` (was der Scraper geliefert hat)
  - `letzte_gefilterte_treffer` (nach MUSS/AUSSCHLUSS/Score-Filter)
  - `letzte_neue_treffer` (wirklich neu in der DB, Duplikate raus)
  Schema v30 erweitert `scraper_health` um `last_filtered_count` und
  `last_new_count`. `letzte_treffer` bleibt als Backward-Compat-Alias.

### 🔍 Filter- & Match-Konsistenz

- **#545 — Genderform-Filter trifft alle Schreibvarianten.** Ausschluss
  „Werkstudent" filtert jetzt auch „Werkstudierende" und „Werkstudentin",
  „Praktikant" trifft „Praktikum", „Praktikantin" und „Pflichtpraktikum".
  Plus Azubi/Trainee/Junior-Stems. Realisiert ueber einen erweiterten
  `_SYNONYM_MAP`-Eintrag — keine separate Pipeline.
- **#546 — Word-Boundary fuer Kurz-Keywords (≤4 Zeichen).** „AI"
  matchte vorher in „Mainz", „ML" in „HTML", „PM" in „Compiler".
  Kurz-Keywords werden jetzt mit `\b…\b`-Regex verglichen, lange
  Keywords behalten Substring-Match (damit „Python" weiter
  „Pythonentwicklung" trifft).
- **#550 — Pandas-NaN als Firmenname „nan" gefiltert.** Der JobSpy-
  Mapper konvertierte `float('nan')` per `str(val)` zu `"nan"` und
  zeigte das als Firmenname an. Jetzt: pre-check via `math.isnan`,
  String-Filter `{"nan", "none", "null", "<na>"}` als Sicherheitsnetz,
  defensiv auch in `run_search`-Dedup.
- **#556 — `stellen_bulk_bewerten` und `stellen_anzeigen` nutzen
  identische „aktiv"-Definition.** Bulk-Pfad rief vorher
  `get_active_jobs(filters=...)` ohne `exclude_blacklisted`,
  `stellen_anzeigen` mit. Bulk-Aussortierung griff dadurch auf
  Stellen zu, die im UI gar nicht mehr sichtbar waren. Jetzt
  identisch — Counter und Liste sehen denselben Pool.
- **#557 — `quelle="linkedin"` trifft auch `jobspy_linkedin`.**
  Filter waren bisher exact-match, JobSpy-Quellen heissen aber
  `jobspy_<site>`. Jetzt: Partial-Match wenn die Quelle keinen
  Unterstrich enthaelt (kompatibel zu „bundesagentur"/„manuell"
  exact-match). Greift in `get_active_jobs` und im Restore-Pfad
  von `stellen_bulk_bewerten`.

### 🧠 Lerneffekt-Robustheit

- **#558 — Score-Drift bei Bulk-Aussortierung gestoppt.** Der
  Auto-Adjust-Hook (`_auto_adjust_scoring`) wurde pro Einzelaufruf
  getriggert — bei einer Bulk-Aussortierung von 100 Stellen kletterte
  `(count − 5) × 0.5` mit jedem Aufruf weiter und der Malus driftete
  ins Extreme. Jetzt: Bulk-Pfad nutzt `skip_auto_adjust=True` und
  triggert den Lerneffekt EINMALIG am Ende mit dem Final-Count.
  Plus klare Drift-Warnung in den `hinweise` mit Empfehlung
  `fit_analyse` neu laufen zu lassen.

### 🛠 Neues Werkzeug

- **#559 — `blacklist_anwenden`-Tool fuer retroaktive Anwendung.**
  Wenn die Blacklist NACH einer Suche erweitert wird, blieben Stellen
  der neu schwarzgelisteten Firmen weiter aktiv — der einzige
  Workaround war eine neue Suche. Neues Tool laeuft mit
  `dry_run=True`-Default-Vorschau, dann gezielt mit
  `dry_run=False` ausfuehren. Nutzt intern `db.dismiss_job` damit der
  PBP-Lifecycle (Audit-Log, Statistik) ueberspielt wird.

### Stats

- **96 MCP-Tools** (vorher 95): +`blacklist_anwenden` (#559)
- **13 neue Tests** in `tests/test_v165_quickfixes.py`, alle gruen.
- **Schema v30** (vorher v29) — ALTER-only Migration, zwei neue
  Spalten in `scraper_health`.
- 10 v1.6.4-Test-Issues geschlossen, alle in einem Release.

### Migration

- **Datenbank:** automatischer Schema-Upgrade beim ersten Start.
  Backwards-Compat: alte Diagnose-Aufrufer kriegen weiter
  `letzte_treffer`. Score-Adjustments aus v1.6.4 bleiben unveraendert.
- **MCP:** `min_gehalt`/`min_tagessatz`/`min_stundensatz` und
  `blacklist_anwenden` sind reine Erweiterungen — keine Breaking
  Changes. `quelle`-Partial-Match laesst die alte Exakt-Filter-Logik
  weiter funktionieren.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.6.5.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.6.5.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.6.4] - 2026-04-28 — Bug-Bash (8 Issues)

Hotfix-Release zwei Tage nach Foundation. User-Bug-Bash mit Beobachtungen
aus dem realen 500-Stellen-Sprint von gestern: viele kleine Inkonsistenzen,
die einzeln nicht weh tun, in Summe aber das Vertrauen in die Zahlen
unterhoehlen. Adressiert acht Issues in einem Rutsch.

### 🎯 Statistik-Korrektheit

- **#530 — Track-Record-Statistik beruecksichtigt jetzt historische
  Interviews.** Vorher zaehlte die Statistik nur den AKTUELLEN Status:
  Bewerbungen die nach dem Interview auf `abgelehnt` oder `abgelaufen`
  rutschten verschwanden aus den Zahlen — statt 7 realer Interviews
  zeigte die Statistik nur 1. Schema v29 fuegt
  `applications.has_reached_interview` als Flag hinzu (gesetzt sobald
  die Bewerbung jemals eine Interview-Stufe erreicht hat, bleibt TRUE
  auch bei spaeteren Statuswechseln). Backfill aus
  `application_events`-Timeline ueber alle bestehenden Bewerbungen.
  Neuer Statistik-Key: `interview_count_total`.
- **#535 — Score wird nach `stelle_bearbeiten` neu berechnet.** Vorher
  blieb `jobs.score` auf dem Stand der initialen Scrape-Beschreibung,
  `fit_analyse` rechnete live mit der neuen Beschreibung — drei
  verschiedene Werte fuer dieselbe Stelle waren die Folge. Jetzt
  triggert ein Recompute-Hook bei `description`- oder `title`-Updates.
- **#532 — Report-Sektion 9 „Nicht beworben trotz gutem Fit-Score"
  zeigt nur noch echte unbearbeitete Stellen.** Vorher waren auch
  aktiv aussortierte Stellen drin (z.B. mit `falsches_fachgebiet` als
  Grund) — Bewerbungen bei der gleichen Firma wurden ignoriert. Jetzt
  filtert die SQL auf `is_active=1` UND blendet Stellen aus deren
  Firma bereits eine Bewerbung hat. Plus Header-Off-by-10-Bug
  behoben (Header sagte 30, Tabelle zeigte 20).

### 🔧 Tool-Konsistenz

- **#528 — `suchkriterien_bearbeiten` akzeptiert Umlaut UND ASCII.**
  Vorher schlug `aktion="hinzufügen"` fehl mit einer Fehlermeldung
  die selbst den Umlaut nutzte. KI-Aufrufer wechseln je nach Kontext
  zwischen beiden Schreibweisen — beide sind jetzt akzeptiert.
- **#522 — Auto-Follow-up beim Statuswechsel auf `beworben` ist
  abschaltbar.** `bewerbung_status_aendern` nimmt jetzt
  `auto_follow_up: bool = True`. Sinnvoll wenn der Recruiter bereits
  zugesagt hat sich zu melden — vorher musste der automatisch
  angelegte Nachfass nachtraeglich auf `hinfaellig` gesetzt werden.
- **#529 — `bewerbung_bearbeiten` kann `applied_at` nachtraeglich
  setzen oder korrigieren.** Akzeptiert YYYY-MM-DD, DD.MM.YYYY und
  ISO-Timestamps. Bei E-Mail-Auto-Match fehlte das Datum oft, der
  einzige Workaround war Direct-DB — jetzt sauber ueber das Tool.
- **#531 — Duplikat-Erkennung in `bewerbung_erstellen` mit
  Vermittler/Endkunde-Heuristik.** Vorher war die Pruefung nur
  exakt-match auf `company.lower() == company.lower()`. Verfehlte
  daher Faelle wie „<FIRMA> <FIRMA>
  (Endkunde: <FIRMA>)" vs „<FIRMA> (via <FIRMA> ...)".
  Jetzt drei Match-Stufen:
  1. Exakt-match (alte Logik)
  2. Fuzzy-match auf normalisierte Firma + Titel (Klammer-Strip,
     Rechtsform-Suffix-Strip, Stadt-Suffix-Strip)
  3. Vermittler/Endkunde-Token-Overlap (>= 2 seltene Tokens
     gemeinsam INKL. Klammerinhalt)
  Plus: Email-/Ansprechpartner-Match liefert sehr starkes Signal.

### 🧠 Heuristik-Verbesserungen

- **#536 — Quereinsteiger-Klauseln heben Hochschulabschluss-Warnung
  auf.** `fit_analyse` triggerte „HOCHSCHULABSCHLUSS GEFORDERT — ATS-
  Aussortierung moeglich" auch wenn die Stellenbeschreibung explizit
  „Career changers welcome" oder „Quereinsteiger willkommen" enthielt.
  Jetzt: 22 Abschwaechungs-Patterns (deutsch + englisch) deaktivieren
  die Warnung. Score-Reduktion (-2) entfaellt entsprechend.

### ✅ Bereits gefixt durch v1.6.3

- **#517 — Auto-Hinfaellig bei Statuswechsel auf `abgelehnt`/
  `zurueckgezogen`/`angenommen`.** Die Lifecycle-Logik
  (`_apply_status_lifecycle` mit `TERMINAL_STATUSES`) existiert seit
  v1.5.7 (#493). Issue trat auf weil Claude vor v1.6.3 teilweise
  direkt in die DB schrieb und damit den Lifecycle umging. Mit dem
  Anti-DB-Bypass-Pattern aus v1.6.3 (Server-Instructions +
  `pbp_capabilities` + `pbp_grenze_melden`) ist das verhindert.
- **#516 — Follow-up-Zaehlung Banner vs Filter.** Folgte aus #517 —
  mit dem konsistenten Lifecycle-Pfad ist die Drift weg.

### Stats

- **96 MCP-Tools** (vorher 95): kein neues Tool ergaenzt — die Fixes
  laufen ueber bestehende Tools (`bewerbung_bearbeiten`,
  `bewerbung_status_aendern`, `bewerbung_erstellen`,
  `stelle_bearbeiten`, `suchkriterien_bearbeiten`).
- **9 neue Tests** in `test_v164_bugfixes.py`, alle gruen.
- **Schema v29** (vorher v28) — ALTER-only Migration mit Backfill.
- 8 Issues geschlossen oder als bereits gefixt markiert.

### Migration

- **Datenbank:** automatischer Schema-Upgrade beim ersten Start.
  Bestehende Bewerbungen werden aus der `application_events`-
  Timeline backfilled — jede Bewerbung die jemals einen
  Interview-Status hatte bekommt das Flag.
- **MCP:** `auto_follow_up` und `applied_at` sind optionale Parameter
  mit ruckwaerts-kompatiblen Defaults — kein Caller-Update noetig.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.6.4.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.6.4.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.6.3] - 2026-04-27 — Anti-DB-Bypass-Pattern (#514)

Hotfix-Release nach Real-Case-Beobachtung am Tag nach Foundation-Release:
**Claude greift bei groesseren Datenmengen zu Workarounds und schreibt
direkt in die SQLite-Datei** — weil PBP fuer einige reale Aufgaben
(z.B. „aussortier mir alle 200 Stellen mit falschem Fachgebiet") keine
adaequate Tool-Abdeckung hat. Direkte DB-Writes umgehen aber die
PBP-Lifecycle-Logik (Audit-Log, Status-Triggers, Lerneffekte,
Backup-Hooks, Validierungen) und korrumpieren die Datenkonsistenz.

v1.6.3 adressiert das Anti-Pattern aus drei Richtungen gleichzeitig.

### 🪖 Drei Hebel gegen den DB-Bypass

#### 1. `stellen_bulk_bewerten` — der konkrete Schmerz

Filterbasierte Bulk-Bewertung von Stellen mit `dry_run=True` als Default.
Loest den 500-Stellen-Real-Case: hunderte Treffer mit falschem
Fachgebiet aussortieren in einem einzigen Tool-Call statt 200x
`stelle_bewerten`.

Filter (kombinierbar mit AND-Logik):
- `min_score` / `max_score`
- `min_alter_tage` / `max_alter_tage`
- `quelle` (z.B. `bundesagentur`)
- `firma` (case-insensitive Substring)
- `titel_enthaelt` / `titel_enthaelt_nicht` (Listen)
- `beschreibung_enthaelt_nicht` (Listen — Hauptwerkzeug fuer Fachgebiets-
  Aussortierung)
- `max_treffer` (harter Cap)

Beispiel:

```
stellen_bulk_bewerten(
    bewertung='passt_nicht',
    gruende=['falsches_fachgebiet'],
    titel_enthaelt_nicht=['Pflege', 'Vertrieb'],
    dry_run=True   # erst pruefen!
)
→ {"dry_run": True, "anzahl_treffer": 137, "vorschau": [...10 Stellen...]}
```

Die ganze Lifecycle-Logik (`dismiss_counts`-Lerneffekt, Auto-Adjust-
Scoring, `dismiss_reasons`-Statistik) laeuft auch beim Bulk durch — die
neue Helper-Funktion `_apply_dismiss_with_lifecycle` wird sowohl von
`stelle_bewerten` als auch von `stellen_bulk_bewerten` aufgerufen.

#### 2. `pbp_capabilities` — Awareness statt Workaround

Read-only Meta-Tool das eine **kuratierte Uebersicht** aller PBP-
Faehigkeiten liefert, gegliedert nach 10 Kategorien (profil, jobsuche,
bewerbungen, dokumente, kalender, analyse, export, workflows,
einstellungen, system). Aufruf:

```
pbp_capabilities()                       # Uebersicht aller Kategorien
pbp_capabilities('jobsuche')             # Konkrete Tool-Liste der Kategorie
```

Wenn Claude unklar ist was PBP fuer eine User-Anfrage anbietet, ruft es
dieses Tool auf — **bevor** es auf andere Tools (Filesystem-MCP,
sqlite-MCP, Direct-DB-Write) ausweicht.

#### 3. `pbp_grenze_melden` — strukturierte Reibung beim Bypass-Versuch

Wenn Claude trotz `pbp_capabilities` keine passende Funktion findet,
ist das ein Signal **dass etwas im Tool-Catalog fehlt** — nicht eine
Einladung zum DB-Bypass. Das neue Tool:

1. **Loggt** die fehlende Tool-Abdeckung nach `data/limitations.log`
   (mit Zeitstempel + Versions-Info)
2. **Liefert einen vorausgefuellten GitHub-Issue-Body** den der User
   direkt bei `github.com/MadGapun/PBP/issues/new` als Issue eroeffnen
   kann (mit URL-encodeten Query-Params zum direkten Vor-Ausfuellen)
3. **Schlaegt einen sauberen Workaround vor** — meistens „im Dashboard
   manuell durchfuehren, da werden alle Hooks korrekt ausgeloest"

Damit wird jede unbedeckte Tool-Luecke ueber Zeit zu einem GitHub-Issue
und damit zu einem zukuenftigen Tool — statt still durch DB-Bypass
„geloest" zu werden.

### Zusaetzlich: PBP-MCP-Server-Instructions

FastMCP unterstuetzt einen `instructions`-String der beim
MCP-Initialize-Handshake an Claude Desktop gesendet wird und Teil des
System-Kontextes fuer den PBP-MCP wird. v1.6.3 fuegt einen knappen
Anti-Bypass-Prompt ein, der drei Punkte adressiert:

- „PBP ist die Quelle fuer ALLE bewerbungs-bezogenen Aktionen"
- „NIEMALS direkt in die SQLite-Datei oder ueber andere MCP-Tools an
  PBP-Daten gehen — Lifecycle-Logik wird umgangen"
- „Bei Unklarheit `pbp_capabilities()`, bei Grenze `pbp_grenze_melden()`"

Damit sieht Claude den Anti-Bypass-Hinweis schon **bevor** das erste
Tool aufgerufen wird, nicht erst wenn ein Workaround droht.

### Stats

- **95 MCP-Tools** in 10 Kategorien (vorher 92)
- **15 Tests fuer den neuen Code** (6 Bulk-Tool, 6 Capabilities/Grenze,
  3 Registry) — alle gruen
- **PBP-Server-Instructions: 1270 Zeichen** Anti-Bypass-Prompt

### Migration

- Keine Schema-Aenderungen
- Keine Breaking API-Changes — `stelle_bewerten` Verhalten unveraendert
- Frontend unveraendert (alle neuen Tools sind MCP-only)

### Fixes

- 2 MCP-Registry-Tests aktualisiert auf Tool-Count 95 + neue Namen
- `pbp_diagnose` Helper-Funktion `_apply_dismiss_with_lifecycle`
  extrahiert (vorher inline in `stelle_bewerten`)

---

## [1.6.2] - 2026-04-26 — Foundation-Release (Stable)

> **Hinweis zur Versionsnummer:** Der Sprint hatte 35 Beta-Iterationen
> als `v1.6.0-beta.NN`. Beim Stable-Release wurden zwei Tag-Namen
> (v1.6.0 und v1.6.1) durch GitHubs „Immutable releases"-Feature
> unbrauchbar. Daher ist die offizielle Foundation-Stable-Version
> **v1.6.2**. Inhaltlich entspricht sie beta.35 + den Polituren aus
> dem Release-Sweep + drei Hotfixes (siehe „Was in v1.6.2 dazu kam").

**v1.6.2 ist der Foundation-Release.** Zwei Tage, 35 Beta-Iterationen,
ungezaehlte „Komm, das ist noch nicht ganz richtig"-Schleifen. Hier ist
das Ergebnis.

---

### Was in v1.6.2 zusaetzlich dazu kam (Hotfixes)

Drei User-Findings nach v1.6.1, die das Bild rund machen:

- **🐛 Gehaltsbandbreite zeigte nur 2 Stellen statt 274.** Bei 2 echten
  Gehalts-Inseraten + 272 geschaetzten hat der Frontend-Filter alle
  geschaetzten verworfen, sobald auch nur ein einziges echtes vorhanden
  war. Jetzt werden beide kombiniert; das „(geschaetzt)"-Label
  erscheint nur noch wenn KEINE echten existieren.
- **🔧 „Gehaltsbandbreite" rechnete in Dashboard und Stellen-Tab
  unterschiedlich.** Dashboard nahm Mittelwert-Min/Max, Stellen-Tab
  echtes Min/Max — gleiche Karten-Bezeichnung, verschiedene Zahlen.
  Jetzt beide auf echte Min/Max-Spanne, gleicher Note-Text.
- **🔗 Update-Banner mit Click-Through.** Der „Neu in vX.Y.Z"-Banner
  hatte keinen Link auf die Release-Notes. Jetzt rendert er das
  optionale `url`-Feld als klickbaren Pfeil → ueberraschend nuetzlich,
  fuehrt direkt zum Latest-Release auf GitHub.

---

### Was du als Nutzer davon hast

#### 🔍 Endlich findet die Jobsuche wieder Stellen

Vorher: Du hast PBP installiert und drei Quellen lieferten zuverlaessig.
Heise-Jobs hat HTTP 200 zurueckgegeben aber „0 Treffer", und keiner hat
dir gesagt warum. Stepstone war ein Wuerfelspiel. LinkedIn? Vergiss es.

Jetzt: **17 von 24 Quellen liefern aktiv.** Indeed, LinkedIn, Glassdoor,
Google Jobs — alle ohne API-Key, ohne Login, ohne Kosten (ueber JobSpy).
Greenhouse-Boards von Tech-Companies (Stripe, Airbnb, GitHub) kannst du
mit deinen eigenen Slugs ergaenzen. Arbeitnow als EU-Aggregator. Plus
DACH-Klassiker: Bundesagentur, Stepstone, <FIRMA>, Stellenanzeigen.de.

Und die 7 Quellen die durch Cloudflare/Captcha tot sind? Werden im
Dashboard **sichtbar ausgegraut** mit Hinweis auf den Chrome-Extension-
Workaround. Nicht versteckt, nicht still aussortiert — klar als „kann
gerade nicht" markiert, damit du Bescheid weisst.

#### 🎨 Neue Sidebar — endlich uebersichtlich auf jedem Bildschirm

Die alte Top-Tab-Reihe war auf 1400px Breite ein Drama: Theme-Toggle
ueberlappt Profile-Switcher, auf Laptops gar nicht mehr bedienbar. Jetzt
gibt's eine **persistente linke Sidebar mit Hover-to-Expand** — zugeklappt
nimmt sie 60px, beim Druebermausen schiebt sie sich als Overlay auf 240px
raus. Pfad-Breadcrumb (`/Profil/Skills`, `/Einstellungen/Quellen`) oben
in der Topbar zeigt dir wo du gerade bist.

Status-Block in der Sidebar: PBP-Version + MCP-Heartbeat + Live-
Jobsuche-Status. Sub-Navigation pro Bereich kaskadiert eingerueckt
unter dem aktiven Eintrag. Niemand verliert mehr den Ueberblick wo
gerade was passiert.

#### 📦 Komplett-ZIP fuer jede Bewerbung

Frueher: deine Bewerbung lebt verstreut in `dokumente/`, `mails/`, der
DB, vielleicht im Anschreiben-Ordner deines Mailprogramms. Wenn ein
Coach drueberschauen soll oder du in einem halben Jahr zurueckblickst,
sammelst du muehsam zusammen.

Jetzt: **Drei Buttons in der Bewerbungsansicht.** „Protokoll drucken",
„Als ZIP", „ZIP + PDF". Du kriegst ein einziges ZIP-File mit:
`bericht.html` (Hauptprotokoll mit Timeline), `stelle.html`,
`notizen.md`, `termine.ics`, `mails.md`, dem `dokumente/`-Ordner mit
deinen verknuepften Lebenslaeufen und Anschreiben, dem `mails/`-Ordner
mit den Original-`.eml`/`.msg`-Dateien, einer `INHALT.md`-Uebersicht
und auf Wunsch einem `bericht.pdf` (per Playwright generiert).

Ideal fuer: dem Coach schicken, dem Steuerberater (Werbungskosten!),
oder dem zukuenftigen Du in zwei Jahren der nochmal schauen will wie
dieser Job damals lief.

#### 🎯 Skills mit echtem Datumsbereich

Bisher: Du hast bei einem Skill „6 Jahre Erfahrung" eingegeben und PBP
hat mit `currentYear - 6` zurueckgerechnet — am Ende stand dann „seit
2018", auch wenn du den Skill von 2010 bis 2024 hattest und seitdem
nichts mehr.

Jetzt: **`start_year`, `end_year`, `level` (best je) und `level_current`
(heute)** als getrennte Felder. Die Skill-Karte zeigt einen ehrlichen
Datumsbereich. Der Editor visualisiert beide Levels als 5-Punkt-Skala
— gefuellt = was du mal warst, halb-transparent = die Differenz zu
heute. Das gleiche fuer das Stellen-Scoring: wenn die Stelle 5/5
verlangt und dein `level_current` ist 3/5, kommt das in der Fit-
Analyse als „Auffrischung empfehlenswert" raus.

#### 🧠 Bessere Keyword-Vorschlaege

Frueher hat dir die Keyword-Vorschlags-Maschine „kunden", „sowie",
„aufgaben" als „passende Begriffe" angeboten. Total nichtssagend —
weil die Stopword-Liste zu kurz war und keine TF-IDF-Gewichtung lief.

Jetzt: erweiterte Stopwords, **TF-IDF-Specificity** (Begriffe die in
deinen erfolgreichen Bewerbungen oft vorkommen aber in den abgelehnten
selten — die sind interessant), **Quellen-Trennung applied vs dismissed**
(was hat Treffer ergeben? was wurde aussortiert?), und vor allem:
strikte Exklusion. Wenn du auf Manager-Stellen beworben hast, schlaegt
PBP nicht mehr „manager" als Aussortier-Begriff vor.

#### 📅 Statistik mit ISO-Wochen, die wirklich stimmt

Vorher: „Wir sind in KW 17, aber das Chart endet bei KW 15." User-Bug.
Grund: SQLite kennt `%V` nicht (das ist ISO-Woche), `%W` ist eine
andere Semantik, und obendrein wurde die laufende Periode nochmal
extra rausgefiltert.

Jetzt: ISO-Wochen-Aggregation in Python (`_iso_week_key`), aktuelle
Periode bleibt drin, Chart endet wirklich da wo du gerade bist.

#### 🎲 172 Tagesimpulse mit mehr Biss

143 wurden's nicht — 172 sind's. 31 neue Sprueche, 17 platte raus
(„bleib freundlich zu dir" — Wartezimmer-Niveau, weg damit), plus drei
selbstironische Meta-Sprueche (siehe „Glueckskeks-Disclaimer" weiter
unten). Neue Schwerpunkte mit klaren Beispielen:

- **Anzeigen-Bullshit-Bingo** — sezieren was Stellenanzeigen wirklich meinen:
  > *„'Familiaere Atmosphaere' ist Code fuer 'der Chef ist auch der Onkel'."*
  > *„'Hands-on Mentalitaet' heisst oft: kein Budget, kein Team, viel Hoffnung."*
- **Sende-Druck** — gegen das Tagelang-am-Anschreiben-Schleifen:
  > *„Eine perfekte Bewerbung in der Schublade ist statistisch genauso erfolgreich wie keine."*
  > *„Senden ist die einzige unverzichtbare Phase. Alles andere ist Zubehoer."*
- **Absagen mit Schulterzucken:**
  > *„Wer dir nach dem Erstgespraech absagt, hat dir gerade zwei Wochen Pendelweg geschenkt."*
- **Schalt-ab-Wochenend-Sprueche** — 12 neue, alle in Richtung „heute reicht":
  > *„Sonntagabend ist nicht der Anfang von Montag. Es ist das Ende von Sonntag."*
  > *„Niemand wird dich am Montag fragen, ob du den Sonntag optimiert hast."*

Die Auswahl bleibt deterministisch nach Datum + Kontext, also kein
Spam — pro Tag genau ein passender Spruch.

> **🥠 Glueckskeks-Disclaimer (v1.6.2):** Einige Sprueche lesen sich beim
> ersten Mal wie etwas frei uebersetzte Bambusstaebchen-Weisheiten. Das
> ist Absicht und Feature — manchmal dauert's einen Schluck Kaffee bis
> der Sinn aufpoppt, manchmal bleibt's Raetsel. *It's not a bug, it's a
> feature.* Drei selbstironische Meta-Sprueche kommentieren das
> Phaenomen direkt im Pool (impuls_187–189) — wenn du also mal mit
> Augenrollen vorm Dashboard sitzt, kann am gleichen Tag ein
> *„Falls dieser Spruch heute klingt wie aus einem Glueckskeks: ja,
> manche tun das. Lies ihn morgen nochmal."* hochkommen.

#### 🆔 Eigenes Icon, klare Identitaet

Nicht mehr das generische Windows-Batch-Icon auf dem Desktop, sondern
das **PBP-Logo** in vier Aufloesungen (16/32/48/256). Multi-Resolution
ICO. Im Browser-Tab + im Dashboard-Header siehst du den Stern mit den
Hoeren-Schwingen, der mittlerweile zur Brand gehoert.

---

### Sonstiges

- **8 Wiki-Seiten aktualisiert** — Home, Jobportale, Architektur,
  MCP-Tools, Dashboard, Tab-Bewerbungen, Tab-Profil, Installation
- **13 Screenshots regeneriert** mit Bob/Anna Mustermann als
  Demo-Personas (statt fiktiver realer Person)
- **Installer durchgesweept** — Versionen synchron, Port 8200 ueberall,
  Playwright + Chromium standardmaessig

---

---

### Sprint-Verlauf — wie aus 35 Betas die Stable-Foundation wurde

Wenn du sehen willst wie der Sprint sich aufgebaut hat, hier die Themen
in chronologischer Reihenfolge. Die einzelnen Beta-Eintraege weiter unten
in diesem Changelog haben die vollen Details.

| Phase | Betas | Thema |
|---|---|---|
| **Foundation** | beta.1–9 | Erste Layer fuer das Layout-Refactor (#508) und den Bewerbungs-Export (#474). MCP-Tools von 84 auf 92. Adapter-v2-Flip, Jobsuche ohne Claude (#461), Duplikat-Merge-Tool (#471). |
| **Scraper-Reanimation Phase 1** | beta.10–16 | Job-Suche als Kern-Mehrwert ernstgenommen (#499/#500). Diagnose: von 17 Quellen lieferten real nur 2. Adapter-v2 mit `AdapterStatus`, `scraper_health`-Tabelle, Silent-Detection. JobSpy als Core-Dependency (vorher Optional → bei den meisten Installationen nicht aktiv). geopy + Playwright + Chromium standardmaessig im Installer. |
| **Scraper-Reanimation Phase 2** | beta.17–20 | Arbeitnow + Greenhouse als neue DACH-Adapter. Glassdoor + Google ueber JobSpy. Stellenalter-Filter via `veroeffentlicht_am`. JobSpy `country_indeed=None`-Fix. Early-stop nach 3 consecutive empty pages. Selektor-Reparaturen + URL-Updates fuer „still 200"-Quellen. |
| **Identity** | beta.21 | Multi-Resolution `assets/pbp.ico` (16/32/48/256). Desktop-Shortcut zeigt PBP-Logo statt generischem Batch-Icon (#502). |
| **Stabilitaets-Welle** | beta.22 | UX-Quickfixes-Block, Mailto-Bugfix, Bewerbungsbericht aufgewertet (Zeitraum, Erstellungszeitpunkt). |
| **Layout-Refactor #508** | beta.23–25 | Variante B aus #508: linke Sidebar mit Sub-Navigation, Hover-to-Expand-Overlay, Skill-Editor mit Punkt-Visualisierung. Race-Condition-Fix in `saveItem keepOpen` (beta.25 hat den Skill-Verschwinde-Bug aus beta.22 endgueltig erledigt). |
| **Polish** | beta.26–28 | Stellen-Page (Layout, Filter, Anzeige, Gehalt, Freelance-Farbe). Min-Score-Filter mit UI-Slider. Bewerbungsprotokoll vollstaendig ausgebaut. |
| **Algorithmus** | beta.29 | Keyword-Vorschlaege grundlegend ueberarbeitet — Stopwords erweitert, TF-IDF Specificity, applied-vs-dismissed Datasource, strikte Exklusion. |
| **Variante A finalisiert** | beta.30 | UI-Konsolidierung: mittlere Sidebar entfaellt, Top-Bar uebernimmt globale Status-Indikatoren. Hover-to-Expand finalisiert. Erste Skizze v1.7.0-Roadmap (Local-LLM). |
| **ZIP-Export #474** | beta.31 | Kompletter Bewerbungs-Export als ZIP statt persistenter Ordner-Struktur. Inhalt: bericht.html, stelle.html, notizen.md, termine.ics, mails.md, dokumente/, mails/, INHALT.md, optional bericht.pdf via Playwright. |
| **Skill-Datenmodell** | beta.32 | Schema v28: `start_year`, `end_year`, `level_current`. Skill-Karte zeigt echten Datumsbereich statt zurueckgerechnetem `currentYear − years_experience`. Editor mit 5-Punkt-Visualisierung. |
| **Statistik-Korrektheit** | beta.33–34 | ISO-Wochen-Aggregation in Python (SQLite kennt `%V` nicht). beta.34 = Hotfix `_now`-Shadowing in `_group_by_iso_week` (UnboundLocalError). |
| **Synchronisation** | beta.35 | Layout-Endspiel nach User-Screenshot. **`api_keyword_suggestions`** und MCP-Tool **`keyword_vorschlaege`** synchronisiert (vorher zwei Implementierungen, eine veraltet — deshalb hat das Frontend trotz beta.29-Fix weiter „kunden, sowie, aufgaben" gezeigt). Strict exclusion: `good_words.get(term, 0) == 0`. |
| **Stable-Sweep** | v1.6.1 / v1.6.2 | Versions-Sync ueber alle 3 Komponenten, `hints.json` aktualisiert, Installer-Header gleichgezogen, `PBP_HINTS_URL` ENV-Variable, 31 neue Tagesimpulse + 17 platte raus, Bob/Anna Mustermann als Demo-Persona, Wiki + Screenshots. v1.6.2 Hotfixes: Salary-Filter, Bandbreite-Konsistenz, Banner-Klickbarkeit. |

**Insgesamt:** 36 Commits seit v1.5.8, 35 Beta-Releases zwischen
24.04. und 26.04.2026, ein Stable. Spitzentag war der 25.04. mit
~17 Betas an einem Tag.

---

### 🔧 Technischer Anhang (fuer Entwickler / Power-User)

<details>
<summary>Aufklappen: API-Aenderungen, Schema, Library-Updates</summary>

#### Datenbank

- **Schema v28** — `skills.start_year`, `skills.end_year`,
  `skills.level_current` (zusaetzlich zu bestehendem `level`)
- ALTER-only Migration; automatisches Backup vor jedem Migration-Run
- ISO-Wochen-Aggregation per `_iso_week_key()` und
  `_group_by_iso_week()` in Python (SQLite kennt `%V` nicht)

#### Backend

- **92 MCP-Tools in 8 Modulen** (Profil, Dokumente, Jobsuche,
  Bewerbungen, Analyse, Export, Suche, Workflows). Vorher 84.
- **`api_keyword_suggestions`** und MCP-Tool **`keyword_vorschlaege`**
  jetzt synchronisiert. Vorher zwei getrennte Implementierungen, eine
  davon veraltet (deshalb hat das Frontend trotz beta.29-Fix weiter
  „kunden, sowie, aufgaben" angezeigt — gefixt in beta.35)
- **`api_application_export_zip`** — neuer Endpoint mit Hilfsfunktionen
  `_render_application_print_html`, `_build_application_print_html`,
  `_render_stelle_html`, `_render_notes_md`, `_render_mails_md`,
  `_render_termine_ics`, `_render_inhalt_md`, `_render_html_to_pdf`
- **`PBP_HINTS_URL` ENV-Variable** — Hints-Quelle konfigurierbar
  (Cloud-URL, lokaler Pfad, oder `off`). Erlaubt deterministische
  Screenshots/Tests und Air-Gap-Setups
- **Fix `_now`-Shadowing in `_group_by_iso_week`** (beta.34 Hotfix):
  `_dt.now().isocalendar()` direkt nutzen, nicht ueber lokale `_now`-
  Variable die spaeter zugewiesen wird (UnboundLocalError)

#### Scraper-Architektur (`job_scraper/`)

- **Adapter v2 mit `AdapterStatus` Enum** — `OK`, `EMPTY`, `BLOCKED`,
  `TIMEOUT`, `ERROR`
- **`scraper_health`-Tabelle** — success_rate, last_run, error_message
  pro Quelle
- **Silent-Detection** — ≥10 EMPTY-Runs in Folge ohne ein OK markieren
  Quelle automatisch als `defekt="scraper"`
- **24 Quellen in `SOURCE_REGISTRY`**:
  - International ueber JobSpy: Indeed (DE/AT/CH), LinkedIn,
    Glassdoor, Google Jobs, ZipRecruiter
  - DACH-spezifisch: Bundesagentur, <FIRMA>, Stepstone, Stellenanzeigen.de,
    Jobware, Arbeitnow (NEU), Greenhouse (NEU), BA-Jobboerse, Xing
  - Freelance: freelance.de, Freelancermap, Twago
  - Sichtbar ausgegraut: ingenieur.de, Heise Jobs, GULP, SOLCOM,
    <FIRMA>, Kimeta, Monster
- **Per-Source-Timeouts** in `_SOURCE_TIMEOUT_MAP` (JobSpy 120s,
  Greenhouse 30s, Arbeitnow 45s, Default 60s)
- **`build_search_keywords`** liefert jetzt zusaetzlich
  `keywords_muss`, `greenhouse_companies` (User-Custom-Slugs)
- **JobSpy `country_indeed=None`-Fix** fuer Multi-Country-Calls
- **Early-stop nach 3 consecutive empty pages** in JobSpy-Iteration

#### Frontend

- **React 19** mit `useEffectEvent`
- **Vite 8**, Tailwind CSS, lucide-react, recharts
- **Sidebar-Component** (`frontend/src/components/Sidebar.jsx`) mit
  `isFloatingOverlay`-State fuer Hover-to-Expand
- **Top-Bar** mit `currentSubPath`-State, reset bei `navigateTo`
- **Skill-Editor** mit 5-Punkt-Visualisierung fuer `level` +
  `level_current`
- **`buildMailto`-Helper** fuer „Name &lt;addr&gt;"-Format
- **Race-Condition-Fix in `saveItem` keepOpen-Modus**:
  `nextDialogDraft` VOR `setProfile` berechnen, nicht innerhalb
  `startTransition`-Callback (laeuft sonst async)
- **`<h1 className="sr-only">`** auf allen 8 Pages — Browser-Tests
  suchen `#page-X h1`, sr-only ist der Kompromiss
- **`bandMin`/`bandMax`** auf JobsPage fuer echte Min/Max-Range statt
  zurueckgerechneter Verteilung

#### Installer-Konsistenz

- `INSTALLIEREN.bat` Header `v0.11.0` → `v1.6.2`
- `installer/install.ps1` Header `v1.0` → `v1.6.2`, Test-Dashboard
  nutzt Port `8201` (vorher: Vite-Dev-Port `5173`), User-Output zeigt
  Produktions-Port `8200`
- `installer/setup_gui.py` `APP_VERSION` `0.1.0` → `1.6.1`
- Frontend-Version (`frontend/package.json`) war `1.2.0` driftet,
  jetzt `1.6.2` synchron mit pyproject + Backend

#### Schluss-Versions-Sync

- `pyproject.toml` `[project] version = "1.6.2"`
- `src/bewerbungs_assistent/__init__.py` `__version__ = "1.6.2"`
- `frontend/package.json` `"version": "1.6.2"`

#### Bekannte Test-Failures

- **10/537 Tests scheitern** (98% Pass-Rate). Alle Failures sind
  PDF-Generation-Tests, die `fpdf2` benoetigen. In der installierten
  Distribution korrekt ueber `[docs]`-Extra abgedeckt; das Test-Venv
  installiert nur Core-Deps. **Kein Production-Bug.**

#### Library-Updates (Auswahl)

- `python-jobspy >= 1.1` — von Optional zu Core-Dep
- `playwright >= 1.40` mit Chromium-Bundle
- `geopy >= 2.4` von Optional zu Core-Dep
- React `19.x`, Vite `8.x`

</details>

## [1.6.1] - 2026-04-26 — Zwischen-Release (siehe v1.6.2)

Zwischen-Release wegen GitHub-Tag-Lock auf `v1.6.0`. Inhaltlich
identisch mit beta.35 + Versions-Sync und Polish — der eigentliche
Foundation-Release-Eintrag ist **v1.6.2** (oben). v1.6.1 wurde noch
am gleichen Tag von v1.6.2 abgeloest, weil drei User-Findings
(Salary-Filter, Bandbreite, Banner-Klickbarkeit) noch nachgezogen
werden mussten.

## [1.6.0-beta.35] - 2026-04-26

Layout-Klaerung-Endspiel (User-Wunsch nach Screenshot) + 3 weitere
User-Findings.

**Top-Bar = App-Identitaet (Logo + Brand + Pfad)**

Frueher: Top-Bar zeigte Status-Indikatoren. User: "Persoenliches
Bewerbungs-Portal sollte da rein, mit Logo, dann der aktuelle Pfad
(/Profil/Skills)."

Jetzt:
- PBP-Logo (assets/pbp.png) + "PBP" + "Persoenliches Bewerbungs-Portal"
- Aktueller Pfad als Breadcrumb: `/Dashboard`, `/Profil`, `/Profil/Skills`,
  `/Einstellungen/Quellen` etc.
- Sub-Pfad wird beim Klick auf Sidebar-Sub-Items getrackt; bei Hauptbereichswechsel reset.

**Sidebar = Status-Block + Hauptnavigation + Suchstatus**

Frueher: App-Branding oben in der Sidebar.
Jetzt:
- Status-Block oben: Version, MCP-Heartbeat (untereinander)
- 8 Hauptbereiche mit Sub-Items
- Suchstatus im Footer-Slot

**Pages: kein eigenes h1 mehr im sichtbaren Header**

Page-Titel wandern komplett in die Top-Bar als Breadcrumb. h1 bleibt
als `sr-only` fuer Screenreader und Test-Selektoren erhalten.
Aktion-Buttons (Export & Backup, Profil-Loeschen, ZIP-Export, etc.)
bleiben im Page-Header sichtbar.

**Skill-Uebersicht: Erfahrungsjahre + level_current korrekt anzeigen
(User-Befund)**

Vorher: "18 Jahre Erfahrung - seit 2008" obwohl User Von=2002 / Bis=2020
gesetzt hatte. Berechnung war `currentYear - years_experience` —
ignorierte `start_year`/`end_year` aus Schema v28.

Jetzt:
- Aktive Skills: "X Jahre Erfahrung · seit YYYY"
- Ruhende Skills: "X Jahre Erfahrung · YYYY-YYYY · ruht (Spitze N/5)"
- Punkte-Anzeige zeigt **level_current** wenn gesetzt (User-Wunsch:
  "aktuell verfuegbares Niveau ist interessanter als Spitze"), sonst
  level (peak). Hover-Tooltip zeigt beide Werte.
- Ruhende Skill-Cards visuell leicht gedimmt.

**Keyword-Vorschlaege: Dashboard-Endpoint hatte alte Logik (User-Befund
"kunden, sowie, aufgaben werden noch vorgeschlagen")**

Beta.29 hatte den Algorithmus im **MCP-Tool** (`tools/analyse.py`)
ueberarbeitet, aber das Frontend ruft den **Dashboard-Endpoint**
`/api/keyword-suggestions` auf — der noch die alte kurze Stop-Word-Liste
und 4-Zeichen-Mindestlaenge hatte. Klassischer "zwei Implementierungen,
eine vergessen"-Bug.

Jetzt synchron: Dashboard-Endpoint hat dieselbe erweiterte Stop-Word-
Liste, 5-Zeichen-Mindestlaenge, TF-IDF-Spezifitaets-Filter und
Bewerbungs-vs-Aussortierten-Datenquelle.

**Plus: Strikteres Ausschluss-Kriterium (User-Beobachtung "manager,
consultant als Ausschluss obwohl ich mich darauf beworben habe")**

Vorher: `bad_count / good_count >= 3` -> als Ausschluss empfehlen.
Problem: Wenn `manager` in 1 Bewerbung und 50 Aussortierten vorkam,
wurde es als Ausschluss empfohlen — obwohl der User aktiv eine
Manager-Stelle beworben hatte.

Jetzt: Ausschluss-Vorschlag nur wenn `good_words.get(term, 0) == 0` —
also wenn der Begriff in **keiner** User-Bewerbung vorkommt. So koennen
echte Zielbegriffe nie irrtuemlich zur Ablehnung empfohlen werden.

### Changed
- `Sidebar.jsx`: Status-Block (Version + MCP) untereinander.
- `App.jsx`: Top-Bar mit Logo + Brand + Pfad-Breadcrumb; `currentSubPath`-State.
- 7 Pages: h1 sr-only, Layout-Container ohne `flex-row-reverse`.
- `ProfilePage.jsx`: Skill-Card-Anzeige nutzt start_year/end_year/level_current.
- `dashboard.py::api_keyword_suggestions`: synchron mit MCP-Tool-Logik.
- `tools/analyse.py::keyword_vorschlaege`: strict-exclusion (good_count == 0).

### Added
- `frontend/public/pbp.png` — Logo-Asset fuer Top-Bar.

## [1.6.0-beta.34] - 2026-04-26

Hotfix Statistik (mein Fehler in beta.33).

**Bug:** `Statistiken konnten nicht geladen werden: Internal Server Error`
beim Wechsel auf "Woechentlich" oder beim Laden der Statistik-Seite mit
`interval=week`.

**Ursache:** In meinem ISO-Wochen-Refactor hatte ich `_now.isocalendar()`
**vor** der lokalen Zuweisung `_now = _dt.now()` verwendet — das Module-
Level `_now()` (Funktion, gibt String) wurde durch lokales Variable-
Shadowing zu `UnboundLocalError`. Die Statistik-Seite hat dann den
500er kassiert.

**Fix:** `_dt.now().isocalendar()` direkt nutzen statt auf eine lokale
Variable zu verlassen, die in dem Block noch nicht existiert.

Smoketest gegen alle 6 Intervals (day/week/month/quarter/year/all)
laeuft sauber durch:
```
day      OK current_period=2026-04-26
week     OK current_period=2026-W17
month    OK current_period=2026-04
quarter  OK current_period=2026-Q2
year     OK current_period=2026
all      OK current_period=2026-04
```

### Klaerungsbedarf zum Header-Layout

User-Feedback: "Persoenliches Bewerbungs-Portal immer noch links in der
Menueleiste, Version+MCP noch rechts auf der Content-Seite."

Wird in beta.35 umgesetzt sobald die genaue Zielposition geklaert ist
(siehe Issue-Antwort).

## [1.6.0-beta.33] - 2026-04-26

Header-Layout-Klarstellung + ISO-Wochen-Fix nach User-Screenshot.

**Header-Layout (User-Wunsch nach Screenshot)**
- Top-Bar: Version + MCP-Badge **untereinander gestackt links**
  (vorher nebeneinander). Kompakter und passt zum Hamburger-Block.
- Page-Header: **Titel rechts, Aktions-Buttons links** — alle 8 Pages
  (Dashboard, Profil, Stellen, Bewerbungen, Dokumente, Kalender,
  Statistiken, Einstellungen) per `flex-row-reverse` umgekehrt.

**Statistik: ISO-Wochen + laufende KW sichtbar (User: "wir haben KW 17,
Chart endet bei KW 15")**

Zwei Bugs zusammen:
1. **Filter-Logik** zog die `current_period` aus dem Chart raus
   (Annahme: "unvollstaendige Woche"). Bei einem User der heute KW 17
   sieht und die Statistik bei KW 15 endet, fehlt also nicht nur die
   laufende Woche, sondern auch noch die Vorwoche — irritierend.
2. **`%W` vs ISO-KW**: Python und SQLite verwenden `%W` (Montag-basiert,
   0-53), nicht ISO-`%V` (1-53). Beispiel 26.04.2026: `%W = 16`, ISO = 17.
   User-Kalender zeigt ISO, PBP zeigte `%W` — Differenz von 1 Woche.

**Loesung:**
- Backend: `_iso_week_key(date)`-Helper + `_group_by_iso_week*`-Funktionen.
  Wochen-Aggregation passiert jetzt in Python via `isocalendar()`, nicht
  per SQLite-`strftime`. Funktioniert fuer applications + jobs.
- `current_period` fuer Wochen-Intervall: `iso.year-Wiso.week`.
- Gap-Fill verwendet `%G-W%V-%u` (ISO) statt `%Y-W%W-%w`.
- Frontend filtert die laufende Woche **nicht mehr** weg —
  `timelinePeriods = allPeriods` direkt.

### Changed
- `App.jsx`: Top-Bar Version+MCP vertikal gestackt.
- 8 Page-Header-Container: `flex-row-reverse` ergaenzt.
- `database.py::get_timeline_stats`: ISO-Wochen-Logik + Gap-Fill.
- `StatsPage.jsx`: kein currentPeriod-Filter mehr.

### Added
- `_iso_week_key()`, `_group_by_iso_week()`, `_group_by_iso_week_count()`
  als Module-Level-Helper in `database.py`.

## [1.6.0-beta.32] - 2026-04-26

User-Feedback-Beta nach beta.31. Drei klare Fixes; zwei Punkte
brauchen User-Klaerung (siehe README/Issue).

**Skill-Editor: Punkte statt Zahl (User: "1=hoch oder 1=niedrig?")**
- Spitzen-Niveau und "Aktuell verfuegbares Niveau" jetzt als 5
  klickbare Punkte (analog zur Listen-Ansicht). Klar erkennbar:
  voller Punkt = aktiv, je mehr Punkte gefuellt, desto hoeher das
  Niveau.
- Beschreibungs-Texte daneben: "Grundkenntnisse / Erweiterte
  Grundkenntnisse / Solide Praxiserfahrung / Fortgeschritten / Experte"
- Bei "Aktuell" statt Punkt-Niveau eine "(= Spitzen-Niveau X)"-
  Anzeige, wenn der User den Wert nicht explizit gesetzt hat.
  Zuruecksetzen-Button daneben.

**Einstellungen Sub-Navigation in Sidebar (Konsequenz mit beta.30)**
- Settings-Tabs (Quellen, System, Erscheinungsbild, Datenschutz, Logs,
  Gefahrenzone) wandern in die linke Sidebar als kaskadierende Sub-
  Items unter "Einstellungen", analog zu Profil/Kalender.
- Dispatch via CustomEvent `settings-nav` an die SettingsPage —
  bestehende horizontale Tab-Reihe in der Page bleibt vorerst als
  Backup, koennte spaeter komplett entfernt werden.

**Gehaltsbandbreite zeigt echte Min/Max (User: "94.500 EUR Stelle, aber
Bandbreite endet bei 74.750")**
- Vorher: Durchschnitt der Min- und Max-Werte (74.750 = avg(maxs) bei
  2 Stellen mit unterschiedlichen Spannen).
- Jetzt: `bandMin = Min(alle Min)`, `bandMax = Max(alle Max)` — die
  echte Spanne ueber alle Stellen. User-intuitive Interpretation.
- Note-Text: "Niedrigster bis hoechster Wert ueber X Stellen".
- Durchschnitt bleibt als separate Karte, mathematisch unveraendert.

### Klaerung benoetigt (kommt ggf. in beta.33)

- **Header-Layout-Reihenfolge**: User: "Titel rechts, anderes
  untereinander links". Aktueller Stand: Top-Bar hat Hamburger |
  Version | MCP | JobsucheStatus | Spacer | Theme | Hilfe | Profil.
  Brauchen Screenshot.
- **Statistik-Bug**: "wir sind bereits einige Kalenderwochen weiter
  als angezeigt, diese Woche ueber 400 Stellen gefunden". Vermutung:
  `found_at`-Feld nicht konsistent gesetzt, oder die `currentPeriod`-
  Filter-Logik filtert die laufende Woche raus. Brauchen Screenshot.

## [1.6.0-beta.31] - 2026-04-26

Bewerbungs-ZIP-Export (#474, neu geloest).

**Statt** "Ordner pro Bewerbung" mit Datei-System-Reorganisation
(urspruenglicher Plan in #474, geschaetzt 10-13h, viele Risiken):
**On-demand-ZIP-Export** auf Knopfdruck — kein Schema-Bump, keine
Pfad-Migration, gleicher User-Mehrwert.

**Neuer Endpoint:** `GET /api/application/{id}/export.zip`

**Phase 1 (immer dabei):**
- `00_INHALT.md` — Uebersicht
- `01_Bewerbungsprotokoll.html` — vollstaendiges Bewerbungs-Dossier
  (das beta.28-Protokoll mit Statistik, Status-Historie, etc.)
- `02_Stellenanzeige.html` — Original-Stellenbeschreibung mit Link
- `03_Notizen.md` — alle Notizen
- `04_Termine.ics` — RFC-5545-konform, importierbar in Outlook,
  Thunderbird, Apple Calendar
- `05_Mail-Verlauf.md` — strukturierte Zusammenfassung mit Body

**Phase 2 (optional via Query-Params):**
- `?dokumente=1` (default) — Original-Files unter `dokumente/`
- `?mails=1` (default) — Original `.eml`/`.msg`-Files unter `mails/`
- `?pdf=1` (default off) — zusaetzliches PDF des Berichts via
  Playwright (haben wir seit beta.16 als Core-Dep installiert)

**Frontend** im Bewerbungs-Detail-Modal:
- Button "Protokoll drucken" bleibt
- Neu: "Als ZIP exportieren" (Komplett-Dossier, schnell)
- Neu: "ZIP + PDF" (mit Playwright-PDF, etwas langsamer)

**Phase 3** (visueller Timeline-Kalender im Bericht, 1-6 Monate
Span mit Stationen) wandert nach **v1.7.0** zu den UI-Visualisierungs-
Themen.

**Issue #474 geschlossen** mit Verweis auf den ZIP-Export — die
Bewerbungs-Ordner-Idee aus #474 ist damit funktional umgesetzt,
ohne dass PBP die User-Festplatte umorganisieren muss.

### Added
- `dashboard.py::api_application_export_zip` (~140 Zeilen) plus
  fuenf Render-Helfer (`_render_stelle_html`, `_render_notes_md`,
  `_render_mails_md`, `_render_termine_ics`, `_render_inhalt_md`,
  `_render_html_to_pdf`).
- 3 neue Buttons im Bewerbungs-Detail-Modal Footer.

### Changed
- `api_application_timeline_print` refaktoriert — HTML-Render-Logik
  als wiederverwendbare Funktion `_build_application_print_html`,
  damit der ZIP-Endpoint sie nutzt.

## [1.6.0-beta.30] - 2026-04-25

UI-Konsolidierung: Variante A aus #508 vollstaendig umgesetzt (mittlere
Sidebar entfaellt, Top-Bar uebernimmt globale Status-Indikatoren), plus
Hover-to-Expand fuer collapsed Sidebar und v1.7.0-Roadmap-Dokument.

**Sidebar-Konsolidierung (User-Wunsch "zwei Menueleisten zusammenfassen")**

- Mittlere Sidebar (Version + MCP-Badge + JobsucheStatus + Profil-/
  Kalender-Sub-Navigation) entfaellt komplett.
- Page-spezifische Sub-Navigation (8 Profil-Sektionen, Kalender-Filter)
  wandert in die linke Sidebar als **eingerueckte Sub-Items unter dem
  aktiven Hauptbereich** (kaskadierend wie VS Code/Linear).
- Sidebar-Brand reduziert auf reinen App-Namen — keine Doppelung mit
  den globalen Status-Indikatoren.

**Top-Bar als globale Status-Zeile (User-Feedback "Titel gequetscht,
besser auf der Page")**

- Page-Breadcrumb in der Top-Bar entfaellt (jede Page hat ihr eigenes
  prominentes h1).
- Stattdessen: Hamburger | Version (v1.6.0-beta.30) | MCP-Badge
  (3-stufig, klickbar) | JobsucheStatus | Spacer | Theme | Hilfe |
  Profil.

**Hover-to-Expand fuer collapsed Sidebar (User-Wunsch)**

- Wenn Sidebar collapsed (60px Layout-Breite), klappt sie bei Hover
  automatisch als Overlay aus (240px) — Layout springt nicht.
- Beim Verlassen klappt sie wieder ein.
- Manueller Toggle bleibt erhalten zum Pinnen/Loesen.
- Visuell sauber: Schatten unter der ausgeklappten Overlay-Sidebar.

**v1.7.0-Roadmap-Dokumentation**

- `docs/ROADMAP_v1.7.0.md` angelegt — strategische Uebersicht der
  Local-LLM-Foundation (Ollama-Sidecar), Phasen A/B/C+D, Begleitende
  Issues, Risiken, Nicht-Ziele.
- `README.md` mit neuem Roadmap-Abschnitt verlinkt darauf.
- Detail-Issue [#512](https://github.com/MadGapun/PBP/issues/512)
  bleibt das lebende Sammel-Dokument fuer Anwendungsfaelle.

### Changed
- `Sidebar.jsx`: hover-to-expand mit Overlay-Mechanik (Layout-Breite
  bleibt 60px, inneres Panel wird position:absolute mit Schatten);
  Brand-Block reduziert; `footerSlot`-Prop fuer Slot-Inhalte.
- `App.jsx`: alte mittlere Sidebar entfernt (~135 Zeilen weg),
  `sidebarSubNavigation` berechnet pro Page, Top-Bar-Layout neu.
- `README.md`: neuer Roadmap-Abschnitt vor dem Changelog.

### Added
- `docs/ROADMAP_v1.7.0.md` (~150 Zeilen).

## [1.6.0-beta.29] - 2026-04-25

Keyword-Vorschlaege grundlegend ueberarbeitet (#User-Feedback nach beta.28).

**User-Befund:** "Plus-Vorschlaege sind nichtssagend (kunden, sowie,
aufgaben, ueber, ...), Minus-Vorschlaege sind genau die Begriffe, die
ich im Plus haben will (manager, consultant)."

**Drei Probleme im alten Algorithmus:**

1. **Tautologische Datenquelle:** Klassifiziert wurde nach `score >= 3`
   (gut) vs `score <= 1` (schlecht). Der Score wird aber AUS den
   Keywords berechnet — die Vorschlaege waren also ein Echo der
   bestehenden Keywords statt ein Lernsignal.

2. **Stop-Words zu eng:** "kunden", "sowie", "aufgaben", "ueber",
   "bereich", "erstellung" sind in 70%+ aller Stellen drin — keine
   Aussagekraft, aber nicht in der alten Stop-Word-Liste.

3. **Min-Wortlaenge zu niedrig:** 4 Zeichen erlaubt "ihre", "team",
   "ueber" als Kandidaten.

**Loesung (ohne LLM, datengetrieben):**

1. **Datenquelle umgestellt:** Stellen mit Bewerbung vs. von dir
   aussortierte Stellen. Beantwortet die User-Frage: "Was unterscheidet
   die Stellen, fuer die ich mich beworben habe, von denen die ich
   abgelehnt habe?"
   - Wenn keine ausreichenden Daten (>=3 Bewerbungen + >=3 Aussortierte)
     vorhanden: Fallback auf alten Score-Vergleich, klar als
     `Score-Vergleich (kein Bewerbungs-Vergleich moeglich)` markiert.

2. **Stop-Word-Liste massiv erweitert** auf 100+ DACH-typische
   Stellenanzeigen-Floskeln (kunden, mitarbeiter, anforderungen,
   verantwortung, montag-freitag, m/w/d, ...).

3. **TF-IDF-Spezifitaets-Filter:** Begriffe die in mehr als 70% aller
   aktiven Stellen vorkommen werden ausgeschlossen — auch wenn sie
   nicht in der Stop-Word-Liste sind. Eliminiert generische Begriffe
   automatisch.

4. **Min-Wortlaenge auf 5 Zeichen** erhoeht.

5. **Frontend zeigt Datenquelle** transparent: "Basis: Vergleich:
   X Stellen mit Bewerbung vs. Y aussortierte Stellen" oder
   "Basis: Score-Vergleich (kein Bewerbungs-Vergleich moeglich)".

**Ollama-Sammel-Issue (#512) angelegt** fuer v1.7.0 — sammelt die
Anwendungsfaelle, fuer die eine lokale LLM den naechsten Sprung in
Qualitaet bringt (z.B. echte semantische Differenzierung "Windchill
vs Teamcenter") ohne das Claude-Konto des Users zu belasten.

### Changed
- `tools/analyse.py::keyword_vorschlaege`: komplett neu — Datenquelle,
  Stop-Words, TF-IDF-Filter.
- `pages/ProfilePage.jsx`: Frontend zeigt Datenquelle transparent;
  Labels umformuliert auf "haeufig in deinen Bewerbungen" /
  "haeufig in von dir aussortierten Stellen".

## [1.6.0-beta.28] - 2026-04-25

Bewerbungsprotokoll vollstaendig ausgebaut (#User-Feedback "darf gerne
ausfuehrlicher sein").

**Vorher:** schmaler Header + flache Chronologie-Tabelle + Doku-Liste.

**Jetzt:** vollstaendiges Bewerbungs-Dossier mit:

1. **Kennzahlen-Block** mit 10 Kacheln:
   - Bewerbung gesendet (Datum + "vor X Tagen")
   - Letzte Aktivitaet (Datum + "vor X Tagen")
   - **Reaktionszeit** (Tage zwischen Bewerbung und erster
     eingehender E-Mail / Status-Wechsel-Event)
   - Aktueller Status
   - Anzahl Status-Wechsel
   - E-Mails (mit Aufschluesselung ein/aus)
   - Termine
   - Dokumente
   - Notizen
   - Timeline-Eintraege gesamt

2. **Stelle-Block** (Standort, Quelle, Gehalt, Link, Ansprechpartner,
   Bewerbungsart, Lebenslauf-Variante).

3. **Status-Historie** als nummerierte Liste mit Status-Badges +
   passender Notiz pro Schritt — zeigt klar den Verlauf:
   beworben -> eingangsbestaetigung -> interview -> ...

4. **E-Mail-Korrespondenz** als Tabelle mit Datum, Richtung
   (Eingehend/Ausgehend), Partner, Betreff.

5. **Termine** mit Datum + Plattform.

6. **Notizen-Block** als hervorgehobene "Sticky-Notes" mit Datum und
   Inhalt — visuell abgesetzt mit oranger Linie.

7. **Verknuepfte Dokumente** mit Typ und Hinzufuegungsdatum.

8. **Vollstaendige Chronologie** als Tabelle (alle Eintraege chrono
   sortiert).

**Layout:**
- Professioneller Header mit blauer Akzentlinie
- Section-Titel mit Unterstrich
- Print-Styles: 5-spaltige Stat-Grid, page-break-Hinweise
- Saubere Typografie, tabular-nums fuer Datumsspalten
- Status-Wechsel-Liste mit Counter-Badges
- HTML-Escaping konsistent (Sicherheit)

### Changed
- `dashboard.py::api_application_timeline_print`: komplett neu
  geschrieben (~200 -> ~280 Zeilen).

## [1.6.0-beta.27] - 2026-04-25

Mindest-Score-Filter mit UI (#User-Feedback).

**Problem:** Stellen mit Score 1 fluteten die Liste — viele davon waren
geographisch weit weg oder hatten nur einen marginalen Keyword-Treffer.
Backend hatte schon einen `min_score_schwelle`-Filter (Default 1), aber
keine UI-Steuerung.

**Loesung:**
- Neuer Slider in der Profil-Seite (im Suchkriterien-Block, direkt unter
  den Gewichtungen): "Mindest-Score 0-20".
- Mit Hinweisen: 0-1 = sehr offen, 3-5 = mittel/empfohlen, 10+ = nur
  klar passende Stellen.
- Greift beim **naechsten Such-Lauf** (Backend-Filter) UND als
  Default-UI-Filter in der Stellen-Liste — bestehende DB-Eintraege mit
  Score < Schwelle werden ausgeblendet, ohne sie zu loeschen.

### Added
- `min_score_schwelle` in `criteriaToDraft` / `criteriaDraftToPayload`
  (ProfilePage).
- Slider-UI mit Erklaerungs-Hinweis.
- JobsPage initialisiert `filters.minScore` aus
  `chrome.search_criteria.min_score_schwelle`.

## [1.6.0-beta.26] - 2026-04-25

Stellen-Page-Polish: 5 User-Findings nach beta.25.

**Layout: rechte Sidebar bleibt sichtbar** statt bei <1024px zu
verschwinden. Stattdessen scrollt der Inhalt horizontal. User-Wunsch:
"besser scrollen als irgendwas verlieren".

**Stellenalter-Filter repariert (#251 / Bug seit beta.25)**
- Filter pruefte das Feld `published_at`, das DB-Feld heisst aber
  `veroeffentlicht_am` (seit Schema v24). Filter griff bei den meisten
  Stellen nicht.
- Default fuer frische Installationen oder neue Quellen: 21 Tage. Vorher
  griff der Filter ueberhaupt nicht, wenn `last_search_at` fehlte —
  User wurde mit jahrealten Stellen erschlagen.
- Mit last_search_at: max(7, intervall*2). Beispiel: Vor 3 Tagen
  gesucht -> jetzt nur Stellen <= 7 Tage alt.

**Anzeige-Bug "X mit Bewerbung" repariert**
- Die Karte "Aktive Stellen" zeigte vorher pauschal `gesamt - aktiv`
  als "mit Bewerbung". Falsch — die Differenz enthaelt aussortierte
  ("passt nicht"), durch UI-Filter ausgeblendete und anders unsichtbare
  Stellen.
- Jetzt 3 separate Zaehler: `mit Bewerbung` (echte applications),
  `aussortiert` (dismissed_jobs), `ausgefiltert` (Rest). Beispiel:
  "459 gesamt (1 mit Bewerbung, 1 aussortiert, 0 ausgefiltert)".

**Gehaltsdurchschnitt-Plausibilitaet**
- Manche Scraper schreiben Tagessaetze (z.B. 850 EUR/Tag) faelschlich
  mit `salary_type=jaehrlich`. Bei nur 2 Stellen mit Jahresgehalt
  ergab das absurde Durchschnitte (User-Beobachtung: "die naechste
  Stelle hat min/max ueber dem Durchschnitt").
- Neuer Plausibilitaets-Filter: Werte unter 20.000 EUR/Jahr werden aus
  dem Durchschnitt ausgeschlossen. In DACH ist das praktisch nie ein
  echtes Vollzeit-Jahresgehalt.

**Freelance-/Selbstaendigen-Projekte sichtbar abgegrenzt**
- Job-Karten mit `employment_type=freelance` haben jetzt einen lila
  Hauch (border-violet/25, bg-violet/[0.02]).
- Pinned (amber) hat weiterhin Vorrang vor Freelance-Faerbung.
- User-Wunsch von frueher, jetzt umgesetzt.

### Changed
- `App.jsx`: Layout-Wrapper ohne `mx-auto max-w` + `overflow-x-auto`,
  rechte Sidebar ohne `hidden lg:block`.
- `JobsPage.jsx`: 3-Wege-Aufteilung "Aktive Stellen"-Note;
  Plausibilitaets-Filter in `buildAnnualSalaryMetrics`; Freelance-
  Card-Faerbung.
- `job_scraper/__init__.py`: Stellenalter-Filter pruef jetzt korrektes
  Feld + Default 21 Tage.

## [1.6.0-beta.25] - 2026-04-25

#510 endgueltig gefixt — beta.22-Fix war fehlerhaft (Race Condition).

**Problem:** Beim Bearbeiten eines bestehenden Skills (Pagination 79/99
o.ae.) springt "Speichern & weiter" weiterhin auf "neuer Skill anlegen"
statt zum naechsten existierenden Skill — obwohl beta.22 das angeblich
gefixt hatte.

**Ursache:** Mein beta.22-Fix berechnete `nextDialogDraft` im
`setProfile`-Updater-Callback. Das war innerhalb von `startTransition`
und lief asynchron. `setSkillDialog` lief direkt danach synchron,
bevor der Updater-Callback ausgefuehrt wurde — die Variable war zum
Zeitpunkt des Reads immer noch `null`. Race Condition.

**Fix:** Den naechsten Skill **vor** dem `setProfile`-Update aus dem
aktuellen `profile`-State ablesen. So ist der Wert deterministisch
verfuegbar fuer `setSkillDialog`. Da Skill-Update die Reihenfolge nicht
aendert, ist `profile.skills[currentIdx + 1]` korrekt.

User-Workflow funktioniert jetzt: 100 extrahierte Skills aus Lebenslauf-
Upload mit "Speichern & weiter" durchklicken springt deterministisch
durch 1/100 → 2/100 → ... → 100/100 → leerer Anlegemodus.

### Fixed
- #510 v2: Race Condition zwischen `startTransition` und
  `setSkillDialog` aufgeloest, indem `nextSkillItem` vor dem Update
  berechnet wird.

## [1.6.0-beta.24] - 2026-04-25

Sidebar-Polish nach erstem User-Feedback zu beta.23.

**Linke Sidebar: echte Version + 3-stufige MCP-Status-Logik**
- Vorher zeigte die linke Sidebar hardcoded "v1.6.0" und ein 2-stufiges
  Verbunden/Offline-Badge (basierend auf `chrome.profile`).
- Jetzt: `chrome.status.version` (zeigt z.B. "v1.6.0-beta.24") +
  3-stufiges Badge (Verbunden/Pruefe…/Nicht verbunden) mit derselben
  Klick-Logik wie das Badge in der alten rechten Sidebar — bei
  "Verbunden" oeffnet es Claude Desktop, sonst die MCP-Hilfe.

**Header: Page-Titel prominenter (User-Feedback "wirkt gequetscht")**
- Schriftgroesse 14px → 18px, vollwertig `font-semibold text-ink`.
- Hamburger-Icon von 18px → 20px, mehr Padding um den Titel.

**Alte rechte Sidebar bleibt vorerst stehen**
- User-Entscheidung: linke Sidebar bekommt erst die richtige Logik,
  dann entscheidet der User selber ob die rechte als redundant entfernt
  werden soll. Diese Beta haelt sich strikt an "linke Sidebar
  korrigieren, alte Sidebar nicht anfassen".

### Changed
- `Sidebar.jsx`: Brand-Block bekommt 3-stufiges MCP-Badge (Click-Handler
  per Prop) statt 2-stufiges Boolean.
- `App.jsx`: `chrome.status.version` und `chrome.status.mcp_connection`
  fliessen jetzt in die Sidebar; Header-Layout: groessere Schrift +
  Padding.

## [1.6.0-beta.23] - 2026-04-25

Sidebar-Navigation (#508) — komplettes UI-Refactor.

**Architektur-Wechsel: Hauptnavigation links statt oben (Variante B)**

Die horizontale Top-Tab-Reihe skalierte nicht. Auf 14"-15"-Laptops und
Bildschirmen unter 1400px ueberlappten Reiter-Texte mit Theme-Toggle und
Profile-Switcher (#507). Hinzu kam, dass kommende Features (Plugin-API
#504, KI-Toggles #425, API-Tokens #478) zusaetzliche Sub-Tabs
einbringen wuerden — die horizontale Sub-Tab-Reihe in Einstellungen mit
heute schon 6 Tabs war nicht mehr haltbar.

**Loesung: Komplette Navigation in eine persistente, kaskadierende
linke Sidebar verlegt** (Modell wie VS Code, Notion, Linear, Slack).

### Top-Bar (entschlackt)

Enthaelt nur noch globale Schalter:
- Hamburger / Sidebar-Toggle
- Seitentitel (kontextueller Bereich-Name als Breadcrumb)
- Hilfe (?), Theme-Toggle, Profile-Switcher

Kein Branding mehr in der Top-Bar (das wandert in die Sidebar), keine
Hauptbereiche, keine Sub-Tabs.

### Sidebar (neu)

- App-Branding "Persönliches Bewerbungs-Portal" oben
- Versions-Badge + Connection-Status (gruen/amber)
- 8 Hauptbereiche vertikal mit Icons + Badges
- Aktiver Bereich farblich hervorgehoben
- Persistente Collapse-Funktion (LocalStorage), 240px breit / 60px collapsed
- Vertikales Scrollen falls Inhalte ueberlaufen
- Sub-Navigation-API vorbereitet (eingerueckt unter aktivem Bereich)

### Behoben

- **#507** ist durch das Refactor automatisch obsolet — Theme-Toggle
  hat jetzt eigenen Platz in der entschlackten Top-Bar.

### Test-Kompatibilitaet

- `.brand-title`, `.tab[data-page=...]`, `tab-meta-*`, `tab-badge-*`-IDs
  bleiben aus der alten Top-Bar erhalten — Browser-Tests laufen
  unveraendert weiter.
- Seitentitel als `<div>` (nicht `<h1>`), weil jede Page ihren eigenen
  `<h1>` hat — vermeidet Strict-Mode-Konflikte in Tests.

### Added
- `frontend/src/components/Sidebar.jsx` — neue Komponente.

### Changed
- `App.jsx` Layout: `flex` row, Sidebar + Hauptbereich.
- Top-Bar entschlackt (Branding + Tabs entfernt, Hamburger + Breadcrumb dazu).

## [1.6.0-beta.22] - 2026-04-25

Skill-Editor + Quellen-Hilfetext: drei User-Issues nach erstem Test-Lauf
des stabilen Beta-Stands.

**#511 Skill-Datenmodell-Erweiterung (Schema v28)**
- Neue Felder: `start_year`, `end_year` (NULL = laeuft noch),
  `level_current` (NULL = identisch mit peak)
- "Seit (Jahr)" -> "Von (Jahr)" + neues Feld "Bis (Jahr) — leer = laufend"
- Neues Feld "Aktuell verfuegbares Niveau (1-5)" — erscheint nur wenn
  bis_jahr gesetzt (Skill ruht). Erlaubt Skills wie "PLM 2005 durchgehend
  (Niveau 5)" sauber von "Skill X 2<telefon>, Prinzip-Verstaendnis bleibt
  (peak 4, current 2)" zu unterscheiden.
- Status-Pille im Editor: gruenes "Aktiv seit YYYY" oder gelbes
  "Skill ruht seit YYYY (aktiv VVVV-YYYY)"
- Migration v27->v28: ALTER TABLE skills ADD COLUMN x3, plus automatische
  Befuellung von `start_year` aus bestehenden `last_used_year - years_experience`.

**#510 Bug: "Speichern & weiter" legt neuen Skill an statt zu navigieren**
- Aus #42 (Pagination zum naechsten existierenden Skill) und #379
  (serielle Anlage neuer Skills) war die Buchhaltung verloren gegangen —
  beide Use-Cases hatten denselben Button mit der falschen Logik.
- Jetzt kontextabhaengig (Variante 1 aus dem Issue):
  - Bearbeiten-Modus + naechster Skill existiert -> springt zu Skill N+1
  - Bearbeiten-Modus am Listen-Ende -> Felder leeren fuer neuen Anlege
  - Anlege-Modus initial -> Felder leeren wie bisher

**#509 Quellen-Hilfetext erweitert um 4 Wege**
- Bisher: nur eine Alternative ("Claude bitten, manuell zu uebernehmen")
  bei Quell-Problemen genannt — drei weitere lagen brach.
- Jetzt: aufklappbares Detail-Element mit allen vier Wegen klar
  beschrieben:
  1. Eingebauter Scraper (Default)
  2. Claude in Chrome (Browser-Extension)
  3. URL kopieren und in den Claude-Chat einfuegen
  4. Manuell ueber `stelle_manuell_anlegen`

### Added
- 3 neue Skill-Felder (Schema v28).
- "Bis (Jahr)" + "Aktuell verfuegbares Niveau" + Status-Pille im Skill-Editor.
- Aufklappbarer Vier-Wege-Hilfetext in der Quellen-Liste.

### Changed
- "Speichern & weiter" navigiert beim Bearbeiten zum naechsten existierenden
  Skill statt Felder zu leeren.
- "Seit (Jahr)" Feld umbenannt zu "Von (Jahr)".

### Fixed
- #510: Skill-Editor-Pagination + Anlege-Logik kollidieren nicht mehr.

## [1.6.0-beta.21] - 2026-04-25

Update-Pfad-Stabilisierung fuer v1.5.x -> v1.6.0 + UX-Polish.

**#503 Dokument-Pfad-Auto-Reparatur**
- Beim DB-Init validiert PBP jetzt alle `documents.filepath`-Eintraege.
  Wenn die Datei nicht mehr am gespeicherten Pfad liegt, sucht es im
  aktuellen `data_dir` an bekannten Fallback-Stellen (data/dokumente/,
  dokumente/, data/dokumente/<profile_id>/) sowie das spezifische
  Pattern aus dem User-Bug (`BewerbungsAssistent\dokumente\` ->
  `BewerbungsAssistent\data\dokumente\`).
- Bei Treffer wird der Pfad still in der DB aktualisiert; bei nicht-
  auffindbarer Datei bleibt der Eintrag unveraendert (kein Datenverlust).
- 4 neue Tests in `TestDocumentPathRepair`. Konkreter User-Workaround
  aus dem Issue ist jetzt automatisiert.

**#502 PBP-Icon fuer Desktop-Verknuepfung**
- `assets/pbp.ico` mit Multi-Resolution (256/128/64/48/32/16) aus
  `docs/pbp.png` generiert.
- `INSTALLIEREN.bat` kopiert das Icon nach `%APP_DIR%\pbp.ico` und
  setzt es als `IconLocation` der Desktop-Verknuepfung. Statt dem
  generischen Batch-Symbol erscheint jetzt das PBP-Logo.

**Update-Pfad 1.5.x -> 1.6.0 verifiziert**
- Schema-Migration 23 -> 27 laeuft sauber durch (alle Zwischenschritte
  v23->v24->v25->v26->v27 vorhanden, jeder Schritt ALTER TABLE-only).
- Backup-Erstellung vor Migration funktioniert (`backups/pbp-backup-
  YYYY-MM-DD_HH-MM-SS.db`).
- Profil-Daten und bestehende Bewerbungen bleiben erhalten.
- Neue Core-Deps (`python-jobspy`, `geopy`, `beautifulsoup4`, `lxml`)
  werden ueber alle vier Installer-Wege (BAT/PS1/SH/GUI) installiert
  (siehe beta.19).

### Issues geschlossen / verschoben
- **CLOSED** #497 Epic Bewerbung-Kalender (Sub-Issues alle erledigt)
- **CLOSED** #498 Meta Regression Protection (Massnahmen umgesetzt)
- **CLOSED** #499 Epic Scraper-v2 (Adapter + Health + Defekt + Timeouts)
- **-> v1.6.1** #474 Bewerbungs-Ordner (eigenes Folge-Release, ~10-13h Arbeit)
- **-> v1.7.0** #429 PyPI-Paket, #472 n:m Bewerbung-Stelle, #505 ID-Praefixe,
  #504 Plugin-Plattform, #481 Termine an Thunderbird/Outlook

**v1.6.0-Milestone: 0 offene Issues.**

### Added
- `_repair_document_paths()` in `Database.initialize()`.
- 4 neue Tests fuer die Pfad-Reparatur.
- `assets/pbp.ico` (Multi-Resolution PBP-Logo).

### Changed
- `INSTALLIEREN.bat` kopiert `assets/pbp.ico` ins App-Verzeichnis und
  setzt `IconLocation` der Desktop-Verknuepfung.

## [1.6.0-beta.20] - 2026-04-25

Per-Source-Timeouts + Glassdoor-Spam-Fix nach Real-Run-Bilanz (#500).
Echter Such-Lauf mit den Live-Suchkriterien zeigte: 5 Quellen lieferten
zu langsam und wurden in den 90s-Default-Timeout gekillt — obwohl sie
echte Daten haben.

**Per-Source-Timeout-Map** ersetzt die pauschale 90s/180s-Logik:
- `bundesagentur`: 180s (war 90s) — bei 1981 Treffern braucht der
  Detail-API-Loop Zeit, selbst mit dem Performance-Limit aus beta.19
- `freelance_de`: 180s (war 90s) — bei vielen User-Keywords (~40)
  und Detail-Pages pro Treffer
- `jobspy_indeed`: 150s (war 90s) — Real-Run lief 114s, knapp am Limit
- `jobspy_linkedin`: 120s (war 90s) — LinkedIn-Rate-Limits pro Page
- `freelancermap`, `indeed`, `monster`: 120s (war 90s) — Anti-Bot bzw.
  Slug-URL-Multi-Keyword
- Alle uebrigen API-Quellen behalten 90s (default).

**JobSpy Glassdoor: Early-Stop bei aufeinanderfolgenden leeren Antworten**
(beta.19 hotfix, 08ef144): Real-Run zeigte 30 sequentielle "Error
encountered in API response"-Logs fuer Glassdoor — die Quelle ist
geblockt, sinnlos weiterzuversuchen. Nach 3 leeren Antworten und 0
bisherigen Treffern wird die Site abgebrochen. Reset bei jedem
Treffer, damit kurze Aussetzer nicht falsch terminieren. Wirkt fuer
alle JobSpy-Sites.

### Real-Run-Bilanz mit aktuellen Live-Suchkriterien (10 Muss-Keywords + 31 Plus, Region Hamburg)

Aktiv liefernd:
- bundesagentur: **1981 Treffer** (41.8s, danach Timeout bei 90s — jetzt 180s)
- jobspy_indeed: **702** (114s — jetzt 150s Limit)
- freelancermap: **488** (Slug-URL pro Keyword, Timeout reduziert)
- <FIRMA>: **50** (42.7s, ok)
- arbeitnow: **49** (sub-second)
- stellenanzeigen_de: **25** (81.2s, ok)
- greenhouse: **16** (DACH-Filter aktiv)

Vorher Timeout, jetzt mehr Spielraum:
- stepstone, freelance_de, jobspy_linkedin, indeed, monster

### Changed
- `__init__.py`: `_SOURCE_TIMEOUT_MAP` + Helper `_timeout_for(quelle)`,
  zwei Aufrufer entsprechend angepasst.

## [1.6.0-beta.19] - 2026-04-25

Performance- und Installer-Robustheit (#500), plus systematischer
Cross-Integration-Audit aller Beta-Issues mit den dabei gefundenen
Luecken behoben.

**Bundesagentur-Performance: Detail-API-Calls limitiert**
- Vorher: Pro Stelle ein Detail-API-Call → bei 6 Keywords × 100 Treffer ≈
  600 sequentielle Calls (5+ Minuten allein fuer BA).
- Jetzt: Detail-Beschreibungen nur fuer die ersten 20 Treffer pro Keyword;
  Rest behaelt die `beruf`-Kurzbeschreibung. Faktor ~4 schneller, kein
  Volumenverlust.

**Installer-Coverage geprueft + Luecken geschlossen**
- `INSTALLIEREN.bat` (Windows-Embedded): `python-jobspy` (Core seit beta.16)
  und `geopy` (Core seit langem) fehlten in der manuellen Paket-Liste —
  ergaenzt. JobSpy-Quellen waren bei diesem Installer-Pfad heimlich tot.
- `installer/install.sh` (macOS/Linux): `playwright install chromium`
  fehlte komplett — ergaenzt. Vorher liefen Stepstone, Freelancermap-
  Fallback, LinkedIn-Browser auf macOS/Linux nach `pip install` mit
  "Executable doesn't exist".
- `installer/setup_gui.py` (Windows-GUI / Setup.exe): nutzt
  `pip install -e .[scraper,docs]` — aber `playwright install chromium`
  fehlte. Ergaenzt mit Subprocess-Aufruf nach Extras-Installation.
- `installer/install.ps1` (Windows-PowerShell): war bereits sauber
  (`-e .[all]` + `playwright install chromium`).

### Changed
- `bundesagentur.py`: `_DETAIL_FETCH_LIMIT_PER_KW = 20`.
- 3 Installer-Skripte ergaenzt.

**Cross-Integration-Audit (Phase A: Test-Schulden, Phase B: Beta-Issues)**

Phase A — bestehende Test-Schulden vor dem Audit beseitigt:
- 3 Schema-Version-Asserts (`test_v010`, `test_email_service`,
  `test_v120_simulations`) hatten harte `== <fixe Zahl>` und blockierten
  jeden Schema-Bump unnoetig. Auf `>= <historische Untergrenze>`
  umgestellt — Forward-Compat erhalten, Tests bleiben sinnvoll.
- `test_mcp_registry`: `stil_auswertung` (Tool aus #406, fruehere Beta)
  fehlte in `EXPECTED_TOOL_NAMES`, `tools_count` 91 → 92 korrigiert.
- `test_daily_impulse_service::test_loads_140_entries` von hartem 140 auf
  `>= 140` umgestellt (Pool waechst, aktuell 143).
- README-Badge + Tabelle auf 533 Tests, 92 MCP-Tools, 22 Quellen,
  Schema v27.

Phase B — Beta-Issue-Cross-Audit:
- B-1 SOURCE_REGISTRY ↔ _SCRAPER_MAP ↔ Adapter-v2-Registry: alle drei
  alignen sauber bei 24 Quellen, alle 7 defekt-Eintraege haben grund
  und manueller_fallback. ✓
- B-3 `scraper_diagnose` zeigt alle 7 Zustaende (defekte_quellen,
  stumme_quellen, auto_deaktiviert) korrekt. ✓
- B-4 `/api/sources` liefert `defekt`, `defekt_grund`,
  `manueller_fallback` fuer alle 7 defekten + `health` fuer alle. ✓
- B-5 `update_scraper_health` differenziert ok/silent/fail sauber,
  Heuristik "verdaechtig schnell" greift bei time_s<2s, Auto-Deactivate
  nach 5 stillen Laeufen funktioniert. ✓
- B-6 #506-Fix isoliert in der MCP-Tool-Logik (`bewerbung_erstellen`),
  Dashboard-`api_add_application` ist transparent (kein Override). ✓
- **B-7 LUECKE:** `build_search_keywords` reichte weder
  `keywords_muss`/`keywords_plus` noch `greenhouse_companies` weiter.
  linkedin/xing-Adapter lasen `keywords_muss` aus `kw_data` und bekamen
  immer `[]`; Greenhouse-User konnten keine eigenen Slugs konfigurieren.
  → Beide Schluessel jetzt im Output, 3 neue Tests.
- **B-8 LUECKE:** Eine Mailto-Stelle in `ApplicationsPage.jsx` Zeile 832
  baute `mailto:${app.kontakt_email}` als Template-String — bei
  "Name <addr@host>"-Format geht der Link kaputt. → Mit `buildMailto`
  gehaertet (transparent fuer einfache Adressen).
- B-9 `get_default_active_source_keys` filtert defekt + login_erforderlich
  korrekt: 14 aktiv von 24, 10 ausgeschlossen (7 defekte + 3 Login). ✓

### Tests
- 533/533 gruen (vorher 530, +3 neue).
- Release-Gate-Check sauber.

## [1.6.0-beta.18] - 2026-04-25

Scraper-Reanimation Phase 3 (#500): Selektor-Reparaturen + URL-Updates fuer
zwei weitere Quellen, die "still" mit HTTP 200 ohne Treffer dastanden.
Diagnose-Befund: kimeta + heise_jobs sind echte SPAs (SSR liefert nur
Kategorie-Listen) — diese werden korrekt als defekt markiert.

**Stellenanzeigen.de repariert** (25 Live-Treffer)
- Bisheriger Selektor `article, .job-item, [class*='stellenangebot']` matcht
  im aktuellen DOM nichts. Die Seite hat ueberhaupt keine `<article>` mehr.
- Echte Job-Links haben jetzt das stabile Schema `/job/<slug>` mit Titel-
  Text. Neuer Selektor `a[href^="/job/"]` liefert 50 Anchors, davon 25
  einzigartige Stellen.

**Freelancermap repariert** (22 Projekte in 1.7s)
- Alte URL `projektboerse.html?q=Python&ort=Hamburg` 301-redirected jetzt
  auf `/projekte` — und schluckt dabei den Query-String. Adapter holte
  immer die Homepage statt Such-Ergebnisse.
- Neues URL-Schema: `/projekte/<keyword-slug>` (slug-basiert).
  `build_search_keywords` baut die Slugs jetzt entsprechend.
- Adapter zieht `a[href*="/projekt/"]` aus dem HTML; die alte
  `projectsObject`-JS-Extraktion bleibt als zweiter Pfad fuer den Fall,
  dass die Seite den Embedded-State zurueckbringt.

**Als defekt markiert: kimeta + heise_jobs**
- kimeta `/jobs?q=...` liefert 235 Links zu Berufsgruppen-Kategorien
  (Abteilungsleiter, Account-Manager, Altenpflege, ...), aber keine
  einzelnen Stellen — die werden client-seitig per JS nachgeladen.
- heise jobs.heise.de zeigt nur Themen-Aggregationen (Jobs Informatik,
  Jobs Softwareentwickler), keine konkreten Postings im SSR.
- Beide sichtbar gesperrt mit Chrome-Extension-Workaround-URL, wie in
  beta.16 fuer <FIRMA>/gulp/ingenieur_de eingefuehrt.

### Aktuelle Trefferquote (vorher 7 → jetzt 9 liefernde Quellen)
| Quelle | Treffer (Live) |
|---|---|
| bundesagentur | 600 |
| freelance_de | 60 |
| <FIRMA> | 50 |
| jobspy_indeed | 37 |
| stepstone | 25 |
| jobspy_linkedin | 25 |
| **stellenanzeigen_de** (neu) | **25** |
| **freelancermap** (neu) | **22** |
| greenhouse | DACH-Pool 2535 |
| arbeitnow | 1-17 |

### Changed
- `freelancermap.py`: Neue HTML-Strategie + Header, slug-basierte URL.
- `stellenanzeigen_de.py`: Selektor `a[href^="/job/"]` statt Card-Suche.
- `__init__.py`: `freelancermap_urls` als slug-URLs gebaut.

### Defekt markiert
- `kimeta`, `heise_jobs` mit konkretem Grund + manueller Fallback.

## [1.6.0-beta.17] - 2026-04-25

Scraper-Reanimation Phase 2 (#500): Zwei vollstaendig kostenlose, key-freie
Aggregatoren neu hinzugefuegt + Stepstone-Parser repariert. Marktabdeckung
sprunghaft erweitert ohne Abhaengigkeit von kostenpflichtigen Diensten.

**Neue Quellen (beide ohne API-Key, ohne Login):**
- **Arbeitnow** (`arbeitnow.com/api/job-board-api`) — freier deutscher Job-
  Aggregator mit offener REST-API. 100 Stellen pro Seite, bis zu 3 Seiten
  pro Lauf. Live-Test 2026-04-25: 17 Python-Stellen deutschlandweit, 1 in
  Hamburg.
- **Greenhouse Boards** (`boards-api.greenhouse.io`) — direkte
  Karriereseiten-API von 10 kuratierten DACH-relevanten Firmen (N26,
  Celonis, HelloFresh, GetYourGuide, Datadog, Elastic, Cloudflare,
  MongoDB, GitLab, Twilio). Zusammen 2535 Stellen im Pool;
  Region-Filter mit DACH-Toleranz (Hamburg matcht auch
  Germany/Europe/EMEA/Remote). User kann eigene Greenhouse-Slugs ueber
  das Suchkriterium `greenhouse_companies` ergaenzen.

**Stepstone-Parser repariert:**
- Bisher schnappte Strategy 1 (alle `<article>`) UI-Filter-Chips als
  Stellen-Titel ("Neuer als 24h", "Teilweise Home-Office",
  "Auf Unternehmenswebsite"). 32 Stellen wurden gefunden, aber alle
  unbrauchbar.
- Neue Reihenfolge: JSON-LD `JobPosting` zuerst (autoritativ),
  dann `<article>` mit UI-Noise-Regex-Filter und Pflicht auf
  `/stellenangebot`-Link, dann Anchor-Fallback.

**Recherche-Ergebnisse die wir NICHT umsetzen** (User-Direktive
"darf nichts kosten"):
- Adzuna API → erfordert Account-Registrierung trotz Free-Tier.
- Jooble API → erfordert API-Key.
- Apify / Unified.to / TheirStack → kostenpflichtig.
- Lever Postings API → 0/15 Slug-Treffer; spaeter mit User-Liste.

### Added
- `job_scraper/arbeitnow.py` (~140 Zeilen).
- `job_scraper/greenhouse.py` (~170 Zeilen) inklusive `DEFAULT_COMPANIES`-
  Liste und DACH-Toleranzen fuer Region-Match.
- 2 neue Eintraege in `SOURCE_REGISTRY` und `_SCRAPER_MAP`.

### Changed
- `stepstone.py`: Multi-Strategy-Reihenfolge, JSON-LD prefereed,
  UI-Noise-Filter.

### Confirmed working
- freelance_de liefert direkt 60 Projekte pro Lauf — frueheres
  `fail`-Status war transient. Kein Code-Fix noetig, naechste
  Suche normalisiert die Health-Daten.

## [1.6.0-beta.16] - 2026-04-25

Scraper-Reanimation Phase 1 (#500): Job-Suche ist Kern-Mehrwert von PBP — eine
Veroeffentlichung ohne funktionierende Quellen ist nicht release-wuerdig. Die
Diagnose aus beta.14 hat gezeigt, dass von 17 Quellen real nur 2 lieferten.
Diese Beta loest die wichtigsten Befunde:

**Booster JobSpy ausgebaut (Indeed 37 + LinkedIn 25 Treffer live bestaetigt):**
- `python-jobspy` von Optional-Extra in Core-Dependency hochgezogen — der
  Booster war bisher in den meisten Installationen schlicht nicht aktiv.
- Bug `country_indeed=None` gefixt — JobSpy crashte intern an
  `Country.from_string(None).strip()`. LinkedIn lieferte deshalb 0 Treffer.
- Neue Quellen `jobspy_glassdoor` und `jobspy_google` ergaenzt. Glassdoor
  und Google werden oft blockiert, laufen aber bei Erfolg als breite
  Aggregatoren mit.
- Registry waechst von 20 auf 22 Quellen.

**Defekte Quellen sichtbar gesperrt (statt heimlich aussortiert):**
- Neue SOURCE_REGISTRY-Felder `defekt`, `defekt_grund`, `manueller_fallback`.
- Live-Diagnose 2026-04-25 markiert: <FIRMA>, gulp, ingenieur_de, solcom,
  monster — bekannt defekt (HTTP 404 / 403 / Timeout).
- `run_search` ueberspringt defekte Quellen, schreibt Skip-Detail
  `defekt: <grund>` ins Status-Tracking. Keine stillen Phantom-Erfolge mehr.
- `get_default_active_source_keys` aktiviert defekte Quellen nicht mehr
  vorab beim ersten Profil.
- Frontend `SourceSelectionList`: defekte Quellen werden ausgegraut
  (opacity 60%, Name durchgestrichen), Toggle ist disabled mit
  Tooltip-Hinweis. Roter "Defekt"-Badge + Hinweisbox mit dem konkreten
  Grund und dem Chrome-Extension-Workaround (URL-Link, der den
  manuellen Import via `stelle_manuell_anlegen` empfiehlt).
- `scraper_diagnose` MCP-Tool listet `defekte_quellen` mit Grund und
  Fallback-URL prominent.

**Jobware-URL-Update:**
- Live-Test 2026-04-25: `/jobs` liefert 200, `/suche/` und `/stellenangebote/`
  404. Neue URL als erstes in der Probe-Liste.

### Added
- 1 neuer Test (`test_sources_api_exposes_defekt_fields`).
- 4 neue JobSpy-Site-Funktionen (`search_jobspy_glassdoor/_google` + Helper).

### Changed
- `python-jobspy` als Core-Dependency (vorher `[scraper]`-Extra).
- `build_source_rows` und `get_default_active_source_keys` respektieren
  `defekt`-Flag.
- 2 bestehende Tests (`test_sources_default_*`, `test_profile_specific_*`)
  filtern erwartete Defaults nun auch nach `defekt`.

## [1.6.0-beta.15] - 2026-04-25

Bugfix #506: `bewerbung_erstellen` ignorierte den `status`-Parameter, wenn
`bereits_beworben=False` gesetzt war — der Status wurde immer auf
`in_vorbereitung` ueberschrieben. Jetzt wird ein expliziter Status
respektiert (z.B. `zurueckgezogen` fuer Inbound-Anfragen, die ohne
Bewerbung sofort abgelehnt werden). Default-Verhalten bleibt unveraendert:
ohne expliziten `status` mappt `bereits_beworben=False` weiterhin auf
`in_vorbereitung`.

### Fixed
- #506: `bewerbung_erstellen(bereits_beworben=False, status="zurueckgezogen")`
  legt die Bewerbung mit Status `zurueckgezogen` an statt sie auf
  `in_vorbereitung` zu zwingen. Spart einen unnoetigen
  `bewerbung_status_aendern`-Call und vermeidet einen falschen
  Status-Eintrag in der Timeline.

### Added
- 4 Regressionstests fuer #506 in `test_v157_flow_completion.py`.

## [1.6.0-beta.14] - 2026-04-25

Scraper-Wahrheit (#499): Status `ok + 0 Treffer` wird nicht mehr als Erfolg
verbucht, sondern als eigener Zustand `silent` getrackt. Stumme Quellen werden
nach 5 stillen Laeufen automatisch deaktiviert, in der Settings-Page mit Badge
gekennzeichnet und vom MCP-Tool `scraper_diagnose` prominent ausgewiesen.

Hintergrund: Reale Tests aller 20 registrierten Adapter haben gezeigt, dass
nur 4 Quellen (bundesagentur, stepstone, <FIRMA>, freelance_de) wirklich Treffer
liefern; 12-13 Adapter melden status=ok ohne Inhalt. Bisher zaehlten diese
als gesund — die Auto-Deaktivierung griff nie. Jetzt sehen Nutzer und Claude
sofort, welche Quellen tatsaechlich aktiv liefern.

### Added
- Schema v27: `scraper_health.last_count`, `last_status_detail`, `consecutive_silent`.
- `update_scraper_health` differenziert `ok` / `silent` / `fail` und gibt das
  Ergebnis-Dict zurueck (`state`, `auto_deactivated`, `detail`).
- Auto-Deaktivierung von Quellen nach 5 stillen Laeufen in Folge.
- `/api/sources` liefert pro Quelle ein `health`-Objekt mit `badge`
  (`ok` / `stumm` / `leer` / `fehler` / `deaktiviert` / `nie`).
- SettingsPage / `SourceSelectionList`: neue Health-Badge ("X Treffer / Ys",
  "0 Treffer", "Auto-Aus") direkt neben dem Speed-Badge.
- `scraper_diagnose` MCP-Tool gibt zusaetzlich `stumme_quellen`,
  `auto_deaktiviert`, `hinweis_stumm`, `hinweis_reaktivierung` aus und
  zeigt pro Eintrag `stille_serie`, `letzte_treffer`, `letzter_status_detail`.

### Changed
- `toggle_scraper` setzt zusaetzlich `consecutive_silent=0` zurueck, damit
  reaktivierte Quellen nicht sofort wieder gegen die Schwelle laufen.

## [1.6.0-beta.13] - 2026-04-25

UX-Quickfixes-Block + Mailto-Bugfix. Schliesst die fuer v1.6.0
geplanten kleinen Luecken in der Posteingang-/Bewerbungs-/Stats-/
Profil-/Kalender-Welt. Mail-Integration-Arc (#469, #478, #480) wurde
nach Recherche auf v1.7.0 verschoben.

### Added

- **#454 stil_auswertung MCP-Tool + /api/stats/style + StatsPage-Card**:
  Aggregiert alle bewerbung_stil_tracken-Eintraege ueber alle
  Bewerbungen und berechnet pro Stil Anzahl + Interview-/Angebots-/
  Absage-Quote (MIN_SAMPLES=3). Damit ist die Daten-Senke aus #454
  endlich auswertbar — sowohl fuer Claude (MCP-Tool) als auch im UI
  (StatsPage Card "Anschreiben-Stile im Vergleich").
- **#457 termin-spezifischer Interview-Prep-Button**: CalendarPage
  zeigt fuer Interview-Meetings (interview, telefoninterview, video,
  vor_ort, kennenlernen, zweitgespraech) einen Briefcase-Button,
  der `/interview_vorbereitung stelle="..." firma="..."` mit dem
  konkreten Meeting-Kontext in die Zwischenablage kopiert.
  DashboardPage-Schnellzugriff verwendet ebenfalls den Termin-Kontext.
- **#458 keyword_vorschlaege im UI**: Neuer Endpoint
  `GET /api/keyword-suggestions` (Status: keine_jobs / zu_wenig_jobs
  / ok, MIN_JOBS=20). ProfilePage zeigt in der Suchkriterien-Card
  Plus-/Minus-Buttons, die direkt in keywords_plus / keywords_ausschluss
  schreiben — ohne Umweg ueber Claude.
- **#459 Posteingang fuer unzugeordnete Mails**: Neuer Endpoint
  `POST /api/emails/{email_id}/create-application` legt eine Bewerbung
  aus einer Mail an und verknuepft die Mail. Title-Fallback aus
  Subject, Company-Fallback aus Sender-Domain. EmailDetailModal zeigt
  fuer unzugeordnete Mails einen "Neue Bewerbung daraus erstellen"-
  Button.
- **#463 Firmen-Recherche-Sektion im Dossier**: Neuer Endpoint
  `PUT /api/applications/{app_id}/research-notes` speichert
  Recherche-Notizen am verknuepften Job (research_notes-Spalte).
  ApplicationsPage-Dossier zeigt nach den Stellendetails eine Card
  "Firmen-Recherche" mit "Mit Claude aktualisieren"-Button (kopiert
  `/firmen_recherche firma=...`), TextArea und Speichern-Button.
- **#467 Sprach-Tipp im Tagesimpuls-Pool**: 3 neue Tipps zu Mikrofon-
  Eingabe in Claude Desktop — gerade fuer Profil-Aufbau und
  Interview-Training relevant.
- **8 neue Dashboard-Tests** decken alle neuen Endpoints ab.

### Fixed

- **Mailto-Links im EmailDetailModal**: "Von:"/"An:" zeigte sich
  zuvor nur als Text-Zeile; ein Klick startete keinen Mail-Client.
  Modal hat jetzt Sender-/Recipient-Mailto-Links und einen prominenten
  "Antworten"-Button im Footer (Subject mit "AW:"-Prefix). Im
  Dossier-Email-List ist die Gegenpartei-Adresse ebenfalls als
  Mailto-Link klickbar (zusaetzlich zum Reply-Icon-Button).

### Changed

- **#469, #478, #480 nach v1.7.0 verschoben**: Thunderbird-MCP-
  Integration, Thunderbird-Add-On und Outlook-Add-In bilden in v1.7.0
  einen koordinierten Mail-Integration-Arc auf einer gemeinsamen
  anbieter-agnostischen Import-Abstraktion. Der bestehende
  POST /api/emails/{id}/create-application-Endpoint (#459) reicht
  fuer den manuellen via-Claude-Desktop-Workflow.
- **#465 abgesorbiert in #425**: Aehnliche-Stellen-Idee wandert in
  den Lokales-LLM-Plan (Embeddings via sqlite-vec); Issue als
  "not planned" geschlossen.
- **Database.update_job** erlaubt jetzt `research_notes` als Feld.

## [1.6.0-beta.12] - 2026-04-25

Adapter-v2-Flip (#499) + Jobsuche-Button ohne Claude (#461):
Die neue Scraper-Architektur ist jetzt tatsaechlich zuschaltbar — ueber
das Feature-Flag `scraper_adapter_v2` (Env-Var `PBP_FEATURES=scraper_adapter_v2`)
laeuft die komplette Jobsuche-Pipeline durch den neuen Adapter-Orchestrator
mit Fehler-Isolation pro Quelle. Zusaetzlich kann die Jobsuche jetzt direkt
aus dem Dashboard gestartet werden, ohne den Umweg ueber Claude.
Default bleibt der alte Pfad; der neue wird schrittweise haerter getestet.

### Added

- **Generischer `LegacyScraperAdapter`**: Wickelt jede
  `search_*`-Funktion des Scraper-Pakets hinter die
  `JobSourceAdapter`-Schnittstelle. Damit deckt die Registry ab
  sofort **alle 20 Quellen** aus `_SCRAPER_MAP` ab (vorher: nur 5
  spezialisierte Adapter), ohne pro Quelle eine Wrapper-Klasse zu
  brauchen. Spezial-Adapter (Bundesagentur, <FIRMA>, JobSpy,
  GoogleJobs) bleiben unveraendert und ueberschreiben den
  generischen Eintrag.
- **Feature-Flag-Pfad in `run_search()`**: `_load_scraper()` liefert
  mit aktivem Flag einen Adapter-Aufruf statt der Direkt-Import-
  Funktion. Timeout-Handling, Parallel-Lauf, Playwright-Serialisierung
  und Progress-Reporting bleiben vollstaendig im alten Code —
  veraendert wird nur der innere "Scraper holen"-Schritt.
- **`adapter_pfad`-Feld im Jobsuche-Ergebnis**: `result.adapter_pfad`
  = `"v2"` oder `"legacy"`, damit im Dashboard/Log nachvollziehbar
  ist, welcher Pfad gelaufen ist.
- **7 Smoke-Tests (`tests/test_scraper_adapter_v2.py`)**: Adapter
  fuer jede `_SCRAPER_MAP`-Quelle vorhanden; Legacy-Adapter isoliert
  Exceptions; Orchestrator reisst nicht um wenn ein Adapter crasht;
  `run_search` routet ohne Flag durch den alten und mit Flag durch
  den neuen Pfad.
- **#461 `POST /api/jobsuche/start`**: Neuer Dashboard-Endpoint
  spiegelt die Logik des MCP-Tools `jobsuche_starten` — filtert
  manuelle Quellen (Claude-in-Chrome-only) heraus, blockt
  Doppel-Starts laufender Jobs, startet den Scraper im Thread-Pool
  mit Timeout-Watchdog.
- **`startJobsuche()`-Helper im Frontend**: App-Context-Funktion
  ruft den neuen Endpoint, zeigt Toast bei Erfolg/Fehler und
  triggert Chrome-Refresh — die globale Statusanzeige aus #487
  schaltet sofort auf "laeuft". 3 neue Dashboard-Tests.
- **Button-Wiring**: DashboardPage (TODO-Karte + Leere-Suche-Hinweis)
  und JobsPage (Banner + Empty-State) rufen jetzt `startJobsuche()`
  statt `copyPrompt('/jobsuche_workflow')`. Nutzer ohne Claude
  bekommen die Suche ohne KI-Umweg direkt aus dem UI.

### Changed

- `JobPosting.to_job_dict()` laesst `description=None` weg (nicht
  mehr als `None` einschleusen), damit Downstream-Heuristiken wie
  Employment-Type-Erkennung nicht auf `None[:500]` crashen.

### Known Issues

- Die Sub-Issues des Epics (#486 Polling-Fix, #487 globale
  Statusanzeige, #488 Chrome-Fallback fuer deprecated Quellen, #489
  Bundesagentur-Fix, #490 JobSpy-Stabilisierung, #461
  Dashboard-Button) sind weiterhin offen und werden schrittweise
  auf dem neuen Pfad umgesetzt.

## [1.6.0-beta.11] - 2026-04-25

Duplikat-Pruefung gehaertet + Merge-Tool fuer nachtraegliche
Duplikat-Aufloesung. Der Real-Case aus #471 (zwei VirtoTech-Stellen
innerhalb von 2 Stunden, Titel leicht umformuliert) wird jetzt erkannt;
und fuer Altlasten gibt es `stelle_mergen()` mit Dry-Run-Default.

### Added

- **#470 `stelle_mergen()` MCP-Tool:** Fuehrt zwei doppelt angelegte
  Stellen zusammen. Dry-Run standardmaessig aktiv — zeigt Vorschau
  mit Feld-Entscheidungen, Konflikten und welche Bewerbungen
  umgehaengt werden. Mit `dry_run=False` wird in einer Transaktion
  ausgefuehrt (Applications umhaengen, Master-Felder mergen,
  Duplikat-Job loeschen).
- **`feld_strategie`-Parameter:** Pro Feld ueberschreibbar mit
  `'master'` (Default), `'duplikat'` oder `'merge'` (fuer Description:
  beide Texte werden konkateniert). Felder, die nur im Duplikat
  gefuellt sind, werden immer automatisch uebernommen.
- **`duplicate_detection.py`:** Neue gemeinsame Utility mit
  `normalize_company_name()` und `find_duplicate_job()`. Erkennt:
  Rechtsform-Suffixe (GmbH, Ltd., AG, KG, ...), Klammer-Zusaetze
  (Endkunde/Abteilung), Umlaute, Domaenen-Keywords (PLM, SAP, ERP,
  CAD, Teamcenter, ...), Zeitnaehe.
- **12 Tests fuer Duplikat-Erkennung** + 9 Tests fuer `merge_jobs`.

### Changed

- **#471 `stelle_manuell_anlegen` Duplikat-Pruefung gehaertet:**
  Der bisherige Token-Overlap-Check hat Fuzzy-Umformulierungen wie
  `PLM Expert via VirtoTech` vs. `SAP / PLM Lead Consultant` nicht
  erkannt. Neue Logik mit normalisierter Firma + Domain-Keyword-
  Overlap + Zeitnaehe findet den Fall. Check laeuft jetzt ueber
  **Bewerbungen UND Jobs** (inkl. dismissed), nicht nur Bewerbungen.
- Duplikat-Warnung ist jetzt aussagekraeftiger (enthaelt
  Match-Grund und gemeinsame Tokens).

## [1.6.0-beta.10] - 2026-04-24

Bewerbungsbericht aufgewertet: Zeitraum und Erstellungszeitpunkt stehen
jetzt prominent auf der Titelseite, das PDF hat drei neue Sektionen
(Bewerbungsart-Verteilung, Ablehnungsgruende, offene Follow-ups), und
Zahlen-Inkonsistenzen zwischen Spitzen-Score, Interview-Zahl und
„Nicht beworben"-Liste sind behoben.

### Added

- **Titelseite**: „Zeitraum: DD.MM.YYYY bis DD.MM.YYYY" und
  „Erstellt am DD.MM.YYYY um HH:MM Uhr" immer prominent sichtbar —
  egal ob Zeitraum explizit gesetzt oder aus den Daten abgeleitet.
- **Sektion 4 — Bewerbungsart-Verteilung**: Tabelle mit Anzahl und
  Anteil pro Bewerbungsart (initiativ, direkt, Headhunter, ...).
- **Sektion 7 — Ablehnungsgruende**: Ablehnungen insgesamt, Top-Gruende
  (bis 15), letzte 10 abgelehnten Bewerbungen.
- **Sektion 8 — Offene Follow-ups**: Alle offenen Nachfass-Termine,
  ueberfaellige rot hervorgehoben.
- **Zeitraum-Filter**: `GET /api/applications/export` akzeptiert jetzt
  `from` und `to` als Query-Parameter. Die Statistik-Seite gibt den
  aktuell ausgewaehlten Zeitraum (30d / 90d / 6m / 12m / Alles) beim
  Export mit — sowohl fuer PDF als auch Excel.
- **Excel-Bericht**: Zeitraum und Erstellungszeitpunkt stehen jetzt
  als Kopfzeilen auf dem Statistik-Sheet. `generate_excel_report()`
  akzeptiert `zeitraum_von` und `zeitraum_bis`.

### Changed

- Bewerbungsliste und Executive Summary benutzen jetzt dieselbe
  kanonische Datenquelle (`db.get_report_data()`) — sowohl dashboard-
  als auch MCP-Pfad. Doppel-Aggregation im MCP-Tool wurde entfernt.
- Inhaltsverzeichnis von 7 auf 10 Eintraege erweitert, doppelter
  „1. Zusammenfassung"-Block entfernt.

### Fixed

- **Spitzen-Score konsistent**: `max_score`/`avg_score` in
  `get_statistics()` haben dismissed Jobs ausgeschlossen — die
  „Nicht beworben"-Sektion zeigt sie aber an. Dadurch stand oben
  z.B. „Spitzen-Score: 22", unten tauchten Stellen mit Score 27+ auf.
  Dismissed Jobs werden jetzt mitgezaehlt.
- **Interview-Rate korrekt**: Wer auf `angebot` oder `angenommen`
  weitergerutscht ist, hatte zwingend ein Interview — zaehlte bisher
  aber nicht mehr mit. Folge: Zahl sank, sobald Kandidaten
  weiterkamen. Fix in `get_statistics()` und Bericht.
- **Score-Anzeige konsistent**: Der stille „+5 Bonus fuer beworbene
  Stellen" im MCP-Export-Tool ist entfernt. Rohe Fit-Scores ueberall.

## [1.6.0-beta.9] - 2026-04-24

Prompt-Templates pro Dokumenttyp: Der „Analysieren"-Button im
Dokumenten-Tab kopiert jetzt einen typ-spezifischen Prompt in die
Zwischenablage — je nachdem ob das Dokument eine Bewerbungsbestaetigung,
eine Stellenausschreibung, eine Absage, ein Vertrag, eine
Gespraechsnotiz oder ein Profildokument ist. Auswahl geschieht
automatisch, kann aber manuell ueberschrieben werden.

### Added

- **#496 Prompt-Templates pro Dokumenttyp:** 7 Templates in
  `src/bewerbungs_assistent/document_analysis_prompts.py` (Bewerbungs-
  bestaetigung, Stellenausschreibung, Absage, Gespraechsnotiz, Vertrag,
  Profil-Aufbau, Fallback). Automatische Auswahl anhand `doc_type`,
  Dateiname und bereits extrahiertem E-Mail-Text (via `STATUS_PATTERNS`
  aus dem email_service).
- **Neuer Endpoint** `GET /api/analysis-templates` — liefert die
  komplette Template-Liste fuer UI-Dropdowns.
- **Template-Dropdown im Dokumenten-Tab:** Im expandierten Dokument
  kann der Nutzer das Template ueberschreiben (Default „Auto") bevor
  er auf „Analysieren" klickt.
- 25 neue Tests in `tests/test_document_analysis_prompts.py`.

### Changed

- `GET /api/document/{id}/analysis-prompt` akzeptiert jetzt
  `?template=<key>` und liefert `template`, `template_label`,
  `apply_to_profile` sowie `available_templates` mit.
- Frontend: `DocumentsPage.buildAnalysisPrompt` entfernt — Prompt wird
  jetzt serverseitig gebaut, damit beide Seiten dieselbe
  Template-Definition verwenden.
- „Analysieren"-Button in der expandierten Dokument-Ansicht erscheint
  jetzt auch bei bereits analysierten Dokumenten (mit Label „Erneut
  analysieren"), damit man mit einem anderen Template neu loslaufen
  kann.

## [1.6.0-beta.8] - 2026-04-24

Follow-up-Lifecycle: Wenn eine Bewerbung terminal wird (abgelehnt,
abgesagt, zurueckgezogen, angenommen, abgelaufen), verschwinden ihre
offenen Follow-ups automatisch aus dem Dashboard. Und nach einem
abgeschlossenen Interview wird automatisch eine Nachfrage-Erinnerung
angelegt — Frist konfigurierbar.

### Added

- **#494 Auto-Nachfrage nach Interview:** Statuswechsel auf
  `interview_abgeschlossen` schliesst alte Follow-ups und legt ein
  neues „Nachfrage"-Follow-up an (Default 14 Tage, konfigurierbar,
  0 = deaktiviert).
- **Einstellungen → System: Follow-up-Automation:** Neuer Bereich
  mit zwei Feldern:
  - „Nachfrage nach Bewerbung" (`followup_default_days`, Default 7)
  - „Nachfrage nach Interview" (`followup_interview_delay_days`, Default 14)
- **HTTP-Endpoints:** `GET/PUT /api/settings/followup` fuer die Werte.
- **HTTP-Status-Endpoint liefert Lifecycle-Info:** `PUT /api/applications/{id}/status`
  gibt jetzt `lifecycle.followups_dismissed` und bei Interview-Abschluss
  `lifecycle.new_followup` (id + scheduled_date) zurueck.

### Changed

- **#497 Event-System (minimal):** Lifecycle-Hooks wandern in
  `Database.update_application_status()` → `_apply_status_lifecycle()`.
  HTTP-Endpoint und MCP-Tool `bewerbung_status_aendern` nutzen jetzt
  denselben Hook — vorher war die Dismiss-Logik nur im MCP-Tool,
  sodass UI-Statuswechsel die Follow-ups nicht mitzogen (#493).
- **Terminale Status vereinheitlicht:** Neue Konstante
  `Database.TERMINAL_STATUSES = ("abgelehnt", "zurueckgezogen",
  "angenommen", "abgelaufen", "abgesagt")` — `abgesagt` war vorher
  nicht abgedeckt.

### Fixed

- **#493 Offene Follow-ups bei UI-Statuswechsel:** UI-seitiges
  Setzen auf abgelehnt/abgesagt/... liess offene Follow-ups zurueck,
  weil der HTTP-Endpoint die Dismiss-Logik umging. Jetzt zentral im
  Database-Layer.

### Deferred nach v1.7

- **#474** (Bewerbungs-Ordner im Filesystem) — Migrations-Risiko,
  eigener Release-Zyklus sinnvoll.
- **#478** (Thunderbird-Add-On) + **#480** (Outlook-Add-In) —
  Research-Phase nach bestehenden Add-Ons/MCP-Loesungen geplant,
  dann als Sub-Repos mit klar definierter Upload-API.
- **#481** (Kalender-Sync) — iCal-Export eventuell in spaeterer
  v1.6.x-Beta, CalDAV/Graph-Sync fuer v1.7.

## [1.6.0-beta.7] - 2026-04-24

Dark/Light Mode mit vollstaendig anpassbaren Paletten. Standard folgt
der System-Einstellung, Umschalter in der Topbar, detaillierte
Farb-Editoren pro Modus in den Einstellungen. Jede Aenderung laesst
sich jederzeit auf den Standard zuruecksetzen.

### Added

- **#475 Dark/Light Mode:** Drei-Wege-Umschalter (System · Hell · Dunkel)
  in der Topbar. Systemmodus respektiert `prefers-color-scheme` und
  reagiert live auf OS-Wechsel. Auswahl persistiert in `localStorage`.
- **Custom-Paletten:** Neuer Tab „Erscheinungsbild" in den Einstellungen
  mit Color-Picker fuer alle 10 Theme-Tokens (App-Hintergrund, Cards,
  Text, Borders und 4 Akzentfarben) pro Modus. Aenderungen greifen
  sofort als inline CSS-Variablen auf `<html>`.
- **Reset-Mechanismen:** Pro Token (Pfeil-Icon), pro Modus
  („Standard wiederherstellen") und global („Alles zuruecksetzen").

### Changed

- **`styles.css` refaktoriert:** Alle hardcoded `rgba(...)`-Werte in
  den `.glass-*`-Klassen auf CSS-Variablen (`rgb(var(--color-X) / α)`)
  umgestellt. Basis fuer das Theme-Swapping via `[data-theme="light"]`.
- **Semantische Surface-Tokens:** Neue Variablen
  `--surface-overlay-{weak,soft,strong}` und `--surface-shadow`
  trennen Overlay-Farben vom Theme-Modus (hell vs. dunkel).

### Fixed

- Light-Mode-Akzentfarben nutzen 600er-Varianten (teal-600, amber-600,
  rose-600, blue-600) statt der 400/500er des Dark-Modes — fuer
  WCAG-AA-Kontrast auf weissem Grund.

### Closes

- Epic **#500** (v1.6.0 UX-Finish): alle sechs Sub-Issues erledigt.

## [1.6.0-beta.6] - 2026-04-24

Dashboard-Aktionen springen jetzt ueberall mit passendem Filter in
den Bewerbungs-Tab. Kein „hier sind alle 247 Bewerbungen, viel Spass
beim Suchen" mehr.

### Changed

- **#483 „Interview vorbereiten"** kopiert keinen Prompt mehr, sondern
  oeffnet den Bewerbungs-Tab mit Status-Filter `Interview`. Anzahl
  stimmt mit dem Dashboard-Hinweis ueberein.
- **#484 „Nachfragen nicht vergessen"** oeffnet den Bewerbungs-Tab
  mit einem neuen Client-Filter `followups_due` — nur Bewerbungen, bei
  denen ein Follow-up faellig ist (scheduled_date &le; heute).
- **#485 „Lange keine Antwort"** oeffnet den Bewerbungs-Tab mit dem
  neuen Filter `zombies` — nur Bewerbungen aus `/api/applications/zombies`
  (Schwelle: 60 Tage ohne Antwort).

### Added

- ApplicationsPage liest `intent.filter` aus dem Navigations-Intent
  und mappt ihn auf die lokale Filterlogik. Vorherige Filter werden
  ueberschrieben, damit die Zahl mit dem Dashboard-Hinweis passt.
- Sichtbarer „Filter: …" Banner oben im Filter-Bereich mit Zaehlung
  (`N von M`) und Reset-Button, damit der User sieht, warum weniger
  Bewerbungen angezeigt werden.

---

## [1.6.0-beta.5] - 2026-04-24

Block C Start — drei Dashboard-Bugs aus dem Review gefixt. Kein neues
Feature, sondern drei Details, die User-Vertrauen untergraben haben:
Button ohne Funktion, Zaehler vs. Filter-Widerspruch, Termin, der nicht
dort auftaucht, wo er erwartet wird.

### Fixed

- **#491 „Analysieren"-Button kopiert jetzt einen Analyse-Prompt** in
  die Zwischenablage und bestaetigt das per Toast. Prompt referenziert
  Dateiname, Typ und ggf. verknuepfte Bewerbung und verweist den LLM
  direkt auf `dokumente_zur_analyse`. Backend-Flag (`reanalyze`) bleibt
  erhalten — User bekommt zusaetzlich den kopierbaren Text.
  Prompt-Template zentral in `buildAnalysisPrompt()` pflegbar.
- **#492 Dokumente-Filter-Zaehler stimmt wieder mit der Liste ueberein**.
  Der Zaehler „Nicht analysiert (N)" rechnete `nicht_extrahiert OR
  basis_analysiert OR NULL`, der Filter filterte aber exakt nur auf
  `nicht_extrahiert`. Fix: Filter-Parameter `nicht_extrahiert` ist nun
  ein Sammelbegriff fuer alle „unfertigen" Stati — Zaehler und Liste
  zeigen dieselben Dokumente.
- **#495 Zweitgespraech-Termin erscheint in der Bewerbungs-Liste** als
  Teil der neuen Sektion „Offene Aktionen". Bisher zeigte die Seite
  nur `follow_ups`, Termine fehlten — jetzt wird auch
  `/api/meetings?days=30` geladen und oben in der Aktions-Liste mit
  eigenem Teal-Badge „Termin" dargestellt. Zweitgespraeche und
  Interviews sind damit im Bewerbungs-Tab nicht mehr unsichtbar.

### Changed

- ApplicationsPage: Card „Follow-ups (N)" heisst jetzt „Offene
  Aktionen (M+N)" und zeigt Termine + Nachfragen zusammen. Termine
  zuerst (zeitkritisch), Follow-ups darunter.

---

## [1.6.0-beta.4] - 2026-04-24

Block B, Teil 3 (Finale): Scraper-Block ist inhaltlich durch — keine
neuen Quellen mehr, stattdessen die UX-Luecken rund um die Jobsuche
geschlossen. User sehen jetzt global, was gerade im Hintergrund laeuft,
der LLM-Assistent pollt nicht mehr in Schleifen auf den Fortschritt,
und deprecated Quellen werden vor dem Start klar gemeldet statt lautlos
zu timeouten.

### Added

- **Status-Badge in der Sidebar** (#487). Live-Fortschritt der Jobsuche
  global auf allen Seiten sichtbar, direkt unter der MCP-Verbindung.
  Beim Uebergang running → fertig wird die Trefferzahl eingeblendet und
  ein Klick springt zu den neu reingekommenen Stellen. Tailwind-Farben
  an das bestehende Theme angepasst: iris (laeuft), teal (fertig),
  amber (Timeout-Quellen). Neues Backend-Endpoint `/api/jobsuche/last`
  liefert den letzten abgeschlossenen Job + Timeout-Zaehlung.
- **`get_last_finished_background_job(job_type)`** auf `Database` —
  sucht den juengsten Job in `status in ('fertig','fehler')`, parst
  `params`/`result` als JSON. Wird vom neuen Endpoint genutzt, steht
  aber auch anderen Status-Anzeigen offen.

### Changed

- **`jobsuche_starten` filtert manuelle Quellen vorher raus** (#488).
  LinkedIn, XING, StepStone, Indeed, Monster und Google Jobs sind im
  neuen Dict `_MANUAL_SOURCES` deklariert und werden vor dem
  Background-Job weggefiltert. Der Aufruf kommt als
  `manuelle_quellen`-Dict + Hinweistext zurueck — der User weiss
  sofort, welche Quelle welchen Ersatzweg hat (JobSpy, Chrome-Extension,
  `google_jobs_url`). Wenn *alle* gewaehlten Quellen manuell sind, gibt
  es `status: nur_manuelle_quellen` und es startet kein Job.
- **Workflow-Prompt in `_jobsuche_workflow`** (#486). Nach dem Start
  explizit verboten, in einer Schleife auf `jobsuche_status()` zu
  warten — stattdessen auf Sidebar-Badge verweisen und den Turn
  beenden. Spart Tokens und verhindert Timeouts im Assistant-Turn.
- **`nachricht`-Text** in `jobsuche_starten` erwaehnt die Sidebar-
  Badge als primaeren Fortschritts-Kanal, `jobsuche_status()` nur als
  Nachschlag fuer explizite Fragen.

### Fixed

- LLM pollt nicht mehr 5-10 Minuten lang auf `jobsuche_status` (#486).
- Manuelle Quellen verursachen keinen stummen Timeout-Pfad mehr (#488).
- Kein globaler Indikator fehlt mehr — Status sichtbar auf allen
  Seiten (#487).

### Known Issues

- `scraper_adapter_v2`-Flag bleibt weiterhin aus. Das Umschalten auf
  die Adapter-Pipeline wurde nach Beta.5 verschoben: nur 5 von 18
  Quellen haben bisher einen Adapter, ein Flip wuerde die restlichen
  13 abschneiden. Kommt zusammen mit dem Migrations-PR fuer den Rest
  der Quellen.

---

## [1.6.0-beta.3] - 2026-04-24

Block B, Teil 2: zwei neue Job-Quellen dazu. LinkedIn + Indeed.de
laufen jetzt ueber die MIT-lizenzierte Open-Source-Bibliothek
`python-jobspy` (#490), Google Jobs ueber die Chrome-Extension (#501).
Beides kostenlos, kein API-Key, kein Account ausser dem bereits
eingeloggten Google-Browser. Bestehender Flow unveraendert — die
neuen Quellen sind separat im Dashboard an/abschaltbar.

### Added

- **`jobspy_linkedin` + `jobspy_indeed`** als neue Scraper-Quellen
  (#490). Dünner Python-Wrapper um `python-jobspy` (MIT, optionale
  Dependency im Extra `scraper`). Liefert Titel, Firma, Ort, Volltext-
  Beschreibung, Gehaltsspanne (falls vorhanden) und Direkt-URL.
  - LinkedIn-spezifisch: Englische Keywords werden automatisch um
    deutsche Aequivalente erweitert (`project manager` → zusaetzlich
    `Projektleiter`), weil LinkedIn sonst keine sauberen DE-Treffer
    filtert.
  - Rate-Limit-Handling: HTTP 429 → Site wird fuer diesen Lauf
    uebersprungen, andere Quellen laufen normal weiter.
  - Graceful degrade, wenn `python-jobspy` nicht installiert ist:
    `NOT_CONFIGURED` statt Crash.
- **`google_jobs` als Quelle + MCP-Tool `google_jobs_url`** (#501).
  Baut die stabile `https://www.google.com/search?q=...&udm=8`-URL mit
  optionalem Zeitraum-Filter (`tbs=qdr:d|w|m`) und Ort. Scraping laeuft
  ueber die Chrome-Extension mit dem eingeloggten Google-Account — der
  zuverlaessig funktionierende Weg, weil Google direkte HTTP-Abrufe
  blockt, den eingeloggten Browser aber nicht. Ingest wie bei LinkedIn
  via `stelle_manuell_anlegen()`.
- **Adapter-Wrapper** fuer alle drei neuen Quellen (`JobSpyLinkedInAdapter`,
  `JobSpyIndeedAdapter`, `GoogleJobsChromeAdapter`). Integration in die
  Adapter-Registry aus Beta.2 — `scraper_adapter_v2` bleibt weiterhin
  aus, das Umschalten kommt in Beta.4.
- **README-Attribution** fuer `python-jobspy` unter Credits →
  Third-Party-Bibliotheken.
- **Smoke-Test** auf 21/21: JobSpy Row-Mapping, LinkedIn-DE-Expansion,
  graceful-without-package, Google-Jobs URL-Schema, Chrome-Adapter-
  Hinweistext.

### Changed

- `SOURCE_REGISTRY` um drei Eintraege erweitert
  (`jobspy_linkedin`, `jobspy_indeed`, `google_jobs`), alle mit
  `beta: True`. `_SCRAPER_MAP` zeigt auf die neuen Module.
- `pyproject.toml`: `python-jobspy>=1.1` im Extra `scraper`
  hinzugefuegt (optional, keine Pflicht-Dependency fuer das Kernpaket).

### Known Issues

- JobSpy/Glassdoor und JobSpy/Google sind upstream broken
  (jobspy#302) und bleiben bewusst deaktiviert.

## [1.6.0-beta.2] - 2026-04-24

Block B, Teil 1: Scraper-Architektur v2 (#499) als Fundament und
Bundesagentur-Stabilisierung (#489). Das neue Adapter-Interface lebt
parallel zur bestehenden `run_search()`-Pipeline — aktiviert wird es
erst in Beta.4 hinter dem Feature-Flag `scraper_adapter_v2`. Kein
bestehender Flow veraendert.

### Added

- **Adapter-Interface (`job_scraper/adapters/`)** — Vertragliche Basis
  fuer Quellen-Adapter: `JobSourceAdapter`, `JobPosting`, `AdapterResult`,
  `AdapterStatus`. Unbekannte Felder aus dem Source-Dict landen in
  `JobPosting.extra` (keine Daten-Verluste beim Roundtrip).
- **Adapter-Registry + Orchestrator** (`registry.py`, `orchestrator.py`)
  — Double-Isolation: unbekannte `source_key` liefern `NOT_CONFIGURED`,
  Exceptions im Adapter werden zu `AdapterResult(status=ERROR)`. Ein
  kaputter Adapter reisst die anderen nicht mit.
- **`BundesagenturAdapter` + `HaysAdapter`** — duenne Wrapper um die
  bestehenden `search_*`-Funktionen. Referenz-Implementierungen fuer
  weitere Migrationen in Beta.3/4.
- **Smoke-Test erweitert** auf 16/16: Adapter-Registry, JobPosting-
  Roundtrip, Fehler-Isolation im Orchestrator, BA-Retry via
  `httpx.MockTransport` (503 → 503 → 200).

### Changed

- **Bundesagentur-API-Client (#489)**:
  - iOS-App-User-Agent (`Jobsuche/2.12.0 … Alamofire/5.6.2`) — die API
    mag einen Client-Kontext sehen statt leerem Python-UA.
  - Retry+Exponential-Backoff (2s/4s/8s) fuer 500/502/503/504 und
    `httpx.TimeoutException`/`TransportError`. Das „DNS cache overflow"-
    503 verschwindet zuverlaessig nach 1–2 Retries.
  - `umkreis_km` aus Dashboard-Criteria wird an die API durchgereicht.
  - Detail-URL auf `pc/v4/jobdetails/{base64(refnr)}` umgestellt — die
    alte `/jobs/{refnr}`-Route liefert seit Anfang 2<telefon>.
  - `_fetch_ba_detail` liest camelCase-Felder
    (`stellenangebotsBeschreibung`, `verguetungsangabe`, …) als
    Primaerquelle, lowercase bleibt als Fallback.

### Fixed

- **BA-Suche lieferte nur ~20 Treffer mit 16-Zeichen-Beschreibung**:
  Die neue API-Schema-Version hat camelCase-Keys. Beschreibungen sind
  jetzt wieder 1000–2000 Zeichen lang (verifiziert an 100 Live-
  Treffern: „Projektmanager Berlin Umkreis 50 km").

### Known Issues

- Feature-Flag `scraper_adapter_v2` bleibt in Beta.2 ausgeschaltet —
  die Adapter-Schicht ist betriebsbereit, wird aber erst in Beta.4
  von der Pipeline angesprochen.

## [1.6.0-beta.1] - 2026-04-24

Block A: Regression-Protection-Foundation (#498). Rein additiv — keine
bestehenden Flows veraendert. Ziel: Schutznetz fuer die folgenden Betas.

### Added

- **`docs/WORKING_FEATURES.md`** als verbindliche „Was funktioniert?"-
  Liste. Baseline ist v1.5.8. Vor jedem Release wird abgeglichen; was von
  `[x]` auf `[ ]` rutscht, blockt den Release.
- **`scripts/smoke_test.py`** — deckt in <1 Minute die kritischen Flows
  ab (Imports, DB-Init, Profil/Bewerbung/Dokument/Job/Termin CRUD,
  Dashboard-Counts). 12/12 gruen als Voraussetzung fuer jede Beta-Promotion.
- **`src/bewerbungs_assistent/feature_flags.py`** — zentrale Registry
  fuer Feature-Flags mit Env-Var-Override (`PBP_FEATURES=flag1,flag2`).
  Groessere Umbauten ab Beta.2 (Scraper-Adapter v2, Lifecycle-Events)
  laufen nur hinter explizitem Opt-In.
- **CHANGELOG-Format-Konvention** (dieser Header). Pro PR ist ein
  Eintrag Pflicht — keine stillen Aenderungen mehr.

### Changed

- Version-Bump `1.5.8` → `1.6.0-beta.1` in `pyproject.toml` und
  `src/bewerbungs_assistent/__init__.py`.

### Fixed

- **Test-Harness an FastMCP 2.12 angepasst**: Die 28 roten Tests in
  `tests/test_v154_writeback.py` und `tests/test_v157_flow_completion.py`
  liefen gegen die entfernte API `FastMCP.call_tool(name, args)`. Der
  `_call`-Helper nutzt jetzt `await mcp.get_tool(name)` + `tool.run(args)`.
  Reine Test-Anpassung, keine Feature-Aenderung. Full Suite: 440 passed.

### Known Issues

- Stand entspricht v1.5.8, siehe `docs/WORKING_FEATURES.md`.

## [1.5.8] - 2026-04-21

Bug-Fix- und Quick-Win-Release: kleine UX-Verbesserungen und zwei Fixes
aus dem Alltagsbetrieb. Kein neuer grosser Arc, kein Scope-Creep — die
Issues mit klarer Loesung werden weggearbeitet.

### Fixes

- **Kalender-Filter: Kategorien wurden doppelt angezeigt** (#451): Die Query
  in `get_meeting_categories()` hat ueber `OR is_system=1` auch System-
  Kategorien *anderer* Profile zurueckgegeben. Bei mehreren Profilen
  erschienen "Bewerbung", "Interview", "Privat" dadurch mehrfach als
  Filter-Chips im Kalender. Profile-Isolation ist jetzt wiederhergestellt.

- **.eml-Import liess `body_text` leer** (#476): Thunderbird-Exports enthalten
  oft nur `text/html` ohne `text/plain`-Part — `body_text` war dann leer, und
  Downstream-Analysen (Status-Detection, Rejection-Feedback, Textsuche)
  arbeiteten auf leeren Daten. Fix: Plaintext wird per BeautifulSoup aus dem
  HTML abgeleitet, wenn kein Klartext-Part vorhanden ist.

- **Drag-and-Drop-Duplikat-Import** (#476): Wenn der Import-Toast fuer den
  User zu langsam erschien und er die Mail erneut ins Dashboard zog, wurde
  die Mail doppelt importiert. `POST /api/emails/upload` prueft jetzt auf
  identischen Sender+Subject+Sent-Date innerhalb der letzten 5 Minuten und
  antwortet mit `409 Conflict` statt stillem Zweit-Import.

### Neue Features

- **mailto-Antworten-Button in der Bewerbungs-Timeline** (#477): Jede E-Mail
  in der Bewerbungs-Timeline hat jetzt einen Antworten-Icon-Button, der den
  Standard-Mail-Client (Thunderbird, Outlook, Apple Mail, ...) mit
  vorausgefuelltem Empfaenger und `AW:`-Betreff oeffnet. Kein Backend- oder
  API-Aufwand — nutzt das OS-mailto-Protokoll.

- **DOCX als Default fuer Bewerbungs-Exporte** (#473): `lebenslauf_exportieren`
  und `anschreiben_exportieren` exportieren jetzt standardmaessig als DOCX.
  Direkt generierte PDFs wirken haeufig KI-generiert (Schrift, Layout, fehlende
  persoenliche Anpassung) — DOCX zwingt zum Nachbearbeiten im eigenen Template,
  das Ergebnis wirkt persoenlicher. Bei explizitem `format='pdf'` liefert das
  Tool ein `empfehlung`-Feld, das auf den DOCX-Workflow hinweist (non-blocking).

### UX

- #479

## [1.5.7] - 2026-04-17

Journey-Abschluss-Release: die Bewerbungs-Pipeline wird an den drei Stellen vervollständigt,
an denen sie bisher "versandet" ist — Zusage ohne Folgeaktionen, Follow-ups ohne
Abschluss, Ablehnungsmuster ohne Sichtbarkeit. Fünf Issues aus der Produkt-Analyse
vom 17.04.2026 plus das offene #453 zu Follow-up-Lifecycle.

### Neue Features

- **Abschluss-Flow bei `angenommen`** (#455): Bei Statuswechsel auf "angenommen"
  öffnet sich automatisch ein Dialog im Dashboard: Position ins Profil übernehmen,
  tatsächliches Gehalt eintragen, optionale Rollen-Beschreibung. STATUS_ACTIONS
  enthält jetzt auch Einträge für `angenommen` und `zurueckgezogen`, die bisher
  unbenutzt waren. Neue MCP-Tools `position_aus_bewerbung_uebernehmen` und
  erweiterte `bewerbung_bearbeiten` (final_salary, gehaltsvorstellung).

- **Ablehnungsmuster-Karte im Statistik-Tab** (#456): Ab 3 Absagen mit Grund
  erscheint eine Karte "Was Absagen dir sagen" mit den häufigsten Gründen und
  betroffenen Firmen. Button "Vertieft mit Claude besprechen" kopiert den
  Coaching-Prompt. Konsumiert den bereits vorhandenen `GET /api/rejection-patterns`
  Endpoint, der bisher nur via MCP sichtbar war.

- **Tatsächliches Gehalt nach Zusage** (#460): Neues Feld `applications.final_salary`.
  Im Bewerbungs-Dossier unter "Bewerbung bearbeiten" und im Abschluss-Dialog
  pflegbar. Basis für die zukünftige "Meine Abschlüsse vs. Markt"-Auswertung.

- **Auto-Follow-up nach `beworben`** (#462): Beim Statuswechsel auf `beworben`
  (oder Anlage mit Status `beworben`) wird automatisch ein Nachfass-Follow-up
  für T+7 angelegt — konfigurierbar via Setting `followup_default_days`. Kein
  "ich hätte nachfassen sollen"-Moment mehr. Sichtbar als nächster Termin im
  Dashboard.

- **Follow-ups & Termine als erledigt / hinfällig markierbar** (#453): Im
  Dashboard-Meeting-Widget und in der Kalender-Ansicht bekommen Follow-ups
  Buttons "Erledigt" und "Hinfällig", vergangene Termine einen "Durchgeführt"-
  Button. Neue MCP-Tools `follow_up_erledigen`, `follow_up_hinfaellig`,
  `follow_up_verschieben`. Meeting-Status `durchgefuehrt` ist jetzt gültig.
  **Automatisch:** Wird eine Bewerbung auf `abgelehnt`, `zurueckgezogen`,
  `angenommen` oder `abgelaufen` gesetzt, werden offene Follow-ups automatisch
  auf `hinfaellig` gesetzt.

### Neue MCP-Tools (4)

- `follow_up_erledigen` — Nachfass als durchgeführt abhaken (#453)
- `follow_up_hinfaellig` — Nachfass als nicht mehr relevant schliessen (#453)
- `follow_up_verschieben` — geplanten Nachfass auf anderen Termin schieben (#453)
- `position_aus_bewerbung_uebernehmen` — nach Zusage neue Profil-Position anlegen (#455)

### Neue API-Endpunkte

- `POST /api/follow-ups/{id}/complete` — Follow-up abschliessen
- `POST /api/follow-ups/{id}/dismiss` — Follow-up als hinfällig markieren
- `PUT /api/follow-ups/{id}` — Follow-up verschieben / editieren
- `POST /api/applications/{id}/adopt-position` — Position ins Profil übernehmen

### Erweitert

- `bewerbung_bearbeiten` akzeptiert jetzt auch `gehaltsvorstellung` und
  `final_salary` (#460, v1.5.4 hatte cover_letter_path/cv_path ergänzt)
- `PUT /api/applications/{id}` Whitelist um `final_salary`
- Meeting-Status-Werte: `geplant, bestaetigt, durchgefuehrt, abgeschlossen, abgesagt, verschoben`

### Unter der Haube

- Schema v25 → v26: `applications.final_salary TEXT DEFAULT ''`
- `test_mcp_registry` prüft jetzt **89 Tools** (vorher 85)
- 11 neue Regressionstests in `tests/test_v157_flow_completion.py`
- **434 Tests grün** (ohne Scraper-Suite, die bs4 benötigt)

### Geschlossene Issues

- #453 Follow-ups & Termine nicht bearbeitbar / nicht abschliessbar
- #455 Status 'angenommen' ist eine Journey-Sackgasse
- #456 ablehnungs_muster hat Tool und API, aber keinen UI-Platz
- #460 Kein Feld für tatsächlich verhandeltes Gehalt
- #462 Nach 'beworben' wird kein Follow-up automatisch geplant

### Upgrade

Schema-Migration v25→v26 läuft automatisch beim ersten Start. Bestehende Daten
bleiben unverändert. Kein manueller Eingriff nötig.

## [1.5.6] - 2026-04-16

Feature-Release mit 7 geschlossenen Issues: Dashboard-Redesign, Scraper-Health-Monitoring,
Report-Charts, Projekt-Datumsverwaltung und verbesserte URL-Erkennung.

### Neue Features

- **Dashboard-Redesign** (#450): Buggy Schnell-Import entfernt, sauberer Dokument-Import
  unterhalb der Anstehenden Termine neu eingebaut. "Naechster sinnvoller Schritt" und
  "Heute fuer dich" auf volle Breite. GlobalDocumentDropZone ruft nicht mehr
  `analyzeUploadedDocuments()` auf (Race-Condition-Fix).

- **Scraper Health Tracking** (#432): Neues `scraper_health`-Monitoring mit
  automatischer Deaktivierung nach 10 konsekutiven Fehlern. Dashboard zeigt farbige
  Status-Dots pro Scraper. Neues MCP-Tool `scraper_diagnose` fuer Diagnose und
  Reaktivierung. API-Endpoints `/api/scraper-health` und `/api/scraper-health/{name}/toggle`.

- **Report-Charts** (#430): PDF- und Excel-Berichte enthalten jetzt optionale
  matplotlib-Charts (Status-Torte, Bewerbungen/Monat, Quellen-Balken, Score-Verteilung).
  Graceful Fallback wenn matplotlib nicht installiert ist. Excel-Charts ueber openpyxl.

- **Projekt-Zeitraum** (#442): Projekte koennen jetzt `start_date` und `end_date`
  speichern. Anzeige im Profil, in Exporten und im MCP-Tool `projekt_hinzufuegen`.

### Verbesserungen

- **Scraper URL-Erkennung** (#436): `is_search_url`-Flag wird beim Scraping direkt
  in der DB persistiert statt nur zur Laufzeit per Heuristik erkannt. Heuristik bleibt
  als Fallback fuer aeltere Eintraege.

- **Report-Terminologie** (#431): "Aussortierte Stellen" → "Analysierte Stellen (aussortiert)"
  in PDF und Excel Reports.

- **Dokumente-Seite** (#450): Neuer `analysiert_leer`-Badge fuer leere Extraktionen.

### Neue MCP-Tools (1)

- `scraper_diagnose` (#432) — Scraper-Status pruefen und deaktivierte Scraper reaktivieren

### Unter der Haube

- Schema v24 → v25: `projects.start_date`, `projects.end_date`, `jobs.is_search_url`,
  `scraper_health`-Tabelle
- `matplotlib>=3.8` als optionale Dependency (Gruppe `docs`)
- `test_mcp_registry` prueft jetzt **85 Tools** (vorher 84)
- Alle 429 Tests gruen

### Geschlossene Issues

- #430 Report-Charts mit matplotlib
- #431 Report-Terminologie
- #432 Scraper Health Tracking
- #436 Scraper-URLs: is_search_url Flag
- #441 Fehlende Dokumente (bereits in v1.5.3 gefixt)
- #442 Projekt start_date/end_date
- #450 Dashboard Schnell-Import Bug

### Upgrade

Schema-Migration v24→v25 laeuft automatisch. Falls `matplotlib` gewuenscht:
`pip install bewerbungs-assistent[docs]`. Bestehende Daten bleiben unveraendert.

## [1.5.4] - 2026-04-15

Schliesst die letzten Write-Back-Luecken im MCP-Server. Claude kann jetzt alles,
was im Dashboard sichtbar ist, auch selbst pflegen — ohne Umweg ueber direktes SQL.

### Warum dieses Release

Ein Anwender hatte berichtet, dass "nicht alles von Claude zurueckgeschrieben wird".
Pruefung hat bestaetigt: fuer Meetings, Emails, Stellen-Korrekturen und mehrere
Dokument-Operationen gab es zwar die DB-Schicht, aber keine passenden MCP-Tools.
Folge: Claude musste in manchen Situationen auf Desktop-Commander + direktes SQL
ausweichen, was fehleranfaellig und fuer den Anwender nicht nachvollziehbar war.
v1.5.4 schliesst diese Luecken. Die oeffentliche MCP-Schnittstelle waechst von
73 auf **84 Tools**.

### Neue MCP-Tools (11)

**Meetings** (#444) — bisher nur lesbar ueber `bewerbung_details`, jetzt voll pflegbar:
- `meeting_hinzufuegen` — Interview, Telefonat, Kennenlerngespraech etc. anlegen
- `meeting_bearbeiten` — Datum, Typ, Ort, Plattform, Notizen, Status aendern
- `meeting_loeschen` — mit Zwei-Phasen-Bestaetigung
- `meetings_anzeigen` — gefiltert nach Bewerbung oder als Terminvorschau fuer die naechsten N Tage

**Emails** (#445) — Posteingang war nur einlesbar, jetzt komplett zuordenbar:
- `email_verknuepfen` — Email einer Bewerbung zuordnen (oder Verknuepfung loesen)
- `email_loeschen` — mit Zwei-Phasen-Bestaetigung
- `emails_anzeigen` — pro Bewerbung oder Liste aller nicht zugeordneten Emails

**Stellen** (#446):
- `stelle_bearbeiten` — Titel, Firma, Ort, Beschreibung korrigieren wenn der Scraper
  etwas falsch uebernommen hat. Kein Umweg mehr ueber `stelle_manuell_anlegen` +
  Loeschen der alten Stelle.

**Dokumente** (#447):
- `dokument_entverknuepfen` — Dokument von einer Bewerbung loesen (Gegenstueck zu `dokument_verknuepfen`)
- `dokument_loeschen` — mit Zwei-Phasen-Bestaetigung, loescht auch die Datei auf Disk
- `dokument_status_setzen` — Extraktions-Status manuell setzen (`nicht_extrahiert`,
  `gestartet`, `extrahiert`, `angewendet`)

### Erweiterte Tools

- **`bewerbung_bearbeiten`** (#448): akzeptiert jetzt auch `cover_letter_path` und
  `cv_path`. Damit lassen sich die in der Bewerbung hinterlegten Dokumentpfade
  aendern, ohne erneut zu exportieren.

### Prompts

- `bewerbung_vorbereitung` und `interview_vorbereitung` erwaehnen die neuen
  Meeting-Tools und `dokument_entverknuepfen`, damit Claude sie in den
  richtigen Situationen anbietet.

### Unter der Haube

- 19 neue Regressionstests fuer alle neuen Tools (`tests/test_v154_writeback.py`)
- `test_mcp_registry` prueft jetzt **84 Tools** (vorher 73)
- `db.update_application` akzeptiert `cover_letter_path` und `cv_path` in der
  Whitelist (#448)
- Keine Schema-Aenderung, keine Migration — v1.5.3-Datenbanken laufen ohne Anpassung weiter

### Upgrade

Einfach die [neue Version herunterladen](https://github.com/MadGapun/PBP/releases/latest)
und installieren. Bestehende Daten bleiben unveraendert.

## [1.5.3] - 2026-04-15

Stabilisierungs-Release direkt nach dem Launch von v1.5. Keine neuen Features —
nur Bugfixes und bessere Selbstdiagnose, damit der Einstieg reibungslos laeuft.

### Bug Fixes

- **Fehlende Dokumente nach Upgrade automatisch reparieren** (#441)
  Nach dem v1.4.x → v1.5.0 Upgrade konnten in seltenen Faellen physische Dokument-Dateien
  verloren gehen: der DB-Eintrag war da, aber die PDF lag nicht mehr im `dokumente/`-Ordner.
  Folge: `dokument_profil_extrahieren` lieferte leere Daten, Dokumente tauchten im Tab auf,
  liessen sich aber nicht lesen.

  **Was neu ist:** `pbp_diagnose()` prueft jetzt bei jedem Lauf, ob zu jedem Dokument-Eintrag
  die Datei auf Disk existiert. Wenn Dateien fehlen, wird das explizit gemeldet — mit
  Dateiname, Doc-Typ und erwartetem Pfad. Mit `pbp_diagnose(auto_fix=True)` werden Dateien,
  die noch im Standard-`dokumente/`-Ordner liegen, automatisch wieder mit dem DB-Eintrag
  verknuepft. Kein manuelles SQL mehr noetig.

  *Betroffen:* Nutzer, die von v1.4.1 oder v1.4.3 auf v1.5.x upgegradet haben.
  *Empfehlung nach dem Upgrade auf v1.5.3:* einmal `pbp_diagnose(auto_fix=True)` laufen
  lassen.

- **Klare Warnung wenn Stellen-Links auf Suchergebnisse zeigen** (#436)
  Manche Scraper — vor allem fuer LinkedIn, freelance.de und Freelancermap — haben bisher
  gelegentlich die URL der Suchergebnis-Seite gespeichert statt der konkreten Stellenanzeige.
  Folge: Klick auf die URL landete auf einer generischen Suchseite, nicht auf der eigentlichen
  Stelle.

  **Was neu ist:** `stellen_anzeigen()`, `fit_analyse()` und `stelle_manuell_anlegen()` erkennen
  solche Such-URLs jetzt automatisch und liefern ein neues Feld `url_warnung` zurueck. Damit
  ist sofort klar, bei welchen Stellen der Link zu kurz greift und auf dem Portal nachgesucht
  werden muss. Stellen werden weiterhin ganz normal angelegt und bewertet — nur die Warnung
  ist neu.

  *Der eigentliche Fix pro Portal* (Detail-URL im Scraper extrahieren statt Such-URL als
  Fallback) folgt in v1.6.

### Unter der Haube

- 8 neue Regressionstests fuer #441 und #436 (Document-Integrity + URL-Heuristik)
- **410 Tests** passing (vorher 402)
- Keine Schema-Aenderung, keine Migration — v1.5.2-Datenbanken laufen ohne Anpassung weiter

### Upgrade

Einfach die [neue Version herunterladen](https://github.com/MadGapun/PBP/releases/latest) und
installieren. Bestehende Daten bleiben unveraendert. Falls du von v1.4.x kommst und den
Eindruck hast, dass Dokumente fehlen, fuehre einmal `pbp_diagnose(auto_fix=True)` aus.

## [1.5.2] - 2026-04-13

### Neue Features
- **Emoji-Marker in stellen_anzeigen** (#435): Stellen zeigen jetzt einen Typ-Indikator — 🟢 Freelance, 🔵 Festanstellung, ⚪ Sonstige. Neues Feld `typ_label` im JSON-Output.
- **Veroeffentlichungsdatum fuer Stellen** (#434): Neues DB-Feld `veroeffentlicht_am` (Schema v24). Freelancermap-Scraper extrahiert das Datum automatisch. Wird in `stellen_anzeigen` und `fit_analyse` ausgegeben wenn vorhanden.

### Dokumentation
- **FAQ: Browser nicht gefunden** (#433): Troubleshooting-Eintrag fuer das Problem wenn Edge statt Chrome verbunden wird

## [1.5.1] - 2026-04-11

### Bug Fixes
- **Dokumente-Tab crasht bei Klick auf Dokumentname** (#426): `formatDateTime` wurde verwendet aber nicht importiert — Import ergaenzt
- **Bewerbungs-Link in Dokumenten navigiert zu Dashboard** (#427): Click-Event bubbelte zum umgebenden Card-onClick — `stopPropagation` hinzugefuegt
- **FAQ/Troubleshooting verlinkt jetzt auf Wiki** (#424): Wiki-Links in FAQ- und Troubleshooting-Tabs eingefuegt

### Entfernt
- **Snapshot-Funktion aus Bewerbungen** (#428): Stellenbeschreibung-Snapshot war redundant (Stellenbeschreibung ist direkt in der Bewerbung verfuegbar und manuell bearbeitbar) und funktionierte nicht zuverlaessig — komplett entfernt

## [1.5.0] - 2026-04-10

Das groesste Update seit dem ersten Public Release. 24 Beta-Iterationen, 100+ geschlossene Issues, 401 Tests.

### macOS-Unterstuetzung

- **Offiziell unterstuetzt**: macOS funktioniert jetzt gleichwertig mit Windows — inklusive Doppelklick-Installer (`INSTALLIEREN.command`), Dashboard-Starter und Deinstaller
- Plattformunabhaengige Scripts: `_setup_claude.py`, `switch_mode.py`, `start_dashboard.py` auf Windows, macOS und Linux
- Claude Desktop Config-Pfade fuer alle Plattformen automatisch erkannt

### Kalender-System (komplett neu)

- **Grafischer Kalender-Grid**: Monatsansicht mit 7-Spalten-Tagesraster (Mo-So), Wochen-/Quartal-/Halbjahres-Ansicht als kompakte Mini-Grids
- **Termine erstellen, bearbeiten, loeschen**: Vollstaendiges CRUD mit Dauer, Kategorie, Bewerbungs-Verknuepfung und Bestaetigungsdialog
- **Benutzerdefinierte Kategorien**: System-Kategorien (Bewerbung, Interview, Privat) plus frei erstellbare mit Farbe und Statistik-Sichtbarkeit
- **Kalender-Sidebar**: Navigations-Sidebar mit Ansicht, Zeitraum und Filter-Kontrollen (Alle/Kommende/Vergangene)
- **Termin-Navigation**: Klick auf Bewerbungstermin oeffnet Dossier, Klick auf privaten Termin oeffnet Bearbeitungsdialog
- **Private Eintraege**: Werden als "Geblockt" angezeigt und erscheinen nicht in Statistik/Aktivitaetslog
- **Kollisionserkennung** fuer ueberlappende Termine
- **.ics-Export** fuer einzelne Termine und Gesamtexport (RFC-5545)

### E-Mail-Pipeline

- **E-Mail-Import**: `.eml` und `.msg` Dateien hochladen — automatische Zuordnung zur passenden Bewerbung
- **Status-Erkennung**: Eingehende E-Mails erkennen Bewerbungsstatus (Einladung, Absage, etc.) mit Konfidenzwert
- **Termin-Extraktion**: Teams-/Zoom-Links und Datumsangaben werden automatisch als Termine angelegt
- **Kontakt-Uebernahme**: Absender-Daten werden als Ansprechpartner in der Bewerbung gespeichert
- **E-Mails downloadbar** (#422): E-Mails im Bewerbungs-Dossier sind jetzt anklickbare Download-Links mit neuem Endpoint `GET /api/emails/{id}/download`
- **Outlook-Support**: `.msg`-Dateien funktionieren auch in der Windows-Installer-Version (extract-msg + setuptools)

### Dashboard-Redesign

- **Neues Layout**: "Im Fluss" + "Heute fuer dich" links (2/3), Schnellimport rechts (1/3)
- **Anstehende Termine**: Direkt unter "Im Fluss" (max 5, mit Klick-Navigation zum Kalender)
- **Follow-ups ueber Bewerbungen** (#423): Follow-ups und Schnell-Import als 2/3+1/3-Grid ueber der Bewerbungsliste
- **Top-Stellen**: Zeigt alle aktiven Stellen sortiert nach Score (nicht mehr nur Score > 0)
- **Metriken**: Klar getrennte Zaehler fuer Bewerbungen und offene Stellen
- **Aktivitaetslog**: Zeigt neuere Workspace-Aktionen

### Dokumenten-Management

- **Docs-Tab**: Eigener Tab mit Drag & Drop Upload, Bewerbungs-Filter, durchsuchbaren Dropdowns, Textvorschau und Paginierung
- **Dokumente loeschbar**: Im Docs-Tab und per API
- **Bewerbungs-Querverweis**: Firma + Jobtitel pro Dokument sichtbar
- **Analyse-Status**: Dashboard zeigt Fortschritt der Dokumentenanalyse
- **OCR-Fallback**: Gescannte PDFs werden per pytesseract erkannt, `.doc`-Support via antiword

### Statistiken & Analyse

- **Unabhaengige Zeitraum-Kontrollen**: Gruppierung (Taeglich/Woechentlich/Monatlich) und Zeitraum (30d/90d/6m/12m/Alles) als separate Controls
- **Lernender Score**: Ab 5+ gleichen Ablehnungen werden Scoring-Regler automatisch angepasst
- **recherche_speichern()**: Analyse-Ergebnisse dauerhaft an Stellen/Bewerbungen speichern

### Profil & Einstellungen

- **Export & Backup zentralisiert**: Profil-Export (JSON), Datenbank-Backup (SQLite) und Komplett-Export (ZIP) in den Einstellungen unter "Datenschutz" zusammengefasst — nicht mehr auf der Profil-Seite verstreut
- **Profil-Import**: Zuvor exportiertes Profil aus JSON wiederherstellen — ebenfalls in den Einstellungen
- **Gefahrenzone**: "Profil loeschen" in die Einstellungen verschoben mit Profilnamen-Bestaetigung
- **Loeschen-Buttons**: Nur noch im jeweiligen Bearbeitungs-Dialog (verhindert versehentliches Klicken)
- **Datenschutz-Seite**: Datenfluss, Speicherorte, DSGVO-konforme Loeschfunktion

### Sicherheit

- **Profil-Isolation gehaertet**: Alle Endpunkte (Dokumente, Meetings, Bewerbungen, E-Mails, CV-Daten) pruefen das aktive Profil — kein Cross-Profile-Zugriff moeglich
- **Status-Validierung**: `PUT /api/applications/{app_id}/status` liefert 400 statt 500 bei ungueltigem Status
- **WAL-sichere Backups**: `create_backup()` nutzt die SQLite Backup-API statt Dateikopie
- **Automatische Sicherungen**: DB-Backup vor jeder Migration und Schema-Upgrade (max. 5, rotierend)
- **Deinstaller**: Bietet Desktop-Backup an, Datenlöschung erfordert Eingabe von "LOESCHEN"

### Jobsuche & Quellen

- **Regionen**: Suchkriterien werden an Indeed, Monster, Bundesagentur, StepStone und Freelancermap durchgereicht
- **Quellen-Transparenz**: Geschwindigkeits-Badges, Browser-Quellen-Warnungen, Timeout-Tipps
- **Duplikat-Erkennung**: Cross-Source beim manuellen Anlegen von Stellen
- **Blacklist**: Deaktiviert sofort alle aktiven Stellen des Unternehmens
- **Scraper-Updates**: Jobware, Kimeta, Gulp komplett neugeschrieben; Heise-Fallback gefiltert

### Layout & Navigation

- **Globale Sidebar**: Version, MCP-Lebensanzeige und Profil-Navigation in linker Sidebar (kein Topbar-Overlap mehr bei 8 Tabs)
- **Auto-Update-Hinweis**: Dashboard prueft GitHub auf neue Versionen
- **Health-Dashboard**: System-Info in Einstellungen (Python/PBP-Version, Module, DB-Groesse, MCP-Status)
- **FAQ & Hilfe**: 10 FAQ-Eintraege, 5 Troubleshooting-Guides, Akkordeon-Layout
- **First-Run UX**: Klarer Primaerpfad (Kennenlerngespräch), kompakte Alternative-Buttons

### Windows-Installer

- **Versions-Erkennung**: Liest Version dynamisch aus `__init__.py`
- **Python-Reparatur**: Laedt Python erneut bei defekter Installation, korrigiert `_pth`-Konfiguration
- **Registry-Verifizierung**: Eintrag wird nach Loeschung geprueft und bei Bedarf erneut versucht

### Technisch

- Schema-Version: 18 → 23
- 73 Tools, 18 Prompts, 6 Resources
- 401 Tests bestanden
- Release-Gate (`release_check.py`) mit 5 Pruefungen: Versionskonsistenz, Skipped Tests, README-Badge, CHANGELOG-Inhalt, First-Run Smoke

## [1.4.3] - 2026-04-05

### Bug Fixes
- **#301**: `MiddlewareContext` hat kein `params`-Attribut — `context.message.name` statt `context.params.name` fuer Tool-Namen im Heartbeat

## [1.4.2] - 2026-04-05

### Bug Fixes
- **#292**: `_setup_claude.py` erkennt Python-Pfad zuverlaessig — AppData (stabil) bevorzugt, Fallback auf Projektordner, PYTHONPATH immer gesetzt
- **#293**: Port-Konflikt bei mehreren PBP-Instanzen — Dashboard ueberspringt Start wenn Port 8200 belegt
- **#294**: Veraltete "Hammer-Symbol"-Referenzen durch "Einstellungen > Entwickler" ersetzt (4 Stellen)
- **#295**: MCP-Status "Nicht verbunden" bei frischem Start — Heartbeat wird jetzt beim Server-Start geschrieben
- **#296**: Heartbeat wurde nie geschrieben — FastMCP 3.x Middleware statt inkompatiblem Tool-Wrapper
- **#298**: Badge-Farben im Dashboard nicht sichtbar — Tailwind Custom Colors (teal/coral) statt ungueltigem emerald

## [1.4.1] - 2026-04-05

### Bug Fixes
- **MCP-Verbindung**: `_setup_claude.py` erkennt jetzt automatisch den richtigen Python-Pfad (Dev/.venv, Windows Embeddable, Official)
- **Hints**: Statischer "Willkommen"-Hint durch Release-Hinweis ersetzt (wurde bei bestehendem Profil unnoetig angezeigt)

## [1.4.0] - 2026-04-05

### Neue Features
- **#285**: macOS Doppelklick-Installer (`INSTALLIEREN.command`) — kein Terminal noetig
- **#286**: Auto-Update-Hinweis — Dashboard prueft GitHub auf neue Versionen und zeigt dezenten Banner
- **#287**: Datenschutz-Seite — zeigt Datenfluss, Speicherorte, DSGVO-konforme Loeschfunktion
- **#288**: "Zu Claude wechseln"-Button — Toast nach Prompt-Kopie mit Deeplink zu Claude Desktop
- **#289**: Export-Paket "Alles mitnehmen" — ZIP-Download aller Daten (Datenbank + Dokumente)
- **#290**: Health-Dashboard — System-Info in Einstellungen (Python/PBP-Version, Module, DB-Groesse, MCP-Status)
- **#291**: FAQ und Hilfe erweitert — 10 FAQ-Eintraege, 5 Troubleshooting-Guides, Akkordeon-Layout

### Verbesserungen
- **#284**: First-Run UX entschlackt — klarer Primaerpfad (Kennlerngespräch), kompakte Alternative-Buttons
- Einstellungen in Tabs reorganisiert (Quellen, System, Datenschutz, Logs, Gefahrenzone)
- Toast-Komponente unterstuetzt jetzt Action-Buttons
- API-Client: `deleteRequest()` unterstuetzt jetzt Request-Body

## [1.3.2] - 2026-04-05

### Bug Fixes
- **#279**: Onboarding-Crash 'chrome is not defined' bei neuem Profil behoben
- **#280**: Versionsinkonsistenz bereinigt — pyproject.toml, Runtime und Changelog synchron
- **#282**: README-Badge und CHANGELOG auf aktuellen Stand gebracht

### Verbesserungen
- **#281**: Browser-Regressionstests fuer Onboarding-Flow reaktiviert und auf React-Frontend aktualisiert
- **#283**: Release-Gate Script (`release_check.py`) eingefuehrt — prueft Versionskonsistenz, skipped Tests und First-Run-Smoke

## [1.3.0] - 2026-04-04

### Neue Features
- **macOS-Support**: Plattformunabhaengige Installation mit `install.sh`, Dashboard-Starter, Deinstaller (#276, #277, #278)
- **MCP Heartbeat**: Verbindungsindikator im Dashboard-Header zeigt live ob Claude Desktop verbunden ist (#273)
- **Setup-Verifikation**: Onboarding warnt wenn Claude nicht verbunden (#274)
- **Kopier-Warnung**: Hinweis beim Prompt-Kopieren ohne aktive MCP-Verbindung (#275)
- **Slider-Labels**: Scoring-Schieberegler mit "unwichtig / sehr wichtig" Beschriftung (#271)

### Cross-Platform
- `_setup_claude.py`, `switch_mode.py`, `start_dashboard.py` funktionieren auf Windows, macOS und Linux
- Claude Desktop Config-Pfade fuer alle Plattformen
- Chrome/Claude-Detection fuer macOS

## [1.3.1] - 2026-04-04

### Bug Fixes
- **#279**: Onboarding-Crash 'chrome is not defined' — `chrome` aus AppContext geholt

## [1.2.1] - 2026-04-03

### Bug Fixes
- **Installer**: Erkennt wenn ZIP nicht entpackt wurde und zeigt klare Anleitung (#275)
- **Installer**: "Fehler melden"-Hinweis mit GitHub Issues Link bei allen Fehlermeldungen
- **Installer**: Versions-Anzeige korrigiert (war 0.9.0, intern 0.10.0 → jetzt einheitlich 0.11.0)

## [1.2.0] - 2026-04-01

### Bug Fixes
- **#268**: Snapshot-Beschreibungen verwenden jetzt 3-Stufen-Extraktion (JSON-LD → CSS → Regex) statt naivem Regex-HTML-Stripping
- **#265**: Stale-Job-Timeout von 30 auf 15 Minuten reduziert, doppelte gleichzeitige Suchen werden verhindert
- **#238**: Playwright-asyncio-Konflikte geloest — jeder Worker-Thread bekommt eigenen Event-Loop
- **#235/#236/#237**: Jobware, Kimeta und Gulp Scraper komplett neugeschrieben fuer aktuelle Website-Strukturen
- **#234**: Httpx-Scraper laufen jetzt parallel (ThreadPoolExecutor max 4), Playwright sequentiell

### UX-Verbesserungen
- **#258**: Dashboard-Layout auf xl:grid-cols-[2fr_1fr] (2/3 + 1/3) umgestellt
- **#259**: Upload-Box als eigene Card in der rechten Sidebar
- **#264**: "Mehr Quellen aktivieren" Hinweis nur bei <2 aktiven Quellen
- **#241**: Stellenhash und "Bereits beworben" Badge als klickbare Links
- **#262**: Neuer Status "Warte auf Rueckmeldung" mit Amber-Farbton
- **#232**: "Auto-Bewerbung" umbenannt in "Gefuehrte Bewerbung"
- **#210**: Fortschrittsbalken waehrend Jobsuche mit Quellen-Anzeige
- **#215**: Geocoding-Fortschritt bei grossen Batches (>50 Standorte)

### Termin-Management
- **#260/#266**: Termine loeschen mit Delete-Button in Timeline und Dashboard
- **#261/#263**: .ics-Export fuer Termine (RFC-5545 mit PBP-Link)
- **#267**: Kollisionserkennung fuer ueberlappende Termine

### Neue Features
- **#246/#247**: Projekt-Kundennamen als vertraulich markieren — automatische Anonymisierung im CV-Export, Rueckfrage bei Eingabe
- **#240**: recherche_speichern() Tool — Analyse-Ergebnisse dauerhaft an Stellen/Bewerbungen speichern
- **#233**: Dashboard-Hinweise aus oeffentlicher GitHub-Quelle (hints.json) — dezentes Update-System ohne Registrierung
- **#192**: OCR-Fallback fuer gescannte PDFs (pytesseract) und .doc-Support (antiword)
- **#222**: Cross-Source Duplikat-Erkennung beim manuellen Anlegen von Stellen
- **#225**: Kontaktdaten aus eingehenden E-Mails automatisch in Bewerbung uebernehmen
- **#109**: Blacklist-Eintrag deaktiviert sofort alle aktiven Stellen des Unternehmens
- **#110**: Lernender Score — ab 5+ gleichen Ablehnungen werden Scoring-Regler automatisch angepasst
- **#117**: Neuer Prompt "profil_sync" — Leitfaden fuer Profil-Abgleich mit LinkedIn/XING/Freelance.de
- **#195**: Neuer Prompt "tipps_und_tricks" — kategorisierte Tipps fuer AI-gestuetzte Jobsuche

### Technisch
- Schema-Version: 19 → 20 (projects.customer_name, projects.is_confidential, jobs.research_notes)
- 73 Tools (+1), 18 Prompts (+2), 6 Resources
- 362 Tests bestanden

---

## [1.1.0] - 2026-04-01

### Bug Fixes
- **#231**: Beworbene Stellen verschwinden jetzt automatisch aus der aktiven Liste
- **#242**: Schema-Migration v19 — `linked_application_id` von INTEGER auf TEXT korrigiert (FK-Kompatibilitaet)
- **#221**: Polling-Intervall von 2s/5s auf 5s/30s erhoeht, Seite wird nur bei Status-Wechsel neu geladen (kein Flackern mehr)
- **#248 + #252**: Stepstone wird als letztes Portal gestartet mit eigenem Timeout (180s), blockiert andere Portale nicht mehr
- **#230**: Dashboard oeffnet nur noch einen Browser (doppeltes Oeffnen in BAT + Python behoben)
- **#243**: Dokument-Status springt nach KI-Analyse automatisch auf "analysiert" (statt auf basis_analysiert haengen zu bleiben)

### UX-Verbesserungen (Toms/Markus Feedback)
- **Text-Reduktion**: Redundante Info-Boxen im Quellen-Panel entfernt (2 Boxen → 1 kurzer Satz)
- **LinkedIn/XING Warnungen**: Von 4 Absaetzen auf einen Satz gekuerzt
- **Quellen-Hinweis**: Wird nur noch angezeigt wenn keine Quellen gewaehlt sind
- **Jobsuche-Prompt**: Schritt 2 (Quellen) wird uebersprungen wenn bereits konfiguriert
- **#249**: LinkedIn/XING als "Manuell" statt "Aktiv" gekennzeichnet

### Neue Features
- **#223**: Verknuepfte Dokumente in Bewerbung-Details sichtbar
- **#224**: Notizen bei Bewerbungserstellung erscheinen als erster Timeline-Eintrag
- **#245**: Schnell-Sortierung in Bewerbungsliste (3 Buttons: Neueste / Status / Firma A-Z)
- **#251**: Stellenalter wird automatisch auf 2x Suchintervall begrenzt (min. 7 Tage)
- **#253**: LinkedIn/XING-Suche nutzt gepaarte Keywords statt breite OR-Queries

### Technisch
- Schema-Version: 18 → 19
- 352 Tests gruen, 4 geskippt

---

## [1.0.0] - 2026-03-26

### Erster offizieller Public Release

PBP ist jetzt Open Source und oeffentlich auf GitHub verfuegbar.

**Inhalt:** 72 MCP-Tools, 16 Prompts, 6 Resources, 18 Jobquellen, Schema v18,
React 19 Dashboard, E-Mail-Integration, Multi-Profil, Scoring-Regler,
Geocoding, gefuehrter Bewerbungs-Workflow, ATS-konformer CV-Export.

**Repository:** Oeffentlich, Issues aktiviert, Branch Protection auf main,
Community-Dateien (CONTRIBUTING, SECURITY, CODE_OF_CONDUCT) vorhanden.

**Tests:** 362 Tests gruen, 4 geskippt

## [0.33.10] - 2026-03-26

### Release-Hygiene: Public-Release-Vorbereitung

Letzter Pre-1.0-Release. Dokumentation, Badges und Community-Dateien auf den aktuellen Stand
gebracht, um das Repository für die Veröffentlichung vorzubereiten.

**Neue Dateien:**

- `CONTRIBUTING.md` — Beitragsrichtlinien mit Schnellstart, Konventionen, Projektstruktur
- `SECURITY.md` — Sicherheitsrichtlinie mit Meldeverfahren
- `CODE_OF_CONDUCT.md` — Verhaltenskodex (Contributor Covenant 2.1)
- `.github/ISSUE_TEMPLATE/bug_report.yml` — Strukturiertes Bug-Formular
- `.github/ISSUE_TEMPLATE/feature_request.yml` — Strukturiertes Feature-Formular
- `.github/ISSUE_TEMPLATE/config.yml` — Template-Konfiguration (keine Blank Issues)
- `.github/pull_request_template.md` — PR-Checkliste

**Aktualisierte Dateien:**

- `README.md` — Tests-Badge (349→362), Quellenzahl (15→18), Schema (v17→v18), Changelog-Excerpt auf v0.33.x
- `AGENTS.md` — Version, Tools (66→72), Prompts (14→16), Quellen (17→18), Schema (v15→v18), Tests (360→362)
- `docs/RELEASE_v1.0.0_DRAFT.md` — Komplett überarbeitet mit aktuellen Zahlen

**Tests:** 362 Tests grün, 4 geskippt

## [0.33.9] - 2026-03-26

### Fix: Archiv-Zaehlung und Interview-Filter korrigiert

Zwei zusammenhaengende Bugs behoben, die zu falschen Zahlen im Dashboard fuehrten.

**Bug 1 — ARCHIVE_STATUSES Encoding-Mismatch:**

`ARCHIVE_STATUSES` in `database.py` enthielt `zurückgezogen` (Umlaut ue) statt
`zurueckgezogen` (ASCII). Da die Datenbank konsequent ASCII-Status verwendet,
wurden zurueckgezogene Bewerbungen weder beim Archiv-Zaehlen noch beim Filtern
erkannt. Dashboard zeigte 32 statt 34 archivierte Bewerbungen.

- `database.py`: ARCHIVE_STATUSES und Job-Hash-Filter auf ASCII korrigiert
- `job_scraper/__init__.py`: Applied-Titles-Filter auf ASCII korrigiert
- `export_report.py`: Umlaut-Duplikat-Keys in STATUS_LABELS/STATUS_COLORS entfernt

**Bug 2 — Interview-Filter zeigt nur einen Status:**

Klick auf "Interview filtern" im Dashboard setzte `status: "interview"`, aber
der Filter matchte nur exakt diesen Wert. Bewerbungen mit `zweitgespraech` oder
`interview_abgeschlossen` fehlten, obwohl die Zaehlung sie einschloss.

- `INTERVIEW_STATUSES`-Konstante eingefuehrt (`interview`, `zweitgespraech`,
  `interview_abgeschlossen`)
- `statusMatch`-Filter erweitert: `status === "interview"` matcht jetzt die
  gesamte Interview-Gruppe
- `interviewApplicationsCount` nutzt die neue Konstante

**Entfernt:**

- "Claude oeffnen"-Button und zugehoerige Endpoints (`/api/claude-open`,
  `/api/claude-status`) — Windows-only, auf Linux-Server nie funktionsfaehig

**Tests:** 362 Tests gruen, 4 geskippt

## [0.32.6] - 2026-03-24

### Fix: Outlook-Mail-Import (.msg) funktioniert jetzt im Installer

**Ursache:** Embeddable Python 3.12 bringt weder `setuptools` noch `wheel` mit.
Beim Installieren von `extract-msg` muss dessen Abhaengigkeit `red-black-tree-mod`
aus dem Source gebaut werden — das scheiterte mit `BackendUnavailable: Cannot import
'setuptools.build_meta'`. Der Installer uebersprang den gesamten E-Mail-Import still.

**Fix (Installer v0.10.0):**
- `setuptools` und `wheel` werden jetzt explizit vor `extract-msg` installiert
- Bei Fehlern bekommt der Nutzer eine klare, mehrzeilige Erklaerung:
  was fehlt, was das bedeutet, und wie der Workaround funktioniert
  (.eml / PDF statt .msg)
- Fehlerbehandlung mit separatem Label statt stiller Zeile

**Fix (Dashboard):**
- Fehlermeldung beim .msg-Upload ist jetzt konkreter und zeigt den Workaround
  (Outlook > Speichern unter > .eml oder PDF) direkt an
- `parse_msg()` Fehlermeldung vereinheitlicht

**Enhancement (Dokumenten-Upload → volle E-Mail-Intelligenz):**
- Dokument-Upload von `.eml`/`.msg` wendet jetzt die gleiche Logik wie der
  dedizierte E-Mail-Endpoint an: Meetings werden erkannt und gespeichert,
  Timeline-Events werden auf der zugeordneten Bewerbung erstellt
- Vorher: nur Textextraktion und Auto-Linking; Meetings und Status-Erkennung
  gingen beim Upload ueber `Profil > Dokumente` verloren
- Neue API-Response enthaelt jetzt `meetings`-Array mit erkannten Terminen

**Tests:** 2 neue Tests (Timeline-Event bei Mail-Upload, Meeting-Extraktion),
362 Tests gruen, 4 geskippt

**Verifikation:** Installer-Logik manuell geprueft. `.msg`-Upload-Fehlerfall
getestet via Unit-Tests. Auf echtem Windows mit embeddable Python verifizierbar
durch Ausfuehren von `INSTALLIEREN.bat`.

## [0.32.5] - 2026-03-24

### Stellen-Dialog und Outlook-Installer vervollstaendigt

Dieser Patch schliesst zwei reale Restprobleme, die im integrierten Testbetrieb direkt
aufgefallen sind: Der Detaildialog in der Stellenliste liess sich trotz klickbarem Titel
nicht oeffnen, und der Windows-Installer installierte die Outlook-Abhaengigkeit fuer
`.msg`-Dateien nicht mit.

**Stellen / Frontend:**

- Klick auf den Stellentitel oeffnet die Stellendetails wieder sauber
- Bearbeiten der Stelle aus dem Detaildialog funktioniert wieder, inklusive Nachpflege
  fehlender Beschreibungen
- der Klickbereich ist jetzt auch per Tastatur sauber bedienbar
- neuer Browser-Regressionstest sichert den kompletten Flow:
  Titel klicken -> Details sehen -> Bearbeiten -> Beschreibung speichern

**Installer / Outlook-Mail-Import:**

- `INSTALLIEREN.bat` installiert jetzt auch `extract-msg` und `icalendar`
- Outlook-`.msg`-Dateien funktionieren damit nicht nur im Dev-Setup, sondern auch
  in der ausgelieferten Windows-Installation
- wenn der Parser trotzdem fehlt, gibt PBP jetzt einen klaren Nutzerhinweis:
  PBP aktualisieren oder die Mail in Outlook als PDF / `.eml` speichern und erneut hochladen

**Verifikation:** 360 Tests gruen, 4 Tests bewusst geskippt, Web-Build gruen
(`python -m pytest tests -q`, `python -m pytest tests/test_dashboard_browser.py -k "jobs_page" -q`,
`pnpm run build:web`)

## [0.32.4] - 2026-03-24

### Mail-Dokumente im Profil-Flow vollstaendig stabilisiert

Dieser Patch schliesst den offenen Rest aus `#191` sauber ab. Mail-Dateien im Profil-
Dokumentbereich verhalten sich jetzt nicht mehr wie Sonderfaelle mit stillen Luecken,
sondern wie ein sauber gefuehrter Teil des normalen Dokument-Workflows.

**Dokument-Upload / Ordner-Import:**

- `.msg` und `.eml` werden jetzt auch im normalen Profil-Dokumentupload und beim
  Ordner-Import extrahiert und nicht mehr als leere Dateien abgelegt
- der Ordner-Import erkennt Mail-Dateien ebenfalls und liefert bei Problemen klare
  Warnungen statt stiller Fehlimporte
- wenn `extract-msg` fuer Outlook-Dateien fehlt, gibt PBP jetzt eine explizite
  Nutzerfehlermeldung aus

**Workflow / Status:**

- Mail-Dokumente mit lesbarem Inhalt landen als `basis_analysiert` statt `analysiert_leer`
- Dokumente mit Text, aber ohne direkt erkannte Profilfelder, bleiben ebenfalls als
  `basis_analysiert` sichtbar und werden nicht mehr faelschlich als `Ohne Inhalt`
  behandelt
- bestehende E-Mail-Helfer werden beim Dokument-Upload mitgenutzt:
  Richtungs-Erkennung, Bewerbungs-Match und Status-Hinweise

**Frontend / UX:**

- Profilseite und Onboarding akzeptieren Mail-Dateien jetzt explizit auch in den
  Dateidialogen
- der Ordner-Import zeigt Warnungen sichtbar in der UI an, statt nur "fertig" zu melden
- statischer Frontend-Build fuer den neuen Stand aktualisiert

**Tests / Verifikation:** 359 Tests gruen, 4 Tests bewusst geskippt, Browser-Smokes gruen,
Web-Build gruen (`python -m pytest tests -q`, `python -m pytest tests/test_dashboard_browser.py -q`,
`pnpm run build:web`)

## [0.32.3] - 2026-03-23

### Finishing-Sprint: Release-Hygiene und Export-Stabilität

Dieser Patch macht aus `v0.32.2` einen runderen veröffentlichbaren Stand. Es gibt keine neuen
Kernfunktionen, sondern gezielte Qualitätsarbeit an den sichtbaren Einstiegspunkten und am
Report-Export.

**Öffentliche Texte / Doku:**

- Help-/Support-Texte im React-Frontend sprachlich konsolidiert
- `docs/FAQ.md` in sauberes, öffentlich lesbares Deutsch überführt
- sichtbare README-/Release-Texte für den aktuellen Stand nachgezogen
- Versionsangaben in Paket, Dashboard und Metadateien auf `0.32.3` angeglichen

**Technisch:**

- `export_report.py` auf die aktuelle `fpdf2`-API umgestellt
- veraltete `ln=True`-Aufrufe durch stabile Zeilenumbrüche via `new_x`/`new_y` ersetzt
- PDF-Report-Export damit wieder ohne die bisherigen Deprecation-Warnings vorbereitet

**Verifikation:** 349 Tests grün, 4 Tests bewusst geskippt, Web-Build grün
(`python -m pytest tests -q`, `pnpm run build:web`)

## [0.32.2] - 2026-03-23

### Guidance- und Stabilitaets-Sprint

Dieser Patch zieht die Stabilisierung von `v0.32.1` bis in die sichtbaren Nutzerfluesse durch.
Der Fokus liegt nicht auf neuen Kernfeatures, sondern auf klarerer Fuehrung, transparenteren
Zustaenden und einer runderen Release-Basis.

**Frontend / UX:**

- **Bewerbungen:** sichtbarer Toggle `Archivierte anzeigen`, damit abgelehnte, zurueckgezogene
  und abgelaufene Bewerbungen nicht nur technisch, sondern auch in der React-UI kontrollierbar sind
- **Bewerbungen:** neue Karte `Naechster sinnvoller Schritt` mit klarer Priorisierung
  fuer Follow-ups, Entwuerfe, Interview-Phase und Archiv-Sicht
- **Stellen:** neue Guidance-Karte mit konkreter Einordnung statt nur Trefferliste
- **Stellen:** sichtbare Warnung `Score unsicher`, wenn eine Stellenbeschreibung fehlt
  oder zu kurz ist
- **Stellen:** neuer Fokus-Filter `Nur ohne Beschreibung`, um unzuverlaessige Treffer
  gezielt nachzuarbeiten
- **Dashboard:** Workspace-Readiness jetzt sichtbar als echte `Naechster sinnvoller Schritt`-Karte
  inklusive direkter Aktionen aus den vorhandenen Workspace-Signalen

**Technisch:**

- Versionsdrift zwischen `pyproject.toml` und `src/bewerbungs_assistent/__init__.py` bereinigt
- Browser-Smoke-Tests fuer Archiv-Toggle, Workspace-Readiness und Score-Warnungen ausgebaut
- statischer Frontend-Build aktualisiert

**Verifikation:** 349 Tests gruen, 4 Tests bewusst geskippt, Web-Build gruen
(`python -m pytest tests -q`, `pnpm run build:web`)

## [0.32.7] - 2026-03-24

### Bugfixes (#197-#201)

5 Bugs aus dem Produktivbetrieb behoben.

- **#197:** Statistiken-Seite 500-Fehler behoben — `/api/stats/timeline` scheiterte an
  gemischten Datumsformaten (ISO mit/ohne Timezone) und leeren `applied_at`-Werten
  (z.B. bei `in_vorbereitung`-Bewerbungen). Datumsnormalisierung und leere Werte werden
  jetzt korrekt behandelt.

- **#198:** Interview-Rate zaehlt `in_vorbereitung` nicht mehr in der Gesamtbasis mit.
  Berechnung basiert jetzt nur auf tatsaechlich eingereichten Bewerbungen
  (in database.py, tools/bewerbungen.py und export_report.py).

- **#199:** Dashboard-Kachel zeigt jetzt die Gesamtzahl aller Bewerbungen (aus Statistics)
  statt nur die nicht-archivierten. Note klargestellt: "X gesamt / Y aktive Stellen".

- **#200:** Jobsuche bricht nicht mehr komplett nach 10 Minuten ab. Jede Quelle hat jetzt
  ein eigenes 90-Sekunden-Timeout. Bei Timeout wird die Quelle uebersprungen und die
  bereits gesammelten Ergebnisse bleiben erhalten. Abschlussmeldung zeigt erfolgreiche
  und uebersprungene Quellen.

- **#201:** Stellentyp-Erkennung erweitert — Freelance/Interim werden jetzt automatisch
  erkannt: Quellen-basiert (freelance_de, freelancermap, gulp, solcom), Titel-basiert
  ("Interim", "Freelance"), und <FIRMA> mit Stundensatz. Keywords erweitert um "interim",
  "interims", "interimsmanag".

**Technisch:** 341 Tests (alle gruen, 4 uebersprungen), keine neuen Tools/Prompts,
keine Schema-Aenderung.

## [0.32.1] - 2026-03-22

### Bugfixes + Diagnose (#178-#184, #154, #168, #176)

Alle Bugs aus den Endtests behoben, Pipeline-Simulation verifiziert.

**Bugfixes:**

- **#178:** source aus Jobs-Tabelle in Bewerbungen uebernehmen, Score-Verteilung zeigt alle Jobs,
  +5 Beworben-Bonus im Scoring-Service
- **#179:** Grammatikfehler "darfst du erinnern" + Umlaut "fuer" im Frontend
- **#180:** Scoring warnt bei fehlender Beschreibung (Mindest-Score statt 0), Dashboard-Todo
- **#181:** bewerbung_bearbeiten erweitert um employment_type, source, vermittler, endkunde
- **#182:** Zurueckgezogene Bewerbungen standardmaessig ausblenden, Stellenart-Filter, Sortierung
- **#183:** Fuzzy-Keyword-Matching — Synonyme (PLM→Teamcenter), Umlaute (Beispielfirma→Beispielfirma),
  Multi-Word-Split ("PLM Projektleiter" matcht "Projektleiter im PLM-Umfeld")
- **#184:** keyword_vorschlaege Tool — analysiert tote Keywords und schlaegt Aenderungen vor
- **#154:** "Bereits beworben"-Badge in Frontend-Stellenkarten
- **#168:** Blacklist-Validierung auf DB-Ebene + Substring-Match fuer Firmennamen
- **#176:** Timeline-Eintrag bei Upload verifiziert (war bereits implementiert)

**Neue Tools:**

- `pbp_diagnose(auto_fix)` — Gesundheitscheck: Profil, Kriterien, Stellen, Bewerbungen,
  Blacklist. Findet Probleme und gibt Handlungsempfehlungen. Mit auto_fix=True werden
  einfache Probleme automatisch behoben (z.B. fehlende source nachgetragen).
- `keyword_vorschlaege()` — Analysiert haeufige Begriffe in gut vs. schlecht bewerteten
  Stellen und findet Keywords die in keiner Stelle vorkommen ("tote Keywords").

**Technisch:** 72 Tools (+2), 341 Tests, Basis-Schema um vermittler/endkunde/description_snapshot ergaenzt,
Blacklist-Firmenfilter mit Substring-Match.

## [0.32.0] - 2026-03-22

### 11 Issues (#167-#177) — Erweiterter Bewerbungsbegleiter

PBP wird zum erweiterten Begleiter: Gefuehrter Workflow, Scoring-Regler, Geocoding,
ATS-konformer CV, aufgewerteter Bericht und Drag & Drop fuer Dokumente.

**Kern-Features:**

- **#170 Gefuehrter Bewerbungs-Workflow:** Neuer Status `in_vorbereitung` mit kontextabhaengigen
  Aktionen pro Status. Jeder Schritt zeigt genau die 3-4 relevanten Aktionen — mit Motivation.
  Einstiegsfrage "Bereits beworben oder will mich bewerben?". Vorbereitungs-Checkliste.
  Neuer orchestrierender Prompt `bewerbung_vorbereitung` mit 7-Schritte Checkliste.
  Fortschritts-Tracking in der Bewerbungsliste.

- **#169 Scoring-Regler-System:** Neue `scoring_config` Tabelle mit 6 Dimensionen
  (Stellentyp, Remote, Entfernung getrennt nach Stellenart, Gehalt, Muss-Kriterien,
  Ausschluss-Keywords). 19 Default-Eintraege. "Komplett Ignorieren"-Flag pro Einzelwert.
  Auto-Ignore-Schwellenwert. Integriert in `stellen_anzeigen`. 2 neue Tools:
  `scoring_konfigurieren` und `scoring_vorschau`.

- **#167 Geocoding/Entfernungsberechnung:** `geopy` als Dependency. Nominatim (OpenStreetMap)
  mit 1 Req/s Rate-Limiting und In-Memory-Cache. Bewerber-Standort in Suchkriterien cachen.
  Automatische Distanzberechnung in der Scraper-Pipeline und bei `stelle_manuell_anlegen`.
  `lat`/`lon` Spalten auf `jobs` Tabelle.

- **#168 Blacklist bereinigt:** `dismiss_pattern`-Typ komplett aus der Blacklist entfernt.
  Nur noch `firma` und `keyword` als Typen erlaubt. Migration konvertiert kurze
  dismiss_patterns zu keywords, loescht lange Freitext-Eintraege. Typ-Validierung und
  Laengen-Warnung bei neuen Eintraegen. `stelle_bewerten` schreibt nicht mehr in Blacklist.
  Duplikat-Erkennung als separater Mechanismus (Titel-Aehnlichkeit + Firmen-Match).

**Export & Bericht:**

- **#174 ATS-konformer CV-Stil:** Komplett ueberarbeitetes CV-Template. Calibri Font,
  KEINE Tabellen, H1/H3-Heading-Hierarchie, Kernkompetenzen als `Kategorie: Werte` Bullets,
  grosser Name-Header auf Seite 1, Pfeil-Symbole fuer Ergebnis-Zeilen, Seitenzahlen im Footer.
  Farbig: nur #1F4E79 fuer Ueberschriften.

- **#173 Aufgewerteter Bewerbungsbericht:** Executive Summary mit Pipeline-Uebersicht.
  Inhaltsverzeichnis. PBP-Branding (Header/Footer mit Name, Link, Beschreibung).
  Zeitraumfilter fuer `statistiken_abrufen` und `bewerbungsbericht_exportieren`.
  Quellenanalyse mit Erfolgsquote pro Quelle. +5 Score-Bonus fuer beworbene Stellen.
  Erweiterte Bewerbungsliste mit 8 Spalten und Farb-Badges. Importierte Bewerbungen
  als "importiert (pre-PBP)" gekennzeichnet.

**Frontend & Dokumente:**

- **#176 Drag & Drop Upload:** Upload-Zone direkt in der Bewerbungs-Timeline.
  Dateien per Drag & Drop oder Klick hochladen — automatisch mit Bewerbung verknuepft.
  "Vorhandenes Dokument verknuepfen" als aufklappbare Auswahl.

- **#177 Auto-Dokumentzuordnung:** `auto_assign_document` in `add_document` integriert.
  Firmenname-Matching mit Teilwoertern und Umlaut-Normalisierung (Beispielfirma = Beispielfirma).
  Zeitliche Naehe (24h) als zusaetzliches Kriterium. Automatische Verknuepfung bei
  Konfidenz >= 70%, Hinweis bei niedrigerer Konfidenz. Timeline-Eintrag bei jeder
  Dokument-Verknuepfung.

- **#171 IDs ueberall:** Kurz-Hashes (8 Zeichen) in `bewerbungen_anzeigen`,
  `bewerbung_details`, `stellen_anzeigen`. Klickbare IDs mit Clipboard-Kopie im Frontend
  (ApplicationsPage Karten + Timeline-Header, JobsPage bereits vorhanden).

**Sonstiges:**

- **#172 Auto-Save Stellenbeschreibung:** Bei `lebenslauf_angepasst_exportieren` und
  `anschreiben_exportieren` wird die Stellenbeschreibung automatisch in der DB gespeichert.
  `bewerbung_erstellen` akzeptiert optionale `stellenbeschreibung`.

- **#175 FAQ / Erste-Schritte-Guide:** `docs/FAQ.md` mit Token-Limit-Warnung,
  Workflow-Uebersicht, Entscheidungsbaum ("Was soll ich tun?"), Troubleshooting.
  Interaktiver `faq` Prompt der den aktuellen Stand zeigt und den naechsten Schritt empfiehlt.

**Schema v17 Migration:**
- Neue Tabelle: `scoring_config` (konfigurierbare Scoring-Regler)
- Neue Spalten: `jobs.lat`, `jobs.lon` (Geocoding)
- Neue Spalten: `applications.source`, `applications.source_secondary` (Quellenfeld)
- Blacklist: dismiss_pattern-Eintraege migriert/bereinigt

**Technisch:**
- 70 MCP-Tools (+3: `scoring_konfigurieren`, `scoring_vorschau`, `bewerbungsbericht_exportieren`)
- 16 MCP-Prompts (+2: `bewerbung_vorbereitung`, `faq`)
- 2 neue Services: `geocoding_service.py`, `scoring_service.py`
- Schema v17, 341 Tests (alle gruen)
- Frontend: `in_vorbereitung`, `eingangsbestaetigung`, `angenommen` Status + Farben

---

## [0.31.1] - 2026-03-22

### Tagesimpulse V1 — vollstaendige Integration (#163)

- 140 kuratierte Originaltexte (statt 30 inline) in `content/tagesimpulse.json`
- Neuer `daily_impulse_service.py` mit 8 Kontexten und Prioritaetslogik
- Kontextabhaengige Filterung: weekend > follow_up_due > jobs_ready > search_refresh > sources_missing > profile_building > onboarding > default
- Tagesstabile Auswahl via SHA-256 Hash (Seed: Datum + Kontext)
- Dashboard-Karte mit Titel "Heute fuer dich" und strukturierter API-Antwort
- 19 neue Tests (Service-Unit, API-Integration, Browser-Smoke)
- Vorarbeit: Codex Seed-Sammlung + Implementierungsplan (PR #164)
- 67 Tools, 14 Prompts, Schema v16, 336 Tests

---

## [0.31.0] - 2026-03-22

### 13 Issues — Stabilisierung, Freelance, LinkedIn-Umbau, Tagesimpulse

**Bugs & Stabilisierung:**
- **#155** Stale-Job-Erkennung: Background-Jobs > 30 Min werden automatisch bereinigt, Startup-Cleanup fuer haengende Jobs
- **#162** MetricCard zeigt jetzt Server-Stellenzahl statt gefilterte Anzahl

**Freelance & Stellentyp (#151):**
- Automatische Freelance-Erkennung ueber Keywords in Titel/Beschreibung
- Stellenart (Festanstellung/Freelance/Praktikum/Werkstudent) manuell editierbar in Bewerbungen
- Schema v16: `employment_type` Spalte in `applications`
- Stellenart-Filter in Bewerbungsuebersicht

**Post-Search Cleanup (#153, #154):**
- Automatische Bereinigung nach Jobsuche: DB-Duplikate, Blacklist, bereits bewertete Stellen werden gefiltert
- Fuzzy-Matching gegen bestehende Bewerbungen (Token-Overlap > 70%)
- Bereinigungs-Statistik in Jobsuche-Ergebnis ("89 gefunden, 12 bekannt, 5 bewertet, 3 Blacklist")

**LinkedIn/XING Umbau (#159, #160, #161):**
- Playwright-basiertes LinkedIn/XING-Scraping deaktiviert (blockiert zuverlaessig)
- Neues MCP-Tool `stelle_manuell_anlegen()` — Bruecke von Claude-in-Chrome zurueck ins PBP
- README aktualisiert: Chrome + Claude-in-Chrome als Voraussetzung dokumentiert

**UX-Verbesserungen:**
- **#156** Stellen-Hash mit Click-to-Copy in Job-Karten und Detail-Dialog
- **#157** Fit-Analyse: "Detailbewertung anfordern" Button kopiert Analyse-Prompt
- **#158** Ablehnungsgruende werden auf Standard-Keywords normalisiert
- **#152** Token-Verbrauch-Hinweis in README (Free-Plan vs. Pro)

**Dashboard (#163):**
- Tagesimpuls-Basis (30 Texte) — vollstaendige V1 mit 140 Texten in v0.31.1
- Kontext-Erkennung (Onboarding, Wochenende, Stellen vorhanden, etc.)
- Ein/Aus-Toggle in Einstellungen

**Technisch:**
- 67 Tools, 14 Prompts, Schema v16, 317 Tests
- Post-Search Cleanup Pipeline mit Fuzzy-Matching

---

## [1.0.0] - 2026-03-22

### Erster öffentlicher Release 🎉

PBP erreicht v1.0.0 — nicht weil alles perfekt ist, sondern weil es zuverlässig funktioniert.

**Was in 1.0.0 steckt** (kumuliert seit v0.1.0):

- **67 MCP-Tools** in 8 Modulen — Profil, Dokumente, Jobs, Bewerbungen, Analyse, Export, Suche, Workflows
- **14 MCP-Prompts** — von Ersterfassung bis Interview-Simulation
- **17 Jobquellen** — Bundesagentur, StepStone, LinkedIn, Indeed, Monster, <FIRMA> und 11 weitere
- **E-Mail-Integration** — .eml/.msg Import, automatisches Matching, Meeting-Extraktion
- **React 19 Dashboard** — 7 Bereiche, Drag & Drop, Live-Updates, Statistik-Charts
- **PDF/DOCX-Export** — Lebenslauf und Anschreiben in professionellem Layout
- **Multi-Profil** — Mehrere Profile mit vollständiger Daten-Isolation
- **Schema v16** — 21 Tabellen, Migrationskette v1→v16, voll abwärtskompatibel
- **317 Tests** — alle grün
- **Zero-Knowledge Installer** — `INSTALLIEREN.bat` für Windows

**Release-Vorbereitung:**
- Versions-Metadaten synchronisiert (pyproject.toml, \_\_init\_\_.py, Credits-Dialog)
- Sekundär-Dokumentation auf v0.30.0 Stand gebracht (ZUSTAND.md, architecture.md, codex_context.md)
- DOKUMENTATION.md aktualisiert (Port, Quellen, Tools, Schema)
- Security-Audit bestanden (keine API-Keys, Passwörter oder private Daten im Repo)

> **Hinweis zur Versionshistorie:** Es existierte ein früherer Release `v1.0.0` vom 2. März 2026,
> der als "Erster Release" auf den zweiten Commit des Repos zeigte (21 Tools, 65 Tests).
> Dieser wurde vor dem offiziellen 1.0.0-Release entfernt, da er nicht dem tatsächlichen
> Reifegrad eines 1.0-Produkts entsprach. Die lückenlose Entwicklungshistorie ist über
> die v0.x-Tags (v0.1.0 bis v0.30.0) und das CHANGELOG vollständig nachvollziehbar.

---

## [0.30.2] - 2026-03-21

### UX: Prompt-Kopie & Paste-Hinweis

- **Jobsuche starten:** Button kopiert jetzt `/jobsuche_workflow` in die Zwischenablage (vorher nur Info-Toast)
- **Paste-Hinweis:** Alle Clipboard-Toasts zeigen jetzt "Prompt kopiert — füge ihn mit Strg+V in Claude ein." und bleiben 7 Sekunden sichtbar (vorher 4s, ohne Hinweis)

---

## [0.30.1] - 2026-03-21

### Hotfix: Versionserkennung & Installer

- **Version-Fix:** `__init__.py` und `pyproject.toml` zeigen jetzt die korrekte Version (v0.28.0–v0.30.0 hatten intern fälschlich `0.27.0` stehen)
- **Installer v0.9.0:** pip-Upgrade-Schritt übersprungen wenn pip bereits vorhanden (verhindert Hänger bei Update-Installation)
- **~300 Umlaut-Korrekturen:** Alle Python-Module verwenden jetzt korrekte deutsche Umlaute in User-Strings
- **Versionshistorie:** Alter historischer `v1.0.0`-Tag → `v0.0.0` umbenannt

---

## [0.30.0] - 2026-03-20

### UX-Verbesserungen & Qualität (Issues #139–#147, Koala280)

**Frontend-Fixes:**
- **#147** Scrollbar-Gutter: `scrollbar-gutter: stable` verhindert Layout-Verschiebung bei Seitenwechsel
- **#139** Status-Charts: Deutsche Anzeigenamen statt interne Keys in Statistik-Legenden
- **#141** Datumsnormalisierung: Profil-Editor konvertiert diverse Datumsformate (`02/2016`, `DD.MM.YYYY`) korrekt für `<input type="month">`
- **#142** (zusammengelegt mit #141)
- **#143** Token-Sync: Nach Dokumenttyp-Änderung kein erzwungener Seiten-Reload mehr (quiet refresh)
- **#146** Stellenanzeigen-Link: ExternalLink-Button in der Bewerbungsdetailansicht
- **#140** Interview-Termine: Interview-Follow-ups erscheinen als Pseudo-Meetings im Dashboard-Widget
- **#145** Lazy Loading: Paginierte Stellenliste mit wählbarer Seitengröße (20/50/100/Alle) + "Mehr laden"-Button
- **#144** (Duplikat von #145, geschlossen)

**Backend:**
- Server-seitige Pagination für `/api/jobs` mit `limit`/`offset` (abwärtskompatibel)
- ~300 Umlaut-Korrekturen: ASCII-Ersetzungen (ae→ä, oe→ö, ue→ü, ss→ß) in allen Python-Modulen
- MCP-Tool-Funktionsnamen bleiben ASCII-kompatibel (MCP-Standard)

**Neue Utility-Funktionen:**
- `statusLabel()` — Status-Key → deutscher Anzeigename
- `normalizeMonthDate()` — Multi-Format-Datum → `YYYY-MM`

## [0.29.0] - 2026-03-20

### Major: E-Mail-Integration — Parsing, Matching, Meetings (#136)

**E-Mail-Import & Parsing:**
- Neuer Service `email_service.py` (~480 Zeilen) fuer .eml (Python stdlib) und .msg (extract-msg) Dateien
- Automatische Richtungserkennung (eingehend/ausgehend) anhand Absender-Domain
- Absender-E-Mail und Domain werden extrahiert und fuer Matching verwendet
- Drag & Drop: .msg/.eml Dateien ins Dashboard ziehen — automatische Erkennung und Routing

**Automatische Zuordnung (6 Strategien):**
- Kontakt-E-Mail exakt → Konfidenz 0.95
- Domain-Match → 0.70
- Firmenname in Absender/Betreff → 0.60
- Jobtitel in Betreff → 0.50
- Ansprechpartner in Absender → 0.80
- URL-Domain-Match → 0.65
- Minimum-Schwelle: 0.30 — darunter bleibt die E-Mail unzugeordnet

**Status-Erkennung:**
- Muster-basierte Erkennung fuer Deutsch + Englisch
- 4 Kategorien: Eingangsbestaetigung, Interview-Einladung, Absage, Angebot
- Umlaut-Normalisierung (ae→ä, ue→ü, oe→ö, ss→ß) fuer robustes Matching

**Meeting-Extraktion:**
- Datum/Uhrzeit aus E-Mail-Body (2 deutsche Datumsformate)
- .ics-Anhang-Parsing via `icalendar` Library
- Meeting-Link-Erkennung: Teams, Zoom, Google Meet, WebEx
- Plattform wird automatisch aus URL erkannt

**Dashboard Meeting-Widget:**
- Anstehende Termine mit Countdown ("in X Tagen", "morgen", "jetzt gleich")
- Plattform-Badge (Teams/Zoom/Meet/WebEx)
- Direkter "Beitreten"-Button mit Meeting-URL
- Manuelle Termin-Erstellung in der Bewerbungs-Detailansicht

**Attachment-Import & Duplikat-Erkennung:**
- E-Mail-Anhaenge (PDF, DOCX) werden automatisch als Dokumente importiert
- SHA256-Content-Hashing auf `documents`-Tabelle
- Duplikate werden erkannt und uebersprungen (mit Info-Badge im UI)

**Absage-Feedback:**
- Konkretes Feedback aus Absage-Mails wird extrahiert
- Automatisch als Notiz in der Bewerbungs-Timeline gespeichert

**17 neue API-Endpoints:**
- `POST /api/emails/upload` — Komplette Pipeline (Parse → Match → Status → Meetings → Attachments)
- `POST /api/emails/{id}/confirm-match` — Zuordnung bestaetigen/aendern
- `POST /api/emails/{id}/apply-status` — Erkannten Status uebernehmen
- `GET/DELETE /api/emails`, `GET /api/emails/{id}`
- `GET /api/applications/{id}/emails`, `GET /api/applications/{id}/meetings`
- `GET/POST/PUT/DELETE /api/meetings`

**Schema-Migration v14→v15:**
- Neue Tabelle `application_emails` (subject, sender, body, direction, matched, status, confidence, ...)
- Neue Tabelle `application_meetings` (title, meeting_date, meeting_url, platform, ...)
- `content_hash TEXT` Spalte auf `documents` fuer Duplikat-Erkennung

**Frontend-Erweiterungen:**
- DashboardPage: Meeting-Widget + E-Mail-Liste + E-Mail-Detail-Modal + Upload-Button
- ApplicationsPage: Meetings/E-Mails in Timeline + MeetingCreator-Komponente
- GlobalDocumentDropZone: Automatische .msg/.eml-Erkennung und Routing
- document-upload.js: `isEmailFile()` + `uploadEmailFile()` Hilfsfunktionen

**Dependencies:**
- Neue optionale Gruppe `email`: `extract-msg>=0.48`, `icalendar>=5.0`
- `all`-Gruppe erweitert: `bewerbungs-assistent[scraper,docs,export,email]`

**Geschlossene Issues:** #136

**Tests:** 317 passed (46 neue E-Mail-Tests), 4 skipped

---

## [0.28.0] - 2026-03-20

### Editierbare Bewerbungen, Statistik-Upgrade, Snapshot (7 Issues)

**Neue Features:**
- **#124** Stellenbeschreibung-Snapshot: URL wird automatisch ausgelesen und in der Bewerbung gespeichert — kein Datenverlust mehr wenn die Anzeige offline geht
- **#132** Template/Vorlagen-Kennzeichnung: Neue Dokumenttypen `lebenslauf_vorlage` und `anschreiben_vorlage` für generische CVs
- **#133** Positions-Überlappungs-Hinweis: CV-Export (PDF/DOCX) zeigt automatisch "(parallel zu XY)" bei überlappenden Positionen
- **#134** Bewerbungen editierbar: Alle Felder nachträglich änderbar + Vermittlerkette (Vermittler → Endkunde) + Timeline-Logging aller Änderungen
- **#135** Erweiterte Statistiken: Tagesbericht, Antwortzeiten-Analyse, Import/Neu-Unterscheidung, Dismiss-Reasons-Chart

**Bugfixes:**
- **#123** LiveUpdate "Failed to fetch": Dashboard-API-Calls resilient gemacht (`optionalApi` statt `api` für nicht-kritische Requests)
- **#137** zombies undefined: TypeError in DashboardPage wenn kein Profil vorhanden (Koala280 Bug-Report)

**Schema-Migration v13→v14:**
- `description_snapshot TEXT`, `snapshot_date TEXT` auf `applications`
- `vermittler TEXT`, `endkunde TEXT` auf `applications`

**Geschlossene Issues:** #123, #124, #132, #133, #134, #135, #137

**Tests:** 271 passed, 4 skipped

---

## [0.27.0] - 2026-03-20

### Datenqualität & Bugfix-Release (8 Issues)

**Bugfixes:**
- **#123** LiveUpdate "Failed to fetch": `optionalApi` fängt Netzwerkfehler ab ohne UI-Fehlermeldung
- **#125** Statistiken repariert: Quellen historisch korrekt, Score-Brackets, Unapplied-Filter, Timeline-Zeitfenster
- **#126** Eigene Ablehnungsgründe: UPSERT-Logik speichert und schlägt beim nächsten Mal vor
- **#127** Stellen-Badge: Zählt nur noch nicht-beworbene, aktive Stellen

**Verbesserungen:**
- **#128** Skill-Kategorie-Normalisierung: Whitelist-basierte Zuordnung (tool→tool, Sprachen→sprache, etc.)
- **#129** Skill-Extraktions-Müllfilter: Satzfragmente, URLs, Klammern und Nummern werden automatisch abgelehnt
- **#130** Zombie-Bewerbungen: Dashboard warnt bei Bewerbungen ohne Rückmeldung >60 Tage
- **#131** Dokument-Typ-Erkennung erweitert: .md, Vorlagen, Test-Docs, Fotos, Portfolios, Stellenbeschreibungen

**Geschlossene Issues:** #123, #125, #126, #127, #128, #129, #130, #131

**Tests:** 267 passed, 4 skipped

---

## [0.26.0] - 2026-03-20

### Major: Filtering, Scoring, UX — 15 Issues (66 Tools, 14 Prompts, Schema v13)

**Bug-Fixes Filtering (#114, #118, #121):**
- Blacklist-Filter in Stellen-API: Stellen von geblacklisteten Firmen werden automatisch ausgeblendet
- Bereits beworbene und aussortierte Stellen erscheinen nicht mehr in der Jobsuche
- Stellen-Zaehler (MetricCard) zeigt nur noch tatsaechlich sichtbare Stellen an
- Zentrale Filter-Funktion in `database.py` — MCP-Tools und Dashboard filtern identisch

**Passt-nicht-Begruendung (#108, #120):**
- Ablehnungsgruende sind jetzt Pflicht beim Aussortieren — kein "Passt nicht" ohne Grund
- Multi-Select: Mehrere Gruende gleichzeitig auswaehlbar (z.B. "zu_weit_entfernt" + "gehalt_zu_niedrig")
- Benutzerdefinierte Gruende koennen hinzugefuegt werden
- Neue `dismiss_reasons`-Tabelle (Schema v13) mit Nutzungszaehler fuer lernendes System
- Frontend: Neuer Dismiss-Dialog mit Chips-Auswahl und optionalem Freitext

**Scoring-Verbesserungen (#105, #112):**
- Freelance-Stellen erhalten keinen Entfernungs-Malus mehr — Festanstellung wie bisher
- Fit-Analyse zeigt explizit "Freelance — kein Malus" bei entfernten Freelance-Stellen

**UX Quick Wins (#106, #111, #116, #119):**
- Farbliche Unterscheidung: Festanstellung (blau) vs. Freelance (gruen) als Badge bei jeder Stelle
- Jobsuche-Button in leerer Stellen-Ansicht — direkter Einstieg in die Jobsuche
- Quell-Link (ExternalLink-Icon) direkt in der Bewerbungsliste neben dem Titel
- Stellen werden ohne automatische passt/passt-nicht-Empfehlung praesentiert

**Profil-Navigation (#122):**
- Sticky Sidebar im Profil-Bereich (ab Desktop-Breite): Schnellnavigation zu allen Sektionen
- Anker-Links: Persoenliche Daten, Suchkriterien, Blacklist, Erfahrung, Ausbildung, Skills, Dokumente

**Compliance & Hilfe (#103, #115):**
- Rechtlicher Disclaimer in Credits: Hinweis zu Scraping-ToS, lokaler Datenspeicherung, keine Gewaehr
- Hilfe/FAQ erweitert: Link zur vollstaendigen GitHub-Dokumentation
- Codex als weiteres Teammitglied in Credits aufgenommen
- Version in Credits auf v0.26.0 aktualisiert

**Roadmap-Issues gekennzeichnet:**
- 5 Issues (#28, #104, #107, #109, #117) als "roadmap" gelabelt — zukuenftige Entwicklungen

**Schema-Migration v13:**
- Neue Tabelle `dismiss_reasons` (id, label, is_custom, usage_count, profile_id)
- Vorbefuellt mit 10 Standard-Ablehnungsgruenden

**Geschlossene Issues:** #103, #105, #106, #108, #111, #112, #114, #115, #116, #118, #119, #120, #121, #122

**Tests:** 271 passed, 4 skipped (7 neue Tests)

---

## [0.25.2] - 2026-03-20

### Frontend-Recovery: Hilfe-Dialog, Timeline-Notizen, Statuswechsel (Codex/Claude)

**Bug-Fixes:**
- Hilfe-Button oben rechts repariert — Modal-`open`-Prop fehlte (#99)
- Notiz-Hinzufuegen in Bewerbungs-Timeline repariert — Click-Event wurde als Argument weitergereicht (#100)

**Neue Features:**
- Statuswechsel direkt in der Timeline-Detailansicht via Dropdown (#102)

**Stabilisierung:**
- Frontend-Build-Skripte auf `pnpm exec vite` umgestellt (stabiler in CI)
- Browser-Regressionstests fuer Hilfe-Modal und Timeline-Flows hinzugefuegt
- Recovery-Dokumentation: `docs/FRONTEND_RECOVERY_v022_to_v025.md`, `docs/CODEX_CLAUDE_FRONTEND_HANDOFF.md`

**Geschlossene Issues:** #99, #100, #101 (bereits seit v0.24.0 implementiert), #102

**Tests:** 264 passed, 4 skipped

---

## [0.25.0] - 2026-03-19

### Major: 14 Issues abgearbeitet — Backend, Frontend, Installer (66 Tools, 14 Prompts)

**Datenqualitaet (#79):**
- Word-Temp-Dateien (~$...) werden bei Import und Upload automatisch gefiltert
- Neue Dokumenttypen: `vorbereitung`, `projektliste`, `referenz`
- BEWERBUNGS-MASTER-WISSEN.md wird korrekt als `referenz` erkannt (nicht mehr als `anschreiben`)
- Einheitliche doc_type-Erkennung in Dashboard und MCP-Tools

**API-Erweiterung: Bewerbungen (#81):**
- Neue Query-Parameter: `from_date`, `to_date`, `search`, `sort_by`, `sort_order`
- Freitext-Suche ueber Titel, Firma und Notizen
- Sortierung nach: applied_at, title, company, status, created_at, updated_at
- SQL-Injection-sichere Whitelist fuer Sortierfelder

**Top-Stellen Bug-Fix (#98):**
- Dashboard-Top-Stellen filtern bereits beworbene Jobs aus
- Jobs mit Score 0 werden nicht mehr als Top-Stellen angezeigt
- Score-Persistenz: Gepinnte Jobs und manuell bewertete Jobs behalten ihren Score bei Re-Import
- `save_jobs()` prueft existierende Scores und Pin-Status vor INSERT OR REPLACE

**Stellen-Detailansicht (#96):**
- Aktionsbuttons im Detail-Modal: Bewerbung erfassen, Fit-Analyse, Anpinnen, Blacklist
- Direkte Interaktion ohne Schliessen des Modals

**Hilfe-Button kontextsensitiv (#95):**
- Hilfe-Inhalte passen sich automatisch an die aktuelle Seite an
- Spezifische Hilfe fuer: Dashboard, Profil, Stellen, Bewerbungen, Statistiken, Einstellungen
- Allgemeine Hilfe wird immer zusaetzlich angezeigt

**Auto-Link Dokumente (#77, #82):**
- Beim Erstellen einer Bewerbung werden Dokumente automatisch per Firmenname verknuepft
- Funktioniert identisch ueber MCP-Tool (`bewerbung_erstellen`) und Dashboard-API
- Shared Logic in `database.py:_auto_link_documents()`
- Dokument-Anzahl wird in der Bewerbungsliste angezeigt

**Bewerbungsansicht verbessern (#78):**
- Follow-Up-Banner verschlankt: Kompakte einzeilige Darstellung statt grosse Cards
- Datumsfilter (Von/Bis) und erweiterte Freitext-Suche (auch Notizen)
- Tage seit Bewerbung, Dokument-Count und Bewerbungsart als Badges
- Ansprechpartner wird in der Karten-Ansicht angezeigt
- Bewerbungstitel klickbar → oeffnet Timeline direkt

**Bewerbungs-Detailansicht (#80, #97):**
- Bewerbungs-Header mit Status-Badge, Kontaktdaten und Portal-Info
- Stellenbeschreibung als ausklappbarer Bereich (collapsible)
- Link zur Original-Stellenanzeige
- Bewerbungsdatum und Ansprechpartner prominent sichtbar

**Informelle Notizen (#92):**
- Neuer Bereich `notizen` in `profil_bearbeiten` mit Aktion `anhang`
- Sektion-basiertes Append: Text wird an benannte Sektion angehaengt (z.B. INTERVIEW-ERKENNTNISSE)
- Timestamps werden automatisch hinzugefuegt ([YYYY-MM-DD])
- Neue Sektionen werden automatisch erstellt wenn noch nicht vorhanden

**Profil-Report PDF (#93):**
- Neues MCP-Tool `profil_report_exportieren` — exportiert vollstaendigen Profil-Report als PDF
- Nutzt bestehende CV-PDF-Generierung (inkl. Positionen, Projekte, Skills, Ausbildung)

**Stundensatz & Arbeitsmodell (#94):**
- Neue Praeferenz-Felder: `min_stundensatz`, `ziel_stundensatz`, `remote_anteil`, `max_vor_ort_tage`, `max_entfernung_km`
- Werden in `profil_zusammenfassung` angezeigt
- 2 neue MCP-Tools: `suchkriterien_bearbeiten` (inkrementell Keywords hinzufuegen/entfernen) und `suchkriterien_anzeigen` (aktuelle Kriterien anzeigen)

**Installer Claude-Check (#91):**
- Automatische Erkennung ob Claude Desktop bereits mit PBP konfiguriert ist
- Checkbox wird deaktiviert mit "bereits konfiguriert" Hinweis

**Technisch:**
- 66 MCP-Tools (+3: profil_report_exportieren, suchkriterien_bearbeiten, suchkriterien_anzeigen)
- 262 Tests, alle bestanden
- Frontend-Build aktualisiert

## [0.24.1] - 2026-03-19

### Hotfix: Profil-Anzeige crashed durch inf-Float-Wert

- **GET /api/profile crashed**: `ValueError: Out of range float values are not JSON compliant: inf`
  verhinderte das Laden des Profils im Dashboard. Ursache: Ein `inf`-Float-Wert in der
  Datenbank (z.B. confidence in suggested_job_titles) konnte nicht JSON-serialisiert werden.
- **Globaler Fix**: Neuer `SafeJSONResponse` als `default_response_class` fuer die gesamte
  FastAPI-App. Alle API-Responses werden jetzt automatisch von `inf`/`nan`-Werten bereinigt
  (rekursive Sanitisierung zu `null`). Dies schuetzt ALLE Endpoints, nicht nur `/api/profile`.
- **Tests:** 2 neue Tests fuer inf-Sanitisierung (262 Tests gesamt)

## [0.24.0] - 2026-03-19

### Major: Dashboard-Erweiterungen (10 Issues)

**Hilfe-Menu (#75):**
- Fragezeichen-Icon im Header mit Modal: Hilfe/FAQ, Bug melden, Feature vorschlagen, Credits
- Bug/Feature-Reports oeffnen vorausgefuellte GitHub Issues

**Profil-Optimierung Hinweis (#76):**
- LinkedIn/XING Quellen zeigen Hinweis zur automatischen Profil-Optimierung
- Token-Warnung wird bei aktiven Quellen angezeigt

**Stellen-Liste (#83, #90):**
- Filter nach Stellenart (Festanstellung, Freelance, Praktikum, Werkstudent)
- Farbige Badges fuer Stellenarten in Jobs- und Bewerbungsliste
- "Beworbene ausblenden" Toggle — Stellen mit aktiver Bewerbung werden gefiltert
- Stellen-Detailansicht: Klick auf Titel oeffnet vollstaendige Ansicht
- Stellen bearbeiten: Titel, Firma, Standort, Beschreibung direkt im Modal

**Fit-Analyse in Bewerbung (#84):**
- Fit-Analyse wird in der Bewerbung gespeichert (neues DB-Feld)
- Anzeige im Timeline-Dialog mit Score, Staerken und Risiken

**Notizen: Antwort-Funktion (#85):**
- Reply-Button bei Notizen im Timeline-Dialog
- Antworten werden eingerueckt unter der Original-Notiz angezeigt
- Thread-Struktur via parent_event_id

**Einstellungen Badge (#86):**
- Settings-Badge "1" wird nur noch angezeigt wenn tatsaechlich Handlungsbedarf besteht
- "Nie gesucht" zaehlt nur wenn Quellen aktiv sind

**Statistiken (#87):**
- Neues Intervall "Komplett" (alle Daten)
- Bewerbungs-Quellen PieChart (woher kamen die Bewerbungen?)
- Klickbare Diagramm-Segmente navigieren zur Stellen-Liste
- Farbige Status-Balken und Quellen-Legende im PDF-Bericht

**Bewerbungen-Layout (#88):**
- Follow-Up Panel wird nur angezeigt wenn Follow-Ups existieren
- Ohne Follow-Ups: Bewerbungsliste nutzt volle Seitenbreite
- Letzte Notiz wird als Vorschau in der Bewerbungsliste angezeigt

**Schema:** v11 -> v12 (fit_analyse + parent_event_id)
**Tests:** Backend-Aenderungen + Frontend-Build erfolgreich

## [0.23.3] - 2026-03-19

### Bugfixes + Installer-Verbesserungen

- **XING Login fehlgeschlagen**: `ensure_xing_session` fehlte im Release-ZIP —
  XING-Login ueber Dashboard schlug mit ImportError fehl. ZIP wird jetzt korrekt
  aus dem aktuellen Code gebaut.
- **Dashboard starten.bat nicht gefunden**: Desktop-Shortcut und Dashboard-Start
  zeigten auf den temporaeren ZIP-Entpackpfad. Startdateien werden jetzt in den
  festen Installationspfad (`%LOCALAPPDATA%\BewerbungsAssistent`) kopiert.
- **Python wird nicht mehr unnoetig heruntergeladen**: Installer prueft jetzt ob
  Python aus einer frueheren Installation bereits vorhanden ist und verwendet es
  wieder, statt bei jedem Update erneut herunterzuladen (Installer v0.8.0).
- **LinkedIn/XING Profil-Optimierung**: Neuer Hinweis bei LinkedIn und XING
  Quellen, dass Profile automatisch von Claude optimiert werden koennen
  (verbraucht viele API-Tokens und dauert einige Minuten).
- **JSON inf-Error**: `ValueError: Out of range float values` bei Statistik-APIs
  wenn Score-Werte `inf` oder `NaN` enthalten. Alle Float-Werte werden jetzt
  vor der JSON-Serialisierung sanitized.
- **Aktives Profil nicht erkannt**: Safety-Net hinzugefuegt — wenn Profile
  existieren aber keins aktiv ist, wird das neueste automatisch aktiviert.

## [0.23.2] - 2026-03-19

### CV-Qualitaet und Recruiter-Best-Practices

**Verbesserte 3-Perspektiven-Bewertung (lebenslauf_bewerten):**
- **Karriereluecken-Erkennung**: Automatische Erkennung von Luecken >6 Monate
  im Lebenslauf mit konkreten Handlungsempfehlungen (Weiterbildung, Ehrenamt,
  Familienzeit dokumentieren).
- **Erfolge vs. Aufgaben**: Warnung wenn nur Aufgaben aber keine quantifizierten
  Erfolge dokumentiert sind — "Was hast du ERREICHT, nicht nur was hast du GETAN?"
- **Datumsformat-Pruefung**: ATS-Perspektive prueft ob Monat/Jahr angegeben ist
  (nicht nur Jahreszahl).
- **Roter-Faden-Analyse**: Recruiter-Perspektive erkennt ob sich Kernthemen
  durch mehrere Karrierestationen ziehen.
- **Zertifizierungen**: Recruiter-Perspektive bewertet Weiterbildungen und
  Zertifizierungen (SCRUM, ITIL, PMP, Cloud-Zertifikate etc.).
- **Sprachkenntnisse-Check**: ATS warnt wenn Sprachen fehlen (deutscher
  Arbeitsmarkt erwartet min. Deutsch + Englisch).
- **Skill-Level-Bonus**: Dokumentierte Skill-Level erhoehen ATS-Score.
- **Priorisierte Empfehlungen**: Top-Empfehlungen jetzt nach Kritikalitaet
  sortiert (kritisch > hoch > mittel) mit max. 8 statt 7 Empfehlungen.

**Verbesserte CV-Erstellungs-Prompts:**
- Neue "CV-Qualitaetsregeln" im bewerbung_schreiben-Prompt:
  Antichronologische Sortierung, max. 2-3 Seiten, quantifizierte Erfolge,
  einheitliches Datumsformat, Skills mit Kontext, ATS-Keyword-Uebernahme.
- Konkretere Empfehlungstexte mit "Tipp:"-Hinweisen statt abstrakter Aussagen.

**Browser-Tests fuer React-Frontend:**
- Alte Vanilla-JS Browser-Tests als `skip` markiert (Dashboard seit v0.23.0 React)
- Neuer React-kompatibler Smoke-Test: Seitenlade, Hash-Navigation, API-Erreichbarkeit

**Installer-Fix:**
- **Fix**: Installer installiert jetzt `playwright` Python-Paket und laedt Chromium-Browser
  automatisch herunter. Vorher fehlte Playwright im Installer, sodass LinkedIn- und
  XING-Browser-Suche mit "Playwright nicht installiert" fehlschlug (Installer v0.7.1).

**Tests:** 253+ bestanden

## [0.23.1] - 2026-03-19

### Hotfix: Schema-Migration + Profil-Isolation

**Kritischer Bug:** v0.23.0 Release-ZIP enthielt Code der `profile_id` auf
`search_criteria` und `blacklist` Tabellen referenzierte, aber die v11 Migration
fehlte. Bestehende DBs (von v0.21.0 oder frueher) crashten beim Start.

**Fixes:**
- Schema-Migration v10->v11 funktioniert jetzt korrekt bei bestehenden DBs
- `active_sources` und `last_search_at` sind jetzt profilbezogen gespeichert
  (Multi-Profil-Isolation komplett)
- `remove_blacklist_entry()` prueft jetzt Profil-Zugehoerigkeit
- ProfilePage.jsx: `Promise.allSettled` statt `Promise.all` — einzelne API-Fehler
  blockieren nicht mehr die gesamte Seite
- `ensure_linkedin_session()` Funktion hinzugefuegt
- 252 Tests bestanden (vorher 248)

## [0.23.0] - 2026-03-18

### Feature-Release: Koala280 React-Frontend Integration

Koala280s komplettes React/Vite/Tailwind-Frontend (7.877 Zeilen neuer UI-Code)
wurde offiziell in das Projekt integriert. Dies ersetzt das bisherige Vanilla-JS
Dashboard durch eine moderne Single-Page-Application.

**React-Frontend (Koala280):**
- Komplettes React/Vite/Tailwind-Frontend mit 7.877 Zeilen neuem UI-Code
- Moderne SPA-Architektur als Ersatz fuer das bisherige Vanilla-JS Dashboard

**Bugfixes:**
- **Status "abgelaufen" und "zweitgespraech" in Frontend-Dropdowns**: Alle drei
  Status-Dropdowns in ApplicationsPage (Filter, Statuswechsel, Neu-Anlegen) um
  die fehlenden Optionen ergaenzt. `STATUS_OPTIONS` in utils.js erweitert.
- **`statusTone()` erweitert**: "zweitgespraech" erhaelt Tone "success",
  "abgelaufen" erhaelt Tone "neutral" — passende Farbgebung in Badges.
- **Profilwechsel auf nicht-existierendes Profil deaktivierte aktives Profil**
  (kritisch): `switch_profile()` fuehrte `UPDATE SET is_active=0` auf alle
  Profile aus, BEVOR geprueft wurde ob das Zielprofil existiert. Bei ungueltigem
  Profil-ID waren danach alle Profile inaktiv. Fix: Existenz-Pruefung VOR dem
  Deaktivieren.
- **Test-Fix**: Versions-Konsistenz korrigiert.
- **DB Schema v11**: `profile_id` auf `search_criteria` und `blacklist` Tabellen
  fuer Profil-Isolation. Migration backfilled bestehende Daten automatisch.
- **delete_profile()** bereinigt jetzt auch `search_criteria` und `blacklist` Daten,
  und gibt korrekten Return-Wert zurueck (war immer None → 404).
- **Screenshots aktualisiert**: Alle 6 Tabs mit neuem React-Design (Dashboard,
  Profil, Stellen, Bewerbungen, Statistiken, Einstellungen).
- **Screenshot-Generator**: Fuer React-Frontend angepasst (Hash-Navigation, Toast-Dismissal).

## [0.22.0] - 2026-03-17

### Bewerbungs-Detailansicht, Gespraechsnotizen und Dokument-Verknuepfung

**Erweiterte Bewerbungs-Detailansicht:**
- Bewerbungs-Detailansicht komplett ueberarbeitet: Klick auf eine Bewerbung zeigt
  jetzt Stellendetails (Fit-Score, Quelle, Ort, Remote-Level, Gehalt, Entfernung),
  Kontaktdaten, aufklappbare Stellenbeschreibung und verknuepfte Dokumente.
- Firmenname prominent mit Original-Link zur Stellenanzeige.
- Portal-Badge (via StepStone, LinkedIn etc.) direkt sichtbar.
- Lebenslauf-Variante und Ablehnungsgrund in der Detailansicht.

**Gespraechsnotizen mit Zeitstempeln:**
- Neue Notizen-Funktion direkt in der Bewerbungs-Detailansicht.
- Notizen mit automatischem Zeitstempel hinzufuegen (Telefonnotizen,
  Interview-Feedback, Vorbereitung, Gespraechsprotokolle).
- Bestehende Notizen inline bearbeiten und loeschen.
- Notizen sind visuell hervorgehoben (blaues NOTIZ-Label) und von
  Statusaenderungen klar unterscheidbar.
- Sicherheit: Nur Notizen koennen geloescht werden, nicht Statusaenderungen.
- Chronologische Sortierung (neueste oben) mit Datum und Uhrzeit.
- API: POST /api/applications/{id}/notes (hinzufuegen),
  PUT /api/applications/{id}/notes/{event_id} (bearbeiten),
  DELETE /api/applications/{id}/notes/{event_id} (loeschen).

**Dokument-Verknuepfung:**
- Lebenslauf, Anschreiben und andere Unterlagen koennen direkt in der
  Detailansicht mit einer Bewerbung verknuepft werden.
- Dokument-Auswahldialog mit Hover-Effekt und Typ-Icons.
- API: GET /api/documents, POST /api/applications/{id}/link-document.

**Archiv-Fix:**
- Archivierte Bewerbungen (abgelehnt, zurueckgezogen, abgelaufen) werden wieder
  korrekt in der eingeklappten Archiv-Sektion angezeigt.

**Tests:**
- 9 neue Tests (237 total): Detailansicht, Dokument-Verknuepfung, Dokumente-API,
  Notizen hinzufuegen/bearbeiten/loeschen, leere Notiz abgewiesen,
  mehrere chronologische Notizen.

## [0.21.1] - 2026-03-17

### Multi-Profil-Haertung und Merge-Stabilisierung

- Jobs werden intern jetzt profilgebunden gespeichert, sodass identische externe
  Stellen-Hashes sich zwischen Profilen nicht mehr gegenseitig ueberschreiben.
- Oeffentliche Tool- und Dashboard-Ausgaben behalten dabei die bekannten
  unveraenderten Job-Hashes bei, obwohl intern scoped gespeichert wird.
- Bewerbungen loesen verknuepfte Stellen-Hashes profilsauber auf; Reports,
  Fit-Analysen und Gehalts-Extraktion bleiben damit konsistent.
- Follow-ups, Gehaltsstatistiken, Firmen-/Skill-Analysen, Ablehnungsmuster und
  naechste Schritte respektieren jetzt das aktive Profil durchgaengig.
- Neue Regressionstests decken Job-Kollisionen, profilgefilterte Follow-ups,
  Statistik-Isolation und stabile oeffentliche Hash-Ausgaben ab.
- MCP-Registry-Tests wurden mit der aktuellen FastMCP-API kompatibel gemacht,
  damit die Vollsuite auf dem aktuellen Dependency-Stand wieder gruen laeuft.

## [0.21.0] — 2026-03-16

### LinkedIn & XING Browser-Integration mit konfigurierbaren Selektoren (#73)

- **LinkedIn Browser-Suche**: Persistent-Browser-Sessions, Smart-Keywords aus
  Profil-Skills, Multi-Page-Pagination (max 3 Seiten), Job-ID-Deduplizierung,
  Beschreibungs-Extraktion aus Detail-Panel, Remote-Filter, Bot-Detection-Erkennung.
- **XING Browser-Suche**: Analoge Verbesserungen — Pagination, Job-ID-Dedup,
  konfigurierbare DOM-Selektoren.
- **Neues Modul `browser_config.py`**: Zentrale DOM-Selektoren fuer LinkedIn und
  XING — einfach aktualisierbar wenn Portale ihr Layout aendern.
- **Neues MCP-Tool**: `linkedin_browser_search()` fuer direkte LinkedIn-Suche.
- **62 Tools** gesamt (+1), 15 neue Tests (223 total).

## [0.20.0] — 2026-03-16

### Statistik-Dashboard, Bewerbungsbericht & Score-Korrektur

**Neuer Tab: Statistiken** (5 interaktive Charts mit Chart.js)
- **Bewerbungs-Timeline**: Balkendiagramm (Bewerbungen) + Linienchart (gefundene
  Stellen) — umschaltbar zwischen Woche / Monat / Quartal / Jahr.
- **Status-Verteilung**: Donut-Diagramm — farbcodierte Aufteilung aller
  Bewerbungen nach aktuellem Status.
- **Quellen-Vergleich**: Horizontale Balken — welche Jobquelle liefert die
  meisten Stellen? Top 12 Quellen auf einen Blick.
- **Fit-Score Verteilung**: Balkendiagramm — farbcodiert nach Qualitaet
  (gruen >= 8, gelb >= 5, grau < 5). Gepinnte Stellen exkludiert.
- **Quellen-Detailvergleich**: Gruppiertes Balkendiagramm — Durchschnittlicher
  vs. maximaler Fit-Score pro Quelle.

**Dashboard-Startseite:**
- Neue Statistik-Vorschau-Karte — zeigt zufaellig einen von 3 Werten
  (Avg Fit-Score, Quellen-Anzahl, Angebots-Rate) mit Link zum Statistik-Tab.

**Score-System: `is_pinned` ersetzt Score=99** (#72)
- **Neues Datenbankfeld `is_pinned`** (Schema v10): Manuell hinzugefuegte
  Stellen werden gepinnt statt kuenstlich auf Score 99 gesetzt.
- **Saubere Sortierung**: Gepinnte Stellen immer oben, dann nach echtem Score.
- **Statistik-Bereinigung**: ALLE Statistiken (Avg, Max, Verteilung) nutzen
  ausschliesslich den echten berechneten Score — keine Verzerrung durch
  kuenstliche 99er. Gepinnte Stellen separat gezaehlt.
- **Migration**: Bestehende Score=99-Eintraege (source="manuell") werden
  automatisch zu `is_pinned=1, score=0` migriert.
- **Pin-Toggle API**: `PUT /api/jobs/{hash}/pin` zum Pinnen/Entpinnen.
- **Score-Edit API**: `PUT /api/jobs/{hash}/score` zum manuellen Aendern.

**Neuer Status: `abgelaufen`** (#72)
- Fuer Bewerbungen, bei denen sich monatelang niemand gemeldet hat.
- Manuell setzbar (nicht automatisch) — da manche Firmen Monate brauchen.
- In allen Status-Dropdowns verfuegbar (Dashboard + MCP Tools).

**Bewerbungsliste: Paginierung + Archiv** (#72)
- **30er Paginierung**: Standardmaessig die letzten 30 Bewerbungen laden.
- **"Mehr laden" + "Alle laden"**: Buttons fuer seitenweises oder komplettes Laden.
- **Archiv-Sektion**: Abgelehnte, zurueckgezogene und abgelaufene Bewerbungen
  in einer eingeklappten `<details>`-Sektion — aktive Bewerbungen bleiben
  uebersichtlich sichtbar.
- Archiv-Badge zeigt Anzahl archivierter Bewerbungen.

**PDF-Bewerbungsbericht** (#72) — Arbeitsamt-tauglich
- Umfassender PDF-Export mit 7 Sektionen:
  1. **Zusammenfassung**: Bewerbungen, analysierte Stellen, Fit-Scores, Raten
  2. **Status-Verteilung**: Visuelle Balken pro Status
  3. **Genutzte Jobquellen**: Tabelle mit Stellenanzahl und Prozent-Anteil
  4. **Fit-Score Verteilung**: Farbige Balken pro Score-Klasse
  5. **Bewerbungsliste**: Tabelle (Datum, Firma, Position, Status, Quelle, Score)
  6. **Nicht beworben trotz gutem Score**: Analyse verpasster Chancen
  7. **Keyword-Analyse**: Top-25 Begriffe in passenden Stellen mit Haeufigkeit
- Export ueber Dashboard-Button oder `/api/applications/export?format=pdf`

**Excel-Export** (optional) (#72)
- Tabellarische Bewerbungsliste + Statistik-Sheet.
- Optionale Dependency: `pip install bewerbungs-assistent[export]` (openpyxl).
- Export ueber Dashboard-Button oder `/api/applications/export?format=xlsx`

**Backend-Verbesserungen:**
- `get_statistics()` jetzt Profil-gefiltert + erweitert um `pinned_jobs`,
  `avg_score`, `max_score`, `scored_jobs`, `jobs_by_source`.
- Neue API-Endpunkte: `/api/stats/timeline`, `/api/stats/scores`.
- `get_timeline_stats(interval)`: Bewerbungen + Stellen pro Zeitraum.
- `get_score_stats()`: Score-Verteilung + Quellen-Vergleich (Avg/Max).
- `get_report_data()`: Umfassende Daten fuer PDF/Excel-Bericht.

**Tests:**
- 18 neue Tests (208 total): Schema-Migration, is_pinned, Pagination,
  Archiv-Filter, Statistik-Bereinigung, Timeline-Stats, PDF-Generierung.

**Abhaengigkeiten:**
- Chart.js 4.4.7 via CDN (Dashboard-Statistiken)
- `openpyxl >= 3.1` als optionale `[export]` Dependency

---

## [0.19.0] — 2026-03-15

### 8 neue Jobquellen — 17 Quellen insgesamt

**Neue Jobboersen (Festanstellung):**
- **ingenieur.de (VDI)**: Engineering-Jobboerse des VDI. HTML-Scraping.
- **Heise Jobs**: IT-Stellenmarkt von Heise Verlag. HTML + JSON-LD.
- **Stellenanzeigen.de**: Grosses Jobportal (3.2 Mio. Besucher/Monat). HTML + JSON-LD.
- **Jobware**: Premium-Jobportal fuer Spezialisten und Fuehrungskraefte. HTML + JSON-LD.
- **<FIRMA>**: Engineering & IT Personaldienstleister. HTML + JSON-LD.
- **Kimeta**: Deutscher Job-Aggregator — buendelt Stellen aus vielen Quellen. HTML.

**Neue Projektboersen (Freelance):**
- **GULP**: Top IT/Engineering Freelance-Projektboerse. HTML + JSON-LD.
- **SOLCOM**: IT + Engineering Projektportal. HTML + JSON-LD.

**Alle neuen Quellen:**
- Kein Login erforderlich
- Multi-Strategie: HTML-Selektoren + JSON-LD Structured Data Fallback
- Dynamische Keywords aus Profil-Skills und Suchkriterien
- Automatische Remote-Level-Erkennung

## [0.18.1] — 2026-03-15

### Scraper-Rewrite: Robustere Jobsuche fuer alle 5 Quellen

**Jobsuche (#57, #48, #50):**
- **StepStone Scraper komplett neu** (#57): Multi-Strategie-Extraktion —
  (1) Article-Elemente, (2) /stellenangebot/-Links Fallback, (3) JSON-LD
  Structured Data. Cookie-Banner-Erkennung. Aktualisierte CSS-Selektoren.
- **Indeed Scraper komplett neu** (#57): Multi-Strategie-Extraktion —
  (1) job_seen_beacon/data-jk Container, (2) /viewjob-Link Fallback.
  Salary-Extraktion, Cookie-Banner-Erkennung.
- **Monster Scraper komplett neu** (#57): Multi-Strategie-Extraktion —
  (1) Article/Job-Card Elemente, (2) /job-openings/-Link Fallback,
  (3) JSON-LD Structured Data. Aktualisierte URL-Patterns.
- **LinkedIn dynamische Keywords** (#48): Suchbegriffe werden aus
  Profil-Skills und Suchkriterien generiert statt hardcoded.
- **LinkedIn regionale Filterung** (#50): Location-Parameter aus
  Suchkriterien-Regionen statt pauschal "Deutschland".
- **XING dynamische Keywords + Region** (#50): Gleiche Verbesserungen
  wie LinkedIn — Keywords aus Profil, Region aus Kriterien.
- Alle Scraper: Robustere Fallback-Selektoren, bessere Fehlerbehandlung.

## [0.18.0] — 2026-03-15

### Mega-Release: 26 GitHub-Issues geschlossen, 61 Tools, 14 Workflows

**Scoring & Suche:**
- **Tagessatz vs. Jahresgehalt korrekt** (#54): Gehaltsvergleich normalisiert jetzt
  Tagessaetze (×220 Arbeitstage) auf Jahresgehalt — Freelance-Stellen werden fair bewertet.
- **Cross-Source Duplikat-Erkennung** (#59): Gleiche Stelle auf mehreren Portalen wird
  erkannt (normalisierter Company+Title-Key) und nur einmal angezeigt.
- **Feineres Entfernungs-Scoring** (#60): 30/50/100/200km-Stufen statt hart/weich,
  Remote vs. Hybrid differenziert, Remote bekommt +4 Bonus.
- **Bewerbung als Scoring-Signal** (#68): Stellen aehnlich zu bisherigen Bewerbungen
  bekommen automatisch einen Bonus (Title-Matching).
- **Mindest-Score-Schwelle** (#53): Stellen unter konfigurierbarem Mindest-Score
  werden gar nicht erst gespeichert (Standard: 1).
- **Stellenbeschreibung in fit_analyse** (#55): Beschreibung (bis 2000 Zeichen)
  wird jetzt im Ergebnis mitgeliefert fuer tiefere Analyse.
- **Zeitraum-Filter** (#52): `max_alter_tage` Parameter — nur Stellen der letzten X Tage.
- **Datum in stellen_anzeigen** (#56): `gefunden_am` Feld in jeder Stelle.
- **Paginierung** (#58): `seite`/`pro_seite` Parameter, `seiten_gesamt`, `quellen_uebersicht`.
- **Beworbene Stellen markieren** (#65): `nur_nicht_beworben` Filter, `bereits_beworben` Flag.
- **Timestamp-Bug behoben** (#51): "Vor 2 Tagen" statt "Heute" korrigiert.

**Bewerbungs-Management:**
- **Bewerbungen vollstaendig verwalten** (#70): 4 neue Tools — `bewerbung_loeschen`,
  `bewerbung_bearbeiten`, `bewerbung_notiz`, `bewerbung_details`.
- **Manuelle Stellen sichtbar** (#67/#49): `bewerbung_erstellen` legt automatisch
  einen Job-Eintrag an (source="manuell", score=99). Duplikat-Erkennung.
- **Stellen-URL verknuepft** (#63): URL wird automatisch mit Bewerbung verknuepft.
- **Lernende Ablehnungsgruende** (#66): 10 vordefinierte Gruende, Zaehler,
  automatische Gewichtungsanpassung ab 3 gleichen Ablehnungen.

**Analyse & Coaching:**
- **Antwort-Formulierung** (#22): `antwort_formulieren` — generiert Kontext fuer
  Recruiter-Antworten basierend auf Bewerbungs-Details und Ton.
- **Dokument-Verknuepfung** (#61): `dokument_verknuepfen` — verknuepft Dokumente
  mit Bewerbungen fuer bessere Organisation.
- **Ablehnungs-Coaching** (#26): Neuer Workflow — empathische Analyse nach Absage
  mit konkreten Verbesserungsvorschlaegen.
- **Auto-Bewerbung** (#21): Neuer Workflow — automatische Bewerbungserstellung
  aus URL oder Stellentext (Fit-Analyse → CV → Anschreiben → Tracking).

**Dashboard:**
- **Klickbare Links** (#64): Stellen-URLs direkt anklickbar, Quellen-Badges,
  Widget-Ueberschriften verlinkt, Bewerbungen anklickbar zum Tab-Wechsel.
- **Drag & Drop Upload** (#32): Dateien per Drag & Drop oder Datei-Browser
  hochladen — visuelles Feedback mit Drop-Zone.

**Export:**
- **Markdown & TXT** (#62): `lebenslauf_exportieren` und `anschreiben_exportieren`
  unterstuetzen jetzt 'md' und 'txt' neben PDF/DOCX.

**Installer:**
- **Claude Desktop erkennen** (#24/#27): Installer erkennt und startet Claude Desktop
  automatisch. Prominenter Hinweis dass Claude im Hintergrund laufen muss.

**Bereits implementiert / geschlossen:**
- **Profildaten aus Dokumenten** (#40): War bereits ueber `extraktion_starten`/
  `profil_erweiterung` implementiert.

**Offen gelassen (4 Issues):**
- #57: Playwright-Scraper (StepStone, LinkedIn, Indeed, XING, Monster) — benoetigt
  Analyse der Portal-Aenderungen
- #50/#48: LinkedIn/XING Crawler-Verbesserungen — Tests auf Windows noetig
- #28: Dashboard-Claude Integration — Vision-Feature fuer spaeter

**61 Tools** in 8 Modulen, **14 Workflows**, 6 Resources, 190+ Tests.

---

## [0.17.1] — 2026-03-13

### Features: 3-Perspektiven-Analyse, Release-Vorbereitung

- **3-Perspektiven CV-Analyse**: Neues Tool `lebenslauf_bewerten()` — bewertet den Lebenslauf
  aus drei Experten-Blickwinkeln mit einstellbarer Gewichtung:
  - **Personalberater (Executive Search)**: Karriereverlauf, Soft Skills, Fuehrung, STAR-Projekte
  - **ATS (Bewerbermanagementsystem)**: Keyword-Treffer, messbare Erfolge, Kontaktdaten, Format
  - **HR-Recruiter (Fachabteilung)**: Technische Tiefe, Expert-Skills, Tech-Stack-Match, Projektqualitaet
- **Gewichtung einstellbar**: Standard 33/34/33, frei anpassbar je Perspektive (0.0-1.0)
- **Top-Empfehlungen**: Priorisierte Verbesserungsvorschlaege, ATS-Empfehlungen zuerst
- **Bewerbungs-Workflow erweitert**: Analyse kommt VOR dem CV-Export, damit der User
  basierend auf den Empfehlungen noch reagieren kann
- **README komplett ueberarbeitet**: Benefit-First, Bedienungsanleitung, Account-Anforderungen,
  rechtliche Hinweise zu LinkedIn/XING, FAQ-Sektion
- **LinkedIn DEFAULT_SEARCHES entpersonalisiert**: Keine standortspezifischen Suchbegriffe mehr
- **Version-Mismatch behoben**: pyproject.toml und __init__.py jetzt konsistent
- **55 Tools**, 12 Prompts, 190 Tests.

---

## [0.17.0] — 2026-03-12

### Features: Split-Layout, Distance-Scoring, Tailored CV, GitHub-Issue-Cleanup

- **Dashboard Split-Layout**: Stellen werden nach Festanstellung/Freelance in zwei Spalten
  angezeigt. Toggle-Button zum Umschalten zwischen Split- und Listen-Ansicht.
  Layout-Wahl wird in localStorage gespeichert.
- **Sortierung nach Entfernung**: Neue Standard-Sortierung — Nah (<30km), dann Remote/Hybrid,
  dann Fern. Zusaetzliche Sort-Optionen: Score, Gehalt, Datum.
- **Entfernung-Schwelle 80→30km**: Stellen unter 30km werden bevorzugt (statt 80km).
- **Gehalts-Scoring**: Neues Gewicht `gehalt` in der Stellenbewertung. Vergleicht Job-Gehalt
  mit Profil-Mindestgehalt/-tagessatz. Gehalts-Risiko in Fit-Analyse wenn <80% der Praeferenz.
- **Kompetenzen in Fit-Analyse**: Profil-Skills werden gegen Stellenbeschreibung gematcht,
  neuer Faktor "Kompetenzen-Match" in der Analyse.
- **Angepasster Lebenslauf (DOCX)**: Neues Tool `lebenslauf_angepasst_exportieren()` —
  ordnet Skills und Positionen nach Relevanz fuer die Stelle, immer DOCX-Format.
- **Bewerbungs-Workflow aktualisiert**: Lebenslauf kommt vor Anschreiben, Anschreiben optional.
- **Next-Steps-Banner**: Kontextbezogener gruener Banner im Dashboard mit naechsten Aktionen.
- **Skill-Navigation**: Prev/Next-Pfeile im Skill-Edit-Modal (← 3/25 →).
- **profil_bearbeiten erweitert**: `aendern`-Aktion fuer Position, Skill, Projekt, Ausbildung;
  `loeschen` fuer Projekt.
- **Skill-Validierung**: Garbage-Filter — min 2 Zeichen, max 100, >50% alphanumerisch,
  keine Markdown-Fragmente, Deduplizierung per LOWER(name).
- **bewerbung_status_aendern**: Erweiterte Docstring-Keywords fuer bessere Tool-Erkennung.
- **GitHub Issues**: 42→11 offene Issues — 31 Issues geschlossen (bereits implementiert oder obsolet).
- **54 Tools**, 12 Prompts, 15 Tabellen, 190 Tests.

---

## [0.16.5] — 2026-03-12

### Fix: Ersterfassung analysiert Dokumente SOFORT ohne zu fragen

- **extraktion_starten() ist IMMER der erste Tool-Aufruf** — nicht erfassung_fortschritt_lesen().
  Das verhindert dass Claude den Fortschritt sieht, denkt "da ist schon was" und fragt
  statt die Dokumente zu analysieren.
- **Reihenfolge umgedreht**: Erst Dokumente pruefen, dann Fortschritt. Nicht umgekehrt.
- **Neue Regeln 14**: Kein Smalltalk und keine Nachrichten an den User VOR dem ersten
  Tool-Aufruf. Erst handeln, dann berichten.
- **Klarere Ablauf-Beschreibung**: 3 nummerierte Schritte statt verschachtelte WENN-Bloecke.
  Claude soll einem einfachen Rezept folgen, nicht Bedingungen evaluieren.

---

## [0.16.4] — 2026-03-12

### Installer v0.7.0: File-Locking Fix + Versions-Check

- **Laufende PBP-Prozesse werden automatisch beendet** bevor die Runtime kopiert wird —
  behebt "Unzulaessiger SHARE-Vorgang" wenn Claude Desktop noch laeuft
- **Versions-Check**: Installer prueft ob die aktuelle Version schon installiert ist und
  fragt ob trotzdem neu installiert werden soll. Bei Updates zeigt er "Update: X auf Y".
- **Bessere Fehlermeldung**: Bei Kopier-Fehler erklaert der Installer jetzt konkret dass
  Claude Desktop beendet werden muss (statt nur "als Administrator ausfuehren")

---

## [0.16.3] — 2026-03-12

### Fix: Ersterfassung arbeitet IMMER mit aktivem Profil

- **SCHRITT 0 radikal vereinfacht** — Claude ruft jetzt nur noch `erfassung_fortschritt_lesen()`
  und `extraktion_starten()` auf. Kein `profile_auflisten()` mehr, das Claude zum Nachdenken
  ueber mehrere Profile verleitete statt einfach zu arbeiten.
- **Aktives Profil ist gesetzt** — Claude stellt das Profil NICHT mehr in Frage. Der User
  hat es im Dashboard gewaehlt, Claude respektiert das und arbeitet damit.
- **Keine Halluzinationen mehr** — Starke Regel: Claude verwendet NUR Daten die die Tools
  JETZT zurueckgeben. Keine Profil-IDs oder Namen aus dem Gedaechtnis/frueheren Gespraechen.
- **Handeln statt diskutieren** — Der Prompt ist jetzt handlungsorientiert: Dokumente
  analysieren → Daten anwenden → fehlende Bereiche im Gespraech ergaenzen.

---

## [0.16.2] — 2026-03-12

### Fix: Ersterfassung nach Reset — Fragmente, Duplikate, Dokumentanalyse

- **Reset loescht jetzt ALLE Tabellen** — `search_criteria` und `follow_ups` fehlten in
  `reset_all_data()` und konnten Fragmente hinterlassen
- **Ersterfassung erkennt Profil-Fragmente** — Profile mit nur Name/E-Mail (aus Dashboard-
  Auto-Erstellung) werden als Fragmente behandelt, nicht als echte Profile. Doppelte
  "Mein Profil"-Eintraege werden automatisch aufgeraeumt statt den User zu verwirren.
- **Dokument-Analyse hat IMMER Vorrang** — Prompt-Prioritaet umstrukturiert: Dokumente
  werden immer zuerst vollstaendig KI-analysiert, auch wenn das Profil schon Basisdaten hat.
  basis_analysiert-Dokumente werden jetzt zuverlaessig gefunden und tiefenanalysiert.
- **Neue Prompt-Regeln 12+13** — Verhindern Profil-Duplikate und Halluzinationen von
  Profil-IDs aus frueheren Gespraechen

---

## [0.16.1] — 2026-03-12

### Fix: Ersterfassung nach Dokumenten-Upload (Issue #38)

- **Dashboard-Auto-Analyse markiert Dokumente jetzt als `basis_analysiert`** statt `angewendet` —
  damit erkennt die Ersterfassung diese Dokumente und fuehrt die vollstaendige KI-Tiefenanalyse durch
  (Positionen, STAR-Projekte, Ausbildung, Skills mit Levels statt nur Regex-Basisdaten)
- **Prominenter Ersterfassung-CTA nach Upload** — nach dem Hochladen eines Dokuments erscheint
  ein grosser, auffaelliger Hinweis der erklaert was als naechstes zu tun ist und den
  Ersterfassung-Workflow direkt zum Kopieren anbietet
- **Ersterfassung-Prompt versteht `basis_analysiert`** — erkennt dass nur Basisdaten extrahiert
  wurden und startet automatisch die vollstaendige KI-Analyse
- **Alle Dokument-Tools aktualisiert** — `extraktion_starten()`, `analyse_plan_erstellen()`,
  `dokumente_batch_analysieren()`, `dokumente_bulk_markieren()` erkennen alle den neuen Status

---

## [0.16.0] — 2026-03-12

### Skill-Aktualitaet & Jobtitel-Vorschlaege

- **Skill Time-Decay**: Skills tracken jetzt `last_used_year` — ein Programmier-Skill von vor
  20 Jahren (seitdem nicht mehr genutzt) wird automatisch als veraltet erkannt (Level ~1).
  Alte Skills (>5 Jahre) werden im Dashboard als graue Badges dargestellt. Beides editierbar.
- **Automatische Jobtitel-Vorschlaege**: PBP leitet aus Profil, Lebenslauf und Dokumenten
  passende Jobtitel ab (deutsch + englisch). Neue Tabelle `suggested_job_titles` mit
  Quelle und Konfidenz. Jobtitel sind im Dashboard editierbar, loeschbar, deaktivierbar.
- **2 neue MCP-Tools** (53 gesamt):
  - `jobtitel_vorschlagen(titel, quelle)` — Speichert vorgeschlagene Jobtitel mit Deduplizierung
  - `jobtitel_verwalten(titel_id, aktion, neuer_titel)` — Bearbeiten/Loeschen/Deaktivieren
- **Schema v9**: Migration fuegt `last_used_year` auf `skills` und neue Tabelle `suggested_job_titles` hinzu
- **Ersterfassung-Prompt**: Phase 2d fragt aktiv nach Skill-Aktualitaet, Phase 3b schlaegt Jobtitel vor
- **Profil-Erweiterung-Prompt**: Dokumentanalyse beruecksichtigt jetzt Skill-Aktualitaet und
  schlaegt nach jeder Analyse passende Jobtitel vor
- **Dashboard**: Neue "Passende Jobtitel"-Sektion, Skill-Edit mit last_used_year, 4 neue API-Endpoints

---

## [0.15.1] — 2026-03-12

### Ersterfassung: Automatische Dokumentanalyse

- **Dokumente werden sofort analysiert** — Ersterfassung prueft jetzt aktiv auf vorhandene
  Dokumente und startet die Extraktion automatisch, statt den User zu fragen
- **Erneut-analysieren-Button** bei jedem analysierten Dokument im Dashboard —
  setzt den Status zurueck, damit Claude das Dokument nochmal gezielt analysieren kann

### Bugfix: Neues Profil war nicht leer

- **Neues Profil uebernahm alle Daten** (kritisch): `neues_profil_erstellen()` und Dashboard
  "Neues Profil" aktualisierten nur das bestehende Profil statt ein neues, leeres anzulegen.
  Neue `create_profile()`-Methode erstellt jetzt ein komplett leeres Profil.

### Dashboard: Direktes Profil-Bearbeiten

- **Edit-Buttons bei Positionen** — Titel, Firma, Zeitraum, Beschreibung direkt aendern
- **Edit-Buttons bei Ausbildung** — Institution, Abschluss, Fachrichtung, Zeitraum bearbeiten
- **Kompetenzen klickbar** — Skill-Name, Level und Kategorie aendern oder Kompetenz entfernen
- **3 neue PUT-Endpoints** — `/api/position/{id}`, `/api/education/{id}`, `/api/skill/{id}`

---

## [0.15.0] — 2026-03-12

### Effiziente Dokument-Analyse & Bewerbungs-Erkennung

Grosses Update fuer Nutzer mit vielen Dokumenten. Batch-Analyse, Duplikat-Erkennung,
automatische Bewerbungs-Erkennung aus Dateinamen und der kritische Summary-Bug behoben.

### Bugfixes

- **Summary-Ueberschreibung behoben** (kritisch): `extraktion_anwenden()` ueberschrieb
  das Profil-Summary mit Dokument-Beschreibungen (z.B. "Jungheinrich Interview-Vorbereitung"
  statt "Lead PLM Architekt mit 20+ Jahren Erfahrung"). Jetzt wird Summary nur noch
  ueberschrieben wenn der neue Text nach einem echten Profil-Summary aussieht und
  laenger ist als das bestehende.

### Neue Tools (4 neue, 51 gesamt)

- **`analyse_plan_erstellen()`** — Vorab-Plan: Anzahl Dokumente, Duplikate, Batches, Firmen
- **`dokumente_batch_analysieren(batch_nr, ...)`** — Effiziente Batch-Analyse mit Token-Budget
- **`dokumente_bulk_markieren(document_ids, status)`** — Bulk-Markierung als analysiert
- **`bewerbungs_dokumente_erkennen(auto_erstellen)`** — Firmen aus Dateinamen erkennen +
  automatisch Bewerbungseintraege anlegen

### Verbesserungen

- **`extraktion_starten(profil_mitsenden=False)`** — Token-sparend bei Folge-Aufrufen
- **PDF/DOCX-Duplikat-Erkennung** — Automatisch bei Batch-Analyse
- **Anleitung in extraktion_starten** — Warnt vor Summary-Missbrauch

---

## [0.14.3] — 2026-03-12

### Fix: Dashboard-Befehle funktionieren jetzt ueberall

Das Dashboard kopierte bisher `/jobsuche_workflow` in die Zwischenablage — das funktionierte
nur in Claude Desktop (als Slash-Command), nicht in claude.ai. Jetzt kopiert der "Kopieren"-Button
`Starte den Workflow: /jobsuche_workflow`, was Claude als natuerliche Anweisung erkennt und
automatisch `workflow_starten()` aufruft.

### Aenderungen

- **Dashboard `copyText()` transformiert Slash-Commands**: `/name` wird zu
  `Starte den Workflow: /name` — funktioniert in Claude Desktop UND claude.ai
- **Alle "Claude Desktop"-Verweise entfernt**: Dashboard sagt jetzt nur "Claude",
  da es mit allen Claude-Umgebungen funktioniert
- **Tooltip-Texte aktualisiert**: Keine irreführende "Claude Desktop"-Referenz mehr

---

## [0.14.2] — 2026-03-12

### Fix: Workflows auch ohne Slash-Commands nutzbar

MCP-Prompts (/slash-commands) werden in manchen Claude-Umgebungen nicht angezeigt.
Alle 12 Workflows sind jetzt zusaetzlich als Tools verfuegbar, sodass sie ueberall
funktionieren — egal ob Claude Desktop, claude.ai oder andere MCP-Clients.

### Aenderungen

- **Neues Modul `tools/workflows.py`**: 3 neue Tools
  - `workflow_starten(name)` — Universeller Workflow-Starter fuer alle 12 Workflows
  - `jobsuche_workflow_starten()` — Direkter Einstieg in den Jobsuche-Workflow
  - `ersterfassung_starten()` — Direkter Einstieg in die Profilerfassung
- **47 Tools** (vorher 44): Workflows als Tools statt nur als Prompts
- Prompts bleiben weiterhin registriert (fuer Clients die sie unterstuetzen)

### Nutzung

Statt `/jobsuche_workflow` einfach sagen:
- "Starte den Jobsuche-Workflow" → Claude ruft `jobsuche_workflow_starten()` auf
- "Starte die Ersterfassung" → Claude ruft `ersterfassung_starten()` auf
- Oder: `workflow_starten(name='bewerbung_schreiben')` fuer jeden anderen Workflow

---

## [0.14.1] — 2026-03-12

### Fix: Update-sichere MCP-Konfiguration

Bei Versions-Updates (z.B. v0.12.0 → v0.14.0) zeigte die Claude Desktop Config
auf den alten, nicht mehr existierenden Ordner. Der MCP-Server wurde dadurch nicht
erkannt und kein einziges PBP-Tool war verfuegbar.

### Aenderungen

- **Installer v0.6.0**: Kopiert `python/` und `src/` jetzt in den festen Pfad
  `%LOCALAPPDATA%\BewerbungsAssistent\`. Bei Updates werden diese Ordner
  ueberschrieben, die Pfade in der Claude-Config bleiben stabil.
- **`_setup_claude.py`**: Schreibt feste Pfade statt `sys.executable`-basierte
  Pfade in die `claude_desktop_config.json`.
- **`installer/install.ps1`**: Gleiche Logik fuer den PowerShell-Installer —
  kopiert `.venv` und `src/` in den festen Installationspfad.
- **Dashboard-Browser-Smoke-Tests**: 3 Playwright-Smokes (Erststart, Navigation, Mobile-Layout)
- **190 Tests** dokumentiert, Test-Setup klarer beschrieben

### Struktur nach Installation

```
%LOCALAPPDATA%\BewerbungsAssistent\
├── python\          (Embedded Python, vom Installer kopiert)
├── src\             (PBP Source Code, vom Installer kopiert)
├── pbp.db           (Datenbank)
├── dokumente\       (Uploads)
├── export\          (Generierte Dokumente)
└── logs\
```

---

## [0.14.0] — 2026-03-10

### Konsolidierung: Service-Layer, Dashboard-UX, Workspace-Guidance

Dieser Release entstand aus einem Codex-Sprint (Branch `codex/konsolidierung-sprint1`)
mit anschliessender Claude-Code-Pruefung und Abnahme. Fokus war Konsolidierung und
Qualitaet, nicht neue End-User-Features.

### Service-Layer (neu)

Gemeinsame Domaenenlogik wurde aus Dashboard und MCP-Tools in drei Service-Module
extrahiert. Damit sprechen beide Schichten dieselbe fachliche Sprache:

- **`services/profile_service.py`** — Profilstatus, Praeferenzen-Parsing,
  Vollstaendigkeits-Checks mit 9 Pruefregeln und Nutzer-Labels.
- **`services/search_service.py`** — Suchstatus-Normalisierung (aktuell/veraltet/dringend),
  Quellenzaehlung (aktiv vs. Registry), Dashboard-freundliche Quellenzeilen.
- **`services/workspace_service.py`** — Workspace-Guidance mit 7 Readiness-Stufen
  (onboarding → profil_aufbauen → quellen_aktivieren → jobsuche_erneuern →
  bewerben → nachfassen → im_fluss), Follow-up-Zusammenfassung, Navigations-Badges.

### Dashboard-UX

- **Workspace-Summary API** — Neuer Endpoint `/api/workspace-summary` aggregiert
  Profil, Quellen, Suchstatus, Jobs, Bewerbungen und Follow-ups zu einer einzigen
  Guidance-Payload mit Readiness-Stufe und konkreter Handlungsempfehlung.
- **Workspace-Kopf** — Das Dashboard zeigt jetzt oben einen kontextabhaengigen
  Hinweis mit Headline, Beschreibung und Aktions-Button (z.B. "Profil ausbauen"
  oder "Quellen einrichten").
- **Navigations-Badges** — Tab-Navigation zeigt Zaehler fuer offene Stellen,
  Bewerbungen und Konfigurationsbedarf.
- **Profil-Schnellzugriffe** — Klarerer Zugang zu Profilstatus und Vollstaendigkeit.
- **Seitenbezogene Orientierung** — Jeder Tab reagiert auf den aktuellen
  Workspace-Zustand.

### Bugfixes

- **Wizard speichert Quellen korrekt** — `active_sources` werden jetzt sauber
  persistiert statt ignoriert.
- **Sprung zum Dokument-/Import-Bereich** — Hash-Navigation korrigiert.
- **Runtime-Log-CSS-Fallback** — Bereinigung eines fehlenden Style-Fallbacks.
- **Quellenfilter** — Wird bei Seitenwechsel sauber neu aufgebaut.

### Tests

- **28 neue Tests** (von 159 auf 187):
  - `test_profile_service.py` (5): Profilstatus, Praeferenzen, Vollstaendigkeit,
    Labels, ungueltige JSON-Praeferenzen.
  - `test_search_service.py` (5): Suchstatus, aktive Quellen, Quellenzeilen.
  - `test_workspace_service.py` (5): Follow-ups, Badges, Onboarding,
    Quellen-Priorisierung, Follow-up-Priorisierung.
  - `test_mcp_registry.py` (3): Registry-Zaehlung, stabile Interface-Namen,
    repraesentative Smoke-Runs.
  - `test_scrapers.py` (3): Fixture-basierte Parser fuer <FIRMA> (Sitemap + JSON-LD),
    Freelance.de (Karten + Paginierung), Freelancermap (JS-State-Extraktion).
  - `test_dashboard.py` (+7): Workspace-Summary (leer, Profil-Ausbau,
    Quellen/Suche/Follow-ups), Profil-Vollstaendigkeit (Adresse), Quellen-API.
- **Scraper-Fixtures**: HTML/XML-Fixtures unter `tests/fixtures/scrapers/`
  fuer reproduzierbare Parsertests ohne Netzwerk.
- Test-Gesamtzahl: **187 Tests** (alle gruen).

### Doku-Sweep

- README-Badge von "159 passing" auf "187 passing" korrigiert.
- Endpoint-Zaehlung von 55 auf 56 korrigiert (alle Dokumente).
- Dashboard-Zeilenanzahl auf ~1.272 aktualisiert.
- Versionshistorie in ZUSTAND.md, AGENTS.md, architecture.md ergaenzt.
- DOKUMENTATION.md Test-Auflistung um Service- und Scraper-Tests erweitert.

## [0.13.0] — 2026-03-08

### Bugfixes

- **FIX-008: job_hash FK-Constraint**: `bewerbung_erstellen` mit leerem `job_hash=""` loeste
  einen Foreign-Key-Fehler aus, weil `""` keinem `jobs.hash` entsprach. Jetzt wird leerer
  String automatisch zu `None` konvertiert (`job_hash or None`).
- **FIX-009: Reset/Profil-Loeschen blockiert**: Wenn durch FIX-008 bereits korrupte
  Eintraege (`job_hash=""`) in der DB existierten, konnte weder Factory-Reset noch
  Profil-Loeschen ausgefuehrt werden (FK-Constraint beim DELETE). Jetzt werden beide
  Operationen mit `PRAGMA foreign_keys=OFF` umschlossen und korrupte Eintraege
  vorher bereinigt.
- **FIX-006: Upload-Modal zeigt falschen Prompt**: Nach Dokument-Upload fuer die
  Ersterfassung wurde nur `/profil_erweiterung` angeboten. Jetzt wird die
  Profil-Vollstaendigkeit geprueft: Bei neuen Profilen (<20%) wird `/ersterfassung`
  empfohlen.
- **FIX-007: Automatische Dokument-Analyse**: Importierte Dokumente wurden nur
  hochgeladen aber nicht ins Profil eingepflegt. Neuer Endpoint
  `/api/dokumente-analysieren` extrahiert per Regex (ohne LLM) E-Mail, Telefon,
  Adresse, Name, Geburtstag, Nationalitaet und Skills. Wird automatisch nach
  Upload und Ordner-Import aufgerufen.

### Neue Features

- **OPT-014: Ordner-Browser**: Der Ordner-Import hat jetzt einen klickbaren
  Verzeichnis-Browser statt nur Pfad-Eingabe. Neuer Endpoint `/api/browse-directory`
  mit Vorschlaegen (Eigene Dateien, Desktop, Downloads), Sicherheits-Checks
  (Systemverzeichnisse blockiert) und Datei-Zaehler.
- **Unterordner-Option**: Checkbox "Unterordner einschliessen" (standardmaessig aus)
  mit Warnhinweis. Backend nutzt `rglob()` statt `glob()` bei `recursive=True`.

### Tests

- 14 neue Tests in `test_v013.py`:
  - TestJobHashFix (3): Leerer, None und gueltiger job_hash
  - TestFKSafeDelete (2): Reset und Profil-Loeschen mit korrupten Daten
  - TestDirectoryBrowser (4): Vorschlaege, existierendes Dir, blockiert, 404
  - TestFolderImportRecursive (2): Nicht-rekursiv vs. rekursiv
  - TestAutoAnalyze (3): Ohne Profil, ohne Dokumente, E-Mail-Extraktion
- Test-Gesamtzahl steigt von 145 auf **159 Tests** (alle gruen).

## [0.12.0] — 2026-03-07

### Architektur: server.py Modularisierung

Die gesamte `server.py` (3.261 Zeilen, 44 Tools + 6 Resources + 12 Prompts in einer
Datei) wurde in fachlich getrennte Module aufgeteilt. Das war die groesste
Strukturschwaeche des Projekts: Ein einziges File fuer die komplette Business-Logik
machte Navigation, Wartung und gezieltes Testen praktisch unmoeglich.

**Vorher:** Alles in `server.py` — Tools, Resources, Prompts, Hilfsfunktionen, Imports.
Wer ein einzelnes Tool aendern wollte, musste durch 3.000+ Zeilen scrollen.

**Nachher:** `server.py` ist nur noch der Composition Root (~140 Zeilen) — sie
initialisiert Logging, Datenbank und MCP-Server, haengt den Logging-Wrapper ein
und ruft `register_all()` / `register_resources()` / `register_prompts()` auf.
Die eigentliche Logik liegt jetzt in eigenen Modulen nach Fachgebiet:

| Modul | Was steckt drin | Tools |
|-------|----------------|-------|
| `tools/profil.py` | Profil-CRUD, Multi-Profil, Erfassungs-Fortschritt | 14 |
| `tools/dokumente.py` | Dokument-Analyse, Extraktion, Profil-Im/Export | 8 |
| `tools/jobs.py` | Jobsuche starten/status, Stelle bewerten, Fit-Analyse | 5 |
| `tools/bewerbungen.py` | Bewerbung erstellen/status, Statistiken | 4 |
| `tools/analyse.py` | Gehalt, Firmenrecherche, Skill-Gap, Ablehnungsmuster, Follow-ups | 9 |
| `tools/export_tools.py` | Lebenslauf + Anschreiben als PDF/DOCX exportieren | 2 |
| `tools/suche.py` | Suchkriterien setzen, Blacklist verwalten | 2 |
| `resources.py` | 6 MCP-Datenquellen (Profil, Jobs, Bewerbungen, Statistik, Config) | — |
| `prompts.py` | 12 MCP-Prompts (Ersterfassung, Interview-Sim, Gehaltsverhandlung, ...) | — |

Jedes Modul hat eine `register(mcp, db, logger)` Funktion — der MCP-Server und die
Datenbank werden als Parameter uebergeben, keine globalen Imports noetig.

**Wichtig:** An der Funktionalitaet hat sich nichts geaendert. Alle 44 Tools, 6
Resources und 12 Prompts verhalten sich exakt gleich. Es ist ein reines Refactoring.

### Bugfix in Prompts

- `willkommen`-Prompt: "bis zu 8 Jobportale" auf "bis zu 9 Jobportale" korrigiert
  (Freelance.de wurde in v0.10.0 als 9. Quelle hinzugefuegt, der Prompt-Text war
  aber nie angepasst worden)

### Dashboard-API-Tests (neu)

Bisher gab es keine Tests fuer die ~47 Dashboard-API-Endpoints. Jetzt gibt es
37 Tests mit dem FastAPI TestClient, die folgendes abdecken:

- **Status-API**: Leere DB liefert `has_profile: false`, nach Profil-Erstellung `true`
- **Profil-CRUD**: Erstellen, Lesen, Aktualisieren eines Profils
- **Validierung** (8 Tests): Fehlende Pflichtfelder bei Profil (Name), Position
  (Firma, Titel), Ausbildung (Einrichtung), Skill (Name) und Bewerbung (Stelle, Firma)
  liefern korrekten HTTP 400 mit Fehlermeldung
- **Multi-Profil** (5 Tests): Profil-Liste, neues Profil erstellen + wechseln,
  nicht-existierendes Profil → 404, Profil loeschen
- **Profil-Elemente**: Position, Skill, Ausbildung hinzufuegen + loeschen
- **Bewerbungen + Paginierung**: Erstellen, Auflisten, Paginierung mit limit/offset
- **CV-Generierung**: Ohne Profil → 404, mit Profil → Text enthaelt Name
- **Statistiken**: Suchkriterien, Profil-Vollstaendigkeit, Next-Steps, Such-Status
- **Factory Reset**: Ohne Bestaetigung → 400, mit Bestaetigung loescht alle Daten

Test-Gesamtzahl steigt von 108 auf **145 Tests** (alle gruen).

### Doku-Korrekturen

Die Codex-Analyse (v0.11.1) hatte aufgedeckt, dass die Dokumentation an vielen
Stellen veraltet war. In v0.11.1 wurden README, ZUSTAND und AGENTS gefixt.
Jetzt kamen die restlichen Dateien dran:

- **`__init__.py`**: Version stand noch auf `0.9.0` (!) statt `0.11.1` —
  das heisst `bewerbungs_assistent.__version__` und der Log beim Start zeigten
  die falsche Version an. Jetzt `0.12.0`.
- **DOKUMENTATION.md**: Komplett ueberarbeitet — Tool-Tabelle von 21 auf 44 Tools
  erweitert, Prompt-Tabelle von 8 auf 12, Schema von v2 auf v8, Tabellen von 13
  auf 15, Dashboard-Endpoints von 28 auf ~47, Tests von 65 auf 145. Veraltete
  "Naechste Schritte" (die laengst umgesetzt waren) entfernt.
- **TESTVERSION.md**: Hinweis "PDF-Export noch nicht implementiert" entfernt
  (ist seit v0.8.0 implementiert)
- **OPTIMIERUNGEN.md**: Als abgeschlossen markiert ("Alle 13 Optimierungen
  abgeschlossen, archiviert")

## [0.11.1] — 2026-03-07

### Konsolidierung (ausgeloest durch Codex-Analyse)

OpenAI Codex hat das Projekt analysiert (siehe `docs/CODEX_ANALYSE.md`) und dabei
massive Inkonsistenzen in der Dokumentation aufgedeckt. Claude Code hat daraufhin
alle Dokumente auf den tatsaechlichen Stand gebracht.

**Was Codex gefunden hat:**

| Aspekt | Vorher (Doku) | Tatsaechlich (Code) |
|--------|--------------|-------------------|
| ZUSTAND.md Version | v1.0.0 | v0.11.0 |
| Jobquellen | "8 Portale" | 9 (freelance_de.py fehlte ueberall) |
| Tests | 65 / 85 / 100 (je nach Datei) | 108 |
| Schema | v2 | v8 |
| Tools | 21 | 44 |
| Prompts | 8 | 12 |
| Tabellen | 13 | 15 |

**Was Claude Code gefixt hat:**
- **ZUSTAND.md** komplett neugeschrieben (war seit v1.0.0 nicht aktualisiert)
- **README.md** — 9 Jobquellen, 108 Tests, `freelance_de.py` im Architekturdiagramm, Changelog auf 3 Versionen + CHANGELOG.md-Link gekuerzt
- **AGENTS.md** — 9 Quellen, `freelance_de.py` ergaenzt
- **docs/architecture.md** — 9 Scraper, 108 Tests
- **docs/codex_context.md** — 9 Portale, 108 Tests
- **pyproject.toml** — Version auf 0.11.1

**Neu erstellt:**
- **docs/VERBESSERUNGSPLAN.md** — Priorisierter Plan (Prio 1-3) fuer zukuenftige Verbesserungen (server.py Modularisierung, Service-Layer, Teststrategie)

## [0.11.0] — 2026-03-06

### Neue Features
- **Form-Validierung** (OPT-004): Pflichtfeld-Pruefung in allen Formularen (Client + Server). Visuelle Hervorhebung mit rotem Rand und Fehlermeldung. E-Mail- und Datums-Validierung.
- **Ladeanimationen** (OPT-009): Spinner beim Laden aller Seiten (Dashboard, Profil, Stellen, Bewerbungen). Loading-Zustand auf Submit-Buttons verhindert Doppelklicks.
- **Paginierung Bewerbungen** (OPT-010): Bewerbungs-Tab laed 20 Eintraege pro Seite. "Mehr laden" Button mit Zaehler. API unterstuetzt `limit`/`offset` Parameter.
- **Auto-Apply Extraktion**: `extraktion_anwenden(auto_apply=True)` ist Standard. Daten werden ohne Rueckfragen uebernommen, nur echte Konflikte werden uebersprungen.
- **Standalone-Projekte**: Extrahierte Projekte (STAR-Format) werden automatisch der passenden Position zugeordnet.

### Bugfixes
- **KRITISCH**: Felder (email, phone, address, summary) waren nach Extraktion leer — `summary` fehlte in der persoenliche_daten-Feldliste, und aktualisierte Profile wurden nicht zwischen Schritten neu gelesen.
- Profilname blieb "Mein Profil" statt automatisch auf extrahierten Namen zu wechseln — Default-Name wird jetzt als leer behandelt.
- Projekte bei doppelten Positionen wurden komplett uebersprungen — neue Projekte werden jetzt trotzdem hinzugefuegt.
- Praeferenzen konnten beim Multi-Step-Update ueberschrieben werden — Profil wird nach jedem Schritt neu gelesen.

### Optimierungen abgeschlossen
- OPT-003: Error-Handling (bereits seit v0.10.0)
- OPT-004: Form-Validierung ✓ NEU
- OPT-008: Scraper-Keywords konfigurierbar (bereits seit v0.10.0)
- OPT-009: Ladeanimationen ✓ NEU
- OPT-010: Paginierung ✓ NEU
- OPT-011: Test-Suite (bereits seit v0.10.0, 108 Tests)

## [0.10.5] — 2026-03-06

### Bugfixes
- Markdown-Dateien (.md, .csv, .json, .xml, .rtf) werden als Plain-Text extrahiert

## [0.10.4] — 2026-03-06

### Neue Features
- Feldnamen-Aliase (adresse→address, kurzprofil→summary, etc.)
- Bulk-Import fuer Skills, Positionen, Projekte, Ausbildung
- Feld-Validierung mit Feedback bei unbekannten Feldnamen

### Bugfixes
- Vollstaendigkeits-Check erkennt jetzt address und summary Aliase

## [0.10.3] — 2026-03-06

### Bugfixes
- Dokument-Upload ohne Profil: Auto-Profil wird erstellt
- Verwaiste Dokumente werden automatisch adoptiert

## [0.10.2] — 2026-03-06

### Neue Features
- Smart Next-Steps (kontextabhaengige Empfehlungen)
- Onboarding Dokument-Upload als 3. Wizard-Option
- Actionable Empty States mit direkten Aktionsbuttons
- Clean Shutdown mit atexit/signal-Handlern

## [0.10.1] — 2026-03-06

### Neue Features
- Factory Reset
- Runtime-Log Viewer
- Extraktions-Historie leeren

### Bugfixes
- Profil loeschen repariert (automatischer Wechsel)
- Daten-Isolation zwischen Profilen (profile_id auf jobs/applications)
- Schema v7 → v8

## [0.10.0] — 2026-03-05

### Neue Features
- Onboarding-Wizard (4 Schritte)
- Bewerbungs-Wizard (5 Schritte)
- Gehalts-Schaetzungs-Engine
- Quellen-Banner und Such-Reminder
- Hint-System (per-Hint dismissbar + Expertenmodus)
- Gehaltsfilter und Tooltips

### Scraper-Reparatur
- StepStone, Indeed, Monster: Komplett auf Playwright umgestellt
- XING: Selektoren repariert
- Freelancermap: Playwright-Fallback

## [0.9.0] — 2026-03-04

- Multi-Profil Support
- KI-Features (Interview-Simulation, Gehaltsverhandlung, Netzwerk-Strategie)
- 12 MCP-Prompts
- 44 MCP-Tools

## [0.8.0] — 2026-03-03

- Profil Import/Export (JSON-Backup)
- Dashboard mit 5 Tabs
- 8 Job-Scraper

## [0.7.0] — 2026-03-02

- KI-Features (Fit-Analyse, Profil-Analyse)
- Scoring-Engine

## [0.6.0] — 2026-03-01

- Multi-Profil Unterstuetzung

## [0.5.0] — 2026-02-28

- Dashboard, Bewerbungs-Tracking
- Scraper (Bundesagentur, <FIRMA>)

## [0.4.0] — 2026-02-27

- MCP Server Grundstruktur
- SQLite Database
- Profil-Management

## [1.0.0] — 2026-02-26

- Initial Release
