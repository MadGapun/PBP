// Hilfe-Dialog: ein Ort fuer die Texte (G68, #1087 D9).
//
// Die Hilfe stand als JSX-Block in App.jsx, je Tab eine Handvoll Karten,
// und sie war an drei Stellen falsch: "Die Metriken aktualisieren sich
// automatisch" (es gibt den Aktualisieren-Knopf, die Zahlen stehen beim
// Oeffnen fest), "Score (0-100)" (der Score ist eine Punktsumme, #999)
// und "/ersterfassung" als Startsatz, waehrend Willkommen-Seite und
// Dashboard "Starte die Ersterfassung" sagen. Fuer Kontakte, Dokumente,
// Aufgaben und Kalender gab es gar keine Hilfe.
//
// Jetzt: eine Tabelle je Tab (jede Seite aus PAGE_IDS muss hier stehen,
// der Node-Test prueft das), die Prompts je Tab als KENNUNGEN des
// Prompt-Katalogs — Titel und Beschreibung kommen aus /api/prompts, also
// aus derselben Quelle wie der Schnellzugriff. Der Python-Test haelt jede
// Kennung gegen prompt_katalog.EINTRAEGE.

import { STARTSATZ } from "./startsatz.js";

export const MELDE_MAIL = "PBP-Service@Elwosa.de";
export const GITHUB_NEU = "https://github.com/MadGapun/PBP/issues/new";

// Zwei Wege, gleichrangig: nicht jeder hat ein GitHub-Konto. Der Text
// entsteht in beiden Faellen ueber den Prompt "problem_melden" — Claude
// sucht zuerst eine Sofortloesung und entfernt Namen aus dem Bericht.
export const MELDEWEGE = [
  {
    art: "github",
    titel: "Mit GitHub-Konto",
    text: "Lege ein Issue an. Andere sehen dann, dass der Fehler bekannt ist.",
    fehler: `${GITHUB_NEU}?labels=bug&title=%5BBug%5D+`,
    wunsch: `${GITHUB_NEU}?labels=enhancement&title=%5BIdee%5D+`,
  },
  {
    art: "mail",
    titel: "Ohne GitHub-Konto",
    text: `Schick denselben Text per Mail an ${MELDE_MAIL}. Ein Konto brauchst du dafür nicht.`,
    fehler: `mailto:${MELDE_MAIL}?subject=${encodeURIComponent("PBP: Fehler")}`,
    wunsch: `mailto:${MELDE_MAIL}?subject=${encodeURIComponent("PBP: Idee")}`,
  },
];

export const MELDE_PROMPT = "problem_melden";

export const START_HILFE = {
  titel: "Wie fange ich an?",
  text: `Öffne Claude Desktop und schreib „${STARTSATZ}“ — auf den genauen Wortlaut kommt es nicht an. Claude baut mit dir dein Profil auf und fragt nach, was fehlt.`,
};

// Je Tab: Abschnitte und die Prompts, die dort weiterhelfen.
export const HILFE = {
  dashboard: {
    abschnitte: [
      { titel: "Übersicht", text: "Das Dashboard zeigt, was gerade ansteht: offene Nachfassungen, Termine, die besten neuen Stellen und deinen Stand. Die Zahlen gelten ab dem Öffnen; Änderungen, die Claude im Hintergrund macht, holst du mit dem Aktualisieren-Knopf oben rechts." },
      { titel: "Bereiche anpassen", text: "Über das Zahnrad-Symbol neben dem Dashboard schaltest du Bereiche ein oder aus und änderst ihre Reihenfolge. Die Auswahl gilt für dein Profil." },
      { titel: "Top-Stellen", text: "Die Stellen mit den meisten Punkten, nach denselben Regeln wie im Stellen-Tab. Stellen ohne Punkte stehen hier nicht." },
    ],
    prompts: ["willkommen", "bewerbungs_uebersicht"],
  },
  profil: {
    abschnitte: [
      { titel: "Dein Profil", text: "Das Profil ist die Grundlage für Lebenslauf, Anschreiben und die Einordnung einer Stelle. Je vollständiger es ist, desto genauer passt das Ergebnis." },
      { titel: "Stationen und Projekte", text: "Beschreib Projekte nach dem Muster Situation, Aufgabe, Vorgehen, Ergebnis. Daraus entstehen gute Absätze für den Lebenslauf." },
      { titel: "Lebenslauf einlesen", text: "Ein Lebenslauf als PDF oder DOCX im Dokumente-Tab genügt. Claude liest ihn und schlägt Stationen, Ausbildung und Skills vor." },
    ],
    prompts: ["ersterfassung", "profil_erweiterung", "profil_ueberpruefen"],
  },
  suche: {
    abschnitte: [
      { titel: "Suchbegriffe", text: "MUSS-Begriffe muss eine Stelle treffen, PLUS-Begriffe bringen zusätzliche Punkte, MINUS-Begriffe ziehen welche ab, und AUSSCHLUSS-Begriffe blenden eine Stelle ganz aus." },
      { titel: "Punkte", text: "Die Punkte sagen, wie gut eine Anzeige deine Suchbegriffe trifft. Sie sind keine Prozentzahl und kein Urteil darüber, ob die Stelle zu dir passt — das entsteht erst, wenn jemand Anzeige und Profil gelesen hat." },
      { titel: "Entfernung", text: "Trag je Anstellungsform eine Grenze in Kilometern ein. Ein leeres Feld nimmt die grau angezeigte Vorgabe, 0 heißt „nur am Wohnort oder remote“. Innerhalb der Grenze gilt: je näher, desto besser. Gerechnet wird mit der Luftlinie — so, wie die Jobbörsen sie angeben." },
      { titel: "Fahrstrecke und Fahrzeit", text: "Mit einem kostenlosen Routing-Schlüssel (Einstellungen › Erweitert › Quellen im Detail) und dem Haken „Echte Fahrstrecke und Fahrzeit verwenden“ rechnet PBP mit der Fahrstrecke. Sie gilt fürs Auto, nicht für Bus und Bahn — wer so pendelt, lässt den Haken aus." },
      { titel: "Feinabstimmung", text: "Die Regler für Entfernung, Remote-Anteil und Gehalt ändern die Reihenfolge der Liste. Du brauchst sie nicht, um anzufangen." },
    ],
    prompts: ["jobsuche_workflow"],
  },
  dokumente: {
    abschnitte: [
      { titel: "Dokumente hochladen", text: "Zieh PDF-, DOCX-, TXT- oder Mail-Dateien in das Fenster oder nutze den Upload-Knopf. PBP erkennt den Typ und liest den Text." },
      { titel: "Zuordnen", text: "Ein Dokument gehört meist zu einer Bewerbung. Claude schlägt die Zuordnung vor; du bestätigst sie." },
      { titel: "Gescannte PDFs", text: "Eine PDF ohne Textebene liefert keinen Text. Mit der Texterkennung (Einstellungen › Erweitert › Erweiterungen, einmalig etwa 55 MB, nur mit deinem Ja) liest PBP sie beim Hochladen selbst. Ohne sie sagt PBP das beim Hochladen; den Text kannst du über Claude nachtragen." },
    ],
    prompts: ["dokumente_verarbeiten", "profil_sync"],
  },
  stellen: {
    abschnitte: [
      { titel: "Stellen finden", text: "Wähle die Quellen in den Einstellungen und starte die Suche mit „Jobsuche mit Claude“ oder mit „Interne Jobsuche starten“. Jede Stelle bekommt Punkte." },
      { titel: "Punkte und Urteil", text: "Die Punkte zeigen, wie gut die Anzeige deine Suchbegriffe trifft. Ob die Stelle zu dir passt, sagt erst die Detailbewertung: sie liest Anzeige und Profil und bleibt an der Stelle stehen." },
      { titel: "Aussortieren", text: "„Passt nicht“ nimmt eine Stelle mit Grund aus der Liste. Das Aussortier-Protokoll zeigt, was weg ist, und holt es zurück. Eine Firma, die du nie sehen willst, kommt auf die Blacklist." },
      { titel: "Die ganze Liste prüfen", text: "„Liste abgleichen mit Claude“ über der Liste kopiert eine Anleitung: Claude liest jede Stelle gegen dein Profil, sortiert aus, was deine Grenzen verletzt, und schreibt zu jeder Stelle ein Urteil mit Begründung. An deinen Suchkriterien ändert Claude dabei nichts." },
    ],
    prompts: ["jobsuche_workflow", "stellen_abgleich", "auto_bewerbung"],
  },
  bewerbungen: {
    abschnitte: [
      { titel: "Bewerbungen verfolgen", text: "Jede Bewerbung hat einen Status, eine Timeline und Notizen. Ein Statuswechsel lässt sich im Hinweis unten sofort zurücknehmen." },
      { titel: "Nachfassen", text: "Plane eine Erinnerung, wann du nachfragst. Sie erscheint auf dem Dashboard und im Aufgaben-Tab." },
      { titel: "Unterlagen", text: "Lebenslauf und Anschreiben zu einer Stelle entstehen mit Claude und landen im Ausgabe-Ordner." },
    ],
    prompts: ["bewerbung_schreiben", "bewerbung_vorbereitung", "ablehnungs_coaching"],
  },
  kontakte: {
    abschnitte: [
      { titel: "Kontakte", text: "Menschen, mit denen du gesprochen hast: Recruiter, Ansprechpartner, Referenzen. Ein Kontakt entsteht, sobald ein Austausch stattfindet." },
      { titel: "Referenzen", text: "Markiere einen Kontakt als Referenz und gib eine Referenzliste aus. Mail und Telefon stehen nur darin, wenn du es ausdrücklich wählst." },
      { titel: "Firmen", text: "Im Reiter Firmen steht alles, was PBP zu einer Firma weiß, als eine Zeitleiste: Bewerbungen, Stellen, Kontakte, Dokumente, Recherche. Ein Firmen-Eintrag fasst Schreibweisen zusammen („Muster AG“ heißt heute „Beispiel GmbH“). PBP macht nur Vorschläge; angelegt wird nichts ohne dein Ja, und deine Bewerbungen behalten ihren Firmennamen." },
    ],
    prompts: ["netzwerk_strategie"],
  },
  aufgaben: {
    abschnitte: [
      { titel: "Alles, was ansteht", text: "Aufgaben, Nachfassungen und Termine in einer Liste. Abhaken, verschieben oder als hinfällig markieren." },
      { titel: "Hinfällig oder erledigt", text: "„Erledigt“ heißt, du hast es getan. „Hinfällig“ heißt, es hat sich erledigt, ohne dass du etwas tun musstest. Die Statistik unterscheidet beides." },
    ],
    prompts: ["bewerbungs_uebersicht"],
  },
  kalender: {
    abschnitte: [
      { titel: "Termine", text: "Interviews und andere Termine zu deinen Bewerbungen. Einen Termin legst du hier an oder Claude übernimmt ihn aus einer Mail." },
      { titel: "In den eigenen Kalender", text: "„ICS“ lädt alle Termine als Datei herunter, die jedes Kalenderprogramm öffnet." },
    ],
    prompts: ["interview_vorbereitung", "interview_simulation", "gehaltsverhandlung"],
  },
  statistiken: {
    abschnitte: [
      { titel: "Statistiken", text: "Verlauf, Antwortquoten, Zeit bis zur Antwort und Gründe für Absagen. Zahlen, deren Grundlage unvollständig ist, stehen mit Hinweis da." },
      { titel: "Bericht", text: "Der Bewerbungsbericht fasst alles als PDF zusammen, etwa für ein Gespräch mit der Arbeitsagentur." },
    ],
    prompts: ["profil_analyse", "ablehnungs_coaching"],
  },
  einstellungen: {
    abschnitte: [
      { titel: "Grundlagen", text: "Quellen, Erscheinungsbild, Datenschutz und Ordner — damit kommst du aus. Alles Weitere steht unter „Erweitert“." },
      { titel: "Quellen", text: "PBP empfiehlt Quellen passend zu deinem Profil. Manche Börsen gehen nur über den Browser mit Claude; die Karte sagt, welche." },
      { titel: "Updates", text: "Unter Erweitert › Updates wählst du, wie neue Versionen auf den Rechner kommen: nur Hinweis (die Vorgabe), mit einem Klick oder automatisch. Ohne deine Wahl installiert PBP nichts. Geladen wird nur von der offiziellen GitHub-Seite des Projekts, jede Datei wird auf Prüfsumme und Signatur geprüft, und startet die neue Version nicht, springt PBP von selbst auf die vorige zurück. Die neue Version gilt nach einem Neustart von PBP und Claude Desktop. Das Ein-Klick-Update gibt es zurzeit nur unter Windows." },
      { titel: "Speicher & Downloads", text: "Zeigt, wohin PBP schreibt und lädt und wie viel dort liegt. Aufräumen zeigt erst eine Vorschau und fragt dann; gelöscht wird nie ohne dein Ja. Was anderen Programmen gehört (der Browser der Jobsuche, KI-Modelle), zeigt PBP nur und löscht es nie." },
      { titel: "Mail-Ordner", text: "Unter Erweitert › Quellen im Detail. Der Ordner-Scan ist standardmäßig aus. PBP öffnet nie selbst ein Postfach; es nimmt nur Mails an, die ein gekoppeltes Add-on schickt, und prüft sie vorher gegen deine Liste freigegebener Ordner." },
      { titel: "Erweiterungen", text: "Zusatzprogramme wie die Texterkennung für gescannte PDFs. Nichts wird ohne dein Ja heruntergeladen; Größe und Lizenz stehen immer dabei." },
      { titel: "Datensicherung", text: "PBP sichert einmal am Tag von selbst, vor dem Leeren eines Bereichs und vor dem Zusammenführen zweier Stellen — samt deiner Dokumente. Unter Datenschutz › Daten & Sicherung legst du selbst eine an oder holst einen früheren Stand zurück; er wird beim nächsten Start eingespielt." },
    ],
    prompts: ["tipps_und_tricks"],
  },
};

// Kurze Antworten; die ausfuehrliche Fassung steht im Wiki.
export const FAQ = [
  { q: "Wo liegen meine Daten?", a: "Auf deinem Gerät: unter Windows in %LOCALAPPDATA%\\BewerbungsAssistent, unter macOS und Linux in ~/.bewerbungs-assistent. Gespeichert wird lokal auf deinem Rechner; was du mit Claude bearbeitest, geht an Anthropic. Was genau wohin geht, steht unter Einstellungen > Datenschutz." },
  { q: "Muss Claude Desktop laufen?", a: "Für alles, was Claude tut, ja. Profil, Stellen und Bewerbungen kannst du im Dashboard auch ohne Claude ansehen und bearbeiten." },
  { q: "Wie fange ich an?", a: START_HILFE.text },
  { q: "Kann ich mehrere Profile haben?", a: "Ja. Oben auf den Profilnamen klicken und „Neues Profil“ wählen." },
  { q: "Wie funktioniert die Jobsuche?", a: "Quellen in den Einstellungen wählen, dann „Jobsuche mit Claude“ kopieren und in Claude einfügen. Claude fragt die Börsen ab und übernimmt die Treffer." },
  { q: "Welche Dateiformate gehen?", a: "PDF, DOCX, DOC, TXT, Markdown, RTF und Mails (EML, MSG)." },
  { q: "Kostet PBP etwas?", a: "Nein. PBP ist kostenlos und quelloffen (MIT-Lizenz). Für Claude brauchst du ein Konto bei Anthropic." },
  { q: "Wie hole ich einen früheren Stand zurück?", a: "Einstellungen › Datenschutz › Daten & Sicherung: die Liste der Sicherungen öffnen und „Diesen Stand wiederherstellen“ wählen. Dein jetziger Stand wird vorher selbst gesichert. Danach PBP und Claude Desktop ganz beenden und neu starten — beim Start wird der Stand eingespielt." },
  { q: "Was lernt PBP über mich?", a: "Einstellungen › Lokale KI › „Was PBP über dich lernt“ zeigt, welche Daten einfließen (aussortierte Stellen, Bewerbungen und ihr Verlauf, mit lokaler KI auch die Nutzung der letzten 30 Tage) und welche nicht (Dokumente, Mails, Profil, Kontakte). Jeder Lernlauf steht dort mit Ergebnis — und wenn nichts herauskam, mit dem Grund. „Lerndaten exportieren“ lädt alles zum Nachlesen herunter. Ausschalten kannst du das Lernen unter Datenschutz." },
  { q: "Wie aktualisiere ich PBP?", a: "Einstellungen › Erweitert › Updates: PBP sagt Bescheid, wenn es eine neue Version gibt, und installiert sie auf Wunsch mit einem Klick (zurzeit nur unter Windows). Danach PBP und Claude Desktop neu starten. Sonst, unter macOS und Linux oder beim Wechsel auf eine neue Hauptversion: neue Version herunterladen und den Installer erneut starten. Deine Daten bleiben erhalten; vorher legt PBP eine Sicherung an." },
  { q: "Was räumt PBP auf, und was löscht es nie?", a: "Einstellungen › Erweitert › Speicher & Downloads zeigt, wohin PBP schreibt und wie viel dort liegt. Aufräumen zeigt erst eine Vorschau und fragt dann. Was anderen Programmen gehört (der Browser der Jobsuche, KI-Modelle), zeigt PBP nur und löscht es nie." },
  { q: "Was ist ein Firmen-Eintrag?", a: "Unter Kontakte › Firmen führt PBP alles zu einer Firma in einer Zeitleiste zusammen. Verschiedene Schreibweisen derselben Firma lassen sich zu einem Eintrag fassen. PBP schlägt das nur vor und legt nichts ohne dein Ja an." },
  { q: "Liest PBP meine Mails?", a: "Nein, nicht von selbst: PBP öffnet nie ein Postfach. Mails kommen nur an, wenn du sie im Mail-Programm an PBP schickst. Der Ordner-Scan unter Erweitert › Quellen im Detail › Mail-Ordner ist standardmäßig aus und gilt nur für Ordner, die du ausdrücklich freigibst." },
  { q: "Wofür ist die Texterkennung?", a: "Gescannte PDFs, zum Beispiel alte Zeugnisse, haben keinen Text, den PBP lesen kann. Die Texterkennung liest sie. Sie ist ein Zusatzprogramm (etwa 55 MB) unter Einstellungen › Erweitert › Erweiterungen und wird nur mit deinem Ja heruntergeladen." },
];

export const PROBLEME = [
  { q: "Claude findet die PBP-Werkzeuge nicht", a: "1. Claude Desktop komplett beenden (auch unten rechts in der Taskleiste) und neu starten.\n2. In Claude unter Einstellungen > Entwickler muss PBP stehen.\n3. Die Verbindungsanzeige oben im Dashboard sagt, wann Claude PBP zuletzt aufgerufen hat." },
  { q: "Das Dashboard startet nicht", a: "1. Läuft PBP schon in einem anderen Fenster? Dann ist der Port belegt.\n2. Die Protokolle stehen unter Einstellungen > Erweitert > Logs." },
  { q: "Die Jobsuche findet nichts", a: "1. Sind Quellen gewählt?\n2. Sind Suchbegriffe gesetzt? Ohne MUSS-Begriffe gibt es nichts zu finden.\n3. Nach dem Lauf sagt PBP, wie viele Treffer an welchem Filter hängen geblieben sind." },
  { q: "Eine Börse blockiert", a: "Manche Börsen erkennen automatische Abrufe. Diese Quellen laufen über den Browser mit Claude: „Jobsuche mit Claude“ nennt sie und erklärt den Weg." },
  { q: "Die Fahrzeit ist viel zu kurz", a: "Fahrstrecke und Fahrzeit gelten fürs Auto. Wer mit Bus und Bahn pendelt, nimmt unter Suche & Bewertung › Max. Entfernung pro Stellentyp den Haken „Echte Fahrstrecke und Fahrzeit verwenden“ ab; dann rechnet PBP mit der Luftlinie." },
  { q: "Stellen ohne Anzeigentext", a: "Manche Börsen liefern in der Trefferliste keinen Text. PBP lädt ihn nach der Suche im Hintergrund nach, die Zahl steht im Hinweis zur Jobsuche; der Rest folgt mit der Automatik." },
  { q: "Ein Dokument liefert keinen Text", a: "Gescannte PDFs haben oft keine Textebene. PBP sagt das beim Hochladen. Mit der Texterkennung (Einstellungen › Erweitert › Erweiterungen) liest PBP sie selbst; sonst kannst du den Text über Claude nachtragen." },
  { q: "Nach einem Update läuft die alte Version", a: "1. Schließe das schwarze Fenster „PBP Bewerbungs-Portal“, beende Claude Desktop ganz (Rechtsklick auf das Symbol unten rechts in der Taskleiste → „Beenden“) und starte beides neu.\n2. Steht danach noch die alte Version in der Seitenleiste, hat sich die neue nicht starten lassen: PBP ist von selbst auf die vorige zurückgesprungen und sagt es auf dem Dashboard. Du verlierst nichts.\n3. Einstellungen › Erweitert › Updates › Verlauf zeigt, was geschehen ist." },
  { q: "PBP bietet kein Update an", a: "PBP bietet nur fertige Versionen der eigenen Linie an, zum Beispiel 1.8.x für 1.8. Eine neuere Vorabversion (Beta) nennt PBP in der Seitenleiste und unter Einstellungen › Erweitert › Updates, installiert sie aber nie von selbst, auch nicht mit der Stufe „Mit einem Klick“: Dort holst du das ZIP und startest den Installer (INSTALLIEREN.bat unter Windows, INSTALLIEREN.command auf dem Mac). Eine neue Hauptversion wird in der Seitenleiste genannt; die installierst du einmal von Hand (ZIP laden, Installer starten). Mit „Jetzt prüfen“ unter Einstellungen › Erweitert › Updates fragst du sofort nach." },
];
