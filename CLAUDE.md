# PBP — Claude-Code-Memory

Persoenliches Bewerbungs-Portal (PBP). MCP-Server (Python/FastMCP 3.x) +
React-Frontend + SQLite. **v1.7.63** ist Stable (`--latest`, 2026-09-09; nach dem Urteil filtern — das siebte und letzte Akzeptanzkriterium von #1007, und ein Issue mit sechs von sieben erfuellten Punkten ist nicht erledigt (DoD 8a). Der neue Filter faellt selbst unter die Lehre aus #1008: Vorgabe AUS, benannt, und er sagt wie viele Stellen er ausblendet). Davor **v1.7.62** war Stable (`--latest`, 2026-09-09; die Liste sagt jetzt, was sie verbirgt — ein Filter, den niemand gesetzt hat, verbarg 7 von 8 Stellen, und #993 hatte ihn zwei Versionen zuvor erst scharfgeschaltet (#1008). Details im Stand-Block unten). Davor **v1.7.61** war Stable (`--latest`, 2026-09-09; die Empfehlung kommt nicht mehr aus dem Score — der Score ist nur ein Indikator fuer die Suchbegriffe, das Urteil entsteht aus der Detailanalyse gegen das Profil (#1003, #1007). Der Stand-Block dazu wurde mit v1.7.63 nachgetragen). Davor **v1.7.60** war Stable (`--latest`, 2026-09-09; erzeugte Dokumente sind versandfertig — viermal `None` im Lebenslauf, und es war keine Regression, sondern zwei Werkzeuge (#1006). Details im Stand-Block unten). Davor **v1.7.59** war Stable (`--latest`, 2026-09-09; Ausgabe- und Vorlagen-Ordner einstellbar — der Zielordner stand an dreizehn Stellen, Vorlagen gab es gar nicht (#973 Teil 1). Details im Stand-Block unten). Davor **v1.7.58** war Stable (`--latest`, 2026-09-09; Ollama startet auf Wunsch mit PBP — Vorgabe AUS, eine Start-Logik fuer Knopf und Autostart (#1001). Details im Stand-Block unten). Davor **v1.7.57** war Stable (`--latest`, 2026-09-09; im Bewerbungs-Detail stand Schreiben vor Lesen, und der Prompt-Knopf speicherte nichts (#958). Details im Stand-Block unten). Davor **v1.7.56** war Stable (`--latest`, 2026-09-09; Score-Verteilung der beworbenen Stellen als eigene Kennzahl (#986). Details im Stand-Block unten). Davor **v1.7.55** war Stable (`--latest`, 2026-09-09; der Installer stoppte Prozesse noch per wmic — auf Win11 24H2 entfernt (#739). Details im Stand-Block unten). Davor **v1.7.54** war Stable (`--latest`, 2026-09-09; der Filtertrichter belegt jetzt, was er zaehlt — #813 vollstaendig abgeschlossen. Details im Stand-Block unten). Davor **v1.7.53** war Stable (`--latest`, 2026-09-09; der PII-Pruefer fand nur die wortgleiche Schreibweise — 39 Issues tragen einen Bestandsnamen. Details im Stand-Block unten). Davor **v1.7.52** war Stable (`--latest`, 2026-09-08; Reisewiderstand — nicht jeder Kilometer kostet gleich viel (#965 Befund 2). Details im Stand-Block unten). Davor **v1.7.51** war Stable (`--latest`, 2026-09-08; "liefert nichts" und "liefert nichts Passendes" waren dieselbe Zahl — und beide fuehrten zur Abschaltung (#995). Details im Stand-Block unten). Davor **v1.7.50** war Stable (`--latest`, 2026-09-08; ein `chrome`-Feld, das es nie gab, und eine Entfernung ohne Einheit (#993, #950). Details im Stand-Block unten). Davor **v1.7.49** war Stable (`--latest`, 2026-09-08; die Empfehlung hielt feste Schwellen gegen eine Skala ohne 100 — perfekte Passung ergab "Gap zu gross" (#999). Details im Stand-Block unten). Davor **v1.7.48** war Stable (`--latest`, 2026-09-08; das tausendste Issue — zwei Parameter von `jobsuche_starten` ohne jeden Leser (#1000). Details im Stand-Block unten). Davor **v1.7.47** war Stable (`--latest`, 2026-09-08; der DOCX-Import las keine Tabellen — ein Lebenslauf im Tabellenlayout ergab 26 Zeichen (#998). Details im Stand-Block unten). Davor **v1.7.46** war Stable (`--latest`, 2026-09-08; `profil_bearbeiten` meldete Erfolg fuer IDs, die es nicht gibt — der Rueckgabewert der DB-Ebene wurde an sieben Stellen verworfen (#997). Details im Stand-Block unten). Davor **v1.7.45** war Stable (`--latest`, 2026-09-08; "remote" schaltete die Ortspruefung ab — US-Stellen im DACH-Bestand (#996). Details im Stand-Block unten). Davor **v1.7.44** war Stable (`--latest`, 2026-09-08; Quellenpflege — eine abgeschaltete Quelle lebte, und die Abschaltung war eine Einbahnstrasse (#813). Details im Stand-Block unten). Davor **v1.7.43** war Stable (`--latest`, 2026-09-07; der LinkedIn-Weg im echten Browser nachgemessen — AK1 erfuellt, und LinkedIn sanitisiert `innerHTML` (#919). Details im Stand-Block unten). Davor **v1.7.42** war Stable (`--latest`, 2026-09-07; LinkedIn liefert wieder — der erprobte Voyager-Weg ist Werkzeug statt Notiz (#919). Details im Stand-Block unten). Davor **v1.7.41** war Stable (`--latest`, 2026-09-07; die Blacklist warf unsichtbar weg, und die Ausnahme wirkte nicht im Suchlauf (#992). Details im Stand-Block unten). Davor **v1.7.40** war Stable (`--latest`, 2026-09-07; das Werkzeug gab es, der Weg dorthin fehlte — erster Fund eines fremden Anwenders im Profil-Bereich (#994). Details im Stand-Block unten). Davor **v1.7.39** war Stable (`--latest`, 2026-09-07; Ungeprueftes wirkte wie Unauffaelliges — was nichts kostet, stand oben (#989). Details im Stand-Block unten). Davor **v1.7.38** war Stable (`--latest`, 2026-09-07; der Analyseplan schlug 962 Dokument-Zuordnungen vor statt 8 — zum fuenften Mal zwei Wege fuer dieselbe Frage (#991). Details im Stand-Block unten). Davor **v1.7.37** war Stable (`--latest`, 2026-09-07; eine Klammer hat den Installer abgebrochen — erster Bericht eines fremden Anwenders (#990). Details im Stand-Block unten). Davor **v1.7.36** war Stable (`--latest`, 2026-09-07; die Trefferliste stand auf dem Kopf — 86 von 86 Stellen zu hoch bewertet (#987), die Entfernung wirkte nicht (#988). Details im Stand-Block unten). Davor **v1.7.35** war Stable (`--latest`, 2026-09-07; das Dashboard gehoert dem Nutzer — Bereiche an/aus, sortierbar, einklappbar (#985), dazu drei Nachzuegler #833/#972/#975 und ein Asset-Fehler, der die ganze Gestaltung gekostet haette. Details im Stand-Block unten). Davor **v1.7.34** war Stable (`--latest`, 2026-09-07; Abschluss von Epic #978 — vier Releases an einem Tag. v1.7.31 die sechs Dashboard-Sub-Issues plus #980 (der Aufgaben-Tab speicherte "hinfaellig" still als "erledigt"), v1.7.32 #981 (der Stellen-Dialog bot einen Status an, den es nicht gibt), v1.7.33 #979 (Prompt-Katalog als einzige Quelle, waehlbarer Schnellzugriff), v1.7.34 zwei Layout-Fehler, die erst der erneuerte Screenshot zeigte. Details im Stand-Block unten). Davor **v1.7.30** war Stable (`--latest`, 2026-09-04; Kompetenzen aus dem Bestand #971 — Abschluss der Berufsfeld-Recherche. Vier von fuenf Issues erledigt, offen bleibt allein #968 als Nutzerentscheidung). Davor **v1.7.29** war Stable (`--latest`, 2026-09-04; Profil-Erkennung #970 — "Kita" enthielt "ki", eine Erzieherin galt als Tech-Seniorin. Sechs Berufsfelder ergaenzt). Davor **v1.7.28** war Stable (`--latest`, 2026-09-04; Berufsbezeichnungen #969 — derselbe Beruf unter anderem Namen erscheint wieder; dazu ein Nachtrag zu #949, dessen Feldname geraten statt nachgeschlagen war). Davor **v1.7.27** war Stable (`--latest`, 2026-09-02; Kaltstart-Fix #967 — ein frisches Profil fand strukturell nichts. Erster Schritt aus der Berufsfeld-Recherche, siehe Stand-Block). Davor **v1.7.26** war Stable (`--latest`, 2026-09-02; drei Defekte aus der Issue-Durchsicht: Anzeigenalter #949, ehrliche 0-Treffer-Meldung #813, Flaky-Test #767). Davor **v1.7.25** war Stable (`--latest`, 2026-09-02; Wartungsversion — der PII-Guard deckt jetzt auch den MCP-Weg ab, siehe DoD-Punkt 9). Davor **v1.7.24** war Stable (`--latest`, 2026-09-02; sieben Praxis-Befunde #960-#966, Details im Stand-Block unten). Davor **v1.7.19** war Stable (`--latest`, 2026-08-18; zwei totgeglaubte Quellen wiederbelebt — Freelance-Schiene und Engineering-Dienstleister, #925/#926). Davor **v1.7.18** war Stable (`--latest`, 2026-08-18; Nachzug #922/#918-Defekt-2 auf die Praxis-Welle v1.7.17 desselben Tages, Details im Stand-Block unten). Davor **v1.7.16** war Stable (`--latest`, 2026-08-14; erster 1.7er-Release MIT der Sichtbarkeits-Arbeit — bis v1.7.15 lag sie nur auf main. MERKE: Schaufenster-Arbeit ist erst beim Nutzer, wenn sie in der Stable-Linie ist) —
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

## Stand 2026-09-09 (v1.7.62 Stable) — Die Liste sagt, was sie verbirgt

**#1008**, Nutzer-Report mit Screenshot: Sidebar 8, Liste 1, F5 hilft
nicht. Drei Befunde, acht Akzeptanzkriterien, plus ein vierter Fund beim
Nachsehen. **Tests: 3380 / 3448.**

MERKE-Punkte:

(1) **Mein eigener Fix aus v1.7.50 hat den gemeldeten Schaden erst
angerichtet.** #993 fand, dass `JobsPage` `chrome.search_criteria.
min_score_schwelle` las — einen Schluessel, den es nicht gibt. Der
Zugriff wurde repariert. Nicht gestellt wurde die Frage, ob dieser Wert
den Filter ueberhaupt speisen darf: `min_score_schwelle` ist die
Schwelle, ab der eine Stelle beim Suchlauf **gespeichert** wird ("wirkt
waehrend der Suche, nicht in der Liste"), der Anzeige-Filter heisst
`schwellenwert/auto_ignore`. Damit wurde aus einem seit beta.27
schlafenden Filter ein wirksamer, und sieben von acht Stellen
verschwanden — bei einem Nutzer, der nie einen Filter gesetzt hat.
**Einen toten Draht anzuschliessen ist nur dann eine Reparatur, wenn
vorher geklaert ist, was an seinem Ende haengt.** Der Alt-Test aus #993
forderte genau den falschen Zugriff und musste mitkorrigiert werden.

(2) **Das Feld ohne Leser war die Folge, nicht die Ursache.** Nach der
Korrektur las niemand mehr `search_criteria` aus der Workspace-Antwort —
also ist es weg. Dasselbe fuer `get_hochschulabschluss_malus`: sie las
einen Regler, dessen Pruefung v1.7.35 (#972) entfernt hat, und ihre zwei
Aufrufer legten das Ergebnis in `criteria` ab, wo es niemand mehr las.
Dritter Fall nach #993 und #1000.

(3) **Der tote Regler stand in JEDER frischen Datenbank.** Der Melder
fand `hochschulabschluss/fehlt` in seinem Bestand und hielt es fuer eine
Karteileiche. Es war eine Vorgabe. Haette ich nur den Bestand gemeldet,
haette die neue Warnung jeden Anwender beim ersten Start getroffen —
**ein Pruefer, der bei korrektem Zustand Alarm gibt, wird nach dem
zweiten Mal ignoriert** (#929). Also erst die Vorgabe entfernen und die
Altzeilen abraeumen, DANN melden. Beide Richtungen im Test.

(4) **Ein Feldname, drei Bedeutungen.** `score` war in der MCP-Liste und
im Bericht der Wert MIT den Scoring-Reglern, in `GET /api/jobs` — also
in der Liste, die der Mensch ansieht — der rohe gespeicherte. Das
Nadeloehr `_mit_scoring_reglern` gab es seit #944 bereits; der
REST-Weg lief nur nicht hindurch. **Ein Nadeloehr nuetzt nichts, solange
ein Aufrufer daran vorbeigeht** — deshalb ist der Guard ein Aufruf und
kein Fundstellen-Abgleich.

(5) **Zwei Zahlen gleichzumachen war die falsche Loesung, und das war
die interessanteste Entscheidung.** Die Fit-Analyse haette die Regler
mitrechnen koennen — dann waere alles eine Zahl. Aber `total_score` wird
gegen `total_score_max` gehalten, und in diesem Hoechstwert kommen die
Regler nicht vor: eine Stelle, die alles trifft, muss exakt 100 %
ergeben (#999). Die Angleichung haette also eine gepruefte Eigenschaft
gebrochen, um eine Anzeige zu gluetten. Die Zahlen werden deshalb
**benannt statt gleichgemacht** — eine Luecke gehoert erklaert, nicht
zugerechnet (#989).

(6) **Der Gesamtwert und seine Aufteilung stammten aus verschiedenen
Laeufen.** `save_jobs` behaelt beim erneuten Speichern den hoeheren
alten `score` (gewolltes Verhalten seit jeher) und schrieb
`fachscore`/`rahmenscore` bedingungslos neu. Nachgestellt: erst voller
Anzeigentext, dann derselbe Hash mit duennem — Ergebnis `score 10.5` bei
`fachscore 0.0`, exakt der gemeldete Widerspruch. **Zwei Werte, die
einander erklaeren sollen, muessen zusammen geschrieben werden oder gar
nicht.** Vom eigenen Test kam der Zusatzfall: ein Metadaten-Update ohne
Bewertung haette die Aufteilung auf NULL gesetzt, also einen Gesamtwert
ohne jede Herkunft hinterlassen.

(7) **Der Farbklassen-Guard aus #964 hat zum dritten Mal gegriffen** —
mein Hinweisbalken trug `bg-amber-400/20`. `amber` ist ein FLACHES
Projekt-Token; die Abstufung loest ins Leere auf, ohne Fehler und ohne
fehlende Regel. Und der Kommentar-Helfer war diesmal von vornherein
eingeplant: der Guard, der `min_score_schwelle` in `JobsPage.jsx`
verbietet, haette sonst an der Begruendung angeschlagen, warum es dort
nicht mehr steht (#993, #998, v1.7.31 MERKE 6).

(8) **Der eigene Fund im MCP wiegt am schwersten, und er kam nur zustande,
weil du "der MCP ist eines der Kernkomponenten von PBP" gesagt hast.**
`stellen_anzeigen` verwarf Stellen unter der Schwelle still (`continue`),
zaehlte sie nur ins Log und antwortete *"Keine Stellen gefunden. Starte
eine Jobsuche"* — waehrend `pbp_diagnose` dieselben Stellen als aktiv
meldete. **PBP widersprach sich in sich selbst, und der genannte
naechste Schritt war der falsche:** eine Suche bringt nichts, wenn die
Treffer laengst da sind. Das ist #813 woertlich, nur an der Trefferliste
statt am Suchlauf. Der genannte Rueckweg wird gegen die echte Signatur
geprueft (#1000/#958), damit die Anleitung nicht ins Leere fuehrt.

(9) **Der Kommentar des Melders hat meine erste Diagnose widerlegt, und
das gehoert gesagt.** Ich hatte den Schwellenfilter (`auto_ignore`) als
Ursache im Verdacht; der stand bei ihm auf 0, also aus. Der MCP-Befund
bleibt ein echter Defekt — er war nur nicht die Ursache DIESES Symptoms.
**Ein Fund, der beim Suchen nach etwas anderem entsteht, ist kein
Beleg fuer die urspruengliche These.**

## Stand 2026-09-09 (v1.7.61 Stable) — Die Empfehlung kommt nicht aus den Punkten

**#1003 + #1007**, nachgetragen mit v1.7.63 (beim Release selbst blieb
der Stand-Block aus — die Lehren gehoeren trotzdem hierher).
Abgeschlossen mit v1.7.63, das #1007s siebtes Akzeptanzkriterium
nachzog.

MERKE-Punkte:

(1) **Die Nutzer-Korrektur hat meinen eigenen Loesungsvorschlag
verworfen, und sie hatte recht.** Das Issue fragte nach einem besseren
MASSSTAB (gegen den bisher besten Wert, gegen die Verteilung des
Bestands); ich hatte die Verteilung selbst vorgeschlagen. Der Satz, der
alles umgeworfen hat: *"Ob es eine Empfehlung gibt, hat nichts mit den
Punkten, nichts mit dem Score zu tun — das ist nur ein Indikator fuer
die Suchbegriffe."* Ein besserer Maszstab haette denselben Fehler nur
sauberer gemacht. **Wenn eine Zahl die falsche Frage beantwortet, hilft
keine bessere Skala.**

(2) **`services/passung.py` rechnet deshalb GAR NICHT.** Es entscheidet
nach Sachverhalten: k.o.-Kriterium schlaegt alles, sonst gilt eine
gelesene Detailanalyse, sonst `NICHT_BEURTEILBAR`. Die Schwellen
`>= 0.75` / `>= 0.50` sind ersatzlos entfallen. Der Score misst, was in
der ANZEIGE steht; der Verdict behauptete, ob ein MENSCH auf die Stelle
passt — der Lebenslauf ging in die Zahl nie ein.

(3) **`NICHT_BEURTEILBAR` ist vom Notausgang zum Normalfall geworden.**
In #999 war die vierte Kategorie ein Behelf fuer einen fehlenden
Hoechstwert. Jetzt sagt sie, was sie sagt: niemand hat diese Stelle
gegen dein Profil gelesen. Das ist etwas anderes als "passt nicht" —
genau die Verwechslung, die #989 abgeschafft hat.

(4) **Die Herkunft ist Pflichtfeld, kein Zierrat.** `grundlage` mit
`detailanalyse` / `ko_kriterium` / `keine_grundlage`: ein maschinelles
und ein gelesenes Urteil duerfen in der Liste nicht gleich aussehen.

(5) **Ein veraltetes Urteil wird gekennzeichnet, nicht verworfen.** Der
Profil-Fingerabdruck ist bewusst grob (Kompetenzen/Stationen/Stand)
statt ein Inhalts-Hash: ein Hinweis, der bei jeder Kleinigkeit
"veraltet" meldet, wird ignoriert (#929). Und ein stilles Wegwerfen
verloere die teuerste Auskunft im System.

(6) **Ein Backtest war nicht moeglich, und der Grund gehoert zur
Sache.** Das dritte Akzeptanzkriterium von #1003 verlangte zu messen,
wie viele Stellen die Kategorie wechseln. Der Verdict wurde vorher
**nirgends gespeichert** — er entstand bei jedem Aufruf neu. Es gibt
also keinen historischen Stand zum Vergleich; genau deshalb war #1007
ueberhaupt noetig. Die Antwort ist strukturell: alles ausser echten
k.o.-Faellen ist jetzt `NICHT_BEURTEILBAR`.

(7) **Offen geblieben und beim Abschluss beziffert: die
Synonym-Blaehung.** Der zweite Befund von #1003 betrifft den Score
selbst. Gemessen: drei Schreibweisen desselben Sachverhalts in der
MUSS-Liste ergeben **21,0 statt 7,0** Punkte — Faktor 3 fuer eine
Umformulierung, und das verschiebt die SORTIERUNG. Zur Abgrenzung
ebenfalls gemessen: blosse Wiederholung blaeht NICHT (20x = 1x). Als
**#1012** erfasst, damit er nicht mit dem geschlossenen Issue
verschwindet.

## Stand 2026-09-09 (v1.7.60 Stable) — Versandfertig statt nachformatieren

**#1006**, Nutzer-Report mit belegtem Lauf. **Tests: 3338 / 3404.**
MCP-Tools 216 / 229.

MERKE-Punkte:

(1) **`edu.get("degree", "")` ist KEIN Vorgabewert.** `dict.get` liefert
ihn nur, wenn der SCHLUESSEL FEHLT. Steht die Spalte auf NULL, ist der
Schluessel da und der Wert `None` — und der f-String schreibt `"None"`
ins Dokument. Genau so kamen die gemeldeten vier `None` in einen
Lebenslauf, und zwar aus BEIDEN Erzeugern. **Der Ausdruck sieht wie eine
Zusicherung aus und ist eine Vermutung** — dieselbe Bauform wie das
`chrome`-Feld aus #993, nur eine Ebene tiefer.

(2) **Es war keine Regression, und das war der eigentliche Ertrag der
Recherche.** Das Issue vermutete eine Verschlechterung seit Mai und
verlangte den Commit. Am Verlauf geprueft: `add_table` kommt im Export
der GESAMTEN Historie nicht vor (die Treffer stammen aus dem
DOCX-IMPORT, #998), und die Fusszeile sitzt seit v0.32.0 im
ATS-Erzeuger. Das Mai-Dokument stammt aus
`lebenslauf_angepasst_exportieren`, das September-Dokument aus
`lebenslauf_exportieren`. **Zwei Werkzeuge, nicht ein
verschlechtertes.** Haette ich die Vermutung uebernommen, waere ich nach
einem Commit gefahndet, den es nicht gibt — und haette am Ende die
falsche Fassung "wiederhergestellt". Als Test festgehalten.

(3) **Der eigene Pruefer hat den eigenen Code erwischt.** Regel 2 (keine
Gedankenstriche) schlug am Bis-Strich in `zeitraum()` an — der ist dort
typografisch richtig. Ein Pruefer, der bei korrektem Ergebnis Alarm
gibt, wird nach dem zweiten Mal ignoriert (#929). Ausgenommen, beide
Richtungen im Test. **Ein Guard, der seinen Autor am selben Tag stoppt,
hat sich bezahlt gemacht** — zum zweiten Mal nach dem #990-Guard.

(4) **Zwei Grenzen, die bewusst nicht ueberschritten werden.** Prosa
wird nicht umgeschrieben (aus "Er verfuegt ueber" wird maschinell kein
guter Satz — Regel 8 wird GEMELDET), und ein fehlender Monat wird nicht
erfunden. `01/2005` zu schreiben, weil das Format MM/JJJJ verlangt,
waere eine geratene Angabe in einem Bewerbungsdokument. **Eine Luecke
gehoert benannt, nicht gefuellt** (#989 in der Textausgabe).

(5) **Die Umlaut-Liste hatte eine Luecke, die der Pruefer fand.** Die
*verfuegen*-Familie stand nicht in der kuratierten Liste aus #742 —
in fast jedem Lebenslauf. Der Pruefer meldet unbekannte
ae/oe/ue-Woerter jetzt als WEICHEN Befund: eine Positivliste kann nur
finden, was in ihr steht, und "Poesie" oder "Duell" sind keine Umlaute.
Die Liste ist dabei ein Dienst geworden (`services/umlaute.py`), weil
sie einen zweiten Aufrufer bekommen hat.

(6) **Geprueft wird am ERGEBNIS, nicht am Quelltext.** Das Referenz-
Profil aus dem Bericht (NULL-Spalten, unsortierte Stationen,
Skill-Fragmente, Jahr ohne Monat) erzeugt im Test ein echtes DOCX, und
die Regeln laufen dagegen. Ein Erzeuger, der sie umgeht, faellt sonst
nicht auf — DoD 8c fuer Ausgaben statt fuer Guards.

## Stand 2026-09-09 (v1.7.59 Stable) — Dein Ordner, dein Layout

**#973 Teil 1**, Nutzerwunsch vom 04.09. und noch einmal am 09.09.
**Tests: 3290 / 3356.** MCP-Tools 215 / 228.

MERKE-Punkte:

(1) **Der Zielordner stand an DREIZEHN Stellen einzeln im Code**
(`get_data_dir() / "export"`, in `export_tools.py`, `dashboard.py` und
`dokumente.py`). Kein Nadeloehr — also die Bauform, aus der #963, #991
und #992 entstanden sind, nur bevor sie auseinanderlaufen konnte. Neu
`services/ablage.py`. **Der Guard zaehlt die Fundstellen nicht ab,
sondern verbietet die Bauform** — eine Zaehlung haette die vierzehnte
durchgelassen.

(2) **Den Vorlagen-Ordner gab es gar nicht — und das war die
eigentliche Ueberraschung.** Die vier DOCX-Erzeuger starten mit einem
LEEREN `Document()`, das Layout steht als Code in `export.py`, und die
Dokumenttypen `lebenslauf_vorlage`/`anschreiben_vorlage` sind blosse
Etiketten ohne Leser. Einen Pfad einzufuehren, den niemand liest, waere
#1000/#988 gewesen. **Ein Pfad ohne Leser ist keine Einstellung,
sondern eine Behauptung** — deshalb wird die Vorlage wirklich als
Grundlage geoeffnet (Rumpf leeren, Stile/Raender/Kopf-/Fusszeilen
behalten), und der Test prueft die SCHRIFT IM FERTIGEN DOKUMENT, nicht
den gespeicherten Wert.

(3) **Mit Vorlage darf Calibri nicht mehr darueber geschrieben
werden.** `generate_cv_docx` setzte `Normal` hart auf Calibri 10,
`_setup_ats_styles` zusaetzlich Heading 1 und 3. Waere das geblieben,
haette die Vorlage nichts bewirkt ausser Arbeit — der Regler haette
einen Draht gehabt und trotzdem nichts getan. Die Ueberschreibung
laeuft jetzt nur noch ohne Vorlage.

(4) **Ein ungueltiger Pfad wird ABGEWIESEN, nicht gespeichert, und PBP
legt den Ordner NICHT an.** Beides bewusst: ein Tippfehler wuerde sonst
still zu einem neuen Ordner, und die Unterlagen laegen ab dann dort.
Dieselbe Entscheidung wie bei den Reisewiderstands-Regeln (#965).

(5) **Der verschwundene Ordner ist ein BENANNTER Sonderfall.** Externe
Platten und Netzlaufwerke sind mal weg. Drei Dinge muessen dann
gleichzeitig gelten: kein Absturz, die Datei geht trotzdem irgendwohin,
und PBP sagt wohin. **Eine stille Umleitung waere schlimmer als ein
Fehler** — man sucht die Datei sonst an einer Stelle, an der sie nicht
liegt. Die Einstellung bleibt dabei stehen.

(6) **Der Download im Dashboard nimmt dieselbe Vorlage wie der Weg
ueber Claude.** Zwei Layouts fuer dasselbe Dokument, je nach Klick,
waere #963/#991 im Layout gewesen. Ein Test haelt beide Wege fest.

(7) **Cherry-Pick: der Konflikt wollte wieder ein Beta-Werkzeug auf die
Stable-Linie holen** (`termine_ics_exportieren`, J4.1/#481). Genau der
Fall aus v1.7.47 MERKE (5) — diesmal beim Aufloesen erkannt, weil der
Konfliktblock groesser war als die eigene Aenderung.

(8) **Bewusst nur Teil 1.** Index ueber den Ordner, Suche darin und
Zuordnungsvorschlaege (AK 4-8) sind eine eigene Arbeit; #973 bleibt
offen, E25 steht auf 🟨. Ein halb erledigtes Issue als erledigt zu
fuehren ist die Falle aus DoD 8a.

(9) **Waehrend des Releases kam #1006 herein** — versandfertige
Dokumente statt Nachformatieren, mit belegten Inhaltsfehlern (`None`
im Text, falsche Sortierung, ungefilterte Skill-Liste). Der
Pre-Release-Issue-Check hat es gefangen. Geprueft und BEWUSST nicht
zurueckgehalten: die Vorlage aus v1.7.59 loest das Layout, die
gemeldeten Fehler sitzen im INHALT und braeuchten dieselbe Arbeit auch
mit der schoensten Vorlage. Als Kommentar an #1006 abgegrenzt, statt
den Eindruck zu erzeugen, es sei erledigt.

## Stand 2026-09-09 (v1.7.58 Stable) — Ollama startet mit, wenn du willst

**#1001**, Nutzerwunsch vom selben Tag. Den Knopf "Ollama starten" gibt
es seit beta.60; was fehlte, war der Weg OHNE Knopfdruck.
**Tests: 3261 / 3327.** MCP-Tools 214 / 227.

MERKE-Punkte:

(1) **Die Vorgabe ist AUS, und das ist die eigentliche Entscheidung.**
Einen fremden Prozess ungefragt zu starten ist eine Nebenwirkung, die
niemand bestellt hat. Wer nichts einstellt, merkt von dieser Version
nichts — das ist bei einer Funktion, die etwas AUSSERHALB von PBP
anfasst, die einzige vertretbare Voreinstellung.

(2) **Eine Start-Logik, drei Aufrufer** — bewusst so gebaut, nicht
hinterher zusammengelegt. `services/ollama_start.py` wird vom Knopf
(`POST /api/llm/start`), vom MCP-Startweg (`server.py`) und vom
Dashboard-Startweg (`start_dashboard`) gerufen. Zwei Fassungen von
Binary-Suche und Detach-Flags waeren mit Sicherheit auseinandergelaufen;
das ist das Muster aus #963/#991/#992 zum achten Mal. Der Guard zaehlt
keine Fundstellen ab, sondern prueft, dass der Endpunkt **keine eigene
Fassung mehr haelt**.

(3) **Der PATH genuegt nicht.** Startet PBP als MCP-Server, erbt es die
Umgebung von Claude Desktop — nicht die der Anmelde-Shell. Der alte
Endpunkt rief `Popen(["ollama", "serve"])`; ein `which`-Fehlschlag haette
dort "nicht installiert" gemeldet, obwohl Ollama danebensteht. Das ist
die Verwechslung von "nicht gefunden" mit "nicht vorhanden" (#989), nur
im Dateisystem. Jetzt erst `which`, dann die Orte, an die Ollamas eigener
Installer schreibt.

(4) **Vom eigenen Test gefunden, im eigenen neuen Code.** Die erste
Fassung von `PUT /api/llm/autostart` kippte einen unsinnigen String still
auf `false` und meldete Erfolg — der Nutzer haette "gespeichert" gelesen
und einen abgeschalteten Autostart bekommen. Das ist #980 in neuer
Gestalt (ein Fallback, der eine ANDERE Bedeutung speichert). **Ein Test,
der Unsinn hineingibt, ist mehr wert als drei, die den Normalfall
bestaetigen.**

(5) **Ein Alt-Test unterstellte den PATH.**
`test_llm_start_spawns_subprocess` aus beta.60 erwartete woertlich
`["ollama", "serve"]` — und haette auf einem Runner OHNE Ollama nach
dieser Aenderung mit 404 versagt, ohne dass jemand den Grund sieht. Die
Annahme steht jetzt als Monkeypatch da statt als Unterstellung (die Lehre
aus #999): geprueft wird, DASS `serve` an der gefundenen Binary gespawnt
wird, nicht wie die Binary heisst.

(6) **Der Autostart greift nur bei `user_state == "active"`** — dieselbe
Bedingung, die der Warmup-Loop aus #638 schon kennt. Wer ihn trotzdem
setzt, bekommt die Begruendung zurueck. Eine Einstellung, die
stillschweigend nichts tut, waere #988.

(7) **Master-Plan-Luecke beim Nachtragen gefunden.** Beim Setzen von G35
auf ✅ fiel auf, dass **#739 und #986 gar keinen Plan-Eintrag hatten** —
zwei Releases desselben Tages ohne Master-Plan-First. Als I13 und D44
nachgetragen, mit dem Vermerk, dass sie nachgetragen sind. Die Regel
sieht genau das vor: im naechsten Commit nachholen.

## Stand 2026-09-09 (v1.7.57 Stable) — Erst lesen, dann schreiben

**#958**, gemeldet am 25.08. Im Bewerbungs-Detail zeigte der Kasten
"Firmen-Recherche" zuerst ein leeres, sechszeiliges Eingabefeld; die
gespeicherten Recherchen standen darunter. **Tests: 3234 / 3300.**

MERKE-Punkte:

(1) **Die Reihenfolge auf dem Bildschirm ist eine Aussage darueber, was
der Normalfall ist.** Beide Kaesten waren da — nur in der falschen
Ordnung. Wer nachsehen wollte, sah als Erstes eine leere Flaeche und
schloss daraus, es sei nichts gespeichert. Ein Test auf "beide
vorhanden" haette den Fehler nicht gefunden; er prueft deshalb die
POSITION im Quelltext.

(2) **Der teurere Befund war der zweite, und er war unsichtbar.** Der
Knopf "Mit Claude aktualisieren" kopierte `/firmen_recherche firma="..."`
**ohne `bewerbung_id`** — und ohne die speichert das Werkzeug seit #674
nichts. Claude recherchierte, gab die Antwort im Chat aus, und in PBP kam
nichts an. **Ein Knopf, der etwas anderes tut als sein Label sagt, ist
teurer als ein fehlender Knopf** — man verlaesst sich darauf und merkt
den Verlust nicht. Das Label heisst jetzt "Prompt kopieren".

(3) **Der Kopier-Knopf gehoert NICHT in das `<summary>`.** Dort haette
jeder Klick auf ihn zusaetzlich das Aufklappen ausgeloest — eine
Nebenwirkung, die niemand gemeint hat. Ein Test haelt das fest, weil es
beim naechsten Umbau sofort wieder passieren wuerde.

(4) **Der Guard prueft den Parameternamen gegen die echte Signatur.**
`inspect.signature(firmen_recherche)` statt einer Liste im Test — ein
Tippfehler im Prompt faellt sonst erst auf, wenn wieder nichts ankommt.
Dasselbe Argument wie beim Prompt-Guard aus #1000.

(5) **Nebenbefund mit Zahl: der SCHREIB-Kasten haengt weiter an
`entry?.job`.** Der Lese-Kasten haengt inzwischen an `application` und
erscheint immer. Zusammen mit der Messung aus #986 — **44 von 99
Bewerbungen haben keine verknuepfte Stelle** — heisst das: fuer fast die
Haelfte des Bestands erscheint das Eingabefeld samt Prompt-Knopf gar
nicht. Noetig ist die Bedingung nicht (gespeichert wird an der
Bewerbung); am Job haengt nur der Anfangswert des Entwurfs. Als
Kommentar an #956 gehaengt, wo die Zusammenfuehrung liegt.

(6) **Master-Plan-First nachgeholt.** Der Code lag auf main, bevor es
einen Plan-Eintrag gab (G35). Das ist ein Verstoss gegen die harte Regel
und wurde vor dem Release korrigiert — die Regel sieht genau das vor:
im naechsten Commit nachholen.

## Stand 2026-09-09 (v1.7.56 Stable) — Bei welchem Score bewirbst du dich

**#986.** Der Nutzer fragte: "Wie hoch war der Score bei den Stellen, auf
die ich mich beworben habe?" Die Zahlen existierten nur als Nebenprodukt
der Schwellenkalibrierung. **Tests: 3225 / 3291.**

MERKE-Punkte:

(1) **Die Kennzahl entsteht an EINER Stelle und hat zwei Aufrufer.**
`get_statistics` (Dashboard) und `statistiken_abrufen` (MCP) rufen
denselben Dienst — zwei Fassungen derselben Kennzahl waeren das Muster
aus #963/#976/#991 gewesen. Ein Test haelt beide Aufrufer fest.

(2) **Score 0 zaehlt NICHT in Mittel und Median.** Er heisst "kein
MUSS-Keyword getroffen": die Stelle wurde nicht schlecht bewertet,
sondern gar nicht beurteilt. Ihn einzurechnen waere der stille Nulltarif
aus #989, nur in der Statistik. Die Zahlen weichen dadurch bewusst vom
Backtest ab (Median 34 statt 30,5) — **das ist die Umsetzung eines
Akzeptanzkriteriums, kein Rechenfehler.**

(3) **Beim Messen kam der eigentliche Befund heraus: 44 von 99
Bewerbungen haben gar keine verknuepfte Stelle.** Sie tragen deshalb
keinen Score und fehlen in JEDER score-basierten Auswertung, auch im
Backtest. Die Verteilung beruht also auf gut der Haelfte des Bestands —
und genau deshalb steht die Zahl jetzt in der Kennzahl, statt still zu
fehlen.

(4) **In die dokumentierte Hash-Falle gelaufen.**
`applications.job_hash` traegt den oeffentlichen Hash, `jobs.hash` den
profil-praefixierten. Mein rohes `WHERE hash=?` fand **0 von 99** —
gemessen, nicht vermutet. CLAUDE.md warnt genau davor unter "Kritische
DB-Helfer". **Eine Regel, die man kennt, schuetzt nicht davor, sie beim
Schreiben zu vergessen — die Messung schon.**

(5) **Der Farbklassen-Guard aus #964 hat wieder gegriffen.** Mein
Balken trug `bg-surface`, ein Token, das es nicht gibt; Tailwind erzeugt
dafuer keine Regel UND keinen Fehler. Zweiter Treffer dieses Guards seit
seiner Einfuehrung.

## Stand 2026-09-09 (v1.7.55 Stable) — Der Installer hielt an einem entfernten Werkzeug fest

**#739**, offen seit dem 18.06.2026, beim Durchgehen der offenen
Meldungen erledigt. **Tests: 3213 / 3279.**

MERKE-Punkte:

(1) **Der Deinstaller wurde umgestellt, der Installer nicht.** Genau
dieselbe `wmic`-Schleife stand dort weiter — an zwei Stellen. Auf
Windows 11 24H2 ist das Werkzeug entfernt: die Schleife findet nichts,
laufende Prozesse laufen weiter, das Kopieren trifft auf gesperrte
Dateien. **Es faellt nur beim UPDATE auf, nicht bei der
Erstinstallation** — deshalb blieb es ein Jahr unbemerkt. Zwei Fassungen
derselben Aufgabe, und nur eine wurde repariert: dasselbe Muster wie
#963 und #991, hier in Batch-Dateien.

(2) **Der #990-Guard hat meinen ersten Entwurf sofort abgewiesen.** Ich
hatte `for /f` mit einem escapten Rohr gebaut, um die Zahl der
beendeten Prozesse zu melden — genau die Falle, die am 07.09. gemessen
wurde (`^|` kommt in der Subshell nicht als Pipe an). Die jetzige
Fassung verzichtet auf die Zahl und nimmt die im Deinstaller erprobte
Form. **Ein Guard, der zwei Tage nach seiner Einfuehrung den eigenen
Autor stoppt, hat sich bezahlt gemacht.**

(3) **Am laufenden System gegengeprueft.** Der PowerShell-Ausdruck
findet die tatsaechlich laufenden PBP-Prozesse — gezaehlt, nicht
beendet. Bei Installer-Aenderungen ist das die einzige ehrliche Probe;
ein Test gegen den Dateiinhalt sagt nichts darueber, ob das Kommando
laeuft.

(4) **Neuer Guard: keine `.bat` ruft `wmic` mehr auf**, Kommentare
ausgenommen — die duerfen erklaeren, warum es weg ist. Dazu die
Forderung, dass Installer und Deinstaller dieselbe Form benutzen.

## Stand 2026-09-09 (v1.7.54 Stable) — Der Trichter belegt, was er zaehlt

**#813 vollstaendig abgeschlossen** — das aelteste grosse Issue der
Quellen- und Filter-Reihe, offen seit dem 06.08.2026. **Tests:
3211 / 3277.**

MERKE-Punkte:

(1) **Eine Zahl ist kein Beleg.** Der Trichter aus #940 sagt "37 unter
der Schwelle" und laesst offen, ob die Schwelle zu hoch steht. Neu sind
die knapp Gescheiterten als Stichprobe (mit den fehlenden Punkten) und
die ausloesenden Ausschluss-Begriffe mit Haeufigkeit. **Ein einzelnes zu
breites Wort ist im Trichter unsichtbar und steht in der Ausloeserliste
oben.**

(2) **Der Beleg muss VOR dem Filtern entstehen** — danach sind die
Stellen weg, und der Beleg waere leer, ohne dass es auffiele. Ein Test
prueft die Reihenfolge im Quelltext.

(3) **"Knapp gescheitert" gilt nur mit fachlichem Anker.** Eine Stelle
ohne MUSS-Treffer ist nicht knapp, sondern nicht gemeint (#940). Sie
mitzuzaehlen haette die Stichprobe mit Rauschen gefuellt — dieselbe
Ueberlegung wie bei #966 ("schwach" war die falsche Kategorie).

(4) **Beim Skript-Patch faellt eine Variable in den falschen Zweig.**
`_knapp`/`_ausloeser` entstanden nur im `else`, gelesen wurden sie
danach immer — im Kaltstart ohne MUSS-Liste waere das ein NameError
gewesen. Gefunden vor dem Commit, weil ich den Zweig gegengelesen habe;
die gezielten Tests haetten ihn nicht getroffen.

(5) **Rueckblick auf die Wirkung dieses Issues.** Der Satz "389
Rohtreffer, 387 am Filter verworfen, gemeldet wurde: alle 2 waren schon
bekannt" beschreibt ein Muster, das danach an fuenf weiteren Stellen
auftauchte: **eine fehlende Unterscheidung wirkt wie eine negative
Auskunft.** Daraus wurden #989, #995, #996 und #999.

## Stand 2026-09-09 (v1.7.53 Stable) — Der Pruefer suchte die falsche Zeichenkette

**Kein gemeldetes Issue, sondern ein Fund BEI der Arbeit an #956/#957.**
Beide Issues nennen eine Firma aus dem echten Bewerbungsbestand — und
`issue_text_pruefen`, das genau das verhindern soll, meldete "sauber".
**Tests: 3201 / 3267.**

MERKE-Punkte:

(1) **Ein Falsch-negativ in einem Schutzwerkzeug, zum zweiten Mal.**
Das ist woertlich die Lehre aus #929, und diesmal traf sie das
Werkzeug, das die gepflegte Namensliste im Repo ABLOESEN sollte (#946).
Die Umkehr "Bestand statt Liste" war richtig — sie hat nur an der
falschen Zeichenkette gesucht: `re.escape(name)` verlangt die
VOLLSTAENDIGE gespeicherte Fassung. Steht eine Firma als "X (Y)" in der
DB, fand der Pruefer weder "X" noch "Y". **Und genau die kurze Form
schreibt ein Mensch in einen Fehlerbericht.**

(2) **Gefunden nur, weil ich einem Verdacht nachgegangen bin.** Der
Pruefer sagte "sauber"; ich habe die Bewerbung trotzdem nachgeschlagen,
weil ein Firmenname im Issue stand. **Ein Werkzeug, das Entwarnung
gibt, beendet die Pruefung — deshalb muss man bei Schutzwerkzeugen die
Entwarnung selbst gelegentlich pruefen**, sonst merkt man den
Ausfall nie.

(3) **Die Gegenrichtung hat den Entwurf zweimal korrigiert.** Erste
Fassung nahm auch den KLAMMERINHALT als Suchbegriff. Gemessen am echten
Bestand ueber alle 400 Issues steht dort weit oefter eine ANMERKUNG als
ein zweiter Firmenname — "(Vermittler)", "(Beratung)",
"(Personalberatung)", "(SAP PLM)", "(Bremen)". Jede davon erzeugte
Fehlalarme ueber Dutzende Issues: vier Fehlalarm-Quellen fuer einen
selten gebrauchten Zusatznamen. **Der Klammerinhalt bleibt draussen,
und das ist eine gemessene Entscheidung, keine Nachlaessigkeit.**

(4) **Ein Fehlalarm, den ich selbst eingebaut hatte.** Die Variante
"<Vermittler> AG" holte einen Namen zurueck, den die Ausnahmeliste
ausdruecklich heraushaelt. Beim Nachsehen: die Ausnahme verglich auf
GLEICHHEIT — ein Vermittler mit angehaengter Rechtsform war also schon
vorher nicht ausgenommen. Die Variantenbildung hat einen alten Fehler
nur sichtbar gemacht.

(5) **Der Bestand enthaelt Namen, die keine sind.** "SAP" (25 Issues),
"Name" (24), "Google" (15) stehen als Firma bzw. Person in der DB. Sie
schweigen jetzt nicht, sondern werden als `unsicher` gemeldet — der
vorhandene Mechanismus aus #962 ist genau dafuer da.

(6) **Der eigentliche Ertrag ist die Messung, nicht der Fix.** Mit dem
reparierten Pruefer ueber alle 400 Issues: **39 tragen einen sicheren
Bestandsnamen** (36 Firmen, 3 Personen). Was damit geschieht, ist eine
Nutzerentscheidung — Issues zu loeschen verbrennt Nummern, und die
Edit-Historie behaelt das Original.

## Stand 2026-09-08 (v1.7.52 Stable) — Nicht jeder Kilometer kostet gleich viel

**#965 Befund 2** (AK 6-8). Befund 1 und der Nebenbefund waren seit
v1.7.24/v1.7.39 erledigt — vor dem Bauen gemessen, welche der neun
Akzeptanzkriterien noch offen sind, statt das ganze Issue neu zu
beginnen. **Tests: 3187 / 3253.**

MERKE-Punkte:

(1) **Der Nutzer beschreibt eine Groesse, die PBP gar nicht kannte.**
Zwei Stellen mit derselben Kilometerzahl sind nicht gleich weit, wenn
zwischen Wohnort und einer davon eine Barriere liegt — und der
Unterschied ist kein Aufschlag, den man mitteln koennte, sondern eine
STREUUNG, die den Weg unplanbar macht. Genau deshalb traegt Weg 1
(Routing-Dienst) nicht: eine Routenberechnung liefert den Mittelwert
und verfehlt das Eigentliche.

(2) **"Sonst wird daraus ein Sonderfall fuer eine Stadt."** Der Satz
stand im Issue und ist die wichtigste Vorgabe gewesen. Das Modul kennt
deshalb keine Elbe, keinen Elbtunnel und kein Hamburg, sondern nur
Himmelsrichtungen aus einem Koordinatenvergleich. **Ein Test liest den
Quelltext und verbietet Ortsnamen** — sonst waechst die Landeskunde
still hinein, sobald jemand einen Sonderfall "nur schnell" ergaenzt.

(3) **Der Aufschlag wirkt auf den PREIS, nie auf die Messung.** Die
ausgewiesene Entfernung bleibt unveraendert; nur die Rechengroesse
steigt. Anders herum haette PBP wieder eine Zahl, die etwas anderes
bedeutet als sie sagt — genau das, was v1.7.50 fuer dieselbe Zahl
gerade behoben hat.

(4) **Beim ersten Anlauf nur in EINEN Rechenweg gebaut.** Das
Patch-Skript meldete "1x eingebaut", erwartet waren zwei — dadurch
aufgefallen und sofort nachgezogen. Das ist das Muster aus #963, das
dieses Projekt sieben Mal gekostet hat; hier hat allein die
Zaehlausgabe des eigenen Skripts es gefangen. **Ein Patch, der sagt wie
oft er gegriffen hat, ist mehr wert als einer, der nur "fertig"
meldet.**

(5) **Zwei tote Spalten wiederbelebt statt neue angelegt.**
`jobs.lat`/`jobs.lon` gibt es seit jeher, `save_jobs` schreibt sie —
**gesetzt hat sie nie jemand.** Dieselbe Klasse wie #993 und #1000, nur
in der Datenbank. Sie tragen jetzt die Koordinaten aus dem Geocoding;
ohne sie liesse sich die Richtung nur per Netzabfrage bestimmen, und ein
Score darf nicht am Netz haengen (v1.7.36 MERKE 3).

(6) **Eine ungueltige Regel wird ABGEWIESEN, nicht teilweise
gespeichert.** Wer zwei Regeln setzt und eine davon ist falsch, bekommt
gar nichts gespeichert und eine Begruendung. Teilweise gespeichert waere
schlimmer: der Mensch glaubte dann an eine Regel, die nur zur Haelfte
gilt (#988).

(7) **Der Aufschlag hat eine Obergrenze.** Ohne sie waere er ein
verstecktes k.o. — und die Entscheidung "Entfernung ist ein Preis, kein
Ausschluss" (#910/#988) gilt weiter.

## Stand 2026-09-08 (v1.7.51 Stable) — "Nichts gefunden" hat zwei Bedeutungen

**#995**, der Nebenbefund aus der Quellenpflege (#813), jetzt behoben.
**Tests: 3170 / 3236.**

MERKE-Punkte:

(1) **Dieselbe Zahl fuer zwei entgegengesetzte Sachverhalte.**
`letzte_rohtreffer` war bei ZWOELF Adaptern bereits das Ergebnis ihres
INTERNEN Keyword-Filters. Gemessen an himalayas: API 20, Adapter 0,
Diagnose 0. Damit sah eine tote Quelle genauso aus wie eine global
ausgerichtete ohne fachliche Passung — **und beide wurden nach fuenf
Laeufen abgeschaltet.** Genau so verlor PBP am 01.09. eine Quelle, die
lieferte (#813). Derselbe Fehlertyp wie #989, diesmal an der
Quellen-Statistik.

(2) **Der Melder nannte drei Adapter und schrieb "mindestens".** Mein
erster Durchgang fand zehn, tatsaechlich sind es zwoelf — ein `grep`
mit `head -20` hatte die letzten beiden abgeschnitten. **Gefunden hat
sie der Test**, der die Adapter selbst abzaehlt statt einer Liste zu
glauben. Ein Guard, der seine eigene Grundlage nachrechnet, faengt
genau den Fehler, den man beim Schreiben der Liste macht — er hat sich
beim ERSTEN Lauf bezahlt gemacht.

(3) **`None` heisst "nicht gemeldet", nicht "null gesehen".** Ohne
diese Unterscheidung waere der Fix wirkungslos gewesen: ein Adapter, der
nichts meldet, haette sonst als "liefert nichts" gegolten und genau die
Abschaltung ausgeloest, die verhindert werden sollte. Adapter ohne
eigenen Filter melden bewusst nicht — bei ihnen war die Zahl schon
richtig.

(4) **Register statt Rueckgabe-Vertrag.** Der saubere Weg waere
`(stellen, befund)` je Adapter — das beruehrt alle 26 und ihre
Aufrufer. Stattdessen meldet jeder filternde Adapter im Vorbeigehen.
Thread-lokale Ablage waere hier FALSCH gewesen: die Quellen laufen in
einem ThreadPool, Adapter und Sammler sitzen also in verschiedenen
Threads. Ein Lock genuegt, weil je Quelle genau ein Arbeiter laeuft.

(5) **Punkt 4 des Melders bleibt offen und ist richtig.** Den
adaptereigenen Keyword-Filter ganz aufzugeben und dem zentralen Filter
zu ueberlassen waere der saubere Umbau — er beruehrt zwoelf Adapter samt
ihrer REGIONSfilter, und das ist eine Verhaltensaenderung, keine
Fehlerbehebung. B44 steht deshalb auf ✅ fuer AK 1-4 und traegt den
Rest als benannten Rueckstand.

## Stand 2026-09-08 (v1.7.50 Stable) — Zahlen, die etwas anderes bedeuten

Zwei Befunde aus der Durchsicht offener Meldungen, beide vom Typ der
ganzen Tageswelle: eine Angabe, die aussieht als bedeute sie etwas, und
etwas anderes bedeutet. **Tests: 3146 / 3212.**

MERKE-Punkte:

(1) **`chrome` ist ein CLIENT-Objekt, nicht die Server-Antwort (#993).**
`JobsPage` las `chrome?.search_criteria?.min_score_schwelle` — den
Schluessel setzt `App.jsx` gar nicht (dort stehen loading, status,
workspace, profiles, profile, wizardCompleted, searchStatus,
profileOnboarding). Mein erster Fix war deshalb an der falschen Stelle:
das Feld in die Workspace-Antwort zu legen half nichts, solange der
Zugriff `chrome.search_criteria` und nicht `chrome.workspace.
search_criteria` lautet. **Bei einem Paritaets-Guard zuerst klaeren,
WELCHE zwei Dinge da eigentlich verglichen werden** — der erste Entwurf
meldete sieben Fehlalarme, weil er die beiden Ebenen verwechselte
(v1.7.31 MERKE 4, jetzt in einer neuen Gestalt).

(2) **Zum DRITTEN Mal an einem Tag hat mein eigener Erklaerkommentar
einen Guard ausgeloest.** Ein Test, der eine falsche Schreibweise
verbietet, schlaegt an der Begruendung an, warum sie falsch ist — und
eine gute Begruendung muss den verbotenen Ausdruck nun einmal nennen.
Nach #998 und v1.7.31 MERKE (6) steht die Bereinigung jetzt als Helfer
`ohne_kommentare()` im Test und nicht mehr als Einzelfall je Guard.

(3) **Eine Groesse, die nur angezeigt wird, darf ungenau sein — eine,
gegen die gerechnet wird, nicht (#950).** `entfernung_km` ist eine
Luftlinie: gemeldet 271,5 km gegen rund 390 km Fahrstrecke, Faktor
1,44 statt der in #167 angenommenen 1,3. Seit #910 wird die Zahl gegen
das Gehalt verrechnet, ein zu niedriger Wert faellt also zugunsten
weit entfernter Stellen aus. Neu `services/entfernung.py`; jede Ausgabe
nennt ihre Art, ab 25 km steht eine als Schaetzung gekennzeichnete
Fahrstrecke daneben. **Im Nahbereich bewusst keine Schaetzung** — dort
waere sie Scheingenauigkeit.

(4) **Bewusst nur AK 1 und 2.** Echtes Routing samt Fahrzeit (AK 3/4)
braucht einen API-Schluessel; das ist eine Nutzerentscheidung und keine
Fehlerbehebung. C55 steht deshalb auf 🟨, nicht auf ✅ — ein halb
erledigtes Issue als erledigt zu fuehren ist die Falle aus DoD 8a.

(5) **Nebenbefund, vom eigenen Test gefunden und als Test
festgehalten:** mit genau EINEM MUSS-Begriff ist der Fachscore so klein
(2 Punkte), dass der Entfernungsmalus ihn ueberholt und
`calculate_score` auf 0 kappt. Eine Fernstelle sieht damit aus wie eine,
die das MUSS-Tor nie passiert hat — zwei Sachverhalte, eine Zahl. Bei
drei und mehr Begriffen tritt es nicht auf (gemessen). Kein Defekt im
engeren Sinn, aber die Grenze gehoert bekannt.

## Stand 2026-09-08 (v1.7.49 Stable) — Der Gap war die Skala

**#999.** Eine Stelle, die ALLE MUSS-Begriffe trifft, remote ist, 3 km
entfernt liegt und ueber Wunsch zahlt, bekam *"Score 15.0/100 —
fachlicher Gap zu gross"*. **Tests: 3132 / 3198.**

MERKE-Punkte:

(1) **Der Satz des Melders ist die ganze Analyse: "Der Gap ist die
Skala."** `total_score` ist keine Prozentzahl, sondern eine
ungedeckelte Punktsumme, deren Obergrenze aus der LAENGE der MUSS-Liste
folgt. Gemessen mit Volltreffer-Anzeigen: 5 Begriffe -> 15 Punkte,
10 -> 26, 20 -> 46, 40 -> 86. Die Schwelle 75 fuer EMPFOHLEN beginnt
damit bei rund 37 gleichzeitig getroffenen Pflichtbegriffen. **Mit
einer realistisch gepflegten Liste war die Kategorie strukturell
unerreichbar** — und jede Stelle bekam denselben Satz, was den Verdict
wertlos macht.

(2) **Der Hoechstwert folgt derselben Rechnung wie der Score.**
`score_maximum(criteria)` = `fachscore_max + min(rahmen_max, Deckel x
fachscore_max)`. Die Probe darauf ist der staerkste Test der Welle: eine
Anzeige, die alles trifft, erreicht bei JEDER Listenlaenge exakt 100 %.
Weicht das ab, ist die Formel falsch und nicht die Einordnung —
deshalb steht genau das als Test da und nicht eine Liste erwarteter
Zahlen.

(3) **Den Score NICHT angefasst.** Er misst, was in der Anzeige steht;
die Einordnung ist eine Darstellung und zieht dort die Konsequenz. Das
ist #989 MERKE (3) woertlich — gespeicherte Zahlen still umzuschreiben
waere derselbe Fehler wie #987, nur absichtlich.

(4) **Vierte Kategorie statt geratener Absage.** Ist der Hoechstwert
unbekannt, gibt es keine Skala und damit keine ehrliche Einordnung:
`NICHT_BEURTEILBAR`. Das erweitert den #662-Vertrag, den CLAUDE.md
vorschreibt — die Alternative waere gewesen, "unbekannt" als "passt
nicht" auszugeben, also genau die Verwechslung aus #989.

(5) **Drei Alt-Tests hielten die falsche Annahme fest.** Sie
uebergaben Scores von 80/60/20 und erwarteten EMPFOHLEN/BEDINGT/
NICHT_EMPFOHLEN — also exakt die 100er-Skala, die es nie gab. Sie
sind nicht geloescht, sondern bekommen `total_score_max: 100`
ausdruecklich mitgegeben. **Ein Alt-Test, der eine Annahme
unterstellt, wird ehrlich, wenn man die Annahme hinschreibt** — dann
prueft er weiter die Stufengrenzen und nicht mehr die Fiktion.

(6) **Nebenbefund im Wiki:** Tab-Stellen behauptete "Der Gesamtscore
wird als Prozentwert angezeigt". Die Doku trug denselben Fehler wie der
Code — und sie war die Stelle, an der ein Leser die Annahme uebernimmt.

## Stand 2026-09-08 (v1.7.48 Stable) — Zwei Regler ohne Draht

**Das tausendste Issue des Projekts (#1000)**, gemeldet vom selben
Anwender wie #990/#994/#997/#998. `jobsuche_starten` nahm
`max_entfernung_km` und `nur_remote` entgegen und las beides nie.
**Tests: 3120 / 3186.**

MERKE-Punkte:

(1) **Nicht zwei Fundstellen, sondern eine Familie.** "Maximale
Entfernung" gibt es in VIER Schreibweisen, und nur eine hat einen
Leser: der Tool-Parameter (tot), `criteria.max_entfernung_km` (tot,
live auf 30 gemessen), der Ersterfassungs-Prompt (nennt zwei Parameter,
die `suchkriterien_setzen` gar nicht hat) und die Karte
`max_entfernung` je Stellenart (der einzige gelesene Wert). Der
gemeldete Teil war der sichtbarste, nicht der teuerste — **der
Onboarding-Prompt trifft jeden neuen Nutzer, und dort verdunstet der
Entfernungswunsch bei der ersten Nennung.**

(2) **Entfernt statt nachtraeglich verdrahtet — mit inhaltlicher
Begruendung.** Als harte Filter wuerden beide Parameter zwei bewussten
Entscheidungen widersprechen: Entfernung ist ein PREIS, kein Ausschluss
(#910/#988), und `nur_remote` verwuerfe jede Stelle mit unbekanntem
`remote_level`, also genau die Verwechslung von "unbekannt" mit
"erfuellt nicht", die #989 abgeschafft hat. **Ein Parameter, dessen
ehrliche Umsetzung eine Designentscheidung brechen wuerde, gehoert
nicht verdrahtet, sondern weg.**

(3) **Ein Werkzeug wegzunehmen ist nur dann richtig, wenn der Wunsch
einen Weg behaelt.** `suchkriterien_setzen(max_entfernung_km=30)` ist
neu — eine Zahl fuer alle Stellenarten, weil ein Mensch "hoechstens
30 km" sagt und keine Karte je Stellenart. Die Karte gewinnt, wenn
beides kommt, und PBP sagt welche es genommen hat.

(4) **Der Altwert wird BENANNT, nicht still umgedeutet.** Ein
`max_entfernung_km`, gegen das niemand rechnet, faellt jetzt in
`suchkriterien_anzeigen` auf. Ihn im Hintergrund neu zu deuten waere
eine Score-Aenderung, die niemand veranlasst hat — dasselbe Vorgehen
wie bei den wirkungslosen Scoring-Reglern in #988 (v1.7.36 MERKE 6).

(5) **Ein Prompt-Guard, der gegen die echte Signatur prueft.** Der Test
liest die Parameternamen aus der Prompt-Anweisung und vergleicht sie mit
`inspect.signature` des Tools. Eine Liste im Test haette denselben
Fehler nur an einer zweiten Stelle festgehalten; so faellt auch ein
kuenftig umbenannter Parameter auf. **Prompts sind Code, den niemand
kompiliert** — und der einzige Teil des Systems, dessen Fehler direkt
beim Nutzer landen.

## Stand 2026-09-08 (v1.7.47 Stable) — Der halbe Lebenslauf

**#998**, aus derselben Vierer-Welle wie #997 und **#1000**. Ein
DOCX-Lebenslauf ergab 26 Zeichen Text — alles lag in einer Tabelle.
**Tests: 3108 / 3174.** MCP-Tools 213 / 226.

MERKE-Punkte:

(1) **`doc.paragraphs` sind NUR Absaetze auf Body-Ebene.** Zelltext,
Kopf-/Fusszeilen und Textfelder kommen dort nicht vor. Der Melder hat
die Zeile mitgeliefert; gemessen an einer Vorlage: **13 gegen 205
Zeichen**, die Mailadresse stand in der Kopfzeile. **Zweispaltiges
Tabellenlayout ist bei Lebenslaeufen die Regel, nicht die Ausnahme** —
das Format war also nicht am Rand, sondern im Zentrum des Anwendungsfalls.

(2) **Der naheliegende Fix aus dem Issue haette den Text verdreifacht.**
`row.cells` liefert eine ueber drei Spalten verbundene Zelle DREIMAL
(gemessen, Test haelt die Annahme fest). In CV-Vorlagen sind
Abschnittsueberschriften fast immer verbunden, und dieser Text geht ins
Scoring. Im rohen OOXML gibt es die Zelle genau einmal — das Problem
entsteht erst durch die Bequemlichkeitsschicht. Deshalb liest `_docx` in
`services/office_text.py` stdlib statt python-docx; Dokumentreihenfolge
und Textfelder kommen dabei kostenlos mit. **Vorschlaege aus Issues
gehoeren geprueft, nicht uebernommen** (v1.7.24 MERKE 1, dritter Fall).

(3) **Ein Sonderweg im `elif` haelt eine ganze Maschinerie fern.**
`.docx` hatte seinen eigenen Zweig und erreichte die #833-Logik nie —
es gab fuer Word also nicht einmal die ehrliche "leer"-Meldung. Der
Melder schrieb, `format_befund` melde `{"format": "leer"}`; tatsaechlich
meldete es GAR NICHTS. **Wenn ein Bericht die Folge etwas zu guenstig
beschreibt, ist der wirkliche Zustand oft schlechter** — nachsehen statt
uebernehmen. Jetzt geht DOCX durch denselben Dienst wie PPTX/XLSX/ODT.

(4) **Ein besserer Leser hilft nur neuen Uploads.** Der Bestand behaelt
den duennen Text und sieht unauffaellig aus — dasselbe galt seit #833
fuer PPTX, ohne dass es jemandem aufgefallen waere. Es gab keinen Weg
zurueck: `extraktion_starten` liest `extracted_text` aus der DB und
fasst die Datei nie wieder an. Neu `dokumente_text_nachziehen`
(Vorschau als Vorgabe, **ueberschreibt nur bei MEHR Text**,
Handnachtrag mit Provenienz-Header bleibt unangetastet). **Eine
Verbesserung ohne Nachziehpfad ist eine halbe Verbesserung.**

(5) **Cherry-Pick: der Konflikt riss 280 Zeilen mit.** Die Aufloesung
holte drei BETA-Werkzeuge (`newsletter_*`, `dokument_ocr_ausfuehren`)
auf die Stable-Linie und dazu main's Namensliste im Registry-Test.
Gefunden hat es der Registry-Guard. Die Regel aus v1.7.46 MERKE (8) hat
gegriffen, aber erst hinterher: **bei einem Konflikt, der groesser ist
als die eigene Aenderung, die Datei zuruecksetzen und den eigenen Block
mit dem Edit-Werkzeug neu setzen** — Marker zu entfernen ist keine
Aufloesung.

(6) **Die Linien-Signatur unterscheidet sich, und das faellt nicht
auf.** `_extract_document_text` gibt auf Stable ein ZWEIER-Tupel zurueck
(kein OCR), auf main ein Dreier. Der portierte Code entpackte drei
Werte. Kein Konflikt, kein Syntaxfehler — nur ein Laufzeitfehler beim
ersten Aufruf. Beim Port also nicht nur den Code, sondern die
SIGNATUREN der aufgerufenen Funktionen abgleichen.

(7) **Denselben Fehler zweimal gemacht, obwohl er notiert war.** Der
CHANGELOG-Eintrag landete wieder unter dem Vorgaenger, weil ich das
Skript aus v1.7.46 in derselben Form wiederverwendet habe — der Anker
muss der KOPF des bisher juengsten Eintrags sein, nicht sein
Installblock. Eine notierte Lehre schuetzt nicht, wenn man die Vorlage
kopiert, in der der Fehler steckt.

(8) **Ein Test darf keine Bibliothek importieren, die nicht in den
Abhaengigkeiten steht.** Mein erster Bestands-Test baute die Fixture mit
`python-pptx` — lokal installiert, aber in keiner Dependency-Gruppe
(#833). Auf dem CI-Runner waere er rot geworden oder, nach einem
`importorskip`, still uebersprungen. Die Fixture entsteht jetzt mit
`zipfile`. Das ist DoD 8c (b) in einer neuen Gestalt.

## Stand 2026-09-08 (v1.7.46 Stable) — Eine Erfolgsmeldung ueber nichts

**#997, gemeldet vom selben fremden Anwender wie #990/#994** — und aus
derselben Vierer-Welle wie das **Issue #1000**. `profil_bearbeiten`
meldete `status: "aktualisiert"` samt `geaenderte_felder` fuer eine ID,
die es nicht gibt. **Tests: 3090 / 3156.**

MERKE-Punkte:

(1) **Die Auskunft war da und wurde weggeworfen.** `update_position` und
ihre sechs Geschwister geben `cur.rowcount > 0` zurueck; die Tool-Ebene
verwarf diesen Wert an SIEBEN Stellen. Das ist nicht dieselbe Bauform
wie #994 (dort filterte die Schreibschicht Felder still heraus) —
diesmal hat die untere Ebene ausdruecklich "nein" gesagt und die obere
hat es nicht zugehoert. **Ein Rueckgabewert, den niemand liest, ist
dasselbe wie kein Rueckgabewert.**

(2) **Der REST-Weg machte es seit jeher richtig.** `dashboard.py`
antwortet auf dieselbe Frage mit HTTP 404 ("Position nicht gefunden"),
und `delete_skill` war der eine von acht MCP-Zweigen, der den Wert
auswertete. Also wieder zwei Wege fuer eine Frage — und wieder ist der
schwaechere der, den Claude nimmt. Das ist #991 in einem anderen Modul.
**Beim Suchen nach der richtigen Fassung lohnt der Blick auf den
anderen Weg**, statt sie neu zu erfinden: die Antwortform steht dort
schon.

(3) **`False` hiess zwei Dinge, und das durfte die Antwort nicht
raten.** Auf DB-Ebene bedeutet `return False` sowohl "diese ID gibt es
nicht" als auch "kein schreibbares Feld dabei" (beide Zweige enden
gleich). Eine Absage, die sich ohne Nachsehen fuer eines entscheidet,
schickt den Aufrufer im halben Fall in die falsche Richtung — genau der
Fehler aus #987 MERKE (5). `_kennt_id` sieht deshalb nach.

(4) **Sind BEIDE falsch, wiegt die ID schwerer** — vom eigenen Test
gefunden, nicht gemeldet. Meine erste Fassung meldete bei falscher ID
UND falschem Feldnamen nur den Feldnamen; wer den korrigiert haette,
waere beim zweiten Versuch weiterhin ins Leere gelaufen. Der zweite
Befund geht jetzt nicht verloren, steht aber hinten.

(5) **Der Guard zaehlt die Fundstellen nicht ab, er ruft sie auf.** Vier
Bereiche mal aendern/loeschen als `parametrize`, jeweils mit einer ID,
die es nicht gibt. Sieben Zeilennummern nachzupruefen haette eine
kuenftige achte Verzweigung uebersehen — dasselbe Argument wie bei
#994 MERKE (4).

(6) **Der vierte Bereich fehlte schon wieder.** #994 hat die
Felduebersetzung fuer position/ausbildung/projekt gebaut und `skill`
ausgelassen — im selben Modul, mit derselben Begruendung, die H19 MERKE
(1) beschreibt ("wenn ein Muster fuer einen von drei Datentypen gebaut
wird..."). Hier war es sogar noetig: ohne `_SCHREIBFELDER["skill"]`
haette die neue Absage "nicht_gefunden" gelautet, wo in Wahrheit nur
der Feldname deutsch war.

(7) **Nebenbefund, vom eigenen Test gefunden:** `add_skill` weist
Extraktions-Muell ab (#43/#129) und gibt eine LEERE ID zurueck — die
Antwort lautete trotzdem "hinzugefuegt", mit `id: ""`. Derselbe stille
Fehlschlag mit Erfolgsmeldung, nur beim Anlegen statt beim Aendern.

(8) **Cherry-Pick: zwei Hunks wurden STILL verschluckt.** Beim Port auf
die Stable-Linie meldete git EINEN Konflikt (den neuen Hilfsblock) und
liess dabei die beiden Eintraege in `_SCHREIBFELDER`/`_FELD_ALIASE`
kommentarlos fallen. Gefunden haben es die mitgewanderten TESTS, genau
wie in v1.7.12 — nicht die Konfliktmeldung. **Nach dem Aufloesen die
portierte Datei gegen die Quelle diffen** (`git diff main -- <datei>`
muss leer sein), nicht nur die Marker zaehlen.

(9) **Beim CHANGELOG die Reihenfolge pruefen.** Mein Skript hat den
neuen Eintrag an der Stelle des Installblocks eingefuegt — er landete
UNTER dem Vorgaenger, und der Vorgaenger verlor seinen eigenen
Installblock. Beides vor dem Commit gefunden. Jeder Eintrag traegt
seine EIGENE Versionsnummer im Download-Link (v1.7.31 MERKE 7); ein
Skript, das den Block verschiebt, muss beide Seiten pruefen.

## Stand 2026-09-08 (v1.7.45 Stable) — "Remote" heisst nicht "von ueberall"

Der Nutzer fragte: *"Was habe ich mit US zu tun? Denke das ist ein
Fehler, zumal wir nur deutsche bzw. Quellen fuer den deutschsprachigen
Raum durchsuchen."* Er hatte recht. **Tests: 3069 / 3135.**

MERKE-Punkte:

(1) **Die Ursache war EINE Zeile, und sie stand seit jeher da.**
`entfernungs_guete` gab fuer `remote_level == "remote"` pauschal
`"entfaellt", "Vollstaendig remote — Entfernung ohne Belang."` zurueck.
Also KEIN Abzug, egal wo die Stelle liegt. **"Remote" heisst nicht "von
ueberall", sondern "ohne festen Buerositz INNERHALB eines
Rechtsraums"** — eine US-gebundene Rolle ist von Hamburg aus nicht weit
weg, sondern nicht bewerbbar (Arbeitserlaubnis, Arbeitsrecht,
Kernzeit). `entfaellt` war exakt derselbe Nulltarif, den #989 beim Score
abgeschafft hat, nur eine Ebene weiter: beim Ort.

(2) **Gemessen, bevor etwas geaendert wurde.** Alle drei Remote-Boersen
live, ohne Keyword-Filter: himalayas 20 von 20 ausserhalb DACH (0 %),
remoteok 90 von 100, remotive 3 von 17. Geliefert wurden
"Remote (United States)" (5x), "Remote (Romania)", "Remote (New
Zealand)", "Remote (Argentina Belize Colombia ...)".

(3) **Positivbeleg statt Verdacht.** Ausgeschlossen wird NUR, wo ein
Nicht-DACH-Land ausdruecklich dasteht. "Bedford", "Nassau" und schlicht
"Remote" bleiben `unbekannt` und unveraendert — es gibt deutsche Orte
mit fremd klingenden Namen, und ein falscher Ausschluss ist teurer als
ein zu hoher Score (#827). Wortgrenzen sind dabei Pflicht: "us" steckt
sonst in "Kundenservice" und "Industrie" (#929-Lehre). Drei Zustaende
statt zwei: `dach` / `ausserhalb` / `unbekannt`.

(4) **In BEIDE Rechenwege eingebaut, beim ersten Anlauf.** `fit_analyse`
hat denselben k.o. wie `calculate_score`, und ein Test vergleicht fuenf
Ortsangaben auf beiden Wegen. Das ist das Muster, das dieses Projekt
sieben Mal gekostet hat (#963 zuerst) — diesmal von vornherein bedacht.

(5) **Eine falsche Registry-Beschreibung waehlt die Quellen falsch
aus.** Bei `himalayas` stand "gute DACH-Abdeckung ueber
country=DE-Filter". Der Filter wirkt nicht, gemessen 0 von 20. Diese
Zeile ist vermutlich der Grund, warum die Quelle ueberhaupt aktiviert
wurde. Neu `regionen_fokus` + `regionen_befund` je Quelle, sichtbar in
`scraper_diagnose`: **eine global fokussierte Quelle ist nicht KAPUTT,
wenn sie fuer eine DACH-Suche nichts bringt — sie ist die FALSCHE
Quelle.** Ohne dieses Feld sah beides gleich aus.

(6) **Selbstkorrektur zu v1.7.44 vom selben Tag.** Dort habe ich die
Ortsbindung nur SICHTBAR gemacht ("Remote (United States)" statt
"Remote") und dabei einen Adapter wiederbelebt, der fuer dieses Profil
nachweislich 0 % Passendes liefert. Die Anzeige war besser, die Frage
"warum fragen wir diese Quelle ueberhaupt" blieb ungestellt. **Ein
repariertes Werkzeug ist nicht dasselbe wie ein nuetzliches.**

(7) **Arbeitsweise, teuer gelernt:** ein `git checkout <datei>` zum
Zuruecknehmen eines misslungenen Regex-Patches hat auch die
funktionierenden, noch nicht committeten Aenderungen derselben Datei
mitgenommen. Vor einem riskanten Skript-Patch committen — der Commit
ist der Rueckfallpunkt, nicht die Erinnerung.

## Stand 2026-09-08 (v1.7.44 Stable) — Eine abgeschaltete Quelle lebte

Eine Bestandsaufnahme, kein Fehlerbericht: sieben Quellen standen seit
dem 01.09. automatisch abgeschaltet ("5 stille Laeufe in Serie").
**Eine davon lieferte in Wahrheit 20 Stellen.**
**Tests: 3052 / 3118.**

MERKE-Punkte:

(1) **Die teuerste Bauform einer stillen Null ist die, die sich selbst
bestaetigt.** `himalayas` antwortet mit HTTP 200 und 20 Stellen; der
Adapter starb an der ERSTEN davon (`seniority` kommt seit einem
Feldumbau als Liste statt als String), und weil die Zuordnungsschleife
in einem grossen `try` lag, kam eine leere Liste zurueck. Der Fehler
erzeugt Leere, die Leere erzeugt die Abschaltung, die Abschaltung
verhindert, dass der Fehler je wieder auffaellt. Neu
`job_scraper/satzweise.py`: ein kaputter Satz kostet einen Satz.
Gezaehlt: **zehn Adapter** tragen dieselbe Bauform, zwei davon
(`remoteok`, `remotive`) liefern produktiv.

(2) **Ein Datenfeld ist kein Mechanismus.** #590-C.1 setzt beim
Abschalten ein `reactivate_at` (24 h, dann 48/72/168) — **gelesen hat es
kein einziger Aufrufer.** Der Backoff stand seit Monaten in CLAUDE.md
als funktionierendes Feature; tatsaechlich lief keine abgeschaltete
Quelle je wieder, und `letzte_probe_am` stand bei allen sieben auf
`null`. Das ist DoD 8c fuer einen Mechanismus statt fuer einen Guard:
**geschrieben ist nicht aufgerufen.** Die Auswahl liegt jetzt in
`quellen_einteilen(db)` — bewusst herausgezogen, weil sie als
Inline-Block in einer mehrhundertzeiligen Funktion von aussen nicht
pruefbar war, und genau deshalb der fehlende Zweig nie auffiel.

(3) **Ein alter Fehler, der stehen bleibt, ist eine Falschaussage.**
`last_error` wurde bei Erfolg nie geloescht: die Bundesagentur trug mit
91 % Erfolgsrate, Fehlerserie 0 und 5122 Treffern weiterhin
"server_weg", remoteok und remotive "timeout", linkedin "deprecated".
Wer die Diagnose las, sah neben JEDER laufenden Quelle einen Fehler.

(4) **"Nicht pruefbar" ist nicht "nicht erreichbar".** Fuenf der sieben
Quellen haben gar keinen Probe (`no_probe_defined`) und wurden trotzdem
als unerreichbar gezaehlt. Dieselbe Verwechslung wie #989: eine
fehlende Information sah aus wie eine negative.

(5) **Beim Cherry-Pick auch die TEXTE pruefen, nicht nur den Code.**
Der Konflikt in `quellen_health_check` zeigte darauf: Stables kuerzere
Fassung war kein Rueckstand, sondern richtig — sie nennt bewusst keine
Beta-Werkzeuge. Beim Nachsehen stand `quelle_handoff` (B25/#735, nur
1.8) auf der Stable-Linie an SIEBEN Stellen als Ausweg fuer tote
Quellen. Auf Stable ersetzt, **auf main bewusst NICHT** — dort gibt es
das Werkzeug. Ein Cherry-Pick, der eine Korrektur in die falsche
Richtung traegt, macht die Gegenseite schlechter.

(6) **Nebenbefund, als #995 erfasst statt hier erledigt:** bei
`himalayas`, `remoteok` und `remotive` ist `letzte_rohtreffer` schon
keyword-gefiltert. Damit sehen "liefert nichts" und "liefert nichts
Passendes" gleich aus — und beide fuehren zur Abschaltung. Das beruehrt
den Rueckgabe-Vertrag der Adapter und gehoert nicht in eine
Fehlerbehebung.

## Stand 2026-09-07 (v1.7.43 Stable) — Im echten Browser nachgemessen

Der LinkedIn-Weg aus v1.7.42 wurde unmittelbar nach dem Release im
eingeloggten Chrome durchgespielt. **Tests: 3035 / 3101.**

MERKE-Punkte:

(1) **AK1 ist jetzt gemessen, nicht behauptet.** Suche "PDM", DE, letzte
Woche: Oberflaeche 8 Karten, Voyager-API 8 Karten, `paging.total` 8,
Schnittmenge 8 — keine Abweichung in beide Richtungen. Zwei Begriffe,
eine Seite: 30 deduplizierte Treffer, alle mit Titel, Firma und Ort;
drei Volltexte mit 4.682 / 1.461 / 4.118 Zeichen. Die Decoration-IDs vom
17.08. gelten weiter (HTTP 200).

(2) **Ein Rezept fuer einen fremden Browser gehoert im fremden Browser
gemessen.** Alle vier Skripte waren gegen Fixtures gruen — und
ausgerechnet der einzige Schritt, der die SEITE anfasst, war falsch:
**LinkedIn sanitisiert `innerHTML`.** `JS_AUSGABE` schrieb
`<main><article>` in den Body; danach standen 10.589 Zeichen Text da und
`document.body.children` war LEER, samt der `<hr>`-Trenner zwischen den
Stellen. Der Text waere angekommen und nicht mehr zerlegbar gewesen.
Jetzt `textContent` (kein Markup, also nichts zu sanitisieren) plus
`white-space: pre-wrap` (ohne das faltet der Browser die Umbrueche zu
Leerzeichen) und Text-Marker statt Tags; `parse_ausgabe()` ist der
Gegenpart, damit nicht jeder Aufrufer die Marker neu raet.

(3) **Der Parser lag richtig, aus einem Grund, den ich nicht kannte.**
Von 16 `JobPostingCard`-Objekten tragen nur 8 eine ID; die anderen 8
sind Stub-Referenzen mit ausschliesslich `entityUrn` — LinkedIns
normalisiertes JSON legt referenzierte Objekte zweimal ab.
`paging.total` bestaetigt die 8. Die Regel "ohne ID faellt die Zeile
heraus" trifft also genau die Stubs. **Bei einer fremden API auch
pruefen, warum etwas stimmt** — sonst haelt man einen Zufall fuer eine
Regel.

## Stand 2026-09-07 (v1.7.42 Stable) — LinkedIn liefert wieder

**#919.** Die Quelle stand auf aktiv, hatte aber `letzter_lauf
23.04.2026` und Erfolgsrate 0 %; die jobspy-Variante ist deprecated nach
24 Fehlern in Serie. HTTP von aussen blockt LinkedIn zuverlaessig,
Requests aus dem EINGELOGGTEN Tab laufen durch. Der am 17.08.
durchgespielte Weg (22 Begriffe, 511 Rohtreffer, 59 Volltexte, 3
uebernommene Stellen) lag bis jetzt nur im Issue.
**Tests: 3034 / 3100.** MCP-Tools 212 / 225.

MERKE-Punkte:

(1) **Der Volltext ist der ganze Wert der Quelle.** Von 59 Titeln, die
den Vorfilter passiert hatten, blieben nach dem Lesen 3 uebrig — und der
nach Titel BESTE Treffer des Laufs verlangte im Fliesstext ein System
von der harten Ausschlussliste. Ein Import, der Titel und Kurztext
nimmt, liefert also nicht ein paar Fehler ein, sondern bevorzugt die
falschen: sie haben die besten Titel. Deshalb ist
`MIN_BESCHREIBUNG = 500` eine Regel und keine Empfehlung.

(2) **Ein zweiter Schreibweg waere der achte Fall desselben Musters
gewesen.** Der Import geht durch `_stelle_uebernehmen` — den Rumpf von
`stelle_manuell_anlegen`, der dafuer aus dem Tool herausgeloest wurde.
Blacklist (#729/#790/#992), Duplikat-Stufen (#317/#567/#670), Anker
(#766) und Scoring gelten damit unveraendert, ohne dass irgendwo steht
"dieselbe Logik wie". Ein Test legt zweimal dieselbe Stelle an und
erwartet eine.

(3) **Der Python-Teil holt nichts.** Er baut URLs und Header, zerlegt
Antworten und zaehlt den Trichter; geholt wird im Browser. Das ist keine
Notloesung, sondern der Grund, warum die Quelle ueberhaupt testbar ist:
`parse_trefferliste`/`parse_detail` laufen gegen gespeicherte Antworten,
also faellt ein Feldumbau bei LinkedIn im Test auf statt im Feld (AK5).

(4) **Die stille Null ist auch hier der teure Fall.** Auf eine veraltete
Decoration-ID antwortet LinkedIn mit 400/426 — ohne Einordnung sieht das
aus wie "gerade keine passenden Stellen". `fehlerklasse()` benennt es,
und die IDs stehen als Konstanten oben im Modul, nicht verstreut im
Code. Derselbe Gedanke wie #813 und #989.

(5) **Suchbegriffe: das Portal-Profil schlaegt die MUSS-Liste.** #564
wurde genau fuer LinkedIn gelernt (Phrase-Match ergibt 0 Treffer, drei
Buchstaben ohne Branchenfilter treffen alles). `nicht_verwenden` aus dem
Profil gewinnt immer — das ist gelerntes Wissen ueber die Quelle, kein
Vorschlag.

(6) **Bewusste Abweichung vom Issue-Vorschlag:** kein zweiter
Quellen-Eintrag `linkedin_voyager`. Die Quelle `linkedin` existiert,
`url_to_source` zeigt darauf, und ein zweiter Eintrag zerlegte die
Lauf-Historie einer Quelle, die man gerade wieder messen will. Der
bestehende Eintrag traegt den neuen Weg und ist nicht mehr `veraltet`.

(7) **AK1 ist NICHT abgehakt.** "Ein Lauf liefert mindestens die
Trefferzahl der LinkedIn-Oberflaeche" laesst sich nur live im
eingeloggten Chrome pruefen. Der Mechanismus steht und ist gegen
Fixtures gruen; die Zaehlprobe steht aus. Das gehoert gesagt, statt ein
Kriterium als erfuellt zu fuehren, das niemand gemessen hat.

## Stand 2026-09-07 (v1.7.41 Stable) — Was der Filter wegwirft

**#992.** Eine fachlich passende Stelle (MUSS-Begriff zweimal im Titel)
wurde beim Anlegen mit einem Gattungsurteil abgewiesen. Der gemeldete
Teil war die Begruendung; der teurere Teil lag darunter.
**Tests: 3002 / 3068.** MCP-Tools 210 / 223 (+`blacklist_wirkung`).

MERKE-Punkte:

(1) **Dieselbe Frage viermal im Code — und die Ausnahme kannten nur
zwei.** "Blockt die Blacklist diese Stelle" stand in
`is_company_blacklisted` (Substring, MIT Ausnahme), `blacklist_anwenden`
(Substring, MIT), `_post_search_cleanup` (Substring, OHNE) und
`get_active_jobs(exclude_blacklisted)` (GLEICHHEIT statt Substring,
OHNE). Ohne Ausnahme waren ausgerechnet der SUCHLAUF und die
TREFFERLISTE — die beiden, auf die es ankommt. Wer die Ausnahme aus
C31/#790 setzte, bekam die Stelle von Hand durch, und der naechste
Suchlauf warf sie stumm wieder weg. **Zum siebten Mal dasselbe Muster**
(#963, #913, #976, #987, #991, #994); neu `services/blacklist_regel.py`.
Die vierte Fassung verglich Firmen sogar auf Gleichheit, also nach einer
ANDEREN Regel als alle anderen — beim Suchen nach Doppelungen nicht nur
zaehlen, wie oft etwas dasteht, sondern ob es dasselbe sagt.

(2) **Ein Filter, dessen Wirkung niemand sieht, laesst sich nicht
ueberpruefen.** Es gab keine Liste der verworfenen Stellen: man wusste
nicht, ob der Filter richtig arbeitet, und merkte nicht, wenn seine
Begruendung veraltete. Das ist #989 in einer anderen Gestalt — dort
wirkte fehlende Information wie Unauffaelligkeit, hier wirkt eine
unsichtbare Blockade wie ein leerer Markt. Neu die Tabelle
`blacklist_blocks` (Safety-Net ohne Schema-Bump, auf 500 gekappt) und
`blacklist_wirkung()`.

(3) **Das Protokoll ist Vergangenheit, das Urteil ist Gegenwart.** Der
Befund rechnet jede protokollierte Blockade gegen die HEUTIGE Regel
nach: wer inzwischen eine Ausnahme gesetzt hat, wird nicht weiter
ermahnt, sondern bekommt "kaemen inzwischen durch". Ein Pruefer, der bei
korrektem Zustand Alarm gibt, wird nach dem zweiten Mal ignoriert
(DoD-9-Lehre) — das gilt auch, wenn der Alarm mal richtig WAR.

(4) **Ein Guard, der nur beim Anlegen laeuft, sieht den Bestand nie.**
Der Kategorienurteil-Hinweis existierte seit #828 und haette den
gemeldeten Grund ("Zeitarbeit/Consulting") erkannt — der Eintrag war nur
aelter als der Guard. Deshalb jetzt die Bestandspruefung in
`blacklist_wirkung()` und in `pbp_diagnose`. Gemessen am 07.09.: 8 von
24 Firmen-Eintraegen tragen Gattungsbegruendungen, 5 gar keine
Begruendung — die kann auch der Mensch selbst nie mehr pruefen.

(5) **Die Warnung gehoert vor die Wirkung, nicht dahinter.** Der Hinweis
auf `ausser_wenn_titel_enthaelt` erschien erst, wenn eine Stelle bereits
abgewiesen war. Jetzt beim ANLEGEN — samt der konkreten Kollision: PBP
sagt, welche bekannten Stellen dieser Eintrag ab jetzt still verwirft,
wenn ihr Titel MUSS-Begriffe traegt. Das ist der maschinell erkennbare
Widerspruch ("das suche ich" und "das will ich nicht" ueber derselben
Stelle).

(6) **Nebenbefund, vom eigenen Test gefunden:**
`durch_ausnahme_verschont` stand in `blacklist_anwenden` NUR im Zweig
"kein Treffer" — sobald irgendeine andere Stelle passte, verschwand die
Auskunft darueber, was die Ausnahme gerettet hat. Sichtbar war sie damit
genau dann nicht, wenn es interessant wurde.

## Stand 2026-09-07 (v1.7.40 Stable) — Der Weg zur Kennung

**#994, gemeldet von demselben fremden Anwender wie #990.** Nach dem
Onboarding legt Claude die Stationen aus dem Lebenslauf korrekt an —
danach liessen sie sich im Gespraech nicht mehr verfeinern; Claude
meldete, das Werkzeug zum Bearbeiten stehe nicht zur Verfuegung.
**Tests: 2971 / 3037.** MCP-Tools 209 / 222 (+`positionen_anzeigen`).

MERKE-Punkte:

(1) **Ein halber Weg sieht von aussen aus wie ein fehlendes Werkzeug.**
`profil_bearbeiten(bereich='position', aktion='aendern')` gab es seit
langem, `update_position`/`update_education` liegen laenger in der
DB-Schicht. Was fehlte, war die `element_id` — kein Lesewerkzeug gab sie
heraus. Und der Weg dorthin war schon gebaut: H16/#741 hat ihn fuer
PROJEKTE angelegt (`projekte_anzeigen` liefert `position_id`) und fuer
die beiden Ebenen darueber nie nachgezogen. Ausgerechnet fuer Positionen
ohne Projekte — also den Normalfall nach einem CV-Import — half er
deshalb nicht. **Wenn ein Muster fuer einen von drei Datentypen gebaut
wird, gehoert im selben Zug geprueft, warum die anderen zwei ihn nicht
brauchen.**

(2) **Der teurere Teil war der zweite, und er stand im Kommentar des
Melders.** Die Lesewerkzeuge sprechen Deutsch (`aufgaben`, `erfolge`,
`technologien`), die Schreibschicht nimmt die Spaltennamen — und
`update_position` filtert alles andere STILL heraus, waehrend
`profil_bearbeiten` `"aktualisiert"` mit `geaenderte_felder:
['aufgaben']` meldet. Gemessen am 07.09.: Antwort erfolgreich, Bestand
unveraendert. **Eine Erfolgsmeldung ueber eine Nicht-Aenderung beendet
die Fehlersuche** — sie ist teurer als ein Fehler. Verwandt mit #980
(Fallback speicherte eine andere Bedeutung), nur ohne falschen
Datensatz. Jetzt `_felder_uebersetzen` + `_feld_rueckmeldung` in
`tools/profil.py`: deutsche Namen werden abgebildet (position,
ausbildung, projekt — aendern UND hinzufuegen), `geaenderte_felder`
nennt die geschriebenen Spalten, der Rest kommt als `ignorierte_felder`
samt `moegliche_felder` zurueck.

(3) **Der Melder hat den Befund zweimal geliefert.** Erst die Ursache
("laut Claude fehlen die Positions-IDs"), dann im Kommentar die zweite
("sieht so aus, als uebermittelt der MCP die Ids und/oder die Feld Namen
nicht alle korrekt"). Beides stimmte. Sein Workaround — Profil
exportieren und das JSON in den Chat — funktionierte, weil er damit
zufaellig die englischen Feldnamen bekam. **Wenn ein Workaround
funktioniert, sagt er einem, was am regulaeren Weg fehlt.**

(4) **Ein Guard gegen den Rueckfall, in die richtige Richtung gedreht:**
`test_994_jeder_ausgabename_ist_ein_gueltiger_eingabename` schickt die
Feldnamen, die `positionen_anzeigen` AUSGIBT, durch die
Uebersetzungsschicht der SCHREIBSEITE. Ein kuenftiges neues Feld in der
Auskunft faellt damit auf, bevor jemand vergeblich versucht, es
zurueckzuschreiben. Das ist die Antwort auf (1) auf Testebene: nicht der
Kommentar haelt die beiden Seiten zusammen, sondern ein Aufruf.

(5) **Kein neues Werkzeug fuer den Rest.** `positionen_anzeigen` benennt
zusaetzlich die leeren Felder je Position (`luecken`), weil ein CV
Aufgaben, Erfolge und Technologien fast nie vollstaendig nennt und genau
das die Arbeit ist, die der Melder machen wollte. Ein Befund, den nur
der Mensch selbst zusammensuchen muss, ist der halbe Befund — dasselbe
Argument wie #989 MERKE (1).

## Stand 2026-09-07 (v1.7.39 Stable) — Was nichts kostet, stand oben

**#989, das Architektur-Epic hinter #987/#965/#972/#988.** Wo eine
Information fehlt, setzt ein Punktesystem einen neutralen Wert ein — und
neutral heisst dort nicht "unbekannt", sondern "kostet nichts". Gemessen:
vollstaendig beschriebene, passende Stelle 32 Punkte, inhaltsleerer
Titel 101. **Tests: 2937 / 3003.**

MERKE-Punkte:

(1) **Der unangenehmste Satz des Issues:** *"Es gibt bereits
entfernung_guete, score_status, grund_guete ... Alle vier stehen in
Tool-Antworten. In der Trefferliste, die der Nutzer tatsaechlich
ansieht, kommt davon nichts an."* Die Bausteine mussten nicht gebaut
werden, sondern ankommen. **Ein Befund, den nur ein Werkzeug kennt, ist
kein Befund** — das ist DoD 8c fuer Auskuenfte statt fuer Guards. Der
Datenguete-Befund haengt deshalb an `stellen_anzeigen` UND an
`GET /api/jobs`, also an der Liste, die den Stellen-Tab speist.

(2) **`verletzt` und `ungeprueft` sehen im Score gleich aus.** Beide
bringen keine Punkte und bedeuten das Gegenteil voneinander. Deshalb
drei Zustaende statt zwei. Schoenstes Beispiel: ein GESCHAETZTES Gehalt
zaehlt seit #827 gar nicht — es galt damit implizit als "erfuellt
nicht", ist aber ungeprueft.

(3) **Den Score NICHT angefasst.** Er misst, was in der Anzeige steht;
das ist eine Messung. Die Rangfolge ist eine Darstellung, und dort zieht
sie die Konsequenz. Ein Update, das gespeicherte Zahlen still
umschreibt, waere derselbe Fehler wie #987 — nur diesmal absichtlich.

(4) **Eine Trennung, die alles trennt, trennt nichts.** Der Vorschlag im
Issue war, den Vollstaendigkeitsgrad in die Rangfolge einzurechnen. Ich
habe die Gruppe an EINER Dimension festgemacht (Anzeigentext): eine
unbekannte Entfernung ist alltaeglich, und wuerde sie die Gruppe
entscheiden, landete fast alles in Gruppe zwei. Ungenau bewertet ist
etwas anderes als gar nicht bewertet. Die uebrigen Dimensionen stehen
als Marke an der Zeile, nur eben nicht gruppenbildend.

(5) **Die Vorgabe ist bewusst nicht die strengste.** `streng` (unbekannte
Entfernung zaehlt wie eine zu grosse) ist eine NUTZERENTSCHEIDUNG, wie
das Issue sie beschreibt. Als Vorgabe waere sie ein erfundener Malus —
derselbe Fehler wie der erfundene Bonus, nur mit anderem Vorzeichen.
Weil `streng` im Score wirkt, geht die Einstellung durch das
Kriterien-Nadeloehr aus #987; sonst rechnete der Suchlauf wieder anders
als die Neuberechnung.

(6) **#966 hat halbiert, wo Null richtig gewesen waere.** Ein
Aussortier-Urteil an einer Anzeige von 23 Zeichen ist kein schwacher
Beleg, sondern keiner: drei solche Urteile ergeben halbiert immer noch
zwei Stimmen, und genau so entstand der gemeldete Dreifach-Wiedergaenger.
Die Abstufung bleibt trotzdem — eine geschaetzte Gehaltszahl zeigt in
eine Richtung, ein Anzeigen-Rumpf in gar keine. **Beim Nachschaerfen
einer Haertung fragen, ob "schwach" ueberhaupt die richtige Kategorie
war.**

(7) **Die 50 lag siebenmal im Code.** Dieselbe Schwelle, jedes Mal neu
getippt (jobs.py viermal, analyse.py, workspace_service.py,
database.py). Jetzt `datenguete.MIN_BESCHREIBUNG` — und gespiegelt in
`frontend/src/lib/datenguete.js` mit eigenem CI-Schritt, nach dem Muster
von #765 und #974.

(8) **Nebenbefund, nicht behoben:** `chrome.search_criteria` in
`JobsPage.jsx` existiert nicht — die Zeile liest ins Leere und faellt
auf 0 zurueck. Kein Schaden (die Schwelle wirkt serverseitig), aber ein
totes Feld.

## Stand 2026-09-07 (v1.7.38 Stable) — Zwei Wege, der schwaechere zuerst

**#991 — 962 Zuordnungsvorschlaege statt 8.** `analyse_plan_erstellen`
fuehrte eine ZWEITE, schwaechere Fassung der Frage "welches Dokument
gehoert zu welcher Bewerbung" neben `dokumente_ohne_bewerbung` (E20/
#797). **Tests: 2912 / 2978.**

MERKE-Punkte:

(1) **Fuenftes Mal dasselbe Muster — und diesmal andersherum.** Nach
#963 (fit_analyse gegen calculate_score), #913 (dismiss_job), #976
(aufgaben_uebersicht) und #987 (Score-Kriterien) lag hier wieder
dieselbe Frage zweimal im Code. Neu ist die Richtung: der schwaechere
Weg war ausgerechnet der, den die eigene Anleitung ZUERST empfiehlt.
Wer dem Plan folgte, bekam die schlechtere Antwort; die gute fand nur,
wer das andere Werkzeug kannte. **Beim Suchen nach Doppelungen zuerst
den Weg ansehen, den die Doku empfiehlt.**

(2) **Ein Firmenname im Fliesstext ist kein Verdachtsmoment.** Der Plan
suchte `LOWER(extracted_text) LIKE '%firma%'`. Der Name steht in jeder
Absage, jeder Signatur und in jedem Anschreiben, das die Firma nur
adressiert. Weil die Schleife zusaetzlich ueber ALLE Bewerbungen lief
und je Paar einen Eintrag erzeugte, entstand das Kreuzprodukt aus
Bewerbungen und Textvorkommen — daher tauchten dieselben Dokumente bei
mehreren Bewerbungen auf. Der Melder hatte das vermutet und als "nicht
verifiziert" markiert; es stimmte.

(3) **Eine Haertung darf ihren Gruendungsfall nicht mitnehmen.** Der
naheliegende Fix — Volltext ersatzlos streichen — haette #686 getoetet:
eine Mail mit nichtssagendem Dateinamen, deren Text die Firma nennt,
samt Alt-Test. Der Volltext bleibt deshalb ein Signal, aber nur fuer
Korrespondenz-Typen und nur bei GENAU EINEM Treffer, mit Konfidenz
`niedrig`. Die drei Alt-Tests zu #686 und #743 sind danach wieder
gruen — sie waren der Beleg, dass die Haertung nicht zu weit ging.

(4) **Eine Warnung an einem von zwei Wegen ist keine Warnung.** Der
Hinweis "Bewerbung bereits abgeschlossen" (#743) stand nur im Plan,
obwohl beide Wege dieselben Vorschlaege machen. Jetzt am Nadeloehr —
dasselbe Argument wie bei der Whitelist in #981.

(5) **Ein Vorschlag ohne Grenze ist auch eine Datenmenge.** 962
Eintraege kosten im MCP-Client Kontext, ohne etwas beizutragen (#635
hatte die Payload desselben Tools schon einmal reduziert). Jetzt 15,
mit Gesamtzahl daneben und Verweis aufs Detailwerkzeug.

## Stand 2026-09-07 (v1.7.37 Stable) — Eine Klammer

Der erste Fehlerbericht eines FREMDEN Anwenders (#990), und er wiegt
schwerer als alles andere an diesem Tag: **seit v1.7.0-beta.18 brach der
Installer ab, bevor er PBP in Claude Desktop eintrug.** Das Dashboard
lief, die Werkzeuge fehlten, das Fenster schloss sich ohne Meldung, und
ins Log kam nichts mehr. **Tests: 2898 / 2964.**

**Die Ursache ist ein einziges Zeichen.** Eine unescapte `)` in einem
`echo` INNERHALB eines Klammerblocks beendet den Block genau dort; der
Zeilenrest wird zur naechsten Anweisung, `cmd` meldet einen Syntaxfehler
und bricht ab. Am laufenden `cmd.exe` reproduziert und in beide
Richtungen gemessen.

MERKE-Punkte:

(1) **Ein Klammerpaar ist in cmd nicht ausbalanciert.** `cmd` zaehlt die
OEFFNENDE Klammer in einem `echo` nicht mit, die SCHLIESSENDE aber
schon. Auch `echo (alles in einer Zeile).` bricht ab. Ich habe zuerst
gegenteilig argumentiert — der Test hat es widerlegt. **Bei
cmd-Parserfragen messen, nicht schliessen.**

(2) **Der Fehler traf ausgerechnet die Sorgfaeltigen.** Getroffen wurde
der letzte Schritt: der Eintrag in Claude Desktop. Alles davor war
fertig, also lief das Dashboard — und der Nutzer sah einen halb
installierten Zustand ohne jede Fehlermeldung. Neun Fundstellen in drei
Dateien, darunter der Deinstaller (moeglicher Teilbeitrag zu #739, dort
liegt der gemeldete Abbruch aber frueher). Jetzt
`tests/test_v1737_batch_klammern_990.py` ueber ALLE `.bat`-Dateien.

(3) **Ein Melder kann die halbe Arbeit machen — und die Luecke, die
er offen laesst, ist der eigentliche Fund.** Der Anwender hat die
MSIX-Ursache vollstaendig analysiert (Store-Claude liegt ACL-geschuetzt
unter `WindowsApps`, steht nicht im PATH, und
`%LOCALAPPDATA%\Packages\Claude_*` enthaelt nur Anwendungsdaten —
die #361-Erkennung suchte an der richtigen Stelle nach der falschen
Sache) und ausdruecklich geschrieben, den Abbruch nicht klaeren zu
koennen. Genau der war die Ursache des gemeldeten Symptoms. **Den offen
gelassenen Rest eines guten Berichts zuerst ansehen.**

(4) **Zwei cmd-Fallen beim MSIX-Fix, beide gemessen.** Ein `^|` im
Backtick-Kommando von `for /f` kommt in der Subshell NICHT als Pipe an
— die Abfrage lieferte still eine leere Zeichenkette, also wieder
ein Fehler, der wie ein normaler Zustand aussieht. Und das `!` in
`shell:AppsFolder\<Paket>!Claude` haette bei `EnableDelayedExpansion`
als Variablenklammer gegolten und waere verschwunden; PowerShell setzt
es jetzt selbst zusammen (`[char]33`).

(5) **Negativbefund, dokumentiert damit ihn niemand nachmisst:** LF-
Zeilenenden im ZIP waren es NICHT. `git archive` wendet die
`eol=crlf`-Regel aus `.gitattributes` an; das heruntergeladene ZIP
traegt CRLF. Am Byte geprueft.

## Stand 2026-09-07 (v1.7.36 Stable) — Die Liste stand auf dem Kopf

Zwei Befunde aus EINER Jobsuche, beide von derselben Art: PBP hat nicht
falsch gerechnet, sondern **mit den falschen Zahlen** gerechnet. Kein
Fehler, keine Meldung, eine plausibel sortierte Liste — und oben stand,
worueber PBP am wenigsten wusste. **Tests: 2883 / 2949.**

**#987 — der gespeicherte Score war reproduzierbar falsch.** 86 von 86
Stellen eines Laufs zu hoch, im Schnitt um 47 Punkte, im Maximum um 105.
`fit_analyse` ergab mit denselben Kriterien 0. Zwei Ursachen, die erst
zusammen den vollen Schaden ergeben:

(1) **Die Kriterien lagen doppelt.** Der Suchlauf reicherte sie an
(`_applied_titles`, `_muss_synonyme`), `scores_neu_berechnen` und
`fit_analyse` nahmen sie roh. Damit war der gespeicherte Score von
keinem anderen Werkzeug nachzurechnen. MERKE: das ist zum VIERTEN Mal
dasselbe Muster (#963 fit_analyse/calculate_score, #913 dismiss_job,
#976 aufgaben_uebersicht) — aber eine Ebene tiefer. **Nicht die Rechnung
lag doppelt, sondern ihre Eingabe.** Ein Nadeloehr fuer die Logik nuetzt
nichts, wenn jeder Aufrufer ihr etwas anderes hineinreicht. Neu
`services/scoring_kriterien.py`.

(2) **Die Anreicherung selbst war falsch, und das ist der teurere
Befund.** Die Berufs-Facette (#969) beantwortet "wer arbeitet damit",
nicht "wie heisst das noch" — und nur wenn der Suchbegriff SELBST ein
Beruf ist, sind das dieselbe Frage. Live gemessen: zu "PLM" nennt sie
IT-Berater, Ingenieur/in - Maschinenbau, Ingenieur/in - Elektrotechnik,
Informatiker/in, Konstrukteur/in. Als MUSS-Synonyme oeffnete damit jede
Ingenieursanzeige das Tor. MERKE: **eine Datenquelle beantwortet ihre
eigene Frage, nicht deine.** Die Annahme "Facette = Synonymliste" stand
nirgends geschrieben und war der ganze Mechanismus.

MERKE-Punkte dieser Welle:

(1) **Ein Fragment ist gefaehrlicher als ein Unwort — auch das ganze
Wort ist ein Fragment.** `_formen` zerlegte die amtliche Bezeichnung an
Leerzeichen: aus "Ingenieur/in - Elektrotechnik" wurden "Ingenieur",
"Ingenieurin" UND "Elektrotechnik". Der Docstring der ersten Fassung
warnte bereits vor Fragmenten ("Gesundheits" traefe jedes Kompositum) —
die Warnung galt nur dem Kompositum-Vorderteil, nicht dem abgetrennten
ganzen Wort, das ein ganzes Berufsfeld benennt. Jetzt wird nur die
SCHREIBWEISE zerlegt (Schraegstrich-Formen), nie die Bezeichnung; die
Fachrichtung hinter " - " faellt weg. Ausnahme mit Ansage: bei einer
Koordination ("Gesundheits- und Krankenpfleger/in") ist das letzte Glied
ein vollstaendiger Berufsname und darf allein stehen.

(2) **Zwei Tore, gemessen statt geschaetzt.** Die Schwelle
`MIN_SPITZENANTEIL = 0.15` steht nicht aus dem Bauch da: gemessen am
07.09. liegen Berufe bei 18–39 % (Elektroniker 18, Pflegefachkraft 20,
Maschinenbauingenieur 36, Erzieherin 39), Technologien und Sachen bei
10–13 %. Die Schwelle liegt bewusst UNTER dem tiefsten gemessenen Beruf:
eine fehlende Alternativbezeichnung ist das Verhalten von vor #969 und
damit harmlos, eine falsche kippt die ganze Liste.

(3) **Ein Score darf nicht am Netz haengen.** Die Alternativbezeichnungen
kommen aus einer Netzabfrage. Waeren sie live geholt worden, haette
dieselbe Stelle online einen anderen Wert als offline. Sie liegen jetzt
in `profile_settings`; die Regel dazu lautet **wer schreibt, frischt
auf; wer liest, nimmt den abgelegten Stand** — ein Lesewerkzeug hat
keine Nebenwirkung (#963). Und: ein LEERES Ergebnis wird nie ueber einen
vorhandenen Stand geschrieben, weil "nichts gefunden" und "nicht
erreichbar" von aussen gleich aussehen.

(4) **Ein Frueh-Ausstieg laesst Altwerte stehen.** `calculate_score`
setzte die Teilscores erst am regulaeren Ende; bei jedem K.o. blieb der
ALTE Fachscore neben dem neuen Gesamtscore stehen ("fachscore 56 gegen
score 1"). Verwandt mit MERKE (3) aus v1.7.24 — dort kuerzte ein
Frueh-Ausstieg die Auskunft, hier laesst er sie veralten.

(5) **Ein Hinweis, der die Ursache ausschliesst, ist schlimmer als
keiner.** `score_abweichung` sagte "meist ist der gespeicherte Wert
aelter als die Kriterien" — ueber einer Stelle, die am SELBEN TAG
angelegt worden war. Der Text hat den Befund aktiv wegerklaert. Jetzt
wird der Fall benannt.

**#988 — der Wunschwert wirkte nicht.** In den Suchkriterien standen
30 km, gerechnet wurde gegen die Reglerstufe 999 km; weil die oberste
Stufe ein Deckel war, kostete 577 km genau so viel wie 87 km. Jenseits
von 999 km traf sogar GAR KEINE Stufe mehr — 1200 km kosteten null.
Diesen zweiten Teil hat kein Mensch gemeldet, sondern der Test beim
Schreiben gefunden. Der Preis waechst jetzt je Verdopplung ueber dem
Wunschwert um einen Punkt, gedeckelt (Entfernung ist ein PREIS, kein
Ausschluss, #910).

(6) **Zwei Einstellungen fuer dieselbe Sache, von denen nur eine wirkt,
sind eine Fehlerquelle — eine, die GAR NICHTS tut, ist schlimmer.**
Unter `schwellenwert` stand neben dem gelesenen `auto_ignore` ein
zweiter Regler mit dem Wert 35, ungeprueft ueber
`scoring_konfigurieren('setzen', ...)` angelegt. Der Nutzer glaubte,
seine Schwelle liege bei 35; sie lag bei 0. **Das ist #981 in einer
anderen Tabelle** (dort ein Status ausserhalb der Whitelist, hier ein
Regler ausserhalb des Vokabulars) — und beide Male entsteht kein Fehler,
sondern eine Einstellung ohne Wirkung, der man glaubt. Neu
`services/scoring_vokabular.py`; bestehende wirkungslose Zeilen werden
in der Anzeige BENANNT statt geloescht.

**Offen als #989 (Architektur-Epic, vom Nutzer angelegt):** das
gemeinsame Muster hinter #987, #965 und #972 — **fehlende Information
wirkt wie Unauffaelligkeit statt als Luecke.** Wo ein Wert fehlt, setzt
PBP neutral ein und rechnet weiter; neutral heisst in einem Punktesystem
aber nicht "unbekannt", sondern "kostet nichts" — und was nichts kostet,
steigt in der Sortierung. Das ist die naechste grosse Arbeit.

## Stand 2026-09-07 (v1.7.35 Stable) — Dein Dashboard

Der Nutzer hat den fertig aufgeraeumten Bildschirm angesehen und die
naechste Frage gestellt: **warum ist er fuer alle gleich?** Daraus #985.
Dazu drei Nachzuegler, die lange genug lagen. **Tests: 2844 / 2908
(Stable / Beta). Schema v48 / v52 unveraendert.**

**#985 — das Dashboard gehoert dem Nutzer.** Bereiche an- und
abschalten, sortieren, einklappen; Zustand in `profile_settings`, also
am Profil und nicht im Browser. Voreinstellung "Offen" und
"Schnellzugriff"; `offen` traegt `fest=True`. `services/
dashboard_bereiche.py` ist der Katalog, `_zusammenfuehren` haengt neue
Bereiche ans Ende und laesst entfernte still herausfallen — dasselbe
Muster wie `prompt_katalog.py` (#979): **der Katalog gibt die
Voreinstellung, der Mensch weicht ab.** Sortierung ueber Pfeile, bewusst
kein Drag-and-drop (acht Eintraege, Handy-Bedienbarkeit).

MERKE-Punkte dieser Welle:

(1) **Gebaute Assets sind ein PAAR, und ein 404 darauf ist stumm.**
Beim Port auf die Stable-Linie uebernahm die `index.html` den
Stylesheet-Namen von main, der Assets-Ordner behielt die Datei von
Stable. Der Verweis lief ins Leere — die Seite laedt, React rendert,
alle Texte stehen da, der Server meldet nichts, und **gestaltet ist gar
nichts**. Gefunden hat es allein
`test_dashboard_mobile_layout_has_no_horizontal_overflow`, und zwar
ueber ein Logo, das ohne CSS in seiner Naturbreite von 1024 px stand.
Ein Browser-Test mit laufendem Server und Mobil-Viewport fuer eine
Frage, die man am Dateinamen beantworten kann. Jetzt
`tests/test_v1735_gebaute_assets.py` (auf BEIDEN Linien): referenzierte
Dateien existieren, keine verwaisten Reste, genau ein Stylesheet. Die
Cherry-Pick-Regel aus v1.7.24 MERKE (6) bleibt richtig — neu bauen
statt auswaehlen —, sie war nur nicht abgesichert.

(2) **Ein `git pull` in einer Pipe kann nicht fehlschlagen.** Der
Wiki-Commit lief trotz `error: cannot pull with rebase` durch, weil die
Kette `git pull --rebase 2>&1 | tail -2 && git add -A && git commit`
lautete: der Exit-Code einer Pipe ist der des LETZTEN Glieds, also von
`tail`. Genau die Verkettung, vor der die Wiki-Clone-Regel warnt — sie
sah nur aus, als waere sie eingehalten. Ausgegangen ist es gut (die
Gegenseite war unveraendert, Fast-Forward), aber der Schutz war
wirkungslos. **Bei Sicherheitsketten das Kommando nie durch eine Pipe
fuehren.**

(3) **Ein Cherry-Pick ohne Gegenstueck gehoert uebersprungen — nach
dem Lesen beider Seiten.** `088e476` korrigierte einen Zeilenumbruch in
der `ocr_info`-Fassung des Office-Zweigs. Diese Fassung gibt es auf der
1.7-Linie nicht (kein OCR, Zweier-Tupel, Grund ueber `format_befund`).
Der Konflikt war also kein Konflikt, sondern die richtige Antwort. Das
ist die Ausnahme zur v1.7.12-Lehre "NIE `--skip` als Fallback": `--skip`
als GEPRUEFTE Entscheidung ist etwas anderes als `--skip` in einer
Aufloesungsschleife.

(4) **#972 — dreimal nachgebessert heisst: weg, nicht haerten.** Die
Hochschulabschluss-Pruefung hatte drei Anlaeufe (#698 Malus, #918
Phrasen-Muster, #955 Zielgruppen-Erkennung) und unterschied "Abschluss
gefordert" von "Studium als Zielgruppe" weiterhin nicht zuverlaessig;
in der Praxis wertete sie mehr passende Stellen ab als unpassende. Der
Ablehnungsgrund `kein_hochschulabschluss` BLEIBT — er beschreibt eine
Entscheidung des Menschen und steht in Altdaten; ihn zu entfernen
wuerde die Statistik ruecklaufend verfaelschen. **Beim Rueckbau eines
Mechanismus trennen: die Automatik geht, das Vokabular bleibt.**

(5) **#833 — die Stille war der Befund, nicht das Format.** Alles
ausserhalb der bekannten Zweige fiel durch den `else`-Zweig mit leerem
Text und `status: "ok"`; ein Dokument, das nichts liefert, war von
einem, das nichts enthaelt, nicht zu unterscheiden. Neu
`services/office_text.py`, bewusst stdlib-only (zipfile + ElementTree)
— `python-pptx` steht nicht in `pyproject.toml`, und eine
Abhaengigkeit fuer eine ZIP-Datei mit XML darin ist
unverhaeltnismaessig. `.ppt`/`.xls` bekommen eine ehrliche Absage.

(6) **#975 — der gefaehrlichste Rueckfall ist der bequeme.** Meine
erste Fassung suchte die `DEINSTALLIEREN.bat` notfalls im
Repo-Wurzelverzeichnis. Diese Kopie entfernt
`%LOCALAPPDATA%\BewerbungsAssistent` — aus einem Entwickler-Checkout
haette der Knopf also die INSTALLIERTE Version des Nutzers abgeraeumt,
waehrend die Karte etwas anderes anzeigt. Ein Test hat es gefangen. Der
Rueckfall ist ersatzlos weg: **"nicht gefunden" melden ist besser als
das Falsche treffen.**

(7) **README-Drift auf main, zum zweiten Mal.** Der README-Kopf auf
main stand auf v1.7.30, also fuenf Releases zurueck — dasselbe Bild
wie am 2026-08-19, das damals das README-Gate ausgeloest hat. Das Gate
greift: auf der Stable-Linie ist es ein Fehler, auf main nur eine
Warnung, und Warnungen driften. **Die sichtbare Seite des Projekts ist
main, nicht die Release-Linie.**

## Stand 2026-09-07 (v1.7.31 Stable) — Eine Information, ein Ort

Ein externer Design-Review vom 05./06.09. lieferte zwei Screenshots und
drei Saetze Kritik; die Pruefung am Code ergab sieben Befunde an EINEM
Bildschirm (Epic #978). Dazu ein Praxisfund aus derselben Durchsicht,
der schwerer wiegt als alle sieben zusammen. **Tests: 2770 / 2836.
Schema v48 / v52 unveraendert. MCP-Tools 206 / 219.**

**#980 zuerst, weil er Daten betrifft.** Der Aufgaben-Tab rief zwei
Routen, die es nicht gibt. `.../reschedule` liess das Verschieben einer
Nachfassung seit v1.7.12 in HTTP 404 enden — sichtbar, aber harmlos.
`.../obsolete` dagegen hatte einen `catch`-Fallback auf `.../complete`:
wer "hinfaellig" anklickte, speicherte **"erledigt"**. Keine
Fehlermeldung, falscher Datensatz, und die Zeile zaehlte seitdem in den
Reaktionszeiten (D29) als durchgefuehrte Nachfassung. MERKE: **ein
Fallback, der eine andere Bedeutung speichert, ist keine
Fehlertoleranz.** Kein Rueckbau moeglich (die Datensaetze tragen kein
Herkunftsfeld) — `pbp_diagnose` listet Verdachtsfaelle, ausdruecklich
ohne `auto_fix` und mit der Grenze im Text.

**Die Wurzel war eine fehlende Kontrolle, nicht Unachtsamkeit.** Das
Frontend nennt API-Pfade als Zeichenketten, und nichts vergleicht sie
mit `app.routes`. Fuer Tab-IDs (G19/#846) und Status-Werte (G20/#896)
gibt es genau solche Guards; fuer Routen fehlte er. Jetzt
`tests/test_frontend_api_paritaet_980.py`.

MERKE-Punkte zur Arbeitsweise:

(1) **Ein Kommentar haelt nichts zusammen — zum dritten Mal.** Die
Aggregation der drei Aufgaben-Toepfe stand ZWEIMAL im Code (MCP-Tool und
REST-Endpunkt), verbunden nur durch den Satz "dieselbe Logik wie das
MCP-Tool aufgaben_uebersicht". Er stimmte bereits nicht mehr: der eine
Weg kannte `ueberholt`/`notiz`, der andere `erledigen_mit`. Nach
`fit_analyse` gegen `calculate_score` (#963, fuenfmal derselbe
Kommentar) und `db.dismiss_job` (#913) ist das die dritte Runde. Neu
`services/aufgaben_sicht.py` als Nadeloehr. **Wo zwei Wege denselben
Wert erzeugen, gehoert ein Aufruf hin, kein Hinweis.**

(2) **Ein Alt-Test kann den Fehler festhalten statt ihn zu finden.**
`test_weekend_has_highest_priority` stand mit `follow_ups_due=3` und der
Erwartung "weekend" im Repo — genau das Verhalten, das #977 als falsch
meldet. Beim Aendern eines Verhaltens den roten Alt-Test LESEN, bevor
man ihn anpasst: er kann die Spezifikation sein oder der Fehler.

(3) **Ein Waechter darf nicht mehr behaupten, als er kann.** Meine erste
Fassung des #984-Guards nutzte Wortueberschneidung mit Schwellwert und
wies damit den AUSLOESENDEN Fall als "ergaenzt" ab: "Es gibt
ueberfaellige Nachfassaktionen." und "Einige Bewerbungen warten auf
deine Rueckmeldung" teilen kein einziges Wort und sind dieselbe Aussage.
Kein lexikalischer Vergleich findet das. Die Funktion heisst jetzt
`beschreibungWiederholtWoertlich` und der Fall wird geloest, indem das
FELD verschwindet. Umgekehrt war die im Issue vorgeschlagene
Teilstring-Regel fuer das Etikett zu schwach: "Nachfassen" steckt nicht
in "Nachfassaktionen" — der Guard haette seinen eigenen Gruendungsfall
durchgelassen. Jetzt ueber den Wortstamm.

(4) **Beim Bauen eines Paritaets-Guards zuerst die Fehlalarme klaeren.**
Meine erste Fassung meldete fuenf Treffer: einer war ein Parser-Artefakt
(die Regex hoerte am `?` eines Ternaers im Template-String auf), vier
waren Fehlalarme, weil ein Frontend-Literal auf einen Server-Parameter
trifft (`/api/workflow-prompt/interview_vorbereitung` gegen
`{workflow_name}`). Ich habe gegengeprueft, dass alle vier Routen
wirklich existieren — sonst haette die Lockerung den Waechter blind
gemacht statt geschaerft.

(5) **Platzhalter werden im Deutschen ZUSAMMENGESETZT.** Der PII-Pruefer
kannte "muster" als Kopfwort, nicht "Musterbetrieb" — dieselbe Lehre wie
#962 und #970. Praefix-Regel jetzt fuer `muster`/`beispiel`/
`platzhalter`, BEWUSST nicht fuer `test` und `demo`: es gibt reale
Firmen, deren Name mit "Test..." beginnt, und ein Pruefer, der reale
Namen durchwinkt, ist schlimmer als keiner (#929).

(6) **Zwei eigene Kommentare haben eigene Tests rot gemacht.** Ein Test,
der prueft, dass eine falsche Route WEG ist, schlaegt an der Erklaerung
an, warum sie weg ist. Solche Tests auf die DEFINITION pruefen
(`const interviewPseudoMeetings`) oder Kommentarzeilen vorher
herausfiltern.

(7) **Beim Cherry-Pick den Installationsblock pruefen.** Ich habe den
Pflicht-Block aus dem CHANGELOG auf `main` extrahiert und auf der
Stable-Linie eingefuegt — er trug die Versionsnummer der Beta-Linie
(v1.7.18). Der Download-Link haette die falsche Version installiert.
Nach dem Einfuegen `grep` auf die neue Versionsnummer.

(8) **Der Farbklassen-Guard G24 hat direkt gegriffen.** Mein erster
Entwurf des neuen Blocks trug `text-violet` — ein Token, das es nicht
gibt; Tailwind erzeugt dafuer keine Regel UND keinen Fehler.

Dazu ein Test mit Verfallsdatum gefunden und behoben:
`test_825_vergangener_termin_ohne_teilnehmer_und_reflexion` nutzte das
feste Datum 2026-08-05 und fiel am 04.09. aus dem 30-Tage-Fenster der
Reflexions-Pruefung — von allein rot, ohne Codeaenderung. Dritter Fall
dieser Art nach `test_782` und #767.

**Das Epic ist abgeschlossen** — vier Releases an einem Tag:

* **v1.7.32 / D43 (#981)** — der Dialog im Stellen-Tab bot `entwurf` an,
  einen Status ausserhalb der Whitelist, und `POST /api/applications`
  schrieb ihn ungeprueft durch. MERKE: `VALID_STATUSES` lag als LOKALE
  Variable in `bewerbung_status_aendern` und konnte damit genau ein Tool
  schuetzen. **Eine Whitelist an einer von mehreren Schreibstellen ist
  keine Whitelist.** Dazu ein Guard ueber die Inline-`<option>`-Listen
  der Seiten — G20/#896 las nur `utils.js`, und genau dort ist der Wert
  ueberlebt.
* **v1.7.33 / G29 (#979)** — Prompt-Katalog als einzige Quelle. Es waren
  nicht vier Quellen, sondern fuenf: `prompts.py` trug eine zweite
  Fassung des `bewerbung_schreiben`-TEXTES, die bereits abgewichen war.
* **v1.7.34** — zwei Layout-Fehler, die erst der erneuerte Screenshot
  zeigte (siehe MERKE 9 und 10).

(9) **Ein gerendertes Bild ist eine eigene Pruefung.** Drei Karten im
oberen Dashboard-Block waren 1035 px breit in einem 961 px breiten
Container und liefen rechts aus dem Fenster. Ursache: ein `grid` ohne
explizite Spalte gibt jedem Item `min-width: auto`, damit kann es nicht
unter seine Mindestbreite schrumpfen — `grid-cols-1` ist
`repeat(1, minmax(0, 1fr))` und erlaubt es. Der Fehler war AELTER als
der neue Block (Readiness-Karte und Tagesimpuls hatten ihn auch) und im
Browser kaum zu bemerken, weil der Ueberhang abgeschnitten wird. Kein
Test und kein Code-Review haette ihn gefunden.

(10) **Zwei Issues koennen sich gegenseitig einen Fehler bauen.** #982
gab der Vorbereitungszeile das TERMINDATUM; #983 entschied danach, die
Termine in denselben Block zu nehmen. Ergebnis: "Vorbereiten: X" stand
direkt ueber "X" — genau die Doppelung, gegen die das Epic angetreten
war. Keines der beiden Issues war fuer sich falsch. Bei Epics mit
Sub-Issues, die dasselbe Bild bauen, gehoert das Ergebnis am Ende
EINMAL angesehen, nicht nur je Issue abgehakt.

(11) **Sieben Tests bestanden nur an einer Stelle.** Sie lasen Dateien
ueber RELATIVE Pfade und warfen aus einem fremden Arbeitsverzeichnis
`FileNotFoundError` (gemessen: 2 von 5 rot in einer Datei). Das ist DoD
8c woertlich. Jetzt ueber einen `_repo()`-Helfer.

## Stand 2026-09-02 (v1.7.24 Stable) — Fehler, die wie Erfolg aussehen

Sieben Praxis-Befunde vom 28.08. und 02.09. Roter Faden: **keiner davon
hat je eine Fehlermeldung erzeugt.** Eine fehlende Farbe, eine
unbekannte Entfernung, ein falsch abgelegtes Stellenangebot — alles sah
aus wie ein normaler Zustand. **Tests: 2563 / 2565 (Stable), 2629 /
2631 (Beta). MCP-Tools: 206 / 219.**

**#963 — die lehrreichste Ursache, weil sie meine eigene war.** Das
MUSS-Tor (#940) und der Rahmen-Deckel (#942) sassen NUR in
`calculate_score`, nicht in `fit_analyse`. Gemessene Divergenz bis zu
6 Punkten auf 21; welcher Wert in der Liste stand, hing davon ab,
welches Tool zuletzt lief. MERKE: **eine Regel in einen von zwei
parallelen Rechenwegen einzubauen verschiebt die Divergenz nur.**
`fit_analyse` trug den Kommentar "dieselbe Logik wie calculate_score"
FUENFMAL (#762, #778, #827, #910, #917) — jedes Mal hatte ein Issue
einen Zweig nachtraeglich wieder angeglichen. Ein Kommentar haelt
nichts zusammen; jetzt tut es ein Guard-Test ueber zehn Faelle.
Ausserdem schrieb `fit_analyse` den Score als NEBENWIRKUNG (#539) — wer
sich eine Stelle nur genauer ansah, verschob ihre Position in der
Liste. Ein Lesewerkzeug schreibt jetzt nur noch auf Ansage.

**#964 — Tailwind meldet unbekannte Farben nicht.** Das Overlay im
Aufgaben-Tab trug `bg-bg`; das Token gibt es nicht, also erzeugte
Tailwind keine Regel UND keinen Fehler. Der Build war gruen, die
Klasse stand im HTML, und sie tat nichts. Ein Guard ueber das ganze
Frontend fand 47 weitere Stellen in neun Dateien — darunter die
Fehlermeldungen mehrerer Seiten. MERKE: Projekt-Tokens sind FLACHE
Farben; sobald `amber` in `extend.colors` eine Zeichenkette ist,
verdraengt es Tailwinds Abstufungen, und `bg-amber-400` loest ebenfalls
ins Leere auf. Am gebauten CSS gegengeprueft, nicht vermutet.

**#965 — unbekannt wirkte wie nah.** Von vier aktiven Stellen trug
genau eine keine Entfernung: die weiteste (~230 km). Weil
`if dist is not None:` sie schlicht uebersprang, entfiel ihr Malus und
sie stand mit dem hoechsten Score oben. MERKE: **ein stiller Bonus fuer
schlechte Datenqualitaet ist das Gegenteil dessen, was ein Scoring
leisten soll.** Ausloeser war ein Klammerzusatz im Ortsstring, an dem
das Geocoding scheiterte. Dazu am Nadeloehr `save_jobs`: HTML-Entities
werden aufgeloest — ein Titel mit `&amp;` wird von keinem Keyword mit
Und-Zeichen gefunden, der Fehler wirkte also im Scoring.

**#961 — der teuerste Ausfallmodus.** Eine Recruiter-Mail mit
vollstaendiger Stellenbeschreibung lag als `sonstiges`, und `sonstiges`
stand in der Korrespondenz-Whitelist von
`dokumente_korrespondenz_abschliessen`. Sie waere sammelweise auf
`angewendet` gesetzt worden: aus dem Analyse-Plan verschwunden, als
erledigt gefuehrt, ohne dass je eine Stelle entsteht. MERKE: die
Typ-Erkennung arbeitet fast nur am DATEINAMEN — der Text wird geladen,
aber nur gegen feste Formulierungen geprueft. Jetzt zusaetzlich an der
STRUKTUR (Rollenbezeichnung plus zwei Ausschreibungs-Merkmale);
Formulierungen aendern sich je Absender, die Struktur nicht.

**#966 — ein Urteil wog mehr als seine Grundlage.** Zwei
Aussortierungen wegen `gehalt_zu_niedrig`, beide an Anzeigen-Rumpfen
von rund 160 Zeichen und auf Basis GESCHAETZTER Spannen, werteten die
vollstaendige Anzeige derselben Rolle ab. #827 hatte die Regel
(geschaetztes Gehalt zaehlt neutral) bereits gezogen — sie wirkte nur
nach vorn. Schwache Gruende zaehlen jetzt halb.

MERKE-Punkte zur Arbeitsweise:

(1) **Positivliste statt Sperrliste, zum zweiten Mal.** #963 Befund 2
und #962 haben dieselbe Wurzel: im Deutschen ist JEDES Substantiv
grossgeschrieben, also nimmt "jedes grossgeschriebene Wort" den ganzen
Fliesstext mit. Eine Sperrliste deutscher Alltagswoerter wird nie
fertig. Bei #962 traegt ausserdem Grossschreibung ALLEIN nicht — das
unterscheidende Merkmal ist der Artikel davor ("die Feder im
Mechanismus" vs. "bei Feder"). Der im Issue vorgeschlagene Fix waere
also nur halb richtig gewesen; Vorschlaege aus Issues gehoeren
geprueft, nicht uebernommen.

(2) **Beim Haerten von Regeln beide Richtungen messen.** Bei #966 war
meine erste Liste textabhaengiger Gruende zu breit (`zeitarbeit`,
`befristet`) — zehn Alt-Tests wurden rot, weil der Mechanismus
verstummte. Zeitarbeit erkennt man an Firma und Titel, nicht am
Fliesstext. Und: ein FEHLENDES Feld ist "unbekannt", nicht "schwach" —
sonst begeht die Haertung genau den Fehler, den #965 behebt.

(3) **Ein Frueh-Ausstieg kuerzt die Auskunft.** Meine erste Fassung des
MUSS-Tors in `fit_analyse` gab ein verkuerztes dict zurueck; zwei
#952-Tests brachen an fehlenden Feldern. Ein Tor soll den Score nullen,
nicht die Antwort abschneiden.

(4) **Heredoc-Escaping unter Git-Bash (Windows).** Mehrfach wurden
doppelte Backslashes in Patch-Skripten zu einem literalen Backspace
bzw. Zeilenumbruch — einmal in einer kompilierten Regex, die daraufhin
still NICHTS mehr matchte, und zweimal in einem f-String, der dadurch
gar nicht mehr parste. Bei Regex- oder String-Literalen in
Patch-Skripten `chr(92)` verwenden oder direkt mit dem Edit-Werkzeug
arbeiten; danach `git diff` lesen statt dem Skript zu glauben.

(5) **Erst pruefen, ob der Branch den Fix enthaelt.** PR #959 meldete
rot wegen `test_782` — dem Test mit Verfallsdatum, der auf main
laengst behoben war. Der Branch war nur veraltet, es gab keinen Fehler
zu suchen.

(6) **Cherry-Pick-Konflikte in gebauten Assets sind keine.** Beim Port
in die 1.7-Linie kollidierten nur Hash-Dateien und ein 1.8-only-Block
(Erweiterungen-Tab). Aufloesung: Stables Fassung nehmen, das Frontend
NEU BAUEN, und den Guard-Test laufen lassen — der beweist, dass beim
Aufloesen nichts verlorenging. Das ist die praktikable Fassung der
Cherry-Pick-Lehre aus v1.7.12 (verlorene Hunks findet man ueber die
mitgewanderten Tests).

## Stand 2026-08-25 (v1.7.23 Stable) — Ehrliche Zahlen

Sieben Praxis-Befunde. Roter Faden: PBP behauptete Dinge, die die Daten
nicht hergaben. **Tests: 2489 / 2555.**

**#952 — die teuerste Ursache.** Der Anzeigentext wurde in JEDEM der 26
Adapter bei exakt 2000 Zeichen gekappt GESPEICHERT (38 Stellen, drei
davon in Browser-JS). Die Grenze sass in der Ablage statt in der
Ausgabe. Getroffen hat das systematisch den Anforderungsteil am Ende.
MERKE: `fetch_description_from_detail` hatte `max_chars=2000` als
DEFAULT — damit kappte ausgerechnet der Refetch, der duenne
Beschreibungen heilen soll (#622/#756 liefen deshalb ins Leere), und
`set_description_snapshot_if_empty` zementierte den halben Text als
unveraenderlichen Snapshot.

**#943/#944 — dasselbe Artefakt, zwei Befunde.** Bei rekonstruierten
Altbewerbungen stehen Bewerbungs- und Absagedatum am selben Tag.
Daraus folgte (a) "automatische Ablehnung" zu 81 % falsch befuellt (die
Kategorie entstand ALLEIN aus dem Zeitabstand) und (b) ein Median
"Zeit bis erste Reaktion" von 0,0 Tagen. MERKE: Der Ausschluss gehoert
auf den NULL-ABSTAND, nicht pauschal auf "wenige Events" — eine echte
Absage nach zwei Tagen hat oft nur zwei Ereignisse und ist gueltig.

**#944 — die drei Ablehnungszahlen.** `get_rejection_patterns` machte
einen LEFT JOIN auf `application_events` und zaehlte ZEILEN. Eine
Bewerbung mit zwei 'abgelehnt'-Ereignissen zaehlte doppelt: 60 in der
Statusverteilung, 64 im Fliesstext. MERKE bei JOIN-Zaehlungen immer
fragen, ob die Kardinalitaet stimmt.

**#924 — Regeln gehoeren ans Nadeloehr.** `pick_line` hatte die
Sperrfrist korrekt; mehrere Pfade (Wiki-Hints, Provider, Claude)
schreiben aber DIREKT. Die Sperre sitzt jetzt in
`db.add_elwosa_message` — dasselbe Muster wie `dismiss_job` (#913).

MERKE-Punkte zur Arbeitsweise:

(1) **Gegenproben decken Ueberschiessen auf, Nachdenken nicht.** Bei
#955 meldete die erste Fassung zwei von fuenf Studierenden-Anzeigen
faelschlich als abschlusspflichtig — dort ist "Studium" die
ZIELGRUPPE. Bei #941 haetten Freitext-Gruende (`zu "hands-on"`) und
`bewerbung_erstellt` (23x!) die BESTBEWERTETE Stelle automatisch
aussortiert; `bewerbung_erstellt` ist das GEGENTEIL eines
Ablehnungsgrundes. Automatik nur auf einer expliziten Positivliste
echter Eignungs-Urteile.

(2) **Branch vor dem Commit pruefen.** Sieben Commits landeten auf
einem Feature-Branch statt auf main; `git push origin main` meldete
Erfolg und uebertrug nichts. `git branch --show-current` vor der
Arbeit, nicht erst beim Release.

(3) **Tests mit Verfallsdatum.** `test_782` nutzte ein festes
"frisches" Datum, das 29 Tage spaeter selbst unter die 30-Tage-Schwelle
fiel. Datumsangaben in Tests immer relativ zu heute.

(4) **Fehlalarme sind teurer als sie aussehen.** Der PII-Repo-Scan war
unbenutzbar, weil er bei jedem Testdatensatz anschlug. Platzhalter
werden jetzt STRUKTURELL am Kopfwort erkannt: "Alt GmbH" ist ein
Platzhalter, ein realer Firmenname mit demselben Wortanfang bleibt ein
Treffer.

## Stand 2026-08-19 (v1.7.21 Stable + beta.14) — Der Pruefer war blind

**#929** — `scrub_pii.py` UND der blockierende `gh_pii_guard.py` lasen
ihre Eingabe mit `sys.stdin.read()`, also unter Windows als **cp1252**.
Jeder Text mit Umlauten kam verstuemmelt an und passte auf KEIN
Erkennungsmuster mehr: ein Firmenname mit Umlaut wurde durchgewunken,
der Pruefer meldete "sauber". MERKE: **Falsch-negativ in einem
Schutzwerkzeug ist der teuerste Fehlertyp** — und er sass ausgerechnet
in der mechanischen Absicherung, die eingefuehrt wurde, weil die Regel
allein dreimal versagt hatte. Beide lesen jetzt
`sys.stdin.buffer.read().decode("utf-8", errors="replace")`.

Dazu drei Fehlalarme, die den Pruefer praktisch unbenutzbar machten
(generische Woerter vor einer Rechtsform, CSS-Farbtripel als
Telefonnummer, Adapter-Klassennamen) — jeder mit Test in BEIDE
Richtungen, nach der Telefon-Lehre von 2026-08-07.

Erst mit dem reparierten Pruefer war ein Repo-Scan sinnvoll: 478
Dateien, 86 Vorkommen zweier realer Firmennamen in Quellcode, Tests und
CHANGELOG, dazu vier reale Arbeitgeber in Tool-Docstrings — ersetzt
durch Platzhalter aus FIKTIVE_FIRMEN. Rest-Triage als **#930** offen
(Quellen-Adapter zulaessig, Testdaten-Platzhalter fehlen in der Liste,
Alt-Tests mit echten Firmen). MERKE zur Platzhalter-Liste: sie
vergleicht per TEILSTRING — ein zu kurzer Eintrag verdeckt reale
Firmen, die den Baustein zufaellig enthalten.

**Zehn Alt-Issues geloescht** (#88, #434, #471, #474, #481, #530, #540,
#568, #658, #709). Das offene #481 (Kalender-Export) wurde vorher
anonymisiert als **#928** neu angelegt — Inhalte erst archivieren, dann
loeschen. GH-Sweep seither sauber (772 Artefakte).

**Zeitzonen-Fund** (fiel auf, weil die Suite nach Mitternacht rot
wurde): `scheduled_date` ist ein LOKALES Datum, SQLites `date('now')`
liefert UTC. In Sommerzeit meldete PBP zwischen 00:00 und 02:00
Ortszeit "keine faelligen Nachfassungen"; `get_statistics` rechnete
schon lokal, die Schwester-Abfrage nicht. MERKE: `date('now')` in SQL
neben `datetime.now()` in Python ist immer ein Verdachtsfall — und
ein Test, der nur nachts rot wird, ist kein Flake, sondern ein Befund.

**README-Gate**: `release_check.py` prueft jetzt die Versionszeile im
README-Kopf gegen das neuste Stable-Tag. Die README stand fuenf
Releases lang auf v1.7.16, obwohl DoD-3 ihre Pflege vorschreibt.

## Stand 2026-08-18 (v1.7.21 Stable + v1.8.0-beta.13) — Keine Sackgassen

**Schema:** v48 / v52 unveraendert. **Tests:** 2335 / 2401 gesammelt.
Neu `services/nutzerfuehrung.py` (`kein_profil` / `leer`).

**#927** — gemessen ueber ALLE 53 argumentlosen Tools auf frischer DB:
18 Sackgassen vorher, 6 danach. Die MESSUNG ist der eigentliche Wert,
nicht die Textarbeit: ohne den Rundumlauf haette niemand gemerkt, dass
die Meldung "kein Profil" in **15 verschiedenen Formulierungen**
existierte. Groesste Einzelwirkung `suchkriterien_anzeigen`: gab `{}`
zurueck — die Grundlage JEDER Jobsuche fehlte, und nichts sagte das;
die Suche lief danach ins Leere. Die restlichen 6 bleiben BEWUSST
("0 Euro Kosten" erklaert sich selbst). Der Guard-Test ruft trotzdem
JEDES argumentlose Tool auf der leeren DB auf und faengt Abstuerze.

MERKE-Punkte:

(1) **Skript-Patches am return-Statement sind gefaehrlich.** Ein
`replace(return_X, "if leer: ...")`, das den Normalpfad nicht wieder
ANHAENGT, loescht ihn: `suchprofile_auflisten` lieferte danach `None`
— gefunden erst von der vollen Suite (`'NoneType' object is not
subscriptable`), nicht von den gezielten Tests. Gegenprobe nach JEDEM
Skript-Lauf: `git diff -U0 | grep "^-[^-]"`, jede entfernte Zeile
einzeln rechtfertigen. (Dieselbe Welle: zweimal zerrissen
Skript-Einfuegungen Import-Bloecke.)

(2) **Zahlendreher im Issue-Verweis wandert in den Release.** Der
v1.7.20-Commit UND sein CHANGELOG-Eintrag verwiesen zweimal auf #927;
gemeint war die Quellen-Arbeit, die gar kein eigenes Issue hatte. Tag
und Release-Notes sind eingefroren — nur die Repo-Datei liess sich
korrigieren. Nummer vor dem Commit gegen `gh issue view N` pruefen.

(3) **Negativ-Befund, dokumentiert damit ihn niemand nachmisst:** die
7 Stellen `{"fehler": str(e)}` in tools/ sind KEIN Traceback-Leck —
durchweg `ValueError` aus der DB-Schicht mit lesbaren deutschen Texten.

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

(12) **B37/B38 — Quellen-Wiederbelebung (v1.7.19)**: zwei als tot
gefuehrte Quellen liefern wieder. MERKE fuer jede kuenftige
Quellen-Diagnose:
  (a) Bevor ein Adapter als kaputt gilt, muss er mit KORREKTEN
      Parametern gelaufen sein — `freelancermap` war voellig intakt und
      scheiterte nur an einem Fallback mit Slug-FRAGMENTEN statt URLs
      (`client.get("Software-Engineer")`). Der Fallback greift genau
      ohne Suchkriterien, also bei frischen Profilen.
  (b) SPA-Karriereseiten liefern JobPosting-Daten haeufig NICHT als
      ld+json im DOM, sondern escaped im SSR-Hydration-Payload
      (`job_scraper/hydration.py`). BeautifulSoup findet dort nichts.
  (c) Das plattform-eigene Datenarray (hier "Offers") ist reicher als
      der schema.org-Auszug: Detail-Slug, ECHTE Gehaltsspanne, Ort.
  (d) Soft-Hyphens (­) MITTEN im Wort killen jedes Keyword-Match,
      waehrend der Titel fuer das Auge normal aussieht — immer
      `entweiche_trennzeichen` vor dem Matchen.
  (e) Bei beiden Quellen war der Query-Parameter serverseitig TOT, die
      Themen-/Slug-Seite dagegen lebendig. Erst pruefen, ob der
      Suchparameter ueberhaupt wirkt — sonst holt man achtmal dieselbe
      Liste.
  (f) MERKE zum eigenen Fehler: der #925-Patch suchte nach dem Text
      "Cloudflare-Bot-Block" und traf damit die FALSCHE Quelle. Bei
      Registry-Patches den Quellen-Key als Anker nehmen, nie den
      Begruendungstext.

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
**Plugins** (40. Seite — Wiki-Guard zaehlt jetzt >= 41). API-v1-Freeze
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
`test $(ls *.md | wc -l) -ge 42 && git add -A ...` (Zahl bei neuen
Seiten nachziehen; Stand 2026-09-07: 42 Seiten, zuletzt Scoring). Ausserdem: `git pull --rebase` und Commit-Kette nie
so verketten, dass der Commit auch bei fehlgeschlagenem Pull/Edit laeuft.

**Und zwar konkret: das Kommando in so einer Kette NIE durch eine Pipe
fuehren.** Am 2026-09-07 lief ein Wiki-Commit trotz
`error: cannot pull with rebase` durch, weil die Kette
`git pull --rebase 2>&1 | tail -2 && git add -A && git commit` lautete —
der Exit-Code einer Pipe ist der des LETZTEN Glieds, hier also der von
`tail`, und der ist immer 0. Die Regel sah eingehalten aus und war
wirkungslos. Ausgegangen ist es gut (Fast-Forward, Gegenseite
unveraendert), aber der Schutz hat nicht geschuetzt. Richtige
Reihenfolge ohne Pipe: **erst committen, dann `git pull --rebase`
(unverpipt, Exit-Code lesen), dann pushen.**

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
8c. **Ein Schutz zaehlt erst, wenn er auch AUFGERUFEN wird (seit
   2026-09-02)** — nach jeder Aenderung an einem Guard, Hook oder Test
   pruefen, ob er in der echten Umgebung ueberhaupt laeuft. Zwei Faelle
   am selben Tag, beide vom selben Typ:
   (a) Der PII-Hook war korrekt und vollstaendig — er hatte nur keinen
   Matcher fuer den MCP-Weg. Fuenf Issues mit realen Firmennamen gingen
   an ihm vorbei, obwohl er jeden davon erkannt haette.
   (b) Ein neuer Test las eine Datei aus `.claude/`; das Verzeichnis ist
   gitignored und fehlt im CI-Klon. Er waere dort rot geworden — oder,
   nach dem Skip-Fix, still uebersprungen worden.
   Konkret also: Matcher gegen echte Werkzeugnamen testen, Tests
   einmal aus einem FREMDEN Arbeitsverzeichnis laufen lassen (`pytest
   <absoluter Pfad>` mit anderem `cwd`), und bei jedem Guard einen Test
   ergaenzen, der seine REGISTRIERUNG prueft. Gruen im
   Repo-Wurzelverzeichnis ist kein Beweis.

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
     **Seit 2026-09-02 deckt er AUCH den MCP-Weg ab** (zweiter Matcher
     in `.claude/settings.json`): jeder schreibende MCP-Aufruf mit
     Issue-, Kommentar-, Story-, Wiki- oder Datei-Bezug laeuft durch
     denselben Pruefer, verschachtelte Felder eingeschlossen; lesende
     Werkzeuge werden nicht angefasst. MERKE dazu: die Beschraenkung
     "nur der Bash-Weg" stand hier als bekannte Grenze — und ist am
     02.09. ein zweites Mal eingetreten. Fuenf Issues vom 21./25.08.
     trugen reale Firmennamen, obwohl alle fuenf seit dem 10.05. in der
     Erkennungsliste stehen: der Pruefer haette sie gefunden, er wurde
     nur nie aufgerufen. **Eine dokumentierte Luecke ist keine Warnung,
     sondern eine Vorhersage** — sie tritt ein, und zwar genau dort, wo
     sie notiert ist. Tests: `tests/test_gh_pii_guard_mcp.py` (17, beide
     Richtungen; bewusst OHNE reale Namen im Repo, ausgeloest wird mit
     einer generischen Fundstelle).
   - **`scripts/gh_pii_sweep.py`**: prueft den IST-Zustand ueber ALLE
     Issues, Kommentare und Releases, auch geschlossene. Seit der Hook
     beide Wege abdeckt, ist der Sweep nicht mehr das einzige Netz fuer
     den MCP-Weg, sondern das Netz fuer den ALTBESTAND und fuer alles,
     was ausserhalb dieser Session entstanden ist. Gehoert weiter in die
     Session-Abschluss-Runde — ein Guard verhindert Neues, er heilt
     nichts Altes.
   - **`FIKTIVE_FIRMEN`** in `scrub_pii.py`: der Pruefer schlug vorher bei
     genau den Platzhaltern an, die diese Regel vorschreibt. Neue
     Platzhalter dort eintragen.
   - **`issue_text_pruefen(text=...)` (MCP, #946, seit 2026-08-19) — der
     Pflichtschritt VOR jedem ausgehenden Text.** Er dreht die Richtung
     um: statt einer gepflegten Namensliste im Repo sucht er die Namen
     aus der DATENBANK (applications/jobs/contacts) im Text. Die
     gepflegte Liste ist immer nur so gut wie ihre letzte Pflege — sie
     hat am 18./19.08. dreimal versagt (#919, #928, #940-#945), obwohl
     die Regel bekannt war. Mit `anonymisieren=True` kommt der fertige
     Text zurueck; die Zuordnung steht in `anonymisierung_map` und
     bleibt stabil, damit dieselbe Firma ueber mehrere Issues denselben
     Platzhalter behaelt. Die Tabelle ist LOKAL und gehoert nie in
     Export oder Telemetrie (Test sichert das ab). Quellennamen,
     Job-Hashes und der eigene Klarname loesen bewusst nichts aus.

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

`fit_analyse` liefert ein strukturiertes `empfehlung`-Feld mit vier
Kategorien: **EMPFOHLEN / BEDINGT / NICHT_EMPFOHLEN / NICHT_BEURTEILBAR**
plus `begruendung` und `kurz`. Claude zitiert den Verdict direkt — keine
eigenen Weichspueler wie "Trefferchance nicht hoch, aber realistisch
vorhanden".

**Der Verdict kommt NICHT aus dem Score (#1003, seit v1.7.61).** Der
Score misst, wie gut eine Anzeige die SUCHBEGRIFFE trifft — Keywords,
Gehalt, Entfernung, Remote-Grad. **Der Lebenslauf geht nicht ein.** Ob
jemand auf eine Stelle passt, ist eine andere Frage, und sie entsteht
erst aus dem Vergleich von Profil und Anzeige.

Deshalb gilt jetzt:

- **`NICHT_BEURTEILBAR` ist der Normalfall**, solange niemand die
  Anzeige gegen das Profil gelesen hat. Das heisst "noch nicht
  gelesen", NICHT "passt nicht" — die Verwechslung ist #989. Der
  richtige naechste Schritt ist die Detailanalyse, nicht eine
  Weichspueler-Formulierung.
- **Hast du Anzeige und Profil wirklich gelesen, schreib dein Urteil
  zurueck:** `stelle_analyse_speichern(job_hash, urteil, begruendung)`.
  Es haengt danach an der Stelle, steht in der Trefferliste und
  ueberlebt das Gespraech. Ein Urteil, das du aus dem Score ableitest,
  waere genau der Fehler, den #1003 behebt — nur von Hand.
- **`NICHT_EMPFOHLEN` aus einem k.o.-Kriterium** (Wiedergaenger mit
  fachlichem Grund, ausserhalb des Rechtsraums, kein MUSS-Anker) gilt
  weiter und schlaegt auch eine gute Analyse.

**Der Score ist KEINE Prozentzahl (#999).** `total_score` ist eine
Punktsumme, deren Obergrenze aus den Kriterien folgt — vor allem aus
der Laenge der MUSS-Liste. Er steht in der Antwort samt
`score_bedeutung`; **nie "X von 100" schreiben**, solange 100 nicht
erreichbar ist, und ihn nie als Passungsaussage zitieren.

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
