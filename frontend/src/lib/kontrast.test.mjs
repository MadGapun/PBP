import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { FLAECHEN, MINDEST_KONTRAST, TEXT_TOKENS, kontrast } from "./kontrast.js";
import { DEFAULT_PALETTE, THEME_PRESETS } from "../theme.js";

// 1. Die Rechnung selbst: Schwarz auf Weiss ist 21:1.
assert.equal(Math.round(kontrast("0 0 0", "255 255 255")), 21);
// 2. Jede Voreinstellung, beide Modi: Lesetext auf jeder Flaeche >= 4,5:1.
const zuSchwach = [];
for (const preset of THEME_PRESETS) {
  for (const [modus, p] of Object.entries(preset.palette)) {
    for (const t of TEXT_TOKENS) {
      for (const f of FLAECHEN) {
        const k = kontrast(p[t], p[f]);
        if (k < MINDEST_KONTRAST) zuSchwach.push(`${preset.id}/${modus}: ${t} auf ${f} = ${k.toFixed(2)}`);
      }
    }
  }
}
assert.deepEqual(zuSchwach, []);
// 3. styles.css traegt dieselben Werte wie die Standardpalette.
const css = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
const hell = css.slice(css.indexOf('[data-theme="light"]'));
for (const t of TEXT_TOKENS) {
  assert.ok(css.includes(`--color-${t}: ${DEFAULT_PALETTE.dark[t]};`), `dunkel ${t}`);
  assert.ok(hell.includes(`--color-${t}: ${DEFAULT_PALETTE.light[t]};`), `hell ${t}`);
}
console.log("kontrast ok");
