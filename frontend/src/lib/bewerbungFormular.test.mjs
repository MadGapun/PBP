// node frontend/src/lib/bewerbungFormular.test.mjs
// G58 (#1087 C6, D7): Beschriftungen, Vorgabe, Datum.
import assert from "node:assert/strict";
import {
  BEWERBUNG_ANLEGEN, BEWERBUNG_FELDER, VORGABE_STATUS,
  bewerbungNutzlast, brauchtBewerbungsdatum, heuteIso,
} from "./bewerbungFormular.js";

// 1. Keine Datenbank-Schluessel als Beschriftung.
for (const feld of BEWERBUNG_FELDER) {
  assert.notEqual(feld.label, feld.key, feld.key);
  assert.ok(!/_/.test(feld.label), feld.label);
}
assert.deepEqual(BEWERBUNG_FELDER.map((f) => f.label), ["Stellentitel", "Firma", "Link zur Anzeige"]);

// 2. Vorgabe ist "Ich will mich bewerben" — nur bei "beworben" laeuft der Auto-Nachfass.
assert.equal(VORGABE_STATUS, "in_vorbereitung");
assert.equal(BEWERBUNG_ANLEGEN, "Bewerbung anlegen");

// 3. Datum nur, wenn die Bewerbung raus ist.
assert.equal(brauchtBewerbungsdatum("in_vorbereitung"), false);
assert.equal(brauchtBewerbungsdatum("beworben"), true);

// 4. Nutzlast: Vorbereitung ohne Datum, beworben ohne Datum -> Server setzt "jetzt".
assert.equal(bewerbungNutzlast({ status: "in_vorbereitung", applied_at: "2026-09-01" }).applied_at, "");
assert.ok(!("applied_at" in bewerbungNutzlast({ status: "beworben", applied_at: "" })));
assert.equal(bewerbungNutzlast({ status: "beworben", applied_at: "2026-09-01" }).applied_at, "2026-09-01");

// 5. Heute in Ortszeit, nicht UTC (#1032).
assert.equal(heuteIso(new Date(2026, 0, 5, 0, 30)), "2026-01-05");

console.log("bewerbungFormular: ok");
