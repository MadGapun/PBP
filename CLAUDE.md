# PBP — Claude-Code-Memory

Persoenliches Bewerbungs-Portal (PBP): MCP-Server (Python, FastMCP 3.x) +
React-Dashboard (Vite, Tailwind) + SQLite (WAL), gebaut fuer Bewerber ohne
Technikwissen. **Leitlinie des Users: Benutzerfuehrung ist oberste
Prioritaet** — jeder Flow fuehrt zum naechsten logischen Schritt,
Melde-Kultur gehoert zur DNA.

## Aktueller Stand

Nur dieser Abschnitt wird bei einem Release aktualisiert.

- **Stable:** v1.7.143 (`--latest`, 2026-09-30), Linie 1.7; Hotfix-Branches
  `hotfix/v1.7.N` vom letzten 1.7-Tag.
- **Beta:** `main` = 1.8.0-beta.15, Betas sind GitHub-Prereleases. Plugins
  sind externe Prozesse gegen die versionierte Ingest-API, Komponenten sind
  keine Plugins, Pairing statt Discovery (D1–D5 in Plan-Roadmap-v18).
- **Roadmap (Nutzer-Wort 02.10.2026):** 1.8 wird das **Auto-Update-Release**
  (#1093 mit #1131, #1152, #947, #1080 und allem, was die 1.8.0-Betas schon
  geliefert haben); die **ELWOSA-Linie heisst 2.0** (Label `v2.0`, Meilenstein
  `v2.0.0`, 25 Issues, vieles noch Konzept). Wo aeltere Texte „v1.8“ fuer
  ELWOSA- oder Lokale-KI-Themen nennen, ist seit dem 02.10.2026 v2.0 gemeint.
  Einzelheiten: Master-Plan, Abschnitt „Neuzuschnitt 1.8 / 2.0“.
- **Schema:** v48 (Stable) / v52 (Beta).
- **Umfang:** 6086 Tests (main) / 5981 (Stable); 270 MCP-Werkzeuge (main) /
  257 (Stable), Wartungswerkzeuge nur im Expertenmodus; 26 Prompts.
- Fixes, die Stable betreffen, gehoeren in die 1.7-Linie, nicht nur in die
  Beta — die zieht kaum jemand. Schaufenster-Arbeit ist erst beim Nutzer,
  wenn sie auf Stable ist.

## Wo steht was

- `docs/internal/claude-md-archiv.md` — diese Datei bis v1.7.139 woertlich,
  mit allen Stand-Bloecken und MERKE-Punkten; per grep nach Issue-Nummer
  oder `v1.7.NN` suchen.
- `docs/internal/lehren.md` — 42 verdichtete Lehren nach Themen, mit Belegen.
- `CHANGELOG.md` und die GitHub-Releases — was sich wann geaendert hat.
- Master-Plan im Wiki (unten) und Dauer-Issue #675 (DoD).

**Regel:** Stand-Bloecke fuer neue Releases gehoeren in `CHANGELOG.md` bzw.
`docs/internal/lehren.md` (neue MERKE-Punkte als Beleg an eine bestehende
Regel oder als neue Regel), NICHT in diese Datei. Hier wird nur „Aktueller
Stand“ aktualisiert. Zielgroesse CLAUDE.md <= 30 KB;
`tests/test_claude_md_groesse.py` schlaegt bei 35 KB an.

## Die 10 wichtigsten Lehren (Kurzform aus lehren.md)

1. **Eine Frage, eine Funktion** — auch fuer die Eingabe (Kriterien durch
   `fuer_scoring`). Ein Kommentar „dieselbe Logik wie“ haelt nichts
   zusammen (L1–L3).
2. **Unbekannt ist ein eigener Zustand.** Fehlende oder geschaetzte Werte
   duerfen nicht wie unauffaellige wirken; Luecken benennen, nicht fuellen
   (L7–L10).
3. **Wortgrenzen und Schreibweisen:** „ki“ steckt in „Kita“, eine Liste
   findet nur ihre Schreibweise — immer beide Richtungen testen (L5–L6).
4. **Setzer und Leser:** jede Einstellung braucht beide; Rueckgabewerte
   auswerten, ein Fallback speichert nie eine andere Bedeutung (L11–L12).
5. **Gegenprobe:** jeden Mechanismus einmal ausbauen; bleibt alles gruen,
   ist das ein Befund ueber die Tests (L23).
6. **Ein Guard prueft die Bauform und muss aufgerufen werden;** eine
   Kontrolle mit derselben Annahme wie der Schreibvorgang prueft nichts
   (L24–L25).
7. **Messen statt vermuten** — auf einer Kopie, mit genug Stichprobe;
   Berichte und Vorschlaege aus Issues nachmessen, nicht uebernehmen
   (L19–L22).
8. **Volle Suite plus Node-Tests vor jedem Release;** Oberflaeche belegt
   ein Browser-Test, der auf Zustaende wartet, nicht auf Zeit (L28–L31).
9. **Shell-Fallen:** Heredocs verderben Backslashes, `Path.write_text`
   schreibt CRLF, Pipes und `;` verschlucken Fehler — Skripte als Datei,
   Bytes schreiben, Pruefungen als Bedingung (L32–L34).
10. **Stable zuerst, Tag erst nach gruener CI;** Cherry-Picks gegen `main`
    diffen und Signaturen abgleichen (L35–L36).

## ⛔ QA-Isolation (HART)

Der Daten-Isolations-Env-Var heisst **`BA_DATA_DIR`** (nicht
`PBP_DATA_DIR` — ein falscher Name faellt STILL auf die echte AppData-DB
zurueck). Jedes QA-/Test-Skript und jede Fixture assertet nach dem Oeffnen:

```python
os.environ["BA_DATA_DIR"] = tmpdir
# ... importlib.reload(database); db = Database(); db.initialize()
assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
```

NIEMALS MCP-Werkzeuge des laufenden bewerbungs-assistent-Servers fuer Tests
nutzen — sie treffen immer die echte DB. Messungen am echten Bestand nur auf
einer Kopie. Subagenten bekommen diese Regel woertlich in den Auftrag.
(Vorfall 2026-06-10: ein QA-Lauf mit falschem Env-Var-Namen ueberschrieb
das echte Profil.)

## ⛔⛔ Master-Plan zuerst (Single Source of Truth)

Der Master-Plan liegt im Wiki, nicht im Code-Repo:
**https://github.com/MadGapun/PBP/wiki/Master-Plan** — dazu
Master-Plan-Optimierung (Risiken, Reihenfolge) und die Sub-Plaene
`Plan-{Cluster}` auf Issue-Ebene.

**Vor JEDER Aenderung** (Code, Schema, Werkzeuge, Doku, Issues): den Plan
frisch lesen (nie aus dem Gedaechtnis), pruefen ob das Vorhaben als Position
gefuehrt wird (Status und Abhaengigkeiten beachten), sonst zuerst einen
⬜-Stub anlegen.

**⛔ Master-Plan-First:** Vor jedem Code-Change existiert ein Plan-Eintrag,
mindestens ⬜ mit Issue-Verweis. Reihenfolge: Plan-Eintrag → Issue
(PII-Scrub) → Code → Tests → Wiki → Plan auf ✅ → Release. ✅ nur, wenn Code
im Repo, Tests gruen UND Wiki-Eintrag vorhanden; sonst 🟨 oder ⬜. Keine
Ausnahmen, auch nicht fuer Hotfixes (⬜ anlegen, derselbe Commit setzt ✅).
Ein Verstoss wird im naechsten Commit nachgeholt.

**⛔ Wiki-Clone-Regeln:**
- Das Wiki ist ein eigenes Repo (`PBP.wiki.git`), bearbeitet nur im Clone
  `D:\MAD\Documents\Entwicklung\PBP.wiki` — nie in Temp- oder
  Scratchpad-Ordnern (2026-07-14 wurden so 34 Seiten als Loeschungen
  gepusht) und nie ueber die Contents-API des Code-Repos. Vor jedem Edit
  frisch ziehen.
- Vor jedem Commit der Vollstaendigkeits-Guard
  `test $(ls *.md | wc -l) -ge 42 && git add -A && git commit ...` (Zahl bei
  neuen Seiten nachziehen) und der Tabellen-Guard
  `python scripts/masterplan_pruefen.py D:\MAD\Documents\Entwicklung\PBP.wiki`
  (Exit 1 = nicht pushen). Er liest die Statusspalte aus der Kopfzeile und
  den Rest hinter dem letzten Rohr; Backticks schuetzen Rohre in Tabellen
  nicht.
- Reihenfolge ohne Pipe: erst committen, dann `git pull --rebase` (Exit-Code
  lesen), dann pushen. Der Exit-Code einer Pipe ist der des letzten Glieds —
  2026-09-07 lief so ein Commit trotz gescheitertem Pull durch.

## ⛔ Session-Abschluss-Checkliste (DoD) — Dauer-Issue #675

Am Ende JEDER Session durchgehen. Massgeblich ist Issue #675 (bleibt
offen); diese Fassung wird synchron gehalten. Die Liste erweitert sich
selbst: taucht eine neue wiederkehrende Pflicht auf, nimmt Claude Code sie
hier und in #675 auf. Die MCP-Chat-Instanz arbeitet die Liste ab und meldet
Kandidaten, schreibt sie aber nicht selbst fort.

1. **Master-Plan** lesen, neue Themen als ⬜ aufnehmen, Status (🟨/✅)
   nachziehen.
2. **Wiki** nachziehen (`Plan-{Cluster}`, Tab-Seiten, MCP-Tools, FAQ) —
   Clone, vorher Pull.
3. **README** pruefen (Version, Zahlen, Features) und nachziehen.
4. **Issues** mit Ergebnis und Versionsbezug kommentieren und schliessen;
   neue Erkenntnisse als neue Issues (PII-Scrub).
5. **GitHub-MCP** fuer Issue-Operationen; nach `create` immer ein `update`
   mit korrekten Umlauten.
6. **PBP-MCP-Luecken als Issue:** alles, was ueber den PBP-MCP gehen
   muesste und nicht geht (fehlende oder kaputte Werkzeuge, Felder ohne
   Wirkung, nicht ladbare Werkzeuge, jeder Direkt-SQL-Workaround) — der
   MCP-Layer soll die einzige Schnittstelle bleiben (#514).
7. **PII-Sweep ueber neue Artefakte** vor Commit oder Wiki-Push: Tests,
   Docstrings, CHANGELOG und Plan-Seiten auf reale Firmen aus der
   Bewerbungshistorie und Personennamen pruefen (`grep -rni`, Muster in
   `scripts/scrub_pii.py`). Reale Faelle als „Praxis-Fall [Datum]“ mit
   fiktiver Firma dokumentieren.
8. **Checkliste selbst pruefen** (Claude Code): neue wiederkehrende Pflicht
   → hier und in #675 aufnehmen.

8a. **Mehr-Defekt-Issues einzeln abhaken:** vor dem Schliessen jeden
   nummerierten Defekt und jeden AK-Block gegen den Code pruefen (#918 wurde
   mit einem von zwei Defekten geschlossen). Warnsignale: „und“, „zwei“,
   „mehrere“ im Titel, nummerierte AK-Listen.

8b. **Tag nur mit sauberem Baum:** `git status --short` leer, nach dem
   Checkout `git branch --show-current` pruefen, nach dem Taggen
   `git log --oneline -1 <tag>` gegen den erwarteten Commit, dazu der
   Versionsstring — jeweils als `test`-Bedingung in der Kette, nicht als
   Ausgabe (v1.7.129 landete so auf main). Ein gescheiterter Checkout laesst die Kette sonst auf dem falschen
   Branch weiterlaufen. Ein Tag ohne Release laesst sich korrigieren
   (`push :refs/tags/X`, `tag -d`, neu setzen) — mit Release ist die Nummer
   verbrannt.

8c. **Ein Schutz zaehlt erst, wenn er aufgerufen wird:** nach jeder
   Aenderung an Guard, Hook oder Test pruefen, ob er in der echten Umgebung
   laeuft. Matcher gegen echte Werkzeugnamen testen (der PII-Hook hatte
   keinen MCP-Matcher, fuenf Issues gingen durch), Tests einmal aus einem
   fremden Arbeitsverzeichnis laufen lassen, Pfade relativ zur Testdatei,
   keine Dateien aus gitignorierten Ordnern wie `.claude/`, und zu jedem
   Guard ein Test seiner Registrierung. Gruen im Repo-Wurzelverzeichnis ist
   kein Beweis.

8d. **Vor dem Anlegen pruefen, ob es das schon gibt:**
   `ls services/ | grep <stichwort>` vor jedem neuen Modul, jeder Tabelle,
   jedem Werkzeug, und die Antwort des Schreibwerkzeugs lesen („updated“
   statt „created“ heisst ueberschrieben; #986 wurde so geloescht, Lehre
   aus #799). Bei aehnlichen Namen die Abgrenzung in beide Modulkoepfe und
   ein Test, dass beide existieren.

8e. **`INSERT OR REPLACE` loescht Spalten ausserhalb der Liste:**
   `save_jobs` schreibt so, und ein Suchlauf loeschte still gelesene
   Urteile (#1007, #913, #948). Neue Spalten von `jobs` gehoeren in
   `_BEWAHREN`; ein Test haelt jede Spalte gegen die INSERT-Liste.

8f. **Erst messen, dann reparieren (seit 2026-10-02):** in #1154 stand
   als Ursache der langsamen Stellenliste "das Lesen der Anzeigentexte".
   Ein `cProfile`-Lauf zeigte: das Lesen kostet 0,1 s; die Last waren
   2,4 Millionen Aufrufe von `normalize_company`. Vor jeder Tempo-Arbeit
   EIN Profil des Aufrufs; zum Fix gehoert ein Messtest mit Grenzwert auf
   grosser Testdatenbank (isolierte `BA_DATA_DIR`), Zahlen vorher/nachher
   in CHANGELOG und Issue.
8g. **Eine Erfolgsmeldung braucht eine Probe (seit 2026-10-02):** "Sicherung
   erstellt" (eine `copy`-Kopie ohne WAL), "PBP laeuft bereits" (der Port
   war nur BELEGT), "[OK] Claude gefunden" (der Rueckgabewert des
   Einrichtungs-Skripts) trugen ein ungeprueftes Ergebnis (#1149). Eine
   Meldung wie "erstellt", "laeuft", "gefunden" steht erst nach einer Probe
   des INHALTS: die Sicherung wird gelesen, `/api/health` muss `pbp_version`
   liefern. Ein Skript, das ohne Fehler endet, hat nicht bewiesen, dass es
   etwas getan hat.

9. **Firmennamen-Sweep ueber GitHub:** reale Firmen aus der
   Bewerbungshistorie stehen NIRGENDS auf GitHub — Issues samt Kommentaren,
   Release-Notes, Wiki, Commit-Messages; das gilt fuer alle Instanzen,
   auch die MCP-Chat-Seite.
   - Vor JEDEM ausgehenden Text (`gh issue|pr|release create/comment/edit`,
     Kommentar, Fehlerbericht): `issue_text_pruefen(text=...)` (MCP, #946 —
     sucht die Namen aus dem eigenen Bestand; bei Treffern mit
     `anonymisieren=True` erneut und NUR den zurueckgegebenen Text
     verwenden; die Zuordnung bleibt lokal, nie in Export oder Telemetrie)
     UND `python scripts/scrub_pii.py --check`. Auch Tabellen und Beispiele
     aus der eigenen DB (so kamen am 23.07. acht reale Firmen in #763/#766).
   - Mechanisch abgesichert: PreToolUse-Hook `scripts/gh_pii_guard.py`
     (`.claude/settings.json`) fuer den Bash-Weg (Argumente,
     `--body-file`, Heredocs) UND schreibende MCP-Aufrufe;
     Tests `tests/test_gh_pii_guard_mcp.py`. Eine Regel, an die man sich
     erinnern muss, ist keine Kontrolle. Seit v1.7.148 (#1137) liest der
     Hook die Kommandozeile STRUKTURIERT (Unterbefehl und Schalter statt
     eines festen Wortlauts: auch `gh -R <Repo> issue ...`, `issue close
     --comment`, `pr review/merge --body`, `gist create`, `api -F`) und
     BLOCKIERT einen Text, den er nicht pruefen kann (Variable, Pipe,
     Unterbefehl, `$(cat ...)`); feste Variablen und `cd` im selben Kommando
     setzt er selbst ein. Titel und Dateipfade deshalb als feste Texte
     angeben. Tests: `tests/test_v17148_gh_waechter_1137.py`.
   - Am Session-Ende neue und geaenderte Issues gegenpruefen;
     `scripts/gh_pii_sweep.py` ist das Netz fuer den Altbestand und liest
     seit v1.7.148 ALLE Veroeffentlichungen (Abbruch mit Exit 3 an einer
     Abfragegrenze statt „sauber“).
   - PII auf GitHub: Issue LOESCHEN (GraphQL `deleteIssue`), nicht
     editieren — die Edit-History behaelt das Original.
   - Ausnahmen: Portale und Vermittler als Quellen-Schluessel, fiktive
     Firmen (`FIKTIVE_FIRMEN` in `scrub_pii.py`; neue Platzhalter dort
     eintragen). Beim Haerten von Erkennungsregeln beide Richtungen testen —
     ein Pruefer mit Fehlalarmen wird ignoriert.

## Issue-Erstellung — DSGVO-Pflicht

**Kein Issue enthaelt Personen-, Firmennamen oder Kontaktdaten** — auch
nicht in Repro-Beispielen, Bug-Beschreibungen oder Testdaten. Issues sind
oeffentlich, ein Verstoss ist DSGVO-relevant fuer den User UND fuer Dritte.
Gilt fuer `gh` im Code wie fuer Claude-Chat-Instanzen.

```bash
python scripts/scrub_pii.py --check < issue_body.md   # exit 0 sauber, 1 Treffer
```

Programmatisch: `from scripts.scrub_pii import scrub_text, find_pii`.
Ersetzungen: User → `<USER>`, Dritte → `<PERSON>`, Firmen → `<FIRMA>` (nicht
durchnummeriert; stabile Platzhalter liefert `issue_text_pruefen`), echte
Mail → `<email-anonymisiert>`, Telefon → `<telefon>`. Erlaubt bleiben
interne IDs und Hashes, `MadGapun`, generische Branchen, Test-Mails wie
`test@example.com` und Indizes ohne konkrete Firma.

Anonymisieren der aktuellen Fassung macht die Edit-History nicht
ungeschehen. Bei echter PII hilft nur Loeschen — das verbrennt die Nummer,
loescht alle Kommentare und macht Verweise in CHANGELOG und Code tot. Im
Zweifel loeschen; besser: vor JEDEM Anlegen pruefen (Mai 2026 mussten ~155
Bodies nachtraeglich anonymisiert werden).

## Auto-Update (#1093, ab v1.8.0)

Aufbau unter Windows: `%LOCALAPPDATA%\BewerbungsAssistent\app\` mit `python\`, `boot\`, `versions\<fassung>\`
(`src\`, `start_dashboard.py`, `_selftest.py`, `manifest.json`, Marke `.fertig`, optional `site\`),
`aktuell.txt`, `update_status.json`, `update\` (Arbeitsordner) und `update.sperre`. Claude Desktop startet
`python -m bewerbungs_assistent_boot`, die Desktop-Verknuepfung `app\start_dashboard.py` (unveraenderlicher
Starter). Der Startbaustein (nur Standardbibliothek) waehlt `aktuell.txt`, setzt `sys.path`, `PBP_APP_DIR` und
`PBP_FASSUNG`, markiert die Belegung (`.in_benutzung\<pid>.json`) und fuehrt per `runpy` aus.

- **Der Vertrag des Startbausteins ist eingefroren** (`FORMAT = 1`). Er aendert sich nie von selbst: jede Aenderung
  an `src/bewerbungs_assistent_boot/` braucht ein neues `FORMAT`, das Manifest-Feld `boot_format` und den Installer.
- **Rueckfall:** harter Fehler vor `bereit_melden()` -> im selben Prozess auf die vorige Fassung (ein Rueckfall je
  Start); weicher Fehler -> zwei unbestaetigte Starts (je aelter als 90 s) -> Rueckfall beim naechsten Start.
  `SystemExit` loest nie aus.
- **Sicherheit:** feste GitHub-Quelle im Code (`services/auto_update/quelle.py`), nur stabile Fassungen der eigenen
  Linie, `SHA256SUMS` Pflicht, Signatur (Ed25519, reines Python) Pflicht, sobald `schluessel.py` Schluessel enthaelt;
  eigenes sicheres Entpacken, Manifest-Pruefung, Selbsttest der neuen Fassung VOR dem Umschalten, `aktuell.txt` zuletzt.
- **Stufen** (`auto_update_stufe`): aus (Vorgabe) | hinweis | auto_meldung | auto_still. Die Automatik laeuft nie
  neben anderer Hintergrundarbeit; Claude-Werkzeuge verlangen `bestaetigt=True`.
- **Schema-Schutz** (`services/schema_schutz.py`): ist die Datenbank neuer als das Programm, weist der alte Prozess
  MCP-Werkzeuge (ausser einer Liste) und schreibende REST-Aufrufe ab (503).
- **Gegenprobe:** `scripts/mutationstest_auto_update.py` (in einem EIGENEN Arbeitsbaum) macht je eine Schutzpruefung
  wirkungslos; die Tests muessen rot werden. Nach jeder Aenderung an den geprueften Dateien laufen lassen. Stand
  02.10.2026: 91 von 92 erkannt, 1 begruendet gleichwertig. Gruen im Repository ist kein Beweis, dass ein Schutz greift.
- MERKE: Windows-Anonym-Pipes fassen nur 4 KB. Ein Test, der den Server mit `subprocess.PIPE` startet, MUSS stderr
  mitlesen (Thread), sonst haengt er an den ~6 KB, die eine frische Datenbank protokolliert.

## Release-Workflow (Pflicht)

1. **Version** an drei Stellen: `pyproject.toml`,
   `src/bewerbungs_assistent/__init__.py`, `frontend/package.json`.
2. **Schema** nur additiv (ALTER/CREATE, keine Daten-Migration). Neue
   Tabellen und Spalten als idempotentes Safety-Net in `initialize()` ohne
   Bump (Muster seit v1.7.10, damit beide Linien dieselbe DB lesen); steigt
   doch `SCHEMA_VERSION`, neue Spalten in `_migrate` UND `SCHEMA_SQL`. Eine
   neue Tabelle braucht einen Loeschbereich (#1025-Guard).
3. **Tests gruen:** volle Suite plus alle Node-Tests
   (`frontend/src/lib/*.test.mjs`, eigene CI-Schritte).
4. **Frontend:** `cd frontend && pnpm exec vite build`; gebaute Assets unter
   `src/bewerbungs_assistent/static/dashboard/assets/` committen, alte
   Hash-Dateien `git rm`.
5. **CHANGELOG.md:** neuer Eintrag GANZ OBEN (Added/Changed/Fixed), am Ende
   IMMER der Pflicht-Block unten — mit der Versionsnummer DIESES Releases.
5a. **Update-Archiv (nur stabile Releases, ab 1.8.0):** nach dem Tag
   `python scripts/build_update_archive.py --ref vX.Y.Z --ausgabe dist [--schluessel-datei <geheimer Schluessel>]`,
   dann `pbp-update-X.Y.Z.zip`, `SHA256SUMS` (und `SHA256SUMS.sig`, sobald Schluessel im Code stehen) an die
   GH-Release haengen (`gh release upload`). Fehlen die Dateien, meldet PBP „Update noch nicht bereit“ — kein Schaden,
   aber kein Auto-Update. `release_check.py` Schritt 7 baut das Archiv vorab aus dem Arbeitsbaum.
6. **Pre-Release-Pause:** vor dem Commit Risiko je Issue (was kann brechen,
   was ist additiv) und nochmal testen (vom User eingefordert).
7. **⛔ Pre-Release-Issue-Check:** UNMITTELBAR vor `gh release create` die
   offenen Issues abrufen
   (`gh issue list --state open --json number,title,createdAt,labels --limit 30`)
   und mit den adressierten abgleichen. Gehoert ein neues Issue in diesen
   Release, zurueckhalten und mitnehmen — lieber 5 Minuten warten als
   nachschieben (beta.81 ging ohne #664 raus).
8. **⛔ Tag erst NACH gruener CI:** Release-Commit pushen, den Lauf abwarten
   (`gh run watch`), erst dann Tag, Push und GH-Release. Native
   Abhaengigkeiten verhalten sich je Plattform verschieden (beta.0:
   PDFium-Segfault nur auf dem Linux-Runner). `tests.yml` laeuft nur auf
   main und PRs — Hotfix-Branches per `gh workflow run tests.yml --ref
   <branch>`. `release_check.py` (Repo-Root) prueft Versionen, CHANGELOG-Kopf
   und README. **„Abgebrochen“ ist weder gruen noch rot (#1132):** endet ein
   Lauf am Zeitlimit, meldet er keinen Fehler, und die Ueberwachung der
   Claude-App wird davon nicht wach. Vor dem Tag den Ausgang des Laufs
   ausdruecklich lesen (`gh run view <id> --json conclusion`); bei
   `cancelled` neu starten und abwarten, nie taggen, weil die Suite „ja
   durchgelaufen ist“.
9. **Erst nach OK des Users** committen, taggen, pushen, Release erstellen.
   `--latest` traegt nur die 1.7-Linie; Betas sind Prereleases.

## GitHub-Release-Notes — Pflicht-Block

**Jeder GitHub-Release enthaelt die volle Installationsanleitung in den
Notes selbst**, nicht nur einen Link aufs CHANGELOG — viele Anwender landen
auf dem Release und wissen mit „Source code (zip)“ nichts anzufangen.
Derselbe Block steht am Ende jedes CHANGELOG-Eintrags. Vorlage (am Ende der
Notes einfuegen, `X.Y.Z` ersetzen):

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
git clone --branch vX.Y.Z --depth 1 https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
\`\`\`

`vX.Y.Z` ist die Version DIESES Releases. Ohne `--branch` klont man `main` —
das ist die Beta, nicht die stabile Version (#1150).

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)
```

## GitHub CLI und Tags

- **Token-Falle:** vor jedem `gh`-Aufruf `unset GITHUB_TOKEN` — sonst nutzt
  `gh` ein Env-Token mit engen Scopes statt des Keyring-Tokens:
  `unset GITHUB_TOKEN; gh release create vX.Y.Z --title "..." --notes-file ... --latest`
- **Tag-Lock:** ein Release ist an seinen Tag gebunden und laesst sich nicht
  neu erstellen, nur editieren (v1.6.0/v1.6.1 verbrannt). Vor `git tag`
  sicher sein (Frontend gebaut, Tests gruen, CHANGELOG aktuell); bei einem
  kaputten Release eine neue Patch-Version, nicht den Lock loesen.
  **Nie `git push --tags`** (schiebt Alt-Tags mit und scheitert an den
  Repo-Regeln), immer gezielt: `git push origin <branch> vX.Y.Z`.

## Bericht-Designprinzip

Kennzahlen, deren Datenbasis nicht ALLE beitragenden Pfade abdeckt, kommen
nicht in den Bewerbungsbericht — lieber eine Sektion weglassen als eine
irrefuehrende Zahl drucken. v1.6.8 entfernte „Aktive Filter-Arbeit“,
„Geschaetzter Zeitaufwand“ und „Bewerbungs-Trichter“, weil Bewerbungen auch
per Direct-Add aus dem Chat entstehen und der Aufwand Groessenordnungen
unterschaetzt war.

## Anti-DB-Bypass (#514)

Claude schreibt NIE direkt in die SQLite (`pbp.db`), auch nicht ueber
Filesystem-, sqlite- oder Desktop-Commander-Werkzeuge. Alle Mutationen
laufen ueber PBP-Werkzeuge (`stelle_einordnen`, `stellen_bulk_bewerten`,
`bewerbung_*` ...), damit Audit, Zaehler, Lerneffekt und Statistik
durchlaufen; Grenzfaelle ueber `pbp_capabilities` und `pbp_grenze_melden`.
Der laufende MCP-Server faehrt die INSTALLIERTE Version, nicht das Repo —
vor Datenaenderungen ueber den MCP pruefen, welche dort laeuft.

## STRENG: Firmen-Status nie aus dem Gedaechtnis (#753)

Faellt ein Firmenname mit einer Wertung („kenne ich“, „war abgesagt“,
„laeuft noch“, „da war ein Interview“, auch beilaeufig in einem Vorschlag),
ZUERST `firma_kontext(firmenname)` aufrufen und NUR auf dessen Ergebnis
antworten. Der Trigger ist der bewertete Name, nicht erst die Statusfrage;
PBP haelt die dokumentierte Wahrheit, Erinnerungen an Bewerbungsverlaeufe
sind regelmaessig falsch.

## STRENG: keine eigenen Ablehnungsgruende (#663)

Beim Aussortieren (`stelle_einordnen(job_hash, 'passt_nicht', grund)`,
alter Name `stelle_bewerten`; `stellen_bulk_bewerten`) NUR Werte aus der
Liste nutzen — nicht kombinieren, eindeutschen, kuerzen oder umschreiben.
Massgeblich ist `verfuegbare_gruende` aus der Werkzeugantwort: die
Standardliste aus `services/ablehnungsgruende.py` (`STANDARD_GRUENDE`) plus
eigene Gruende, die der User in den Einstellungen angelegt hat.

```
zu_weit_entfernt     gehalt_zu_niedrig    falsches_fachgebiet  falsches_system
falsche_branche      zu_junior            zu_senior            unpassendes_arbeitsmodell
firma_uninteressant  zeitarbeit           befristet            bereits_beworben
duplikat             kein_hochschulabschluss                   sonstiges
```

Verboten, weil frei erfunden: z. B. `abgelaufen`, `war_nur_anfrage`,
`windchill_fehlt`, `duplikat_bewerbung`, `teamcenter_fehlt`,
`kein_passendes_projekt` (Systemwerte setzen nur die zustaendigen
Werkzeuge). Unbekanntes wird still zu `sonstiges` normalisiert und
verfaelscht Statistik und Lerneffekt (#648) — im Zweifel `sonstiges` oder
den User fragen.

## Fit-Analyse-Verdict scharf zitieren (#662, #999, #1003)

`fit_analyse` liefert `empfehlung` mit **EMPFOHLEN / BEDINGT /
NICHT_EMPFOHLEN / NICHT_BEURTEILBAR** plus `begruendung` und `kurz` —
direkt zitieren, keine Weichspueler.

- **Der Verdict kommt NICHT aus dem Score.** Die Punkte messen, wie gut
  eine Anzeige die Suchbegriffe trifft; der Lebenslauf geht nicht ein. Ob
  jemand passt, entsteht erst aus dem Vergleich von Profil und Anzeige.
- **`NICHT_BEURTEILBAR` ist der Normalfall**, solange niemand Anzeige und
  Profil gelesen hat: „noch nicht gelesen“, nicht „passt nicht“ (#989). Der
  naechste Schritt ist die Detailanalyse.
- **Gelesen? Urteil zurueckschreiben:**
  `stelle_urteil_speichern(job_hash, urteil, begruendung)` (alter Name
  `stelle_analyse_speichern`) — es haengt an der Stelle und ueberlebt das
  Gespraech. Ein aus dem Score abgeleitetes Urteil waere der Fehler aus
  #1003, nur von Hand.
- **`NICHT_EMPFOHLEN` aus einem k.o.-Kriterium** (Wiedergaenger mit
  fachlichem Grund, ausserhalb des Rechtsraums, kein MUSS-Anker) schlaegt
  auch eine gute Analyse.
- **Der Score ist keine Prozentzahl (#999):** eine Punktsumme, deren
  Obergrenze aus den Kriterien folgt. Nie „X von 100“, nie als
  Passungsaussage; die Bedeutung steht in `services/punkte.py`
  (`SCORE_BEDEUTUNG`) — diesen Satz verwenden.

**EMPFOHLEN**: klare Ansage. **BEDINGT**: Luecke ueberbrueckbar, im
Anschreiben offen adressieren, nicht verstecken. **NICHT_EMPFOHLEN**:
k.o.-Kriterium oder Gap zu gross — nicht weichspuelen; der User darf
trotzdem, die Empfehlung steht. Statt „die Trefferchance ist nicht sehr
hoch“: „Ohne [Skill X] wird diese Stelle nicht antreten.“ Statt „denkbar
mit Anpassung des Anschreibens“: „BEDINGT — Methoden uebertragbar, aber
[Fachbegriff Y] muss im Anschreiben offen erwaehnt werden.“ Statt „lohnt
sich nur bedingt“: „NICHT EMPFOHLEN — [k.o.-Kriterium]. Bewerbung nur bei
Kontakt im Unternehmen.“

## Kritische DB-Helfer

- `db.dismiss_job(hash, reason, herkunft=, notiz=)` — Nadeloehr aller
  Aussortierungen, loest den Hash per `resolve_job_hash` auf. Nie roh
  `UPDATE jobs SET is_active=0 WHERE hash=?`: `jobs.hash` ist mit
  `{profile_id}:` praefixiert, `applications.job_hash` traegt die
  oeffentliche Form (#986).
- `db.update_job(hash, fields)` filtert still per Whitelist (Tupel `allowed`
  in `update_job`; der Name `_ALLOWED_UPDATE_FIELDS` aus frueheren
  Fassungen existiert nicht). Kommt ein neues Feld nicht durch, dort
  ergaenzen.
- `db.close()` nie, solange Hintergrund-Threads laufen (Absturz auf C-Ebene,
  Exit 139); Tests, die Threads starten, joinen sie vor dem Teardown.

## Mojibake-Repair

Doppelt kodiertes UTF-8 (als Latin-1 gelesen) reparieren:
`s.encode('latin-1').decode('utf-8')` (v1.6.4, 47 Stellen in `dashboard.py`).

## Umlaut-Regel (#1087 G66, #1088, #1089)

Sichtbare Texte — Dashboard, Server-Texte, Werkzeugbeschreibungen,
Antworten, Prompts, Server-Anleitung — stehen mit echten Umlauten. **Werte,
die Claude zurueckschickt, bleiben in Umschrift:** Status
(`zurueckgezogen`), Aktionen (`loeschen`), Gehaltsarten (`jaehrlich`),
Werkzeug- und Parameternamen (immer ASCII), Werte-Listen, Schluessel und
gespeicherte Werte. `scripts/ui_texte_pruefen.py` prueft Frontend UND
Server und rechnet die geschuetzten Werte aus dem Code
(`geschuetzte_werte()`). Suchmuster fuer Text von aussen kennen beide
Schreibweisen. Code-Kommentare, Tests, interne Doku und Prompts an die
lokale KI bleiben in Umschrift.

## Elwosa-Pflege (#599)

Elwosa ist die Statusanzeige der lokalen KI in der Seitenleiste
(geschlechtsfrei, britisch-ironisch, lakonisch). Dateien:
`docs/elwosa-character.md` (Charakter und Linienpool),
`services/elwosa_lines.py` (Pool im Code), `services/elwosa.py` (Trigger
und Validator), `tools/elwosa.py` (Werkzeuge fuer Claude — User sprechen
Elwosa nicht direkt an, Claude uebersetzt).

Neue Linien: Doku und `elwosa_lines.py` synchron halten; Sprach-DNA ohne
Ausrufezeichen, Emojis und `Ihre/Ihnen` („Sie“ als 3. Person fuer Firma
oder Recruiter ist erlaubt, Sektion 3 der Charakter-Doku); lakonische
Untertreibung, hoechstens 280 Zeichen; `test_all_pool_lines_pass_validator`
gruen halten. Der Linienpool ist Anzeige (echte Umlaute). Status-Trigger
sind unbegrenzt, Idle/Welt/Tipp folgen dem Frequenz-Regler, Cooldown
(Vorgabe 90 s);
`elwosa_schreiben` validiert den Tonfall.

## Tests (FastMCP 3.x)

`pyproject.toml` verlangt `fastmcp>=3.0,<4`. Tests laufen mit
`.venv/Scripts/python.exe -m pytest`, nie mit `python` aus dem PATH: das
System-Python hat FastMCP 2.12, und die Suite bricht dort mit rund 800
Fehlern ab (27.09.2026), oder sie ist gruen, wo die CI bricht (v1.7.120).
Werkzeug aufrufen:

```python
def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg
```

- **Prompts:** `await prompt.render(args)` liefert ein `PromptResult`; den
  Text aus `r.messages` (`m.content.text`) lesen, das Modell nie direkt
  iterieren.
- **Registrieren:** Module an einem nackten `FastMCP` nur ueber
  `tools.mit_katalog(mcp, db)` — sonst fehlen Tags, Annotations und
  KI-Sperre. Testdoppel fuer `mcp.tool` nehmen `name=` an.
- **Expertenmodus:** Wartungswerkzeuge sind ohne ihn ausgeblendet
  (`get_tool` liefert `None`); die conftest setzt `BA_EXPERTENMODUS=1`, den
  Aus-Zustand prueft ein eigener Fall.
- **Frontend:** Browser-Tests laufen gegen das GEBAUTE Bundle (nach
  JSX-Aenderungen neu bauen); Node-Tests sind eigene CI-Schritte.
