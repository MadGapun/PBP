// #1035: Score-Anzeige mit hoechstens einer Nachkommastelle. Framework-frei:
//   node src/lib/score.test.mjs
import { faktorSumme, punkteText, punkteWert, scoreText, scoreWert } from "./score.js";

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

// C96 (#1087): ein Wert, ein Name, eine Skala.
check("punkte vor fach_score vor score", punkteWert({ punkte: 5, fach_score: 6, score: 7 }), 5);
check("fach_score, wenn punkte fehlt", punkteWert({ fach_score: 6, score: 7 }), 6);
check("mit Skala", punkteText({ punkte: 7, punkte_max: 26 }), "7 von 26 Punkten");
check("ohne Skala", punkteText({ punkte: 7 }), "7 Punkte");
check("ueber der Skala keine Skala", punkteText({ punkte: 30, punkte_max: 26 }), "30 Punkte");
check("negativ ohne Skala", punkteText({ punkte: -2, punkte_max: 26 }), "-2 Punkte");
check("Einzahl", punkteText({ punkte: 1 }), "1 Punkt");
check("Faktoren addieren", faktorSumme({ a: 6, b: -1.5, c: 0.5 }), 5);

if (failed) {
  console.error(`${failed} Fehler`);
  process.exit(1);
}
console.log("alle ok");
