// node frontend/src/lib/hinweisZone.test.mjs
// G60 (#1087 B1, B5, A5): höchstens ein Banner, nur auf dem Dashboard,
// feste Reihenfolge.
import assert from "node:assert/strict";
import { hinweisFuer, SUCHE_DRINGEND_NACH_TAGEN, tageSeit } from "./hinweisZone.js";

const jetzt = new Date("2026-09-25T12:00:00Z");
const vorTagen = (n) => new Date(jetzt.getTime() - n * 86400000).toISOString();
const alles = {
  seite: "dashboard", verbunden: false, hatProfil: true, quellenAktiv: 0,
  letzteSucheAm: null, updateBekannt: { version: "1.7.200", url: "https://example.com" },
  ollamaAngebot: true, einstiegFertig: true,
};

// 1. Nur auf dem Dashboard.
for (const seite of ["aufgaben", "stellen", "bewerbungen", "kalender", "einstellungen"]) {
  assert.equal(hinweisFuer({ ...alles, seite }, jetzt), null, seite);
}

// 2. Reihenfolge: jede Stufe verdrängt die nächste.
assert.equal(hinweisFuer(alles, jetzt).id, "verbindung");
assert.equal(hinweisFuer({ ...alles, verbunden: true }, jetzt).id, "quellen");
assert.equal(hinweisFuer({ ...alles, verbunden: true, quellenAktiv: 3 }, jetzt).id, "suche");
assert.equal(hinweisFuer({ ...alles, verbunden: true, quellenAktiv: 3, letzteSucheAm: vorTagen(1) }, jetzt).id, "update");
assert.equal(hinweisFuer({ ...alles, verbunden: true, quellenAktiv: 3, letzteSucheAm: vorTagen(1), updateBekannt: null }, jetzt).id, "ollama");
assert.equal(hinweisFuer({ ...alles, verbunden: true, quellenAktiv: 3, letzteSucheAm: vorTagen(1), updateBekannt: null, ollamaAngebot: false }, jetzt), null);

// 3. Ohne Profil kein Banner — der Einstieg erklärt es selbst.
assert.equal(hinweisFuer({ ...alles, hatProfil: false }, jetzt), null);
// Unbekannte Verbindung ist kein Alarm.
assert.equal(hinweisFuer({ ...alles, verbunden: null }, jetzt).id, "quellen");

// 4. Suche: gestern ist kein Anlass, erst nach sieben Tagen.
const basis = { ...alles, verbunden: true, quellenAktiv: 3, updateBekannt: null, ollamaAngebot: false };
assert.equal(hinweisFuer({ ...basis, letzteSucheAm: vorTagen(SUCHE_DRINGEND_NACH_TAGEN - 1) }, jetzt), null);
assert.equal(hinweisFuer({ ...basis, letzteSucheAm: vorTagen(SUCHE_DRINGEND_NACH_TAGEN) }, jetzt).id, "suche");

// 5. Ollama erst nach dem Einstieg.
assert.equal(hinweisFuer({ ...basis, letzteSucheAm: vorTagen(1), ollamaAngebot: true, einstiegFertig: false }, jetzt), null);

// 6. Hilfsfunktion.
assert.equal(tageSeit(vorTagen(3), jetzt), 3);
assert.equal(tageSeit("kaputt", jetzt), null);

console.log("hinweisZone: ok");
