# Changelog

Alle wichtigen Änderungen am Bewerbungs-Assistent werden hier dokumentiert.

## [1.5.0-beta.23] - 2026-04-10

### Bug Fixes
- **Kalender-Modals funktionslos** (#418, #419, #417): Alle drei Modals (Neuer Termin, Bearbeiten, Kategorien) waren defekt wegen fehlendem `open`-Prop — jetzt behoben
- **Termin-Klick oeffnet falsche Seite** (#395): Follow-up-Termine mit Bewerbungs-Verknuepfung navigieren jetzt korrekt zur Bewerbung statt nichts zu tun
- **Top-Stellen leer auf Dashboard**: Filter entfernte Stellen mit Score 0 — jetzt werden alle aktiven Stellen angezeigt, sortiert nach Score
- **Statistiken woechentlich leer**: SQLite unterstuetzt `'-12 weeks'` nicht als Modifier — auf `'-84 days'` korrigiert
- **Loeschen-Button Berufserfahrung**: Entfernt von der Profil-Hauptseite (versehentliches Klicken), jetzt nur im Bearbeitungs-Dialog verfuegbar

### Features
- **Grafischer Kalender-Grid**: Monatsansicht mit 7-Spalten-Tagesraster (Mo-So), alle Tage sichtbar auch ohne Termine; Wochen-, Quartal- und Halbjahres-Ansicht als kompakte Mini-Grids; Klick auf Tag erstellt neuen Termin mit Datum vorbelegt
- **Kalender-Sidebar**: Navigations-Sidebar (wie Profil) mit Ansicht, Zeitraum und Filter-Kontrollen direkt unter dem Heartbeat
- **Termin-Filter wiederhergestellt**: Alle/Kommende/Vergangene als Sidebar-Filter — war versehentlich entfernt worden
- **Statistiken: Unabhaengige Zeitraum-Kontrollen**: Gruppierung (Taeglich/Woechentlich/Monatlich) und Zeitraum (30d/90d/6m/12m/Alles) sind jetzt zwei separate, unabhaengige Controls — z.B. taeglich ueber 12 Monate ist jetzt moeglich

## [1.5.0-beta.22] - 2026-04-10

### Features
- **Kalender CRUD** (#418, #419): "Neuer Termin" Button funktioniert jetzt vollstaendig mit Dauer, Kategorie, Bewerbungs-Verknuepfung; Termine koennen bearbeitet und mit Bestaetigungsdialog geloescht werden
- **Benutzerdefinierte Kategorien** (#417): System-Kategorien (Bewerbung, Interview, Privat) und frei erstellbare Kategorien mit Farbe und Statistik-Sichtbarkeit; Filter-Checkboxen im Kalender
- **Kalender-Ansichten** (#394): Umschaltbare Ansichten (Woche/Monat/Quartal/Halbjahr) mit Navigation; Private Eintraege werden als "Geblockt" (grau) angezeigt und erscheinen nicht in Statistik/Aktivitaetslog
- **Termin-Navigation** (#395): Klick auf Bewerbungstermin oeffnet Bewerbungs-Dossier; Klick auf privaten/unverknuepften Termin oeffnet Bearbeitungsdialog
- **Profil-Gefahrenzone** (#420): "Profil loeschen" wurde von der Profil-Seite in die Gefahrenzone der Einstellungen verschoben mit Profilnamen-Bestaetigung
- **Dashboard-Redesign** (#421): "Im Fluss" + "Heute fuer dich" links (2/3), Schnellimport rechts (1/3); Anstehende Termine direkt unter "Im Fluss" (max 5, mit Klick-Navigation)

### Datenbank
- Schema v23: `application_meetings.application_id` ist jetzt nullable (erlaubt manuelle Termine ohne Bewerbung), neue Spalten `is_private`, `duration_minutes`, `category_id`; neue Tabelle `meeting_categories`

## [1.5.0-beta.21] - 2026-04-10

### Bug Fixes
- Profil-Isolation fuer CV-Daten-Endpunkte gehaertet: Positionen, Ausbildung, Skills, Jobtitel und Projekte pruefen jetzt das aktive Profil bei PUT und DELETE
- `PUT /api/applications/{app_id}/status` validiert jetzt das `status`-Feld und liefert 400 statt 500 bei fehlendem Pflichtfeld

### Qualitaet
- Regressionstests fuer Cross-Profile-Zugriffe auf alle 10 CV-Daten-Endpunkte

## [1.5.0-beta.20] - 2026-04-10

### Bug Fixes
- Weitere Application-/Email-Endpunkte gegen profilfremde IDs abgesichert: Timeline, Print, Status, Notes, Snapshot, Fit-Analyse, E-Mail-Details, E-Mail-Loeschen, Match-Bestaetigung und Status-Uebernahme pruefen jetzt aktives Profil und aktive Bewerbung
- Bewerbungsbearbeitung schreibt Timeline-Eintraege wieder schema-konform ohne String-ID und liefert bei echten Aenderungen keinen `datatype mismatch`-500er mehr

### Qualitaet
- Regressionstests fuer Cross-Profile-Bewerbungen/E-Mails sowie Same-Profile-Bearbeitung und E-Mail-Aktionen ergaenzt

## [1.5.0-beta.19] - 2026-04-10

### Bug Fixes
- Profil-Isolation fuer Dokument-Endpunkte gehaertet: Download, Typ-Aenderung, Relinking und Loeschen akzeptieren nur noch Dokumente aus dem aktiven Profil
- Meeting-Endpunkte gegen profilfremde IDs abgesichert: Einzelansicht, ICS, Update, Delete und Bewerbungs-Meetingliste pruefen jetzt das aktive Profil
- `create_backup()` erzeugt Sicherungen jetzt SQLite-/WAL-sicher ueber die Backup-API statt ueber eine nackte Dateikopie
- `release_check.py` smoke-testet das Repo jetzt mit `src/` auf dem Python-Pfad und meldet Versions-/Changelog-Mismatches klarer

### Qualitaet
- Neue Regressionstests fuer Cross-Profile-Dokumente, Cross-Profile-Meetings, WAL-Backups und den Release-Gate

## [1.5.0-beta.18] - 2026-04-09

### Verbesserungen
- 19 umgesetzte Issues fuer den Beta-Feinschliff rund um Dashboard, Dokumente, Kalender, Settings und Import-/Analyse-Flows

## [1.5.0-beta.17] - 2026-04-09

### Bug Fixes
- Installer laedt Python erneut, wenn eine kopierte Installation defekt ist (#386)

## [1.5.0-beta.16] - 2026-04-09

### Bug Fixes
- Installer korrigiert `_pth`-Konfiguration bei vorhandener Python-Installation (#386)

## [1.5.0-beta.15] - 2026-04-09

### Qualitaet
- Clean-Release ohne ZIP-Asset fuer den Installer-/Release-Pfad

## [1.5.0-beta.14] - 2026-04-09

### Qualitaet
- Release-Stand fuer `v1.5.0-beta.14` konsolidiert

## [1.5.0-beta.13] - 2026-04-09

### Neue Features
- Dokument-Analyse-Status im Dashboard und Import-Flag fuer uebernommene Daten
- Aktivitaetslog fuer neuere Workspace-Aktionen

## [1.5.0-beta.12] - 2026-04-09

### Verbesserungen
- Dokumente loeschbar, Metrik-Perspektiven nachgeschaerft, Chrome-/Skill-/Settings-UX erweitert

## [1.5.0-beta.11] - 2026-04-09

### Bug Fixes
- Dual-DB-Probleme, Kalender-Kantenfaelle, Umlaute, Antwortzeiten und `is_active`-Handling stabilisiert

## [1.5.0-beta.10] - 2026-04-08

### Verbesserungen
- Dashboard Metrik-Karte: Zeigt jetzt nur unbearbeitete Stellen (ohne bereits beworbene). "20 geschrieben / 0 unbearbeitete Stellen" statt irreführend "3 aktive Stellen"

## [1.5.0-beta.9] - 2026-04-08

### Bug Fixes
- **Docs-Tab unerreichbar:** `dokumente` fehlte in PAGE_IDS — Klick auf Docs-Tab landete auf Dashboard
- **Dashboard Metrik-Karte:** "59/3" war verwirrend — zeigt jetzt klar "20" (Bewerbungen geschrieben) getrennt von "3 offene Stellen"

### Verbesserungen
- **Profil-Dokumente verschlankt:** Dokumentenliste aus Profil-Seite entfernt, nur noch Upload + Status-Dashboard + "Docs-Tab oeffnen"-Button. Volle Verwaltung im Docs-Tab.
- **Docs-Tab: Upload integriert:** Drag & Drop + Datei/Ordner-Upload direkt im Docs-Tab (kein Umweg ueber Profil noetig)
- **Docs-Tab: Durchsuchbare Bewerbungs-Dropdowns:** Bewerbungs-Filter und Verknuepfungs-Modal sind jetzt durchsuchbar (Freitext-Eingabe filtert die Liste)

### Qualitaet
- 390 Tests bestanden (1 Test an neues Profil-Layout angepasst)
- Frontend-Build aktualisiert

## [1.5.0-beta.8] - 2026-04-08

### Layout-Redesign
- **#363**: Topbar-Overlap behoben — Version und MCP-Lebensanzeige aus der Topbar in eine globale linke Sidebar verschoben. Profil-Navigation ebenfalls in Sidebar integriert. Kein Overlap mehr bei 8 Tabs.

### Bug Fixes
- **#364**: Kalender zeigt jetzt alle Termine — Follow-ups als eigene Kategorie integriert, Status `tentativ` wird angezeigt, heutige Termine verschwinden nicht mehr in "Vergangene". Route-Reihenfolge korrigiert (`/calendar` vor `/{meeting_id}`, gleicher Bug wie #339).
- **#365**: Profil-Seite Dokumente-Sektion zeigt jetzt Bewerbungs-Querverweis (Firma + Jobtitel) pro Dokument

### Verbesserungen
- **#366**: Docs-Tab UX komplett ueberarbeitet — Bewerbungs-Filter, "Nicht verknuepft"-Schnellfilter, klickbare Firmenlinks, ausklappbare Textvorschau, "Verknuepfung aendern"-Modal, verbesserte Paginierung (Seite X von Y + Gesamtzahl)

### Qualitaet
- 390 Tests bestanden (0 Regressionen)
- Frontend-Build aktualisiert

## [1.5.0-beta.5] - 2026-04-08

### KRITISCH — Datensicherheit
- **#341**: Profil-Migration v1.4.x → v1.5.0 gefixt — `get_data_dir()` zeigt jetzt korrekt auf `data/`-Unterordner, automatische Migration der flachen v1.4.x-Struktur
- **#349**: Automatisches DB-Backup vor jeder Migration und vor jedem Schema-Upgrade (max. 5 Backups, rotierend)
- **#345**: Deinstaller bietet jetzt Desktop-Backup an bevor Daten geloescht werden; Datenlöschung erfordert Eingabe von "LOESCHEN" statt einfachem "j/n"
- **#343**: Registry-Eintrag wird nach Loeschung verifiziert und bei Bedarf erneut versucht

### Bug Fixes
- **#342**: Help-Button (?) funktionierte nicht — `setShowWizard` (undefined) durch `setWizardOpen` ersetzt
- **#340**: Unicode-Escape `N\u00e4chstes` durch echtes `Nächstes` ersetzt (3 Stellen im Dashboard)

### Verbesserungen
- **#344**: Installer liest Version dynamisch aus `__init__.py` statt hardcoded `beta.0`
- **#348**: Versionsnummer dezent im Dashboard-Header sichtbar (neben Help-Button)

## [1.5.0-beta.4] - 2026-04-08

### Verbesserungen
- **#337**: Quellen-Transparenz und Nutzer-Fuehrung bei langsamen Browser-Quellen
  - SOURCE_REGISTRY: Alle 17 Quellen mit `geschwindigkeit`-Feld (schnell/langsam/manuell) und Warnhinweisen fuer Browser-Quellen
  - Frontend Quellen-Einstellungen: Geschwindigkeits-Badges (⚡ Schnell / 🕐 Browser / Manuell), Infobox mit Erklaerung und Tipp fuer Claude-Suche
  - Such-Progress: Browser-Quellen werden namentlich und mit Zeitschaetzung angekuendigt
  - Timeout-Meldung: Statt "Uebersprungen" jetzt konkreter Tipp "Lass Claude gezielt auf diesen Portalen suchen"
  - README: Quellen-Tabelle nach Geschwindigkeit sortiert, neue Hinweisbox zu Browser-Quellen und Claude-Alternativsuche

## [1.5.0-beta.3] - 2026-04-08

### Bug Fixes
- **#334**: `release_check.py` Windows-safe — UTF-8 stdout reconfigure, ASCII-Fallback-Symbole, Temp-Ordner Cleanup mit `try/finally`
- **#336**: Wizard-Overlay blockiert Header nicht mehr — z-index unter Header (`z-45`), Overlay startet unterhalb Topbar, Hilfe-Button schliesst Wizard

### Verbesserungen
- README Test-Badge auf 390 aktualisiert
- Frontend-Build aktualisiert

## [1.5.0-beta.2] - 2026-04-08

### Bug Fixes
- **#339**: ICS-Gesamtexport defekt — statische Route `/api/meetings/export.ics` wurde von dynamischer `{meeting_id}` Route ueberschattet (Route-Reihenfolge korrigiert)
- **#335**: Regionen in Jobsuche ignoriert — `regionen` aus Suchkriterien werden jetzt an Indeed (`l=`), Monster (`where=`), Bundesagentur (`wo=`), StepStone (`?where=`) und Freelancermap (`&ort=`) durchgereicht
- **#334**: `release_check.py` crasht unter Windows — alle `read_text()` Aufrufe auf `encoding="utf-8"` umgestellt
- **#338**: Heise-Fallback liefert generische Uebersichtsseiten — Kategorie-Links und Titel ohne konkrete Stellen-ID werden gefiltert
- **#336**: First-Run-Wizard Button "Spaeter" blockiert Browser-Tests — Text auf "Spaeter" mit korrektem UTF-8 geaendert

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
