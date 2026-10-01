// node frontend/src/lib/webAdresse.test.mjs — v1.7.145
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { oeffneAdresse, istWebAdresse, sichereAdresse } from "./webAdresse.js";

// Dieselbe Fallliste wie der Server-Test (tests/test_v17145_web_adresse.py).
const faelle = JSON.parse(
  readFileSync(new URL("../../../tests/fixtures/web_adresse_faelle.json", import.meta.url), "utf-8"));
assert.ok(faelle.length >= 20, "Fallliste zu kurz");
for (const [url, erlaubt] of faelle) {
  assert.equal(istWebAdresse(url), erlaubt, `istWebAdresse(${JSON.stringify(url)})`);
}

// sichereAdresse: bereinigte Adresse oder undefined (nie ein leerer Text)
assert.equal(sichereAdresse("  https://example.com/x "), "https://example.com/x");
assert.equal(sichereAdresse("javascript:alert(1)"), undefined);
assert.equal(sichereAdresse(null), undefined);

// oeffneAdresse: öffnet nur http(s)
const geoeffnet = [];
globalThis.window = { open: (...args) => { geoeffnet.push(args); return "fenster"; } };
assert.equal(oeffneAdresse("javascript:alert(1)"), null);
assert.equal(oeffneAdresse("file:///C:/x"), null);
assert.deepEqual(geoeffnet, []);
assert.equal(oeffneAdresse("https://example.com/a"), "fenster");
assert.deepEqual(geoeffnet, [["https://example.com/a", "_blank", "noopener,noreferrer"]]);
oeffneAdresse("https://example.com/b", "_self", "noopener");
assert.deepEqual(geoeffnet[1], ["https://example.com/b", "_self", "noopener"]);

console.log("webAdresse: ok");
