import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { FAQ, HILFE, MELDE_MAIL, MELDEWEGE, PROBLEME, START_HILFE } from "./hilfe.js";
import { STARTSATZ } from "./startsatz.js";

// 1. Jede Seite aus PAGE_IDS hat Hilfe (G68: Kontakte, Dokumente,
//    Aufgaben und Kalender hatten keine).
const utils = readFileSync(new URL("../utils.js", import.meta.url), "utf8");
const block = utils.slice(utils.indexOf("PAGE_IDS"), utils.indexOf("];"));
const ids = [...block.matchAll(/^\s*"([a-z_]+)"/gm)].map((m) => m[1]);
assert.ok(ids.length >= 10, "PAGE_IDS nicht gelesen");
for (const id of ids) {
  assert.ok(HILFE[id], `keine Hilfe fuer ${id}`);
  assert.ok(HILFE[id].abschnitte.length >= 1, `leere Hilfe fuer ${id}`);
  assert.ok(Array.isArray(HILFE[id].prompts), `keine Prompt-Liste fuer ${id}`);
}
// 2. Beide Meldewege, einer davon ohne GitHub.
assert.deepEqual(MELDEWEGE.map((w) => w.art), ["github", "mail"]);
assert.ok(MELDEWEGE[1].fehler.startsWith(`mailto:${MELDE_MAIL}`));
assert.ok(MELDEWEGE[0].fehler.includes("github.com/MadGapun/PBP/issues/new"));
// 3. Der Startsatz ist derselbe wie auf Willkommen-Seite und Dashboard.
assert.ok(START_HILFE.text.includes(STARTSATZ));
const alles = JSON.stringify([HILFE, FAQ, PROBLEME, START_HILFE]);
// 4. Keine der drei alten Falschaussagen.
assert.ok(!/aktualisieren sich automatisch/i.test(alles));
assert.ok(!/0\s*[–-]\s*100/.test(alles));
assert.ok(!alles.includes("/ersterfassung"));
// 5. Keine Namen aus einem einzelnen Profil (PLM, Hamburg) in der Hilfe.
assert.ok(!/\bPLM\b|Hamburg/.test(alles));
// 6. #1170 U1: die Hilfe kennt 1.8. Jede neue Funktion steht in der Hilfe ihrer Seite.
const text = (id) => JSON.stringify(HILFE[id].abschnitte);
for (const wort of ["Updates", "Speicher & Downloads", "Mail-Ordner", "Erweiterungen"]) {
  assert.ok(HILFE.einstellungen.abschnitte.some((a) => a.titel === wort), `Einstellungen: kein Abschnitt „${wort}“`);
}
assert.ok(HILFE.kontakte.abschnitte.some((a) => a.titel === "Firmen"), "Kontakte: kein Abschnitt „Firmen“");
assert.ok(text("dokumente").includes("Texterkennung"), "Dokumente: die Texterkennung fehlt");
// Die FAQ „Wie aktualisiere ich PBP?“ nennt das Ein-Klick-Update, nicht mehr nur den Installer.
const aktualisieren = FAQ.find((f) => f.q === "Wie aktualisiere ich PBP?");
assert.ok(aktualisieren.a.includes("Einstellungen › Erweitert › Updates"), "FAQ Aktualisieren ohne den neuen Weg");
assert.ok(aktualisieren.a.includes("Installer"), "der Weg von Hand bleibt genannt (macOS, Linux, neue Hauptversion)");
for (const q of ["Was räumt PBP auf, und was löscht es nie?", "Was ist ein Firmen-Eintrag?", "Liest PBP meine Mails?", "Wofür ist die Texterkennung?"]) {
  assert.ok(FAQ.some((f) => f.q === q), `FAQ: „${q}“ fehlt`);
}
for (const q of ["Nach einem Update läuft die alte Version", "PBP bietet kein Update an"]) {
  assert.ok(PROBLEME.some((p) => p.q === q), `Probleme: „${q}“ fehlt`);
}
// Der Neustart wird in der Hilfe so beschrieben wie in der Oberfläche (lib/autoUpdate.js: NEUSTART_SCHRITTE).
assert.ok(PROBLEME.find((p) => p.q === "Nach einem Update läuft die alte Version").a.includes("schwarze Fenster"));
// Kein Weg zeigt auf eine Stelle, die es so nicht mehr gibt: „Quellen im Detail“ liegt unter „Erweitert“.
assert.ok(!/Einstellungen › Quellen im Detail/.test(alles), "veralteter Pfad Einstellungen › Quellen im Detail");
// Keine Wörter ohne Umlaute (Teil von U13), sonst liest sich die Hilfe wie ein Fremdtext.
assert.ok(!/\b(fuer|ueber|koennen|moeglich|Schluessel|einfuegen|Datensaetze)\b/i.test(alles), "ae/oe/ue-Schreibweise in der Hilfe");
console.log("hilfe ok");
