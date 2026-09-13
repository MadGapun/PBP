// #1044: Karte und Popup zeigen eine Stelle gleich. Framework-frei:
//   node src/lib/stellenAngaben.test.mjs
import {
  anstellungsform, entfernungText, firmaText, gehaltText, umfangText,
} from "./stellenAngaben.js";

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

const euro = (wert) => `${wert} EUR`;

// Die Faelle aus dem Issue.
check("Firma fehlt: benannter Platzhalter", firmaText({ company: "" }), "Unbekannte Firma");
check("Firma nur Leerzeichen", firmaText({ company: "   " }), "Unbekannte Firma");
check("Firma vorhanden", firmaText({ company: "Musterfirma GmbH" }), "Musterfirma GmbH");
check("Anstellungsform mit Text und Ton", anstellungsform({ employment_type: "festanstellung" }),
  { text: "Festanstellung", ton: "sky" });
check("unbekannte Form bleibt lesbar", anstellungsform({ employment_type: "arbeitnehmerueberlassung" }),
  { text: "arbeitnehmerueberlassung", ton: "neutral" });
check("keine Form, kein Abzeichen", anstellungsform({}), null);
check("Umfang Vollzeit", umfangText({ arbeitsumfang: "vollzeit" }), "Vollzeit");
check("Umfang beides", umfangText({ arbeitsumfang: "beides" }), "Voll- oder Teilzeit");
check("Umfang unbekannt: kein Etikett", umfangText({ arbeitsumfang: "unbekannt" }), null);
check("Gehalt mit bis und Umlaut",
  gehaltText({ salary_min: 50000, salary_max: 60000, salary_estimated: 1, salary_type: "jaehrlich" }, euro),
  "Gehalt: 50000 EUR bis 60000 EUR (geschätzt)");
check("Gehalt ohne Obergrenze", gehaltText({ salary_min: 50000 }, euro), "Gehalt: 50000 EUR");
check("kein Gehalt, keine Zeile", gehaltText({ salary_max: 60000 }, euro), null);
check("der Rohwert der Gehaltsart steht nirgends",
  (gehaltText({ salary_min: 1, salary_type: "jaehrlich" }, euro) || "").includes("jaehrlich"), false);
check("Entfernung vom Server", entfernungText({ entfernung: { entfernung_text: "8 km Luftlinie" } }),
  "8 km Luftlinie");
check("keine Entfernung, keine Zeile", entfernungText({}), null);

if (failed) {
  console.error(`${failed} Fehler`);
  process.exit(1);
}
console.log("alle ok");
