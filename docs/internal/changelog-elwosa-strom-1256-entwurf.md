# Entwurf: CHANGELOG-Eintrag zu #1256 (Elwosa-Strom: die Marke „N neu“ und das Mitscrollen bei geänderter Höhe)

> **Kein Teil des CHANGELOG.** Der Text gehört in den Eintrag der Version, die die Änderung ausliefert: in der 1.8-Linie Eintrag `[1.8.0]`, Abschnitt „Fixed“.
> **Stable ist betroffen:** `ElwosaSidebarChat.jsx` trägt in v1.7.158 dieselbe Rechnung (Zahl der Nachrichten, ein Merker aus einem Scroll-Ereignis). Ob die
> Änderung in die 1.7-Linie zurückgeführt wird (Hotfix), entscheidet der Nutzer; der Teil zur Marke und zum Beobachter der Höhe lässt sich ohne den Strom von #1254
> übernehmen, die Rechnung steht getrennt in `lib/elwosaStrom.js`. Datum beim Release einsetzen, danach diese Datei löschen.
>
> Belegt: elf Browser-Fälle am gerenderten Bild in `tests/test_v18_hilfe_frage_browser_1233.py` (`test_1256_*`; neun davon auf dem Ausgangsstand rot, zwei Gegenstücke
> grün), Node-Test `frontend/src/lib/elwosaStrom.test.mjs` (eigener CI-Schritt), ein Wächter im Quelltext in `tests/test_v1717_sidebar_907.py`, Gegenprobe Katalog
> `elwosa_strom1256` (`scripts/mutationstest_auto_update.py --katalog elwosa_strom1256`, Einträge ev01 bis ev16).

---

## Eintrag (Titelvorschlag)

**Elwosas „N neu“ kommt, wenn etwas Neues da ist — und der Verlauf bleibt unten, wo du ihn gelassen hast**

<!-- anwender -->
Hast du im Verlauf von Elwosa nach oben gescrollt und sie sagt etwas Neues, zeigt dir jetzt der Knopf „N neu“ unten im Bereich, wie viele neue Nachrichten unter dem Bild liegen. Bisher kam er in aller Regel gar nicht, sobald der Verlauf voll war. Blendest du eine Nachricht aus, meldet er keine „neue“ mehr.
Wer unten liest, bleibt unten: auch wenn sich der Bereich verkleinert (zum Beispiel, weil im Kopf der Seitenleiste „Update-Stand unbekannt“ erscheint, oder weil du das Fenster kleiner ziehst), und eine neue Meldung bleibt nicht mehr unter dem Bild verborgen. Blendest du Elwosa aus und wieder ein, steht der Verlauf wieder unten.
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
  gesehene Kennung sinkt nie, auch wenn die neueste Nachricht ausgeblendet wird.
- **Der Bereich beobachtet seine Höhe** (`ResizeObserver`, als Ref-Funktion, weil es den Bereich erst gibt, wenn der Status da ist). Bei jeder Änderung wird der Abstand zum Ende zweimal gerechnet: mit der Höhe von VORHER (stand der Mensch am Ende?)
  und mit der von JETZT (reicht der Bereich nach dem Wachsen bis ans Ende?). Wer am Ende stand, bleibt dort; wer oben liest, bleibt stehen.
- **Ob der Mensch am Ende steht, wird beim Eintreffen der Daten an der Geometrie gemessen**, vor dem Einfügen, nicht allein aus dem Merker: das Scroll-Ereignis zu einem Sprung kann noch ausstehen. Das behebt nebenbei einen zufälligen Fehler im
  Test `test_1254_eine_neue_nachricht_elwosas_kommt_unter_die_antwort_und_ist_zu_sehen` (auf dem Stand von #1255 in 3 von 8 Läufen rot: Sprung ans Ende bei 199 ms, Meldung bei 223 ms, Ereignis zum Sprung bei 227 ms).
- **Ein neuer Bereich beginnt unten** wie ein Chat.
- **Technisch:** die Rechnung der Marke steht in `frontend/src/lib/elwosaStrom.js` mit eigenem Node-Test und eigenem CI-Schritt; `ElwosaSidebarChat.jsx` behält `stickyRef`, `distanceFromBottom`, `atBottom`, `showJumpToBottom`, `unreadBelow`
  und `jumpToBottom` (die Wächter aus #611 und #907 gelten unverändert). Die Gegenprobe macht je einen Handgriff wirkungslos (Zählen nach Zahl, Beobachter ohne Wirkung, nur die Höhe von jetzt oder nur die von vorher, keine Messung beim Eintreffen,
  Toleranz 0, …); die Tests müssen rot werden.
