// node frontend/src/lib/seitenleiste.test.mjs
// Die Seitenleiste in schmalen Fenstern (#1170 U15).
import assert from "node:assert/strict";
import { eingeklappt, istSchmal, SCHLUESSEL_BREIT, SCHLUESSEL_SCHMAL, SCHMAL_BIS_PX, wahlAusText } from "./seitenleiste.js";

// ── Was „schmal“ heißt ────────────────────────────────────────────────────────────────
assert.equal(SCHMAL_BIS_PX, 900);
assert.equal(istSchmal(680), true, "das Dashboard neben Claude Desktop");
assert.equal(istSchmal(420), true);
assert.equal(istSchmal(899), true);
assert.equal(istSchmal(900), false, "die Grenze selbst ist breit");
assert.equal(istSchmal(1440), false);
// ohne brauchbare Breite gilt das Fenster als breit (nie eine Leiste einklappen, weil etwas nicht messbar war)
for (const unbrauchbar of [0, -1, NaN, undefined, null, "", "abc"]) assert.equal(istSchmal(unbrauchbar), false, String(unbrauchbar));

// ── Die gemerkte Wahl ────────────────────────────────────────────────────────────────
assert.equal(wahlAusText("1"), true);
assert.equal(wahlAusText("0"), false);
for (const x of [null, undefined, "", "true", "2"]) assert.equal(wahlAusText(x), null, String(x));

// ── Eingeklappt oder nicht ───────────────────────────────────────────────────────────
// breit: wie bisher - ausgeklappt, außer der Mensch hat eingeklappt
assert.equal(eingeklappt(false, false, null), false);
assert.equal(eingeklappt(false, true, null), true);
assert.equal(eingeklappt(false, false, false), false, "die Wahl für schmal ändert breit nichts");
assert.equal(eingeklappt(false, false, true), false);
// schmal: eingeklappt, außer der Mensch hat DORT ausgeklappt
assert.equal(eingeklappt(true, false, null), true);
assert.equal(eingeklappt(true, false, undefined), true);
assert.equal(eingeklappt(true, false, false), false, "im schmalen Fenster ausgeklappt gewählt");
assert.equal(eingeklappt(true, false, true), true);
assert.equal(eingeklappt(true, true, null), true, "die Wahl für breit gilt nicht für schmal");
assert.equal(eingeklappt(true, false, false), false);

// ── Zwei Schlüssel, nie derselbe ─────────────────────────────────────────────────────
assert.equal(SCHLUESSEL_BREIT, "pbp-sidebar-collapsed", "der bisherige Schlüssel bleibt: gemerkte Wahlen gelten weiter");
assert.notEqual(SCHLUESSEL_BREIT, SCHLUESSEL_SCHMAL);

console.log("seitenleiste.test.mjs: ok");
