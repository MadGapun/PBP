// #1091: Eine Zahl aus einem Eingabefeld — und eine 0 bleibt 0.
//
// `Number(wert) || 1` hielt eine eingetragene 0 für "fehlt": der Regler
// der Aufnahmeschwelle sprang von 0 auf 1 zurück, zeigte 1 und
// speicherte 1. Die Vorgabe gilt nur, wenn nichts oder keine Zahl da ist.
export function zahlOderVorgabe(wert, vorgabe) {
  if (wert === "" || wert === null || wert === undefined) return vorgabe;
  const zahl = Number(wert);
  return Number.isFinite(zahl) ? zahl : vorgabe;
}
