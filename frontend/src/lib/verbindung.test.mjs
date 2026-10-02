// node frontend/src/lib/verbindung.test.mjs — #1144
import assert from "node:assert/strict";
import {
  ABFRAGE_MS,
  ANFANG,
  FEHLSCHLAEGE_BIS_WEG,
  WIEDERHOLUNG_MS,
  anzeigeStand,
  kiAnzeige,
  naechsteAbfrageMs,
  naechsterStand,
} from "./verbindung.js";

// Solange der Server antwortet, bleibt alles beim Alten.
let s = ANFANG;
for (let i = 0; i < 5; i += 1) s = naechsterStand(s, true);
assert.deepEqual(s, { fehlschlaege: 0, erreichbar: true });
assert.equal(naechsteAbfrageMs(s), ABFRAGE_MS);

// Ein einzelner Fehlschlag ist noch kein Ausfall (Ruhezustand, Neustart) —
// aber die nächste Abfrage kommt bald, nicht erst in 30 Sekunden.
s = naechsterStand(ANFANG, false);
assert.equal(s.erreichbar, true);
assert.equal(s.fehlschlaege, 1);
assert.equal(naechsteAbfrageMs(s), WIEDERHOLUNG_MS);
assert.ok(WIEDERHOLUNG_MS < ABFRAGE_MS);

// Der zweite hintereinander schlägt die Anzeige um.
s = naechsterStand(s, false);
assert.equal(FEHLSCHLAEGE_BIS_WEG, 2);
assert.equal(s.erreichbar, false);
assert.equal(naechsteAbfrageMs(s), WIEDERHOLUNG_MS);

// Weitere Fehlschläge ändern nichts mehr, und der Zähler läuft nicht über.
for (let i = 0; i < 50; i += 1) s = naechsterStand(s, false);
assert.equal(s.erreichbar, false);
assert.equal(s.fehlschlaege, FEHLSCHLAEGE_BIS_WEG);

// Die erste Antwort nimmt es sofort zurück.
s = naechsterStand(s, true);
assert.deepEqual(s, { fehlschlaege: 0, erreichbar: true });
assert.equal(naechsteAbfrageMs(s), ABFRAGE_MS);

// Eine Antwort zwischen zwei Fehlschlägen setzt den Zähler zurück: zwei
// Ruckler mit Antwort dazwischen sind kein Ausfall.
s = naechsterStand(ANFANG, false);
s = naechsterStand(s, true);
s = naechsterStand(s, false);
assert.equal(s.erreichbar, true);

// Fehlt der Zustand ganz (Aufruf vor dem ersten Mal), gilt der Anfang.
assert.equal(naechsterStand(undefined, false).fehlschlaege, 1);
assert.equal(naechsteAbfrageMs(undefined), ABFRAGE_MS);

// Die Anzeige: fehlt der Server, steht dort nicht der zuletzt gemeldete
// Stand ("verbunden"), sondern server_weg.
assert.equal(anzeigeStand(true, "connected"), "connected");
assert.equal(anzeigeStand(false, "connected"), "server_weg");
assert.equal(anzeigeStand(true, undefined), "unknown");
assert.equal(anzeigeStand(false, undefined), "server_weg");

// Die Lokale-KI-Zeile ebenso.
assert.equal(kiAnzeige(true, "active"), "active");
assert.equal(kiAnzeige(false, "active"), "unbekannt");
assert.equal(kiAnzeige(true, undefined), "not_installed");

console.log("verbindung.test.mjs: ok");
