// G65 (#1087 D2): Anzeigenamen statt Rohwerte.
import { bewerbungsartText, datumText, grundText, klartext, quelleText } from "./anzeige.js";

let fehler = 0;
function check(name, ist, soll) {
  if (ist !== soll) { fehler += 1; console.error(`FEHLER ${name}: ${ist} != ${soll}`); }
}
check("Standardgrund", grundText("zu_junior"), "Zu junior");
check("zweites Wort gross", grundText("falsche_branche"), "Falsche Branche");
check("gespeichert klein mit Leerzeichen", grundText("falsches system"), "Falsches System");
check("eigener Grund aus Katalog", grundText("mag ich nicht", [{ label: "Mag ich NICHT" }]), "Mag ich NICHT");
check("unbekannt lesbar", grundText("mag_ich_nicht"), "Mag ich nicht");
check("Bewerbungsart", bewerbungsartText("mit_dokumenten"), "mit Unterlagen");
check("Quelle mit Label", quelleText({ name: "jobspy_indeed", label: "Indeed.de (via JobSpy)" }), "Indeed.de (via JobSpy)");
check("Quelle aus der Registry", quelleText({ name: "stellenanzeigen_de" }), "Stellenanzeigen.de");
check("Quelle unbekannt lesbar", quelleText("neue_boerse"), "neue boerse");
check("Quelle manuell", quelleText("manuell"), "Von Hand");
check("Datum", datumText("2026-09-04T10:00:00"), "04.09.2026");
check("Klartext", klartext("hinfaellig"), "hinfällig");
if (fehler) { console.error(`${fehler} Fehler`); process.exit(1); }
console.log("anzeige: alle Faelle gruen");
