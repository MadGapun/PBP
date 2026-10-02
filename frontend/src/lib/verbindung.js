/**
 * Erreichbarkeit des PBP-Servers in der Seitenleiste — #1144.
 *
 * Vorher fragte die Oberfläche alle 30 Sekunden nach dem Verbindungsstand
 * und tat bei "keine Antwort" nichts: wurde PBP beendet, blieb die Zeile
 * "Claude Desktop: verbunden" grün stehen, und "nicht erreichbar" kam erst
 * beim Neuladen der Seite. Jetzt zählt die Oberfläche aufeinanderfolgende
 * Fehlschläge, fragt nach dem ersten bald noch einmal und zeigt nach dem
 * zweiten "PBP antwortet nicht" — und nimmt es bei der ersten Antwort
 * sofort zurück.
 *
 * Framework-frei, damit der Node-Test sie prüfen kann.
 */

/** Regelmäßige Abfrage, solange alles antwortet. */
export const ABFRAGE_MS = 30 * 1000;
/** Nach einem Fehlschlag oder solange der Server fehlt: bald noch einmal. */
export const WIEDERHOLUNG_MS = 8 * 1000;
/** So viele Fehlschläge hintereinander, bevor die Anzeige umschlägt. Einer
 *  allein kann ein Ruckler sein (der Rechner wacht gerade aus dem Ruhezustand
 *  auf, ein Neustart des Servers dauert eine Sekunde). */
export const FEHLSCHLAEGE_BIS_WEG = 2;

/** Der Zustand, mit dem die Oberfläche startet. */
export const ANFANG = Object.freeze({ fehlschlaege: 0, erreichbar: true });

/** Ergebnis einer Abfrage einarbeiten. `antwortKam` ist wahr, sobald der
 *  Server irgendetwas geantwortet hat. */
export function naechsterStand(stand, antwortKam) {
  const alt = stand || ANFANG;
  if (antwortKam) return { fehlschlaege: 0, erreichbar: true };
  const fehlschlaege = Math.min((alt.fehlschlaege || 0) + 1, FEHLSCHLAEGE_BIS_WEG);
  return { fehlschlaege, erreichbar: fehlschlaege < FEHLSCHLAEGE_BIS_WEG };
}

/** Wann die nächste Abfrage kommt. Ein Fehlschlag — auch der erste, bei dem
 *  die Anzeige noch grün bleibt — verkürzt die Wartezeit. */
export function naechsteAbfrageMs(stand) {
  if (!stand || (stand.fehlschlaege || 0) === 0) return ABFRAGE_MS;
  return WIEDERHOLUNG_MS;
}

/** Was die Zeile "Claude Desktop" zeigt: fehlt der Server, steht dort nicht
 *  der zuletzt gemeldete Stand, sondern `server_weg`. */
export function anzeigeStand(erreichbar, mcpStand) {
  if (!erreichbar) return "server_weg";
  return mcpStand || "unknown";
}

/** Die Lokale-KI-Zeile weiß ebenfalls nichts, solange der Server fehlt. */
export function kiAnzeige(erreichbar, kiStand) {
  if (!erreichbar) return "unbekannt";
  return kiStand || "not_installed";
}
