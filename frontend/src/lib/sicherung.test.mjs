// node frontend/src/lib/sicherung.test.mjs — #1098
import assert from "node:assert/strict";
import { alterText, groesseText, versuchText } from "./sicherung.js";

assert.deepEqual(alterText(null), { text: "Noch keine Sicherung vorhanden", alt: true });
assert.equal(alterText(0.01).text, "Letzte Sicherung: gerade eben");
assert.equal(alterText(3 / 24).text, "Letzte Sicherung: vor 3 Stunden");
assert.equal(alterText(1 / 24).text, "Letzte Sicherung: vor 1 Stunde");
assert.equal(alterText(1.2).text, "Letzte Sicherung: vor 1 Tag");
assert.equal(alterText(6.9).alt, false);
assert.equal(alterText(9).alt, true);
assert.equal(alterText(9).text, "Letzte Sicherung: vor 9 Tagen");
assert.equal(groesseText(500), "1 KB");
assert.equal(groesseText(5 * 1024 * 1024), "5,0 MB");
assert.equal(groesseText(2.5 * 1024 * 1024 * 1024), "2,5 GB");
// v1.7.146 (#1142): der Ausgang des juengsten Versuchs. Ein Fehler soll sichtbar sein,
// ein ueberholter oder glatter Versuch nichts melden.
assert.equal(versuchText(null), null);
assert.equal(versuchText({ status: "laeuft", aktuell: true }), null);
assert.equal(versuchText({ status: "fertig", nachricht: "Sicherung angelegt", aktuell: true }), null);
assert.deepEqual(
  versuchText({ status: "fehler", nachricht: "Datei X ist gesperrt", aktuell: true }),
  { art: "fehler", text: "Die letzte Sicherung ist fehlgeschlagen: Datei X ist gesperrt" });
assert.deepEqual(
  versuchText({ status: "fehler", nachricht: "", aktuell: true }),
  { art: "fehler", text: "Die letzte Sicherung ist fehlgeschlagen." });
assert.equal(
  versuchText({ status: "fehler", nachricht: "alt", aktuell: false }), null,
  "ein Fehler, den eine neuere Sicherung ueberholt hat, meldet nichts mehr");
assert.equal(
  versuchText({ status: "fertig", nachricht: "2 Dateien waren gesperrt", aktuell: true }).art, "hinweis");
console.log("sicherung: ok");
