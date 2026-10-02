/**
 * Speicher & Downloads — was die Oberfläche aus /api/speicher macht (#1131, v1.8).
 *
 * Framework-frei, damit der Node-Test die Regeln prüfen kann: Größen mit „oder mehr“, die Zusammenfassung oben,
 * die Schritte des Bereinigens (Auswahl → Vorschau → Ergebnis) und die Summe einer Auswahl.
 *
 * Grundsatz: gelöscht wird nie ohne Bestätigung, und was einem anderen Programm gehört, wird nur gezeigt und erklärt.
 */
import { groesseText } from "./autoUpdate.js";

/** Die Töne der Abzeichen je Urheber. */
export const URHEBER_TON = {
  pbp: "sky",
  komponente: "neutral",
  du: "amber",
  fremd: "neutral",
};

/** „2,4 MB“, bei einer abgebrochenen Messung „2,4 MB oder mehr“. */
export function ortGroesse(ort) {
  if (!ort || ort.nichts_vorhanden) return "nichts vorhanden";
  const text = groesseText(ort.bytes);
  return ort.vollstaendig === false ? `${text} oder mehr` : text;
}

/** Der eine Satz oben über der Liste. */
export function zusammenfassung(u) {
  if (!u || !Array.isArray(u.orte)) return "";
  const eigen = groesseText(u.gesamt_bytes);
  const fremd = Number(u.gesamt_fremd_bytes) > 0 ? ` Dazu kommen ${groesseText(u.gesamt_fremd_bytes)} bei anderen Programmen, die PBP nutzt.` : "";
  return `PBP und deine Dateien belegen zusammen ${eigen}.${fremd}`;
}

/** Gibt es etwas, das sich bereinigen lässt? Fremdes zählt nie. */
export function bereinigbar(ort, aktionen) {
  if (!ort || ort.urheber === "fremd") return [];
  return (ort.aktionen || []).filter((id) => aktionen && aktionen[id]);
}

/**
 * In welchem Schritt steht der Dialog, nach der Antwort von POST /api/speicher/bereinigen?
 *   auswahl   → der Mensch wählt aus (Liste mit Häkchen)
 *   vorschau  → Zahlen und Dateien, dann bestätigen
 *   ergebnis  → fertig (bereinigt, teilweise)
 *   leer      → nichts zu bereinigen
 *   fehler    → unbekannt oder nichts gewählt
 */
export function schrittAus(antwort) {
  switch (antwort?.status) {
    case "auswahl": return "auswahl";
    case "vorschau": return "vorschau";
    case "bereinigt":
    case "teilweise": return "ergebnis";
    case "nichts": return "leer";
    default: return "fehler";
  }
}

/** Summe der gewählten Einträge in Bytes. */
export function auswahlSumme(kandidaten, gewaehlt) {
  if (!Array.isArray(kandidaten)) return 0;
  const set = gewaehlt instanceof Set ? gewaehlt : new Set(gewaehlt || []);
  return kandidaten.filter((k) => set.has(k.id)).reduce((s, k) => s + (Number(k.bytes) || 0), 0);
}

/** Der Satz über dem Bestätigen-Knopf: Zahl und Größe dessen, was weg soll. */
export function loeschSatz(antwort, gewaehlt) {
  const n = antwort?.braucht_auswahl && gewaehlt ? gewaehlt.size : antwort?.anzahl || 0;
  const b = antwort?.braucht_auswahl && gewaehlt ? auswahlSumme(antwort.kandidaten, gewaehlt) : antwort?.bytes || 0;
  return `${n} ${n === 1 ? "Eintrag" : "Einträge"}, zusammen ${groesseText(b)}, ${n === 1 ? "wird" : "werden"} gelöscht.`;
}

/** Kann der Mensch löschen? Bei Aktionen mit Auswahl erst, wenn etwas gewählt ist. */
export function darfLoeschen(antwort, gewaehlt) {
  if (!antwort) return false;
  if (antwort.braucht_auswahl) return Boolean(gewaehlt && gewaehlt.size > 0);
  return (antwort.anzahl || 0) > 0;
}
