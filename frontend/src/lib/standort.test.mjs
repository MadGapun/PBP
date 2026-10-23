// #1235: der Satz zum Standort nennt einen mehrdeutigen Wohnort, statt ihn als "nicht aufgelöst" abzutun.
import { standortSatz } from "./standort.js";

let fehler = 0;
function check(name, ist, soll) {
  if (ist !== soll) { fehler += 1; console.error(`FEHLER ${name}: ${ist} != ${soll}`); }
}
function enthaelt(name, text, teil) {
  if (!text.includes(teil)) { fehler += 1; console.error(`FEHLER ${name}: "${text}" enthaelt nicht "${teil}"`); }
}

check("ohne Befund", standortSatz(null), "");
enthaelt("kein Standort", standortSatz({ ort: "", profil_wohnort: "", aufgeloest: false }), "Kein Standort");

const nichtGefunden = standortSatz({ ort: "Nirgendwo", aufgeloest: false });
enthaelt("nicht aufgeloest", nichtGefunden, "noch nicht aufgelöst");
check("nicht aufgeloest sagt nichts von mehrfach", nichtGefunden.includes("mehrfach"), false);

const mehrfach = standortSatz({
  ort: "", profil_wohnort: "Rosengarten", aufgeloest: false,
  mehrdeutig: ["Rosengarten, Landkreis Harburg, Niedersachsen", "Rosengarten, Landkreis Schwäbisch Hall, Baden-Württemberg"],
});
enthaelt("mehrdeutig nennt den Grund", mehrfach, "gibt es mehrfach");
enthaelt("mehrdeutig nennt den ersten Ort", mehrfach, "Landkreis Harburg");
enthaelt("mehrdeutig nennt den zweiten Ort", mehrfach, "Schwäbisch Hall");
enthaelt("mehrdeutig nennt den Ausweg", mehrfach, "Ergänze die PLZ, etwa „12345 Rosengarten“");
check("mehrdeutig ist nicht der Satz fuer 'nicht aufgeloest'", mehrfach.includes("noch nicht aufgelöst"), false);

const leereListe = standortSatz({ ort: "Rosengarten", aufgeloest: false, mehrdeutig: [] });
enthaelt("leere Liste: wie nicht aufgeloest", leereListe, "noch nicht aufgelöst");

check("aufgeloest, eigener Ort", standortSatz({ ort: "Bremen", aufgeloest: true, quelle: "eigene" }),
  "Entfernungen werden ab „Bremen“ gerechnet (von dir gesetzt).");
check("aufgeloest, Wohnort", standortSatz({ ort: "20095 Hamburg", aufgeloest: true, quelle: "profil" }),
  "Entfernungen werden ab deinem Wohnort „20095 Hamburg“ gerechnet (aus dem Profil).");
// Ein aufgeloester Ort braucht kein "mehrdeutig" - es kommt dann auch nicht vom Server, aber die Reihenfolge zaehlt.
check("aufgeloest schlaegt mehrdeutig", standortSatz({ ort: "X", aufgeloest: true, quelle: "profil", mehrdeutig: ["a", "b"] }).includes("mehrfach"), false);

if (fehler) { console.error(`${fehler} Fehler`); process.exit(1); }
console.log("standort: alle Faelle gruen");
