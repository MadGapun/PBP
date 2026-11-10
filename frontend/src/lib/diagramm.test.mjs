// #1345 (G117): Farben, Phasen, Zahlen und Rangliste der Statistik-Seite.
// Framework-frei:  node src/lib/diagramm.test.mjs
import { FARBEN, PHASEN, farben, phaseVon, phasenImVerlauf, phasenSumme, prozent, rangliste, zahl } from "./diagramm.js";

let failed = 0;
function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    failed++;
    console.error(`  FAIL  ${name}: erwartet ${e}, war ${a}`);
  } else {
    console.log(`  ok    ${name}`);
  }
}

// Zahlen in deutscher Schreibweise.
check("Prozent mit Komma", prozent(12.5), "12,5 %");
check("Prozent ganze Zahl", prozent(40), "40 %");
check("Prozent null ist ein Wert", prozent(0), "0 %");
check("Prozent ohne Wert ist ein Strich", prozent(null), "–");
check("Prozent kaputt ist ein Strich", prozent("abc"), "–");
check("Tausender mit Punkt", zahl(12345), "12.345");
check("eine Nachkommastelle", zahl(6.199999999999999), "6,2");
check("Zahl ohne Wert", zahl(undefined), "–");

// Jeder bekannte Status hat eine Phase; Unbekanntes faellt nicht in eine bekannte.
const BEKANNT = [
  "in_vorbereitung", "beworben", "eingangsbestaetigung", "interview", "zweitgespraech",
  "interview_abgeschlossen", "angebot", "angenommen", "abgelehnt", "zurueckgezogen",
  "abgelaufen", "arbeitgeber_ausgefallen",
];
check("kein bekannter Status in Sonstige", BEKANNT.filter((s) => phaseVon(s) === "sonstige"), []);
check("unbekannter Status", phaseVon("gibt_es_nicht"), "sonstige");
check("leerer Status", phaseVon(undefined), "sonstige");
check("Zweitgespräch zählt als Gespräch", phaseVon("zweitgespraech"), "gespraech");

check(
  "Summe je Phase",
  phasenSumme({ beworben: 3, eingangsbestaetigung: 2, interview: 1, abgelehnt: 0, neu_erfunden: 4 }),
  { beworben: 5, gespraech: 1, sonstige: 4 },
);
check("Summe ohne Daten", phasenSumme(null), {});
check(
  "Phasen im Verlauf in fester Reihenfolge",
  phasenImVerlauf([{ abgelehnt: 1 }, { beworben: 2 }, { in_vorbereitung: 1 }]).map((p) => p.key),
  ["vorbereitung", "beworben", "absage"],
);

// Jede Phase hat in beiden Farbschemata eine Farbe, und keine zwei teilen eine.
for (const schema of ["light", "dark"]) {
  const f = FARBEN[schema].phasen;
  check(`${schema}: Farbe je Phase`, PHASEN.filter((p) => !/^#[0-9a-f]{6}$/.test(f[p.key] || "")).map((p) => p.key), []);
  check(`${schema}: Farben verschieden`, new Set(PHASEN.map((p) => f[p.key])).size, PHASEN.length);
}
check("unbekanntes Schema ist dunkel", farben("irgendwas"), FARBEN.dark);
check("helles Schema", farben("light"), FARBEN.light);

// Rangliste: absteigend, Rest gefaltet, Anteile ergeben 100.
const zehn = Array.from({ length: 10 }, (_, i) => ({ name: `Q${i}`, wert: i + 1 }));
const liste = rangliste(zehn, { max: 4 });
check("Rangliste Namen", liste.map((e) => e.name), ["Q9", "Q8", "Q7", "Sonstige"]);
check("Rangliste Rest", [liste[3].wert, liste[3].gefaltet], [28, 7]);
check("Anteile ergeben 100", Math.round(liste.reduce((s, e) => s + e.anteil, 0)), 100);
check("längster Balken ist 100", Math.max(...liste.map((e) => e.breite)), 100);
check("Nullwerte fallen weg", rangliste([{ name: "a", wert: 0 }, { name: "b", wert: 2 }]).map((e) => e.name), ["b"]);
check("gleiche Werte behalten die Reihenfolge", rangliste([{ name: "x", wert: 2 }, { name: "y", wert: 2 }]).map((e) => e.name), ["x", "y"]);
check("genau max Zeilen: nichts gefaltet", rangliste(zehn.slice(0, 4), { max: 4 }).some((e) => e.gefaltet), false);
check("leere Liste", rangliste(null), []);
check("weitere Felder bleiben", rangliste([{ name: "a", wert: 1, ziel: "stellen" }])[0].ziel, "stellen");

if (failed) {
  console.error(`${failed} Fehler`);
  process.exit(1);
}
console.log("alle ok");
