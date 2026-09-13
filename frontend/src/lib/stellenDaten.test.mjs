// #1032: Fund- und Veroeffentlichungsdatum auf Karte und Dialog. Framework-frei:
//   node src/lib/stellenDaten.test.mjs
import { alsDatum, stellenDaten } from "./stellenDaten.js";

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

// Der Fall aus dem Issue: veroeffentlicht am 01.09., gefunden am 08.09.
const beide = stellenDaten({
  found_at: "2026-09-08T15:29:00",
  veroeffentlicht_am: "2026-09-01",
});
check("beide Daten in einer Zeile", beide.text,
  "Gefunden: 08.09.2026, 15:29 · Veröffentlicht: 01.09.2026");

const nurFund = stellenDaten({ found_at: "2026-09-08T15:29:00" });
check("ohne Veroeffentlichung entfaellt der Teil", nurFund.text,
  "Gefunden: 08.09.2026, 15:29");
check("kein Ersatzdatum", nurFund.veroeffentlicht, "");

const leererString = stellenDaten({ found_at: "2026-09-08T15:29:00", veroeffentlicht_am: "  " });
check("leerer String zaehlt als fehlend", leererString.text, "Gefunden: 08.09.2026, 15:29");

check("gar kein Datum ergibt keinen Text", stellenDaten({}).text, "");
check("kein 'Keine Angabe'", stellenDaten({ found_at: null }).text.includes("Keine"), false);
check("unlesbares Datum ergibt keinen Text", stellenDaten({ veroeffentlicht_am: "demnaechst" }).text, "");

// Ein reines Datum ist ein ORTSDATUM — in jeder Zeitzone derselbe Tag.
const tag = alsDatum("2026-09-01");
check("reines Datum: Tag", tag.getDate(), 1);
check("reines Datum: Monat", tag.getMonth(), 8);
check("reines Datum: Mitternacht Ortszeit", tag.getHours(), 0);

if (failed) {
  console.error(`\n${failed} Pruefung(en) fehlgeschlagen`);
  process.exit(1);
}
console.log("\nalle Pruefungen bestanden");
