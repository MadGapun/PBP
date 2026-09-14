// #1047: Kipp-Test fuer den gegliederten Auszug. Framework-frei, laeuft
// mit dem blanken Node der CI-Runner:
//   node frontend/src/lib/textAuszug.test.mjs
//
// Der Kern: eine Detailansicht mit `whitespace-pre-wrap` bekommt ihre
// Absaetze und Listen — `textExcerpt` hatte sie zu einem Absatz gemacht.
import { gegliederterAuszug } from "./textAuszug.js";

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

check("Absaetze und Listen bleiben",
  gegliederterAuszug("Wir suchen.\n\nIhre Aufgaben:\n- Planen\n- Pruefen"),
  "Wir suchen.\n\nIhre Aufgaben:\n- Planen\n- Pruefen");
check("Leerraum in der Zeile wird zusammengefasst",
  gegliederterAuszug("Zeile   mit\t Abstand  \nzwei"),
  "Zeile mit Abstand\nzwei");
check("nie mehr als eine Leerzeile",
  gegliederterAuszug("eins\n\n\n\nzwei"),
  "eins\n\nzwei");
check("Windows-Zeilenenden",
  gegliederterAuszug("eins\r\nzwei"),
  "eins\nzwei");
check("kuerzt auf die Laenge",
  gegliederterAuszug("abcdef\nghij", 6),
  "abcdef...");
check("leer bleibt leer", gegliederterAuszug(null), "");

if (failed) {
  console.error(`\n${failed} Fall/Faelle rot`);
  process.exit(1);
}
console.log("\nalle Faelle gruen");
