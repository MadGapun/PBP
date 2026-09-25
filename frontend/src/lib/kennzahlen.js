// G61 (#1087 B2-B4): Kennzahlen mit fester Bedeutung.
//
// Bis v1.7.135 waehlte "Bew. / Woche" die Perspektive beim Laden per
// Zufall (fuenf verschiedene Rechnungen unter einem Etikett), die
// Top-Stellen zeigten Stellen mit negativen Punkten, die der Stellen-Tab
// ausblendet, und die Gehaltskacheln "0 – 0 EUR", wo keine Daten waren.

const TAG = 1000 * 60 * 60 * 24;

// Zwei Ansichten, beschriftet; die erste ist die Vorgabe.
export const WOCHEN_ANSICHTEN = [
  { id: "gesamt", label: "seit der ersten Bewerbung" },
  { id: "30_tage", label: "letzte 30 Tage" },
];

function zahl(v) {
  return new Intl.NumberFormat("de-DE", {
    minimumFractionDigits: v > 0 && v < 10 ? 1 : 0,
    maximumFractionDigits: v > 0 && v < 10 ? 1 : 0,
  }).format(v);
}

// Ø Bewerbungen je Woche. `zeitpunkte` sind Millisekunden.
export function bewerbungenProWoche(zeitpunkte, ansicht = "gesamt", jetzt = Date.now()) {
  const gueltig = (zeitpunkte || []).filter((t) => Number.isFinite(t));
  if (!gueltig.length) {
    return { wert: "—", notiz: "Noch keine Bewerbung mit Datum" };
  }
  if (ansicht === "30_tage") {
    const anzahl = gueltig.filter((t) => jetzt - t <= 30 * TAG).length;
    return { wert: zahl(anzahl / (30 / 7)), notiz: "Ø der letzten 30 Tage" };
  }
  const erste = Math.min(...gueltig);
  const tage = Math.max(7, Math.ceil((jetzt - erste) / TAG) + 1);
  return { wert: zahl(gueltig.length / (tage / 7)), notiz: "Ø seit der ersten Bewerbung" };
}

function punkte(job) {
  const p = Number(job?.punkte ?? job?.score);
  return Number.isFinite(p) ? p : 0;
}

// Top-Stellen: was der Stellen-Tab zeigt (die Liste kommt mit dessen
// Vorgaben vom Server), dazu nur Stellen mit Punkten ueber 0.
export function topStellen(jobs, max = 6) {
  return (jobs || [])
    .filter((j) => punkte(j) > 0)
    .sort((a, b) => punkte(b) - punkte(a))
    .slice(0, max);
}

// Ein Gehaltswert gilt nur, wenn er groesser als 0 ist.
export function gehaltsWert(v) {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
}

export const KEIN_GEHALT = "Keine der Stellen nennt ein Gehalt";
