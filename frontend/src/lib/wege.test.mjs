// node frontend/src/lib/wege.test.mjs
// Wege durch PBP (#1171, G85): wohin ein Klick auf ein Ding führt, und was die Sprungleiste zeigt.
import assert from "node:assert/strict";
import {
  offenZeileZiel, sprungleiste, SPRUNG_WORT, TIMELINE_ABSCHNITTE, verknuepfungZeile,
  zuAufgabe, zuBewerbung, zuDokument, zuFirma, zuKontakt, zuMail, zuProfil, zuStelle, zuSuchtreffer, zuTermin,
} from "./wege.js";
import { PAGE_IDS, parseHashZiel, sprungAusHash } from "../utils.js";

// ── Objekte öffnen ────────────────────────────────────────────────────────────────────
assert.deepEqual(zuBewerbung("ab12cd34"), { seite: "bewerbungen", intent: { applicationId: "ab12cd34", focus: "timeline" } });
assert.deepEqual(zuStelle("h1"), { seite: "stellen", intent: { focus: "job", jobHash: "h1", oeffnen: true } }, "die Stelle wird geöffnet, nicht nur angescrollt");
assert.deepEqual(zuKontakt("c9"), { seite: "kontakte", intent: { ansicht: "kontakte", kontaktId: "c9" } }, "die Person wird geöffnet, nicht gesucht");
assert.deepEqual(zuFirma({ firmaId: "fi_1" }), { seite: "kontakte", intent: { ansicht: "firmen", firmaId: "fi_1" } });
assert.deepEqual(zuFirma({ firmaName: "Muster GmbH" }), { seite: "kontakte", intent: { ansicht: "firmen", firmaName: "Muster GmbH" } });
assert.deepEqual(zuFirma({ firmaId: "fi_1", firmaName: "Muster GmbH" }).intent, { ansicht: "firmen", firmaId: "fi_1" }, "die Kennung geht vor dem Namen");
assert.deepEqual(zuDokument("d7"), { seite: "dokumente", intent: { dokumentId: "d7" } });

// ohne Kennung kein Sprung: der Aufrufer zeichnet dann keinen toten Knopf
for (const leer of ["", "  ", null, undefined]) {
  assert.equal(zuBewerbung(leer), null);
  assert.equal(zuStelle(leer), null);
  assert.equal(zuKontakt(leer), null);
  assert.equal(zuDokument(leer), null);
}
assert.equal(zuFirma({}), null);
assert.equal(zuFirma(), null);

// ── Termin und Aufgabe: gehören sie zu einer Bewerbung, ist deren Timeline der Weg ──────
assert.deepEqual(zuTermin({ id: "t1", application_id: "ab12" }), zuBewerbung("ab12"));
assert.deepEqual(zuTermin({ id: "t1", bewerbung_id: "ab12" }), zuBewerbung("ab12"));
assert.deepEqual(zuTermin({ id: "t1" }), { seite: "kalender", intent: { terminId: "t1" } });
assert.deepEqual(zuTermin({}), { seite: "kalender", intent: null });
assert.deepEqual(zuAufgabe({ id: "a1", bewerbung_id: "ab12" }), zuBewerbung("ab12"));
assert.deepEqual(zuAufgabe({ id: "a1" }), { seite: "aufgaben", intent: { aufgabeId: "a1" } });
assert.deepEqual(zuAufgabe({}), { seite: "aufgaben", intent: null });

// ── Block „Offen“ im Dashboard ───────────────────────────────────────────────────────
assert.deepEqual(offenZeileZiel({ herkunft: "nachfass", id: "f1", bewerbung_id: "ab12" }), zuBewerbung("ab12"), "eine Nachfassung öffnet ihre Bewerbung (war: nur die Aufgaben-Seite)");
assert.deepEqual(offenZeileZiel({ herkunft: "todo", id: "t1", bewerbung_id: "ab12" }), zuBewerbung("ab12"));
assert.deepEqual(offenZeileZiel({ herkunft: "todo", id: "t1" }), { seite: "aufgaben", intent: null }, "ohne Bewerbung bleibt es die Aufgaben-Seite");
assert.deepEqual(offenZeileZiel({ herkunft: "termin", id: "m1", bewerbung_id: "ab12" }), zuBewerbung("ab12"));
assert.deepEqual(offenZeileZiel({ herkunft: "termin", id: "m1" }), { seite: "kalender", intent: { terminId: "m1" } });
assert.equal(offenZeileZiel(null), null);

// ── Verknüpfungen eines Kontakts ────────────────────────────────────────────────────
const app = verknuepfungZeile({ target_kind: "application", target_id: "ab12", role: "Leiter Fertigung", ziel_titel: "Fertigungssteuerer", ziel_firma: "Muster GmbH", ziel_gefunden: true });
assert.equal(app.text, "Bewerbung: Fertigungssteuerer bei Muster GmbH");
assert.equal(app.rolle, "Leiter Fertigung");
assert.deepEqual(app.ziel, zuBewerbung("ab12"));
assert.equal(app.sprungWort, "Zur Bewerbung");
assert.doesNotMatch(app.text, /application/, "kein rohes englisches Wort mehr");
const job = verknuepfungZeile({ target_kind: "job", target_id: "h1", ziel_titel: "Meister", ziel_firma: "Beispiel AG", ziel_gefunden: true });
assert.equal(job.text, "Stelle: Meister bei Beispiel AG");
assert.deepEqual(job.ziel, zuStelle("h1"));
assert.equal(job.sprungWort, "Zur Stelle");
const termin = verknuepfungZeile({ target_kind: "meeting", target_id: "m1", ziel_titel: "Erstgespräch", ziel_bewerbung_id: "ab12", ziel_gefunden: true });
assert.deepEqual(termin.ziel, zuBewerbung("ab12"));
assert.equal(termin.text, "Termin: Erstgespräch");
const firma = verknuepfungZeile({ target_kind: "company", target_id: "x", ziel_titel: "Beispiel AG", ziel_gefunden: true });
assert.equal(firma.text, "Firma: Beispiel AG");
assert.deepEqual(firma.ziel, zuFirma({ firmaName: "Beispiel AG" }));
const weg = verknuepfungZeile({ target_kind: "application", target_id: "geloescht", ziel_gefunden: false });
assert.equal(weg.ziel, null, "was es nicht mehr gibt, bleibt Text");
assert.equal(weg.vorhanden, false);
assert.equal(weg.text, "Bewerbung");
assert.equal(verknuepfungZeile({ target_kind: "seltsam", target_id: "1" }).ziel, null);
assert.equal(verknuepfungZeile(null).text, "Verknüpfung");

// ── Wörter und Sprungleiste ─────────────────────────────────────────────────────────
assert.equal(SPRUNG_WORT.bewerbung, "Zur Bewerbung");
assert.equal(SPRUNG_WORT.kontakt, "Zum Kontakt");
assert.deepEqual(TIMELINE_ABSCHNITTE.map((a) => a.kennung), ["status", "stelle", "dokumente", "personen", "aufgaben", "termine", "verlauf"]);
assert.deepEqual(sprungleiste(["verlauf", "status", "dokumente"]).map((a) => a.label), ["Status", "Dokumente", "Verlauf"], "feste Reihenfolge, nur was es gibt");
assert.deepEqual(sprungleiste([]), []);
assert.deepEqual(sprungleiste(null), []);

// ── Treffer der Suche oben (#1177, G88): ein Klick OEFFNET das Objekt ───────────────────
// Bis v1.7.154 tat er nichts: die Suche lieferte `#bewerbungen?id=…`, das Dashboard liest nur `#seite/kennung`.
assert.deepEqual(zuSuchtreffer({ kind: "application", id: "ab12" }), zuBewerbung("ab12"));
assert.deepEqual(zuSuchtreffer({ kind: "job", id: "h1" }), zuStelle("h1"), "die Stelle wird geöffnet, nicht nur angescrollt");
assert.deepEqual(zuSuchtreffer({ kind: "document", id: "d7" }), zuDokument("d7"));
assert.deepEqual(zuSuchtreffer({ kind: "skill", id: "s1", title: "Python" }), { seite: "profil", intent: { abschnitt: "skills", suche: "Python" } });
// ein Termin mit Bewerbung: deren Timeline, am Abschnitt „Termine“; ohne Bewerbung: der Termin im Kalender
assert.deepEqual(zuSuchtreffer({ kind: "meeting", id: "m1", application_id: "ab12" }),
  { seite: "bewerbungen", intent: { applicationId: "ab12", focus: "timeline", abschnitt: "termine" } });
assert.deepEqual(zuSuchtreffer({ kind: "meeting", id: "m1", application_id: "" }), { seite: "kalender", intent: { terminId: "m1" } });
// eine Mail öffnet IHR Fenster auf der Dokumente-Seite — gleich, ob sie zu einer Bewerbung gehört
assert.deepEqual(zuSuchtreffer({ kind: "email", id: "e1", application_id: "ab12" }), { seite: "dokumente", intent: { mailId: "e1" } });
assert.deepEqual(zuSuchtreffer({ kind: "email", id: "e1" }), zuMail("e1"));
assert.match(zuSuchtreffer({ kind: "gibts_nicht", id: "x" }).meldung, /keine Ansicht/);
assert.match(zuSuchtreffer(null).meldung, /keine Ansicht/);
// ohne Kennung kein Sprung — und nie ein stilles Nichts
for (const art of ["application", "job", "document", "email"]) assert.ok(zuSuchtreffer({ kind: art, id: "" }).meldung, art);
assert.equal(zuMail(""), null);
assert.deepEqual(zuProfil("skills"), { seite: "profil", intent: { abschnitt: "skills" } });
assert.deepEqual(zuProfil("skills", "  "), { seite: "profil", intent: { abschnitt: "skills" } });

// Dieselben Ziele über die Adresse (Link aus Claude, `#dokumente/<id>`): dieselben Namen der Absichten wie in `wege.js`.
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

console.log("wege.test.mjs: ok");
