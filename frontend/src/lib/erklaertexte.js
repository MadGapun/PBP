// Lange Erklärtexte lassen sich einklappen (#1170 U11).
//
// Befund der Bedienungsprüfung: einzelne Hinweise lassen sich schließen („Nicht mehr anzeigen“), die langen Erklärtexte der
// Seiten nicht — die Willkommenskarte „So arbeiten Dashboard und Claude zusammen“, der Sicherheitsabsatz bei den Updates, der
// Erklärabsatz zur Fahrstrecke, die Einleitung von Speicher & Downloads. Wer PBP kennt, liest sie bei jedem Besuch wieder.
//
// Zwei Ebenen, beide im Browser gemerkt (eine Bequemlichkeit je Gerät, kein Datenbestand):
//   * der Schalter „Erklärtexte zeigen“ unter Einstellungen › Erscheinungsbild (Vorgabe an): ob ein Erklärtext, zu dem du nichts
//     entschieden hast, aufgeklappt steht;
//   * die Wahl je Erklärtext (auf oder zu): sie geht dem Schalter vor. Ändert man den Schalter, fallen die Einzelwahlen weg —
//     eine ausdrückliche Wahl „für alle“ gilt für alle.
// Ohne Browserspeicher (privater Modus) bleibt es bei der Vorgabe: aufgeklappt, nichts geht verloren.

export const ALLE_SCHLUESSEL = "pbp-erklaertexte";
export const EINZEL_PRAEFIX = "pbp-erklaerung-";
export const EREIGNIS = "pbp-erklaertexte-geaendert";

/** Aus dem gemerkten Text des Schalters: nur „0“ heißt eingeklappt; alles andere (auch nichts) ist die Vorgabe, aufgeklappt. */
export function alleZeigenAusText(text) {
  return text !== "0";
}

/** Aus dem gemerkten Text eines einzelnen Erklärtexts: true (auf), false (zu) oder null (keine Wahl). */
export function einzelnAusText(text) {
  if (text === "auf") return true;
  if (text === "zu") return false;
  return null;
}

/** Steht der Erklärtext aufgeklappt? Die Wahl für ihn geht dem Schalter vor. */
export function aufgeklappt(alleZeigen, einzeln) {
  if (einzeln === null || einzeln === undefined) return Boolean(alleZeigen);
  return Boolean(einzeln);
}

function speicher() {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function leseAlle() {
  try {
    return alleZeigenAusText(speicher()?.getItem(ALLE_SCHLUESSEL) ?? null);
  } catch {
    return true;
  }
}

export function leseEinzeln(id) {
  try {
    return einzelnAusText(speicher()?.getItem(EINZEL_PRAEFIX + id) ?? null);
  } catch {
    return null;
  }
}

function melden() {
  try {
    window.dispatchEvent(new CustomEvent(EREIGNIS));
  } catch {
    // ohne Fenster nichts zu melden
  }
}

export function schreibeEinzeln(id, offen) {
  try {
    speicher()?.setItem(EINZEL_PRAEFIX + id, offen ? "auf" : "zu");
  } catch {
    // Browserspeicher gesperrt: die Wahl gilt nur fuer diese Ansicht
  }
  melden();
}

/** Der Schalter unter Erscheinungsbild. Die Einzelwahlen fallen weg: „für alle“ gilt für alle. */
export function schreibeAlle(zeigen) {
  try {
    const s = speicher();
    if (s) {
      s.setItem(ALLE_SCHLUESSEL, zeigen ? "1" : "0");
      const weg = [];
      for (let i = 0; i < s.length; i += 1) {
        const k = s.key(i);
        if (k && k.startsWith(EINZEL_PRAEFIX)) weg.push(k);
      }
      weg.forEach((k) => s.removeItem(k));
    }
  } catch {
    // Browserspeicher gesperrt
  }
  melden();
}
