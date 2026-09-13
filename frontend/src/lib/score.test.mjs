// #1035: Score-Anzeige mit hoechstens einer Nachkommastelle. Framework-frei:
//   node src/lib/score.test.mjs
import { scoreText, scoreWert } from "./score.js";

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

// Der Fall aus dem Issue.
check("Meldefall als Zahl", scoreWert(6.199999999999999), 6.2);
check("Meldefall als Text", scoreText(6.199999999999999), "6,2");
check("ganze Zahl ohne Nachkomma", scoreText(18), "18");
check("Zehntel bleiben", scoreText(18.7), "18,7");
check("aus dem Server als Zeichenkette", scoreText("11.25"), "11,3");
check("fehlender Wert ist 0", scoreText(undefined), "0");
check("null ist 0", scoreText(null), "0");
check("Unsinn ist 0", scoreWert("kaputt"), 0);
check("Eingabefeld bekommt die gerundete Zahl", String(scoreWert(9.199999999999999)), "9.2");

if (failed) {
  console.error(`${failed} Fehler`);
  process.exit(1);
}
console.log("alle ok");
