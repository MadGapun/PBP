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
console.log("hilfe ok");
