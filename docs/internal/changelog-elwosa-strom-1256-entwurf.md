# Entwurf: CHANGELOG-Eintrag zu #1256 (Elwosa-Strom: die Marke „N neu“ und das Mitscrollen bei geänderter Höhe)

> **Kein Teil des CHANGELOG.** Der Text gehört in den Eintrag der Version, die die Änderung ausliefert: in der 1.8-Linie Eintrag `[1.8.0]`, Abschnitt „Fixed“.
> **Stable ist betroffen:** `ElwosaSidebarChat.jsx` trägt in v1.7.158 dieselbe Rechnung (Zahl der Nachrichten, ein Merker aus einem Scroll-Ereignis). Ob die
> Änderung in die 1.7-Linie zurückgeführt wird (Hotfix), entscheidet der Nutzer; die Rechnung der Marke steht getrennt in `lib/elwosaStrom.js`, die Browser-Tests von
> #1233 gibt es in der 1.7-Linie nicht (eigenes Gerüst nötig). Datum beim Release einsetzen, danach diese Datei löschen.
>
> Belegt: vierzehn Browser-Fälle am gerenderten Bild in `tests/test_v18_hilfe_frage_browser_1233.py` (`test_1256_*`; elf davon auf dem Ausgangsstand rot, drei Gegenstücke
> grün: kurze Liste, „wer oben liest, bleibt oben“, Ausblenden mit einer Meldung dazwischen), Node-Test `frontend/src/lib/elwosaStrom.test.mjs` (eigener CI-Schritt), ein Wächter im Quelltext in `tests/test_v1717_sidebar_907.py`,
> Gegenprobe Katalog `elwosa_strom1256` (`scripts/mutationstest_auto_update.py --katalog elwosa_strom1256`, Einträge ev01 bis ev20). Ein unabhängiger Leser (nur lesend) hat
> den ersten Stand geprüft und fünf Funde gemeldet; drei sind eingearbeitet (siehe unten), zwei sind Folgearbeit.

---

## Eintrag (Titelvorschlag)

**Elwosas „N neu“ kommt, wenn etwas Neues da ist — und der Verlauf bleibt unten, wo du ihn gelassen hast**

<!-- anwender -->
Hast du im Verlauf von Elwosa nach oben gescrollt und sie sagt etwas Neues, zeigt dir jetzt der Knopf „N neu“ unten im Bereich, wie viele neue Nachrichten unter dem Bild liegen. Bisher kam er in aller Regel gar nicht, sobald der Verlauf voll war. Blendest du eine Nachricht aus, meldet er keine „neue“ mehr.
Wer unten liest, bleibt unten: auch wenn sich der Bereich verkleinert (zum Beispiel, weil im Kopf der Seitenleiste „Update-Stand unbekannt“ erscheint, oder weil du das Fenster kleiner ziehst), und eine neue Meldung bleibt nicht mehr unter dem Bild verborgen. Blendest du Elwosa aus und wieder ein, steht der Verlauf wieder unten; wechselst du das Profil, siehst du gleich die Nachrichten des neuen Profils.
<!-- /anwender -->

Die Seitenleiste holt nur die letzten zehn Nachrichten. Ob eine neu war, entschied bisher die Länge der Liste (`lastMessageCountRef`), und ob der Mensch am Ende stand, ein Merker, den nur ein Scroll-Ereignis setzte
(`stickyRef`, #611). Gemessen am gerenderten Bild (21.10.2026, isolierte Testdatenbank, Fenster 1440 × 960):

- **Marke bei voller Liste:** zehn Nachrichten im Verlauf, Mensch ganz oben, eine und dann zwei neue Meldungen: **keine Marke**. Bei kurzer Liste (vier Nachrichten) kam sie.
- **Marke ohne Anlass:** Mensch oben, eine Nachricht ausgeblendet; beim nächsten Holen rückt eine ÄLTERE ins Fenster, die Zahl steigt von neun auf zehn — „1 neu“, obwohl nichts neu ist.
- **Das Ende rutscht aus dem Bild:** der Bereich wird um 38 Pixel niedriger (die Zeile „Update-Stand unbekannt“ im Kopf), Abstand zum Ende 0 → 38 Pixel: die letzte Meldung ist abgeschnitten, bis die nächste kommt.
- **Eine Meldung bleibt verdeckt:** Sprung ans Ende und Höhenänderung im selben Bild; das Scroll-Ereignis zum Sprung läuft erst im nächsten Bild, rechnet mit der neuen Höhe (38 Pixel, über der Toleranz von 30) und setzt „nicht am Ende“.
  Die nächste Meldung lag bei 217 bis 292 Pixeln in einem 170 Pixel hohen Bereich: verdeckt, und ohne Marke.
- **Nach dem Wiedereinblenden** (Auge, „Elwosa wieder einblenden“) stand der Verlauf oben (Abstand zum Ende 804 Pixel), bei den ältesten Nachrichten.

**Wichtig zu wissen:**

- **Neu ist, was eine größere Kennung trägt als die zuletzt gesehene** (`neueNachrichten` in `lib/elwosaStrom.js`; `elwosa_messages.id` steigt mit jeder Nachricht, Ausblenden löscht keine Zeile). Das erste Laden ist nichts Neues; die größte
  gesehene Kennung sinkt nie, auch wenn die neueste Nachricht ausgeblendet wird. Sie wird auch nachgeführt, solange es den Bereich nicht gibt (Elwosa ausgeblendet): was dann kam, steht beim Wiedereinblenden unten im Bild und ist nicht „neu“.
- **Ob der Mensch am Ende steht, misst die Seite beim Eintreffen der Daten**, vor dem Einfügen (`warAmEnde` aus `stehtAmEnde`), und entscheidet nur danach. Der Merker `stickyRef` ist weg: das Scroll-Ereignis zu einem Sprung kann noch ausstehen, und ein Merker aus einem
  Ereignis war veraltet, sobald sich die Höhe ohne Ereignis änderte. Das behebt nebenbei einen zufälligen Fehler im Test `test_1254_eine_neue_nachricht_elwosas_kommt_unter_die_antwort_und_ist_zu_sehen`
  (auf dem Stand von #1255 in 3 von 8 Läufen rot: Sprung ans Ende bei 199 ms, Meldung bei 223 ms, Ereignis zum Sprung bei 227 ms). Ohne Messung (eine Nachricht ausblenden, „gelesen“ melden) wird nicht gescrollt.
- **Der Bereich beobachtet seine Höhe** (`ResizeObserver`, als Ref-Funktion, weil es den Bereich erst gibt, wenn der Status da ist). Bei jeder Änderung wird der Abstand zum Ende zweimal gerechnet: mit der Höhe von VORHER (stand der Mensch am Ende?)
  und mit der von JETZT (reicht der Bereich nach dem Wachsen bis ans Ende?). Wer am Ende stand, bleibt dort; wer oben liest, bleibt stehen. Ein neuer Bereich beginnt unten wie ein Chat.
- **Nach einem Profilwechsel beginnt die Seitenleiste neu** (`key` am Aufruf in `App.jsx`): die Kennungen laufen über alle Profile, die Liste zeigt nur die des aktiven. Die Nachrichten des anderen Profils stehen gleich da (bisher bis zum nächsten Takt
  von 30 Sekunden die des alten) und gelten nicht als neu. Der Verlauf der Fragen zur Bedienung in der Seitenleiste beginnt damit auch neu (er lebt nur im Arbeitsspeicher der Seite).
- **Technisch:** die Rechnung der Marke steht in `frontend/src/lib/elwosaStrom.js` mit eigenem Node-Test und eigenem CI-Schritt; in `ElwosaSidebarChat.jsx` bleiben `distanceFromBottom`, `atBottom`, `showJumpToBottom`, `unreadBelow`
  und `jumpToBottom`. Der Wächter `test_sticky_bottom_detection` (#611) ist nachgezogen: er verlangt jetzt, dass es `stickyRef` NICHT mehr gibt. Die Gegenprobe macht je einen Handgriff wirkungslos (Zählen nach Zahl, Beobachter ohne Wirkung,
  nur die Höhe von jetzt oder nur die von vorher, keine Messung beim Eintreffen, jede Meldung gilt als gefolgt, Kennung nur mit Bereich, kein Neubeginn beim Profilwechsel, Toleranz 0, …); die Tests müssen rot werden.

**Gemessen, aber nicht Gegenstand (Folgearbeit):**

- **Dialog-Zeilen tragen Ortszeit statt UTC** (`services/elwosa_dialog.py`, `_log_dialog`: `datetime.now().isoformat()`; alle anderen Wege schreiben `_now()` mit `+00:00`). Sortiert wird als Text: eine Dialog-Zeile (Werkzeug `elwosa_fragen`) steht in der MESZ bis zu zwei Stunden
  über Meldungen, die nach ihr kamen. Älter als diese Änderung, auch in der 1.7-Linie.
- **Die Marke führt ans Ende, nicht zur ersten neuen Nachricht.** Kommt eine Meldung, die zeitlich VOR der Antwort der Hilfe liegt (Elwosa schrieb, die Seite holte erst nach der Frage), steht sie im Strom ÜBER der Antwort; „N neu“ führt ans Ende der Antwort. Entwurf von #1255 (Strom nach der Zeit).
