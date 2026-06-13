// #701: Relative Datumslabels (heute/morgen/uebermorgen/in X Tagen) muessen
// auf KALENDERTAGEN in Europe/Berlin rechnen — nicht auf 24h-Schritten und
// nicht abhaengig von der System-Zeitzone des Browsers.
//
// Zwei Fehlerquellen, die das hier vermeidet:
//  1. 24h-Schritte: Ein Termin in 47h ist "uebermorgen", nicht "morgen".
//     Wird durch Kalendertag-Differenz geloest (Uhrzeit-unabhaengig).
//  2. Zeitzone: Rechnet man Kalendertage in der lokalen Browser-Zeit und der
//     Rechner steht nicht auf Berlin (oder ein Timestamp ist UTC), kippt das
//     Label um Mitternacht UTC statt um Mitternacht Berlin. Deshalb werden die
//     Kalendertage explizit in Europe/Berlin bestimmt.

const BERLIN_TZ = "Europe/Berlin";

// Liefert das Kalenderdatum (Jahr/Monat/Tag), an dem `date` in Europe/Berlin
// liegt — unabhaengig davon, in welcher Zeitzone der ausfuehrende Rechner steht.
function berlinYMD(date) {
  // en-CA formatiert als YYYY-MM-DD, robust und sprachunabhaengig parsebar.
  const s = new Intl.DateTimeFormat("en-CA", {
    timeZone: BERLIN_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
  const [y, m, d] = s.split("-").map(Number);
  return { y, m, d };
}

// Ganzzahlige Differenz in Kalendertagen (Europe/Berlin) zwischen `target` und
// `ref`. Heute = 0, morgen = 1, gestern = -1. Vollstaendig Uhrzeit-unabhaengig.
export function berlinDayDiff(target, ref = new Date()) {
  const a = berlinYMD(target instanceof Date ? target : new Date(target));
  const b = berlinYMD(ref instanceof Date ? ref : new Date(ref));
  // Beide Kalendertage auf 00:00 UTC abbilden — so ist die Differenz exakt
  // ganzzahlig und frei von DST-Spruengen (Sommer-/Winterzeit), weil beide
  // Bezugspunkte denselben (UTC-)Nullpunkt haben.
  const ua = Date.UTC(a.y, a.m - 1, a.d);
  const ub = Date.UTC(b.y, b.m - 1, b.d);
  return Math.round((ua - ub) / 86400000);
}

// Menschenlesbares relatives Label fuer einen Termin/ein Datum.
export function relativeDayLabel(target, ref = new Date()) {
  const diff = berlinDayDiff(target, ref);
  if (diff === 0) return "heute";
  if (diff === 1) return "morgen";
  if (diff === -1) return "gestern";
  if (diff > 1) return `in ${diff} Tagen`;
  return `vor ${Math.abs(diff)} Tagen`;
}
