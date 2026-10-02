// node frontend/src/lib/updateStand.test.mjs — #1134
import assert from "node:assert/strict";
import {
  FRAGE_MAX_MS,
  FRAGE_MIN_MS,
  FRAGE_OHNE_ANTWORT_MS,
  grundText,
  naechsteFrageMs,
  unbekanntTitel,
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

console.log("updateStand: ok");
