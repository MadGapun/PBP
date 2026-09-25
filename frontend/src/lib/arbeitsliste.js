/**
 * Eine Arbeitsliste fuer Offenes — G64 (#1087 D1).
 *
 * Bis v1.7.133 stand dieselbe Nachfassung im Dashboard-Block "Offen", im
 * Aufgaben-Tab, unter "Offene Aktionen" im Bewerbungen-Tab und im
 * Kalender — unter fuenf Namen. Massgeblich ist jetzt der Aufgaben-Tab;
 * Dashboard und Bewerbungen zeigen eine VORSCHAU von hoechstens fuenf
 * Zeilen und verweisen auf "Alle Aufgaben". Der Kalender zeigt nur echte
 * Termine.
 */

export const VORSCHAU_ZEILEN = 5;
export const ALLE_AUFGABEN = "Alle Aufgaben";

/**
 * Nimmt aus Gruppen (in ihrer Reihenfolge) hoechstens `max` Zeilen.
 * Liefert `{ gruppen, gezeigt, weitere }` — `gruppen` in derselben Form
 * wie die Eingabe, leere Gruppen fallen weg.
 */
export function vorschau(gruppen, reihenfolge, max = VORSCHAU_ZEILEN) {
  const aus = {};
  let rest = max;
  let gesamt = 0;
  for (const key of reihenfolge) {
    const zeilen = gruppen?.[key] || [];
    gesamt += zeilen.length;
    if (rest <= 0 || !zeilen.length) continue;
    aus[key] = zeilen.slice(0, rest);
    rest -= aus[key].length;
  }
  const gezeigt = max - rest;
  return { gruppen: aus, gezeigt, weitere: gesamt - gezeigt };
}

/** Knopftext: nennt, wie viele nicht in der Vorschau stehen. */
export function alleAufgabenText(weitere) {
  return weitere > 0 ? `${ALLE_AUFGABEN} (${weitere} weitere)` : ALLE_AUFGABEN;
}
