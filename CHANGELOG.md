# Changelog

Alle wichtigen Aenderungen am Bewerbungs-Assistent werden hier dokumentiert.

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
