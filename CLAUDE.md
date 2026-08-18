# PBP — Claude-Code-Memory

Persoenliches Bewerbungs-Portal (PBP). MCP-Server (Python/FastMCP 3.x) +
React-Frontend + SQLite. **v1.7.18** ist Stable (`--latest`, 2026-08-18; Nachzug #922/#918-Defekt-2 auf die Praxis-Welle v1.7.17 desselben Tages, Details im Stand-Block unten). Davor **v1.7.16** war Stable (`--latest`, 2026-08-14; erster 1.7er-Release MIT der Sichtbarkeits-Arbeit — bis v1.7.15 lag sie nur auf main. MERKE: Schaufenster-Arbeit ist erst beim Nutzer, wenn sie in der Stable-Linie ist) —
Hotfix aus Branch `hotfix/v1.7.8` vom Tag v1.7.7: Ausschluss-Keywords matchen
strikt (#762; der harte K.o. feuerte fuzzy beim Volltext-Nachpflegen und nullte
den Score). MERKE: Fixes, die auch das Stable betreffen, gehoeren in die
1.7-Linie und nicht nur in die 1.8-Beta — die Beta zieht kaum jemand.
Davor: **v1.7.7** war Stable — v1.7.0 wurde am
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
+ J4.1 ics, beta.3 = J5 Newsletter, beta.5 = Welle B (B25/B16/B18-Teil,
Schema v52), beta.6 = Hotfix #760 (stderr-Backpressure-Freeze).
Betas sind GitHub-Prereleases,
`--latest` bleibt v1.7.7; Hotfix-Pfad: Branch vom Tag v1.7.7. **ALLE 25
offenen Issues sind Wellen zugeordnet** (Tabelle im Master-Plan →
Naechste Schritte): Kern-Wellen B (Quellen: #656 Playwright-Komponente,
#735/B25 neu, #627), F (Lokale KI: #669, #714, #632, F16-Rest), D
(Bewerbungs-Mehrwert: #740 Referenzen, #452 Interview-Arc), J8
(Branchen-Radar #718/#716/#717, zuletzt); beta.0-Beipack A21/#758,
beta.1-Beipack #687/#688 (Snapshots). #671 wurde 2026-07-14 geschlossen
(Ebene 0+2 fertig, Ollama-Rest in Welle F). ACHTUNG Schema: v49 ist fuer
`components` (beta.0) reserviert — D24/#740 bekommt die naechste Nummer.

## Stand 2026-08-18 (v1.7.17 Stable + v1.8.0-beta.12) — Praxis-Welle 18.08.

**Schema:** v48 / v52 unveraendert (Safety-Nets: scoring_config.
set_by_user, jobs.dismiss_note, scraper_health deaktiviert_am/-grund +
letzte_probe_am/-status). **Tests:** 2288 / 2354 passed. Elf Issues aus
zwei Bewerbungs-Nachmittagen (#906-#920); Hotfix-Branch vom Tag v1.7.16,
7 Cherry-Picks, Port-Audit ueber die 65 mitgewanderten Wellen-Tests.
Neu offen: #924 (Elwosa-Linien-Wiederholung), #919 als B36 fuer v1.8
(LinkedIn-Voyager-Handoff), #922 (Phantom-Termine aus Mail-Zitaten)
blieb BEWUSST liegen — Kandidat naechste Welle.

MERKE-Punkte dieser Welle:

(1) **C34/#917 A+B** — INSERT OR REPLACE ersetzt nur bei UNIQUE-
Konflikt: Seed-Zeilen tragen profile_id='', der Write die aktive ID —
kein Konflikt, also Dublette, und die Altzeile (samt ignore_flag der
Automatik) blieb ueber MCP unerreichbar. Echtes UPSERT = DELETE beider
Varianten + INSERT; scoring_konfigurieren hat jetzt 'loeschen';
set_by_user macht Nutzer-Regler fuer _auto_adjust_scoring unantastbar
(Live-Repro: Automatik kehrte die Nutzerkorrektur im selben Durchgang
um, Zaehler 71 >= Schwelle 5).

(2) **C34/#917 C** — die Entfernungs-Brackets sind OBERGRENZEN. Der
Lern-Schluessel '50km' landete via Ziffern-Extraktion im Bracket 50 und
bestrafte Stellen BIS 50 km — der Lerneffekt war INVERTIERT (-10 auf
nahe, -8 auf 600 km). Lernen jetzt in Stufe '999'; Safety-Net migriert
km-Altzeilen (tiefer gewinnt) und stellt die Nah-Brackets wieder her.

(3) **C34/#917 D** — fit_analyse wendete keywords_ausschluss NIE an und
matchte gegen die UNgestrippte Beschreibung: dieselbe Stelle hatte
Score 0 (Liste) und 88 (Fit-Analyse) gleichzeitig. Ausloeser im Feld:
redaktionelle Notiz mit LinkedIn-Bewerberstatistik ('20 %
Berufseinsteiger') VOR dem ----Trenner. Beide Pfade jetzt identisch;
scores_neu_berechnen liefert auffaellige_aenderungen mit Grund.

(4) **A29/#915** — busy_timeout (30 s) war gesetzt, es kam trotzdem
NICHTS: 4-Minuten-Stille = Blockade auf PYTHON-Ebene, dagegen hilft nur
ein Wall-Clock-Budget im Tool-Pfad (services/tool_budget.py, 45 s,
fester ThreadPool wegen A28-per-Thread-Connections — ein Thread je
Aufruf wuerde Connections leaken). pbp_mcp_diagnose hing an seinem
EINZIGEN DB-Zugriff — Anreicherungen gehoeren hinter mit_kurzbudget.
Sperrhalter-Benennung DB-frei via services/hintergrund_status.py.

(5) **C38/#913** — db.dismiss_job ist das Nadeloehr ALLER dismiss-
Writes und damit der richtige Ort fuer den Vokabular-Schreibschutz;
Freitext nach jobs.dismiss_note, nie ins Lern-Feld. auto:-Prefix hat
eine KURZFORM ohne Begruendung ('auto:falsches_fachgebiet') — Regex mit
optionalem Rest, sonst bricht der Wiedergaenger-Vertrag (#671). Die
Ollama-Genauigkeits-Statistik zaehlt jetzt LIKE-auto UND
profil_match_negativ (beide Formate).

(6) **F39/#908** — die alte Eskalation (count-5)*0.5 war ab ~13
Nennungen am Cap = Zweistufen-Schalter. Linear ueber (start,max) je
Grund, 5..155. zu_junior mappte auf stellentyp/praktikum und traf
Festanstellungen NIE (Senioritaet ist keine Stellenart).

(7) **G22/#907** — maxHeight:'100%' gegen ein height:auto-Elternteil
ist in CSS unaufloesbar (= none): der 'adaptive' Elwosa-Scroller
scrollte seit beta.61 NIE, die Liste schob den Footer. Prozent-Hoehen
brauchen eine geschlossene Flex-Kette (h-full/min-h-0 durchgereicht).

(8) **B35/#906** — Auto-Deaktivierung ist ein sich selbst
bestaetigender Zustand (deaktivierte Quelle laeuft nie wieder, Status
wird nie widerlegt). Deshalb: Probe-Ergebnisse an der Quelle
persistieren und erreichbare Deaktivierte als 'pruefen' melden.
deprecated (Registry, bewusst) und auto_deaktiviert (Automatik) sind
zwei verschiedene Dinge in zwei verschiedenen Feldern.

(9) **Release-Mechanik** — tests.yml triggert NUR auf main/PR: fuer
Hotfix-Branches `gh workflow run tests.yml --ref hotfix/vX.Y.Z`
(workflow_dispatch), sonst wartet man ewig auf einen Run, der nie
kommt. release_check.py liegt im REPO-ROOT (nicht scripts/).

(10) **D37/#922 (Nachzug v1.7.18)** — der Mail-Terminextraktor lief
ueber den KOMPLETTEN Text: eine Mail mit Antwortverlauf erzeugte je
zitierter Sendezeit einen Termin (vier Stueck, alle 'interview', 60
min). firma_kontext meldete daraufhin fuenf Interviews statt einem —
die Regel 'nie aus dem Gedaechtnis, immer aus PBP' setzt voraus, dass
PBP stimmt. Jetzt: Zitat abschneiden (strip_quoted_reply), Datum
allein genuegt NICHT (Beleg: ICS/Link/Terminvokabular), kein pauschales
'interview'. MERKE beim Zitat-Marker: '-----Urspruengliche Nachricht---'
kommt in ue-UND-ü-Schreibweise vor — `urspr(?:u|ue|ü)ngliche`.

(11) **C35 Teil 2/#918 (Nachzug v1.7.18)** — ein Issue-Titel mit zwei
Defekten wurde nur zur Haelfte abgearbeitet und trotzdem geschlossen.
MERKE: bei Issues mit mehreren nummerierten Defekten die
Akzeptanzkriterien-Liste VOR dem Schliessen einzeln abhaken. Inhaltlich:
die Abschluss-Erkennung lief ueber den ganzen Datensatz (Bewerber-
statistik in den Notizen = Aussage ueber ANDERE Bewerber, loeste
ATS-Alarm aus) und kannte keine englischen Muster. Und: Phrasen-Muster
brauchen Whitespace-Glaettung, sonst zerreisst ein Zeilenumbruch mitten
in 'oder eine vergleichbare Ausbildung' ausgerechnet die Oeffnungsklausel.

## Stand 2026-08-11 (v1.7.12 Stable + v1.8.0-beta.11) — Grosse Welle

**Schema:** v48 / v52, beide unveraendert (nur idempotente Safety-Nets:
blacklist.is_active/updated_at/grund_vorher, interview_reflections.
meeting_id, elwosa_messages.link_url/link_label, tasks.application_id
nullable via writable_schema). **MCP-Tools:** 202 / 215 (+9: follow_up_
bearbeiten, todo_bearbeiten/_hinfaellig/_details, aufgaben_uebersicht,
interview_reflexion_loeschen, interview_lehren_auswerten,
diagnose_befund_abweisen, dokumente_ohne_bewerbung). **Tests:** 2199 /
2265 passed. 15 Issues in einer Welle (#768, #797, #809-#816,
#822-#828), 6 davon vom selben Vormittag.

MERKE-Punkte dieser Welle:

(1) **F36/#822** — der Elwosa-Kern-Bug war ein KLASSEN-MAPPING:
can_post_class prueste `trigger_kind == "world"`, gefeuert wurde mit
`holiday_summer`/`late_night` → fiel durch ALLE Limits und durch
`sachlich`. Zweite Ursache: pick_line fiel auf den vollen Pool zurueck,
sobald er verbraucht war. Bei Drossel-Logik IMMER pruefen, ob die
Pruefung dieselben Schluessel sieht wie der Aufrufer.

(2) **C32/#827** — Anzeigen-Scoring: Treffer im Firmen-Werbeabsatz
(Portfolio-Prosa) zaehlen 0.25x (`_firmenabsatz_ende` in
job_scraper/__init__). Abwerten statt nullen — falscher Ausschluss ist
teurer als zu hoher Score. Geschaetzte Gehaelter zaehlen GAR NICHT mehr.

(3) **A27/#768** — es gab im gesamten Code KEINEN wal_checkpoint-
Aufruf. close() macht jetzt TRUNCATE, die Auto-Engine PASSIVE je
Zyklus. Bei Zweitprozess-Symptomen: pbp_diagnose zeigt WAL-Groesse und
Blockade.

(4) **D35/#814/#815** — tasks.application_id NOT NULL wurde per
writable_schema + PRAGMA schema_version geloest (das #796-Muster, NIE
db.close()). Der Erledigt-Haken-Befund: ein funktionierender Button in
Statussymbol-Optik gilt als nicht vorhanden — vor Neubau pruefen, ob
etwas nur unsichtbar ist.

(5) **Cherry-Pick-Lehre (Stable-Port):** NIE `--skip` als Fallback in
Resolution-Schleifen — vier Teile wurden still uebersprungen. Verlorene
Hunks findet man ueber die mitgewanderten TESTS (82 Wellen-Tests auf
dem Stable-Branch deckten den verlorenen analyse.py-Hunk auf).

Offen fuer die naechste Welle: #802 (Score-Schwelle aus Verteilung),
#808 (Health inhaltlich — deckt #809-Rest-UI mit ab), #811 (ATS-Slugs),
#813 (Filterstufen-Telemetrie), #823-Rest (Kanaele 2/3/5/7), #817
(PII an der Quelle), #791-#795, #798, #801, #806.

## Stand 2026-08-06 (v1.7.11 Stable + v1.8.0-beta.10) — Stille Ausfaelle

**Schema:** v48 / v52, beide unveraendert. **MCP-Tools:** 193 / 206
(+`termin_dubletten_bereinigen`). **Tests:** 2082 / 2147 passed.

Roter Faden: Fehler, die sich als Erfolg tarnen — keiner warf je eine
Fehlermeldung.

(1) **B29/#807** — die Bundesagentur-Suche lief auf `pc/v4/jobs`; der
Endpunkt liefert seit Sommer 2026 **404**. Die produktivste Quelle lag
still. Suche jetzt **v6**, Details bleiben **v4** (v5/v6 dort 403 — live
geprueft 06.08.). MERKE: v6 hat ALLE Feldnamen umbenannt
(`stellenangebote`→`ergebnisliste`, `titel`→`stellenangebotsTitel`,
`arbeitgeber`→`firma`, `refnr`→`referenznummer`, `beruf`→`hauptberuf`,
Ort unter `stellenlokationen[0].adresse.ort`) — ein reiner
Endpunkt-Tausch haette leere Stellen ergeben.

(2) **F35/#799** — der `lernen`-Lauf lief SYNCHRON im Scheduler-Thread
samt Ollama-Aufruf. Bei geteilter SQLite-Connection
(`check_same_thread=False`) blockiert das den GESAMTEN MCP-Server.
MERKE: langlaufende Arbeit gehoert in einen Thread mit
`background_jobs`-Eintrag — sonst gibt es nicht mal eine Spur.
Ausserdem KORREKTUR des eigenen Fehlers aus F28/#784: `learned_insights`
war eine Doppelanlage neben `learning_insights` (#594). **Vor dem
Anlegen einer Tabelle pruefen, ob es sie unter aehnlichem Namen gibt.**

(3) **A25/#796** — `documents.linked_application_id` hatte in
gewachsenen Bestaenden INTEGER-Affinitaet; Hex-IDs wie `42061e46` werden
darin still zu `4.2061e+50`, `1e960980` zu `inf`. MERKE: `inf = inf` ist
wahr — solche Fehlzuordnungen melden sich bei JEDER SELECT-Pruefung als
sauber. Heilung: erst Typ auf TEXT, DANN Werte zurueckuebersetzen (sonst
laeuft der korrigierte Wert wieder in dieselbe Falle).

**MERKE (CI-Segfault, teuer erkauft):** NIE `db.close()` aufrufen,
solange Hintergrund-Threads laufen — alle teilen sich eine Connection,
SQLite stuerzt dann auf C-Ebene ab (Exit 139). Fuer einen Schema-Reload
stattdessen `PRAGMA schema_version` hochzaehlen. Tests, die Threads
starten, muessen diese vor dem Fixture-Teardown joinen.

Ausserdem: D30/#804 Termin-Dubletten, C31/#790 Blacklist-Ausnahme je
Titel. Offen als B30/#808: der Health-Check meldet falsch-gruen, weil
HTTP 200 nichts ueber gelieferte Stellen aussagt — genau deshalb blieb
B29 wochenlang unbemerkt.

## Stand 2026-07-24 (v1.7.10 Stable + v1.8.0-beta.9) — Stabilisierungswelle

**Schema:** v48 (Stable) / v52 (Beta), beide unveraendert — die neue
`learned_insights`-Tabelle kommt als idempotentes CREATE-IF-NOT-EXISTS-
Safety-Net OHNE Versions-Bump (v49 bleibt fuer `components` reserviert;
Muster fuer kuenftige linien-uebergreifende Tabellen). **MCP-Tools:**
192 / 205 (+9: `kalibrierung_backtest`, `suchperformance_auswerten`,
`kontakt_historie`, `vermittler_historie`, `erkenntnisse_ableiten/
anzeigen`, `erkenntnis_bestaetigen`, `elwosa_fragen`,
`elwosa_prompt_kopieren`). **Tests:** 2045 / 2111 passed.

Acht Praxis-Issues vom 24.07., strikt getrennt: v1.7 = Fehler/
Datenqualitaet/Kalibrierung/fehlende Auswertungen; v1.8-Reste nur als
Label `v1.8` + Kommentar. MERKE: die urspruenglichen Issues #769/#770/
#772/#773/#775/#776/#777 trugen PII (Recruiter-Namen, User-Klarname im
Dateipfad, Gehaltszahlen) und wurden nach DoD-9 GELOESCHT und als
**#778-#784** anonymisiert neu angelegt (Mapping: 772→778, 775→779,
776→780, 777→781, 773→782, 769→783, 770→784; #774 war sauber).

Kern: (1) **C29/#778** `kalibrierung_backtest` ist eine SCHATTENRECHNUNG
(ruft nie scores_neu_berechnen — Test erzwingt das); IDF+Top-5-Deckelung
nur als Opt-in (`suchkriterien_bearbeiten(kategorie='scoring',
aktion='idf')`), Injektion via `criteria['_idf_faktoren']` in
get_search_criteria; Einzelgewichte in `criteria['keyword_gewichte']`.
(2) **D27/#779** applied_at-Nachtrag bei uebersprungenem 'beworben';
Status `arbeitgeber_ausgefallen` (kein Rueckzug, Angebot bleibt via
Event-Historie in offer_rate) — Status-Listen an 10+ Stellen (DB, Tools,
dashboard.py, Frontend). (3) **D29/#781** `services/statistik_erweitert.py`
(Zeit/Kanal/Ablehnungs-Kategorien, Quote roh+bereinigt; Vor-PBP =
Untergrenze). (4) **C30/#782** Repost-Erkennung compute-on-read
(`find_repost_of_application` in duplicate_detection, bewusst OHNE
URL-Vergleich — Reposts haben neue URLs, #670-Regel wuerde sie filtern).
(5) **F28/#784 + F29/#774** learned_insights (nichts wirkt ohne
Nutzerbestaetigung; widersprochen = -1, nie erneut) + Elwosa-Dialog
(auskunftsfaehig, nicht urteilsfaehig; Ausfall ehrlich statt
Claude-Fallback).

## Stand 2026-07-23 (v1.7.9 Stable + v1.8.0-beta.8) — Verfolgbarkeit

**Schema:** v48 (Stable) / v52 (Beta), beide unveraendert. **MCP-Tools:**
183 / 196 (+`stellen_urls_heilen`, +`bewerbungs_stellen_abgleichen` in
tools/jobs.py). **Tests:** 1999 / 2064 passed, 1 skipped.

Vier Befunde aus einem Praxis-Nachmittag (23.07.): von acht aktiven Stellen
hatte KEINE einen nachvollziehbaren Weg zur Original-Ausschreibung.
(Die Issues #763 und #766 wurden noch am selben Tag DSGVO-geloescht —
reale Firmennamen; Inhalte stehen in Master-Plan B27/C28 + CHANGELOG.)

(1) **B27/#763** — `is_search_result_url` uebersah pfadbasierte Such-URLs
ohne Query, darunter die Form, die PBP fuer den Portal-Aufruf SELBST baut.
MERKE: Detail-Marker gegen den **Pfad** pruefen, nicht gegen die ganze URL —
sonst reisst `xing.com/jobs/<slug>-123456` mit. Neu `stellen_urls_heilen`
(AK5 aus #645 war nie umgesetzt; wirkte nur auf NEUE Laeufe). **Ehrliche
Grenze, nicht spaeter als Bug behandeln:** echte Detail-URLs sind aus dem
Bestand NICHT rekonstruierbar — Portal-IDs werden beim INSERT nie
persistiert.

(2) **D25/#764** — `add_application` legte GAR KEINE `application_jobs`-Zeile
an; die Junction lief seit v34 strukturell leer. `application_jobs` ist jetzt
fuehrend, `applications.job_hash` wird synchron gehalten. Neu
`bewerbungs_stellen_abgleichen`.

(3) **D26/#765** — Frontend: `frontend/src/lib/jobLink.js` spiegelt
`is_search_result_url`; CI-Schritt prueft DIESELBEN Faelle auf beiden Seiten
(`jobLink.test.mjs`). Bei Aenderung an einer Seite die andere nachziehen.

(4) **C28/#766** — Anker-Pflicht (`services/stellen_anker.py`): URL, Dokument
oder Kontakt. Such-URL zaehlt NICHT, lange `description` auch nicht (eine
Claude-Zusammenfassung liest sich wie eine Anzeige). Bewusst kein harter
Block. `stelle_manuell_anlegen` nimmt jetzt Kontakt-Parameter (via
`contact_links` `target_kind='job'`, kein Schema-Bump).

**Linien-Unterschied:** die Such-URL-Muster liegen in der 1.7-Linie als reine
Daten in `job_scraper/such_urls.py`, in der 1.8-Linie in
`job_scraper/handoff.py` (B25/#735, mit dem Handoff-Feature). Der Import in
`stellen_urls_heilen` faellt der Reihe nach durch — keine Linie schleppt das
Feature der anderen mit.

**MERKE Release-Gate:** `release_check.py` erwartet den CHANGELOG-Kopf auf der
AKTUELLEN Version. Ein nachtraeglich oben eingefuegter Stable-Eintrag (wie der
v1.7.8-Nachzug am 22.07.) bricht damit das Gate auf main, bis der naechste
Release-Eintrag darueber kommt.

## Stand 2026-07-16 (v1.8.0-beta.6, Prerelease) — Hotfix #760

**Schema:** v52 (unveraendert). **MCP-Tools:** 194. **Prompts:** 25.

Kern: **A23/#760** — Server-Freeze bei `jobsuche_starten` mit vielen
Quellen REPRODUZIERT und behoben. Mechanismus: Such-Thread loggt massiv
auf stderr; liest der MCP-Client stderr nicht kontinuierlich (Claude
Desktop tut das nicht), laeuft der OS-Pipe-Puffer voll → der Log-write
blockiert UND haelt den Logging-Handler-Lock → `logger.info("Tool
aufgerufen")` der Middleware (Event-Loop-Thread!) haengt am Lock →
kein Tool antwortet mehr, Heartbeat friert ein, Dashboard/DB laufen
weiter (eigene uvicorn-Handler). Differential-Beweis via
stdio-Repro-Client (QA-isoliert): 35 Quellen + ungelesenes stderr =
Freeze t+40s; stderr gelesen = stabil; mit Fix + ungelesen = stabil.
Fix: `logging_config.py` Console ueber `DropOnFullQueueHandler` +
`QueueListener` entkoppelt (volle Queue → Console-Zeilen verworfen,
Log-DATEI behaelt alles); Middleware schreibt Heartbeat VOR dem Log.
Tests: `test_v18_logging_backpressure_760.py` (4). MERKE fuer
Debug-Anleitungen: py-spy 0.4.2 kam an die venv-Python-3.13-Prozesse
nicht ran („Failed to find python version") — Diagnose-Anleitungen
lieber auf Differential-Läufe + Log-Datei stuetzen.

## Stand 2026-07-16 (v1.8.0-beta.5, Prerelease) — Welle B: Quellen

**Schema:** v52 (`scraper_runs` + `custom_sources`, additiv).
**MCP-Tools:** 194 (+`quelle_handoff`/`quellen_langzeit_auswertung`
(#735 B25), +`custom_quelle_hinzufuegen/anzeigen/loeschen` (#627 B16),
alle in tools/jobs.py). **Prompts:** 25.

Kern: (1) **B25/#735** — `update_scraper_health` schreibt jetzt je Lauf
einen `scraper_runs`-Datensatz (Historie darf Health-Write nie
blockieren); `quellen_langzeit_auswertung(tage)` rechnet Trefferquote,
Fehlerklassen, Trend (versiegt = frueher neu>0, zweite Haelfte 0) und
Empfehlung. `job_scraper/handoff.py`: HANDOFF_URL_TEMPLATES (langlebige
Such-URLs, KEINE DOM-Wetten) + GENERIC_EXTRACTION_JS (Anker-Heuristik
wie Newsletter-Ingest) + build_handoff — `quelle_handoff`-Tool,
google_jobs_url-Muster generalisiert. (2) **B16/#627** —
Custom-Karriereseiten als HANDOFF-Quellen (bewusst KEIN Auto-Scraping,
B18-Lehre); Health-Ping im quellen_health_check (Status an Quelle
vermerkt). (3) **B18/#656 Teilschritt** — `playwright-chromium` als
I10-Komponente (art='playwright': Detection via ms-playwright-Ordner +
importierbares Paket, Install via `python -m playwright install
chromium`, plattformuebergreifend VOR dem win32-Gate); SPA-Selektoren
bleiben zurueckgestellt (Master-Plan-Optimierung: Live-Inspection-
Bedingung, JSON-API bevorzugt) — B18 im Plan 🟨. Tests:
`test_v18_beta5_welle_b.py` (9).

## Stand 2026-07-14 (v1.8.0-beta.4, Prerelease) — Newsletter-Ingest

**Schema:** v51 (`newsletter_sources`, additiv). **MCP-Tools:** 189
(+`newsletter_quelle_markieren`/`newsletter_verarbeiten` in dokumente).
**Prompts:** 25. Damit sind ALLE J-Feature-Betas geliefert; weiter mit
Kern-Wellen B/F/D/J8 nach User-Prio.

Kern: **J5/#525** — `services/newsletter_service.py`: `erkennung()`
(gelernte Quellen → BUILTIN_SOURCES-Portale → konservative
Betreff-Hinweise), `extract_job_links()` KI-frei (Portal-URL-Regexes
StepStone/LinkedIn/XING/Indeed/Arbeitsagentur/freelance.de/JobLeads,
Anker-Titel mit `_ist_boilerplate`-Wortmengen-Filter, „Titel bei Firma"-
Split, Tracking-Param-Dedup), `verarbeite_newsletter()` → save_jobs mit
`source='newsletter:<label>'` + `_manual_entry` (Stellen kommen ohne
Beschreibung → #756-unbewertet → #622-Refetch → C23-Snapshot greifen
ineinander). Ollama NUR als Fallback bei leerer Ebene 0 (TaskKind
EXTRACT_NEWSLETTER_JOBS, Routing [LOCAL, MANUAL]). Upload-Pfad erkennt
Newsletter automatisch, uebernimmt und archiviert die Mail
(Response-Feld `newsletter`); gilt damit auch fuer Thunderbird-Add-on
und Watch-Folder (delegieren an api_upload_document). Lern-Mechanik:
`newsletter_quelle_markieren` speichert Domain+Betreff-Prefix in
`newsletter_sources`. Tests: `test_v18_beta4_newsletter.py` (12).

## Stand 2026-07-14 (v1.8.0-beta.3, Prerelease) — Thunderbird + ics

**Schema:** v50 (unveraendert). **MCP-Tools:** 187
(+`termine_ics_exportieren` in export_tools). **Prompts:** 25.

Kern: (1) **J2/#478** — Thunderbird-MailExtension
`plugins/thunderbird-pbp/` (manifest MV2, TB 115+): Kontextmenue
„An PBP senden" auf der Nachrichtenliste, Mehrfachauswahl = Thread
(J2.2), `messages.getRaw(id, {data_format:'File'})` mit byte-treuem
Binary-String-Fallback (Uint8Array.from charCodeAt — nie UTF-8-deuten),
POST an `/api/v1/ingest/email`, Options-Seite (URL+Key+Ping),
401/403-Fehlerbild stoppt Batch. Install: Ordner zippen → .xpi →
„aus Datei installieren" (unsigned ok in TB). Icons via Pillow
generiert. J2.3: Watch-Folder (beta.2) deckt die Alternative.
(2) **J4.1/#481** — ics-Export war seit #310 da, aber NICHT
RFC-5545-fest: Kern nach `services/ics_service.py` extrahiert
(ics_escape: Komma/Semikolon/Backslash/Newlines; ics_fold: 75-Oktett-
Folding UTF-8-sicher), Endpoint nutzt ihn, NEU MCP-Tool
`termine_ics_exportieren` (Export-Ordner, `newline=''` beim Schreiben
erhaelt CRLF). Plan-Wahrheit korrigiert: J4.1 war faelschlich ⬜.
#481 bleibt offen (J4.2 CalDAV / J4.3 Graph opportunistisch).
Tests: `test_v18_beta3_ics_thunderbird.py` (12, inkl. Vertragstest:
beide pbp-plugin.json bestehen validate_manifest; Add-on nutzt die
richtigen Endpunkte).

## Stand 2026-07-14 (v1.8.0-beta.2, Prerelease) — Ingest-API v1 + Snapshot

**Schema:** v50 (`plugins`-Tabelle + `jobs.description_snapshot`/
`snapshot_at`/`snapshot_source`, additiv). **MCP-Tools:** 186
(+`plugins_anzeigen` in `tools/komponenten.py`). **Prompts:** 25.

Kern: (1) **J1/#504** — `services/plugins.py`: Manifest-Validierung
(`pbp-plugin.json`, `ingest_api: "^1"`, Capabilities-Whitelist
ingest:email/ingest:job), Pairing erzeugt `pbp_<hex>`-Key (DB haelt NUR
sha256; Einmal-Anzeige in der UI), Widerruf = DELETE. REST:
`/api/plugins` + `/api/plugins/pair` + DELETE; Ingest-API
`/api/v1/ingest/ping|job|email` mit `X-PBP-API-Key`-Header (401/403),
job-Ingest laeuft durch stelle_hash+calculate_score+save_jobs
(`source='plugin:<name>'`, `_manual_entry`, #317-Dup-Check → 409,
Blacklist → 409), email-Ingest delegiert an `api_upload_document`
(volle Pipeline). save_jobs-URL-Guard laesst `plugin:`-Quellen ohne URL
zu. Referenz-Plugin `plugins/watch-folder/` (stdlib-only, README =
API-Doku). UI: „Gekoppelte Plugins" im Erweiterungen-Tab. Wiki-Seite
**Plugins** (40. Seite — Wiki-Guard zaehlt jetzt >= 40). API-v1-Freeze
mit Stable = Beta-Exit Punkt 2. (2) **C23/#687** —
`description_snapshot` unveraenderlich: save_jobs fuellt bei Anlage
(>= 50 Zeichen) und schleift Bestand durch REPLACE durch;
`set_description_snapshot_if_empty` (atomare WHERE-Klausel) an beiden
Refetch-Stellen; fit_analyse faellt bei weggebrochener Beschreibung auf
den Snapshot zurueck (`beschreibung_aus_snapshot`). (3) **B24/#688** —
Auto-Engine-Step `_run_snapshot_backfill` (DB-only, 500/Lauf, Setting
`auto_snapshot_backfill`). Tests: `test_v18_beta2_plugins.py` (14,
TestClient).

## Stand 2026-07-14 (v1.8.0-beta.1, Prerelease) — Komponenten + Auto-OCR

**Schema:** v49 (`components`-Tabelle, rein additiv). **MCP-Tools:** 185
(+`komponenten_status`/`komponente_installieren`/`komponente_pfad_setzen`
im neuen Modul `tools/komponenten.py` (#751 I10),
+`dokument_ocr_ausfuehren` (#750 E19)). **Prompts:** 25. Stable/`--latest`
bleibt v1.7.7 — Betas sind GitHub-Prereleases.

Kern: (1) **I10/#751** — `services/components.py`: Registry (Tesseract,
Apache-2.0, ~55 MB, UB-Mannheim-NSIS silent nach
`BewerbungsAssistent\\components\\`), Detection (PBP-Pfad → DB-Pfad →
PATH → bekannte Orte), Install als Background-Job (`start_install_job`,
REST `GET/POST/DELETE /api/components*`), manueller Pfad, deu-tessdata
automatisch (Fallback selbsttragender TESSDATA_PREFIX-Ordner inkl.
eng+osd). Settings-Tab **„Erweiterungen"** (SettingsPage,
`ErweiterungenTab`); Ollama nur mit-angezeigt (D2). Deinstaller entfernt
`components\\` mit. ZUSTIMMUNGS-PFLICHT: `komponente_installieren` ohne
`bestaetigt=True` liefert NUR das Angebot. (2) **E19/#750-T2** —
`services/ocr_service.py`: pypdfium2-Rendering (neue docs-Dependencies
pypdfium2+pillow; ersetzt toten #192-pdf2image-Pfad in
`dashboard._extract_document_text`, Rueckgabe jetzt 3-Tupel mit
`ocr_info`), tesseract-subprocess `--psm 1` (OSD) mit Fallback,
Provenienz-Header, Scan-Erkennung < 50 Zeichen, Seiten-Cap 15;
Upload-Response traegt `ocr`-Feld (durchgefuehrt/erforderlich+Angebot).
(3) **A21/#758** — PII-Altbestand bereinigt; `scripts/check_urls_645.py`
(reale Sichtungsliste) entfernt. Tests: `test_v18_beta0_komponenten.py`
(20, Netz+Binary gemockt); Real-Install-Verifikation ist Beta-Exit
Punkt 3.

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

8a. **Mehr-Defekt-Issues einzeln abhaken (seit 2026-08-18)** — bei Issues,
   die mehrere nummerierte Defekte oder zwei AK-Bloecke tragen, VOR dem
   Schliessen jeden Block einzeln gegen den Code pruefen. Hintergrund:
   #918 ("Zwei Metadaten-Fehler...") wurde geschlossen, obwohl nur
   Defekt 1 umgesetzt war — der Titel nannte beide, der Kommentar
   beschrieb nur einen. Faustregel: Issue-Titel mit "und"/"zwei"/
   "mehrere" oder AK-Listen mit Nummerierung sind Warnsignale.

8b. **Tag-Setzen nur mit sauberem Working Tree (seit 2026-08-18)** —
   `git checkout <release-branch>` VOR `git tag` kann an uncommitteten
   Dateien scheitern ("Aborting"); die Kette laeuft dann auf dem
   FALSCHEN Branch weiter und der Tag landet still auf dem falschen
   Commit. Deshalb: erst `git status --short` leer machen, nach dem
   Checkout `git branch --show-current` verifizieren, und nach dem
   Taggen `git log --oneline -1 <tag>` gegen den erwarteten Commit
   pruefen. Ein Tag OHNE Release laesst sich noch gefahrlos
   korrigieren (push :refs/tags/X + tag -d + neu setzen) — mit Release
   ist die Nummer verbrannt.
9. **Firmennamen-Sweep ueber GitHub** (seit 2026-07-23) — reale Firmen aus
   der Bewerbungshistorie duerfen NIRGENDS auf GitHub stehen: Issues (Body
   UND Kommentare), Release-Notes, Wiki, Commit-Messages. Vor JEDEM
   `gh issue create/comment/edit` und `gh release create` den Text durch
   `python scripts/scrub_pii.py --check` schicken — AUCH Tabellen und
   Beispiele aus der eigenen DB (genau so kamen am 23.07. acht reale
   Firmen in zwei Issues). Das gilt fuer ALLE Instanzen, auch die
   MCP-Chat-Seite. Am Session-Ende zusaetzlich alle seit der letzten
   Session neuen/geaenderten Issues gegenpruefen. Wird PII auf GH
   gefunden: Issue LOESCHEN (GraphQL `deleteIssue`), NICHT editieren —
   die Edit-History behaelt das Original. Dokumentierte Ausnahmen:
   Portale/Vermittler als Quellen-Feature (hays, ferchau, ...) und
   fiktive Firmen (Halbleiterwerk Nord GmbH). Hintergrund: #763 und #766
   enthielten am 23.07. die reale Stellen-Tabelle des Users und wurden
   geloescht — die Nummern sind verbrannt, die Inhalte stehen im
   Master-Plan (B27/C28) und im CHANGELOG.

   **Seit 2026-08-07 MECHANISCH abgesichert — die Regel allein hat
   dreimal versagt.** Nach ihrer Einfuehrung am 23.07. kamen am 31.07.
   und 06.08. drei weitere Issues mit realen Firmen dazu, eines davon
   mit Klarnamen, Mailadresse und zwei Telefonnummern eines Dritten
   (geloescht am 07.08., anonymisiert neu als #814/#815/#816). Eine
   Regel, an die man sich erinnern muss, ist keine Kontrolle. Jetzt:

   - **PreToolUse-Hook** (`.claude/settings.json` →
     `scripts/gh_pii_guard.py`): blockiert JEDEN `gh issue|pr|release
     create/comment/edit` mit PII, bevor er laeuft — prueft
     Inline-Argumente, `--body-file`-Inhalte UND Heredocs.
     **GRENZE: nur der Bash-Weg.** Der GitHub-MCP (Claude Desktop) laeuft
     daran vorbei — genau dort entstanden die drei Issues.
   - **`scripts/gh_pii_sweep.py`**: prueft den IST-Zustand ueber ALLE
     Issues, Kommentare und Releases, auch geschlossene. Deckt den
     MCP-Weg mit ab, gehoert in die Session-Abschluss-Runde.
   - **`FIKTIVE_FIRMEN`** in `scrub_pii.py`: der Pruefer schlug vorher bei
     genau den Platzhaltern an, die diese Regel vorschreibt. Neue
     Platzhalter dort eintragen.

   MERKE (warum dem Report niemand mehr glaubte): die Telefon-Erkennung
   matchte ueber ZEILENUMBRUECHE und las die Jahresspanne `2020-2024` als
   Rufnummer — 16 von 60 Treffern waren Fehlalarm. Ein Pruefer, der bei
   korrektem Ergebnis Alarm gibt, wird nach dem zweiten Mal ignoriert.
   Beim Haerten von Erkennungs-Regeln IMMER beide Richtungen testen.

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
`docs/internal/QA-Audit-beta90.md`. Das Wiki war auf beta.74 eingefroren (152
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
Am 2026-07-23 passierte es doch wieder: #763/#766 trugen die reale
Stellen-Tabelle des Users (8 Firmen) und mussten GELOESCHT werden —
DoD-Punkt 9 ist seitdem der Pflicht-Riegel.

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
8. **⛔ Tag erst NACH gruenem CI (HART, seit beta.0-Segfault 2026-07-14):**
   Release-Commit auf main pushen, den CI-Lauf ABWARTEN (`gh run watch`),
   und erst bei Erfolg Tag setzen + pushen + GH-Release erstellen.
   Hintergrund: v1.8.0-beta.0 wurde vor dem CI-Ergebnis getaggt; der
   Linux-Runner fand einen PDFium-Segfault (exit 139), den Windows lokal
   nicht zeigte — der Tag war gelocked, beta.1 musste nachgeschoben
   werden. Native Dependencies (pypdfium2, playwright, ...) verhalten
   sich plattformspezifisch; die lokale Windows-Suite reicht als
   Tag-Freigabe nicht.
9. **Erst nach OK** committen, taggen, pushen, GH-Release erstellen.

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
