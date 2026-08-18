# LinkedIn-Beitrag zu PBP — Entwurf für Jobsuchende

> Arbeitsdatei, nicht Teil des Produkts. Ton nach `docs/assets/texte.md`:
> kein Marketing-Sprech, keine Superlative, keine Ausrufezeichen.
>
> Stand: v1.7.16 ist am 14.08.2026 veröffentlicht (`--latest`).
> Inhaltlich abgedeckt: alles zwischen v1.7.0 (18.06.) und v1.7.16.
>
> **Zielgruppe:** Menschen auf Jobsuche aus Medien, HR, Engineering,
> Verwaltung, Handwerk. Keine Entwickler. Keine KI-Affinität vorausgesetzt.
> Alles, was nach Software-Innerei klingt, ist bewusst draußen.

---

## Der Filter: was von 1.7.0–1.7.16 überhaupt in den Beitrag darf

**Drin (weil es einen Alltagsschmerz löst):**

| Neuerung | Warum es jemanden auf Jobsuche interessiert |
|---|---|
| Firmen- und Vermittler-Historie auf Zuruf | „Wer war das nochmal und was war da los?" — der häufigste Moment am Telefon |
| Erkennung neu ausgeschriebener Stellen | „Habe ich mich da nicht schon beworben?" |
| Aufgaben, Nachfassungen und Termine in einer Sicht | Der Überblick, den sonst drei Excel-Listen nicht liefern |
| Nachfassungen mit Inhalt statt leerem Termin | Erinnert nicht nur woran, sondern auch worum es ging |
| Gesprächs-Nachbereitung über mehrere Runden | Vor dem Zweitgespräch nachlesen, was man im ersten gesagt hat |
| Ehrlichere Stellenbewertung | Firmen-Selbstlob zählt kaum noch; ohne Anzeigentext gibt es kein Urteil |
| Bereinigte Auswertung | Eine gestrichene Stelle ist keine Absage an dich |
| Geführter Einstieg ab Lebenslauf-Upload | „Ich muss nichts können" — die entscheidende Hürde |
| Neue Projektseite mit Bildern (v1.7.16) | Anschauen vor Installieren |

**Draußen (Entwicklerthemen, für die Zielgruppe bedeutungslos):**
Datenbank-Verbindungen je Thread, WAL-Checkpoints, Schema-Parität,
Endpunkt-Wechsel bei der Bundesagentur, MCP-Tool-Anzahl, Testzahlen,
Scoring-Kalibrierung, IDF-Gewichtung, Blacklist-Pflege, Adzuna-Keys,
robots.txt-Konformität, sämtliche Issue-Nummern.

---

## Entwurf C — Hauptversion (~2.000 Zeichen)

Nicht jede Absage war eine Absage an dich.

Stellen werden gestrichen, Einstellungsstopps kommen, Budgets kippen, Firmen gehen insolvent. In deiner eigenen Bilanz sieht das am Ende trotzdem aus wie ein Nein zu dir.

Das ist einer der Gründe, warum ich angefangen habe, mir ein eigenes Werkzeug für die Jobsuche zu bauen. Es heißt PBP, es kostet nichts, es läuft auf deinem Rechner, und deine Bewerbungsdaten gehen nirgendwohin.

Was es dir abnimmt:

Es merkt sich, was du längst vergessen hast. Ein Firmenname genügt, und du siehst, was war: wann du dich beworben hast, mit wem du gesprochen hast, was daraus wurde. Ruft jemand an, dessen Namen du zum dritten Mal hörst, weißt du sofort, worum es beim letzten Mal ging. Und wenn dieselbe Stelle Wochen später wieder ausgeschrieben wird, sagt PBP dir das.

Es hält fest, was ansteht. Nachfassen, Termine, offene Punkte, alles an einer Stelle und nach Fälligkeit sortiert. Mit dem Hinweis, worum es bei der Nachfrage eigentlich ging.

Es begleitet Gespräche über mehrere Runden. Vor dem Zweitgespräch kannst du nachlesen, was du im ersten gesagt hast.

Es ist ehrlich zu dir. Ob du auf eine Stelle passt, sagt es dir auch dann, wenn die Antwort nein lautet. Umgekehrt lässt es sich nicht davon beeindrucken, wie schön eine Firma über sich selbst schreibt. Und die Auswertung rechnet heraus, was nie an dir lag.

Und es sieht mehr in dir als deinen Lebenslauf. Was du im Verein organisiert hast, die Zeit, in der du jemanden gepflegt hast, der Umweg, der eigentlich keiner war. Das kannst du PBP alles erzählen, und es rechnet damit. Manchmal kommen dabei Stellen heraus, an die du von selbst nicht gedacht hättest.

Und es zeigt dir, welcher Weg dich tatsächlich zu Gesprächen bringt und welcher nicht. Nach ein paar Wochen ist das kein Gefühl mehr, sondern ablesbar.

Was du dafür können musst: nichts. Du lädst deinen Lebenslauf hoch, das Profil entsteht daraus, die ersten Suchbegriffe kommen als Vorschlag. Unter Windows sind es ein Download und ein Doppelklick, den Rest macht das Setup in ein paar Minuten. PBP nutzt Claude Desktop als Gesprächspartner, den es kostenlos gibt. Und wer mit KI nichts zu tun haben möchte, nutzt PBP einfach als Verwaltung für Bewerbungen.

Anschauen geht vor Installieren: auf der Projektseite siehst du zuerst Bilder von allem, was drin ist.

Das meiste davon gab es im Frühjahr noch nicht. Es ist dazugekommen, weil Leute mir geschrieben haben, was ihnen fehlt. Was alles neu ist, steht im ersten Kommentar.

Wenn du gerade suchst, probier es aus. Wenn du jemanden kennst, der sucht, gib es weiter.

Jede Bewerbung, die mit Struktur statt mit Stress rausgeht, ist ein guter Tag für jemanden.

https://github.com/MadGapun/PBP

#Bewerbung #Jobsuche #Wiedereinstieg

---

## Warum dieser Einstieg

Der gewählte Einstieg gibt etwas her, bevor er etwas will: eine Entlastung.
Er stellt sich auf die Seite der Lesenden, statt ihnen ihren Schmerz
vorzulesen, den sie ohnehin kennen. Und er passt nicht ins übersättigte
Muster „meine Jobsuche hat mich gelehrt", das im Feed eines
#OpenToWork-Profils reflexhaft weggescrollt wird.

Sichtbares Fenster (rund 200 Zeichen): die erste Zeile trägt die komplette
Aussage allein — auch wenn die zweite abgeschnitten wird, ist die Botschaft
angekommen. Genau das soll sie.

Verworfen: **„Nach der zwölften Bewerbung habe ich den Überblick verloren."**
Zwölf ist für viele Suchende eine kleine Zahl; wer bei achtzig steht, liest
Anfänger und fühlt sich nicht gemeint.

---

## Alternative Einstiege (die ersten Zeilen austauschbar)

**1 — Szene am Telefon.** Konkreter, weniger Anspruch, funktioniert fast
genauso gut und handelt nicht von dir:

> „Guten Tag, hier ist Frau Berger, wir hatten ja telefoniert."
>
> Hatten wir. Nur wann, worüber und für welche Stelle, keine Ahnung.

**2 — Der Stapel.** Für Leute, die nicht digital denken:

> Irgendwann bestand meine Jobsuche aus vier Excel-Listen, einem Ordner mit
> zwölf Lebenslauf-Versionen und einem Kalender voller Termine, bei denen
> nicht dabeistand, worum es geht.

**3 — Die unbezahlte Arbeit.** Am ehesten diskussionsauslösend:

> Bewerben ist ein Vollzeitjob. Nur besteht er zur Hälfte aus Buchhaltung.

---

## Erster Kommentar (direkt nach dem Posten, trägt die eigentliche Neuigkeit)

Für alle, die PBP schon kennen: das ist seit dem Frühjahr dazugekommen.

Ein Aufgabenbereich, der Nachfassungen, Termine und offene Punkte an einer
Stelle zusammenführt, auch für alles, was zu keiner Bewerbung gehört.

Firmen- und Vermittlerhistorie auf Zuruf: ein Name genügt, und der ganze
Vorgang liegt vor dir.

Erkennung von Stellen, die Wochen später erneut ausgeschrieben werden.

Gesprächs-Nachbereitung über mehrere Runden, mit einem Archiv der eigenen
Antworten.

Eine fairere Bewertung von Anzeigen: Selbstlob im Firmenprofil zählt kaum
noch, und ohne Anzeigentext gibt es gar kein Urteil mehr.

Eine Auswertung, die zwischen einer Absage und einer gestrichenen Stelle
unterscheidet, dazu Reaktionszeiten und die Frage, welcher Weg dich
tatsächlich zu Gesprächen bringt.

Und eine neue Projektseite: man sieht jetzt zuerst Bilder von allem, was drin
ist, bevor man irgendetwas installiert.

Alles im Einzelnen steht auf GitHub unter Releases.

Und falls du wissen willst, wofür das Ganze überhaupt gut ist: hier habe ich
es ausführlich beschrieben, mit drei Beispiel-Situationen.
https://www.linkedin.com/pulse/pbp-wenn-jobsuche-einen-roten-faden-bekommt-markus-birzite-fk3ne/

Zwei Dinge sage ich lieber noch dazu: PBP ist deutschsprachig und auf
Deutschland, Österreich und die Schweiz zugeschnitten. Und es ist kein
Produkt einer Firma, sondern etwas, das ich für meine eigene Jobsuche gebaut
habe und weiter baue. Wenn dir etwas fehlt, schreib es mir, hier oder auf
GitHub.

---

## Beurteilung: lohnt der Link auf den Artikel vom 27.04.2026?

Ja — aber mit klarer Rollenverteilung, sonst konkurrieren die beiden Ziele.

**Was der Artikel leistet und das Repo nicht:** die drei Situationen
(Festanstellung / Teilzeit und Wiedereinstieg / Freelance) und vor allem der
Abschnitt über das, was nicht im Zeugnis steht — Ehrenamt, Pflege eines
Angehörigen, Auszeiten, Umwege. Das ist der Teil, der Jobsuchende persönlich
abholt, und er steht so weder im README noch im Wiki.

**Was gegen ihn spricht:** er ist knapp vier Monate alt und kennt keine der
Neuerungen. Wer über eine Update-News in einem Artikel landet, der kein Wort
zum Update sagt, fühlt sich fehlgeleitet. Deshalb muss die Link-Zeile ehrlich
beschriften: „Ausführlich, mit drei Beispiel-Situationen", nicht „mehr dazu".

**Reihenfolge:** Artikel zuerst, GitHub danach. Der Artikel ist
LinkedIn-intern (keine Reichweitenstrafe) und die weichere Landebahn.

**Faktenprüfung Artikel gegen heutigen Stand:** keine Aussage ist durch
v1.7.x überholt. Einziger Schönheitsfehler: die Autorenzeile sagt
„20+ Jahre", die GitHub-Bio „25+ Jahre".

---

## Hinweise zur Verwendung

- **Bild mitgeben.** `docs/social-preview.png` oder der Screenshot der
  Bewerbungs-Übersicht. Beiträge ohne Bild verlieren spürbar Reichweite.
- **Die ersten zwei bis drei Zeilen entscheiden.** Alles danach steht hinter
  „mehr anzeigen". Der Einstieg muss aus der Sicht der Lesenden funktionieren,
  nicht aus der Sicht der Software.
- **Externe Links im Text kosten Reichweite.** Falls der Anlauf schwach ist:
  Links in den ersten Kommentar verschieben und im Beitrag durch „Links im
  ersten Kommentar" ersetzen.
- **Keine Gedankenstriche im Beitragstext.** Der Gedankenstrich als
  Einschub-Zeichen ist inzwischen das auffälligste Erkennungsmerkmal für
  maschinell verfasste Texte. Doppelpunkt, Komma oder ein zweiter Satz tun
  dasselbe, ohne den Verdacht auszulösen. Gilt für den Beitrag und den ersten
  Kommentar; die Notizen darunter sind interne Arbeitstexte.
- **Vorschaubild prüfen, bevor der Beitrag rausgeht.** LinkedIn hält
  Link-Vorschauen rund sieben Tage im Zwischenspeicher. Nach einem Wechsel
  des Social-Preview-Bilds auf GitHub erst die Repo-URL durch den
  [Post Inspector](https://www.linkedin.com/post-inspector/) schicken, sonst
  erscheint das alte Bild im Beitrag.
- **Zeitpunkt:** Dienstag bis Donnerstag, vormittags.
- **Hashtags bringen keine Reichweite mehr.** Seit LinkedIn 2024 das Folgen
  von Hashtags abgeschafft hat, sind sie weitgehend neutral — sie helfen nur
  noch bei der Suche und als Themensignal. Drei bis fünf, am Ende, zum Text
  passend. Bewusst ohne #OpenSource und #KI: die holen die Entwickler-Bubble,
  also das falsche Publikum für diesen Beitrag. Die eigentliche Arbeit machen
  ohnehin die Wörter im Text selbst.
- **Kein Wort über Versionen, Tests oder Technik.** Wer das wissen will,
  findet es auf GitHub.
