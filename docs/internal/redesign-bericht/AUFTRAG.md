# Auftrag: Bewerbungsbericht und Statistik neu (PBP #798, mit #1337 und #1420)

Stand 21.11.2026. Verfasst von Claude (Chat-Instanz) nach Untersuchung an 1.8.8 in einer isolierten Testinstallation (`BA_DATA_DIR`, Musterprofil mit 25 Bewerbungen). Dieselbe Analyse steht als Kommentar in #798. Diese Datei ist die Arbeitsgrundlage für die Umsetzung.

## Entscheidungen des Betreibers (21.11.2026)

1. Reihenfolge: erst die Fehler (#1337, #1420), dann der Neuentwurf (#798), dann wird Videofolge 10 neu gedreht.
2. Seite 1 der Auswertung: **Variante A (Zahlen zuerst)**. Variante B (jede Bewerbung als Linie) wird nicht gebaut.
3. Gebaut wird von Claude Code auf der Workstation.

## Vorgaben von Claude, solange der Betreiber nichts anderes sagt

1. Kosten im Nachweis: Vorgabe **aus**, ein Haken in Einstellungen › Erweitert › Bewerbungsbericht schaltet sie ein (Datensparsamkeit gegenüber dem Amt).
2. Titel des Dokuments: „Nachweis der Bewerbungsbemühungen“.

## Die Entwurfsdateien in diesem Ordner

Vier Dateien `entwurf-*.dc.html`. Es sind Quelltexte eines Entwurfswerkzeugs, keine fertigen Seiten: Im oberen Teil steht das Markup mit allen Abständen, Schriftgrößen und Farben als Inline-Stil, im Skriptblock unten stehen die Musterzahlen (`renderVals`). `<sc-for>` ist eine Schleife über eine dieser Listen, `{{name}}` ein Platzhalter. Ohne das Werkzeug lassen sie sich nicht im Browser öffnen; sie werden gelesen, nicht ausgeführt.

1. `entwurf-nachweis-seite1.dc.html` und `entwurf-nachweis-seite2.dc.html`: A4 hoch, 794 x 1123 px bei 96 dpi.
2. `entwurf-auswertung-seite1.dc.html`: A4 hoch, Variante A.
3. `entwurf-statistik-seite.dc.html`: Seite im Dashboard, fließende Breite.

Maßgeblich sind Aufbau, Reihenfolge, Wortlaut der Überschriften und die Regeln unten. Pixelgenau muss nichts sein. Die Farben des Entwurfs (Dunkelblau `#1d4f91`, Grautöne) sind für den Druck gewählt; die Statistik-Seite folgt dem bestehenden Erscheinungsbild des Dashboards. Die Zahlen im Entwurf sind Musterdaten: Die Bewerbungen stammen aus dem Musterprofil, die Daten der Ereignisse (Gespräche, Rückmeldungen) sind für den Entwurf frei gesetzt, weil das Musterprofil dafür heute keine brauchbaren Daten hat (siehe Bestandsaufnahme, Punkt 6).

## Analyse und Entwurf

### 1. Bestandsaufnahme

1. **PDF** (`export_report.py`, 1851 Zeilen, fpdf2, matplotlib mit Rückfall auf Balken): 9 Seiten, 13 Abschnitte in der Reihenfolge ihrer Entstehung. Seite 1 ist Deckblatt plus Inhaltsverzeichnis; die erste Zahl steht auf Seite 2. Die Bewerbungsliste, das Einzige, was ein Amt braucht, steht auf Seite 4.
2. **Ein Dokument für zwei Leser.** Das Amt bekommt Punktzahlen, Ablehnungsquoten, Schlüsselwort-Analyse und „Nicht beworben trotz gutem Fit-Score“ mit. Der Bewerber bekommt keine Antwort auf „Was läuft, was steht an, was funktioniert?“.
3. **Zeitraum:** wirkt auf Deckblatt, Liste und Protokoll, nicht auf Kennzahlen, Kanal-Tabelle, Kosten, Excel-Blatt „Statistik“ (#1337, #1420 B1).
4. **Statistik-Seite** (`StatsPage.jsx`): Die Zeitraum-Wahl geht nur an `/api/stats/timeline`. `/api/stats/scores`, `/api/stats/extended`, `/api/statistics`, `/api/rejection-patterns` und `/api/stats/style` laufen ohne Zeitraum. Die Seite zeigt also Zahlen aus verschiedenen Zeiträumen nebeneinander, ohne es zu sagen.
5. **Widersprüche auf der Statistik-Seite:** „Beworben 17, 73,9 % Trefferquote“ (Stellen mit Bewerbung) steht neben „25 Bewerbungen“. Zwei Kreisdiagramme zu Quellen („Quellen-Verteilung“, „Bewerbungs-Quellen“) mit abgeschnittenen Beschriftungen. Rund 20 Karten ohne Rangfolge; „Heute 0, 0, 0“ steht ganz oben.
6. **Musterprofil:** Alle Ereignisse tragen den Zeitstempel des Anlegens. Deshalb „Prozessdauer 0.0 / 0.0 Tage“, und das Aktivitätsprotokoll zeigt 23 Statuswechsel am selben Tag. Die Schlüsselwort-Analyse führt mit „fiktive, musterstelle, demo, zwecke“. Das Schaufenster zeigt den Bericht damit von seiner schwächsten Seite.
7. **Sprache und Form:** #1420 B2, B3, B6.

### 2. Zielgruppen: zwei Dokumente aus einem Datenkern (begründeter Vorschlag)

Nicht ein Dokument mit Anhang, sondern zwei:

1. **Nachweis** (für Agentur und Jobcenter), 1 bis 3 Seiten. Enthält nur, was der Bewerber getan hat: Liste, Tage, Termine, auf Wunsch Kosten. Keine Punkte, keine Quoten, keine Absagegründe, keine Suche. Grund: Datensparsamkeit gegenüber Dritten, und ein Sachbearbeiter liest eine Seite, keine neun.
2. **Auswertung** (für den Bewerber), etwa 6 Seiten. Seite 1 ist das Cockpit, danach Grafiken mit ihren Zahlen, am Ende die Listen.

Der heutige Tätigkeitsbericht-Modus, der Vorlagenblock und der Beraterkommentar gehen im Nachweis auf (Einstellungen bleiben, wirken nur dort).

### 3. Leitlinien

1. **Ein Zeitraum, überall.** Jede Zahl trägt ihren Bezug: „im Zeitraum“ oder „am Stichtag“. Was sich nicht auf den Zeitraum rechnen lässt, entfällt im Zeitraum-Bericht.
2. **Eine Zahl, eine Funktion.** PDF, Excel, Statistik-Seite, `statistiken_abrufen` und die Werkzeugantwort lesen aus demselben Datenkern.
3. **Kleine Fallzahlen:** unter 10 Fällen Anzahlen („4 von 4“) statt Prozent; Median erst ab 3 Fällen, immer mit Anzahl und Spanne.
4. **Unbekannt ist ein Zustand:** „noch keine Angabe“ statt 0.0.
5. **Fragen als Überschriften** („Welcher Weg führt zu Gesprächen?“) statt Abschnittsnummern.
6. **Balken statt Kreise,** direkt beschriftet, in Graustufen lesbar (Helligkeit trägt, nicht der Farbton), keine doppelten Achsen.
7. **Bezeichnungen statt Schlüssel,** echte Umlaute, „du“, Datum `TT.MM.JJJJ`, Beträge `63,30 €`. Eine zentrale Zuordnung Schlüssel zu Bezeichnung, die PDF, Excel und Oberfläche gemeinsam nutzen.
8. **Kein Wort wird abgeschnitten.** Tabellen brechen um.
9. **Sätze nur, wenn die Zahlen sie tragen** („4 der 5 Absagen kamen nach einem Gespräch“), sonst bleibt der Platz leer. Regeln dafür fest im Code, kein freier Text.
10. **Jede Seite trägt Name, Zeitraum und Seitenzahl.**

### 4. Aufbau

**Nachweis, Seite 1:** Kopf (Name, Zeitraum, Erstelldatum, Block mit Kundennummer, Aktenzeichen, Beratung, Stelle). Vier Kennzahlen: Bewerbungen, Gespräche, Rückmeldungen (alle im Zeitraum), laufende Verfahren (am Stichtag). Leiste „Aktivität je Kalenderwoche“. Tabelle „Bewerbungen im Zeitraum“: Nr., Datum, Arbeitgeber und Stelle, Weg (Quelle und Art), Stand am Stichtag mit Datum. Tabelle „Laufende Verfahren aus früheren Zeiträumen“.
**Nachweis, Seite 2:** „Was an welchem Tag geschah“ (Tag, Art, Was). „Bewerbungskosten im Zeitraum“ mit Einzelposten und Summe (abschaltbar). Notizzeilen, Ort und Datum, Unterschrift. Schlusssatz: nur selbst erfasste Angaben, keine Bewertungen, keine geschätzten Zeiten.

**Auswertung, Seite 1 (Variante A, Zahlen zuerst):** sechs Kacheln (Bewerbungen, laufen noch, mit Gespräch, Angebote, Tage bis zur Antwort, Nachfassen fällig). Trichter als Balken (beworben, Antwort erhalten, Gespräch, Zweitgespräch, Angebot). Säulen je Monat. Wege mit „davon Gespräch“. Wie die abgeschlossenen Verfahren endeten. Dauer. Tabelle „Was jetzt ansteht“.
**Auswertung, Folgeseiten:** 2 Wege und Quellen, 3 Absagen und Ausstiegsstufe (#1283), 4 Dauer und Reaktionszeiten (#781), 5 Meine Suche (Stellen, Aussortierungen, getrennt von den Bewerbungen, #1284), 6 Bewerbungsliste und Chronik.

**Statistik-Seite:** ein Zeitraum-Schalter oben, darunter der Satz „Alles auf dieser Seite gilt für …“. Drei Knöpfe: Nachweis (PDF), Auswertung (PDF), Rohdaten (Excel). Abschnitte in dieser Reihenfolge: Wie steht es? Was steht an? Was funktioniert? Meine Suche. Die Seite ist die Auswertung am Bildschirm, mit denselben Zahlen.

**Excel:** Rohdaten. Blätter Bewerbungen, Ereignisse, Termine, Kosten, Kennzahlen (mit Zeitraum und Bezug je Zeile). Echte Datumszellen, Filter, feste Kopfzeile, keine abgeschnittenen Spalten.

### 5. Umsetzung in Stufen

1. **Fehler** (#1337, #1420): Zeitraum, Umschrift, abgeschnittene Wörter, Kosten, zwei Quoten. Aufbau bleibt.
2. **Datenkern** `bericht_daten(profil, von, bis)`: jede Kennzahl als Wert mit Anzahl, Bezug und Zustand „unbekannt“. Zentrale Bezeichnungen und Formate.
3. **Nachweis** als neues Dokument, danach **Auswertung**, danach **Statistik-Seite** auf dem Datenkern.
4. **Musterprofil:** Ereignisse mit glaubwürdigen Daten über den Zeitraum verteilt, Mustertexte ohne „fiktive Musterstelle“ in der Schlüsselwort-Quelle.

### 6. Abnahme (zusätzlich zu den Kriterien im Issue #798)

1. Ein Test liest den Text aus dem erzeugten PDF und aus der Excel-Datei: kein Unterstrich-Schlüssel, keine Umschrift, kein abgeschnittenes Wort aus der Liste der Statusbezeichnungen, ein Datumsformat.
2. Musterbestand mit Teilmenge (4 von 25): jede Zahl in Nachweis, Auswertung, Excel, Statistik-Seite und `statistiken_abrufen` stimmt überein.
3. Der Nachweis enthält die Wörter „Punkte“, „Score“ und „Quote“ nicht.
4. Graustufen-Probe: Bericht in Grau gerendert, jede Grafik bleibt lesbar (Sichtprüfung am Bild).
5. Fall mit 1, 3 und 12 Bewerbungen: Regel für kleine Fallzahlen greift.

### 7. Probe am echten Bestand (21.11.2026, über 100 Bewerbungen, Zeitraum über zwei Jahre)

Der Entwurf wurde mit den Summen eines echten Bestands durchgespielt. Er trägt, wenn diese sechs Regeln gebaut werden. Sie gehören zu Stufe 2 und 3 und sind Teil der Abnahme.

1. **Zeitachse:** bis 12 Monate Säulen je Monat, darüber je Quartal, über 5 Jahre je Jahr. Leere Abschnitte bleiben als Lücke sichtbar. Unter jeder Säule steht die Zahl der Gespräche.
2. **Lange Listen:** Wege, Gründe und "Was jetzt ansteht" zeigen höchstens 5 bis 7 Zeilen, danach "und N weitere". Wege werden zu Gruppen zusammengefasst (Portale, Personalvermittler, direkt), die einzelne Quelle steht auf der Folgeseite.
3. **Stufen ohne belastbare Zahl entfallen** und werden genannt. Im echten Bestand betrifft das "Antwort erhalten" (die heutige Reaktionsquote zählt abgelaufene Verfahren mit, siehe #1337) und "Zweitgespräch" (nicht eigens erfasst, siehe #1283).
4. **Datenlücken sind eine eigene Zeile,** kein Rest: "Weg nicht erfasst" steht als Zeile mit dem Satz, dass es eine Lücke ist und kein Ergebnis.
5. **Zeit vor PBP:** Nachgetragene Bewerbungen zählen bei Anzahlen mit, bei Dauer und Antwortzeit nicht. Die Seite sagt in einem Satz, wie viele das sind. Die Trennung "seit PBP / vor PBP" der heutigen Statistik-Seite bleibt als Schalter erhalten.
6. **Vergleich zum Vorzeitraum** auf einer Kachel (letzte 3 Monate gegen die 3 davor), nur als zwei Zahlen, ohne Pfeil und ohne Wertung.

Dazu der Nachweis: In einem starken Monat (über 20 Bewerbungen) läuft die Tabelle über mehrere Seiten. Kopfzeile der Tabelle auf jeder Seite wiederholen, keine Zeile über den Seitenwechsel teilen.

## Nachmessung vor Stufe 1 (21.11.2026, Claude Code)

Gemessen in einer isolierten Installation (`BA_DATA_DIR`, Musterprofil, Zeitraum 01.11. bis 30.11.2026), nicht am echten Bestand. Die Befunde aus #1337 und #1420 stimmen, mit diesen Korrekturen an den Zahlen und Annahmen oben:

1. **Zahlen des Musterprofils:** Es liefert heute 24 Bewerbungen (Bob) und 22 (Anna), davon 6 im November. Der Seed datiert relativ zu „heute“; die „25 / 4“ von oben gelten nicht mehr. Die Tests der Stufe 1 bauen ihren Bestand mit festen Daten (25 Bewerbungen, 4 im November).
2. **Seitenzahl:** Das heutige PDF hat im Zeitraum-Bericht des Musterprofils 6 Seiten, nicht 9 (9 hängt vom Bestand ab).
3. **Quoten:** Es sind drei, nicht zwei: Angebotsquote im PDF 0,0 % (Zeitraum), im Excel 4,2 % (gesamt); im Werkzeug zählt der obere `offer_rate` nur den Status Angebot, `quoten.gesamt` zusätzlich Arbeitgeber-Ausfall nach Angebot (aus dem Code gelesen, Werkzeug nicht ausgeführt). Ablehnung: der Bericht nannte „roh 54,2 % / bereinigt 50,0 %“ (mit versandeten Vorgängen), das Werkzeug 16,7 %.
4. **„Eigene Bewerbungen als aussortiert“:** im Code bestätigt (die SQL-Zählung nimmt jeden `dismiss_reason`), im Musterprofil nicht sichtbar, weil der Seed diesen Grund nicht setzt. Der Test baut den Fall selbst.
5. **„12b“ im Inhaltsverzeichnis:** stand fest im Code, auch ohne Abschnitt; im Musterprofil ist der Abschnitt da.
6. **Schrift:** Das PDF nutzte die eingebaute Helvetica (Latin-1). Das Euro-Zeichen und Buchstaben wie `ł`/`ş` wurden zu „?“. Stufe 1 nutzt, wenn vorhanden, die DejaVu-Sans-Schnitte, die matplotlib (feste Abhängigkeit) mitbringt, und fällt sonst auf Latin-1 mit „EUR“ zurück. Abweichung von der Vorgabe „nur dokumentieren“: Der Betrag `63,30 €` ist ohne Unicode-Schrift nicht darstellbar.
7. **Prüfer:** `scripts/ui_texte_pruefen.py` kannte den PDF-Erzeuger nicht; Einzelwörter wie „Taetigkeitsbericht“ fielen auch nach Aufnahme der Datei durch. Beides ist behoben, ein Test hält die Registrierung.
