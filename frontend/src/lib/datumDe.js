// #1412 D8: ein deutsches Datumsfeld. Ein <input type="date"> zeigt das Format
// der Browsersprache (mm/dd/yyyy bei englischem Browser); die Oberflaeche ist
// deutsch, also liest und zeigt dieses Feld TT.MM.JJJJ und gibt ISO weiter.

/** "01.12.2026" (auch "1.12.26", "1.12.") -> "2026-12-01"; sonst null. */
export function deZuIso(text, heute = new Date()) {
  const m = String(text || "").trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})?$/);
  if (!m) return null;
  const tag = Number(m[1]);
  const monat = Number(m[2]);
  let jahr = m[3] ? Number(m[3]) : heute.getFullYear();
  if (m[3] && m[3].length === 2) jahr += 2000;
  const d = new Date(Date.UTC(jahr, monat - 1, tag));
  if (d.getUTCFullYear() !== jahr || d.getUTCMonth() !== monat - 1 || d.getUTCDate() !== tag) return null;
  return `${String(jahr).padStart(4, "0")}-${String(monat).padStart(2, "0")}-${String(tag).padStart(2, "0")}`;
}

/** "2026-12-01" -> "01.12.2026"; sonst "". */
export function isoZuDe(iso) {
  const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "";
}
