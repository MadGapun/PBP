// node frontend/src/lib/suche.test.mjs
// Treffer der Suche oben im Dashboard (#1177): ein Klick OEFFNET das Objekt — Zuordnung Treffer → Ziel und die Adressen.
// Bis v1.7.154 tat der Klick nichts: die Suche lieferte `#bewerbungen?id=…`, das Dashboard liest nur `#seite/kennung`.
import assert from "node:assert/strict";
import { zuBewerbung, zuDokument, zuMail, zuProfil, zuStelle, zuSuchtreffer, zuTermin } from "./suche.js";
import { PAGE_IDS, parseHashZiel, sprungAusHash } from "../utils.js";

// ── Objekte öffnen ────────────────────────────────────────────────────────────────────
assert.deepEqual(zuBewerbung("ab12cd34"), { seite: "bewerbungen", intent: { applicationId: "ab12cd34", focus: "timeline" } });
assert.deepEqual(zuStelle("h1"), { seite: "stellen", intent: { focus: "job", jobHash: "h1", oeffnen: true } }, "die Stelle wird geöffnet, nicht nur angescrollt");
assert.deepEqual(zuDokument("d7"), { seite: "dokumente", intent: { dokumentId: "d7" } });
assert.deepEqual(zuMail("e1"), { seite: "dokumente", intent: { mailId: "e1" } });
assert.deepEqual(zuTermin({ id: "t1", application_id: "ab12" }), zuBewerbung("ab12"), "ein Termin mit Bewerbung öffnet deren Timeline");
assert.deepEqual(zuTermin({ id: "t1" }), { seite: "kalender", intent: { terminId: "t1" } });
assert.equal(zuTermin({}), null);
assert.deepEqual(zuProfil("skills"), { seite: "profil", intent: { abschnitt: "skills" } });
assert.deepEqual(zuProfil("skills", "  "), { seite: "profil", intent: { abschnitt: "skills" } });
for (const leer of ["", "  ", null, undefined]) {
  assert.equal(zuBewerbung(leer), null);
  assert.equal(zuStelle(leer), null);
  assert.equal(zuDokument(leer), null);
  assert.equal(zuMail(leer), null);
}

// ── Treffer der Suche ─────────────────────────────────────────────────────────────────
assert.deepEqual(zuSuchtreffer({ kind: "application", id: "ab12" }), zuBewerbung("ab12"));
assert.deepEqual(zuSuchtreffer({ kind: "job", id: "h1" }), zuStelle("h1"));
assert.deepEqual(zuSuchtreffer({ kind: "document", id: "d7" }), zuDokument("d7"));
assert.deepEqual(zuSuchtreffer({ kind: "skill", id: "s1", title: "Python" }), { seite: "profil", intent: { abschnitt: "skills", suche: "Python" } });
assert.deepEqual(zuSuchtreffer({ kind: "meeting", id: "m1", application_id: "ab12" }), zuBewerbung("ab12"));
assert.deepEqual(zuSuchtreffer({ kind: "meeting", id: "m1", application_id: "" }), { seite: "kalender", intent: { terminId: "m1" } });
assert.deepEqual(zuSuchtreffer({ kind: "email", id: "e1", application_id: "ab12" }), { seite: "dokumente", intent: { mailId: "e1" } }, "eine Mail öffnet IHR Fenster, gleich ob sie zu einer Bewerbung gehört");
assert.deepEqual(zuSuchtreffer({ kind: "email", id: "e1" }), zuMail("e1"));
// ohne Ziel nie ein stilles Nichts: der Mensch liest, dass nichts aufgeht
assert.match(zuSuchtreffer({ kind: "gibts_nicht", id: "x" }).meldung, /keine Ansicht/);
assert.match(zuSuchtreffer(null).meldung, /keine Ansicht/);
for (const art of ["application", "job", "document", "email"]) assert.ok(zuSuchtreffer({ kind: art, id: "" }).meldung, art);

// ── Dieselben Ziele über die Adresse (Link aus Claude): dieselben Namen der Absichten ──
const ueberAdresse = (hash) => { const z = parseHashZiel(hash); return { seite: z.page, intent: sprungAusHash(z) }; };
assert.deepEqual(ueberAdresse("#dokumente/d7"), { seite: "dokumente", intent: zuDokument("d7").intent });
assert.deepEqual(ueberAdresse("#kalender/t1"), { seite: "kalender", intent: zuTermin({ id: "t1" }).intent });
assert.deepEqual(ueberAdresse("#profil/skills"), { seite: "profil", intent: { abschnitt: "skills" } });
assert.equal(ueberAdresse("#bewerbungen/ab12").intent.applicationId, "ab12");
assert.equal(ueberAdresse("#stellen/h1").intent.jobHash, "h1");
// Das FRÜHERE Format der Suche ist keine Seite: es fiel still auf das Dashboard zurück (der Fehler hinter #1177)
assert.equal(parseHashZiel("#bewerbungen?id=ab12").page, "dashboard");
// Jede Seite, auf die ein Treffer führt, kennt das Dashboard
for (const art of ["application", "job", "document", "meeting", "email", "skill"]) {
  const ziel = zuSuchtreffer({ kind: art, id: "x1", application_id: "", title: "x" });
  assert.ok(PAGE_IDS.includes(ziel.seite), `${art} → ${ziel.seite}`);
}

console.log("suche.test.mjs: ok");
