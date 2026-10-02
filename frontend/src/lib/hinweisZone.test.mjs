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

// 7. Auto-Update (#1093): was gerade passiert oder gefragt werden muss, steht vor "Quellen" und "Suche".
const au = (aend) => ({ verfuegbar: true, stufe: "aus", laufend: "1.8.0", aktuell: "1.8.0", neustart_noetig: false,
  neu: null, job: null, rueckgang: null, blockiert: null, ...aend });
const neuU = { version: "1.8.1", status: "neu", auszug: ["Etwas wurde besser."], frage_faellig: false };
const ohneAlt = { ...alles, verbunden: true, updateBekannt: null, ollamaAngebot: false };

// Rückfrage, Rückfall, Lauf, Fehler, Neustart: dringend — vor Quellen (0 aktiv) und vor einer nie gelaufenen Suche.
for (const [name, a, erwartet] of [
  ["frage", au({ neu: { ...neuU, frage_faellig: true } }), "update-frage"],
  ["rueckfall", au({ rueckgang: { von: "1.8.1", nach: "1.8.0" } }), "update-rueckgang"],
  ["lauf", au({ neu: neuU, job: { status: "laeuft", version: "1.8.1", anteil: 0.2, text: "x" } }), "update-laeuft"],
  ["fehler", au({ neu: neuU, job: { status: "fehler", version: "1.8.1", text: "x" } }), "update-fehler"],
  ["neustart", au({ aktuell: "1.8.1", neustart_noetig: true }), "update-neustart"],
]) {
  assert.equal(hinweisFuer({ ...ohneAlt, autoUpdate: a }, jetzt).id, erwartet, name);
}
// ...aber nicht vor der fehlenden Verbindung zu Claude: die ist die Voraussetzung für alles andere.
assert.equal(hinweisFuer({ ...ohneAlt, verbunden: false, autoUpdate: au({ neu: { ...neuU, frage_faellig: true } }) }, jetzt).id, "verbindung");
// ...und ohne Profil gibt es keinen Hinweis (der Einstieg erklärt es selbst).
assert.equal(hinweisFuer({ ...ohneAlt, hatProfil: false, autoUpdate: au({ rueckgang: { von: "a", nach: "b" } }) }, jetzt), null);

// Ein bloß BEKANNTES Update bleibt an Stufe 5: Quellen und Suche gehen vor.
const bekannt = au({ neu: neuU });
assert.equal(hinweisFuer({ ...ohneAlt, quellenAktiv: 0, autoUpdate: bekannt }, jetzt).id, "quellen");
assert.equal(hinweisFuer({ ...ohneAlt, quellenAktiv: 3, autoUpdate: bekannt }, jetzt).id, "suche");
assert.equal(hinweisFuer({ ...ohneAlt, quellenAktiv: 3, letzteSucheAm: vorTagen(1), autoUpdate: bekannt }, jetzt).id, "update");
// Der Rückfall geht allem vor, auch einer stillen Stufe.
assert.equal(hinweisFuer({ ...ohneAlt, autoUpdate: au({ stufe: "auto_still", rueckgang: { von: "1.8.1", nach: "1.8.0" } }) }, jetzt).id, "update-rueckgang");

// Arbeitet Claude noch mit der älteren Fassung, sagt die Zone es: vor "Quellen" und "Suche", hinter der fehlenden Verbindung.
const claudeAlt = { status: "connected", version: "1.8.0" };
const neuerLaeuft = au({ laufend: "1.8.1", aktuell: "1.8.1" });
assert.equal(hinweisFuer({ ...ohneAlt, quellenAktiv: 0, autoUpdate: neuerLaeuft, mcp: claudeAlt }, jetzt).id, "update-verbindung");
assert.notEqual(hinweisFuer({ ...ohneAlt, autoUpdate: neuerLaeuft, mcp: { status: "connected", version: "1.8.1" } }, jetzt)?.id, "update-verbindung", "gleiche Fassung: kein Hinweis von hier");
assert.equal(hinweisFuer({ ...ohneAlt, verbunden: false, autoUpdate: neuerLaeuft, mcp: claudeAlt }, jetzt).id, "verbindung");
assert.notEqual(hinweisFuer({ ...ohneAlt, autoUpdate: neuerLaeuft, mcp: { status: "disconnected", version: "1.8.0" } }, jetzt)?.id, "update-verbindung");

// Gibt es das Auto-Update hier nicht (aus dem Quellcode, macOS, Linux), gilt der bisherige Hinweis.
const alt = { ...ohneAlt, quellenAktiv: 3, letzteSucheAm: vorTagen(1), updateBekannt: { version: "1.8.1", url: "https://example.com" } };
assert.equal(hinweisFuer({ ...alt, autoUpdate: au({ verfuegbar: false }) }, jetzt).id, "update");
assert.equal(hinweisFuer({ ...alt, autoUpdate: au({ verfuegbar: false }) }, jetzt).aktion.art, "link");
assert.equal(hinweisFuer({ ...alt, autoUpdate: null }, jetzt).id, "update");
// Ist es da, ersetzt der neue Hinweis den alten (kein Doppel).
assert.equal(hinweisFuer({ ...alt, autoUpdate: au({ neu: neuU }) }, jetzt).aktionen[0].art, "link");

console.log("hinweisZone: ok");
