// G62 (#1087 C2): eine Kernaussage und ein Grund je Karte.
import { kartenFakten, kartenGrund, kernaussage } from "./stellenKarte.js";

let fehler = 0;
function check(name, ist, soll) {
  const ok = JSON.stringify(ist) === JSON.stringify(soll);
  if (!ok) { fehler += 1; console.error(`FEHLER ${name}: ${JSON.stringify(ist)} != ${JSON.stringify(soll)}`); }
}

const text = "x".repeat(80);
const urteil = { description: text, pruefstand: { art: "beurteilt", text: "gelesen" }, analyse: { urteil: "BEDINGT" } };
check("Urteil ist Kernaussage", kernaussage(urteil).text, "Bedingt");
check("Urteil ist klickbar", kernaussage(urteil).urteil, true);
check("Urteil-Ton", kernaussage(urteil).ton, "amber");
const ueberholt = { ...urteil, pruefstand: { art: "beurteilt", ueberholt: true } };
check("ueberholt benannt", kernaussage(ueberholt).text, "Bedingt ⚠ überholt");
check("ueberholt als Grund", kartenGrund(ueberholt), "Das Urteil ist älter als Profil oder Anzeige");

const daumen = { description: text, fach_daumen: { richtung: "hoch", farbe: "belegt" } };
check("ohne Urteil der Daumen", kernaussage(daumen).text, "passt fachlich gut");
check("Daumen nicht klickbar", kernaussage(daumen).urteil, false);
check("angesehen im Titel", kernaussage({ ...daumen, pruefstand: { art: "gesichtet" } }).titel.includes("angesehen"), true);
check("ohne alles", kernaussage({}).text, "Fachlich noch nicht eingeordnet");

check("ohne Beschreibung zuerst", kartenGrund({ description: "", muss_tor: {} }), "Ohne Beschreibung — noch nicht bewertet");
check("mit Punkten unsicher", kartenGrund({ description: "", score: 3 }), "Beschreibung fehlt — Punkte unsicher");
check("Pflichtbegriff", kartenGrund({ description: text, muss_tor: { text: "x" } }), "Keiner deiner Pflichtbegriffe kommt vor");
check("ungepruefte Angaben", kartenGrund({ description: text }, { ungeprueft: ["entfernung", "gehalt", "beschreibung"] }), "Nicht angegeben: Entfernung, Gehalt");
check("nichts zu sagen", kartenGrund({ description: text }, { ungeprueft: [] }), "");

check("Fakten in einer Zeile", kartenFakten({ remote_level: "hybrid", befristet: 1 }, { entfernung: "12 km", form: "Festanstellung", umfang: "Vollzeit" }), "12 km · Hybrid · Festanstellung · Vollzeit · Befristet");
check("unbekannt faellt weg", kartenFakten({ remote_level: "unbekannt" }), "");

if (fehler) { console.error(`${fehler} Fehler`); process.exit(1); }
console.log("stellenKarte: alle Faelle gruen");
