// G64 (#1087 D1): hoechstens fuenf Zeilen, die Reihenfolge der Gruppen zaehlt.
import { alleAufgabenText, vorschau } from "./arbeitsliste.js";

let fehler = 0;
function check(name, ist, soll) {
  if (JSON.stringify(ist) !== JSON.stringify(soll)) { fehler += 1; console.error(`FEHLER ${name}: ${JSON.stringify(ist)} != ${JSON.stringify(soll)}`); }
}
const g = { ueberfaellig: [1, 2, 3], heute: [4, 5, 6], diese_woche: [7] };
const v = vorschau(g, ["ueberfaellig", "heute", "diese_woche"]);
check("fuenf Zeilen", v.gezeigt, 5);
check("ueberfaellige zuerst", v.gruppen.ueberfaellig, [1, 2, 3]);
check("Rest aus heute", v.gruppen.heute, [4, 5]);
check("Woche faellt weg", v.gruppen.diese_woche, undefined);
check("weitere", v.weitere, 2);
check("wenige", vorschau({ a: [1] }, ["a"]).weitere, 0);
check("Knopf ohne Rest", alleAufgabenText(0), "Alle Aufgaben");
check("Knopf mit Rest", alleAufgabenText(2), "Alle Aufgaben (2 weitere)");
if (fehler) { console.error(`${fehler} Fehler`); process.exit(1); }
console.log("arbeitsliste: alle Faelle gruen");
