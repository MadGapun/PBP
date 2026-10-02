/**
 * Datum und Uhrzeit in Ortszeit — v1.7.146 (#1140).
 *
 * `new Date().toISOString()` liefert UTC. Wer daraus ein Datum oder eine
 * Uhrzeit für Eingabefelder und Termine schneidet, rechnet falsch: In
 * Deutschland wurde aus „14:00, 60 Minuten“ im Sommer das Terminende 13:00
 * (Ende vor Beginn, ungültige ICS-Datei, keine Kollisionsprüfung), und
 * zwischen 00:00 und 02:00 galt „heute“ noch als „gestern“.
 *
 * Alles hier arbeitet mit den lokalen Bestandteilen (Jahr, Monat, Tag,
 * Stunde, Minute). Framework-frei, damit der Node-Test es prüfen kann.
 */

const zwei = (n) => String(n).padStart(2, "0");

/** „2026-10-01“ — das lokale Datum von `d` (Vorgabe: jetzt). */
export function lokalesDatum(d = new Date()) {
  return `${d.getFullYear()}-${zwei(d.getMonth() + 1)}-${zwei(d.getDate())}`;
}

/** „2026-10-01T14:00“ — die lokale Zeit von `d` in der Form der Eingabefelder. */
export function lokaleDatumZeit(d = new Date()) {
  return `${lokalesDatum(d)}T${zwei(d.getHours())}:${zwei(d.getMinutes())}`;
}

/**
 * Das Ende eines Termins: `beginn` („2026-10-01T14:00“, Ortszeit) plus
 * `dauerMin` Minuten, wieder in Ortszeit. `null`, wenn der Beginn nicht
 * lesbar ist, nur ein Datum (ganztägig) oder keine Dauer da ist.
 */
export function terminEnde(beginn, dauerMin) {
  const dauer = Number(dauerMin);
  if (!beginn || !dauer || dauer <= 0) return null;
  const text = String(beginn).trim();
  if (text.length <= 10) return null; // nur ein Datum: ganztägig
  const start = new Date(text); // Datum mit Uhrzeit ohne Zone gilt als Ortszeit
  if (Number.isNaN(start.getTime())) return null;
  return lokaleDatumZeit(new Date(start.getTime() + dauer * 60 * 1000));
}
