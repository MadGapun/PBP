// node frontend/src/lib/sicherung.test.mjs — #1098
import assert from "node:assert/strict";
import { alterText, groesseText } from "./sicherung.js";

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
console.log("sicherung: ok");
