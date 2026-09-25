import assert from "node:assert/strict";
import { bewerbungenProWoche, topStellen, gehaltsWert, WOCHEN_ANSICHTEN } from "./kennzahlen.js";

const TAG = 86400000;
const jetzt = Date.UTC(2026, 8, 25);

// 1. Ohne Bewerbung ein Strich, keine 0.
assert.equal(bewerbungenProWoche([], "gesamt", jetzt).wert, "—");
// 2. Vorgabe: Durchschnitt seit der ersten Bewerbung — fest, nicht zufaellig.
const ts = [jetzt - 69 * TAG, jetzt - 30 * TAG, jetzt - 2 * TAG];
const a = bewerbungenProWoche(ts, "gesamt", jetzt);
assert.equal(a.wert, "0,3");
assert.equal(a.notiz, "Ø seit der ersten Bewerbung");
assert.deepEqual(bewerbungenProWoche(ts, "gesamt", jetzt), a);
// 3. Die zweite Ansicht rechnet ueber 30 Tage.
assert.equal(bewerbungenProWoche(ts, "30_tage", jetzt).wert, "0,5");
assert.equal(WOCHEN_ANSICHTEN[0].id, "gesamt");
// 4. Top-Stellen: keine mit 0 oder weniger Punkten.
const top = topStellen([{ hash: "a", punkte: -2 }, { hash: "b", punkte: 0 }, { hash: "c", punkte: 3 }, { hash: "d", punkte: 5 }]);
assert.deepEqual(top.map((j) => j.hash), ["d", "c"]);
// 5. 0 EUR ist kein Gehalt.
assert.equal(gehaltsWert(0), null);
assert.equal(gehaltsWert(52000), 52000);
console.log("kennzahlen: alle Faelle gruen");
