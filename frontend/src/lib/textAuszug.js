// #1047: Ein Auszug, der die Gliederung eines Anzeigentexts behaelt.
//
// `textExcerpt` in utils.js fasst jeden Leerraum zu einem Leerzeichen
// zusammen — richtig fuer einen Einzeiler auf der Karte, falsch fuer eine
// Detailansicht mit `whitespace-pre-wrap`: dort gingen Absaetze und Listen
// verloren, obwohl sie gespeichert waren.

export function gegliederterAuszug(value, max = 2000) {
  const text = String(value || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((zeile) => zeile.replace(/[ \t\f\v ]+/g, " ").trim())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max).trimEnd()}...`;
}
