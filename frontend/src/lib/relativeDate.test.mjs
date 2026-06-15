// #701: Kipp-Test fuer die relative Datumsberechnung. Framework-frei, laeuft
// mit dem blanken Node der CI-Runner (kein vitest/jest noetig):
//   node src/lib/relativeDate.test.mjs
//
// Der Kern-Beweis: die Labels muessen auch dann stimmen, wenn der ausfuehrende
// Rechner NICHT auf Europe/Berlin steht (CI laeuft typischerweise in UTC) und
// wenn ein Termin nahe der UTC-Mitternachtsgrenze liegt.
import { berlinDayDiff, relativeDayLabel, berlinTimeOfDay, relativeDayLabelWithTime } from "./relativeDate.js";

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

console.log(`relativeDate-Kipp-Test (Host-TZ: ${Intl.DateTimeFormat().resolvedOptions().timeZone})`);

// --- Kernfall: UTC-Mitternachts-Kipp (Sommerzeit, Berlin = UTC+2) ---
// ref  = 2026-06-14T23:30:00Z  -> 2026-06-15 01:30 Berlin (Kalendertag 15.)
// targ = 2026-06-16T08:00:00Z  -> 2026-06-16 10:00 Berlin (Kalendertag 16.)
// Korrekt in Berlin: 1 Tag ("morgen"). Eine naive UTC-Rechnung saehe 14. vs 16.
// und wuerde faelschlich 2 ("uebermorgen") liefern.
const refSommer = new Date("2026-06-14T23:30:00Z");
check("sommer kipp -> morgen", berlinDayDiff(new Date("2026-06-16T08:00:00Z"), refSommer), 1);
check("sommer kipp label", relativeDayLabel(new Date("2026-06-16T08:00:00Z"), refSommer), "morgen");

// --- Winterzeit (Berlin = UTC+1), gleiche Mechanik ---
// ref  = 2026-01-10T23:30:00Z -> 2026-01-11 00:30 Berlin (11.)
// targ = 2026-01-12T08:00:00Z -> 2026-01-12 09:00 Berlin (12.)  -> "morgen"
const refWinter = new Date("2026-01-10T23:30:00Z");
check("winter kipp -> morgen", berlinDayDiff(new Date("2026-01-12T08:00:00Z"), refWinter), 1);

// --- Uhrzeit-Unabhaengigkeit: gleicher Kalendertag, egal wie spaet ---
const refTag = new Date("2026-06-15T12:00:00+02:00");
check("frueh am selben Tag = heute", berlinDayDiff(new Date("2026-06-15T05:00:00+02:00"), refTag), 0);
check("spaet am selben Tag = heute", berlinDayDiff(new Date("2026-06-15T22:00:00+02:00"), refTag), 0);

// --- 47h sind uebermorgen, nicht morgen ---
// ref 15. 12:00 Berlin, targ 17. 11:00 Berlin -> 2 Tage
check("47h -> uebermorgen (2)", berlinDayDiff(new Date("2026-06-17T11:00:00+02:00"), refTag), 2);
check("uebermorgen label", relativeDayLabel(new Date("2026-06-17T11:00:00+02:00"), refTag), "in 2 Tagen");

// --- gestern / vergangen ---
check("gestern", berlinDayDiff(new Date("2026-06-14T20:00:00+02:00"), refTag), -1);
check("gestern label", relativeDayLabel(new Date("2026-06-14T20:00:00+02:00"), refTag), "gestern");

// --- #701: Uhrzeit in Europe/Berlin (zeitzonen-robust) ---
// 12:00 UTC = 14:00 Berlin (Sommer, UTC+2)
check("berlinTimeOfDay sommer", berlinTimeOfDay(new Date("2026-06-15T12:00:00Z")), "14:00");
// 12:00 UTC = 13:00 Berlin (Winter, UTC+1)
check("berlinTimeOfDay winter", berlinTimeOfDay(new Date("2026-01-15T12:00:00Z")), "13:00");

// --- #701: relatives Label mit Uhrzeit ---
const refLabel = new Date("2026-06-15T12:00:00+02:00");
check("label mit Uhrzeit morgen",
  relativeDayLabelWithTime(new Date("2026-06-16T14:00:00+02:00"), refLabel),
  "morgen, 14:00 Uhr");
check("label mit Uhrzeit in 2 Tagen",
  relativeDayLabelWithTime(new Date("2026-06-17T09:30:00+02:00"), refLabel),
  "in 2 Tagen, 09:30 Uhr");

if (failed > 0) {
  console.error(`\n${failed} Test(s) fehlgeschlagen.`);
  process.exit(1);
}
console.log("\nAlle relativeDate-Kipp-Tests gruen.");
