// node frontend/src/lib/apiWeg.test.mjs
// Optionaler API-Weg der KI (#1236): wann die Karte erscheint, die Zeilen, das Budget, die Auswahl.
import assert from "node:assert/strict";
import {
  datumText, aufgabeStatus, aufgabeTon, budgetEingabe, budgetZeile, datenflussApi, kannPruefen, letzterAufrufText, neueAuswahl,
  pruefungText, pruefungTon, sichtbar, verbrauchProzent, verbrauchZeile,
} from "./apiWeg.js";

// ── Die Karte erscheint nur, wenn es etwas zu zeigen gibt ────────────────────────────────────
assert.equal(sichtbar(null), false);
assert.equal(sichtbar(undefined), false);
assert.equal(sichtbar({ sichtbar: false, schluessel_gesetzt: false }), false, "ohne Schlüssel und Freigabe: nichts");
assert.equal(sichtbar({ sichtbar: true }), true);

// ── Ein reines Datum bleibt in jeder Zeitzone derselbe Tag ──────────────────────────────────
assert.equal(datumText("2026-10-16"), "16.10.2026");
assert.equal(datumText("2026-10-16T23:59:59+00:00"), "16.10.2026");
assert.equal(datumText(""), "");
assert.equal(datumText(null), "");
assert.equal(datumText("kein Datum"), "");

// ── Die Prüfung: „gültig“ nur nach einer echten Probe ────────────────────────────────────
assert.equal(pruefungText({ ergebnis: "nicht_geprueft" }), "Noch nicht geprüft");
assert.equal(pruefungText(undefined), "Noch nicht geprüft");
assert.equal(pruefungText({ ergebnis: "irgendwas" }), "Noch nicht geprüft", "Unbekanntes ist nie „gültig“");
assert.match(pruefungText({ ergebnis: "gueltig", zeit: "2026-10-16T12:00:00+00:00" }), /^Gültig – die API hat die Probeanfrage angenommen \(\d\d\.\d\d\.2026/);
assert.equal(pruefungText({ ergebnis: "gueltig" }), "Gültig – die API hat die Probeanfrage angenommen");
assert.equal(pruefungText({ ergebnis: "ungueltig" }), "Die API hat den Schlüssel abgelehnt");
assert.match(pruefungText({ ergebnis: "unklar", code: "kein_netz" }), /kein klares Ergebnis.*letzter Aufruf/);
assert.equal(pruefungTon({ ergebnis: "gueltig" }), "success");
assert.equal(pruefungTon({ ergebnis: "ungueltig" }), "danger");
assert.equal(pruefungTon({ ergebnis: "unklar" }), "neutral");
assert.equal(pruefungTon(null), "neutral");
assert.equal(kannPruefen({ schluessel_gesetzt: true }), true);
assert.equal(kannPruefen({ schluessel_gesetzt: false }), false, "ohne Schlüssel gibt es nichts zu prüfen");
assert.equal(kannPruefen(null), false);

// ── Eine Aufgabe in einem Satz ───────────────────────────────────────────────────────────
assert.equal(aufgabeStatus(null), "");
assert.equal(aufgabeStatus({ freigegeben: false }), "Aus");
assert.equal(aufgabeStatus({ freigegeben: true, bereit: true }), "Freigegeben und bereit");
assert.equal(aufgabeStatus({ freigegeben: true, bereit: false, grund_text: "Das Budget ist aufgebraucht." }),
  "Freigegeben, aber gerade nicht genutzt: Das Budget ist aufgebraucht.", "der Grund kommt vom Server");
assert.match(aufgabeStatus({ freigegeben: true, bereit: false }), /unbekannter Grund/);
assert.equal(aufgabeTon({ freigegeben: false }), "neutral");
assert.equal(aufgabeTon({ freigegeben: true, bereit: true }), "success");
assert.equal(aufgabeTon({ freigegeben: true, bereit: false }), "amber", "freigegeben, aber ruhend fällt auf");

// ── Die neue Auswahl beim Umschalten ──────────────────────────────────────────────────────
const u = { aufgaben: [{ id: "a", freigegeben: true }, { id: "b", freigegeben: false }] };
assert.deepEqual(neueAuswahl(u, "b", true), ["a", "b"]);
assert.deepEqual(neueAuswahl(u, "a", false), []);
assert.deepEqual(neueAuswahl(u, "a", true), ["a"], "doppeltes Einschalten ändert nichts");
assert.deepEqual(neueAuswahl({ aufgaben: [] }, "a", true), ["a"]);
assert.deepEqual(neueAuswahl(null, "a", true), ["a"]);

// ── Das Budget ────────────────────────────────────────────────────────────────────────────
for (const [text, soll] of [["5", 5], ["5,50", 5.5], ["5.5", 5.5], [" 12 ", 12], ["0", 0], ["0,01", 0.01]]) {
  assert.equal(budgetEingabe(text), soll, `„${text}“`);
}
for (const text of ["", "  ", "abc", "-1", "5,555", "5,", ",5", "1e3", "5 Dollar", "5,00,00", null, undefined]) {
  assert.equal(budgetEingabe(text), null, `„${text}“ ist kein Betrag`);
}
assert.equal(budgetZeile({ budget: { gesetzt: false } }), "Kein Budget gesetzt – ohne Obergrenze ruft PBP die API nicht auf.");
assert.equal(budgetZeile({ budget: { gesetzt: true, text: "5,00 US-Dollar" }, verbrauch: { text: "0,02 US-Dollar" } }),
  "Verbraucht 0,02 US-Dollar von 5,00 US-Dollar");
assert.equal(verbrauchProzent({ budget: { usd: 10 }, verbrauch: { usd: 2.5 } }), 25);
assert.equal(verbrauchProzent({ budget: { usd: 10 }, verbrauch: { usd: 99 } }), 100, "die Leiste läuft nie über");
assert.equal(verbrauchProzent({ budget: { usd: null }, verbrauch: { usd: 1 } }), null, "ohne Budget keine Leiste");
assert.equal(verbrauchProzent({ budget: { usd: 0 } }), null);
assert.equal(verbrauchProzent(null), null);

// ── Der Verbrauch ─────────────────────────────────────────────────────────────────────────
assert.equal(verbrauchZeile({ verbrauch: { aufrufe: 0 } }), "Bisher kein Aufruf über PBP.");
assert.equal(verbrauchZeile(null), "Bisher kein Aufruf über PBP.");
assert.match(verbrauchZeile({ verbrauch: { aufrufe: 1, eingabe_tokens: 100, ausgabe_tokens: 20, text: "0,00002 US-Dollar" } }),
  /^1 Aufruf \(100 Tokens ein, 20 aus\), 0,00002 US-Dollar$/);
assert.match(verbrauchZeile({ verbrauch: { aufrufe: 1200, eingabe_tokens: 1500000, ausgabe_tokens: 40000, text: "0,17 US-Dollar", seit: "2026-10-16T08:00:00+00:00" } }),
  /^1\.200 Aufrufe \(1\.500\.000 Tokens ein, 40\.000 aus\), 0,17 US-Dollar, seit 16\.10\.2026$/);

// ── Der letzte Aufruf ─────────────────────────────────────────────────────────────────────
assert.equal(letzterAufrufText(null), "");
assert.match(letzterAufrufText({ ok: true, zeit: "2026-10-16T12:00:00+00:00" }), /^Letzter Aufruf: gelungen \(\d\d\.\d\d\.2026/);
assert.match(letzterAufrufText({ ok: false, text: "Das Guthaben ist aufgebraucht." }), /gescheitert – Das Guthaben ist aufgebraucht\.$/);
assert.match(letzterAufrufText({ ok: false, code: "kein_netz" }), /gescheitert – kein_netz$/, "ohne Text zumindest der Code, nie nichts");
assert.match(letzterAufrufText({ ok: false }), /unbekannter Grund$/);

// ── Datenschutz-Anzeige: nur mit der vierten Zeile ─────────────────────────────────────────
assert.equal(datenflussApi({ local_only: [], sent_to_claude: [] }), null, "ohne Freigabe bleibt die Auskunft, wie sie war");
assert.equal(datenflussApi({ sent_to_api: [] }), null);
assert.equal(datenflussApi(undefined), null);
assert.deepEqual(datenflussApi({ sent_to_api: ["a", "b"] }), ["a", "b"]);

console.log("apiWeg: ok");
