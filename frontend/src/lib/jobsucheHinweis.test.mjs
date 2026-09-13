// #1033: Regeln fuer den Jobsuche-Hinweis in der Navigation. Framework-frei:
//   node src/lib/jobsucheHinweis.test.mjs
import { jobsucheHinweis } from "./jobsucheHinweis.js";

let failed = 0;
function check(name, actual, expected) {
  const ok = actual === expected;
  if (!ok) {
    failed++;
    console.error(`  FAIL  ${name}: erwartet ${JSON.stringify(expected)}, war ${JSON.stringify(actual)}`);
  } else {
    console.log(`  ok    ${name}`);
  }
}

// Der gemeldete Fall: 105 gefunden, 88 aktiv, eine Quelle im Timeout.
const bericht = jobsucheHinweis({
  vorhanden: true, ergebnis: "fertig", neue_stellen: 105, neu_aktiv: 88,
  quellen: { ok: 12, timeout: 1, fehler: 0, uebersprungen: 2 },
});
check("Anzahl steht im Text", bericht.text, "Fertig — 105 neue Stellen");
check("ein Timeout faerbt nicht als Warnung", bericht.ton, "ok");
check("Tooltip nennt aktiv und ausgeblendet",
  bericht.titel.includes("88 davon in der Liste, 17 sofort ausgeblendet"), true);
check("Tooltip nennt den Timeout", bericht.titel.includes("1 im Timeout"), true);

const eine = jobsucheHinweis({ vorhanden: true, ergebnis: "fertig", neue_stellen: 1, neu_aktiv: 1 });
check("Einzahl", eine.text, "Fertig — 1 neue Stelle");

const leer = jobsucheHinweis({ vorhanden: true, ergebnis: "fertig", neue_stellen: 0, neu_aktiv: 0 });
check("ohne Funde: benannt", leer.text, "Fertig — keine neuen Stellen");

const fehler = jobsucheHinweis({
  vorhanden: true, ergebnis: "fehlgeschlagen", neue_stellen: null, meldung: "Verbindung weg",
});
check("fehlgeschlagen ist keine Null", fehler.text, "Jobsuche fehlgeschlagen");
check("fehlgeschlagen hat eigenen Ton", fehler.ton, "fehler");
check("fehlgeschlagen nennt die Meldung", fehler.titel, "Verbindung weg");

const ohne = jobsucheHinweis({ vorhanden: true, ergebnis: "nicht_gestartet", neue_stellen: null });
check("nicht gestartet wird benannt", ohne.text, "Jobsuche nicht gestartet");

const unbekannt = jobsucheHinweis({ vorhanden: true, ergebnis: "fertig", neue_stellen: null });
check("unbekannte Zahl ist nicht 0", unbekannt.text.includes("0"), false);

check("kein Lauf -> nichts", jobsucheHinweis({ vorhanden: false }), null);

if (failed) {
  console.error(`\n${failed} Fall/Faelle fehlgeschlagen`);
  process.exit(1);
}
console.log("\nalle Faelle ok");
