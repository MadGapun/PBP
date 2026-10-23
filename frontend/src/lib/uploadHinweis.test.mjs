// node frontend/src/lib/uploadHinweis.test.mjs
// Was nach dem Hochladen eines Dokuments zu sagen ist (#1170 U12).
import assert from "node:assert/strict";
import { ocrHinweis, ocrHinweise } from "./uploadHinweis.js";

// ── Scan ohne Komponente: der Weg zur Texterkennung steht da ──────────────────────────
const scan = { status: "ok", filename: "zeugnis.pdf", extracted_length: 0, ocr: { ocr: "erforderlich", angebot: { name: "Tesseract" } } };
const h = ocrHinweis(scan, "Zeugnis 2019.pdf");
assert.equal(h.art, "erforderlich");
assert.equal(h.aktion, "texterkennung");
assert.match(h.text, /Zeugnis 2019\.pdf/);
assert.match(h.text, /Einstellungen › Erweiterungen/);
assert.match(h.text, /Scan ohne Text/);

// der Name kommt sonst aus der Antwort, sonst steht „Das Dokument“
assert.match(ocrHinweis(scan).text, /zeugnis\.pdf/);
assert.match(ocrHinweis({ ocr: { ocr: "erforderlich" } }).text, /Das Dokument/);

// ── Fehlgeschlagen: ehrlich, ohne Aktion ──────────────────────────────────────────────
const fehl = ocrHinweis({ ocr: { ocr: "fehlgeschlagen", fehler: "Zeitüberschreitung" } }, "scan.pdf");
assert.equal(fehl.art, "fehlgeschlagen");
assert.equal(fehl.aktion, undefined);
assert.match(fehl.text, /scan\.pdf/);
assert.match(fehl.text, /trotzdem gespeichert/);

// ── Durchgeführt oder nichts: kein Hinweis (Erfolg bleibt leise) ──────────────────────
assert.equal(ocrHinweis({ ocr: { ocr: "durchgefuehrt", seiten: 1 } }, "x.pdf"), null);
for (const x of [null, undefined, {}, { ocr: null }, { ocr: "erforderlich" }, { ocr: {} }]) assert.equal(ocrHinweis(x, "x.pdf"), null, JSON.stringify(x));

// ── Mehrere Dateien: derselbe Weg steht einmal da ─────────────────────────────────────
const alle = ocrHinweise([
  { antwort: scan, name: "a.pdf" },
  { antwort: scan, name: "b.pdf" },
  { antwort: { ocr: { ocr: "durchgefuehrt" } }, name: "c.pdf" },
  { antwort: { ocr: { ocr: "fehlgeschlagen" } }, name: "d.pdf" },
]);
assert.deepEqual(alle.map((x) => x.art), ["erforderlich", "fehlgeschlagen"]);
assert.deepEqual(ocrHinweise(null), []);
assert.deepEqual(ocrHinweise([]), []);

console.log("uploadHinweis.test.mjs: ok");
