// #1050: Regeln fuer den Detailbewertungs-Prompt. Framework-frei:
//   node src/lib/detailbewertung.test.mjs
import { URTEILE, detailbewertungKnopf, detailbewertungPrompt } from "./detailbewertung.js";

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

const stelle = { hash: "abc123", title: "Sachbearbeitung Datenpflege", company: "Musterfirma Nord" };
const text = detailbewertungPrompt(stelle);

// AK 1: Hash und Titel eingesetzt.
check("Hash steht im Prompt", text.includes("abc123"), true);
check("Titel steht im Prompt", text.includes('"Sachbearbeitung Datenpflege"'), true);
check("Firma steht im Prompt", text.includes("bei Musterfirma Nord"), true);

// AK 2: ausdruecklich speichern, nicht nur antworten.
check("Speicherweg genannt", text.includes('stelle_analyse_speichern(job_hash="abc123"'), true);
check("nicht nur im Chat", text.includes("Antworte nicht nur im Chat"), true);
for (const urteil of URTEILE) {
  check(`Urteil ${urteil} genannt`, text.includes(urteil), true);
}
check("ohne Befund kein Neubewerten", text.includes("bereits ein Befund"), false);

// AK 3: vorhandener Befund.
const bewertet = { ...stelle, analyse: { urteil: "BEDINGT", am: "2026-09-15T12:43:00" } };
const neu = detailbewertungPrompt(bewertet);
check("vorhandener Befund benannt", neu.includes("bereits ein Befund vor (BEDINGT, vom 2026-09-15)"), true);
check("Knopf ohne Befund", detailbewertungKnopf(stelle).text, "Detailbewertung");
check("Knopf mit Befund", detailbewertungKnopf(bewertet).text, "Neu bewerten");
check("Knopf nennt den Befund", detailbewertungKnopf(bewertet).befund, "BEDINGT");

// Ohne Firma kein "bei".
check("ohne Firma kein leeres bei", detailbewertungPrompt({ hash: "x", title: "T" }).includes(" bei "), false);

if (failed) {
  console.error(`\n${failed} Fall/Faelle fehlgeschlagen`);
  process.exit(1);
}
console.log("\nalle Faelle ok");
