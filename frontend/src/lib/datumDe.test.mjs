// #1412 D8
import { deZuIso, isoZuDe } from "./datumDe.js";

let fehler = 0;
function check(name, ist, soll) {
  if (ist !== soll) { fehler += 1; console.error(`FEHLER ${name}: ${ist} != ${soll}`); }
}
const heute = new Date(2026, 10, 19);
check("voll", deZuIso("01.12.2026", heute), "2026-12-01");
check("einstellig", deZuIso("1.2.2027", heute), "2027-02-01");
check("zweistelliges Jahr", deZuIso("01.12.27", heute), "2027-12-01");
check("ohne Jahr: dieses Jahr", deZuIso("24.12.", heute), "2026-12-24");
check("Schalttag gueltig", deZuIso("29.02.2028", heute), "2028-02-29");
check("Schalttag ungueltig", deZuIso("29.02.2027", heute), null);
check("Monat 13", deZuIso("01.13.2026", heute), null);
check("US-Schreibweise wird nicht geraten", deZuIso("12/01/2026", heute), null);
check("ISO-Eingabe wird nicht geraten", deZuIso("2026-12-01", heute), null);
check("leer", deZuIso("", heute), null);
check("anzeigen", isoZuDe("2026-12-01"), "01.12.2026");
check("anzeigen mit Zeit", isoZuDe("2026-12-01T10:00:00"), "01.12.2026");
check("anzeigen leer", isoZuDe(""), "");
if (fehler) process.exit(1);
console.log("datumDe: ok");
