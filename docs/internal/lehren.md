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
*Belege:* #963, #913, #976, #991, #992, #951, #1017, #1036, #1051, v1.7.132/1, #1106 (Blacklist auf den Bestand war die fuenfte Fassung neben `blacklist_regel`)

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
*Belege:* #1028, #663, #1080, #1089, v1.7.53/1, v1.7.77/1, v1.7.138/3, v1.7.143/1 (Akzente: 'Société Beispiel' gegen 'Societe Beispiel Deutschland GmbH' — der Teilstring scheitert am Akzent; gefaltet wird NACH der Umschrift der Umlaute, sonst wird aus 'Müller' ein 'Muller')

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
*Belege:* v1.7.79/9, #1031, #1026, #1019, #1036, v1.7.102/6, v1.7.114/9, v1.7.122/12, v1.7.127/6, v1.7.133/6, #1106 (stumme Gegenproben fanden fehlende isolierende Faelle und wirkungslosen Code), #1120 (Ausbau eines "wirkungslosen" Mechanismus war am Fixture gruen und an den echten Mails falsch — nach jedem Ausbau erneut an echten Daten messen), #1122 (drei von vier CSS-Aenderungen blieben einzeln gruen; zwei davon zusammen ebenfalls — ausgebaut statt mitgeliefert), #1123 (ein Typ-Vorfilter war neben der schliessenden Funktion wirkungslos), v1.7.143/4 (34 Mechanismen im Backend, 5 in der Oberfläche mit Neubau nach jedem Ausbau; alle rot)

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
Beim Portieren: `cherry-pick --continue` verschluckt Betreffe, die mit
`#` beginnen (`-c core.commentChar=;`); ein Modify/Delete-Konflikt hat keine
Marker und darf nie automatisch als geloest gelten — so kam ein
1.8-Modul auf die Stable-Linie. Quelltext-Tests, die Bauformen per
Zeichenkette suchen, vor dem Umbenennen per grep finden (die CI fand zwei).
*Belege:* v1.7.8, v1.7.16, v1.7.12/5, #997, #998, #1016, v1.7.136/8, v1.7.138/5, v1.7.139/8, v1.7.140 (#1102, #1113), #1130 (30.09.2026: als Hotfix-Kandidat vorgeschlagen, im Tag v1.7.143 gab es die Datei nicht)

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
*Belege:* #1163 (Installer-Helfer, Selbsttest, pip, Komponenten, Texterkennung), `tests/test_v18_auto_update_pfade.py`, `tests/test_v18_ocr_pfade.py`

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
