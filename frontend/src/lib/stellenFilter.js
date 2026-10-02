/**
 * Filter der Stellenliste: Untergrenze, Speicherung und Streifen — #1158.
 *
 * Der Befund: der Stellen-Tab zeigte 2 von 4 aktiven Stellen. Zwei Stellen hatten einen negativen
 * Punktestand (ein Abzug für Entfernung beziehungsweise Gehalt), und die Voreinstellung "Punkte ≥ 0"
 * schluckte sie, ohne dass der Mensch je einen Filter gesetzt hätte. Das Feld "Punkte ≥" nahm keine
 * negativen Werte an, der Streifen nannte den wirksamen Filter nicht, und "Filter zurücksetzen" schaltete
 * Filter AN, statt sie auszuschalten.
 *
 * Hier stehen die Teile, die ohne Oberfläche prüfbar sind: wann eine Untergrenze gilt, was gespeichert
 * wird, und wie der Streifen jeden wirksamen Filter mit seiner Zahl nennt.
 *
 * Framework-frei, damit der Node-Test sie prüfen kann.
 */

/** Unter diesem Schlüssel merkt sich der Browser die Filter der Stellenliste. */
export const SPEICHER_SCHLUESSEL = "pbp-stellen-filter-v1";

/** Welcher Filter der Seite heißt beim Server wie. */
export const FILTER_SERVERNAMEN = {
  query: "query",
  source: "source",
  minScore: "min_score",
  remote: "remote",
  salaryOnly: "nur_mit_gehalt",
  employmentType: "employment_type",
  arbeitsumfang: "arbeitsumfang",
  hideApplied: "beworbene_ausblenden",
  missingDescriptionOnly: "nur_ohne_beschreibung",
  pruefstand: "pruefstand",
  rahmenAusblenden: "rahmen_ausblenden",
  schwelleAusblenden: "schwelle_ausblenden",
};

/** Gilt eine Untergrenze? Auch 0 und negative Werte gelten: "0" ist eine Entscheidung, "" ist keine. */
export function minScoreGesetzt(wert) {
  const text = String(wert ?? "").trim();
  return text !== "" && Number.isFinite(Number(text));
}

/** Der Wert für den Server-Parameter `min_score`, oder `null`, wenn keine Untergrenze gilt. */
export function minScoreParameter(wert) {
  return minScoreGesetzt(wert) ? String(Number(String(wert).trim())) : null;
}

// Felder, die nicht gemerkt werden: der Suchtext (ein vergessener Suchtext würde die Liste beim nächsten Öffnen
// leise verkürzen) und die Ansicht (aktiv/aussortiert ist Navigation, kein Filter).
const NICHT_GEMERKT = ["query", "view"];

/** Was in den Speicher des Browsers kommt: alle Filter bis auf Suchtext und Ansicht. */
export function filterFuerSpeicher(filters) {
  const rest = {};
  for (const [schluessel, wert] of Object.entries(filters || {})) {
    if (!NICHT_GEMERKT.includes(schluessel)) rest[schluessel] = wert;
  }
  return JSON.stringify(rest);
}

/**
 * Aus dem gemerkten Text wieder ein Filterobjekt. Nur bekannte Felder, nur der Typ der Vorgabe —
 * alles andere (kaputter Text, ein Feld aus einer älteren Fassung, ein falscher Typ) fällt auf die
 * Vorgabe zurück. Suchtext und Ansicht kommen nie aus dem Speicher.
 */
export function filterAusSpeicher(text, standard) {
  const ergebnis = { ...standard };
  let roh;
  try {
    roh = JSON.parse(text);
  } catch (err) {
    return ergebnis;
  }
  if (!roh || typeof roh !== "object" || Array.isArray(roh)) return ergebnis;
  for (const schluessel of Object.keys(standard)) {
    if (NICHT_GEMERKT.includes(schluessel) || !(schluessel in roh)) continue;
    const wert = roh[schluessel];
    if (typeof wert === typeof standard[schluessel]) ergebnis[schluessel] = wert;
  }
  return ergebnis;
}

/** Zu jedem wirksamen Filter die Zahl der Stellen, die er allein verbirgt (vom Server gerechnet). */
export function mitZahlen(aktiv, verborgen) {
  const zahlen = verborgen || {};
  return aktiv.map((filter) => {
    const n = Number(zahlen[FILTER_SERVERNAMEN[filter.schluessel]]);
    const anzahl = Number.isFinite(n) && n > 0 ? n : 0;
    return { ...filter, anzahl, text: anzahl > 0 ? `${filter.text} (${anzahl})` : filter.text };
  });
}

/**
 * Wie viele offene Stellen fehlen, weil MEHRERE Filter zugleich sie verbergen. Eine solche Stelle steht
 * bei keinem einzelnen Filter in der Zahl; ohne diese Angabe ginge die Rechnung des Streifens nicht auf.
 * Die Beworbenen zählen nicht mit: sie sind keine offenen Stellen.
 */
export function mehrereFilter(offenVerborgen, verborgen) {
  let summe = 0;
  for (const [name, n] of Object.entries(verborgen || {})) {
    if (name !== "beworbene_ausblenden") summe += Number(n) || 0;
  }
  return Math.max(0, Number(offenVerborgen || 0) - summe);
}
