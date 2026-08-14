# LinkedIn-Beitrag zu PBP v1.7.16 — Entwürfe

> Arbeitsdatei, nicht Teil des Produkts. Ton nach `docs/assets/texte.md`:
> kein Marketing-Sprech, keine Superlative, keine Ausrufezeichen.
>
> **Vor dem Posten prüfen:** v1.7.16 muss als GitHub-Release veröffentlicht
> sein (Stand beim Verfassen: `--latest` = v1.7.15). Testzahl und
> Portal-Anzahl gegen den Release-Stand gegenprüfen.

---

## Entwurf A — Hauptversion (~2.400 Zeichen)

Wer sich bewirbt, verbringt die meiste Zeit nicht mit Bewerben.

Sondern mit Nachhalten. Wo habe ich mich beworben, wann war das, wer war der
Ansprechpartner, welche Fassung des Lebenslaufs ist rausgegangen — und war
diese Stelle nicht schon mal da?

Dafür gibt es PBP: ein Bewerbungs-Helfer, der komplett auf dem eigenen
Rechner läuft. Eine Datei, kein Konto, keine Cloud. Er durchsucht Jobportale,
hält Bewerbungen, Termine und Dokumente an einem Ort zusammen und redet dabei
über Claude Desktop mit dir, statt dich durch Formulare zu schicken.

Seit dem Sommer hat sich einiges getan. Das Wichtigste daraus:

Ein Einstieg ohne Sackgasse. Lebenslauf hochladen, das Profil entsteht daraus,
Suchbegriffe kommen als Vorschlag, die erste Suche läuft. Und wenn nichts
gefunden wird, sagt PBP warum — statt nur „0 Treffer".

Ehrliche Bewertungen. Eine fachfremde Stelle kam auf 30 von 36 Punkten, weil
sämtliche Treffer im Werbeabsatz der Firma standen. Solche Treffer zählen
jetzt kaum noch. Und eine Stelle ohne Beschreibungstext heißt „unbewertet"
statt „Score 0" — ein fehlender Text ist kein Urteil.

Gedächtnis statt Behauptung. Ein Firmenname genügt, und der dokumentierte
Stand liegt vor: Bewerbungen, Termine, Absagen mit Grund. Dasselbe für
Recruiter und Vermittler. Wird dieselbe Stelle Wochen später neu
ausgeschrieben, erkennt PBP das — auch unter neuer Adresse.

Zahlen, die stimmen. Die Absagequote wird um Fälle bereinigt, die nichts mit
dir zu tun hatten: eine gestrichene Stelle oder eine insolvente Firma ist
keine Ablehnung. Dazu Reaktionszeiten, Zeit bis zum Gespräch und die
Bewerbungsquote je Portal — nicht die Trefferzahl.

Ein Aufgaben-Bereich. Offene Punkte, Nachfassungen und Termine in einer Sicht,
nach Fälligkeit sortiert. Auch für alles, was zu keiner Bewerbung gehört.

Interview-Nachbereitung, die trägt. Mehrere Gesprächsrunden je Bewerbung, ein
Archiv der eigenen Antworten, wiederkehrende Muster über alle Gespräche hinweg.

Kostenlos und Open Source. Voraussetzung ist Claude Desktop.

Was PBP ist und für wen — ausführlich, mit drei Beispiel-Situationen:
https://www.linkedin.com/pulse/pbp-wenn-jobsuche-einen-roten-faden-bekommt-markus-birzite-fk3ne/

Herunterladen und installieren: https://github.com/MadGapun/PBP

#Bewerbung #Jobsuche #Arbeitsmarkt #OpenSource #KI

---

## Entwurf B — kompakt (~1.200 Zeichen)

Bewerben ist zum größeren Teil Verwaltungsarbeit. Wer sich beworben hat, weiß
das: nachhalten, wiederfinden, nachfassen.

PBP ist ein Bewerbungs-Helfer dagegen — kostenlos, Open Source und komplett
auf dem eigenen Rechner. Keine Cloud, kein Konto, deine Bewerbungsdaten
bleiben bei dir.

Version 1.7.16 ist draußen. Seit dem Sommer-Release neu:

– Geführter Einstieg: Lebenslauf hochladen, Profil entsteht, erste Suche läuft
– Ehrlichere Bewertung von Stellenanzeigen — Werbetext der Firma zählt kaum noch
– Firmen- und Recruiter-Historie auf Zuruf, statt aus dem Gedächtnis
– Erkennt Stellen, die neu ausgeschrieben wurden, auch unter neuer Adresse
– Statistik, die zwischen „abgelehnt" und „Stelle gestrichen" unterscheidet
– Aufgaben, Nachfassungen und Termine in einer Sicht
– Interview-Nachbereitung über mehrere Runden

Voraussetzung ist Claude Desktop, der Rest ist ein Download und ein Doppelklick.

Ausführlich, mit drei Beispiel-Situationen:
https://www.linkedin.com/pulse/pbp-wenn-jobsuche-einen-roten-faden-bekommt-markus-birzite-fk3ne/

Herunterladen: https://github.com/MadGapun/PBP

#Bewerbung #Jobsuche #OpenSource

---

## Erster Kommentar (optional, direkt nach dem Posten)

Zwei Dinge, die ich lieber dazusage, als sie im Beitrag zu verstecken:

PBP ist deutschsprachig und auf den DACH-Arbeitsmarkt zugeschnitten. Und es
braucht Claude Desktop als Gesprächspartner — ohne läuft das Dashboard zwar,
aber der geführte Teil fehlt.

Wer es ausprobiert: Rückmeldungen gehen am besten direkt als Issue auf GitHub.
Fast alles, was seit Juni dazugekommen ist, stammt aus echten
Bewerbungs-Nachmittagen und nicht aus einer Roadmap.

---

## Beurteilung: lohnt der Link auf den Artikel vom 27.04.2026?

Ja — aber mit klarer Rollenverteilung, sonst konkurrieren die beiden Ziele.

**Was der Artikel leistet und das Repo nicht:** die drei Situationen
(Festanstellung / Teilzeit und Wiedereinstieg / Freelance) und vor allem der
Abschnitt über das, was nicht im Zeugnis steht — Ehrenamt, Pflege eines
Angehörigen, Auszeiten, Umwege. Das ist der Teil, der Jobsuchende persönlich
abholt, und er steht so weder im README noch im Wiki. Genau deshalb bleibt er
verlinkenswert.

**Was gegen ihn spricht:** er ist knapp vier Monate alt und kennt keine der
Neuerungen. Wer über eine Update-News in einem Artikel landet, der kein Wort
zum Update sagt, fühlt sich fehlgeleitet. Deshalb muss die Link-Zeile
ehrlich beschriften: „Was PBP ist und für wen", nicht „mehr dazu".

**Reihenfolge:** Artikel zuerst, GitHub danach. Der Artikel ist
LinkedIn-intern (keine Reichweitenstrafe) und die weichere Landebahn — für
jemanden, der gerade Bewerbungen schreibt und kein Entwickler ist, ist ein
GitHub-Repo als erster Kontakt eine Hürde.

**Gegenargument, das trägt, falls nur ein Link gewünscht ist:** genau dieses
Problem hat v1.7.16 gelöst. Das neue README zeigt Produkt vor Installation,
mit Hero-Bild und Bildergalerie. Was im April nur der Artikel leisten konnte,
leistet die Repo-Startseite inzwischen selbst. Wer sich für einen Link
entscheiden muss, nimmt GitHub — das ist das Ziel, an dem Installationen
entstehen.

**Faktenprüfung Artikel gegen heutigen Stand:** keine Aussage ist durch
v1.7.x überholt. „Die Werkzeuge reden miteinander" ist weiterhin der Anker
aus `docs/assets/texte.md`. Einziger Schönheitsfehler: die Autorenzeile sagt
„20+ Jahre", die GitHub-Bio „25+ Jahre".

---

## Hinweise zur Verwendung

- **Bild mitgeben.** `docs/social-preview.png` oder ein Screenshot der
  Bewerbungs-Übersicht. Beiträge ohne Bild verlieren spürbar Reichweite.
- **Erste drei Zeilen entscheiden.** Alles danach steht hinter „mehr anzeigen".
- **Externe Links im Text kosten Reichweite** (bewusste Entscheidung des
  Autors). Alternative bei schwachem Anlauf: Links nachträglich in den ersten
  Kommentar verschieben und im Beitrag durch „Link im ersten Kommentar"
  ersetzen.
- **Zeitpunkt:** Dienstag bis Donnerstag, vormittags.
