// #989: Kipp-Test fuer die Datenguete-Regeln. Framework-frei, laeuft mit
// dem blanken Node der CI-Runner:
//   node src/lib/datenguete.test.mjs
//
// Die Faelle sind DIESELBEN wie in `tests/test_v1739_datenguete_989.py`.
// Weicht eine Seite ab, sortiert die Liste im Browser anders als die im
// Chat — genau die Divergenz, gegen die #987 angetreten ist, nur eine
// Etage hoeher. Dasselbe Muster wie `jobLink.js` (#765) und
// `dashboardRegeln.js` (#974).
import {
  MIN_BESCHREIBUNG,
  MITMISCHEN,
  NACHRANGIG,
  guetRang,
  hatBewertungsgrundlage,
  kurzmarke,
  sortierRang,
  vergleicheMitGuete,
} from "./datenguete.js";

let failed = 0;
function check(name, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (!ok) {
    failed++;
    console.error(`  FAIL  ${name}: erwartet ${JSON.stringify(expected)}, war ${JSON.stringify(actual)}`);
  } else {
    console.log(`  ok    ${name}`);
  }
}

console.log("Datenguete-Regeln (#989 C51)");

// --- Die Schwelle ist dieselbe wie in Python ---
check("Schwelle ist 50", MIN_BESCHREIBUNG, 50);

const OHNE = { title: "Ingenieur Elektrotechnik", description: "Ingenieur/in - Elektrotechnik", score: 101 };
const MIT = { title: "PLM Berater", description: "x".repeat(600), score: 32 };
const GRENZE_KNAPP_DRUNTER = { description: "x".repeat(49) };
const GRENZE_GENAU = { description: "x".repeat(50) };

check("kurzer Titeltext traegt keine Bewertung", hatBewertungsgrundlage(OHNE), false);
check("voller Text traegt eine Bewertung", hatBewertungsgrundlage(MIT), true);
check("49 Zeichen reichen nicht", hatBewertungsgrundlage(GRENZE_KNAPP_DRUNTER), false);
check("50 Zeichen reichen", hatBewertungsgrundlage(GRENZE_GENAU), true);
check("leeres Objekt faellt nicht um", hatBewertungsgrundlage({}), false);
check("null faellt nicht um", hatBewertungsgrundlage(null), false);

check("Rang ohne Grundlage", guetRang(OHNE), 1);
check("Rang mit Grundlage", guetRang(MIT), 0);

// --- Der gemeldete Fall, als Sortierung ---
// 101 Punkte ohne Text gegen 32 Punkte mit Text. Nach Score allein
// stuende der inhaltsleere Titel oben.
const nachScore = (a, b) => (b.score || 0) - (a.score || 0);
const liste = [OHNE, MIT];

const sortiert = [...liste].sort((a, b) => vergleicheMitGuete(a, b, nachScore));
check("beschriebene Stelle steht oben", sortiert[0].title, "PLM Berater");

const gemischt = [...liste].sort((a, b) => vergleicheMitGuete(a, b, nachScore, MITMISCHEN));
check("mit 'mitmischen' gewinnt wieder der Score", gemischt[0].title, "Ingenieur Elektrotechnik");

// --- Innerhalb einer Gruppe entscheidet weiter der Score ---
const zweiMitText = [
  { title: "niedrig", description: "y".repeat(300), score: 10 },
  { title: "hoch", description: "z".repeat(300), score: 40 },
];
const innen = [...zweiMitText].sort((a, b) => vergleicheMitGuete(a, b, nachScore));
check("innerhalb der Gruppe zaehlt der Score", innen[0].title, "hoch");

check("sortierRang folgt der Einstellung", sortierRang(OHNE, MITMISCHEN), 0);
check("sortierRang Vorgabe", sortierRang(OHNE, NACHRANGIG), 1);

// --- Marke an der Zeile ---
check("vollstaendige Stelle bekommt keine Marke", kurzmarke(MIT), null);
check("Servermarke wird uebernommen",
      kurzmarke({ description: "", datenguete: { text: "Ungeprüft: Entfernung" } }).text,
      "Ungeprüft: Entfernung");
check("Rueckfall ohne Servermarke", kurzmarke(OHNE).text, "Ungeprüft: Anzeigentext");

if (failed) {
  console.error(`\n${failed} Pruefung(en) fehlgeschlagen.`);
  process.exit(1);
}
console.log("\nAlle Datenguete-Regeln erfuellt.");
