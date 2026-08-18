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
>
> **Update 2026-07-23:** Die Issues **#763** und **#766** enthielten reale
> Firmennamen aus der Bewerbungshistorie (Stellen-Tabelle) und wurden
> komplett geloescht — Verweise darauf in den v1.7.9-/v1.8.0-beta.8-
> Eintraegen fuehren zu 404. Die Inhalte sind im Master-Plan (B27/C28)
> und in den Eintraegen selbst dokumentiert. Seitdem gilt DoD-Punkt 9:
> Scrub-Pflicht vor JEDEM GitHub-Text, Loeschen statt Editieren.

## [1.8.0-beta.12] - 2026-08-18 — Praxis-Welle 18.08.: Scoring-Wahrheit, stille Haenger, Quellen-Ehrlichkeit (#906-#920)

> **Prerelease der v1.8-Linie.** Identischer Inhalt wie **v1.7.17**
> (Stable, siehe Eintrag darunter) auf der Beta-Codebasis: elf Issues
> aus zwei realen Bewerbungs-Nachmittagen. Schema **v52** unveraendert —
> nur idempotente Safety-Nets (`scoring_config.set_by_user`,
> `jobs.dismiss_note`, vier `scraper_health`-Metadaten-Spalten).

### Fixed
- Scoring-Regler ueber MCP repariert: UPSERT, Aktion `'loeschen'`,
  deterministischer Tie-Break, Dubletten-Migration (#917/A+B)
- Entfernungs-Lerneffekt war invertiert (`'50km'` traf Stellen BIS
  50 km) — Lern-Malus in Stufe `999`, Altzeilen migriert (#917/C)
- Score-Pfade vereinheitlicht: `fit_analyse` wendet Ausschluss-Keywords
  an und matcht notiz-bereinigt; `scores_neu_berechnen` nennt Gruende;
  Notizen-Konvention dokumentiert + Heuristik-Warnung (#917/D)
- Schaetz-Gehalt-Regression in `fit_analyse` (+8 fuer Schaetzungen)
  behoben — beide Pfade neutral (#918)
- "100 EUR/hour" wurde als Tagessatz gelesen; `min_stundensatz` wird
  jetzt ausgewertet (#920)
- Termin-Merge verwirft keine Texte mehr; Master-Wahl nach
  Informationsgehalt (#916)
- Wall-Clock-Budgets (45 s) fuer `meeting_hinzufuegen`,
  `meeting_bearbeiten`, `todo_anlegen`, `dokument_verknuepfen` —
  `status='timeout'` mit Hintergrund-Tasks statt 4 Minuten Stille;
  `pbp_mcp_diagnose` antwortet auch bei DB-Blockade (#915)
- Ablehnungsgrund-Vokabular durchgesetzt: zentrale Normalisierung in
  `db.dismiss_job`, Freitext nach `jobs.dismiss_note`,
  Bestands-Migration mit Bericht; NEU `falsches_system` und
  `falsche_branche` als regulaere Gruende (#913)
- Sidebar-Hoehenkette: genau EIN Scroll-Container (die
  Nachrichtenliste); "X neu"-Button wieder im sichtbaren Bereich (#907)

### Changed
- Lernmodus "schaerfer statt aus": kein automatisches `ignore_flag`,
  gestufte Malusse mit linearer Eskalation (5..155 Nennungen),
  `zu_junior` raus aus der Stellenart-Achse, `falsches_fachgebiet`
  liefert belegte MINUS-Kandidaten via `keyword_vorschlaege()`,
  `set_by_user`-Regler sind fuer die Automatik unantastbar,
  `suchkriterien_setzen` dedupliziert (#908)
- Quellen-Wahrheit: `zugriffsart` je Quelle (api/browser/browser_login),
  Bestaetigungsdialog + "Wartet auf dich" fuer Browser-Quellen,
  Deaktivierungs-Metadaten, Probe hebt erreichbare deaktivierte Quellen
  auf `pruefen`, Warnung bei Stellentyp ohne laufende Quelle (#906)

### Added
- Entfernung-Gehalt-Kompensation: `entfernung_gehalt_kompensation/spanne`
  (Opt-in, Default aus; nie mit Schaetzungen; identisch in allen drei
  Score-Pfaden, Basis/Grad/Gutschrift getrennt ausgewiesen) (#910)

---

## [1.8.0-beta.11] - 2026-08-11 — Grosse Welle: Bedienbarkeit, Elwosa, Scoring, Aufgaben (#768, #797, #809-#816, #822-#828)

> **Prerelease.** `--latest` ist v1.7.12 — dieselben Fixes in der
> Stable-Linie. KEINE Schema-Migration (Schema **v52** unveraendert;
> alle neuen Spalten sind idempotente Safety-Nets). Die groesste
> Einzelwelle bisher: 15 Issues aus dem Praxisbetrieb, davon 6 vom
> selben Vormittag (11.08.).

### Added
- **Aufgaben-Bereich** (#814/#815, D35): eigener Menuepunkt mit
  Gesamtsicht ueber alle drei Toepfe (Todos, Nachfassungen, Termine),
  gruppiert nach Faelligkeit, bedienbar aus der Zeile; Aufgaben OHNE
  Bewerbungsbezug; `todo_bearbeiten`/`todo_hinfaellig`/`todo_details`/
  `aufgaben_uebersicht`; Dashboard-Warnung direkt abhakbar (jetzt **215**
  MCP-Tools)
- **Interview-Nachbereitung vollwertig** (#824, D31): Reflexion im
  Frontend pflegbar (Formular in der Bewerbungs-Timeline), MEHRERE
  Reflexionen je Bewerbung (vorher ueberschrieb Runde 2 die Runde 1),
  Termin-Zuordnung, Teilnehmer als Kontakte am Termin,
  `interview_reflexion_loeschen`, `interview_lehren_auswerten`
  (Antwortarchiv, wiederkehrende Muster mit Fallzahl-Regel, Gefuehl
  gegen Ausgang — Beobachtung, nie Urteil)
- **Vollstaendigkeits-Check Interview-Verfahren** (#825, D32) in
  `pbp_diagnose`: nur-Vermittler-Kontakte, Termin ohne Teilnehmer/
  Reflexion, Bewerbung ohne Kontakt, Gespraech nur in Notizen — kein
  auto_fix, jeder Befund dauerhaft abweisbar (`diagnose_befund_abweisen`)
- **Elwosa-Inhaltskanaele** (#823, F37): Provider-Architektur, Linien
  koennen verlinken (`link_url`/`link_label`), Kanal Changelog (max 3
  Linien je Version), Kanal Betriebslage (Stellen ohne Anker, versiegte
  Quelle, Repost), Feature-Tipps mit geteiltem Dismiss in beide
  Richtungen, Rueckschlag-Sperre (24 h nach Absage keine Scherzlinien)
- **Lose Dokumente auffindbar** (#797, E20): `dokumente_ohne_bewerbung`
  mit drei Verdachtssignalen (Thread-Geschwister, Firmenname, Vorgangs-
  Typ) und Zuordnungs-Vorschlag samt Konfidenz; kaputte Verknuepfungen
  als kritischer Diagnose-Befund
- **Adzuna einsatzbereit** (#809, B31): Keys in Einstellungen >
  Erweiterungen eintragbar, Speichern loest sofort einen Testabruf aus —
  abgelehnte Keys werden nicht gespeichert
- **Blacklist-Pflege** (#828, C33): `aendern`/`deaktivieren`/`aktivieren`
  statt nur loeschen; `entry_id` im Ergebnis; alter Grund bleibt als
  `grund_vorher` nachvollziehbar; Kategorienurteil-Hinweis beim Anlegen
- **Nachfass-Inhalt** (#816, D34): Auto-Nachfassungen tragen
  fallbezogenen Inhalt (Rolle, Firma, Ansprechpartner, Kanal) statt
  leer zu entstehen; `follow_up_bearbeiten` zum Nachtragen

### Changed
- **Elwosa wiederholt sich nicht mehr stuendlich** (#822, F36): der
  Kern-Bug war ein Klassen-Mapping (Limits prueften 'world', gefeuert
  wurde mit 'holiday_summer' — fiel durch ALLES durch). Jetzt harte
  Sperrfristen (Linie 24 h, Art 12 h, Ziehen ohne Zuruecklegen),
  Ambiente-Tageskontingent, Anwesenheitspflicht fuer anredende Trigger,
  Ruhezeit, Ungelesen-Daempfung; `sachlich` wirkt jetzt tatsaechlich
- **Scoring belohnt keine Werbeabsaetze mehr** (#827, C32): Treffer, die
  NUR in der Firmen-Selbstdarstellung stehen, zaehlen 0.25x (belegt:
  fachfremde Rolle mit 30 von 36 Punkten aus dem Portfolio-Absatz);
  MUSS/PLUS-Doppelzaehlung beseitigt; `stellen_anzeigen` liefert die
  Empfehlung mit und laesst NICHT_EMPFOHLEN unter alle Empfohlenen
  sinken (`nur_empfohlen`-Filter); geschaetzte Gehaelter zaehlen
  gar nicht mehr statt 0.5x
- **Offene Aktionen fallbezogen** (#816): ohne je ein Interview keine
  Interview-Workflow-Vorschlaege; Funkstille schlaegt 'abgelaufen' vor
  statt 'zurueckgezogen'; Prioritaeten deterministisch
- **kimeta wird nicht mehr gescrapt** (#810, B32): robots.txt untersagt
  es — Handoff statt Scraping. **GULP** ebenso (#812, B34: SPA ohne
  erreichbare JSON-API)

### Fixed
- **WAL-Hygiene** (#768, A27 — critical): erster wal_checkpoint-Aufruf
  im Code ueberhaupt; close() schreibt die WAL zurueck, die Auto-Engine
  checkpointet je Zyklus, pbp_diagnose macht Blockaden durch
  Zweitprozesse sichtbar (belegt: 3,9 MB / 29 h Rueckstand)

### Offen (naechste Welle)
- #802 Score-Schwelle aus Verteilung, #808 Health-Check inhaltlich,
  #813 Filterstufen-Telemetrie — brauchen Orchestrator-Arbeit mit
  eigenem Anlauf

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein (siehe unten), **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.8.0-beta.11.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.8.0-beta.11.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `dataackups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

## [1.8.0-beta.10] - 2026-08-06 — Stille Ausfaelle: tote Job-API, blockierter Lernmodus, verunglueckte IDs (#790, #796, #799, #804, #807)

> **Prerelease.** `--latest` ist v1.7.11 — dieselben Fixes in der
> Stable-Linie. KEINE Schema-Migration (Schema **v52** unveraendert). Nach dem Update Claude Desktop komplett
> beenden und neu starten.
>
> Der rote Faden dieser Version: **Fehler, die sich als Erfolg tarnen.**
> Eine tote API, die der Health-Check gruen meldet. Ein Lernlauf, der
> taeglich meldet zu laufen und nie ankommt. IDs, die beim Speichern
> still zu Zahlen werden. Nichts davon warf je eine Fehlermeldung.

### Fixed

- **#807 — Bundesagentur-Suche lief ins Leere (der teuerste Fund).** Der
  Adapter fragte `pc/v4/jobs` ab; dieser Endpunkt liefert seit Sommer 2026
  **HTTP 404**. Damit lag ausgerechnet die produktivste Quelle still —
  beim letzten dokumentierten Lauf hatte sie noch 3.732 Rohtreffer und 17
  neue Stellen geliefert. Live geprueft am 06.08.: Suche v4/v5 → 404,
  **v6 → 200**; Details v4 → 200, v5/v6 → 403. Die Suche laeuft jetzt auf
  v6, die Detail-API bleibt bewusst auf v4. Weil v6 saemtliche Feldnamen
  umbenannt hat (`stellenangebote`→`ergebnisliste`, `titel`→
  `stellenangebotsTitel`, `arbeitgeber`→`firma`, `refnr`→`referenznummer`
  …), waere ein reiner Endpunkt-Tausch in einer Liste leerer Stellen
  geendet — schlimmer als ein Fehler, weil es wie ein Erfolg aussieht. Das
  Feld-Mapping ist ergaenzt, die v4-Namen bleiben als Fallback.
  **Verifikation nach dem Umbau: 100 Stellen mit vollstaendigen Feldern,
  0 unvollstaendig.** Der Health-Check probte denselben toten Endpunkt und
  meldete deshalb konsistent dasselbe wie die Suche — beide falsch; er
  zeigt jetzt auf v6, ein Regressionstest haelt beide zusammen.
- **#799 — Lernmodus lieferte dem Nutzer nichts.** Drei Ursachen, alle
  behoben. (1) Der `lernen`-Lauf rief die Pattern-Analyse **synchron im
  Scheduler-Thread** auf, inklusive Ollama-Aufruf (bei kaltem Modell
  50-60 s). Da sich alle Threads EINE SQLite-Connection teilen, zog ein
  haengender Lauf jeden weiteren Zugriff mit — der MCP-Server war komplett
  blockiert, bis hin zur Diagnose selbst. Jetzt laeuft er wie die Jobsuche
  im eigenen Thread mit Eintrag in `background_jobs`; vorher hinterliess
  er nicht einmal eine Spur. (2) **Zwei Tabellen mit fast gleichem Namen:**
  `learned_insights` (aus v1.7.10/#784, leer) neben dem seit #594
  existierenden `learning_insights` (gefuellt). Die UI las die eine, die
  Logik schrieb in die andere. Das war ein Fehler von uns — die Doppelanlage
  wird migriert und entfernt, `learning_insights` gewinnt. (3) Der
  Duplikat-Schutz griff nur bei exakt gleichem Titel und liess deshalb
  dieselbe Aussage mit anderer Prozentzahl erneut durch.
- **#796 — Text-IDs wurden beim Speichern still zu Zahlen.**
  `documents.linked_application_id` hatte in gewachsenen Bestaenden
  INTEGER-Affinitaet. Eine Hex-ID wie `42061e46` ist zugleich eine gueltige
  Zahl in wissenschaftlicher Notation und wurde zu `4.2061e+50`; `1e960980`
  lief sogar zu `inf` ueber. Folge: `dokument_verknuepfen` brach mit
  "FOREIGN KEY constraint failed" ab — und, gefaehrlicher, `inf = inf` ist
  wahr, sodass jede Pruefung per SELECT solche Zeilen als sauber meldete,
  obwohl sie rechnerisch zu **jeder** ueberlaufenden Bewerbung passten.
  Die Heilung laeuft automatisch beim Start: Spalte auf TEXT, Werte gegen
  die echten IDs zurueckuebersetzt (nicht geraten). Nur wo mehrere IDs auf
  denselben Zahlwert fallen, wird die Verknuepfung geleert statt falsch
  belassen. Frische Installationen waren nie betroffen.
- **#804 — Termine lagen doppelt im Kalender.** `meeting_hinzufuegen`
  pruefte nicht, ob fuer dieselbe Bewerbung schon ein Termin im selben
  Zeitfenster liegt — bei Stellen (#670) und Nachfassungen (#665) gibt es
  das laengst. Im belegten Fall ergaenzten sich die beiden Eintraege sogar:
  einer trug den Video-Link, der andere Dauer und Gespraechskontext, keiner
  war vollstaendig, und jede Auswertung zaehlte den Termin zweimal. Neu:
  `wenn_dublette='melden'` (Default), `'zusammenfuehren'` (fuellt nur
  LEERE Felder, ueberschreibt nie gefuellte) und `'trotzdem_neu'`.
- **#790 — Firmen-Blacklist blockte fachlich passende Stellen.** Ein
  Firmen-Block wirkt pauschal, seine Begruendung stammt aber fast immer
  aus der Bewertung EINER Stelle. Bei Personaldienstleistern, die quer
  durch alle Fachgebiete ausschreiben, wirft das die passenden Treffer
  mit weg. Neu: `ausser_wenn_titel_enthaelt` — die Firma bleibt geblockt,
  Rollen mit den genannten Fachbegriffen kommen durch. Wirkt beim Anlegen,
  im Scraper-Pfad und retroaktiv in `blacklist_anwenden`; bestehende
  Eintraege verhalten sich unveraendert.

### Added

- **`termin_dubletten_bereinigen()`** (jetzt **206** MCP-Tools): findet
  Termin-Paare im Bestand und fuehrt sie feldweise zusammen, mit Vorschau.
- **Fuenf regelbasierte Erkenntnis-Arten** (#799), die **ohne lokale KI**
  laufen: dominante Aussortier-Gruende, Kanal-Unterschiede (welcher Weg
  fuehrt wirklich zum Interview), Score-Realitaetscheck (hoher Score
  trotzdem aussortiert), Reaktionszeiten (ab wann ist ein Vorgang
  praktisch tot) und zeitliche Muster. Jede Aussage traegt Evidenz und
  eine Konfidenz aus der Fallzahl; bei duenner Datenlage steht die
  Unsicherheit **in** der Aussage. Ollama darf darueber formulieren, nicht
  darunter. Neu getrennt: `bereich='strategie'` gegen `'bedienung'` — wer
  wissen will, was seine Absagen verbindet, will nicht zugleich lesen,
  dass er viel klickt.
- `erkenntnisse_ableiten()` laeuft mit **Wall-Clock-Budget** und liefert
  bei Ueberschreitung ein gekennzeichnetes Teilergebnis, statt zu haengen.

### Unter der Haube

Neue Services: `spalten_affinitaet.py`, `termin_dubletten.py`;
`lerninsights.py` neu geschrieben. 39 neue Tests, Suite in der Beta-Linie: **2111+ passed**. Zwei Folge-Issues aus dieser Runde: #808 (Health-Check meldet
falsch-gruen, weil HTTP 200 allein nichts ueber Stellen aussagt) und die
Bestands-Frage aus #799 zur Trennung von Lern- und Bedien-Erkenntnissen.

## [1.8.0-beta.9] - 2026-07-24 — Stabilisierungswelle: Kalibrierung, Statistik-Ehrlichkeit, Historie, Lern-Fundament (#774, #778-#784)
---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.8.0-beta.10.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.8.0-beta.10.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.10] - 2026-07-24 — Stabilisierungswelle: Kalibrierung, Statistik-Ehrlichkeit, Historie, Lern-Fundament (#774, #778-#784)

> **Prerelease.** `--latest` ist v1.7.10 — dieselben Aenderungen in der
> Stable-Linie. KEINE Schema-Migration (Schema **v52** unveraendert — die neue `learned_insights`-Tabelle kommt
> als idempotentes Safety-Net ohne Versions-Bump, weil v49 in der
> 1.8-Linie fuer `components` reserviert ist). Nach dem Update Claude
> Desktop komplett beenden und neu starten.
>
> Acht Issues aus den Praxis-Sessions vom 24.07. — alles, was den
> bestehenden Funktionsumfang korrekt und ehrlich macht. Umbauten und
> Automatiken wurden bewusst nach v1.8 verschoben (Label `v1.8` an den
> Issues).

### Added

- **#778 — Scoring-Kalibrierung (C29).** Neues Tool `kalibrierung_backtest()`:
  validiert die aktuellen Suchkriterien gegen die gelabelte Historie
  (Bewerbungen = positiv, Aussortierte = negativ) als reine
  **Schattenrechnung** — es wird garantiert kein Score persistiert.
  Schwellen-Vorschlag = niedrigster Bewerbungs-Score × 0,8 (User-Vorgabe),
  Warnung wenn historische Bewerbungen unter der aktuellen Schwelle laegen
  (die Schwelle darf ausblenden, nie loeschen). Dazu als **Opt-in**
  (`suchkriterien_bearbeiten(kategorie='scoring', aktion='idf',
  werte=['an'])`): IDF-Seltenheitsgewichtung („Digital Transformation" in
  50 % aller Anzeigen zaehlt weniger als ein Nischenbegriff mit 1 %) plus
  Top-5-Deckelung der MUSS-Summe — Masse schlaegt nicht mehr Klasse. Der
  Backtest vergleicht beide Modi (`modus='beide'`). **Einzelgewichte pro
  Keyword** (`aktion='gewichten'`) uebersteuern das Kategorie-Gewicht —
  „Arbeitnehmerueberlassung" kann milder wirken als „Bauwesen". Ausschluss-
  Klassiker bekommen beim Anlegen einen DE/EN-Paar-Hinweis (Praxis-Fall:
  „Working Student" erreichte Score 40, weil nur deutsche Junior-Begriffe
  gepflegt waren). Default-Verhalten ohne Opt-in: exakt wie vorher.
- **#780 — Recruiter-Historie (D28).** `kontakt_historie(suchbegriff)`
  („Hier ist Frau X" → sofort alle Vorgaenge, sucht auch in den
  Freitextfeldern des Altbestands, Teilname genuegt) und
  `vermittler_historie(firma)` (Anfragen, Ausgaenge, Endkunden,
  Ansprechpartner, Zeitraum — „die sechste Anfrage, keine fuehrte zum
  Abschluss" aendert die Reaktion).
- **#783 — Suchperformance (B28).** `suchperformance_auswerten()`: die
  komplette Kette gefunden → aussortiert (Top-Gruende) → beworben →
  Interview/Angebot je Quelle, rueckwirkend aus Bestandsdaten. Die
  Kennzahl ist die **Bewerbungsquote pro Quelle**, nicht die Trefferzahl.
- **#784 — Lern-Fundament (F28).** Tabelle `learned_insights` +
  `erkenntnisse_ableiten(dry_run)` (regelbasiert: dominante Aussortier-
  Gruende, Zeitarbeit-Muster, Hochscore-Fehlleitungen, Kanal-Unterschiede
  — jede Aussage mit Evidenz und Konfidenz aus der Fallzahl),
  `erkenntnisse_anzeigen()`, `erkenntnis_bestaetigen()`. ⛔ Grundsatz:
  **Keine Erkenntnis wird ohne Nutzerbestaetigung wirksam.** Widersprochene
  Aussagen werden nie erneut vorgeschlagen.
- **#774 — Elwosa ueber Claude ansprechbar (F29).** `elwosa_fragen(frage)`
  reicht Fragen an die lokale KI durch — mit PBP-Kontext (Profil-Kurztext,
  Statistik, bestaetigte Erkenntnisse). Elwosa ist auskunftsfaehig, nicht
  urteilsfaehig; Claude kennzeichnet die Antwort als Position. Lokale KI
  nicht erreichbar → ehrliche Meldung, kein stiller Claude-Fallback.
  `elwosa_prompt_kopieren()` zeigt den vollstaendigen Prompt ohne
  Ausfuehrung (Debugging/Prompt-Entwicklung). Dialoge landen in
  `elwosa_messages`.
- **Neuer Status `arbeitgeber_ausgefallen`** (#779): Insolvenz,
  Stellenstreichung, Einstellungsstopp — der Prozess endete ohne Zutun des
  Bewerbers. Zaehlt NICHT in die withdrawal_rate; ein vorher vorliegendes
  Angebot bleibt in der offer_rate (belegter Fall: Angebot lag vor, Firma
  ging insolvent, Statistik zeigte 0 % Angebote und einen „Rueckzug").

### Fixed

- **#779 — Bewerbungen ohne applied_at fielen aus der Statistik (D27).**
  Der intensivste Vorgang des Jahres (drei Gespraeche, Angebot, Insolvenz)
  war unsichtbar, weil bei einem Netzwerk-Kontakt der Status `beworben`
  uebersprungen wurde. Jetzt: Statuswechsel, die eine Bewerbung
  voraussetzen, tragen `applied_at` aus dem aeltesten Timeline-Event nach
  (Hinweis im Tool-Result); `statistiken_abrufen()` weist Ausgeschlossene
  aus statt sie zu verschlucken; `pbp_diagnose(auto_fix=True)` heilt den
  Bestand idempotent.
- **#782 — Repost-Erkennung (C30).** Neu gefundene Stellen werden gegen
  die Bewerbungshistorie geprueft (Firma + Titel-Aehnlichkeit, bewusst
  ohne URL-Vergleich — Reposts haben neue URLs). Warnung in
  `stellen_anzeigen`, `fit_analyse` und `firma_kontext` inkl. Datum,
  Status und ob ein Ablehnungsgrund dokumentiert ist. **Keine automatische
  Aussortierung** — ein Repost kann eine echte zweite Chance sein.
  Dazu: Absage ohne Grund → Rueckfrage im Tool-Result (kein Zwang);
  rekonstruierte Altbewerbungen werden in `bewerbung_details` als solche
  gekennzeichnet (abgeleitet, kein Schema-Feld).
- **#781 — Statistik sagt jetzt, was wirklich passiert ist (D29).**
  `statistiken_abrufen()` liefert `zeitliche_kennzahlen` (Prozessdauer
  nach Ausgang, Reaktionszeit, Zeit bis Interview/Absage — Median UND
  Mittelwert, denn 48-Stunden-Absagen und Vier-Monats-Prozesse sind
  verschiedene Welten), `kanal_auswertung` (Interview-Quote je Kanal)
  und `ablehnungs_kategorien` (still/automatisch/nach Interview/
  Vermittler/extern — die Quote wird um extern bedingte Faelle
  **bereinigt**, denn „Stelle gestrichen" ist keine Ablehnung des
  Bewerbers). Der PDF-Bericht bekommt die Bloecke als eigene Abschnitte;
  Vor-PBP-Zahlen sind als **Untergrenze** gekennzeichnet (rekonstruierter
  Altbestand hat typisch nur 1-2 Events). `pbp_diagnose()` findet
  Gespraeche, die nur im Notizfeld stehen (Muster + Datum, reine Liste —
  bewusst kein Auto-Anlegen).

### Nach v1.8 verschoben (Label `v1.8` + Kommentar am Issue)

- #778 Teil 4 (Kalibrierungs-Schleife in der Automatik), #780 (Auto-
  Kontakt-Anlage + Bestands-Migration), #781 (PDF-Diagramme), #782
  (CV-Text ins Stilarchiv), #783 (search_runs-Tabellen + Query-Ebene —
  die Beta-Linie hat mit `scraper_runs` bereits die Lauf-Historie),
  #784 (LLM-Ableitung, Anbindung an Auto-Aussortierung, Dashboard-
  Kuratierung), #774 (weitere Prompt-Zwecke, Dashboard-Einsicht).

### Unter der Haube

- 9 neue MCP-Tools (jetzt **192**), 46 neue Tests. Suite: **2045 passed,
  1 skipped**. Neue Services: `kalibrierung.py`, `statistik_erweitert.py`,
  `lerninsights.py`, `elwosa_dialog.py`.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.8.0-beta.9.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.8.0-beta.9.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.8.0-beta.8] - 2026-07-23 — Verfolgbarkeit: Link zur Anzeige, Anker-Pflicht, Bestands-Heilung (#763, #764, #765, #766)

> **Prerelease.** `--latest` bleibt v1.7.9. KEINE Schema-Migration
> (Schema **v52** unveraendert) — rein additive Logik plus zwei neue Tools.
> Dieselben Fixes sind als **v1.7.9** in der Stable-Linie erschienen.
>
> **Wichtig nach dem Update:** einmal `stellen_urls_heilen()` und
> `bewerbungs_stellen_abgleichen()` laufen lassen (beide mit `dry_run=True`
> als Default — erst Vorschau, dann anwenden). Bestehende Daten heilen sich
> nicht von selbst.

### Fixed

- **#763 — Such-URLs wurden nicht als solche erkannt, Bestand blieb ungeheilt.**
  Zwei Befunde. (1) `is_search_result_url` uebersah pfadbasierte Such-URLs ohne
  Query-Parameter — darunter ausgerechnet die Form, die PBP in `handoff.py`
  **selbst baut** (`stepstone.de/jobs/{keyword}/in-{ort}`). Fuenf Luecken
  geschlossen (`/jobs`, `/jobsuche`, `/stellenangebote`, `/suche`,
  `/jobsuche/suche` und die StepStone-SEO-Form), ohne dass eine echte
  Detail-URL faelschlich als Suche gilt — die Detail-Marker werden jetzt gegen
  den PFAD statt gegen die ganze URL geprueft, sonst haette
  `xing.com/jobs/hamburg-plm-manager-123456` mitgerissen. (2) Das
  Akzeptanzkriterium AK5 aus #645 (Bestands-Heilung) war nie umgesetzt: der
  Scraper-Fix wirkte nur auf NEUE Laeufe. Neues Tool `stellen_urls_heilen()`
  reklassifiziert `is_search_url` in **beiden** Richtungen (auch zurueck auf 0,
  wenn eine echte Detail-URL nachgepflegt wurde — sonst bleibt
  `stellenbeschreibung_nachladen` dauerhaft blockiert) und traegt bei leerer URL
  eine gezielte Such-URL nach.
  **Ehrliche Grenze:** echte Detail-URLs sind aus dem Bestand NICHT
  rekonstruierbar — die Portal-IDs wurden beim INSERT nie persistiert. Die
  Heilung kann nur korrekt klassifizieren und eine SUCH-URL nachtragen; diese
  wird dann auch ehrlich als solche markiert. Stellen, deren Quelle kein
  Handoff-Template hat, kommen als `nicht_heilbar` zurueck statt still leer zu
  bleiben.

- **#764 — `applications.job_hash` und `application_jobs` liefen auseinander.**
  Belegter Fall: eine Bewerbung wurde von einer veralteten Anzeige auf den
  Repost umgehaengt; die Junction war korrekt, die Legacy-Spalte `job_hash`
  blieb auf der ALTEN Stelle stehen. Die UI liest `job_hash` und zeigte weiter
  die tote Anzeige mit dem alten Score. Ursachen an drei Stellen:
  `link_application_to_job` und `unlink_application_job` zogen die Legacy-Spalte
  nicht mit, und `add_application` legte ueberhaupt keine Junction-Zeile an —
  seit v34 lief die Junction fuer alles strukturell leer, was nicht explizit
  verknuepft wurde. Ab jetzt ist `application_jobs` **fuehrend** und die
  Legacy-Spalte wird synchron gehalten (beim Entknuepfen der primaeren Stelle
  rueckt die naechste Verknuepfung nach, bei der letzten wird geleert statt
  einen verwaisten Verweis zu hinterlassen). Neues Tool
  `bewerbungs_stellen_abgleichen()` heilt den Bestand (fehlende Junction,
  leerer `job_hash`, Divergenz, nicht normalisierte Primaer-Markierung, plus
  verwaiste Junction-Zeilen).

- **#765 — Link zur Original-Anzeige fehlte oder war mehrdeutig.**
  (1) In der Stellendetail-Ansicht fehlte bei leerer URL **kommentarlos** der
  Link. Jetzt gibt es immer eine sichtbare Aussage: Link, oder ein Hinweis,
  dass die URL auf eine Trefferliste zeigt, oder ein Hinweis, dass gar kein
  Link hinterlegt ist — kein stiller toter Link und kein leeres Feld mehr.
  (2) In der Bewerbungs-Timeline standen **zwei Buttons mit identischer
  Beschriftung** „Stellenanzeige öffnen" auf unterschiedlichen URLs, ohne dass
  erkennbar war, welcher der richtige ist. Jetzt: bei gleicher URL genau EIN
  Link; bei abweichender URL beide, aber eindeutig als „Anzeige zum
  Bewerbungszeitpunkt" und „Aktuelle Ausschreibung" beschriftet.

### Added

- **#766 — Anker-Pflicht: keine Stelle ohne Verfolgbarkeit.** Praxis-Fall
  23.07.2026: von acht aktiven Stellen hatte **keine einzige** einen
  nachvollziehbaren Weg zur Original-Ausschreibung. Mehrere davon waren mit
  einer zusammenfassenden **Notiz statt der echten Anzeige** als Beschreibung
  angelegt — ohne URL, ohne Kontakt. Folge: kein Nachladen moeglich, Score
  kuenstlich niedrig, und eine Bewerbung waere nur gegen die Zusammenfassung
  formulierbar gewesen statt gegen die echten Anforderungen.
  Neuer Helper `services/stellen_anker.py`: eine Stelle gilt als verfolgbar,
  wenn sie mindestens **einen** von drei Ankern hat — Detail-URL, verknuepftes
  Dokument mit der Anzeige, oder Ansprechpartner. Eine reine Such-URL zaehlt
  bewusst NICHT, und eine lange `description` auch nicht: genau die
  Claude-Zusammenfassung liest sich wie eine Anzeige, ist aber keine.
  Wirksam an drei Stellen: `stelle_manuell_anlegen` warnt (`anker_warnung`) und
  nimmt neu `kontakt_name`/`kontakt_email`/`kontakt_telefon` entgegen — bei
  Vermittler-Stellen mit unbekanntem Endkunden ist der Recruiter-Kontakt oft
  das Einzige, was es gibt; `stellen_anzeigen` markiert ankerlose Stellen
  sichtbar statt sie wie normale Treffer darzustellen; und `bewerbung_erstellen`
  benennt den Zustand am Uebergang zur Bewerbung mit einem konkreten naechsten
  Schritt. Bewusst **kein harter Block**: die Eingaben zu verwerfen waere
  schlimmer als der fehlende Anker. Die Anker-Pflicht steht ausserdem in der
  Tool-Beschreibung von `stelle_manuell_anlegen`, damit sie modellseitig
  durchgesetzt wird und nicht von der Tagesform abhaengt.

- **Zwei neue MCP-Tools** (jetzt **196**): `stellen_urls_heilen(dry_run=True,
  nur_aktive=True)` und `bewerbungs_stellen_abgleichen(dry_run=True)`. Beide
  idempotent, beide mit Vorschau als Default.

### Changed

- Frontend-Link-Klassifikation (`frontend/src/lib/jobLink.js`) spiegelt
  `is_search_result_url` aus dem Backend; ein CI-Schritt prueft **dieselben
  Faelle auf beiden Seiten**, damit die zwei Implementierungen nicht
  auseinanderlaufen.

### Tests

- `tests/test_v179_url_heilung_763.py` (19), `tests/test_v179_verknuepfung_764.py`
  (9), `tests/test_v179_anker_766.py` (12), `frontend/src/lib/jobLink.test.mjs`
  (22 Faelle). Suite: **2064 passed, 1 skipped**.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.8.0-beta.8.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.8.0-beta.8.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.8] - 2026-07-22 — Hotfix: Ausschluss-K.o. feuerte beim Volltext-Nachpflegen (#762, #761)

> **Empfohlenes Update fuer alle v1.7-Nutzer.** KEINE Schema-Migration
> (Schema **v48** unveraendert) — rein additive Logik. Nach dem Update Claude
> Desktop komplett beenden und neu starten.
>
> **Wichtig nach dem Update:** einmal `scores_neu_berechnen()` laufen lassen.
> Stellen, die durch den Fehlalarm faelschlich auf Score 0 stehen, korrigieren
> sich nicht von selbst.

### Fixed

- **#762 — Ausschluss-Keywords nullten den Score beim Nachpflegen echter
  Anzeigen (Haupt-Bug).** Wer den empfohlenen Weg ging und den Anzeigen-Volltext
  nachpflegte, sah den Score einbrechen (belegt: 59/39/15 -> 0). Ursache war das
  **Fuzzy-Matching der AUSSCHLUSS-Keywords**: bei einem Mehrwort-Keyword
  genuegte, dass dessen Einzelwoerter *irgendwo* im Text vorkommen
  (Multi-Word-Split). Deterministisch reproduziert: Ausschluss „Product Manager"
  feuerte auf einem PLM-Volltext, weil 'product' (in „product lifecycle") und
  'manager' (in „manager der Fachabteilung") in verschiedenen Saetzen standen.
  **Je laenger der Text, desto wahrscheinlicher der Fehlalarm** — also
  ausgerechnet beim Volltext. **Fix:** AUSSCHLUSS matcht jetzt strikt
  (`_strict_keyword_match`: Wortgrenzen + zusammenhaengende Phrase, keine
  Synonym-Expansion) — genau wie MINUS seit v1.7.7 (#755). Der **harte** K.o. ist
  damit nicht mehr lockerer als die **weiche** Abwertung. Echte, zusammenhaengende
  Treffer schliessen weiterhin hart aus.
- **#762 — K.o.-Grund ist sichtbar.** Faellt der Score auf 0, nennt
  `stelle_bearbeiten` jetzt den Grund (welches Ausschluss-Keyword getroffen hat
  bzw. „kein MUSS-Keyword gefunden") statt kommentarlos `neuer_score: 0`.
- **#762 / #761 — `quellen_health_check` reisst keinen MCP-Timeout mehr.**
  Neues hartes Wall-Clock-Budget (`budget_sekunden`, Default 90s) mit
  **Teilergebnis** statt „No result received" nach 4 Minuten; haengende Probes
  werden nicht mehr abgewartet, offene Quellen kommen als `nicht_geprueft`
  zurueck.

### Changed

- **#762 — Kurztext-Scores sind keine fachliche Absage mehr.** Stellen mit nur
  einer Kurznotiz (typisch nach `stelle_manuell_anlegen`) wurden mit kuenstlich
  niedrigem Score als „NICHT_EMPFOHLEN — Gap zu gross" abgeurteilt, obwohl die
  Rolle fachlich passte. `fit_analyse` liefert jetzt `beschreibung_kurz`, die
  Empfehlung sagt ehrlich „Score NICHT belastbar, ausdruecklich **keine**
  fachliche Absage — Volltext nachladen", plus maschinenlesbar
  `score_zuverlaessig`.
- **#762 — `stelle_manuell_anlegen` weist auf die fehlende Detail-URL hin.**
  Ohne URL ist `stellenbeschreibung_nachladen` blockiert — das Tool sagt das
  jetzt beim Anlegen, statt dass man erst spaeter auflaeuft. Zusaetzlich ein
  Hinweis, wenn die Beschreibung zu kurz fuer einen belastbaren Score ist.

### Unter der Haube

Neue Tests: `tests/test_v178_scoring_762.py` (7, inkl. deterministischem
Fehlalarm-Nachweis). Keine Schema-Migration (v48). Dieselben Fixes sind
parallel in der v1.8-Beta-Linie (beta.7).

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.8.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.8.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.8.0-beta.7] - 2026-07-22 — Scoring-Ehrlichkeit: Ausschluss-K.o., Kurztext-Scores, Health-Check-Budget (#762, #761)

> ⚠️ **Pre-Release / Beta.** Stable bleibt **v1.7.7**. **KEINE Schema-Migration**
> (Schema **v52** unveraendert) — rein additive Logik. Nach dem Update Claude
> Desktop komplett beenden und neu starten.

Bugfix-Welle aus dem manuellen Quellen- und Nachpflege-Durchgang vom 22.07.

### Fixed

- **#762.1 — Ausschluss-Keywords: Fehlalarm beim Volltext-Nachpflegen (Haupt-Bug).**
  Nach dem Einfuegen einer echten Anzeige fiel der Score auf 0 (in der Session 3x
  belegt: 59->0, 39->0, 15->0). Ursache war **nicht** der Recompute in
  `stelle_bearbeiten` (der ist korrekt), sondern das **Fuzzy-Matching der
  AUSSCHLUSS-Keywords**: bei einem Mehrwort-Keyword genuegte, dass dessen
  Einzelwoerter *irgendwo* im Text vorkommen (Multi-Word-Split). Deterministisch
  reproduziert: Ausschluss „Product Manager" feuerte auf einem PLM-Volltext, weil
  'product' (in „product lifecycle") und 'manager' (in „manager der
  Fachabteilung") in verschiedenen Saetzen standen. Je **laenger** der Text, desto
  wahrscheinlicher der Fehlalarm — also ausgerechnet beim empfohlenen
  Volltext-Nachpflegen. **Fix:** AUSSCHLUSS matcht jetzt strikt
  (`_strict_keyword_match`: Wortgrenzen + zusammenhaengende Phrase, keine
  Synonym-Expansion) — genau wie MINUS seit #755. Der **harte** K.o. ist damit
  nicht mehr lockerer als die weiche Abwertung.
- **#762.1b — K.o.-Grund ist sichtbar.** Faellt der Score doch auf 0, nennt
  `stelle_bearbeiten` jetzt den Grund (welches Ausschluss-Keyword getroffen hat
  bzw. „kein MUSS-Keyword gefunden") statt kommentarlos `neuer_score: 0`.
- **#762.3 / #761 — `quellen_health_check` reisst keinen MCP-Timeout mehr.**
  Neues hartes Wall-Clock-Budget (`budget_sekunden`, Default 90s, min 5s) mit
  **Teilergebnis** statt „No result received" nach 4 Minuten. Haengende Probes
  werden nicht mehr abgewartet (`shutdown(wait=False)`), offene Quellen kommen als
  `nicht_geprueft` zurueck. Analog zu den Budget-Caps bei
  `stellen_auto_aussortieren` / `stellen_bulk_bewerten`.

### Changed

- **#762.2 — Kurztext-Scores sind keine fachliche Absage mehr.** Stellen mit nur
  einer Kurznotiz (typisch nach `stelle_manuell_anlegen`) wurden mit kuenstlich
  niedrigem Score als „NICHT_EMPFOHLEN — Gap zu gross" abgeurteilt, obwohl die
  Rolle fachlich passte. `fit_analyse` liefert jetzt `beschreibung_kurz`, und die
  Empfehlung sagt ehrlich: „Score NICHT belastbar, ausdruecklich **keine**
  fachliche Absage — Anzeigen-Volltext nachladen". Zusaetzlich maschinenlesbar
  `score_zuverlaessig`.
- **#762.4 — `stelle_manuell_anlegen` weist auf die fehlende Detail-URL hin.**
  Ohne URL ist `stellenbeschreibung_nachladen` blockiert („Stelle hat keine
  URL") — das Tool sagt das jetzt aktiv beim Anlegen, statt dass man erst spaeter
  auflaeuft. Zusaetzlich ein Hinweis, wenn die Beschreibung zu kurz fuer einen
  belastbaren Score ist.

### Unter der Haube

Neue Tests: `tests/test_v18_beta7_scoring_762.py` (7, inkl. deterministischem
Fehlalarm-Nachweis). Keine Schema-Migration (v52). Suite: **2025 passed, 1
skipped**. Hinweis: der OCR-Test braucht das `[docs]`-Extra (`pypdfium2`) —
ohne das Paket meldet `ocr_pdf` korrekt `status=fehler`.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.8.0-beta.7.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.8.0-beta.7.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.8.0-beta.6] - 2026-07-16 — Hotfix: Server-Freeze bei grossen Suchlaeufen (#760)

> ⚠️ **Beta (Prerelease).** Stable bleibt **v1.7.7**. Empfohlenes Update
> fuer alle Beta-Tester — behebt einen kompletten Server-Haenger.

### Fixed

- **#760 — MCP-Server fror bei `jobsuche_starten` mit vielen Quellen ein
  (A23):** Praxis-Fall vom 16.07., lokal reproduziert: Der Such-Thread
  loggt pro Quelle dutzende Zeilen auf stderr. Liest der MCP-Client
  (Claude Desktop) stderr nicht kontinuierlich, laeuft der OS-Pipe-Puffer
  voll — der Log-Aufruf blockiert und haelt dabei den Logging-Lock, an dem
  als naechstes die Tool-Middleware im Event-Loop haengen bleibt: **kein
  Tool antwortet mehr** (auch `pbp_mcp_diagnose` nicht), der Heartbeat
  friert ein, waehrend Dashboard und Datenbank im selben Prozess normal
  weiterlaufen. Reproduktion: mit 35 aktiven Quellen und ungelesenem
  stderr fror der Server nach ~40 s ein; mit gelesenem stderr lief er
  durch (300 s Watch). Fix: Die Console-Ausgabe laeuft jetzt ueber eine
  entkoppelte Queue (`DropOnFullQueueHandler` + `QueueListener` in
  `logging_config.py`) — ist stderr verstopft, werden Console-Zeilen
  verworfen statt den Server zu blockieren; die **Log-Datei
  (`logs/pbp.log`) bekommt weiterhin alles**. Zusaetzlich schreibt die
  Tool-Middleware den Heartbeat jetzt VOR dem Log-Aufruf, damit er selbst
  bei klemmendem Logging Lebenszeichen dokumentiert. Neue Tests:
  `tests/test_v18_logging_backpressure_760.py` (4).

---

## [1.8.0-beta.5] - 2026-07-16 — Welle B: Quellen-Langzeitblick, Browser-Handoff, eigene Karriereseiten (#735, #627, #656)

> ⚠️ **Beta (Prerelease).** Stable bleibt **v1.7.7**. Erste Kern-Welle
> nach den J-Feature-Betas.

### Added

- **#735 — Quellen-Langzeit-Auswertung (B25):** Jeder Suchlauf wird jetzt
  pro Quelle historisiert (`scraper_runs`, Schema **v52**). Das neue Tool
  `quellen_langzeit_auswertung(tage)` beantwortet die Frage „welche
  Quelle bringt mir seit Wochen nichts mehr?": Laeufe, Treffer, NEUE
  Stellen pro Lauf, Fehlerklassen, Trend (versiegt/stabil/steigend) und
  eine klare Empfehlung (behalten / beobachten / deaktivieren+Handoff).
- **#735 — Browser-Handoff fuer blockierte Quellen (B25):** Das erprobte
  `google_jobs_url`-Muster gilt jetzt fuer alle wichtigen Portale:
  `quelle_handoff(quelle, keyword, ort)` liefert eine langlebige
  Such-URL (gulp, kimeta, heise_jobs, StepStone, LinkedIn, XING, Indeed)
  plus ein **DOM-agnostisches Extraktions-JS** — Claude oeffnet die Seite
  im eingeloggten Chrome, zieht die Treffer strukturiert und uebernimmt
  sie per `stelle_manuell_anlegen`. Bewusst KEINE geratenen
  DOM-Selektoren (die dokumentierte B18-Lehre).
- **#627 — Eigene Karriereseiten als Quellen (B16):**
  `custom_quelle_hinzufuegen(name, url)` legt eine Firmen-/Nischenseite
  als Quelle an — PBP prueft die Erreichbarkeit im `quellen_health_check`
  mit und liefert jederzeit den Browser-Handoff. Bewusst **kein
  Auto-Scraping** (Karriereseiten sind zu verschieden fuer stabile
  Selektoren); der Handoff-Weg ist der ehrliche. Dazu
  `custom_quellen_anzeigen` / `custom_quelle_loeschen`. Jetzt 194 Tools.
- **#656 — Browser-Komponente sichtbar (B18, Teilschritt):**
  Playwright/Chromium erscheint als zweite Komponente im
  Erweiterungen-Tab — der Installer liefert Chromium zwar mit, aber wenn
  das fehlschlug oder geloescht wurde, scheiterten browser-gestuetzte
  Adapter bisher STILL. Jetzt: Status sichtbar, Reparatur per Klick
  (`playwright install chromium`). Die portalspezifischen SPA-Adapter
  bleiben bewusst hinter der dokumentierten Bedingung
  (Live-Browser-Inspection statt geratener Selektoren).

---

## [1.8.0-beta.4] - 2026-07-14 — Newsletter-Ingest (J5 #525)

> ⚠️ **Beta (Prerelease).** Stable bleibt **v1.7.7**. Damit sind alle
> vier J-Feature-Betas des Fahrplans geliefert (Plattform → Thunderbird/
> ics → Newsletter).

### Added

- **#525 — Job-Newsletter fliessen automatisch in den Stellen-Pool (J5):**
  Newsletter von StepStone, LinkedIn-Job-Alerts, XING, Indeed,
  Arbeitsagentur, freelance.de und JobLeads werden beim Eingang erkannt
  (Upload, Thunderbird-Add-on oder Watch-Folder — alles laeuft durch
  dieselbe Pipeline) und die enthaltenen Stellen uebernommen:
  **KI-frei** per Link-Extraktion (Job-Detail-URLs + Titel/Firma aus dem
  Linktext, Tracking-Parameter werden fuer die Duplikat-Erkennung
  entfernt); ein optionaler Ollama-Fallback greift nur, wenn die
  Link-Extraktion bei unbekannten Formaten leer bleibt. Die Mail selbst
  wird nach der Uebernahme archiviert. Uebernommene Stellen kommen ohne
  Beschreibung an und greifen nahtlos in die bestehende Kette: als
  „unbewertet" gefuehrt (#756), Beschreibung laedt der Auto-Refetch nach
  (#622), der Volltext wird als Snapshot eingefroren (C23).
- **Lern-Mechanik fuer eigene Quellen (J5.1/J5.2):** Einmal
  `newsletter_quelle_markieren(dokument_id)` — PBP merkt sich
  Absender-Domain + Betreff-Muster (Tabelle `newsletter_sources`) und
  erkennt kuenftige Mails dieser Quelle automatisch. Fuer
  Altbestand/unbekannte Formate: `newsletter_verarbeiten(dokument_id)`.
  Jetzt 189 Tools.

### Changed

- Schema v50 → **v51** (`newsletter_sources`, rein additiv). Neuer
  optionaler LLM-Task `extract_newsletter_jobs` (nur Ollama/Manual —
  die Kernfunktion braucht ihn nicht).

---

## [1.8.0-beta.3] - 2026-07-14 — Thunderbird-Add-on (J2 #478) + Kalender-Export gehaertet (J4.1 #481)

> ⚠️ **Beta (Prerelease).** Stable bleibt **v1.7.7**.

### Added

- **#478 — Thunderbird-Add-on „An PBP senden" (J2):** MailExtension in
  [`plugins/thunderbird-pbp/`](plugins/thunderbird-pbp/) — markierte
  Nachrichten (auch ganze Threads via Mehrfachauswahl, J2.2) per
  **Rechtsklick → „An PBP senden"** an die lokale Ingest-API uebergeben.
  Byte-treuer .eml-Transfer (Umlaute in Headern bleiben heil),
  Options-Seite mit Verbindungstest, klare Fehlerbilder
  (Kopplung fehlt / Key widerrufen / Dashboard aus) als
  Benachrichtigung. Installation ohne Store: Ordner zippen → `.xpi` →
  „Add-on aus Datei installieren" (README mit 4-Schritte-Anleitung).
  J2.3 (Alternativen) war mit dem Watch-Folder aus beta.2 bereits
  geliefert.
- **MCP-Tool `termine_ics_exportieren`** (J4.1/#481): Claude kann den
  Kalender-Export jetzt direkt ausloesen — Datei landet im
  Export-Ordner, Antwort nennt Pfad + Terminzahl (vorher gab es den
  Export nur als Dashboard-Button; DoD-Regel 6: MCP-Luecke
  geschlossen). Jetzt 187 Tools.

### Fixed

- **Kalender-Export RFC-5545-fest (J4.1/#481):** Der seit #310
  existierende `.ics`-Export zerbrach bei Titeln mit Komma/Semikolon
  („Interview, 2. Runde") und bei mehrzeiligen Notizen — jetzt korrektes
  TEXT-Escaping und 75-Oktett-Line-Folding (Kern extrahiert nach
  `services/ics_service.py`, identisch fuer Button und MCP-Tool).
- **#759 — Test-Suite stabil auf langsamen Runnern (A22):**
  Jobsuche-Hintergrund-Threads ueberlebten den Test-Teardown und
  griffen auf die geschlossene SQLite zu (auf Linux-CI sporadisch
  Segfault). Jetzt: benannte `pbp-*`-Threads + pytest-Teardown-Hook,
  der sie VOR dem DB-Schliessen joint; dazu der modul-globale
  Tool-Timing-Ringbuffer im betroffenen Test deterministisch geleert.
  Reine Test-/Infra-Aenderung, kein Laufzeitverhalten betroffen
  (Thread-Namen ausgenommen).

---

## [1.8.0-beta.2] - 2026-07-14 — Ingest-API v1 + Plugin-Pairing (J1 #504) + Volltext-Snapshot (#687/#688)

> ⚠️ **Beta (Prerelease).** Stable bleibt **v1.7.7**. Die Ingest-API v1
> gilt waehrend der Beta als „kann sich additiv aendern" und wird mit dem
> 1.8-Stable eingefroren.

### Added

- **#504 — Ingest-API v1 + Plugin-Pairing (J1):** Externe Programme
  koennen PBP jetzt zuliefern — ueber eine versionierte lokale REST-API
  (`/api/v1/ingest/ping|job|email`, 127.0.0.1, nichts verlaesst den
  Rechner). **Kein Code-Loading**: Plugins sind eigene Prozesse
  (Architektur D1, Sandbox by design). Kopplung per **API-Key-Pairing**
  in den Einstellungen (Erweiterungen → Gekoppelte Plugins): Manifest
  (`pbp-plugin.json` mit `ingest_api: "^1"` + Capabilities) einfuegen,
  Key wird **genau einmal** angezeigt (DB haelt nur den sha256-Hash),
  Widerruf toetet den Key sofort. Zugelieferte Stellen laufen durch
  dieselbe Pipeline wie manuelle (Scoring, Duplikat-Erkennung #641/#317,
  Blacklist, Quelle `plugin:<name>`); E-Mails durch die volle
  Upload-Pipeline (Matching, Termine, Timeline). Neues MCP-Tool
  `plugins_anzeigen` (Diagnose; Kopplung bewusst nur in der UI — der
  Key gehoert nicht in den Chat). Jetzt 186 Tools.
- **Referenz-Plugin „Watch-Folder"** (`plugins/watch-folder/`, J1.6):
  ~150 Zeilen Python-Standardbibliothek — beobachtet einen Ordner und
  uebergibt neue `.eml`/`.msg`-Dateien an PBP. Zugleich der einfachste
  Mail-Zubringer (Thunderbird-Mails per Drag&Drop, J2.3-Alternative)
  und die dokumentierte Vorlage fuer eigene Plugins (README = API-Doku).
- **#687 — Volltext-Snapshot beim Anlegen (C23):** Jede Stelle mit
  brauchbarer Beschreibung bekommt einen **unveraenderlichen**
  `description_snapshot` (+ Quelle/Zeitstempel) — schuetzt vor
  Offline-Gehen der Anzeige und vor Ueberschreiben durch spaetere
  kaputte Refetches. `fit_analyse` faellt automatisch auf den Snapshot
  zurueck, wenn die Live-Beschreibung weggebrochen ist (mit sichtbarem
  Hinweis). Kein Setter kann einen vorhandenen Snapshot ueberschreiben.
- **#688 — Snapshot-Nachhol-Trigger (B24):** Neuer Auto-Engine-Step
  zieht den Snapshot fuer den Bestand nach (deterministisch, DB-only;
  der HTTP-Refetch beschreibungsloser Stellen laeuft weiter im
  #622-Step). Abschaltbar per Setting `auto_snapshot_backfill`.

### Changed

- Schema v49 → **v50** (`plugins`-Tabelle + 3 Snapshot-Spalten auf
  `jobs`, rein additiv). MCP-Tools: 185 → **186**.

---

## [1.8.0-beta.1] - 2026-07-14 — Hotfix: PDFium-Segfault beim OCR-Rendering

> ⚠️ **Beta (Prerelease).** Ersetzt beta.0 (dessen Tag ist gelocked,
> daher neue Nummer). Stable bleibt **v1.7.7**.

### Fixed

- **OCR-Rendering: PDFium-Handles deterministisch freigeben.** Unter
  Linux (und potenziell macOS) segfaultete der OCR-Pfad, weil
  pypdfium2-Page-/Bitmap-Objekte erst vom Garbage Collector NACH dem
  Schliessen des Dokuments freigegeben wurden (Doppel-Free in der
  nativen PDFium-Library; auf dem Linux-CI-Runner als exit 139
  aufgefallen, Windows war tolerant). Jetzt werden bitmap → page →
  document in dieser Reihenfolge explizit geschlossen.

---

## [1.8.0-beta.0] - 2026-07-14 — Komponenten-Framework + Auto-OCR (I10 #751, E19 #750)

> ⚠️ **Beta (Prerelease).** Erster Schritt der v1.8-Linie („Plugin-Plattform
> & Integrationen", Fahrplan im Wiki: Plan-Roadmap-v18). Fuer den Alltag
> bleibt **v1.7.7** der empfohlene Stable-Release (`--latest`). Update von
> 1.7.x: einfach drueberinstallieren; Downgrade zurueck auf 1.7.7 ist
> moeglich (Schema v49 ist rein additiv, Backup entsteht automatisch).

### Added

- **#751 — Optionale-Komponenten-Framework (I10):** PBP kann jetzt
  Zusatzprogramme **on-demand** nachinstallieren — nie automatisch, immer
  mit Groesse, Quelle und Lizenz VOR dem Download. Neuer Settings-Tab
  **„Erweiterungen"**: Status je Komponente (installiert von PBP / extern
  gefunden / nicht installiert), Installation mit Fortschrittsbalken,
  manueller Pfad fuer Offline-Faelle, Entfernen (nur der PBP-Kopie —
  extern installierte Programme werden erkannt, aber nie angefasst).
  Ollama wird dort mit-angezeigt, bleibt aber eigenstaendig verwaltet.
  Unterbau: `components`-Tabelle (Schema **v49**, rein additiv),
  `services/components.py`, REST `GET/POST/DELETE /api/components*`,
  MCP-Tools `komponenten_status`, `komponente_installieren`
  (Zustimmungs-Pflicht via `bestaetigt=True`), `komponente_pfad_setzen`.
  Der Windows-Deinstaller entfernt nachinstallierte Komponenten mit.
- **#750 (Teil 2) — Auto-OCR fuer gescannte PDFs (E19):** Die erste
  Komponente ist **Tesseract OCR** (Apache-2.0, ~55 MB): Zeugnisse und
  Zertifikate ohne Text-Ebene werden beim Upload automatisch erkannt —
  ist die Komponente installiert, laeuft OCR sofort (deu+eng,
  Rotationskorrektur) und der Text landet mit **Provenienz-Header** im
  Dokument; fehlt sie, kommt ein Angebot statt eines stillen Fehlers.
  Neues MCP-Tool `dokument_ocr_ausfuehren(dokument_id)` zieht bereits
  hochgeladene Scans nach. Deutsch-Sprachpaket wird automatisch
  mitgeladen (~2 MB). PDF-Rendering via pypdfium2 (reine
  pip-Dependency) — der tote #192-Fallback (pdf2image/pytesseract,
  brauchte System-Poppler) ist ersetzt.

### Fixed

- **#758 — PII-Altbestand bereinigt (A21):** Reale Firmennamen aus der
  Bewerbungshistorie in Alt-Tests, einem Einweg-Diagnoseskript
  (entfernt), einem CHANGELOG-Alt-Eintrag und einem Code-Kommentar durch
  fiktive Namen ersetzt.

### Changed

- **MCP-Tools: 181 → 185**, neues Tool-Modul `komponenten`. Schema
  v48 → **v49** (`components`-Tabelle). Neue Dependencies (docs-Extra):
  `pypdfium2`, `pillow`.

---

## [1.7.7] - 2026-07-14 — Scoring-Fairness & Praxis-Funde: faire Urteile, ehrliche Firmen-Auskunft (#752-#757, #750)

> **Empfohlenes Update (`--latest`).** Sechs Funde aus einem realen
> Bewerbungs-Nachmittag (13.07.): PBP urteilt jetzt fair — kein k.o. mehr
> durch grobe Aehnlichkeits-Matches, kein Score-0-Fehlurteil ohne
> Stellentext, keine Firmen-Behauptungen aus dem Gedaechtnis. KEINE
> Schema-Migration (v48 unveraendert).

### Fixed

- **#755 — MINUS-Keywords treffen nur noch echte Treffer (C25):**
  Minus-Begriffe matchen jetzt strikt mit Wortgrenzen und als
  zusammenhaengende Phrase — ohne die Synonym-/Teilwort-Aufweichung des
  Plus-Matchings. Vorher konnte ein Minus-Keyword wie „Product Portfolio
  Manager" eine Stelle abwerten, in deren Text nur „product portfolio"
  und „project management" getrennt vorkamen; ein Minus „SAP" traf
  „Aussaat-Planung" nicht mehr. Betrifft `calculate_score` UND
  `fit_analyse` (identische Logik).
- **#754 + #757 (Stufe 1) — Wiedergaenger-Check ist rollen-sensitiv (F25):**
  Drei aussortierte Halbleiter-Fachrollen (Quality/Reliability/Wafertest
  Engineer) machten einen „(Sr.) Project Manager" derselben Firma zum
  Wiedergaenger-k.o. — der Match kam ueber generische Tokens („sr",
  „project"). Jetzt gilt: Fach-Domaenen-Ueberlappung traegt allein (#671
  bleibt: PLM Owner + PLM Manager → PLM Architect ist Wiedergaenger);
  OHNE Fach-Signal zaehlt nur dieselbe Rollen-Familie
  (Manager/Engineer/Entwickler/...). Die Historie anderer Rollen kommt
  als **neutrale `firmen_historie`** mit — ausdruecklich kein k.o., denn
  Aussortier-Gruende gelten je STELLE, nicht fuer die Firma (#757).
- **#756 — Beschreibung zuerst, Score 0 ist kein Urteil (F26):**
  `stellen_auto_aussortieren` legt beschreibungslose Stellen (< 50
  Zeichen) NIE mehr der lokalen KI vor — sie werden als
  `uebersprungen_ohne_beschreibung` ausgewiesen, naechster Schritt
  `stellenbeschreibung_nachladen`. `stellen_anzeigen` markiert Score 0 +
  fehlende Beschreibung als `score_status='unbewertet'` mit Summenzeile.
  Frontend: der „Score unsicher"-Badge greift jetzt auch bei Score 0
  (vorher fielen genau diese Stellen durchs Raster) und heisst dort
  ehrlich „Unbewertet".
- **#752 — Elwosa kennt den Kalender (F27):** Eine Sommer-Linie begann
  hartkodiert mit „August." — mitten im Juli. Der Linien-Pool nutzt
  jetzt den `{monat}`-Platzhalter, ein Guard blockt Linien, die mit
  einem falschen Monatsnamen BEGINNEN (Zukunfts-Bezuege wie „Kommt im
  September zurueck" bleiben erlaubt), und `elwosa_status` zeigt
  `paused_until` nur noch bei tatsaechlich aktiver Pause an.

### Added

- **#753 — `firma_kontext(firmenname)`: Firmen-Status nie aus dem
  Gedaechtnis (H18):** Ein Call liefert den dokumentierten Stand einer
  Firma: Bewerbungen (Status, Datum, Termine), aktive Stellen,
  Aussortierungen mit Gruenden. Hintergrund: Claude behauptete einer
  Firma gegenueber einen Absage-Status, der nie in PBP stand. Die
  PFLICHT-Regel (erst `firma_kontext`, dann antworten) steht jetzt in
  den Server-Instructions, im `willkommen`-Prompt und in CLAUDE.md.
  Teilstring-Suche inkl. Rechtsform-Normalisierung („Acme" findet
  „Acme Solutions GmbH").
- **#750 (Teil 1) — `dokument_text_setzen`: OCR-Text ohne DB-Bypass
  (E18):** Extrahierter Text (z.B. aus einem gescannten Zeugnis via
  Claude-OCR) laesst sich jetzt regulaer nachtragen — mit
  **Provenienz-Pflicht**: die Quelle („OCR via Tesseract 5.4.0, ...")
  wird als Header im Text dokumentiert. Vorher ging das nur per
  Direkt-SQL (Anti-DB-Bypass-Verstoss, #514). Teil 2 (Auto-OCR beim
  Import) ist als E19 fuer v1.8 geplant.

### Changed

- **MCP-Tools: 179 → 181** (+`firma_kontext`, +`dokument_text_setzen`).
  Prompts unveraendert 25, Schema unveraendert v48.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein (siehe unten), **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.7.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.7.zip)
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

## [1.7.6] - 2026-07-03 — Alltags-Fuehrung: Interview-Button, Notizen-Pflege, Lernprotokoll-Steuerung (#706, #707, #689)

> **Empfohlenes Update (`--latest`).** Fuehrung im Bewerbungs-Alltag:
> Der naechste logische Schritt ist jetzt auch NACH der ersten Suche
> immer einen Klick entfernt — und die lokale KI laesst sich vollstaendig
> steuern. KEINE Schema-Migration (v48 unveraendert).

### Added

- **#706 — Interview-Vorbereitung direkt aus der Bewerbung (G16):**
  Bewerbungen im Status `interview`/`zweitgespraech` haben jetzt einen
  Button in der Uebersicht UND in der Timeline: Er kopiert die
  **vorbefuellte** Vorbereitungs-Anleitung (Stelle + Firma bereits
  eingesetzt, keine Rueckfragen) in die Zwischenablage — einfuegen in
  Claude Desktop, fertig. Die Anleitung legt zusaetzlich ein **Todo mit
  Faelligkeit** an (Termin-Datum, falls ein Meeting existiert).
  Unterbau: `/api/workflow-prompt/{name}` reicht optionale Query-Parameter
  an Prompt-Funktionen durch (signatur-geprueft, rein additiv).
- **#707 — Informelle Notizen werden aktiv gepflegt (H15):** Neuer
  Onboarding-Hint auf dem Profil-Tab, wenn die Notizen leer/kurz sind
  (sie speisen Anschreiben-Tonalitaet, Bewertung und Interview-
  Vorbereitung); Hilfetext mit Hover-Erklaerung direkt am Notizen-Feld;
  und die Prompts `ersterfassung` + `willkommen` weisen Claude an,
  nebenbei erwaehnte Praeferenzen/No-Gos/Lebensumstaende SOFORT via
  `profil_bearbeiten(bereich='notizen')` festzuhalten.
- **#749 — Verbindungsstatus direkt auf dem Welcome-Screen (G18):** Der
  frisch installierte User sieht jetzt SOFORT und prominent, ob Claude
  Desktop mit PBP verbunden ist. Gruen: „du kannst direkt loslegen."
  Amber: die exakte 3-Schritte-Anleitung (Claude ueber das Taskleisten-
  Symbol KOMPLETT beenden — Fenster schliessen reicht nicht — neu starten,
  Anzeige wird von selbst gruen) plus „jetzt pruefen"-Button. Vorher war
  der haeufigste Support-Stolperstein nur am kleinen Sidebar-Badge
  erkennbar.
- **#689 (Rest) — Lernprotokoll: stummschalten & zuruecksetzen (F21):**
  Im Lokale-KI-Tab laesst sich jetzt jeder Lern-Eintrag einzeln
  stummschalten und das komplette Protokoll per Doppel-Klick-Bestaetigung
  zuruecksetzen (neuer Endpoint `POST /api/learning/insights/reset` —
  harter Reset, Ollama lernt danach von vorn; Stellen/Bewerbungen bleiben
  unberuehrt). Damit ist F21 (Transparenz + Steuerung der lokalen KI)
  komplett.

### Sonstiges

- **Plan-Hygiene:** Master-Plan-Position C24 (Hochschulabschluss-Malus
  konfigurierbar, #698) war seit beta.107/Schema v48 umgesetzt, stand aber
  noch auf ⬜ — Status nachgezogen.

### Unter der Haube

Geaendert: `dashboard.py` (Query-Args fuer Workflow-Prompts,
Insights-Reset), `tools/workflows.py` (interview_vorbereitung
parametrisiert + Todo-Anweisung, willkommen-Guidance), `prompts.py`
(ersterfassung Regel 6b), `services/onboarding_hints.py` (+1 Hint),
`database.py` (reset_learning_insights), `ApplicationsPage.jsx`
(2 Buttons), `ProfilePage.jsx` (Hint-Banner + Feld-Hilfe),
`SettingsPage.jsx` (Lernprotokoll-Steuerung) + Frontend-Rebuild.
Tests: +12 (test_v176_alltags_fuehrung.py) + beta.76-Hint-Test an neues
Verhalten angepasst. Kein Schema-Bump.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.6.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.6.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.5] - 2026-07-03 — Fuehrung & Pflege: Onboarding-Hints sichtbar, ehrliche Quellen-Diagnose, Umlaut-Restaurierung (#652, #748, #742)

> **Empfohlenes Update (`--latest`).** Rundet die Einsteiger-Welle ab:
> Feature-Hinweise erscheinen jetzt direkt im Dashboard, der Quellen-
> Health-Check meldet nicht mehr falsch-rot, und der Profil-Altbestand
> bekommt seine echten Umlaute zurueck (kuratiert, mit Vorschau).
> KEINE Schema-Migration (v48 unveraendert).

### Added

- **#652 — Onboarding-Hints im Frontend (G11, Rest):** Das Hint-Backend
  existierte seit beta.76, war aber nur per MCP erreichbar — jetzt gibt es
  REST-Endpoints (`GET /api/onboarding/hints?tab=...`,
  `DELETE /api/onboarding/hints/{id}`) und die neue Komponente
  `OnboardingHintBanner` auf Dashboard-, Stellen-, Bewerbungs- und
  Kalender-Tab: kuratierte "Naechster-Schritt"-Tipps mit Hover-Erklaerung,
  „Sag Claude: ..."-Anleitung und persistentem Wegklicken (wirkt auch
  auf das MCP-Tool und umgekehrt). Neuer vierter Hint
  `g11_erste_suche_starten` schliesst die #744-Kette fuer Dashboard-First-
  Nutzer: Profil vorhanden, aber keine Suchbegriffe → konkreter naechster
  Schritt.
- **#742 — Umlaut-Restaurierung Altbestand (A20):** Neues Tool
  `profil_umlaute_reparieren(anwenden=False, bereiche=[])` — ersetzt
  ASCII-Umschreibungen (Mehrjaehrige, Oekosystem, fuer, ...) in Profil-,
  Positions-, Projekt-, Ausbildungs- und Skill-Texten anhand einer
  **kuratierten Positivliste** (~150 Woerter, wortweise, case-erhaltend).
  Sicherheits-Design: legitime ue/ae/oe-Sequenzen (neue, Steuerung,
  Aussage, Queue) bleiben unangetastet, `ss`→`ß` passiert NIE,
  `technologies`-Felder sind ausgenommen, Default ist die Diff-VORSCHAU,
  vor jedem Schreiben entsteht ein JSON-Backup, und alle Writes laufen
  ueber die bestehenden Whitelist-Pfade (Anti-DB-Bypass #514). Ungemappte
  Kandidaten-Woerter werden zur Kuratierung aufgelistet.
  MCP-Tool-Count: 178 → **179**.

### Fixed

- **#748 — Quellen-Health-Check meldet nicht mehr falsch-rot (B13.4):**
  Mehrere Probes wichen vom echten Adapter-Request ab und meldeten
  403/404, obwohl die Scraper liefen: `bundesagentur` bekam keinen
  `X-API-Key`-Header (Adapter sendet ihn), `workable` probte die alte
  v3-API (Adapter nutzt v1-Widget), `personio` probte eine Firma
  ausserhalb der Adapter-Liste. Prinzip jetzt: **Probe == Adapter**
  (URL, Header, Firma) — inkl. neuem `_PROBE_EXTRA_HEADERS`-Mechanismus.
  Die RSS-Probes (berufsstart/studentjob/praktikum_de) waren bereits
  adapter-identisch und bleiben unveraendert: wenn sie rot melden, ist
  der Adapter wirklich betroffen — genau dafuer ist der Check da.

### Unter der Haube

Geaendert: `services/onboarding_hints.py` (+1 Hint), `dashboard.py`
(2 Endpoints), `OnboardingHintBanner.jsx` (neu) + 4 Page-Mounts,
`job_scraper/health.py` (Probe-Header + 2 URLs), `tools/profil.py`
(Umlaut-Map + Tool) + Frontend-Rebuild.
Tests: +30 (onboarding_hints_652, probe_konsistenz_748,
umlaut_reparatur_742). Kein Schema-Bump.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.5.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.5.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.4] - 2026-07-03 — Einsteiger-Welle: gefuehrte Kette bis zur ersten Suche, Ollama-Vorschlaege, Melde-Hilfe (#744, #745, #746, #747)

> **Empfohlenes Update (`--latest`).** Einsteiger werden jetzt durchgehend
> gefuehrt — vom Lebenslauf-Upload bis zur laufenden ersten Stellensuche.
> Die lokale KI (Ollama) uebernimmt mehr Automatik, wo sie installiert ist.
> KEINE Schema-Migration (v48 unveraendert).

### Added

- **#744 — Gefuehrte Einsteiger-Kette (G17):** Der Ersterfassungs-Wizard
  endet nicht mehr nach dem Profil-Review, sondern fuehrt in **Phase 5**
  direkt weiter: Suchbegriffe vorschlagen (`keyword_vorschlaege`) →
  bestaetigen → `suchkriterien_setzen` → erste Suche mit drei schnellen,
  zuverlaessigen Quellen ohne Login (Bundesagentur, Arbeitnow,
  JobSpy-Indeed) → Treffer-Vorschau. Dazu:
  - `keyword_vorschlaege` ist bei leerem Stellen-Bestand keine Sackgasse
    mehr („starte zuerst eine Jobsuche"), sondern liefert Vorschlaege aus
    dem Profil (`profil_vorschlaege`) — lokale KI bevorzugt, sonst
    Jobtitel-/Skill-Heuristik.
  - `jobsuche_starten` empfiehlt bei fehlenden Quellen den Starter-Satz
    (`empfohlene_start_quellen`) und uebernimmt beim allerersten explizit
    gestarteten Lauf die Quellen als aktive Quellen (nie ueberschreibend).
  - **0-Treffer-Diagnostik:** Liefert eine Suche nichts, erklaert das
    Ergebnis-Feld `diagnose`, WARUM (alles schon bekannt / Quellen defekt /
    Fehler+Timeout / Suchbegriffe zu eng) statt nur „0 Stellen".
  - Welcome-Screen: **Lebenslauf-Upload ist jetzt der prominente
    Einstieg** („Profil entsteht automatisch"), Gespraechs-Variante als
    Alternative; Schritt-Karten beschreiben die neue Kette.
- **#745 — Ollama-gestuetzte Vorschlaege (F24):** Neue lokale Tasks
  `EXTRACT_KEYWORDS` und `SUGGEST_JOB_TITLES` (lokal bevorzugt,
  Fallback-Kette wie ueblich). `jobtitel_vorschlagen` kann jetzt OHNE
  uebergebene Titel aufgerufen werden — die lokale KI generiert sie dann
  selbst aus dem Profil (`generiert_von: "lokale_ki"`); ohne Ollama kommt
  ein klarer Hinweis statt eines Fehlers. Antworten kennzeichnen die
  Quelle (`quelle: "lokale_ki" | "heuristik_profil"`). Feature-Gate:
  `ki_features` (stellenanalyse); ohne Ollama exakt bisheriges Verhalten.
- **#746 — Melde-Hilfe (H17):** Neuer Prompt `problem_melden` — Claude
  versucht bei Problemen/Ideen ZUERST eine Sofortloesung (Diagnose-Tools,
  FAQ-Workarounds) und formuliert dann den fertigen, automatisch
  anonymisierten Report-Text zum Einfuegen auf GitHub. Der
  `tipps_und_tricks`-Prompt und das Wiki (FAQ, Erste Schritte) verweisen
  darauf. Prompts: 24 → **25**.
- **#747 — Probe-URLs vervollstaendigt (B13):** `quellen_health_check`
  kann jetzt auch `ingenieur_de` und `ferchau` aktiv proben (die zwei
  Quellen mit URL-Migrations-Historie aus #653); Konsistenz-Tests
  Probe ↔ SOURCE_REGISTRY, defekte Quellen bleiben bewusst ohne Probe.

### Unter der Haube

Geaendert: `prompts.py` (Wizard-Phase 5, problem_melden, Tipps),
`services/llm_service.py` (2 neue TaskKinds + Profil-Kurztext-Builder),
`tools/analyse.py` (Profil-Pfad keyword_vorschlaege), `tools/profil.py`
(jobtitel-Generierung, kennlerngespraech naechster_schritt),
`tools/jobs.py` (Smart-Default-Quellen), `job_scraper/__init__.py`
(zero_treffer_diagnose), `job_scraper/health.py` (2 Probes),
`DashboardPage.jsx` (Welcome) + Frontend-Rebuild.
Tests: +42 (probe_urls_747, ollama_vorschlaege_745, einsteiger_kette_744,
problem_melden_746). Kein Schema-Bump.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.4.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.4.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.3] - 2026-07-02 — Hotfix: Dokument-Matching, STAR-Volltext, Schema-Parity (#743, #741, #738)

> **Empfohlenes Update (`--latest`).** Haertet das Auto-Matching von Mails/
> Dokumenten (keine Fehlzuordnung an abgeschlossene Bewerbungen mehr),
> liefert Projekt-Volltexte fuer bessere Anschreiben und schliesst die
> #737-Restluecke fuer v1.6.x-Neuinstallations-Upgrader.
> KEINE Schema-Migration (v48 unveraendert).

### Fixed

- **#743 — Auto-Matching haengt neue Vermittler-Mails nicht mehr an alte
  Bewerbungen (E17):** Eingehende Mails von Recruiting-Agenturen (gleiche
  Absender-Domain, aber anderer Berater/Endkunde/Thema) wurden mit Konfidenz
  70% an inhaltlich fremde, laengst abgeschlossene Bewerbungen verknuepft.
  Es waren ZWEI Matcher beteiligt, beide gefixt:
  - `auto_assign_document` (Dateiname-Matcher, #177): Auto-Link-Schwelle von
    0.7 auf 0.9 angehoben (Angleich an das #523-Prinzip „im Zweifel
    unverknuepft" — der reine Firmenname-im-Dateinamen-Treffer ist nur noch
    ein Vorschlag) und Bewerbungen mit Archiv-Status (abgelehnt/
    zurueckgezogen/abgelaufen) werden NIE mehr auto-verknuepft. Bei gleicher
    Konfidenz gewinnt jetzt die aktive Bewerbung.
  - `match_email_to_application` (E-Mail-Matcher, #523): Archiv-Bewerbungen
    matchen nur noch bei exakter kontakt_email; teilen sich mehrere
    ZULAESSIGE Bewerbungen denselben Domain-Treffer, entscheidet
    ausschliesslich ein inhaltliches Signal (Ansprechpartner/Stellentitel/
    kontakt_email) auf genau EINER Kandidatin; bekannte Vermittler-Domains
    (Hays, SThree, Randstad, ...) matchen nie ueber die Domain allein.
    Eine alte abgelehnte Bewerbung derselben Firma blockt den einzigen
    aktiven Kandidaten dabei NICHT (Fund des adversarialen Reviews).
  - `analyse_plan_erstellen` (#686) markiert Zuordnungsvorschlaege auf
    abgeschlossene Bewerbungen jetzt mit einem `achtung`-Warnhinweis.
  - Bereits falsch verknuepfte Dokumente werden NICHT automatisch
    aufgeraeumt — manuelle Korrektur via `dokument_entverknuepfen`.
  - Regression abgesichert: Absage-/Update-Mails an noch AKTIVE Bewerbungen
    matchen weiterhin (auch von Vermittler-Domains, sofern der Stellentitel
    im Betreff steht).
- **#737-Restluecke — Statistik-Crash auch fuer v1.6.x-Neuinstallations-
  Upgrader behoben (Fund des neuen Schema-Parity-Tests):** Das
  v1.6.x-SCHEMA_SQL enthielt `applications.is_imported` nicht. Wer v1.6.x
  FRISCH installiert hatte und auf v1.7.x upgradet, startete mit
  schema_version 31 — die v22-Migration lief nie mehr, die Spalte fehlte
  weiter und `/api/stats/extended` crashte trotz v1.7.1-Hotfix mit HTTP 500.
  Fix: idempotentes Safety-Net in `initialize()` zieht die Spalte beim
  ersten Start nach (Muster wie `is_pinned`).

### Added

- **#741 — Neues MCP-Tool `projekte_anzeigen` (H16):** liefert ALLE Projekte
  mit ungekuerzten STAR-Feldern (situation/task/action/result), Beschreibung,
  Rolle, Zeitraum, Technologien und Projekt-IDs (die `profil_bearbeiten`
  braucht). Hintergrund: `profil_zusammenfassung` kuerzt description/result
  auf 100 Zeichen und laesst situation/task/action ganz weg — Modelle, die
  Anschreiben/CV formulieren, hatten keinen Zugriff auf die vollen, mit
  Zahlen belegten Projektbeschreibungen. `customer_name` wird bei
  `is_confidential` maskiert (wie in den Exporten, #246).
  `profil_zusammenfassung` bleibt als Kurzuebersicht erhalten (Kuerzungen
  jetzt mit `…`-Marker) und verweist auf den Volltext-Weg; die Prompts
  `bewerbung_schreiben`, Interview-Vorbereitung/-Simulation und der
  Bewerbungs-Workflow rufen das Tool jetzt explizit auf.
  MCP-Tool-Count: 177 -> **178**.
- **#738 — Generischer Fresh-Install-Schema-Parity-Test (A19):**
  `tests/test_schema_parity_738.py` macht die #737-Fehlerklasse (Spalte per
  Migration, aber nicht im CREATE TABLE) zur CI-Pflicht: (1) Doppel-
  Migrations-Trick — die komplette idempotente Migrationskette darf auf
  einer frischen DB nichts mehr anlegen; (2) echte v1.6.10-DB (Fixture aus
  der Migrations-Generalprobe #705) hochmigrieren und spaltenweise
  zweiseitig gegen einen Fresh-Install vergleichen; (3) Selbsttest: eine
  kuenstlich entfernte CREATE-TABLE-Spalte wird nachweislich erkannt.
  Die #705-Fixture wurde dabei gegen das ECHTE v1.6.10-Schema aus der
  Git-Historie korrigiert (blacklist.reason, dismiss_reasons.id/usage_count,
  application_meetings-Spalten, scoring_config.id; applications bewusst
  ohne is_imported — originalgetreu inkl. der historischen Luecke).

### Unter der Haube

Geaendert: `database.py` (auto_assign_document, is_imported-Safety-Net),
`services/email_service.py` (Matcher-Umbau + Vermittler-Domain-Liste),
`tools/dokumente.py` (Analyse-Plan-Warnung), `tools/profil.py`
(projekte_anzeigen + Kurz-Marker), `prompts.py`/`tools/workflows.py`
(Prompt-Guidance), Tests (+33: matching_743, projekte_anzeigen_741,
schema_parity_738). Kein Frontend-Change, kein Schema-Bump.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.3.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.3.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.2] - 2026-06-18 — Hotfix: Windows-Deinstaller-Haertung (#739)

> **Hotfix fuer v1.7.x (Windows).** Empfohlen, falls die Deinstallation bei dir
> nicht sauber durchlief. KEINE Schema-Migration. Wirkt erst nach
> Neuinstallation von 1.7.2 (die gefixte `DEINSTALLIEREN.bat` wird dabei
> mitkopiert).

### Fixed / Changed

- **#739 — Windows-Deinstaller robuster:** Der Prozess-Stopp (Schritt [1/7])
  haengt nicht mehr an `wmic` (auf neueren Windows-Builds deprecated/entfernt),
  sondern nutzt PowerShell/CIM. Vor dem Loeschen der Runtime gibt es eine kurze
  Pause + einen `rmdir`-Retry, damit frisch freigegebene Datei-Handles
  (`pbp.db`/WAL) das Entfernen nicht mehr still scheitern lassen. Am Ende nennt
  der Deinstaller den Datenordner explizit, falls Reste verbleiben — der kann
  gefahrlos manuell geloescht werden. Der Prozess-Stopp wird zusaetzlich ins
  `deinstall_log.txt` protokolliert.
- **Footprint-Klarstellung:** PBP legt nur an EINER Stelle Daten ab
  (`%LOCALAPPDATA%\BewerbungsAssistent`) plus einen HKCU-Uninstall-Key, die
  Desktop-Verknuepfung und den Claude-MCP-Eintrag. Keine Dienste, kein
  Autostart, kein HKLM. Eine manuelle Komplett-Entfernung ist gefahrlos
  moeglich.

### Unter der Haube

Geaendert: `DEINSTALLIEREN.bat` + Version. Versions-/Registry-Tests 112 passed,
Deinstaller-Launcher-Test 4 passed. Der genaue Abbruch-Punkt auf einer
betroffenen Maschine wird ueber `deinstall_log.txt` weiter eingegrenzt.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.2.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.2.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.1] - 2026-06-18 — Hotfix: Statistik-Tab auf Neuinstallationen (#737)

> **Hotfix fuer v1.7.0.** Empfohlenes Update (`--latest`), besonders relevant
> fuer **Neuinstallationen**. KEINE Schema-Migration (v48 unveraendert).

### Fixed

- **#737 — Statistik-Tab crasht bei Neuinstallationen:** Die Spalte
  `applications.is_imported` wurde nur per Migration v21->v22 (ALTER TABLE)
  angelegt und fehlte im `CREATE TABLE applications` (SCHEMA_SQL). Auf einer
  frisch installierten v1.7.0 (Schema direkt v48, Migration laeuft nicht)
  fehlte die Spalte daher -> `get_extended_stats()` (nutzt
  `COALESCE(a.is_imported, 0)`) warf `no such column: a.is_imported`, der
  Endpoint `/api/stats/extended` lieferte HTTP 500 und der Statistik-Tab blieb
  leer. Fix: `is_imported` ins `CREATE TABLE` aufgenommen (additiv, bestehende
  DBs unveraendert; die Migration bleibt fuer Upgrader). Migrierte Alt-DBs
  (Upgrade von < v22) waren nie betroffen. Regressionstest
  `test_v17_fresh_install_stats` (frische DB -> Spalte vorhanden + kein Crash).

### Unter der Haube

Eine Zeile in SCHEMA_SQL + zwei Regressionstests. Suite: **1804 passed, 1 skipped**.
Gefunden beim Neuaufnehmen der Wiki-Screenshots aus einer frischen Demo-Instanz.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.1.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.1.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0] - 2026-06-18 — Stable: Lokale KI, Elwosa, Multi-Profil, Stabilisierung

**Erster Stable-Release der 1.7-Reihe.** Loest **v1.6.10** als empfohlene Version
(`--latest`) ab. Ergebnis aus ueber 100 Beta-Iterationen (April–Juni 2026); die
Detail-Changelogs stehen in den `1.7.0-beta.*`-Eintraegen unterhalb. v1.6.10
bleibt als Release weiterhin verfuegbar.

> **Update von v1.6.x:** einfach drueberinstallieren — deine Daten bleiben
> erhalten. Das Schema-Upgrade (bis **v48**) laeuft automatisch beim ersten
> Start, rein additiv, mit Pre-Migration-Backup (bricht bei Fehler HART ab).
> Nach dem Update Claude Desktop komplett beenden und neu starten, Dashboard
> hart neu laden (Strg+F5).

### Highlights gegenueber v1.6.10

- **Lokale KI (Ollama) als Hintergrund-Backbone** — Auto-Aussortieren per
  Profil-Match, Dokument-Klassifikation, 5-stufiges Lern-System mit
  Pattern-Analyse, Automatik-Scheduler; TaskKind-Routing (lokal / Claude /
  manuell).
- **Elwosa** — Live-Statusanzeige der lokalen AI in der Sidebar mit eigener
  Persoenlichkeit und kontextuellen Tipps pro Seite.
- **Multi-Profil**, **Skills mit Zeitraeumen**, **Typed IDs** (sichtbare
  Praefixe, nicht-breaking: nackte 8-Hex-IDs funktionieren weiter).
- **Kontakte-System, TODOs mit Faelligkeit, Dokument-Lifecycle,
  Recherche-Persistenz, Outcome-Quoten, Minus-Keywords, Wiedergaenger-Erkenner,
  Ablehnungsgruende-Editor**.
- **Scraper-Robustheit** — Fehlerklassifikation (tot/blockiert/server_weg/
  kaputt) + differenzierter Backoff statt Pauschal-Deaktivierung; 35 Quellen.
- **Datenqualitaet der Suche** — Geo-Filter fuer nicht-DACH Stellen,
  tz-robuste Zeitanzeige (Europe/Berlin), Stilarchiv-Autosave.
- **Stand:** 177 MCP-Tools, 24 Prompts, Schema v48, ueber 1800 Tests gruen.

### Release-Reife

Die projekteigenen Release-Gates sind erfuellt: Datenintegritaet
(Migrations-Generalprobe #705), DB-Schreib-Kontention Dashboard<->MCP (#723),
tz-robuste Zeitanzeige (#701). Der 1.6.x->1.7-Migrationspfad ist als
Generalprobe verifiziert (rein additiv, Tabellen-Rebuilds nur fuer Schema
< v23). beta.108 lief mehrere Tage im Realbetrieb ohne kritische Befunde.

### Bewusst auf v1.8 verschoben

Plugin-Plattform (#504), Mail-Integrationen (#478/#480/#481), Newsletter-Ingest
(#525), Branchen-Radar/Tools-News (#718/#735), DB-weiter Timestamp-Umbau (A18).
Tracking im [Master-Plan](https://github.com/MadGapun/PBP/wiki/Master-Plan).

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.108] - 2026-06-15 — Bugfix-Welle: Geo-Filter, Quellen-Hinweis, Stilarchiv-Autosave + Interview-Quote (#731/#732/#733/#734/#736)

> ⚠️ **Pre-Release / Beta.** Stable bleibt **v1.6.10**. **KEINE Schema-Migration**
> (Schema **v48** unveraendert) — alle Aenderungen sind rein additive Logik.
> Nach dem Update Claude Desktop komplett beenden und neu starten, Dashboard
> hart neu laden (Strg+F5).

Fortsetzung der Bugfix-Welle aus den User-Tests vom 15.06.2026 — Schwerpunkt
Datenqualitaet der Stellensuche und Nutzbarkeit des Stilarchivs.

### Fixed

- **#732 — Geo-Filter fuer nicht-DACH Stellen:** Stellen aus Scraper-Quellen mit
  erkennbar auslaendischem Ort (z.B. „Brazil", „Remote (Florianópolis)", „USA")
  werden beim Ingest automatisch aussortiert (`is_active=0`,
  `dismiss_reason='zu_weit_entfernt'`) statt mit falschem Naehe-Wert im aktiven
  Pool zu landen. Hintergrund: das Geocoding haengt `", Deutschland"` an die
  Anfrage und bekam fuer „Brazil" einen DE-Treffer mit ~533 km statt ~10.000 km;
  der gedeckelte Entfernungs-Malus reichte nicht zum Aussortieren. Neue
  konservative Heuristik `is_non_dach_location` (ein DACH-Marker gewinnt immer;
  unbekannte und reine Remote-Orte werden NICHT gefiltert). Manuelle und
  Email-Eintraege (bewusste User-Aktion) sind ausgenommen.
- **#731 — Scoring-False-Positives via Remote-Aggregatoren:** Der konkrete Fall
  (10 Consumer-Tech-Stellen aus Brasilien, durch das MUSS-Keyword „Product
  Lifecycle" gerutscht) wird durch den neuen Geo-Filter (#732) bereits vor dem
  Scoring geblockt. (Zusaetzliche Keyword-Praezisierung „Product Lifecycle
  Management" ist eine User-Daten-Entscheidung in den Suchkriterien.)
- **#736 — stil_auswertung zaehlt Interviews korrekt:** Die Interview-Quote
  misst jetzt, welcher Anteil der Bewerbungen eines Stils MINDESTENS EIN
  Interview erreicht hat — bestimmt ueber den Status-Verlauf (Timeline +
  `has_reached_interview`-Flag), nicht ueber den finalen Status. Eine Bewerbung
  mit Verlauf `interview -> abgelehnt` zaehlt damit als Interview-Treffer (und
  zusaetzlich als `absage_nach_interview`) statt als 0 Interviews. Begruendung:
  das Anschreiben entscheidet ueber die Einladung, nicht ueber das Ergebnis im
  Gespraech.

### Added / Changed

- **#733 — stelle_manuell_anlegen: Quellen-Hinweis:** Bleibt die Quelle nach dem
  Anlegen `'manuell'` (keine aus der URL ableitbare Herkunft), liefert das Tool
  jetzt einen `hinweis`, die echte Quelle (linkedin/xing/firmenwebsite) zu
  setzen — sonst verfaelschen KI-gesteuerte Chrome-Adds die Quellenstatistik.
  Die automatische URL->Quelle-Ableitung (#613) bleibt unveraendert.
- **#734 — Stilarchiv-Autosave nach Anschreiben-Export:** `anschreiben_exportieren`
  legt das Anschreiben automatisch im Stilarchiv ab (neue DB-Methode
  `upsert_document_version`, „letzte Version gewinnt" pro Bewerbung/Titel +
  `kind`) — damit `stil_auswertung`/`stilarchiv_kontext` echte Daten haben, ohne
  dass der manuelle Schritt vergessen wird. (CV-Autosave ist bewusst
  zurueckgestellt: `lebenslauf_angepasst_exportieren` erzeugt direkt ein DOCX
  ohne greifbaren Text, und das Stilarchiv wertet ohnehin den Schreibstil =
  Anschreiben aus.)

### Unter der Haube

Neue Tests: `tests/test_v17_beta108_fixes.py` (35 Tests fuer
#731/#732/#733/#734/#736). KEINE Schema-Migration (Schema v48 unveraendert),
rein additive Logik. Suite: **1802 passed, 1 skipped**.

Begleit-Aufraeumen: Master-Issue #719 (Scraper-Robustheit 1.7) geschlossen — der
1.7-Scope ist mit beta.106 erledigt; die bewusst auf 1.8 verschobene Folgearbeit
(Claude-Handoff fuer blockierte/SPA-tote Quellen, Langzeit-Auswertung pro
Quelle) ist als #735 ausgegliedert.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.108.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.108.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.107] - 2026-06-15 — Bugfix-Welle: Installer, Blacklist, Zeitanzeige, Scoring, Live-Updates (#728/#729/#701/#698/#630)

> ⚠️ **Pre-Release / Beta.** Stable bleibt **v1.6.10**. **Schema v47 -> v48**
> (rein additiv: ein sichtbarer Scoring-Regler `hochschulabschluss/fehlt`;
> automatisches Backup laeuft vor der Migration). Nach dem Update Claude Desktop
> komplett beenden und neu starten, Dashboard hart neu laden (Strg+F5).

### Fixed

- **#728 — macOS-Installer erkennt Homebrew-Python:** `INSTALLIEREN.command`
  und `installer/install.sh` probieren jetzt zuerst die versionierten Binaries
  (`python3.13`/`python3.12`/`python3.11`), bevor sie auf `python3` zurueckfallen.
  Vorher fand der Installer auf macOS nur Apples System-Python 3.9 und brach ab,
  obwohl `brew install python@3.12` (der empfohlene Weg) ein passendes Python
  bereitstellt.
- **#729 — Blacklist-Check beim manuellen Anlegen:** `stelle_manuell_anlegen()`
  prueft jetzt VOR dem Anlegen, ob die Firma auf der Blacklist steht, und legt
  sie nicht an (klarer Fehler; `force=True` ueberbrueckt bewusst). Zusaetzlich
  schlaegt PBP nach `stelle_bewerten()` nicht mehr vor, eine Firma auf die
  Blacklist zu setzen, die bereits drauf steht. Neuer Helfer
  `is_company_blacklisted` als gemeinsame Basis.
- **#701 — Zeitdarstellung auf Europe/Berlin:** Relative Datumslabels tragen
  jetzt die Berliner Uhrzeit ("in 2 Tagen, 14:00 Uhr") und die Uhrzeit-Anzeige
  rechnet zeitzonen-robust (`berlinTimeOfDay`). Die Serverzeit steht zum
  Debugging im Footer ("Serverzeit: HH:MM (Europe/Berlin)"). Der einheitliche
  DB-weite Timestamp-Standard (naive vs. aware) bleibt bewusst Folge-Arbeit
  (Master-Plan A18) — der akute Anzeige-Fehler ist behoben.

### Added

- **#698 — Hochschulabschluss-Malus konfigurierbar:** Der frueher hart codierte
  -2-Malus (fehlender Hochschulabschluss) ist jetzt ein sichtbarer Scoring-Regler.
  `scoring_konfigurieren('setzen','hochschulabschluss','fehlt', wert=0)` aendert
  den Wert, `ignorieren=True` deaktiviert Malus UND Risiko-Hinweis komplett.
  Default bleibt -2 (rueckwaertskompatibel).
- **#630 — Live-Updates Stufe 1:** Aktualisieren-Knopf oben rechts in der
  Kopfzeile (auf jeder Seite) laedt die aktuelle Seite neu und zeigt
  Aenderungen, die Claude im Hintergrund gemacht hat; daneben "Letzter Sync:
  HH:MM". FAQ-Eintrag "Wann muss ich aktualisieren?". (Automatisches Polling/SSE
  bleibt spaetere Ausbaustufe.)

### Unter der Haube

Neue Tests: `test_v17_blacklist_manuell_729`, `test_v17_hochschul_malus_698`,
`test_v17_serverzeit_701`, erweiterter Frontend-Kipp-Test (berlinTimeOfDay).
Schema-Migration v47->v48 (ALTER-/INSERT-only). Suite: 1767 passed, 1 skipped.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.107.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.107.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `dataackups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.106] - 2026-06-13 — Scraper-Robustheit: Fehlerklassifikation statt Pauschal-Deaktivierung (#719-#722)

> ⚠️ **Pre-Release / Beta.** Stable bleibt **v1.6.10**. **Schema v46 -> v47**
> (rein additiv: eine neue Spalte `scraper_health.error_class`; automatisches
> Backup laeuft vor der Migration). Nach dem Update Claude Desktop komplett
> beenden und neu starten, Dashboard hart neu laden (Strg+F5).

Ein eigenstaendiger Feature-Block (kein Stabilitaets-Fix): Das System
unterscheidet beim Abschalten einer Job-Quelle jetzt zwischen "kurz weg" und
"dauerhaft kaputt" — und behandelt das oft nur temporaere Problem (Timeout,
5xx, Verbindung) nicht mehr mit der haertesten, dauerhaftesten Reaktion.

### Added

- **#720 — Fehlerklassifikation:** Neue zentrale, testbare Funktion
  `classify_scraper_error` leitet aus dem aufgetretenen Fehler eine Klasse ab —
  `tot` (404/410), `blockiert` (403/429), `server_weg` (Timeout/5xx/Connection/
  DNS), `kaputt` (Parser-Crash/ImportError). Die Klasse wird bis in
  `scraper_health.last_status_detail` ("server_weg: timeout 90s") und eine
  eigene Spalte `error_class` durchgereicht. Rein additiv, kein
  Verhaltenswechsel in diesem Schritt.
- **#721 — Differenzierte Reaktion:** Der fail-Pfad nutzt jetzt die schon
  vorhandene Backoff-/Probe-Mechanik, gesteuert durch die Klasse:
  - `server_weg` / `blockiert` werden nach 5 gleichartigen Fehlern in Folge
    **pausiert-mit-Probe** (kommen per Probe-Run automatisch zurueck) statt
    hart deaktiviert. Bei 429 wird der Retry-After-Header respektiert.
  - `tot` / `kaputt` werden weiterhin hart deaktiviert (kommen nicht von
    selbst zurueck).
  - Ein einzelner Aussetzer bei sonst gesunder Quelle deaktiviert NICHT.
  - Fehlt die Klasse (Altdaten), bleibt das bisherige Verhalten — kein
    Regressionsrisiko.
- **#722 — Dashboard-Sichtbarkeit:** Die Quellen-Health-Anzeige (Einstellungen
  -> Quellen) zeigt jetzt differenzierte Zustaende statt nur "deaktiviert":
  **pausiert (Probe geplant)**, **blockiert (403/429)**, **tot (404)**,
  **kaputt (Code-Fix)** — je mit Fehlerklasse im Klartext, naechstem
  Probe-Zeitpunkt sowie letztem Erfolg und letzter Trefferzahl. Der
  "Jetzt reaktivieren"-Button war bereits vorhanden.

### Verifiziert

- **#719 (Master):** Generalprobe als Test abgedeckt — server_weg x5 ->
  pausiert (nicht hart), 404 -> tot (hart), Erfolg nach Pause -> reaktiviert.
  Der 1.8-Roadmap-Teil (Claude-Handoff fuer blockierte/SPA-tote Quellen,
  Playwright-Adapter #656, Langzeit-Auswertung) bleibt bewusst offen.

### Unter der Haube

Neuer Service `services/scraper_classifier.py`. Neue Tests
`test_v17_scraper_robustheit_720_721` (Klassifikation + differenzierte
Reaktion) und `test_v17_scraper_dashboard_722` (Badge-Vertrag). Schema-
Migration v46->v47 (ALTER-only). Suite: 1753 passed, 1 skipped.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.106.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.106.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `dataackups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.105] - 2026-06-13 — Release-Gate: Datenintegritaet, DB-Kontention, Zeitanzeige (Teil A, Stable-Kandidat)

> ⚠️ **Pre-Release / Beta — zugleich der Stable-Kandidat fuer v1.7.0.** Stable
> bleibt **v1.6.10**, bis der Abschlusstest durch ist. Keine Schema-Aenderung
> (bleibt v46). Nach dem Update Claude Desktop komplett beenden und neu starten,
> Dashboard hart neu laden (Strg+F5).

Diese Version schliesst die drei Pflicht-Blocker des Release-Gates ab. Vieles
davon war Verifikation statt Neubau — bestaetigt mit Tests, nicht nur Code-Lesung.

### Datenintegritaet bei Update/Migration (#705, Teil A1)

- **Generalprobe Migration** als Pflicht-Test: Eine voll befuellte 1.6.x-DB
  (Schema v31, Profil inkl. informal_notes/summary/Kontaktdaten, mehrere
  Bewerbungen mit Events/Meetings/Follow-ups, Dokumente, Skills, Positionen,
  Projekt, Ausbildung) wird auf das aktuelle Schema migriert und Feld- bzw.
  zeilengenau gegen den Vorher-Zustand geprueft: kein vorher befuelltes
  Profilfeld wird leer, alle Tabellen-Zaehler bleiben >= vorher, keine Waisen.
  Bestaetigt: der reale 1.6.x->1.7-Pfad ist rein additiv (ADD COLUMN /
  CREATE TABLE) — die drei Tabellen-Rebuilds greifen nur fuer Schemas < v23.
- **Pre-Migration-Backup ist jetzt verbindlich:** Schlaegt das Backup vor der
  Migration fehl, wird die Migration HART abgebrochen (klare Fehlermeldung)
  statt ohne Sicherheitsnetz weiterzulaufen.
- **profil_erstellen-Merge** gegen Datenverlust gehaertet und um Randfaelle
  erweitert (leerer String loescht keinen Bestand, sequenzielle Teilupdates,
  nur-Telefon / nur-Summary).
- **Export/Import-Sicherheitsnetz** mit Round-Trip-Test (informal_notes
  ueberlebt Export -> Import).

### DB-Schreib-Kontention Dashboard <-> MCP (#723, Teil A2)

- **busy_timeout auf 30s angehoben** (war 5s) auf der gemeinsam genutzten
  Connection — ueberdauert auch laengere Bulk-Writes/Auto-Engine-Zyklen, bleibt
  aber weit unter dem 4-Min-Client-Timeout. Zusammen mit WAL und dem
  rollback_if_stale-Sicherheitsnetz (#708) heilt das die sporadischen
  "MCP antwortet nicht"-Haenger, wenn parallel im Dashboard gepflegt wird.
- **Reproduktionstest** fuer den Kontentions-Fall: ein zweiter Writer wartet
  auf die Lock-Freigabe und geht dann durch, statt sofort zu scheitern oder in
  den Client-Timeout zu haengen.

### Zeitanzeige (#701, Teil A3)

- Relative Datumslabels (heute/morgen/uebermorgen/in X Tagen) rechnen jetzt
  explizit in **Europe/Berlin** und sind damit unabhaengig von der Zeitzone des
  Rechners — das Label kippt nicht mehr um Mitternacht UTC. Logik in eine pure,
  testbare Hilfsfunktion (`lib/relativeDate`) ausgelagert.
- **Kipp-Test** deckt den UTC-Mitternachts-Grenzfall ab (Sommer-/Winterzeit),
  laeuft in der CI bewusst unter TZ=UTC. Der grosse einheitliche UTC-Umbau
  (Master-Plan A18) ist bewusst auf v1.7.1/v1.8 vertagt — der akute Fall ist
  behoben.

### Verifiziert und geschlossen

- **#668** (Jobsuche-Gesamttimeout): Pro-Scraper-Timeout, Auto-Skip defekter
  Quellen, Teilergebnis-Persistierung und parallele Ausfuehrung sind vorhanden
  und belegt.
- **#724 / #725** (E-Mail-Verknuepfung + Dashboard-Kachel): E-Mail-Matching
  laeuft ueber alle Bewerbungs-Status (kein Aktiv-Filter); die "offen"-Kachel
  ist klickbar mit Zuordnen-/Loeschen-Aktionen.

### Unter der Haube

Neue Tests: `test_v17_migration_generalprobe_705`, `test_v17_db_contention_723`,
erweiterte `test_v17_profil_merge_695`, Frontend-Kipp-Test
`frontend/src/lib/relativeDate.test.mjs` (in CI). Suite: 1739 passed, 1 skipped.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.105.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.105.zip)
2. **Entpacken:** Rechtsklick auf die ZIP -> *„Alle extrahieren..."* -> Zielordner waehlen (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Installieren:** Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3-5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.
6. **Claude Desktop oeffnen** (lief es schon: komplett beenden — Rechtsklick aufs Claude-Symbol unten rechts in der Taskleiste -> *Beenden* — und neu starten) und tippen: **„Starte die Ersterfassung"**
7. Taucht PBP nicht auf: Claude Desktop nochmal komplett beenden und neu starten — siehe [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ).

### macOS

1. **Einmalig vorab: Python 3.11+** — am einfachsten der [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **ZIP herunterladen** (siehe Windows-Link) und **entpacken** (Doppelklick; im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt („kann nicht geoeffnet werden"): Rechtsklick auf die Datei -> *„Oeffnen"* -> nochmal *„Oeffnen"*

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

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `dataackups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki -> Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.104] - 2026-06-12 — Lokale-KI-Transparenz + Elwosa-Feature-Tipps (#689 Teil 1, #713)

> ⚠️ **Pre-Release / Beta**. Stable bleibt **v1.6.10**. Neuer Frontend-Build,
> keine Schema-Aenderung (bleibt v46). Nach dem Update Claude Desktop einmal
> komplett beenden und neu starten, Dashboard hart neu laden (Strg+F5).

Direkte Umsetzung der User-Wuensche vom 12.06.

### Added

- **#689 (Teil 1) — „Was wurde aussortiert?":** Neuer aufklappbarer Bereich
  in den Lokale-KI-Einstellungen listet jede Auto-Aussortierung mit Titel,
  Firma und der **KI-Begruendung** — und einem **Zurueckholen-Button** pro
  Stelle (Ollama lernt aus jeder Korrektur). Neuer Endpoint
  `GET /api/local-ai/auto-dismissed`.
- **#689 (Teil 1) — Lernprotokoll:** Was die lokale KI gelernt hat
  (`learning_insights`) ist jetzt dauerhaft in den Lokale-KI-Einstellungen
  einsehbar — nicht mehr nur fluechtig auf der Dashboard-Card.
  (Insight-Loeschen + Komplett-Reset folgen als #689 Teil 2.)
- **#713 — Elwosa stellt selten genutzte Funktionen vor:** Die
  nutzungsbasierten Tipps aus #652 (Suchprofile, Aufwand-Tracking,
  Interview-Reflexion) erreichen den Nutzer jetzt wirklich — als
  Elwosa-Linien mit zwei Klick-Aktionen: **„Ansehen"** (springt direkt in
  den passenden Tab) und **„Claude-Prompt kopieren"** (fertiger Prompt in
  der Zwischenablage). Neues Link-Markup `[link:prompt:...]`. Feature-Tipps
  haben Vorrang vor generischen Tipp-Linien und respektieren Tonfall-Modus,
  Frequenz-Drossel und Anti-Repeat.

### Unter der Haube

Neue Tests `test_v17_ki_transparenz_689_713` (inkl. Sprach-DNA-Pruefung der
dynamischen Linien). Master-Plan: F21 auf 🟨 (Teil 1), F24 auf ✅.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.104.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.104.zip)
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

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `dataackups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.103] - 2026-06-12 — User-Test-Welle: DB-Lock-Haertung, ehrliches Dedup-Gate, Update-Banner (#704, #705, #708-#711)

> ⚠️ **Pre-Release / Beta**. Stable bleibt **v1.6.10**. Kein Frontend-Build
> noetig, keine Schema-Aenderung (bleibt v46). Nach dem Update Claude Desktop
> einmal komplett beenden und neu starten.

Fixes aus dem laufenden Abschlusstest (Stellen-Triage 11./12.06.).

### Fixed

- **#708 — „database is locked" bis zum Neustart (kritisch):** Der
  Haupt-Connection fehlte `busy_timeout` (Writes scheiterten sofort, statt
  kurz zu warten), und ein per Timeout abgebrochenes Tool konnte eine offene
  Transaktion hinterlassen, die den Write-Lock dauerhaft hielt. Jetzt:
  `busy_timeout=5000` + Rollback-Sicherheitsnetz an den Ausfuehrungs-Grenzen
  (Tool-Middleware + Auto-Engine-Zyklus) mit WARNING-Log.
- **#709 — Dedup-Override war eine Luege:** Die Fehlermeldung versprach einen
  `notes`-Bypass, der **nie implementiert** war. Jetzt gibt es den ehrlichen
  Parameter `force=True` in `bewerbung_erstellen`; alle Duplikat-Meldungen
  nennen ihn.
- **#710 — `endkunde` in `bewerbung_erstellen`:** Die DB-Spalte existierte
  seit Schema v14, wurde aber nie durchgereicht. Bei gesetztem Endkunden
  trennt die Duplikat-Erkennung jetzt Vermittler-Engagements (gleicher
  Vermittler + anderer Endkunde ≠ Duplikat).
- **#711 — Release-Banner ist wieder ein Update-Hinweis:** Das Dashboard
  zeigte beta.102-Nutzern „Neu in beta.101". Release-Hints werden jetzt nur
  noch angezeigt, wenn die angekuendigte Version NEUER ist als die
  installierte (korrekter Versionsvergleich, Stable > Beta).
- **#705 — Profil-Datenverlust-Haertung:** `pbp_diagnose` erkennt jetzt das
  Muster „gepflegtes Profil, aber Kontaktfelder/Notizen leer" und zeigt den
  Wiederherstellungs-Weg aus `data/backups/`. (Die Ursache des gemeldeten
  Verlusts — der `profil_erstellen`-Ueberschreib-Bug — ist seit beta.101
  gefixt; Migrationen selbst leeren keine Felder, sie sind ALTER-only.)

### Changed

- **#704 — Jobsuche-Workflow schliesst manuelle Quellen ein:** Claude wird im
  gefuehrten Workflow angewiesen, LinkedIn/XING/StepStone/Google Jobs ohne
  Nachfrage via Claude-in-Chrome abzuarbeiten (sofern verbunden) und Treffer
  direkt mit `stelle_manuell_anlegen()` zu erfassen.

### Unter der Haube

Neue Regressionstests `test_v17_user_test_703plus` (9 Tests). Keine
Schema-/Frontend-Aenderung. #706 (Interview-Button) und #707
(Notizen-Pflege) sind als G16/H15 im Master-Plan eingeplant.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.103.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.103.zip)
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

## [1.7.0-beta.102] - 2026-06-10 — Feinschliff aus der Dashboard-Tour (#702)

> ⚠️ **Pre-Release / Beta**. Stable bleibt **v1.6.10**. Neuer Frontend-Build,
> keine Schema-Aenderung (bleibt v46). Nach dem Update Claude Desktop einmal
> komplett beenden und neu starten, Dashboard hart neu laden (Strg+F5).

Kleiner, rein kosmetischer Release: Ergebnis eines vollstaendigen
Klick-Durchgangs durch alle Dashboard-Bereiche (beta.101 gegen eine
DB-Kopie). Dabei nebenbei live verifiziert: die Jobsuche laeuft ohne
0%-Haenger durch (#668) und die Datums-Labels stimmen (#701-Teilfix).

### Fixed

- **Nackte „0" im Termine-Widget** — `is_private` kommt aus SQLite als 0/1,
  React renderte die 0 als Text. (#702)
- **„Neu in v1.6.2"-Banner** auf der Startseite — die remote geladene
  `hints.json` war seit v1.6.2 eingefroren; zeigt jetzt den
  Stabilisierungs-Release. (#702)
- **Follow-ups erschienen mit „02:00 Uhr"** (Kalender + Termine-Widget) —
  Nachfass-Erinnerungen sind Tages-Aufgaben und zeigen jetzt nur das Datum.
  (#702)
- **„Auf Basis von 1 Stellen"** — Singular/Plural korrigiert; bei weniger als
  3 Datenpunkten steht jetzt „wenig Datenbasis" an den Gehaltskennzahlen.
  (#702)
- **Elwosa-Linie mit fehlendem Satzanfang** („ will dich sehen.") —
  `pick_line` ueberspringt Linien mit ungefuellten Text-Platzhaltern. (#702)
- **Stellen-KPI las sich wie Teilmengen** („2 gesamt (6 mit Bewerbung, 1676
  aussortiert)") — aktive Stellen, Bewerbungen und Aussortierte sind
  getrennte Mengen und werden jetzt entkoppelt aufgezaehlt. (#702)
- **KPI „Follow-ups" vs. „Offene Aktionen"** widersprachen sich — Label heisst
  jetzt „Faellige Nachfaesse" mit klarer Abgrenzung. (#702)
- Stale Texte: Elwosa-Tipp „ueber 130 Werkzeuge" → „ueber 170"; Tippfehler
  „Falls du noch nicht durch ist"; Hilfe-Dialog nennt jetzt auch die
  MINUS-Keywords; Quellen-Zahl ueberall auf die Code-Wahrheit **35**
  normiert (`len(SOURCE_REGISTRY)`). (#702)

### Unter der Haube

Kein Schema-, kein Tool-Signatur-Change. Neue Regressionstests
`test_v17_feinschliff_702`. Bewusst nicht angefasst (Design, kein Glitch):
Hero- und Workspace-Card zeigen beide den Jobsuche-CTA; „Offene Aktionen"
mischt Termine + Nachfaesse absichtlich mit Labels.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein, **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.102.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.102.zip)
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

## [1.7.0-beta.101] - 2026-06-10 — Beta-Stabilisierung: 13 Bugfixes, Onboarding-Haertung, CI-Gate

> ⚠️ **Pre-Release / Beta**. Stable bleibt **v1.6.10**. Neuer Frontend-Build,
> keine Schema-Aenderung (bleibt v46). Nach dem Update Claude Desktop einmal
> komplett beenden (Tray-Symbol → Beenden) und neu starten, Dashboard hart
> neu laden (Strg+F5).

Der groesste Stabilisierungs-Release der Beta-Reihe — Ergebnis eines
Multi-Agent-Audits aus Sicht unerfahrener Nutzer plus der User-Test-Funde
vom 8.-10. Juni. Ziel: PBP laeuft fehlerfrei fuer Menschen ohne PBP- und
ohne Claude-Vorwissen.

### Fixed

- **#692 — Prompt-Karten `/tipps_und_tricks` + `/profil_sync` luden nicht**
  („Inhalt konnte nicht geladen werden"). Ursache: FastMCP 3.x brach die
  interne Prompt-Delegation. Texte sind jetzt versions-stabil entkoppelt.
- **#691 — `stellen_auto_aussortieren`:** schemakonformes Teil-Ergebnis statt
  „outputSchema"-Validierungsfehler bei groesseren Laeufen (Budget jetzt 50s
  Default, bis 90s via `max_dauer_sek`); der Platzhalter „KURZBEGRUENDUNG"
  landet nie mehr als Begruendung.
- **#690 — `stellenbeschreibung_nachladen`** laedt jetzt bis 20.000 Zeichen
  statt bei 2.000 abzuschneiden.
- **#686 — Dublettenschutz:** `analyse_plan_erstellen` erkennt Firmen auch im
  Dokument-INHALT und schlaegt vor, zu welcher bestehenden Bewerbung ein
  Dokument gehoert (`bewerbungs_zuordnungen`).
- **#685/#684 — `kontakt_verknuepfen`:** Ziel `meeting` funktioniert (Tabellen-
  Fix) und das `CON-`-Praefix wird akzeptiert.
- **#668 — Jobsuche haengt nicht mehr bei 0%:** Ergebnisse werden in
  Fertigstellungs-Reihenfolge eingesammelt + globales Phasen-Budget gegen
  haengende Quellen.
- **#694 — Onboarding-Sackgassen:** gefuehrte Prompts verwiesen auf nicht
  existierende Tools (`anschreiben_generieren`, Umlaut-Varianten wie
  `skill_hinzufügen`) — mitten im Kennenlerngespraech. Alle Tool-Referenzen
  korrigiert, `workflow_starten` versteht jetzt auch Umlaut-Schreibweisen und
  meldet unbekannte Workflows ehrlich (statt „gestartet" mit Fehlertext).
  ~340 Zeilen toter Alt-Prompt-Code entfernt.
- **#695 — Stille Falsch-Erfolge:** `stelle_bewerten` und
  `bewerbung_status_aendern` melden bei unbekannter ID jetzt einen Fehler
  statt Erfolg (vorher wurde sogar die Lern-Statistik verfaelscht);
  `bewerbung_status_aendern` akzeptiert die `APP-`-ID-Form. **Wichtigster
  Fix: `profil_erstellen` loescht beim Aktualisieren keine Bestandsfelder
  mehr** (E-Mail/Telefon/Notizen blieben vorher auf der Strecke).
  `jobsuche_starten` startet nicht mehr ohne Suchkriterien (verhinderte
  Flut profil-fremder Treffer beim Erstnutzer).
- **#696 — Ehrliche Leere-Zustaende:** 0 hochgeladene Dokumente heisst jetzt
  „Noch keine Dokumente hochgeladen" (statt „alle analysiert"); Kein-Profil-
  Antworten sagen, was zu tun ist. `pbp_capabilities` kennt jetzt die
  Features seit beta.78 (Aufgaben, Dokument-Lifecycle, `stelle_reaktivieren`,
  Ablehnungsgruende-Editor, Minus-Keywords) und beschreibt
  `kennlerngespraech_abschliessen` korrekt.
- **#697 — Installation fuer Neulinge:** macOS-Doku ist ehrlich (Python-
  Voraussetzung + Gatekeeper-Hinweis), `INSTALLIEREN.command` installiert
  jetzt Chromium (Browser-Quellen liefen auf macOS sonst in einen Fehler),
  Tippfehler im Windows-Download-Fallback behoben, Release-Notes erklaeren
  den Claude-Desktop-Neustart und den ersten Befehl.
- **#699 — Blacklist-Schutz:** `blacklist_verwalten` warnt, wenn die Firma
  laufende Bewerbungen im Interview-Stadium hat (statt deren Stellen still zu
  deaktivieren); `force=True` uebersteuert bewusst.
- **#700 — Termine vs. Erinnerungen:** der Auto-Reconciler legt keinen
  Nachfass mehr an, wenn bereits ein zukuenftiger Termin existiert (vorher:
  „Nachfassen" 4 Tage NACH dem Interview); das Dashboard trennt „Anstehende
  Termine" (echte Meetings) von „Offene Erinnerungen" (Nachfass & Co., mit
  Erledigt/Hinfaellig-Buttons).
- **#701 (Teilfix) — Datums-Labels:** „morgen"/„in X Tagen" rechnen jetzt in
  Kalendertagen statt 24-Stunden-Schritten — ein Termin in 47 Stunden ist
  „uebermorgen", nicht „morgen". (Vollausbau Timestamp-Standard folgt, A18.)

### Changed

- **CI-Test-Gate:** GitHub Actions laesst bei jedem Push/PR die volle Suite
  (inkl. Installer-Extras + Chromium) und den Release-Check laufen — fing auf
  dem ersten Lauf direkt einen Linux-only-Bug (Pfad-Reparatur, #503).
- **`fastmcp` auf `>=3.0,<4` gepinnt** — ein Major-Update kann nicht mehr
  lautlos Interna brechen (Ursache von #692).
- README/Doku-Zahlen normiert (177 Tools, Schema v46, 34 Quellen) und der
  faq-Prompt zeigt jetzt aktive Onboarding-Tipps.

### Unter der Haube

Tool-Count bleibt 177, Schema bleibt v46. 9 neue Regressionstest-Dateien,
Suite: **1710 passed, 1 skipped**. Master-Plan Teil K (K1-K18) dokumentiert
jeden Fix; Issues #694-#697 dokumentieren die Audit-Befunde.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

**Unter Windows** brauchst du kein Git, kein Python, kein Vorwissen — nur einen ZIP-Download und einen Doppelklick. **Unter macOS** muss vorher einmalig Python 3.11+ installiert sein (siehe unten), **unter Linux** Git und Python. Voraussetzung ueberall: [Claude Desktop](https://claude.ai/download) ist installiert (Linux: alternativ Claude Code CLI).

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.101.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.101.zip)
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

## [1.7.0-beta.100] - 2026-06-04 — Aufgaben mit „Erledigt bis"-Datum + Dashboard warnt bei Ueberfaelligkeit (#683)

> ⚠️ **Pre-Release / Beta**. Stable bleibt **v1.6.10**. Neuer Frontend-Build,
> keine Schema-Aenderung (bleibt v46). Nach dem Update MCP-Server / Claude
> Desktop einmal neu starten und die Seite hart neu laden (Strg+F5).

### Added

- **#683 — „Erledigt bis"-Datum direkt beim Anlegen einer Aufgabe.** Im
  Bewerbungs-Detail (Aufgaben-Sektion) gibt es jetzt neben dem Titel ein
  Datumsfeld. Das Backend konnte `faellig_am` bereits — bisher hat das
  Frontend es nur nicht gesendet. (Termine/„Termin hinzufuegen" bleiben davon
  unberuehrt; Kalender-Verknuepfung war nicht noetig.)
- **#683 — Prominente Dashboard-Warnung bei ueberfaelligen Aufgaben.** Ganz
  oben im Dashboard erscheint eine rote Karte, sobald offene Aufgaben ihr
  Faelligkeitsdatum ueberschritten haben — mit Anzahl, Titeln (inkl.
  Bewerbung/Firma), Faelligkeitsdatum und Sprung zu den Bewerbungen.
  Ueberfaellige Aufgaben werden zusaetzlich in der Aufgaben-Liste der
  Bewerbung rot markiert („ueberfaellig: …").

### Unter der Haube

Neuer DB-Helper `get_overdue_tasks` (offen + `faellig_am` < heute, joint die
Bewerbung fuer Titel/Firma), eingehaengt in die Workspace-Zusammenfassung
(`/api/workspace-summary` → `ueberfaellige_aufgaben`). Keine Schema-Aenderung
(`tasks.faellig_am` existiert seit #666). Tool-Count bleibt 177. Neue Tests
`test_v17_overdue_tasks_683.py`. Im Browser gegen eine Real-DB-Kopie geprueft
(Dashboard-Warnung + Datumsfeld). Volle Suite gruen.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.100.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.100.zip)
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

## [1.7.0-beta.99] - 2026-06-04 — Outcome-Quoten segmentiert am PBP-Startdatum (#682)

> ⚠️ **Pre-Release / Beta**. Stable bleibt **v1.6.10**. Enthaelt einen neuen
> Frontend-Build, keine Schema-Aenderung (bleibt v46). Nach dem Update
> MCP-Server / Claude Desktop einmal neu starten und die Seite hart neu
> laden (Strg+F5).

### Added

- **#682 — Abgeleitete Outcome-Quoten + Segmentierung am PBP-Startdatum.**
  `statistiken_abrufen` / `get_statistics` liefern jetzt `expired_rate`,
  `rejection_rate` und `withdrawal_rate` (analog zu interview_rate /
  offer_rate) plus einen `quoten`-Block, der die Quoten in drei Segmenten
  ausweist: **gesamt**, **seit_pbp** (Bewerbungen ab dem System-Startdatum)
  und **vor_pbp**. Segmentiert wird am bereits vorhandenen System-Startdatum
  (Settings/System, Auto-Detect) nach `applied_at`. Damit wird sichtbar, ob
  seit der systematischen PBP-Nutzung anteilig weniger Bewerbungen versanden.
- **Dashboard-Kachel „Outcome-Quoten"** im Statistik-Tab mit Umschalter
  **Seit PBP** (Default) / **Vor PBP** / **Gesamt**, je Segment fuenf
  Quoten-Kacheln (Abgelaufen, Abgelehnt, Zurueckgezogen, Interview erreicht,
  Angebot) mit absoluter Anzahl und Basis.

### Bewusst nicht enthalten

Die im Issue zusaetzlich gewuenschte Segmentierung **aktiv-beworben vs.
inbound-Anfrage** ist nicht umgesetzt: dafuer fehlt ein zuverlaessiges
Unterscheidungs-Merkmal in den Daten (`bewerbungsart` beschreibt die
Einreichungs-Art — mit_dokumenten / elektronisch / ueber_portal —, nicht ob
es eine eingehende Anfrage war). Gemaess dem Bericht-Designprinzip („keine
Kennzahl auf unzuverlaessiger Datenbasis") bleibt dieser Schnitt offen, bis
es einen expliziten Inbound-Marker gibt. Im Issue dokumentiert.

### Unter der Haube

Backend-Berechnung profil-scoped, Basis = abgeschickte Bewerbungen (ohne
`in_vorbereitung`). Verifiziert auf einer Real-DB-Kopie (gesamt 22,9% vs.
seit-PBP-Zeitraum niedriger) und im Browser. Tool-Count bleibt 177. Neue
Tests `test_v17_statistik_quoten_682.py`. Volle Suite gruen.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.99.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.99.zip)
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

## [1.7.0-beta.98] - 2026-06-04 — Recherchen strukturiert speichern + im Detail anzeigen (#673/#674)

> ⚠️ **Pre-Release / Beta**. Stable bleibt **v1.6.10**. **Schema-Upgrade
> auf v46** (additiv, automatisches Backup vor der Migration). Enthaelt
> einen neuen Frontend-Build — nach dem Update MCP-Server / Claude Desktop
> einmal neu starten und die Seite hart neu laden (Strg+F5).

Baut auf beta.97 (#672) auf und schliesst den Recherche-Cluster.

### Added

- **#674 — Dedizierte `research_notes`-Tabelle (Schema v46).** Recherchen
  werden jetzt strukturiert abgelegt (Kategorie + Datum + Text), gebunden an
  eine Bewerbung und/oder eine Stelle (n:m-sauber, #472). Loest die alte
  Sammeltopf-Problematik endgueltig: keine Kollision mehr im
  Fit-Analyse-Feld, kein Vermischen mit dem manuellen Firmen-Recherche-
  Notizblock.
- **#674 — Ein-Schritt-Persistenz.** `firmen_recherche`, `branchen_trends`
  und `skill_gap_analyse` nehmen optional `bewerbung_id` (firmen_recherche
  zusaetzlich `job_hash`) und speichern das Ergebnis im selben Aufruf an die
  richtige Stelle — kein separater `recherche_speichern`-Schritt mehr noetig.
  Die Antwort nennt unter `gespeichert_als` das konkrete Ziel.
- **#673 — Recherchen-Abschnitt im Bewerbungs-Detail.** Sowohl die
  Tool-Ausgabe `bewerbung_details()` (Feld `recherchen`) als auch der
  Detail-Dialog im Dashboard zeigen jetzt alle gespeicherten Recherchen —
  pro Eintrag Kategorie, Datum und auf-/zuklappbarer Text. Klarer
  Leer-Zustand, wenn noch nichts gespeichert ist.

### Changed

- **`recherche_speichern` schreibt in die neue Tabelle** statt (wie in
  beta.97) in `jobs.research_notes`. Ohne verknuepfte Stelle wird die
  Recherche jetzt an die Bewerbung gebunden gespeichert (vorher Fehler).
  Bei job_hash + bewerbung_id auf dieselbe Stelle: ein Eintrag, beide
  Bindungen. Der manuelle „Firmen-Recherche"-Notizblock auf der Stelle
  (`jobs.research_notes`) bleibt davon unberuehrt.

### Migration

Schema v45 → v46: neue Tabelle `research_notes` + drei Indizes, rein additiv.
Automatisches DB-Backup vor der Migration (`data/backups/`). Verifiziert auf
einer Kopie der echten DB (v44 → v46 in einem Rutsch, alle Datensaetze
unveraendert: 1645 Stellen / 93 Bewerbungen / 203 Dokumente).

### Unter der Haube

Tool-Count bleibt 177 (nur Parameter ergaenzt, keine neuen Tools). Neue Tests
`test_v17_research_table_673_674.py` + aktualisierte
`test_v17_recherche_notizen_672_680.py`. Frontend-Detail-Dialog im Browser
gegen die Real-DB-Kopie verifiziert. Volle Suite gruen.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.98.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.98.zip)
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

## [1.7.0-beta.97] - 2026-06-04 — Recherche landet sichtbar + informelle Notizen editierbar (#672/#680)

> ⚠️ **Pre-Release / Beta**. Stable bleibt **v1.6.10**. **Backend-only**
> (kein neuer Frontend-Build, keine Schema-Aenderung — bleibt v45). Nach
> dem Update MCP-Server / Claude Desktop einmal neu starten.

Zwei Daten-Hygiene-Fixes aus dem Issue-Backlog.

### Fixed

- **#672 — Recherche landete im falschen, unsichtbaren Feld.**
  `recherche_speichern(..., bewerbung_id=...)` schrieb die Recherche bisher
  als JSON in `applications.fit_analyse`. Das ist das Feld fuer das
  Fit-Verdict — die Recherche kollidierte damit UND tauchte im Frontend
  nirgends auf. Jetzt wird sie an das **anzeigbare** `research_notes` der
  mit der Bewerbung verknuepften Stelle gehaengt (dasselbe Feld, das schon
  „FIRMEN-RECHERCHE" im Detail-Dialog zeigt). Hat die Bewerbung keine
  verknuepfte Stelle, kommt eine klare Meldung statt eines stillen
  Fehlschlags. Doppelziel (job_hash + bewerbung_id auf dieselbe Stelle)
  schreibt nur noch einen Eintrag. Die Antwort nennt jetzt das Zielfeld.
  Damit ist die Recherche auch ueber `bewerbung_id` sofort im Detail
  sichtbar (Teil von #673).

### Added

- **#680 — Informelle Notizen sind editierbar, nicht nur anhaengbar.**
  `profil_bearbeiten(bereich="notizen", ...)` kann jetzt:
  - `lesen` — gibt alle Sektionen strukturiert zurueck (welche Sektionen
    existieren, was steht drin),
  - `ersetzen` (`daten={"sektion","text"}`) — ersetzt den Inhalt einer
    Sektion,
  - `loeschen` (`daten={"sektion"}`) — entfernt eine ganze Sektion
    (meldet `nicht_gefunden`, wenn es die Sektion nicht gibt).

  Bisher ging nur `anhang` (immer nur dazu) und `aendern` (kompletter
  Roh-Ersatz).

### Bekannte Folge-Themen (offen, nicht in diesem Release)

- **#673** (alle Recherche-Kategorien als eigene Timeline-Sektion) und
  **#674** (Recherche-Tools persistieren direkt, dedizierte
  `research_notes`-Tabelle) bleiben offen — sie brauchen einen
  Frontend-Build bzw. eine Schema-Migration und kommen in einer eigenen
  Iteration. Die Daten-Integritaet (#672) ist die Voraussetzung dafuer und
  jetzt erledigt.

### Unter der Haube

Backend-only, keine Schema-Aenderung (bleibt v45), Tool-Count bleibt 177.
Neue Tests: `test_v17_recherche_notizen_672_680.py` (11 Faelle —
Recherche-Routing inkl. fit_analyse-Schutz + Dedupe; Notizen
lesen/ersetzen/loeschen inkl. nicht_gefunden). Volle Suite gruen.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.97.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.97.zip)
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

## [1.7.0-beta.96] - 2026-06-03 — Ollama kennt das Datum + Junk-Skills raus (#679/#681)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Backend-only, **kein
> Frontend-Build**. Nach Update MCP-Server neu starten.

Zwei Folge-Fixes nach dem Zeit-Thema (#679) und ein User-Test-Befund zur
Skill-Datenqualitaet (#681).

### Fixed

- **Ollama kennt jetzt das heutige Datum (#679-Folge).** Lokale Modelle
  haben kein eingebautes „heute" — vor jeden Ollama-Prompt
  (`_run_local`) kommt jetzt der echte Zeitbezug („Heute ist der ...,
  Jahr ..."). So rechnet das Modell `X Jahre Erfahrung` / `seit JJJJ`
  gegen das richtige Jahr und haelt alte Stellen nicht faelschlich fuer
  aktuell.
- **Junk-Skills aus der Extraktion (#681).** Die Skill-Heuristik
  (`_is_garbage_skill`) liess Satzfragmente durch („in Systemen wie Creo",
  „Programmierung in CATIA.", „SAP oder vergleichbar)"). Verschaerft:
  fuehrende Funktionswoerter (in/oder/und/…), Satz-Endzeichen,
  unbalancierte Klammern werden jetzt erkannt und abgewiesen.
- **Skill-Loeschen meldet ehrlich.** `profil_bearbeiten(bereich="skill",
  aktion="loeschen")` gab bisher „geloescht" auch bei unbekannter ID.
  Jetzt `nicht_gefunden`, wenn nichts getroffen wurde.

### Added

- **`skills_bereinigen(anwenden=False)`** — findet Junk-Skills im Profil
  (auch Altbestand, der unter der frueheren schwaecheren Heuristik
  reinrutschte) und entfernt sie auf Wunsch. Default ist Vorschau.
  Tool-Count **176 → 177**.

### Tests

- `test_v17_skill_junk_681.py` (Heuristik faengt 7 Junk-Beispiele, laesst
  10 echte Skills durch; add_skill-Reject; find/bereinigen). 
  `test_v17_ollama_zeitkontext_96.py` (Datum im Prompt). Registry 177.

### Schema

**Keine Schema-Aenderung** (v45).

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.96.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.96.zip)
2. **Entpacken + Doppelklick `INSTALLIEREN.bat`**

### macOS

`INSTALLIEREN.command` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

```bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
```

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.95] - 2026-06-03 — Elwosa nennt die echte Uhrzeit (#679)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **Kein Frontend-Build**
> noetig (reine Backend-Linien). Nach Update MCP-Server neu starten.

User-Test, 5 Uhr morgens: Elwosa fragte „Halb zwei. Was machst du noch
hier." — die Uhrzeit war falsch und wirkte wie ein kaputter Zeit-Abgleich.

### Fixed

- **Feste Uhrzeiten im Elwosa-Linientext.** Nicht der Clock war kaputt
  (`datetime.now()` ist korrekt — der Nacht-Trigger feuerte ja richtig),
  sondern mehrere Welt-Linien hatten eine **hartkodierte Uhrzeit** im Text
  („Halb zwei", „Drei Uhr morgens", „Achtzehn Uhr", „Sechzehn Uhr Freitag").
- Neuer Platzhalter **`{zeit}`** in `fill_template` setzt die **echte lokale**
  Uhrzeit ein (`format_uhrzeit`: 04:30 → „Halb fuenf", 16:00 → „Vier Uhr",
  04:32 → „4:32 Uhr"). Dazu `{uhrzeit}` (Alias) + `{datum}`.
- Die betroffenen Linien auf `{zeit}` umgestellt bzw. zeit-generisch gemacht
  (Freitag-Linien → „Freitagabend"). `docs/elwosa-character.md` synchron.

### Tests

- `test_v17_elwosa_zeit_95.py`: `format_uhrzeit`, `{zeit}`-Substitution,
  Regression (keine feste Uhrzeit mehr in den Pools). Tonfall-Validator +
  Lifesign weiter gruen.

### Hinweis

Gespeicherte Zeitstempel (`_now()`) sind UTC und werden im Frontend lokal
angezeigt (`toLocaleString`) — das war korrekt, es ging rein um die
hartkodierten Linientexte. **Keine Schema-Aenderung** (v45).

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.95.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.95.zip)
2. **Entpacken + Doppelklick `INSTALLIEREN.bat`**

### macOS

`INSTALLIEREN.command` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

```bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
```

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.94] - 2026-06-03 — Automatik im Hintergrund: interne Jobsuche + Ollama-Lernen nach Zeitplan (#677/#678)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **Frontend neu gebaut**,
> nach Update neu laden (Strg+F5).

Aus dem User-Test: zwei Automatik-Wuensche. (1) Ollama soll **regelmaessig
automatisch** aus Verhalten + Dokumenten lernen (der manuelle „Sofort-Lauf"
zeigte als letzten Lauf Anfang Mai). (2) Eine **interne** Jobsuche soll nach
Zeitplan laufen (taeglich/woechentlich/alle 3 Tage) — ausdruecklich nur die
internen Scraper, nicht die Claude-Browser-Quellen.

### Added — Hintergrund-Scheduler

- **Neuer Daemon-Scheduler** (`services/automatik_scheduler.py`), gestartet
  aus `start_dashboard`. Tickt alle 5 Min und startet faellige Tasks. Laeuft
  in der einen Instanz mit Dashboard -> kein Doppel-Lauf.
- **Task „interne Jobsuche"** (#678): nur Scraper-Quellen; Browser-/Login-
  Quellen (`_MANUAL_SOURCES`: LinkedIn, StepStone, XING, Indeed, ...) bleiben
  aussen vor. Respektiert die Dubletten-Sperre (kein zweiter Lauf parallel).
- **Task „Ollama-Lernen"** (#677): stoesst `_run_analyze_user_patterns` an
  (self-gated: nur bei aktivem Lern-Modus + genug Events + lokaler AI).
- **Intervalle:** 0 (aus) / 1 / 3 / 7 / 14 / 30 Tage, pro Task, pro Profil.

### Added — Bedienung

- **Automatik-Tab** (Einstellungen): neue Karte „Automatik im Hintergrund"
  mit Intervall-Auswahl je Task, Anzeige „letzter/naechster Lauf" und einem
  **Jetzt-Button** je Task. Im echten Browser gegen eine Real-DB-Kopie
  verifiziert (rendert, 0 Konsolen-Fehler).
- **MCP:** `automatik_status()` + `automatik_setzen(jobsuche_intervall_tage,
  lernen_intervall_tage)`. Tool-Count **174 → 176**.
- **REST:** `GET/PUT /api/automatik/settings`, `POST /api/automatik/run-now`.

### Hinweis (Constraint)

Der Scheduler laeuft nur, **solange Claude Desktop / der MCP-Server offen
ist** — es ist kein Windows-Dienst. Im UI und in den Tool-Beschreibungen
benannt.

### Tests

- `test_v17_automatik_scheduler_677.py` (Settings, Validierung,
  Faelligkeits-Logik, Status, MCP-Tools). REST via TestClient geprueft.
  Registry auf 176.

### Schema

**Keine Schema-Aenderung.** Settings als profile_settings. Bleibt v45.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.94.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.94.zip)
2. **Entpacken + Doppelklick `INSTALLIEREN.bat`**

### macOS

`INSTALLIEREN.command` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

```bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
```

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.93] - 2026-06-03 — White-Screen-Fix: Telemetrie-Sharing + App-weites Sicherheitsnetz

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **Wichtiger Fix** —
> wer Telemetrie-Sharing aktiviert hatte, wurde aus dem Dashboard
> ausgesperrt. **Frontend neu gebaut**, nach Update neu laden (Strg+F5).

Direkt aus dem User-Test: nach **Aktivieren des Telemetrie-Sharings** im
Datenschutz-Tab zeigte das Dashboard nur noch den blauen Hintergrund —
auch nach Neustart, und man kam nicht mehr an den Toggle, um es
rueckgaengig zu machen.

### Fixed

- **White-Screen beim Telemetrie-Sharing.** Ursache: im Datenschutz-Tab
  wurde die Intervall-Auswahl (`<SelectInput>`) genutzt, aber die
  Komponente war in `SettingsPage.jsx` **nicht importiert**. Das wirft erst
  **zur Laufzeit** `SelectInput is not defined` — und nur, wenn der
  Toggle AN ist (vorher rendert die Auswahl nicht). Ein gruener Build
  faengt so einen undefinierten Komponenten-Verweis nicht. Import ergaenzt;
  im echten Browser gegen eine DB-Kopie mit aktivierter Telemetrie
  verifiziert (Auswahl rendert, 0 Konsolen-Fehler).

### Added — Robustheit

- **App-weite ErrorBoundary** (`components/ErrorBoundary.jsx`). Bisher hat
  ein einzelner Render-Fehler den **ganzen** React-Baum mitgerissen — der
  User sah nur Blau und kam an keine Einstellung mehr. Jetzt zeigt der
  betroffene Tab eine Fehlerkarte (mit „nochmal versuchen" / „neu laden"),
  **die Sidebar bleibt bedienbar**, man kann woanders hin navigieren. Per
  `key={page}` resettet die Boundary beim Tab-Wechsel automatisch.

### Added — Telemetrie als MCP (Recovery + „alles als MCP")

- **`telemetrie_status()`** und **`telemetrie_setzen(aktiv, intervall_tage)`**
  — Claude kann den Telemetrie-Stand lesen und das Sharing abschalten,
  auch wenn das Dashboard mal nicht erreichbar ist. Tool-Count
  **172 → 174**.

### Tests

- `test_v17_telemetrie_mcp_93.py` (5 Faelle: Status, An/Aus-Recovery,
  Intervall, ungueltiges Intervall, Leer-Aufruf). Registry auf 174.
  Browser-Verifikation des Fixes via Playwright gegen Real-DB-Kopie.

### Schema

**Keine Schema-Aenderung.** Bleibt v45.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.93.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.93.zip)
2. **Entpacken + Doppelklick `INSTALLIEREN.bat`**

### macOS

`INSTALLIEREN.command` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

```bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
```

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.92] - 2026-06-03 — Ablehnungsgruende: Loeschen + Umbenennen (User-Test-Fix #663 C20)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **Frontend neu gebaut** —
> nach dem Update einmal neu laden. Direkt aus dem User-Test gekommen.

Im Bewertung-Tab konnte man Ablehnungsgruende bisher nur **deaktivieren**.
Beim Test kamen drei berechtigte Wuensche: (1) das Deaktivieren gab kein
sichtbares Feedback, (2) man will Gruende richtig **loeschen** — und dann
festlegen, welchem anderen Grund die bisher so aussortierten Stellen
zugeordnet werden, (3) Gruende mit Tippfehlern **umbenennen**.

### Added

- **Loeschen mit Neuzuordnung** — Papierkorb-Button pro Grund. Hat der
  Grund bereits aussortierte Stellen, fragt ein Dialog, welchem **anderen**
  Grund diese Stellen zugeordnet werden sollen (Default `sonstiges`), bevor
  geloescht wird. Keine Stelle bleibt ohne gueltigen Grund zurueck.
- **Umbenennen (inline)** — Stift-Button pro Grund. Korrigiert Tippfehler
  und **zieht die bestehenden `jobs.dismiss_reason`-Werte mit** — der
  falsch geschriebene Wert verschwindet komplett aus den Daten. Kollidiert
  der neue Name mit einem vorhandenen Grund, werden beide zusammengefuehrt
  (Merge, usage_count addiert).
- **MCP-Tool `ablehnungsgrund_loeschen(grund_id, neu_zuordnen_zu)`** — damit
  Claude das Gleiche kann. Tool-Count **171 → 172**.
- DB: `rename_dismiss_reason` (Cascade + Merge), `delete_dismiss_reason`
  (Pflicht-Neuzuordnung bei Verwendung). REST: `DELETE
  /api/dismiss-reasons/{id}` (Body `{reassign_to}`); `PATCH` mit `label`
  cascaded jetzt.

### Changed

- **`ablehnungsgrund_umbenennen`** schreibt jetzt die jobs-Tabelle mit
  (vorher bewusst nicht — fuer Tippfehler-Korrektur aber genau richtig).
- **Deaktivieren/Aktivieren** gibt jetzt einen Toast als klares Feedback
  ("X deaktiviert."). Das adressiert das "passiert nichts"-Gefuehl.

### Tests

- `test_v17_ablehnungsgruende_c20_663.py` um 6 Faelle erweitert
  (Cascade-Rename, Merge, Delete ohne/mit Verwendung, Pflicht-Neuzuordnung,
  MCP-Loeschen). Registry auf 172. Volle Suite gruen.

### Schema

**Keine Schema-Aenderung.** Bleibt v45 (nutzt bestehende Tabellen).

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.92.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.92.zip)
2. **Entpacken + Doppelklick `INSTALLIEREN.bat`**

### macOS

`INSTALLIEREN.command` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

```bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
```

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.91] - 2026-06-02 — QA-Selbsttest + Doku-Sync (Wiki beta.74 → beta.90)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **Kein Verhaltens- oder
> UI-Change gegenueber beta.90** — das Frontend-Bundle ist unveraendert
> (Version wird vom Backend gelesen, nicht ins Bundle gebacken). Dein fuer
> morgen geplanter Test der beta.90-Oberflaeche gilt also 1:1 weiter; diese
> Version ergaenzt nur Doku + einen winzigen Fallback-Fix.

Autonomer QA-Lauf: alles selbst durchgetestet, Workflow analysiert, Wiki
gegen den Code-Stand abgeglichen. Befund: das Wiki war auf **beta.74**
eingefroren (152 Tools / 23 Prompts / Schema v42), waehrend der Code bei
**beta.90** steht (171 / 24 / v45). Komplett nachgezogen.

### Added

- **`docs/QA-Audit-beta90.md`** — technischer Beleg des Selbsttests:
  was getestet wurde (volle Suite, Migration v43→v45 auf Real-DB-**Kopie**,
  10/10 REST-Endpoints via TestClient), Drift-Tabelle, Liste der
  undokumentierten beta.78-90-Features, Workflow-Analyse mit rauen Kanten.
- **`tools/qa_rest_smoke.py`** — REST-Smoke-Harness (FastAPI TestClient,
  kein Port-Binding) gegen eine migrierte DB-Kopie. Pfad via `QA_DATA_DIR`
  ueberschreibbar.

### Changed

- **`pbp_capabilities`** — der Fallback-Text fuer die Tool-Gesamtzahl (greift
  nur wenn die MCP-Registry-Introspektion fehlschlaegt) sagte stale `~152`,
  jetzt `~171`. Der Normalpfad zaehlt ohnehin dynamisch (war korrekt).
- **`CLAUDE.md`** — Header `zuletzt beta.74` → `beta.90`; neuer Stand-Block
  (Schema v45, 171 Tools, 24 Prompts, 1611 Tests, Modul-Aufschluesselung).

### Docs (Wiki, separates Repo PBP.wiki)

- Stale Zahlen Wiki-weit korrigiert: 171 Tools, 24 Prompts, Schema v45,
  beta.90, 1611 Tests (Home, Architektur, MCP-Tools, Master-Plan,
  Plan-MCP-Layer/-Datenbasis, Workflows, Master-Plan-Optimierung).
- Neue User-Doku fuer die beta.78-90-Welle: Dokument-Lifecycle (#657/#658)
  + Routing (#643) in Tab-Dokumente; TODOs/Tasks (#666) + Follow-up-
  Direkt-Abhaken + Dubletten-Check (#665) in Tab-Bewerbungen;
  Ablehnungsgruende-Editor (#663) als 9. Einstellungen-Tab; MINUS-Keywords
  (#667) in Suchkriterien; Wiedergaenger-Erkenner (#671),
  `stelle_reaktivieren` (#664), verfeinerte Duplikat-Erkennung (#670) in
  Tab-Stellen. Plan-* Sub-Pages (B/C/D/F/G) auf beta.90 nachgezogen.

### Schema

**Keine Schema-Aenderung.** Bleibt v45.

### Tests

- Volle Suite: **1611 passed, 1 skipped** (1612 collected).
  `test_mcp_registry.py` bestaetigt 171 Tools.

### Offene Issues (Hinweis)

Die in beta.78-90 umgesetzten Issues (#657-#671) bleiben bewusst **offen**
als deine Test-Checkliste fuer morgen — sie werden nach erfolgreichem
User-Test geschlossen, nicht vorher.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.91.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.91.zip)
2. **Entpacken + Doppelklick `INSTALLIEREN.bat`**

### macOS

`INSTALLIEREN.command` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

```bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
```

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.90] - 2026-06-02 — Frontend: Ablehnungsgruende-Editor + Tasks + Direkt-Abhaken (#663 C20 + #666 D19 + #665 D18)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Schliesst die Frontend-Reihe ab (C20/D18/D19). Build gruen. **Blind gebaut — bitte morgen visuell gegenchecken.**

### Added — Frontend

- **#663 (C20): Ablehnungsgruende-Editor** — neuer Tab "Bewertung" in den Einstellungen. Listet alle Gruende (mit Verwendungs-Haeufigkeit + "eigen"-Badge), erlaubt Anlegen neuer Custom-Gruende und Aktivieren/Deaktivieren bestehender. Verdrahtet an `/api/dismiss-reasons` (GET/POST/PATCH). Aktive Custom-Gruende stehen Claude bei `stelle_bewerten` zur Verfuegung (dynamische Whitelist aus beta.85).
- **#666 (D19): Aufgaben-Sektion im Bewerbungs-Detail** — Tasks/Todos pro Bewerbung in der Timeline-Ansicht. Anlegen (Titel + Enter), Abhaken (Toggle erledigt/offen), Loeschen. Zeigt "(N offen)" im Header. Verdrahtet an `/api/applications/{id}/tasks` + `/api/tasks/{id}/complete|reopen` + DELETE.
- **#665 (D18): Direkt-Abhaken-Button** — Check-Icon auf jeder Follow-up-Zeile in "Offene Aktionen". Ein Klick markiert den Nachfass als erledigt (`/api/follow-ups/{id}/complete`), ohne Umweg ueber Timeline oder Claude. `stopPropagation`, damit der Zeilen-Klick (Timeline oeffnen) nicht mit ausgeloest wird.

### Bug gefangen beim Bauen

- C20-Toast-Aufrufe nutzten faelschlich die Objekt-Form `pushToast({tone, message})` — die echte Signatur ist positional `pushToast(message, tone)`. Vor dem Build korrigiert (haette sonst `[object Object]`-Toasts gezeigt). Genau die Klasse Fehler, die ein gruener Build nicht faengt — daher der Hinweis: morgen visuell pruefen.

### Frontend-Build

- `pnpm exec vite build` gruen. Neue Assets committed, alte Hash-Datei entfernt. **Damit ist Cluster-Frontend B20/C20/D18/D19 komplett.**

### Schema

**Keine Schema-Aenderung.** Reine Frontend-Arbeit gegen bestehende REST-Endpoints (beta.85). Schema bleibt v45.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.90.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.90.zip)
2. **Entpacken + Doppelklick \`INSTALLIEREN.bat\`**

### macOS

\`INSTALLIEREN.command\` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
\`\`\`

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.89] - 2026-06-02 — Frontend: Minus-Keywords-Sektion (#667 B20)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Erste **Frontend**-Beta der B20/C20/D18/D19-Reihe. Keine neuen Tests (Backend unveraendert), Frontend gebaut.

### Added — Frontend

- **#667 (B20): Minus-Keywords-Sektion im Suchkriterien-Editor** (ProfilePage). Neue vierte Keyword-Kategorie zwischen PLUS und Ausschluss:
  - **MINUS-Keywords (weiche Abwertung)** — Chip-Editor mit amber-Farbe, Platzhalter "z.B. Automotive, SAP-only"
  - **Ausschluss-Keywords (harter Filter)** — Label klargestellt zur Abgrenzung
  - Neuer **Gewicht-Slider "MINUS-Abzug"** (coral) in der Gewichtungs-Sektion — steuert den Score-Malus pro Treffer (0 = wirkungslos). Speichert ueber `criteria.gewichtung.minus`.
- Verdrahtet an das bestehende Backend aus beta.84 (`keywords_minus` + `gewichtung.minus`). Speichern/Laden ueber `/api/search-criteria` ohne Backend-Aenderung.

### Frontend-Build

- `pnpm exec vite build` gruen. Neue Assets unter `static/dashboard/assets/` committed, alte Hash-Datei `git rm`-t. CSS unveraendert.

### Bekannt nicht enthalten (kommen in eigenen Frontend-Betas)

Die Backend + REST-API fuer alle drei sind seit beta.85 fertig — die React-Sektionen folgen einzeln, weil sie in grosse stateful Pages (SettingsPage ~3000 Zeilen, ApplicationsPage ~2500) integriert werden und im Live-Dev-Umfeld visuell verifiziert werden sollten:

- **C20** — Ablehnungsgruende-Editor im Tab Einstellungen (REST: `GET/POST/PATCH /api/dismiss-reasons`)
- **D19** — Tasks-pro-Bewerbung-Sektion im Bewerbungs-Detail (REST: `/api/applications/{id}/tasks`)
- **D18** — Direkt-Abhaken-Buttons in "Offene Aktionen" (REST: `/api/tasks/{id}/complete`, `/api/follow-ups/{id}/complete`)

Alle drei sind ueber MCP-Tools bereits voll bedienbar — Claude kann sie sofort nutzen.

### Schema

**Keine Schema-Aenderung.** Schema bleibt v45.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.89.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.89.zip)
2. **Entpacken + Doppelklick \`INSTALLIEREN.bat\`**

### macOS

\`INSTALLIEREN.command\` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
\`\`\`

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.88] - 2026-06-02 — Elwosa KI-freies Safety-Net (#669, Teil 1)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **+8 neue Tests, 1611 passed.** Keine Schema-Aenderung. **Ohne lokale KI.**

### Hintergrund (#669)

Elwosa schwieg seit Sonntag — `messages_today: 0` am Dienstag, nicht mal die Morgen-Linie. Diagnose: zwei KI-freie Luecken im Trigger-Pfad.

**Wichtig:** #669 fordert mittelfristig eine zweistufige KI-Architektur (Ollama-Live-Generierung als Standard, Claude-Eskalation). Das ist **Ebene 1/2** und bleibt offen (Plan F15). Diese Beta liefert das **KI-freie Fundament**: Elwosa darf nie wieder dauerhaft schweigen, egal ob Ollama laeuft oder nicht.

### Fixed

- **Validierungs-Retry in `speak()`** (`_pick_valid_line`): Vorher fiel Elwosa fuer einen Tick still, wenn die zufaellig gewaehlte Linie die Sprach-DNA-Validierung nicht bestand (eine kaputte Linie → Schweigen). Jetzt werden bis zu 6 Kandidaten probiert, bevor aufgegeben wird.
- **Tageslebenszeichen-Garantie** (`ensure_daily_lifesign`): Die Morgen-Linie feuerte nur, wenn die Auto-Engine im 6-11-Uhr-Fenster tickte. Tickt sie erst nachmittags, gab `detect_world_trigger()` an einem Wochentag `None` → Schweigen den ganzen Tag. Jetzt: wenn HEUTE noch nichts gepostet wurde und es nach 6 Uhr ist, wird die passende Tageszeit-Linie aus dem rotierenden Pool gepostet — unabhaengig vom engen Welt-Trigger-Fenster. Respektiert weiterhin enabled/pause/cooldown/tonfall_modus.

### Changed

- `dashboard.py:_run_elwosa_speak` ruft nach den Welt-/Idle-Checks `ensure_daily_lifesign` auf, falls noch nichts gepostet wurde.
- Der rotierende Fallback-Pool (`pick_line` faellt auf den vollen Pool zurueck, wenn alle Linien der letzten 7 Tage gesehen wurden) war bereits vorhanden und greift weiterhin — `pending: 0` fuehrt damit nie zu Dauerschweigen.

### Bekannt nicht enthalten (Ebene 1/2, Plan F15)

- **Ollama-Live-Generierung bei Events** (Standardweg laut #669) — optional, separate Beta. Braucht lokale KI.
- **Claude-Eskalation** fuer anspruchsvolle Situationen — separate Beta.

### Schema

**Keine Schema-Aenderung.** Reine Logik in `services/elwosa.py` + `dashboard.py`. Schema bleibt v45.

### Tests

8 neue in `tests/test_v17_elwosa_lifesign_669.py` — Validierungs-Retry (kaputte Linie uebersprungen), Tageslebenszeichen (Vormittag + Nachmittag), kein Doppel-Post, tiefe Nacht, disabled. Volle Suite: **1611 passed, 1 skipped** (vorher 1603).

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.88.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.88.zip)
2. **Entpacken + Doppelklick \`INSTALLIEREN.bat\`**

### macOS

\`INSTALLIEREN.command\` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
\`\`\`

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.87] - 2026-06-02 — Duplikat-Erkennung verfeinert + force-Override (#670)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **+6 neue/geaenderte Tests, 1603 passed.** Keine Schema-Aenderung.

### Hintergrund (#670)

`stelle_manuell_anlegen` blockierte das Anlegen einer zweiten, inhaltlich verschiedenen Stelle derselben Firma als vermeintliches Duplikat. Konkret: zwei verschiedene PLM-Rollen bei derselben Firma ("PLM Project Manager" + "PLM Product Owner") wurden geblockt, weil sie ein einzelnes Domain-Keyword ("PLM") teilten. Schlimmer: `firma_plus_zeitnaehe` blockte sogar bei `shared_tokens: []` — also pro Firma nur eine Stelle pro Zeitfenster.

### Fixed

- **Ein einzelnes geteiltes Domain-Keyword blockt nicht mehr.** Die Duplikat-Entscheidung haengt jetzt an der **Titel-Aehnlichkeit** (Token-Set + Domain-Bonus), die einen Schwellwert (0.5) erreichen muss. "PLM Project Manager" vs "PLM Product Owner" (sim 0.4) gilt nicht mehr als Duplikat.
- **`firma_plus_zeitnaehe` alleine blockt nicht mehr.** Zeitnaehe ist nur noch ein Ranking-Tiebreaker unter bereits qualifizierten Kandidaten, NIE ein Standalone-Trigger. Bei `shared_tokens: []` kommt gar keine Warnung mehr.
- **Unterschiedliche URLs sind ein starkes Trennsignal.** Bei verschiedenen nicht-leeren URLs wird nur noch bei nahezu identischem Titel (Schwellwert 0.85) ein Duplikat angenommen.
- Der Schwellwert-Vergleich passiert auf der reinen Titel-Aehnlichkeit (ohne Zeit-Bonus), damit Zeitnaehe einen knappen Nicht-Treffer nicht ueber die Grenze hebt.

### Added

- **`stelle_manuell_anlegen(..., force=False)`** — neuer Parameter. `force=True` legt eine Stelle trotz erkanntem Duplikat-Verdacht an. Der Verdacht wird im Erfolgs-Result als `duplikat_uebersteuert` (Stufe, Grund, shared_tokens, existierende ID/Hash) transparent gemeldet. Statt "Stelle geht verloren" hat der Aufrufer jetzt die Wahl.

### Abgrenzung zu #671

- **#670** (dieser Fix): identische/aehnliche *aktive* Stellen → Anlage-Block, jetzt feiner + Override.
- **#671** (beta.86): frueher *verworfene* Wiedergaenger → Auto-Markierung.

### Schema

**Keine Schema-Aenderung.** Reine Logik-Verfeinerung in `duplicate_detection.py` + `stelle_manuell_anlegen`. Schema bleibt v45.

### Tests

- `tests/test_v17_duplikat_670.py` (5 neu): Tchibo-Doppelrolle anlegbar, Zeitnaehe-ohne-Titel kein Block, URL-Match weiter erkannt, force-Override, Gegentest ohne force.
- `tests/test_duplicate_detection.py` aktualisiert: zwei Tests dokumentieren jetzt das #670-Verhalten (single-keyword + Zeitnaehe blocken nicht; URL-Match faengt reale Reposts).

Volle Suite: **1603 passed, 1 skipped** (vorher 1597).

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.87.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.87.zip)
2. **Entpacken + Doppelklick \`INSTALLIEREN.bat\`**

### macOS

\`INSTALLIEREN.command\` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
\`\`\`

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.86] - 2026-06-02 — Wiedergaenger-Erkenner, KI-frei (#671)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **+13 neue Tests, 1597 passed.** Keine Schema-Aenderung. **Komplett ohne lokale KI** (Architektur-Leitplanke aus #671).

### Hintergrund (#671)

Dieselbe Stelle (bzw. ihre Geschwister derselben Firma + Domaene) taucht ueber verschiedene Scrapes immer wieder als "neuer Fund" auf und wird jedes Mal bis zur vollen Detailbewertung durchgeschleift — obwohl sie schon mehrfach aus identischem Grund verworfen wurde. Konkret: Tchibo GmbH PLM-Rolle wurde 2x als `falsches_fachgebiet` aussortiert, taucht beim 3. Scrape (neuer Hash, andere Quelle) wieder als frischer Fund auf.

**Architektur-Leitplanke (User-Vorgabe):** PBP-Kernfunktionen duerfen lokale KI NIE voraussetzen. Manche User wollen bewusst gar kein Ollama. Daher die gestufte Verteidigung:

- **Ebene 0 — deterministischer DB-Check (immer, ohne KI):** traegt das Feature allein.
- **Ebene 1 — Ollama (optional):** semantische Verfeinerung — in dieser Beta NICHT enthalten, bleibt Plan-Item F16-Sub.
- **Ebene 2 — Claude-Kontext in `fit_analyse`:** greift unabhaengig von Ollama.

beta.86 liefert **Ebene 0 + Ebene 2** — beide KI-frei.

### Added

- **`services/wiedergaenger.py`** (Ebene 0, reines Python): `find_wiedergaenger_pattern(db, company, title, schwellwert=2)` sucht aussortierte Stellen DERSELBEN FIRMA mit Titel-Domaenen-Token-Ueberlappung, aggregiert nach `dismiss_reason`. Firmen-Normalisierung (Rechtsform-Suffixe raus: "Tchibo GmbH" == "Tchibo"), Domaenen-Token-Extraktion (generische Rollen-/Gender-Woerter raus, nur fachliche Tokens wie "plm" zaehlen als Ueberlappung). `auto:`-Prefix-Normalisierung.
- **MCP-Tool `stelle_wiedergaenger_pruefen(job_hash="", firma="", titel="", schwellwert=2, auto_aussortieren=False)`** — exponiert Ebene 0. Mit `auto_aussortieren=True` + `job_hash` wird die Stelle direkt mit `dismiss_reason='wiedergaenger:<grund>'` aussortiert. Default nur melden.
- **Ebene 2 in `fit_analyse`:** firma-verankerter Wiedergaenger-Check (im Gegensatz zum bestehenden token-Jaccard `outcome_pattern`, das ueber alle Firmen geht). Neues Result-Feld `wiedergaenger` + Risk-Eintrag.
- 13 neue Tests in `tests/test_v17_wiedergaenger_671.py` — alle ohne Ollama.

### Changed

- **`_build_empfehlung` (fit_analyse-Verdict):** ein Wiedergaenger mit **fachlichem** k.o.-Grund (`falsches_fachgebiet`/`zu_junior`/`zu_senior`/`kein_hochschulabschluss`/`unpassendes_arbeitsmodell`) und `anzahl >= 2` setzt die Empfehlung auf `NICHT_EMPFOHLEN`. Nicht-fachliche Gruende (Gehalt, Entfernung) taugen NICHT als k.o. — die koennen sich aendern.
- MCP-Tool-Count: 170 → **171**.

### Abgrenzung zu #670

- **#670** (active duplicates): identische *aktive* Stellen derselben Firma → Anlage-Block.
- **#671** (revenants): frueher *verworfene* Stellen, die wiederkommen → Auto-Markierung/Aussortierung.

### Schema

**Keine Schema-Aenderung.** Nutzt die bestehende `jobs`-Tabelle (`is_active=0` + `dismiss_reason`). Schema bleibt v45.

### Bekannt nicht enthalten

- **Ebene 1 (Ollama-Verfeinerung):** optional, separate Beta. Plan-Sub-Item zu F16.
- **Auto-Engine-Step** der neue Stellen beim Scrapen automatisch gegen die Wiedergaenger-Historie prueft — kommt separat. Aktuell: Tool-Aufruf durch Claude + fit_analyse-Kontext.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.86.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.86.zip)
2. **Entpacken + Doppelklick \`INSTALLIEREN.bat\`**

### macOS

\`INSTALLIEREN.command\` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
\`\`\`

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.85] - 2026-06-02 — Backend-Bundle: Tasks + Ablehnungsgrunde-Editor + Scraper-Auto-Skip (#666 + #663 + #668)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **Backend-only.** Schema-Aenderung v44→v45 mit Auto-Backup. **+22 neue Tests, 1584 passed.**

### Geplanter Scope vs. tatsaechlich geliefert

Diese Beta sollte urspruenglich Backend + Frontend fuer B20+C20+D18+D19 + Bug #668 in einem Wurf liefern. Realistisch-pragmatischer Schwenk: Backend ist solide getestet (22 neue Tests), Frontend (4 Sektionen + Direkt-Abhaken-Buttons) kommt in **beta.86** mit User-Live-Feedback. Die Backend-Bestandteile sind ueber MCP-Tools voll nutzbar — Claude kann alle vier Themen direkt bedienen, ohne dass das Frontend nachgezogen sein muss.

### Schema v44 → v45 (additiv, mit Auto-Backup)

- **Neue Tabelle `tasks`** (#666 D19): id, application_id, profile_id, typ, titel, beschreibung, faellig_am, status (offen/erledigt/hinfaellig), erledigt_am, notiz, created_at, updated_at. Plus 3 Indizes (app_id, status+faellig_am, profile_id+status).
- **Neue Spalte `dismiss_reasons.is_active`** (#663 C20). Default 1. Erlaubt Deaktivierung statt Loeschen — Statistik bleibt erhalten.
- Pre-Migration-Backup automatisch unter `data/backups/pbp.db.bak-pre-v45-tasks-<timestamp>`.

### Added — MCP-Tools

**Tasks (#666 D19) — 4 neue Tools in `tools/tasks.py`:**
- `todo_anlegen(bewerbung_id, titel, faellig_am="", beschreibung="", typ="custom")` — typ custom/nachfass/termin/vorbereitung
- `todo_erledigen(todo_id, notiz="")` — idempotent, markiert als 'erledigt' mit optionaler Abschluss-Notiz
- `todo_reaktivieren(todo_id)` — setzt zurueck auf 'offen'
- `todos_anzeigen(bewerbung_id="", nur_offen=False)` — sortiert nach status + faellig_am

**Ablehnungsgruende (#663 C20) — 4 neue Tools in `tools/suche.py`:**
- `ablehnungsgruende_anzeigen(nur_aktiv=False)` — mit Verwendungs-Haeufigkeit
- `ablehnungsgrund_anlegen(label)` — neuer Custom-Grund, Duplikat-Check
- `ablehnungsgrund_umbenennen(grund_id, neues_label)` — historische Werte in jobs-Tabelle bleiben unveraendert
- `ablehnungsgrund_aktivieren_setzen(grund_id, aktiv)` — Deaktivierung statt Loeschen

### Added — REST-Endpoints (fuer kommendes Frontend in beta.86)

- `PATCH /api/dismiss-reasons/{id}` — label + is_active in einem Call
- `GET /api/applications/{id}/tasks?offen=N` — Tasks pro Bewerbung
- `GET /api/tasks?offen=N` — alle Tasks des aktiven Profils
- `POST /api/applications/{id}/tasks` — Task anlegen
- `POST /api/tasks/{id}/complete` — erledigen mit Notiz
- `POST /api/tasks/{id}/reopen` — wieder oeffnen
- `DELETE /api/tasks/{id}` — loeschen

### Changed

- **`stelle_bewerten` akzeptiert jetzt Custom-Ablehnungsgruende.** Wenn der User via `ablehnungsgrund_anlegen` einen Grund angelegt hat und dieser `is_active=1` ist, wird er in `_normalize_reason_list` nicht mehr auf 'sonstiges' normalisiert (#663 C20). Beispiel: nach `ablehnungsgrund_anlegen("kein_homeoffice")` ist `stelle_bewerten(..., gruende=["kein_homeoffice"])` zulaessig.

### Fixed

- **#668** Defekte Scraper blockieren nicht mehr die Gesamt-Suche. Zusaetzlich zur bestehenden `is_active=0`-Filter wird jetzt auch `consecutive_failures >= 5` als "dauerhaft defekt" behandelt und vor dem Start des Search-Jobs ausgefiltert. Vorher liefen Quellen wie ferchau/gulp/ingenieur_de/heise_jobs/kimeta/solcom trotz 8 Fehlern in Serie weiter mit, weil die Auto-Deaktivierung nicht griff — Folge: 10-Min-Total-Timeout mit 0 Ergebnissen. Hard-Skip-Schwelle bei 5 Fehlern in Serie ist Kompromiss aus Toleranz (kurze Aussetzer ueberbruecken) und Selbstschutz.

### Migration

Schema v44 → v45 ist ALTER-only, idempotent und reversibel. Vor der Migration wird automatisch ein Backup unter `%LOCALAPPDATA%\BewerbungsAssistent\data\backups\` angelegt.

**Rollback (falls noetig):**
1. PBP beenden.
2. Backup-Datei aus `data\backups\` zurueck nach `data\pbp.db` kopieren.
3. Alte PBP-Version installieren.

### Tests

22 neue:
- `tests/test_v17_tasks_d19_666.py` — Tasks-Tabelle + 4 Tools (12 Tests)
- `tests/test_v17_ablehnungsgruende_c20_663.py` — Schema + 4 Tools + dyn. Whitelist (10 Tests)

MCP-Tool-Count: 162 → **170** (+8). Volle Suite: **1584 passed, 1 skipped** (vorher 1562).

### Bekannt nicht enthalten (kommt in eigenen Betas)

- **Frontend-Sektionen** fuer B20 (Minus-Keywords) + C20 (Ablehnungsgruende-Editor) + D19 (Tasks pro Bewerbung) + D18 (Direkt-Abhaken-Buttons). Backend + REST-API sind alle vorbereitet — die Frontend-Komponenten kommen mit deinem Live-Feedback in **beta.86**.
- **Teilergebnis-Persistierung bei Gesamt-Timeout** (#668-Subitem) — separat in beta.86, weil das den Job-Runner anfasst.
- **#670** (Bug) `stelle_manuell_anlegen` Duplikat-Erkennung zu grob → Plan-Eintrag **B22 ⬜** (separate Beta).
- **#669** (Feature) Elwosa Ollama-Live-Generierung → Plan-Eintrag **F15 ⬜** (separate Beta wie geplant).
- **#671** (Feature) Wiedergaenger-Erkenner mit Ollama-Vorabfilter → Plan-Eintrag **F16 ⬜** (separate Beta, baut auf #669 auf).

### Pre-Release-Issue-Check

Vor dem Release wurde die offene Issue-Liste nochmal abgerufen (Regel aus beta.82). **Zwei neue Issues sind waehrend der Backend-Arbeit dazwischen gekommen** (#670, #671) — bewusst aus diesem Backend-Bundle rausgehalten und als Plan-Items B22/F15/F16 dokumentiert. Die Regel funktioniert.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.85.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.85.zip)
2. **Entpacken + Doppelklick \`INSTALLIEREN.bat\`**

### macOS

\`INSTALLIEREN.command\` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
\`\`\`

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner \`data\backups\\\`).

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.84] - 2026-06-02 — Minus-Keywords als weiche Score-Abwertung (#667, B19)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **+11 neue Tests, 1562 passed.** Keine Schema-Aenderung.

### Hintergrund (#667)

User-Wort: *"Wo Plus ist, muss es auch Minus geben."*

Bisher gab es drei Keyword-Kategorien:
- **Muss** — mindestens eins muss vorkommen, sonst zaehlt die Stelle nicht
- **Plus** — erhoeht den Score
- **Ausschluss** — kommt eins vor → Stelle wird komplett ignoriert

Es fehlte das Gegenstueck zu Plus: ein weicher Malus, der den Score senkt, die Stelle aber nicht komplett verschwinden laesst. Ausschluss war fuer viele Faelle zu radikal (z.B. "Automotive" oder "Versicherung" — nicht per se k.o., aber Passung gesenkt).

### Added

- **#667 (B19) Vierte Kategorie `keywords_minus`** als Gegenstueck zu `keywords_plus`:
  - In `suchkriterien_setzen(keywords_minus=[...])` als neuer Parameter
  - In `suchkriterien_bearbeiten(kategorie='minus', ...)` als vierte Kategorie
  - In `suchkriterien_anzeigen()` mit zurueckgegeben (durch get_search_criteria)
- **Scoring-Engine** (`job_scraper/__init__.py:fit_analyse` und `calculate_score`):
  - Pro Minus-Treffer wird ein Malus abgezogen (Default-Gewicht 1, konfigurierbar via `criteria["gewichtung"]["minus"]`)
  - Neuer Result-Key `minus_hits` in `fit_analyse`
  - Risk-Eintrag ab 2+ Minus-Treffern fuer Transparenz
- 11 neue Tests in `tests/test_v17_minus_keywords_667.py`: Tools (set/edit/anzeigen) + Scoring-Engine (fit_analyse + calculate_score) + Risk-Schwelle + Default-Gewicht + Abgrenzung gegen Ausschluss.

### Wann was nutzen — Abgrenzung

- **Ausschluss** bleibt: harter Filter fuer echte k.o.-Begriffe (Junior, Werkstudent, Zeitarbeit, Bauwesen)
- **Minus** neu: weiche Abwertung fuer "unschoen, aber nicht disqualifizierend"
  - Beispiele: "Automotive", "Versicherung", "Beratungshaus", "SAP-only", "Customizing-lastig"

### Schema

**Keine Schema-Aenderung.** `search_criteria` ist ein generisches Key-Value-Store (Profile-ID + Key + JSON-Value), `keywords_minus` ist nur ein neuer Key im bestehenden Schema. Schema bleibt v44.

### Bekannt nicht enthalten

- **Frontend-Sektion fuer Minus-Keywords im Tab Einstellungen** — kommt als separate Beta zusammen mit den anderen Frontend-Sektionen (#665 Direkt-Abhaken, #666 Aufgaben-System).
- **`scoring_konfigurieren`-Slider fuer das Minus-Gewicht** — Default 1 reicht; wer ein anderes Gewicht will, kann es via `criteria["gewichtung"]["minus"]` setzen.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.84.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.84.zip)
2. **Entpacken + Doppelklick \`INSTALLIEREN.bat\`**

### macOS

\`INSTALLIEREN.command\` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
\`\`\`

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.83] - 2026-06-02 — nachfass_planen Dubletten-Check (#665 MCP-Teil)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **+6 neue Tests, 1551 passed.** Keine Schema-Aenderung.

### Fixed / Changed

- **#665 (MCP-Teil)** `nachfass_planen()` legt nicht mehr stillschweigend einen zweiten Nachfass an, wenn fuer dieselbe Bewerbung schon ein offener existiert. Neuer Parameter `wenn_dublette` mit vier Modi:
  - **`melden`** (Default) — KEIN Insert, liefert `status="dublette_offen"` mit Details zum bestehenden Nachfass + drei konkreten Handlungsoptionen. Claude fragt den User und ruft mit explizitem `wenn_dublette` erneut auf.
  - **`vorhandenen_erledigen`** — alten auf `gesendet` + neuen anlegen (Default-Empfehlung, wenn User aktiv neu plant).
  - **`vorhandenen_verschieben`** — alten auf das neue Datum verschieben statt zweiten Eintrag.
  - **`trotzdem_neu`** — alten lassen + neuen anlegen (Legacy-Verhalten fuer bewusste Dubletten).
- Dubletten-Check greift NUR fuer `typ='nachfass'`. `danke`/`info`-Follow-ups sind situativ und werden NICHT dedupliziert.
- Tool-Signatur bleibt kompatibel: `wenn_dublette='melden'` ist Default, bestehende Aufrufer brechen nicht — sie erhalten bei Dublette jetzt eine klare Meldung statt einen versteckten zweiten Eintrag.
- 6 neue Tests in `tests/test_v17_nachfass_dublette_665.py`.

### Bekannt nicht enthalten (eigene Beta)

- **#665 Frontend-Teil** (Direkt-Abhaken-Button in "Offene Aktionen" und Bewerbungs-Detail) — braucht React-Komponenten + Frontend-Build. Plan-Eintrag **D18** ⬜.
- **#666 (groß, eigenes Issue)** generisches Aufgaben-/Todo-System pro Bewerbung mit eigener `tasks`-Tabelle, freien Custom-Todos und drei neuen MCP-Tools. Baut auf #665 auf. Plan-Eintrag **D19** ⬜.
- **#667** Minus-Keywords (weiche Score-Abwertung zusaetzlich zu harten Ausschluss-Keywords). Betrifft 11 Dateien (Schema + Scoring-Engine + 3 MCP-Tools + Frontend) — bewusst aus dieser Beta rausgehalten, kommt als eigene Beta. Plan-Eintrag **B19** ⬜.

### Schema

**Keine Schema-Aenderung.** beta.83 ist additiv (1 Parameter + Dubletten-Logik). Schema bleibt v44.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen)

1. **ZIP:** [PBP-1.7.0-beta.83.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.83.zip)
2. **Entpacken + Doppelklick \`INSTALLIEREN.bat\`**

### macOS

\`INSTALLIEREN.command\` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
\`\`\`

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.82] - 2026-06-02 — `stelle_reaktivieren` + Pre-Release-Issue-Check (#664)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Nachzieher zu beta.81 fuer Issue #664 — das waehrend des beta.81-Release-Prozesses dazwischen kam. **+5 neue Tests, 1545 passed.** Keine Schema-Aenderung.

### Added

- **#664 (enhancement)** Neues MCP-Tool `stelle_reaktivieren(job_hash, grund="")` — Gegenstueck zu `stelle_bewerten('passt_nicht')`. Setzt `is_active=1`, loescht `dismiss_reason`, idempotent bei bereits aktiven Stellen. Analog zu `dokument_reaktivieren()` aus beta.79. Schliesst eine konkrete Luecke im Anti-DB-Bypass-Pattern (#514, H9) — vorher musste Claude bei einer irrtuemlich aussortierten Stelle in den DB-Bypass.
- 5 neue Tests in `tests/test_v17_stelle_reaktivieren_664.py`: Standard-Reaktivierung, Kurzhash-Aufloesung, Idempotenz, Fehlerpfad, End-to-End-Check (Stelle taucht wieder in `stellen_anzeigen()` auf).

### Changed

- **CLAUDE.md**: neuer Pflicht-Schritt im Release-Workflow:
  > **Pre-Release-Issue-Check (HART, seit beta.82):** unmittelbar vor `gh release create` IMMER die aktuelle offene Issue-Liste auf GitHub abrufen und mit den in der Session adressierten Issues abgleichen. Wenn ein neues Issue dazwischen gekommen ist, das in diesen Release gehoert haette, den Release zurueckhalten.

  Hintergrund: beta.81 wurde zu frueh veroeffentlicht — waehrend Tests + CHANGELOG liefen, kam #664 rein und musste in eine hektische beta.82 nachgezogen werden. Diese Regel verhindert das Wiederholen.
- MCP-Tool-Count: 161 → **162**.

### Schema

**Keine Schema-Aenderung.** beta.82 ist additiv (ein neues Tool + CLAUDE.md-Regel). Schema bleibt v44.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.82.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.82.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. \`C:\PBP\`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **\`INSTALLIEREN.bat\`**

### macOS

\`INSTALLIEREN.command\` (Rechtsklick → Oeffnen falls macOS warnt)

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
\`\`\`

### Update

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.81] - 2026-06-02 — User-Test-Findings (#659 + #661 + #662 + #663)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Vier Bug- und Prompt-Findings aus dem Live-Test von beta.80 — alle additiv. **+14 neue Tests, 1540 passed.** Keine Schema-Aenderung.

### Fixed

- **#659 (bug)** `profil_bearbeiten` akzeptiert jetzt **beide Schreibweisen** (`ändern`/`aendern`, `löschen`/`loeschen`, `hinzufügen`/`hinzufuegen`) und beide Bereich-Varianten (`persönlich`/`persoenlich`, `präferenzen`/`praeferenzen`). Vorher schlug der dokumentierte Umlaut-Wert mit "Ungueltige Kombination" fehl und trieb Anwender unnoetig in den DB-Bypass.
- **#661 (bug)** `scoring_vorschau` crasht nicht mehr bei Entfernungs-Brackets mit Einheit (z.B. `'50km'`). Neuer Parse-Helper extrahiert defensiv den numerischen Anteil; Brackets ohne Ziffern werden uebersprungen statt einen `ValueError` zu werfen.

### Added

- **#662 (enhancement)** `fit_analyse` liefert jetzt ein scharfes `empfehlung`-Feld mit drei Kategorien: **EMPFOHLEN / BEDINGT / NICHT_EMPFOHLEN** plus `begruendung`, `kurz` und ggf. `ko_gruende`. Drei k.o.-Kriterien (fehlende Stellenbeschreibung, geforderter Hochschulabschluss + nicht im Profil, 0 MUSS-Treffer) ueberschreiben selbst hohen Score. Score-Buckets: ≥75 EMPFOHLEN, 50-74 BEDINGT, <50 NICHT_EMPFOHLEN.
- **#663 Teil 2 (prompt)** CLAUDE.md enthaelt jetzt das harte Verbot, eigene Ablehnungsgruende zu erfinden — mit kompletter Whitelist und Negativ-Beispielen (`abgelaufen`, `windchill_fehlt`, ...). Plus den scharfen Fit-Analyse-Verdict-Zitierstil ohne Weichspueler.

### Changed

- CLAUDE.md: zwei neue Sektionen
  - "STRENG: keine eigenen Ablehnungsgruende erfinden (#663 Teil 2)" mit Whitelist + Verbot
  - "Fit-Analyse-Verdict scharf zitieren (#662)" mit konkreten Vorher-/Nachher-Sprach-Beispielen
- `fit_analyse`-Response um Feld `empfehlung: {kategorie, score, begruendung, kurz, ko_gruende?}` erweitert. Bestehende Felder unveraendert.
- 14 neue Tests in `tests/test_v17_userbugs_beta81.py`.

### Bekannt nicht enthalten (kommt spaeter)

- **#663 Teil 1 (Settings-UI)** — Ablehnungsgruende in Einstellungen editierbar machen. Braucht Backend-Settings + Frontend-Section. User hat im Issue selbst geschrieben: "Kurzfristig reicht die CLAUDE.md-Verschaerfung allein." → zurueckgestellt fuer eine eigene Beta.

### Schema

**Keine Schema-Aenderung.** beta.81 ist reine Bug- und Prompt-Politur. Schema bleibt v44.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.81.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.81.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. \`C:\PBP\`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **\`INSTALLIEREN.bat\`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf \`INSTALLIEREN.command\`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
\`\`\`

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: \`%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db\`
- macOS/Linux: \`~/.bewerbungs-assistent/pbp.db\`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner \`data\backups\\\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## [1.7.0-beta.80] - 2026-06-02 — Dokument-Routing Phase 3 (#643, E11)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Sechster Master-Plan-First-
> Release: Plan-Eintrag E11 → Code → 16 neue Tests → Wiki ✅ → Commit.
> **Cluster E (Dokumenten-Pipeline) ist mit dieser Beta komplett (13/13 ✅).**

### Hintergrund (#643)

Bisher war `/dokumente_verarbeiten` rein auf Profildaten-Extraktion ausgelegt:
"Analysiere die Dokumente und extrahiere Profildaten" — egal ob CV oder Absage-
Mail. Die Konsequenz war, dass Einladungen kein Termin wurden, Absagen keinen
Status setzten, Recruiter-Anfragen keine Antwort triggerten — die Aktion-Schicht
fehlte komplett.

Phase 3 verbindet die Per-Typ-Handler aus E14 (beta.77) mit dem Verarbeitungs-
Flow. Pro `doc_type` wird die passende PBP-Aktion abgeleitet (Profil-
Extraktion, Termin-Anlage, Status-Wechsel, Bewerbung-Erfassen,
Korrespondenz-Abschluss). Plus eine Rauschen-Heuristik im Mail-Import, die
LinkedIn-/XING-Digest-Mails sofort archiviert.

### Added

- **MCP-Tool `dokumente_routing_plan_erstellen(archiv=False)`** — gruppiert
  alle noch-nicht-fertig-verarbeiteten Dokumente nach abgeleiteter Aktion.
  Pro Aktion: Anzahl, Hint fuer den naechsten konkreten Tool-Aufruf, Liste
  der betroffenen Docs. Nutzt `services/document_handlers.handle_doc()`.
- **MCP-Tool `dokument_aktion_ausfuehren(dokument_id, aktion, args)`** —
  Wrapper um bestehende MCP-Tools. Aktionen:
  - `profil_extraktion` → Anleitung (User-Bestaetigung notwendig, kein
    Auto-Apply)
  - `termin_anlegen` → delegiert an `meeting_hinzufuegen`
  - `bewerbung_status_setzen` → delegiert an `bewerbung_status_aendern`
    (Auto-Veralten-Hook aus #657 greift automatisch)
  - `eingangsbestaetigung` → setzt Status auf `eingangsbestaetigung`
  - `bewerbung_erfassen` → delegiert an `bewerbung_erstellen`
  - `noop_korrespondenz_abschliessen` → setzt nur Status auf `angewendet`
  Am Ende jeder Aktion: `extraction_status='angewendet'` fuer das Doku.
- **`dokumente_batch_analysieren(routing_modus=False)`** — neuer Opt-in-
  Parameter. Wenn True: pro Doku ein `routing`-Feld im Response mit
  `aktion`, `claude_action_hint`, `extrahierte_felder`,
  `naechster_aufruf_hinweis`. Default-Verhalten bleibt unveraendert.
- **Rauschen-Heuristik `services/document_handlers.is_pure_notification(sender, subject)`**
  — erkennt LinkedIn-/XING-Digest-Avisos, Mail-Robot-Pushes. Konservativ:
  nur klare Treffer (Absender-Domain ODER eindeutiges Betreff-Muster mit
  Umlaut-Normalisierung).
- **Mail-Import-Hook** im Ordner-Import-Pfad (`dashboard.py`) und im
  Mail-Upload-Pfad: wenn `is_pure_notification` greift, wird das Doku
  direkt auf `lifecycle='archiviert'` gesetzt — taucht damit gar nicht
  erst im Analyse-Plan auf. Reversibel ueber `dokument_reaktivieren`.
- **16 neue Tests** in `tests/test_v17_routing_643.py`: Routing-Plan-
  Gruppierung, Batch-Routing-Modus, alle 5 Aktions-Typen,
  Rauschen-Heuristik (LinkedIn, XING, echte Mails, Umlaute, leere Werte).

### Changed

- MCP-Tool-Count: 159 → **161**.
- Plan-Dokumente.md: E11 ✅, **Cluster E komplett 13/13 ✅**.
- Master-Plan.md: E11 (#643) auf ✅.
- `_build_email_document_context` (dashboard.py) liefert jetzt zusaetzlich
  `is_pure_notification` zurueck.

### Schema

**Keine Schema-Aenderung.** Phase 3 ist reine Logik. Schema bleibt v44.

### DSGVO-Hinweis

Die Rauschen-Heuristik prueft Absender-Adressen und Betreff-Zeilen *nur
lokal in Python*. Es werden keine Daten an externe Services geschickt.
Pattern-Liste ist statisch im Code dokumentiert.

### Bekannt nicht enthalten

- **Frontend-UI fuer Routing-Plan / Aktion-Ausfuehrer** — wird nachgezogen.
  MCP-Tools reichen fuer den Claude-Workflow.
- **LLM-basierte Klassifikation fuer Routing-Entscheidung** — bewusst nicht
  Phase 3. Regex/Keyword-basierter Pfad ist deterministisch und latenz-
  arm. Tiefenanalyse via `_run_auto_deep_analysis` (E12, beta.76) bleibt
  parallel verfuegbar.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.80.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.80.zip)
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

## [1.7.0-beta.79] - 2026-06-02 — Dokument-Lifecycle Phase 2 (#657, E16)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Fuenfter Master-Plan-First-
> Release: Plan-Eintrag E16 → Code → 18 neue Tests → Wiki ✅ → Commit.
> **Schema-Aenderung — automatisches Backup vor Migration.**

### Hintergrund (#657)

Bisher waren `extraction_status` und Verfuegbarkeit eines Dokuments dasselbe.
Wer Rauschen (LinkedIn-/XING-Digest-Mails) ausblenden oder zu abgelehnten
Bewerbungen gehoerende Anhaenge wegfiltern wollte, musste sie loeschen — was
DB-Eintrag UND Datei verbrennt. Phase 2 fuehrt die orthogonale Dimension
`lifecycle` ein:

  - `aktiv`      = Default, taucht in Standard-Analyse-Ansichten auf
  - `archiviert` = manuell ausgeblendet (DB-Flag, Datei unberuehrt)
  - `veraltet`   = auto-gesetzt beim Bewerbungs-Statuswechsel auf
                   abgelehnt/abgelaufen/zurueckgezogen

### Schema v43 → v44

- Neue Spalte `documents.lifecycle TEXT NOT NULL DEFAULT 'aktiv'`
- Neuer Index `idx_documents_lifecycle (lifecycle, profile_id)`
- Migration ist additiv und idempotent — bestehende Docs erhalten den
  Default `aktiv`, kein bestehender Workflow wird beeintraechtigt.
- **Backup wird vor Migration automatisch erstellt** (Standard-Pfad
  `data/backups/`).

### Added

- **MCP-Tool `dokument_archivieren(dokument_id, grund='')`** — markiert ein
  Doku als `lifecycle=archiviert`. DB-only, Datei bleibt unberuehrt,
  reversibel.
- **MCP-Tool `dokument_reaktivieren(dokument_id)`** — setzt `archiviert`
  oder `veraltet` zurueck auf `aktiv`.
- **MCP-Tool `dokumente_bulk_archivieren(filter_doc_type, filter_extraction_status,
  dry_run=True, max_treffer=200)`** — Massenrueckruf mit dry-run + Hard-Cap.
  Filter-Kombination ueber doc_type und/oder extraction_status. Hard-Cap
  meldet, wenn Treffer abgeschnitten wurden.
- **Auto-Veralten-Hook in `bewerbung_status_aendern`** — wenn der neue
  Status in `{abgelehnt, abgelaufen, zurueckgezogen}` liegt, werden alle
  mit dieser Bewerbung verknuepften Docs auf `lifecycle=veraltet` gesetzt.
  Hinweis steht im Tool-Result unter `dokumente_veraltet`. Reversibel ueber
  `dokument_reaktivieren`.
- **18 neue Tests** in `tests/test_v17_lifecycle_657.py`: Migration,
  archivieren/reaktivieren, Default-Filter in drei Read-Tools, Auto-Veralten
  fuer drei End-Stati, Schutz vor versehentlicher Beruehrung anderer
  Bewerbungen.

### Changed

- `analyse_plan_erstellen(archiv=False)` — Default zeigt nur `aktiv`.
  `archiv=True` bezieht archivierte/veraltete Docs ein. Bestehende
  Aufrufer ohne Argument sehen das gewohnte Verhalten direkt nach
  Migration (alle Docs sind `aktiv`).
- `dokumente_batch_analysieren(archiv=False)` — gleiche Semantik.
- `dokumente_zur_analyse(archiv=False)` — analog zu
  `bewerbungen_anzeigen(archiv=...)`. Neues Feld `lifecycle` im
  zurueckgegebenen Doku-Eintrag.
- `documents.lifecycle` wird zusaetzlich im Response von
  `analyse_plan_erstellen` und `dokumente_batch_analysieren` mitgesendet.
- MCP-Tool-Count: 156 → **159** (drei neue Tools).
- Plan-Dokumente.md: E16 ✅, neuer Phase-2-Abschnitt, naechste Iteration
  zeigt E11 (#643, doc_type-Routing) als naechsten Schritt.
- Master-Plan.md: E16 (#657) auf ✅.

### Migration

Schema v43 → v44 ist ALTER-only, idempotent und reversibel. Vor der
Migration wird automatisch ein Backup unter
`%LOCALAPPDATA%\BewerbungsAssistent\data\backups\` angelegt.

**Rollback (falls noetig):**
1. PBP beenden.
2. Backup-Datei aus `data\backups\` zurueck nach `data\pbp.db` kopieren.
3. Alte PBP-Version installieren.

### DB-Helfer (intern, nicht MCP)

- `Database.update_document_lifecycle(doc_id, lifecycle, profile_id=None)` —
  validiert gegen `("aktiv", "archiviert", "veraltet")`, profile-scoped.
- `Database.get_documents_linked_to_application(application_id)` — Cast-sicher
  fuer Auto-Veralten-Hook, beruecksichtigt INTEGER/TEXT-Mismatch zwischen
  `documents.linked_application_id` und `applications.id`.

### Bekannt nicht enthalten (kommt in Phase 3)

- **Doc-Type-Routing mit typspezifischen Aktionen** (#643, E11) → Phase 3.
- **Rauschen-Heuristik beim Import** (#657 MVP-Phase 3, optional) — kommt
  zusammen mit dem Routing-Refactor.
- **Frontend-UI fuer Archiv-Toggle** — wird nachgezogen, sobald sich der
  Filter-Pfad stabilisiert hat. MCP-Tools reichen fuer den Claude-Workflow.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.79.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.79.zip)
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

## [1.7.0-beta.78] - 2026-06-02 — Dokument-Lifecycle Phase 1 (#658, E15)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Vierter Master-Plan-First-
> Release: Plan-Eintrag E15 → Issue #658 → Code → 8 neue Tests → Wiki ✅ → Commit.

### Hintergrund (#658)

Korrespondenz-Dokumente (Absagen, Einladungen, Recruiter-Anfragen, LinkedIn-/
XING-Benachrichtigungen) blieben dauerhaft auf `extraction_status='basis_analysiert'`
haengen und tauchten beim naechsten `analyse_plan_erstellen()`-Lauf erneut auf.
Ursache: Der Status-Uebergang `basis_analysiert` → `angewendet` haengt allein
am Profildaten-Pfad (`extraktion_anwenden()`). Korrespondenz liefert aber keine
Profildaten und durchlaeuft `extraktion_anwenden()` nie — daher der Stuck.

Phase 1 entkoppelt das Lifecycle-Ende von der Profildaten-Bedingung. Phase 2
(#657, lifecycle-Spalte) und Phase 3 (#643, doc_type-Routing) folgen.

### Fixed

- **#658 (E15): `_run_auto_deep_analysis` setzt jetzt `angewendet` statt `analysiert`.**
  Der Halbschritt `analysiert` war redundant — wenn das LLM ein Doku gesehen
  hat, ist der Auto-Pfad fuer Korrespondenz fertig. (`dashboard.py:7836,7844`)
- **`dokument_status_setzen()`-Whitelist erweitert.** Vorher waren nur
  `{nicht_extrahiert, gestartet, extrahiert, angewendet}` erlaubt — der Auto-
  Pfad vergibt aber auch `basis_analysiert`, `analysiert`, `analysiert_leer`,
  `duplikat`, `verworfen`. Manuelles Zuruecksetzen ist damit jetzt durchgaengig
  moeglich. (`tools/dokumente.py:_DOC_STATUS_VALUES`)

### Added

- **MCP-Tool `dokumente_korrespondenz_abschliessen(dry_run=True)`.** Raeumt
  Altlasten ab: findet alle Korrespondenz-Typen
  (`sonstiges`/`recruiter_anfrage`/`absage`/`einladung`/`eingangsbestaetigung`/
  `interview_*`/`gespraechs_feedback`/`projekt_update`/`vermittler_korrespondenz`)
  im `basis_analysiert`/`analysiert`/`analysiert_leer`-Bucket und hebt sie
  auf `angewendet`. Parameter `zusaetzliche_doc_types` erlaubt projekt-
  spezifische Typen. **DB-only — physische Dateien bleiben unberuehrt.**
  Profil-Docs (Lebenslauf/Anschreiben/Projektliste/Zeugnis) werden NIE
  durch dieses Tool angefasst — die brauchen `extraktion_anwenden()`.
- 8 neue Tests in `tests/test_v17_doc_lifecycle_658.py` decken: dry-run-
  Vorschau, Schutz von Profil-Docs, Erweiterungsparameter, Auto-Deep-
  Status-Fix, Whitelist-Erweiterung.

### Changed

- MCP-Tool-Count: 155 → **156** (neuer Repair-Tool).
- Plan-Dokumente.md: E15 ✅, neuer Phase-1-Abschnitt, naechste Iteration
  zeigt jetzt E16 (#657, lifecycle-Spalte) als naechsten Schritt.
- Master-Plan.md: E15 (#658) + E16 (#657) als neue Eintraege im Cluster E.
- `_run_auto_deep_analysis` pflegt jetzt `last_extraction_at` mit (vorher
  nur Status).

### Migration

Keine Schema-Aenderung. Keine DB-Migration. Phase 1 ist additiv und
reversibel — `dokumente_korrespondenz_abschliessen` schreibt nur in
`extraction_status` + `last_extraction_at`, die bestehenden Werte koennen
manuell zurueckgesetzt werden.

### Bekannt nicht enthalten (kommt in Phase 2/3)

- **Lifecycle-Spalte `aktiv`/`archiviert`/`veraltet`** (#657, E16) → Phase 2.
- **Doc-Type-Routing mit typspezifischen Aktionen** (#643, E11) → Phase 3.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.78.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.78.zip)
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

## [1.7.0-beta.77] - 2026-06-01 — Scraper-Reanimation + Adzuna + Doku-Typen (#653 + #654 + #655)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. **Dritter Master-Plan-First-
> Release.** Scraper-URL-Updates, neuer Adzuna-Adapter, Doku-Klassifikator
> erweitert + Per-Typ-Handler-System. **22 neue Tests, 1484 passed.**

### 🔧 #653 (B12) Scraper-Reanimation + Deprecation

Live-Probes der 7 als defekt markierten Quellen aus `scraper_diagnose`:

- **`ferchau`** ✅ — URL-Migration zu `touch.ferchau.com`. Scraper-Code und
  SOURCE_REGISTRY aktualisiert. Vorher `/de/de/jobs` 404 seit 2026-04-25.
- **`ingenieur_de`** ✅ — URL-Migration zur eigenen Subdomain
  `jobs.ingenieur.de`. Scraper-Code und SOURCE_REGISTRY aktualisiert.
- **`monster`** ❌ → **deprecated**. Monster Europe Domain transitioning
  seit 08/2025, keine deutschen Job-Listings mehr — nur noch CV-Service.
  Manueller Fallback: Indeed.
- **`solcom`** ❌ → **deprecated** (`chrome_extension_only`). Cloudflare
  Bot-Block dauerhaft aktiv (HTTP 403), nur noch via Chrome-Extension.
- **`gulp`**, **`kimeta`**, **`heise_jobs`** — bleiben als ⬜ in #656
  (Playwright-Integration als eigenes Issue).

### 🆕 #654 (B17) Neuer Adapter: Adzuna API

Adzuna bietet eine kostenlose REST-API mit deutschen Job-Listings — gute
Ergaenzung zu Bundesagentur und Ersatz fuer die deprecated/blockierten
Quellen.

- Neuer Adapter `job_scraper/adzuna.py` (~170 LOC)
- Voraussetzung: `adzuna_app_id` + `adzuna_app_key` in Settings (kostenlose
  Registrierung auf `developer.adzuna.com`)
- Ohne Keys: schneller Skip mit klarer Meldung
- REST + JSON, keine SPA-Probleme, keine Bot-Walls
- Bonus: liefert Gehalts-Predictions als `salary_estimated=1`

### 📁 #655 (E14) Doku-Typen erweitern + Per-Typ-Handler-System

**Teil A — Klassifikator erweitert** (`_detect_doc_type` in `dashboard.py`):

Drei neue `doc_type`-Werte aus dem Reality-Check:
- `interview_bestaetigung` (anders als `interview_einladung` — schon zugesagt)
- `projekt_update` (Zwischenfeedback / Status-Update vom Recruiter)
- `gespraechs_feedback` (Persoenliche Rueckmeldung nach Gespraech)
- `vermittler_korrespondenz` (in KNOWN_TYPES gelistet, manuell setzbar)

Filename- + Content-Patterns mit konkreten Beispielen aus den 200
echten Markus-Dokumenten.

**Teil B — Per-Typ-Handler-System** (`services/document_handlers.py`):

Jeder bekannte Typ hat:
- `extract_fields(doc)` — typspezifische Felder via Regex (Recruiter-
  Email, Termin-Datum/Uhrzeit/Platform, Feedback-Tendenz positiv/negativ)
- `claude_action` — konkrete naechste Aktion ("Status auf 'interview' aendern
  + Termin im Kalender anlegen" statt generisch "Doku ansehen")

22 Typ-Definitionen in `KNOWN_TYPES`. Pro Typ: Beschreibung + Aktion +
hat_extraktor-Flag.

**Teil C — Neuer MCP-Tool `dokument_typen_anzeigen`**:

Listet alle bekannten Typen + Beschreibung + Action-Vorschlag + Anzahl
in der DB. Hilft Discovery und zeigt **unbekannte_typen_in_db** wenn
Werte in der DB stehen die nicht in `KNOWN_TYPES` dokumentiert sind —
Signal fuer "Handler-Eintrag fehlt noch".

### Tests

22 neue in `tests/test_v17_optimierungen_beta77.py`:
- 6 fuer B12 (SOURCE_REGISTRY-Updates, Scraper-Code-Aktualisierung)
- 5 fuer B17 (Adzuna-Adapter Skip-Verhalten, Mapping, Credentials)
- 11 fuer E14 (3 neue Filename-Patterns, Content-Detection, Per-Typ-
  Handler, MCP-Tool)

MCP-Tool-Count: **154 → 155** (+ `dokument_typen_anzeigen`).
Quellen-Count: **34 → 35** (+ `adzuna`).
Volle Suite: **1484 passed, 1 skipped** (vorher 1462).

### Master-Plan-First

Dritter Release. Alle Items als ⬜ + Issue im Plan bevor Code begann
(B12 #653, B17 #654, E14 #655). Plus zwei neue Roadmap-Items:
- B18 #656 — Playwright-Adapter fuer SPA-Quellen (gulp/kimeta/heise_jobs)
- B13 — Probe-URL-Inventar pflegen (unveraendert offen)

---

## [1.7.0-beta.76] - 2026-06-01 — Auto-Steps + Nachfass + Onboarding-Hints (#650 + #651 + #652)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Zweiter Master-Plan-First-
> Release. **Drei neue Auto-Engine-Steps + 2 neue MCP-Tools + 1 neuer Service.**
> 10 neue Tests, **1462 passed**.

### 🤖 #651 (E12) Auto-Tiefenanalyse-Step

Neuer `_run_auto_deep_analysis(now_iso, max_docs=3)` in `dashboard.py`:

- Holt bis zu 3 Dokumente pro Lauf aus `extraction_status='basis_analysiert'`
- Pro Doc: Ollama-`CLASSIFY_DOCUMENT`-Call -> ggf. neuer `doc_type`
- Setzt `extraction_status='analysiert'` nach erfolgreicher Verarbeitung
- **Backoff** bei 3+ Fehlern pro Doc (Setting `deep_analysis_fail:{doc_id}`)
- Bei `Lokale AI nicht aktiv`: schneller Skip mit klarer Meldung
- Elwosa-Linie `auto_deep_analysis` (4 Varianten)
- Hook in `_run_auto_actions`

Reality-Check zeigte 16 Docs in `basis_analysiert` ohne weitere Verarbeitung —
dieser Step wird sie nach und nach auflösen.

### 📨 #650 (D15) Nachfass-Trigger bei Status ohne Update >7d

Neuer `_run_check_stale_applications(now_iso)`:

- Iteriert ueber Bewerbungen in aktiven Statuses
  (`offen`/`in_vorbereitung`/`beworben`/`eingangsbestaetigung`/`interview`/`zweitgespraech`)
- Prueft letztes `application_events.event_date`
- **>=7 Tage**: setzt `stale_app_lastnotified:{app_id}` -> Frontend kann das aufgreifen
- **>=14 Tage**: zusaetzlich Elwosa-Linie `auto_followup_overdue` (4 Varianten)
- **Re-Notify-Window 5 Tage** — kein Spam, kein Daily-Reminder
- Idempotent: wenn neueres Event als letzte Notification -> Counter-Reset

Plus: in `bewerbung_details:nächste_aktionen` taucht bei >=14d ein
prioritärer Nachfass-Eintrag auf, der die generischen Workflow-Vorschläge
verdrängt (mit Anzahl Tage seit letztem Event).

### 🛟 #652 (G11) Onboarding-Hints Backend

Neuer Service `services/onboarding_hints.py` + 2 MCP-Tools:

- **`onboarding_hints_anzeigen()`** — liefert aktive Hints (Condition erfüllt
  + nicht dismissed). 3 Hint-Definitionen aus dem Reality-Check:
  - `g11_suchprofile_anlegen` (0 Suchprofile + >=3 Bewerbungen)
  - `g11_aufwand_tracken` (>=5 Meetings + 0 Reisekosten/Vorbereitungszeit)
  - `g11_interview_reflexion` (>=2 Interview-Bewerbungen + 0 Reflexionen)
- **`onboarding_hint_dismiss(hint_id)`** — persistiert die Wegklick-Entscheidung
  in `profile_settings.onboarding_hints_dismissed` (JSON-Liste)

Backend-only — Frontend-Cards kommen als separate Beta. Claude kann die Hints
aber jetzt schon im Chat anzeigen wenn der User danach fragt.

### Tests

10 neue in `tests/test_v17_optimierungen_beta76.py`:
- 3 fuer `_run_auto_deep_analysis` (Skip ohne Ollama, normaler Lauf, Backoff)
- 2 fuer `_run_check_stale_applications` (7d/14d finden, Idempotenz)
- 5 fuer Onboarding-Hints (leeres Profil, Trigger, Dismiss-Persistierung,
  unbekannte ID, MCP-Tool)

MCP-Tool-Count: **152 → 154** (+2).
Volle Suite: **1462 passed, 1 skipped** (vorher 1452).

### Master-Plan-First

Zweiter Release nach Einfuehrung der Disziplin. Alle drei Items waren als
⬜ + Issue (#650, #651, #652) im Master-Plan bevor der Code begann. Jetzt
auf ✅ + Sub-Plaene Plan-Bewerbungen, Plan-Dokumente, Plan-Frontend
aktualisiert.

---

## [1.7.0-beta.75] - 2026-06-01 — Reality-Check-Optimierungen (#647 + #648 + #649)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Drei kleine Optimierungen
> aus dem Reality-Check-Bericht 2026-06-01. **11 neue Tests, 1452 passed**.
> Erster Release nach Einfuehrung der Master-Plan-First-Disziplin.

### 🛠 #647 (H12) `pbp_capabilities` Tool-Count-Sync

Vorher hardcoded "PBP-MCP bietet 95 Tools" — real sind es **152**. Der
Reality-Check hat diese Diskrepanz aufgedeckt. Jetzt liefert
`pbp_capabilities()` zwei getrennte Counts:

- `tools_gesamt` — echte Anzahl aus dem MCP-Registry (ermittelt via
  `_tool_manager._tools` mit Fallback auf `list_tools_sync`)
- `tools_kuratiert` — Anzahl der Tools in den 10 User-Facing-Kategorien
- `tools_hinweis` — erklaert die Differenz wenn sie existiert

Plus: der `ueberblick`-Text spiegelt jetzt die echten Counts statt der
veralteten 95.

### 🛠 #648 (C17) Outcome-Signal in `fit_analyse`

Wenn drei oder mehr aehnliche Stellen aus dem **gleichen Grund**
aussortiert wurden, weist `fit_analyse` jetzt darauf hin:

```json
{
  ...
  "risks": [
    ...,
    "Aufmerksamkeit: 5 aehnliche Stellen wurden wegen 'falsches_fachgebiet' aussortiert. Pruefe ob das hier auch zutrifft."
  ],
  "outcome_pattern": {
    "risk_text": "...",
    "top_grund": "falsches_fachgebiet",
    "anzahl": 5,
    "beispiele": [{"hash": "...", "title": "...", "company": "..."}, ...]
  }
}
```

Neue Pure-Helper-Funktion `_aehnliche_outcome_pattern(db, target_job)` —
nutzt Token-Jaccard (>= 0.10) gegen `db.get_dismissed_jobs()`, zaehlt
`dismiss_reasons` und triggert ab dem Schwellwert. Read-only, keine
State-Aenderung. Bei Fehler: stille Exception-Aufnahme, fit_analyse
gibt trotzdem normales Ergebnis.

### 🛠 #649 (E13) Recall-Fix Recruiter-Anfrage-Klassifikator

Reality-Check zeigte: 16 von ~20 Recruiter-Mails wurden als `sonstiges`
klassifiziert statt als `recruiter_anfrage`. Ursache: `_detect_doc_type`
in `dashboard.py` hatte zu enge Filename- und Content-Keyword-Listen.

Erweitert um:

- **Filename-Patterns:** `"hat ihnen eine nachricht gesendet"`,
  `"neue recruiting-nachricht"`, `"wir suchen einen"`, `"sie sind der
  richtige kandidat"`, `"neuer job fuer dich"`, `"live "`, `"interested?"`,
  `"follow-up on my last email"`, `"consulting opportunity"`, ...
- **Content-Keywords:** LinkedIn/XING-Outreach (`"ich habe ihr profil"`,
  `"i came across your profile"`, `"talent acquisition"`,
  `"looking forward to hearing from you"`, ...), Projekt-/Headhunter-
  Outreach (`"wir haben aktuell eine"`, `"projektanfrage"`,
  `"freelance opportunity"`, ...)

### Tests

11 neue in `tests/test_v17_optimierungen_beta75.py`:

- 2 fuer `pbp_capabilities` (getrennte Counts, ueberblick-Text passt)
- 3 fuer `_aehnliche_outcome_pattern` (Trigger ab 3, kein Trigger bei 2,
  kein Trigger bei verschiedenen Gruenden)
- 5 fuer `_detect_doc_type` (LinkedIn-Outreach, englische Outreach,
  deutsche Outreach, Content-Phrasen, Regression-Schutz mit 6 echten
  Subjects aus dem Reality-Check)
- 1 Precision-Test (Eingangsbestaetigung bleibt eigenstaendig)

Volle Suite: **1452 passed, 1 skipped** (vorher 1441).

### Master-Plan-First

Erster Release nach Einfuehrung der Master-Plan-First-Disziplin in
CLAUDE.md. Workflow-Bewaehrung: alle 3 Items wurden ERST im Master-Plan
als ⬜ + Issue-Refs eingetragen (C17, E13, H12), DANN umgesetzt, jetzt
auf ✅ gesetzt + Wiki ergaenzt. Hat funktioniert.

---

## [1.7.0-beta.74] - 2026-06-01 — Bulk-Tools-Timeout-Schutz (#646)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Reiner Bugfix-
> Release fuer #646. 4 neue Tests, 1441 passed insgesamt.

### 🐛 #646 `stellen_auto_aussortieren` + `stellen_bulk_bewerten` Timeout-Schutz

Reproduzierbarer Fehler vor beta.74: beide Bulk-Tools liefen in den
4-Minuten-MCP-Client-Timeout, machten den Massen-Aussortier-Use-Case
(genau wofuer #514 sie gebaut hatte) unbenutzbar.

**Ursache `stellen_auto_aussortieren`:** N sequentielle Ollama-Calls,
default `max_stellen=50`. Lokales LLM braucht 5-30s pro Call →
50 × 10s = 8 Min Wall-Clock → Timeout.

**Ursache `stellen_bulk_bewerten`:** Verdacht SQLite-Lock-Konflikt mit
dem parallelen Auto-Engine-Step `_run_auto_refetch_descriptions` der
pro Stelle 15s httpx-Timeout hat und in dieser Zeit die DB-Connection
haelt.

### Fix in beta.74

- **`stellen_auto_aussortieren`**:
  - Default `max_stellen` von **50 → 10**, mit Hard-Cap auf 30.
  - Neuer Parameter `max_dauer_sek=180` (Wall-Clock-Budget), gedeckelt
    auf 240s (unter dem MCP-Client-Timeout).
  - Wall-Clock-Check vor jedem Ollama-Call. Bei Erreichen: Abbruch mit
    `status='teilweise'`, `kandidaten_gesamt`, `unverarbeitet` und
    Hinweis "erneut aufrufen um die Reste zu bearbeiten (idempotent)".
- **`stellen_bulk_bewerten`**:
  - Neues internes 90s-Wall-Clock-Budget.
  - Check nach DB-Load (Lock-Verdacht-Frueherkennung) und pro Stelle
    in der Bulk-Apply-Schleife.
  - Bei Timeout: `status='timeout'`, klare Fehler-Meldung mit Tipp
    (engere Filter / kurz warten bis Auto-Engine-Step durch ist),
    `verarbeitet`-Counter mit `stichprobe_bearbeitet` fuer Audit.

### Tests

`tests/test_v17_bulk_timeout_646.py` (4 Tests):
- Defensive Caps werden eingehalten (max_stellen >30 → 30, max_dauer
  >240 → 240).
- `status='teilweise'` mit Teil-Ergebnis bei Budget-Erschoepfung.
- Normaler Dry-Run mit wenigen Treffern ist schnell (< 90s Budget).
- Fehler-Pfade (ungueltige Bewertung) sofort zurueck, kein Budget-Verbrauch.

Volle Suite: **1441 passed, 1 skipped** (vorher 1437).

---

## [1.7.0-beta.73] - 2026-05-31 — URL-Aging-Auto-Cleanup + Ollama-Validator (#645)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.
> Funktionsreich. **27 neue Tests** (18 url_health + 9 qualitaet_pruefen),
> Suite 1437/1437 gruen. Keine Schema-Aenderung.

### 🩺 Neuer Service `services/url_health.py`

Wiederverwendbarer Pure-Python-Health-Checker fuer Job-URLs:

- HTTP-Status + Bot-Block-Marker
- 17 lokalisierte "Stelle vergeben/expired"-Marker (DE + EN, Greenhouse,
  Workday, Arbeitsagentur, generisch)
- **Workday-SPA-Sonderfall**: HTML-Body ist nur ein Skeleton, Stellen-
  Existenz nur ueber `wday/cxs/{tenant}/{site}/job/{path}`-API testbar.
  Workday-API-404 wird als `EXPIRED` klassifiziert. So fallen Workday-
  Stellen wie `b9f0bbe25d09` (<FIRMA>, Workday-Portal) ab denen die HTML
  weiterhin 200 OK liefert obwohl die Stelle weg ist.
- **Title-Token-Cross-Check** fuer statisches HTML: wenn keine
  signaltragenden Title-Tokens im Body stehen, hat der Server eine
  Generic-Replacement-Seite geliefert -> `EXPIRED`.
- 7 Status-Werte: `OK`, `EXPIRED`, `HTTP_404`, `HTTP_ERROR`, `TIMEOUT`,
  `BLOCKED` (Cloudflare/Captcha), `LEER`.
- `should_dismiss`-Property: True nur fuer `EXPIRED` + `HTTP_404`. 5xx,
  Timeout, Blocked sind transient — kein Auto-Aussortieren.

### 🛠 Neues MCP-Tool `stellen_qualitaet_pruefen`

```
stellen_qualitaet_pruefen(
    max_stellen=50,
    nur_problematische=True,
    auto_aussortieren=False,
    mit_ollama_validierung=False,
)
```

Geht pro aktiver Stelle durch und kategorisiert:
- `url_404`, `url_expired` -> Aussortier-Kandidat (`auto_aussortieren=True`
  -> dismiss als `'veraltet_url'`)
- `url_blocked`, `url_timeout` -> NICHT aussortieren (transient)
- `beschreibung_fehlt` -> Hinweis fuer Claude
- `search_url` -> Markierung dass nur Such-URL gespeichert (#645-Fallback)
- `ok` -> alles fein

Default ist Vorschau-Modus (`auto_aussortieren=False`), liefert Hinweis
mit `auto_aussortieren=True`-Empfehlung wenn dismiss-Kandidaten gefunden.

### 🤖 Ollama-Validator fuer Stellenbeschreibungs-Vollstaendigkeit

Neuer `TaskKind.VALIDATE_JOB_QUALITY` im LLM-Service. Routing:
LOCAL > CLAUDE > MANUAL — bei aktiver Lokaler AI laeuft Ollama mit
strukturiertem JSON-Output:

```
{
  "vollstaendig": true|false,
  "score": 0-10,
  "vorhanden": ["aufgaben", "anforderungen", "gehalt", ...],
  "fehlt": ["..."],
  "begruendung": "1-2 Saetze",
  "claude_action": "nachladen" | "manuell_ergaenzen" | "keine"
}
```

`claude_action` macht Claude direkt actionable: bei `"nachladen"` wird
`stellenbeschreibung_nachladen` empfohlen, bei `"manuell_ergaenzen"`
soll Claude beim User nachfragen oder via WebSearch ergaenzen.

Robust gegen Markdown-Codefence und Vor-/Nachspann (kommt vor bei
einigen Ollama-Modellen). Wird ueber `mit_ollama_validierung=True` in
`stellen_qualitaet_pruefen` integriert.

### 🔁 Auto-Engine-Step `_run_url_aging_check`

Laeuft pro Engine-Tick (alle paar Minuten), prueft bis zu **10 aktive
Stellen** pro Lauf auf URL-Health, sortiert 404 + expired auto-aus mit
`dismiss_reason='veraltet_url'`. **24h-Backoff** pro Stelle nach
erfolgreichem Check (Setting `url_aging_lastok:{hash}`) — keine
Server-Bombardierung.

Such-URL-Stellen werden uebersprungen (`is_search_url=1`). Elwosa
bekommt eine neue Trigger-Linie `auto_url_aging` mit 4 lakonischen
Varianten zur Meldung.

### Tests

- `tests/test_v17_url_health_645.py` — 18 Tests (Workday-API-Routing,
  Marker-Erkennung, Title-Token-Match, Mock-httpx-Client)
- `tests/test_v17_qualitaet_pruefen_645.py` — 9 Tests (Parser-Robustheit
  inkl. Codefence + Prefix, MCP-Tool-Klassifikation, Auto-Aussortieren)

Volle Suite: **1437 passed, 1 skipped** (vorher 1410).

---

## [1.7.0-beta.72] - 2026-05-31 — Hard-Guard fuer leere URLs aus Scraper-Quellen (#645)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10. Direktes Follow-up zu beta.71.
> 2 neue Tests, 1410/1410 gruen.

### 🛡 #645 `save_jobs` blockt leere URLs aus Scraper-Quellen

Defense-in-Depth zusaetzlich zum Scraper-Fix in beta.71: Wenn irgendein
Scraper (alles ausser `manuell`, `email`, `recruiter_inbound`) eine Stelle
mit leerer `url` durchschiebt, fuegt `save_jobs` jetzt aktiv ein
`is_search_url=True` ein UND loggt eine WARN-Zeile mit Quelle, Titel
und Firma — sichtbar in `pbp_diagnose` / scraper_health.

Garantie nach #645: `jobs.url` ist ab jetzt entweder eine Detail-URL
oder (mit Markierung) eine Such-URL — niemals wieder ein leeres Feld
ohne Indikator. Selbst wenn ein zukuenftiger Scraper-Refactor wieder
den Fallback "vergisst", wird die Stelle korrekt als Such-URL behandelt
und der User sieht in den Logs sofort, dass ein Scraper-Bug entstanden ist.

`save_jobs` liefert jetzt zusaetzlich `leere_url_warnungen: {source: count}`
im Result-Dict zurueck, falls Stellen ohne URL ankamen. job_runner und
scraper_health koennen das weiterreichen.

---

## [1.7.0-beta.71] - 2026-05-31 — Regression-Fix: leere jobs.url bei XING/Stepstone (#645)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.
> Reiner Bugfix-Release. Keine Schema-Aenderung. 9 neue Tests
> (`test_v17_url_regression_645.py`), 1410/1410 gruen.

### 🐛 #645 Stellen-URLs werden wieder gespeichert (Detail- oder Such-Fallback)

Bei der Durchsicht am 29.05.2026 fielen 7 von 8 aktiven Stellen mit
**leerem url-Feld** auf — XING/Stepstone/E-Mail-Quellen. Folge:
`stellenbeschreibung_nachladen` (#622) bricht mit "Stelle hat keine URL"
ab, der User kann die Anzeige nicht oeffnen, der Score basiert nur auf
dem Titel und wird unzuverlaessig. Regression hinter #436 (v1.5.3, dort
nur Detection + Warnung — der eigentliche Fallback pro Portal war nie
ueberall implementiert, nur in `monster.py` / `freelancermap.py`).

**Scraper — URL-Fallback-Kaskade jetzt einheitlich:**

- **`xing.py` `_process_raw_job`** — Reihenfolge: (1) Detail-Link aus
  der Karte; (2) wenn leer aber `jobId` vorhanden, Detail-URL aus jobId
  rekonstruieren (`https://www.xing.com/jobs/{jobId}`); (3) sonst
  aktuelle Such-URL eintragen + `is_search_url=True`. Relative Links
  werden mit Host vorgeklebt.
- **`stepstone.py`** — pro Stelle: relative Links absolutieren
  (JSON-LD-Posts liefern manchmal ohne Host), und wenn am Ende immer
  noch kein Detail-Link da ist, Such-URL als Fallback +
  `is_search_url=True`. `_fetch_detail_descriptions` ueberspringt
  Such-URL-Stellen (sonst landet der Anriss der Suchergebnis-Seite als
  "Beschreibung" und verfaelscht das Scoring).

**DB-Schicht — URL nachpflegbar:**

- `Database.update_job` hat `url` und `is_search_url` jetzt in der
  Allowed-List (vorher Whitelist-Drop ohne Warnung).
- `stelle_bearbeiten(<hash>, url="...")` akzeptiert URL als Parameter
  und setzt `is_search_url` automatisch via `is_search_result_url()`.
  Bei nachgereichter Such-URL gibt's `url_warnung` wie bei
  `stelle_manuell_anlegen`.

**Tool-Schicht — bessere Fehler-Meldung:**

- `stellenbeschreibung_nachladen` zeigt jetzt einen konkreten
  copy-paste-fertigen Vorschlag: `stelle_bearbeiten('<hash>', url='https://...')`.
  Vorher wurde auf `stelle_bearbeiten` verwiesen, das den `url`-Parameter
  gar nicht akzeptierte — der Workaround lief ins Leere.
- Separater Fehler-Branch wenn die gespeicherte URL eine Such-URL ist
  (kein sinnloser HTTP-Fetch der Suchseite mehr).
- `_run_auto_refetch_descriptions` (Auto-Engine-Step aus #622)
  ueberspringt Such-URL-Stellen via `COALESCE(is_search_url, 0) = 0`.

**Noch offen (eigene Issues empfohlen):**

- AK3 "E-Mail-Quelle ohne Link: definierter Umgang" — Schema-Erweiterung
  mit eigener Migration, separat zu trennen
- AK5 "Datenheilung fuer bestehende leere Stellen" — eine optionale
  Migration `quellen_aus_urls_korrigieren`-aehnlich
- medac/Workday-Deep-Link-Pattern aus Kommentar #4582087088 — eigene
  Untersuchung im Workday-Adapter

---

## [1.7.0-beta.70] - 2026-05-29 — Doku-Fixes: Phantom-Bewerbungen + Mail-Doku-Verknuepfung (#642 + #644)

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.
> 🔧 **Ersetzt die defekten Zwischen-Releases beta.68 + beta.69** — diese
> gingen mit unvollstaendigem Code / roten Tests raus (Edit-Fehler meinerseits).
> **beta.70 ist die erste saubere Version dieser Fixes, 1401/1401 gruen.**
> beta.68 + beta.69 NICHT installieren.

### 🐛 #642 Keine Phantom-Bewerbungen mehr aus CV-Dateinamen

`bewerbungs_dokumente_erkennen(auto_erstellen=True)` legte aus generischen
CV-Varianten Phantom-Bewerbungen an (Bewerbung bei „Ausfuehrlich",
„freelancer", „SC", „SL"; „Dassault-Systems" zu „Systems" verstuemmelt).
`_extract_firma_from_filename` neu aufgebaut:

- **Trenner-Logik:** enthaelt der Rest nach dem DocType-Praefix ein `;`,
  ist die Firma der Teil nach dem **letzten** `;` (darf Bindestriche tragen
  -> „Dassault-Systems" bleibt ganz); sonst der Teil nach dem **ersten** `-`
- **Blacklist** (umlaut-normalisiert): freelancer, ausfuehrlich,
  deutsch/english, master, version, mit/ohne-foto, kurz/lang, …
- **Kuerzel-Filter:** ≤ 3 Zeichen ohne Kleinbuchstaben (SC, SL, BWI) =
  Initialen, keine Firma
- **Zahlen/Datum-Filter**

### 🐛 #644 `email_verknuepfen` akzeptiert jetzt auch Dokument-IDs

Hochgeladene `.eml`/`.msg` landen als `documents`, gepollte IMAP-Mails als
`emails` — die IDs sehen identisch aus. `email_verknuepfen` mit einer
Dokument-ID lieferte „E-Mail nicht gefunden". Jetzt: Fallback-Lookup im
Dokument-Store + transparente Verknuepfung via `linked_application_id`,
klare Fehlermeldung bei wirklich unbekannter ID.

### Geparkt

**#643** (Doku-Routing nach `doc_type`) ueberschneidet sich mit dem
bestehenden `/dokumente_verarbeiten`-Prompt — nach v1.8.0 verschoben.

### Tests

- 5 neue Tests (`test_v170_beta68_doku_fixes.py`)
- **1401 / 1401 gruen**

### Migration / Breaking Changes

Keine. Beide Aenderungen sind defensiv/additiv.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.70.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.70.zip)
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

## [1.7.0-beta.67] - 2026-05-14 — Ollama-Leistungs-Anzeige: #638 vollstaendig

> ⚠️ **Pre-Release / Beta**. Stable bleibt v1.6.10.

Letztes fehlendes Stueck von #638: der **Feedback-Loop im Dashboard**.
Backend (`/api/llm/accuracy`, beta.66) gab es schon — jetzt die Anzeige.

### ✨ Ollama-Leistung-Card (Settings → Lokale KI)

Neue Card im Lokale-KI-Tab (nur sichtbar wenn Ollama schon Stellen
auto-aussortiert hat):

- **automatisch aussortiert** — Gesamtzahl der `auto:`-Aussortierungen
- **von dir zurueckgeholt** — wie oft du eine Auto-Entscheidung
  korrigiert hast (reaktiviert)
- **Treffergenauigkeit** — Anteil der nicht-korrigierten Entscheidungen
  (farbcodiert: gruen ≥85%, amber ≥65%, coral darunter). Erscheint erst
  ab 5 Auto-Entscheidungen (sonst zu duenne Datenbasis).

Damit ist **#638 komplett** — alle 5 Stufen umgesetzt:
1. Auto-Aussortierung nach Jobsuche (beta.63/65)
2. Score-Anreicherung fuer duenne Beschreibungen (beta.65)
3. Few-Shot-Lernschleife aus Bewertungen (beta.63/65)
4. Heartbeat/Warmup-Service (beta.62)
5. Genauigkeits-Tracking + Dashboard-Anzeige (beta.66/67)

### Tests

- Backend unveraendert (Endpoint + Stats seit beta.66 getestet),
  Aenderung ist reine Frontend-Card
- 1394 / 1394 gruen

### Migration / Breaking Changes

Keine. Reine Anzeige.

### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-1.7.0-beta.67.zip](https://github.com/MadGapun/PBP/archive/refs/tags/v1.7.0-beta.67.zip)
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
