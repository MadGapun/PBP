/**
 * Was ist ein Text, der mit "/" beginnt? (v1.7.120)
 *
 * In PBP heisst "/name" IMMER: ein Workflow, dessen Anleitung der Server
 * liefert (`/api/workflow-prompt/<name>`). Claude Desktop kennt diese
 * Namen NICHT als Schraegstrich-Befehle — ein roher "/dokumente_verarbeiten"
 * kommt dort als "diesen Skill gibt es nicht" an. Der rohe Text ist also
 * nie ein brauchbarer Ersatz fuer die Anleitung.
 *
 * Gemeldet am 18.09.2026: der Knopf "Dokumente verarbeiten" bekam ein 404,
 * kopierte den rohen Befehl und meldete dreimal hintereinander etwas
 * anderes, darunter "Anleitung kopiert!".
 *
 * Zwei Dinge regelt dieses Modul:
 *
 * 1. `zerlegePrompt` — Name UND Argumente. Bis hierher wurden Argumente
 *    wie `stelle="..." firma="..."` beim Aufloesen weggeworfen: der
 *    terminspezifische Knopf im Kalender lieferte die allgemeine
 *    Anleitung. Der Endpunkt nimmt sie seit #706 als Query entgegen.
 * 2. `werkzeugAufruf` — ein WERKZEUG ist kein Workflow. Wer Claude ein
 *    Werkzeug aufrufen lassen will, schreibt einen Satz, keinen
 *    Schraegstrich-Befehl.
 */

const ARGUMENT = /([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"/g;

export function zerlegePrompt(roh) {
  const text = String(roh || "").trim();
  if (!text.startsWith("/")) {
    return { istWorkflow: false, text };
  }
  const name = text.slice(1).split(/\s+/)[0] || "";
  const argumente = {};
  for (const treffer of text.matchAll(ARGUMENT)) {
    argumente[treffer[1]] = treffer[2];
  }
  return { istWorkflow: Boolean(name), name, argumente, text };
}

export function workflowPfad(zerlegt) {
  const basis = `/api/workflow-prompt/${encodeURIComponent(zerlegt.name)}`;
  const paare = Object.entries(zerlegt.argumente || {}).filter(([, wert]) => wert !== "");
  if (!paare.length) return basis;
  const query = paare
    .map(([schluessel, wert]) => `${encodeURIComponent(schluessel)}=${encodeURIComponent(wert)}`)
    .join("&");
  return `${basis}?${query}`;
}

/**
 * Ein Werkzeugaufruf als Satz. Leere Werte fallen weg — ein
 * `bewerbung_id=""` saehe nach einer Angabe aus und waere keine.
 */
export function werkzeugAufruf(werkzeug, argumente = {}, nachsatz = "") {
  const teile = Object.entries(argumente)
    .filter(([, wert]) => wert !== undefined && wert !== null && String(wert) !== "")
    .map(([schluessel, wert]) => `${schluessel}="${String(wert).replace(/"/g, "'")}"`);
  const aufruf = `${werkzeug}(${teile.join(", ")})`;
  return `Rufe in PBP das Werkzeug ${aufruf} auf.${nachsatz ? ` ${nachsatz}` : ""}`;
}

export function fehlerText(name) {
  return (
    `Die Anleitung "${name}" konnte nicht geladen werden — es wurde NICHTS kopiert. `
    + "Läuft PBP noch? Sonst bitte melden (Schnellzugriff „Problem melden“)."
  );
}
