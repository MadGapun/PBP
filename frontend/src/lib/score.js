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

// H24 (#1087 G4): derselbe Satz wie `services/punkte.SCORE_BEDEUTUNG`,
// hier mit echten Umlauten. Ein Test vergleicht beide Fassungen.
export const SCORE_BEDEUTUNG =
  "Die Punkte zeigen, wie gut eine Anzeige deine Suchbegriffe trifft " +
  "(Pflicht- und Wunschbegriffe, abzüglich Ausschlussbegriffe). Mehr " +
  "ist besser. Sie sind kein Urteil darüber, ob du passt — dein " +
  "Lebenslauf geht nicht ein, und Ort, Gehalt und Arbeitsmodell stehen " +
  "getrennt daneben. Es gibt keine Prozentangabe und keine feste Skala; " +
  "wo ein Höchstwert erreichbar ist, steht er dabei.";

// C96 (#1087 C1): EIN Wert je Stelle an allen Orten. Der Server setzt
// `punkte` (services/punkte.py: Fachwert mit Begriffs-Reglern, ohne die
// Rahmen-Regler) an Liste, Dashboard, Timeline und Fit-Dialog. Wo er
// fehlt (Altantwort), gilt der Fachwert, dann der gespeicherte Wert.

/** Die Punkte einer Stelle als Zahl. */
export function punkteWert(job) {
  if (!job) return 0;
  if (job.punkte !== undefined && job.punkte !== null) return scoreWert(job.punkte);
  if (job.fach_score !== undefined && job.fach_score !== null) return scoreWert(job.fach_score);
  return scoreWert(job.score);
}

/** "7 von 26 Punkten", "7 Punkte", "1 Punkt" — mit Skala, wo sie erreichbar ist. */
export function punkteText(job) {
  const wert = punkteWert(job);
  const max = Number(job?.punkte_max);
  const zahl = scoreText(wert);
  if (Number.isFinite(max) && max > 0 && wert >= 0 && wert <= max) {
    return `${zahl} von ${scoreText(max)} Punkten`;
  }
  return wert === 1 ? "1 Punkt" : `${zahl} Punkte`;
}

/** Summe einer Faktorenliste (fuer den Test, dass sie zur Zahl passt). */
export function faktorSumme(faktoren) {
  let s = 0;
  for (const v of Object.values(faktoren || {})) {
    const n = Number(v);
    if (Number.isFinite(n)) s += n;
  }
  return scoreWert(s);
}
