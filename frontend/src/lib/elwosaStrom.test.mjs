// #1256 (F58): was im Elwosa-Strom NEU ist. Kein Framework, kein Server.
import { hoechsteKennung, neueNachrichten } from "./elwosaStrom.js";

let fehler = 0;
function check(name, ist, soll) {
  const a = JSON.stringify(ist);
  const b = JSON.stringify(soll);
  if (a !== b) { fehler += 1; console.error(`FEHLER ${name}: ${a} != ${b}`); }
}

const liste = (...ids) => ids.map((id) => ({ id, content: `Nachricht ${id}` }));

// ── die groesste Kennung ──
check("groesste Kennung", hoechsteKennung(liste(3, 9, 5)), 9);
check("leere Liste", hoechsteKennung([]), 0);
check("keine Liste", hoechsteKennung(null), 0);
check("Eintraege ohne gueltige Kennung zaehlen nicht", hoechsteKennung([{ id: "x" }, { id: null }, {}, null, { id: -4 }, { id: 7 }]), 7);
check("eine Kennung als Text", hoechsteKennung([{ id: "12" }, { id: 4 }]), 12);

// ── das erste Laden ist nichts Neues ──
check("erstes Laden: nichts neu", neueNachrichten(null, liste(1, 2, 3)), { anzahl: 0, hoechste: 3 });
check("erstes Laden ohne Nachrichten", neueNachrichten(null, []), { anzahl: 0, hoechste: 0 });
check("noch nichts gesehen (undefined)", neueNachrichten(undefined, liste(5)), { anzahl: 0, hoechste: 5 });
// danach ist die Liste nie mehr "unbekannt": auch nach einem leeren ersten Laden zaehlt die naechste Nachricht
check("nach leerem Laden zaehlt die erste Nachricht", neueNachrichten(0, liste(1)), { anzahl: 1, hoechste: 1 });

// ── der Normalfall: die Liste ist voll, eine neue schiebt die aelteste hinaus ──
const voll = liste(4, 5, 6, 7, 8, 9, 10, 11, 12, 13);
check("volle Liste, nichts neu", neueNachrichten(13, voll), { anzahl: 0, hoechste: 13 });
check("volle Liste, eine neue (die Zahl bleibt zehn)", neueNachrichten(13, liste(5, 6, 7, 8, 9, 10, 11, 12, 13, 14)), { anzahl: 1, hoechste: 14 });
check("volle Liste, drei neue", neueNachrichten(13, liste(8, 9, 10, 11, 12, 13, 14, 15, 16)), { anzahl: 3, hoechste: 16 });
check("mehr neue als das Fenster fasst: gezaehlt wird, was im Fenster steht", neueNachrichten(13, liste(20, 21, 22, 23, 24, 25, 26, 27, 28, 29)), { anzahl: 10, hoechste: 29 });

// ── ausblenden: kein Fehlalarm ──
// eine Nachricht ausgeblendet: die Liste hat neun, danach rueckt eine AELTERE ins Fenster (die Zahl steigt wieder auf zehn)
check("ausgeblendet: weniger, nichts neu", neueNachrichten(13, liste(5, 6, 7, 8, 9, 10, 11, 12, 13)), { anzahl: 0, hoechste: 13 });
check("danach rueckt eine aeltere nach: nichts neu", neueNachrichten(13, liste(3, 5, 6, 7, 8, 9, 10, 11, 12, 13)), { anzahl: 0, hoechste: 13 });
// die neueste ausgeblendet: die groesste gesehene Kennung bleibt, eine kleinere wird nicht "neu"
check("die neueste ausgeblendet: die Marke bleibt bei 13", neueNachrichten(13, liste(4, 5, 6, 7, 8, 9, 10, 11, 12)), { anzahl: 0, hoechste: 13 });
check("danach kommt eine wirklich neue", neueNachrichten(13, liste(4, 5, 6, 7, 8, 9, 10, 11, 12, 14)), { anzahl: 1, hoechste: 14 });
check("Verlauf geloescht: leer, nichts neu", neueNachrichten(13, []), { anzahl: 0, hoechste: 13 });
check("nach dem Loeschen zaehlt die naechste", neueNachrichten(13, liste(14)), { anzahl: 1, hoechste: 14 });

// ── Randfaelle ──
check("Zeile ohne Kennung ist nie neu", neueNachrichten(5, [{ id: null }, {}, { id: 6 }]), { anzahl: 1, hoechste: 6 });
check("keine Liste", neueNachrichten(5, null), { anzahl: 0, hoechste: 5 });
check("die Kennung allein entscheidet, nicht die Reihenfolge", neueNachrichten(10, liste(14, 3, 11, 9)), { anzahl: 2, hoechste: 14 });

if (fehler) { console.error(`${fehler} Fehler`); process.exit(1); }
console.log("elwosaStrom.test.mjs: ok");
