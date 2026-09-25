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
      { titel: "Feinabstimmung", text: "Die Regler für Entfernung, Remote-Anteil und Gehalt ändern die Reihenfolge der Liste. Du brauchst sie nicht, um anzufangen." },
    ],
    prompts: ["jobsuche_workflow"],
  },
  dokumente: {
    abschnitte: [
      { titel: "Dokumente hochladen", text: "Zieh PDF-, DOCX-, TXT- oder Mail-Dateien in das Fenster oder nutze den Upload-Knopf. PBP erkennt den Typ und liest den Text." },
      { titel: "Zuordnen", text: "Ein Dokument gehört meist zu einer Bewerbung. Claude schlägt die Zuordnung vor; du bestätigst sie." },
      { titel: "Gescannte PDFs", text: "Eine PDF ohne Textebene liefert keinen Text. PBP sagt das beim Hochladen; den Text kannst du über Claude nachtragen." },
    ],
    prompts: ["dokumente_verarbeiten", "profil_sync"],
  },
  stellen: {
    abschnitte: [
      { titel: "Stellen finden", text: "Wähle die Quellen in den Einstellungen und starte die Suche mit „Jobsuche mit Claude“ oder mit „Interne Jobsuche starten“. Jede Stelle bekommt Punkte." },
      { titel: "Punkte und Urteil", text: "Die Punkte zeigen, wie gut die Anzeige deine Suchbegriffe trifft. Ob die Stelle zu dir passt, sagt erst die Detailbewertung: sie liest Anzeige und Profil und bleibt an der Stelle stehen." },
      { titel: "Aussortieren", text: "„Passt nicht“ nimmt eine Stelle mit Grund aus der Liste. Das Aussortier-Protokoll zeigt, was weg ist, und holt es zurück. Eine Firma, die du nie sehen willst, kommt auf die Blacklist." },
    ],
    prompts: ["jobsuche_workflow", "auto_bewerbung"],
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
  { q: "Wie aktualisiere ich PBP?", a: "Neue Version herunterladen und den Installer erneut starten. Deine Daten bleiben erhalten; vorher legt PBP eine Sicherung an." },
];

export const PROBLEME = [
  { q: "Claude findet die PBP-Werkzeuge nicht", a: "1. Claude Desktop komplett beenden (auch unten rechts in der Taskleiste) und neu starten.\n2. In Claude unter Einstellungen > Entwickler muss PBP stehen.\n3. Die Verbindungsanzeige oben im Dashboard sagt, wann Claude PBP zuletzt aufgerufen hat." },
  { q: "Das Dashboard startet nicht", a: "1. Läuft PBP schon in einem anderen Fenster? Dann ist der Port belegt.\n2. Die Protokolle stehen unter Einstellungen > Erweitert > Logs." },
  { q: "Die Jobsuche findet nichts", a: "1. Sind Quellen gewählt?\n2. Sind Suchbegriffe gesetzt? Ohne MUSS-Begriffe gibt es nichts zu finden.\n3. Nach dem Lauf sagt PBP, wie viele Treffer an welchem Filter hängen geblieben sind." },
  { q: "Eine Börse blockiert", a: "Manche Börsen erkennen automatische Abrufe. Diese Quellen laufen über den Browser mit Claude: „Jobsuche mit Claude“ nennt sie und erklärt den Weg." },
  { q: "Ein Dokument liefert keinen Text", a: "Gescannte PDFs haben oft keine Textebene. PBP sagt das beim Hochladen; den Text kannst du über Claude nachtragen." },
];
