// node frontend/src/lib/updateStand.test.mjs — #1134
import assert from "node:assert/strict";
import {
  FRAGE_MAX_MS,
  FRAGE_MIN_MS,
  FRAGE_OHNE_ANTWORT_MS,
  grundText,
  naechsteFrageMs,
  neueLinieHinweis,
  unbekanntTitel,
  VEROEFFENTLICHUNGEN_URL,
} from "./updateStand.js";

// Der Server bestimmt, wann erneut gefragt wird: nach einem Fehlschlag bald,
// nach einem Erfolg erst in einer Stunde.
assert.equal(naechsteFrageMs({ stand: "unbekannt", wieder_fragen_nach_s: 120 }), 120 * 1000);
assert.equal(naechsteFrageMs({ stand: "geprueft", wieder_fragen_nach_s: 3600 }), FRAGE_MAX_MS);

// Grenzen: nie dichter als 30 s (auch wenn der Server 5 s sagt), nie länger als eine Stunde.
assert.equal(naechsteFrageMs({ wieder_fragen_nach_s: 5 }), FRAGE_MIN_MS);
assert.equal(naechsteFrageMs({ wieder_fragen_nach_s: 86400 }), FRAGE_MAX_MS);

// Fehlt die Angabe (ältere Server) oder ist sie Unsinn: stündlich, nicht im Sekundentakt.
assert.equal(naechsteFrageMs({ stand: "geprueft" }), FRAGE_MAX_MS);
assert.equal(naechsteFrageMs({ wieder_fragen_nach_s: "bald" }), FRAGE_MAX_MS);
assert.equal(naechsteFrageMs({ wieder_fragen_nach_s: -3 }), FRAGE_MAX_MS);

// Antwortet der Dashboard-Server selbst nicht: in fünf Minuten noch einmal.
assert.equal(naechsteFrageMs(null), FRAGE_OHNE_ANTWORT_MS);
assert.equal(naechsteFrageMs(undefined), FRAGE_OHNE_ANTWORT_MS);

// Der Grund steht im Klartext und nennt jede Quelle.
const daten = {
  stand: "unbekannt",
  wieder_fragen_nach_s: 120,
  quellen_versucht: [
    { name: "elwosa", status: 404 },
    { name: "github", fehler: "[Errno 11001] getaddrinfo failed" },
  ],
};
assert.equal(
  grundText(daten),
  "Keine Update-Quelle hat geantwortet (elwosa: Antwort 404, github: keine Verbindung).",
);
assert.equal(grundText({ quellen_versucht: [] }), "Keine Update-Quelle hat geantwortet.");
assert.equal(grundText(null), "Keine Update-Quelle hat geantwortet.");
assert.ok(grundText({ quellen_versucht: [{ name: "github", ergebnis: "nichts_passendes" }] })
  .includes("github: keine passende Version"));

// Das Tooltip sagt auch, wann PBP erneut fragt — ein Weg weiter statt einer Sackgasse.
const titel = unbekanntTitel(daten);
assert.ok(titel.includes("weiß PBP gerade nicht"), titel);
assert.ok(titel.includes("in etwa 2 Minuten erneut"), titel);
assert.ok(unbekanntTitel({ wieder_fragen_nach_s: 60 }).includes("in etwa 1 Minute erneut"));
assert.ok(!unbekanntTitel({ quellen_versucht: [] }).includes("erneut"));

// #1144 Punkt 2: GitHub hat geantwortet, nennt aber keine Version der eigenen Linie (Beta-Installation) -
// das ist kein Netzfehler und darf nicht so klingen.
const ohneLinie = {
  stand: "unbekannt",
  grund: "keine_version_der_linie",
  linie: "1.8",
  wieder_fragen_nach_s: 3600,
  quellen_versucht: [
    { name: "elwosa", status: 404 },
    { name: "github", status: 200, ergebnis: "nichts_passendes" },
  ],
};
assert.equal(
  grundText(ohneLinie),
  "Die Update-Quelle hat geantwortet, nennt aber keine veröffentlichte Version der Linie 1.8.",
);
assert.ok(!grundText(ohneLinie).includes("Keine Update-Quelle hat geantwortet"));
assert.ok(unbekanntTitel(ohneLinie).includes("in etwa 60 Minuten erneut"), unbekanntTitel(ohneLinie));
assert.ok(grundText({ grund: "keine_version_der_linie" }).endsWith("Version der Linie."));
// Ohne diesen Grund bleibt es beim bisherigen Text, auch mit denselben Versuchen.
assert.equal(
  grundText({ ...ohneLinie, grund: "keine_antwort" }),
  "Keine Update-Quelle hat geantwortet (elwosa: Antwort 404, github: keine passende Version).",
);

// #1168: eine höhere Linie wird genannt — mit dem Weg dorthin, nie als Update.
const mit18 = { linie: "1.7", neue_linie: { version: "1.8.0", linie: "1.8", url: "https://example.com/v1.8.0" } };
const h = neueLinieHinweis(mit18);
assert.equal(h.titel, "Version 1.8 ist erschienen");
assert.equal(h.url, "https://example.com/v1.8.0");
assert.ok(h.text.includes("einmal von Hand"), h.text);
assert.ok(h.text.includes("Daten bleiben"), h.text);
assert.ok(h.text.includes("selbst installieren"), "eine 1.7-Installation erfährt, warum sich der Wechsel lohnt");
// Ohne Adresse: die Seite mit den Veröffentlichungen, nie ein toter Link.
assert.equal(neueLinieHinweis({ linie: "1.7", neue_linie: { version: "1.8.0", linie: "1.8" } }).url, VEROEFFENTLICHUNGEN_URL);
// Eine Installation, die selbst schon Updates installieren kann, bekommt den Satz dazu nicht.
assert.ok(!neueLinieHinweis({ linie: "1.8", neue_linie: { version: "2.0.0", linie: "2.0" } }).text.includes("selbst installieren"));
// Nichts gemeldet, nichts Brauchbares oder keine höhere Linie: kein Hinweis.
assert.equal(neueLinieHinweis({ linie: "1.7" }), null);
assert.equal(neueLinieHinweis(null), null);
assert.equal(neueLinieHinweis({ linie: "1.7", neue_linie: { version: "1.8.0" } }), null);
assert.equal(neueLinieHinweis({ linie: "1.8", neue_linie: { version: "1.8.0", linie: "1.8" } }), null);
assert.equal(neueLinieHinweis({ linie: "1.10", neue_linie: { version: "1.9.0", linie: "1.9" } }), null, "1.10 ist höher als 1.9");
assert.equal(neueLinieHinweis({ linie: "1.9", neue_linie: { version: "1.10.0", linie: "1.10" } }).titel, "Version 1.10 ist erschienen");

console.log("updateStand: ok");
