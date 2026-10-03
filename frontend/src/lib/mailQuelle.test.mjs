// node frontend/src/lib/mailQuelle.test.mjs
// Mail-Ordner als Quelle (#947): die Zeile über dem Schalter, Zahlen je Ordner, Freigabe-Schritte.
import assert from "node:assert/strict";
import { ANBIETER_LISTE, anbieterLabel, darfFreigeben, freigabeSchritt, statusText, statusTon, zahlenText } from "./mailQuelle.js";

// ── Die Anbieter ──────────────────────────────────────────────────────────────────────
assert.deepEqual(ANBIETER_LISTE.map((a) => a.id), ["thunderbird", "outlook", "sonstige"]);
assert.equal(anbieterLabel("outlook"), "Outlook");
assert.equal(anbieterLabel("gibts-nicht"), "gibts-nicht");
assert.equal(anbieterLabel(undefined), "");

// ── Die Zeile über dem Schalter ───────────────────────────────────────────────────────────
assert.equal(statusText(null), "");
assert.equal(statusText({ scan_aktiv: false, freigaben: [] }), "Aus");
assert.equal(statusText({ scan_aktiv: true, freigaben: [] }), "An, aber kein Ordner freigegeben – es wird nichts gelesen",
  "ehrlich: an, aber nichts wird gelesen");
assert.equal(statusText({ scan_aktiv: true, wirksam: true, freigaben: [{}] }), "An – 1 Ordner freigegeben");
assert.equal(statusText({ scan_aktiv: true, wirksam: true, freigaben: [{}, {}] }), "An – 2 Ordner freigegeben");
assert.match(statusText({ scan_aktiv: true, neu_bestaetigen: true, freigaben: [{}] }), /^Aus .*Beta.*erneut bestätigen/,
  "eine Beta-Einstellung gilt in stabil als aus, und die Zeile sagt es");
assert.match(statusText({ scan_aktiv: false, unlesbar: true, freigaben: [] }), /^Aus .*nicht sicher lesen/);
assert.equal(statusTon({ wirksam: true }), "amber", "nur wirksam fällt auf");
assert.equal(statusTon({ wirksam: false, scan_aktiv: true }), "neutral");
assert.equal(statusTon(null), "neutral");

// ── Zahlen je Ordner ───────────────────────────────────────────────────────────────────
assert.equal(zahlenText({ letzter_lauf: null, mails: 0, stellen: 0 }), "noch nichts gelesen");
assert.equal(zahlenText(null), "noch nichts gelesen");
assert.match(zahlenText({ letzter_lauf: "2026-10-02T10:15:00+00:00", mails: 1, stellen: 1 }), /^1 Mail, 1 Stelle, zuletzt \d\d\.\d\d\.2026/);
assert.match(zahlenText({ letzter_lauf: "2026-10-02T10:15:00+00:00", mails: 12, stellen: 0 }), /^12 Mails, 0 Stellen, zuletzt /);

// ── Freigeben ─────────────────────────────────────────────────────────────────────────
assert.equal(darfFreigeben("thunderbird", "Jobs"), true);
assert.equal(darfFreigeben("thunderbird", "Jobs/Portale"), true);
assert.equal(darfFreigeben("thunderbird", ""), false);
assert.equal(darfFreigeben("thunderbird", "  / \\ "), false, "nur Trenner und Leerraum ist kein Ordner");
assert.equal(darfFreigeben("gmail", "Jobs"), false, "unbekannter Anbieter");
assert.equal(darfFreigeben("", "Jobs"), false);
for (const [status, soll] of [["freigegeben", "fertig"], ["posteingang_warnung", "warnung"], ["schon_da", "schon_da"],
  ["fehler", "fehler"], [undefined, "fehler"]]) {
  assert.equal(freigabeSchritt({ status }), soll, String(status));
}
assert.equal(freigabeSchritt(null), "fehler");

console.log("mailQuelle: ok");
