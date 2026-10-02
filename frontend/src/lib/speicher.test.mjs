// node frontend/src/lib/speicher.test.mjs
// Speicher & Downloads (#1131): Größen, Zusammenfassung, Schritte des Bereinigens.
import assert from "node:assert/strict";
import {
  URHEBER_TON, auswahlSumme, bereinigbar, darfLoeschen, loeschSatz, ortGroesse, schrittAus, zusammenfassung,
} from "./speicher.js";

const MB = 1024 * 1024;

// ── Größen ────────────────────────────────────────────────────────────────────────────
assert.equal(ortGroesse({ bytes: 5 * MB, vollstaendig: true }), "5,0 MB");
assert.equal(ortGroesse({ bytes: 5 * MB, vollstaendig: false }), "5,0 MB oder mehr", "eine abgebrochene Messung sagt es");
assert.equal(ortGroesse({ bytes: 0, nichts_vorhanden: true }), "nichts vorhanden");
assert.equal(ortGroesse({ bytes: 3 * 1024 ** 3, vollstaendig: true }), "3,0 GB");
assert.equal(ortGroesse(null), "nichts vorhanden");

// ── Zusammenfassung ───────────────────────────────────────────────────────────────────
assert.equal(zusammenfassung(null), "");
assert.equal(zusammenfassung({ orte: [], gesamt_bytes: 100 * MB, gesamt_fremd_bytes: 0 }), "PBP und deine Dateien belegen zusammen 100 MB.");
assert.match(zusammenfassung({ orte: [], gesamt_bytes: 100 * MB, gesamt_fremd_bytes: 2 * 1024 ** 3 }),
  /Dazu kommen 2,0 GB bei anderen Programmen/);

// ── Was sich bereinigen lässt ─────────────────────────────────────────────────────────
const aktionen = { export: {}, protokolle: {} };
assert.deepEqual(bereinigbar({ urheber: "pbp", aktionen: ["export", "protokolle", "gibts_nicht"] }, aktionen), ["export", "protokolle"]);
assert.deepEqual(bereinigbar({ urheber: "fremd", aktionen: ["export"] }, aktionen), [], "Fremdes wird nie bereinigt, auch wenn die Antwort es anböte");
assert.deepEqual(bereinigbar(null, aktionen), []);
assert.deepEqual(Object.keys(URHEBER_TON).sort(), ["du", "fremd", "komponente", "pbp"]);

// ── Die Schritte ──────────────────────────────────────────────────────────────────────
for (const [status, soll] of [["auswahl", "auswahl"], ["vorschau", "vorschau"], ["bereinigt", "ergebnis"], ["teilweise", "ergebnis"],
  ["nichts", "leer"], ["fehler", "fehler"], ["abgelehnt", "fehler"], [undefined, "fehler"]]) {
  assert.equal(schrittAus({ status }), soll, String(status));
}
assert.equal(schrittAus(null), "fehler");

// ── Auswahl und Bestätigung ────────────────────────────────────────────────────────────
const kand = [{ id: "a", bytes: 1 * MB }, { id: "b", bytes: 2 * MB }, { id: "c", bytes: 4 * MB }];
assert.equal(auswahlSumme(kand, new Set(["a", "c"])), 5 * MB);
assert.equal(auswahlSumme(kand, ["b"]), 2 * MB);
assert.equal(auswahlSumme(kand, new Set()), 0);
assert.equal(auswahlSumme(null, new Set(["a"])), 0);

const mitAuswahl = { braucht_auswahl: true, kandidaten: kand, anzahl: 3, bytes: 7 * MB };
assert.equal(darfLoeschen(mitAuswahl, new Set()), false, "ohne Häkchen nichts löschen");
assert.equal(darfLoeschen(mitAuswahl, new Set(["a"])), true);
assert.equal(loeschSatz(mitAuswahl, new Set(["a", "c"])), "2 Einträge, zusammen 5,0 MB, werden gelöscht.");
assert.equal(loeschSatz(mitAuswahl, new Set(["a"])), "1 Eintrag, zusammen 1,0 MB, wird gelöscht.");
const ohneAuswahl = { braucht_auswahl: false, anzahl: 4, bytes: 3 * MB, kandidaten: [] };
assert.equal(darfLoeschen(ohneAuswahl, null), true);
assert.equal(darfLoeschen({ braucht_auswahl: false, anzahl: 0 }, null), false);
assert.equal(darfLoeschen(null, null), false);
assert.equal(loeschSatz(ohneAuswahl, null), "4 Einträge, zusammen 3,0 MB, werden gelöscht.");

console.log("speicher: ok");
