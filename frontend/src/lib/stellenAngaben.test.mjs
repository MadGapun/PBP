// #1044: Karte und Popup zeigen eine Stelle gleich. Framework-frei:
//   node src/lib/stellenAngaben.test.mjs
import { readFileSync } from "node:fs";
import {
  ANSTELLUNGSFORM_TEXT, ANSTELLUNGSFORM_TON, ANSTELLUNGSFORM_TON_UNBEKANNT, KARTE_TON,
  anstellungsform, anstellungsformMarke, entfernungText, firmaText, gehaltText, stelleSpeichernNutzlast, umfangText,
} from "./stellenAngaben.js";
import { FLAECHEN, MINDEST_KONTRAST, kontrast } from "./kontrast.js";

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

// #1299: ein Merkmal geht nur mit, wenn es geaendert wurde.
const stelle = { title: "Projekt", employment_type: "festanstellung", remote_level: "True", arbeitsumfang: null };
check("unveraenderte Merkmale bleiben weg",
  stelleSpeichernNutzlast(stelle, { title: "Projekt", employment_type: "festanstellung", arbeitsumfang: "unbekannt" }),
  { title: "Projekt" });
check("geaenderte Anstellungsform geht mit",
  stelleSpeichernNutzlast(stelle, { title: "Projekt", employment_type: "freelance" }),
  { title: "Projekt", employment_type: "freelance" });
check("Remote aus ungueltigem Altwert geht mit",
  stelleSpeichernNutzlast(stelle, { remote_level: "remote" }),
  { remote_level: "remote" });
check("leere Auswahl geht nicht mit",
  stelleSpeichernNutzlast(stelle, { remote_level: "" }),
  {});

// #1301: EINE Farbtabelle fuer die Anstellungsform.
const formen = Object.keys(ANSTELLUNGSFORM_TEXT);
check("jede Form hat einen Ton", formen.filter((f) => !ANSTELLUNGSFORM_TON[f]), []);
check("keine Farbe ohne Form", Object.keys(ANSTELLUNGSFORM_TON).filter((f) => !formen.includes(f)), []);
const toene = Object.values(ANSTELLUNGSFORM_TON);
check("jede Form hat ihre eigene Farbe", new Set(toene).size, toene.length);
check("Vorgabe #111: Festanstellung blau, Freelance gruen",
  [ANSTELLUNGSFORM_TON.festanstellung, ANSTELLUNGSFORM_TON.freelance], ["sky", "success"]);
check("keine Form in Amber (Angepinnt) oder Rot (Warnung)",
  toene.filter((t) => t === "amber" || t === "danger" || t === ANSTELLUNGSFORM_TON_UNBEKANNT), []);
check("jeder Ton hat einen Kartenrand", toene.filter((t) => !KARTE_TON[t]), []);
check("Festanstellung ist auf der Karte markiert", Boolean(anstellungsformMarke("festanstellung").karte), true);
check("Freelance und Zeitarbeit unterscheiden sich",
  anstellungsformMarke("freelance").ton !== anstellungsformMarke("zeitarbeit").ton, true);
check("unbekannt ist grau, mit Namen und ohne Kartenfarbe",
  (({ text, ton, karte }) => ({ text, ton, karte }))(anstellungsformMarke("")),
  { text: "Form unbekannt", ton: "neutral", karte: "" });
check("unbekannt sieht nicht aus wie Festanstellung",
  anstellungsformMarke(null).ton !== anstellungsformMarke("festanstellung").ton, true);
check("fremder Rohwert bleibt lesbar und grau",
  (({ text, ton }) => ({ text, ton }))(anstellungsformMarke("arbeitnehmerueberlassung")),
  { text: "arbeitnehmerueberlassung", ton: "neutral" });
check("die Marke erklaert die Farbe", anstellungsformMarke("praktikum").titel.includes("Farbe"), true);
check("Abzeichen und Marke sagen dasselbe",
  formen.every((f) => anstellungsform({ employment_type: f }).ton === anstellungsformMarke(f).ton), true);

// Kontrast der neuen Farben in beiden Modi (WCAG, Lesetext >= 4,5:1).
const css = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
const hellAb = css.indexOf('[data-theme="light"]');
const wert = (teil, name) => (teil.match(new RegExp(`--color-${name}: ([0-9 ]+);`)) || [])[1];
const zuSchwach = [];
for (const ton of new Set(toene)) {
  const name = ton === "success" ? "teal" : ton;
  for (const [modus, teil] of [["dunkel", css.slice(0, hellAb)], ["hell", css.slice(hellAb)]]) {
    const farbe = wert(teil, name);
    if (!farbe) { zuSchwach.push(`${modus}: --color-${name} fehlt`); continue; }
    for (const f of FLAECHEN) {
      const k = kontrast(farbe, wert(teil, f));
      if (k < MINDEST_KONTRAST) zuSchwach.push(`${modus}: ${name} auf ${f} = ${k.toFixed(2)}`);
    }
  }
}
check("Kontrast der Anstellungsform-Farben", zuSchwach, []);

if (failed) {
  console.error(`${failed} Fehler`);
  process.exit(1);
}
console.log("alle ok");
