// node frontend/src/lib/erklaertexte.test.mjs
// Lange Erklärtexte lassen sich einklappen (#1170 U11).
import assert from "node:assert/strict";
import {
  aufgeklappt, ALLE_SCHLUESSEL, alleZeigenAusText, EINZEL_PRAEFIX, einzelnAusText, leseAlle, leseEinzeln, schreibeAlle,
  schreibeEinzeln,
} from "./erklaertexte.js";

// ── Der Schalter: Vorgabe an ─────────────────────────────────────────────────────────
assert.equal(alleZeigenAusText(null), true, "nichts gemerkt = aufgeklappt, wie bisher");
assert.equal(alleZeigenAusText(undefined), true);
assert.equal(alleZeigenAusText("1"), true);
assert.equal(alleZeigenAusText("0"), false);
assert.equal(alleZeigenAusText("aus"), true, "nur ein ausdrückliches 0 klappt ein");

// ── Die Wahl je Erklärtext ───────────────────────────────────────────────────────────
assert.equal(einzelnAusText("auf"), true);
assert.equal(einzelnAusText("zu"), false);
for (const x of [null, undefined, "", "1", "0"]) assert.equal(einzelnAusText(x), null, String(x));

// ── Was zählt ────────────────────────────────────────────────────────────────────────
assert.equal(aufgeklappt(true, null), true, "keine Wahl: der Schalter entscheidet");
assert.equal(aufgeklappt(false, null), false);
assert.equal(aufgeklappt(true, false), false, "die Wahl für den Erklärtext geht vor");
assert.equal(aufgeklappt(false, true), true);
assert.equal(aufgeklappt(false, undefined), false);

// ── Mit Browserspeicher (nachgestellt) ───────────────────────────────────────────────
function speicherNachstellen() {
  const daten = new Map();
  const ereignisse = [];
  globalThis.window = {
    localStorage: {
      getItem: (k) => (daten.has(k) ? daten.get(k) : null),
      setItem: (k, v) => { daten.set(k, String(v)); },
      removeItem: (k) => { daten.delete(k); },
      key: (i) => [...daten.keys()][i] ?? null,
      get length() { return daten.size; },
    },
    dispatchEvent: (e) => { ereignisse.push(e.type); return true; },
  };
  globalThis.CustomEvent = class { constructor(type) { this.type = type; } };
  return { daten, ereignisse };
}

{
  const { daten, ereignisse } = speicherNachstellen();
  assert.equal(leseAlle(), true);
  assert.equal(leseEinzeln("fahrstrecke"), null);
  schreibeEinzeln("fahrstrecke", false);
  assert.equal(daten.get(EINZEL_PRAEFIX + "fahrstrecke"), "zu");
  assert.equal(leseEinzeln("fahrstrecke"), false);
  schreibeEinzeln("updates-sicherheit", true);
  assert.equal(leseEinzeln("updates-sicherheit"), true);
  assert.deepEqual(ereignisse, ["pbp-erklaertexte-geaendert", "pbp-erklaertexte-geaendert"], "jede Wahl wird gemeldet");

  // „für alle“ gilt für alle: die Einzelwahlen fallen weg
  schreibeAlle(false);
  assert.equal(daten.get(ALLE_SCHLUESSEL), "0");
  assert.equal(leseAlle(), false);
  assert.equal(leseEinzeln("fahrstrecke"), null);
  assert.equal(leseEinzeln("updates-sicherheit"), null);
  assert.equal([...daten.keys()].filter((k) => k.startsWith(EINZEL_PRAEFIX)).length, 0);
  schreibeAlle(true);
  assert.equal(leseAlle(), true);
}

// ── Ohne Browserspeicher bleibt es bei der Vorgabe ───────────────────────────────────
{
  globalThis.window = {
    get localStorage() { throw new Error("gesperrt"); },
    dispatchEvent: () => true,
  };
  assert.equal(leseAlle(), true);
  assert.equal(leseEinzeln("x"), null);
  assert.doesNotThrow(() => schreibeEinzeln("x", false));
  assert.doesNotThrow(() => schreibeAlle(false));
}

console.log("erklaertexte.test.mjs: ok");
