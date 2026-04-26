# Changelog

Alle wichtigen Änderungen am Bewerbungs-Assistent werden hier dokumentiert.

Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Sektionen: **Added** (neue Features), **Changed** (bestehendes geändert),
**Fixed** (Bugs), **Deprecated** (bald weg), **Removed** (weg),
**Known Issues** (bekannt kaputt in diesem Release).

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
  (Niveau 5)" sauber von "Skill X 2020-2022, Prinzip-Verstaendnis bleibt
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
- hays: **50** (42.7s, ok)
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
  beta.16 fuer ferchau/gulp/ingenieur_de eingefuehrt.

### Aktuelle Trefferquote (vorher 7 → jetzt 9 liefernde Quellen)
| Quelle | Treffer (Live) |
|---|---|
| bundesagentur | 600 |
| freelance_de | 60 |
| hays | 50 |
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
- Live-Diagnose 2026-04-25 markiert: ferchau, gulp, ingenieur_de, solcom,
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
nur 4 Quellen (bundesagentur, stepstone, hays, freelance_de) wirklich Treffer
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
  brauchen. Spezial-Adapter (Bundesagentur, Hays, JobSpy,
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
    alte `/jobs/{refnr}`-Route liefert seit Anfang 2026 403.
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
  ("Interim", "Freelance"), und Hays mit Stundensatz. Keywords erweitert um "interim",
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
- **#183:** Fuzzy-Keyword-Matching — Synonyme (PLM→Teamcenter), Umlaute (Luerssen→Lürssen),
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
  Firmenname-Matching mit Teilwoertern und Umlaut-Normalisierung (Luerssen = Lürssen).
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
- **17 Jobquellen** — Bundesagentur, StepStone, LinkedIn, Indeed, Monster, Hays und 11 weitere
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
- **FERCHAU**: Engineering & IT Personaldienstleister. HTML + JSON-LD.
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
  - `test_scrapers.py` (3): Fixture-basierte Parser fuer Hays (Sitemap + JSON-LD),
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
- Scraper (Bundesagentur, Hays)

## [0.4.0] — 2026-02-27

- MCP Server Grundstruktur
- SQLite Database
- Profil-Management

## [1.0.0] — 2026-02-26

- Initial Release
