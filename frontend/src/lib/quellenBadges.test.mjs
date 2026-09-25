// node frontend/src/lib/quellenBadges.test.mjs
import assert from "node:assert/strict";
import { WEG_BROWSER, quellenBadges } from "./quellenBadges.js";

const texte = (q, login) => quellenBadges(q, login).map((b) => b.text);

// Die vier gemeldeten Quellen, mit den Registry-Werten vom 18.09.2026.
const stepstone = { active: true, zugriffsart: "browser_login", geschwindigkeit: "langsam", login_erforderlich: false };
const indeed = { ...stepstone };
const linkedin = { active: true, zugriffsart: "browser_login", geschwindigkeit: "manuell", login_erforderlich: true, beta: true };
const xing = { ...linkedin, veraltet: true };

// 1. Alle vier sagen ihren WEG mit demselben Etikett.
for (const q of [stepstone, indeed, linkedin, xing]) {
  assert.ok(texte(q).includes(WEG_BROWSER), JSON.stringify(q));
}

// 2. "Browser" als Tempo-Etikett gibt es nicht mehr — bei keiner Quelle.
for (const q of [stepstone, indeed, linkedin, xing, { geschwindigkeit: "langsam", active: true }]) {
  assert.ok(!texte(q).includes("Browser"), "das Tempo heisst nie 'Browser'");
}
assert.ok(texte({ geschwindigkeit: "langsam", active: true }).includes("Langsam"));

// 3. XING trug zweimal "Manuell" — jetzt keinmal: der Weg sagt es schon.
assert.equal(texte(xing, "fertig").filter((t) => t === "Manuell").length, 0);
// ... und ueberhaupt steht kein Text doppelt, bei keiner der vier.
for (const q of [stepstone, indeed, linkedin, xing]) {
  const t = texte(q, "fertig");
  assert.equal(new Set(t).size, t.length, t.join(" | "));
}

// 4. Der Weg schlaegt das Tempo: eine Browser-Quelle traegt KEIN Tempo.
for (const q of [stepstone, linkedin]) {
  assert.ok(!quellenBadges(q).some((b) => b.art === "tempo"));
}
// Die Gegenrichtung: eine automatische Quelle behaelt ihr Tempo und bekommt
// keinen Browser-Weg.
const jobspy = { active: true, geschwindigkeit: "schnell", beta: true };
assert.deepEqual(texte(jobspy), ["Aktiv", "Schnell", "Beta"]);
// `veraltet` ohne Browser-Weg hat ein eigenes Wort.
assert.ok(texte({ active: false, veraltet: true, geschwindigkeit: "manuell" }).includes("Nicht automatisiert"));

// 5. Konto noetig gegen Konto empfohlen — der Unterschied steht im Text.
assert.ok(texte(linkedin).includes("Konto nötig"));
assert.ok(texte(stepstone).includes("Konto empfohlen"));
assert.ok(!texte(stepstone).includes("Konto nötig"));

// 6. Der Login-Status ist ein Zustand, steht zuletzt und sagt es.
const mitLogin = quellenBadges(xing, "fertig");
assert.equal(mitLogin.at(-1).art, "zustand");
assert.equal(mitLogin.at(-1).text, "Login: Session bereit");

// Ein fehlgeschlagener Login ist rot und heisst so (vorher `loginTone`).
const fehl = quellenBadges(xing, "fehler").at(-1);
assert.deepEqual([fehl.text, fehl.tone], ["Login fehlgeschlagen", "danger"]);

// 7. "Wartet auf dich" nur bei AKTIVER Browser-Quelle.
assert.ok(texte(stepstone).includes("Wartet auf dich"));
assert.ok(!texte({ ...stepstone, active: false }).includes("Wartet auf dich"));

// 8. Eine defekte Quelle sagt nur das.
assert.deepEqual(texte({ defekt: true, zugriffsart: "browser_login", geschwindigkeit: "langsam", login_erforderlich: true }),
  ["Defekt"]);

console.log("quellenBadges: ok");
