# Lehren aus der PBP-Entwicklung

Verdichtet aus 125 Stand-Bloecken (v1.7.24 bis v1.7.139, dazu die frueheren
Beta-Bloecke) mit 893 MERKE-Punkten; seit v1.7.140 direkt hier gepflegt. Die Originale stehen woertlich in
[`claude-md-archiv.md`](claude-md-archiv.md) — dort per grep nach der
Issue-Nummer oder nach `v1.7.NN` suchen.

**Belege:** `#NNN` ist ein Issue, `v1.7.NN/M` der MERKE-Punkt M im
Stand-Block der Version v1.7.NN.

**Pflege:** Neue MERKE-Punkte kommen hierher, nicht in `CLAUDE.md` —
als weiterer Beleg an eine bestehende Regel oder als neue Regel mit ein bis
drei Saetzen. Keine Nacherzaehlung von Versionen; was sich geaendert hat,
steht in `CHANGELOG.md`.

---

## 1. Eine Frage, ein Ort

**L1. Eine Frage, eine Funktion.** Wo zwei Wege denselben Wert erzeugen,
gehoert ein gemeinsamer Aufruf hin, kein Kommentar "dieselbe Logik wie" —
der stand bei `fit_analyse` fuenfmal und stimmte nie lange. Eine Regel in
nur einen von zwei Wegen einzubauen verschiebt die Abweichung; und beim
Suchen nach Doppelungen zuerst den Weg ansehen, der schreibt oder den die
Doku empfiehlt — der schwaechere ist oft genau dieser.
*Belege:* #963, #913, #976, #991, #992, #951, #1017, #1036, #1051, v1.7.132/1, #1106 (Blacklist auf den Bestand war die fuenfte Fassung neben `blacklist_regel`), #1173 (Lesen und Schreiben der eigenen Ordner gingen verschiedene Wege; siehe L64), #1237 (die Berufsjahre gab es dreimal: einmal mit der Uhr, zweimal mit einer festen 2026 -- ab 2027 fehlte jeder laufenden Position ein Jahr; die Auto-Aussortierung nimmt jetzt `berufsfeld.berufsjahre`)

**L2. Das Nadeloehr gilt auch fuer die Eingabe.** Kriterien, die roh statt
durch `fuer_scoring` gereicht oder hinter dem Nadeloehr ueberschrieben
werden, ergeben dieselbe Stelle mit zwei Zahlen; dieselbe Funktion mit
anderem Eingang ist eine zweite Regel. Guards pruefen per Syntaxbaum, dass
jeder Aufrufer die Eingabe aus dem Nadeloehr bekommt.
*Belege:* #987, #1045, #1051, #1055, #1076, v1.7.112/3, v1.7.116/1

**L3. Eine Liste an zwei Orten laeuft auseinander.** Registries, Kataloge,
Rollen- und Reiterlisten gehoeren an eine Stelle, von der alle Leser
ableiten; ein Paritaets-Guard muss genau die Liste pruefen, die der Nutzer
tatsaechlich fragt. Beim Zusammenfuehren zweier Fassungen beide lesen —
die kuerzere trug Regeln, die der laengeren fehlten.
*Belege:* #979, #1060, v1.7.120/1, v1.7.134/3, v1.7.135/3, v1.7.136/3

**L4. Nachschlagen statt voraussetzen.** Vor jedem neuen Modul, jeder
Tabelle, Regel oder jedem Werkzeug pruefen, ob es das schon gibt (oft ist
der Mechanismus fertig und wird nur nicht gefragt), und die Antwort des
Schreibwerkzeugs lesen ("updated" statt "created"). Namen und Signaturen
werden nachgeschlagen: ein `except Exception` um einen geratenen
Methodennamen verschluckt den AttributeError und schaltet still ab.
Gesucht wird nach dem GEDANKEN, nicht nach dem geplanten Namen:
`unescape` und `ueberholt` fanden, was `text_bereinigen` und
`nachfass_abgleich` schon waren.
*Belege:* #799, #986, #994, #1065, #1011, #1012, #1025, v1.7.94/9, DoD 8d, #1122/#1123 (zweimal beinahe doppelt gebaut: `_entities_aufloesen` gab es seit #965, der Aufraeumer `_run_followup_ueberholt` seit #945; gefunden erst beim Lesen roter Alt-Tests)

## 2. Vergleiche und Schreibweisen

**L5. Woerter mit Wortgrenzen vergleichen, in beide Richtungen getestet.**
"ki" steckt in "Kita", "us" in "Kundenservice", "Eur" in "Europastr.",
"intern" in "International", "p.a." in "Patient", "leiter" in "Begleiter",
"Nord" in "Nordwerk"; `\b` oeffnet auch hinter einem Doppelpunkt, und eine
Versionsnummer ist kein Praefix ("v1.7.12" in "v1.7.120"). Jede Regel
bekommt Faelle, die treffen muessen, und Faelle, die nicht treffen duerfen.
*Belege:* #970, #996, #1026, #1015, #1018, #1070, #1080, #1019, #937, v1.7.120/12

**L6. Eine Liste findet nur die Schreibweise, in der sie steht.**
Umschrift gegen Umlaut, Label gegen gespeicherten Wert, Langform gegen
Kurzform: verglichen wird nach Normalisierung beider Seiten. Suchmuster fuer
Text von aussen kennen beide Schreibweisen; Werte, die Claude zurueckschickt
(Status, Aktionen, Schluessel), bleiben in Umschrift.
*Belege:* #1028, #663, #1080, #1089, v1.7.53/1, v1.7.77/1, v1.7.138/3, v1.7.143/1 (Akzente: 'Société Beispiel' gegen 'Societe Beispiel Deutschland GmbH' — der Teilstring scheitert am Akzent; gefaltet wird NACH der Umschrift der Umlaute, sonst wird aus 'Müller' ein 'Muller'), #1231 (der PII-Prüfer: die Platzhalterliste führt 'vermittler sued', ein Beitrag schrieb 'Süd' und bekam einen Firmentreffer; jetzt laufen Text UND Liste durch dieselbe Umschrift)

## 3. Fehlende Information ist kein Befund

**L7. "Unbekannt" ist ein eigener Zustand.** Wo ein Wert fehlt, darf ein
Punktesystem nicht neutral einsetzen — neutral heisst dort "kostet nichts"
und steigt in der Sortierung. Ungeprueft muss anders aussehen als
unauffaellig und anders als "passt nicht": drei Zustaende statt zwei,
Gruppe vor Zahl, grauer statt roter Daumen.
*Belege:* #989, #965, #1003, #999, #1052, #1069

**L8. Eine Null hat mehrere Bedeutungen.** "Liefert nichts" und "liefert
nichts Passendes", 410 Gone und Bot-Block, "nicht pruefbar" und "nicht
erreichbar", "nicht gemeldet" (`None`) und "null gesehen" muessen
unterscheidbar bleiben; HTTP 200 sagt nichts ueber gelieferte Stellen.
Status und Befund werden durchgereicht, nie auf einen leeren String
reduziert.
*Belege:* #995, #1014, #813, #1016, #1033, #808, v1.7.44/4

**L9. Werte bleiben, was sie sind.** Geschaetzte Werte zaehlen nie als
belegt, und eine Luecke wird benannt statt gefuellt — kein erfundener
Monat, keine Uhrzeit aus dem Mail-Kopf, kein Zeitpunkt aus `updated_at`,
kein Gehalt aus einer Telefonnummer oder Arbeitszeit. Python-Fallen dabei:
`dict.get(k, vorgabe)` greift nicht bei NULL, `int()` schneidet ab,
einzeln gerundete Teile ergeben nicht die Summe, eine Menge ist kein
Wahrheitswert.
*Belege:* #827, #1017, #1018, #1026, #1006, #1019, #1010, #987, #1035, #1054

**L10. Was verborgen wird, benennt sich.** Ein Filter oder eine Schwelle,
die Stellen ausblendet, nennt die Zahl und bietet "Filter aufheben"; eine
Kennzahl nennt ihre Grundlage (geladene Seite oder Bestand, Anteil
geschaetzter Werte). Ein unsichtbar gesetzter Filter ist fuer den Menschen
dasselbe wie ein leerer Markt.
*Belege:* #1008, #1022, #1030, #1063, #992, #1010

## 4. Leser, Schreiber, Wirkung

**L11. Jede Einstellung braucht einen Setzer und einen Leser.** Parameter
ohne Draht, Felder ohne Leser und Schluessel, die niemand erzeugt, sehen
im Docstring wie eine Funktion aus. Vokabulare entstehen aus den Lesern,
nicht aus den Schreibern, und ein Guard haelt beide gegeneinander.
Eine Automatik hat auch einen Ausloeser: der Aufraeumer fuer ueberholte
Nachfragen lief hoechstens stuendlich und nur bei offenem Dashboard — wer
ueber Claude arbeitet, hatte ihn nie. Was sich an einem Ereignis aendert,
haengt am Ereignis; die Automatik bleibt das Netz darunter.
*Belege:* #993, #1000, #988, #1015, #811, #1053, #1074, #973, v1.7.116/5, #1037 (Schluessel ist nicht Schalter: eine Einstellung, die Zugang UND Nutzung bedeutet, laesst sich nicht halb abschalten), #1123 (Nachfrage blieb "ueberfaellig", weil der Aufraeumer nie lief), #1115 (Leser der Whitelist ohne Draht zur Quelle), v1.7.143/2 (`_repost_verdacht` in der Automatik gelesen und nirgends gesetzt; das Feld `endkunde` einer Bewerbung von der Vermittler-Prüfung nie gelesen)

**L12. Rueckgabewerte auswerten, Fallbacks ohne andere Bedeutung.** Eine
Erfolgsmeldung ueber eine Nicht-Aenderung beendet die Fehlersuche und ist
teurer als ein Fehler. Ein Fallback speichert nie eine andere Bedeutung
("hinfaellig" als "erledigt", roher Befehl als "Anleitung kopiert"), und
eine Zustandsanzeige setzt der Empfaenger, nicht der Absender.
*Belege:* #997, #994, #1073, #980, v1.7.120/2, v1.7.133/1

**L13. Wer eine Form aendert, fragt zuerst, wer die alte liest.**
Trennzeilen, Laengenvergleiche, `startswith` auf Registry-Texten und
Praefixlisten auf Anzeigetexten brechen still, wenn sich Text oder
Schreibweise aendert. Nach jeder Umstellung jede Lesestelle gegen die neue
Form pruefen.
*Belege:* #1047, v1.7.110/4, v1.7.121/6, v1.7.138/2, v1.7.139/6, v1.7.143/3 (Akzent-Faltung im Firmennamen: `find_vermittler_bewerbung` verglich den gefalteten Namen mit ungefaltetem Rohtext und hätte einen Treffer verloren; aufgefallen beim Durchsehen, nicht in der Gegenprobe — der Fall steht jetzt als eigener Test)

**L14. Gespeicherte Werte werden nie still umgedeutet.** Wirkungslose
Altwerte werden benannt statt geloescht, Umbenennungen bekommen Aliase,
Umzuege eine Vorschau und einen Beleg; eine Migration ordnet ein, sie
entscheidet nicht (kein `dismiss_job` beim Umschichten). Eine Umleitung
nimmt nur, was der Aufruf mitbringt.
*Belege:* #988, #1000, #1063, #957, #956, #1010, #1055, #1087 (H29)

## 5. Daten schreiben und loeschen

**L15. Bei `INSERT OR REPLACE` zaehlt die Spaltenliste.** REPLACE loescht
die Zeile und legt sie neu an; jede Spalte ausserhalb der Liste ist danach
NULL, und ein Suchlauf loescht still ein gelesenes Urteil. Die Abhilfe ist
strukturell: `_BEWAHREN` plus ein Test ueber jede Spalte von `jobs`.
*Belege:* #892, #1007, #913, #948, DoD 8e

**L16. Wer loescht oder zusammenfuehrt, muss jeden Bezug kennen.** Auch
polymorphe Verweise (`contact_links`) und Tabellen ohne Fremdschluessel;
Loeschbereiche werden aus dem Schema abgeleitet, Kinder vor Eltern
geloescht, und Vorschau- und Ist-Zahl muessen gleich sein. Eine neue
Tabelle wird einem Loeschbereich zugeordnet (Guard).
*Belege:* #1025, #1077, #1075, #1053, #1084

**L17. Loeschen ohne Spur heisst Wiederkommen, und eine Kennung ist ein
Vertrag.** Zusammengefuehrte Dubletten brauchen einen Grabstein, und der
Import vergleicht gegen alle Fundstellen. Wer die Bildung einer Kennung
aendert, braucht einen Uebergang fuer den Bestand; Kurzkennungen muessen
eindeutig bleiben.
*Belege:* #1084, #951, #1041, #1040, #1029

**L18. SQLite und Zeit.** `db.close()` nie, solange Hintergrund-Threads
laufen (Absturz auf C-Ebene, Exit 139); Connection je Thread. `date('now')`
in SQL ist UTC, `datetime.now()` lokal, ein reines Datum ist ein Ortsdatum —
Zeitvergleiche immer zeitzonenbewusst.
*Belege:* v1.7.11, v1.7.15 (A28), v1.7.21, #1010, #1032

## 6. Messen statt vermuten

**L19. Gemessen wird auf einer Kopie, mit genug Stichprobe und derselben
Rechnung.** Die echte Datenbank nur als Kopie mit Isolations-Zusicherung;
die aktiven Stellen sind oft eine Handvoll, gemessen wird dann ueber die
aussortierten. Bevor eine Messung eine Entscheidung traegt, pruefen, ob sie
dieselbe Rechnung misst wie das Ergebnis.
*Belege:* #1012, #1020, #1063, v1.7.116/1, QA-Isolation

**L20. Ein Bericht beschreibt seinen Bestand und seinen Tag.** Vor dem Fix
nachmessen, ob es den Defekt noch gibt und wie gross er ist — oft ist er
groesser als gemeldet, manchmal schon behoben. Vorschlaege aus Issues
werden geprueft, nicht uebernommen, und vor dem Schliessen werden die
letzten Kommentare gelesen, nicht nur der Titel.
*Belege:* #1023, #931, #892, #998, #1014, #1025, #962, #956, v1.7.128/1, #1124 (die Quelle des Fehlalarms war `jobs.company`, nicht die Firmenrecherche — Punkt 2 des Vorschlags traf nichts), #1117 (die Annahme 'der Namensvergleich beherrscht Akzente' stützte sich auf einen URL-Treffer, der den Firmenvergleich überspringt)

**L21. Regeln entstehen aus Messungen, in beide Richtungen.** Grenzen,
Schwellen und Wortlisten werden gegen echte Titel und Texte gehalten,
bevor sie entscheiden; eine Haertung darf ihren Gruendungsfall nicht
mitnehmen. Gemessen hat die ausgegebene Liste, nicht das Nachdenken.
*Belege:* #966, #1064, #1054, #968, #1070, #991, v1.7.139/2

**L22. Die Umgebung ist Teil der Messung.** Der laufende MCP-Server faehrt
die installierte Version, nicht das Repo; die lokale `.venv` kann eine
andere Hauptversion fahren als die CI (FastMCP 2 gegen 3), und native
Abhaengigkeiten brechen nur auf dem Linux-Runner. Gruen lokal ist deshalb
kein Beleg fuer die ausgelieferte Version.
*Belege:* v1.7.76/6, v1.7.120/13, v1.7.87/9, beta.0, H34 (System-Python mit FastMCP 2.12, 27.09.2026), #1130 (30.09.2026: die Suite trotz dieser Regel mit dem System-Python gestartet; die Fehlalarme fielen nach Minuten auf und wurden gegen einen sauberen Worktree von `origin/main` gegengeprueft. Ein Abbruch mit klarer Meldung bei FastMCP < 3 in der conftest waere ein mechanischer Schutz statt einer Erinnerung)

## 7. Tests, Guards, Gegenprobe

**L23. Gegenprobe: jeden Mechanismus einmal ausbauen.** Wird kein Test
rot, ist das ein Befund ueber die Tests — oder darueber, dass der
Mechanismus nichts tut (dann ausbauen). Zwei Fixes fuer denselben Fall
belegen einander nicht; je ein isolierender Fall. Das Gegenprobe-Skript
selbst laeuft im Hintergrund mit Log und Zeitlimit, liest alle Kanaele und
Testlaeufer, unterscheidet Sammelfehler von "rot", und der Arbeitsstand ist
danach bytegleich.
*Belege:* v1.7.79/9, #1031, #1026, #1019, #1036, v1.7.102/6, v1.7.114/9, v1.7.122/12, v1.7.127/6, v1.7.133/6, #1106 (stumme Gegenproben fanden fehlende isolierende Faelle und wirkungslosen Code), #1120 (Ausbau eines "wirkungslosen" Mechanismus war am Fixture gruen und an den echten Mails falsch — nach jedem Ausbau erneut an echten Daten messen), #1122 (drei von vier CSS-Aenderungen blieben einzeln gruen; zwei davon zusammen ebenfalls — ausgebaut statt mitgeliefert), #1123 (ein Typ-Vorfilter war neben der schliessenden Funktion wirkungslos), v1.7.143/4 (34 Mechanismen im Backend, 5 in der Oberfläche mit Neubau nach jedem Ausbau; alle rot), #1237 (ein Fehler, der von der Uhr abhaengt, ist am Tag des Tests nie rot -- die feste 2026 war bis zum 31.12.2026 "richtig": die Tests stellen die Uhr auf Tage vor, in und nach 2026, und die Gegenprobe trennt "feste Zahl" von "an der Naht vorbei" (datetime.now statt uhr.heute); 19 Eingriffe, alle rot, sieben davon im Waechter selbst)

**L24. Ein Guard prueft die Bauform, nicht eine Zeichenkette.** Ein
gesuchtes Wort steht oft auch im Kommentar oder im `title`, ein festes
Fenster misst den Abstand statt den Aufruf, gezaehlte Fundstellen lassen
die naechste durch. Syntaxbaum statt Regex — und eine Kontrolle, die
dieselbe Annahme benutzt wie der Schreibvorgang, prueft nichts.
*Belege:* #973, #1016, #1036, #1048, #1050, #1055, v1.7.115/6, v1.7.130/10, v1.7.134/7, v1.7.135/9, #1106 ("no such table" zaehlte im SQL-Guard nicht, die Tabelle `meetings` gab es nie), #1120 (`test_951` las 14.000 Zeichen ab `def save_jobs`; ein Kommentar schob den Aufruf hinaus, jetzt bis zur naechsten Methode)

**L25. Ein Schutz zaehlt erst, wenn er aufgerufen wird.** Matcher gegen
echte Werkzeugnamen, ein Test fuer die Registrierung jedes Guards, Tests
einmal aus fremdem Arbeitsverzeichnis mit Pfaden relativ zur Testdatei.
Ein Pruefer, der bei korrektem Zustand Alarm gibt, wird ignoriert —
Fehlalarme sind Defekte.
Ein Netz, dessen Fehler ein `except: pass` schluckt, hat womoeglich nie
gegriffen: die drei Stale-Netze zogen ein zeitzonenbewusstes `updated_at`
von einem naiven `datetime.now()` ab. Was ein Update beim ersten Start
anstoesst, trifft auf die faellige Automatik — Last beim Start gehoert in
kurze Schreibvorgaenge.
*Belege:* DoD 8c, #929, #1017, #1078, v1.7.131/6, #1118, #1128 (vier dauerhaft rote Tests wurden 'bekannt' genannt und überlesen; der Test meldete 'diese Maschine kann kein Bash' statt eines Skriptfehlers)

**L26. Alt-Tests zuerst lesen.** Ein roter Alt-Test ist die Spezifikation
oder die alte Loesung: die Absicht bleibt, der Stellvertreter (Wortlaut,
Name, dict-Gleichheit) wird angepasst. Ein `try/skip` um den Aufbau macht
aus einer Regression eine Uebersprungzahl.
Auch der Docstring eines Alt-Tests ist Spezifikation: "Bewusst in der
Automatik und nicht beim Lesen" (#945) hat einen Sweep im Lesepfad
verhindert, der schon geschrieben war.
*Belege:* v1.7.31/2, #1022, #1023, #968, #1049, #1053, #1065, #1123 (sieben Alt-Tests angepasst, Begruendung jeweils im Test)

**L27. Testdaten in der Form, in der der Aufrufer sie bekommt.** Wer einen
Fehlschlag liest, statt die Erwartung anzupassen, findet falsche Testdaten
(Abkuerzung, JSON im Einzelfeld, ein Zeichen zu lang); ein Test, der
"nichts ist falsch" prueft, zeigt zuerst, dass er etwas sieht.
Testdoppel bilden den echten Vertrag nach (`name=`-Argument, Host als
Text).
Ein Fixture nach einer Beschreibung ist eine Vermutung: es wird aus einer
echten Probe gebaut (anonymisiert, Byte-Struktur erhalten), laeuft durch
denselben Parser wie die echten Daten, und ein Test haelt seine Form fest.
*Belege:* #1036, #1080, #811, #1046, #1070, v1.7.110/8, v1.7.132/6, v1.7.135/8, #1106 (Test-Doppel ohne `get_active_profile_id` nach dem Profilfilter), #1120 (Google-Alert-Fixture nach Beschreibung: gruen, an neun echten Mails 0 von 25 Treffern)

**L28. Die Auswahl "betroffener" Tests ist eine Annahme.** Vor jedem
Release die volle Suite plus alle Node-Tests (eigene CI-Schritte). Tests
mit festen Daten verfallen, Tests um Mitternacht UTC treffen die
Tagesgrenze.
*Belege:* v1.7.100/6, #1051, #1053, #1063, #1070, v1.7.134/8, #767, v1.7.105/4, v1.7.21, #1123 (ein Teillauf nach Namensschlagwort verfehlte drei rote Alt-Tests; erst die ganzen Dateien fanden sie)

## 8. Frontend und Browser-Tests

**L29. Tailwind meldet nichts.** Eine unbekannte Farbe, eine Deckkraft-Stufe
ausserhalb der Skala oder ein falscher Ton erzeugt weder Regel noch Fehler;
Guards pruefen gegen die Tokens und gegen das gebaute CSS. Lesetext braucht
volle Deckkraft fuer 4,5:1, und `white`-Ueberlagerungen brauchen im hellen
Modus eine eigene Variable.
*Belege:* #964, #1043, v1.7.117/9, v1.7.137/1, v1.7.137/2

**L30. Ein gruener Build sagt nichts ueber einen Weg, den niemand klickt.**
ReferenceErrors, Hooks nach einem fruehen `return`, JSX-Kommentare an der
falschen Stelle, Unicode-Escapes in JSX und `||` bei einer gueltigen 0
fallen erst zur Laufzeit auf — der Beleg ist ein Browser-Test je Weg.
Gebaute Assets sind ein Paar (`index.html` plus Hash-Dateien) und werden
neu gebaut statt gepickt; ein gerendertes Bild ist eine eigene Pruefung.
*Belege:* v1.7.131/1, v1.7.131/3, #1009, v1.7.102/5, v1.7.93/8, v1.7.35/1, v1.7.34

**L31. Browser-Tests warten auf Zustaende und pruefen die Datenbank.**
Locator mit `exact=True` und eng genug (ein `.glass-overlay` trifft auch
verborgene Overlays); ein `<label>` wickelt Knoepfe ein, Playwrights
`check()` prueft zu frueh. Gewartet wird auf Elemente oder Datenbankwerte,
nie auf feste Zeiten, und belegt wird der gespeicherte Wert, nicht der
Toast.
Ein Sichtbarkeitstest baut den Risikofall selbst und prueft seine
Vorbedingung (ueberschneidet das Menue die Folgekarte ueberhaupt?) — sonst
bleibt er ohne den Fix gruen; `elementFromPoint` statt Rollen-Suche, die
auch verdeckte Elemente findet.
*Belege:* #1027, #1050, #1039, v1.7.103/6, v1.7.83/8, v1.7.93/9, v1.7.136/4, v1.7.137/4, #1113

## 9. Shell, Dateien, Git

**L32. Heredoc-Falle.** Backslashes in Heredocs werden unter Git-Bash zu
Steuerzeichen oder Zeilenumbruechen (`\b` als Backspace, `\n` mitten im
String) — mehr als fuenfzehnmal passiert. Patch-Skripte stehen als Datei
(Write-Werkzeug), Stellen mit Backslash macht das Edit-Werkzeug oder
`chr(92)`; danach `git diff -U0` lesen und nach Steuerzeichen suchen. Seit v1.7.143 bekannt: die Werkzeugschicht wandelt schon VOR Bash doppelte Rückwärtsstriche in einfache und Unicode-Escape-Folgen in das Zeichen um, und Befehle ab etwa 6 KB scheitern mit 'unexpected EOF' — Dateien in Teilen unter 5 KB schreiben, Zeichen direkt statt als Escape-Folge, Rückwärtsstriche vermeiden.
*Belege:* v1.7.24/4, v1.7.82/8, v1.7.84/10, v1.7.117/11, v1.7.125/13, v1.7.135/7, v1.7.136/6

**L33. Zeilenenden und BOM bestimmen die Anker.** Viele Frontend-Dateien
sind CRLF mit BOM, `Path.write_text` schreibt unter Windows CRLF, und eine
Pruefung, die andere Bytes liest als die Mutation, meldet Erfolg ohne
Wirkung. Patch-Skripte lesen BOM und Zeilenende aus der Datei und
schreiben Bytes.
Das Write-Werkzeug schreibt unter Windows CRLF, und `grep`/`cat -A` in
Git-Bash zeigen das `\r` nicht zuverlaessig — Anker im Patch-Skript an das
Zeilenende der Zieldatei anpassen, Bytes pruefen.
`core.autocrlf=true` stellt auch Test-Fixtures beim Auschecken auf CRLF
um; wessen Bytes der Test sind, der braucht `-text` in `.gitattributes`
und einen Test auf die Zeilenenden. Gezaehlt wird mit Python, nicht mit
`grep -c $'\r$'` (zaehlte 139 CRLF in einer reinen LF-Datei).
*Belege:* v1.7.102/6, v1.7.103/4, v1.7.109/7, v1.7.125/12, v1.7.126/12, v1.7.131/9, v1.7.140 (#1113), #1120

**L34. Sicherheitsketten ohne Pipe und ohne `;`.** Der Exit-Code einer
Pipe ist der des letzten Glieds, und `;` laeuft trotz Fehler weiter;
Pruefungen stehen als Bedingung (`test ...`) in der Kette, nicht als
Ausgabe. Vor riskanten Eingriffen committen — ein `git checkout -- datei`
als Rueckweg nimmt fertige Arbeit mit.
*Belege:* Wiki-Vorfall 2026-09-07, v1.7.92/8, v1.7.130/11, v1.7.138/6, v1.7.45/7, v1.7.86/9, #1120 (`pytest ... | tail || rueckfall`: ein Aufruffehler lief als "exit 0" durch, die Suite war nie gelaufen)

## 10. Release und Stable-Linie

**L35. Stable zuerst, Cherry-Picks gegen `main` pruefen.** Fixes, die
Stable betreffen, gehoeren in die 1.7-Linie; Schaufenster-Arbeit ist erst
beim Nutzer, wenn sie dort ist. Umgekehrt nie "Hotfix der 1.7-Linie"
vorschlagen, ohne im Tag nachzuschlagen, ob der Code dort existiert
(`git cat-file -e v1.7.N:<pfad>`): Beta-Dateien wie `services/components.py`
fehlen in Stable, der Fehler ist dann ein Beta-Fehler. Nie `--skip` als Fallback, nach dem
Aufloesen `git diff main -- <datei>` leer, Signaturen der aufgerufenen
Funktionen abgleichen (1.8-only-Funktionen, andere Tupel), nur geloeste
Dateien einzeln hinzufuegen, Assets neu bauen; bei stark abweichenden
Dateien Stable-Fassung plus deterministischer Umschreiber.
Umgibt `try/except` die neue Pruefung, schluckt es auch einen fehlenden Namen (`kanon` gab es nur in 1.8: der NameError wurde zur
Warnung im Log, die Pruefung lief nie) — die mitgewanderten Tests muessen die WIRKUNG verlangen (der Hinweis steht im Ergebnis),
nicht nur das Ausbleiben eines Fehlers.
Beim Portieren: `cherry-pick --continue` verschluckt Betreffe, die mit
`#` beginnen (`-c core.commentChar=;`); ein Modify/Delete-Konflikt hat keine
Marker und darf nie automatisch als geloest gelten — so kam ein
1.8-Modul auf die Stable-Linie. Quelltext-Tests, die Bauformen per
Zeichenkette suchen, vor dem Umbenennen per grep finden (die CI fand zwei).
*Belege:* v1.7.8, v1.7.16, v1.7.12/5, #997, #998, #1016, v1.7.136/8, v1.7.138/5, v1.7.139/8, v1.7.140 (#1102, #1113), #1130 (30.09.2026: als Hotfix-Kandidat vorgeschlagen, im Tag v1.7.143 gab es die Datei nicht), #1184/#1187 (v1.7.157: `kanon` nur in 1.8, stiller NameError; fiel nur durch den mitgewanderten Test auf)

**L36. Ein Release aus mehreren Dateien faellt stueckweise aus.** Tag erst
nach gruener CI, mit Baum, Branch, Commit und Versionsstring als
`test`-Bedingung; CHANGELOG, README und Stand auf `main` danach
gegenpruefen. "Abgebrochen" ist weder gruen noch rot: ein Lauf am Zeitlimit
meldet keinen Fehler und weckt keine Ueberwachung; den Ausgang ausdruecklich
lesen (`gh run view <id> --json conclusion`), bei `cancelled` neu starten.
Doku-Skripte fuehren erst alle Pruefungen und dann alle
Schreibvorgaenge aus, ein Wiki-Push nimmt alle lokalen Commits mit, und
eine Issue-Nummer wird vor dem Commit gegen `gh issue view` geprueft.
*Belege:* beta.0, v1.7.130/11, v1.7.81/11, v1.7.124/11, v1.7.93/10, v1.7.103/3, v1.7.97/7, v1.7.21/2, #1132 (30.09.2026: nach 30 Minuten abgebrochen, 28 Sekunden nach dem vollstaendigen Durchlauf)

## 11. Datenschutz

**L37. PII-Schutz ist mechanisch, nicht erinnert.** Hook fuer Bash- und
MCP-Weg, `issue_text_pruefen` gegen den eigenen Bestand, woechentlicher
Sweep ohne Namen im oeffentlichen Log; Pruefer lesen ihre Eingabe als
UTF-8. Funde einzeln ansehen, bevor eine Nummer verbrannt wird;
Testnummern nie in echten Vorwahlen; Quellen-Schluessel in Kleinschrift
statt am Pruefer vorbei.
*Belege:* DoD 9, #929, #946, #817, #1078, #1068, v1.7.53, v1.7.109/6, v1.7.82/10

## 12. Nutzerfuehrung und Bauform

**L38. Jeder Hinweis nennt Grund und naechsten Schritt, und ein Knopf
liefert, was er verspricht.** Der naechste Schritt haengt am Zustand; ein
Prompt, der das Speichern nicht verlangt, fuehrt nicht zum Ergebnis. Ein
Hinweis, der eine Entscheidung des Menschen nicht akzeptiert, wird zur
Tapete.
*Belege:* #927, #1046, #958, #1049, #1050, #929, v1.7.117/8

**L39. Vorgaben fuer Nebenwirkungen stehen auf AUS, Zahlen haben eine
Bezugsgroesse.** Autostart, Filter und Kontaktdaten im Export sind ab Werk
aus und benannt; ein Filter, der an ist, zeigt seine Zahl. Eine Zahl ohne
Skala ist keine Einstellung — benannte Stufen mit ihrer Wirkung im eigenen
Bestand.
*Belege:* #1001, #1008, #884, #1086, #1063, #999, v1.7.117/4

**L40. Die Bauform entscheidet, nicht die Sorgfalt.** Eine Funktion, die
nur die gekuerzte Fassung liefert, verlaesst sich darauf, dass der Aufrufer
an die Meldung denkt; abschliessende Positivlisten statt Sperrlisten, eine
Stelle statt vieler (Annotations im Proxy, KI-Sperre in einer Zuordnung),
und ein Lookup liefert Verweise statt Volltext.
*Belege:* #1064, #937, #962, v1.7.131/6, v1.7.135/5, v1.7.130/1

**L41. Ein Werkzeug ohne Weg zu seiner Kennung ist ein fehlendes Werkzeug.**
Verlangt ein Werkzeug eine ID, muss ein anderes sie ausgeben — sonst endet
jeder Aufruf im Raten, und "nicht gefunden" darf nie als Erfolg ueber nichts
antworten.
*Belege:* `jobtitel_verwalten`, `bewerbung_event_datum_setzen` (Welle 27.09., #994-Klasse)

**L42. Ein Profilfilter fehlt dort, wo niemand zwei Profile testet.**
Neun Abfragen nach #1106 lasen ueber alle Profile, darunter eine
schreibende und eine Kurz-ID-Aufloesung. Jede neue Abfrage auf
profilbezogene Tabellen braucht den Filter oder einen benannten Grund in
der Ausnahmeliste des Guards (`tests/test_profilfilter_1106.py`).
*Belege:* #1106, #1104

**L43. Eine Meldung beschreibt, was geschehen ist -- nicht, was geschehen soll.**
"Verworfen", "geloescht", "gespeichert" stehen erst NACH dem Vorgang und nur,
wenn er gelungen ist; scheitert er, sagt die Meldung das. Aufraeumen gehoert
in `finally`, nicht ans Ende des Erfolgswegs, und eine Datei unter ihrem
endgueltigen Namen ist immer ganz: erst unter `.part` schreiben, die Laenge
pruefen (urllib meldet eine zu kurz angekommene Antwort nicht), dann umbenennen.
*Belege:* #1130 (Protokoll "Download verworfen", die 55 MB blieben liegen)

## 13. Windows-Alltag: Pfade und Zeichentabellen

**L44. Der Pfad traegt den Benutzernamen -- und der ist nicht immer ASCII.** Programm- und Datenordner liegen unter dem
Benutzerordner (`Ölmühle O'Neill (Büro)`, `Łódź`, `Şişli`). Die Ausgabe eines Unterprozesses wird nie mit `text=True` allein
gelesen: bei umgeleiteter Ausgabe gilt die Zeichentabelle des Rechners (cp1252), ein UTF-8-Byte wie 0x81 wirft
`UnicodeDecodeError`, ein `print` mit »ł« im Kind wirft `UnicodeEncodeError` -- und der Selbsttest scheitert an einem Pfad, nicht an
der Fassung. Richtig: `encoding="utf-8", errors="replace"` beim Lesen UND `PYTHONIOENCODING=utf-8` fuers Kind; Skripte, die einen Pfad
drucken, stellen ihre Ausgabe auf `backslashreplace`. Tesseract (Windows) liest Dateipfade und `TESSDATA_PREFIX` in der ANSI-Tabelle:
das Bild geht ueber die Standardeingabe, die Sprachdaten ueber den Kurzpfad (8.3). Pruefen heisst: den Test mit so einem Pfad laufen
lassen UND die Zeichentabelle erzwingen (`PYTHONIOENCODING=cp1252`) -- sonst ist er auf einem UTF-8-Rechner gruen und auf dem
Zielrechner rot.
**Nachtrag (#1182, 08.10.2026): die Regel stand hier und wurde trotzdem wieder gebrochen.** `claude_laeuft` las `tasklist` mit `text=True`, und im Fenster stand ein
`UnicodeDecodeError` -- nur wenn Claude Desktop NICHT lief (die deutsche Meldung „... ausgeführt.“ trägt ein ü), sonst nie; die Prüfung stimmte dabei nur zufällig. Zwei
Ergänzungen: (1) Programme von Windows (`tasklist`, `taskkill`, `powershell`) schreiben in der Kodierung der KONSOLE (OEM, cp850: ü = 0x81), nicht in UTF-8; dort
`encoding=konsole_kodierung()` oder Bytes lesen und nach ASCII suchen (`services/konsole.py`); `utf-8` gilt nur fürs eigene Kind. (2) Eine Regel, die nur in dieser Datei steht,
hält nicht: ein Wächter-Test (`test_1182_waechter_kein_textmodus_mit_der_standardkodierung`) sucht jedes `text=True` ohne Kodierung im Quelltext.
*Belege:* #1163 (Installer-Helfer, Selbsttest, pip, Komponenten, Texterkennung), `tests/test_v18_auto_update_pfade.py`, `tests/test_v18_ocr_pfade.py`;
#1182 (`claude_laeuft`, PowerShell-Pfade), `tests/test_v18_konsole_ausgabe_1182.py`, Gegenprobe ko01 bis ko11

## 14. Auskunft an den Menschen: was beim Update zu lesen steht

**L45. Eine Release-Notiz hat zwei Leser: den Menschen, der entscheidet, und den Entwickler, der nachschlaegt.** Der Update-Dialog
zeigt drei Zeilen, und an ihnen haengt die Entscheidung, ob jemand neu startet. Wer sie aus den ersten Zeilen einer Entwickler-Notiz
schneidet, bekommt abgeschnittene Absaetze und Zwischenueberschriften (gemessen an den echten Notizen von v1.7.151 und v1.7.152:
ein Satz bricht mitten im Wort ab, eine Zeile lautet nur »Wichtig zu wissen:«). Deshalb steht am Anfang jedes CHANGELOG-Eintrags ein
kurzer Block zwischen `<!-- anwender -->` und `<!-- /anwender -->` (auf GitHub unsichtbar), und `release_check.py` mahnt ihn an.
Der Auszug nimmt ihn bevorzugt, sonst ganze Saetze; er kuerzt an Satzfugen, nie mitten im Wort. Und: Texte, die ein Mensch liest,
prueft man mit dem echten Material, nicht mit einem erfundenen Beispiel.
*Belege:* #1170 (U2), `tests/test_v18_update_notizen_auszug_1170.py`, `tests/fixtures/release_notizen/`

## 15. Gruen auf dem eigenen Rechner: was nur eine frische Installation zeigt

**L46. Ein Pruefer, der zum Ersetzen auffordert, kann Code zerstoeren -- und ein Test, der nur den Quelltext liest, sieht es nicht.**
Der Text-Pruefer (G66) verlangt echte Umlaute in sichtbaren Texten. Er las aber auch Code zwischen zwei JSX-Tags als Text:
in `</Badge> ) : laeuft ? ( <Badge>` stand das Wort fuer ihn in einem Textknoten. Die Umstellung machte daraus an dieser einen
Stelle `läuft`; die Variable hiess an drei anderen weiter `laeuft`. Das baut ohne Meldung (ein unbekannter Name ist zur Bauzeit
kein Fehler) und faellt nur auf, wenn der Zweig laeuft -- hier: eine Komponente ist NICHT installiert, also auf jeder frischen
Installation. Auf dem Entwicklungsrechner ist alles installiert, jede Demo ging am Zweig vorbei; gefunden hat es erst die
Praxisprobe auf einem frischen Rechner. Dazu kam: die Absturz-Grenze galt je Seite, ein Fehler legte alle Reiter der
Einstellungen lahm, und die Seitenleiste tat nichts mehr. Folgen: Funde, die ein Werkzeug von selbst umschreibt, werden danach
auf getroffenen CODE geprueft (der Pruefer ueberspringt jetzt Code zwischen Tags); der Absturz-Test oeffnet jede Seite und jeden
Reiter im Browser gegen eine FRISCHE Datenbank ohne installierte Komponenten; jeder Reiter hat seine eigene Grenze. Und: ein
Gruen auf dem eigenen Rechner prueft nur die eigenen Zustaende.
*Belege:* Praxisprobe 1.8 (05.10.2026), #1170, `tests/test_v18_einstellungen_reiter_stuerzen_nicht_ab.py`

**L47. Ein gemocktes `Popen` prueft keine Flags.** Der Deinstaller-Knopf setzte `DETACHED_PROCESS` und `CREATE_NEW_CONSOLE` zugleich;
Windows lehnt das ab (`OSError: [WinError 87]`). Der Fehler wurde gefangen, die Oberflaeche sagte „Kein Terminal gefunden“ — fuenf
Releases lang, weil jeder Test `subprocess.Popen` ersetzte und damit nur den eigenen Aufruf bestaetigte. Bei Betriebssystem-Aufrufen
gehoert ein Test dazu, der das Betriebssystem WIRKLICH fragt: dieselben Flags, aber ein harmloser Befehl (`cmd /c exit 0`, ohne neues
Fenster), und die Gegenprobe, dass die alte Maske abgelehnt wird. Und: ein gefangener Fehler braucht einen Text, der sagt, was
passiert ist — nicht den Text eines anderen Falls.
*Belege:* Praxisprobe 1.8 (05.10.2026), #1170 PP9, `tests/test_v18_praxisprobe_deinstaller.py`

**L48. Was der Installer schreibt, raeumt der Deinstaller weg — aus derselben Liste.** `_setup_claude.py` schreibt den MCP-Eintrag in
den Standardpfad UND in die Store-Pakete; `DEINSTALLIEREN.bat` las nur den Standardpfad und meldete „[OK] MCP-Eintrag entfernt“.
Claude (Store) behielt den Eintrag und meldete danach bei jedem Start einen Server ohne Programm. Dasselbe Muster: ~830 MB
Playwright-Browser und pip-Cache blieben liegen, das Dashboard-Fenster blieb stehen. Ein Erfolgssatz sagt nur, was der Schritt
selbst angefasst hat. Pruefen heisst: den Installer laufen lassen, dann den Deinstaller, dann nachsehen, was uebrig ist
(Dateien, Registry, Konfigurationen, Fenster, Caches) — und die Orte in beiden Richtungen aus einer Quelle ableiten.
*Belege:* Praxisprobe 1.8 (05.10.2026), #1170 PP10-PP12, `tests/test_v18_praxisprobe_deinstaller.py`

**L49. Eine Frage in einem Konsolenfenster darf den Start nie aufhalten.** „Claude jetzt neu starten? [j/N]“ stand VOR dem Start des
Servers. Das Fenster liegt hinter anderen, niemand antwortet, es laeuft kein Server, der Installer wartet 60 Sekunden und oeffnet
„Verbindung verweigert“ — bei jedem, der Claude Desktop beim Installieren offen hat, also im Normalfall. Fragen kommen NACH dem
Start (Hintergrund-Thread, Vorgabe NEIN, ohne Konsole gar nicht) oder in die Oberflaeche, die ohnehin fuehrt. Jede interaktive
Eingabe in einem Startpfad ist ein moeglicher Stillstand: dort pruefen, was passiert, wenn niemand antwortet.
*Belege:* Praxisprobe 1.8 (05.10.2026), #1170 PP1, `tests/test_v18_praxisprobe_start.py`

**L50. Ein Bild in der Doku ist Code: es muss geprueft werden, bevor es gespeichert wird.** Das Titelbild des Wikis zeigte seit v1.7.137 die
Fehlerkarte „Dieser Bereich ist abgestuerzt“. Der Generator hatte mit `el.remove()` Knoten geloescht, die React verwaltet (alles mit
`[role=status]`, darunter einen Hinweis), und speicherte das Bild, ohne hinzusehen. Gefunden hat es niemand in neun Wochen — erst ein
Klick der Praxisprobe auf einen Anleitungslink. Ein Generator verbirgt statt zu entfernen, prueft vor jeder Aufnahme auf die Fehlerkarte
und auf eine leere Seite, und ein Test haelt die Bilder im Repo gegen die Fehlerkarte (Pixelfarbe des Fehlerblocks).
*Belege:* Praxisprobe 1.8 (05.10.2026), #1170 PP7, `tests/test_v18_screenshot_generator.py`

**L51. Ein Prozess hält seinen Arbeitsordner fest — und ein Test, der die Datei nur liest, merkt es nicht.** Nach den Reparaturen der ersten Probe lief
eine Gegenprobe auf demselben Rechner. Der Deinstaller, jetzt über den Knopf im Dashboard geöffnet, meldete in Schritt [5/7], der App-Ordner „konnte
nicht entfernt werden“, und ein leerer Ordner blieb liegen. Das neue Fenster hatte den Ordner der `.bat` als Arbeitsordner (`start /D`), und diese
`cmd.exe` wartet auf die nach `%TEMP%` verschobene Kopie — ein Prozess hält den Ordner fest, in dem er steht. Der Doppelklick auf die Datei im
App-Ordner hat denselben Arbeitsordner. Kein Test hatte das gesehen: die Strukturtests lasen die Datei, die Verhaltenstests führten nur ihre
PowerShell-Zeilen aus. Der neue Test führt den ECHTEN Anfang der Datei aus (Arbeitsordner = App-Ordner) und hängt einen Platzhalter an, der den Ordner
löscht; ohne die Korrektur kommt „GESPERRT“, mit ihr „WEG“. Regel: Eine Datei, die sich selbst verschiebt oder ihren eigenen Ordner löscht, gehört
mit Start AUS diesem Ordner getestet — und eine Reparatur an Installer oder Deinstaller ist erst fertig, wenn sie auf einem sauberen Rechner einmal
vollständig durchlief (Installation bis Deinstallation), nicht wenn die Einzelschritte grün sind.
*Belege:* Gegenprobe Hotfix 1.7.153 (05.10.2026), #1170 PP13, `tests/test_v18_praxisprobe_deinstaller.py`

**L52. Wer in fremde Dateien schreibt, ändert nur seine Zeile, prüft das Ergebnis und hat einen Rückfall — und was nach dem Löschen der eigenen
Datei kommt, läuft nie.** Zwei Funde der Gegenprobe: (a) Der Deinstaller las die Konfiguration von Claude, entfernte den Eintrag und schrieb die
GANZE Datei neu — in der Formatierung von Windows PowerShell (siebenmal so groß, anderer Leerraum, `"mcpServers": {}` als Rest). Inhaltlich gleich,
aber es ist nicht seine Datei. Jetzt wird nur der Eintrag aus dem Text genommen; ein Zähler für Klammern kennt Zeichenketten, das Komma geht mit, und
das Ergebnis wird gegen die erwartete Fassung geprüft (beide geparst und verglichen). Stimmt es nicht, gilt der alte Weg — so kann die neue Fassung
nichts schlechter machen als die alte. (b) `cmd` liest eine Batch-Datei Zeile für Zeile von der Platte. Löscht Schritt [5/7] die Ursprungsdatei, bricht
die wartende `cmd.exe` vor dem `del` in der nächsten Zeile still ab; die Kopie in `%TEMP%` blieb liegen. Was nach dem Löschen der eigenen Datei noch laufen soll,
steht in DERSELBEN Zeile. Beide Fälle hat kein Test gesehen, der die Datei nur las; sie fielen auf einem echten Rechner auf und wurden mit Tests
gesichert, die den echten Text der Datei ausführen (Platzhalter für den Rest, alles im Temp-Ordner).
*Belege:* Gegenprobe Hotfix 1.7.153 (05.10.2026), #1170 PP16/PP17, `tests/test_v18_praxisprobe_deinstaller.py`

**L53. `for /f` führt den Befehl über `cmd /c` aus — und `cmd /c` schneidet Anführungszeichen ab.** Am Ende jeder gelungenen Installation im 1.8-Zweig stand
„Die Syntax für den Dateinamen, Verzeichnisnamen oder die Datenträgerbezeichnung ist falsch.“, und die Einstellung zum Aufräumen (nie, fragen, immer) kam nie an.
Die Zeile `for /f "usebackq" %%E in (`"python.exe" "skript.py" arg "ordner"`)` beginnt mit einem Anführungszeichen und hat mehr als zwei: `cmd` entfernt das
erste und das letzte, übrig bleibt ein Befehl mit unpassenden Zeichen. Pfade ohne Leerzeichen helfen nicht; die Regel zählt Anführungszeichen, nicht Leerzeichen.
Ein zusätzliches Paar um den ganzen Befehl (`` `""python.exe" "skript.py" arg "ordner""` ``) behebt es. Kein Test hatte die Zeile je ausgeführt; sie fiel
beim dritten vollständigen Durchlauf auf dem frischen Rechner auf, als der Installer-Abschluss zum ersten Mal bis zum Ende angesehen wurde. Der Test führt
jetzt die ECHTE Zeile aus (Kopie des Basis-Python als Laufzeit, ein Skript, das „nie“ meldet). Regel: Jede Zeile mit `for /f` oder `cmd /c` und mehreren
Anführungszeichen gehört mit dem echten Text und einem Stand-in ausgeführt, nicht nur gelesen.
*Belege:* Praxisprobe 1.8, dritter Durchlauf (05.10.2026), #1170 PP18, `tests/test_v18_praxisprobe_start.py`

**L54. Unter `EnableDelayedExpansion` verschluckt `cmd` das Paar `!!` — eine Fehlermarke `[!!]` sagt dann nichts.** Beim Bau der Frage nach den 830 MB (PP10)
zeigte der Test für die gesperrte Datei „[]“ statt „[!!]“. Dieselbe Schreibweise steckte in zehn alten Meldungen des Installers und des Deinstallers
(„… konnte nicht entfernt werden“, „Datei in Benutzung?“): wer einen Fehler hatte, sah leere eckige Klammern vor dem Text. Kein Test hatte diese Meldungen je
ausgeführt; sie prüften Dateien und Rückgabewerte, und die Texte erschienen nur im Fehlerfall. Maskiert wird mit `^^!^^!` (wie bei „Willkommen^^!“ im Installer).
Zwei Tests sichern es: einer liest beide Dateien und verbietet die ungeschützte Schreibweise außerhalb von Kommentaren, einer führt das echte Unterprogramm mit
einer gesperrten Datei aus und erwartet die Marke im Wortlaut. Regel: Eine Meldung, die nur im Fehlerfall erscheint, gehört einmal im Fehlerfall ausgeführt und
im Wortlaut gelesen — ein Test, der nur „kein Absturz“ prüft, übersieht, dass die Meldung leer ist.
*Belege:* PP10-Bau (05.10.2026), #1170 PP19, `tests/test_v18_praxisprobe_deinstaller.py`

**L55. Wer außerhalb seines Ordners etwas ablegt, nennt es beim Entfernen — und nimmt nur das Seine mit.** Der Installer lädt den Browser für Quellen (Playwright) und füllt
den Zwischenspeicher von pip, zusammen rund 830 MB außerhalb von `%LOCALAPPDATA%\BewerbungsAssistent`. Der Windows-Deinstaller erwähnte beides nie, macOS und Linux fragten.
Jetzt fragt er zum Schluss, mit Ort und Größe, und die Vorgabe ist BEHALTEN: beide Ordner gehören nicht PBP allein (jedes Programm mit Playwright nutzt denselben Browser-Ordner,
jedes Python-Werkzeug den pip-Zwischenspeicher), und ein Deinstaller, der Fremdes mitnimmt, ist schlimmer als einer, der zu wenig entfernt. Von pip geht nur `Cache`, der Ordner
selbst nur, wenn er danach leer ist — liegt dort die `pip.ini` eines anderen Programms, bleibt sie. In einem Klammerblock steht der Pfad als `!VAR!`, nicht als `%VAR%`:
ein `)` im Benutzernamen (`Max (privat)`) beendet sonst den Block. Der Test führt das echte Unterprogramm in einem Temp-Ordner aus (`LOCALAPPDATA` umgebogen, QA-Isolation).
*Belege:* Praxisprobe 1.8 (05.10.2026), #1170 PP10, `tests/test_v18_praxisprobe_deinstaller.py`

**L56. Ein Prüfwerkzeug, das nicht in der CI läuft, veraltet still — und seine Meldung „Muster nicht gefunden“ ist kein Fehler.** Der Lauf aller fünf
Mutationskataloge vor Beta 16 (237 absichtlich eingebaute Fehler) fand zwei Einträge des Firmen-Katalogs, deren Suchmuster nicht mehr passten: die Einrückung
in `firma_kontext` hatte sich geändert. Beide Mutationen prüften seither nichts, und der Entwurf des CHANGELOG sagte trotzdem „alle erkannt“. Das Skript
druckt dann `MUSTER 0x gefunden (Eintrag nachziehen)` und zählt den Eintrag erst am Ende als offen. Nachgezogen; beide Fehler werden von den Tests erkannt.
Dazu ein Test (`tests/test_v18_mutationskatalog_muster.py`, läuft in der CI): jedes Muster kommt in seiner Datei genau einmal vor, die Kennungen sind eindeutig,
die Testdateien gibt es — gegen den alten Katalog schlägt er an und nennt fb06 und fb07. Regel: Wer eine Prüfung nur von Hand laufen lässt, braucht einen billigen Test
für ihre VORAUSSETZUNGEN, sonst merkt es niemand, wenn sie nichts mehr prüft (DoD 8c).
*Belege:* Beta 16 (06.10.2026), `scripts/mutationstest_auto_update.py`, `tests/test_v18_mutationskatalog_muster.py`

**L57. „Übersprungen“ in der Übersicht eines Pull Requests kann „abgebrochen“ heißen — und abgebrochen ist weder grün noch rot.** Drei Köpfe in Folge zeigten
`passing 1, skipped 1`; ich meldete „GitHub-Prüfung grün“. In Wahrheit war der Syntax-Job bestanden und der `pytest`-Job nie gelaufen: GitHub fand keinen
Rechner („The job was not acquired by Runner of type hosted even after multiple attempts“, `steps: []`). Der Lauf endete als `failure`, ohne dass ein Test lief.
Regel (steht in CLAUDE.md seit #1132, ich habe sie nicht angewandt): vor „CI grün“ und vor jedem Tag den Lauf lesen — `gh run view <id> --json jobs` — und prüfen,
dass der Test-Job Schritte hat und mit `success` endet; sonst `gh run rerun <id>` und abwarten.
*Belege:* Läufe 37362918664, 37363604915, 37372302207 (abgebrochen), 37376045112 (grün), 05.10.2026

**L58. Ein Browser-Test, der „manchmal“ rot ist, hat die Seite meist mitten im Aufbau erwischt — erst warten, bis sie ruhig ist, dann handeln.** Die vier Tests
`test_pp7_*` (ein Knoten wird von außen entfernt, dann wechselt die Verbindung) schlugen lokal in jedem dritten Lauf und in der GitHub-Prüfung zweimal von vier an,
mit zwei verschiedenen Meldungen. Gefunden mit einem `MutationObserver` und 60 Beobachtungsläufen: der Hinweis, den der Test sucht, erscheint nach 0,3 Sekunden,
noch bevor die Seite ihren Takt der Live-Aktualisierung gestartet hat; die EINE Änderung, die der Test auslöste, ging am noch nicht gesetzten Ausgangswert vorbei, die Seite
übernahm den Wechsel nie, und es gab keinen Absturz zu sehen. Behebung: warten, bis der Takt zweimal lief und 1,5 Sekunden nichts Neues kam; die Änderung alle
drei Sekunden wiederholen, bis das Ziel erreicht ist. 25 Läufe grün (vorher rund ein Drittel rot). Regel: vor dem Eingriff den Zustand der Seite abwarten, nicht die
Zeit; und ein Test, der zufällig rot ist, wird nicht wiederholt, bis er grün ist, sondern an einem Beobachtungslauf aufgeklärt.
*Belege:* Beta 16 (06.10.2026), `tests/test_v18_screenshot_generator.py`, GitHub-Läufe 37379191395 und 37379576626

**L59. Eine leere Vergleichsspalte ist ein Befund, kein Gutbefund.** Beim Zurücksetzen des Werkstatt-PCs druckte das Probe-Skript für die Claude-Konfiguration im
Paketordner `(Basis )` mit leeren Werten, weil der Zugriff auf das zweite Feld der aus JSON gelesenen Liste unter PowerShell 5.1 ins Leere ging; für die erste Konfiguration
stand dort „False“ und „-“. Es wäre leicht gewesen, „die Prüfsumme sieht ähnlich aus“ zu denken. Stattdessen wurden die Dateien direkt verglichen (Prüfsumme gegen die
gesicherte Kopie, Inhalt ohne das leere `mcpServers`); dabei fiel auch auf, dass der Installer die Datei neu einrückt (14.762 → 3.393 Bytes). Regel: sieht ein
Vergleich auf einer Seite „leer“ aus, ist es kein Vergleich; die Gegenprobe nimmt die Rohdaten (Bytes, Prüfsumme), nicht die gleiche Auswertung noch einmal (vgl. L52).
*Belege:* Werkstatt-PC, 06.10.2026, `docs/internal/praxisprobe-1.8.0.md`

**L60. Ein gefundener Fehler gehört zu einer Klasse — danach ALLE Stellen der Klasse suchen, nicht nur die eine.** PP13 (05.10.) war: ein Fenster erbt den
Arbeitsordner und hält ihn fest, der Deinstaller konnte seinen Ordner nicht löschen; behoben wurde der Deinstaller. Derselbe Fehler steckt in `INSTALLIEREN.bat`
(`start … /MIN` für das Dashboard-Fenster) und wurde erst bei der dritten Probe auf einem zweiten Rechner sichtbar (PP20: ein leerer Ordner bleibt stehen).
Eine Suche nach `start "` und `Start-Process` ohne Arbeitsordner in allen Installern am Tag des ersten Fundes hätte ihn gefunden. Regel: zu jedem Fund einen Satz
„welche anderen Stellen machen dasselbe?“ und die Suche dazu, noch im selben Zug (DoD 8c: ein Schutz zählt erst, wenn er überall greift).
Zweites Beispiel, #1177: Ein Klick auf einen Treffer der Suche oben tat seit v1.7.0 nichts — der Server lieferte Adressen (`#bewerbungen?id=…`), die das Dashboard seit H31 nicht mehr
las, und kein Test klickte je einen Treffer. Dieselbe Klasse („etwas erzeugt ein Sprungziel, niemand liest es“) steckte in den Wegen aus Beta 17: `wege.js` erzeugte `dokumentId` und
`terminId`, keine Seite las sie. Die Suche nach der Klasse ergab den Test `test_jede_absicht_hat_einen_leser_auf_einer_seite` (zu jedem Schlüssel, den ein Weg erzeugt, eine Lesestelle;
Ausnahmen mit Grund) und `dashboard_link.hash_ziel` als EINE Adressform für Links und Treffer; je Trefferart klickt ein Browser-Test und prüft, dass das OBJEKT offen ist.
Drittes Beispiel, #1184: Die Regel „der Text entscheidet, nicht die Angabe der Quelle“ (B63/#1072, JobSpy: `is_remote` ungeprüft) wurde für den JobSpy-Weg gebaut. Der Weg über den
Browserlauf (`stelle_manuell_anlegen`, `remote` vom Aufrufer) trug dieselbe Klasse und fiel erst auf, als Googles „Homeoffice“ eine rund 570 km entfernte Stelle nach oben sortierte.
Die Frage „welcher Weg schreibt `remote_level` aus einer fremden Angabe?“ ergab `services/google_angaben` als EINE Entscheidung, ob eine Angabe schon belegt ist. Dieselbe Klasse bei der
Dublettenprüfung beim Anlegen: sie sah nur Aktives, aber nie Aussortiertes (`find_aussortierte_dublette`).
Viertes Beispiel, #1238: Dass der Installer den Eintrag in der Claude-Konfiguration neu baut und das `env` des Menschen verwirft, wurde am 01.10.2026 in `_setup_claude.py` behoben
(v1.7.145, #1136). Drei weitere Schreiber derselben Datei bauten den Eintrag weiter selbst, `install.ps1`, `setup_gui.py` und `switch_mode.py`, und fielen erst am 16.10.2026
auf, als ein Schlüssel unter `env` nach dem Überinstallieren fehlte. Beim Nachstellen kam in `install.ps1` ein schlimmerer Bruder der Klasse dazu: ohne Konfigurationsdatei
oder ohne `mcpServers` schrieb das Skript GAR keinen Eintrag und meldete „geschrieben“ (`Add-Member` an einer Hashtable steht nicht im JSON; `-is [pscustomobject]` trifft in
Windows PowerShell 5.1 jeden Wert). Der Fund-Satz „welche anderen Stellen schreiben die Datei?“ ist jetzt ein Test, kein Vorsatz: `test_jeder_schreiber_der_konfiguration_ist_erfasst`
listet alle Dateien mit `mcpServers`, ein neuer Schreiber fällt auf, und jedem Schreiber wird dieselbe Beispielkonfiguration gereicht (Gegenprobe Katalog `claude_konfig`).
In der 1.8-Linie ist `install.ps1` seit #1149 ein Stub; dieselbe Testdatei gilt dort (die PowerShell-Fälle überspringen sich, ein Test verlangt vom Stub, die Konfiguration nicht
zu nennen), damit ein Fix in beiden Linien byte-gleich bleibt.
*Belege:* Werkstatt-PC, 06.10.2026, #1170 PP20, Lehre L51; #1177; #1184; #1238 (`tests/test_1238_installer_env_erhalten.py`)

**L61. Jede Seite im Leerlauf messen — ein Sturm wirft nie einen Fehler.** Beim Messen der Wege fiel ein Browser-Test von selbst um (die Liste war „leer“, obwohl
sie gerade gezeichnet war). Die Spur führte zu einer Seite, die im Stillstand 270 bis 470 Anfragen pro Sekunde schickte und den Hauptthread des Browsers zu zwei Dritteln
auslastete — seit März 2026 in jeder Fassung, auch in der Stable-Version. Keine Meldung, kein Absturz; man bemerkt nur einen lauteren Rechner. Ursache: eine Funktion
aus `useEffectEvent` stand in einer Abhängigkeitsliste (sie ist bei jedem Zeichnen neu, der Effekt startete nach jeder Antwort neu). Regel: zu jeder Seite die Messung
„zwei Sekunden Ruhe nach dem Laden, dann fünf Sekunden zählen (Anfragen, Rechenzeit)“; ein gesunder Leerlauf liegt bei 0,0 %. Das Muster ist durchsuchbar; ein
Wächter-Test (mit benanntem Bestand) hält neue Fälle fern.
*Belege:* #1171, `test_stellen_seite_fragt_im_leerlauf_nicht_hunderte_male`, `test_kein_effekt_ereignis_in_einer_abhaengigkeitsliste`

**L62. Ein Weg endet nicht beim Klick, sondern dort, wo das Ergebnis ankommt.** Die Wege A → B (Stelle ansehen, bewerten lassen, bewerben; bei einer Bewerbung nachfassen)
stimmten Klick für Klick, aber das Ergebnis des Dritten — das Urteil, das Claude gerade speichert — erschien im offenen Fenster nie, und die Seite sprang dabei an den
Anfang. Ein Weg-Test, der nur klickt, sieht das nicht. Regel: bei jedem Weg, an dem Claude mitschreibt, im Test das Schreiben nachstellen (über den einen Schreibort der
Datenbank) und prüfen, was der Mensch sieht: kommt es an, bleibt die Leseposition, flackert nichts?
*Belege:* #1171, `test_urteil_von_claude_kommt_im_offenen_dialog_an`, `test_notiz_von_claude_kommt_in_der_offenen_timeline_an`

**L63. Wer eine Endlosschleife entfernt, prüft, was sie nebenbei erledigt hat.** Die Reparatur der Stellen-Seite war eine Zeile und senkte die Last von 66 % auf 0,2 %.
Die Gegenprobe der Reparatur selbst — „sieht die Seite eine Suche, die Claude von außen startet, noch?“ — zeigte: vorher nach 0,1 Sekunden (durch Zufall: die Schleife
fragte ständig), nachher nach 26 Sekunden (die Seite fragte nur alle 30 Sekunden nach, so war es gedacht, hatte aber nie gewirkt). Hätte ich nur „Last gesunken, Tests grün“
geprüft, wäre ein Hotfix mit einer neuen, stillen Verschlechterung hinausgegangen. Regel: nach dem Abschalten eines Dauerläufers fragen, welche Beobachtung ihn bisher
unbemerkt als Taktgeber hatte, und genau diesen Weg messen — vorher und nachher, mit demselben Skript.
*Belege:* #1171, `test_suche_von_claude_steht_nach_wenigen_sekunden_auf_der_seite`, Gegenprobe wg33

**L64. Ein Test richtet seinen Zustand über denselben Weg ein wie der Betrieb — sonst prüft er einen Zustand, den es nie gibt.** Die Liste „eigene Ordner außerhalb des
Datenordners“ war seit v1.7.59 im Betrieb immer leer: gespeichert wird je Profil, gelesen wurde der Schlüssel ohne Profil. Der Test dazu blieb grün, weil er den Schlüssel selbst
ohne Profil schrieb — auf dem Weg, den das Produkt nie benutzt. Aufgefallen ist es erst, als eine Oberfläche den Ordner wirklich über den Schreibweg setzte. Dasselbe Bild beim
„Zurücksetzen“: den Platzhalter „-“ kannte nur das Werkzeug für Claude; der Weg über das Dashboard schickte ihn und bekam 400, am Feld stand nur „HTTP 400“. Regel: den Zustand
im Test über die öffentliche Schreibfunktion herstellen (hier `ablage.ordner_setzen`), nie über die Tabelle; und bei jedem Wert, der „leer“, „zurücksetzen“ oder „Standard“ kennt,
den Weg des Menschen (Oberfläche) mit dem Weg von Claude (Werkzeug) vergleichen (vgl. L1).
*Belege:* #1173, `test_gefahrenzone_nennt_eigene_ablageordner`, `test_rest_leer_und_minus_setzen_den_ordner_zurueck`, Gegenprobe sp25 und sp30

**L65. Zwei Auskünfte zur selben Frage müssen dieselbe Seite sehen — oder jede Meldung muss zu einem Ort führen, an dem man tun kann, was sie verspricht.** Die Seitenleiste sagte
„Neue Version verfügbar: v1.8.0-beta.18“, die Update-Seite „Aktuell“, und es gab keinen Knopf. Beide stimmten für sich: die allgemeine Prüfung nennt einer Beta-Installation auch
neuere Betas, die feste Quelle des Auto-Updates nie. Zusammen führte die Meldung in eine Sackgasse; aufgefallen ist es erst, als der Nutzer ihr folgte und „Mit einem Klick“
gewählt hatte. Regel: wo zwei Quellen dieselbe Frage beantworten („gibt es etwas Neues?“), steht an EINER Stelle, was gilt, wenn sie sich widersprechen; und jede Meldung
wird im Test bis zum Ziel angeklickt (vgl. L62), mit den Antworten beider Quellen als Attrappen — einmal übereinstimmend, einmal widersprüchlich.
*Belege:* #1179, `test_seitenleiste_und_update_seite_sagen_bei_einer_neueren_beta_dasselbe`, Gegenprobe vo01 und vo09

**L66. Ein Auftrag an Claude ist Code — er braucht eine Quelle, einen Wächter und eine Antwort auf den Zweifelsfall.** Ein Lauf über sechs Browser-Quellen mit rund 1.300 Rohtreffern
legte keine einzige Stelle in PBP an. Fünf Anleitungen (der Auftrag je Quelle, der Handoff einer Quelle, der Workflow-Prompt der Jobsuche, `google_jobs_url`, der LinkedIn-Plan) sagten
Claude, „passende“ Stellen zu übernehmen und Verworfenes im Chat zu melden; der Katalogtext von `stelle_manuell_anlegen` sagte „nicht für Treffer aus einer Jobbörse“. Jede Anleitung war für
sich vernünftig, zusammen machten sie Claude zum Türsteher: die Auswahl fand im Chat statt, der Mensch sah nur den Bericht. Dazu kehrte die Vorschau (`dry_run=True`, die Vorgabe) vor
jeder Prüfung zurück und zeigte „alle angelegt“. Regel: (1) Verlangt ein Auftrag eine Auswahl („passende“, „relevante“, „wichtige“), steht im selben Satz, was im Zweifel geschieht — sonst
entscheidet Claude, und zwar für den Menschen. (2) Diese Antwort steht als EINE Konstante im Code (`REGEL_IM_ZWEIFEL`), jede Anleitung setzt sie ein, ein Test verlangt sie in jeder, und ein
Wächter über den ganzen Quelltext verbietet die alte Formulierung auch dort, wo noch niemand hinsieht (vgl. L1). (3) Eine Vorschau stellt dieselben Fragen wie die Anlage und schreibt nichts;
der Test legt sie neben den echten Lauf und vergleicht die Zählungen — und prüft zusätzlich die erwarteten Gründe, denn zwei blinde Seiten wären auch gleich.
(4) Eine Auflage einer Quelle (jobtic, #1189: kein automatisches Auslesen, keine Kontaktdaten) gehört nicht nur in den Auftrag an Claude, sondern dorthin, wo PBP SELBST
handelt — Nachladen, Auto-Nachladen, Aging-Check, Qualitätsprüfung, Anlage. Dort fragt eine Funktion (`quellen_auflagen`), und ein Test stellt einen Client hin, der bei
jedem Abruf scheitert. Auch die Auswahl mit LIMIT gehört dazu: sonst füllen die gesperrten Stellen das LIMIT und verdrängen bei jedem Lauf dieselben anderen.
*Belege:* #1187, #1189 (`test_nachladen_ruft_eine_jobtic_adresse_nie_ab`, `test_die_auto_engine_waehlt_jobtic_stellen_gar_nicht_erst_aus`), `test_1187_jede_anleitung_setzt_die_regel_ein`, `test_1187_kein_text_im_code_sagt_claude_passende_treffer_zu_uebernehmen`,
`test_1187_vorschau_und_lauf_zaehlen_gleich_und_die_vorschau_schreibt_nichts`, Gegenprobe bw01 bis bw30

**L67. „Ohne Administratorrechte“ und „der Ordner wird gehalten“ lassen sich nur auf einem Rechner belegen, auf dem das wirklich so ist.** Das Setup der Texterkennung verlangt Administratorrechte (`WinError 740` aus einem Programm ohne Erhöhung), und der Aufräum-Helfer des Installers starb am ersten Versuch, weil das Installer-Fenster den Ordner hält. Beides war auf dem Entwicklungsrechner unsichtbar: dort laufen Programme mit Erhöhung, und Windows (Build 26200) löscht einen gehaltenen Ordner trotzdem. Die Tests ersetzten genau die Funktion, die scheitert (`_loeschen_versuchen` ganz), und prüften also nichts. Regel: bei jeder Aussage „geht ohne …“ oder „bleibt liegen, solange …“ steht dabei, auf welchem Rechner und unter welcher Bedingung sie gesehen wurde; ein Test, der die scheiternde Stelle ersetzt, belegt sie nicht; der Beleg ist der Lauf auf einem Rechner ohne die Rechte (zweiter Lauf auf dem Werkstatt-PC, 11.10.2026).
*Belege:* PP24, PP26, `test_v18_texterkennung_ohne_admin_pp26.py`, `test_v18_installer_reste_pp24_pp25.py`, `docs/internal/praxisprobe-1.8.0.md`

**L68. Ein Test, der Windows nur nachstellt, läuft unter Linux anders — Pfade und Rechte nie mit POSIX-Annahmen bauen.** Zwei Fehler der Reparatur färbten die Linux-Prüfung rot (10 Tests), obwohl die Suite unter Windows grün war: (1) `Path(basis) / r"Programs\Tesseract-OCR"` ist unter POSIX EIN Name mit Backslash; (2) `os.chmod(ordner, S_IWRITE)` macht einen Ordner unter POSIX unlesbar (nur schreiben), der nächste Durchgang scheiterte schon am Öffnen. Regel: Windows-Teilpfade mit `PureWindowsPath(…).parts` zerlegen, Ordner mit `S_IRWXU` freigeben; ein unabhängiger Leser sagte beides aus dem Quelltext voraus, bevor die CI es zeigte — der Lauf vor dem Push lohnt sich.
*Belege:* `_benutzer_ordner_win`, `_freigeben`, die CI-Läufe vom 11.10.2026 (Köpfe 5c3f8016 bis 3f878131)

## 16. Bedienung messen: Wege, Listen und Prüfläufe

**L69. Ein Teil-Lauf ist kein Lauf — vor jedem Commit auf dem Release-Zweig die ganze Suite, in Teilen parallel.** Am 12.10.2026 liefen
fünf Wächter und 17 Muster des Mutationskatalogs seit mehreren Commits rot (Adress-Wächter, #948-Wächter, SQL-Spalten, Werkzeugnamen,
Typ-Kennungen, ein veralteter Installer-Test): jeder Commit hatte nur die Tests seiner eigenen Änderung gesehen, und die CI lief für den
Zweig noch nicht. Die ganze Suite (9.093 Tests) lief danach in sechs parallelen `pytest`-Prozessen (je eigene Datenbank und Ports) in
neun Minuten, die Browser-Tests (628) in vier — nicht mehr „zu lang zum Mitlaufen“. Dazu: ein Wächter, der Muster in Quelltext sucht,
gehört selbst in die Suite (hier `test_v18_mutationskatalog_muster.py`) und versteht Knotenkennungen (`datei::funktion`), sonst veraltet
er still.
*Belege:* #1171, #1170, `test_v18_mutationskatalog_muster.py`, Commit ac57ecdf

**L70. `position: sticky` greift nicht hinter einem Vorfahren mit `overflow-x: auto` — und ein Test, der nur den Quelltext liest, sieht
`sticky` und wird grün.** Die feste Leiste der Firmen-Ansicht stand im Quelltext richtig da und blieb beim Scrollen nicht stehen: der
Inhalt der App scrollt waagerecht (`overflow-x-auto`, damit nichts verschwindet), und damit ist dieser Vorfahr der nächste scrollende,
auch wenn er senkrecht nie scrollt. Gefunden hat es der Browser-Test, der WIRKLICH scrollt und die Lage der Leiste misst; behoben wurde
es, indem die Leiste in den festen Kopf der App gezeichnet wird (Portal). Beim Testen des Scrollens: `scroll-behavior: smooth` macht
`scrollTop` direkt nach `scrollTo` zu 0 — `behavior: "instant"` nehmen.
*Belege:* #1171, `test_die_leiste_der_firma_bleibt_beim_scrollen_der_historie_stehen`, Gegenprobe fl04/fl08

**L71. „Ohne Scrollen“ ist eine Zahl — ein Wächter misst die Unterkante der ersten Zeile bei den zwei Fenstergrößen, mit Luft.** Die
Listen begannen nach 600 bis 900 Pixeln; das hatte jeder gesehen und niemand gemessen. `test_v18_listen_zuerst_1171.py` setzt die
Fenster auf 1366 × 768 und 1920 × 1080 und verlangt, dass die erste Zeile samt Hauptknopf unter der Falz endet — nicht „bei y = 404“, denn
die Schriftbreite der Linux-CI verschiebt um Zeilen. Eine Messung, die nur bei genau einer Schrift grün ist, wird nach dem zweiten
roten Lauf ausgeschaltet; die Mutanten, die nur wenige Pixel verschieben (Innenabstand der Filterkarte), bleiben deshalb bewusst
unerkannt und stehen nicht im Katalog.
*Belege:* #1171, `docs/internal/wegetabelle-1171.md`, Gegenprobe lk01 bis lk11

**L72. Eine Option ist erst bewiesen, wenn der letzte Schreibvorgang gelaufen ist — ein Test, der nur die Auswahl prüft, beweist die
Anzeige.** Der Schalter „Vorabversionen automatisch“ (#1199) ließ die Prüfung „neu“ melden, aber Start, Vorbedingung und Manifest der
Installation kannten nur stabile Fassungen: „Jetzt installieren“ scheiterte. Der Test prüfte nur, welcher Kandidat gewählt wird; und der
Archiv-Bauer übersprang bei einer Vorabversion gerade die eine Prüfung (Manifest gegen den Leser, „würde zu Recht abgewiesen“), die den
Widerspruch gezeigt hätte. Regel: für jede Option ein Test, der mit einem echten Archiv bis `aktuell.txt` läuft (Gegenprobe: jede der
Sperren einzeln aus); jede Stelle, die eine Prüfung „aus Gründen“ auslässt, ist die verdächtige.
*Belege:* #1222, `test_v18_vorab_installation_1222.py`, Gegenprobe vi01 bis vi05

**L73. Ein Ereignis, das den Zustand ändert, ist in BEIDEN Zweigen zu testen — und eine Schleife über einen Stapel, den die Schleife selbst
füllt, läuft endlos.** Die Zurück-Taste (#1171 Baustein 4) war nur ohne Eingabe getestet. Mit Eingabe legte `zurueck()` seinen Eintrag
wieder auf den Stapel, über den die Schleife gerade lief: die Seite fror ein (gemessen: 100 Sekunden, dann beendete der Browser den Tab).
Regel: einen Stapel erst abtragen, dann abarbeiten (und von unten nach oben, damit ein Dialog, der sich wieder hinlegt, die Reihenfolge
behält); je Handler mit „geändert“-Zustand ein Test mit und einer ohne Änderung, und einer, der danach prüft, dass die Seite noch antwortet.
*Belege:* #1210, `test_1210_*`, Gegenprobe pf01

**L74. Wächter lesen Namen und Zeilen — ein neuer Name im Code muss durch die Wächter-Muster, bevor er eingecheckt wird.** Zwei Fälle am
selben Tag: `pbp_norm(` in einer SQL-Zeichenkette las der Werkzeugnamen-Wächter (#1148) als Werkzeug (erstes Segment `pbp` wie bei
`pbp_diagnose`); ein zweites `setlocal EnableDelayedExpansion` im Fehlerzweig einer .bat verletzte PP19 (das ERSTE ist das, nach dem
kein `endlocal` mehr stehen darf). Beide fielen erst in der ganzen Suite auf (L69), nicht in den Tests der eigenen Änderung. Regel: Namen,
die wie ein Aufruf aussehen, beginnen nicht mit einem Werkzeug-Präfix; in .bat-Dateien gibt der Fehlerzweig Pfade ohne eigenes `setlocal`
aus (`set PBP_ORT_` druckt Werte, ohne dass ein `&` im Pfad als Befehl gelesen wird).
*Belege:* `test_1148_kein_text_verweist_auf_ein_werkzeug_das_es_nicht_gibt`, `test_pp19_die_maske_gilt_nur_unter_verzoegerter_expansion`

**L75. Drei unabhängige Leser fanden 19 Fehler in einem Stand, den die eigene Gegenprobe (534 Eingriffe) für sauber hielt — der Leser
ohne Vorwissen lohnt vor JEDEM Testlauf.** Updates und Backend: 8 (verfallener Zähler, Schreibweisen des Schlüssels, Vorschau gegen Lauf,
Umlaute und Leerraum im Vergleich, …), Installer: 5 Issues mit 8 Befunden (Anführungszeichen um `$PYTHON`, echte Datenbank im
Funktionstest, grüner Schluss trotz stehengebliebenem Eintrag, …), Frontend: 6 (die Zurück-Taste friert ein, …). Die Gegenprobe prüft nur,
was ich mir ausgedacht habe; ein Fremder fragt „und wenn der Ordner ein Leerzeichen hat?“. Regel: den Prüfer mit den Dateien beauftragen,
nicht mit meiner Zusammenfassung; jeden Fund am Code belegen, als Issue führen und mit einem Test beheben, der VOR der Korrektur rot war.
*Belege:* #1201 bis #1220, Katalog `pruefung1214`

**L76. Ein Schalter, der die Frage ändert, stellt die Frage neu — und ein gemerktes Ergebnis trägt den Stand der Einstellung, mit der es
geholt wurde.** „Vorabversionen automatisch“ (#1199) änderte, WAS gefragt wird (mit oder ohne Vorabversionen), aber das Ergebnis der letzten
Prüfung wusste nichts davon: nach dem Einschalten las die Karte „Schalter an, nichts gefunden“ als „andere Linie“ und sagte etwas Falsches,
bis jemand „Jetzt prüfen“ klickte. Regel: jede Einstellung, die in die Frage eingeht, steht im gemerkten Ergebnis (Speicher UND Platte), der
Zwischenspeicher gilt nur bei gleichem Stand, das Umschalten holt die Antwort in derselben Anfrage, und eine Anzeige sagt „noch nicht
geprüft“ statt eines Grundes, den sie nicht belegen kann.
*Belege:* #1226, `test_v18_vorab_schalter_1226.py`, Gegenprobe vs01 bis vs10

**L77. Eine Probe auf den eigenen Rechner kann unter Windows je Adresse den vollen Zeitablauf kosten — gemessen wurde es am echten PC, nicht
am Entwicklungsrechner.** `localhost` heißt `::1` und `127.0.0.1`; verwirft die Firewall das SYN an einen geschlossenen Port, wartet jede
Adresse die ganze Frist (2 × 2,0 s), und in einem `async def`-Handler steht der Server dabei. Der Entwicklungsrechner hat ein laufendes Ollama
und sah nichts. Regel: erst eine kurze TCP-Probe je Adresse (0,5 s), dann die Abfrage an die Adresse, die angenommen hat; Netzaufrufe nie
in einem `async def`-Handler; und eine Suite, die „Dienst da“ nur über ein untergeschobenes `urlopen` simuliert, einmal mit GESCHLOSSENEM
Port laufen lassen (`no_ollama_plugin`), weil sie sonst auf dem Entwicklungsrechner durchläuft und auf der CI nicht.
*Belege:* #1227, `test_v18_ollama_probe_1227.py`, Gegenprobe ol01 bis ol06

**L78. Was der Installer außerhalb des Programmordners anlegt, muss der Updater mitführen — und ein Test, der die Registry berührt, vergleicht
den Ort, bevor er schreibt.** `DisplayVersion` in „Apps & Features“ schrieb nur `INSTALLIEREN.bat`; nach einem Auto-Update stand dort für immer
die Fassung der Erstinstallation (gemessen: laufend 1.9.0-rc.2, Registry 1.9.0-rc.1). Der Abgleich beim Start ändert nur einen vorhandenen
Eintrag, nur diesen Wert, nur wenn `InstallLocation` auf den laufenden Programmordner zeigt (über den echten Pfad: Junction, 8.3-Name) — sonst
schriebe die Suite auf einem Rechner mit echter Installation in deren Registry.
*Belege:* #1228, `test_v18_windows_liste_1228.py`, Gegenprobe rg01 bis rg08

**L79. Ein Knopf, der nach seinem Rückweg heißt, wird auch nach vorn benutzt — Wortlaut, Verlauf und Rückfrage je Richtung.** „Beim nächsten
Start nutzen“ gilt für jede installierte Fassung; im Verlauf stand für einen Schritt nach vorn „Zurückgeschaltet · zurück von A auf B“. Regel: wo
eine Funktion zwei Richtungen hat, trägt der Verlaufseintrag die Richtung, die Rückfrage nennt sie, und die ausdrückliche Wahl hebt eine frühere
Zurücknahme dieses Ziels auf (wie die ausdrückliche Installation).
*Belege:* #1229, `test_v18_umschalten_richtung_1229.py`, Gegenprobe um01 bis um06

**L80. Das Probe-Paket trägt den Stand VOR dem Fix — für den Rückbau auf dem Zielrechner die korrigierte Fassung des Kandidaten laden.** Die
Archive rc.1/rc.2 der Probe-Veröffentlichung enthielten den Deinstaller ohne die Korrektur von #1224; der Abbruch nach der Backup-Frage war auf
dem PC der bekannte Fehler der alten Fassung, nicht ein neuer. Regel: Werkzeuge für den Rückbau (Deinstaller, Skripte) nie aus einem Paket nehmen,
das vor der Korrektur gebaut wurde; die Datei des Kandidaten laden (rohe Datei, Zeilenenden für `cmd` auf CRLF bringen) und aus `%TEMP%` starten.
*Belege:* #1224, PP30

**L81. Beim Rückbau nicht Claudes eigene Einstellungen überschreiben — die Kopie vom Anfang gilt nur, wenn die Anwendung nicht lief.** Die Store-
Konfiguration von Claude Desktop hatte sich während des Laufs selbst geändert (Ordnerfreigaben, Zwischenspeicher-Schalter, `epitaxyPrefs`); ein
Zurückkopieren der Sicherung vom Anfang hätte diese Schlüssel zurückgesetzt. Regel: vor dem Zurückkopieren die Schlüssel vergleichen (nur alt,
nur neu, anders); entfernt wird nur, was PBP hinterlassen hat (leerer `mcpServers`, die neue klassische Datei), und der Bericht nennt, dass die
Prüfsumme deshalb nicht gleich ist.
*Belege:* Block H des dritten Laufs, `praxisprobe-1.8.0.md`

**L82. Ein Fremdbeitrag läuft nicht über die CI des Beitragenden: den Zweig lokal holen, ganz lesen, an den Abnahmepunkten des Issues messen.** Ein Pull-Request aus einem Fork darf eigenen Code in den Lauf bringen (Tests, Workflow-Dateien); wer den Lauf freigibt, gibt diesen Code frei. Vorgehen (PR #1230 zu #1198): (1) den Kopf in einen eigenen Arbeitsbaum holen, nie in den Arbeitsordner; (2) den ganzen Diff lesen, auch Tests und alles außerhalb von `src/`; (3) die volle Suite dort laufen lassen, mit isolierter Datenbank; (4) eigene Abnahmetests nach den Punkten des Issues schreiben, unabhängig von denen des Beitrags, und sie auf der ALTEN Fassung laufen lassen: sie müssen rot sein (hier 3 von 6), sonst messen sie den Fehler nicht; (5) übernehmen mit `cherry-pick -x`, damit der Autor im Verlauf bleibt, Kommentare und Texte in die Sprache des Codes bringen, in beide Linien. Freigegeben, zusammengeführt oder kommentiert wird erst auf das Wort des Nutzers.
*Belege:* #1198, PR #1230, `test_v17158_vermittler_endkunde_1198.py` (Stable), `test_v18_vermittler_endkunde_1198.py` (1.8), Gegenprobe vm01 bis vm06

**L83. Was ein Werkzeug still schließt, löst nur eine ausdrückliche Absicht aus — und die Vorgabe ist die Wirkung, die nichts verliert.** Seit #1123 galt jede Notiz an einer Bewerbung als „Kontakt mit dem Arbeitgeber“ und machte den automatischen Nachfass hinfällig; der übliche Ablauf (Bewerbung anlegen, dann gleich eine interne Notiz) ließ die Erinnerung nach Minuten sterben. Gemessen am echten Bestand: vier automatische Schließungen, zwei zu Unrecht. Regel: eine Wirkung, die etwas beendet, hängt an einem Parameter, den der Aufrufer bewusst setzt (`art`), nicht an einem Ereignis, das nur „etwas schreibt“; die Vorgabe lässt den Zustand stehen. Dazu: das Rückgabefeld trägt den GESPEICHERTEN Zustand (`nachfassung_hinfaellig`, nicht „erledigt“), und eine unbekannte Art wird abgewiesen, bevor etwas geschrieben wird. Ein Test, der die Folge einer Regel prüft, nimmt den Ablauf, der sie im Alltag auslöst (anlegen, dann notieren), nicht nur den Aufruf allein.
*Belege:* #1232, #1123, `test_v17158_nachfass_notiz_1232.py`, Gegenprobe nf01 bis nf12

**L84. Ein Beleg zählt nur für das, wofür er einer ist — und was eine Zählung folgert, entscheidet EINE Funktion für alle Wege.** Der Wiedergänger-Zähler (#671) nahm jeden Aussortier-Grund als Beleg, auch `bewerbung_erstellt`: die Stelle ging aus der Liste, weil sich der Mensch beworben hat, das GEGENTEIL einer Ablehnung. Zwei Fassungen derselben früheren Bewerbung machten eine gelesene, empfohlene Stelle zum k.o. (`stellen_anzeigen`: NICHT_EMPFOHLEN, unter allen anderen, bei `nur_empfohlen` ganz heraus); die Automatik nach einer Suche hätte sie ohne Rückfrage aussortiert. Vier andere Stellen des Codes schlossen den Grund längst aus (`kalibrierung`, `lerninsights`, `lernprotokoll`, `fachwert`), und die Analyse fragte „fachlicher Grund?“, die Liste „irgendein Muster?“ — dieselbe Frage in der fünften und sechsten Fassung (L1). Regel: vor jeder Zählung nennen, welche Frage ein Datensatz beantwortet, und die Ausnahme in EINER Liste führen (`KEIN_URTEIL_GRUENDE`); die Folgerung („ist das ein k.o.?“) in EINER Funktion (`ist_fachlicher_ko`), die Liste und Analyse gemeinsam fragen. Der Test nimmt den Fall aus dem Alltag (zwei Fassungen einer Bewerbung, dann eine neue Stelle), nicht nur den Aufruf; auf dem Altstand waren 17 von 25 rot, und die Gegenprobe nimmt Liste, Funktion und Rollenwörter einzeln heraus.
*Belege:* #1234, `test_v18_wiedergaenger_urteil_1234.py`, Gegenprobe wg01 bis wg21

**L85. Der erste Treffer eines Dienstes ist eine Schätzung, sobald der Dienst mehrere kennt — und die Schwelle dazwischen misst man, man rät sie nicht.** `geocode(exactly_one=True)` gab bei „Rosengarten“ den Treffer mit dem höchsten Gewicht zurück; die Stelle stand mit 24 statt rund 500 km als nah in der Liste, und nichts sagte, dass der Ort geraten war. Gemessen an 15 Abfragen (Nominatim, 16.10.2026, von Hand im Sekundentakt, nicht in der Suite): bei mehrdeutigen Namen liegen die Gewichte der zwei wichtigsten Orte höchstens 0,061 auseinander, bei Frankfurt, Halle oder Offenbach mindestens 0,136; in der Lücke steht die Grenze (0,10). Ein Verhältnis hätte kaum getrennt (1,13 gegen 1,23). Regel: Unbekannt ist ein Zustand (L7): ein mehrdeutiger Ort hat KEINE Entfernung, nicht die erstbeste; der Befund wird samt Grund und Kandidaten gemerkt, damit die Oberfläche erklären kann, warum nichts dasteht. Ein Fix am Dienst heilt nur NEUE Anfragen (#1158): Speicherzeilen aus der Zeit davor gelten als ungeprüft (Stand), und der Bestand wird nachgeprüft — begrenzt je Lauf, ohne von Hand gesetzte Werte, ohne Postleitzahl-Orte und große Städte. Die Testdaten sind die gemessenen Zahlen; die Suite braucht kein Netz.
*Belege:* #1235, #1158 Punkt 8, `test_v18_ortsdienst_mehrdeutig_1235.py`, Gegenprobe od01 bis od27

**L86. Wer an einem Fragenkatalog einstellt, misst danach nur die Einstellung — die ehrliche Zahl steht in einer Gruppe, die nie gesehen wurde.** Die Suche der Hilfe (#1233) traf auf die 42 Fragen, an denen sie eingestellt wurde, in 95 % der Fälle unter den ersten drei, auf 41 danach angesehene in 98 %; auf 42 frisch geschriebene, zum Einstellen nie benutzte Fragen zuerst nur in 64 %, nach Synonymen und Wortregeln in 76 %. Der Unterschied sind die Wörter der Menschen („Word-Datei“ statt „DOCX“, „Zahl“ statt „Punkte“). Regel: die Gruppen VOR dem Einstellen trennen und die ungesehene aufheben; Schwellen im Test auf die ehrliche Zahl setzen, nicht auf die schmeichelnde, und den Stand in CHANGELOG und Known Issues nennen (L19 bis L22). Zwei Versuche, die Lücke mit der lokalen KI zu schließen, schnitten schlechter ab als die einfache Suche und sind NICHT eingebaut: die KI ordnet zu (21 gegen 32 von 42), die KI erzeugt je Abschnitt typische Fragen (33 gegen 32 auf den neuen, 76 gegen 80 von 83 auf den beiden anderen Gruppen). Samt dem schon geschriebenen Lesepfad für die erzeugten Fragen, der wieder herauskam: ein Leser ohne Schreiber behauptet eine Fähigkeit, die keiner nutzt (L11). Wo ein Sprachmodell nur umformuliert, prüft eine Funktion seine Antwort, bevor sie erscheint (Quelle genannt, keine erfundene Adresse, kein erfundener Befehl, kein erfundener Menüpfad), und die Kurzantwort steht standardmäßig aus.
*Belege:* #1233, `test_v18_hilfe_suche_1233.py`, `test_v18_hilfe_ki_1233.py`, `tests/hilfe_fragen_1233.py`, Gegenprobe hi01 bis hi36

**L87. Die Erfolgsmeldung eines Installers beweist, dass wir geschrieben haben, nicht dass der Leser es liest — und der Ort einer fremden Datei wandert mit der Fassung des Fremdprogramms.** Claude Desktop aus dem Store liest seine Konfiguration ab der Paketversion 2.4 aus `%LOCALAPPDATA%\Claude-Data\claude_<Kennung>\`. `_setup_claude.py` schrieb weiter nach `%APPDATA%\Claude` und in den Paketordner, meldete „konfiguriert“, und Claude startete PBP nie; der Deinstaller führte dieselbe Liste und meldete „entfernt“ über einen Eintrag, der stehen blieb. Alle Tests verglichen die Liste des Installers mit der des Deinstallers (L48) und keiner fragte, ob irgendwer die Datei liest; aufgefallen ist es erst auf dem Werkstatt-PC. Die Probe eines Ortes ist das Verhalten des Lesers: Eintrag in die Datei, Claude neu starten, das Dashboard sagt „verbunden“. Im Code bleibt, was sich prüfen lässt: der Eintrag wird nach dem Schreiben zurückgelesen, und ein Ort zählt nur, wenn die Fremdanwendung ihn selbst angelegt hat (der Ordner existiert), nicht weil wir ihn für richtig halten.
*Belege:* #1245, PP37/PP37b, `test_v17159_claude_konfig_ort_1245.py`, Gegenprobe co01 bis co12

**L88. Ein Befund „gibt es nicht“ über die Oberfläche entsteht im Quelltext, nicht am Bildschirm eines Prüfrechners — die Oberfläche hängt vom Zustand ab.** PP38 (#1246) meldete eine „erfundene“ Schaltfläche „Update-Optionen“. Sie ist eine echte Aktion an den Update-Hinweisen, die nur bei einem bekannten Update erscheinen, und sie stand in den Abschnitten, aus denen die Kurzantwort entstand: die Prüfung hatte zu Recht durchgelassen. Der Fehlbefund stand in fünf Texten (Issue, zwei Kommentare, Plan, Notizen), bevor die Umsetzung ihn zurücknahm; der zweite Irrtum desselben Laufs (PP39: „Melden hat ein Formular“, es hat keine Eingabefelder) zeigte dasselbe Muster. Vor einem Befund die Bezeichnung im Quelltext suchen und den Zustand nennen, in dem sie erscheint; beim Umsetzen eines eigenen Issues zuerst die Voraussetzung nachlesen, dann bauen — und eine Härtung ohne Vorfall nicht auf Verdacht.
*Belege:* #1246 (geschlossen als nicht geplant), #1247, `test_v18_hilfe_frage_browser_1233.py`, Gegenprobe hs01 und hs02
