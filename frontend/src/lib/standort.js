/**
 * Der Satz zum Standort: von wo aus PBP Entfernungen rechnet (#1090, #1235).
 *
 * Eigenes Modul, damit der Satz ohne Browser prüfbar ist (`standort.test.mjs`).
 * Die Karte (`StandortKarte.jsx`) zeigt ihn nur an.
 */
export function standortSatz(befund) {
  if (!befund) return "";
  if (!befund.ort && !befund.profil_wohnort) {
    return "Kein Standort: PBP rechnet keine Entfernungen. Trage deinen Wohnort im Profil ein oder setze hier einen Ort.";
  }
  if (!befund.aufgeloest) {
    const ort = befund.ort || befund.profil_wohnort;
    // #1235: den Ort gibt es mehrfach — PBP rät nicht, und der Mensch kann etwas tun.
    if (befund.mehrdeutig?.length) {
      return `„${ort}“ gibt es mehrfach in Deutschland (${befund.mehrdeutig.join("; ")}) — Entfernungen fehlen, bis klar ist, welcher gemeint ist. Ergänze die PLZ, etwa „12345 ${ort}“.`;
    }
    return `„${ort}“ ist noch nicht aufgelöst — Entfernungen fehlen, bis der Ort gefunden ist. Versuche PLZ und Ort.`;
  }
  if (befund.quelle === "eigene") {
    return `Entfernungen werden ab „${befund.ort}“ gerechnet (von dir gesetzt).`;
  }
  return `Entfernungen werden ab deinem Wohnort „${befund.ort}“ gerechnet (aus dem Profil).`;
}
