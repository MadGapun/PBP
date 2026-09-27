import { nichtBelegt } from "./herkunft.js";

let fehler = 0;
function check(bedingung, was) {
  if (!bedingung) { fehler += 1; console.error("FEHLER:", was); }
}

check(nichtBelegt(null).length === 0, "ohne Stelle nichts");
check(nichtBelegt({}).length === 0, "ohne Herkunft nichts");

const job = {
  herkunft: {
    beschreibung: { guete: "belegt", methode: "anzeige", text: "" },
    entfernung: { guete: "geschaetzt", methode: "luftlinie", text: "12 km Luftlinie" },
    gehalt: { guete: "unbekannt", methode: "keine", text: "Die Anzeige nennt kein Gehalt." },
  },
};
const liste = nichtBelegt(job);
check(liste.length === 2, "nur nicht Belegtes");
check(liste[0].name === "Entfernung" && liste[0].wort === "geschätzt", "Alltagswort mit Umlaut");
check(liste[1].wort === "unbekannt", "unbekannt bleibt unbekannt");
check(!liste.some((e) => e.feld === "beschreibung"), "belegt erscheint nicht");
check(!JSON.stringify(liste).includes("luftlinie\""), "keine Methode als Anzeigewort");

if (fehler) process.exit(1);
console.log("herkunft: ok");
