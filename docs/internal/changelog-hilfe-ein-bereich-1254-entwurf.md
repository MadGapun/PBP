# Entwurf: CHANGELOG-Eintrag zu #1254 (Seitenleiste: Elwosas Nachrichten und die Antworten der Hilfe in EINEM Bereich zum Scrollen)

> **Kein Teil des CHANGELOG.** Der Text gehört in den Eintrag der Version, die die Änderung ausliefert. Die Hilfe zum Fragen (#1233) gibt es nur in der
> 1.8-Linie (seit rc.4), also Eintrag `[1.8.0]`, Abschnitt „Fixed“; Stable ist nicht betroffen. Datum beim Release einsetzen, danach diese Datei löschen.
>
> Belegt: neun Browser-Fälle am gerenderten Bild in `tests/test_v18_hilfe_frage_browser_1233.py` (sieben davon auf dem Ausgangsstand rot), Node-Tests der beiden neuen
> Funktionen in `frontend/src/lib/hilfeFrage.test.mjs`, ein Wächter im Quelltext in `tests/test_v1717_sidebar_907.py`, Gegenprobe Katalog `hilfe1233`
> (`scripts/mutationstest_auto_update.py --katalog hilfe1233`, Einträge hi27 bis hi30, hi33 bis hi35 und hi37 bis hi51). Ein unabhängiger Leser (nur lesend) hat die
> erste Fassung geprüft und einen echten Mangel gefunden (siehe unten); seine Funde sind bis auf die genannten eingearbeitet.
> **Nicht Gegenstand, aber gemessen:** Unterhalb von etwa 800 Pixeln Fensterhöhe lässt das Menü der Seitenleiste dem Elwosa-Bereich kaum Platz (bei 720 Pixeln ist der
> Verlauf 0 bis 1 Pixel hoch, bei 760 etwa 30 bis 40, bei 800 etwa 80 bis 105; die Zeile „Update-Stand unbekannt“ im Kopf, die nach einer
> Sekunde erscheint, kostet 38 Pixel). Das war im alten Aufbau ähnlich (720: 0, 760: 33, 800: 105) und gehört nicht zu dieser Änderung.

---

## Eintrag (Titelvorschlag)

**In der Seitenleiste scrollst du in EINEM Bereich: Elwosas Nachrichten und die Antworten der Hilfe, nach der Zeit geordnet**

<!-- anwender -->
Fragst du in der Seitenleiste etwas zur Bedienung, stehen Frage und Antwort jetzt im selben Bereich wie Elwosas Nachrichten, nach der Zeit geordnet wie in einem Chat: das Neueste steht unten. Das Feld zum Fragen bleibt darunter stehen.
Vorher bekamen die Antworten einen eigenen Bereich zum Scrollen und drückten Elwosas Verlauf auf wenige Zeilen zusammen.
<!-- /anwender -->

Die Hilfe in der Seitenleiste (#1233, nur bei laufender lokaler KI) zeigte ihre Antworten in einem zweiten Scroller (`max-h-[38vh]`) unter dem Elwosa-Verlauf. Er wuchs
bis auf 38 % der Fensterhöhe und nahm sie dem Verlauf weg. Gemessen am gerenderten Bild (Fenster 1440 Pixel breit, zehn Nachrichten, lokale KI aktiv, Höhe des Verlaufs
vor der Frage → nach der ersten → nach der zweiten): bei 960 Pixeln Fensterhöhe 233 → 0 → 0, bei 1080 Pixeln 353 → 61 → 0. Jetzt: 241 → 241 → 241 und 361 → 361 → 361. Das Zielbild aus #907 („genau EIN Scroll-Container“) war damit aufgehoben, und kein Test hatte es bemerkt, weil keiner die Höhe am gerenderten Bild maß.

**Wichtig zu wissen:**

- **Ein Bereich zum Scrollen, nach der Zeit geordnet.** Nachrichten Elwosas und Antworten der Hilfe stehen hintereinander, das Neueste unten wie in einem Chat. Vor jeder
  Reihe von Antworten steht die Zeile „Fragen zur Bedienung“ (die Hilfe ist nicht Elwosa). Das Feld liegt fest darunter und scrollt nicht weg.
- **Was nach einer Antwort kommt, steht darunter.** Eine erste Fassung stellte die Antworten als Abschnitt hinter ALLE Nachrichten; ein unabhängiger Leser fand, dass dann jede
  neue Meldung Elwosas OBERHALB der Antworten landet und niemand sie sieht, der unten liest. Darum ordnet `stromMit` beide nach der Zeit; Elwosas Nachrichten behalten dabei
  ihre Reihenfolge.
- **Nach einer Frage springt der Bereich an den Anfang der neuen Antwort**, nicht ans Ende: die Frage und der erste Treffer sind zu sehen, der Rest liegt darunter.
  Das gilt auch für eine Antwort, die höher ist als der Bereich.
- **Eine lange Frage ohne Leerzeichen** (zum Beispiel eine eingefügte Adresse) bricht um und macht keine waagerechte Leiste.
- **Vorleseprogramme** bekommen eine neue Antwort über einen unsichtbaren Rahmen gemeldet (Frage, Kopfzeile, Titel des ersten Treffers); die Gedankenstriche der Zeile
  „Fragen zur Bedienung“ werden nicht mitgelesen.
- **Der Hilfe-Dialog ist unverändert** (Reiter „Frag mich“: das Feld oben, die neueste Antwort zuerst, Beispielfragen vor der ersten Frage), ebenso die Wege weiter
  (Öffnen, Wiki, Prompt kopieren) und der Satz „Deine Frage wird nicht gespeichert“. Der Verlauf der Fragen bleibt wie bisher nur im Arbeitsspeicher der Seite
  (höchstens fünf, nichts davon wird gespeichert).
- **Technisch:** `HilfeFrage.jsx` teilt sich in den Zustand (`useHilfeFrage`), das Feld (`HilfeEingabe`), eine Frage mit Antwort (`HilfeAntwort`) und den Verlauf des Dialogs
  (`HilfeVerlauf`); die Seitenleiste hält den Zustand und stellt die Antworten in ihren einen Bereich (`stromMit` und `ansageText` in `lib/hilfeFrage.js`). Ein Wächter hält
  fest, dass `HilfeFrage.jsx` keinen `overflow-y` und kein `max-h-` mehr enthält.
