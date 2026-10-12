// node frontend/src/lib/wegleiste.test.mjs
// Die feste Weg-Leiste (#1171, G85, Baustein 3): was von einer Ansicht aus als Nächstes geht.
import assert from "node:assert/strict";
import {
  bewerbungLeiste, bewerbungSchritt, klicksZu, kontaktLeiste, kontaktSchritt, stelleLeiste, stelleSchritt, WEG_WORT,
} from "./wegleiste.js";

const ids = (liste) => liste.map((f) => f.id);

// ── Die Wörter: einmal ────────────────────────────────────────────────────────────────
assert.deepEqual(WEG_WORT, { stelle: "Zur Stelle", bewerbung: "Zur Bewerbung", firma: "Zur Firma", kontakt: "Zum Kontakt" });

// ── Bewerbung: der nächste Schritt je Status ─────────────────────────────────────────
assert.equal(bewerbungSchritt({ status: "in_vorbereitung" }).haupt.aktion, "lebenslauf");
assert.deepEqual(bewerbungSchritt({ status: "in_vorbereitung" }).weitere.map((w) => w.aktion), ["anschreiben"]);
assert.equal(bewerbungSchritt({ status: "in_vorbereitung", hatLebenslauf: true }).haupt.aktion, "anschreiben");
assert.equal(bewerbungSchritt({ status: "in_vorbereitung", hatLebenslauf: true, hatAnschreiben: true }).haupt.aktion, "beworben_eintragen");
assert.equal(bewerbungSchritt({ status: "beworben" }).haupt.aktion, "nachfassen");
assert.equal(bewerbungSchritt({ status: "eingangsbestaetigung" }).haupt.aktion, "nachfassen");
assert.equal(bewerbungSchritt({ status: "interview" }).haupt.aktion, "gespraech_vorbereiten");
assert.equal(bewerbungSchritt({ status: "zweitgespraech" }).haupt.aktion, "gespraech_vorbereiten");
assert.equal(bewerbungSchritt({ status: "angebot" }).haupt.aktion, "angebot_pruefen");
assert.equal(bewerbungSchritt({ status: "abgelehnt" }).haupt.aktion, "aus_absage_lernen");
// ein Gespräch geht vor einer fälligen Nachfassung
assert.equal(bewerbungSchritt({ status: "interview", nachfassenFaellig: true }).haupt.aktion, "gespraech_vorbereiten");
// zu Ende: kein erfundener Schritt
for (const s of ["angenommen", "zurueckgezogen", "abgelaufen", "arbeitgeber_ausgefallen"]) {
  assert.equal(bewerbungSchritt({ status: s, nachfassenFaellig: true }).haupt, null, s);
}
assert.equal(bewerbungSchritt({}).haupt, null);
assert.equal(bewerbungSchritt({ status: "unbekannt" }).haupt, null);
// Unterlagen und Nachfassen sind Aufträge an Claude
assert.equal(bewerbungSchritt({ status: "in_vorbereitung" }).haupt.mitClaude, true);
assert.equal(bewerbungSchritt({ status: "in_vorbereitung", hatLebenslauf: true, hatAnschreiben: true }).haupt.mitClaude, false);

// ── Stelle ────────────────────────────────────────────────────────────────────────────
assert.equal(stelleSchritt({ beurteilt: false }).haupt.aktion, "bewerten");
assert.deepEqual(stelleSchritt({ beurteilt: false }).weitere.map((w) => w.aktion), ["bewerbung_anlegen"]);
assert.equal(stelleSchritt({ beurteilt: true }).haupt.aktion, "bewerbung_anlegen");
assert.equal(stelleSchritt({ beurteilt: true, bewerbungId: "ab12" }).haupt.aktion, "zur_bewerbung");
assert.equal(stelleSchritt({ beurteilt: false, bewerbungId: "ab12" }).haupt.label, "Zur Bewerbung");
assert.deepEqual(stelleSchritt({ beurteilt: true, hatAnzeige: true }).weitere.map((w) => w.aktion), ["anzeige_oeffnen"]);

// ── Kontakt ───────────────────────────────────────────────────────────────────────────
assert.equal(kontaktSchritt({ name: "Erika Beispiel", laufendeBewerbung: true }).haupt.label, "Nachfassen bei Erika Beispiel");
assert.equal(kontaktSchritt({ laufendeBewerbung: true }).haupt.label, "Nachfassen");
assert.equal(kontaktSchritt({ name: "Erika Beispiel" }).haupt, null);

// ── Die Leiste einer Bewerbung: nur, was es gibt, mit Anzahl; ein Klick öffnet das Objekt ──
const b = bewerbungLeiste({
  zurueckLabel: "Bewerbungen", jobHash: "h1", firma: "Beispielwerk GmbH", bewerbungId: "app1", status: "interview",
  kontakte: [{ id: "c1", full_name: "Erika Beispiel" }],
  dokumente: [{ id: "d1", filename: "Lebenslauf.pdf" }, { id: "d2", filename: "Anschreiben.pdf" }],
  termine: [{ id: "t1", title: "Gespräch", meeting_date: "2026-11-03T10:00:00" }],
});
assert.equal(b.art, "bewerbung");
assert.equal(b.zurueck.label, "Zurück zu Bewerbungen");
assert.deepEqual(ids(b.faelle), ["stelle", "firma", "kontakte", "dokumente", "termine"]);
assert.deepEqual(b.faelle.find((f) => f.id === "stelle").eintraege[0].ziel,
  { seite: "stellen", intent: { focus: "job", jobHash: "h1", oeffnen: true } }, "die Stelle wird geöffnet, nicht die Liste");
assert.deepEqual(b.faelle.find((f) => f.id === "kontakte").eintraege[0].ziel,
  { seite: "kontakte", intent: { ansicht: "kontakte", kontaktId: "c1" } });
assert.equal(b.faelle.find((f) => f.id === "dokumente").anzahl, 2);
assert.equal(b.faelle.find((f) => f.id === "termine").eintraege[0].label, "Gespräch · 2026-11-03");
assert.equal(b.haupt.aktion, "gespraech_vorbereiten");
// ein Termin einer Bewerbung öffnet deren Verlauf, nicht den Kalender (wege.js)
assert.equal(b.faelle.find((f) => f.id === "termine").eintraege[0].ziel.seite, "bewerbungen");

// Klicks: 1 mit einem Objekt, 2 mit Auswahl, nichts ohne Fall
assert.equal(klicksZu(b, "stelle"), 1);
assert.equal(klicksZu(b, "kontakte"), 1);
assert.equal(klicksZu(b, "dokumente"), 2);
assert.equal(klicksZu(b, "aufgaben"), null);

// Was es nicht gibt, steht nicht da
const leer = bewerbungLeiste({ status: "beworben" });
assert.deepEqual(leer.faelle, []);
assert.equal(leer.haupt.aktion, "nachfassen");
assert.equal(bewerbungLeiste({ status: "angenommen" }).haupt, null);
// Einträge ohne Kennung gibt es nicht
assert.deepEqual(ids(bewerbungLeiste({ kontakte: [{ full_name: "Ohne Kennung" }] }).faelle), []);

// ── Die Leiste einer Stelle ──────────────────────────────────────────────────────────
const s = stelleLeiste({ zurueckLabel: "Stellen", firma: "Beispielwerk GmbH", beurteilt: true, hatAnzeige: true });
assert.deepEqual(ids(s.faelle), ["firma"]);
assert.equal(s.haupt.aktion, "bewerbung_anlegen");
const sMit = stelleLeiste({ firma: "Beispielwerk GmbH", bewerbungId: "app1", kontakte: [{ id: "c1", full_name: "Erika Beispiel" }] });
assert.deepEqual(ids(sMit.faelle), ["bewerbung", "firma", "kontakte"]);
assert.deepEqual(sMit.faelle[0].eintraege[0].ziel, { seite: "bewerbungen", intent: { applicationId: "app1", focus: "timeline" } });
assert.equal(sMit.haupt.aktion, "zur_bewerbung");

// ── Die Leiste eines Kontakts ────────────────────────────────────────────────────────
const k = kontaktLeiste({
  name: "Erika Beispiel", firma: "Beispielwerk GmbH", laufendeBewerbung: true,
  bewerbungen: [{ id: "app1", label: "Bewerbung: Leiter Fertigung" }], stellen: [{ hash: "h1", label: "Stelle: Leiter Fertigung" }],
});
assert.deepEqual(ids(k.faelle), ["bewerbungen", "stellen", "firma"]);
assert.equal(k.haupt.label, "Nachfassen bei Erika Beispiel");
assert.equal(k.zurueck.label, "Zurück zu Kontakte");

console.log("wegleiste.test.mjs: ok");
