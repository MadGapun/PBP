// #1035: ein Score hat hoechstens eine Nachkommastelle — in jeder Anzeige.
//
// Gemeldet stand `6.199999999999999` auf der Stellenkarte: der Wert kam
// ungerundet vom Server, und sechs Stellen im Frontend gaben ihn roh aus.
// Der Server rundet inzwischen selbst; diese Funktion haelt die Anzeige
// trotzdem fest, damit ein kuenftiger ungerundeter Weg nicht wieder als
// Zahlensalat auf der Karte landet.

/** Der Score als Zahl mit hoechstens einer Nachkommastelle, sonst 0. */
export function scoreWert(wert) {
  const zahl = Number(wert);
  if (!Number.isFinite(zahl)) return 0;
  return Math.round(zahl * 10) / 10;
}

/** Der Score zur Anzeige: "18,7", "18", "0". */
export function scoreText(wert) {
  return scoreWert(wert).toLocaleString("de-DE", { maximumFractionDigits: 1 });
}
